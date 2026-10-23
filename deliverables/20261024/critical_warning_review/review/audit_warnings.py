from pathlib import Path
import re,json,hashlib,shutil,collections
W=Path(__file__).resolve().parent
SEEDS=[2,3,5,7,8,9,10,11]
STAGES=['compile','synthesize','device_map','place_route','report_timing','generate_bitstream']
BASES={'G7':Path('D:/FPGA_management/work/G7_six_receipts_20261023/physical_g7_original'),'G8':Path('D:/FPGA_management/work/G8_followup_20261023/physical_g8')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def parse(p):
 out=[]
 for n,line in enumerate(p.read_text(encoding='utf-8',errors='replace').splitlines(),1):
  m=re.match(r'^\s*C:\s*([\w-]+):\s*(.*)',line)
  if m:
   # Remove only logged absolute source prefix; preserve pin, clock, arc, and message.
   semantic=re.sub(r'\[[^\]]*\(line number: (\d+)\)\]',r'[source line \1]',m[2])
   out.append(dict(line=n,code=m[1],message=line,semantic=semantic))
 return out
def main():
 sources=[];records=[];ios=[];static=[]
 def copy(root,rel,dest,anchor=None):
  p=root/rel;h=sha(p)
  if anchor and h!=anchor.lower():raise ValueError('Original receipt mismatch '+str(p))
  q=W/'evidence'/dest/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
  if sha(q)!=h:raise ValueError('Copy mismatch')
  sources.append(dict(original=str(p),path=q.relative_to(W).as_posix(),sha256=h,bytes=p.stat().st_size,receipt_hash=anchor.lower() if anchor else None))
  return q
 for candidate,base in BASES.items():
  for seed in SEEDS:
   root=base/f'seed_{seed}';dest=f'{candidate}/seed_{seed}'
   receipt=json.loads((root/'process_receipt.json').read_text(encoding='utf-8'));art=receipt['artifacts_sha256']
   if receipt['exit_code']!=0 or receipt['inputs_before']!=receipt['inputs_after']:raise ValueError('Unclean run')
   copy(root,'process_receipt.json',dest)
   for stage in STAGES:
    rel=f'{stage}/run.log';p=copy(root,rel,dest,art[rel]);events=parse(p)
    records.append(dict(candidate=candidate,seed=seed,stage=stage,path=p.relative_to(W).as_posix(),count=len(events),codes=dict(collections.Counter(e['code'] for e in events)),events=events))
   for rel in ['HDMI_DDR3_OV5640_test.fdc','place_route/hdmi_ddr_ov5640_top.prr','device_map/hdmi_ddr_ov5640_top.pcf','place_route/clock_utilization.txt','source/rtl/hdmi_ddr_ov5640_top.v','source/rtl/reg_config.v','source/rtl/i2c_com.v','build.tcl','run_trial.pds']:
    copy(root,rel,dest,art[rel])
   prr=root/'place_route/hdmi_ddr_ov5640_top.prr';ports={}
   for no,line in enumerate(prr.read_text(encoding='utf-8',errors='replace').splitlines(),1):
    cells=[x.strip() for x in line.split('|')][1:]
    if len(cells)>9 and cells[1] in ['input','output','inout']:
     ports[cells[0]]=dict(zip(['direction','loc','bank','vccio','iostd','drive','pull','slew'],cells[1:9]),line=no)
   ios.append(dict(candidate=candidate,seed=seed,ports=ports))
   fdc=(root/'HDMI_DDR3_OV5640_test.fdc').read_text(encoding='utf-8',errors='replace')
   locs=re.findall(r'define_attribute\s+\{p:([^}]+)\}\s+\{PAP_IO_LOC\}\s+\{([^}]+)\}',fdc)
   dup={k:v for k,v in ((loc,[p for p,l in locs if l==loc]) for loc in set(l for p,l in locs)) if len(v)>1}
   src=(root/'source/rtl/hdmi_ddr_ov5640_top.v').read_text(encoding='utf-8',errors='replace')
   refs={n:[i for i,l in enumerate(src.splitlines(),1) if re.search(r'\b'+n+r'\b',l)] for n in ['cmos2_d_16bit','cmos2_href_16bit','cmos2_pclk_16bit','cmos1_data','cmos1_href','cmos1_pclk','cmos1_vsync']}
   static.append(dict(candidate=candidate,seed=seed,explicit_locs=len(locs),duplicate_locs=dup,top_identifier_lines=refs,fdc_sha256=sha(root/'HDMI_DDR3_OV5640_test.fdc'),top_sha256=sha(root/'source/rtl/hdmi_ddr_ov5640_top.v')))
 baseline=next(r for r in records if (r['candidate'],r['seed'],r['stage'])==('G7',2,'synthesize'))['events']
 assert len(baseline)==38
 ledger=[]
 for i,e in enumerate(baseline,1):
  m=re.search(r'Port (.+?) has been placed at location (\S+),',e['message'])
  if m:port,loc=m.groups();kind='share_pin';fdcline=int(re.search(r'line number: (\d+)',e['message'])[1])
  else:port='uart_tx';loc='C24';kind='missing_'+('DRIVE' if 'PAP_IO_DRIVE' in e['message'] else 'SLEW');fdcline=1017
  values=[dict(candidate=r['candidate'],seed=r['seed'],**r['ports'][port]) for r in ios]
  assert all(x['loc']==loc for x in values)
  ledger.append(dict(id=f'CW{i:02}',kind=kind,port=port,loc=loc,fdc_line=fdcline,baseline_log_line=e['line'],original_message=e['message'],semantic=e['semantic'],observed_io=values,status='OPEN_BOARD_EVIDENCE' if m else 'OPEN_SOURCE_CONSTRAINT',owner='一号修正/二号交叉审查/本机板级裁决'))
 for r in records:
  expected={'compile':18,'synthesize':38 if r['candidate']=='G7' else 46,'device_map':0,'place_route':51,'report_timing':32,'generate_bitstream':0}[r['stage']]
  assert r['count']==expected,(r['candidate'],r['seed'],r['stage'],r['count'])
  if r['stage']=='synthesize':
   a=collections.Counter(e['semantic'] for e in r['events'] if e['code'].startswith('ConstraintEditor'))
   assert a==collections.Counter(e['semantic'] for e in baseline)
  r['unique_semantics']=len(set((e['code'],e['semantic']) for e in r['events']))
 result=dict(scope='96 authoritative stage logs / 16 runs; event counts, not unique defects',seeds=SEEDS,records=records,static_checks=static,original_38=ledger,source_count=len(sources),anchored_sources=sum(bool(x['receipt_hash']) for x in sources),originals_unchanged=all(sha(Path(x['original']))==x['sha256'] for x in sources))
 assert result['originals_unchanged'] and all(x['explicit_locs']>100 and not x['duplicate_locs'] for x in static)
 dump(W/'source_index.json',sources);dump(W/'warning_audit.json',result)
 print(json.dumps(dict(counts=[{k:r[k] for k in ['candidate','seed','stage','count','unique_semantics']} for r in records if r['seed']==2],sources=len(sources),anchored=result['anchored_sources'],loc_counts=sorted(set(x['explicit_locs'] for x in static)),static=static[8],io_example=ledger[0]['observed_io'][8]),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
