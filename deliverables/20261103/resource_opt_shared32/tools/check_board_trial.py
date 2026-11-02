"""Controller concurrency/protocol checks using only in-memory fakes; no devices."""
from pathlib import Path
import argparse
import json
import queue
import struct
import sys
import tempfile
import time

import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
import board_trial
from model import affine,compile_registers,load_calibration
from protocol import Connection,decode
from stabilizer import matrix_from_registers

class FakeLink:
    def __init__(self,port):
        self.regs=compile_registers(load_calibration(),affine(zoom=1.15),False)
        self.sent=[]
        self.frames=0
    def frame_state(self):
        self.frames+=1
        return dict(frames=self.frames,registers=self.regs[:6],gamma=0,flags=self.regs[15])
    def status(self):
        return dict(frames=self.frames,core_fault=False,write_fault=False,overflow_tiles=0,rx_errors=0,gamma_mode=0)
    def configure(self,regs,timeout):
        self.regs=regs.copy();self.sent.append((time.monotonic(),regs.copy()))
        return self.status()
    def set_target(self,regs):
        self.regs=regs.copy();self.sent.append((time.monotonic(),regs.copy()))
    def close(self): self.closed=True

class FakeCapture:
    error=None
    frame=np.zeros((1080,1920,3),np.uint8)
    def read(self):
        now=time.monotonic()
        return int(now*30),now,self.frame

class FakeEstimator:
    def __init__(self,width):
        import threading
        self.results=queue.Queue();self.stopped=threading.Event()
    def submit(self,item):
        generation,anchor,stamp,frame,seen=item
        if anchor:
            self.results.put((generation,True,stamp,100,None,.001))

args=argparse.Namespace(analysis_width=800,capture_delay=0.,zoom=1.15,gamma=False,
    shape_limit=.02,shape_response=.8,shape_rate=.015,
    response_time=.08,max_speed=700.,command_rate=30.,deadband=.5,max_age=.25,
    calibration=ROOT/'calibration/ov5640_1080p.json',port='FAKE',auto_start=False)
board_trial.Connection=FakeLink
board_trial.Estimator=FakeEstimator

def wait_for(predicate,timeout=2.):
    deadline=time.monotonic()+timeout
    while not predicate():
        if time.monotonic()>deadline:raise AssertionError('Controller state timeout')
        time.sleep(.005)

with tempfile.TemporaryDirectory() as tmp:
    args.output=Path(tmp)
    c=board_trial.Controller(FakeCapture(),args)
    wait_for(lambda:c.snapshot()['state']=='OFF')
    c.action('start');wait_for(lambda:c.snapshot()['state']=='LOCKED')
    baseline=len(c.link.sent)
    target=np.vstack((affine(10,1.15,shear=.12),[0,0,1]))
    # One observation only: UART must continue making small moves while a
    # hypothetical global ORB job runs. No fresh estimates are injected.
    c.estimator.results.put((c.generation,False,time.monotonic(),
        (target,dict(method='FAKE',inliers=100,rms_px=.5)),None,.001))
    time.sleep(.25)
    during=c.link.sent[baseline:]
    assert len(during)>=4, len(during)
    assert all(regs[15] & (1<<17) for _,regs in during)
    # Narrow/unknown support must not leak a stretched fit to the UART path.
    for _,regs in during:
        actual=matrix_from_registers(load_calibration(),regs[:6])
        singular=np.linalg.svd(actual[:2,:2],compute_uv=False)
        assert singular[0]/singular[1] < 1.001
    c.action('off');wait_for(lambda:c.snapshot()['state']=='OFF')
    stale_generation=c.generation-1
    c.estimator.results.put((stale_generation,False,time.monotonic(),
        (target,dict(method='FAKE',inliers=100,rms_px=.5)),None,.001))
    time.sleep(.08)
    assert c.snapshot()['state']=='OFF' and c.link.regs[15]==0
    c.close()
    assert c.snapshot()['state']=='CLOSED' and not c.thread.is_alive()
    assert c.link.regs==compile_registers(load_calibration(),np.eye(3)[:2],False)

# Exceptions must restore a clean identity too, without process/window cleanup.
class FaultCapture(FakeCapture):
    pass
with tempfile.TemporaryDirectory() as tmp:
    args.output=Path(tmp)
    cap=FaultCapture()
    c=board_trial.Controller(cap,args)
    wait_for(lambda:c.snapshot()['state']=='OFF')
    cap.error='Injected capture failure'
    wait_for(lambda:not c.thread.is_alive())
    assert c.snapshot()['state']=='ERROR' and c.link.closed
    assert c.link.regs==compile_registers(load_calibration(),np.eye(3)[:2],False)

# Verify frame-state payload parsing without constructing serial.Serial.
class Port:
    def write(self,data):self.last=data
link=Connection.__new__(Connection);link.serial=Port();link.sequence=5
payload=struct.pack('<12I',0x534d5432,12,1,2,3,4,5,6,12,0,1<<17,0x00020001)
link._receive=lambda command,seq,timeout:payload
state=link.frame_state()
assert state['registers']==[1,2,3,4,5,6] and state['frames']==12
assert decode(link.serial.last)[0]==0x21
report=dict(passed=True,hardware_opened=False,
    commands_during_250ms_without_new_estimate=len(during),
    checks=['Estimator does not block UART progression','Stale generation cannot override OFF',
            'OFF, normal exit and capture exception restore exact configuration',
            'Unsupported shear does not leak to UART commands','Clean frame-state protocol parsing'])
(ROOT/'reports/board_trial_offline_checks.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
