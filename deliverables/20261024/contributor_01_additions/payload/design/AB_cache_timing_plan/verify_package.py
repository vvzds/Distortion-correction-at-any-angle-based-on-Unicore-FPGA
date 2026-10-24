from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
records=json.loads((root/'files_sha256.json').read_text(encoding='utf-8'))
errors=[]
for item in records:
    p=root/item['path']
    if not p.is_file():errors.append('missing '+item['path']);continue
    if p.stat().st_size!=item['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:
        errors.append('mismatch '+item['path'])
if errors:
    print('\n'.join(errors));raise SystemExit(1)
print('PASS',len(records),'files; package integrity only, no RTL or physical acceptance')
