"""Focused IMU offline tests. Never opens a serial port, JTAG or capture card."""
from collections import Counter
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
import zipfile

import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'host'))
from imu import (WitParser, PoseHistory, euler_rotation, exp_rotation, inverse_affine,
                 interpolate_rotation, parse_snapshot, signed_us, load_mount)
import imu_trial
from model import affine, load_calibration
from stabilizer import fast_guard

checks = []
c = load_calibration()
identity = np.eye(3)
for angles in ([0, 0, 60], [20, 30, 40], [180, 0, 0], [0, 90, 20]):
    r = euler_rotation(angles)
    assert np.allclose(interpolate_rotation(r, r, .5), r)
assert np.allclose(interpolate_rotation(euler_rotation([0, 0, 179]),
                                      euler_rotation([0, 0, -179]), .5), euler_rotation([0, 0, 180]))
checks.append('SO(3) interpolation including +/-180 and Euler singularity, no angle subtraction')
base = np.vstack((affine(zoom=1.5), [0, 0, 1]))
center = np.array([959.5, 539.5, 1])
for degrees in (-180, -90, -20, 0, 20, 90, 180):
    pose = euler_rotation([0, 0, degrees])
    a = inverse_affine(c, identity, pose, identity)
    principal = np.array([c['cx'], c['cy'], 1])
    reference_pixel = np.linalg.inv(base)@principal
    assert np.allclose(a@reference_pixel, principal)
    assert np.allclose(np.linalg.svd(a[:2, :2], compute_uv=False), [1/1.5]*2)
    # A world ray moves by current.T; inverse sampler must follow exactly that
    # motion, so the display ray remains locked to reference. Pixel focal ratio
    # approximated as 1 in rigid-roll mode (actual fx/fy differs <0.021%).
    assert np.allclose(a[:2, :2], pose.T[:2, :2]/1.5)
    ray = np.array([400., 200., 1.])
    rigid = a@np.linalg.inv(base)
    expected = principal[:2]+pose.T[:2, :2]@(ray[:2]-principal[:2])
    assert np.allclose((rigid@ray)[:2], expected)
    fast_guard(c, a)
    if degrees == 20:
        assert a[1, 0] < 0  # sign explicitly checked
for xyz in ([10, 0, 0], [0, 10, 0], [4, 5, 20]):
    current = euler_rotation(xyz)
    a = inverse_affine(c, identity, current, identity, mode='affine')
    k = np.array([[c['fx'], 0, c['cx']], [0, c['fy'], c['cy']], [0, 0, 1.]])
    h = k@current.T@np.linalg.inv(k)@base
    for delta in ([0, 0, 0], [.01, 0, 0], [0, .01, 0]):
        p = center+delta
        v = h@p
        assert np.max(abs((a@p)[:2]-v[:2]/v[2])) < .001
    fast_guard(c, a)
try:
    inverse_affine(c, identity, euler_rotation([25, 0, 0]), identity, mode='affine')
except ValueError:
    pass
else:
    raise AssertionError('Unsafe tilt accepted')
checks.append('Inverse mapping sign, roll rigid shape/center, perspective local Jacobian and tilt guard')
assert np.isclose(signed_us(1000, 0xfffffc18), .002)
def state(t, angle=0, frames=1):
    return dict(now=t+2000, frame_us=t, frames=frames, gyro_us=t, angle_us=t,
                seen=3, euler=np.array([0., 0., angle]), gyro=np.array([0., 0., 100.]),
                errors=0, packets=t//10000)
h = PoseHistory()
for i in range(8):
    h.append(state(100000+i*10000, i))
assert np.isclose(h.rate(), 100)
decimated = PoseHistory()
for i in range(0, 15, 2):
    decimated.append(state(100000+i*10000, i))
assert np.isclose(decimated.rate(), 100)  # host reads 50Hz, device sends 100Hz
assert np.allclose(h.at(165000), euler_rotation([0, 0, 6.5]))
assert np.allclose(h.at(180000), euler_rotation([0, 0, 8]))
try:
    h.at(220000)
except ValueError:
    pass
else:
    raise AssertionError('Unbounded prediction')
checks.append('100Hz history, interpolation, bounded gyro prediction, uint32 clock wrap')
payload = struct.pack('<5I4hI4h2I', 0x494d5501, 100, 90, 8, 70,
                      -32768, 16384, 0, 0, 80, 16384, 0, -16384, 0, 2, (1<<29)|(3<<24)|4)
s = parse_snapshot(payload)
assert s['baud_code'] == 1 and s['packets'] == 4 and s['seen'] == 3
assert np.allclose(s['gyro'], [-2000, 1000, 0]) and np.allclose(s['euler'], [90, 0, -90])
checks.append('RTL snapshot byte offsets, scaling, sign, receiver baud readback')

archive = Path(r'C:\Users\songtianyu\xwechat_files\wxid_xpvac4ccqb4k22_0ed2\msg\file\2026-10\JY901P_测试报告与CH340驱动_20261030.zip')
replay = []
if archive.exists():
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not name.endswith('.bin'):
                continue
            parser, output = WitParser(), []
            data = z.read(name)
            for start in range(0, len(data), 17):
                output.extend(parser.feed(data[start:start+17]))
            counts = dict(Counter(p[0] for p in output))
            assert parser.errors == parser.discarded == 0 and set(counts) == {0x51, 0x52, 0x53}
            replay.append(dict(file=Path(name).name, counts=counts, tail=len(parser.buffer)))
    checks.append('Supplied two raw sensor captures replayed in 17-byte chunks without executing attachment code')
good = bytes([0x55, 0x53])+struct.pack('<4h', 0, 0, 0, 0)
good += bytes([sum(good)&255])
bad = good[:-1]+bytes([good[-1]^1])
parser = WitParser()
assert len(parser.feed(b'noise'+bad+good)) == 1 and parser.errors == 1

class FakeCapture:
    error = None
    def read(self):
        raise AssertionError('Image analysis entered IMU control path')

class FakeLink:
    last = None
    stale = False
    def __init__(self, port):
        FakeLink.last = self
        self.sent = []
        self.start = time.monotonic()
    def imu_state(self):
        elapsed = time.monotonic()-self.start
        t = 1000000+int(elapsed*100)*10000
        s = state(t, 0, int(elapsed*30)+1)
        if self.stale:
            s['now'] += 200000
        return s
    def receiver_baud(self, baud):
        return self.imu_state()
    def set_target(self, regs):
        self.sent.append(regs)
    def status(self):
        return dict(frames=1, core_fault=False, write_fault=False, overflow_tiles=0, rx_errors=0)
    def configure(self, regs, timeout):
        self.sent.append(regs)
    def close(self):
        self.closed = True

def until(fn, timeout=2):
    deadline = time.monotonic()+timeout
    while not fn():
        if time.monotonic() > deadline:
            raise AssertionError('Controller timeout: '+str(ctrl.snapshot()))
        time.sleep(.005)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    mount = tmp/'mount.json'
    mount.write_text(json.dumps(dict(verified=True, camera_from_sensor=identity.tolist())))
    args = imu_trial.arguments(['--mount', str(mount), '--output', str(tmp/'runs'), '--headless'])
    imu_trial.ImuConnection = FakeLink
    ctrl = imu_trial.Controller(FakeCapture(), args)
    try:
        until(lambda:ctrl.snapshot()['state'] == 'OFF')
        time.sleep(.12)
        # require camera static on lock
        original = FakeLink.imu_state
        def still(self):
            s = original(self)
            s['gyro'] = np.zeros(3)
            return s
        FakeLink.imu_state = still
        ctrl.action('start')
        until(lambda:ctrl.snapshot()['state'] == 'LOCKED')
        assert all(r[15] == 0 for r in FakeLink.last.sent)  # no old frame half-step
        FakeLink.last.stale = True
        until(lambda:ctrl.snapshot()['state'] == 'HOLD')
        count = len(FakeLink.last.sent)
        time.sleep(.05)
        assert len(FakeLink.last.sent) == count
        ctrl.action('off')
        until(lambda:ctrl.snapshot()['state'] == 'OFF')
    finally:
        ctrl.close()
    assert FakeLink.last.closed and not ctrl.thread.is_alive()
    mount.write_text(json.dumps(dict(camera_from_sensor=[[-1,0,0],[0,1,0],[0,0,1]])))
    try:
        load_mount(mount)
    except ValueError:
        pass
    else:
        raise AssertionError('Reflection mount accepted')
checks.append('Fake-link controller: no image reads, lock/off, stale hold, frame-atomic commands, cleanup and mount guard')
import hashlib
inputs = [ROOT/'host/imu.py', ROOT/'host/imu_trial.py', Path(__file__).resolve()]
report = dict(passed=True, checks=checks, raw_replay=replay, hardware_access=False,
              inputs_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
              limitations=['Mount/convention not yet verified', 'Sensor still known only at 10Hz',
                           'Frame association approximate; source-age/packet-delay/command-lead need board calibration'])
(ROOT/'reports/imu_offline_checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
