"""Rebuild complete recipient ZIPs using immutable repository evidence; Python standard library only."""
from pathlib import Path
import argparse,json,hashlib,zipfile,shutil
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def build(recipe,repo,out):
 dest=out/recipe['filename']
 if dest.exists():raise FileExistsError('Will not overwrite '+str(dest))
 # Every Git source has a size and hash, including original G8 chunks.
 seen={}
 for item in recipe['entries']:
  for part in item['source_parts']:
   path=(repo/part['path']).resolve()
   if not path.is_relative_to(repo.resolve()):raise ValueError('Out-of-repository source')
   if path not in seen:seen[path]=(path.stat().st_size,sha(path))
   if seen[path]!=(part['bytes'],part['sha256']):raise ValueError('Source integrity: '+part['path'])
 out.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
  for item in recipe['entries']:
   info=zipfile.ZipInfo(item['path'],date_time=(2026,10,23,0,0,0));info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_STORED
   h=hashlib.sha256();size=0
   with z.open(info,'w',force_zip64=True) as target:
    for part in item['source_parts']:
     with (repo/part['path']).open('rb') as f:
      for b in iter(lambda:f.read(8*1024*1024),b''):target.write(b);h.update(b);size+=len(b)
   if size!=item['bytes'] or h.hexdigest()!=item['sha256']:raise ValueError('Assembled member integrity '+item['path'])
   if size>100000000:print('assembled',item['path'],size,flush=True)
 with zipfile.ZipFile(dest) as z:
  if len(z.infolist())!=len(recipe['entries']):raise ValueError('Member count')
  for item in recipe['entries']:
   h=hashlib.sha256();size=0
   with z.open(item['path']) as f:
    for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b);size+=len(b)
   if h.hexdigest()!=item['sha256'] or size!=item['bytes']:raise ValueError('ZIP readback '+item['path'])
 result=dict(filename=dest.name,bytes=dest.stat().st_size,sha256=sha(dest),members=len(recipe['entries']),all_members_verified=True)
 if recipe.get('zip_sha256') and result['sha256']!=recipe['zip_sha256']:raise ValueError('Final ZIP hash')
 print(json.dumps(result,ensure_ascii=False),flush=True);return result
def main():
 base=Path(__file__).resolve().parent
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--recipient',choices=['one','two','all'],default='all');p.add_argument('--out',type=Path,required=True);p.add_argument('--repo',type=Path,default=base.parents[2]);a=p.parse_args()
 keys=['one','two'] if a.recipient=='all' else [a.recipient]
 results=[build(json.loads((base/'recipes'/f'{key}.json').read_text(encoding='utf-8')),a.repo.resolve(),a.out.resolve()) for key in keys]
 (a.out/'reassembly_receipt.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
