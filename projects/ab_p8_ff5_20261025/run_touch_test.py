from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parent;O=R/'results/touch_exhaustive_retry';O.mkdir(parents=True,exist_ok=False)
T=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app')
drive=next(c+':' for c in 'YXWVUTSRQP' if not Path(c+':/').exists());subprocess.run(['subst',drive,str(T)],check=True)
files=[R/'tests/p8_touch_exhaustive_tb.sv',R/'candidate/source/rtl/undistort_cache_ab.v']
before={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
commands=[[str(Path(drive+'/')/'bin/iverilog.exe'),'-B',str(Path(drive+'/')/'lib/ivl'),'-g2012','-s','p8_touch_exhaustive_tb','-o',str(O/'sim.vvp')]+[str(p) for p in files],[str(Path(drive+'/')/'bin/vvp.exe'),str(O/'sim.vvp')]]
steps=[]
try:
 for cmd,name in zip(commands,['compile','simulation']):
  with (O/(name+'.log')).open('wb') as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=90).returncode
  steps.append(dict(argv=cmd,exit_code=rc))
  if rc:break
finally:subprocess.run(['subst',drive,'/D'],check=True)
after={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
text=(O/'simulation.log').read_text(errors='replace') if (O/'simulation.log').exists() else ''
result=dict(passed=len(steps)==2 and all(s['exit_code']==0 for s in steps) and 'P8_TOUCH_EXHAUSTIVE PASS checks=2752' in text and before==after,steps=steps,inputs_before=before,inputs_after=after,log=text)
(O/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(text);raise SystemExit(0 if result['passed'] else 1)
