from pathlib import Path
import hashlib,json,zipfile,datetime
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for r in json.loads((ROOT/'evidence/source_identity.json').read_text(encoding='utf-8')):
    if sha(Path(r['source']))!=r['sha256'] or sha(ROOT/r['package_path'])!=r['sha256']:
        raise ValueError('Reference/source modified: '+r['source'])
facts=json.loads((ROOT/'evidence/design_facts.json').read_text(encoding='utf-8'))
if facts['baseline_core_sha256']!='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68':raise ValueError('wrong core')
if abs(facts['route_sum_ns']-9.081)>1e-9:raise ValueError('route arithmetic mismatch')
tests=json.loads((ROOT/'evidence/existing_test_entry_index.json').read_text(encoding='utf-8'))
if not all(r['exists'] for r in tests):raise ValueError('referenced test missing')
records=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name!='files_sha256.json']
(ROOT/'files_sha256.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
target=ROOT.parent/'待转交/给设计方及二号_AB缓存时序改进方案_20261024.zip'
target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(ROOT.rglob('*')):
        if p.is_file():z.write(p,'AB_cache_timing_plan_20261024/'+p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(target) as z:
    if z.testzip() is not None:raise ValueError('CRC')
    for r in records:
        b=z.read('AB_cache_timing_plan_20261024/'+r['path'])
        if len(b)!=r['bytes'] or hashlib.sha256(b).hexdigest()!=r['sha256']:raise ValueError('member mismatch')
    if len(z.infolist())!=len(records)+1:raise ValueError('member coverage')
digest=sha(target)
target.with_suffix('.zip.sha256').write_text(digest+'  '+target.name+'\n',encoding='utf-8')
receipt={'created':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'zip':str(target),'sha256':digest,'bytes':target.stat().st_size,'manifest_files':len(records),'source_files_unchanged':True,'crc':'PASS','zip_members_sha256':'PASS','candidate_RTL_created':False,'RTL_or_PDS_run':False,'status':'DESIGN_PROPOSAL_ONLY'}
(ROOT.parent/'AB缓存时序改进方案_20261024_打包核对.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
