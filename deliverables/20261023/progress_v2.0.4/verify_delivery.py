from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parent
m=json.loads((R/'files_sha256.json').read_text(encoding='utf-8'))
for row in m['files']:
 p=(R/row['name']).resolve()
 if not p.is_relative_to(R) or not p.is_file():raise SystemExit('Missing/unsafe: '+row['name'])
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 if p.stat().st_size!=row['bytes'] or h.hexdigest()!=row['sha256']:raise SystemExit('Mismatch: '+row['name'])
print('PASS',len(m['files']),'files verified')
