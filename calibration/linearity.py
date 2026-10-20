# -*- coding: utf-8 -*-
"""
linearity.py —— 直线度误差测量（赛题判据工具：直线弯曲/边缘拉伸）
================================================================
图卡 : 网格线 / 倾斜黑色方块（打印，含 5~15 度倾斜直线为佳）
用法 : python linearity.py IMG.png [--minlen 300] [--show]
输出 : 每条检测长直线的最大偏差(px)与全长，末行给全图最大值
       矫正后复测同图卡：max 偏差应 <=1~2px 且边缘无断裂
原理 : Hough 检测直线参考方向 -> 沿法向逐行找边缘亚像素中心
       -> 全点最小二乘 fitLine -> 各点到理想直线垂距 -> max
"""
import cv2
import argparse
import numpy as np


def subpix_edge_centroid(g, p0, nrm, half=25):
    """沿直线 p0 处，法向 ±half 像素带内取灰度质心（亚像素边缘中心）"""
    px, py = p0
    samples = []
    for d in range(-half, half + 1):
        x, y = int(round(px + nrm[0] * d)), int(round(py + nrm[1] * d))
        if 0 <= y < g.shape[0] and 0 <= x < g.shape[1]:
            samples.append((d, g[y, x]))
    if len(samples) < 10:
        return None
    s = np.diff(np.array([v for _, v in samples]))           # 灰度跳变检测
    i = int(np.argmax(np.abs(s)))                            # 最强台阶
    w = np.array([abs(v) for v in s[max(0, i-2):i+3]])       # 台阶邻域加权
    ds = np.array([d for d, _ in samples][max(0, i-2):i+3])
    if w.sum() == 0:
        return None
    d0 = float((w * ds).sum() / w.sum())                     # 加权中心=亚像素
    return (px + nrm[0] * d0, py + nrm[1] * d0)


def main():
    ap = argparse.ArgumentParser(description='直线度误差测量')
    ap.add_argument('img')
    ap.add_argument('--minlen', type=int, default=300, help='纳入统计的最短直线长度 px')
    ap.add_argument('--show', action='store_true', help='弹出标注窗口（q 退出）')
    a = ap.parse_args()

    img = cv2.imread(a.img)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(g, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 720, 80,
                            minLineLength=a.minlen, maxLineGap=5)
    assert lines is not None and len(lines), '未检测到长直线，检查图卡/对比度/--minlen'

    worst = 0.0
    out = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    for ln in lines[:, 0]:
        x1, y1, x2, y2 = ln
        d = np.array([x2 - x1, y2 - y1], np.float64)
        L = np.linalg.norm(d)
        if L < a.minlen:
            continue
        t = d / L
        nrm = np.array([-t[1], t[0]])                        # 直线法向
        pts = []
        for s in np.arange(0, L, 2.0):                       # 沿线每 2px 取边缘中心
            p0 = (x1 + t[0] * s, y1 + t[1] * s)
            e = subpix_edge_centroid(g, p0, nrm)
            if e is not None:
                pts.append(e)
        if len(pts) < L * 0.3:                              # 有效点覆盖不足则跳过
            continue
        pts = np.array(pts)
        # 最小二乘直线（PCA 主轴）
        c = pts.mean(0)
        u = np.linalg.svd(pts - c, full_matrices=False)[2][0]
        dev = np.abs((pts - c) - ((pts - c) @ u)[:, None] * u).max()
        worst = max(worst, dev)
        print(f'直线 L={L:.0f}px  有效点 {len(pts)}  max偏差 {dev:.3f}px')
        cv2.line(out, (x1, y1), (x2, y2), (0, 255, 0), 1)

    print(f'\n全图最大直线度偏差: {worst:.3f} px（矫正后应 <=1~2px）')
    if a.show:
        cv2.imshow('lines  [q]=quit', out)
        while cv2.waitKey(1) & 0xFF != ord('q'):
            pass
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
