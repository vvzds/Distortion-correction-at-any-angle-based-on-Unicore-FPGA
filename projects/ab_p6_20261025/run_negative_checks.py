"""Prove that unchanged cycle/state checks detect P6 local age and victim faults."""
from pathlib import Path
import subprocess, json, hashlib
R = Path(__file__).resolve().parent
src = (R/'candidate/source/rtl/undistort_cache_ab.v').read_text(encoding='utf-8')
faults = {'stale_row_equality': ('lookup_same_row<=qa==qb;', 'lookup_same_row<=0;'), 'stale_segment_equality': ('lookup_same_seg<=qs0==qs1;', 'lookup_same_seg<=0;'), 'wrong_group': ('i_alloc_id[7:4]==GROUP', 'i_alloc_id[7:4]==((GROUP+1)%12)'), 'wrong_parity': ('local_idx=2*j+i_parity;', "local_idx=2*j+(i_parity^1'b1);"), 'wrong_local_slot': ('age[s]<=i_seq;', 'age[s^1]<=i_seq;'), 'missing_mark': ("else if(bank_mark)mask[i_mark_id[3:0]]<=1'b1;", 'else if(bank_mark)begin end'), 'stale_mask': ('else if(i_select)mask<=0;', 'else if(i_select)begin end'), 'touch_priority': ('age[s]<=i_seq;', 'age[s]<=i_touch?i_touch_seq:i_seq;'), 'mask_protection': ('if(i_qfound[k] && i_qids[k*8+:8]==gid)protected_id=1;', 'if(mask[local_idx])protected_id=1;'), 'retirement_equal_allowed': ('age[local_idx]<i_retired_count', 'age[local_idx]<=i_retired_count'), 'wrong_tie_priority': ('else local_older=(a[29:8]<b[29:8])?a:b;', 'else local_older=(a[29:8]<=b[29:8])?a:b;')}

assert all(x['pass'] for x in json.loads((R/'results/equivalence_p6/summary.json').read_text())['results']), 'Positive reference must pass before accepting mutation failures'
out=R/'results/negative_checks_p6';out.mkdir(parents=True,exist_ok=False)
toolroot=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app')
drive=next(c+':' for c in 'YXWVUTSRQP' if not Path(c+':/').exists())
subprocess.run(['subst',drive,str(toolroot)],check=True);tool=Path(drive+'/')
results=[]
try:
    for name,(original,fault) in faults.items():
        assert src.count(original)==1, (name,src.count(original))
        d=out/name;d.mkdir();v=d/'mutant.v'
        v.write_text(src.replace(original,fault),encoding='utf-8')
        cmd=[str(tool/'bin/iverilog.exe'),'-B',str(tool/'lib/ivl'),'-g2012','-s','cache_p6_equivalence_tb','-o',str(d/'sim.vvp'),str(R/'tests/cache_p6_equivalence_tb.sv'),str(v),str(R/'baseline/undistort_cache_ab_reference.v')]
        with (d/'compile.log').open('wb') as log:
            rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=90).returncode
        assert rc==0,name
        with (d/'simulation.log').open('wb') as log:
            run=subprocess.run([str(tool/'bin/vvp.exe'),str(d/'sim.vvp')],stdout=log,stderr=subprocess.STDOUT,timeout=90)
        body=(d/'simulation.log').read_text(errors='replace')
        detected=run.returncode!=0 and 'FATAL' in body and 'watchdog' not in body and 'P6_EQUIVALENCE PASS' not in body
        results.append(dict(mutation=name,compile_exit=rc,simulation_exit=run.returncode,detected=detected,mutant_sha256=hashlib.sha256(v.read_bytes()).hexdigest(),log=body,argv=cmd))
        print(name,detected,body[:180],flush=True)
finally:
    subprocess.run(['subst',drive,'/D'],check=True)
    (out/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
assert len(results)==len(faults) and all(x['detected'] for x in results)
