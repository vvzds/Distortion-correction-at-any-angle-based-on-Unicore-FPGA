"""Read-only review evidence verification; does not approve electrical/timing closure."""
from pathlib import Path
import json,hashlib,re,collections,argparse,datetime
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 w=Path(__file__).resolve().parent;p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);o=p.parse_args().out
 require(not o.exists(),'Refuse overwrite')
 sources=read(w/'source_index.json');audit=read(w/'warning_audit.json');verified=0
 for item in sources:
  f=(w/item['path']).resolve();require(f.is_relative_to(w),'Evidence outside root')
  require(f.stat().st_size==item['bytes'] and sha(f)==item['sha256'],'Evidence SHA: '+item['path'])
  rel=Path(item['path']);parts=rel.parts
  if item['receipt_hash']:
   if parts[1]=='G8_native_seed2':expected=read(w/'evidence/G8_native_seed2/export_receipt.json')['files_sha256'][f.name]
   else:expected=read(w/Path(*parts[:3])/'process_receipt.json')['artifacts_sha256'][Path(*parts[3:]).as_posix()]
   require(expected.lower()==item['sha256']==item['receipt_hash'],'Receipt anchor');verified+=1
  elif f.name=='process_receipt.json':
   receipt=read(f);require(receipt['exit_code']==0 and receipt['inputs_before']==receipt['inputs_after'],'Execution receipt')
 keys=set();events=0
 for row in audit['records']:
  key=(row['candidate'],row['seed'],row['stage']);require(key not in keys,'Duplicate run/stage');keys.add(key)
  actual=[]
  for n,line in enumerate((w/row['path']).read_text(encoding='utf-8',errors='replace').splitlines(),1):
   if re.match(r'^\s*C:',line):actual.append((n,line))
  expected={'compile':18,'synthesize':38 if row['candidate']=='G7' else 46,'device_map':0,'place_route':51,'report_timing':32,'generate_bitstream':0}[row['stage']]
  require(len(actual)==row['count']==expected,'Stage count')
  require(actual==[(x['line'],x['message']) for x in row['events']],'Ledger versus original log')
  events+=len(actual)
 require(keys=={(c,s,t) for c in ['G7','G8'] for s in [2,3,5,7,8,9,10,11] for t in ['compile','synthesize','device_map','place_route','report_timing','generate_bitstream']},'96 stage coverage')
 require(events==2288 and len(sources)==258 and verified==241,'Total coverage')
 originals=audit['original_38'];require([x['id'] for x in originals]==[f'CW{i:02}' for i in range(1,39)],'Original numbering')
 require(collections.Counter(x['kind'] for x in originals)=={'share_pin':36,'missing_DRIVE':1,'missing_SLEW':1},'Original categories')
 for c in ['G7','G8']:
  for seed in [2,3,5,7,8,9,10,11]:
   base=w/'evidence'/c/f'seed_{seed}'
   fdc=(base/'HDMI_DDR3_OV5640_test.fdc').read_text(encoding='utf-8',errors='replace')
   attributes={(port,k):v for port,k,v in re.findall(r'define_attribute\s+\{p:([^}]+)\}\s+\{([^}]+)\}\s+\{([^}]+)\}',fdc)}
   locs=[v for (port,k),v in attributes.items() if k=='PAP_IO_LOC']
   require(len(locs)==143 and len(set(locs))==143,'LOC count/duplicates')
   require(('uart_tx','PAP_IO_DRIVE') not in attributes and ('uart_tx','PAP_IO_SLEW') not in attributes,'UART missing attribute conclusion')
   ports={}
   for n,line in enumerate((base/'place_route/hdmi_ddr_ov5640_top.prr').read_text(encoding='utf-8',errors='replace').splitlines(),1):
    cells=[x.strip() for x in line.split('|')][1:]
    if len(cells)>9 and cells[1] in ['input','output','inout']:ports[cells[0]]=dict(zip(['direction','loc','bank','vccio','iostd','drive','pull','slew'],cells[1:9]),line=n)
   for entry in originals:
    observed=[x for x in entry['observed_io'] if x['candidate']==c and x['seed']==seed]
    require(len(observed)==1,'IO run coverage')
    require(ports[entry['port']]=={k:v for k,v in observed[0].items() if k not in ['candidate','seed']},'IO ledger')
    require(attributes[(entry['port'],'PAP_IO_LOC')]==entry['loc']==ports[entry['port']]['loc'],'FDC/PRR LOC')
   require(ports['uart_tx']['drive']=='4' and ports['uart_tx']['slew']=='FAST','UART implemented properties')
   syn=next(x for x in audit['records'] if (x['candidate'],x['seed'],x['stage'])==(c,seed,'synthesize'))
   require(collections.Counter(x['semantic'] for x in syn['events'] if x['code'].startswith('ConstraintEditor'))==collections.Counter(x['semantic'] for x in originals),'Original38 across candidates')
 for entry in originals:
  require(len({tuple(x[k] for k in ['direction','loc','bank','vccio','iostd','drive','pull','slew']) for x in entry['observed_io']})==1,'IO stable')
 manifest=w/'files_sha256.json'
 if manifest.exists():
  for row in read(manifest):require(sha(w/row['path'])==row['sha256'] and (w/row['path']).stat().st_size==row['bytes'],'Review manifest')
 result=dict(status='PASS_EVIDENCE_ONLY',sources=258,receipt_anchored=241,stage_logs=96,critical_events=events,original_38_closed=0,production_approved=False,time_bj=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat())
 with o.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
