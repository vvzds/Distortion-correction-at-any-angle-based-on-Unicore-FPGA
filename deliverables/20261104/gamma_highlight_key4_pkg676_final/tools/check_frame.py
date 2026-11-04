import sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from generate_frame_vectors import generate
from run_sim import run
p=argparse.ArgumentParser();p.add_argument('--angle',type=float,default=0);p.add_argument('--zoom',type=float,default=1)
p.add_argument('--latency',type=int,default=24);p.add_argument('--gap',type=int,default=4)
a=p.parse_args();tag=generate(a.angle,a.zoom)
folder=ROOT/'build/vectors'
run('tile_engine_tb',['source/rtl/projective_divide.v','source/rtl/mul32_pipe.v','source/rtl/brown_map.v','source/rtl/patch_store.v','source/rtl/bilinear_rgb.v',
    'source/rtl/adaptive_gamma.v','source/rtl/tile_engine.v','source/rtl/tile_write_pack.v','sim/tile_engine_tb.v'],
    ['+CONFIG='+str(folder/f'frame_config_{tag}.hex'),'+GOLDEN='+str(folder/f'golden_{tag}.hex'),
     '+RESULT='+str(ROOT/f'reports/frame_{tag}_latency{a.latency}.json'),f'+LATENCY={a.latency}',f'+GAP={a.gap}'])
