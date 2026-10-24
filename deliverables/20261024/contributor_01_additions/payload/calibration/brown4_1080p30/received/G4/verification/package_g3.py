"""Package tracked workspace bytes, then independently verify ZIP manifest."""
import csv
import hashlib
import io
import pathlib
import subprocess
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / 'undistort_core_stage2_v1.2_G3_candidate_20261018.zip'


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def main():
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)
    assert not status.strip(), 'Commit verified changes before packaging'
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    paths = sorted(p for p in paths if p)
    assert 'MANIFEST_SHA256.tsv' not in paths
    manifest = io.StringIO(newline='')
    writer = csv.writer(manifest, delimiter='\t', lineterminator='\n')
    writer.writerow(['path', 'bytes', 'sha256'])
    with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in paths:
            data = (ROOT / path).read_bytes()
            z.writestr(path, data)
            writer.writerow([path, len(data), digest(data)])
        z.writestr('MANIFEST_SHA256.tsv', manifest.getvalue().encode('utf-8'))
    with zipfile.ZipFile(OUTPUT) as z:
        assert z.testzip() is None
        rows = list(csv.DictReader(io.StringIO(z.read('MANIFEST_SHA256.tsv').decode()), delimiter='\t'))
        assert len(z.namelist()) == len(rows) + 1
        for row in rows:
            data = z.read(row['path'])
            assert len(data) == int(row['bytes']) and digest(data) == row['sha256'], row['path']
            assert data == (ROOT / row['path']).read_bytes(), row['path']
    sha = digest(OUTPUT.read_bytes())
    OUTPUT.with_suffix('.zip.sha256').write_text(f'{sha}  {OUTPUT.name}\n', encoding='ascii')
    print(f'PASS: files={len(rows)+1}, manifest_rows={len(rows)}, missing=0, mismatch=0')
    print(f'{OUTPUT}\nbytes={OUTPUT.stat().st_size}\nSHA256={sha}')


if __name__ == '__main__':
    main()
