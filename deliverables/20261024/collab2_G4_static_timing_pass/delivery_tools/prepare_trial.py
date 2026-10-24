"""Prepare a new native PDS physical trial from the frozen mapped checkpoint."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import checked_build

TASK = Path(__file__).resolve().parent
BASELINE = Path('D:/FPGA PDS/yx/static_G4_bringup_20261024/G4_host')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--route-seed', type=int)
    parser.add_argument('--suffix', default='')
    parser.add_argument('--hold-iterations', type=int)
    parser.add_argument('--multi-corner-hold', action='store_true')
    args = parser.parse_args()
    seed = args.seed
    assert seed >= 0
    route_seed = seed if args.route_seed is None else args.route_seed
    assert route_seed >= 0
    assert not args.suffix or re.fullmatch('[a-z0-9_]+', args.suffix)
    assert args.hold_iterations is None or 1 <= args.hold_iterations <= 100
    name = 'seed_' + str(seed) + ('_' + args.suffix if args.suffix else '')
    target = Path('D:/FPGA PDS/yx/static_G4_timing_resume_20261024/' + name)
    assert not target.exists(), 'Keep existing trial evidence; use a new seed/directory.'
    old = json.loads((BASELINE / 'local_runs/20261024_170317_585569/process_receipt.json').read_text(encoding='utf-8'))
    assert old['state'] != 'RUNNING'
    assert all(checked_build.sha(BASELINE / p) == s for p, s in old['inputs_before'].items())
    target.mkdir(parents=True)
    for name in ('source', 'ipcore', 'compile', 'synthesize', 'device_map', 'constraint_check'):
        shutil.copytree(BASELINE / name, target / name,
                        ignore=shutil.ignore_patterns('*.lock'))
    shutil.copy2(BASELINE / 'HDMI_DDR3_OV5640_test.fdc', target / 'HDMI_DDR3_OV5640_test.fdc')
    project = (BASELINE / 'task1_1080p30.pds').read_text(encoding='utf-8')
    project, count = re.subn(r'(\(_command cmd_pnr\s+)\(_gci_state \(_integer 2\)\)',
        r'\g<1>(_gci_state (_integer 0))\n'
        '            (_option gplace_seed (_integer ' + str(seed) + '))\n'
        '            (_option groute_seed (_integer ' + str(route_seed) + '))', project)
    assert count == 1
    physical_options = ''
    if args.multi_corner_hold:
        physical_options += ' -optimize_multi_corner_timing -fix_hold_violation'
        project = project.replace('(_option groute_seed (_integer ' + str(route_seed) + '))',
            '(_option groute_seed (_integer ' + str(route_seed) + '))\n'
            '            (_option optimize_multi_corner_timing (_switch ON))\n'
            '            (_option fix_hold_violation (_switch ON))')
    if args.hold_iterations is not None:
        physical_options += ' -fix_hold_violation_iterations ' + str(args.hold_iterations)
        project = project.replace('(_option groute_seed (_integer ' + str(route_seed) + '))',
            '(_option groute_seed (_integer ' + str(route_seed) + '))\n'
            '            (_option fix_hold_violation_iterations (_integer ' + str(args.hold_iterations) + '))')
    project, count = re.subn(r'(\(_command cmd_report_post_pnr_timing\s+)\(_gci_state \(_integer 2\)\)',
                            r'\g<1>(_gci_state (_integer 0))', project)
    assert count == 1
    (target / checked_build.PROJECT).write_text(project, encoding='utf-8')
    # 检查点入口会由PDS重写，另存完整源码入口供交付。
    source_project = re.sub(r'\(_gci_state \(_integer [0-9]+\)\)',
                            '(_gci_state (_integer 0))', project)
    (target / 'full_source_1080p30.pds').write_text(source_project, encoding='utf-8')
    flow = (BASELINE / 'build.tcl').read_text(encoding='utf-8')
    flow = flow[flow.index('set_arch '):flow.index('\n# Do not generate')]
    assert flow.count('\npnr\n') == 1
    flow = flow.replace('\npnr\n', '\npnr -gplace_seed %d -groute_seed %d%s\n' % (seed, route_seed, physical_options))
    (target / 'build_to_timing.tcl').write_text('cd [file dirname [info script]]\n' + flow + '\n', encoding='utf-8')
    (target / 'pnr_to_timing.tcl').write_text(
        'cd [file dirname [info script]]\n'
        'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'add_constraint "HDMI_DDR3_OV5640_test.fdc"\n'
        'add_constraint "device_map/hdmi_ddr_ov5640_top.pcf"\n'
        'pnr -force_to_run -input_db_file "device_map/hdmi_ddr_ov5640_top_map.adf" '
        '-gplace_seed %d -groute_seed %d%s\nreport_timing\n' % (seed, route_seed, physical_options), encoding='utf-8')
    (target / 'bitstream_only.tcl').write_text(
        'cd [file dirname [info script]]\n'
        'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'gen_bit_stream -force_to_run -input_db_file "place_route/hdmi_ddr_ov5640_top_pnr.adf"\n', encoding='utf-8')
    shutil.copy2(TASK / 'checked_build.py', target / 'checked_build.py')
    (target / 'run_checked_build.cmd').write_text(
        '@echo off\r\ncd /d "%~dp0"\r\n'
        '"%USERPROFILE%\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe" '
        '-B -X utf8 "%~dp0checked_build.py"\r\npause\r\n', encoding='ascii')
    now = checked_build.inputs(target)
    expected_hardware = {p: s for p, s in now.items() if p not in (
        'build_to_timing.tcl', 'pnr_to_timing.tcl', 'bitstream_only.tcl')}
    baseline_hardware = {p: s for p, s in old['inputs_before'].items() if p != 'build.tcl'}
    assert expected_hardware == baseline_hardware
    checked_build.save(target / 'expected_inputs.json', now)
    checked_build.save(target / 'trial_preparation.json', dict(
        seed=seed, route_seed=route_seed, baseline=str(BASELINE), rtl_ip_fdc_identical=True,
        native_extra_physical_options=physical_options,
        baseline_input_snapshot=old['inputs_before'],
        checkpoint_inputs={name: checked_build.sha(target / name) for name in (
            'device_map/hdmi_ddr_ov5640_top_map.adf', 'device_map/hdmi_ddr_ov5640_top.pcf')},
        reused_stages=['compile', 'synthesize', 'device_map'],
        rerun_stages=['place_route', 'report_timing'],
        timing_gate='external Python, after native PDS process completion',
        bitstream_gate='separate native process only after timing gate passes',
        source_hz=125000000, hdmi='1920x1080@30', programmed=False))
    print(target)


if __name__ == '__main__':
    main()
