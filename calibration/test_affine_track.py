# -*- coding: utf-8 -*-
"""
test_affine_track.py —— affine_track 无硬件全链自检
覆盖 : T1 协议组装(与 uart_tool 冻结实现逐字节一致)
      T2 ECC 估计方向与精度(含 2x3 求逆方向证明)
      T3 闭环控制律单步收敛(A_new = A_prev @ D -> C^-1)
      T4 安全退化(黑帧触发/恒等下发/退化期保持/重锚恢复)
      T5 G02 越界夹紧(事件记录)
      T6 显著变化判据(微扰不下发)
      T7 0x05 状态帧解析(mock 串口)
判据 : 全部 check 通过退出 0, 任一失败退出 1(统一出口, 不抛裸异常)
运行 : python test_affine_track.py
"""
import sys
import os
import struct

import numpy as np
import cv2

# 导入搜索: 本目录(脚本自身目录)优先, 仓库同仓 uart_host_tool/ 回退(后 insert 者优先)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "uart_host_tool"))
sys.path.insert(0, _HERE)
import uart_tool  # noqa: E402

import affine_track  # noqa: E402

PASSED, FAILED = [], []


def check(label, condition):
    if condition:
        PASSED.append(label)
        print("[PASS] {}".format(label))
    else:
        FAILED.append(label)
        print("[FAIL] {}".format(label))


def make_texture(size=(1080, 1920), seed=20261020):
    """合成纹理图: 棋盘 + 高斯噪点 + 若干圆形(ECC 稳定配准用)。"""
    rng = np.random.default_rng(seed)
    img = np.zeros(size, dtype=np.float32)
    img += rng.normal(0, 8, size).astype(np.float32)
    for y in range(0, size[0], 120):
        for x in range(0, size[1], 120):
            if ((x // 120 + y // 120) % 2) == 0:
                img[y:y + 120, x:x + 120] += 60.0
    for cy, cx, r in [(270, 480, 90), (810, 1440, 130), (540, 960, 160)]:
        yy, xx = np.ogrid[:size[0], :size[1]]
        img[(yy - cy) ** 2 + (xx - cx) ** 2 < r * r] += 90.0
    return np.clip(img, 0, 255).astype(np.uint8)


def invert_2x3(m):
    """2x3 齐次求逆, 返回 2x3。"""
    h = np.vstack([m, [0.0, 0.0, 1.0]])
    return np.linalg.inv(h)[:2, :]


def mat_close(a, b, atol_a=1e-2, atol_t=2.0):
    d = np.asarray(a, float) - np.asarray(b, float)
    return (abs(d[:, :2]).max() <= atol_a) and (abs(d[:, 2]).max() <= atol_t)


def test_all():
    # ---------- T1 协议组装 ----------
    tracker = affine_track.AffineTracker(scale=0.5)
    wire_self = tracker.build_frame(affine_track.IDENTITY)
    wire_ref = uart_tool.build_affine(dict(affine_track.IDENTITY), enable=1)
    check("T1a 恒等组 0x02 帧与 uart_tool 冻结实现逐字节一致",
          bytes(wire_self) == bytes(wire_ref))
    check("T1b 帧长 30B(AA 55 02 19 + 25B + chk)", len(wire_ref) == 30)
    cmd, length_field, payload = uart_tool.parse_frame(bytes(wire_ref))
    check("T1c parse_frame 回读 cmd=0x02/len=25/末字节=aff_en=1",
          cmd == 0x02 and length_field == 25 and payload[-1] == 1)
    check("T1d Q16.16 编码抽查: encode_q16(1.0)==0x00010000 小端",
          uart_tool.encode_q16(1.0) == struct.pack("<i", 0x00010000))

    # ---------- T2 估计方向与精度 ----------
    ref = make_texture()
    theta = np.deg2rad(3.0)
    m_true = np.array([[np.cos(theta), -np.sin(theta), 10.0],
                       [np.sin(theta), np.cos(theta), -6.0]], dtype=np.float64)
    cur = cv2.warpAffine(ref, m_true.astype(np.float32), (ref.shape[1], ref.shape[0]),
                         borderMode=cv2.BORDER_REFLECT_101)  # 反射边: 消黑边, 贴近满幅真实场景
    d_est, ecc = affine_track.estimate_delta(ref, cur, scale=0.5)
    expected = invert_2x3(m_true)  # cur = ref(M p) 且 D: cur(D p)=ref(p) -> M D = I -> D = M^-1
    check("T2a ECC 置信度高(>0.9)", d_est is not None and ecc > 0.9)
    check("T2b 估计方向=真值逆且精度达标(系数<1e-2, 平移<2px)",
          d_est is not None and mat_close(d_est, expected))

    # ---------- T3 控制律单步收敛 ----------
    trk = affine_track.AffineTracker(scale=0.5)
    raw0 = make_texture(seed=7)
    c_theta = np.deg2rad(-4.0)  # 相机运动: 画面出现 C 变换, 闭环应下发 C^-1 补偿
    c_mat = np.array([[np.cos(c_theta), -np.sin(c_theta), -18.0],
                      [np.sin(c_theta), np.cos(c_theta), 12.0]], dtype=np.float64)
    def camera_output(a_2x3):
        """模拟链路: out(p) = raw0(C (A p)) (A 为已生效仿射)。"""
        comp = np.vstack([c_mat, [0, 0, 1]]) @ np.vstack([a_2x3, [0, 0, 1]])
        return cv2.warpAffine(raw0, comp[:2, :].astype(np.float32),
                             (raw0.shape[1], raw0.shape[0]),
                             borderMode=cv2.BORDER_REFLECT_101)  # 满幅场景, 无黑边
    trk.step(raw0)  # 第一帧设为参考(out0 = raw0)
    out_k = camera_output(np.eye(2, 3))  # 当前 A=I, 输出偏差 C
    action, params = trk.step(out_k)
    target = invert_2x3(c_mat)  # 理想收敛 A* = C^-1
    got = np.array([[params["a11"], params["a12"], params["tx"]],
                    [params["a21"], params["a22"], params["ty"]]])
    check("T3a 一步即下发(action=send)", action == "send")
    check("T3b 单步收敛至 C^-1(系数<1e-2, 平移<3px)", mat_close(got, target, atol_t=3.0))
    # 收敛后不再发(微小残差 hold)
    out_k2 = camera_output(got)
    action2, _ = trk.step(out_k2)
    check("T3c 收敛后微扰保持(action=hold)", action2 == "hold")

    # ---------- T4 安全退化 ----------
    trk4 = affine_track.AffineTracker(scale=0.5)
    trk4.step(ref)
    action_b, params_b = trk4.step(np.zeros_like(ref))  # 全黑帧: 遮挡/换卡瞬间
    check("T4a 黑帧触发安全退化(action=degraded-send)", action_b == "degraded-send")
    check("T4b 退化下发=恒等组(画面冻结直通)", params_b == affine_track.IDENTITY)
    check("T4c 状态=DEGRADED", trk4.state == affine_track.STATE_DEGRADED)
    action_c, params_c = trk4.step(make_texture(seed=99))  # 退化期喂新内容
    check("T4d 退化期不估计不改动(degraded-hold 且参数仍恒等)",
          action_c == "degraded-hold" and params_c == affine_track.IDENTITY)
    trk4.reanchor(make_texture(seed=99))  # 人工重锚
    check("T4e 重锚后状态恢复 CLOSED 且参数复位恒等",
          trk4.state == affine_track.STATE_CLOSED and trk4.applied == affine_track.IDENTITY)

    # ---------- T5 G02 夹紧 ----------
    clamped, events = affine_track.clamp_params(
        {"a11": 0.0, "a12": 0.0, "a21": 0.0, "a22": 1.0, "tx": 8000.0, "ty": -8000.0})
    check("T5a tx/ty 夹紧到 ±4096",
          clamped["tx"] == 4096.0 and clamped["ty"] == -4096.0)
    check("T5b 越界事件记录 2 条", len(events) == 2)
    clamped2, events2 = affine_track.clamp_params(
        {"a11": float("nan"), "a12": 0.0, "a21": 0.0, "a22": 1.0, "tx": 0.0, "ty": 0.0})
    check("T5c NaN 参数回退恒等值并记事件", clamped2["a11"] == 1.0 and len(events2) == 1)

    # ---------- T6 显著变化判据 ----------
    trk6 = affine_track.AffineTracker(scale=0.5)
    trk6.step(ref)
    tiny = np.array([[1.0, 0.0, 0.05], [0.0, 1.0, -0.05]])
    cur6 = cv2.warpAffine(ref, tiny.astype(np.float32), (ref.shape[1], ref.shape[0]),
                          borderMode=cv2.BORDER_REFLECT_101)
    action6, _ = trk6.step(cur6)
    # 0.05px 平移 < hold_trans(0.2px): 不可见微扰不应占用串口
    check("T6 亚阈值微扰不占用串口(action=hold)", action6 == "hold")

    # ---------- T7 0x05 状态帧解析(mock 串口) ----------
    class MockSerial(object):
        """喂一个固定 status=0x00080312 回帧(valid=1, pub=0x0008, ver=0x12)。"""
        def __init__(self, wire):
            self._buf = bytearray(wire)
        def read(self, n):
            take, self._buf = bytes(self._buf[:n]), self._buf[n:]
            return take
    status_wire = uart_tool.HEADER + bytes((0x05, 0x04)) + \
        struct.pack("<I", 0x00080312) + \
        bytes((sum(struct.pack("<I", 0x00080312)) & 0xFF,))
    status = uart_tool.read_status_frame(MockSerial(status_wire), timeout=2.0)
    check("T7 0x05 回帧解析 status=0x00080312", status == 0x00080312)
    check("T7b 位域判读 params_valid=1 / pub_count=8",
          ((status >> 8) & 1) == 1 and ((status >> 16) & 0xFFFF) == 8)


def main():
    test_all()
    print()
    print("=" * 60)
    print("RESULT: {} passed, {} failed".format(len(PASSED), len(FAILED)))
    if FAILED:
        for f in FAILED:
            print("  FAILED:", f)
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
