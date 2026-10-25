"""Run the accepted M02 producer in a fresh directory; never opens UART.

python run_calibration.py --images calib --out runs/new --cb 11 8
python run_calibration.py --verify runs/new/receipt.json
"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import uuid

CALIBRATE_SHA = 'e7581eedb1b62090eef15d0d083eb58b41f21b1965438613c45acc2fa7862ebe'
NAMES = ('fx', 'fy', 'cx', 'cy', 'k1', 'k2', 'p1', 'p2')
LIMITS = ((128, 32767.99), (128, 32767.99), (0, 1919), (0, 1079),
          (-.5, .5), (-.5, .5), (-.01, .01), (-.01, .01))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    def bad(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=bad)


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                    allow_nan=False) + '\n', encoding='utf-8')


def check_result(result):
    """Independent wire oracle; does not call producer or UART helpers."""
    require(result.get('g02_pass') is True, 'Calibration G02 must be true')
    require(result.get('calib_flags') == 'CALIB_FIX_K3', 'Brown4 flag mismatch')
    d = result.get('dist_full')
    require(isinstance(d, list) and len(d) == 5 and d[4] == 0, 'k3 must be fixed zero')
    require(all(type(v) in (float, int) and math.isfinite(v) for v in d), 'Nonfinite distortion')
    require(all(d[i] == result[n] for i, n in enumerate(NAMES[4:])), 'Distortion evidence mismatch')
    integers = []
    for name, (lo, hi) in zip(NAMES, LIMITS):
        value = result[name]
        require(type(value) in (float, int) and math.isfinite(value), 'Nonfinite ' + name)
        require(lo <= value <= hi, 'Source range ' + name)
        word = round(value * 65536)
        require(-2**31 <= word < 2**31, 'Signed Q16 overflow ' + name)
        require(lo <= word / 65536 <= hi, 'Quantized range ' + name)
        require(abs(word / 65536 - value) <= .5 / 65536, 'Roundtrip ' + name)
        integers.append(word)
    payload = struct.pack('<8i', *integers)
    frame = b'\xaa\x55\x01\x20' + payload + bytes([sum(payload) & 255])
    require(bytes.fromhex(result['uart01_frame']) == frame, 'Wire bytes mismatch')
    return frame


def local_file(root, relative):
    require(isinstance(relative, str) and not Path(relative).is_absolute(), 'Relative file required')
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), 'File escapes run directory')
    return path


def verify(receipt_path):
    path = Path(receipt_path).resolve()
    receipt = load(path)
    require(receipt['status'] == 'VALIDATED_OFFLINE', 'Run is not validated')
    require(receipt['returncode'] == 0 and receipt['run_id'], 'Producer failed')
    require(receipt['source']['sha256'] == CALIBRATE_SHA, 'Unaccepted producer version')
    require(sha(receipt['source']['path']) == CALIBRATE_SHA, 'Live producer changed')
    require(sha(receipt['runner']['path']) == receipt['runner']['sha256'], 'Runner changed')
    for row in receipt['inputs']:
        require(sha(row['path']) == row['sha256'], 'Calibration input changed')
    for name, digest in receipt['artifacts'].items():
        require(sha(local_file(path.parent, name)) == digest, 'Artifact hash mismatch: ' + name)
    frame = check_result(load(path.parent / 'calib_result.json'))
    require(bytes.fromhex((path.parent / 'validated_uart01.hex').read_text()) == frame,
            'Validated frame changed')
    return receipt


def run(images, out, cb=(11, 8), square_m=.025, timeout=600, scratch=None):
    source = Path(__file__).resolve().with_name('calibrate.py')
    require(sha(source) == CALIBRATE_SHA, 'Producer is not accepted M02 version')
    images = Path(images).resolve()
    out = Path(out).resolve()
    require(images.is_dir(), 'Image directory missing')
    require(not out.exists(), 'Use a new output directory; old output is preserved')
    require(not out.is_relative_to(images) and not images.is_relative_to(out),
            'Output and image directories must be separate')
    require(len(cb) == 2 and all(type(v) is int and v >= 2 for v in cb), 'Invalid board')
    require(math.isfinite(square_m) and square_m > 0, 'Invalid square size')
    require(math.isfinite(timeout) and timeout > 0, 'Invalid timeout')
    files = sorted(list(images.glob('*.png')) + list(images.glob('*.bmp')))
    inputs = [dict(path=str(p), sha256=sha(p), bytes=p.stat().st_size) for p in files]
    producer_images = images
    stage = None
    if any(not str(p).isascii() for p in files):
        require(scratch is not None, 'Non-ASCII image paths require --scratch with an ASCII directory')
        scratch = Path(scratch).resolve()
        require(str(scratch).isascii(), 'Scratch directory must be ASCII')
        require(not scratch.is_relative_to(images) and not scratch.is_relative_to(out)
                and not images.is_relative_to(scratch) and not out.is_relative_to(scratch),
                'Scratch must be separate from input and output')
        require(all(p.name.isascii() for p in files), 'Image basenames must be ASCII; preserve a mapping before renaming')
        stage = scratch / ('m02_' + uuid.uuid4().hex)
        stage.mkdir(parents=True, exist_ok=False)
        for p in files:
            shutil.copyfile(p, stage / p.name)
            require(sha(stage / p.name) == sha(p), 'Staged image hash mismatch')
        producer_images = stage
    out.mkdir(parents=True, exist_ok=False)
    now = lambda: dt.datetime.now(dt.timezone.utc).isoformat()
    cmd = [sys.executable, *(['-O'] if sys.flags.optimize else []), '-B', '-X', 'utf8',
           str(source), '--dir', str(producer_images), '--cb', *map(str, cb), '--sq', str(square_m)]
    receipt = dict(schema_version=1, run_id=uuid.uuid4().hex, started_at=now(),
                   status='RUNNING', source=dict(path=str(source), sha256=sha(source)),
                   runner=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)),
                   inputs=inputs, argv=cmd, cwd=str(out), returncode=None,
                   uart_opened=False, uart_bytes_sent=0, quality_acceptance='NOT_EVALUATED',
                   artifacts={})
    receipt['staging'] = None if stage is None else dict(path=str(stage), byte_identical=True,
                                                        cleanup='Retained until task archival')
    save(out / 'receipt.json', receipt)
    try:
        with (out / 'stdout.log').open('xb') as stdout, (out / 'stderr.log').open('xb') as stderr:
            process = subprocess.Popen(cmd, cwd=out, stdout=stdout, stderr=stderr,
                                       env=dict(os.environ, PYTHONIOENCODING='utf-8',
                                                PYTHONDONTWRITEBYTECODE='1'))
            receipt['pid'] = process.pid
            try:
                receipt['returncode'] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                receipt['returncode'] = process.wait(timeout=30)
                raise ValueError('Calibration timed out')
        require(receipt['returncode'] == 0, 'Producer failed; see stderr.log')
        require(all(sha(row['path']) == row['sha256'] for row in inputs), 'Inputs changed during run')
        if stage is not None:
            require(all(sha(stage / Path(row['path']).name) == row['sha256'] for row in inputs),
                    'Staged inputs changed during run')
        require(sha(source) == CALIBRATE_SHA, 'Producer changed during run')
        frame = check_result(load(out / 'calib_result.json'))
        (out / 'validated_uart01.hex').write_text(frame.hex(' ') + '\n', encoding='ascii')
        receipt['status'] = 'VALIDATED_OFFLINE'
    except Exception as exc:
        receipt['status'] = 'REJECTED'
        receipt['reason'] = str(exc)
    receipt['finished_at'] = now()
    receipt['artifacts'] = {p.name: sha(p) for p in out.iterdir()
                            if p.is_file() and p.name != 'receipt.json'}
    save(out / 'receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--cb', nargs=2, type=int, default=[11, 8])
    parser.add_argument('--square-m', type=float, default=.025)
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--scratch', type=Path, help='Separate ASCII folder for non-ASCII image paths')
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        result = verify(args.verify)
    else:
        require(args.images is not None and args.out is not None, '--images and --out required')
        result = run(args.images, args.out, args.cb, args.square_m, args.timeout, args.scratch)
    print(json.dumps(dict(status=result['status'], run_id=result['run_id'],
                          uart_bytes_sent=0), ensure_ascii=False))
    return 0 if result['status'] == 'VALIDATED_OFFLINE' else 3


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
