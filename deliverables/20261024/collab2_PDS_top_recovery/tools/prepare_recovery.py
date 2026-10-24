"""Prepare isolated native PDS compile recovery without changing frozen inputs."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import re
import shutil

ROOT = Path('D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project')
TASK = Path('C:/Users/叶翔/Desktop/yx/PDS顶层解析修复_二号_20261024')
WORK = ROOT / 'top_recovery'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def main():
    TASK.mkdir(parents=True, exist_ok=True)
    (TASK/'00_开工声明_给执行者.md').write_text(
        '# PDS 顶层解析恢复\n\n执行：二号协作者；接收：执行者/管理方；一号协作者可查阅。\n\n'
        '目标：定位 full_source_1080p30.pds 的 Flow-0245，验证显式指定 '
        'hdmi_ddr_ov5640_top 的原生 Compile 入口。保持 1080P30、125MHz 以及 '
        'RTL/IP/FDC 原始字节；不烧录、不下发 UART、不覆盖既有时序和位流证据。\n\n'
        '采用 top_recovery 独立工作目录，保留原工程。原 .pds 已含 top_module 配置；'
        '20:04:47 的日志刚启动层次解析，20:04:49 Compile 报错。'
        '层次更新未完成是候选原因，不能仅凭此确认。\n', encoding='utf-8')
    assert not WORK.exists(), 'Preserve existing recovery directory'
    project = ROOT/'full_source_1080p30.pds'
    text = project.read_text(encoding='utf-8')
    assert '(_option top_module (_string "hdmi_ddr_ov5640_top"))' in text
    paths = re.findall(r'\(_(?:file|ip|ip_source_item) "([^"]+)"', text)
    missing = [p for p in paths if not (ROOT/p).is_file()]
    assert not missing, missing
    frozen = json.loads((ROOT/'expected_inputs.json').read_text(encoding='utf-8'))
    mismatch = [p for p,h in frozen.items() if not (ROOT/p).is_file() or sha(ROOT/p) != h]
    assert not mismatch, mismatch
    WORK.mkdir()
    for folder in ('source','ipcore'):
        shutil.copytree(ROOT/folder,WORK/folder)
    shutil.copy2(ROOT/'HDMI_DDR3_OV5640_test.fdc',WORK/'HDMI_DDR3_OV5640_test.fdc')
    shutil.copy2(project,TASK/'full_source_1080p30.before.pds')
    shutil.copy2(ROOT/'pds.log',TASK/'gui_failure_before.log')
    # Native known-good design list, with explicit top and no synthesis/P&R.
    flow = (ROOT/'build_to_timing.tcl').read_text(encoding='utf-8')
    flow = flow.split('\nsynthesize ',1)[0] + '\nputs {=== EXPLICIT TOP COMPILE COMPLETED ===}\n'
    (WORK/'compile_only.tcl').write_text(flow,encoding='utf-8')
    shutil.copy2(Path(__file__).with_name('run_compile.py'), WORK/'run_compile.py')
    launcher = ('@echo off\r\ncd /d "%~dp0"\r\n'
        '"%USERPROFILE%\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe" '
        '-B -X utf8 "%~dp0run_compile.py"\r\npause\r\n')
    (WORK/'run_compile.cmd').write_bytes(launcher.encode('ascii'))
    # Console alternative operates only on the currently loaded design.
    console = ('# Run inside the existing PDS Console after hierarchy update.\n'
        'cd {'+ROOT.as_posix()+'}\ncompile -top_module hdmi_ddr_ov5640_top\n')
    (ROOT/'compile_explicit_top.tcl').write_text(console,encoding='utf-8')
    save(WORK/'preflight.json',dict(time=dt.datetime.now().astimezone().isoformat(),
        root=str(ROOT),input_files=len(frozen),input_hashes=frozen,
        all_frozen_inputs_match=True,project_paths_checked=len(paths),
        missing_paths=missing,top='hdmi_ddr_ov5640_top',original_project_sha256=sha(project),
        source_project_already_has_top=True,programmed=False,uart_sent=False))
    for name in ('preflight.json','compile_only.tcl','run_compile.py','run_compile.cmd'):
        shutil.copy2(WORK/name,TASK/name)
    print(json.dumps(dict(task=str(TASK),work=str(WORK),frozen_files=len(frozen),paths=len(paths)),ensure_ascii=False))

if __name__ == '__main__':
    main()
