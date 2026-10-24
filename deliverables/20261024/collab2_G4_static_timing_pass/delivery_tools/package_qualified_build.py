"""Freeze exact G4 physical build and board-test candidate; never program."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import re
import shutil
import zipfile

import checked_build as gate
from collect_native_batch import extract_tables


TASK = Path(__file__).resolve().parent
BASE = Path('D:/FPGA PDS/yx/static_G4_timing_resume_20261024')
BUILD = BASE / 'seed_4_hold20_r5'
RUN = BUILD / 'checked_runs/20261024_182133_049086'
OUT = TASK.parents[1] / 'outputs/static_G4_timing_resume_20261024'
NAME = 'G4_静态校正1080p30_时序通过待板测_二号给管理方_20261024'
PKG = OUT / NAME
DESKTOP = Path('C:/Users/叶翔/Desktop/yx/静态畸变校正_时序实现与板测续作_二号_20261024')
RECEIVED = TASK.parents[1] / 'work/static_G4_bringup_20261024/received/static_correction_existing_20261024'


def write(name, text):
    p = PKG / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def save(name, value):
    write(name, json.dumps(value, ensure_ascii=False, indent=2))


def main():
    receipt = json.loads((RUN / 'receipt.json').read_text(encoding='utf-8'))
    assert receipt['state'] == 'BUILD_PASSED_BOARD_TEST_PENDING'
    assert gate.inputs(BUILD) == receipt['inputs_before'] == receipt['inputs_after']
    assert all(gate.sha(BUILD / p) == h for p, h in receipt['checkpoint_inputs'].items())
    report = BUILD / 'report_timing' / (gate.TOP + '.rtr')
    route = BUILD / 'place_route' / (gate.TOP + '_pnr.adf')
    bit = Path(receipt['release_bitstream'])
    assert gate.sha(report) == receipt['timing_gate']['sha256']
    assert gate.sha(route) == receipt['reviewed_route_sha256']
    assert gate.sha(bit) == receipt['release_bitstream_sha256']
    assert gate.inspect_timing(report, receipt['phases'][0]['start_epoch'])['passed']
    assert len(receipt['phases']) == 2 and all(p['exit_code'] == 0 and not p['errors'] for p in receipt['phases'])
    assert not re.search(r'^Process "(?:Compile|Synthesize|Device Map|Place & Route)" started\.',
                         (RUN / 'bitstream.log').read_text(encoding='utf-8', errors='replace'), re.M)
    PKG.mkdir(parents=True, exist_ok=False)
    project = PKG / '01_project'
    project.mkdir()
    for folder in ('source', 'ipcore', 'compile', 'synthesize', 'device_map', 'constraint_check',
                   'place_route', 'report_timing', 'generate_bitstream'):
        if (BUILD / folder).exists():
            shutil.copytree(BUILD / folder, project / folder, ignore=shutil.ignore_patterns('*.lock'))
    for name in ('HDMI_DDR3_OV5640_test.fdc', 'full_source_1080p30.pds', gate.PROJECT,
                 'build_to_timing.tcl', 'pnr_to_timing.tcl', 'bitstream_only.tcl',
                 'expected_inputs.json', 'trial_preparation.json', 'checked_build.py', 'run_checked_build.cmd'):
        shutil.copy2(BUILD / name, project / name)
    shutil.copytree(RUN, PKG / '02_evidence/qualified_native_run')
    shutil.copy2(BASE / 'targeted_route_batch_receipt.json', PKG / '02_evidence/targeted_route_batch_receipt.json')
    shutil.copy2(OUT / 'gate_selftest/synthetic_gate_selftest.log', PKG / '02_evidence/gate_selftest_synthetic_only.log')
    save('02_evidence/timing_summary.json', extract_tables(report))
    for name in ('03_原生批次结果_给执行者.md', '04_定向修复结果与布线续作_给执行者.md'):
        shutil.copy2(OUT / name, PKG / '02_evidence' / ('历史_' + name))
    shutil.copytree(RECEIVED / '02_标定参数', PKG / '03_parameters')
    shutil.copytree(RECEIVED / '04_UART工具/UART_HOST_TOOL', PKG / '04_uart_tool')
    shutil.copytree(RECEIVED / '05_板卡串口及实测准备', PKG / '05_uart_constraint_provenance')
    ready = PKG / '06_bitstream'
    ready.mkdir()
    ready_bit = ready / 'G4_static_CMOS2_1080p30_P125_seed4_route5.sbit'
    shutil.copy2(bit, ready_bit)
    (ready / 'SHA256.txt').write_text(gate.sha(ready_bit) + '  ' + ready_bit.name + '\n', encoding='ascii')
    version = dict(version='G4_STATIC_C2_1080P30_P125_S4_R5_20261024',
                   state='BUILD_PASSED_BOARD_TEST_PENDING', source_candidate='G4 existing frozen core',
                   prepared=dt.datetime.now().astimezone().isoformat(), recipient='管理方/执行者先核对；一号协作者接收采集显示整机；二号留档',
                   pds='2022.2-SP6.1 build138931', pds_sha256=receipt['tool_sha256'],
                   device='PG2L100H-6IFBG676', camera='CMOS2', hdmi='1920x1080@30',
                   ddr_core_mhz=125, pixel_requested_mhz=74.25, slow_setup_wns_ns=0.183,
                   place_seed=4, route_seed=5, multi_corner_hold=True, max_hold_iterations=20,
                   rtl_ip_fdc_unchanged=True, source_inputs=receipt['inputs_before'],
                   map_checkpoints=receipt['checkpoint_inputs'], route_sha256=gate.sha(route),
                   report_sha256=gate.sha(report), bitstream_path=ready_bit.relative_to(PKG).as_posix(),
                   bitstream_bytes=ready_bit.stat().st_size, bitstream_sha256=gate.sha(ready_bit),
                   uart_port_observed='COM11, CP2102, Started', programmed=False, uart_sent=False,
                   board_acceptance='NOT_TESTED', actual_corrected_frame_rate='NOT_MEASURED')
    save('VERSION.json', version)
    write('00_开工与版本核对声明_给管理方.md', '''# G4静态校正匹配整机候选

接收：管理方/执行者先核对版本和证据；一号协作者接收匹配采集显示整机及接口；二号协作者执行、打包及留档。用户已授权继续本轮静态校正，沿用先做版本证据核对的安排。

本包由原G4映射检查点完成原生PDS物理实现，未修改核心RTL/IP/FDC，也未降低125MHz或改变1080P30。优化为布局种子4、布线种子5、多角保持修复、保持修复最大迭代20次。原生报告All Constraints Met，DDR125慢角建立WNS=+0.183ns。首次通过后批处理自动停止，第二轮没有执行。

已生成匹配sbit及SHA256，源码、约束、映射检查点、布局布线、报告和位流之间的哈希关系均重新核对。此处“时序通过”限于报告中的已约束检查；保留原始未约束端口警告，不能推导全部外部接口约束完整。

没有烧录，没有UART下发，没有取得真实校正前后图像或新帧发布率；尚不是实板验收通过或实测30帧校正。资源不作全部低于30%的承诺（原综合APM105/240，43.75%）。
''')
    write('07_下载与板测步骤_给执行者.md', '''# 下载与板测步骤

1. 先由管理方核对VERSION.json、文件SHA256及原生rtr。06_bitstream中的sbit是本包唯一简明下载入口，匹配PG2L100H-6IFBG676、CMOS2、1080P30。校验SHA256应为3084b93d0bf15d3b632358301fa3a5f070aba7b6181866e3e33468f7e1b67cb1。旧包没有位流，本包不能混用旧包的失败报告。
2. 下载时打开PDS内Fabric Configuration（编译时不需要PDS图形界面），连接JTAG并扫描链，核对PG2L100H，给该器件指定06_bitstream内sbit，使用普通FPGA配置下载。先做SRAM运行验证；当前资料没有执行Flash固化。保持板卡正常供电、HDMI→采集卡和板载USB-UART连接。下载完成后把成功日志交回二号，二号再发参数；不要混烧测试彩条等历史位流。
3. 板载CP2102已识别COM11，115200/8N1/无流控。先运行04_uart_tool/uart_tool.py read-0x05 --port COM11，确认合法回复和固件状态。03_parameters/parameters内有恒等、真实Brown4、禁用仿射和禁用gamma的已冻结报文与CSV；由二号按恒等→真实顺序下发并记录，发送无ACK不能当作参数已生效。保持镜头、采集窗口、方向与标定一致。
4. 固定静态场景，保存原始/恒等/真实校正对应图，核对边缘直线、花点和帧完整性；用状态pub_count按16位回绕差分测真实新帧发布率，HDMI30Hz不代表校正每秒发布30张新帧。当前这些板测项全部未执行。

完整源码项目入口：01_project/full_source_1080p30.pds，状态重置为待构建，使用相对源文件路径；01_project/task1_1080p30.pds为本次原生检查点流程生成的项目，不能当完整源码入口。复现当前映射检查点物理结果使用run_checked_build.cmd；从RTL重建使用checked_build.py --full。两者均通过外部时序门禁后才生成位流，均不自动烧录。PDS安装路径与本机一致；完整源码重建尚未额外复跑，已通过的是附带实际映射检查点的P&R和位流生成。
''')
    write('08_文件校验.py', '''from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
entries=json.loads((root/'SHA256.json').read_text(encoding='utf-8'))
bad=[name for name,digest in entries.items() if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest]
print('PASS' if not bad else 'FAIL: '+repr(bad))
raise SystemExit(bool(bad))
''')
    files = {p.relative_to(PKG).as_posix(): gate.sha(p) for p in sorted(PKG.rglob('*')) if p.is_file()}
    save('SHA256.json', files)
    assert all(gate.sha(PKG / name) == digest for name, digest in files.items())
    archive = OUT / (NAME + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(PKG.rglob('*')):
            if p.is_file():
                z.write(p, NAME + '/' + p.relative_to(PKG).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    result = dict(package=str(PKG), archive=str(archive), sha256=gate.sha(archive), bytes=archive.stat().st_size,
                  files=len(files) + 1, state=version['state'], board_tested=False)
    gate.save(OUT / 'qualified_package_receipt.json', result)
    DESKTOP.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PKG, DESKTOP / NAME, dirs_exist_ok=False)
    shutil.copy2(archive, DESKTOP / archive.name)
    shutil.copy2(OUT / 'qualified_package_receipt.json', DESKTOP / 'qualified_package_receipt.json')
    assert gate.sha(DESKTOP / archive.name) == result['sha256']
    assert all(gate.sha(DESKTOP / NAME / name) == digest for name, digest in files.items())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
