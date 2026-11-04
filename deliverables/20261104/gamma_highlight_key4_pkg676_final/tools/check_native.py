import sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from generate_frame_vectors import generate
from run_sim import run
p=argparse.ArgumentParser();p.add_argument('--angle',type=float,default=45);p.add_argument('--zoom',type=float,default=1)
p.add_argument('--latency',type=int,default=24);p.add_argument('--gap',type=int,default=4);p.add_argument('--period',type=int,default=514)
p.add_argument('--next-angle',type=float)
p.add_argument('--feedback-tag',type=int)
p.add_argument('--smooth-next',action='store_true',help='Check an actual second-frame half-step, no hardware')
a=p.parse_args();tag=generate(a.angle,a.zoom,a.feedback_tag);folder=ROOT/'build/vectors'
extra=[];suffix=''
if a.next_angle is not None:
    tag2=generate(a.next_angle,a.zoom);suffix=f'_then{a.next_angle:g}'
    if a.smooth_next:
        from model import compile_registers,load_calibration,affine
        start=compile_registers(load_calibration(),affine(a.angle,a.zoom),False)
        target=compile_registers(load_calibration(),affine(a.next_angle,a.zoom),False,smooth=True)
        expected=target.copy()
        for i in range(6):expected[i]=start[i]+((target[i]-start[i])//2 or (1 if target[i]>start[i] else 0))
        tag2=generate(a.next_angle,a.zoom,registers_override=expected,suffix='_halfstep')
        # The bus carries the target; only the golden model uses interpolated values.
        (folder/f'frame_config_{tag2}.hex').write_text('\n'.join(f'{r&0xffffffff:08x}' for r in target)+'\n')
        suffix+='_smooth'
    extra=['+CONFIG2='+str(folder/f'frame_config_{tag2}.hex'),'+GOLDEN2='+str(folder/f'golden_{tag2}.hex')]
run('native_video_tb',['source/rtl/projective_divide.v','source/rtl/mul32_pipe.v','source/rtl/brown_map.v','source/rtl/patch_store.v','source/rtl/bilinear_rgb.v',
    'source/rtl/adaptive_gamma.v','source/rtl/tile_engine.v','source/rtl/tile_write_pack.v',
    'source/rtl/corr_read_bridge.v','source/rtl/corr_write_arb.v','sim/native_video_tb.v'],
    ['+CONFIG='+str(folder/f'frame_config_{tag}.hex'),'+GOLDEN='+str(folder/f'golden_{tag}.hex'),
     '+RESULT='+str(ROOT/f'reports/native_{tag}{suffix}_latency{a.latency}_period{a.period}.json'),
     f'+LATENCY={a.latency}',f'+GAP={a.gap}',f'+PERIOD={a.period}',*extra])
