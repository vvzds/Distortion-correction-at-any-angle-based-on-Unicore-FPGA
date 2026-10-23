"""Recheck packaged native DRM/APM evidence, without PDS or management filesystem access."""
from pathlib import Path
import argparse,json,hashlib,re
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise FileExistsError('New output file required')
 root=Path(__file__).resolve().parent;ledger=json.loads((root/'resource_audit.json').read_text(encoding='utf-8'));results=[]
 for r in ledger['records']:
  f=root/r['path'];raw=f.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('Native evidence hash changed')
  text=raw.decode('utf-8',errors='replace');lines=text.splitlines()
  if f.suffix=='.prr':
   get=lambda k:float(re.search(r'\| Use of '+k+r'\s*\|\s*([\d.]+)',text)[1])
  else:
   get=lambda k:float(re.search(r'Total '+('APMs' if k=='APM' else 'DRM')+r' = ([\d.]+)',text)[1])
  # Independently read raw table values at captured original lines, not report summaries.
  native=[]
  for m in r['modules']:
   cells=lines[m['line']-1].split('|')
   name=cells[1].strip().lstrip('+ ').strip()
   if name!=m['name']:raise ValueError('Original line changed')
   apm=float(cells[5].strip());drm=float(cells[6].strip())
   if (apm,drm)!=(m['APM'],m['DRM']):raise ValueError('Ledger/table mismatch')
   native.append((m,apm,drm))
  top=native[0]
  if (get('APM'),get('DRM'))!=(top[1],top[2]):raise ValueError('Device/module mismatch')
  excl_apm=excl_drm=0
  for m,apm,drm in native:
   children=[(a,d) for child,a,d in native if child['path'].startswith(m['path']+'/') and child['depth']==m['depth']+1]
   excl_apm+=apm-sum(a for a,d in children);excl_drm+=drm-sum(d for a,d in children)
  if (excl_apm,excl_drm)!=(get('APM'),get('DRM')):raise ValueError('Hierarchy conservation')
  results.append(dict(candidate=r['candidate'],seed=r['seed'],stage=r['stage'],APM=get('APM'),DRM=get('DRM'),status='PASS_DRM_APM_ONLY',other_resource_errors_preserved=r['tables_agree']))
 if len(results)!=34:raise ValueError('Expected 34 reports')
 out=dict(status='PASS_DRM_APM_ACCOUNTING_ONLY',native_reports=34,new_PDS_run=False,master_limit_changed=False,S3_overall_pass=False,reports=results)
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS: 34 native reports; DRM/APM scope only')
if __name__=='__main__':main()
