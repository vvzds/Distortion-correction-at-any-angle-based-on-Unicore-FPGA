# -*- coding: utf-8 -*-
"""
capture.py —— HDMI 采集卡抓帧工具（标定/质量分析图像采集）
用法 : python capture.py [--cam 0] [--dir calib] [--prefix shot]
按键 : 空格 = 保存当前帧 PNG    q = 退出
硬约束: 输入必须是 1920x1080 原始分辨率（采集卡禁止缩放，否则标定坐标
        系与引擎 1920x1080 输出坐标系不一致，标定结果作废）
"""
import cv2
import os
import glob
import argparse

ap = argparse.ArgumentParser(description='HDMI 采集卡抓帧')
ap.add_argument('--cam', type=int, default=0, help='采集卡序号（多设备时试 0/1/2）')
ap.add_argument('--dir', default='calib', help='保存目录')
ap.add_argument('--prefix', default='shot', help='文件名前缀')
a = ap.parse_args()

os.makedirs(a.dir, exist_ok=True)
cap = cv2.VideoCapture(a.cam + cv2.CAP_DSHOW)   # Windows DirectShow 后端
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
if not cap.isOpened():
    raise SystemExit('打不开视频设备，换 --cam 序号重试')

w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f'输入分辨率: {w}x{h}')
if (w, h) != (1920, 1080):
    print(f'警告: 非 1920x1080，请在采集卡/驱动设置中改为原始分辨率直通，'
          f'缩放抓帧不可用于标定！')

n = len(glob.glob(os.path.join(a.dir, a.prefix + '_*.png')))
print(f'已有 {n} 张，继续编号。空格=保存  q=退出')
while True:
    ok, img = cap.read()
    if not ok:
        continue
    cv2.imshow('capture  [space]=save  [q]=quit', img)
    k = cv2.waitKey(1) & 0xFF
    if k == ord(' '):
        f = os.path.join(a.dir, f'{a.prefix}_{n:03d}.png')
        cv2.imwrite(f, img)
        n += 1
        print('saved', f)
    elif k == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()
