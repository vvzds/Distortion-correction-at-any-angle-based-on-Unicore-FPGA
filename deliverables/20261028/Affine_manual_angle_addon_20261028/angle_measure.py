"""Offline manual-point metrology; independent of tracking/ECC, no UART access."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

ROLES = ('reference', 'corrected', 'off', 'off_repeat', 'returned')
LABELS = {
    'reference': '原姿态、对应本轮参考图',
    'corrected': '转动并停稳、补偿开启的截图',
    'off': '保持转后姿态、按D并等待后截图',
    'off_repeat': '继续保持同一姿态、再等1秒截图',
    'returned': '补偿仍关闭、手动回到原姿态的截图',
}


def fit_points(source, destination, click_error=2.):
    """Least-squares similarity and separate affine diagnostic in image pixels."""
    source, destination = np.asarray(source, float), np.asarray(destination, float)
    if (source.ndim != 2 or source.shape[1] != 2 or destination.shape != source.shape
            or len(source) < 4 or not np.isfinite(source).all()
            or not np.isfinite(destination).all()):
        raise ValueError('Need >=4 finite matching points in the same order')
    x = source - source.mean(axis=0)
    y = destination - destination.mean(axis=0)
    for centered in (x, y):
        covariance = centered.T @ centered / len(centered)
        if np.linalg.eigvalsh(covariance).min() < 60. ** 2:
            raise ValueError('Points too clustered/collinear: spread them over a 2D area')
    u, singular, vt = np.linalg.svd(x.T @ y)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) <= 0:
        raise ValueError('Reflected/order-inconsistent points; check point identities')
    scale = float(singular.sum() / np.sum(x * x))
    if not .5 <= scale <= 2.:
        raise ValueError('Unexpected scale: check cropping, resolution and point order')
    linear = scale * rotation
    translation = destination.mean(axis=0) - linear @ source.mean(axis=0)
    error = source @ linear.T + translation - destination
    coefficients = np.linalg.lstsq(np.column_stack((source, np.ones(len(source)))),
                                   destination, rcond=None)[0]
    affine = coefficients[:2].T
    au, stretch, avt = np.linalg.svd(affine)
    if np.linalg.det(affine) <= 0:
        raise ValueError('Invalid affine geometry; check point order')
    affine_rotation = au @ avt
    sensitivity = math.degrees(click_error * math.sqrt(len(x)) *
                               (1 / np.linalg.norm(x) + 1 / np.linalg.norm(y)))
    return dict(
        angle_clockwise_deg=math.degrees(math.atan2(rotation[1, 0], rotation[0, 0])),
        scale=scale, translation_px=translation.tolist(),
        similarity_rms_px=float(np.sqrt(np.mean(np.sum(error ** 2, axis=1)))),
        max_point_displacement_px=float(np.linalg.norm(destination-source, axis=1).max()),
        affine_angle_clockwise_deg=math.degrees(math.atan2(affine_rotation[1, 0], affine_rotation[0, 0])),
        affine_anisotropy=float(stretch.max() / stretch.min()),
        angle_click_sensitivity_deg=float(sensitivity),
        matrix=np.column_stack((linear, translation)).tolist())


def analyse(records, click_error=2.):
    """Screen test evidence suitability, never certify physical rotation/latency."""
    if click_error <= 0 or not math.isfinite(click_error):
        raise ValueError('click-error must be positive and finite')
    reference = records['reference']['points']
    count = len(reference)
    if any(len(records[role]['points']) != count for role in ROLES):
        raise ValueError('All five images must have the same point count/order')
    fits = {role: fit_points(reference, records[role]['points'], click_error)
            for role in ROLES if role != 'reference'}
    drift = fit_points(records['off']['points'], records['off_repeat']['points'], click_error)
    warnings = []
    for role, fit in fits.items():
        if fit['similarity_rms_px'] > max(5., 3 * click_error):
            warnings.append(role + ': high non-rigid residual; check points, perspective, shear or motion')
        if fit['affine_anisotropy'] > 1.03:
            warnings.append(role + ': anisotropy >3%; roll-only interpretation is questionable')
    angle = fits['off']['angle_clockwise_deg']
    residual = fits['corrected']['angle_clockwise_deg']
    sensitivity = fits['off']['angle_click_sensitivity_deg']
    if abs(angle) < max(2., 5 * sensitivity):
        warnings.append('Small input roll: correction ratio is sensitive to point-picking error')
    if (abs(drift['angle_clockwise_deg']) > max(.5, 2 * drift['angle_click_sensitivity_deg'])
            or drift['max_point_displacement_px'] > max(8., 4 * click_error)):
        warnings.append('off/off_repeat drift: camera/scene was not held still; repeat this trial')
    returned = fits['returned']
    if (abs(returned['angle_clockwise_deg']) > max(.5, 2 * returned['angle_click_sensitivity_deg'])
            or returned['max_point_displacement_px'] > max(8., 4 * click_error)):
        warnings.append('Return did not reproduce baseline; inspect grip, translation and point selection')
    if records['off'].get('sha256') == records['off_repeat'].get('sha256'):
        warnings.append('off/off_repeat identical bytes: cannot establish independent captures')
    for role in ('corrected', 'off', 'off_repeat'):
        if records[role].get('sha256') == records['reference'].get('sha256'):
            warnings.append(role + ': identical to baseline; check file roles/frozen capture')
    ratio = None
    if abs(angle) >= max(2., 5 * sensitivity):
        ratio = 100 * (1 - abs(residual) / abs(angle))
    return dict(
        schema='manual-angle-v1', method='manual landmarks + least-squares similarity; no tracker/ECC',
        coordinate_convention='image x right, y down; positive angle clockwise',
        quantity='apparent image-plane roll, not calibrated mechanical angle',
        assumed_radial_point_error_px=click_error,
        sensitivity_note='First-order point-picking sensitivity only; not a calibrated confidence interval',
        apparent_input_roll_deg=angle, corrected_residual_roll_deg=residual,
        residual_roll_reduction_percent=ratio, evidence_review='REVIEW' if warnings else 'CONSISTENT',
        review_note='CONSISTENT screens geometry only, not hardware acceptance or proof of compensation causality',
        warnings=warnings, fits=fits, off_repeat_drift=drift,
        hardware_ack=False, physical_angle_calibrated=False, latency_measured=False)


def read_image(path):
    payload = Path(path).read_bytes()
    image = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Cannot decode image: ' + str(path))
    return image, hashlib.sha256(payload).hexdigest()


def validate_records(records):
    checked = {}
    shape = None
    for role in ROLES:
        entry = records[role]
        path = Path(entry['file']).resolve()
        image, digest = read_image(path)
        if shape is None:
            shape = image.shape[:2]
        if image.shape[:2] != shape or shape != (1080, 1920):
            raise ValueError('Use unchanged 1920x1080 PNGs from S/reference, all same resolution')
        if entry.get('sha256') and entry['sha256'] != digest:
            raise ValueError('Image changed since point selection: ' + role)
        points = np.asarray(entry['points'], float)
        if (points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all()
                or (points < 0).any() or (points[:, 0] >= shape[1]).any()
                or (points[:, 1] >= shape[0]).any()):
            raise ValueError('Invalid/out-of-bounds points: ' + role)
        checked[role] = dict(file=str(path), sha256=digest, points=points.tolist())
    return checked


def pick_points(image, role, count, reference=None):
    # Stored coordinates refer to original pixels; preview is scaled uniformly.
    factor = min(1200 / image.shape[1], 720 / image.shape[0], 1.)
    points = []
    window = role + ' | left=add right=undo R=clear Enter=accept Q=cancel'
    def mouse(event, x, y, flags, parameter):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < count:
            points.append([x / factor, y / factor])
        elif event == cv2.EVENT_RBUTTONDOWN and points:
            points.pop()
    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window, mouse)
    reference_window = 'reference numbered points (same physical features/order)'
    if reference is not None:
        ref_image, ref_points = reference
        ref_display = cv2.resize(ref_image, None, fx=factor, fy=factor)
        for index, point in enumerate(ref_points, 1):
            location = tuple(np.round(np.array(point)*factor).astype(int))
            cv2.circle(ref_display, location, 5, (0, 255, 255), 2)
            cv2.putText(ref_display, str(index), location, cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 255), 2)
        cv2.imshow(reference_window, ref_display)
    try:
        while True:
            display = cv2.resize(image, None, fx=factor, fy=factor)
            for index, point in enumerate(points, 1):
                location = tuple(np.round(np.array(point)*factor).astype(int))
                cv2.circle(display, location, 5, (0, 255, 255), 2)
                cv2.putText(display, str(index), location, cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 255), 2)
            cv2.putText(display, '%s: %d/%d points' % (role, len(points), count),
                        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 0), 2)
            cv2.imshow(window, display)
            key = cv2.waitKey(20) & 255
            if key == ord('q') or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                raise KeyboardInterrupt('Point selection cancelled')
            if key == ord('r'):
                points.clear()
            if key in (10, 13) and len(points) == count:
                return points
    finally:
        cv2.destroyAllWindows()


def collect(initial_directory, count):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    files = {}
    try:
        directory = str(initial_directory)
        for role in ROLES:
            filename = filedialog.askopenfilename(
                parent=root, title=role + ': ' + LABELS[role], initialdir=directory,
                filetypes=[('Original PNG', '*.png')])
            if not filename:
                raise KeyboardInterrupt('File selection cancelled')
            files[role] = filename
            directory = str(Path(filename).parent)
    finally:
        root.destroy()
    records = {}
    reference = None
    for role in ROLES:
        image, digest = read_image(files[role])
        if image.shape[:2] != (1080, 1920):
            raise ValueError('Expected original 1920x1080 image: ' + role)
        print(role + ': ' + LABELS[role], flush=True)
        points = pick_points(image, role, count, reference)
        records[role] = dict(file=str(Path(files[role]).resolve()), sha256=digest, points=points)
        if role == 'reference':
            reference = image, points
    return records


def write_report(directory, records, result):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'points.json').write_text(json.dumps(dict(images=records), ensure_ascii=False, indent=2), encoding='utf-8')
    (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    rows = ['# 人工转动截图测量', '',
            '测量的是图像平面表观滚转；不代表精密机械角度或时延验收。正值为图像顺时针。', '',
            '| 项目 | 结果 |', '| --- | --- |',
            '| 关闭补偿后的表观转角 | %.3f° |' % result['apparent_input_roll_deg'],
            '| 补偿后残余转角 | %.3f° |' % result['corrected_residual_roll_deg'],
            '| 关闭补偿两次截图的转角差 | %.3f° |' % result['off_repeat_drift']['angle_clockwise_deg'],
            '| 回到原姿态后的转角差 | %.3f° |' % result['fits']['returned']['angle_clockwise_deg'],
            '| 几何证据筛查 | %s |' % result['evidence_review'], '',
            '残余角减少比例仅在同一转后姿态、图像有效且点选可靠时才有意义；不是整机防抖效率。', '',
            '点选敏感度不是置信区间。本次假设每张原图每点径向误差不超过%.1fpx；低估点选误差会夸大精度。'
            % result['assumed_radial_point_error_px'], '',
            '## 需要复核', '']
    rows += ['- ' + warning for warning in result['warnings']] or ['- 未触发默认几何筛查；仍须人工核对画面、姿态和日志。']
    rows += ['', '## 分项几何', '', '| 图像 | 转角° | 相似拟合RMS/px | 尺度 | 各向异性 | 点选角敏感度° |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for role, fit in result['fits'].items():
        rows.append('| %s | %.3f | %.2f | %.4f | %.4f | %.3f |' % (
            role, fit['angle_clockwise_deg'], fit['similarity_rms_px'], fit['scale'],
            fit['affine_anisotropy'], fit['angle_click_sensitivity_deg']))
    (directory / 'report.md').write_text('\n'.join(rows) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, default=Path.cwd(), help='Initial screenshot directory')
    parser.add_argument('--points', type=Path, help='Recompute from saved points.json without GUI')
    parser.add_argument('--out', type=Path, help='New output directory; existing paths are refused')
    parser.add_argument('--count', type=int, default=4, choices=range(4, 9))
    parser.add_argument('--click-error', type=float, default=2., help='Assumed original-pixel radial point error')
    args = parser.parse_args()
    try:
        records = (json.loads(args.points.read_text(encoding='utf-8-sig'))['images'] if args.points
                   else collect(args.session, args.count))
        records = validate_records(records)
        result = analyse(records, args.click_error)
        parent = Path(records['reference']['file']).parent
        directory = args.out or parent / ('measurement_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        write_report(directory, records, result)
        print('Report: ' + str(directory.resolve() / 'report.md'))
        print('Input image roll %.3f deg; residual %.3f deg; %s' % (
            result['apparent_input_roll_deg'], result['corrected_residual_roll_deg'], result['evidence_review']))
        return 0
    except KeyboardInterrupt:
        print('Cancelled; no UART commands were sent.')
        return 130
    except (ValueError, OSError, KeyError, np.linalg.LinAlgError, cv2.error) as exc:
        parser.exit(2, 'Measurement failed: ' + str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
