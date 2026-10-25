from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parent
src=(R/'candidate/source/rtl/undistort_cache_ab.v').read_text(encoding='utf-8')
mutations={
 'stale_row_equality':src.replace('lookup_same_row<=qa==qb;','lookup_same_row<=0;'),
 'stale_segment_equality':src.replace('lookup_same_seg<=qs0==qs1;','lookup_same_seg<=0;'),
 'missing_last_id':src.replace("done_mask[sel]<=1'b1;","if(qwhich!=3)done_mask[sel]<=1'b1;").replace("done_mask[chosen]<=1'b1;","if(qwhich!=3)done_mask[chosen]<=1'b1;"),
 'stale_mask':src.replace('                    Q_SELECT:begin\n                        done_mask<=0;','                    Q_SELECT:begin'),
 'old_qid':src.replace("done_mask[sel]<=1'b1;","done_mask[qid[qwhich]]<=1'b1;"),
 'touch_priority':src.replace('(qstate==Q_DONE && done_mask[lu]))last_use[lu]<=qseq;','(qstate==Q_DONE && done_mask[lu]))last_use[lu]<=i_touch?i_touch_seq:qseq;'),
 'mask_protection':src.replace('if(qfound[k] && qid[k]==idx)protected_id=1;','if(done_mask[idx])protected_id=1;')}
out=R/'results/negative_checks_p4';out.mkdir(parents=True,exist_ok=False)
toolroot=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app')
drive=next(c+':' for c in 'YXWVUTSRQP' if not Path(c+':/').exists())
subprocess.run(['subst',drive,str(toolroot)],check=True);tool=Path(drive+'/')
results=[]
try:
 for name,body in mutations.items():
  assert body!=src,name
  d=out/name;d.mkdir();v=d/'mutant.v';v.write_text(body,encoding='utf-8')
  cmd=[str(tool/'bin/iverilog.exe'),'-B',str(tool/'lib/ivl'),'-g2012','-s','cache_p4_equivalence_tb','-o',str(d/'sim.vvp'),str(R/'tests/cache_p4_equivalence_tb.sv'),str(v),str(R/'baseline/undistort_cache_ab_reference.v')]
  with (d/'compile.log').open('wb') as log:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=90).returncode
  assert rc==0,name
  with (d/'simulation.log').open('wb') as log:run=subprocess.run([str(tool/'bin/vvp.exe'),str(d/'sim.vvp')],stdout=log,stderr=subprocess.STDOUT,timeout=90)
  text=(d/'simulation.log').read_text(errors='replace')
  detected=run.returncode!=0 and 'FATAL' in text and 'watchdog' not in text and 'P4_EQUIVALENCE PASS' not in text
  results.append({'mutation':name,'compile_exit':rc,'simulation_exit':run.returncode,'detected':detected,'mutant_sha256':hashlib.sha256(v.read_bytes()).hexdigest(),'log':text})
  print(name,detected,text[:180],flush=True)
finally:subprocess.run(['subst',drive,'/D'],check=True)
(out/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
assert all(x['detected'] for x in results)
