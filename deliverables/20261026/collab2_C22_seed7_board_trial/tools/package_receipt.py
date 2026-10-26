"""Package the existing board measurements without further hardware writes."""
from pathlib import Path
import datetime, hashlib, json, platform, shutil, socket, sys, zipfile
BASE=Path(__file__).parent
ROOT=Path('C:/Users/叶翔/Desktop/yx/G7_C22_seed7真实板测_二号_20261026')
IN=ROOT/'给二号协作者_G7_C22_seed7真实板测与上位机准备包_20261026'
OUT=ROOT/'03_实板回传_给执行者与一号协作者'
OUT.mkdir(exist_ok=True)
def cp(src,dst):
    dst=OUT/dst;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
for d in ['02_baseline_220853','02_affine_220950','logs']:
    shutil.copytree(ROOT/d,OUT/d,dirs_exist_ok=True)
for f in ['board_trial.py','analyze_trial.py','package_receipt.py','offline_analysis.json']:
    cp(BASE/f,Path('tools')/f)
cp(ROOT/'00_开工声明_给执行者.md',Path('provenance')/'00_开工声明_给执行者.md')
cp(ROOT/'01_准备核对结果.md',Path('provenance')/'01_历史准备记录_以最终报告为准.md')
for f in ['C22八种子正式物理验证与位流报告_20261026.md','board_trial_candidate_summary.json','candidate_identity.json','hold_failure_path_inventory.json']:
    cp(IN/'05_身份与验证证据'/f,Path('provenance')/f)
cp(IN/'FILES_SHA256SUMS.txt',Path('provenance')/'输入包FILES_SHA256SUMS.txt')
incoming=Path('C:/Users/叶翔/xwechat_files/wxid_qanrp2aqlq8h22_bb90/msg/file/2026-10/给二号协作者_G7_C22_seed7真实板测与上位机准备包_20261026.zip')
assert sha(incoming)=='d310c82b9dd78c71f0dd732815e88b8de21826e9414720e6de40d43f33db1bd1'
cp(incoming,Path('inputs')/incoming.name)
ref=Path('C:/Users/叶翔/Documents/Codex/fpga-main/deliverables/20261025/collab2_module2_uart/source/reference')
cp(ref/'uart_tool_tlimfix.py',Path('reference')/'uart_tool_tlimfix.py')
for f in (ref/'parameters').iterdir():
    if f.is_file(): cp(f,Path('reference/parameters')/f.name)
cp(BASE.parent/'affine_track_loop_review_20261020/camera_devices.py',Path('reference')/'camera_devices.py')
stages=[]
for d in ['02_baseline_220853','02_affine_220950']:
    log=json.loads((ROOT/d/'board_trial.json').read_text(encoding='utf-8'))
    assert not log['errors'] and log['state']=='TRIAL_FINISHED_NOT_PRODUCTION_ACCEPTANCE'
    for s in log['stages']:
        assert all(x['valid'] for x in s['samples'])
        stages.append(dict(label=s['label'],delta=s['delta'],elapsed=s['elapsed'],fps=s['publication_fps'],
            status_samples=len(s['samples']),capture=s['capture'],
            maximum_query_duration=max(x['query_end']-x['query_start'] for x in s['samples'])))
receipt=dict(date='2026-10-26',host=socket.gethostname(),python=sys.version,platform=platform.platform(),
    candidate='G7_C22_CACHE12_MIXED seed7',
    candidate_identity_sha256='ceb0363b3db4a08e363be15c4208fa01a6d6b78baf61fd82e90ffcdf20f5a7bd',
    bit_sha256='668d08ec6e19550ec5dcd86ebfad4ef0d595b6e66e912abb56e3d3bee8eaf145',
    input_zip_sha256=sha(incoming),program_success=True,uart_port='COM11',uart_baud=115200,
    stages=stages,conclusion='REAL_CALIBRATION_30FPS_FAIL_NOT_PRODUCTION_ACCEPTED',
    affine_geometric_effect='INCONCLUSIVE_SCENE_MOVED',
    formal_multiseed_acceptance=False,
    final_state='Real calibration, Gamma disabled, affine disabled packet sent, serial/capture released',
    board_model_and_voltage='User confirms same successful G4 hardware/wiring; not independently measured')
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
table='\n'.join(f"|{s['label']}|{s['delta']}|{s['elapsed']:.3f}|{s['fps']:.3f}|" for s in stages)
report=f'''# C22 seed7 真实板测回传（二号，2026-10-26）

接收人：**执行者/管理方、一号协作者均需接收**。本包完成起机和真实参数发布率测量；真实校正约4fps，**1080p30动态畸变校正未达标**。未改候选RTL、约束或位流，未做Flash固化。

## 版本与下载

- 候选：G7_C22_CACHE12_MIXED / seed7。
- 候选身份SHA256：`{receipt['candidate_identity_sha256']}`。
- 实际Program文件：`D:\\FPGA PDS\\yx\\C22_board_20261026\\C22_seed7.sbit`。
- 位流SHA256：`{receipt['bit_sha256']}`，大小3,791,112字节。
- 输入ZIP SHA256：`{receipt['input_zip_sha256']}`。inputs保留原始完整工程包，包含源码、IP、FDC、构建/时序证据与对应位流，未重新综合。
- 构建工具：交付包PDS2022.2-SP6.4；现场下载工具SP6.1。JTAG识别PG2L100H（扫描ID记录0x00602899）。日志记录done bit=1、Program成功，用时3.6秒；见logs/pds_program_console.txt。
- 用户确认沿用G4成功的同一板卡和接线。板卡版本丝印、Bank供电及UART电压未在本轮独立测量，不能填写为全面电气验收通过。

## 实测结果

COM11（CP210x），115200-8-N-1；状态命令0x05，固件字节0x12。由真实`corr_pub_pulse`递增的16位pub_count测量唯一校正新帧发布率，按模65536求差，以单调时间戳计算窗口；每次查询保留TX/RX和时间戳。写参数无ACK，不能把发送成功等同于参数精确生效。

|模式|发布计数增量|窗口秒|唯一校正帧/秒|
|---|---:|---:|---:|
{table}

各窗口约10秒、查询间隔约0.5秒；每阶段随后读取60张采集卡帧并保留末帧PNG，均为1920×1080且非黑帧。五张PNG是HDMI采集卡解码图，非板内RGB565无损导出。采集卡设定30fps/HDMI30Hz不能当作校正30fps。恒等模式约30.16fps与名义30fps的微小差别未通过独立时钟仪器标定，不能解释为传感器超出30fps。

首次下载、下发参数前回读0x00000012，params_valid=0。发送恒等/真实参数后，各测量窗口状态params_valid均为1。真实标定包SHA256为`1ac17c4bea8947d1e4a84f50a7eaaf46c0b1d90dd4b8e8ba880bc01e0a09537a`，使用已有有效标定，没有重新标定。

仿射tx=+24/-24已发送，发送及回读日志完整；但拍摄中棋盘和手发生移动，图像特征匹配内点不足，**仿射几何响应/位移精度未验证**，不得填写PASS。动态跟踪闭环、连续30fps参数更新、长期稳定性、端到端延迟、MTF/直线度、随机彩点消除均未在本轮验收。

## 吞吐排查线索与分工

1. 二号负责核心调度、真实映射访问序列与cpp≤2；一号负责缓存内部及DDR接口等待。双方必须绑定本报告版本后联合定位，不能只凭125MHz时序闭合推断30fps。
2. 原包corr_top只覆盖SIM_MODE，undistort_core默认LINES_PER_SET=2，因此逻辑驻留4条完整源行；“CACHE12”是物理缓存DRM用量，不能解释为12条驻留源行。非恒等模式miss会装载整行120拍，装载期间暂停像素派发；现有主动预取条件仅针对恒等模式。
3. 独立浮点Brown访问画像显示：当前真实参数下，单输出行涉及源行跨度最大72行，平均约37.62行；4行驻留、轮转按需替换的简化模型估计每帧约69,916次整行加载。见tools/offline_analysis.json。**这是离线定位线索，不是实板计数或周期精确仿真，不足以单独证明约4fps的根因**；还需分离DDR仲裁/首拍/间拍等待、读写回压与发布等待。
4. 建议下一候选提供帧周期数、整行加载次数、读gnt等待/返回间隙、缓存命中及输出阻塞周期的同帧统计，并在真实参数上验证。当前o_stat_line_loads等端口在corr_top悬空，板上没有这些细分计数。
5. 125MHz下1920×1080×30的预算约2.009拍/像素，留给整帧额外开销约19,467拍（按2拍/像素基线），不能仅验证恒等映射后承诺真实参数达标。以约3.97fps折算的整链路有效成本约15.2拍/像素，仅为墙钟发布率换算，非核心内部周期实测。

## 验收与回执归属

|接收人|需处理/回执内容|
|---|---|
|执行者/管理方|登记本位流真实参数约4fps、动态30fps未通过；原包正式八种子6/8闭合仍FAIL，不晋升生产版本；统一下一次整机候选身份|
|一号协作者|基于同一候选核查缓存/DDR读写等待、源行驻留及整行miss代价；提供接口/周期变化与对应测试证据，跨模块路径共同确认|
|二号（本方）|保留本次源码/位流/参数身份与实测脚本，后续对核心调度及cpp≤2负责；本包没有进行未经验证的RTL替换|

seed7本身八项时序均正裕量，最小+0.103ns；原包正式多种子6/8未满足门槛，二者结论并不矛盾。固定工具18/18通过；本机UART自测U0-U3通过、U4/U5因WinError5未完成，保留原日志，没有声明完整自测PASS。

测试结束已恢复真实标定、Gamma关闭、发送仿射关闭包，释放串口及采集卡；板上仍为C22 seed7，未切回G4。断电后SRAM配置丢失；再次上电需重新Program，并下发参数后出画面，本轮未加入上电参数固化。

## 包内索引及复现范围

- `receipt.json`：测量摘要与环境；`02_baseline_220853`/`02_affine_220950`：串口原始事务、逐次状态、PNG及预览。
- `inputs`：原始完整工程包；`provenance`：原候选身份、多种子报告和历史准备记录，历史“尚未下载”等内容由本报告续接。
- `reference`：实际UART工具及参数、摄像头枚举帮助程序；`tools/board_trial.py`是本机实际执行脚本，保留原绝对路径以便审计，**不是免配置的一键跨机器程序**。迁移时先核对路径/设备和位流SHA，不要误重跑板端写入。
- `tools/analyze_trial.py`为离线诊断，使用numpy/opencv；浮点画像不是RTL golden验收。`FILES_SHA256SUMS.txt`绑定除自身外全部文件。
'''
(OUT/'00_实板结论与分工_给执行者和一号.md').write_text(report,encoding='utf-8')
manifest=[]
for p in sorted(OUT.rglob('*')):
    if p.is_file() and p.name!='FILES_SHA256SUMS.txt':manifest.append(f'{sha(p)}  {p.relative_to(OUT).as_posix()}')
(OUT/'FILES_SHA256SUMS.txt').write_text('\n'.join(manifest)+'\n',encoding='utf-8')
archive=ROOT/'C22_seed7实板回传_二号_20261026.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(OUT))
with zipfile.ZipFile(archive) as z: assert z.testzip() is None
(ROOT/'C22_seed7实板回传_二号_20261026.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n',encoding='utf-8')
print(json.dumps(dict(folder=str(OUT),zip=str(archive),zip_bytes=archive.stat().st_size,zip_sha256=sha(archive),files=len(manifest)),ensure_ascii=False))
