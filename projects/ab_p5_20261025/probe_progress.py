from pathlib import Path
import json,re,datetime
R=Path(__file__).resolve().parent
def read(p):return p.read_text(encoding='utf-8',errors='replace') if p.exists() else ''
P=R/'results/physical_seed2';body=read(P/'console.log')
receipt=json.loads(read(P/'process_receipt.json') or '{}')
result={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'physical':{k:receipt.get(k) for k in ('state','pid','elapsed_s','last_route','exit_code')},
        'last_physical_lines':body.splitlines()[-3:],
        'timestamp_feedback_warnings':sum('Feedback mux' in s and ('last_use' in s or "signal 'age[" in s) for s in body.splitlines()),
        'error_lines':[s for s in body.splitlines() if s.startswith('E:')],
        'regression':[]}
for name in ('identity','real_joint','legacy_sim','integration','c6_real_subsystem','c6_host_arb'):
    d=R/'results/regression_p5'/name
    if not d.exists():row={'case':name,'state':'QUEUED'}
    elif (d/'result.json').exists():
        r=json.loads(read(d/'result.json'));row={'case':name,'state':'PASS' if r['passed'] else 'FAIL','summary':r['summary_lines']}
    else:row={'case':name,'state':'RUNNING','last_lines':read(d/'simulation.log').splitlines()[-2:]}
    result['regression'].append(row)
snr=R/'physical/host_seed2/synthesize/hdmi_ddr_ov5640_top.snr'
if snr.exists():
    lines=read(snr).splitlines()
    result['synthesis_cache_rows']=[s for s in lines if '+ u_cache ' in s]
    result['synthesis_bank_instances']=sum('meta_group' in s for s in lines)
(R/'results/progress_latest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
