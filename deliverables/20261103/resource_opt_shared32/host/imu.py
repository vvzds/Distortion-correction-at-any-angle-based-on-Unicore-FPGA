"""Receive-only JY901P snapshots and IMU-only inverse affine geometry.

Convention (must verify on the mounted sensor): Euler = Rz(yaw) Ry(pitch)
Rx(roll), sensor-to-world. camera_from_sensor maps sensor vectors into camera
coordinates: x right, y down, z along optical axis. No visual estimator here.
"""
from collections import deque
import json
import struct

import numpy as np
from model import affine
from protocol import Connection, packet

BAUD_CODES = {9600: 0, 115200: 1, 57600: 2, 38400: 3, 19200: 4}


class WitParser:
    """Offline/adapter byte parser; checksum + bytewise resynchronization."""
    def __init__(self):
        self.buffer = bytearray()
        self.errors = self.discarded = 0

    def feed(self, data):
        self.buffer.extend(data)
        packets = []
        while len(self.buffer) >= 11:
            if self.buffer[0] != 0x55 or not 0x50 <= self.buffer[1] <= 0x59:
                del self.buffer[0]
                self.discarded += 1
            elif sum(self.buffer[:10]) & 255 != self.buffer[10]:
                self.errors += 1
                del self.buffer[0]
                self.discarded += 1
            else:
                packets.append((self.buffer[1], struct.unpack('<4h', self.buffer[2:10])))
                del self.buffer[:11]
        return packets


def signed_us(a, b):
    return ((int(a)-int(b)+2**31) % 2**32-2**31)*1e-6


def parse_snapshot(payload):
    if len(payload) != 48:
        raise ValueError('Wrong IMU snapshot length')
    magic, now, frame_us, frames, gyro_us = struct.unpack_from('<5I', payload)
    if magic != 0x494d5501:
        raise ValueError('IMU bridge firmware required')
    angle_us = struct.unpack_from('<I', payload, 28)[0]
    errors, flags = struct.unpack_from('<2I', payload, 40)
    return dict(now=now, frame_us=frame_us, frames=frames, gyro_us=gyro_us,
                gyro=np.array(struct.unpack_from('<3h', payload, 20))*2000/32768,
                angle_us=angle_us,
                euler=np.array(struct.unpack_from('<3h', payload, 32))*180/32768,
                errors=errors, packets=flags & 0xffffff, seen=(flags >> 24) & 3,
                baud_code=flags >> 29)


class ImuConnection(Connection):
    def imu_state(self):
        seq = self.next_sequence()
        self.serial.write(packet(0x22, seq))
        return parse_snapshot(self._receive(0xa2, seq, timeout=.3))

    def receiver_baud(self, baud):
        """Changes FPGA receiver only; never sends configuration to sensor."""
        code = BAUD_CODES[baud]
        self.serial.write(packet(0x23, self.next_sequence(), bytes([code])))
        state = self.imu_state()
        if state['baud_code'] != code:
            raise RuntimeError('FPGA IMU baud readback mismatch')
        return state


def exp_rotation(vector):
    v = np.asarray(vector, dtype=float)
    theta = np.linalg.norm(v)
    skew = np.array([[0., -v[2], v[1]], [v[2], 0., -v[0]], [-v[1], v[0], 0.]])
    a = 1-theta**2/6 if theta < 1e-7 else np.sin(theta)/theta
    b = .5-theta**2/24 if theta < 1e-7 else (1-np.cos(theta))/theta**2
    return np.eye(3)+a*skew+b*skew@skew


def euler_rotation(degrees):
    x, y, z = np.deg2rad(degrees)
    return (exp_rotation([0, 0, z]) @ exp_rotation([0, y, 0]) @
            exp_rotation([x, 0, 0]))


def interpolate_rotation(a, b, fraction):
    # Quaternion shortest-path interpolation; avoids +/-180 Euler discontinuity.
    def quaternion(r):
        # Eigenvector method remains well-conditioned at rotations near pi.
        x, y, z = r[0], r[1], r[2]
        k = np.array([[x[0]-y[1]-z[2], x[1]+y[0], x[2]+z[0], z[1]-y[2]],
                      [x[1]+y[0], y[1]-x[0]-z[2], y[2]+z[1], x[2]-z[0]],
                      [x[2]+z[0], y[2]+z[1], z[2]-x[0]-y[1], y[0]-x[1]],
                      [z[1]-y[2], x[2]-z[0], y[0]-x[1], np.trace(r)]])/3
        _, vectors = np.linalg.eigh(k)
        return vectors[:, -1]
    qa, qb = quaternion(a), quaternion(b)
    dot = float(qa@qb)
    if dot < 0:
        qb, dot = -qb, -dot
    dot = np.clip(dot, -1., 1.)
    if dot > .9995:
        q = qa+fraction*(qb-qa)
    else:
        t = np.arccos(dot)
        q = (np.sin((1-fraction)*t)*qa+np.sin(fraction*t)*qb)/np.sin(t)
    q /= np.linalg.norm(q)
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def projective_rotation_homography(reference_sensor_to_world,
                                    current_sensor_to_world,
                                    camera_from_sensor, calibration):
    """Return the output-to-source homography for rotation-only stabilization.

    The homography maps a pixel in the reference view to the corresponding
    ideal pixel in the current view. It models camera rotation about its
    optical center; translation, depth variation, and Brown distortion are
    intentionally handled outside this geometric model.
    """
    reference = np.asarray(reference_sensor_to_world, dtype=float)
    current = np.asarray(current_sensor_to_world, dtype=float)
    mount = np.asarray(camera_from_sensor, dtype=float)
    if any(r.shape != (3, 3) or not np.isfinite(r).all()
           for r in (reference, current, mount)):
        raise ValueError('Rotations and mount must be finite 3x3 matrices')
    fx, fy = float(calibration['fx']), float(calibration['fy'])
    cx, cy = float(calibration['cx']), float(calibration['cy'])
    if not np.isfinite([fx, fy, cx, cy]).all() or fx <= 0 or fy <= 0:
        raise ValueError('Invalid camera intrinsics')
    k = np.array([[fx, 0., cx], [0., fy, cy], [0., 0., 1.]])
    camera_delta = mount @ current.T @ reference @ mount.T
    return k @ camera_delta @ np.linalg.inv(k)


def projective_rotation_map(u, v, homography):
    """Map reference-view pixels to current ideal-source pixels."""
    u, v = np.broadcast_arrays(np.asarray(u, dtype=float),
                               np.asarray(v, dtype=float))
    h = np.asarray(homography, dtype=float)
    if h.shape != (3, 3) or not np.isfinite(h).all():
        raise ValueError('Homography must be a finite 3x3 matrix')
    denominator = h[2, 0]*u + h[2, 1]*v + h[2, 2]
    valid = np.isfinite(denominator) & (denominator > 1e-9)
    safe_denominator = np.where(valid, denominator, 1.)
    x = (h[0, 0]*u + h[0, 1]*v + h[0, 2])/safe_denominator
    y = (h[1, 0]*u + h[1, 1]*v + h[1, 2])/safe_denominator
    valid &= np.isfinite(x) & np.isfinite(y)
    return x, y, valid


def load_mount(path):
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    r = np.asarray(config['camera_from_sensor'], dtype=float)
    if (r.shape != (3, 3) or not np.isfinite(r).all() or
            not np.allclose(r@r.T, np.eye(3), atol=1e-5) or
            not np.isclose(np.linalg.det(r), 1, atol=1e-5)):
        raise ValueError('Mount must be a proper 3D rotation (det=+1)')
    return config, r


class PoseHistory:
    def __init__(self):
        self.angles = deque(maxlen=300)
        self.gyros = deque(maxlen=600)
        self.counts = deque(maxlen=100)
        self.last_now = None

    def append(self, state):
        now = state['now']
        if self.last_now is not None and signed_us(now, self.last_now) < 0:
            raise ValueError('Board clock reset; reference must be reacquired')
        self.last_now = now
        if state['seen'] & 2 and (not self.counts or state['angle_us'] != self.counts[-1][0]):
            self.counts.append((state['angle_us'], state['packets']))
        for items, flag, stamp, value in (
                (self.angles, 2, state['angle_us'], state['rotation'] if 'rotation' in state else euler_rotation(state['euler'])),
                (self.gyros, 1, state['gyro_us'], np.deg2rad(state['gyro']))):
            if state['seen'] & flag and (not items or items[-1][0] != stamp):
                if items and signed_us(stamp, items[-1][0]) <= 0:
                    raise ValueError('IMU timestamps reversed')
                items.append((stamp, value))

    def rate(self):
        if len(self.angles) < 3:
            return 0.
        samples = list(self.counts)[-30:]
        return ((samples[-1][1]-samples[0][1]) & 0xffffff)/signed_us(samples[-1][0], samples[0][0])

    def at(self, stamp, max_prediction=.025):
        if not self.angles:
            raise ValueError('No valid Euler packets yet')
        values = list(self.angles)
        for (ta, a), (tb, b) in zip(values, values[1:]):
            dt = signed_us(stamp, ta)
            span = signed_us(tb, ta)
            if 0 <= dt <= span:
                if span > .15:
                    raise ValueError('IMU sample gap; holding affine')
                return interpolate_rotation(a, b, dt/span)
        ta, a = values[-1]
        dt = signed_us(stamp, ta)
        if dt < 0 or dt > max_prediction:
            raise ValueError('Pose outside bounded history/prediction; holding affine')
        if dt < 1e-6:
            return a.copy()
        gyros = [(t, w) for t, w in self.gyros if -.02 <= signed_us(t, ta) <= dt]
        if not gyros or signed_us(stamp, gyros[-1][0]) > .03:
            raise ValueError('Fresh gyro required for short prediction')
        result, previous, omega = a.copy(), ta, gyros[0][1]
        for t, w in gyros:
            step = signed_us(t, previous)
            if step > 0:
                result = result @ exp_rotation(omega*step)
                previous = t
            omega = w
        return result @ exp_rotation(omega*max(0., signed_us(stamp, previous)))


def inverse_affine(calibration, reference, current, camera_from_sensor, zoom=1.5,
                   mode='roll', max_tilt=15., roll_sign=1):
    if roll_sign not in (-1, 1):
        raise ValueError('Roll direction must be -1 or +1')
    # Poses map sensor -> world. Map a reference-camera ray into current camera.
    c = camera_from_sensor
    relative = c @ current.T @ reference @ c.T
    tilt = np.rad2deg(np.arccos(np.clip(relative[2, 2], -1, 1)))
    if tilt > max_tilt:
        raise ValueError(f'Tilt {tilt:.1f}deg exceeds affine envelope {max_tilt:.1f}deg')
    k = np.array([[calibration['fx'], 0, calibration['cx']],
                  [0, calibration['fy'], calibration['cy']], [0, 0, 1.]])
    base = np.vstack((affine(zoom=zoom), [0, 0, 1]))
    if mode == 'roll':
        theta = roll_sign*np.arctan2(relative[1, 0]-relative[0, 1], relative[0, 0]+relative[1, 1])
        # Exact rigid roll in pixels, no estimated scale/shear or breathing.
        r = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
        # Physical rotation is about the calibrated optical principal point,
        # not the geometric display center; conflating them adds translation.
        center = np.array([calibration['cx'], calibration['cy']])
        a = np.column_stack((r, center-r@center))
    else:
        h = k @ relative @ np.linalg.inv(k) @ base
        point = np.array([959.5, 539.5, 1.])
        v = h@point
        if v[2] < .25:
            raise ValueError('Reference rays behind camera')
        jac = (h[:2, :2]*v[2]-np.outer(v[:2], h[2, :2]))/v[2]**2
        # Analytic local perspective derivative, no unconstrained image fit.
        return np.vstack((np.column_stack((jac, v[:2]/v[2]-jac@point[:2])), [0, 0, 1]))
    return np.vstack((a, [0, 0, 1])) @ base
