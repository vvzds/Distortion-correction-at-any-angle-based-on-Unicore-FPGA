from pathlib import Path
import json,hashlib,zipfile,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from hash_inventory import native
BASE=Path('C:/Users/叶翔/Documents/Codex/fpga-main/deliverables/20261024/collab2_local_archive')
root=Path('C:/Users/叶翔/Documents/Codex/a1024m01/M01')
items=[]
with zipfile.ZipFile(BASE/'supplemental_M01_sources.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in root.rglob('*'):
        if not p.is_file() or any(x in {'.git','__pycache__','.venv','node_modules'} for x in p.parts):continue
        rel=p.relative_to(root).as_posix();raw=Path(native(p)).read_bytes()
        z.writestr(rel,raw)
        items.append({'source':str(p),'zip_entry':rel,'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
with zipfile.ZipFile(BASE/'supplemental_M01_sources.zip') as z:
    for item in items:assert hashlib.sha256(z.read(item['zip_entry'])).hexdigest()==item['sha256']
source=Path('C:/Users/叶翔/Documents/Codex/2026-09-17/wo/work/build_dewarp_report.py')
if source.exists():
    dest=BASE/'standalone_project_files/build_dewarp_report.py';dest.parent.mkdir(exist_ok=True)
    dest.write_bytes(source.read_bytes())
    items.append({'source':str(source),'path':dest.relative_to(BASE).as_posix(),'size':source.stat().st_size,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
(BASE/'SUPPLEMENTAL_FILES.json').write_text(json.dumps({'state':'PASS','files':items,'note':'M01 full source tree supplements keyword-only inventory; matching archive payloads may already appear under other original paths. ZIP members individually verified.'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'supplemental_files':len(items),'m01_zip_size':(BASE/'supplemental_M01_sources.zip').stat().st_size}))
