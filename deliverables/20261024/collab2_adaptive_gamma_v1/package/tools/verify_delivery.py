"""Verify packaged bytes and six successful ModelSim receipts."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
def require(ok,msg):
    if not ok:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=json.loads((ROOT/'MANIFEST_SHA256.json').read_text(encoding='utf-8'))
    for name,h in manifest.items():require(sha(ROOT/name)==h,'Hash mismatch '+name)
    report=json.loads((ROOT/'evidence/RESULT.json').read_text(encoding='utf-8'))
    require(len(report['tests'])==6,'Expected six testbenches')
    for t in report['tests']:
        log=ROOT/t['log'];text=log.read_text(encoding='utf-8',errors='replace')
        require(sha(log)==t['sha256'],'Log hash mismatch')
        require(text.count('=== ALL TESTS PASSED (err=0) ===')==1,'Missing PASS')
        require('FAIL' not in text and '** Error' not in text and '** Fatal' not in text,'Failure in log')
        receipt=json.loads((ROOT/t['receipt']).read_text(encoding='utf-8'))
        case=next(c for c in receipt['cases'] if c['top']==t['name'])
        require(case['exit']==0 and case['passed'],'Invalid test receipt')
        required=['rtl/adaptive_gamma.v','rtl/adaptive_gamma_curve.v','rtl/corr_top.v','rtl/gamma_lut.v','sim/'+t['name']+'.v']
        if t['name']=='adaptive_gamma_tb':required.append('sim/vectors.mem')
        inputs={k.replace('\\','/'):v for k,v in receipt['inputs'].items()}
        for name in required:require(sha(ROOT/name)==inputs[name],'Test input changed '+name)
    refs=json.loads((ROOT/'evidence/integration_reference_hashes.json').read_text(encoding='utf-8'))
    for name,h in refs.items():require(sha(ROOT/'reference'/name)==h,'Reference changed '+name)
    native=json.loads((ROOT/report['native_synthesis']['receipt']).read_text(encoding='utf-8'))
    require(native['status']=='PASS' and native['exit']==0,'Synthesis failed')
    for name,h in native['input_sha256'].items():require(sha(ROOT/'rtl'/name)==h,'Synthesis input changed')
    require(sha(ROOT/'reference/gamma_lut.v')==sha(ROOT/'rtl/gamma_lut.v'),'Manual Gamma changed')
    print('=== DELIVERY VERIFIED (err=0) ===')
if __name__=='__main__':main()
