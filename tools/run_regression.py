"""Portable G6 regression. Requires locally installed ModelSim; downloads nothing."""
from pathlib import Path
import argparse, datetime, hashlib, json, re, shutil, subprocess, time

P=argparse.ArgumentParser()
P.add_argument('--vsim',required=True,type=Path)
P.add_argument('--scratch',required=True,type=Path,help='Existing writable ASCII parent; a fresh child is created')
P.add_argument('--only',choices=['all','map','equiv','cache','bilinear','protocol','core_suite','integration'],default='all')
A=P.parse_args()
ROOT=Path(__file__).resolve().parent.parent
assert A.vsim.is_file(), 'ModelSim executable missing'
assert A.scratch.is_dir(), 'Create scratch parent first'
assert A.scratch.resolve().as_posix().isascii(), 'ModelSim 10.7 requires ASCII work path'
RUN=A.scratch.resolve()/('g6_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
RUN.mkdir()
LOG=RUN/'evidence';LOG.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
for part in ('source','sim'):
 shutil.copytree(ROOT/part,RUN/part)
shutil.copytree(ROOT/'verification/g6_baseline',RUN/'verification/g6_baseline')
manifest={p.relative_to(ROOT).as_posix():sha(p) for d in ('source','sim','verification/g6_baseline','verification/integration_received') for p in (ROOT/d).rglob('*') if p.is_file()}
(LOG/'input_sha256.json').write_text(json.dumps(manifest,indent=2))
jobs=[('map','run_undistort_map.do',['map_result.txt']),
 ('equiv','run_undistort_map_g6_equiv.do',['map_g6_equiv_result.txt']),
 ('cache','run_undistort_line_cache.do',['line_cache_result.txt']),
 ('bilinear','run_undistort_bilinear.do',['bilinear_result.txt']),
 ('protocol','run_undistort_core_g4_protocol.do',['core_g4_protocol_result.txt','core_g4_protocol_sim_result.txt']),
 ('core_suite','run_undistort_core.do',['core_suite_result.txt'])]
results=[]
def invoke(label,runner,cwd):
 start=time.monotonic();print('RUN '+label,flush=True)
 path=LOG/(label+'_console.log')
 with path.open('wb') as f:
  p=subprocess.run([str(A.vsim.resolve()),'-batch','-do','do '+runner],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=2400)
 text=path.read_text(encoding='utf-8',errors='replace')
 assert p.returncode==0,(label,p.returncode,path)
 # Match actual diagnostic lines, not echoed Tcl regex source containing FAIL/TIMEOUT.
 assert not re.search(r'(?m)^(?:# )?\*\* (?:Error|Fatal):',text),(label,path)
 row=dict(test=label,exit_code=p.returncode,seconds=round(time.monotonic()-start,3),log_sha256=sha(path))
 return text,row
for label,runner,result_names in jobs:
 if A.only not in ('all',label):continue
 text,row=invoke(label,runner,RUN/'sim')
 for name in result_names:
  p=RUN/'sim'/name
  result=p.read_text()
  assert '=== ALL TESTS PASSED (err=0) ===' in result,(label,name)
  assert not re.search(r'FAIL|TIMEOUT',result),(label,name)
  shutil.copy2(p,LOG/name)
 if label=='core_suite':assert '=== CORE SUITE PASSED: T0-T9 (err=0) ===' in (LOG/'core_suite_result.txt').read_text()
 if label=='protocol':
  fault=RUN/'sim/core_g4_fault_injection_result.txt'
  assert 'injected early request must FAIL' in fault.read_text()
  assert 'EXPECTED EARLY-REQUEST FAULT DETECTED' in text
  shutil.copy2(fault,LOG/fault.name)
 row['pass']=True;results.append(row)
 (LOG/'results.json').write_text(json.dumps(results,indent=2))
if A.only in ('all','integration'):
 integ=RUN/'integration'
 for part in ('source','sim_models','tb'):shutil.copytree(ROOT/'verification/integration_received'/part,integ/part)
 for p in (RUN/'source/rtl').glob('*.v'):shutil.copy2(p,integ/'source/rtl'/p.name)
 shutil.copy2(ROOT/'sim/run_integ_g6.do',integ/'tb/run_integ_g6.do')
 text,row=invoke('integration','run_integ_g6.do',integ/'tb')
 assert all('I%d done'%i in text for i in range(8))
 assert text.count('== golden (')==9
 assert 'PASS I6 exact status: status=00080012' in text
 assert '=== ALL TESTS PASSED (err=0) ===' in text
 assert 'LOCAL_FINAL err=0 link_viol=0 pub_cnt=9' in text
 assert not re.search(r'FAIL|TIMEOUT',text)
 row['pass']=True;results.append(row)
for name,digest in manifest.items():assert sha(ROOT/name)==digest
(LOG/'results.json').write_text(json.dumps(results,indent=2))
print('=== G6 SELECTED REGRESSIONS PASSED (err=0) ===')
print('Evidence: '+str(LOG))
