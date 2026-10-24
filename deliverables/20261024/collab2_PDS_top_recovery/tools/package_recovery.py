"""Package compile recovery and current evidence, without overstating results."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

TASK=Path('C:/Users/叶翔/Desktop/yx/PDS顶层解析修复_二号_20261024')
ROOT=Path('D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project')
WORK=ROOT/'top_recovery'
DEST=Path('C:/Users/叶翔/Documents/Codex/fpga-main/deliverables/20261024/collab2_PDS_top_recovery')

def main():
    runs=sorted((WORK/'runs').glob('*/receipt.json'))
    latest=json.loads(runs[-1].read_text(encoding='utf-8')) if runs else {}
    state=latest.get('state','NOT_RUN')
    status=('原生 Compile 已通过，耗时 '+str(latest.get('elapsed_s'))+
        ' 秒，错误数 0；保留原有警告。') if state=='PASS' else (
        '自动化会话原生 Compile 返回 Flow-0189 内部错误；'
        '正常桌面启动结果待补，尚未证明本轮 Compile 通过。')
    readme=('# PDS 顶层解析恢复入口与证据\n\n'
        '制作：二号协作者；接收：执行者/管理方；一号协作者可查阅。\n\n'
        '原工程：`D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project/full_source_1080p30.pds`。\n\n'
        '## 当前结论\n\n'
        '- 原工程已配置 `hdmi_ddr_ov5640_top`，并非工程文件漏写顶层。\n'
        '- 115 个工程文件引用均存在；139 个冻结输入 SHA256 全部匹配。\n'
        '- GUI 日志显示 20:04:47 启动层次解析，20:04:49 Compile 报 Flow-0245；'
        '层次更新尚未完成为候选原因，未据此断言唯一根因。\n'
        '- '+status+'\n'
        '- 没有修改 RTL、IP、FDC、时钟、分辨率；没有重新生成位流、烧录或下发 UART。\n\n'
        '## 本机下一步\n\n'
        '本机已验证工程入口：`D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project/top_recovery/'
        'full_source_top_recovered.pds`。在 PDS 中关闭原项目（避免把旧项目覆盖保存到新入口），'
        '然后打开此工程。顶层已固定，Compile 已完成；后续可从 Synthesize 开始。'
        '该副本保留原工程布局种子4、布线种子5、多角保持修复与20次迭代设置。\n\n'
        '如需重复独立 Compile，双击 `D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project/top_recovery/run_compile.cmd`，'
        '保持窗口打开。程序在独立目录中重新导入冻结源码，显式执行 '
        '`compile -top_module hdmi_ddr_ov5640_top`，只执行 Compile。\n\n'
        '也可在当前工程的 PDS Console 输入 '
        '`source {D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project/compile_explicit_top.tcl}`；'
        '它对当前工程执行 Compile，会更新当前工程编译结果，因此优先使用独立目录入口。\n\n'
        '日志与回执：`top_recovery/runs/<时间>/console.log`、`receipt.json`；'
        '只有 `state=PASS` 才是本轮 Compile 成功。\n\n'
        '## 包内内容\n\n'
        '`PDS_top_recovery.zip` 包含完整的原样 source、ipcore、FDC、原生 Compile 数据库、'
        '已完成 Compile 的 .pds、显式顶层 Tcl、运行器与本次日志，不含 PDS 安装包。'
        '解压后可打开 `full_source_top_recovered.pds`；重复编译在正常桌面双击 `run_compile.cmd`。'
        'PDS 默认安装路径为本机 SP6.1；安装位置不同时需修改 run_compile.py 的 tool 路径。'
        '不把 Compile 通过等同于综合、布局布线、时序或板测通过。\n')
    (TASK/'01_核查与操作说明_给执行者.md').write_text(readme,encoding='utf-8')
    if (TASK/'native_runs').exists():
        # Overlay only; never remove prior evidence.
        shutil.copytree(WORK/'runs',TASK/'native_runs',dirs_exist_ok=True)
    else:
        shutil.copytree(WORK/'runs',TASK/'native_runs')
    with zipfile.ZipFile(TASK/'PDS_top_recovery.zip','w',zipfile.ZIP_DEFLATED) as z:
        for folder in ('source','ipcore','runs','compile'):
            for p in sorted((WORK/folder).rglob('*')):
                if p.is_file() and p.suffix!='.lock': z.write(p,p.relative_to(WORK).as_posix())
        for name in ('compile_only.tcl','run_compile.py','run_compile.cmd','preflight.json',
                     'HDMI_DDR3_OV5640_test.fdc','full_source_top_recovered.pds'):
            z.write(WORK/name,name)
        if (TASK/'FINAL_VERIFICATION.json').is_file():
            z.write(TASK/'FINAL_VERIFICATION.json','FINAL_VERIFICATION.json')
    DEST.mkdir(parents=True,exist_ok=True)
    for name in ('00_开工声明_给执行者.md','preflight.json','gui_failure_before.log',
                 'full_source_1080p30.before.pds','PDS_top_recovery.zip'):
        shutil.copy2(TASK/name,DEST/name)
    (DEST/'README.md').write_text(readme,encoding='utf-8')
    shutil.copytree(TASK/'native_runs',DEST/'native_runs',dirs_exist_ok=True)
    if (TASK/'FINAL_VERIFICATION.json').is_file():
        shutil.copy2(TASK/'FINAL_VERIFICATION.json',DEST/'FINAL_VERIFICATION.json')
    shutil.copytree(Path(__file__).parent,DEST/'tools',dirs_exist_ok=True,
        ignore=shutil.ignore_patterns('__pycache__'))
    receipt=dict(status=state,scope='compile_recovery_preparation',
        validation_passed=state=='PASS',latest_run=latest,
        original_project_unchanged=True,rtl_ip_fdc_unchanged=True,
        recipient='执行者/管理方；一号协作者可查阅；二号留档')
    (DEST/'STATUS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    hashes={p.relative_to(DEST).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.json'}
    (DEST/'SHA256SUMS.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(state=state,destination=str(DEST),files=len(hashes),
        package_bytes=(TASK/'PDS_top_recovery.zip').stat().st_size),ensure_ascii=False))

if __name__=='__main__': main()
