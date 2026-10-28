"""C50 board trial entry point; FPGA/protocol unchanged. Python 3.10+."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
import sys
import threading
import time

import cv2
import numpy as np
import affine_track as legacy
import uart_tool as uart
from tracking_engine import EstimationWorker, RegistrationEstimator, result_rejection, validate_geometry

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_VERSION = 'opt-20261028'
IDENTITY = np.eye(3, dtype=np.float64)
WIDTH, HEIGHT = 1920, 1080
FLIP = np.array([[1., 0., 0.], [0., -1., HEIGHT - 1.], [0., 0., 1.]])


def homogeneous(matrix):
    return np.vstack((matrix, [0., 0., 1.])) if matrix.shape == (2, 3) else matrix.copy()


def cv_to_fpga(matrix):
    # OpenCV has top-left origin; C50 core feeds (x,1079-y) into map and
    # converts the source row back with 1079-map_sy. Thus A_hw = F A_cv F.
    return FLIP @ homogeneous(matrix) @ FLIP


def quantized_command(matrix, enable=True):
    hw = cv_to_fpga(matrix)
    values = legacy.to_params(hw[:2])
    wire = uart.build_affine(values, enable=int(enable))
    _, _, payload = uart.parse_frame(wire)
    q = [uart.decode_q16(payload[i:i + 4]) for i in range(0, 24, 4)]
    hw_q = np.array([[q[0], q[1], q[4]], [q[2], q[3], q[5]], [0., 0., 1.]])
    return wire, FLIP @ hw_q @ FLIP


def estimate_sampling_delta(reference, current, scale, recovery=False):
    # Synchronous compatibility helper for offline tests. The live loop uses
    # the same estimator in its worker with a tighter configurable budget.
    try:
        result = RegistrationEstimator().estimate(
            dict(generation=0, reference=reference, gray=current, scale=scale,
                 budget=2., confidence_min=.65), lambda: False)
        return result['delta'], result['confidence']
    except ValueError:
        return None, 0.


def propose(sent_matrix, delta, gain, max_rot_step=None, max_shift_step=None,
            report=False, max_corner_step=60.):
    """Polar interpolation at image center; validate raw motion before limiting."""
    increment = homogeneous(delta)
    validate_geometry(increment, (HEIGHT, WIDTH))
    u, singular, vt = np.linalg.svd(increment[:2, :2])
    orthogonal = u @ vt
    theta = math.atan2(orthogonal[1, 0], orthogonal[0, 0])
    stretch = vt.T @ np.diag(singular) @ vt
    eigenvalues, eigenvectors = np.linalg.eigh(stretch)
    center = np.array([(WIDTH - 1) / 2., (HEIGHT - 1) / 2.])
    center_shift = increment[:2, :2] @ center + increment[:2, 2] - center
    alpha = float(gain)
    if max_rot_step is not None and abs(theta) > 1e-12:
        alpha = min(alpha, math.radians(max_rot_step) / abs(theta))
    if max_shift_step is not None and np.linalg.norm(center_shift) > 1e-12:
        alpha = min(alpha, max_shift_step / float(np.linalg.norm(center_shift)))
    corners = np.array([[0., WIDTH-1., 0., WIDTH-1.],
                        [0., 0., HEIGHT-1., HEIGHT-1.], [1., 1., 1., 1.]])
    for _ in range(20):
        c, s = math.cos(theta * alpha), math.sin(theta * alpha)
        linear = np.array([[c, -s], [s, c]]) @ (eigenvectors @ np.diag(eigenvalues ** alpha) @ eigenvectors.T)
        step = IDENTITY.copy()
        step[:2, :2] = linear
        step[:2, 2] = center + alpha * center_shift - linear @ center
        result = homogeneous(sent_matrix) @ FLIP @ step @ FLIP
        movement = float(np.linalg.norm(((result - sent_matrix) @ corners)[:2], axis=0).max())
        if movement <= max_corner_step:
            return (result, alpha) if report else result
        alpha *= .8
    raise ValueError('Unable to bound corner movement')


def check_candidate(matrix, absolute_rot_limit=20., absolute_shift_limit=800.):
    if not np.isfinite(matrix).all():
        raise ValueError('Non-finite affine estimate')
    singular = np.linalg.svd(matrix[:2, :2], compute_uv=False)
    if np.linalg.det(matrix[:2, :2]) <= 0 or singular.min() < .7 or singular.max() > 1.4:
        raise ValueError('Scale/shear outside trial envelope; reanchor with R')
    angle = abs(math.degrees(math.atan2(matrix[1, 0], matrix[0, 0])))
    if angle > absolute_rot_limit:
        raise ValueError('Absolute correction exceeds %.1f degrees; reanchor with R' % absolute_rot_limit)
    corners = np.array([[0., WIDTH - 1., 0., WIDTH - 1.],
                        [0., 0., HEIGHT - 1., HEIGHT - 1.],
                        [1., 1., 1., 1.]])
    displacement = np.linalg.norm(((matrix - IDENTITY) @ corners)[:2], axis=0).max()
    if displacement > absolute_shift_limit:
        raise ValueError('Absolute correction exceeds %.1f pixels; reanchor with R' % absolute_shift_limit)
    try:
        quantized_command(matrix)  # G02 checks all coefficients after y conversion.
    except uart.ToolError as exc:
        raise ValueError('Parameter range rejected: ' + str(exc)) from exc


class ConfidenceGate:
    """Hysteresis: one bad frame holds the last legal matrix before degrading."""
    GOOD, HOLD, DEGRADED = 'GOOD', 'HOLD', 'DEGRADED'

    def __init__(self, low_frames=3, recover_confidence=.75, recover_frames=2,
                 hold_timeout=2.5):
        self.low_frames = int(low_frames)
        self.recover_confidence = float(recover_confidence)
        self.recover_frames = int(recover_frames)
        self.state = self.GOOD
        self.low_streak = 0
        self.recover_streak = 0
        self.hold_timeout = hold_timeout
        self.hold_since = None

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        if self.state == self.HOLD and now - self.hold_since >= self.hold_timeout:
            self.state = self.DEGRADED
            return True
        return False

    def reject(self, now=None):
        now = time.monotonic() if now is None else now
        if self.state == self.DEGRADED:
            return False, True
        if self.state == self.GOOD:
            self.hold_since = now
        self.low_streak += 1
        self.recover_streak = 0
        self.state = self.DEGRADED if self.low_streak >= self.low_frames else self.HOLD
        self.tick(now)
        return False, self.state == self.DEGRADED

    def accept(self, confidence, now=None):
        if self.tick(now):
            return False
        if self.state == self.DEGRADED:
            return False
        self.low_streak = 0  # a valid observation breaks consecutive failures
        if self.state == self.HOLD:
            if confidence < self.recover_confidence:
                self.recover_streak = 0
                return False
            self.recover_streak += 1
            if self.recover_streak < self.recover_frames:
                return False
        self.state = self.GOOD
        self.low_streak = 0
        self.recover_streak = 0
        self.hold_since = None
        return True

    def reset(self, degraded=False):
        self.state = self.DEGRADED if degraded else self.GOOD
        self.low_streak = 0
        self.recover_streak = 0
        self.hold_since = None


class Journal:
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=False)
        self.file = (directory / 'events.jsonl').open('w', encoding='utf-8')

    def event(self, kind, **fields):
        entry = dict(time=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
                     monotonic=time.monotonic(), kind=kind, **fields)
        self.file.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + '\n')
        self.file.flush()

    def close(self):
        self.file.close()


def send(connection, data, journal, label):
    uart.parse_frame(data)
    journal.event('tx_attempt', label=label, wire=data.hex())
    written = connection.write(data)
    connection.flush()
    if written != len(data):
        raise uart.ToolError('Short UART write; stop and run init again')
    # Deliberately called "sent", not "applied": protocol has no matrix ACK.
    journal.event('tx_complete', label=label, wire=data.hex())


def status(connection, journal):
    connection.reset_input_buffer()
    send(connection, uart.frame(0x05), journal, 'status_request')
    value = uart.read_status_frame(connection, timeout=1.5)
    payload = value.to_bytes(4, 'little')
    wire = uart.HEADER + b'\x05\x04' + payload + bytes([sum(payload) & 255])
    journal.event('rx_status', wire=wire.hex(), status=value,
                  valid=bool(value & 256), busy=bool(value & 512), pub=value >> 16)
    if value & 255 != 0x12:
        raise uart.ToolError('Unexpected firmware/protocol version: 0x%08X' % value)
    print('status=0x%08X valid=%d busy=%d pub=%d' %
          (value, bool(value & 256), bool(value & 512), value >> 16), flush=True)
    return value


def require_valid(value):
    if not value & 256:
        raise uart.ToolError('params_valid=0; check bitstream and real calibration CSV')


class StatusMonitor:
    """Incremental receive, same UART owner as control commands, no read wait."""
    def __init__(self, now):
        self.next_query = now + 2.
        self.deadline = None
        self.buffer = bytearray()
        self.last_pub = None
        self.last_progress = now

    def tick(self, connection, journal, now):
        if self.deadline is None:
            if now < self.next_query:
                return
            connection.reset_input_buffer()
            send(connection, uart.frame(0x05), journal, 'status_request')
            self.buffer.clear()
            self.deadline = now + 1.5
            return
        available = connection.in_waiting
        if available:
            self.buffer.extend(connection.read(min(64, available)))
        offset = self.buffer.find(uart.HEADER)
        if offset >= 0:
            del self.buffer[:offset]
            if len(self.buffer) >= 9:
                wire = bytes(self.buffer[:9])
                _, _, payload = uart.parse_frame(wire, status_reply=True)
                value = int.from_bytes(payload, 'little')
                journal.event('rx_status', wire=wire.hex(), status=value,
                              valid=bool(value & 256), busy=bool(value & 512), pub=value >> 16)
                if value & 255 != 0x12:
                    raise uart.ToolError('Unexpected status version')
                require_valid(value)
                pub = value >> 16
                if self.last_pub is None or pub != self.last_pub:
                    self.last_progress = now
                elif now - self.last_progress > 5.:
                    raise uart.ToolError('Publish count stalled; run init again')
                self.last_pub = pub
                self.deadline = None
                self.next_query = now + 2.
                return
        if len(self.buffer) > 512:
            del self.buffer[:-1]
        if now >= self.deadline:
            raise uart.ToolError('Status timeout; stop and reconnect')


def initialize(connection, args, journal):
    rows = uart.load_csv(args.params)
    if len(rows) != 1:
        raise ValueError('Trial requires exactly one calibration parameter row')
    row = rows[0]
    sequence = [('disable_affine', quantized_command(IDENTITY, False)[0]),
                ('disable_gamma', uart.build_mode(0)),
                ('real_brown4', uart.build_distortion({k: row[k] for k in uart.DISTORTION}))]
    for label, wire in sequence:
        send(connection, wire, journal, label)
    time.sleep(args.settle)
    before = status(connection, journal)
    require_valid(before)
    time.sleep(max(.25, args.settle))
    after = status(connection, journal)
    require_valid(after)
    if not 0 < (((after >> 16) - (before >> 16)) & 65535) < 32768:
        raise uart.ToolError('No forward publish progress during initialization')
    print('Real calibration loaded; affine/Gamma disabled. Publish progress observed.')


class LatestCamera:
    """Continuously drain DirectShow; estimates use latest decoded frame only."""
    def __init__(self, index):
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            self.cap.release()
            raise RuntimeError('Cannot open capture card; try another --cam index')
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.latest = None
        self.sequence = 0
        self.timestamp = 0.
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        while not self.stop.is_set():
            ok, frame = self.cap.read()
            if not ok:
                self.stop.wait(.02)
                continue
            with self.lock:
                self.latest = frame
                self.sequence += 1
                self.timestamp = time.monotonic()

    def get(self):
        with self.lock:
            if self.latest is None:
                return None
            return self.sequence, self.timestamp, self.latest.copy()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2.)
        self.cap.release()


def rotation(degrees):
    theta = np.deg2rad(degrees)
    linear = np.array([[np.cos(theta), -np.sin(theta)],
                       [np.sin(theta), np.cos(theta)]])
    center = np.array([(WIDTH - 1) / 2., (HEIGHT - 1) / 2.])
    result = IDENTITY.copy()
    result[:2, :2] = linear
    result[:2, 2] = center - linear @ center
    return result


def run_camera(args, connection, journal):
    camera = LatestCamera(args.cam)
    worker = EstimationWorker() if args.mode == 'track' else None
    reference = None
    sent_matrix = IDENTITY.copy()
    ready_at = time.monotonic() + max(.3, args.settle)
    last_submitted = -1
    pending_at = None
    generation, anchor_index = 0, 0
    started = time.monotonic()
    monitor = StatusMonitor(started) if connection is not None else None
    active = args.mode == 'track'
    gate = ConfidenceGate(args.low_confidence_frames, args.recover_confidence,
                          args.recover_frames, args.hold_timeout)
    window = 'C50 optimized | R=reset/reanchor D=disable S=save Q=quit'
    print(window, flush=True)

    def disable(reason, frame=None):
        nonlocal sent_matrix
        if worker:
            worker.invalidate()
        send(connection, quantized_command(IDENTITY, False)[0], journal, 'degraded_affine_off')
        sent_matrix = IDENTITY.copy()
        gate.state = ConfidenceGate.DEGRADED
        if frame is not None:
            cv2.imwrite(str(journal.directory / ('degraded_%03d.png' % generation)), frame)
        journal.event('degraded', reason=reason, generation=generation,
                      low_streak=gate.low_streak)
        print('DEGRADED: affine disabled; keep camera still and press R.', flush=True)

    try:
        while True:
            now = time.monotonic()
            item = camera.get()
            if (pending_at is not None and now - pending_at > args.estimate_budget + .05
                    and gate.state != ConfidenceGate.DEGRADED):
                worker.invalidate()
                pending_at = None
                _, should_degrade = gate.reject(now)
                journal.event('hold', reason='worker_budget_watchdog', state=gate.state,
                              low_streak=gate.low_streak)
                if should_degrade:
                    disable('worker_budget_watchdog', None if item is None else item[2])
            if gate.tick(now) and connection is not None:
                disable('hold_timeout', None if item is None else item[2])
            if item is None or now - item[1] > 3.:
                if now - started > 5.:
                    raise RuntimeError('Capture missing/stale; tracking stopped')
                time.sleep(.005)
                continue
            seq, stamp, frame = item
            if frame.shape[:2] != (HEIGHT, WIDTH):
                raise RuntimeError('Capture must be 1920x1080; got %dx%d' %
                                   (frame.shape[1], frame.shape[0]))
            result = worker.poll() if worker else None
            if result is not None and gate.state != ConfidenceGate.DEGRADED:
                pending_at = None
                reason = result_rejection(result, generation, time.monotonic(), ready_at,
                                          args.max_frame_age, args.estimate_budget)
                if not np.array_equal(result['sent_matrix'], sent_matrix):
                    reason = 'obsolete_command_reference'
                journal.event('observation', frame=result['frame'], generation=result['generation'],
                              captured_monotonic=result['captured_monotonic'],
                              estimate_started=result['started_monotonic'],
                              estimate_finished=result['finished_monotonic'],
                              estimate_ms=result['estimate_ms'],
                              decoded_age_ms=1000 * (time.monotonic() - result['captured_monotonic']),
                              confidence=float(result['confidence']), quality=result.get('quality'),
                              rejection=reason,
                              delta=None if result['delta'] is None else result['delta'].tolist())
                candidate = None
                if reason is None:
                    try:
                        # Check the raw estimate even when the proposed step is tiny.
                        validate_geometry(result['delta'], frame.shape)
                        candidate, fraction = propose(
                            sent_matrix, result['delta'], args.gain, args.max_rot_step,
                            args.max_shift_step, report=True, max_corner_step=args.max_corner_step)
                        check_candidate(candidate, args.absolute_rot_limit, args.absolute_shift_limit)
                        wire, candidate = quantized_command(candidate)
                        check_candidate(candidate, args.absolute_rot_limit, args.absolute_shift_limit)
                    except (ValueError, uart.ToolError) as exc:
                        reason = str(exc)
                if reason is not None:
                    if reason.startswith('obsolete_') or reason == 'before_settle_deadline':
                        journal.event('discard', reason=reason, frame=result['frame'])
                    else:
                        _, should_degrade = gate.reject()
                        journal.event('hold', reason=reason, state=gate.state,
                                      low_streak=gate.low_streak)
                        if should_degrade:
                            disable(reason, frame)
                elif gate.accept(result['confidence']):
                    a, b = legacy.to_params(candidate[:2]), legacy.to_params(sent_matrix[:2])
                    coeff, trans = legacy.params_diff(a, b)
                    if coeff >= .001 or trans >= .3:
                        # No queue: one result leads to at most one command.
                        send(connection, wire, journal, 'tracking_affine')
                        sent_matrix = candidate
                        ready_at = time.monotonic() + args.settle
                        journal.event('matrix_sent', cv_matrix=sent_matrix.tolist(),
                                      step_alpha=float(fraction), source_frame=result['frame'])
                else:
                    journal.event('hold', state=gate.state, low_streak=gate.low_streak,
                                  recover_streak=gate.recover_streak)
                    if gate.state == ConfidenceGate.DEGRADED:
                        disable('hold_timeout', frame)
            display = cv2.resize(frame, (960, 540))
            state = 'PREVIEW' if not active else gate.state
            cv2.putText(display, state, (18, 30), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 255), 2)
            cv2.imshow(window, display)
            key = cv2.waitKey(1) & 255
            if key == ord('q') or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                if worker:
                    worker.invalidate()
                cv2.imwrite(str(journal.directory / 'last.png'), frame)
                return
            if key == ord('s'):
                name = 'snapshot_%06d.png' % seq
                cv2.imwrite(str(journal.directory / name), frame)
                journal.event('snapshot', file=name, frame=seq, generation=generation)
            if connection is not None and key in (ord('r'), ord('d')):
                if worker:
                    worker.invalidate()
                generation += 1
                pending_at = None
                send(connection, quantized_command(IDENTITY, False)[0], journal, 'manual_affine_off')
                sent_matrix = IDENTITY.copy()
                reference = None
                gate.reset(degraded=key == ord('d'))
                ready_at = time.monotonic() + max(.3, args.settle)
                journal.event('manual_reset', reanchor=key != ord('d'), state=gate.state,
                              generation=generation)
            if monitor:
                monitor.tick(connection, journal, time.monotonic())
            if active and gate.state != ConfidenceGate.DEGRADED and stamp >= ready_at:
                if reference is None:
                    reference = legacy.to_gray(frame).copy()
                    anchor_index += 1
                    name = 'reference_%03d.png' % anchor_index
                    cv2.imwrite(str(journal.directory / name), frame)
                    journal.event('anchor', frame=seq, generation=generation, file=name)
                    print('Reference captured:', name, flush=True)
                elif seq != last_submitted and time.monotonic() - stamp <= args.max_frame_age:
                    job = dict(generation=generation, reference=reference,
                               gray=legacy.to_gray(frame), frame=seq, stamp=stamp,
                               sent_matrix=sent_matrix.copy(), scale=args.scale,
                               budget=args.estimate_budget,
                               confidence_min=args.ecc_min)
                    if worker.submit(job):
                        last_submitted = seq
                        pending_at = time.monotonic()
    finally:
        if worker:
            worker.close()
        camera.close()
        cv2.destroyAllWindows()


def parser():
    p = argparse.ArgumentParser(description='C50 board trial: init, fixed transforms, dynamic feedback')
    p.add_argument('mode', choices=['list', 'selftest', 'init', 'status', 'demo', 'reset', 'preview', 'track'])
    p.add_argument('--port', help='Actual CP210x COM port; no implicit COM11 assumption')
    p.add_argument('--cam', type=int, default=0)
    p.add_argument('--params', type=Path, default=ROOT / '03_params' / 'real_parameters.csv')
    p.add_argument('--settle', type=float, default=.15, help='Minimum latest-only update interval; not an ACK')
    p.add_argument('--scale', type=float, default=.25)
    p.add_argument('--gain', type=float, default=.6)
    p.add_argument('--ecc-min', type=float, default=.65)
    p.add_argument('--max-rot-step', type=float, default=1.25,
                   help='Maximum rotation change per update in degrees')
    p.add_argument('--max-shift-step', type=float, default=40.,
                   help='Maximum translation change per update in pixels')
    p.add_argument('--absolute-rot-limit', type=float, default=20.,
                   help='Absolute safety envelope in degrees')
    p.add_argument('--absolute-shift-limit', type=float, default=800.,
                   help='Absolute corner displacement safety envelope in pixels')
    p.add_argument('--low-confidence-frames', type=int, default=3,
                   help='Consecutive failed observations before affine-off')
    p.add_argument('--recover-confidence', type=float, default=.75,
                   help='Confidence required to leave HOLD')
    p.add_argument('--recover-frames', type=int, default=2,
                   help='Consecutive good recovery frames required')
    p.add_argument('--hold-timeout', type=float, default=2.5)
    p.add_argument('--estimate-budget', type=float, default=.25,
                   help='Soft seconds budget between OpenCV stages; late results discarded')
    p.add_argument('--max-frame-age', type=float, default=.45,
                   help='Maximum age since PC decode; not camera exposure time')
    p.add_argument('--max-corner-step', type=float, default=60.)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if (not .05 <= args.settle <= 10 or not .125 <= args.scale <= 1 or
            not 0 < args.gain <= 1 or not 0 <= args.ecc_min <= 1 or
            not .05 <= args.max_rot_step <= 20 or not .5 <= args.max_shift_step <= 800 or
            not 1 <= args.absolute_rot_limit <= 45 or not 10 <= args.absolute_shift_limit <= 1800 or
            not 1 <= args.low_confidence_frames <= 20 or
            not args.ecc_min <= args.recover_confidence <= 1 or not 1 <= args.recover_frames <= 10 or
            not .5 <= args.hold_timeout <= 10 or not .05 <= args.estimate_budget <= 2 or
            not args.estimate_budget <= args.max_frame_age <= 3 or
            not 1 <= args.max_corner_step <= 200):
        raise ValueError('Invalid settle/scale/gain/step/limit/recovery settings')
    if args.cam < 0:
        raise ValueError('Camera index must be nonnegative')
    if args.mode == 'list':
        return uart.main(['list'])
    if args.mode == 'selftest':
        from smoke_test import run
        return run()
    if args.mode != 'preview' and not args.port:
        raise ValueError('--port COMx required; use list to find CP210x')
    folder = ROOT / 'sessions' / dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    journal = Journal(folder)
    connection = None
    safe_exit = False
    journal.event('session_start', mode=args.mode, port=args.port, camera=args.cam,
                  package_version=PACKAGE_VERSION,
                  settle=args.settle, scale=args.scale, gain=args.gain,
                  max_rot_step=args.max_rot_step, max_shift_step=args.max_shift_step,
                  absolute_rot_limit=args.absolute_rot_limit,
                  absolute_shift_limit=args.absolute_shift_limit,
                  low_confidence_frames=args.low_confidence_frames,
                  recover_confidence=args.recover_confidence,
                  recover_frames=args.recover_frames,
                  hold_timeout=args.hold_timeout, estimate_budget=args.estimate_budget,
                  max_frame_age=args.max_frame_age, max_corner_step=args.max_corner_step,
                  numpy=np.__version__, opencv=cv2.__version__)
    print('Session:', folder, flush=True)
    try:
        if args.mode != 'preview':
            connection = uart.open_serial(args.port)
        if args.mode in ('init', 'demo', 'track'):
            initialize(connection, args, journal)
        if args.mode == 'status':
            status(connection, journal)
        elif args.mode == 'reset':
            send(connection, quantized_command(IDENTITY, False)[0], journal, 'affine_off')
            time.sleep(args.settle)
            status(connection, journal)
        elif args.mode == 'demo':
            for label, matrix in [('identity', IDENTITY), ('rotate_plus5', rotation(5)),
                                  ('rotate_minus5', rotation(-5)), ('translate_right_sample40',
                                   np.array([[1., 0., 40.], [0., 1., 0.], [0., 0., 1.]]))]:
                print('Fixed sampling transform:', label, flush=True)
                send(connection, quantized_command(matrix)[0], journal, label)
                time.sleep(max(2., args.settle))
                require_valid(status(connection, journal))
        elif args.mode in ('track', 'preview'):
            run_camera(args, connection, journal)
        safe_exit = True
        return 0
    except KeyboardInterrupt:
        safe_exit = True
        journal.event('interrupted')
        return 130
    except Exception as exc:
        journal.event('error', message=str(exc))
        print('STOP:', exc, '\nNo automatic retry. Reconnect and run init before restarting.', file=sys.stderr)
        return 1
    finally:
        restore_error = None
        if connection is not None:
            # On a communication/runtime error, stop all sends: delivery state is uncertain.
            # Q or Ctrl+C on a working connection explicitly restores affine-off.
            if safe_exit and args.mode in ('demo', 'track'):
                try:
                    send(connection, quantized_command(IDENTITY, False)[0], journal, 'normal_exit_affine_off')
                except Exception as exc:
                    restore_error = exc
                    print('Exit restore failed:', exc, file=sys.stderr)
                    journal.event('restore_failed', message=str(exc))
            connection.close()
        journal.event('session_end', normal=safe_exit)
        journal.close()
        if restore_error is not None:
            raise uart.ToolError('Exit restore failed; run reset/init after reconnecting: ' + str(restore_error))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
