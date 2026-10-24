"""Inject faults into isolated copies; verify the receiving probe rejects them."""
from pathlib import Path
import argparse, hashlib, json, subprocess, sys

ROOT=Path(__file__).resolve().parent

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--map',type=Path,required=True)
    p.add_argument('--tool-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
    before=sha(a.map);source=a.map.read_text(encoding='utf-8')
    changes=[('valid_one_edge_early','o_valid<=valid_pipe[10];','o_valid<=valid_pipe[9];','VALID_LATENCY'),
             ('identity_pixel_corrupt',"o_sx_q16<={u8,16'd0};","o_sx_q16<={u8,16'd0} ^ 27'd1;",'IDENTITY_COORD'),
             ('output_width_narrow','output reg  [26:0] o_sx_q16,o_sy_q16','output reg  [25:0] o_sx_q16,o_sy_q16','PORT_WIDTH_WARNING')]
    rows=[]
    for name,old,new,reason in changes:
        if source.count(old)!=1:raise RuntimeError('mutation anchor missing or duplicated')
        file=a.out/(name+'.v');file.write_text(source.replace(old,new),encoding='utf-8')
        out=a.out/name
        cmd=[sys.executable,'-B','-X','utf8',str(ROOT/'run_map_probe.py'),'--map',str(file),
             '--tool-root',str(a.tool_root.resolve()),'--out',str(out)]
        proc=subprocess.run(cmd,capture_output=True,timeout=60)
        (a.out/(name+'_runner.log')).write_bytes(proc.stdout+proc.stderr)
        r=json.loads((out/'result.json').read_text(encoding='utf-8'))
        log=(out/'simulation.log').read_text(encoding='utf-8',errors='replace') if (out/'simulation.log').exists() else ''
        expected=(r['port_width_warning'] if reason=='PORT_WIDTH_WARNING' else reason in log)
        ok=proc.returncode!=0 and r['status']=='FAIL' and expected
        rows.append(dict(case=name,expected_rejection=reason,exit_code=proc.returncode,
                         status='EXPECTED_REJECTION_PASS' if ok else 'FAIL',source_sha256=sha(file),
                         actual_result=r['status'],port_width_warning=r['port_width_warning'],command=cmd))
    unchanged=sha(a.map)==before
    result=dict(status='PASS' if unchanged and all(x['status']=='EXPECTED_REJECTION_PASS' for x in rows) else 'FAIL',
                baseline_file=str(a.map.resolve()),baseline_sha256=before,baseline_unchanged=unchanged,cases=rows,
                scope='TESTBENCH_NEGATIVE_SELF_CHECK_ONLY_MUTATED_COPIES_NOT_NEW_RTL_CANDIDATES')
    (a.out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':sys.exit(main())
