"""Full frame from a held-out camera PNG through production RTL/DDR brokers."""
import argparse,os,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(os.environ.get('FPGA_SIM_ROOT',Path(__file__).resolve().parents[1])).absolute()
sys.path[:0]=[str(ROOT/'host'),str(ROOT/'tools')]
from model import load_calibration,compile_registers,fixed_map
from resample import bilinear565,pack565
from run_sim import run

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,
                    default=ROOT/'reports/real_images/rtl_full_frame_fixture.png',
                    help='1080p image used for the bit-exact full-frame RTL regression')
args=parser.parse_args()
folder=ROOT/'build/vectors';folder.mkdir(parents=True,exist_ok=True)
path=args.source
image=cv2.imread(str(path))
if image is None:raise FileNotFoundError(f'Unable to load full-frame RTL fixture: {path}')
regs=compile_registers(load_calibration(),adaptive=False)
sx,sy,valid=fixed_map(regs);golden=pack565(bilinear565(image,sx,sy,valid))
config=folder/'real_config.hex';source=folder/'real_source.hex';target=folder/'real_golden.hex'
config.write_text('\n'.join(f'{r&0xffffffff:08x}' for r in regs)+'\n')
np.savetxt(source,pack565(image).reshape(-1),fmt='%04x');np.savetxt(target,golden.reshape(-1),fmt='%04x')
run('native_video_tb',['source/rtl/projective_divide.v','source/rtl/mul32_pipe.v','source/rtl/brown_map.v','source/rtl/patch_store.v','source/rtl/bilinear_rgb.v',
    'source/rtl/adaptive_gamma.v','source/rtl/tile_engine.v','source/rtl/tile_write_pack.v',
    'source/rtl/corr_read_bridge.v','source/rtl/corr_write_arb.v','sim/native_video_tb.v'],
    [f'+CONFIG={config}',f'+SOURCE={source}',f'+GOLDEN={target}',
     '+RESULT='+str(ROOT/'reports/native_real_pose031.json'),'+LATENCY=40','+GAP=4','+PERIOD=514'])
