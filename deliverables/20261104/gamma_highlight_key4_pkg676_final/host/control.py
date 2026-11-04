"""CLI for calibration, affine preflight, UART control and measured frame rate."""
import argparse,json,time
from pathlib import Path
import numpy as np
from model import load_calibration,affine,preflight,fixed_map,compile_registers,ROOT
from protocol import Connection
from resample import bilinear565,static_gamma565

def covering_zoom(c,angle,tx=0,ty=0,shear=0):
    """Find a crop that contains only valid samples; verify the full final map."""
    u,v=np.meshgrid(np.linspace(0,1919,65).round().astype(int),np.linspace(0,1079,37).round().astype(int))
    lo,hi=.5,8.
    def fits(z):
        r=compile_registers(c,affine(angle,z,tx,ty,shear));return fixed_map(r,u,v)[2].all()
    if not fits(hi): raise ValueError('No border-free crop in supported zoom range')
    for _ in range(16):
        mid=(lo+hi)/2
        if fits(mid): hi=mid
        else: lo=mid
    z=hi*1.003
    for _ in range(10):
        _,report=preflight(c,affine(angle,z,tx,ty,shear))
        if report['valid_fraction']==1.: return z
        z*=1.01
    raise ValueError('Full-resolution crop validation failed')

def main():
    p=argparse.ArgumentParser(description='紫光 FPGA 图像校正上位机')
    p.add_argument('command',choices=['ports','preflight','send','status','monitor','preview'])
    p.add_argument('--calibration',default=str(ROOT/'calibration/ov5640_1080p.json'))
    p.add_argument('--angle',type=float,default=0);p.add_argument('--zoom',type=float,default=1)
    p.add_argument('--tx',type=float,default=0);p.add_argument('--ty',type=float,default=0)
    p.add_argument('--shear',type=float,default=0);p.add_argument('--auto-crop',action='store_true')
    p.add_argument('--linear',action='store_true');p.add_argument('--port');p.add_argument('--seconds',type=float,default=10)
    p.add_argument('--input');p.add_argument('--output')
    a=p.parse_args()
    if a.command=='ports':
        from serial.tools.list_ports import comports
        print(json.dumps([{'port':x.device,'description':x.description} for x in comports()],ensure_ascii=False,indent=2));return
    if a.command in ['preflight','send','preview']:
        c=load_calibration(a.calibration)
        if a.auto_crop:a.zoom=max(a.zoom,covering_zoom(c,a.angle,a.tx,a.ty,a.shear))
        matrix=affine(a.angle,a.zoom,a.tx,a.ty,a.shear)
        registers,report=preflight(c,matrix,not a.linear)
        report.update(angle=a.angle,zoom=a.zoom,tx=a.tx,ty=a.ty,shear=a.shear)
        if a.command=='preflight':
            print(json.dumps(report,indent=2));return
        if a.command=='preview':
            import cv2
            image=cv2.imread(a.input or '')
            if image is None or image.shape[:2]!=(1080,1920): raise ValueError('Input must be a readable 1920x1080 image')
            sx,sy,valid=fixed_map(registers)
            out=bilinear565(image,sx,sy,valid)
            if not a.linear:out,mode=static_gamma565(out,valid)
            target=Path(a.output or 'preview.png');target.parent.mkdir(parents=True,exist_ok=True)
            if not cv2.imwrite(str(target),out):raise IOError(target)
            print(json.dumps({'output':str(target.resolve()),'preview':'RGB565 bit model; gamma assumes a steady scene',**report},indent=2));return
    if not a.port:p.error('--port is required for hardware commands')
    link=Connection(a.port)
    try:
        if a.command=='send':print(json.dumps({'preflight':report,'status':link.configure(registers)},indent=2))
        elif a.command=='status':print(json.dumps(link.status(),indent=2))
        elif a.command=='monitor':
            samples=[];end=time.monotonic()+a.seconds
            while True:
                state=link.status();samples.append({'monotonic':time.monotonic(),**state})
                if time.monotonic()>=end:break
                time.sleep(.5)
            first,last=samples[0],samples[-1];elapsed=last['monotonic']-first['monotonic']
            measured=((last['frames']-first['frames'])&0xffffffff)/elapsed if elapsed else 0
            result={'actual_new_frame_fps':measured,'elapsed_seconds':elapsed,'samples':samples}
            if a.output:Path(a.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result,indent=2))
    finally:link.close()

if __name__=='__main__':main()
