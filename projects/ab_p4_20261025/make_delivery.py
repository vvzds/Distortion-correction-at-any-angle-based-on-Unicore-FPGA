"""Package this isolated task after evidence and report completion; no upload."""
from pathlib import Path
import hashlib,json,zipfile,datetime
R=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
receipt=json.loads((R/'results/physical_seed2/process_receipt.json').read_text(encoding='utf-8'))
assert receipt['state'] in ('FINISHED','TIMEOUT')
assert json.loads((R/'results/regression_comparison.json').read_text(encoding='utf-8'))['passed']
assert (R/'审查结果与回传说明.md').is_file()
files=[p for p in R.rglob('*') if p.is_file() and p.suffix!='.vvp' and '__pycache__' not in p.parts and p.name!='DELIVERY_MANIFEST.json']
manifest=[{'file':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)]
m=R/'DELIVERY_MANIFEST.json';m.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
files.append(m)
out=R.parent/'待转交';out.mkdir(exist_ok=True)
z=out/'AB_P4缓存优化_源码与验证_20261024.zip'
assert not z.exists(),'Do not overwrite an existing delivery'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as f:
 for p in sorted(files):f.write(p,R.name+'/'+p.relative_to(R).as_posix())
with zipfile.ZipFile(z) as f:
 assert f.testzip() is None
 for row in manifest:
  assert hashlib.sha256(f.read(R.name+'/'+row['file'])).hexdigest()==row['sha256'],row['file']
result={'archive':str(z),'bytes':z.stat().st_size,'sha256':sha(z),'file_count':len(files),'verified_manifest_entries':len(manifest),'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'excluded':'Only regenerated .vvp executables and Python caches','sent_or_uploaded':False}
(out/'AB_P4交付包校验回执_20261024.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
