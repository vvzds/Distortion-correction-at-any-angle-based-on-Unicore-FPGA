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

ROOT = Path(__file__).resolve().parent.parent
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


def estimate_sampling_delta(reference, current, scale):
    # Legacy ECC uses template=current,input=reference, yielding the reverse
    # of the destination-to-source sampling transform needed by C50.
    reverse, confidence = legacy.estimate_delta(reference, current, scale)
    if reverse is None or not math.isfinite(confidence):
        return None, 0.
    matrix = homogeneous(reverse)
    if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix[:2, :2])) < 1e-5:
        return None, 0.
    return np.linalg.inv(matrix), confidence


def propose(sent_matrix, delta, gain):
    increment = IDENTITY + gain * (delta - IDENTITY)
    return homogeneous(legacy.compose(sent_matrix, increment[:2]))


def check_candidate(matrix):
    if not np.isfinite(matrix).all():
        raise ValueError('Non-finite affine estimate')
    singular = np.linalg.svd(matrix[:2, :2], compute_uv=False)
    if np.linalg.det(matrix[:2, :2]) <= 0 or singular.min() < .7 or singular.max() > 1.4:
        raise ValueError('Scale/shear outside trial envelope; reanchor with R')
    quantized_command(matrix)  # G02 checks all coefficients after y conversion.


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
    reference = None
    sent_matrix = IDENTITY.copy()
    ready_at = time.monotonic() + args.settle
    next_status = time.monotonic() + 2.
    last_pub, last_progress = None, time.monotonic()
    last_sequence = -1
    started = time.monotonic()
    active = args.mode == 'track'
    degraded = False
    window = 'C50 trial | R=reset/reanchor D=disable S=save Q=quit'
    print(window, flush=True)
    try:
        while True:
            item = camera.get()
            now = time.monotonic()
            if item is None or now - item[1] > 3.:
                if now - started > 5.:
                    raise RuntimeError('Capture missing/stale; tracking stopped')
                time.sleep(.02)
                continue
            seq, stamp, frame = item
            if frame.shape[:2] != (HEIGHT, WIDTH):
                raise RuntimeError('Capture must be 1920x1080; got %dx%d' %
                                   (frame.shape[1], frame.shape[0]))
            if seq == last_sequence:
                time.sleep(.005)
                continue
            last_sequence = seq
            if connection is not None and now >= next_status:
                value = status(connection, journal)
                require_valid(value)
                pub = value >> 16
                if last_pub is None or pub != last_pub:
                    last_progress = time.monotonic()
                elif now - last_progress > 5.:
                    raise RuntimeError('Publish count stalled; stop and run init again')
                last_pub = pub
                next_status = time.monotonic() + 2.
            gray = legacy.to_gray(frame)
            if active and not degraded and stamp >= ready_at:
                if reference is None:
                    reference = gray.copy()
                    cv2.imwrite(str(journal.directory / 'reference.png'), frame)
                    journal.event('anchor', frame=seq)
                    print('Reference captured. Move camera slowly; Q restores affine-off.', flush=True)
                else:
                    delta, confidence = estimate_sampling_delta(reference, gray, args.scale)
                    journal.event('estimate', frame=seq, captured_monotonic=stamp,
                                  confidence=float(confidence),
                                  delta=None if delta is None else delta.tolist())
                    try:
                        if delta is None or confidence < args.ecc_min:
                            raise ValueError('Low confidence / scene changed')
                        candidate = propose(sent_matrix, delta, args.gain)
                        check_candidate(candidate)
                    except ValueError as exc:
                        send(connection, quantized_command(IDENTITY, False)[0], journal, 'degraded_affine_off')
                        sent_matrix = IDENTITY.copy()
                        degraded = True
                        journal.event('degraded', reason=str(exc))
                        cv2.imwrite(str(journal.directory / 'degraded.png'), frame)
                        print('DEGRADED: affine disabled; keep camera still and press R.', flush=True)
                    else:
                        a, b = legacy.to_params(candidate[:2]), legacy.to_params(sent_matrix[:2])
                        coeff, trans = legacy.params_diff(a, b)
                        if coeff >= .001 or trans >= .3:
                            wire, quantized = quantized_command(candidate)
                            send(connection, wire, journal, 'tracking_affine')
                            sent_matrix = quantized
                            journal.event('matrix_sent', cv_matrix=sent_matrix.tolist())
                            ready_at = time.monotonic() + args.settle
            display = cv2.resize(frame, (960, 540))
            state = 'PREVIEW' if not active else ('DEGRADED: R to reanchor' if degraded else 'TRACKING (trial)')
            cv2.putText(display, state, (18, 30), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 255), 2)
            cv2.imshow(window, display)
            key = cv2.waitKey(1) & 255
            if key == ord('q') or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                cv2.imwrite(str(journal.directory / 'last.png'), frame)
                return
            if key == ord('s'):
                name = 'snapshot_%06d.png' % seq
                cv2.imwrite(str(journal.directory / name), frame)
                journal.event('snapshot', file=name, frame=seq)
            if connection is not None and key in (ord('r'), ord('d')):
                send(connection, quantized_command(IDENTITY, False)[0], journal, 'manual_affine_off')
                sent_matrix = IDENTITY.copy()
                reference = None
                degraded = key == ord('d')
                ready_at = time.monotonic() + args.settle
                journal.event('manual_reset', reanchor=not degraded)
    finally:
        camera.close()
        cv2.destroyAllWindows()


def parser():
    p = argparse.ArgumentParser(description='C50 board trial: init, fixed transforms, dynamic feedback')
    p.add_argument('mode', choices=['list', 'selftest', 'init', 'status', 'demo', 'reset', 'preview', 'track'])
    p.add_argument('--port', help='Actual CP210x COM port; no implicit COM11 assumption')
    p.add_argument('--cam', type=int, default=0)
    p.add_argument('--params', type=Path, default=ROOT / '03_params' / 'real_parameters.csv')
    p.add_argument('--settle', type=float, default=.5, help='Minimum feedback settling time in seconds; not ACK')
    p.add_argument('--scale', type=float, default=.25)
    p.add_argument('--gain', type=float, default=.5)
    p.add_argument('--ecc-min', type=float, default=.65)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if not .2 <= args.settle <= 10 or not .125 <= args.scale <= 1 or not 0 < args.gain <= 1 or not 0 <= args.ecc_min <= 1:
        raise ValueError('Use settle .2..10, scale .125..1, gain (0,1], ecc-min 0..1')
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
                  settle=args.settle, scale=args.scale, gain=args.gain,
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
