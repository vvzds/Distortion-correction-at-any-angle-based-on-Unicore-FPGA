"""Synthetic gate tests; these do not constitute PDS or board evidence."""
from pathlib import Path
import contextlib
import io
import json
import os
import sys
import time
import unittest
from unittest.mock import patch

import checked_build as gate


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/static_G4_timing_resume_20261024/gate_selftest'
PASS_REPORT = '''Design Summary : All Constraints Met.
ddrphy_sysclk 125.0000 MHz
pix_clk 74.2500 MHz
'''


class GateTests(unittest.TestCase):
    def setUp(self):
        self.folder = OUT / self._testMethodName
        self.folder.mkdir(parents=True, exist_ok=True)

    def report(self, text):
        path = self.folder / 'synthetic.rtr'
        path.write_text(text, encoding='utf-8')
        return path

    def test_missing_report_rejected(self):
        self.assertFalse(gate.inspect_timing(self.folder / 'missing.rtr', time.time())['passed'])

    def test_real_failed_report_rejected(self):
        path = Path('D:/FPGA PDS/yx/static_G4_bringup_20261024/G4_host/report_timing/hdmi_ddr_ov5640_top.rtr')
        result = gate.inspect_timing(path, path.stat().st_mtime)
        self.assertFalse(result['summary_pass'])
        self.assertFalse(result['no_violated_path'])
        self.assertFalse(result['passed'])

    def test_synthetic_pass_accepted(self):
        self.assertTrue(gate.inspect_timing(self.report(PASS_REPORT), time.time())['passed'])

    def test_stale_report_rejected(self):
        path = self.report(PASS_REPORT)
        os.utime(path, (time.time() - 60, time.time() - 60))
        self.assertFalse(gate.inspect_timing(path, time.time())['passed'])

    def test_conflicting_violation_rejected(self):
        for marker in ('Slack (VIOLATED)', 'Some Constraints Violated'):
            self.assertFalse(gate.inspect_timing(self.report(PASS_REPORT + marker), time.time())['passed'])

    def test_lowered_clocks_rejected(self):
        for text in (PASS_REPORT.replace('125.0000', '100.0000'),
                     PASS_REPORT.replace('74.2500', '148.5000')):
            self.assertFalse(gate.inspect_timing(self.report(text), time.time())['passed'])

    def pipeline(self, report_text, native_error=False, rebuild=False):
        root = self.folder / 'project'
        root.mkdir(exist_ok=True)
        for folder in ('source', 'ipcore', 'report_timing', 'place_route', 'generate_bitstream'):
            (root / folder).mkdir(exist_ok=True)
        for name in ('build_to_timing.tcl', 'pnr_to_timing.tcl', 'bitstream_only.tcl', gate.PROJECT):
            (root / name).write_text('# synthetic fixture only\n', encoding='utf-8')
        (root / 'HDMI_DDR3_OV5640_test.fdc').write_text(
            '{p:uart_rx} {PAP_IO_LOC} {B24}\n{p:uart_tx} {PAP_IO_LOC} {C24}\n', encoding='utf-8')
        gate.save(root / 'expected_inputs.json', gate.inputs(root))
        fake_tool_root = root / 'fake_tool'
        (fake_tool_root / 'bin').mkdir(parents=True, exist_ok=True)
        (fake_tool_root / 'bin/pds_shell.exe').write_bytes(b'SYNTHETIC; NOT EXECUTABLE')
        calls = []

        class FakeProcess:
            pid = 0

            def __init__(self, argv, **kwargs):
                calls.append(argv[2])
                self.stream = kwargs['stdout']
                if argv[2] == 'build_to_timing.tcl':
                    (root / 'report_timing' / (gate.TOP + '.rtr')).write_text(report_text, encoding='utf-8')
                    (root / 'place_route' / (gate.TOP + '_pnr.adf')).write_bytes(b'SYNTHETIC ROUTE')
                    self.stream.write(b'E: synthetic tool error\n' if native_error else b'SYNTHETIC timing process\n')
                else:
                    self.stream.write(b'Process "Place & Route" started.\n' if rebuild else b'SYNTHETIC bitstream process\n')
                    (root / 'generate_bitstream' / (gate.TOP + '.sbit')).write_bytes(b'SYNTHETIC BIT; NEVER DOWNLOAD')

            def wait(self):
                return 0

        with patch.object(sys, 'argv', ['checked_build.py', '--full', '--project-dir', str(root), '--pds-root', str(fake_tool_root)]), \
             patch.object(gate.subprocess, 'Popen', FakeProcess), contextlib.redirect_stdout(io.StringIO()):
            code = gate.main()
        receipt = max((root / 'checked_runs').glob('*/receipt.json'), key=lambda p: p.stat().st_mtime)
        return code, calls, json.loads(receipt.read_text(encoding='utf-8'))

    def test_pipeline_fail_never_calls_bitstream(self):
        code, calls, receipt = self.pipeline(PASS_REPORT.replace('All Constraints Met', 'Some Constraints Violated'))
        self.assertEqual(code, 2)
        self.assertEqual(calls, ['build_to_timing.tcl'])
        self.assertEqual(receipt['state'], 'FAILED_NO_RELEASE')
        self.assertIsNone(receipt['release_bitstream'])

    def test_native_error_exit_zero_rejected(self):
        code, calls, receipt = self.pipeline(PASS_REPORT, native_error=True)
        self.assertEqual(code, 2)
        self.assertEqual(calls, ['build_to_timing.tcl'])
        self.assertIn('TOOL_FAILED', receipt['error'])

    def test_bitstream_stage_rebuild_rejected(self):
        code, calls, receipt = self.pipeline(PASS_REPORT, rebuild=True)
        self.assertEqual(code, 2)
        self.assertEqual(len(calls), 2)
        self.assertIn('UNREVIEWED_REBUILD', receipt['error'])

    def test_synthetic_pipeline_pass(self):
        code, calls, receipt = self.pipeline(PASS_REPORT)
        self.assertEqual(code, 0)
        self.assertEqual(calls, ['build_to_timing.tcl', 'bitstream_only.tcl'])
        self.assertFalse(receipt['programmed'])
        self.assertFalse(receipt['uart_sent'])
        bit = Path(receipt['release_bitstream'])
        self.assertEqual(gate.sha(bit), receipt['release_bitstream_sha256'])


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    result = unittest.TextTestRunner(stream=buffer, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GateTests))
    text = buffer.getvalue()
    (OUT / 'synthetic_gate_selftest.log').write_text(text, encoding='utf-8')
    print(text)
    raise SystemExit(0 if result.wasSuccessful() else 1)
