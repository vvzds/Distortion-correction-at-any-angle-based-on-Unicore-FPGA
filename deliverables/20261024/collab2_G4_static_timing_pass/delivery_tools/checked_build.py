"""External, fail-closed PDS timing gate. No GUI, UART or programming actions."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import time

TOP = 'hdmi_ddr_ov5640_top'
PROJECT = 'task1_1080p30.pds'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def inputs(root):
    files = [root / name for name in ('HDMI_DDR3_OV5640_test.fdc', 'build_to_timing.tcl',
                                     'pnr_to_timing.tcl', 'bitstream_only.tcl')]
    files += [p for folder in ('source', 'ipcore') for p in (root / folder).rglob('*') if p.is_file()]
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(files)}


def inspect_timing(path, began):
    result = dict(exists=path.is_file(), fresh=False, summary_pass=False,
                  no_violated_path=False, fixed_clocks=False, passed=False)
    if not path.is_file():
        return result
    text = path.read_text(encoding='utf-8', errors='replace')
    result.update(sha256=sha(path), fresh=path.stat().st_mtime >= began - 1,
                  summary_pass=bool(re.search(r'^\s*Design Summary\s*:\s*All Constraints Met\.?\s*$', text, re.M)),
                  no_violated_path=not bool(re.search(r'Slack\s*\(VIOLATED\)|Some Constraints Violated', text)),
                  fixed_clocks=bool(re.search(r'^\s*ddrphy_sysclk\s+125\.0000\s+MHz', text, re.M))
                  and bool(re.search(r'^\s*pix_clk\s+74\.25\d*\s+MHz', text, re.M)))
    result['passed'] = all(result[key] for key in (
        'fresh', 'summary_pass', 'no_violated_path', 'fixed_clocks'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--pds-root', type=Path,
                        default=Path('D:/FPGA PDS/site/PDS_2022.2-SP6.1-win64'))
    parser.add_argument('--full', action='store_true', help='Rebuild from RTL instead of mapped checkpoint')
    args = parser.parse_args()
    root = args.project_dir.resolve()
    out = root / 'checked_runs' / dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    out.mkdir(parents=True, exist_ok=False)
    receipt_path = out / 'receipt.json'
    tool = args.pds_root / 'bin/pds_shell.exe'
    record = dict(state='PREFLIGHT', started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  cwd=str(root), phases=[], programmed=False, uart_sent=False,
                  release_bitstream=None, release_bitstream_sha256=None)
    save(receipt_path, record)
    try:
        if not tool.is_file():
            raise RuntimeError('PDS_TOOL_NOT_FOUND')
        before = inputs(root)
        expected = json.loads((root / 'expected_inputs.json').read_text(encoding='utf-8'))
        if before != expected:
            raise RuntimeError('INPUT_HASH_MISMATCH: review changed inputs before building')
        if not args.full:
            preparation = json.loads((root / 'trial_preparation.json').read_text(encoding='utf-8'))
            checkpoint = preparation['checkpoint_inputs']
            if any(sha(root / name) != digest for name, digest in checkpoint.items()):
                raise RuntimeError('MAPPED_CHECKPOINT_HASH_MISMATCH')
            record['checkpoint_inputs'] = checkpoint
        record.update(inputs_before=before, tool_sha256=sha(tool),
                      project_before_sha256=sha(root / PROJECT),
                      launcher_sha256=sha(Path(__file__)))
        fdc = (root / 'HDMI_DDR3_OV5640_test.fdc').read_text(encoding='utf-8')
        for port, ball in (('uart_rx', 'B24'), ('uart_tx', 'C24')):
            if not re.search(r'\{p:' + port + r'\}\s+\{PAP_IO_LOC\}\s+\{' + ball + r'\}', fdc):
                raise RuntimeError('UART_LOC_MISMATCH: ' + port)
        env = dict(os.environ)
        temp = root / 'task_temp'
        temp.mkdir(exist_ok=True)
        env.update(TEMP=str(temp), TMP=str(temp))
        env['PATH'] = str(tool.parent) + os.pathsep + env.get('PATH', '')

        def stage(name, argv):
            log = out / (name + '.log')
            row = dict(name=name, argv=argv, start_epoch=time.time(), exit_code=None)
            record['phases'].append(row)
            record['state'] = name.upper() + '_RUNNING'
            save(receipt_path, record)
            print('START ' + name + ': ' + str(log), flush=True)
            with log.open('wb') as stream:
                process = subprocess.Popen(argv, cwd=root, env=env, stdout=stream,
                                           stderr=subprocess.STDOUT)
                row['pid'] = process.pid
                save(receipt_path, record)
                row['exit_code'] = process.wait()
            row.update(elapsed_s=round(time.time() - row['start_epoch'], 3),
                       log_sha256=sha(log))
            raw = log.read_text(encoding='utf-8', errors='replace')
            row['errors'] = re.findall(r'^E:.*$', raw, re.M)
            save(receipt_path, record)
            if row['exit_code'] != 0 or row['errors']:
                raise RuntimeError(name.upper() + '_TOOL_FAILED: ' + repr(row['errors'][:3]))
            if inputs(root) != before:
                raise RuntimeError('BUILD_INPUTS_CHANGED_DURING_' + name.upper())
            return row, raw

        if args.full:
            argv = [str(tool), '-file', 'build_to_timing.tcl', '-work_dir', str(root),
                    '-project_name', PROJECT[:-4]]
        else:
            argv = [str(tool), '-file', 'pnr_to_timing.tcl', '-work_dir', str(root),
                    '-project_name', PROJECT[:-4]]
        timing_row, _ = stage('timing', argv)
        report = root / 'report_timing' / (TOP + '.rtr')
        record['timing_gate'] = inspect_timing(report, timing_row['start_epoch'])
        save(receipt_path, record)
        if not record['timing_gate']['passed']:
            raise RuntimeError('TIMING_GATE_REJECTED: no bitstream generation requested')
        shutil.copy2(report, out / 'reviewed_timing.rtr')
        route_db = root / 'place_route' / (TOP + '_pnr.adf')
        record['reviewed_route_sha256'] = sha(route_db)
        record['project_at_gate_sha256'] = sha(root / PROJECT)
        bit_row, bit_log = stage('bitstream', [str(tool), '-file', 'bitstream_only.tcl',
                                              '-work_dir', str(root), '-project_name', PROJECT[:-4]])
        if re.search(r'^Process "(?:Compile|Synthesize|Device Map|Place & Route)" started\.', bit_log, re.M):
            raise RuntimeError('UNREVIEWED_REBUILD_DURING_BITSTREAM_STAGE')
        if sha(report) != record['timing_gate']['sha256'] or sha(route_db) != record['reviewed_route_sha256']:
            raise RuntimeError('REVIEWED_REPORT_OR_ROUTE_CHANGED: do not release bitstream')
        bit = root / 'generate_bitstream' / (TOP + '.sbit')
        if not bit.is_file() or bit.stat().st_mtime < bit_row['start_epoch'] - 1:
            raise RuntimeError('FRESH_BITSTREAM_MISSING')
        release = out / 'qualified_for_board_test'
        release.mkdir()
        shutil.copy2(bit, release / bit.name)
        record.update(state='BUILD_PASSED_BOARD_TEST_PENDING',
                      release_bitstream=str(release / bit.name),
                      release_bitstream_sha256=sha(bit),
                      inputs_after=inputs(root), immutable_inputs_unchanged=True)
        print('BUILD PASSED; board acceptance remains NOT_TESTED.', flush=True)
        code = 0
    except Exception as exc:
        record.update(state='FAILED_NO_RELEASE', error=str(exc))
        print('FAILED: ' + str(exc), flush=True)
        code = 2
    record['ended_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    save(receipt_path, record)
    print('RECEIPT ' + str(receipt_path), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
