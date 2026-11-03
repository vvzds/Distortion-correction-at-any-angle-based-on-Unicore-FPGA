"""Clean HDMI preview and reference-locked, frame-smoothed FPGA stabilization.

The displayed image is the capture-card image; Python does not stabilize or
warp the preview. All visible geometric compensation is rendered by the FPGA.
"""
import argparse
from collections import deque
from datetime import datetime
import json
from pathlib import Path
import queue
import threading
import time

import cv2
import numpy as np

from model import ROOT, affine, load_calibration, compile_registers
from protocol import Connection
from stabilizer import (ReferenceTracker, corner_distance, fast_guard,
                        FrameTimeline, SmoothTarget, ShapeStabilizer, matrix_from_registers)


class Capture:
    def __init__(self, index=None):
        if index is None:
            from cv2_enumerate_cameras import enumerate_cameras
            devices = [c for c in enumerate_cameras(cv2.CAP_DSHOW)
                       if c.name == 'Hagibis' and 'vid_345f' in c.path.lower()]
            if len(devices) != 1:
                raise RuntimeError('Hagibis not uniquely identified; select --camera INDEX explicitly')
            index = devices[0].index
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise RuntimeError('Could not open capture card; close other capture software')
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.lock = threading.Lock()
        self.latest = None
        self.number = 0
        self.stopped = False
        self.error = None
        self.stamps = deque(maxlen=90)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            while not self.stopped:
                ok, frame = self.cap.read()
                if not ok:
                    raise RuntimeError('Capture card stopped returning frames')
                if frame.shape != (1080, 1920, 3):
                    raise RuntimeError('Capture card must return unscaled 1920x1080 frames')
                stamp = time.monotonic()
                with self.lock:
                    self.number += 1
                    self.latest = (self.number, stamp, frame)
                    self.stamps.append(stamp)
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.cap.release()

    def read(self):
        with self.lock:
            return self.latest

    def fps(self):
        with self.lock:
            stamps = list(self.stamps)
        span = stamps[-1]-stamps[0] if len(stamps)>1 else 0.
        return (len(stamps)-1)/span if span>0 else 0.

    def close(self):
        self.stopped = True
        self.thread.join(timeout=2)


class Estimator:
    """One latest work item; an ORB refresh never blocks UART progression."""
    def __init__(self, width):
        self.tracker = ReferenceTracker(width)
        self.work = queue.Queue(maxsize=1)
        self.results = queue.Queue()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def submit(self, item):
        try:
            self.work.get_nowait()
        except queue.Empty:
            pass
        self.work.put_nowait(item)

    def run(self):
        while not self.stopped.is_set():
            try:
                generation, anchor, stamp, frame, seen = self.work.get(timeout=.1)
            except queue.Empty:
                continue
            started = time.monotonic()
            try:
                if anchor:
                    value = self.tracker.anchor(frame)
                else:
                    delta, quality = self.tracker.estimate(frame, started)
                    value = (seen@delta, quality)
                result = (generation, anchor, stamp, value, None, time.monotonic()-started)
            except (ValueError, cv2.error, np.linalg.LinAlgError) as exc:
                self.tracker.previous = None
                result = (generation, anchor, stamp, None, str(exc), time.monotonic()-started)
            self.results.put(result)


class Controller:
    def __init__(self, capture, args):
        self.capture, self.args = capture, args
        self.commands = queue.Queue()
        self.view_lock = threading.Lock()
        self.view = dict(state='CONNECTING', message='Opening UART; preview is live capture', tracking=False)
        self.stop_event = threading.Event()
        self.estimator = Estimator(args.analysis_width)
        self.timeline = FrameTimeline(args.capture_delay)
        self.generation = 0
        self.current = np.eye(3)
        self.base = np.vstack((affine(zoom=args.zoom), [0, 0, 1]))
        self.gamma = args.gamma
        self.tracking = self.arming = False
        self.last_send = 0.
        self.last_success = 0.
        self.records = 0
        self.published = None
        self.last_frame = -1
        self.smoother = SmoothTarget(self.base, args.response_time, args.max_speed)
        self.shape = ShapeStabilizer(self.base, args.shape_limit, args.shape_response, args.shape_rate)
        self.shape_stamp = None
        self.session = args.output / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.session.mkdir(parents=True, exist_ok=False)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def update(self, **values):
        with self.view_lock:
            self.view.update(values)

    def snapshot(self):
        with self.view_lock:
            return dict(self.view)

    def action(self, name):
        self.commands.put(name)

    def log(self, event, **values):
        self.records += 1
        record = dict(event=event, monotonic=time.monotonic(), **values)
        self.journal.write(json.dumps(record, default=lambda x: x.tolist() if isinstance(x, np.ndarray) else str(x))+'\n')
        self.journal.flush()

    def send(self, matrix, immediate=False):
        guard = fast_guard(self.calibration, matrix)
        registers = compile_registers(self.calibration, matrix[:2], self.gamma, smooth=not immediate)
        started = time.monotonic()
        if immediate:
            state = self.link.configure(registers, timeout=.6)
            if any(state[k] for k in ('core_fault','write_fault','overflow_tiles','rx_errors')):
                raise RuntimeError(f'FPGA health fault: {state}')
        else:
            self.link.set_target(registers)
            state = None
        self.current = matrix.copy()
        self.last_send = time.monotonic()
        fps = None
        if state is not None and self.published is not None:
            stamp, count = self.published
            fps = ((state['frames']-count)&0xffffffff)/(self.last_send-stamp)
        if state is not None:
            self.published = self.last_send, state['frames']
        self.update(gamma=self.gamma,
                    published_fps=fps, command_ms=1000*(self.last_send-started),
                    matrix=matrix.tolist())
        self.log('command_sent', matrix=matrix, registers=registers,
                 status=state, guard=guard, command_ms=1000*(self.last_send-started))

    def command(self, name):
        if name == 'toggle':
            name = 'off' if self.tracking or self.arming else 'start'
        if name in ('start', 'reanchor'):
            self.generation += 1
            self.tracking = False
            self.smoother = SmoothTarget(self.base, self.args.response_time, self.args.max_speed)
            self.shape = ShapeStabilizer(self.base, self.args.shape_limit, self.args.shape_response, self.args.shape_rate)
            self.shape_stamp = None
            self.send(self.base, immediate=True)
            self.arm_after = time.monotonic()+self.args.capture_delay+.20
            self.anchor_pending = False
            self.arming = True
            self.update(state='ARMING', tracking=False, message='Waiting for settled reference; keep camera still')
            self.log('arming')
        elif name == 'off':
            self.generation += 1
            self.tracking = self.arming = False
            self.smoother = SmoothTarget(self.base, self.args.response_time, self.args.max_speed)
            self.send(self.base, immediate=True)
            self.update(state='OFF', tracking=False, message='Stabilization OFF; calibrated image, fixed crop')
            self.log('off')
        elif name == 'pause':
            self.generation += 1
            self.tracking = self.arming = False
            self.smoother.target = self.smoother.current.copy()
            self.send(self.smoother.current, immediate=True)
            self.update(state='PAUSED', tracking=False, message='Last affine frozen; S/R locks a new reference')
            self.log('paused')
        elif name == 'gamma':
            self.gamma = not self.gamma
            self.send(self.current, immediate=not self.tracking)
            self.log('gamma', enabled=self.gamma)
        elif name in ('zoom_in', 'zoom_out'):
            self.args.zoom = float(np.clip(self.args.zoom*(1.05 if name=='zoom_in' else 1/1.05), 1., 2.5))
            self.base = np.vstack((affine(zoom=self.args.zoom), [0, 0, 1]))
            self.update(zoom=self.args.zoom)
            self.command('start' if self.tracking or self.arming else 'off')

    def _run(self):
        self.link = None
        compatible = False
        try:
            with (self.session/'events.jsonl').open('w', encoding='utf-8') as self.journal:
                self.calibration = load_calibration(self.args.calibration)
                self.link = Connection(self.args.port)
                # Identify new firmware BEFORE changing any configuration.
                self.link.frame_state()
                compatible = True
                self.log('session_start', args=vars(self.args), calibration=self.calibration)
                self.send(self.base, immediate=True)
                self.update(state='OFF', gamma=self.gamma, zoom=self.args.zoom,
                            message='Ready: S/Space locks reference, X disables, R reanchors')
                if self.args.auto_start:
                    self.command('start')
                last_tick = last_poll = last_health = time.monotonic()
                self.last_success = last_tick
                while not self.stop_event.is_set():
                    while not self.commands.empty():
                        self.command(self.commands.get_nowait())
                    if self.capture.error:
                        raise RuntimeError(self.capture.error)
                    now = time.monotonic()
                    if now-last_poll >= .04:
                        before = time.monotonic()
                        state = self.link.frame_state()
                        after = time.monotonic()
                        actual = matrix_from_registers(self.calibration, state['registers'])
                        self.timeline.append((before+after)/2, state['frames'], actual)
                        self.update(board_frames=state['frames'], gamma_mode=state['gamma'])
                        self.log('frame_state', status=state, matrix=actual, query_ms=1000*(after-before))
                        last_poll = after
                    if now-last_health >= 1.:
                        status = self.link.status()
                        if status['core_fault'] or status['write_fault'] or status['overflow_tiles'] or status['rx_errors']:
                            raise RuntimeError(f'FPGA health fault: {status}')
                        self.log('health', status=status)
                        last_health = time.monotonic()
                    # Process completed estimates; old generations cannot move
                    # the board after X/P/R or an updated reference.
                    while not self.estimator.results.empty():
                        generation, anchor, stamp, value, error, elapsed = self.estimator.results.get_nowait()
                        if generation != self.generation:
                            continue
                        if anchor:
                            self.anchor_pending = False
                            if error:
                                self.update(state='ARMING', message=error)
                                continue
                            self.arming, self.tracking = False, True
                            self.last_success = time.monotonic()
                            self.update(state='LOCKED', tracking=True, message=f'Reference locked ({value} features)')
                            self.log('reference_locked', features=value)
                        elif self.tracking:
                            try:
                                if error:
                                    raise ValueError(error)
                                raw_target, quality = value
                                age = time.monotonic()-stamp
                                if age > self.args.max_age:
                                    raise ValueError(f'Late estimate ({age*1000:.0f}ms); target held')
                                fast_guard(self.calibration, raw_target)
                                target, shape = self.shape.constrain(raw_target, quality,
                                    0. if self.shape_stamp is None else stamp-self.shape_stamp)
                                self.shape_stamp = stamp
                                fast_guard(self.calibration, target)
                                movement = corner_distance(self.smoother.target, target)
                                if movement > self.args.deadband:
                                    self.smoother.target = target
                                self.last_success = time.monotonic()
                                self.update(state='LOCKED', tracking=True, estimate_ms=elapsed*1000,
                                            message=f"{quality['method']} {quality['inliers']} inliers; fit {quality['rms_px']:.2f}px")
                                self.log('observation', target=target, raw_target=raw_target,
                                         shape=shape, quality=quality, age_ms=1000*age)
                            except (ValueError, np.linalg.LinAlgError) as exc:
                                self.update(state='HOLD', message=str(exc))
                                self.log('observation_rejected', reason=str(exc))
                    now = time.monotonic()
                    dt, last_tick = now-last_tick, now
                    if self.tracking:
                        # Hold progression after a genuine loss; do not chase a
                        # stale target indefinitely while the scene is unknown.
                        if now-self.last_success > .35:
                            self.smoother.target = self.smoother.current.copy()
                            self.update(state='HOLD', message='No fresh scene estimate; holding affine')
                        desired = self.smoother.advance(dt)
                        if now-self.last_send >= 1/self.args.command_rate and corner_distance(self.current, desired) > .04:
                            self.send(desired)
                    item = self.capture.read()
                    if item is not None and item[0] != self.last_frame:
                        self.last_frame, stamp, frame = item
                        if now-stamp > .2:
                            self.update(state='STALE', message='Capture stalled; holding affine')
                        elif self.arming and not self.anchor_pending and now >= self.arm_after:
                            self.estimator.submit((self.generation, True, stamp, frame, None))
                            self.anchor_pending = True
                        elif self.tracking:
                            seen = self.timeline.seen(stamp)
                            if seen is not None:
                                self.estimator.submit((self.generation, False, stamp, frame, seen))
                    self.stop_event.wait(.002)
                self.tracking = False
                self.send(np.eye(3), immediate=True)
                self.update(state='CLOSED', tracking=False, message='Closed; natural calibrated image restored')
        except Exception as exc:
            self.update(state='ERROR', tracking=False, message=str(exc))
            # Best-effort cleanup also runs for exceptions, not just Q/Esc.
            if compatible and self.link is not None:
                try:
                    registers = compile_registers(self.calibration, np.eye(3)[:2], self.gamma)
                    self.link.configure(registers, timeout=.6)
                except Exception:
                    pass
        finally:
            self.estimator.stopped.set()
            if self.link is not None:
                self.link.close()
            (self.session/'summary.json').write_text(json.dumps(self.snapshot(), indent=2), encoding='utf-8')

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=4)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', default='COM9')
    p.add_argument('--camera', type=int, help='Explicit DirectShow index; otherwise select Hagibis by USB identity')
    p.add_argument('--calibration', default=str(ROOT/'calibration/ov5640_1080p.json'))
    p.add_argument('--zoom', type=float, default=1.15, help='Fixed crop margin; 1.15 means modest reserve')
    p.add_argument('--gamma', action='store_true', help='Enable adaptive gamma; off by default for tracking')
    p.add_argument('--analysis-width', type=int, default=800)
    p.add_argument('--command-rate', type=float, default=30.)
    p.add_argument('--response-time', type=float, default=.08)
    p.add_argument('--max-speed', type=float, default=700., help='Maximum corner motion, pixels/second')
    p.add_argument('--shape-limit', type=float, default=.02, help='Maximum relative scale/stretch deviation; 0 locks shape')
    p.add_argument('--shape-response', type=float, default=.8, help='Scale/shear response in seconds, independent of roll')
    p.add_argument('--shape-rate', type=float, default=.015, help='Maximum log stretch change per second')
    p.add_argument('--capture-delay', type=float, default=.065, help='Estimated publication-to-host capture delay, seconds; calibrate on the target setup')
    p.add_argument('--deadband', type=float, default=.5)
    p.add_argument('--max-age', type=float, default=.25, help='Maximum estimate age after host decode, seconds')
    p.add_argument('--output', type=Path, default=ROOT/'reports/stabilization_runs')
    p.add_argument('--headless', action='store_true')
    p.add_argument('--seconds', type=float, default=0., help='Optional timed test; 0 waits for keyboard exit')
    p.add_argument('--auto-start', action='store_true')
    args = p.parse_args()
    if not (1 <= args.zoom <= 2.5 and 400 <= args.analysis_width <= 1280 and
            1 <= args.command_rate <= 30 and .03 <= args.response_time <= 1 and
            50 <= args.max_speed <= 1200 and 0 <= args.shape_limit <= .05 and
            .2 <= args.shape_response <= 3 and .001 <= args.shape_rate <= .05 and
            0 <= args.capture_delay <= .6 and 0 <= args.deadband <= 10 and .05 <= args.max_age <= 1):
        p.error('Tracking parameters outside supported ranges')
    cv2.setNumThreads(2)
    capture = Capture(args.camera)
    controller = Controller(capture, args)
    print('Session:', controller.session, flush=True)
    print('S/Space=start lock; X=off; R=reanchor; P=freeze; G=gamma; +/-=crop; Q/Esc=exit', flush=True)
    deadline = time.monotonic()+args.seconds if args.seconds else float('inf')
    try:
        if args.headless:
            while time.monotonic() < deadline and controller.thread.is_alive():
                time.sleep(.1)
        else:
            import tkinter as tk
            root = tk.Tk()
            root.title('FPGA Reference Lock - Live HDMI Capture')
            root.geometry('1280x800')
            status = tk.StringVar(value='Connecting...')
            buttons = tk.Frame(root)
            buttons.pack(side='bottom', fill='x')
            for title, action in [('S 开始锁定', 'start'), ('X 关闭仿射', 'off'), ('R 重新锁定', 'reanchor'),
                                  ('P 冻结', 'pause'), ('G Gamma', 'gamma'), ('+ 裁边', 'zoom_in'), ('- 裁边', 'zoom_out')]:
                tk.Button(buttons, text=title, command=lambda a=action:controller.action(a)).pack(side='left', padx=4, pady=6)
            tk.Button(buttons, text='Q 退出', command=root.destroy).pack(side='right', padx=6)
            tk.Label(root, textvariable=status, anchor='w', justify='left', font=('Consolas', 10)).pack(side='bottom', fill='x')
            viewport = tk.Frame(root, bg='black')
            viewport.pack(fill='both', expand=True)
            viewport.pack_propagate(False)
            image_label = tk.Label(viewport, bg='black')
            image_label.pack(fill='both', expand=True)
            actions = {'s':'start', ' ':'toggle', 'x':'off', 'r':'reanchor', 'p':'pause',
                       'g':'gamma', '+':'zoom_in', '=':'zoom_in', '-':'zoom_out'}
            def key(event):
                name = event.char.lower()
                if name in ('q', '\x1b'):
                    root.destroy()
                elif name in actions:
                    controller.action(actions[name])
            root.bind('<Key>', key)
            previous = [-1]
            def refresh():
                item = capture.read()
                if item and item[0] != previous[0]:
                    previous[0] = item[0]
                    width = max(320, image_label.winfo_width())
                    height = max(180, image_label.winfo_height())
                    scale = min(width/1920, height/1080)
                    display = cv2.resize(item[2], (int(1920*scale), int(1080*scale)), interpolation=cv2.INTER_AREA)
                    rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
                    ppm = f'P6\n{rgb.shape[1]} {rgb.shape[0]}\n255\n'.encode()+rgb.tobytes()
                    image_label.photo = tk.PhotoImage(data=ppm, format='PPM')
                    image_label.configure(image=image_label.photo)
                state = controller.snapshot()
                status.set(f"{state['state']} | capture {capture.fps():.1f} fps | Gamma {state.get('gamma_mode','?')} | crop {state.get('zoom',args.zoom):.2f}\n"
                           f"{state['message']}\nS/Space lock | X off | R new reference | P freeze | G gamma | +/- crop | Q quit")
                if time.monotonic() >= deadline:
                    root.destroy()
                else:
                    root.after(16, refresh)
            root.after(20, refresh)
            root.mainloop()
    finally:
        controller.close()
        capture.close()
        print(json.dumps(controller.snapshot(), indent=2), flush=True)


if __name__ == '__main__':
    main()
