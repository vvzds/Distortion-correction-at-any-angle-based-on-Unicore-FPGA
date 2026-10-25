from pathlib import Path
import json,hashlib,difflib,shutil
W=Path(r'C:\Users\lenovo\Desktop\ww');B=W/'AB_P7R1标签RAM与共享比较_20261025';R=W/'AB_P8触摸译码局部化_20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=json.loads((R/'candidate_identity.json').read_text(encoding='utf-8'))['files']
assert len(rows)==81
candidate_changes=[]
for row in rows:
    p=R/'candidate'/row['file'];b=B/'candidate'/row['file'];assert sha(p)==row['sha256'] and sha(b)==row['p7r1_sha256']
    if sha(p)!=sha(b):candidate_changes.append(row['file'])
assert candidate_changes==['source/rtl/undistort_cache_ab.v']
rows2=json.loads((R/'physical/input_identity.json').read_text(encoding='utf-8'))['inputs']
physical_changes=[]
for row in rows2:
    p=R/'physical/host_seed2'/row['file'];b=B/'physical/host_seed2'/row['file'];assert sha(p)==row['sha256']
    if sha(p)!=sha(b):physical_changes.append(row['file'])
assert physical_changes==['source/rtl/undistort_cache_ab.v']
paths=['candidate/source/rtl/undistort_cache_ab.v','physical/host_seed2/source/rtl/undistort_cache_ab.v']
assert len({sha(R/p) for p in paths})==1
changes=''.join(difflib.unified_diff((B/paths[0]).read_text(encoding='utf-8').splitlines(True),(R/paths[0]).read_text(encoding='utf-8').splitlines(True),fromfile='P7R1/undistort_cache_ab.v',tofile='P8/undistort_cache_ab.v'))
(R/'results/cache_source.diff').write_text(changes,encoding='utf-8')
result=dict(passed=True,candidate_file_count=len(rows),physical_input_count=len(rows2),candidate_changes=candidate_changes,physical_changes=physical_changes,core_sha256=sha(R/'candidate/source/rtl/undistort_core.v'),cache_sha256=sha(R/paths[0]),original_constraints_unchanged=True,original_ips_unchanged=True,p7_manifest_unchanged=None)
old_manifest=json.loads((B/'DELIVERY_MANIFEST.json').read_text(encoding='utf-8'))
assert all(sha(B/row['file'])==row['sha256'] for row in old_manifest)
result['p7_manifest_unchanged']=True
(R/'results/input_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
shutil.copy2(__file__,R/'audit_p8_inputs.py');print(json.dumps(result,indent=2))
