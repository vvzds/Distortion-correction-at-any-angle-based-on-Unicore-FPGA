"""Freeze seed4 evidence and prepare a sequential desktop-run batch."""
from pathlib import Path
import datetime as dt
import json
import re
import shutil
import subprocess
import sys

import checked_build as gate


TASK = Path(__file__).resolve().parent
ROOT = TASK.parents[1]
BASE = Path('D:/FPGA PDS/yx/static_G4_timing_resume_20261024')
OUT = ROOT / 'outputs/static_G4_timing_resume_20261024'
DESKTOP = Path('C:/Users/叶翔/Desktop/yx/静态畸变校正_时序实现与板测续作_二号_20261024')


def summarize(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    header = text.split('\nSlow Corner\n', 1)[0]
    summaries = []
    for match in re.finditer(r'(?m)^(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):\s*\n(.*?)(?=^=+)', header, re.S | re.M):
        summaries.append(dict(kind=match[1], corner=match[2], table=match[3]))
    violations = []
    for match in re.finditer(r'(?m)^Startpoint\s*:.*?(?=^=+)', text, re.S | re.M):
        block = match[0]
        slack = re.search(r'Slack \(VIOLATED\)\s+(-?\d+\.\d+)', block)
        if slack:
            fields = {name: re.search(r'^' + name + r'\s*:\s*(.+)$', block, re.M)[1]
                      for name in ('Startpoint', 'Endpoint', 'Path Type', 'Path Group')}
            violations.append(dict(fields, slack_ns=float(slack[1]), full_path=block))
    return dict(report_sha256=gate.sha(path), summaries=summaries, violated_paths=violations)


def main():
    seed = BASE / 'seed_4'
    run = seed / 'checked_runs/20261024_174357_475624'
    receipt = json.loads((run / 'receipt.json').read_text(encoding='utf-8'))
    assert receipt['state'] == 'FAILED_NO_RELEASE'
    assert receipt['error'].startswith('TIMING_GATE_REJECTED')
    assert receipt['inputs_before'] == gate.inputs(seed)
    evidence = OUT / 'seed4_native_evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    for folder in ('report_timing', 'place_route'):
        shutil.copytree(seed / folder, evidence / folder, dirs_exist_ok=True)
    shutil.copytree(run, evidence / 'checked_run', dirs_exist_ok=True)
    for name in ('trial_preparation.json', 'expected_inputs.json', 'checked_build.py',
                 'pnr_to_timing.tcl', 'bitstream_only.tcl', 'build_to_timing.tcl', gate.PROJECT):
        shutil.copy2(seed / name, evidence / name)
    gate.save(evidence / 'timing_summary.json', summarize(seed / 'report_timing' / (gate.TOP + '.rtr')))
    # 旧启动记录未正常收尾，保留原件并独立注明，不伪造完成状态。
    interrupted = seed / 'checked_runs/20261024_174327_316361'
    shutil.copytree(interrupted, evidence / 'earlier_interrupted_run', dirs_exist_ok=True)
    (evidence / 'README.md').write_text('''# Seed4 原生PDS物理结果

接收：管理方/执行者；一号协作者参阅；二号协作者留档。

实际运行：2026-10-24 17:43:57—17:48:35，PDS 2022.2-SP6.1。
CMOS2，1920×1080@30，像素74.25MHz，校正/DDR125MHz。RTL/IP/FDC与冻结基线一致，复用已核对哈希的映射检查点，仅改变原生布局/布线种子为4。

慢角DDR125建立WNS从-0.570ns改善到+0.082ns；该组建立失败端点18→0。整体仍失败：快角DDR PHY→DDR125保持WHS=-0.058ns，1个失败端点。报告仅有一条Slack(VIOLATED)，详见timing_summary.json及原始rtr。

构建门禁正确阻止了位流生成；没有合格sbit，没有烧录，没有UART下发，不代表实板验收通过。外部端口约束覆盖仍沿用基线，本结果不额外证明外部接口时序完整性。

earlier_interrupted_run保留17:43:27那次未收尾的原始记录。17:50之后检查已无PDS进程；其TIMING_RUNNING是遗留状态，不能视为一次完成运行，也不能作为当前成功证据。

task1_1080p30.pds是本次检查点流程生成的原始项目文件，不是完整RTL源项目。完整源码仍在冻结基线；下一轮同时提供独立full_source_1080p30.pds及build_to_timing.tcl入口。
''', encoding='utf-8')
    gate.save(evidence / 'SHA256.json', {p.relative_to(evidence).as_posix(): gate.sha(p)
                                      for p in sorted(evidence.rglob('*')) if p.is_file() and p.name != 'SHA256.json'})
    for seed_number in (5, 6, 7, 8):
        subprocess.run([sys.executable, '-B', '-X', 'utf8', str(TASK / 'prepare_trial.py'), '--seed', str(seed_number)], check=True)
    shutil.copy2(TASK / 'run_trial_batch.py', BASE / 'run_trial_batch.py')
    (BASE / 'run_next_seeds_checked.cmd').write_text(
        '@echo off\r\ncd /d "%~dp0"\r\n'
        '"%USERPROFILE%\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe" '
        '-B -X utf8 "%~dp0run_trial_batch.py"\r\npause\r\n', encoding='ascii')
    (OUT / '01_本轮结果与续跑说明_给执行者.md').write_text('''# 本轮结果与续跑说明

接收：管理方/执行者；抄阅：一号协作者；执行与留档：二号协作者。

Seed4真实P&R：125MHz慢角建立WNS=+0.082ns，快角DDR PHY保持WHS=-0.058ns（1端点）。整体不通过，未生成或烧录位流。原始报告、路径、检查点、日志、回执与哈希见seed4_native_evidence。

已准备互相隔离的Seed5/6/7/8，保持RTL/IP/FDC和时钟相同。双击 `D:\\FPGA PDS\\yx\\static_G4_timing_resume_20261024\\run_next_seeds_checked.cmd` 一次即可串行尝试；首次完整时序通过并生成匹配位流后停止，工具错误或输入变更时停止。锁防止同一批次被重复启动。最多4次，无自动下载和UART操作；不要同时在PDS中编译这些目录。

运行状态见同目录batch_receipt.json，各种子详细日志见seed_N/checked_runs。完整源项目入口full_source_1080p30.pds与检查点流程分开保存。

gate_selftest内10项门禁测试通过，其中合成报告/虚拟PDS/虚拟位流仅供测试门禁控制流；虚拟位流不能下载，未包含进桌面交付目录。此自检不等价于RTL、PDS时序或板测通过。
''', encoding='utf-8')
    DESKTOP.mkdir(parents=True, exist_ok=True)
    for name in ('00_继续开工声明_给执行者.md', '01_本轮结果与续跑说明_给执行者.md'):
        shutil.copy2(OUT / name, DESKTOP / name)
    shutil.copytree(evidence, DESKTOP / evidence.name, dirs_exist_ok=True)
    tools = DESKTOP / '构建门禁与续跑脚本'
    tools.mkdir(exist_ok=True)
    for name in ('checked_build.py', 'prepare_trial.py', 'run_trial_batch.py', 'test_checked_build.py', 'prepare_batch.py'):
        shutil.copy2(TASK / name, tools / name)
    shutil.copy2(OUT / 'gate_selftest/synthetic_gate_selftest.log', tools / 'synthetic_gate_selftest.log')
    print(BASE / 'run_next_seeds_checked.cmd')
    print(DESKTOP)


if __name__ == '__main__':
    main()
