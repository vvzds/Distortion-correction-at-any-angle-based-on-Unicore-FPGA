"""Frame-paced affine commands for the clean-smooth FPGA firmware.

The host describes the desired display transform with an unwrapped angle. The FPGA
receives the inverse destination-to-source matrix, then applies Brown4 and
bilinear resampling to a whole frame. No video pixels are processed here.
"""
from dataclasses import dataclass
import math
import threading
import time

import numpy as np

from model import affine, compile_registers
from stabilizer import fast_guard


@dataclass(frozen=True)
class Pose:
    angle: float = 0.0
    zoom: float = 2.0
    tx: float = 0.0
    ty: float = 0.0
    shear: float = 0.0

    def validate(self):
        values = (self.angle, self.zoom, self.tx, self.ty, self.shear)
        if not all(math.isfinite(value) for value in values):
            raise ValueError('Pose contains a non-finite value')
        if not (.5 <= self.zoom <= 3.0 and abs(self.tx) <= 480 and
                abs(self.ty) <= 270 and abs(self.shear) <= .5):
            raise ValueError('Zoom, translation or shear exceeds the host envelope')
        return self

    def matrix(self):
        self.validate()
        return np.vstack((affine(self.angle, self.zoom, self.tx, self.ty,
                                 self.shear), [0., 0., 1.]))


def _toward(current, target, maximum):
    return current + max(-maximum, min(maximum, target-current))


def advance_pose(current, target, dt, angular_speed=360., pixel_speed=1200.,
                 shear_speed=1.0, zoom_speed=1.5):
    """Slew explicit unwrapped angles; a 0->270 command turns 270 degrees."""
    dt = max(0., min(float(dt), .1))
    return Pose(_toward(current.angle, target.angle, angular_speed*dt),
                _toward(current.zoom, target.zoom, zoom_speed*dt),
                _toward(current.tx, target.tx, pixel_speed*dt),
                _toward(current.ty, target.ty, pixel_speed*dt),
                _toward(current.shear, target.shear, shear_speed*dt))


class AffineCommander:
    """Only the newest target is kept; UART and all board reads share one thread."""
    def __init__(self, link, calibration, initial=Pose(), rate=30.,
                 angular_speed=360., pixel_speed=1200., shear_speed=1.,
                 zoom_speed=1.5, smooth=False, on_update=None):
        if not (1 <= rate <= 30 and 1 <= angular_speed <= 720 and
                1 <= pixel_speed <= 2400 and 0 < shear_speed <= 2 and
                0 < zoom_speed <= 3):
            raise ValueError('Invalid command rate or slew limit')
        self.link, self.calibration = link, calibration
        self.rate, self.angular_speed = rate, angular_speed
        self.pixel_speed, self.shear_speed, self.zoom_speed = pixel_speed, shear_speed, zoom_speed
        self.smooth, self.on_update = smooth, on_update
        self.lock = threading.Lock()
        self.current = self.target = initial.validate()
        self.error = None
        self.frames = None
        self.commands_sent = 0
        self.compatible = False
        self.stopped = threading.Event()
        self.thread = None

    def set_target(self, pose):
        pose.validate()
        matrix = pose.matrix()
        fast_guard(self.calibration, matrix)
        with self.lock:
            self.target = pose

    def set_speed(self, angular_speed, pixel_speed, shear_speed, zoom_speed):
        if not (1 <= angular_speed <= 720 and 1 <= pixel_speed <= 2400 and
                0 < shear_speed <= 2 and 0 < zoom_speed <= 3):
            raise ValueError('Invalid slew limit')
        with self.lock:
            self.angular_speed = angular_speed
            self.pixel_speed = pixel_speed
            self.shear_speed = shear_speed
            self.zoom_speed = zoom_speed

    def snapshot(self):
        with self.lock:
            return dict(current=self.current, target=self.target, error=self.error,
                        frames=self.frames, commands_sent=self.commands_sent)

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Commander already started')
        # Read 21h before sending, so the old 30 fps firmware is rejected.
        self.link.frame_state()
        self.compatible = True
        matrix = self.current.matrix()
        fast_guard(self.calibration, matrix)
        status = self.link.configure(compile_registers(self.calibration, matrix[:2], False,
                                                       smooth=self.smooth), timeout=.8)
        if any(status.get(key) for key in
               ('core_fault', 'write_fault', 'overflow_tiles', 'rx_errors')):
            raise RuntimeError(f'FPGA reported a fault: {status}')
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        period = 1/self.rate
        next_tick = previous = time.monotonic()
        last_health = previous
        try:
            while not self.stopped.is_set():
                now = time.monotonic()
                if now < next_tick:
                    self.stopped.wait(min(next_tick-now, .01))
                    continue
                # A delayed UART transaction must not create a burst of old commands.
                next_tick = max(next_tick+period, now+period)
                dt, previous = min(now-previous, .1), now
                with self.lock:
                    current, target = self.current, self.target
                    speeds = (self.angular_speed, self.pixel_speed,
                              self.shear_speed, self.zoom_speed)
                candidate = advance_pose(current, target, dt, *speeds)
                if candidate != current:
                    matrix = candidate.matrix()
                    fast_guard(self.calibration, matrix)
                    self.link.set_target(compile_registers(self.calibration, matrix[:2],
                                                           False, smooth=self.smooth))
                    with self.lock:
                        self.current = candidate
                        self.commands_sent += 1
                    if self.on_update:
                        self.on_update(self.snapshot())
                if now-last_health >= .5:
                    status = self.link.status()
                    if any(status.get(key) for key in
                           ('core_fault', 'write_fault', 'overflow_tiles', 'rx_errors')):
                        raise RuntimeError(f'FPGA reported a fault: {status}')
                    with self.lock:
                        self.frames = status['frames']
                    last_health = time.monotonic()
        except Exception as exc:
            with self.lock:
                self.error = str(exc)
            self.stopped.set()

    def close(self, restore=True):
        self.stopped.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                raise RuntimeError('UART worker did not stop; board connection remains open')
        try:
            if restore and self.compatible:
                identity = np.eye(3)
                self.link.configure(compile_registers(self.calibration, identity[:2], False),
                                    timeout=.8)
        finally:
            self.link.close()
