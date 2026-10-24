from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parent
B=Path(r'C:\Users\lenovo\Desktop\ww\audit_delivery_20261024\runs\ab_seed2_inputs')
P=R/'physical/host_seed2';P.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for d in ['source','ipcore']:shutil.copytree(B/d,P/d,dirs_exist_ok=True)
for name in ['analysis.tcl','HDMI_DDR3_OV5640_test.fdc','task1_1080p30.pds']:
    shutil.copyfile(B/name,P/name)
assert sha(P/'source/rtl/undistort_cache_ab.v')=='4fc449dc3bf1e34711c774057c4d92559ebd545e5f88facac27cac5da33a6a60'
shutil.copyfile(R/'candidate/source/rtl/undistort_cache_ab.v',P/'source/rtl/undistort_cache_ab.v')
changes=[];rows=[]
for p in sorted(P.rglob('*')):
    if p.is_file():
        rel=p.relative_to(P).as_posix();h=sha(p);old=sha(B/rel)
        rows.append({'file':rel,'sha256':h,'baseline_sha256':old})
        if h!=old:changes.append(rel)
assert changes==['source/rtl/undistort_cache_ab.v'],changes
assert 'gen_bit_stream' not in (P/'analysis.tcl').read_text()
(R/'physical/input_identity.json').write_text(json.dumps({'baseline':str(B),'changed_files':changes,'inputs':rows},indent=2),encoding='utf-8')
print('Prepared same-seed2 offline host; only cache RTL differs:',len(rows),'input files.')
