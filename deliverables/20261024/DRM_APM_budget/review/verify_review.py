from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parent
rows=json.loads((root/'files_sha256.json').read_text(encoding='utf-8'));bad=[]
for r in rows:
 p=(root/r['path']).resolve()
 if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size!=r['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:bad.append(r['path'])
print(json.dumps(dict(status='FAIL' if bad else 'PASS',files=len(rows),failures=bad),ensure_ascii=False));sys.exit(bool(bad))
