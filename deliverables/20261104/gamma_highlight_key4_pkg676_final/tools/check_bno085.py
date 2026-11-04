"""BNO085 offline protocol, quaternion, mount and controller checks; no hardware."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from bno085 import ShtpDecoder, quaternion_rotation, parse_snapshot, parse_diagnostics
from imu import (exp_rotation, inverse_affine, load_mount, PoseHistory,
                 projective_rotation_homography, projective_rotation_map)
from model import load_calibration
import imu_trial
sys.path.insert(0,str(ROOT/'tools'))
from analyze_bno085_log import analyze

checks=[]
assert len(imu_trial.CROP_LEVELS)==16
assert imu_trial.crop_step(1.,-1)==1. and imu_trial.crop_step(2.5,1)==2.5
assert imu_trial.crop_step(1.15,1)==1.2 and imu_trial.crop_step(1.15,-1)==1.1
checks.append('Crop 1.0..2.5 by 0.1; bounded steps, off-grid input, paused geometry and locked reference preservation')
mount_config,mount=load_mount(ROOT/'calibration/bno085_mount.json')
assert np.allclose(mount@[1,0,0],[0,0,1])
assert np.allclose(mount@[0,1,0],[-1,0,0])
assert np.allclose(mount@[0,0,1],[0,-1,0])
assert np.isclose(np.linalg.det(mount),1)
c=load_calibration()
for axis in np.eye(3):
    for angle in [-179,-30,-1,0,1,30,179]:
        t=np.deg2rad(angle)
        q=np.r_[axis*np.sin(t/2),np.cos(t/2)]
        assert np.allclose(quaternion_rotation(q),exp_rotation(axis*t))
        assert np.allclose(quaternion_rotation(q),quaternion_rotation(-q))
# Camera positive roll corresponds to sensor -X. Use arbitrary reference,
# not an initial orientation aligned with gravity/world.
reference=exp_rotation(np.array([.2,.4,-.6]))
for angle in [-120,-20,20,120]:
    camera_turn=exp_rotation([0,0,np.deg2rad(angle)])
    sensor_turn=mount.T@camera_turn@mount
    current=reference@sensor_turn
    a=inverse_affine(c,reference,current,mount)
    assert np.allclose(a[:2,:2],camera_turn.T[:2,:2]/1.5)
checks.append('Effective mount from isolated physical axes; quaternion sign invariance and arbitrary reference roll')

# Physical feedback: uncorrected displayed roll has the opposite parity to the
# original ideal optical-axis model. Check actual output->input sampling on
# independent asymmetric feature offsets, not just coefficient sign.
assert mount_config['roll_sign']==1
for angle in [-120,-20,-5,5,20,120]:
    turn=exp_rotation([0,0,np.deg2rad(angle)])
    current=reference@(mount.T@turn@mount)
    target=inverse_affine(c,reference,current,mount,roll_sign=mount_config['roll_sign'])
    sampling=target[:2,:2]*1.5
    raw_features=turn.T[:2,:2]@np.array([[103.,-77.,40.],[31.,65.,-92.]])
    output=np.linalg.solve(sampling,raw_features)
    assert np.allclose(output,np.array([[103.,-77.,40.],[31.,65.,-92.]]))
checks.append('Physical doubled-roll feedback: signed output-to-input compensation cancels raw feature rotation; physical retest pending')

# A rotation-only planar homography maps reference-output rays back to the
# current camera image. This is the floating-point oracle for the FPGA map.
for axis, angle in (([0, 1, 0], 7.), ([1, 0, 0], -5.), ([0, 0, 1], 12.)):
    camera_turn = exp_rotation(np.asarray(axis)*np.deg2rad(angle))
    sensor_turn = mount.T @ camera_turn @ mount
    reference_pose = exp_rotation([.1, -.2, .3])
    current_pose = reference_pose @ sensor_turn
    h = projective_rotation_homography(reference_pose, current_pose, mount, c)
    points = np.array([[300., 960., 1600.], [180., 540., 900.]])
    sx, sy, valid = projective_rotation_map(points[0], points[1], h)
    rays = np.vstack(((points[0]-c['cx'])/c['fx'],
                      (points[1]-c['cy'])/c['fy'], np.ones(3)))
    expected = camera_turn.T @ rays
    expected = expected[:2]/expected[2]
    expected[0] = expected[0]*c['fx']+c['cx']
    expected[1] = expected[1]*c['fy']+c['cy']
    assert valid.all() and np.allclose(np.vstack((sx, sy)), expected, atol=1e-9)
h_bad = np.zeros((3, 3))
_, _, valid = projective_rotation_map([0.], [0.], h_bad)
assert not valid[0]
checks.append('Rotation-only projective output-to-source homography; isolated pitch/yaw/roll axes and invalid denominator')

# Replay isolated operator-labelled movements through effective mount.
trial=json.loads((ROOT/'reports/bno085_axis_direction_review.json').read_text())
center=np.array([959.5,539.5,1.])
base=inverse_affine(c,np.eye(3),np.eye(3),mount,mode='affine')
for name in ('pitch_trial','yaw_trial'):
    v=trial[name]
    ref=np.array(v['reference']['pose']);cur=np.array(v['last']['data']['rotation'])
    target=inverse_affine(c,ref,cur,mount,mode='affine')
    delta=(target@center-base@center)[:2]
    if name=='pitch_trial':assert delta[1]>50 and abs(delta[0])<30
    else:assert delta[0]<-50 and abs(delta[1])<30
# Exact roll behavior agrees with previously accepted mount+roll-sign adapter.
old=np.array(mount_config['declared_camera_from_sensor'])
for angle in (-100,-10,10,100):
    cur=reference@exp_rotation([np.deg2rad(angle),0,0])
    assert np.allclose(inverse_affine(c,reference,cur,mount),
                       inverse_affine(c,reference,cur,old,roll_sign=-1))
checks.append('Recorded pitch-up/yaw-right center-sampling direction; effective mount preserves accepted pure roll')
records=[]
for i in range(40):
    t=i*.01;angle=t*.8
    records.append(dict(now=1000000+i*10000+3000,angle_us=1000000+i*10000,seen=3,
                        generation=1,packets=i,errors=0,gyro=[0,0,np.rad2deg(.8)],
                        quaternion=[0,0,np.sin(angle/2),np.cos(angle/2)]))
assert analyze(records,mount)['convention']=='sensor_to_world_supported_by_motion'
for s in records:s['quaternion'][2]*=-1
assert analyze(records,mount)['convention']=='world_to_sensor_suspected_STOP_and_review_adapter'
checks.append('Offline log reviewer distinguishes quaternion inverse using known synthetic body gyro')

def shtp(channel,seq,payload):
    return struct.pack('<HBB',len(payload)+4,channel,seq)+payload
base=b'\xfb'+struct.pack('<i',10)
gyro=bytes([2,1,0,2])+struct.pack('<3h',512,-512,1024)
pose=bytes([8,1,0,3])+struct.pack('<4h',0,0,0,16384)
decoder=ShtpDecoder()
events=decoder.decode(shtp(3,255,base+gyro+pose),100000)
assert events[0]['stamp']==99200 and events[1]['stamp']==99300
assert np.allclose(events[0]['gyro_rad_s'],[1,-1,2])
decoder.decode(shtp(3,0,base+pose),105000)
assert decoder.gaps==0
decoder.decode(shtp(3,2,base+pose),110000)
assert decoder.gaps==1
for malformed in [b'\x04',struct.pack('<HBB',0x8008,3,3)+bytes(4),
                  struct.pack('<HBB',20,3,3)+bytes(2),shtp(3,3,b'\x08\x00')]:
    try:decoder.decode(malformed,110000)
    except ValueError:pass
    else:raise AssertionError('Malformed SHTP accepted')
girv=struct.pack('<7h',0,0,0,16384,1024,-2048,512)
events=ShtpDecoder().decode(shtp(5,0,girv),100000,mode='girv')
assert np.allclose(events[0]['gyro_rad_s'],[1,-2,.5])
assert events[0]['stamp']==100000
checks.append('SHTP multi-report, SH2 100us delay/timebase, sequence wrap/gap, truncation/continuation rejection and GIRV Q10')

def snapshot(t=1000000,generation=2,mode=0,count=20,seen=3):
    flags=(mode<<29)|(seen<<24)|count
    return struct.pack('<5I3hHI4h2I',0x424e4f01,t+2000,t,int(t/33333)+1,t,
                       0,0,0,generation,t,0,0,0,16384,0,flags)
s=parse_snapshot(snapshot())
assert s['generation']==2 and s['packets']==20 and np.allclose(s['rotation'],np.eye(3))
for bad in [bytes(48),snapshot()[:-1]]:
    try:parse_snapshot(bad)
    except ValueError:pass
    else:raise AssertionError('Bad snapshot identity')
try:quaternion_rotation([0,0,0,0])
except ValueError:pass
else:raise AssertionError('Zero quaternion')
diag=parse_diagnostics(struct.pack('<12I',0x424e4401,1,5000,0x03020708,2,0,0,100,5000,5000,1234,5678))
assert diag['status']==7 and diag['version_major']==3 and diag['version_minor']==2
checks.append('Snapshot identity/quantization and reset generation; feature/product diagnostics decoding; norm guard')

class Capture:
    error=None
    def read(self):raise AssertionError('Image estimator invoked')

class Link:
    latest=None
    def __init__(self,port):
        Link.latest=self;self.started=time.monotonic();self.sent=[];self.generation=2;self.stale=False
    def imu_state(self):
        t=1000000+int((time.monotonic()-self.started)*200)*5000
        s=parse_snapshot(snapshot(t,self.generation,count=t//5000))
        if self.stale and hasattr(self,'previous'):
            now=s['now'];s=dict(self.previous,now=now,frame_us=s['frame_us'],frames=s['frames'])
        else:
            self.previous=s.copy()
        return s
    def set_mode(self,name):return self.imu_state()
    def set_target(self,regs):self.sent.append(regs)
    def diagnostics(self):
        return dict(diag,resets=self.generation)
    def status(self):return dict(frames=10,core_fault=False,write_fault=False,overflow_tiles=0,rx_errors=0)
    def configure(self,regs,timeout):self.sent.append(regs)
    def close(self):self.closed=True

def until(fn):
    deadline=time.monotonic()+3
    while not fn():
        if time.monotonic()>deadline:raise AssertionError(ctrl.snapshot())
        time.sleep(.005)

with tempfile.TemporaryDirectory() as temp:
    args=imu_trial.arguments(['--sensor','bno085','--headless','--output',temp])
    imu_trial.BnoConnection=Link
    ctrl=imu_trial.Controller(Capture(),args)
    try:
        until(lambda:ctrl.snapshot()['state']=='OFF' and ctrl.bno_diagnostics is not None)
        time.sleep(.1)
        ctrl.action('start');until(lambda:ctrl.snapshot()['state']=='LOCKED')
        assert ctrl.history.rate()>150
        # Crop changes preserve reference and orientation without image reads.
        reference_before=ctrl.reference.copy()
        ctrl.action('pause');until(lambda:ctrl.snapshot()['state']=='PAUSED')
        old_base=ctrl.base.copy();old_current=ctrl.current.copy()
        ctrl.action('zoom_in');until(lambda:ctrl.snapshot()['zoom']==1.6)
        assert np.allclose(ctrl.current@np.linalg.inv(ctrl.base),old_current@np.linalg.inv(old_base))
        ctrl.action('zoom_out');until(lambda:ctrl.snapshot()['zoom']==1.5)
        ctrl.action('start');until(lambda:ctrl.snapshot()['state']=='LOCKED')
        ref=ctrl.reference.copy()
        ctrl.action('zoom_in');until(lambda:ctrl.snapshot()['zoom']==1.6)
        assert ctrl.tracking and np.allclose(ctrl.reference,ref)
        ctrl.action('zoom_out');until(lambda:ctrl.snapshot()['zoom']==1.5)
        Link.latest.stale=True
        until(lambda:ctrl.snapshot()['state']=='HOLD')
        sent=len(Link.latest.sent);time.sleep(.05);assert len(Link.latest.sent)==sent
        Link.latest.stale=False
        until(lambda:ctrl.snapshot()['state']=='LOCKED')
        Link.latest.generation+=1
        until(lambda:ctrl.sensor_generation==3)
        assert not ctrl.tracking and ctrl.reference is None
        time.sleep(.1);assert not ctrl.tracking
        ctrl.action('off');until(lambda:ctrl.snapshot()['state']=='OFF')
    finally:ctrl.close()
    assert not ctrl.thread.is_alive() and Link.latest.closed
    # Verify diagnostic mode cannot bypass missing product/feature ack.
    ctrl.bno_diagnostics=None
    try:ctrl.ready_pose(Link.latest.imu_state())
    except ValueError:pass
    else:raise AssertionError('Missing BNO product identification accepted')
checks.append('BNO-only controller with no capture reads; feature ack, 200Hz count, stale hold, reset invalidates reference, off/exit cleanup')

files=['host/bno085.py','host/imu.py','host/imu_trial.py','calibration/bno085_mount.json',
       'tools/check_bno085.py','tools/analyze_bno085_log.py','reports/bno085_axis_direction_review.json']
report=dict(passed=True,hardware_access=False,checks=checks,
 inputs_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
 limitations=['No physical BNO data replay supplied','Actual module voltage/pin mux and signed rotation convention require board tests',
 '200Hz requested, not yet measured','Exposure-time association remains approximate'])
(ROOT/'reports/bno085_offline_checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
