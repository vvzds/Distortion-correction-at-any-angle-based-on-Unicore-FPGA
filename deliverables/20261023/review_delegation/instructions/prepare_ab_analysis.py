"""Derive a fixed-seed, offline AB host analysis input without modifying RTL/FDC or producing bitstreams."""
from pathlib import Path
import argparse,hashlib,json,shutil,re
CORE='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 source=a.candidate/'host_ab';out=a.out.resolve()
 if out.exists() or out.is_relative_to(a.candidate.resolve()):raise ValueError('Output must be new and outside source candidate')
 for root in [a.candidate,source]:
  if sha(root/'source/rtl/undistort_core.v')!=CORE:raise ValueError('AB core identity mismatch')
 tcl=(source/'synth_only.tcl').read_text(encoding='utf-8-sig')
 if not re.search(r'(?m)^exit\s*$',tcl) or re.search(r'(?m)^\s*(?:pnr|dev_map|gen_bit_stream)\b',tcl):raise ValueError('Unexpected source flow')
 # Copy the full frozen host, including its historical reports (clearly not new-run output).
 before={f.relative_to(source).as_posix():sha(f) for f in source.rglob('*') if f.is_file()}
 shutil.copytree(source,out)
 derived=re.sub(r'(?m)^exit\s*$', 'dev_map\npnr -gplace_seed 2 -groute_seed 2\nreport_timing\nexit',tcl)
 (out/'analysis.tcl').write_text('# OFFLINE_ANALYSIS_ONLY; UART LOC unresolved; no bitstream; seed=2\n'+derived,encoding='utf-8')
 if any(sha(source/n)!=h or sha(out/n)!=h for n,h in before.items()):raise ValueError('Copy/source integrity failure')
 report=dict(status='PREPARED_NOT_EXECUTED',scope='AB_HOST_OFFLINE_DIAGNOSTIC_ONLY',seed=2,core_sha256=CORE,source_host=str(source.resolve()),source_files=before,analysis_tcl_sha256=sha(out/'analysis.tcl'),rtl_fdc_ip_unchanged=True,uart_loc_unresolved=True,gen_bit_stream=False,production_eligible=False)
 (out/'analysis_input_identity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k!='source_files'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
