"""Create an immutable local ZIP only after final evidence audit."""
from pathlib import Path
import json,hashlib,zipfile,datetime
R=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert json.loads((R/'results/evidence_audit.json').read_text())['passed']
run=json.loads((R/'results/synthesis_gate/process_receipt.json').read_text())
assert run['state'] not in ('RUNNING','STARTING')
assert not run['changed_input_files'] and not run['bitstreams_present']
assert (R/'审查结果与回传说明.md').is_file()
out=R.parent/'待转交';out.mkdir(exist_ok=True)
z=out/'AB_P6标签RAM局部替换_源码与筛选证据_20261025.zip';assert not z.exists()
m=R/'DELIVERY_MANIFEST.json';assert not m.exists()
files=sorted(p for p in R.rglob('*') if p.is_file() and p.suffix not in ('.vvp','.pyc') and '__pycache__' not in p.parts
             and not (p.parent==R/'docs' and p.name.endswith('_User_Guide.txt')))
assert not any(any(x in p.relative_to(R).parts for x in ('.git','.local','github-cli-auth')) for p in files)
manifest=[dict(file=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
m.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');files.append(m)
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as f:
    for p in sorted(files):f.write(p,R.name+'/'+p.relative_to(R).as_posix())
with zipfile.ZipFile(z) as f:
    assert f.testzip() is None
    for row in manifest:assert hashlib.sha256(f.read(R.name+'/'+row['file'])).hexdigest()==row['sha256'],row['file']
receipt=dict(archive=str(z),bytes=z.stat().st_size,sha256=sha(z),file_count=len(files),verified_manifest_entries=len(manifest),
    verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    excluded='Regenerable VVP executables, Python caches and local full vendor manual text extracts; all design inputs and generated evidence retained')
(out/'AB_P6交付包校验回执_20261025.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
