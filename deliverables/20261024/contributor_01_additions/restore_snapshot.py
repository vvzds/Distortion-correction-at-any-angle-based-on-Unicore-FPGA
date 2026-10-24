"""Restore a byte-exact review snapshot from new files and existing Git archives."""
import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def safe_relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value or ':' in value:
        raise ValueError('Unsafe relative path: ' + value)
    return Path(*path.parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--git', default='git')
    parser.add_argument('--local-archive-map', type=Path,
                        help='Optional JSON mapping repository archive paths to local byte-identical ZIPs')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    manifest = json.loads((here/'SNAPSHOT_MANIFEST.json').read_text(encoding='utf-8'))
    cache_map = json.loads(args.local_archive_map.read_text(encoding='utf-8')) if args.local_archive_map else {}
    if args.out.exists():
        parser.error('--out must not already exist')
    # Validate every destination before creating the output directory.
    for row in manifest['files']:
        safe_relative(row['path'])
    args.out.mkdir(parents=True)
    git_cache, zip_cache = {}, {}

    def base_bytes(path):
        if path not in git_cache:
            if path in cache_map:
                data = Path(cache_map[path]).read_bytes()
            else:
                data = subprocess.check_output([args.git, '-C', str(args.repo), 'show',
                                                manifest['base_commit']+':'+path])
            expected = manifest['base_blobs'][path]
            if git_blob_sha(data) != expected:
                raise ValueError('Base Git blob mismatch: '+path)
            git_cache[path] = data
        return git_cache[path]

    def archive_member(locator):
        parts = locator.split('!/')
        key = parts[0]
        if key not in zip_cache:
            zip_cache[key] = zipfile.ZipFile(io.BytesIO(base_bytes(key)))
        for member in parts[1:-1]:
            next_key = key+'!/'+member
            if next_key not in zip_cache:
                zip_cache[next_key] = zipfile.ZipFile(io.BytesIO(zip_cache[key].read(member)))
            key = next_key
        return zip_cache[key].read(parts[-1])

    count = 0
    try:
        for row in manifest['files']:
            storage = row['storage']
            if storage['kind'] == 'payload':
                data = (here/safe_relative(storage['path'])).read_bytes()
            elif storage['kind'] == 'git':
                data = base_bytes(storage['path'])
            elif storage['kind'] == 'archive':
                data = archive_member(storage['path'])
            else:
                raise ValueError('Unknown storage kind')
            if len(data) != row['bytes'] or sha256(data) != row['sha256']:
                raise ValueError('Snapshot hash mismatch: '+row['path'])
            target = args.out/safe_relative(row['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            count += 1
    finally:
        for archive in zip_cache.values():
            archive.close()
    print(f'PASS restored {count} files; every byte count and SHA256 verified')


if __name__ == '__main__':
    main()
