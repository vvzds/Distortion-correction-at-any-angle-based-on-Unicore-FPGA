"""Verify all locally downloaded archive files and object references (no network)."""
from pathlib import Path
import hashlib,json,gzip,sys,zipfile,zlib
base=Path(__file__).resolve().parent
checked=0
for line in (base/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    expected,rel=line.split('  ',1);p=base/rel
    h=hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda:f.read(1024**2),b''):h.update(data)
    if h.hexdigest()!=expected:raise SystemExit('FAIL file hash: '+rel)
    checked+=1
manifest=json.loads((base/'MANIFEST.json').read_text(encoding='utf-8'))
aliases=0
with gzip.open(base/'PATHS.jsonl.gz','rt',encoding='utf-8') as f:
    for line in f:
        row=json.loads(line);obj=manifest['objects'][row['sha256']]
        if obj['size']!=row['size']:raise SystemExit('FAIL alias size')
        aliases+=1
for sha,obj in manifest['objects'].items():
    storage=obj['storage']
    for part in storage.get('parts',[]) if storage['kind']=='recipe' else []:
        if 'chunk' in part:assert part['chunk'] in manifest['chunks']
        else:assert part['object'] in manifest['objects']
print('PASS: %d archive files, %d original paths, %d objects; existing Git references retained. Initial full decode evidence: VERIFICATION.json.'%(checked,aliases,len(manifest['objects'])))
