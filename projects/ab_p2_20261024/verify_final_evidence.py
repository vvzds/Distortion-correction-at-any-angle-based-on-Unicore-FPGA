from pathlib import Path
import hashlib,json,csv,datetime
R=Path(__file__).resolve().parent
def load(p):return json.loads((R/p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
run=load('results/physical_seed2/process_receipt.json')
assert run['state']=='FINISHED' and run['exit_code']==0
assert not run['changed_input_files'] and not run['bitstreams_present']
assert sha(R/'results/physical_seed2/console.log')==run['console_sha256']
counts={}
for root,path,key in [('candidate','candidate_identity.json','files'),('physical/host_seed2','physical/input_identity.json','inputs')]:
    d=load(path);assert d['changed_files']==['source/rtl/undistort_cache_ab.v']
    for x in d[key]:assert sha(R/root/x['file'])==x['sha256'],x['file']
    counts[root]=len(d[key])
comparison=load('results/physical_comparison.json')
for root,d in [('baseline/physical',comparison['baseline']),('physical/host_seed2',comparison['candidate']),('prior_p1/physical',load('prior_p1/physical_comparison.json')['candidate'])]:
    for x in d['native_reports'].values():assert sha(R/root/x['path'])==x['sha256'],x['path']
csv_path=R/'physical/host_seed2/multiseed_summary.csv'
rows=list(csv.reader(csv_path.read_text(encoding='utf-8').splitlines()))
header=next(x for x in rows if x and x[0]=='Seed')
values=next(x for x in rows if x and x[0]=='single')
c=dict(zip(header,values))
for t in comparison['candidate']['timing_summary']:
    assert float(c[f'{t["kind"]}({t["corner"]})'])==t['worst_slack_ns']
slow=next(t for t in comparison['candidate']['timing_summary'] if t['kind']=='Setup' and t['corner']=='Slow')
assert float(c['Setup(Slow) Total Failing TNS'])==sum(x['total_slack_ns'] for x in slow['rows'])
assert int(c['Setup(Slow) Total Failing Endpoints'])==sum(x['failing_endpoints'] for x in slow['rows'])
assert c['State']=='OK' and c['Convergence']=='Fail'
assert not list((R/'physical/host_seed2').rglob('*.sbit'))
out={'verification_passed':True,'candidate_promoted':False,'timing_passed':False,'input_files_verified':counts,'native_report_sha_verified':12,'csv_matches_final_report':True,'csv_state':c['State'],'csv_convergence':c['Convergence'],'csv_sha256':sha(csv_path),'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(R/'results/final_evidence_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
