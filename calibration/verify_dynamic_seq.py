# -*- coding: utf-8 -*-
"""verify_dynamic_seq.py —— 动态序列收敛离线验证(正式验收资产)

对应《模块分工与工作包交付总说明_v1.7.md》§2.4 验收判据:
  判据 1: 闭环跟随 ±15°(判据边界角), 单步回正(演示口径 1-3 帧的下界)
  判据 4: 动态序列 —— 连续多步复合运动(每步新增转动+平移), 全程不发散
场景 : 合成纹理(棋盘+圆+噪点, ECC/ORB 稳定配准), 物理相机位姿 P 累计
       复合, FPGA 已生效 A, 输出 out(p)=raw0(P(A p)); 闭环目标 A -> P^-1。
判据 : 每步残差(输出相对参考帧的剩余偏差) 系数 <0.02 且平移 <3px;
       任一步失败退出 1, 全过退出 0。
运行 : python verify_dynamic_seq.py
"""
import sys
import os
import numpy as np
import cv2

# 导入搜索: 本目录(脚本自身目录)优先, 仓库同仓 uart_host_tool/ 回退(后 insert 者优先)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "uart_host_tool"))
sys.path.insert(0, _HERE)

import affine_track
from test_affine_track import make_texture

W = (1920, 1080)
raw0 = make_texture(seed=7)

trk = affine_track.AffineTracker(scale=0.5)
trk.step(raw0)  # 参考帧 = 零位姿输出

# 物理相机位姿 P 累计作用于 raw0 采集; FPGA 已生效 A; 输出 out(p)=raw0(P(A p))
# 闭环目标: A -> P^-1(输出回正参考帧)
P = np.eye(3)
A = np.eye(3)   # 与 tracker.applied_3x3 保持同步
seq = [(15.0, 30, -20), (3.0, -10, 5), (-8.0, 0, 25), (1.0, 40, 40), (-2.0, -5, -5)]
print("动态序列(含 +15deg 判据边界角): 每步一次物理运动, 期望单步回正")
worst = (0.0, 0.0)
for k, (ang, tx, ty) in enumerate(seq):
    th = np.deg2rad(ang)
    C = np.array([[np.cos(th), -np.sin(th), tx],
                  [np.sin(th), np.cos(th), ty], [0, 0, 1]])
    P = C @ P
    out = cv2.warpAffine(raw0, (P @ A)[:2, :].astype(np.float32), W,
                         borderMode=cv2.BORDER_REFLECT_101)
    action, params = trk.step(out)
    if action == "send":
        A = np.array([[params["a11"], params["a12"], params["tx"]],
                      [params["a21"], params["a22"], params["ty"]], [0, 0, 1]])
    resid = np.linalg.inv(P @ A)   # 输出相对参考帧的剩余偏差
    e_c = abs(resid[:2, :2] - np.eye(2)).max()
    e_t = abs(resid[:2, 2]).max()
    worst = (max(worst[0], e_c), max(worst[1], e_t))
    print("  step{}: {:+.0f}deg/({},{})px -> action={} 残差 系数 {:.4f} 平移 {:.2f}px".format(
        k + 1, ang, tx, ty, action, e_c, e_t))
    if not (e_c < 0.02 and e_t < 3.0):
        print("FAIL: 残差超演示判据")
        sys.exit(1)
print("PASS: 全序列单步回正, 最差残差 系数 {:.4f} 平移 {:.2f}px (判据: <0.02 / <3px)".format(*worst))
