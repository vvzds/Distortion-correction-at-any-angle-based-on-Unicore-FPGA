"""Known-point geometry and actual PNG/CLI/report regression; no board needed."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import cv2
import numpy as np

import angle_measure as tool

POINTS = np.array([[450., 230.], [1450., 250.], [1430., 830.], [470., 810.],
                   [950., 390.], [930., 700.]])


def transform(angle, scale=1., shift=(0., 0.)):
    a = np.deg2rad(angle)
    rotation = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    center = np.array([959.5, 539.5])
    return (POINTS-center) @ (scale*rotation).T + center + np.array(shift)


def records():
    return {role: dict(points=points.tolist(), sha256=role) for role, points in (
        ('reference', POINTS), ('corrected', transform(.2)), ('off', transform(12.)),
        ('off_repeat', transform(12.05)), ('returned', transform(.1)))}


def rejects(function):
    try:
        function()
    except ValueError:
        return
    raise AssertionError('Expected ValueError')


def main():
    for angle in (-12., -2., 0., 2., 12.):
        result = tool.fit_points(POINTS, transform(angle, 1.04, (25., -13.)))
        assert abs(result['angle_clockwise_deg'] - angle) < 1e-10
        assert abs(result['scale'] - 1.04) < 1e-10
        assert result['similarity_rms_px'] < 1e-9
    base = records()
    report = tool.analyse(base)
    assert report['evidence_review'] == 'CONSISTENT', report['warnings']
    assert abs(report['residual_roll_reduction_percent'] - 98.333333333333) < 1e-8
    changed = copy.deepcopy(base)
    changed['off_repeat']['points'] = transform(13., shift=(20., 0.)).tolist()
    assert any('drift' in w for w in tool.analyse(changed)['warnings'])
    changed = copy.deepcopy(base)
    changed['returned']['points'] = transform(2.).tolist()
    assert any('Return' in w for w in tool.analyse(changed)['warnings'])
    changed = copy.deepcopy(base)
    changed['off']['points'] = (POINTS @ np.diag([1.1, .9])).tolist()
    assert any('anisotropy' in w for w in tool.analyse(changed)['warnings'])
    changed = copy.deepcopy(base)
    changed['off']['points'][0][0] += 80
    assert any('residual' in w for w in tool.analyse(changed)['warnings'])
    changed = copy.deepcopy(base)
    changed['off_repeat']['sha256'] = changed['off']['sha256']
    assert any('identical bytes' in w for w in tool.analyse(changed)['warnings'])
    changed = copy.deepcopy(base)
    changed['off']['points'] = transform(.2).tolist()
    assert tool.analyse(changed)['residual_roll_reduction_percent'] is None
    rejects(lambda: tool.fit_points(POINTS, POINTS * [-1, 1]))
    rejects(lambda: tool.fit_points(POINTS[:3], POINTS[:3]))
    rejects(lambda: tool.fit_points(np.array([[1., 0.], [2., 0.], [3., 0.], [4., 0.]]),
                                    np.array([[1., 0.], [2., 0.], [3., 0.], [4., 0.]])))
    rejects(lambda: tool.analyse(base, float('nan')))
    noisy = transform(12.) + np.random.default_rng(7).normal(0., .8, POINTS.shape)
    noise_result = tool.fit_points(POINTS, noisy)
    assert abs(noise_result['angle_clockwise_deg'] - 12.) < .2
    with tempfile.TemporaryDirectory(prefix='manual_angle_') as temporary:
        root = Path(temporary) / '中文 with spaces'
        root.mkdir()
        disk_records = records()
        for i, role in enumerate(tool.ROLES):
            image = np.zeros((1080, 1920, 3), np.uint8)
            for number, point in enumerate(disk_records[role]['points']):
                cv2.circle(image, tuple(np.round(point).astype(int)), 10, (255, 255, 255), -1)
            cv2.putText(image, str(i), (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1., (255, 0, 0), 2)
            path = root / (role + '.png')
            path.write_bytes(cv2.imencode('.png', image)[1].tobytes())
            disk_records[role] = dict(file=str(path), points=disk_records[role]['points'])
        validated = tool.validate_records(disk_records)
        invalid = copy.deepcopy(validated)
        invalid['off']['sha256'] = 'wrong'
        rejects(lambda: tool.validate_records(invalid))
        invalid = copy.deepcopy(validated)
        invalid['off']['points'][0][0] = 1920
        rejects(lambda: tool.validate_records(invalid))
        manifest = root / 'points.json'
        manifest.write_text(json.dumps(dict(images=validated)), encoding='utf-8')
        output = root / 'report'
        completed = subprocess.run([sys.executable, str(Path(tool.__file__)), '--points',
                                    str(manifest), '--out', str(output)], capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        assert (output / 'report.md').is_file()
        result = json.loads((output / 'result.json').read_text(encoding='utf-8'))
        assert result['evidence_review'] == 'CONSISTENT'
        repeated = subprocess.run([sys.executable, str(Path(tool.__file__)), '--points',
                                   str(manifest), '--out', str(output)], capture_output=True, text=True)
        assert repeated.returncode == 2, repeated.stderr
        wrapper = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                  '-File', str(Path(tool.__file__).with_name('measure_trial.ps1')),
                                  '-PythonExe', sys.executable, '-Points', str(manifest),
                                  '-Out', str(root / 'wrapper_report'), '-ClickError', '3.5'],
                                 capture_output=True, text=True, encoding='utf-8')
        assert wrapper.returncode == 0, wrapper.stderr
        wrapper_result = json.loads((root / 'wrapper_report' / 'result.json').read_text(encoding='utf-8'))
        assert wrapper_result['assumed_radial_point_error_px'] == 3.5
    summary = dict(result='PASS', hardware_connected=False, gui_manually_tested=False,
                   known_rotation_translation_scale='PASS', direction_sign='PASS',
                   point_noise='PASS', drift_return_anisotropy_outlier_duplicate='PASS',
                   small_angle_ratio_suppression='PASS', invalid_points_and_hash='PASS',
                   actual_png_cli_and_unicode_paths='PASS', powershell_wrapper='PASS',
                   prevent_report_overwrite='PASS',
                   known_input_deg=12., measured_residual_deg=report['corrected_residual_roll_deg'])
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
