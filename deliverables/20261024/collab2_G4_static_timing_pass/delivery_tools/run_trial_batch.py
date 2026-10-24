"""Run isolated native physical seeds sequentially; never program hardware."""
from pathlib import Path
import argparse
import datetime as dt
import json
import msvcrt
import os
import re
import subprocess
import sys


def save(path, record):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials', nargs='+', default=['seed_5', 'seed_6', 'seed_7', 'seed_8'])
    parser.add_argument('--receipt-name', default='batch_receipt.json')
    args = parser.parse_args()
    assert all(re.fullmatch('seed_[0-9]+(?:_[a-z0-9_]+)?', name) for name in args.trials)
    assert re.fullmatch(r'[a-z0-9_]+\.json', args.receipt_name)
    base = Path(__file__).resolve().parent
    lock = (base / 'native_batch.lock').open('a+b')
    if lock.seek(0, 2) == 0:
        lock.write(b'0')
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        print('Another batch is running. Do not launch a second copy.', flush=True)
        lock.close()
        return 3
    receipt = dict(state='RUNNING', started=dt.datetime.now().astimezone().isoformat(),
                   pid=os.getpid(), synthetic=False, programmed=False, uart_sent=False, trials=[])
    receipt_path = base / args.receipt_name
    save(receipt_path, receipt)
    code = 2
    try:
        for label in args.trials:
            root = base / label
            old = set((root / 'checked_runs').glob('*/receipt.json'))
            print('Starting isolated native PDS trial: ' + label, flush=True)
            result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(root / 'checked_build.py')], cwd=root)
            new = set((root / 'checked_runs').glob('*/receipt.json')) - old
            if len(new) != 1:
                raise RuntimeError('EXPECTED_EXACTLY_ONE_NEW_RECEIPT')
            path = next(iter(new))
            record = json.loads(path.read_text(encoding='utf-8'))
            receipt['trials'].append(dict(trial=label, returncode=result.returncode,
                                           receipt=str(path), state=record['state'], error=record.get('error')))
            save(receipt_path, receipt)
            if result.returncode == 0 and record['state'] == 'BUILD_PASSED_BOARD_TEST_PENDING':
                receipt.update(state='BUILD_PASSED_BOARD_TEST_PENDING',
                               release_bitstream=record['release_bitstream'],
                               release_bitstream_sha256=record['release_bitstream_sha256'])
                code = 0
                break
            if record.get('error') != 'TIMING_GATE_REJECTED: no bitstream generation requested':
                raise RuntimeError('NON_TIMING_FAILURE_STOP: ' + str(record.get('error')))
        else:
            receipt['state'] = 'ALL_TRIALS_TIMING_REJECTED_NO_RELEASE'
    except Exception as exc:
        receipt.update(state='STOPPED_NO_RELEASE', error=str(exc))
    finally:
        receipt['ended'] = dt.datetime.now().astimezone().isoformat()
        save(receipt_path, receipt)
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()
    print('BATCH RESULT: ' + receipt['state'], flush=True)
    print('RECEIPT: ' + str(receipt_path), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
