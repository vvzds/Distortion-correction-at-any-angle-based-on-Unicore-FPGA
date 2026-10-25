from pathlib import Path
import json,hashlib
from netlist_metrics import measure
R=Path(__file__).resolve().parent
saved=json.loads((R/'results/synthesis_gate/netlist_metrics.json').read_text())
ref=json.loads((R/'reference_p4_resource/REFERENCE_MANIFEST.json').read_text())
for f,d in ref['files'].items():
    assert hashlib.sha256((R/'reference_p4_resource'/f).read_bytes()).hexdigest()==d['sha256']
checks={}
for name,root in [('baseline',R/'reference_p4_resource'),('candidate',R/'results/synthesis_gate/native')]:
    actual=json.loads(json.dumps(measure(root/'synthesize/hdmi_ddr_ov5640_top_syn.vm')))
    expected=saved[name]
    diffs=[k for k in actual if k!='netlist' and actual[k]!=expected[k]]
    assert not diffs,(name,diffs)
    checks[name]=dict(matched=True,netlist_sha256=actual['sha256'],tag_ram_primitives=actual['tag_ram_primitives'],parity_pin_loads=actual['parity_pin_loads'])
(R/'results/archived_metrics_recheck.json').write_text(json.dumps(dict(passed=True,scope='Recompute recorded synthesis structure metrics from self-contained archived netlists; no design or simulation rerun',checks=checks),indent=2),encoding='utf-8')
print(json.dumps(checks,indent=2))
