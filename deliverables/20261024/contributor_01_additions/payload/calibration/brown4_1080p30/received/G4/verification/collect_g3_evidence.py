"""Collect byte-exact G3 simulation and G2 source evidence; no RTL changes."""
import argparse
import csv
import hashlib
import io
import pathlib
import shutil
import subprocess
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def tsv(path, header, rows):
    with (ROOT / path).open('w', encoding='utf-8', newline='') as f:
        out = csv.writer(f, delimiter='\t', lineterminator='\n')
        out.writerow(header)
        out.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-dir', type=pathlib.Path, required=True)
    ap.add_argument('--g2-zip', type=pathlib.Path, required=True)
    ap.add_argument('--g2-review', type=pathlib.Path, required=True)
    ap.add_argument('--final', action='store_true')
    args = ap.parse_args()
    frozen = list(csv.DictReader(io.StringIO(
        (ROOT / 'verification/g2_frozen_files.tsv').read_text(encoding='utf-8')), delimiter='\t'))
    rows = []
    for row in frozen:
        path = row['path']
        current = git('hash-object', path).decode().strip()
        assert current == row['accepted_209ff75_git_blob'], path
        rows.append([path, row['accepted_209ff75_git_blob'], current, 'true'])
    tsv('verification/g3_frozen_files.tsv',
        ['path', 'accepted_209ff75_git_blob', 'current_git_blob', 'unchanged'], rows)
    rows = []
    old_sim = git('ls-tree', '-r', '--name-only', '1a6ef9d', 'sim').decode().splitlines()
    for path in old_sim:
        baseline = git('rev-parse', '1a6ef9d:' + path).decode().strip()
        current = git('hash-object', path).decode().strip()
        assert baseline == current, path
        rows.append([path, baseline, current, 'true'])
    assert len(rows) == 19
    tsv('verification/g3_existing_sim_files.tsv',
        ['path', 'g2_1a6ef9d_git_blob', 'current_git_blob', 'unchanged'], rows)
    files = [f'source/rtl/{name}.v' for name in (
        'undistort_map', 'undistort_core', 'undistort_line_cache', 'undistort_bilinear')]
    files += [f'sim/{name}' for name in (
        'undistort_map_tb.v', 'run_undistort_map.do',
        'undistort_map_g3_equiv_tb.v', 'run_undistort_map_g3_equiv.do',
        'undistort_core_sim_tb.v', 'undistort_core_t1_tb.v',
        'undistort_core_t2_tb.v', 'undistort_core_golden_tb.v', 'run_undistort_core.do')]
    files += ['verification/g1_baseline/undistort_map_v12_ref.v']
    rows = []
    for path in files:
        workspace = (ROOT / path).read_bytes()
        run_copy = (args.run_dir / path).read_bytes()
        assert workspace == run_copy, path
        rows.append([path, sha(workspace), sha(run_copy), 'true'])
    tsv('verification/g3_sim_sources_sha256.tsv',
        ['path', 'workspace_sha256', 'run_copy_sha256', 'match'], rows)
    rows = []
    archive_dir = ROOT / 'verification/design_g2_sp64_20261018'
    with zipfile.ZipFile(args.g2_zip) as z:
        for member in z.infolist():
            if member.is_dir():
                continue
            target = archive_dir / pathlib.PurePosixPath(member.filename).name
            data = z.read(member)
            assert target.read_bytes() == data, member.filename
            rows.append([member.filename, target.relative_to(ROOT).as_posix(),
                         len(data), sha(data), 'true'])
    data = args.g2_review.read_bytes()
    target = archive_dir / '接收审查结论_设计方.md'
    assert target.read_bytes() == data
    rows.append([args.g2_review.name, target.relative_to(ROOT).as_posix(),
                 len(data), sha(data), 'true'])
    tsv('verification/g2_sp64_sources_sha256.tsv',
        ['original_member', 'archived_path', 'bytes', 'sha256', 'match'], rows)
    if args.final:
        sim = args.run_dir / 'sim'
        names = ['map_result.txt', 'map_g3_equiv_result.txt',
                 'core_suite_result.txt', 'core_sim_result.txt',
                 'core_t1_result.txt', 'core_t1_final_result.txt', 'core_t2_result.txt']
        names += [f'core_{t}_p{p}_result.txt' for t, p in (
            (3, 0), (4, 0), (51, 0), (52, 0), (53, 0), (6, 0), (3, 1), (4, 1))]
        for name in names:
            content = (sim / name).read_text(errors='replace')
            if name == 'core_t1_result.txt':
                # 冻结TB的逐帧文件仅写两条逐帧PASS，总结在final文件。
                lines = content.strip().splitlines()
                assert len(lines) == 2, name
                for index, line in enumerate(lines, 1):
                    assert line.startswith(f'[T1 frame {index}] PASS err=0 pixels=2073600 '), name
            else:
                assert 'ALL TESTS PASSED (err=0)' in content, name
            assert 'FAIL' not in content and 'TIMEOUT' not in content, name
        assert '=== CORE SUITE PASSED: T0-T9 (err=0) ===' in (
            sim / 'core_suite_result.txt').read_text()
        names += ['map_g3_transcript.log', 'map_g3_console_full.log',
                  'map_g3_equiv_transcript.log', 'map_g3_equiv_console_full.log',
                  'core_suite_transcript.log', 'core_suite_console_full.log', 'run_summary.txt']
        output = ROOT / 'verification/logs/g3_20261018'
        output.mkdir(parents=True, exist_ok=True)
        rows = []
        for name in names:
            shutil.copyfile(sim / name, output / name)
            data = (output / name).read_bytes()
            rows.append([(output / name).relative_to(ROOT).as_posix(), len(data), sha(data)])
        tsv('verification/g3_logs_sha256.tsv', ['path', 'bytes', 'sha256'], rows)
    print('PASS: G3 frozen, historical tests, run-copy, G2 original hashes' +
          (' and simulation results/logs' if args.final else ''))


if __name__ == '__main__':
    main()
