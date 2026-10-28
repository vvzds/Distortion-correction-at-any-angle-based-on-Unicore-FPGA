"""C50 board trial entry point; FPGA/protocol unchanged. Python 3.10+."""
import argparse
import datetime as dt
import hashlib
import json
import math
import platform
from pathlib import Path
import sys
import threading
import time

import cv2
import numpy as np
import affine_track as legacy
import uart_tool as uart
from tracking_engine import EstimationWorker, RegistrationEstimator, result_rejection, validate_geometry
from evidence_recorder import EvidenceRecorder, summarise_session

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_VERSION = 'manual-20261028-r2'
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


def check_candidate(matrix, absolute_rot_limit=40., absolute_shift_limit=1500.):
    if not np.isfinite(matrix).all():
        raise ValueError('Non-finite affine estimate')
    singular = np.linalg.svd(matrix[:2, :2], compute_uv=False)
    if np.linalg.det(matrix[:2, :2]) <= 0 or singular.min() < .7 or singular.max() > 1.4:
        raise ValueError('Scale/shear outside representable trial envelope; keep last command')
    angle = abs(math.degrees(math.atan2(matrix[1, 0], matrix[0, 0])))
    if angle > absolute_rot_limit:
        raise ValueError('Absolute correction exceeds %.1f degrees; keep last command' % absolute_rot_limit)
    corners = np.array([[0., WIDTH - 1., 0., WIDTH - 1.],
                        [0., 0., HEIGHT - 1., HEIGHT - 1.],
                        [1., 1., 1., 1.]])
    displacement = np.linalg.norm(((matrix - IDENTITY) @ corners)[:2], axis=0).max()
    if displacement > absolute_shift_limit:
        raise ValueError('Absolute correction exceeds %.1f pixels; keep last command' % absolute_shift_limit)
    try:
        quantized_command(matrix)  # G02 checks all coefficients after y conversion.
    except uart.ToolError as exc:
        raise ValueError('Parameter range rejected: ' + str(exc)) from exc


class Journal:
    def __init__(self, directory):
        self.directory = directory
        self.lock = threading.Lock()
        directory.mkdir(parents=True, exist_ok=False)
        self.file = (directory / 'events.jsonl').open('w', encoding='utf-8')

    def event(self, kind, **fields):
        entry = dict(time=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
                     monotonic=time.monotonic(), kind=kind, **fields)
        with self.lock:
            if not self.file.closed:
                self.file.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + '\n')
                self.file.flush()

    def close(self):
        with self.lock:
            self.file.close()


class ConsoleMirror:
    def __init__(self, stream, file, lock):
        self.stream, self.file, self.lock = stream, file, lock

    def write(self, value):
        with self.lock:
            self.stream.write(value)
            if not self.file.closed:
                self.file.write(value)
                self.file.flush()
        return len(value)

    def flush(self):
        with self.lock:
            self.stream.flush()
            if not self.file.closed:
                self.file.flush()


def send(connection, data, journal, label):
    uart.parse_frame(data)
    started = time.monotonic()
    journal.event('tx_attempt', label=label, wire=data.hex())
    written = connection.write(data)
    connection.flush()
    if written != len(data):
        raise uart.ToolError('Short UART write; stop and run init again')
    # Deliberately called "sent", not "applied": protocol has no matrix ACK.
    journal.event('tx_complete', label=label, wire=data.hex(), duration_ms=1000*(time.monotonic()-started))


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
        self.capture_info = dict(requested_width=WIDTH, requested_height=HEIGHT,
            reported_width=self.cap.get(cv2.CAP_PROP_FRAME_WIDTH),
            reported_height=self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
            reported_fps=self.cap.get(cv2.CAP_PROP_FPS),
            reported_fourcc=self.cap.get(cv2.CAP_PROP_FOURCC),
            reported_buffer_size=self.cap.get(cv2.CAP_PROP_BUFFERSIZE),
            decoded_timestamp_is_exposure_time=False)
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
    journal.event('capture_open', **getattr(camera, 'capture_info', {}))
    worker = EstimationWorker() if args.mode == 'track' else None
    recorder = EvidenceRecorder(journal, video=not args.no_video)
    reference = None
    sent_matrix = IDENTITY.copy()
    affine_requested = False
    ready_at = time.monotonic() + max(.5, args.settle)
    generation, anchor_index, command_seq = 0, 0, 0
    last_submitted, last_video = -1, -1
    pending_at = None
    pending_image = None
    pending_metadata = None
    started = time.monotonic()
    monitor = StatusMonitor(started) if connection is not None else None
    active = args.mode == 'track'
    paused = False
    state = 'ANCHOR_WAIT' if active else 'PREVIEW'
    reason_text = ''
    last_auto = last_rejection_image = last_heartbeat = started
    next_video = started
    scheduled = []
    window = 'C50 MANUAL | D=OFF C=resume R=new reference S=stop+save B=move Q=quit'
    print(window, flush=True)
    print('Focus preview before pressing keys. Image failures never automatically disable affine.', flush=True)
    print('D=关闭补偿并暂停；C=沿用原参考继续；R=把当前姿态设为新参考；S=停稳取证；B=开始动作标记；Q=退出。', flush=True)

    def metadata(seq, stamp):
        return dict(frame=seq, decoded_monotonic=stamp, generation=generation,
                    anchor=anchor_index, command_seq=command_seq, state=state,
                    affine_requested=affine_requested, matrix_sent=sent_matrix.tolist())

    def invalidate():
        nonlocal pending_at, pending_image, pending_metadata
        if worker:
            worker.invalidate()
        pending_at = pending_image = pending_metadata = None

    try:
        while True:
            now = time.monotonic()
            item = camera.get()
            fresh = item is not None and now - item[1] <= 3.
            frame = item[2] if item is not None else None
            if frame is not None and frame.shape[:2] != (HEIGHT, WIDTH):
                raise RuntimeError('Capture must be 1920x1080; got %dx%d' %
                                   (frame.shape[1], frame.shape[0]))
            if item is None and now - started > 5.:
                raise RuntimeError('No capture frames; check capture-card index and other software')
            if frame is not None:
                seq, stamp, frame = item
                display = cv2.resize(frame, (960, 540))
                cv2.putText(display, '%s  anchor=%d sent=%d' % (state, anchor_index, command_seq),
                            (14, 28), cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 255, 255), 2)
                if reason_text:
                    cv2.putText(display, reason_text[:100], (14, 54), cv2.FONT_HERSHEY_SIMPLEX, .46, (0, 200, 255), 1)
                if recorder.errors:
                    cv2.putText(display, 'RECORDING ERROR - check console/disk', (14, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 0, 255), 2)
                cv2.imshow(window, display)
            # Manual keys are handled before any estimator result can write UART.
            key = cv2.waitKey(10) & 255
            if key == ord('q') or (frame is not None and cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1):
                invalidate()
                journal.event('manual_action', action='Q_exit', anchor=anchor_index, command_seq=command_seq)
                if frame is not None:
                    recorder.snapshot(frame, metadata(seq, stamp), 'exit')
                return
            if frame is not None and key in (ord('s'), ord('b')):
                role = 'off_snapshot' if paused else ('settled_snapshot' if key == ord('s') else 'motion_start')
                journal.event('manual_action', action='S_stopped_save' if key == ord('s') else 'B_motion_start',
                              anchor=anchor_index, command_seq=command_seq, frame=seq)
                name = recorder.snapshot(frame, metadata(seq, stamp), role)
                print('Saved request:', name, 'state=', state, flush=True)
                if key == ord('s'):
                    scheduled.extend((now + delay, generation, 'settle_%04dms' % int(delay*1000))
                                     for delay in (.5, 1.5, 3.))
            if connection is not None and key in (ord('r'), ord('d'), ord('c')):
                invalidate()
                scheduled.clear()
                generation += 1
                action = {ord('r'): 'R_new_reference', ord('d'): 'D_disable_pause', ord('c'): 'C_resume_original'}[key]
                journal.event('manual_action', action=action, anchor=anchor_index, command_seq=command_seq)
                if key != ord('c'):
                    if frame is not None:
                        recorder.snapshot(frame, metadata(seq, stamp), 'before_' + action[0])
                    send(connection, quantized_command(IDENTITY, False)[0], journal, 'manual_affine_off')
                    command_seq += 1
                    affine_requested = False
                    sent_matrix = IDENTITY.copy()
                ready_at = time.monotonic() + max(.5, args.settle)
                reason_text = ''
                if key == ord('r'):
                    reference = None
                    paused = False
                    state = 'ANCHOR_WAIT'
                    print('R: 当前姿态将成为新参考，请先保持不动。', flush=True)
                elif key == ord('d'):
                    paused = True
                    state = 'PAUSED'
                    scheduled.extend((now + delay, generation, role) for delay, role in
                                     ((1., 'off_after_D'), (2., 'off_repeat_after_D')))
                    print('D: 已发送关闭指令；原参考保留。保持姿态约2秒，自动保存两张关闭后的图。', flush=True)
                else:
                    paused = False
                    state = 'TRACKING' if reference is not None else 'ANCHOR_WAIT'
                    print('C: 沿用原参考继续尝试补偿。', flush=True)
                journal.event('control_state', state=state, generation=generation, anchor=anchor_index,
                              command_seq=command_seq, affine_requested=affine_requested)
            if monitor:
                monitor.tick(connection, journal, time.monotonic())
            if not fresh:
                if active and not paused:
                    state, reason_text = 'WAIT_IMAGE', 'capture missing/stale; keep last command, retrying'
                if now - last_heartbeat >= 1.:
                    journal.event('capture_wait', state=state)
                    last_heartbeat = now
                continue
            # All evidence records identify the decoded frame and last sent command;
            # neither is a sensor timestamp or a matrix-application acknowledgement.
            if now >= next_video and seq != last_video:
                recorder.video(display, metadata(seq, stamp))
                next_video = now + .1
                last_video = seq
            if now - last_auto >= args.auto_snapshot:
                recorder.snapshot(frame, metadata(seq, stamp), 'periodic')
                last_auto = now
            for due, saved_generation, role in list(scheduled):
                if now >= due and stamp >= due:
                    if saved_generation == generation:
                        recorder.snapshot(frame, metadata(seq, stamp), role)
                    scheduled.remove((due, saved_generation, role))
            if now - last_heartbeat >= 1.:
                journal.event('heartbeat', **metadata(seq, stamp),
                              decoded_age_ms=1000*(now-stamp), recorder_errors=recorder.errors,
                              recorder_dropped=recorder.dropped)
                last_heartbeat = now
            if pending_at is not None and now - pending_at > args.estimate_budget + .05:
                if pending_image is not None and now - last_rejection_image >= 2.:
                    recorder.snapshot(pending_image, pending_metadata, 'estimate_timeout')
                    last_rejection_image = now
                invalidate()
                state, reason_text = 'WAIT_IMAGE', 'estimate timed out; keep last command, retrying'
                journal.event('observation_timeout', state=state, generation=generation)
            result = worker.poll() if worker else None
            if result is not None and not paused:
                source_image, source_metadata = pending_image, pending_metadata
                pending_at = pending_image = pending_metadata = None
                reason = result_rejection(result, generation, time.monotonic(), ready_at,
                                          args.max_frame_age, args.estimate_budget)
                if not np.array_equal(result['sent_matrix'], sent_matrix):
                    reason = 'obsolete_command_reference'
                candidate = None
                fraction = None
                if reason is None:
                    try:
                        validate_geometry(result['delta'], frame.shape)
                        candidate, fraction = propose(sent_matrix, result['delta'], args.gain,
                            args.max_rot_step, args.max_shift_step, report=True, max_corner_step=args.max_corner_step)
                        check_candidate(candidate, args.absolute_rot_limit, args.absolute_shift_limit)
                        wire, candidate = quantized_command(candidate)
                        check_candidate(candidate, args.absolute_rot_limit, args.absolute_shift_limit)
                    except (ValueError, uart.ToolError) as exc:
                        reason = str(exc)
                journal.event('observation', frame=result['frame'], generation=result['generation'],
                    anchor=anchor_index, command_seq=command_seq,
                    captured_monotonic=result['captured_monotonic'],
                    estimate_started=result['started_monotonic'], estimate_finished=result['finished_monotonic'],
                    estimate_ms=result['estimate_ms'], decoded_age_ms=1000*(time.monotonic()-result['captured_monotonic']),
                    confidence=float(result['confidence']), quality=result.get('quality'),
                    error_stage=result.get('error_stage'), rejection=reason,
                    delta=None if result['delta'] is None else result['delta'].tolist())
                if reason is not None:
                    previous_state = state
                    state, reason_text = 'WAIT_IMAGE', reason
                    journal.event('skip_update', reason=reason, frame=result['frame'],
                                  command_seq=command_seq, keeping_last_matrix=True, automatic_affine_off=False)
                    if source_image is not None and (previous_state != state or now-last_rejection_image >= 2.):
                        recorder.snapshot(source_image, source_metadata, 'rejected_observation')
                        last_rejection_image = now
                else:
                    state, reason_text = 'TRACKING', ''
                    corners = np.array([[0.,1919.,0.,1919.],[0.,0.,1079.,1079.],[1.,1.,1.,1.]])
                    movement = float(np.linalg.norm(((candidate-sent_matrix) @ corners)[:2], axis=0).max())
                    if movement >= args.deadband_px:
                        send(connection, wire, journal, 'tracking_affine')
                        command_seq += 1
                        sent_matrix = candidate
                        affine_requested = True
                        ready_at = time.monotonic() + args.settle
                        journal.event('matrix_sent', cv_matrix=sent_matrix.tolist(), command_seq=command_seq,
                                      step_alpha=float(fraction), source_frame=result['frame'],
                                      anchor=anchor_index, corner_step_px=movement, application_ack=False)
            if active and not paused and stamp >= ready_at:
                if reference is None:
                    reference = legacy.to_gray(frame).copy()
                    anchor_index += 1
                    state = 'TRACKING'
                    name = 'reference_%03d.png' % anchor_index
                    recorder.snapshot(frame, metadata(seq, stamp), 'reference', name=name)
                    journal.event('anchor', frame=seq, generation=generation, anchor=anchor_index, file=name)
                    print('Reference captured:', name, '；现在可以开始转动。', flush=True)
                elif seq != last_submitted and time.monotonic()-stamp <= args.max_frame_age:
                    job = dict(generation=generation, reference=reference, gray=legacy.to_gray(frame),
                               frame=seq, stamp=stamp, sent_matrix=sent_matrix.copy(), scale=args.scale,
                               budget=args.estimate_budget, confidence_min=args.ecc_min,
                               model=args.model, refine=args.refine)
                    if worker.submit(job):
                        last_submitted = seq
                        pending_at = time.monotonic()
                        pending_image, pending_metadata = frame, metadata(seq, stamp)
    finally:
        if worker:
            worker.close()
        camera.close()
        cv2.destroyAllWindows()
        recorder.close()


def run_demo(args, connection, journal):
    camera = LatestCamera(args.cam)
    journal.event('capture_open', **getattr(camera, 'capture_info', {}))
    recorder = EvidenceRecorder(journal, video=not args.no_video)
    monitor = StatusMonitor(time.monotonic())
    window = 'C50 fixed demo | D=OFF+stop Q=quit'
    stages = [('identity', IDENTITY, True), ('rotate_plus5', rotation(5), True),
              ('rotate_minus5', rotation(-5), True), ('translate_right_sample40',
              np.array([[1.,0.,40.],[0.,1.,0.],[0.,0.,1.]]), True),
              ('after_exit_affine_off', IDENTITY, False)]
    next_video, last_video = 0., -1
    try:
        for index, (label, matrix, enabled) in enumerate(stages):
            send(connection, quantized_command(matrix, enabled)[0], journal, label)
            print('固定指令 %d/5: %s；保持镜头不动，自动截图。' % (index+1, label), flush=True)
            sent_at = time.monotonic()
            saved = False
            while time.monotonic()-sent_at < 3. or not saved:
                now = time.monotonic()
                item = camera.get()
                if item is not None:
                    seq, stamp, frame = item
                    if frame.shape[:2] != (HEIGHT, WIDTH):
                        raise RuntimeError('Fixed demo capture must be 1920x1080')
                    metadata = dict(frame=seq, decoded_monotonic=stamp, generation=index,
                                    anchor=0, command_seq=index+1, state='FIXED_'+label,
                                    affine_requested=enabled, matrix_sent=matrix.tolist())
                    display = cv2.resize(frame, (960,540))
                    cv2.putText(display, '%d/5 %s' % (index+1,label), (15,30),
                                cv2.FONT_HERSHEY_SIMPLEX, .7, (0,255,255), 2)
                    cv2.imshow(window, display)
                    if now >= next_video and seq != last_video:
                        recorder.video(display, metadata)
                        next_video, last_video = now+.1, seq
                    if not saved and stamp >= sent_at+1.5:
                        name = 'fixed_%02d_%s.png' % (index,label)
                        saved = recorder.snapshot(frame, metadata, 'fixed_'+label, name=name) is not None
                key = cv2.waitKey(10) & 255
                if key in (ord('d'),ord('q')) or (item is not None and cv2.getWindowProperty(window,cv2.WND_PROP_VISIBLE)<1):
                    send(connection, quantized_command(IDENTITY,False)[0], journal, 'manual_demo_affine_off')
                    journal.event('manual_action', action='D_or_Q_stop_fixed_demo', anchor=0)
                    return
                monitor.tick(connection, journal, now)
                if now-sent_at > 6.:
                    raise RuntimeError('Fixed-demo capture unavailable/stale or evidence writer overloaded')
        print('固定指令演示结束，已发送关闭仿射；五阶段原图和录像已记录。', flush=True)
    finally:
        camera.close()
        cv2.destroyAllWindows()
        recorder.close()


def parser():
    p = argparse.ArgumentParser(description='C50 board trial: init, fixed transforms, dynamic feedback')
    p.add_argument('mode', choices=['list', 'selftest', 'init', 'status', 'demo', 'reset', 'preview', 'track'])
    p.add_argument('--port', help='Actual CP210x COM port; no implicit COM11 assumption')
    p.add_argument('--cam', type=int, default=0)
    p.add_argument('--params', type=Path, default=ROOT / '03_params' / 'real_parameters.csv')
    p.add_argument('--settle', type=float, default=.15, help='Minimum latest-only update interval; not an ACK')
    p.add_argument('--scale', type=float, default=.25)
    p.add_argument('--gain', type=float, default=.9)
    p.add_argument('--ecc-min', type=float, default=.65)
    p.add_argument('--max-rot-step', type=float, default=6.,
                   help='Maximum rotation change per update in degrees')
    p.add_argument('--max-shift-step', type=float, default=100.,
                   help='Maximum translation change per update in pixels')
    p.add_argument('--absolute-rot-limit', type=float, default=40.,
                   help='Absolute safety envelope in degrees')
    p.add_argument('--absolute-shift-limit', type=float, default=1500.,
                   help='Absolute corner displacement safety envelope in pixels')
    p.add_argument('--estimate-budget', type=float, default=.3,
                   help='Soft seconds budget between OpenCV stages; late results discarded')
    p.add_argument('--max-frame-age', type=float, default=.6,
                   help='Maximum age since PC decode; not camera exposure time')
    p.add_argument('--max-corner-step', type=float, default=180.)
    p.add_argument('--deadband-px', type=float, default=1.2)
    p.add_argument('--model', choices=['affine', 'similarity'], default='affine')
    p.add_argument('--refine', choices=['checked', 'features'], default='checked')
    p.add_argument('--auto-snapshot', type=float, default=5.)
    p.add_argument('--no-video', action='store_true', help='Still saves PNG evidence and timestamps')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if (not .05 <= args.settle <= 10 or not .125 <= args.scale <= 1 or
            not 0 < args.gain <= 1 or not 0 <= args.ecc_min <= 1 or
            not .05 <= args.max_rot_step <= 20 or not .5 <= args.max_shift_step <= 800 or
            not 1 <= args.absolute_rot_limit <= 45 or not 10 <= args.absolute_shift_limit <= 1800 or
            not .05 <= args.estimate_budget <= 2 or
            not args.estimate_budget <= args.max_frame_age <= 3 or
            not 1 <= args.max_corner_step <= 200 or not 0 <= args.deadband_px <= 10 or
            not 1 <= args.auto_snapshot <= 60):
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
    console_file = (folder / 'console.log').open('w', encoding='utf-8')
    original_stdout, original_stderr = sys.stdout, sys.stderr
    console_lock = threading.Lock()
    sys.stdout = ConsoleMirror(original_stdout, console_file, console_lock)
    sys.stderr = ConsoleMirror(original_stderr, console_file, console_lock)
    connection = None
    safe_exit = False
    journal.event('session_start', mode=args.mode, port=args.port, camera=args.cam,
                  package_version=PACKAGE_VERSION,
                  settle=args.settle, scale=args.scale, gain=args.gain,
                  max_rot_step=args.max_rot_step, max_shift_step=args.max_shift_step,
                  absolute_rot_limit=args.absolute_rot_limit,
                  absolute_shift_limit=args.absolute_shift_limit,
                  automatic_image_degradation=False, estimate_budget=args.estimate_budget,
                  max_frame_age=args.max_frame_age, max_corner_step=args.max_corner_step,
                  deadband_px=args.deadband_px, model=args.model, refine=args.refine,
                  auto_snapshot=args.auto_snapshot, video_recording=not args.no_video,
                  command_line=sys.argv if argv is None else argv,
                  python=sys.version, python_executable=sys.executable, platform=platform.platform(),
                  source_sha256={name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                                 for name in ('board_trial.py', 'tracking_engine.py', 'evidence_recorder.py')},
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
            run_demo(args, connection, journal)
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
        try:
            summarise_session(folder)
        except Exception as exc:
            print('Summary generation failed; events.jsonl remains available:', exc, file=sys.stderr)
        print('本次记录目录：', folder, flush=True)
        sys.stdout, sys.stderr = original_stdout, original_stderr
        console_file.close()
        if restore_error is not None:
            raise uart.ToolError('Exit restore failed; run reset/init after reconnecting: ' + str(restore_error))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
