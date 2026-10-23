from pathlib import Path
import json,hashlib,shutil,re,collections
W=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
idx=json.loads((W/'source_index.json').read_text(encoding='utf-8'))
idx=[x for x in idx if not x['path'].startswith('evidence/G8_native_seed2/')]
root=Path('D:/FPGA_management/work/G8_followup_20261023/native_g8/seed_2')
rec=json.loads((root/'export_receipt.json').read_text(encoding='utf-8'))
dest=W/'evidence/G8_native_seed2';dest.mkdir(exist_ok=True)
for name in ['export_receipt.json','routed.v']:
 p=root/name;h=sha(p);anchor=rec['files_sha256'].get(name)
 if anchor:assert h==anchor
 shutil.copy2(p,dest/name)
 idx.append(dict(original=str(p),path=(dest/name).relative_to(W).as_posix(),bytes=p.stat().st_size,sha256=h,receipt_hash=anchor))
dump(W/'source_index.json',idx)
a=json.loads((W/'warning_audit.json').read_text(encoding='utf-8'))
result={}
for c in ['G7','G8']:
 for stage in ['compile','synthesize','place_route','report_timing']:
  rr=[r for r in a['records'] if r['candidate']==c and r['stage']==stage]
  signatures=[collections.Counter((e['code'],e['semantic']) for e in r['events']) for r in rr]
  result[c+'/'+stage]=dict(exact_semantics_identical=all(x==signatures[0] for x in signatures),unique_per_run=[r['unique_semantics'] for r in rr])
io_variants={e['id']:len(set(tuple(x[k] for k in ['direction','loc','bank','vccio','iostd','drive','pull','slew']) for x in e['observed_io'])) for e in a['original_38']}
assert set(io_variants.values())=={1}
result['all_38_io_fields_stable_across_16_runs']=True
result['netlist_unused_identifier_matches']={n:len(re.findall(r'\b'+n+r'\b',(dest/'routed.v').read_text(encoding='utf-8',errors='replace'))) for n in ['cmos2_d_16bit','cmos2_href_16bit','cmos2_pclk_16bit']}
result['sources']=len(idx);result['receipt_anchored_sources']=sum(bool(s['receipt_hash']) for s in idx)
a['source_count']=len(idx);a['anchored_sources']=result['receipt_anchored_sources']
a['originals_unchanged']=all(sha(Path(s['original']))==s['sha256'] for s in idx)
if not a['originals_unchanged']:raise ValueError('Original changed')
dump(W/'warning_audit.json',a)
dump(W/'cross_checks.json',result)
print(json.dumps(result,ensure_ascii=False,indent=2))
