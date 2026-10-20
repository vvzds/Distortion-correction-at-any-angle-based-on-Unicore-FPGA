# -*- coding: utf-8 -*-
"""
calibrate.py —— OV5640 链路相机标定（张正友棋盘格法，OpenCV）
================================================================
与 FPGA 校正引擎同构（设计文档 V1.2 §3.2 / §3.5 G02 冻结）：
  - 畸变模型 = OpenCV 4 参数：径向 k1,k2 + 切向 p1,p2（无 k3）
  - 内参 fx,fy,cx,cy 为像素域，坐标系 = HDMI 输出 1920x1080 图像坐标系
  - 定点 = Q16.16 有符号小端，UART 0x01 帧 32 字节负载
输出：
  K 矩阵 / 4 畸变系数 / RMS 与逐张误差 / G02 范围预检 / 0x01 帧 hex
  calib_result.json + calib_result.txt（证据链存档，赛题要求参数来自真实标定）
用法：
  python calibrate.py [--dir calib] [--cb 12 9] [--sq 0.025]
  --cb 内角点数（列 行）。采购"12x9"板可能指内角点 12x9，也可能指
      格子数 12x9（此时内角点为 11x8），脚本按首张图自动探测两者。
  --sq 方格物理边长 [m]，默认 0.025（25mm）。
"""
import cv2
import glob
import os
import json
import argparse
import datetime
import numpy as np


def q16_16(v):
    """浮点 -> Q16.16 有符号小端 4 字节（与 param_mgr 解码一致）"""
    return (int(round(v * 65536.0)) & 0xFFFFFFFF).to_bytes(4, 'little')


def g02_violations(p):
    """G02 参数范围预检（越界组引擎将拒收且 status.bit8=0）"""
    lims = [('fx', p['fx'], 128.0, 32767.99), ('fy', p['fy'], 128.0, 32767.99),
            ('cx', p['cx'], 0.0, 1919.0), ('cy', p['cy'], 0.0, 1079.0),
            ('k1', p['k1'], -0.5, 0.5), ('k2', p['k2'], -0.5, 0.5),
            ('p1', p['p1'], -0.01, 0.01), ('p2', p['p2'], -0.01, 0.01)]
    return [(n, v, lo, hi) for n, v, lo, hi in lims if not (lo <= v <= hi)]


def main():
    ap = argparse.ArgumentParser(description='棋盘格相机标定（引擎同构 4 参数模型）')
    ap.add_argument('--dir', default='calib', help='标定图像目录')
    ap.add_argument('--cb', nargs=2, type=int, default=[12, 9],
                    help='内角点数 列 行（默认 12 9，自动回退 11x8）')
    ap.add_argument('--sq', type=float, default=0.025, help='方格边长 [m]')
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(a.dir, '*.png')) +
                   glob.glob(os.path.join(a.dir, '*.bmp')))
    print(f'发现 {len(files)} 张图像')
    assert len(files) >= 15, '标定图像不足 15 张，请先按采集 SOP 完成 20+ 张采集'

    # ---- 内角点规格自动探测（12x9 内点 / 11x8 内点 两种标称口径）----
    def detect(gray, cb):
        return cv2.findChessboardCornersSB(gray, tuple(cb), None)

    g0 = cv2.cvtColor(cv2.imread(files[0]), cv2.COLOR_BGR2GRAY)
    cands = [tuple(a.cb), (a.cb[0] - 1, a.cb[1] - 1)]
    CB = None
    for t in cands:
        if detect(g0, t)[0]:
            CB = t
            break
    assert CB is not None, f'首张图按 {cands} 均未检出棋盘，检查图像与标定板'
    print(f'采用内角点规格: {CB[0]} x {CB[1]}')

    objp = np.zeros((CB[0] * CB[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CB[0], 0:CB[1]].T.reshape(-1, 2) * a.sq
    objps, imgps, used = [], [], []
    for f in files:
        g = cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2GRAY)
        ok, c = detect(g, CB)
        if ok:
            objps.append(objp)
            imgps.append(c)
            used.append(os.path.basename(f))
        else:
            print('  skip(角点未检出):', os.path.basename(f))
    print(f'有效用例: {len(used)}/{len(files)}')
    assert len(used) >= 15, '有效张数不足 15，补拍（棋盘需完整、清晰、无反光）'

    # ---- 标定：distCoeffs 长度=4 -> 仅优化 k1,k2,p1,p2（与引擎同构）----
    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(
        objps, imgps, g.shape[::-1], None, np.zeros(4, np.float64))
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    k1, k2, p1, p2 = (float(x) for x in np.ravel(dist)[:4])

    # ---- 逐张重投影 RMS（>1px 列为离群，提示补拍）----
    perr = []
    for o, i, rv, tv in zip(objps, imgps, rvecs, tvecs):
        pr, _ = cv2.projectPoints(o, rv, tv, K, dist)
        perr.append(float(np.sqrt(((pr.reshape(-1, 2) - i.reshape(-1, 2)) ** 2)
                                   .sum(axis=1).mean())))
    print('\n逐张 RMS 误差(px):')
    for fn, e in zip(used, perr):
        print(f'  {fn}: {e:.3f}{"   <-- 离群, 建议剔除重拍" if e > 1.0 else ""}')

    print(f'\n总 RMS = {rms:.4f} px  (门槛 <0.5, 目标 <0.3)')
    print(f'fx = {fx:.2f}   fy = {fy:.2f}   (互差比 {abs(fx-fy)/((fx+fy)/2)*100:.2f}%, 应 <2%)')
    print(f'cx = {cx:.2f}   cy = {cy:.2f}   (期望接近 960/540)')
    print(f'k1 = {k1:+.6f}   k2 = {k2:+.6f}')
    print(f'p1 = {p1:+.6f}   p2 = {p2:+.6f}')
    print('提示: OV5640 中心裁切后视场小、原生畸变弱，|k1| 为 1e-3~1e-2 量级属正常。')

    p = dict(fx=fx, fy=fy, cx=cx, cy=cy, k1=k1, k2=k2, p1=p1, p2=p2)
    viol = g02_violations(p)
    if viol:
        print('\nG02 预检 FAIL（引擎将拒收该组）:')
        for n, v, lo, hi in viol:
            print(f'  {n}={v:.6f} 越界 [{lo}, {hi}]')
        print('排查: 标定板平整度 / 摆姿角覆盖是否单一 / 反光')
    else:
        print('\nG02 范围预检: PASS（8 参数全部在引擎合法域内）')

    # ---- UART 0x01 帧生成（checksum = 负载字节和 mod 256）----
    payload = b''.join(q16_16(v) for v in (fx, fy, cx, cy, k1, k2, p1, p2))
    frame = bytes([0xAA, 0x55, 0x01, 32]) + payload + bytes([sum(payload) & 0xFF])
    hexstr = ' '.join(f'{b:02X}' for b in frame)
    print('\nUART 0x01 帧（37 字节）:')
    print(' ', hexstr)

    # ---- 存档（证据链：赛题要求畸变参数须来自真实标定）----
    out = dict(time=datetime.datetime.now().isoformat(timespec='seconds'),
               board=f'chessboard {CB[0]}x{CB[1]} inner corners, square={a.sq} m',
               images=used, rms=float(rms), per_view_err=dict(zip(used, perr)),
               fx=fx, fy=fy, cx=cx, cy=cy, k1=k1, k2=k2, p1=p1, p2=p2,
               g02_pass=(len(viol) == 0), uart01_frame=hexstr)
    with open('calib_result.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n结果已存档 calib_result.json（发送前核对，保留原始文件作为标定证据）')
    print('下发方式: 用已验收的 uart_host_tool 发送 0x01 参数组（或将上方 hex 串按')
    print('工具十六进制模式发送），发送后 --status 读回确认 bit8(params_valid)=1。')


if __name__ == '__main__':
    main()
