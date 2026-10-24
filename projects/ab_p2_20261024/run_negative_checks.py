from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parent
src=(R/'candidate/source/rtl/undistort_cache_ab.v').read_text(encoding='utf-8')
mutations={
 'omit_fourth_hit':src.replace('assign selected_hit_mask[ps]=|key_selected;','assign selected_hit_mask[ps]=|key_selected[2:0];'),
 'ignore_group_priority':src.replace("((match_hit[pk] >> (pg+1))==12'd0)","1'b1"),
 'omit_allocated_id':src.replace("                            done_mask[chosen]<=1'b1;",''),
 'stale_initial_mask':src.replace('done_mask<=selected_hit_mask;','done_mask<=done_mask | selected_hit_mask;'),
 'touch_priority':src.replace('(qstate==Q_DONE && done_mask[lu]))last_use[lu]<=qseq;','(qstate==Q_DONE && done_mask[lu]))last_use[lu]<=i_touch?i_touch_seq:qseq;')}

out=R/'results/negative_checks_p2';out.mkdir(parents=True,exist_ok=False)
toolroot=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app')
drive=next(c+':' for c in 'YXWVUTSRQP' if not Path(c+':/').exists())
subprocess.run(['subst',drive,str(toolroot)],check=True);tool=Path(drive+'/')
results=[]
try:
 for name,body in mutations.items():
  assert body!=src,name
  d=out/name;d.mkdir();v=d/'mutant.v';v.write_text(body,encoding='utf-8')
  cmd=[str(tool/'bin/iverilog.exe'),'-B',str(tool/'lib/ivl'),'-g2012','-s','cache_p2_equivalence_tb','-o',str(d/'sim.vvp'),str(R/'tests/cache_p2_equivalence_tb.sv'),str(v),str(R/'baseline/undistort_cache_ab_reference.v')]
  with (d/'compile.log').open('wb') as log:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=90).returncode
  assert rc==0,name
  with (d/'simulation.log').open('wb') as log:run=subprocess.run([str(tool/'bin/vvp.exe'),str(d/'sim.vvp')],stdout=log,stderr=subprocess.STDOUT,timeout=90)
  text=(d/'simulation.log').read_text(errors='replace')
  detected=run.returncode!=0 and 'FATAL' in text and 'watchdog' not in text and 'P2_EQUIVALENCE PASS' not in text
  results.append({'mutation':name,'compile_exit':rc,'simulation_exit':run.returncode,'detected':detected,'mutant_sha256':hashlib.sha256(v.read_bytes()).hexdigest(),'log':text})
  print(name,detected,text[:180],flush=True)
finally:subprocess.run(['subst',drive,'/D'],check=True)
(out/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
assert all(x['detected'] for x in results)
