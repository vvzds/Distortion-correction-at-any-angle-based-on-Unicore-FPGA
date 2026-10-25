from pathlib import Path
import argparse,hashlib,json,zipfile
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
root=Path(__file__).resolve().parent;meta=json.loads((root/'PACKAGE.json').read_text(encoding='utf-8'))
out=args.out.resolve()
if out.exists():raise ValueError('Use a new output directory')
for r in meta['parts']:
 p=root/r['path']
 if p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:raise ValueError('Part SHA/size mismatch')
out.mkdir(parents=True);archive=out/meta['zip_name']
with archive.open('xb') as f:
 for r in meta['parts']:
  with (root/r['path']).open('rb') as part:
   for b in iter(lambda:part.read(1024*1024),b''):f.write(b)
if sha(archive)!=meta['zip_sha256']:raise ValueError('Complete ZIP SHA mismatch')
with zipfile.ZipFile(archive) as z:
 if z.testzip():raise ValueError('ZIP CRC mismatch')
 raw=z.read('MANIFEST_SHA256.json')
 if hashlib.sha256(raw).hexdigest()!=meta['manifest_sha256']:raise ValueError('Manifest mismatch')
 manifest=json.loads(raw)
 for name,h in manifest.items():
  if hashlib.sha256(z.read(name)).hexdigest()!=h:raise ValueError('Payload SHA mismatch '+name)
 for member in z.infolist():
  if not (out/member.filename).resolve().is_relative_to(out):raise ValueError('Unsafe archive path')
 z.extractall(out)
print('RESTORE_VERIFIED',len(manifest),'files',meta['zip_sha256'])
