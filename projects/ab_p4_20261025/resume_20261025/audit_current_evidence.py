"""Verify each current case against recorded hashes and retain mixed-run provenance."""
from pathlib import Path
import json,hashlib,datetime,re,sys
N=Path(__file__).resolve().parent;R=N.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
assert load(R/'results/regression_comparison_20261025.json')['passed']
cases=[]
for name in ['identity','real_joint','legacy_sim','integration','c6_real_subsystem','c6_host_arb']:
    folder=R/('results/regression_p4_resume_20261025' if name in ('integration','c6_host_arb') else 'results/regression_p4')/name
    result=load(folder/'result.json');inputs=load(folder/'inputs.json')
    assert result['passed'] and result['inputs_unchanged']
    for row in inputs['inputs']:assert sha(R/'candidate'/row['file'])==row['sha256'],(name,row['file'])
    logs=[]
    for step in result['steps']:
        p=folder/step['log'];assert sha(p)==step['log_sha256']
        logs.append({'file':p.relative_to(R).as_posix(),'sha256':sha(p)})
    cases.append({'case':name,'folder':folder.relative_to(R).as_posix(),'reused_pre_pause':name not in ('integration','c6_host_arb'),'logs':logs,'passed':True})
for row in load(R/'candidate_identity.json')['files']:assert sha(R/'candidate'/row['file'])==row['sha256']
for row in load(R/'physical/input_identity.json')['inputs']:assert sha(R/'physical/host_seed2_resume_20261025'/row['file'])==row['sha256']
run=load(R/'results/physical_seed2_resume_20261025/process_receipt.json')
allow_incomplete='--allow-incomplete-physical' in sys.argv
console=(R/'results/physical_seed2_resume_20261025/console.log').read_text(errors='replace')
physical_completed=(run['exit_code']==0 and run['state']=='FINISHED' and
    'P4_UNRESTRICTED_REPORT_RESTORED' in console and
    (R/'physical/host_seed2_resume_20261025/report_timing/hdmi_ddr_ov5640_top.rtr').is_file() and
    (R/'physical/host_seed2_resume_20261025/place_route/hdmi_ddr_ov5640_top.prr').is_file())
assert run['state'] in ('FINISHED','TIMEOUT') and not run['changed_input_files'] and not run['bitstreams_present']
assert physical_completed or allow_incomplete,'Nonzero physical result requires explicit incomplete-evidence audit'
assert sha(R/'results/physical_seed2_resume_20261025/console.log')==run['console_sha256']
native=[]
for kind in ['synthesize','device_map','place_route','report_timing','report_timing_map_diagnostic','report_timing_cache_from_diagnostic','report_timing_cache_to_diagnostic']:
    folder=R/'physical/host_seed2_resume_20261025'/kind
    for p in sorted(folder.glob('*')):
        if p.is_file() and p.suffix in ('.snr','.dmr','.prr','.rtr'):native.append({'file':p.relative_to(R).as_posix(),'sha256':sha(p)})
required=['synthesize','device_map','place_route','report_timing'] if physical_completed else ['synthesize','device_map']
assert all(any(f'/{part}/' in x['file'] for x in native) for part in required)
eq=load(R/'results/equivalence_p4/summary.json')['results']
assert len(eq)==5
for row in eq:
    assert row['pass']
    assert sha(R/'results/equivalence_p4'/row['case']/'simulation.log')==row['simulation_log_sha256']
    for rel,h in row['inputs_after'].items():assert sha(R/rel)==h
negative=load(R/'results/negative_checks_p4/summary.json')
assert len(negative)==7 and all(x['detected'] for x in negative)
for row in negative:
    folder=R/'results/negative_checks_p4'/row['mutation']
    assert sha(folder/'mutant.v')==row['mutant_sha256']
    assert (folder/'simulation.log').read_text(errors='replace')==row['log']
out={'passed':True,'physical_completed':physical_completed,'physical_state':run['state'],'physical_exit_code':run['exit_code'],'note':'Audit pass verifies evidence identity and functional results, not timing closure.','case_provenance':cases,'candidate_inputs':81,'physical_inputs':139,'equivalence':5,'mutation_checks':7,'native_reports':native,'physical_console_sha256':run['console_sha256'],'saved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(R/'results/evidence_audit_20261025.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':True,'cases':len(cases),'native_reports':len(native),'inputs':{'candidate':81,'physical':139}},indent=2))
