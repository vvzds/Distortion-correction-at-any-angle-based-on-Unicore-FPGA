"""Portable ZIP manifest verification. No extraction, third-party modules or tools."""
import argparse
import hashlib
import json
from pathlib import PurePosixPath
import zipfile

def verify(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate ZIP names')
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
                raise ValueError('unsafe ZIP name: ' + name)
        manifests = [name for name in names if len(PurePosixPath(name).parts) == 2
                     and name.endswith('/files_sha256.json')]
        if len(manifests) != 1:
            raise ValueError('expected one top-level files_sha256.json')
        manifest_name = manifests[0]
        prefix = manifest_name.rsplit('/', 1)[0] + '/'
        manifest = json.loads(z.read(manifest_name))
        expected = {prefix + item['file'] for item in manifest}
        if len(expected) != len(manifest) or expected | {manifest_name} != set(names):
            raise ValueError('manifest coverage mismatch')
        if z.testzip() is not None:
            raise ValueError('CRC mismatch')
        for item in manifest:
            h = hashlib.sha256()
            count = 0
            with z.open(prefix + item['file']) as stream:
                while True:
                    block = stream.read(1024 * 1024)
                    if not block:
                        break
                    h.update(block)
                    count += len(block)
            if count != item['bytes'] or h.hexdigest() != item['sha256']:
                raise ValueError('file mismatch: ' + item['file'])
        return dict(file=str(path), entries=len(names), verified_files=len(manifest),
                    status='PASS', scope='ZIP_CRC_MANIFEST_COVERAGE_SHA256_ONLY_NOT_RTL_SIGNOFF')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip_files', nargs='+')
    args = parser.parse_args()
    print(json.dumps([verify(p) for p in args.zip_files], ensure_ascii=False, indent=2))
