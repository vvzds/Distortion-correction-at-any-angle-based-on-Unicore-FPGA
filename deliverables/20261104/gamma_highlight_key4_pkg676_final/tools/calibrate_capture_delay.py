"""Small +/-3 degree scene sweep to estimate publication-to-capture time offset.
Requires an explicitly authorized board trial and a physically fixed camera.
Only parameters/quality are written; camera frames stay in memory.
"""
import argparse
from pathlib import Path
import json
import sys
import time
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from board_trial import Capture
from protocol import Connection
from model import load_calibration,compile_registers,affine
from stabilizer import ReferenceTracker,matrix_from_registers,corner_distance

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',default='COM9')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    cv2.setNumThreads(2)
    c=load_calibration();base=np.vstack((affine(zoom=1.15),[0,0,1]))
    cap=Capture();link=Connection(args.port)
    frames=[];states=[];checks=[]
    try:
        link.frame_state()
        link.configure(compile_registers(c,base[:2],False),timeout=.6)
        time.sleep(.6)
        reference=cap.read()[2].copy()
        start=time.monotonic();last_record=-1.;last_frame=-1
        while time.monotonic()-start < 5.5:
            now=time.monotonic();t=now-start
            angle=3*np.sin(2*np.pi*t/2.5)
            link.set_target(compile_registers(c,affine(angle,1.15),False,smooth=True))
            before=time.monotonic();state=link.frame_state();after=time.monotonic()
            states.append(((before+after)/2,matrix_from_registers(c,state['registers'])))
            item=cap.read()
            if item and item[0]!=last_frame and now-last_record >= .10:
                frames.append((item[1],item[2].copy()));last_frame=item[0];last_record=now
            time.sleep(max(0.,.035-(time.monotonic()-now)))
        status=link.status()
        if any(status[k] for k in ['core_fault','write_fault','overflow_tiles','rx_errors']):
            raise RuntimeError(status)
        fps=cap.fps()
    finally:
        try:link.configure(compile_registers(c,np.eye(3)[:2],False),timeout=.6)
        finally:link.close();cap.close()
    tracker=ReferenceTracker();tracker.anchor(reference)
    for stamp,image in frames:
        try:
            delta,quality=tracker.estimate(image)
            checks.append((stamp,delta,quality))
        except ValueError:
            pass
    candidates=[]
    for delay in np.arange(0.,.401,.005):
        errors=[]
        for stamp,delta,quality in checks:
            earlier=[(ts,m) for ts,m in states if ts<=stamp-delay]
            if not earlier:continue
            actual=earlier[-1][1]
            errors.append(corner_distance(actual@delta,base))
        if len(errors)>=15:
            candidates.append(dict(delay_s=float(delay),median_corner_error_px=float(np.median(errors)),
                                   p95_corner_error_px=float(np.percentile(errors,95)),samples=len(errors)))
    if not candidates:raise RuntimeError('Insufficient scene matches for delay calibration')
    best=min(candidates,key=lambda x:x['median_corner_error_px'])
    report=dict(best=best,capture_fps=fps,health=status,checked_frames=len(checks),
                candidates=candidates,raw_captures_saved=False,
                meaning='Estimated time offset from UART publication sampling to capture decode. Not exposure-to-display latency.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='candidates'},indent=2))
if __name__=='__main__':main()
