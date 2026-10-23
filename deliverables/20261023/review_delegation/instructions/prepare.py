"""Verify selected archive identities and extract read-only source copies; never runs input tools."""
from pathlib import Path,PurePosixPath
import argparse,json,zipfile,hashlib,stat
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def unpack(p,out):
 out=out.resolve();seen=set()
 with zipfile.ZipFile(p) as z:
  for i in z.infolist():
   name=i.filename.replace('\\','/');rel=PurePosixPath(name)
   target=(out/name).resolve()
   if rel.is_absolute() or ':' in name or '..' in rel.parts or not target.is_relative_to(out) or stat.S_ISLNK(i.external_attr>>16):raise ValueError('Unsafe member: '+name)
   key=name.rstrip('/').casefold()
   if key in seen:raise ValueError('Duplicate member: '+name)
   seen.add(key)
  out.mkdir(parents=True,exist_ok=False)
  for i in z.infolist():
   target=out/i.filename.replace('\\','/')
   if i.is_dir():target.mkdir(parents=True,exist_ok=True)
   else:
    target.parent.mkdir(parents=True,exist_ok=True)
    with z.open(i) as source,target.open('xb') as dest:
     for b in iter(lambda:source.read(8*1024*1024),b''):dest.write(b)
 return [str(p) for p in out.iterdir() if p.is_dir()]
def main():
 root=Path(__file__).resolve().parent;rows=json.loads((root/'archives.json').read_text(encoding='utf-8'))
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--select',nargs='+',choices=list(rows),required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if len(set(a.select))!=len(a.select):raise ValueError('Duplicate selection')
 if a.out.exists():raise FileExistsError('Use a new directory')
 for key in a.select:
  r=rows[key];f=root/r['path']
  if f.stat().st_size!=r['bytes'] or sha(f)!=r['sha256']:raise ValueError('Archive identity mismatch: '+key)
 a.out.mkdir(parents=True);result={}
 for key in a.select:
  result[key]=dict(path=str((a.out/key).resolve()),roots=unpack(root/rows[key]['path'],a.out/key),archive_sha256=rows[key]['sha256'])
  if key=='COMPARE':
   base=a.out/key/'AB_G8_M01_review_20261023/received'
   for prefix,label in [('G4_AB_R1_R4','AB_candidate'),('FPGA参数包','PARAMETERS')]:
    candidates=list(base.glob(prefix+'*.zip'))
    if len(candidates)!=1:raise ValueError('Ambiguous nested archive '+prefix)
    result[label]=dict(path=str((a.out/label).resolve()),roots=unpack(candidates[0],a.out/label),archive_sha256=sha(candidates[0]))
 (a.out/'prepared_paths.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
