from pathlib import Path
import argparse,hashlib,json,zipfile
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parent;meta=json.loads((root/'PACKAGE.json').read_text(encoding='utf-8'))
out=a.out.resolve()
if out.exists():raise ValueError('Use fresh output directory')
for row in meta['parts']:
 f=root/row['path']
 if f.stat().st_size!=row['bytes'] or sha(f)!=row['sha256']:raise ValueError('Part mismatch')
out.mkdir(parents=True);zpath=out/meta['zip_name']
with zpath.open('xb') as f:
 for row in meta['parts']:
  with (root/row['path']).open('rb') as part:
   for b in iter(lambda:part.read(1024*1024),b''):f.write(b)
if sha(zpath)!=meta['zip_sha256']:raise ValueError('ZIP mismatch')
with zipfile.ZipFile(zpath) as z:
 if z.testzip():raise ValueError('ZIP CRC mismatch')
 raw=z.read('MANIFEST_SHA256.json')
 if hashlib.sha256(raw).hexdigest()!=meta['manifest_sha256']:raise ValueError('Manifest mismatch')
 manifest=json.loads(raw)
 for name,h in manifest.items():
  if hashlib.sha256(z.read(name)).hexdigest()!=h:raise ValueError('File SHA mismatch '+name)
 for member in z.infolist():
  if not (out/member.filename).resolve().is_relative_to(out):raise ValueError('Unsafe ZIP path')
 z.extractall(out)
print('RESTORE_VERIFIED',len(manifest),meta['zip_sha256'])
