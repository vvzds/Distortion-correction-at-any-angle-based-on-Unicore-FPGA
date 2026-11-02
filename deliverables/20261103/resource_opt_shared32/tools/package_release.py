"""Package tracked sources plus text-only board evidence without raw captures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_RUNS = {
    '20261029_1454_seed3_normal_jtag',
    '20261029_1456_seed3_acceptance',
    '20261029_1458_seed3_sustained',
    '20261029_1501_seed3_angle_sweep',
    '20261029_1506_checker_complete',
    '20261029_1540_checker_repositioned',
    '20261029_1540_reprogram_for_checker',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path,
                        default=Path('D:/restart/deliverables'))
    parser.add_argument('--archive-name', default='pango_1080p30_software_release',
                        help='Basename for a separate release; keeps older archives intact')
    args = parser.parse_args()
    if Path(args.archive_name).name != args.archive_name or any(c in args.archive_name for c in '/\\:'):
        parser.error('Archive name must be a plain basename')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tracked = subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    files = {Path(name) for name in tracked if name}
    files.update({Path('release/board_acceptance.json'),
                  Path('tools/board_test.py'),
                  Path('tools/program_sram.py'),
                  Path('tools/analyze_board_checker.py'),
                  Path('tools/package_release.py')})
    evidence = ROOT / 'reports/board_runs'
    if evidence.exists():
        for run in ACCEPTED_RUNS:
            for path in (evidence / run).rglob('*'):
                if path.is_file() and path.suffix.lower() in {'.json', '.jsonl', '.txt'}:
                    files.add(path.relative_to(ROOT))
    files = sorted(p for p in files if (ROOT / p).is_file())

    hashes = {p.as_posix(): hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
              for p in files if p.as_posix() != 'DELIVERY_SHA256.json'}
    (ROOT / 'DELIVERY_SHA256.json').write_text(
        json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
    files = sorted(set(files) | {Path('DELIVERY_SHA256.json')})

    archive = args.output_dir / (args.archive_name+'.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as output:
        for path in files:
            output.write(ROOT / path, Path('pango-undistort') / path)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (args.output_dir / (args.archive_name+'.sha256')).write_text(
        f'{digest}  {archive.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(archive), 'files': len(files),
                      'sha256': digest, 'raw_board_captures_included': False}, indent=2))


if __name__ == '__main__':
    main()
