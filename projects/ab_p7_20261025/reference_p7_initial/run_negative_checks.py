"""P7 faults must be detected by an otherwise passing all-slot equivalence TB."""
from pathlib import Path
import subprocess,json,hashlib,datetime
R=Path(__file__).resolve().parent
src=(R/'candidate/source/rtl/undistort_cache_ab.v').read_text(encoding='utf-8')
assert all(x['pass'] for x in json.loads((R/'results/equivalence_p7/summary.json').read_text())['results'])
assert all(x['pass'] for x in json.loads((R/'results/banks_p7/summary.json').read_text())['results'])
faults={
 'stale_row_equality':('lookup_same_row<=qa==qb;','lookup_same_row<=0;'),
 'stale_segment_equality':('lookup_same_seg<=qs0==qs1;','lookup_same_seg<=0;'),
 'missing_mark':("done_mask[sel]<=1'b1;","if(qwhich!=3)done_mask[sel]<=1'b1;"),
 'stale_mask':('Q_SELECT:begin\n                        done_mask<=0;','Q_SELECT:begin'),
 'old_qid':("done_mask[sel]<=1'b1;","done_mask[qid[qwhich]]<=1'b1;"),
 'touch_priority':('(qstate==Q_DONE && done_mask[lu]))last_use[lu]<=qseq;',
                    '(qstate==Q_DONE && done_mask[lu]))last_use[lu]<=i_touch?i_touch_seq:qseq;'),
 'mask_protection':('if(qfound[k] && qid[k]==idx)protected_id=1;','if(done_mask[idx])protected_id=1;'),
 'wrong_write_bank':('chosen[7:4]==tag_g','chosen[7:4]==((tag_g+1)%12)'),
 'wrong_write_slot':('tags[chosen[3:0]]<=','tags[chosen[3:0]^1]<= '),
 'wrong_row_bit':('tags[chosen[3:0]]<={missing_row,missing_seg};',"tags[chosen[3:0]]<={missing_row^11'd2,missing_seg};"),
 'wrong_segment_bit':('tags[chosen[3:0]]<={missing_row,missing_seg};',"tags[chosen[3:0]]<={missing_row,missing_seg^5'd1};"),
 'wrong_fetch_bank':('bank_fetch[o_fetch_bank[7:4]][15:5]','bank_fetch[0][15:5]'),
 'wrong_fetch_slot':('tags[o_fetch_bank[3:0]]','tags[o_fetch_bank[3:0]^1]'),
 'wrong_read_parity':('tags[2*slot_idx+row_key[0]]==','tags[2*slot_idx+(row_key[0]^1)]=='),
 'lowest_local_priority':('for(slot_idx=0;slot_idx<8;slot_idx=slot_idx+1)',
                         'for(slot_idx=7;slot_idx>=0;slot_idx=slot_idx-1)'),
 'missing_tag_valid':('if(tag_valid[16*tag_g+2*slot_idx+row_key[0]] &&','if(1\'b1 &&'),
 'retirement_equal_allowed':('last_use[idx]<i_retired_count','last_use[idx]<=i_retired_count'),
 'wrong_tie_priority':('else older=(a[29:8]<b[29:8])?a:b;','else older=(a[29:8]<=b[29:8])?a:b;')}
out=R/'results/negative_checks_p7';out.mkdir(parents=True,exist_ok=False)
toolroot=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app')
drive=next(c+':' for c in 'YXWVUTSRQP' if not Path(c+':/').exists())
subprocess.run(['subst',drive,str(toolroot)],check=True);tool=Path(drive+'/')
results=[]
try:
    for name,(original,fault) in faults.items():
        assert src.count(original)==1,(name,src.count(original))
        d=out/name;d.mkdir();v=d/'mutant.v';v.write_text(src.replace(original,fault),encoding='utf-8')
        cmd=[str(tool/'bin/iverilog.exe'),'-B',str(tool/'lib/ivl'),'-g2012','-s','cache_p7_banks_tb',
             '-o',str(d/'sim.vvp'),str(R/'tests/cache_p7_banks_tb.sv'),str(v),str(R/'baseline/undistort_cache_ab_reference.v')]
        with (d/'compile.log').open('wb') as log:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=90).returncode
        assert rc==0,name
        with (d/'simulation.log').open('wb') as log:
            run=subprocess.run([str(tool/'bin/vvp.exe'),str(d/'sim.vvp')],stdout=log,stderr=subprocess.STDOUT,timeout=90)
        text=(d/'simulation.log').read_text(errors='replace')
        detected=run.returncode!=0 and 'FATAL' in text and 'watchdog' not in text and 'P7_BANKS_EQUIVALENCE PASS' not in text
        results.append(dict(mutation=name,compile_exit=rc,simulation_exit=run.returncode,detected=detected,
                            mutant_sha256=hashlib.sha256(v.read_bytes()).hexdigest(),log=text,argv=cmd))
        print(name,detected,text[:130],flush=True)
finally:
    subprocess.run(['subst',drive,'/D'],check=True)
    (out/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
assert len(results)==18 and all(x['detected'] for x in results)
