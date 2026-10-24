"""Read native-run evidence; copies only completed trials into this workspace."""
from pathlib import Path
import argparse
import datetime as dt
import json
import re
import shutil
import time

import checked_build as gate
from prepare_batch import summarize


TASK = Path(__file__).resolve().parent
OUT = TASK.parents[1] / 'outputs/static_G4_timing_resume_20261024'
BASE = Path('D:/FPGA PDS/yx/static_G4_timing_resume_20261024')


def extract_tables(report):
    tables = summarize(report)
    for table in tables['summaries']:
        rows = []
        for line in table['table'].splitlines():
            match = re.fullmatch(r'\s*(\S+)\s+(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*', line)
            if match:
                rows.append(dict(launch=match[1], capture=match[2], worst_ns=float(match[3]),
                                 total_negative_ns=float(match[4]), failed_endpoints=int(match[5]),
                                 total_endpoints=int(match[6])))
        table['rows'] = rows
    return tables


def collect(trial_name=None):
    batch_path = BASE / 'batch_receipt.json'
    batch = json.loads(batch_path.read_text(encoding='utf-8')) if batch_path.exists() else dict(state='NOT_STARTED', trials=[])
    records = []
    trials = [(seed, 'seed_' + str(seed)) for seed in (5, 6, 7, 8)]
    if trial_name:
        assert re.fullmatch('seed_[0-9]+_[a-z0-9_]+', trial_name)
        trials = [(int(trial_name.split('_')[1]), trial_name)]
        batch = dict(state='NOT_STARTED', trials=[])
    for seed, label in trials:
        root = BASE / label
        found = sorted((root / 'checked_runs').glob('*/receipt.json'))
        if not found:
            continue
        path = found[-1]
        record = json.loads(path.read_text(encoding='utf-8'))
        row = dict(seed=seed, label=label, state=record['state'], run=str(path.parent), error=record.get('error'))
        if trial_name:
            batch['state'] = record['state'] if record['state'] in ('FAILED_NO_RELEASE', 'BUILD_PASSED_BOARD_TEST_PENDING') else 'RUNNING'
        if record['state'] in ('FAILED_NO_RELEASE', 'BUILD_PASSED_BOARD_TEST_PENDING'):
            destination = OUT / ('single_native_evidence' if trial_name else 'batch_native_evidence') / label / path.parent.name
            marker = destination / 'COLLECTED.json'
            if not marker.exists():
                destination.mkdir(parents=True, exist_ok=True)
                shutil.copytree(path.parent, destination / 'checked_run', dirs_exist_ok=True)
                for folder in ('report_timing', 'place_route'):
                    if (root / folder).is_dir():
                        shutil.copytree(root / folder, destination / folder, dirs_exist_ok=True)
                for name in ('trial_preparation.json', 'expected_inputs.json', 'checked_build.py',
                             'pnr_to_timing.tcl', 'bitstream_only.tcl', 'build_to_timing.tcl',
                             'full_source_1080p30.pds', gate.PROJECT):
                    shutil.copy2(root / name, destination / name)
                report = destination / 'report_timing' / (gate.TOP + '.rtr')
                if report.is_file():
                    gate.save(destination / 'timing_summary.json', extract_tables(report))
                gate.save(marker, dict(collected=dt.datetime.now().astimezone().isoformat(),
                                       seed=seed, source_run=str(path.parent), native_result=record['state'],
                                       source_input_hashes_unchanged=gate.inputs(root) == record['inputs_before'],
                                       programmed=False, uart_sent=False))
                gate.save(destination / 'SHA256.json', {p.relative_to(destination).as_posix(): gate.sha(p)
                           for p in sorted(destination.rglob('*')) if p.is_file() and p.name != 'SHA256.json'})
            summary = destination / 'timing_summary.json'
            if summary.exists():
                tables = json.loads(summary.read_text(encoding='utf-8'))
                row['violated_paths'] = [{key: value for key, value in entry.items() if key != 'full_path'}
                                         for entry in tables['violated_paths']]
                row['failed_endpoints_total_in_summary'] = sum(r['failed_endpoints'] for t in tables['summaries'] for r in t['rows'])
                row['ddr125_slow_setup'] = next((r for t in tables['summaries'] if t['kind'] == 'Setup' and t['corner'] == 'Slow'
                                                for r in t['rows'] if r['launch'] == r['capture'] == 'ddrphy_sysclk'), None)
            row['workspace_evidence'] = str(destination)
            row['release_bitstream'] = record.get('release_bitstream')
            row['release_bitstream_sha256'] = record.get('release_bitstream_sha256')
        else:
            log = path.parent / ('bitstream.log' if record['state'] == 'BITSTREAM_RUNNING' else 'timing.log')
            if log.exists():
                raw = log.read_text(encoding='utf-8', errors='replace')
                phases = re.findall(r'^.*(?:Phase .* started\.|Detailed routing takes \d+ iterations|Start fix hold violation|Process ".*" (?:started|done)\.).*$', raw, re.M)
                row['last_phase'] = phases[-1].strip() if phases else 'Starting'
        records.append(row)
    result = dict(observed=dt.datetime.now().astimezone().isoformat(), batch_state=batch['state'],
                  synthetic=False, trials=records, programmed=False, uart_sent=False)
    OUT.mkdir(parents=True, exist_ok=True)
    gate.save(OUT / ('native_' + trial_name + '_progress.json' if trial_name else 'native_batch_progress.json'), result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--trial')
    args = parser.parse_args()
    previous = None
    began = time.monotonic()
    while True:
        result = collect(args.trial)
        current = json.dumps({key: value for key, value in result.items() if key != 'observed'}, ensure_ascii=False)
        if current != previous:
            compact = dict(observed=result['observed'], state=result['batch_state'],
                           trials=[{key: row[key] for key in ('label', 'state', 'last_phase', 'ddr125_slow_setup',
                                   'failed_endpoints_total_in_summary', 'release_bitstream') if key in row}
                                   for row in result['trials']])
            print(json.dumps(compact, ensure_ascii=False), flush=True)
            previous = current
        if not args.watch or result['batch_state'] not in ('RUNNING', 'NOT_STARTED'):
            return
        if time.monotonic() - began > 1800:
            print('WATCH_TIMEOUT; native batch left running, no process terminated.', flush=True)
            return
        time.sleep(10)


if __name__ == '__main__':
    main()
