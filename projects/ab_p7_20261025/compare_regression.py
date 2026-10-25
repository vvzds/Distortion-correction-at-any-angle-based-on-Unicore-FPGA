"""Compare frozen input hashes, plusargs, complete normalized logs and counters."""
from pathlib import Path
import json,re,hashlib
R=Path(__file__).resolve().parent
cases=['identity','real_joint','legacy_sim','integration','c6_real_subsystem','c6_host_arb']
old='4fc449dc3bf1e34711c774057c4d92559ebd545e5f88facac27cac5da33a6a60'
new='b2042db9c8d40dafb4c277104d909a76caca140d57e2c549bf1d7665324678c3'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def normalized(p):
    # Icarus prints an absolute source path for $finish. Strip only that path;
    # retain source line number, simulation finish time, and all other lines.
    # Windows Icarus emits the absolute Chinese path in a local code page.
    # Compare raw bytes so encoding replacement cannot hide a real difference.
    return [re.sub(rb'^.*?([^/\\]+\.v:\d+: \$finish called at)',rb'\1',s.strip())
            for s in p.read_bytes().splitlines() if s.strip()]
rows=[]
for case in cases:
    b=R/'baseline/evidence'/case;c=R/'results/regression_p7'/case
    br=read(b/'result.json');cr=read(c/'result.json')
    bi={x['file']:x['sha256'] for x in read(b/'inputs.json')['inputs']}
    ci={x['file']:x['sha256'] for x in read(c/'inputs.json')['inputs']}
    diffs=[{'file':f,'baseline':bi.get(f),'candidate':ci.get(f)} for f in sorted(bi.keys()|ci.keys()) if bi.get(f)!=ci.get(f)]
    allowed=diffs==[{'file':'source/rtl/undistort_cache_ab.v','baseline':old,'candidate':new}]
    ba=[a for s in br['steps'] for a in s['command'] if a.startswith('+')]
    ca=[a for s in cr['steps'] for a in s['command'] if a.startswith('+')]
    bl=normalized(b/'simulation.log');cl=normalized(c/'simulation.log')
    row={'case':case,'baseline_passed':br['passed'],'candidate_passed':cr['passed'],
         'only_expected_cache_changed':allowed,'input_differences':diffs,
         'plusargs_equal':ba==ca,'plusargs':ca,'normalized_complete_log_equal':bl==cl,
         'candidate_inputs_unchanged':cr['inputs_unchanged'],
         'baseline_summary':br['summary_lines'],'candidate_summary':cr['summary_lines']}
    row['passed']=all(row[k] for k in ['baseline_passed','candidate_passed','only_expected_cache_changed','plusargs_equal','normalized_complete_log_equal','candidate_inputs_unchanged'])
    rows.append(row)
out={'purpose':'Cycle and behavior regression against frozen original AB; not formal proof or physical/board fps evidence', 'passed':all(x['passed'] for x in rows),'results':rows}
(R/'results/regression_comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
raise SystemExit(0 if out['passed'] else 1)
