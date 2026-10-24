"""Check delivered byte integrity and recovered project compile state."""
from pathlib import Path
import ast
import hashlib
import json
import zipfile

ROOT=Path('C:/Users/叶翔/Documents/Codex/fpga-main/deliverables/20261024/collab2_PDS_top_recovery')
hashes=json.loads((ROOT/'SHA256SUMS.json').read_text(encoding='utf-8'))
for name,h in hashes.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
for p in (ROOT/'tools').glob('*.py'):
    ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
frozen=json.loads((ROOT/'preflight.json').read_text(encoding='utf-8'))['input_hashes']
verified=json.loads((ROOT/'FINAL_VERIFICATION.json').read_text(encoding='utf-8'))
assert verified['state']=='PASS_COMPILE_ONLY'
with zipfile.ZipFile(ROOT/'PDS_top_recovery.zip') as z:
    assert z.testzip() is None
    n=0
    for name,h in frozen.items():
        if name.startswith(('source/','ipcore/')) or name.endswith('.fdc'):
            assert hashlib.sha256(z.read(name)).hexdigest()==h,name
            n+=1
    assert hashlib.sha256(z.read('full_source_top_recovered.pds')).hexdigest()==verified['recovered_project_sha256']
    assert hashlib.sha256(z.read('compile/hdmi_ddr_ov5640_top_comp.adf')).hexdigest()==verified['compile_database_sha256']
    assert verified['native_run']['state']=='PASS' and not verified['native_run']['errors']
print(json.dumps(dict(state='PASS',delivery_files=len(hashes),frozen_package_inputs=n,
    compile_elapsed_s=verified['native_run']['elapsed_s'],native_errors=0)))
