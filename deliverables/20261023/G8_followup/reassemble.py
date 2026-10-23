"""Reassemble the single delivery ZIP and verify every part and the whole SHA256."""
from pathlib import Path
import json,hashlib,datetime,sys
root=Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
index=json.loads((root/'parts_manifest.json').read_text(encoding='utf-8'))
name=index['zip']
if Path(name).name!=name:raise ValueError('Invalid ZIP name')
out=root/name
if out.exists():
 if out.stat().st_size==index['bytes'] and sha(out)==index['sha256']:print('EXISTING_ZIP_PASS',out);sys.exit(0)
 raise FileExistsError('Preserve existing different output: '+str(out))
total=hashlib.sha256();size=0
temp=root/(name+'.assembling_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
with temp.open('xb') as f:
 for row in index['parts']:
  part=root/row['path']
  if not part.resolve().is_relative_to(root.resolve()) or not part.is_file():raise ValueError('Missing/unsafe part')
  if part.stat().st_size!=row['bytes'] or sha(part)!=row['sha256']:raise ValueError('Part hash mismatch: '+row['path'])
  with part.open('rb') as src:
   for b in iter(lambda:src.read(1048576),b''):f.write(b);total.update(b);size+=len(b)
  print('PART_PASS',row['path'],flush=True)
if size!=index['bytes'] or total.hexdigest()!=index['sha256']:raise ValueError('Whole ZIP mismatch; partial preserved')
if out.exists():raise FileExistsError('Output appeared; verified temporary file preserved')
temp.rename(out)
print('REASSEMBLY_PASS',out,index['sha256'])
