import sys,argparse
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'host'))
from model import load_calibration,compile_registers,affine,fixed_map,tile_profile

def source(x,y):
    return ((x&31)<<11)|((y&63)<<5)|((x^y)&31)

def generate(angle=0,zoom=1,feedback_tag=None,registers_override=None,suffix=''):
    folder=ROOT/'build/vectors';folder.mkdir(parents=True,exist_ok=True)
    regs=compile_registers(load_calibration(),affine(angle,zoom),adaptive=False,feedback_tag=feedback_tag)
    if registers_override is not None:regs=list(registers_override)
    sx,sy,ok=fixed_map(regs);print(tile_profile(sx,sy,ok))
    x=np.clip(sx>>16,0,1919);y=np.clip(sy>>16,0,1079)
    x1=np.minimum(x+1,1919);y1=np.minimum(y+1,1079)
    wx=(sx>>8)&255;wy=(sy>>8)&255
    pixels=[source(x,y),source(x1,y),source(x,y1),source(x1,y1)]
    result=np.zeros(x.shape,dtype=np.int64)
    for shift,mask in [(11,31),(5,63),(0,31)]:
        a,b,c,d=[(p>>shift)&mask for p in pixels]
        h0=a*(256-wx)+b*wx;h1=c*(256-wx)+d*wx
        channel=(h0*(256-wy)+h1*wy+32768)>>16
        result|=channel<<shift
    result=np.where(ok,result,0)
    # Legacy marker flags are ignored by clean firmware: even an old client
    # cannot write metadata into the picture.
    tag=f'{angle:g}_{zoom:g}'
    if feedback_tag is not None:tag+=f'_tag{feedback_tag}'
    tag+=suffix
    (folder/f'frame_config_{tag}.hex').write_text('\n'.join(f'{r&0xffffffff:08x}' for r in regs)+'\n')
    with (folder/f'golden_{tag}.hex').open('w') as f:
        np.savetxt(f,result,fmt='%04x')
    return tag

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--angle',type=float,default=0);p.add_argument('--zoom',type=float,default=1)
    a=p.parse_args();print(generate(a.angle,a.zoom))
