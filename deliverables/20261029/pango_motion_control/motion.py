"""Predictive, bounded affine motion for the frame-latched FPGA controller."""
import math

from model import affine, preflight
from control import covering_zoom


def motion_pose(elapsed_seconds, center_degrees, rotation_amplitude,
                shear_center, shear_amplitude, period_seconds,
                phase_lead_ms=0.0):
    """Smoothly oscillate rotation and shear; lead shifts the whole trajectory."""
    if period_seconds <= 0:
        raise ValueError('Motion period must be positive')
    t = elapsed_seconds + phase_lead_ms / 1000.0
    phase = math.tau * t / period_seconds
    return (center_degrees + rotation_amplitude * math.sin(phase),
            shear_center + shear_amplitude * math.cos(phase))


def update_latency_estimate(previous_ms, observed_ms, weight=0.2):
    """EMA smooths frame-boundary and host scheduling variation."""
    observed_ms = max(0.0, float(observed_ms))
    if previous_ms is None:
        return observed_ms
    return previous_ms * (1.0 - weight) + observed_ms * weight


def trajectory_samples(center_degrees, rotation_amplitude,
                       shear_center, shear_amplitude, count=None):
    """Return a phase grid covering a complete out-and-back motion cycle."""
    if count is None:
        count = max(72, int(math.ceil(abs(rotation_amplitude) * 2.0)))
    if count < 8:
        raise ValueError('At least 8 trajectory samples are required')
    return [motion_pose(i / count, center_degrees, rotation_amplitude,
                        shear_center, shear_amplitude, 1.0)
            for i in range(count)]


def verify_trajectory(calibration, center_degrees, rotation_amplitude,
                      base_zoom, tx, ty, shear_center, shear_amplitude,
                      crop, adaptive, progress=None, cancel=None):
    """Preflight the full motion path and reserve patch capacity headroom."""
    samples = trajectory_samples(center_degrees, rotation_amplitude,
                                 shear_center, shear_amplitude)
    zoom = float(base_zoom)
    if crop:
        crop_samples = samples[::max(1, len(samples) // 24)]
        for angle, shear in crop_samples:
            if cancel and cancel.is_set():
                raise RuntimeError('动态轨迹预检已取消')
            zoom = max(zoom, covering_zoom(calibration, angle, tx, ty, shear))
        zoom *= 1.01

    reports = []
    for index, (angle, shear) in enumerate(samples):
        if cancel and cancel.is_set():
            raise RuntimeError('动态轨迹预检已取消')
        _, report = preflight(calibration,
                              affine(angle, zoom, tx, ty, shear), adaptive)
        reports.append(report)
        if report['valid_fraction'] < 0.01:
            raise ValueError(f'轨迹在 {angle:.1f}° 的有效画面不足 1%，拒绝输出近乎全黑画面')
        if report['max_patch_width'] > 192 or report['max_patch_height'] > 192:
            raise ValueError(
                f"轨迹预检在 {angle:.1f}° 需要 "
                f"{report['max_patch_width']}×{report['max_patch_height']} 源块；"
                '安全运行余量不足，请降低剪切/平移或缩小角度范围')
        if progress:
            progress(index + 1, len(samples), angle, report)

    return {
        'zoom': zoom,
        'samples': len(samples),
        'max_patch_width': max(item['max_patch_width'] for item in reports),
        'max_patch_height': max(item['max_patch_height'] for item in reports),
        'min_valid_fraction': min(item['valid_fraction'] for item in reports),
        'crop_enabled': bool(crop),
    }
