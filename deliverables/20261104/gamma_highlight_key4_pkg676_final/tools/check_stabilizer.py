"""Deterministic geometry, delay-feedback and registration checks; no hardware."""
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'host'))
from model import affine, compile_registers, fixed_map, load_calibration, tile_profile
from stabilizer import (FrameTimeline, SmoothTarget, ReferenceTracker, corner_distance,
                        matrix_from_registers, fast_guard, homogeneous, interpolate_affine)


def main():
    cv2.setNumThreads(2)
    rng = np.random.default_rng(20261029)
    checks = []
    c = load_calibration()
    profiles = []
    for angle in range(0, 360, 15):
        matrix = homogeneous(affine(angle, 1.15))
        guard = fast_guard(c, matrix)
        regs = compile_registers(c, matrix[:2], False)
        sx, sy, inside = fixed_map(regs)
        profile = tile_profile(sx, sy, inside)
        assert profile['max_patch_width'] <= guard['max_patch_width_bound']
        assert profile['max_patch_height'] <= guard['max_patch_height_bound']
        profiles.append(dict(angle=angle, **guard))
    checks.append('All 24 roll angles pass conservative patch guard and exact full-map profile')
    try:
        fast_guard(c, [[1, 0, 50000], [0, 1, 0]])
    except ValueError:
        pass
    else:
        raise AssertionError('Unsafe normalized transform accepted')
    camera_motion = homogeneous(affine(24, 1, 36, -17, .04))
    a_seen = homogeneous(affine(-11, 1.15, -8, 9))
    base = homogeneous(affine(0, 1.15))
    target = camera_motion@base
    timeline = FrameTimeline(.12)
    for i in range(8):
        timeline.append(i/30, i, a_seen)
    observed = timeline.seen(.24)
    residual = np.linalg.inv(observed)@target
    assert corner_distance(observed@residual, target) < 1e-9
    assert timeline.seen(.01) is None and timeline.seen(1.) is None
    recovered = matrix_from_registers(c, compile_registers(c, a_seen[:2], False))
    assert corner_distance(recovered,a_seen) < .03
    checks.append('UART quantized matrix recovery; delayed timeline rejects missing/stale history')
    smoother = SmoothTarget(base, .08, 700)
    smoother.target = homogeneous(affine(45,1.15))
    errors, movements = [], []
    for i in range(90):
        before = smoother.current.copy()
        smoother.advance(1/30)
        movements.append(corner_distance(before,smoother.current))
        errors.append(corner_distance(smoother.current,smoother.target))
    assert all(b <= a+1e-7 for a,b in zip(errors, errors[1:]))
    assert errors[-1] < .1 and max(movements) <= 700/30+.1
    assert all(m > .01 for m in movements[:15])
    checks.append('90-frame polar target progression continues without new estimates; bounded corner speed and monotone convergence')
    half = interpolate_affine(np.eye(3), homogeneous(affine(179)), .5)
    assert np.linalg.det(half[:2, :2]) > .99
    # Stationary scene, old commands delayed six observations. Correct tagging
    # converges without reapplying the same displayed residual to latest state.
    current = base.copy()
    delay = [base.copy() for _ in range(6)]
    errors = []
    for i in range(120):
        observed = delay.pop(0)
        delta = np.linalg.inv(observed)@target
        current = interpolate_affine(current, observed@delta, .35)
        delay.append(current.copy())
        errors.append(corner_distance(current, target))
    assert errors[-1] < .001 and all(b <= a+1e-8 for a,b in zip(errors, errors[1:]))
    checks.append('Six-frame delayed closed-loop model converges monotonically; polar 180deg interpolation preserves scale')
    reference = np.zeros((1080, 1920, 3), np.uint8)
    for i in range(1800):
        x,y = rng.integers([20, 30], [1900, 1060])
        color = tuple(map(int, rng.integers(40, 255, 3)))
        cv2.circle(reference, (int(x), int(y)), int(rng.integers(2, 10)), color, -1)
    for i in range(50):
        cv2.putText(reference, str(i), tuple(map(int, rng.integers([80, 80], [1700, 1000]))),
                    cv2.FONT_HERSHEY_SIMPLEX, .8, (255, 255, 255), 2)
    results = []
    for angle in [0, 15, 45, 90, 135, 179, 225, 270, 315]:
        truth = homogeneous(affine(angle, 1., 9., -6., .025))
        current_image = cv2.warpAffine(reference, truth[:2], (1920, 1080))
        tracker = ReferenceTracker()
        tracker.anchor(reference)
        start = time.monotonic()
        estimated, quality = tracker.estimate(current_image)
        elapsed = time.monotonic()-start
        error = corner_distance(estimated, truth)
        assert error < 3., (angle, error, quality)
        results.append(dict(angle=angle, corner_error_px=error, estimate_ms=elapsed*1000, **quality))
    checks.append('ORB absolute reacquisition through full roll range with translation and shear')
    small_motion = []
    for angle in [.5, 1., 2.]:
        truth = homogeneous(affine(angle, 1., 0., 0., .002))
        current_image = cv2.warpAffine(reference, truth[:2], (1920,1080))
        tracker = ReferenceTracker()
        tracker.anchor(reference)
        estimated, quality = tracker.estimate(current_image)
        error = corner_distance(estimated, truth)
        movement = corner_distance(np.eye(3), estimated)
        assert error < 2. and movement > .25, (angle, movement, error, quality)
        small_motion.append(dict(angle=angle, corner_error_px=error,
                                 corner_movement_px=movement, **quality))
    checks.append('Sub-degree roll remains measurable above the revised 0.5px deadband')
    # Three degrees of ideal-camera pitch: affine approximation error remains
    # scene/ROI dependent and must be measured, not presented as exact homography.
    k = np.array([[c['fx'],0,c['cx']],[0,c['fy'],c['cy']],[0,0,1.]])
    pitch_results = []
    for degrees in [-3., 3.]:
        t = np.deg2rad(degrees)
        rotation = np.array([[1,0,0],[0,np.cos(t),-np.sin(t)],[0,np.sin(t),np.cos(t)]])
        h = k@rotation@np.linalg.inv(k)
        current_image = cv2.warpPerspective(reference, h, (1920,1080))
        tracker = ReferenceTracker()
        tracker.anchor(reference)
        estimated, quality = tracker.estimate(current_image)
        pitch_results.append(dict(pitch_degrees=degrees, **quality))
        assert quality['coverage'] > .12 and quality['rms_px'] < 4
    checks.append('Synthetic +/-3deg pitch accepted as approximate affine, not exact perspective correction')
    report = dict(passed=True, hardware_tested=False, checks=checks,
                  roll_registration=results, small_motion=small_motion,
                  pitch_approximation=pitch_results,
                  full_map_guard_profiles=profiles)
    (ROOT/'reports/stabilizer_checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
