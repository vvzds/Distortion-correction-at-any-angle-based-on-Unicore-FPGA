"""Continue the authorized P3 checks once the current regression writes its summary."""
from pathlib import Path
import json,time,subprocess,sys
R=Path(__file__).resolve().parent
summary=R/'results/regression_p3/summary.json'
limit=time.monotonic()+7200
print('WAITING_FOR_REGRESSION_SUMMARY',flush=True)
while not summary.exists():
    if time.monotonic()>limit:raise RuntimeError('Regression summary not produced within 7200 seconds; physical run not started')
    time.sleep(3)
d=json.loads(summary.read_text(encoding='utf-8'))
assert len(d['results'])==6 and all(x['passed'] for x in d['results']), 'P3 functional gate failed; physical run not started'
print('REGRESSION_ALL_PASS; comparing complete logs',flush=True)
subprocess.run([sys.executable,'-B','-X','utf8',str(R/'compare_regression.py')],check=True)
print('LOG_COMPARISON_PASS; starting fixed seed2 physical run',flush=True)
subprocess.run([sys.executable,'-B','-X','utf8',str(R/'run_physical.py')],check=True)
print('PHYSICAL_FINISHED; extracting actual results',flush=True)
subprocess.run([sys.executable,'-B','-X','utf8',str(R/'inspect_physical.py')],check=True)
subprocess.run([sys.executable,'-B','-X','utf8',str(R/'compare_warnings.py')],check=True)
print('P3_EVIDENCE_READY; timing acceptance still requires report review',flush=True)
