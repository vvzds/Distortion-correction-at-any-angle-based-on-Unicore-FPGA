"""Offline host checks, including a withdrawn Tk instance; no port is opened."""
import binascii,hashlib,json,struct,sys,time,tkinter as tk
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'host'))
from protocol import (packet,decode,parse_status,Connection,MAGIC,
                      CMD_SHARPEN,CMD_DENOISE,CMD_OSD_ROW,CMD_OSD_VISIBLE,
                      parse_quality_ack)
from osd_monitor import calibration_rows
from model import load_calibration,affine,preflight,compile_registers,fixed_map
from resample import pack565,unpack565,static_gamma565
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
status=parse_status(struct.pack('<12I',MAGIC,(8<<16)|7,123,3125000,4,5,6,7,8,0x6b4ef,9,10))
assert status['active_sequence']==7 and status['pending_sequence']==8
assert status['processing_capacity_fps']==40 and status['gamma_mode']==2
assert status['core_fault'] and status['write_fault'] and status['pending'] and status['busy']
assert status['pose_map_enabled'] and status['pose_reference_valid']
assert status['pose_capture_generation']==0x5a
assert status['pose_map_valid'] and not status['pose_map_busy']
assert status['key1_lock_requested']
checks.append('Status field positions, flags and cycle-to-capacity conversion')

class MockPort:
    def __init__(self):self.last_packets=[]
    def write(self,data):self.last=data;self.last_packets.append(data);return len(data)
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
link.serial.last_packets.clear()
def quality_ack(command,sequence,timeout=1.):
    request_command,request_sequence,body=decode(link.serial.last_packets[-1])
    assert request_command|0x80==command and request_sequence==sequence
    assert body in (b'\x02',b'\x01')
    return struct.pack('<4sBBBB',b'QACK',1,request_command,body[0],0)+bytes(40)
link._receive=quality_ack
link.set_quality(2,1)
commands=[]
for frame in link.serial.last_packets:
    commands.append(decode(frame)[0])
assert commands==[CMD_DENOISE,CMD_SHARPEN]
valid_ack=struct.pack('<4sBBBB',b'QACK',1,CMD_DENOISE,1,0)+bytes(40)
assert parse_quality_ack(valid_ack,CMD_DENOISE,1)['level']==1
link.serial.last_packets.clear();ack_count=[0]
def partial_quality_ack(command,sequence,timeout=1.):
    ack_count[0]+=1
    if ack_count[0]==1:return struct.pack('<4sBBBB',b'QACK',1,command&0x7f,2,0)+bytes(40)
    raise TimeoutError('injected missing sharpen ACK')
link._receive=partial_quality_ack
try:link.set_quality(2,3)
except RuntimeError as error:
    assert 'denoise confirmed' in str(error) and 'sharpen is unknown' in str(error)
else:raise AssertionError('Partial quality ACK was reported as success')
assert len(link.serial.last_packets)==2
link.serial.last_packets.clear()
def no_quality_ack(command,sequence,timeout=1.):
    raise TimeoutError('injected missing quality ACK')
link._receive=no_quality_ack
try:link.set_quality(0,0)
except RuntimeError as error:
    assert 'none' in str(error) and 'denoise is unknown' in str(error)
else:raise AssertionError('Missing quality ACK was reported as success')
assert len(link.serial.last_packets)==1
for bad_ack in (bytes(48),struct.pack('<4sBBBB',b'QACK',1,CMD_DENOISE,2,1)+bytes(40),
                struct.pack('<4sBBBB',b'QACK',1,CMD_DENOISE,3,0)+bytes(40)):
    try:parse_quality_ack(bad_ack,CMD_DENOISE,2)
    except ValueError:pass
    else:raise AssertionError('Malformed quality ACK accepted')
checks.append('Per-command QACK confirmation, matching payload/sequence and partial-failure reporting')
rows=calibration_rows(load_calibration())
assert set(rows)==set(range(4))
assert all(any(key in rows[i] for key in ('FX','FY')) for i in [0])
assert 'CX' in rows[1] and 'K1' in rows[2] and 'P1' in rows[3]
assert all(len(text.encode('ascii'))<=48 for text in rows.values())
assert not any(key in ''.join(rows.values()) for key in ('A11','ZOOM','DENOISE','SHARPEN'))
checks.append('KEY4 OSD contains exactly four camera calibration rows')
gamma_values=np.array([0x7bef]*6+[0xdebc,0xffff],dtype=np.int64)
gamma_image=unpack565(gamma_values).reshape(1,8,3)
gamma_result,gamma_mode=static_gamma565(gamma_image,np.ones((1,8),dtype=bool))
assert gamma_mode==3 and pack565(gamma_result)[0,6]==0xd65b
assert pack565(gamma_result)[0,0]==0x7bef
checks.append('Highlight gamma preview preserves midtones and rolls off bright non-clipped values')
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
