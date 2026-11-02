import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'host'),str(ROOT/'tools')]
from model import load_calibration,affine,compile_registers,fixed_map
from run_sim import run

c=load_calibration();folder=ROOT/'build'/'vectors';folder.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(108030)
u=np.r_[np.arange(1920),rng.integers(0,1920,30000),[0,1919,0,1919]]
v=np.r_[np.zeros(1920,dtype=int),rng.integers(0,1080,30000),[0,0,1079,1079]]
cases=[(angle,1,0,0,0,None) for angle in [0,45,90,135,270]]
cases += [(12.375,1.17,37.25,-24.75,.15,None),
          (359.9,.5,0,0,-.3,None),(-120,8,-1000,2000,.1,None),
          (45,1,10000,0,0,None),
          (0,1,0,0,0,(.08,-.04)),(12,1.1,25,-10,.02,(-.12,.07)),
          (0,1,0,0,0,(.5,.5))]
for index,(angle,zoom,tx,ty,shear,projective) in enumerate(cases):
    regs=compile_registers(c,affine(angle,zoom,tx,ty,shear),projective=projective)
    sx,sy,valid=fixed_map(regs,u,v)
    config=folder/f'config_case{index}.hex';vectors=folder/f'map_case{index}.txt'
    config.write_text('\n'.join(f'{r&0xffffffff:08x}' for r in regs)+'\n')
    vectors.write_text(''.join(f'{a} {b} {int(x)&0x7ffffff:07x} {int(y)&0x7ffffff:07x} {int(ok)}\n' for a,b,x,y,ok in zip(u,v,sx,sy,valid)))
    run('brown_map_tb',['source/rtl/projective_divide.v','source/rtl/mul32_pipe.v',
                        'source/rtl/brown_map.v','sim/brown_map_tb.v'],
        ['+CONFIG=build/vectors/'+config.name,
         '+VECTORS=build/vectors/'+vectors.name])
