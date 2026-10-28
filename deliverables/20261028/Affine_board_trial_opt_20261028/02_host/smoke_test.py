"""Hardware-free checks of wire format and actual destination-to-source sampling."""
import contextlib
import io
import json
import platform
import struct
import sys
import time
import threading
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import serial
import board_trial as board
import uart_tool as uart
from tracking_engine import (RegistrationEstimator, EstimationWorker, ObservationError,
                             validate_geometry, match_quality, result_rejection)


def texture():
    rng = np.random.default_rng(20261027)
    image = rng.integers(0, 256, (540, 960), dtype=np.uint8)
    image = cv2.GaussianBlur(image, (7, 7), 1.5)
    for _ in range(200):
        x, y = rng.integers([25, 25], [935, 515])
        cv2.circle(image, (int(x), int(y)), int(rng.integers(3, 15)), int(rng.integers(0, 256)), -1)
    return image


def sampling(image, matrix):
    return cv2.warpAffine(image, matrix[:2], (image.shape[1], image.shape[0]),
                          flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)


def render(image, matrix):
    return cv2.warpAffine(image, matrix[:2], (image.shape[1], image.shape[0]),
                          flags=cv2.INTER_LINEAR)


def visible_from_command(matrix):
    return board.FLIP @ np.linalg.inv(matrix) @ board.FLIP


def point_error(a, b):
    points = np.array([[50., 910., 910., 50., 480.], [50., 50., 490., 490., 270.], [1., 1., 1., 1., 1.]])
    return float(np.linalg.norm(((a - b) @ points)[:2], axis=0).max())


def check_direction():
    ref = texture()
    known = np.array([[1., 0., 12.], [0., 1., -8.], [0., 0., 1.]])
    # No INVERSE_MAP here: source features move by known, so compensation
    # must sample current(known*p), not current(inv(known)*p).
    cur = cv2.warpAffine(ref, known[:2], (960, 540))
    estimate, confidence = board.estimate_sampling_delta(ref, cur, .25)
    assert estimate is not None and confidence > .9
    error = point_error(estimate, known)
    recovered = sampling(cur, estimate)
    roi = np.s_[40:-40, 40:-40]
    before = float(np.abs(cur[roi].astype(float) - ref[roi]).mean())
    after = float(np.abs(recovered[roi].astype(float) - ref[roi]).mean())
    assert error < .7 and after < before * .15, (error, before, after)
    return dict(max_point_error_px=error, image_mae_before=before, image_mae_after=after,
                confidence=confidence)


def check_composition():
    ref = texture()
    physical = board.homogeneous(cv2.getRotationMatrix2D((480., 270.), -2., 1.))
    physical[:2, 2] += [6., -4.]
    previous = board.homogeneous(cv2.getRotationMatrix2D((480., 270.), 1., 1.))
    previous[:2, 2] += [-3., 5.]
    start = point_error(visible_from_command(previous) @ physical, board.IDENTITY)
    for _ in range(6):
        cur = render(ref, visible_from_command(previous) @ physical)
        delta, confidence = board.estimate_sampling_delta(ref, cur, .25)
        assert delta is not None and confidence > .8
        candidate = board.propose(previous, delta, .5)
        board.check_candidate(candidate)
        _, previous = board.quantized_command(candidate)
    end = point_error(visible_from_command(previous) @ physical, board.IDENTITY)
    assert end < .8 and end < start * .15, (start, end)
    return dict(initial_max_point_error_px=start, final_max_point_error_px=end, iterations=6)


def check_step_controller():
    target = board.homogeneous(cv2.getRotationMatrix2D((960., 540.), 12., 1.))
    target[:2, 2] += [260., -180.]
    candidate, fraction = board.propose(board.IDENTITY, target, .7, 1.25, 40., report=True)
    angle = abs(float(np.rad2deg(np.arctan2(candidate[1, 0], candidate[0, 0]))))
    displacement = float(np.linalg.norm(candidate[:2, 2]))
    assert 0 < fraction < 1 and angle <= 1.3 and displacement <= 40.1
    board.check_candidate(candidate)
    return dict(step_fraction=fraction, rotation_step_deg=angle,
                translation_step_px=displacement)


def check_confidence_gate():
    gate = board.ConfidenceGate(3, .75, 2)
    assert gate.reject() == (False, False) and gate.state == gate.HOLD
    assert not gate.accept(.80) and gate.state == gate.HOLD
    assert gate.accept(.80) and gate.state == gate.GOOD
    assert gate.reject() == (False, False)
    assert gate.reject() == (False, False)
    assert gate.reject() == (False, True) and gate.state == gate.DEGRADED
    gate.reset()
    assert gate.state == gate.GOOD
    return dict(single_bad_frame='hold', consecutive_bad_frames='degraded',
                recovery_frames=2)


def check_timeout_and_consecutive():
    gate = board.ConfidenceGate(3, .75, 2, hold_timeout=2.5)
    gate.reject(now=0.)
    for i in range(1, 21):
        assert not gate.accept(.70, now=i * .1)
        assert gate.low_streak == 0
    assert not gate.tick(2.49)
    assert gate.tick(2.5) and gate.state == gate.DEGRADED
    gate.reset()
    for t in (.0, .4, .8, 1.2):
        assert gate.reject(now=t) == (False, False)
        assert not gate.accept(.70, now=t + .1)
        assert gate.state == gate.HOLD and gate.low_streak == 0
    assert gate.accept(.80, now=1.4) is False
    assert gate.accept(.80, now=1.5) is True
    return dict(middle_confidence_timeout='PASS', interleaved_failures='not_consecutive',
                timed_recovery='PASS')


def check_raw_and_quality():
    for matrix in (np.diag([-1., -1., 1.]), np.diag([2., .5, 1.]),
                   np.array([[1., 0., 9000.], [0., 1., 0.], [0., 0., 1.]])):
        try:
            board.propose(board.IDENTITY, matrix, .01, 1.25, 40.)
        except ValueError:
            pass
        else:
            raise AssertionError('Bad raw geometry hidden by a small step')
    src = np.float32([[x, y] for x in (80., 300., 600., 880.) for y in (60., 260., 470.)])
    dst = src + [12., -8.]
    matrix = np.array([[1., 0., 12.], [0., 1., -8.]])
    good = match_quality(src, dst, np.ones(len(src)), matrix, (540, 960))
    for inliers, observed in ((np.r_[np.ones(4), np.zeros(8)], dst),
                              (np.ones(12), dst + 20.)):
        try:
            match_quality(src, observed, inliers, matrix, (540, 960))
        except ObservationError:
            pass
        else:
            raise AssertionError('Bad feature quality accepted')
    return dict(raw_rejection='PASS', good_inliers=good['inliers'], mismatched_features='rejected')


def check_polar_and_corners():
    for angle in (5., 15.):
        initial = board.rotation(8.)
        candidate = board.propose(initial, board.rotation(angle), .6, 1.25, 40.)
        assert np.allclose(np.linalg.svd(candidate[:2, :2], compute_uv=False), [1., 1.], atol=1e-9)
        corners = np.array([[0., 1919., 0., 1919.], [0., 0., 1079., 1079.], [1., 1., 1., 1.]])
        assert np.linalg.norm(((candidate-initial) @ corners)[:2], axis=0).max() <= 60.0001
    return dict(pure_rotation_scale='preserved', final_corner_limit='PASS')


def check_cache_and_freshness():
    ref = texture()
    current = cv2.warpAffine(ref, np.float32([[1, 0, 12], [0, 1, -8]]), (960, 540))
    estimator = RegistrationEstimator()
    job = dict(generation=1, reference=ref, gray=current, scale=.25, budget=2., confidence_min=.65)
    for _ in range(2):
        result = estimator.estimate(job, lambda: False)
        assert point_error(result['delta'], np.array([[1.,0.,12.],[0.,1.,-8.],[0.,0.,1.]])) < .7
    assert estimator.estimate(job, lambda: False)['quality']['reference_cache_builds'] == 1
    assert estimator.cache_builds == 1
    large_error = []
    for angle in (-12., 12.):
        target = board.homogeneous(cv2.getRotationMatrix2D((480.,270.), angle, 1.))
        target[:2,2] += [80.,-40.]
        moved = cv2.warpAffine(ref, target[:2], (960,540))
        value = estimator.estimate(dict(job, generation=int(angle+20), gray=moved), lambda: False)
        large_error.append(point_error(value['delta'],target))
        assert value['quality']['inlier_ratio'] > .55 and value['quality']['overlap'] > .75
    assert max(large_error) < 1.
    try:
        estimator.estimate(dict(job, budget=0.), lambda: False)
    except ObservationError as exc:
        assert 'budget' in str(exc)
    else:
        raise AssertionError('Budget was ignored')
    observation = dict(generation=1, captured_monotonic=10., started_monotonic=10.,
                       finished_monotonic=10.1)
    assert result_rejection(observation, 1, 10.2, 9., .45, .25) is None
    assert result_rejection(observation, 2, 10.2, 9., .45, .25) == 'obsolete_anchor'
    assert result_rejection(observation, 1, 10.6, 9., .45, .25) == 'stale_decoded_frame'
    assert result_rejection(observation, 1, 10.2, 10.1, .45, .25) == 'before_settle_deadline'
    assert result_rejection(dict(observation, finished_monotonic=10.3), 1, 10.3, 9., .45, .25) == 'estimation_budget_exceeded'
    return dict(reference_cache_builds=estimator.cache_builds, stale_results='rejected',
                budget='enforced', large_rotation_max_point_error_px=max(large_error))


def check_worker_cancellation():
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    class SlowEstimator:
        def estimate(self, job, cancelled):
            entered.set()
            assert release.wait(2.)
            finished.set()
            return dict(delta=np.eye(3), confidence=.99)
    worker = EstimationWorker(SlowEstimator())
    job = dict(generation=1, frame=1, stamp=time.monotonic(), sent_matrix=np.eye(3))
    try:
        assert worker.submit(job) and entered.wait(2.)
        assert not worker.submit(dict(job, frame=2))  # no queue behind slow work
        worker.invalidate()  # same invalidation as D/R/Q
        release.set()
        assert finished.wait(2.)
        deadline = time.monotonic() + 2.
        while worker.busy and time.monotonic() < deadline:
            time.sleep(.001)
        assert not worker.busy and worker.poll() is None
        assert worker.submit(dict(job, generation=2, frame=3))
        result = None
        deadline = time.monotonic() + 2.
        while result is None and time.monotonic() < deadline:
            result = worker.poll()
            time.sleep(.001)
        assert result is not None and result['generation'] == 2
    finally:
        release.set()
        worker.close()
    return dict(no_backlog='PASS', invalidated_result='discarded', next_anchor='accepted')


def check_camera_controls_with_blocked_estimator():
    entered, release = threading.Event(), threading.Event()
    class SlowEstimator:
        def estimate(self, job, cancelled):
            entered.set()
            release.wait(3.)
            return dict(delta=np.eye(3), confidence=.99)
    class FakeCamera:
        def __init__(self, index):
            self.sequence = 0
            self.frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        def get(self):
            self.sequence += 1
            return self.sequence, time.monotonic(), self.frame
        def close(self):
            pass
    journal, connection = MemoryJournal(), MockSerial()
    journal.directory = Path('.')
    saved = []
    state = dict(disabled=False, reanchored=False)
    started = time.monotonic()
    def keyboard(_):
        time.sleep(.002)
        if time.monotonic() - started > 2.5:
            raise AssertionError('Control integration timed out')
        if entered.is_set() and not state['disabled']:
            state['disabled'] = True
            return ord('d')
        if state['disabled'] and not state['reanchored']:
            state['reanchored'] = True
            return ord('r')
        if sum(e['kind'] == 'anchor' for e in journal.entries) >= 2:
            release.set()
            return ord('q')
        return 255
    args = board.parser().parse_args(['track', '--port', 'MOCK', '--estimate-budget', '1.0',
                                      '--max-frame-age', '1.2'])
    factory = EstimationWorker
    with patch.object(board, 'LatestCamera', FakeCamera), \
         patch.object(board, 'EstimationWorker', lambda: factory(SlowEstimator())), \
         patch.object(board.cv2, 'imshow'), patch.object(board.cv2, 'waitKey', keyboard), \
         patch.object(board.cv2, 'getWindowProperty', return_value=1), \
         patch.object(board.cv2, 'destroyAllWindows'), \
         patch.object(board.cv2, 'imwrite', side_effect=lambda p, f: saved.append(p) or True):
        try:
            board.run_camera(args, connection, journal)
        finally:
            release.set()
    anchors = [e['file'] for e in journal.entries if e['kind'] == 'anchor']
    assert anchors == ['reference_001.png', 'reference_002.png']
    assert state['disabled'] and state['reanchored']
    assert not any(e['kind'] == 'matrix_sent' for e in journal.entries)
    assert connection.commands == [2, 2]  # D and R, both affine-off
    return dict(controls_during_blocked_estimate='PASS', distinct_anchors=anchors,
                stale_matrix_writes=0)


def check_coordinates():
    maximum = 0.
    for matrix in (board.rotation(5), board.rotation(-5),
                   np.array([[1.02, .03, 15.], [-.02, .98, -9.], [0., 0., 1.]])):
        wire, roundtrip = board.quantized_command(matrix)
        cmd, length, payload = uart.parse_frame(wire)
        assert cmd == 2 and length == 25 and len(wire) == 30 and payload[-1] == 1
        q = struct.unpack('<6i', payload[:24])
        hw = np.array([[q[0], q[1], q[4]], [q[2], q[3], q[5]], [0., 0., 65536.]]) / 65536.
        # Independent point equation: FPGA v=1079-y; source y=1079-v'.
        for x, y in ((0., 0.), (1919., 1079.), (800., 200.)):
            hp = hw @ [x, 1079. - y, 1.]
            actual = np.array([hp[0], 1079. - hp[1], 1.])
            expected = matrix @ [x, y, 1.]
            maximum = max(maximum, float(np.abs(actual - expected).max()))
            assert np.allclose(actual, roundtrip @ [x, y, 1.], atol=1e-9)
    assert maximum < .04, maximum
    return dict(max_roundtrip_pixel_error=maximum)


class MemoryJournal:
    def __init__(self):
        self.entries = []

    def event(self, kind, **fields):
        self.entries.append(dict(kind=kind, **fields))


class MockSerial:
    def __init__(self, short=False):
        self.short = short
        self.rx = bytearray()
        self.commands = []

    def write(self, wire):
        cmd, _, _ = uart.parse_frame(wire)
        self.commands.append(cmd)
        if cmd == 5:
            value = (123 << 16) | 0x112
            data = value.to_bytes(4, 'little')
            self.rx.extend(b'\xaa\x55\x05\x04' + data + bytes([sum(data) & 255]))
        return len(wire) - int(self.short)

    def reset_input_buffer(self):
        self.rx.clear()

    def flush(self):
        pass

    @property
    def in_waiting(self):
        return len(self.rx)

    def read(self, count):
        value = bytes(self.rx[:count])
        del self.rx[:count]
        return value


def check_incremental_status():
    journal, connection = MemoryJournal(), MockSerial()
    monitor = board.StatusMonitor(0.)
    monitor.tick(connection, journal, 2.)
    reply = bytes(connection.rx)
    connection.rx[:] = reply[:4]
    monitor.tick(connection, journal, 2.05)
    assert monitor.deadline is not None
    connection.rx[:] = reply[4:]
    monitor.tick(connection, journal, 2.1)
    assert monitor.deadline is None and monitor.last_pub == 123
    for query, receive in ((4.2,4.3),(6.4,6.5)):
        monitor.tick(connection,journal,query)
        monitor.tick(connection,journal,receive)
    monitor.tick(connection,journal,8.6)
    try:
        monitor.tick(connection,journal,8.7)
    except uart.ToolError as exc:
        assert 'stalled' in str(exc)
    else:
        raise AssertionError('Stalled publish counter accepted')
    monitor = board.StatusMonitor(0.)
    monitor.tick(connection,journal,2.)
    connection.rx.clear()
    try:
        monitor.tick(connection,journal,3.6)
    except uart.ToolError as exc:
        assert 'timeout' in str(exc)
    else:
        raise AssertionError('Missing status response accepted')
    return dict(fragmented_rx='PASS', waiting_read_calls=0, stalled='rejected', timeout='rejected')


def check_serial():
    log, connection = MemoryJournal(), MockSerial()
    value = board.status(connection, log)
    assert value == (123 << 16) | 0x112
    assert connection.commands == [5] and log.entries[-1]['kind'] == 'rx_status'
    try:
        board.send(MockSerial(short=True), uart.frame(5), log, 'test_short')
    except uart.ToolError:
        pass
    else:
        raise AssertionError('Short write was accepted')
    rows = uart.load_csv(board.ROOT / '03_params' / 'real_parameters.csv')
    assert len(rows) == 1
    uart.parse_frame(uart.build_distortion({key: rows[0][key] for key in uart.DISTORTION}))
    return dict(status_parser='PASS', short_write='rejected', real_csv='encodes')


def run(record_package=False):
    output = io.StringIO()
    results = dict(python=sys.version, platform=platform.platform(), numpy=np.__version__,
                   opencv=cv2.__version__, pyserial=serial.__version__, hardware_connected=False)
    failed = False
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        print('Board package minimal software smoke checks; no camera/UART/PDS run.')
        started = time.monotonic()
        try:
            assert uart.main(['selftest']) == 0
            results['uart_U0_U5'] = 'PASS'
        except Exception as exc:
            results['uart_U0_U5'] = 'FAIL: ' + repr(exc)
            failed = True
        for name, check in [('sampling_direction', check_direction),
                            ('closed_loop_composition', check_composition),
                            ('step_limited_controller', check_step_controller),
                            ('confidence_hysteresis', check_confidence_gate),
                            ('hold_timeout_and_consecutive', check_timeout_and_consecutive),
                            ('raw_geometry_and_features', check_raw_and_quality),
                            ('polar_and_corner_limit', check_polar_and_corners),
                            ('cache_budget_and_freshness', check_cache_and_freshness),
                            ('worker_cancellation', check_worker_cancellation),
                            ('incremental_status_monitor', check_incremental_status),
                            ('camera_controls_and_anchors', check_camera_controls_with_blocked_estimator),
                            ('fpga_y_and_q16', check_coordinates), ('serial_and_real_csv', check_serial)]:
            try:
                results[name] = dict(result='PASS', **check())
            except Exception as exc:
                results[name] = dict(result='FAIL', error=repr(exc))
                failed = True
            print(name, json.dumps(results[name], ensure_ascii=False))
        results['elapsed_seconds'] = time.monotonic() - started
        results['result'] = 'FAIL' if failed else 'PASS'
        print('OVERALL:', results['result'])
    target = (board.ROOT / '05_checks' if record_package else board.ROOT / 'sessions' /
              ('selftest_' + time.strftime('%Y%m%d_%H%M%S')))
    target.mkdir(exist_ok=True, parents=True)
    (target / 'host_smoke.log').write_text(output.getvalue(), encoding='utf-8')
    (target / 'host_smoke.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output.getvalue())
    return int(failed)


if __name__ == '__main__':
    sys.exit(run('--record-package' in sys.argv))
