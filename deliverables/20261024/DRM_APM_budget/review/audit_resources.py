from pathlib import Path
import json,hashlib,re,shutil,csv,datetime
W=Path(__file__).resolve().parent;E=W/'evidence';E.mkdir(exist_ok=True)
SEEDS=[2,3,5,7,8,9,10,11]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[]
def copy_source(p,dest,anchor=None):
 h=sha(p)
 if anchor and h.lower()!=anchor.lower():raise ValueError('Recorded hash mismatch '+str(p))
 dst=E/dest;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
 if sha(dst)!=h:raise ValueError('Copy mismatch')
 sources.append(dict(original=str(p),path=dst.relative_to(W).as_posix(),bytes=p.stat().st_size,sha256=h,recorded_hash_matched=bool(anchor)))
 return dst
def parse(p):
 text=p.read_text(encoding='utf-8',errors='replace');lines=text.splitlines();table=False;rows=[];stack=[]
 for no,line in enumerate(lines,1):
  if '| Module Inst Name' in line:table=True;continue
  if not table or not line.startswith('|'):continue
  c=line.split('|')[1:]
  if len(c)<6:continue
  try:values=dict(zip(['LUT','FF','distributed_RAM','APM','DRM'],map(float,c[1:6])))
  except ValueError:continue
  cell=c[0];name=cell.strip();plus='+' in name
  depth=(cell.index('+')-1)//2+1 if plus else 0
  name=name.lstrip('+ ').strip()
  if depth>len(stack):raise ValueError('Hierarchy gap')
  stack=stack[:depth]+[name]
  rows.append(dict(path='/'.join(stack),name=name,depth=depth,line=no,**values))
 if not rows:raise ValueError('No hierarchy '+str(p))
 if p.suffix=='.prr':
  device={}
  for key in ['APM','DRM']:
   m=re.search(r'\| Use of '+key+r'\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)',text)
   if not m:raise ValueError('Missing '+key)
   device[key]=float(m[1]);device[key+'_available']=float(m[2])
  # Device table has CLMA and CLMS LUT/FF rows; top module may differ.
  prefix=text.split('Device Utilization Summary Of Each Module:')[0]
  device['LUT']=sum(float(x) for x in re.findall(r'\|\s+LUT\s*\|\s*([\d.]+)\s*\|',prefix))
  device['FF']=sum(float(x) for x in re.findall(r'\|\s+FF\s*\|\s*([\d.]+)\s*\|',prefix))
  primitive=None
 else:
  device={}
  for key,pat in [('DRM',r'Total DRM = ([\d.]+) of ([\d.]+)'),('APM',r'Total APMs = ([\d.]+) of ([\d.]+)')]:
   m=re.search(pat,text);device[key]=float(m[1]);device[key+'_available']=float(m[2])
  device['LUT']=float(re.search(r'Total LUTs: (\d+)',text)[1]);device['FF']=float(re.search(r'Total Registers: (\d+)',text)[1])
  primitive={}
  for key in ['APM_E2','DRM18K_E1','DRM36K_E1']:
   m=re.search(r'^GTP_'+key+r'\s+(\d+) uses?$',text,re.M);primitive[key]=int(m[1]) if m else 0
  if primitive['DRM36K_E1']+primitive['DRM18K_E1']/2!=device['DRM'] or primitive['APM_E2']!=device['APM']:raise ValueError('Primitive sum mismatch')
 checks={k:device[k]==rows[0][k] for k in ['APM','DRM','LUT','FF']}
 for k in ['APM','DRM']:
  if not checks[k]:raise ValueError('DRM/APM table mismatch')
 # Inclusive rows must not be summed across hierarchy levels.
 for r in rows:
  children=[x for x in rows if x['depth']==r['depth']+1 and x['path'].startswith(r['path']+'/')]
  r['exclusive_DRM']=r['DRM']-sum(x['DRM'] for x in children)
  r['exclusive_APM']=r['APM']-sum(x['APM'] for x in children)
  if min(r['exclusive_DRM'],r['exclusive_APM'])<0:raise ValueError('Hierarchy double count')
 return dict(path=p.relative_to(W).as_posix(),sha256=sha(p),header=lines[0],device=device,top=rows[0],tables_agree=checks,primitives=primitive,modules=rows)
records=[]
for candidate,base in [('G7',Path('D:/FPGA_management/work/G7_six_receipts_20261023/physical_g7_original')),('G8',Path('D:/FPGA_management/work/G8_followup_20261023/physical_g8'))]:
 for seed in SEEDS:
  root=base/f'seed_{seed}';receipt=json.loads((root/'process_receipt.json').read_text(encoding='utf-8'));artifacts=receipt['artifacts_sha256']
  copy_source(root/'process_receipt.json',f'{candidate}/seed_{seed}/process_receipt.json')
  for folder,suffix in [('synthesize','snr'),('place_route','prr')]:
   rel=f'{folder}/hdmi_ddr_ov5640_top.{suffix}';p=copy_source(root/rel,f'{candidate}/seed_{seed}/{suffix}.{suffix}',artifacts[rel]);item=parse(p);item.update(candidate=candidate,seed=seed,stage=folder,evidence_scope='MATCHED_PROCESS_RECEIPT');records.append(item)
ab=Path('D:/FPGA_management/work/G4_AB_review_20261023/extracted/G4_AB_candidate_20261022/reports')
for name,label in [('pds_v7','AB_OLD_CORE'),('host_ab_synth_20261023','AB_OLD_HOST')]:
 p=copy_source(ab/(name+'.snr'),f'{label}/synth.snr');item=parse(p);item.update(candidate=label,seed=None,stage='synthesize',evidence_scope='HISTORICAL_PRE_R1_R4_ONLY');records.append(item)
 for suffix in ['inputs.json','result.json']:copy_source(ab/(name+'.'+suffix),f'{label}/{suffix}')
reference=Path('D:/FPGA_management/work/G7_six_receipts_20261023/execution/6/reference_original/M03/references')
for p in [reference/'图像畸变校正系统设计文档_V1.2.md',Path('D:/FPGA项目文档/总说明/模块分工与工作包交付总说明_v2.0.4.md')]:copy_source(p,'specs/'+p.name)
root=Path('D:/FPGA_management/work/G8_followup_20261023/physical_g8/seed_2')
for name in ['undistort_line_cache.v','undistort_map.v','undistort_bilinear.v','undistort_core.v','gamma_lut.v','param_mgr.v']:
 p=root/'source/rtl/corr_subsys'/name
 if p.exists():copy_source(p,'G8_RTL/'+name)
abroot=Path('D:/FPGA_management/work/G4_AB_R1_R4_20261023/received/G4_AB_R1_R4_20261023/candidate/source/rtl')
for name in ['undistort_cache_ab.v','undistort_core.v']:copy_source(abroot/name,'AB_CURRENT_RTL/'+name)
oldroot=Path('D:/FPGA_management/work/G4_AB_review_20261023/extracted/G4_AB_candidate_20261022/source/rtl')
for name in ['undistort_cache_ab.v','undistort_core.v']:copy_source(oldroot/name,'AB_OLD_RTL/'+name)
v=Path('D:/FPGA_management/work/review_delegation_20261023/received/二号协作者/3/V204_independent_review')
for name in ['evidence/cache_native_configuration.json','evidence/core_audit_final/audit.json','02_核心资源约束分析与处理建议.md']:copy_source(v/name,'prior_G7_analysis/'+Path(name).name)
def find(item,name):
 vals=[r for r in item['modules'] if r['name']==name]
 if len(vals)!=1:raise ValueError('Module ambiguous '+name)
 return vals[0]
summary=[]
for r in records:
 core=next((x for x in r['modules'] if x['name']=='u_core'),r['top'])
 cache=find(r,'u_cache');mp=find(r,'u_map');bi=find(r,'u_bilinear')
 summary.append(dict(candidate=r['candidate'],stage=r['stage'],seed=r['seed'],host_DRM=r['device']['DRM'],host_APM=r['device']['APM'],core_DRM=core['DRM'],cache_DRM=cache['DRM'],core_direct_DRM=core['exclusive_DRM'],map_APM=mp['APM'],bilinear_APM=bi['APM'],host_other_DRM=r['device']['DRM']-core['DRM'],LUT_difference=r['device']['LUT']-r['top']['LUT'],DRM_capacity_percent=r['device']['DRM']/155*100,APM_capacity_percent=r['device']['APM']/240*100,DRM_remaining=155-r['device']['DRM'],APM_remaining=240-r['device']['APM']))
out=dict(status='DRM_APM_ACCOUNTING_PASS_SCOPED',time_bj=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),native_reports=len(records),matched_prior_process_reports=32,candidate_latest_ab='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68',AB_new_physical_status='NOT_AVAILABLE',formal_cache_limit=12,cache_limit_changed=False,overall_S3='NOT_PASSED',summary=summary,records=records)
(W/'resource_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
(W/'source_index.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
with (W/'resource_ledger.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
if any(sha(Path(r['original']))!=r['sha256'] for r in sources):raise ValueError('Source changed during audit')
print(json.dumps(dict(status=out['status'],reports=len(records),sources=len(sources),representative=[s for s in summary if s['seed'] in [2,None]]),ensure_ascii=False,indent=2))
