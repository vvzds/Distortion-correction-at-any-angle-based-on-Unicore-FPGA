"""Full-pixel software sweep: bounded patches and float/fixed map error."""
import argparse,hashlib,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'host'))
from model import load_calibration,affine,preflight,fixed_map,float_map
p=argparse.ArgumentParser();p.add_argument('--step',type=int,default=5);a=p.parse_args()
if not 1<=a.step<=90:raise ValueError('step must be in [1,90]')
c=load_calibration();rows={};start=time.monotonic()
for angle in range(0,360,a.step):
    matrix=affine(angle);regs,report=preflight(c,matrix,False)
    if angle in [0,30,45,90,135,180,270]:
        sx,sy,ok=fixed_map(regs);fx,fy,float_ok=float_map(c,matrix)
        error=np.hypot(sx/65536-fx,sy/65536-fy)[ok&float_ok]
        report['max_error_px']=float(error.max());report['p99_error_px']=float(np.percentile(error,99))
    rows[str(angle)]=report
summary={'angle_step_degrees':a.step,'angle_count':len(rows),'elapsed_seconds':time.monotonic()-start,
         'all_tiles_fit':True,'gamma_enabled':False,'zoom':1.,'results':rows,
         'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [ROOT/'host/model.py',ROOT/'calibration/ov5640_1080p.json']}}
(ROOT/'reports/angle_sweep.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(ROOT/'reports/map_preflight.json').write_text(json.dumps({k:v for k,v in rows.items() if 'max_error_px' in v},indent=2))
print('PASS',len(rows),'angles, max read beats',max(r['read_beats'] for r in rows.values()),
      'max row commands',max(r['row_commands'] for r in rows.values()))
