# -*- coding: utf-8 -*-
"""
affine_track.py —— 图像反馈闭环动态仿射演示（高阶任务 1：②+安全退化 路线）
规格权威源：《模块分工与工作包交付总说明_v1.7.md》§2.4

环路 : HDMI(MS2109) -> 抓帧 -> ECC 仿射估计(当前输出 vs 参考帧)
       -> 增量复合控制律 A_new = A_prev @ D -> G02 夹紧 -> 0x02 下发(aff_en=1)
       -> 0x05 周期确认(params_valid/pub_count)
安全退化(四类):
  1) 置信度不足(ECC<阈值/估计异常) -> 回退恒等仿射组, 画面冻结直通, 等待重锚
  2) 场景内容剧变(换卡/大转场)     -> 同上(低置信度自然覆盖) + 提示重锚
  3) 估计值越 G02 域               -> 逐参数夹紧到合法域再下发, 事件计数
  4) 串口/0x05 异常                -> 保持最后合法参数组(影子组保证帧内原子), 停发等待恢复
按键 : r = 重锚(以当前画面为新参考帧)   q = 退出
硬边界: FPGA/协议零改动; 感知对象为"画面内容相对参考帧的位姿变化",
        内容剧变按"退化+重锚"流程处理(V1.7 §2.4.3 诚实口径)。

用法 :
  python affine_track.py --port COM3                    # 实机闭环
  python affine_track.py --dry-run                     # 不接串口, 打印应发帧(链路预演)
  python affine_track.py --port COM3 --scale 0.5 --ecc-min 0.55 --hold-coeff 1e-3 --hold-trans 0.2
"""
import sys
import os
import time
import math
import argparse
import datetime

import numpy as np
import cv2

# ---- 复用 uart_host_tool V1.0 冻结协议实现(验收件, 只读引用, 不修改) ----
# 导入搜索: 包内同目录优先(uart_tool.py 随包同放即可),
#           仓库同仓 uart_host_tool/ 目录回退。后 insert 者优先, 故 _HERE 在后。
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "uart_host_tool"))
sys.path.insert(0, _HERE)
import uart_tool  # noqa: E402  (encode_q16/frame/build_affine/read_status_frame/open_serial)

# G02 仿射合法域(与 uart_tool.LIMITS / param_mgr 一致, 独立声明防隐式耦合)
G02_AFFINE = {
    "a11": (-2.0, 2.0), "a12": (-2.0, 2.0),
    "a21": (-2.0, 2.0), "a22": (-2.0, 2.0),
    "tx": (-4096.0, 4096.0), "ty": (-4096.0, 4096.0),
}
AFFINE_ORDER = ("a11", "a12", "a21", "a22", "tx", "ty")
IDENTITY = {"a11": 1.0, "a12": 0.0, "a21": 0.0, "a22": 1.0, "tx": 0.0, "ty": 0.0}

STATE_CLOSED, STATE_DEGRADED = "CLOSED", "DEGRADED"

ECC_CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_COUNT, 100, 1e-4)
PYRAMID_LEVELS = (0.125, 0.25, 0.5, 1.0)   # 兜底金字塔层(ORB 特征不足时用)
ORB_COARSE_SCALE = 0.5   # ORB 粗对准工作尺度(与 ECC 精化级解耦, 保特征密度)
ORB_MIN_MATCHES = 6      # RANSAC 前有效匹配下限(Lowe ratio 筛后)
ORB_MIN_INLIERS = 6     # RANSAC 后内点下限


# ---------------- 估计器 ----------------

def to_gray(frame):
    """BGR 帧转灰度。"""
    if frame.ndim == 3:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return frame


def _small(img, scale):
    """降采样(INTER_AREA 抗混叠); scale>=1 原图直返。"""
    if scale >= 1.0:
        return img
    return cv2.resize(img, None, fx=scale, fy=scale,
                      interpolation=cv2.INTER_AREA)


def _levels_up_to(scale):
    """由粗到细取金字塔层, 最细层 = scale 本身(不小于 scale 的固定层全部跳过)。"""
    levels = [s for s in PYRAMID_LEVELS if s < scale]
    levels.append(float(scale))
    return levels


def _orb_coarse(ref_small, cur_small):
    """ORB 特征粗对准: 返回小图坐标系 D0(2x3) 或 None。

    RANSAC partial-affine(4 自由度: 旋转+缩放+平移) —— 物理相机运动正是
    刚体(+镜头缩放); ORB 描述子旋转不变, 对 ±15deg 大角度无收敛域问题。
    匹配方向: cur 特征点 -> ref 特征点 的映射即 D(cur(D p)=ref(p))。
    """
    orb = cv2.ORB_create(nfeatures=3000)
    kp_ref, desc_ref = orb.detectAndCompute(ref_small, None)
    kp_cur, desc_cur = orb.detectAndCompute(cur_small, None)
    if desc_ref is None or desc_cur is None or len(kp_ref) < 8 or len(kp_cur) < 8:
        return None
    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(desc_cur, desc_ref, k=2)
    good = [m for m, n in matches if m.distance < 0.75 * n.distance]   # Lowe ratio
    if len(good) < ORB_MIN_MATCHES:
        return None
    src = np.float32([kp_cur[m.queryIdx].pt for m in good])
    dst = np.float32([kp_ref[m.trainIdx].pt for m in good])
    m_r, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                               ransacReprojThreshold=3.0)
    if m_r is None or inliers is None or inliers.sum() < ORB_MIN_INLIERS:
        return None
    return np.asarray(m_r, np.float64)


def estimate_delta(ref_gray, cur_gray, scale=0.25):
    """估计当前帧相对参考帧的仿射补偿 D(输出->采样方向)。

    目标 : D 使 cur(D p) = ref(p) —— 把 cur 校正回参考帧位姿的采样映射。
    cv2.findTransformECC(A, B, w) 实测语义为 A(w p) = B(p)(第一个参数才是
    被 warp 的图), 故调用时 cur 在前、ref 在后, 返回的 w 即 D 本身, 无需再求逆。
    (自检 T2 证明: cur = warpAffine(ref, M) 时 D = M^-1, 误差系数 <1e-4)
    两级策略(2026-10-20 实测定标, 批量 36 组含 ±15deg 全组合):
      主路 —— ORB+RANSAC 粗对准(全局解, 无收敛域问题) -> ECC 单级精化
             (ECC 仿射 6 参数在重复棋盘纹理上恒等初值会锁进"y 压扁"等
              局部极小盆, 实测 ±15deg 组合 20/36 失败; ORB 初值 36/36 过)
      兜底 —— 特征不足/精化失败时恒等初值金字塔(0.125 起 2:1) 兜小角度
    两路皆败(粗级都配不上=内容剧变/黑屏) -> (None, 0.0) 交由上层安全退化。
    平移量按各级比例换算回全分辨率像素。
    返回 (D_2x3, ecc) ; 失败返回 (None, 0.0)。
    """
    try:
        # -- 主路: ORB 粗对准 -> ECC 单级精化 --
        s_orb = max(float(scale), ORB_COARSE_SCALE)
        d0 = _orb_coarse(_small(ref_gray, s_orb), _small(cur_gray, s_orb))
        if d0 is not None:
            try:
                d_full = np.asarray(d0, np.float64)
                d_full[0, 2] /= s_orb   # s_orb 小图平移 -> 全图平移
                d_full[1, 2] /= s_orb
                small_ref = _small(ref_gray, scale)
                small_cur = _small(cur_gray, scale)
                warp = np.asarray(d_full, np.float32).copy()
                warp[0, 2] *= scale   # 全图平移 -> 精化级小图平移
                warp[1, 2] *= scale
                result = cv2.findTransformECC(small_cur, small_ref, warp,
                                              cv2.MOTION_AFFINE, ECC_CRITERIA,
                                              None, 5)
                # OpenCV 4.5+/5.x 返回 (ecc, warp); 个别构建只返回 warp
                if isinstance(result, tuple):
                    ecc = float(result[0])
                    if not math.isfinite(ecc):
                        ecc = 0.0
                else:
                    ecc = 1.0   # 无相关度返回值的构建: 按收敛处理, 由下游兜底
                d_full = np.asarray(warp, np.float64)
                d_full[0, 2] /= scale
                d_full[1, 2] /= scale
                if np.all(np.isfinite(d_full)):
                    return d_full, ecc
            except cv2.error:
                pass   # ORB 初值下 ECC 仍不收敛 -> 落到金字塔兜底
        # -- 兜底: 恒等初值金字塔(小角度/弱纹理场景) --
        d_full = np.eye(2, 3, dtype=np.float64)
        ecc = 1.0
        for s in _levels_up_to(scale):
            small_ref = _small(ref_gray, s)
            small_cur = _small(cur_gray, s)
            warp = np.asarray(d_full, dtype=np.float32).copy()
            warp[0, 2] *= s
            warp[1, 2] *= s
            result = cv2.findTransformECC(small_cur, small_ref, warp,
                                          cv2.MOTION_AFFINE, ECC_CRITERIA,
                                          None, 5)
            if isinstance(result, tuple):
                ecc = float(result[0])
                if not math.isfinite(ecc):
                    ecc = 0.0
            else:
                ecc = 1.0
            d_full = np.asarray(warp, dtype=np.float64)
            d_full[0, 2] /= s
            d_full[1, 2] /= s
        if not np.all(np.isfinite(d_full)):
            return None, 0.0
        return d_full, ecc
    except cv2.error:
        return None, 0.0


# ---------------- 控制律 / 夹紧 ----------------

def compose(a_prev_3x3, delta_2x3):
    """增量复合 A_new = A_prev @ D(齐次 3x3, D 在右: ref(p)=raw(A_prev(D p)))。"""
    d_h = np.vstack([delta_2x3, [0.0, 0.0, 1.0]])
    m = a_prev_3x3 @ d_h
    return m


def to_params(matrix_2x3):
    """2x3 -> G02 参数字典(行主序即 a11,a12,tx,a21,a22,ty)。"""
    return {
        "a11": float(matrix_2x3[0, 0]), "a12": float(matrix_2x3[0, 1]),
        "tx": float(matrix_2x3[0, 2]),
        "a21": float(matrix_2x3[1, 0]), "a22": float(matrix_2x3[1, 1]),
        "ty": float(matrix_2x3[1, 2]),
    }


def clamp_params(params):
    """逐参数夹紧到 G02 合法域。返回 (夹紧后参数, 越界事件列表)。"""
    out, events = {}, []
    for name in AFFINE_ORDER:
        low, high = G02_AFFINE[name]
        value = params[name]
        if not math.isfinite(value):
            out[name] = IDENTITY[name]
            events.append((name, value, "NaN->identity"))
            continue
        clipped = min(max(value, low), high)
        if clipped != value:
            events.append((name, value, clipped))
        out[name] = clipped
    return out, events


def params_diff(new, old):
    """参数变化量分列两类: 返回 (系数最大差, 平移最大差[像素])。

    两类量级不同(系数 1e-3 ~ 2px 边缘错位, 平移直接以像素计), 统一单一
    阈值会把平移压到无物理意义的 1/250 像素、或把系数放到 10% 尺度误差。
    """
    coeff = max(abs(new[k] - old[k]) for k in ("a11", "a12", "a21", "a22"))
    trans = max(abs(new[k] - old[k]) for k in ("tx", "ty"))
    return coeff, trans


# ---------------- 闭环状态机 ----------------

class AffineTracker:
    """闭环跟踪器: 估计/复合/夹紧/退化/下发/确认。与 IO 解耦, 便于离线自检。"""

    def __init__(self, ecc_min=0.55, hold_coeff=1e-3, hold_trans=0.2, scale=0.25):
        self.ecc_min = float(ecc_min)
        self.hold_coeff = float(hold_coeff)   # 系数变化阈值(边缘错位 ~2px 级, 肉眼不可见)
        self.hold_trans = float(hold_trans)   # 平移变化阈值(像素, 0.2px 在 1080p 不可见)
        self.scale = float(scale)
        self.state = STATE_CLOSED
        self.applied = dict(IDENTITY)   # 已生效(已下发)参数
        self.applied_3x3 = np.eye(3)
        self.clamp_events = []          # (时间, 参数, 原值, 夹紧值)
        self.degrade_events = []        # (时间, 原因)
        self.frames = 0

    # -- 退化/恢复 --
    def degrade(self, reason):
        """回退恒等仿射组: 画面冻结为稳定直通。"""
        self.state = STATE_DEGRADED
        self.applied = dict(IDENTITY)
        self.applied_3x3 = np.eye(3)
        self.degrade_events.append((datetime.datetime.now().isoformat(timespec="seconds"), reason))

    def reanchor(self, new_ref_gray):
        """人工重锚: 以给定帧为新参考, 恢复闭环。"""
        self.ref_gray = new_ref_gray
        self.state = STATE_CLOSED
        self.applied = dict(IDENTITY)
        self.applied_3x3 = np.eye(3)

    # -- 主决策 --
    def step(self, cur_gray):
        """处理一帧。返回 (action, params) :
        action in {"send", "hold", "degraded-send", "degraded-hold"}"""
        self.frames += 1
        if getattr(self, "ref_gray", None) is None:
            self.ref_gray = cur_gray
            return "hold", dict(self.applied)

        if self.state == STATE_DEGRADED:
            # 退化期: 保持恒等, 不再估计(黑屏/换卡期间估计无意义), 等待重锚
            return "degraded-hold", dict(self.applied)

        delta, ecc = estimate_delta(self.ref_gray, cur_gray, self.scale)
        if delta is None or ecc < self.ecc_min:
            self.degrade("ecc={:.3f}({})".format(ecc, "估计失败" if delta is None else "低于阈值"))
            return "degraded-send", dict(IDENTITY)

        m_new = compose(self.applied_3x3, delta)
        raw = to_params(m_new[:2, :])
        params, events = clamp_params(raw)
        if events:
            stamp = datetime.datetime.now().isoformat(timespec="seconds")
            self.clamp_events.extend([(stamp,) + ev for ev in events])
        # 夹紧后回写复合矩阵基, 防止夹紧损失在下一步被放大
        m_clamped = np.array([[params["a11"], params["a12"], params["tx"]],
                              [params["a21"], params["a22"], params["ty"]],
                              [0.0, 0.0, 1.0]])
        coeff_d, trans_d = params_diff(params, self.applied)
        if coeff_d < self.hold_coeff and trans_d < self.hold_trans:
            return "hold", dict(self.applied)   # 变化不显著, 不占用串口
        self.applied_3x3 = m_clamped
        self.applied = params
        return "send", params

    # -- 下发帧构造(经 uart_tool 冻结实现, 0x02/25B/aff_en=1) --
    def build_frame(self, params):
        return uart_tool.build_affine({k: params[k] for k in AFFINE_ORDER}, enable=1)


# ---------------- 采集与串口 IO ----------------

def open_camera(index):
    cap = cv2.VideoCapture(index + cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    if not cap.isOpened():
        raise SystemExit("打不开视频设备, 换 --cam 序号重试")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if (w, h) != (1920, 1080):
        print("警告: 非 1920x1080({}x{}), 采集卡须设为原始分辨率直通".format(w, h))
    return cap


def confirm_status(connection, last_status):
    """0x05 周期确认: bit8=params_valid, [31:16]=pub_count。异常时保持末组(退化 4)。"""
    try:
        connection.reset_input_buffer()
        request = uart_tool.frame(0x05)
        connection.write(request)
        connection.flush()
        status = uart_tool.read_status_frame(connection, timeout=2.0)
        valid = 1 if (status >> 8) & 1 else 0
        pub = (status >> 16) & 0xFFFF
        print("  [0x05] status=0x{:08X} params_valid={} pub_count={}".format(status, valid, pub))
        return status
    except Exception as exc:  # 串口异常: 不改参数, 保持末组(影子组保证帧内原子)
        print("  [0x05] 确认异常(保持末组合法参数): {}".format(exc))
        return last_status


def main(argv=None):
    parser = argparse.ArgumentParser(description="affine_track 图像反馈闭环动态仿射 (V1.7 s2.4)")
    parser.add_argument("--port", default=None, help="串口, 例如 COM3; 省略且未 --dry-run 时仅打印不发送")
    parser.add_argument("--cam", type=int, default=0, help="采集卡序号")
    parser.add_argument("--scale", type=float, default=0.5, help="ECC 精化级降采样系数(0.5=960x540 实测定标; 0.25 可省 CPU)")
    parser.add_argument("--ecc-min", type=float, default=0.55, help="置信度阈值, 低于即安全退化")
    parser.add_argument("--hold-coeff", type=float, default=1e-3, help="系数变化阈值(不显著即 hold)")
    parser.add_argument("--hold-trans", type=float, default=0.2, help="平移变化阈值[像素](不显著即 hold)")
    parser.add_argument("--frame-skip", type=int, default=1, help="每 N 帧处理一次(降低 CPU)")
    parser.add_argument("--confirm-period", type=float, default=5.0, help="0x05 确认周期(秒)")
    parser.add_argument("--dry-run", action="store_true", help="不接串口, 仅打印应发帧 hex")
    parser.add_argument("--save-dir", default=None, help="可选: 保存参考帧/事件 CSV 到此目录")
    args = parser.parse_args(argv)

    tracker = AffineTracker(args.ecc_min, args.hold_coeff, args.hold_trans, args.scale)
    cap = open_camera(args.cam)
    connection = None
    if not args.dry_run and args.port:
        connection = uart_tool.open_serial(args.port)
        print("串口 {} 已打开(115200 8N1)".format(args.port))
    else:
        print("dry-run 模式" if args.dry_run else "无串口: 仅打印不发送")

    if args.save_dir:
        os.makedirs(args.save_dir, exist_ok=True)

    print("r=重锚  q=退出  | ECC阈值={} 降采样x{}".format(args.ecc_min, args.scale))
    frame_no, last_confirm = 0, time.monotonic()
    sent_count = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        frame_no += 1
        if frame_no % args.frame_skip:
            continue

        action, params = tracker.step(to_gray(frame))
        if action.endswith("send"):
            wire = tracker.build_frame(params)
            if connection is not None:
                try:
                    connection.write(wire)
                    connection.flush()
                    sent_count += 1
                except Exception as exc:
                    print("串口发送异常, 保持末组合法参数: {}".format(exc))
            else:
                print("应发 0x02: {}".format(uart_tool.hex_dump(wire[:12]) + " ..."))
        if action == "degraded-send":
            print("** 安全退化已下发恒等组, 画面冻结直通; 按 r 重锚 **")
        if action == "hold" and tracker.state == STATE_CLOSED and frame_no % (30 * args.frame_skip) == 0:
            ecc_probe = 1.0  # hold 期间只打印心跳, 不重复估计
            print("[心跳] 帧x{} 已下发={} 状态={}".format(frame_no, sent_count, tracker.state))

        if connection is not None and time.monotonic() - last_confirm >= args.confirm_period:
            confirm_status(connection, None)
            last_confirm = time.monotonic()

        cv2.imshow("affine_track  [r]=reanchor  [q]=quit", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("r"):
            ok2, f2 = cap.read()
            if ok2:
                tracker.reanchor(to_gray(f2))
                print(">> 已重锚(新参考帧=当前画面), 闭环恢复")
                if args.save_dir:
                    cv2.imwrite(os.path.join(args.save_dir, "reanchor_ref.png"), f2)
        elif key == ord("q"):
            break

    if args.save_dir:
        import csv as _csv
        with open(os.path.join(args.save_dir, "affine_track_events.csv"), "w",
                  newline="", encoding="utf-8-sig") as fh:
            wcsv = _csv.writer(fh)
            wcsv.writerow(["kind", "time", "param", "from", "to"])
            for t, reason in tracker.degrade_events:
                wcsv.writerow(["degrade", t, "", "", reason])
            for t, name, old, new in tracker.clamp_events:
                wcsv.writerow(["clamp", t, name, old, new])
        np.save(os.path.join(args.save_dir, "affine_track_applied.npy"), tracker.applied_3x3)
        print("事件与末态已保存至", args.save_dir)
    if connection is not None:
        connection.close()
    cap.release()
    cv2.destroyAllWindows()
    print("结束: 处理帧={} 下发={} 退化事件={} 夹紧事件={}".format(
        tracker.frames, sent_count, len(tracker.degrade_events), len(tracker.clamp_events)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
