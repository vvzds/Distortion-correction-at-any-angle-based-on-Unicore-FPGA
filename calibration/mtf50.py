# -*- coding: utf-8 -*-
"""
mtf50.py —— MTF50 测量（斜棱/斜刃法，赛题 SFR 判据工具）
================================================================
图卡 : 黑白刀刃斜边卡，刃倾角 5~15 度（打印或采购 SFR 卡）
用法 : python mtf50.py IMG.png --roi x y w h
       ROI 框住刃及其两侧渐变带（各留 >=40px），ROI 不可含其他边缘
输出 : MTF 曲线数据 mtf_curve.csv + MTF50（cy/px，cycles/pixel）
       同卡同 ROI 矫正前后各测一次，MTF50 越高清晰度越好
"""
import cv2
import argparse
import numpy as np


def edge_angle(g):
    """刃主方向角：图像梯度协方差矩阵主特征向量（刃方向）"""
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    m = (np.hypot(gx, gy) > np.percentile(np.hypot(gx, gy), 90))
    X = np.stack([gx[m], gy[m]], 1)
    _, _, V = np.linalg.svd(X - X.mean(0), full_matrices=False)
    return V[0]                                    # 梯度主方向 = 刃法向


def main():
    ap = argparse.ArgumentParser(description='斜棱法 MTF50')
    ap.add_argument('img')
    ap.add_argument('--roi', nargs=4, type=int, required=True,
                    metavar=('x', 'y', 'w', 'h'))
    a = ap.parse_args()

    x, y, w, h = a.roi
    g = cv2.cvtColor(cv2.imread(a.img), cv2.COLOR_BGR2GRAY)[y:y+h, x:x+w].astype(np.float64)
    nrm = edge_angle(g)                            # 刃法向单位向量
    # ---- 沿法向投影：每个像素 -> (投影位置, 灰度) ----
    ys, xs = np.mgrid[0:g.shape[0], 0:g.shape[1]]
    pos = (xs * nrm[0] + ys * nrm[1]).ravel()
    val = g.ravel()
    o = np.argsort(pos)
    pos, val = pos[o], val[o]
    # ---- oversample: 1/8 像素 bin 聚合 -> ESF ----
    grid = np.arange(pos[0], pos[-1], 0.125)
    idx = np.clip(np.searchsorted(pos, grid), 1, len(pos) - 1)
    esf = np.array([val[i-1:i+1].mean() if pos[idx[i]-1] > pos[idx[i]-2] else val[idx[i]]
                    for i in range(len(grid))])
    # 平滑与细化：线性插值去空 bin
    ok = ~np.isnan(esf)
    esf = np.interp(grid, grid[ok], esf[ok])
    esf = cv2.GaussianBlur(esf.reshape(-1, 1), (1, 5), 0).ravel()   # 轻度去噪
    # ---- 差分 -> LSF（汉宁窗抑制边界效应）----
    lsf = np.diff(esf)
    win = np.hanning(len(lsf))
    lsf = lsf * win
    # ---- FFT -> MTF，归一化（0 频=1）----
    mtf = np.abs(np.fft.rfft(lsf))
    mtf = mtf / mtf[0]
    # 频轴: 采样间隔 0.125px -> 频率分辨率 1/(0.125*N)
    freq = np.fft.rfftfreq(len(lsf), d=0.125)      # cy/px
    # ---- MTF50 插值 ----
    m50 = None
    for i in range(1, len(mtf)):
        if mtf[i-1] >= 0.5 > mtf[i]:
            t = (mtf[i-1] - 0.5) / (mtf[i-1] - mtf[i])
            m50 = freq[i-1] + t * (freq[i] - freq[i-1])
            break
    np.savetxt('mtf_curve.csv', np.stack([freq, mtf], 1), delimiter=',',
               header='freq_cy_per_px,mtf', comments='')
    print(f'MTF50 = {m50:.4f} cy/px' if m50 else 'MTF50 未找到（刃太软/ROI 不当）')
    print('曲线已存 mtf_curve.csv（同图卡同 ROI 矫正前后对比）')


if __name__ == '__main__':
    main()
