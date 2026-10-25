"""Reconstruct and verify complete M10 ZIP from ordered GitHub parts."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args();root=Path(__file__).resolve().parent;out=a.out.resolve()
    if out.exists():raise ValueError('Output must not exist')
    meta=json.loads((root/'PACKAGE.json').read_text(encoding='utf-8'))
    for part in meta['parts']:
        p=root/part['path']
        if p.stat().st_size!=part['bytes'] or sha(p)!=part['sha256']:raise ValueError('Part mismatch')
    out.mkdir(parents=True)
    zpath=out/meta['zip_name']
    with zpath.open('xb') as f:
        for part in meta['parts']:
            with (root/part['path']).open('rb') as source:
                for block in iter(lambda:source.read(1024*1024),b''):f.write(block)
    if sha(zpath)!=meta['zip_sha256']:raise ValueError('ZIP mismatch')
    with zipfile.ZipFile(zpath) as z:
        if z.testzip():raise ValueError('CRC failure')
        manifest_raw=z.read('MANIFEST_SHA256.json')
        if hashlib.sha256(manifest_raw).hexdigest()!=meta['manifest_sha256']:raise ValueError('Manifest mismatch')
        manifest=json.loads(manifest_raw)
        for row in manifest['files']:
            data=z.read(row['path'])
            if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('File mismatch')
        for member in z.infolist():
            target=(out/member.filename).resolve()
            if not target.is_relative_to(out):raise ValueError('ZIP path escape')
        z.extractall(out)
    print('RESTORE_VERIFIED',meta['files'],meta['zip_sha256'])
