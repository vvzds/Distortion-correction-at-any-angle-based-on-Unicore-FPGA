"""Collect sessions for human board-trial return; does not upload anything."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def export(root=ROOT):
    sessions = root / 'sessions'
    files = sorted(path for path in sessions.rglob('*') if path.is_file()) if sessions.exists() else []
    if not files:
        raise ValueError('No session records yet; run preview/demo/track first')
    notes = root / '板测记录_请填写.md'
    if notes.exists():
        files.append(notes)
    for filename in ('README_板测.md', '04_reference/本轮回传分析与改动.md'):
        if (root / filename).exists():
            files.append(root / filename)
    target = root / ('board_return_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.zip')
    manifest = []
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            archive.write(path, relative, compress_type=(zipfile.ZIP_STORED if path.suffix.lower() in
                          ('.png','.avi','.jpg','.jpeg') else zipfile.ZIP_DEFLATED))
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''):
                    digest.update(chunk)
            manifest.append(dict(file=relative, bytes=path.stat().st_size, sha256=digest.hexdigest()))
        archive.writestr('return_manifest.json', json.dumps(dict(
            package_version='manual-20261028-r2', files=manifest,
            note='Host timestamps and sent commands are not exposure/applied-frame acknowledgements'),
            ensure_ascii=False, indent=2))
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise OSError('Return ZIP CRC check failed')
    print('回传压缩包：', target, flush=True)
    print('请将该ZIP发回；原sessions目录保留。', flush=True)
    return target


if __name__ == '__main__':
    try:
        export()
    except Exception as exc:
        raise SystemExit('打包失败：' + str(exc))
