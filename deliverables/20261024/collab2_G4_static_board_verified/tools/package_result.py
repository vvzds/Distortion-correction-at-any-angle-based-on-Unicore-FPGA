"""Archive the actual programmed candidate, UART evidence and current limitations."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import re
import shutil
import zipfile

HERE=Path(__file__).resolve().parent
BASE=Path('D:/FPGA PDS/yx/DCSjingtaijiaozheng')
ROOT=BASE/'01_project/top_recovery'
TASK=Path('C:/Users/叶翔/Desktop/yx/静态校正_黑屏定位与恒等出图_二号_20261024')
REPO=Path('C:/Users/叶翔/Documents/Codex/fpga-main')
DEST=REPO/'deliverables/20261024/collab2_G4_static_board_verified'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    TASK.mkdir(parents=True,exist_ok=True)
    package=TASK/'G4_1080P30_真实参数校正已出图_更新率待优化_二号给执行者与一号'
    assert not package.exists(),'Preserve previous package; do not overwrite it'
    package.mkdir()
    project=package/'01_project'
    project.mkdir()
    for name in ('source','ipcore','compile','synthesize','device_map','constraint_check',
                 'place_route','report_timing','generate_bitstream','log'):
        shutil.copytree(ROOT/name,project/name,ignore=shutil.ignore_patterns('*.lock'))
    for name in ('HDMI_DDR3_OV5640_test.fdc','full_source_top_recovered.pds','impl.tcl',
                 'pds.log','multiseed_summary.csv'):
        shutil.copy2(ROOT/name,project/name)
    evidence=package/'02_evidence'
    evidence.mkdir()
    shutil.copy2(ROOT/'full_source_top_recovered.pds',evidence/'full_source_top_recovered.native.pds')
    # 工程元数据显式固定同一顶层；保存的原生数据库与所有RTL保持原样。
    pds=project/'full_source_top_recovered.pds'
    text=pds.read_text(encoding='utf-8')
    if not re.search(r'\(_option top_module ',text):
        text=text.replace('(_command cmd_compile\n','(_command cmd_compile\n'
            '            (_option top_module (_string "hdmi_ddr_ov5640_top"))\n',1)
        pds.write_text(text,encoding='utf-8')
    paths=re.findall(r'\(_(?:file|ip|ip_source_item) "([^"]+)"',text)
    missing=[p for p in paths if not (project/p).is_file()]
    assert not missing,missing
    pre=json.loads((ROOT/'preflight.json').read_text(encoding='utf-8'))
    for name,h in pre['input_hashes'].items():
        if name.startswith(('source/','ipcore/')) or name.endswith('.fdc'):
            assert sha(project/name)==h,name
    shutil.copytree(BASE/'03_parameters',package/'03_parameters')
    tools=package/'04_uart_tool'
    shutil.copytree(BASE/'04_uart_tool',tools,ignore=shutil.ignore_patterns('__pycache__'))
    probe=(HERE/'probe_uart.py').read_text(encoding='utf-8')
    probe=probe.replace("BASE=Path('D:/FPGA PDS/yx/DCSjingtaijiaozheng')",'BASE=Path(__file__).resolve().parent.parent')
    probe=probe.replace('HERE=Path(__file__).resolve().parent','HERE=Path(__file__).resolve().parent / "hardware_runs"\nHERE.mkdir(exist_ok=True)')
    (tools/'apply_parameters.py').write_text(probe,encoding='utf-8')
    for mode in ('identity','real'):
        launcher=('@echo off\r\ncd /d "%~dp0"\r\n'
            '"%USERPROFILE%\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe" '
            '-B -X utf8 "%~dp0apply_parameters.py" --'+mode+'\r\npause\r\n')
        (tools/('run_'+mode+'_parameters.cmd')).write_bytes(launcher.encode('ascii'))
    records=[]
    for p in sorted(HERE.glob('uart_*.json')):
        shutil.copy2(p,evidence/p.name)
        records.append(json.loads(p.read_text(encoding='utf-8')))
    stable=records[-1]
    assert stable['state']=='COMPLETE' and not stable['writes']
    assert all(r['params_valid']==1 and r['fw_version']==0x12 for r in stable['queries'])
    rate=stable['observed_publish_per_s']
    rtr=(project/'report_timing/hdmi_ddr_ov5640_top.rtr').read_text(encoding='utf-8',errors='replace')
    assert 'Design Summary : All Constraints Met.' in rtr
    assert 'Slack (VIOLATED)' not in rtr
    bits=project/'generate_bitstream/hdmi_ddr_ov5640_top.sbit'
    assert sha(bits)=='67ce6939f03abe9e9594f6bd071a567988eeda96fecb4eec2c3f5b8ed6cdf317'
    version=dict(version='G4_STATIC_BOARD_REAL_PARAMS_20261024',
        state='REAL_CORRECTION_VISUALLY_CONFIRMED_RATE_BELOW_TARGET',
        recipient='执行者/管理方接收验收状态；一号协作者接收整机；二号保留优化与证据',
        time=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        device='PG2L100H-6IFBG676',camera='CMOS2',hdmi='1920x1080@30',
        ddr_core_mhz=125,pixel_mhz=74.25,pds='2022.2-SP6.1 build138931',
        bitstream_sha256=sha(bits),fdc_sha256=sha(project/'HDMI_DDR3_OV5640_test.fdc'),
        top='hdmi_ddr_ov5640_top',project_file_references_checked=len(paths),
        rtl_ip_fdc_unchanged=True,project_metadata_explicit_top_added=True,
        timing_native_all_constraints_met=True,slow_setup_wns_ns=.183,
        timing_external_port_coverage_complete=False,
        programming_done_bit=1,programming_source='user action and native configuration.log',
        black_initial_status='0x00000012',black_cause='params_valid=0 gates correction start; display reads corrected slots',
        identity_display_confirmed_by_user=True,real_correction_confirmed_by_user=True,
        image_quality_quantified=False,saved_capture_comparison=False,
        stable_publish_window_seconds=stable['elapsed_s'],
        stable_publish_count_delta=stable['publish_delta'],
        real_corrected_frames_per_second=rate,
        correction_30fps_requirement_met=False,
        real_parameters_sent=True,affine_enabled=False,gamma_enabled=False,
        reboot_requires_parameter_reload=True,calibration_optics_reconfirmed=False)
    save(package/'VERSION.json',version)
    (evidence/'用户实机确认记录.md').write_text(
        '# 用户确认\n\n用户先确认“出画面了”，此时为恒等映射。\n\n'
        '用户随后反馈原有严重畸变；二号下发既有 Brown4 真实参数后，用户确认“矫正成功”。\n\n'
        '本轮没有保存新的采集卡截图或量化直线误差，不能将口头确认写成M03画质量化验收通过。\n',encoding='utf-8')
    explanation=('# 静态校正已出图，真实新帧率待优化\n\n'
        '制作：二号协作者；接收：执行者/管理方，以及一号协作者（整机链路）。\n\n'
        '## 已完成\n\n'
        '本包对应用户实际烧录并确认“矫正成功”的源码、位流、原生时序和UART记录。'
        '起初串口连续回复0x00000012：参数无效、引擎空闲、发布计数0。'
        '上电默认读取校正槽，未下发参数时没有已发布校正帧，所以显示屏锁定1080P30仍黑屏。'
        '先下发恒等参数恢复基准画面，再下发既有真实Brown4参数；参数有效且发布计数递增。\n\n'
        '## 必须保留的限制\n\n'
        f'真实参数稳定窗口 {stable["elapsed_s"]:.3f}s 新发布 {stable["publish_delta"]}帧，'
        f'约 {rate:.3f}fps，未达到校正新帧30fps目标。HDMI时序仍是1080P30，会重复显示已有校正帧。'
        '本包是可出图候选，不能标作性能终验通过。仍需新帧率优化、画质截图/定量验收。'
        '原生时序All Constraints Met、slow setup WNS +0.183ns；外部端口约束覆盖警告仍在。\n\n'
        '## 下载与上电\n\n'
        '1. 管理方核对VERSION.json和SHA256SUMS.json；实际位流位于 '
        '`01_project/generate_bitstream/hdmi_ddr_ov5640_top.sbit`，SHA256为 '
        '`'+sha(bits)+'`。这是本次实测新位流，不能与旧3084...位流混作同一证据。\n'
        '2. PDS/Fabric Configuration执行普通SRAM配置，核对器件PG2L100H；'
        '保持HDMI和板载USB-UART连接。完整工程入口 '
        '`01_project/full_source_top_recovered.pds`，含原样源码/IP/FDC及本轮全部原生构建产物。\n'
        '3. 每次重新下载或断电重启后运行 `04_uart_tool/run_real_parameters.cmd`；'
        '程序定位CP2102，先核对0x12固件，再发送关闭Gamma、关闭仿射、真实参数，'
        '并回读params_valid/pub_count。仅发送无ACK的报文不算参数已应用。'
        '基准对比使用run_identity_parameters.cmd；恒等映射保留原始镜头畸变。\n\n'
        '工具依赖pyserial。本机沿用既有host_validation_deps；其他电脑需使用已有Python并安装requirements.txt，'
        '运行 `python apply_parameters.py --real`。本包不含Python/PDS安装包。'
        'COM11是本次CP2102枚举结果；工具按VID/PID定位，不能使用JTAG的COM9/COM10。\n\n'
        '## 版本与下一步\n\n'
        '本包保留源码、真实/恒等参数、全部报告与原始串口回读。'
        '由于真实校正新帧率尚不达标，不据此删除仍有价值的历史候选或验收证据。'
        '下一步由二号针对真实映射的源行缓存和DDR读访问开销定位性能；'
        '执行者/管理方记录实机视觉确认与性能缺口；一号保留采集/显示接口契约。\n')
    (package/'README_给执行者和一号协作者.md').write_text(explanation,encoding='utf-8')
    shutil.copy2(HERE/'00_开工声明_给执行者.md',package/'00_开工声明_给执行者.md')
    hashes={p.relative_to(package).as_posix():sha(p) for p in sorted(package.rglob('*')) if p.is_file()}
    save(package/'SHA256SUMS.json',hashes)
    zip_path=TASK/(package.name+'.zip')
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(package.rglob('*')):
            if p.is_file(): z.write(p,package.name+'/'+p.relative_to(package).as_posix())
    with zipfile.ZipFile(zip_path) as z: assert z.testzip() is None
    DEST.mkdir(parents=True,exist_ok=True)
    shutil.copy2(zip_path,DEST/zip_path.name)
    shutil.copy2(package/'VERSION.json',DEST/'VERSION.json')
    shutil.copy2(package/'README_给执行者和一号协作者.md',DEST/'README.md')
    shutil.copytree(evidence,DEST/'evidence',dirs_exist_ok=True)
    shutil.copytree(HERE,DEST/'tools',dirs_exist_ok=True,ignore=shutil.ignore_patterns('uart_*.json','__pycache__'))
    save(DEST/'SHA256SUMS.json',{p.relative_to(DEST).as_posix():sha(p)
        for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.json'})
    save(TASK/'打包回执.json',dict(package=str(package),zip=str(zip_path),
        zip_sha256=sha(zip_path),zip_bytes=zip_path.stat().st_size,repository_dir=str(DEST),
        files_verified=len(hashes),state=version['state']))
    print(json.dumps(dict(zip=str(zip_path),bytes=zip_path.stat().st_size,
        files=len(hashes),real_publish_fps=rate,state=version['state']),ensure_ascii=False))

if __name__=='__main__': main()
