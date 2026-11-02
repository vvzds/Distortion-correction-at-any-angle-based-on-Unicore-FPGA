"""Offline host checks, including a withdrawn Tk instance; no port is opened."""
import binascii,hashlib,json,struct,sys,time,tkinter as tk
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'host'))
from protocol import (packet,decode,parse_status,Connection,MAGIC,
                      CMD_SHARPEN,CMD_DENOISE,CMD_OSD_ROW,CMD_OSD_VISIBLE)
from osd_monitor import calibration_rows
from model import load_calibration,affine,preflight,compile_registers,fixed_map
from gui import Application

start=time.monotonic();checks=[]
assert binascii.crc_hqx(b'123456789',0xffff)==0x29b1
data=packet(0x10,65535,bytes(range(64)))
assert decode(data)==(0x10,65535,bytes(range(64)))
bad=bytearray(data);bad[14]^=1
try:decode(bad)
except ValueError:pass
else:raise AssertionError('Bad CRC accepted')
checks.append('CRC16 check vector, packet round trip and corruption rejection')
status=parse_status(struct.pack('<12I',MAGIC,(8<<16)|7,123,3125000,4,5,6,7,8,0x2b4ef,9,10))
assert status['active_sequence']==7 and status['pending_sequence']==8
assert status['processing_capacity_fps']==40 and status['gamma_mode']==2
assert status['core_fault'] and status['write_fault'] and status['pending'] and status['busy']
assert status['pose_map_enabled'] and status['pose_reference_valid']
assert status['pose_capture_generation']==0x5a
assert status['pose_map_valid'] and not status['pose_map_busy']
checks.append('Status field positions, flags and cycle-to-capacity conversion')

class MockPort:
    def __init__(self):self.last_packets=[]
    def write(self,data):self.last=data;self.last_packets.append(data)
link=Connection.__new__(Connection);link.serial=MockPort();link.sequence=65534
previous=dict(status,active_sequence=65535,pending_sequence=0)
def mock_status():
    if not hasattr(link.serial,'last'):return previous
    return dict(status,active_sequence=decode(link.serial.last)[1],core_fault=False,write_fault=False)
link.status=mock_status
regs,_=preflight(load_calibration(),affine(),False)
link.configure(regs)
assert decode(link.serial.last)[1]==1
checks.append('Sequence wrap cannot match an old active/pending configuration')
link.sequence=7;status_calls=[0]
def pose_status():
    status_calls[0]+=1
    return dict(status,pose_capture_generation=0x5a if status_calls[0]==1 else 0x5b)
link.status=pose_status
link.set_pose_map(True)
assert decode(link.serial.last)==(0x26,8,b'\x01')
checks.append('Pose-map command carries capture/enable request and waits for reference status')
link.sequence=100
quality_status=dict(status,rx_errors=8,valid_packets=20)
def quality_mock_status():
    quality_status['valid_packets']+=2
    return dict(quality_status)
link.status=quality_mock_status
link.serial.last_packets.clear()
link.set_quality(2,1)
commands=[]
for frame in link.serial.last_packets:
    commands.append(decode(frame)[0])
assert commands==[CMD_DENOISE,CMD_SHARPEN]
checks.append('Denoise/sharpen levels use distinct validated UART commands')
rows=calibration_rows(load_calibration())
assert all(rows[i] for i in range(4)) and all(not rows[i] for i in range(4,8))
assert all(len(text.encode('ascii'))<=48 for text in rows.values())
checks.append('Four-row calibration OSD payload fits the merged 48-character protocol')
projective_regs=compile_registers(load_calibration(),affine(),adaptive=False,
                                  feedback_tag=0x1234,smooth=True,
                                  projective=(.125,-.0625))
assert projective_regs[14]&15==14
assert ((projective_regs[14]&0xffffffff)>>16)==2048
assert ((projective_regs[15]&0xffffffff)>>16)==((-1024)&65535)
assert projective_regs[15]&65535==0x1234
sx,sy,valid=fixed_map(projective_regs,np.array([300,960,1600]),np.array([180,540,900]))
assert valid.all() and np.any(sx!=np.array([300,960,1600],dtype=np.int64)<<16)
legacy_regs=compile_registers(load_calibration(),affine(),adaptive=False,
                              feedback_tag=0x1234,smooth=True)
assert legacy_regs[14]==0 and legacy_regs[15]==0x00031234
checks.append('Projective Q14 fields use reserved high bits; legacy Gamma/feedback/smooth encoding remains unchanged')

root=tk.Tk();root.withdraw()
app=Application(root);root.update_idletasks()
assert len(root.winfo_children())>0 and app.link is None
_,report,parameters=app.prepare(dict(angle=90,zoom=2.,tx=0.,ty=0.,shear=0.),True,True)
assert parameters['zoom']==2. and report['valid_fraction']==1.
app.angle.set('invalid');assert app.parameters() is None
root.destroy()
checks.append('Hidden GUI initialization, no implicit serial open, manual zoom preserved, invalid text handled')
report={'passed':True,'hardware_opened':False,'elapsed_seconds':time.monotonic()-start,'checks':checks,
        'inputs_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (ROOT/'host').glob('*.py')}}
(ROOT/'reports/host_checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PASS host checks:',len(checks))
