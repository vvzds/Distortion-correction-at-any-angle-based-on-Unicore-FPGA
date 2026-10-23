"""Rebuild either recipient ZIP from this directory and existing G7 archive parts."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--recipient',choices=['1','2'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--evidence-zip',type=Path);a=p.parse_args()
 cfg=json.loads((ROOT/'bundle_sources.json').read_text(encoding='utf-8'))[a.recipient]
 if a.out.exists():raise SystemExit('Output exists; use a new filename')
 a.out.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(a.out,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
  for row in cfg['members']:
   info=zipfile.ZipInfo(row['name'],date_time=(2026,10,23,0,0,0));info.create_system=0;info.external_attr=0x20;info.file_size=row['bytes'];info.compress_type=zipfile.ZIP_STORED
   if 'file' in row:paths=[ROOT/row['file']];parts=None
   elif a.evidence_zip:paths=[a.evidence_zip];parts=None
   else:
    idxpath=ROOT/row['parts_manifest'];parts=json.loads(idxpath.read_text(encoding='utf-8'))
    assert parts['sha256']==row['sha256'] and parts['bytes']==row['bytes']
    paths=[idxpath.parent/r['path'] for r in parts['parts']]
   h=hashlib.sha256();size=0
   with z.open(info,'w',force_zip64=True) as dest:
    for i,path in enumerate(paths):
     ph=hashlib.sha256();ps=0
     with path.open('rb') as f:
      for b in iter(lambda:f.read(1048576),b''):
       dest.write(b);h.update(b);ph.update(b);size+=len(b);ps+=len(b)
     if parts:assert ph.hexdigest()==parts['parts'][i]['sha256'] and ps==parts['parts'][i]['bytes']
   assert h.hexdigest()==row['sha256'] and size==row['bytes'],row['name']
 h=digest(a.out)
 if cfg.get('zip_sha256'):assert h==cfg['zip_sha256']
 print(json.dumps(dict(file=str(a.out),bytes=a.out.stat().st_size,sha256=h),ensure_ascii=False))
if __name__=='__main__':main()
