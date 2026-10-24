"""Verify all packaged bytes and live-run accounting without opening hardware."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path('C:/Users/叶翔/Documents/Codex/fpga-main/deliverables/20261024/collab2_G4_static_board_verified')
hashes=json.loads((ROOT/'SHA256SUMS.json').read_text(encoding='utf-8'))
for name,h in hashes.items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
archive=next(ROOT.glob('*.zip'))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    root=z.namelist()[0].split('/')[0]+'/'
    entries=json.loads(z.read(root+'SHA256SUMS.json'))
    for name,h in entries.items():
        assert hashlib.sha256(z.read(root+name)).hexdigest()==h,name
    version=json.loads(z.read(root+'VERSION.json'))
    assert version['real_correction_confirmed_by_user']
    assert not version['correction_30fps_requirement_met']
    assert version['bitstream_sha256']==hashlib.sha256(z.read(root+'01_project/generate_bitstream/hdmi_ddr_ov5640_top.sbit')).hexdigest()
    records=[json.loads(z.read(n)) for n in z.namelist() if '/02_evidence/uart_' in n and n.endswith('.json')]
    stable=sorted(records,key=lambda r:r['start'])[-1]
    a,b=stable['queries'][0],stable['queries'][-1]
    assert ((b['pub_count']-a['pub_count'])&65535)==stable['publish_delta']
    assert abs(stable['observed_publish_per_s']-stable['publish_delta']/stable['elapsed_s'])<1e-9
print(json.dumps(dict(state='PASS',repository_files=len(hashes),package_files=len(entries),
    actual_real_publish_fps=version['real_corrected_frames_per_second'])))
