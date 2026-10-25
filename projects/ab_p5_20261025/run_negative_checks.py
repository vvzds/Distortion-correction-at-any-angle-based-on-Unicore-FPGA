"""Prove that unchanged cycle/state checks detect P5 metadata faults."""
from pathlib import Path
import subprocess, json, hashlib
R = Path(__file__).resolve().parent
src = (R/'candidate/source/rtl/undistort_cache_ab.v').read_text(encoding='utf-8')
faults = {
    'stale_row_equality': ('lookup_same_row<=qa==qb;', 'lookup_same_row<=0;'),
    'stale_segment_equality': ('lookup_same_seg<=qs0==qs1;', 'lookup_same_seg<=0;'),
    'wrong_group': ('i_alloc_id[7:4]==GROUP', 'i_alloc_id[7:4]==((GROUP+1)%12)'),
    'wrong_parity': ('i_alloc_id[0]==PARITY', 'i_alloc_id[0]!=PARITY'),
    'wrong_local_slot': ('row[i_alloc_id[3:1]]<=i_alloc_row;', "row[i_alloc_id[3:1]^3'd1]<=i_alloc_row;"),
    'missing_mark': ("else if(bank_mark)mask[i_mark_id[3:1]]<=1'b1;", "else if(bank_mark)begin end"),
    'stale_mask': ('if(i_lookup_clear)mask<=0;', 'if(i_lookup_clear)begin end'),
    'touch_priority': ('age[j]<=i_lookup_seq;', 'age[j]<=i_touch?i_touch_seq:i_lookup_seq;'),
    'mask_protection': ('if(qfound[k] && qid[k]==idx)protected_id=1;', 'if(done_mask[idx])protected_id=1;'),
}
out=R/'results/negative_checks_p5';out.mkdir(parents=True,exist_ok=False)
toolroot=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app')
drive=next(c+':' for c in 'YXWVUTSRQP' if not Path(c+':/').exists())
subprocess.run(['subst',drive,str(toolroot)],check=True);tool=Path(drive+'/')
results=[]
try:
    for name,(original,fault) in faults.items():
        assert src.count(original)==1, (name,src.count(original))
        d=out/name;d.mkdir();v=d/'mutant.v'
        v.write_text(src.replace(original,fault),encoding='utf-8')
        cmd=[str(tool/'bin/iverilog.exe'),'-B',str(tool/'lib/ivl'),'-g2012','-s','cache_p5_equivalence_tb','-o',str(d/'sim.vvp'),str(R/'tests/cache_p5_equivalence_tb.sv'),str(v),str(R/'baseline/undistort_cache_ab_reference.v')]
        with (d/'compile.log').open('wb') as log:
            rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=90).returncode
        assert rc==0,name
        with (d/'simulation.log').open('wb') as log:
            run=subprocess.run([str(tool/'bin/vvp.exe'),str(d/'sim.vvp')],stdout=log,stderr=subprocess.STDOUT,timeout=90)
        body=(d/'simulation.log').read_text(errors='replace')
        detected=run.returncode!=0 and 'FATAL' in body and 'watchdog' not in body and 'P5_EQUIVALENCE PASS' not in body
        results.append(dict(mutation=name,compile_exit=rc,simulation_exit=run.returncode,detected=detected,mutant_sha256=hashlib.sha256(v.read_bytes()).hexdigest(),log=body,argv=cmd))
        print(name,detected,body[:180],flush=True)
finally:
    subprocess.run(['subst',drive,'/D'],check=True)
    (out/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
assert len(results)==len(faults) and all(x['detected'] for x in results)
