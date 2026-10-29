"""Rebuild the supplied release ZIP with the predictive GUI overlay."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


OVERLAY = {
    'README.md': 'package_README.md',
    'release/README.txt': 'release_README.txt',
    'host/gui.py': 'gui.py',
    'host/motion.py': 'motion.py',
    'host/protocol.py': 'protocol.py',
    'tools/check_motion.py': 'check_motion.py',
    'MOTION_CONTROL.md': 'MOTION_CONTROL.md',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_zip', type=Path)
    parser.add_argument('overlay_dir', type=Path)
    parser.add_argument('output_zip', type=Path)
    args = parser.parse_args()
    overlay = {f'pango-undistort/{target}': (args.overlay_dir / source).read_bytes()
               for target, source in OVERLAY.items()}

    with zipfile.ZipFile(args.original_zip) as original:
        entries = {item.filename: (item, original.read(item.filename))
                   for item in original.infolist() if not item.is_dir()}

    entries.update({name: (zipfile.ZipInfo(name), data)
                    for name, data in overlay.items()})
    file_hashes = {name.removeprefix('pango-undistort/'): hashlib.sha256(data).hexdigest()
                   for name, (_, data) in entries.items()
                   if name != 'pango-undistort/DELIVERY_SHA256.json'}
    manifest_name = 'pango-undistort/DELIVERY_SHA256.json'
    entries[manifest_name] = (zipfile.ZipInfo(manifest_name),
                              (json.dumps(file_hashes, indent=2) + '\n').encode())

    args.output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output_zip, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as output:
        for name, (info, data) in sorted(entries.items()):
            output.writestr(info, data)
    digest = hashlib.sha256(args.output_zip.read_bytes()).hexdigest()
    args.output_zip.with_suffix('.sha256').write_text(
        f'{digest}  {args.output_zip.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(args.output_zip), 'sha256': digest,
                      'entries': len(entries)}, indent=2))


if __name__ == '__main__':
    main()
