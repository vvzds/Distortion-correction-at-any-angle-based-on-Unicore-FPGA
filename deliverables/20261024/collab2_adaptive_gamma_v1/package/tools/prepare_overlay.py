"""Prepare a hash-checked Gamma overlay; never edits a baseline project."""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--baseline',required=True,type=Path,help='Existing corr_top.v')
    ap.add_argument('--out',required=True,type=Path,help='New overlay directory')
    a=ap.parse_args()
    if sha(a.baseline)!=sha(ROOT/'reference/corr_top.v'):
        raise ValueError('Baseline differs: review merge manually; refusing blind replacement')
    if a.out.exists():raise ValueError('Output exists; select a new directory')
    a.out.mkdir(parents=True)
    for name in ('adaptive_gamma.v','adaptive_gamma_curve.v','gamma_lut.v'):
        shutil.copy2(ROOT/'rtl'/name,a.out/name)
    text=(ROOT/'rtl/corr_top.v').read_text(encoding='utf-8')
    old='parameter integer ADAPTIVE_GAMMA = 0,'
    if text.count(old)!=1:raise ValueError('Unexpected candidate parameter declaration')
    (a.out/'corr_top.v').write_text(text.replace(old,'parameter integer ADAPTIVE_GAMMA = 1,'),encoding='utf-8')
    info=dict(mode='adaptive_default_on_enable_by_existing_0x04_bit0',
              baseline_sha256=sha(a.baseline),sources={p.name:sha(p) for p in a.out.glob('*.v')},
              tested_parameter_value=1,baseline_modified=False,bitstream_generated=False)
    (a.out/'OVERLAY.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(a.out)
if __name__=='__main__':main()
