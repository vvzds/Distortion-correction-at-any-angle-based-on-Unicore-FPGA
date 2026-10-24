"""Verify approved G4 scope and collect current simulation evidence."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest().upper()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def tsv(path, header, rows):
    with (ROOT/path).open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t', lineterminator='\n')
        writer.writerow(header)
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-dir', type=Path, required=True)
    args = ap.parse_args()
    paths = git('ls-tree', '-r', '--name-only', '3e50aae', 'source/rtl', 'sim').decode().splitlines()
    assert len(paths) == 25
    changed = []
    rows = []
    for path in paths:
        before = git('rev-parse', '3e50aae:'+path).decode().strip()
        current = git('hash-object', path).decode().strip()
        same = before == current
        if not same:
            changed.append(path)
        rows.append([path, before, current, str(same).lower()])
    assert changed == ['source/rtl/undistort_core.v'], changed
    tsv('verification/g4_baseline_files.tsv',
        ['path', 'g3_3e50aae_git_blob', 'current_git_blob', 'unchanged'], rows)
    before = git('show', '3e50aae:source/rtl/undistort_core.v').decode()
    current = (ROOT/'source/rtl/undistort_core.v').read_text(encoding='utf-8')
    assert before.split(');', 1)[0] == current.split(');', 1)[0], 'core interface changed'
    (ROOT/'verification/g4_core_vs_g3.patch').write_bytes(
        git('diff', '3e50aae', '--', 'source/rtl/undistort_core.v'))
    source_paths = [f'source/rtl/{name}.v' for name in (
        'undistort_map', 'undistort_core', 'undistort_line_cache', 'undistort_bilinear')]
    source_paths += [f'sim/{name}' for name in (
        'undistort_map_tb.v', 'run_undistort_map.do',
        'undistort_map_g3_equiv_tb.v', 'run_undistort_map_g3_equiv.do',
        'undistort_core_sim_tb.v', 'undistort_core_t1_tb.v',
        'undistort_core_t2_tb.v', 'undistort_core_golden_tb.v', 'run_undistort_core.do',
        'undistort_core_g4_protocol_tb.v', 'run_undistort_core_g4_protocol.do',
        'undistort_line_cache_tb.v', 'run_undistort_line_cache.do')]
    source_paths += ['verification/g1_baseline/undistort_map_v12_ref.v']
    rows = []
    for path in source_paths:
        workspace = (ROOT/path).read_bytes()
        run = (args.run_dir/path).read_bytes()
        assert workspace == run, path
        rows.append([path, sha(workspace), sha(run), 'true'])
    tsv('verification/g4_sim_sources_sha256.tsv',
        ['path', 'workspace_sha256', 'run_copy_sha256', 'match'], rows)
    sim = args.run_dir/'sim'
    results = ['map_result.txt', 'map_g3_equiv_result.txt', 'line_cache_result.txt',
               'core_suite_result.txt', 'core_sim_result.txt', 'core_t1_result.txt',
               'core_t1_final_result.txt', 'core_t2_result.txt',
               'core_g4_protocol_result.txt', 'core_g4_protocol_sim_result.txt']
    results += [f'core_{t}_p{p}_result.txt' for t,p in (
        (3,0), (4,0), (51,0), (52,0), (53,0), (6,0), (3,1), (4,1))]
    for path in results:
        text = (sim/path).read_text()
        assert 'FAIL' not in text and 'TIMEOUT' not in text, path
        if path == 'core_t1_result.txt':
            lines = text.strip().splitlines()
            assert len(lines) == 2
            for index,line in enumerate(lines, 1):
                assert line.startswith(f'[T1 frame {index}] PASS err=0 pixels=2073600 ')
        else:
            assert 'ALL TESTS PASSED (err=0)' in text, path
    fault = (sim/'core_g4_fault_injection_result.txt').read_text()
    assert 'injected early request must FAIL' in fault and 'FAIL err=33' in fault
    assert 'ALL TESTS PASSED' not in fault and 'TIMEOUT' not in fault
    assert 'EXPECTED EARLY-REQUEST FAULT DETECTED' in (sim/'core_g4_protocol_console_full.log').read_text()
    assert 'CORE SUITE PASSED: T0-T9 (err=0)' in (sim/'core_suite_result.txt').read_text()
    logs = results + ['core_g4_fault_injection_result.txt', 'run_summary.txt']
    for prefix in ('core_suite', 'core_g4_protocol', 'map_g4', 'map_g4_equiv', 'cache_g4'):
        logs += [prefix+'_transcript.log', prefix+'_console_full.log']
    output = ROOT/'verification/logs/g4_20261018'
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in logs:
        shutil.copyfile(sim/name, output/name)
        data = (output/name).read_bytes()
        rows.append([(output/name).relative_to(ROOT).as_posix(), len(data), sha(data)])
    tsv('verification/g4_logs_sha256.tsv', ['path', 'bytes', 'sha256'], rows)
    report = {'production_changed': changed, 'unchanged_production': 3,
              'existing_sim_unchanged': 21, 'core_external_interface_unchanged': True,
              'run_copy_matches': len(source_paths), 'positive_result_files': len(results),
              'expected_fault_result': '33 injected early requests detected as FAIL',
              'logs': len(logs), 'g4_synthesis': 'NOT RUN', 'corr_top_pnr': 'NOT RUN: missing project/tool'}
    (ROOT/'verification/g4_evidence_summary.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))
    print('=== G4 EVIDENCE CHECKS PASSED ===')


if __name__ == '__main__':
    main()
