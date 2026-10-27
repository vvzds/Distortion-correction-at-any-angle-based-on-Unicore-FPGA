"""Hardware-free checks of wire format and actual destination-to-source sampling."""
import contextlib
import io
import json
import platform
import struct
import sys
import time

import cv2
import numpy as np
import serial
import board_trial as board
import uart_tool as uart


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
    start = point_error(physical @ previous, board.IDENTITY)
    for _ in range(6):
        cur = sampling(ref, physical @ previous)
        delta, confidence = board.estimate_sampling_delta(ref, cur, .25)
        assert delta is not None and confidence > .8
        candidate = board.propose(previous, delta, .5)
        board.check_candidate(candidate)
        _, previous = board.quantized_command(candidate)
    end = point_error(physical @ previous, board.IDENTITY)
    assert end < .8 and end < start * .15, (start, end)
    return dict(initial_max_point_error_px=start, final_max_point_error_px=end, iterations=6)


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

    def read(self, count):
        value = bytes(self.rx[:count])
        del self.rx[:count]
        return value


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
