"""IMU-only FPGA stabilization trial. Preview = unwarped HDMI capture.

No serial/capture device opens until main() runs. JY901P mode is receive-only;
BNO085 mode uses the FPGA's autonomous SPI feature configuration.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import queue
import threading
import time

import cv2
import numpy as np

from board_trial import Capture
from imu import (BAUD_CODES, ImuConnection, PoseHistory, inverse_affine,
                 load_mount, signed_us)
from model import ROOT, affine, compile_registers, load_calibration
from stabilizer import fast_guard
from bno085 import BnoConnection, MODES


CROP_LEVELS = tuple(round(1.0+i*.1, 1) for i in range(16))


def crop_step(zoom, direction):
    if direction > 0:
        return next((v for v in CROP_LEVELS if v > zoom+1e-6), CROP_LEVELS[-1])
    return next((v for v in reversed(CROP_LEVELS) if v < zoom-1e-6), CROP_LEVELS[0])


class Controller:
    def __init__(self, capture, args):
        self.capture, self.args = capture, args
        self.commands = queue.Queue()
        self.lock = threading.Lock()
        self.view = dict(state='CONNECTING', message='Identifying IMU bridge firmware', zoom=args.zoom)
        self.stop_event = threading.Event()
        self.tracking = False
        self.reference = None
        self.gamma = args.gamma
        self.base = np.vstack((affine(zoom=args.zoom), [0, 0, 1]))
        self.current = self.base.copy()
        self.history = PoseHistory()
        self.sensor_generation = None
        self.bno_diagnostics = None
        self.session = args.output / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.session.mkdir(parents=True)
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def snapshot(self):
        with self.lock:
            return dict(self.view)

    def update(self, **values):
        with self.lock:
            self.view.update(values)

    def action(self, name):
        self.commands.put(name)

    def log(self, event, **data):
        self.journal.write(json.dumps(dict(event=event, host_time=time.monotonic(), **data),
                           default=lambda v:v.tolist() if isinstance(v, np.ndarray) else str(v))+'\n')

    def send(self, matrix):
        fast_guard(self.calibration, matrix)
        # IMU feed-forward: no image-estimator rate limiter and no FPGA half-step
        # smoothing. The video engine still switches matrices only at frame start.
        self.link.set_target(compile_registers(self.calibration, matrix[:2], self.gamma, smooth=False))
        self.current = matrix.copy()
        self.log('target', matrix=matrix)

    def ready_pose(self, state):
        now = state['now']
        if state['seen'] != 3 or signed_us(now, state['angle_us']) > .15:
            raise ValueError('No fresh gyro + Euler; check IMU power, TX and selected baud')
        if signed_us(now, state['gyro_us']) > .08:
            raise ValueError('Gyro stale; affine held')
        if min(signed_us(now, state['gyro_us']), signed_us(now, state['angle_us'])) < -.005:
            raise ValueError('IMU timestamp unexpectedly ahead of FPGA time; inspect SH2 timing')
        if len(self.history.angles) < 5:
            raise ValueError('Collecting IMU samples')
        rate = self.history.rate()
        if self.args.sensor == 'bno085':
            diag = self.bno_diagnostics
            if not diag or not diag['status'] & 1:
                raise ValueError('BNO product identification pending; affine held')
            if diag['status'] & 128:
                raise ValueError('BNO startup/stream fault; inspect wiring and restart explicitly')
            if not diag['pose_interval_us'] or (self.args.bno_report != 'girv' and not diag['gyro_interval_us']):
                raise ValueError('BNO requested features not acknowledged yet')
        if rate < self.args.min_rate and not self.args.allow_low_rate:
            raise ValueError(f'IMU {rate:.1f} Hz; need >= {self.args.min_rate:.0f} Hz (10 Hz is diagnostic only)')
        if state['frames'] == 0 or signed_us(now, state['frame_us']) > .1:
            raise ValueError('Camera source-frame event stale; affine held')
        # frame_us denotes completed source frame, NOT HDMI capture arrival.
        # source_age: exposure midpoint -> source DDR completion; must measure.
        # packet_delay: sensor sample -> header arrival incl. internal latency;
        # convert desired exposure time to the sensor HEADER time domain.
        stamp = (state['frame_us']-round(self.args.source_age*1e6)+
                 round((self.args.packet_delay+self.args.command_lead)*1e6)) & 0xffffffff
        return self.history.at(stamp, self.args.max_prediction), rate

    def command(self, name, state):
        if name == 'toggle':
            name = 'off' if self.tracking else 'start'
        if name in ('start', 'reanchor'):
            if not self.mount_config.get('verified'):
                raise ValueError('Mount unverified: edit mount JSON after signed axis/rigid mount checks')
            pose, rate = self.ready_pose(state)
            if np.linalg.norm(state['gyro']) > 5.:
                raise ValueError('Hold camera still, then S/R to lock reference')
            self.reference = pose.copy()
            self.tracking = True
            self.last_frame = None
            self.send(self.base)
            self.update(state='LOCKED', message=f'IMU-only {self.args.mode}; reference locked, {rate:.1f}Hz')
            self.log('reference', pose=pose)
        elif name == 'off':
            self.tracking = False
            self.reference = None
            self.send(self.base)
            self.update(state='OFF', message='Calibrated image, fixed crop; rotation compensation off')
        elif name == 'pause':
            self.tracking = False
            self.reference = None
            self.update(state='PAUSED', message='Last matrix held; S/R locks a new reference')
        elif name in ('zoom_in', 'zoom_out'):
            zoom = crop_step(self.args.zoom, 1 if name=='zoom_in' else -1)
            base = np.vstack((affine(zoom=zoom), [0, 0, 1]))
            # Preserve the existing rotation/translation and reference, including
            # PAUSED or HOLD. Only change output crop about the same center.
            target = self.current @ np.linalg.inv(self.base) @ base
            self.send(target)  # Validate/send before committing the new crop.
            self.args.zoom, self.base = zoom, base
            self.update(zoom=zoom)
            self.log('crop', zoom=zoom)
        elif name == 'gamma':
            self.gamma = not self.gamma
            self.send(self.current)
        self.log('key', action=name)

    def run(self):
        self.link = None
        compatible = False
        try:
            with (self.session/'events.jsonl').open('w', encoding='utf-8') as self.journal:
                self.calibration = load_calibration(self.args.calibration)
                self.mount_config, self.mount = load_mount(self.args.mount)
                self.link = (BnoConnection if self.args.sensor == 'bno085' else ImuConnection)(self.args.port)
                state = self.link.imu_state()  # identify before changing FPGA state
                compatible = True
                if self.args.sensor == 'bno085':
                    state = self.link.set_mode(self.args.bno_report)
                else:
                    state = self.link.receiver_baud(self.args.imu_baud)
                self.log('session', args=vars(self.args), mount=self.mount_config)
                self.send(self.base)
                self.update(state='OFF', message='S locks stationary reference; X off; no image estimation')
                self.last_frame = None
                last_health = last_send = last_poll = 0.
                next_send = 0.
                while not self.stop_event.is_set():
                    tick = time.monotonic()
                    if tick-last_poll < 1/self.args.poll_rate:
                        time.sleep(.001)  # Python high-resolution sleep on Windows
                        continue
                    state = self.link.imu_state()
                    last_poll = tick
                    generation = state.get('generation')
                    if generation is not None and generation != self.sensor_generation:
                        if self.sensor_generation is not None:
                            self.tracking = False
                            self.reference = None
                            self.update(state='HOLD', message='BNO reset detected; keep still and S/R to reanchor')
                        self.sensor_generation = generation
                        self.history = PoseHistory()
                        self.bno_diagnostics = None
                    self.history.append(state)
                    self.update(rate=self.history.rate(), errors=state['errors'],
                                frames=state['frames'], gamma=self.gamma,
                                euler=state['euler'].tolist(), gyro=state['gyro'].tolist(),
                                angle_age_ms=signed_us(state['now'], state['angle_us'])*1000)
                    self.log('imu', data=state)
                    while not self.commands.empty():
                        try:
                            self.command(self.commands.get_nowait(), state)
                        except ValueError as exc:
                            self.update(message=str(exc))
                            self.log('command_rejected', reason=str(exc))
                    if self.capture.error:
                        raise RuntimeError(self.capture.error)
                    now = time.monotonic()
                    if self.tracking:
                        try:
                            pose, rate = self.ready_pose(state)
                            if state['frames'] != self.last_frame and now >= next_send-.002:
                                target = inverse_affine(self.calibration, self.reference, pose,
                                                        self.mount, self.args.zoom, self.args.mode,
                                                        self.args.max_tilt,
                                                        self.mount_config.get('roll_sign', 1))
                                self.send(target)
                                last_send = time.monotonic()
                                # Advance a cadence, not "last send + period":
                                # USB/scheduler jitter must not drop 30Hz to 25Hz.
                                next_send = max(next_send+1/self.args.command_rate,
                                                now+1/self.args.command_rate*.25)
                                self.last_frame = state['frames']
                            self.update(state='LOCKED', message=f'IMU-only {self.args.mode} {rate:.1f}Hz; crop fixed {self.args.zoom:.2f}')
                        except ValueError as exc:
                            # Keep last frame matrix. Never integrate through a stale
                            # interval or silently substitute a visual rotation estimate.
                            self.update(state='HOLD', message=str(exc))
                    if now-last_health >= 1.:
                        if self.args.sensor == 'bno085':
                            self.bno_diagnostics = self.link.diagnostics()
                            self.log('bno_diagnostics', data=self.bno_diagnostics)
                        health = self.link.status()
                        self.log('health', data=health)
                        if any(health[k] for k in ('core_fault', 'write_fault', 'overflow_tiles', 'rx_errors')):
                            raise RuntimeError(f'FPGA fault: {health}')
                        if self.tracking and self.last_frame is not None:
                            # Published fps includes the unchanged production
                            # core; source event fps alone is not enough evidence.
                            self.update(board_frames=health['frames'])
                        last_health = time.monotonic()
                    self.journal.flush()
                self.update(state='CLOSED', message='Closed; calibrated uncropped image restored')
        except Exception as exc:
            self.update(state='ERROR', message=str(exc))
        finally:
            if compatible and self.link is not None:
                try:
                    regs = compile_registers(self.calibration, np.eye(3)[:2], self.gamma)
                    self.link.configure(regs, timeout=.6)
                except Exception as exc:
                    self.update(cleanup_error=str(exc))
            if self.link is not None:
                self.link.close()
            (self.session/'summary.json').write_text(json.dumps(self.snapshot(), indent=2), encoding='utf-8')

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=4)


def preview(capture, controller, seconds=0):
    import tkinter as tk
    root = tk.Tk()
    root.title('FPGA IMU-only - live HDMI capture')
    root.geometry('1280x800')
    status = tk.StringVar()
    controls = tk.Frame(root)
    controls.pack(side='bottom', fill='x')
    for title, action in [('S 开始/锁参考', 'start'), ('X 关闭', 'off'), ('R 重新锁定', 'reanchor'),
                          ('P 冻结', 'pause'), ('G Gamma', 'gamma'),
                          ('− 裁边', 'zoom_out'), ('＋ 裁边', 'zoom_in')]:
        tk.Button(controls, text=title, command=lambda a=action:controller.action(a)).pack(side='left', padx=5, pady=5)
    tk.Button(controls, text='Q 退出', command=root.destroy).pack(side='right')
    tk.Label(root, textvariable=status, anchor='w', justify='left').pack(side='bottom', fill='x')
    label = tk.Label(root, bg='black')
    label.pack(fill='both', expand=True)
    actions = {'s':'start', 'r':'reanchor', 'x':'off', 'p':'pause', 'g':'gamma', ' ':'toggle',
               '+':'zoom_in', '=':'zoom_in', '-':'zoom_out'}
    def key(event):
        name = event.char.lower()
        if name in ('q', '\x1b'):
            root.destroy()
        elif name in actions:
            controller.action(actions[name])
    root.bind('<Key>', key)
    previous = [-1]
    deadline = time.monotonic()+seconds if seconds else float('inf')
    def refresh():
        item = capture.read()
        if item and item[0] != previous[0]:
            previous[0] = item[0]
            scale = min(max(320, label.winfo_width())/1920, max(180, label.winfo_height())/1080)
            rgb = cv2.cvtColor(cv2.resize(item[2], (int(1920*scale), int(1080*scale))), cv2.COLOR_BGR2RGB)
            label.photo = tk.PhotoImage(data=f'P6\n{rgb.shape[1]} {rgb.shape[0]}\n255\n'.encode()+rgb.tobytes(), format='PPM')
            label.configure(image=label.photo)
        state = controller.snapshot()
        angles = ','.join(f'{v:.1f}' for v in state.get('euler', [0, 0, 0]))
        gyro = ','.join(f'{v:.1f}' for v in state.get('gyro', [0, 0, 0]))
        status.set(f"{state['state']} | HDMI {capture.fps():.1f}fps | IMU {state.get('rate',0):.1f}Hz | "
                   f"crop {state.get('zoom',1.5):.2f}x | angle age {state.get('angle_age_ms',0):.0f}ms | errors {state.get('errors',0)}\n"
                   f"Euler XYZ [{angles}] deg | gyro XYZ [{gyro}] deg/s\n"
                   f"{state['message']}\nS/Space lock | X off | R new reference | P freeze | G gamma | +/- crop | Q quit")
        if time.monotonic() >= deadline:
            root.destroy()
        else:
            root.after(16, refresh)
    root.after(20, refresh)
    root.mainloop()


def arguments(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', default='COM9')
    p.add_argument('--camera', type=int)
    p.add_argument('--imu-baud', type=int, choices=BAUD_CODES, help='JY901P receive baud only; forbidden with BNO SPI')
    p.add_argument('--sensor', choices=['jy901p', 'bno085'], default='jy901p')
    p.add_argument('--bno-report', choices=MODES, default='game')
    p.add_argument('--mount', type=Path)
    p.add_argument('--calibration', default=str(ROOT/'calibration/ov5640_1080p.json'))
    p.add_argument('--mode', choices=['roll', 'affine'], default='roll')
    p.add_argument('--zoom', type=float, default=1.5)
    p.add_argument('--gamma', action='store_true')
    p.add_argument('--source-age', type=float, default=.0167, help='Exposure midpoint to DDR frame-complete seconds; must calibrate')
    p.add_argument('--packet-delay', type=float, default=0., help='Sensor sample to FPGA header-receipt seconds; must calibrate')
    p.add_argument('--command-lead', type=float, default=1/30, help='Target next source frame (frame period); approximate until board time alignment is measured')
    p.add_argument('--max-prediction', type=float, default=.025)
    p.add_argument('--max-tilt', type=float, default=15.)
    p.add_argument('--min-rate', type=float, default=80.)
    p.add_argument('--poll-rate', type=float, default=100.)
    p.add_argument('--command-rate', type=float, default=30.)
    p.add_argument('--allow-low-rate', action='store_true', help='Diagnostic only, not fast-motion acceptance')
    p.add_argument('--output', type=Path, default=ROOT/'reports/imu_runs')
    p.add_argument('--headless', action='store_true')
    p.add_argument('--seconds', type=float, default=0.)
    args = p.parse_args(argv)
    if args.sensor == 'bno085' and args.imu_baud is not None:
        p.error('BNO085 uses SPI; --imu-baud is only for JY901P')
    if args.imu_baud is None:
        args.imu_baud = 9600
    if args.mount is None:
        args.mount = ROOT/('calibration/bno085_mount.json' if args.sensor == 'bno085' else 'calibration/imu_mount.example.json')
    if not (1 <= args.zoom <= 2.5 and 0 <= args.source_age <= .2 and 0 <= args.packet_delay <= .1 and
            0 <= args.command_lead <= .05 and
            0 <= args.max_prediction <= .03 and 0 < args.max_tilt <= 20 and
            20 <= args.poll_rate <= 100 and 1 <= args.command_rate <= 30 and
            50 <= args.min_rate <= 200 and 0 <= args.seconds):
        p.error('IMU parameters outside supported ranges')
    load_mount(args.mount)
    return args


def main():
    args = arguments()
    cv2.setNumThreads(2)
    capture = Capture(args.camera)
    controller = Controller(capture, args)
    try:
        if args.headless:
            deadline = time.monotonic()+args.seconds if args.seconds else float('inf')
            while controller.thread.is_alive() and time.monotonic() < deadline:
                time.sleep(.05)
        else:
            preview(capture, controller, args.seconds)
    finally:
        controller.close()
        capture.close()
    print(json.dumps(controller.snapshot(), indent=2))


if __name__ == '__main__':
    main()
