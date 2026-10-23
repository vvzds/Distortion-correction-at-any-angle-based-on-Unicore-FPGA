from pathlib import Path
import hashlib,json,sys
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 root=Path(__file__).resolve().parent
 rows=json.loads((root/'files_sha256.json').read_text(encoding='utf-8'))
 failures=[]
 for r in rows:
  p=(root/r['path']).resolve()
  if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:failures.append(r['path'])
 print(json.dumps(dict(status='FAIL' if failures else 'PASS',files=len(rows),failures=failures),ensure_ascii=False))
 return 1 if failures else 0
if __name__=='__main__':sys.exit(main())
