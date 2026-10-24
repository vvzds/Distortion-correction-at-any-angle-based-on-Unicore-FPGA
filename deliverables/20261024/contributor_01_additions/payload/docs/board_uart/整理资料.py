from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,re,subprocess,shutil,struct,zipfile

ROOT=Path(__file__).resolve().parent
WW=ROOT.parent
BOARD=Path(r'D:\FPGA PDS\盘古100Pro+开发板（MES2L676-100HP）配套资料')
CAL=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\outputs\calibration_brown4_1080p30_20261022')
HOST=WW/'AB_independent_20261023/host'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write(name,s):(ROOT/name).write_text(s.strip()+'\n',encoding='utf-8')

for name in ['reference','parameters','templates','evidence']:(ROOT/name).mkdir(exist_ok=True)
source_manifest=[]
def copy(p,name):
    dst=ROOT/name;shutil.copyfile(p,dst)
    source_manifest.append(dict(source=str(p),copy=name,bytes=dst.stat().st_size,sha256=sha(dst)))

manual=next(BOARD.rglob('教程1_硬件实验指导手册*.pdf'))
copy(manual,'reference/厂商硬件实验指导手册.pdf')
archive=BOARD/'2_Demo/2_8_uart_test.rar'
member='2_8_uart_test/2_8_uart_test/uart_test.fdc'
proc=subprocess.run(['tar','-xOf',str(archive),member],capture_output=True,check=True)
(ROOT/'reference/uart_test_厂商原件.fdc').write_bytes(proc.stdout)
source_manifest.append(dict(source=str(archive),archive_sha256=sha(archive),member=member,
                            copy='reference/uart_test_厂商原件.fdc',sha256=sha(ROOT/'reference/uart_test_厂商原件.fdc')))
remote=BOARD/'9_远程升级/FPGA_remote_update/pg2l100h_remote_update/remote_update_golden/prj/pg2l100h_remote_updata.fdc'
copy(remote,'reference/remote_update_厂商原件.fdc')
copy(CAL/'received/标定结果说明(1).md','reference/标定结果说明_原件.md')
for p in (CAL/'parameters').iterdir():
    if p.is_file():copy(p,'parameters/'+p.name)
copy(CAL/'reports/verification_summary.json','reference/既有标定仿真总结.json')
dump(ROOT/'evidence/来源清单.json',source_manifest)

def uart_attributes(text):
    attrs={}
    for port,key,value in re.findall(r'define_attribute\s+\{p:(uart_rx|uart_tx)\}\s+\{([^}]+)\}\s+\{([^}]+)\}',text):
        attrs.setdefault(port,{})[key]=value
    return attrs
uart=uart_attributes(proc.stdout.decode('utf-8-sig'))
remote_attrs=uart_attributes(remote.read_text(encoding='utf-8-sig'))
for a in (uart,remote_attrs):
    assert a['uart_rx']['PAP_IO_LOC']=='B24' and a['uart_tx']['PAP_IO_LOC']=='C24'
    assert all(a[x]['PAP_IO_STANDARD']=='LVCMOS33' and a[x]['PAP_IO_VCCIO']=='3.3' for x in a)
fdc=HOST/'HDMI_DDR3_OV5640_test.fdc';txt=fdc.read_text(encoding='utf-8-sig')
pins=re.findall(r'define_attribute\s+\{p:([^}]+)\}\s+\{PAP_IO_LOC\}\s+\{(B24|C24)\}',txt)
top=(HOST/'source/rtl/hdmi_ddr_ov5640_top.v').read_text(encoding='utf-8-sig')
dump(ROOT/'evidence/UART约束核对.json',dict(status='DOCUMENT_CROSSCHECK_PASS_PHYSICAL_BOARD_UNCONFIRMED',
    manual_pages=[43,44],manual_printed_pages=[39,40],uart_demo=uart,remote_demo=remote_attrs,
    tx_drive_conflict='8mA UART demo vs 12mA remote update demo; both SLOW',
    host_fdc_sha256=sha(fdc),host_uart_attributes=uart_attributes(txt),host_b24_c24_claims=pins,
    top_uart_lines=[dict(line=i,text=l.strip()) for i,l in enumerate(top.splitlines(),1) if re.search(r'\b(input|output)\b.*uart_(rx|tx)',l)],
    actual_board_revision=None,actual_connection=None,live_vccio_measurement=None,
    applied_to_project=False,com_status='CIM_ACCESS_DENIED_REGISTRY_NOT_CONFIRMED_NO_SERIAL_OPEN'))
lines=['# REVIEW ONLY: not sourced by any build; hardware identity/connection and timing review pending.',
       '# Manufacturer UART demo uses DRIVE 8; remote-update demo uses 12. No single final DRIVE chosen.']
for port in ['uart_rx','uart_tx']:
    for key in ['PAP_IO_DIRECTION','PAP_IO_LOC','PAP_IO_VCCIO','PAP_IO_STANDARD','PAP_IO_SLEW']:
        if key in uart[port]:lines.append(f'define_attribute {{p:{port}}} {{{key}}} {{{uart[port][key]}}}')
lines += ['# TX DRIVE unresolved: UART demo 8mA, remote-update demo 12mA.',
          '# No input_delay/output_delay/false_path invented. Not a complete timing constraint.']
write('UART约束共同部分_仅供审阅.fdc.txt','\n'.join(lines))

encoding=json.loads((ROOT/'parameters/parameter_encoding.json').read_text(encoding='utf-8'))
frames=[]
for p in sorted((ROOT/'parameters').glob('*.bin')):
    b=p.read_bytes();ok=b[:2]==b'\xaa\x55' and len(b)==b[3]+5 and (sum(b[4:-1])&255)==b[-1]
    if not ok:raise RuntimeError('frame validation failed '+p.name)
    frames.append(dict(file=p.name,bytes=len(b),cmd=b[2],payload_length=b[3],checksum=b[-1],sha256=sha(p),status='PASS_NOT_SENT'))
real=(ROOT/'parameters/real_0x01.bin').read_bytes();values=list(struct.unpack('<8i',real[4:-1]))
assert values==[v['signed_integer'] for v in encoding['parameters']]
assert encoding['order']==['fx','fy','cx','cy','k1','k2','p1','p2']
assert encoding['image']==[1920,1080] and encoding['fps']==30
dump(ROOT/'evidence/参数包离线复核.json',dict(status='PASS',frames=frames,parameter_order=encoding['order'],
    signed_q16_match=True,source_parameters_unchanged=True,serial_sent=False,
    physical_optics_unchanged=None,original_35_images='NOT_FOUND_IN_SEARCHED_LOCATIONS'))
dump(ROOT/'templates/实测会话_待填写.json',dict(status='TEMPLATE_NOT_CAPTURED',timezone='Asia/Shanghai',run_id=None,
    board_core_version=None,board_base_version=None,uart_connection=None,com_port=None,
    lens_changed_since_calibration=None,focus_changed=None,window_or_orientation_changed=None,
    image_width=1920,image_height=1080,target_capture_fps=30,bitstream_file=None,bitstream_sha256=None,
    source_sha256=None,constraint_sha256=None,parameter_files=[],uart_raw_records=None,
    capture_fps_measured=None,hdmi_refresh_measured=None,new_frame_publication_rate=None,
    fifo_watermark_definition=None,fifo_peak=None,exposure=None,white_balance=None,
    roi=None,target_square_size_mm=25,target_inner_corners=[11,8],before_image=None,after_image=None,
    calibration_session='session_203513',notes=[]))
write('实测准备与操作顺序.md','''
# 实测准备与操作顺序（准备完成，尚未采数）

保持当前1920×1080@30配置。此次不启动旧G4板测，不连接或发送串口命令。准备材料已复制至parameters、reference，均保留原字节与来源哈希。

## 现在可准备

1. 对照板卡丝印记录核心板/底板型号及版本，确定使用板载CP2102的USB Type-C接口还是外接USB-TTL；USB接口不要与JTAG下载口混同。实际接口尚待用户回复。
2. 保存10月22日标定对应镜头/焦点、传感器窗口、缩放及上下左右方向。若已改动，标记“不一致待核对”，不直接宣称原标定仍适用，也不先改参数符号。
3. 找回session_203513的35张原始PNG、角点/采集记录、calibration_comparison.json、brown4_candidate_parameters.json和solve_calibration.py。现有MD记载前30张拟合、后5张留出；本机已检索桌面、Codex工作区及D盘命名匹配，未找到原始照片本体。此结果不证明其他目录/电脑没有照片。
4. 使用现有12×9格、11×8内角点、25mm格距棋盘；另备笔直边框/尺边。不要缩放打印后仍把格距填25mm；以实际尺寸为准。此次不生成替代原标定图，也不要求重新标定。
5. 固定摄像头、靶标与照明；记录焦点、曝光、白平衡及采集卡设置。对比前后尽量同一机位/场景/参数与相同原始尺寸；中心、边缘和四角分别观察。原标定角点覆盖约x109～1769/y72～1008，四角不宜宣称已精确验证。
6. `templates/实测会话_待填写.json`字段为空是未采集，不是0或PASS。原图应单独保存，截图、叠字或前后拼图只作预览，不能替代原始素材。

## 等最终整机通过并恢复板测后

先记录位流/源代码/约束哈希和板卡信息，再按既有流程关闭仿射及Gamma影响、恒等参数→真实参数。parameters中的0x01/0x02/0x04二进制已做离线字节数/校验和/参数顺序复核，但此次未发送，不因存在.bin就认定已经在板端生效。

逐项检查方向、颜色、首尾行、直线弯曲和边缘；记录0x05活性及M01原始时间/发布计数。摄像头采集帧率、HDMI刷新率、新校正帧发布率分开。FIFO水位/压力用已确认信号定义记录，不新增未批准协议位域。

每组恒等/真实模式保存位流与实际参数、时间、原始帧和UART会话关联。连续稳定性、随机彩点、停顿及断连照实记录；不预填fps或合格结论。原图/ROI/条件交二号做M03画质分析，板端记录交管理方验收。
''')
write('UART核对结论_给设计方与执行方.md','''
# UART板载引脚与电气依据核对

2026-10-24。本轮完成厂商资料交叉核对，补足E02此前“没有引脚/电气文档依据”的部分；实际板型、连接路径、供电与最终约束仍需核对。未改冻结FDC、未重综合/烧录。

| FPGA顶层端口 | FPGA方向 | 焊球 | 厂商例程VCCIO/标准 | 例程SLEW |
|---|---|---|---|---|
| uart_rx | 输入，PC→FPGA | B24 | 3.3V / LVCMOS33 | 输入不设 |
| uart_tx | 输出，FPGA→PC | C24 | 3.3V / LVCMOS33 | SLOW |

硬件手册§2.1.3.2.5，PDF第43/44页（印刷39/40页）给出FPGA_UART_RXD=B24、TXD=C24，板载CP2102，USB Type-C。已渲染并人工看过完整相关页，原PDF和页图在reference/evidence。手册示意图的CP2102端RXD/TXD字样与常规芯片方向存在容易混淆的标注；引脚以FPGA端方向表及厂商两份实际约束交叉确认，不按示意图给外接线强行同名连接。

厂商2_8_uart_test.rar内uart_test.fdc和PG2L100H远程升级例程均支持B24/C24、LVCMOS33、3.3V和TX SLOW。**TX DRIVE不一致：串口例程8mA，远程升级例程12mA。**两份原约束已保存，不把其中任一值冒称项目唯一冻结值。执行方结合实际板型、电压/负载与板级规则确定，并记录选择依据。

当前AB宿主FDC确实没有uart_rx/uart_tx属性；精准匹配未见其他端口占用B24/C24（AB24/AC24不算同一球）。顶层存在对应UART端口，详情见evidence/UART约束核对.json。

提供UART约束共同部分_仅供审阅.fdc.txt，故意使用.txt且不进入任何工程构建。它不包含未决定的TX DRIVE，不编造input/output delay、异步false path或时钟约束，不能直接当完整签核FDC。

需要确认的剩余项目：实际核心板/底板丝印版本；是否使用板载串口而不是外接扩展口；VCCIO实际符合厂商版本；TX DRIVE采用8或12的依据；UART异步输入同步/时序例外及整机时钟审核。用户文字确认或现场核对后再作为独立约束变更评审，保留新FDC diff/SHA。

本机串口查询：Win32_SerialPort只读查询返回访问被拒绝，注册表查询未取得可确认结果。不能推断没有串口、驱动未安装或设备已正常；没有打开COM或发送字节。

原理图.sch为二进制文件，本轮仅识别网名，不声称完成该格式的电路连通/供电审查。3.3V电气依据来自厂商FDC，不是本轮电压实测。
''')
write('README.md','''
# 板卡与实测准备 20261024

本轮完成：厂商UART引脚/电气依据交叉核对；既有标定参数完整复制及离线检查；实测条件、原始资料缺项和会话模板整理。未运行G4板测、未发送串口、未改冻结RTL/FDC。

- 给设计方和执行方：`UART核对结论_给设计方与执行方.md`、原始厂商FDC、手册相关页与来源哈希。可减少E02缺件范围，不能把板型/实际接线已确认写成事实。
- 给自己/负责实机的队友：`实测准备与操作顺序.md`与空会话模板，先固定镜头/靶标和保留资料，等最终整机及恢复板测安排后执行。
- 给二号/M03协作者：请协助找回session_203513原始35图/记录/求解脚本；只靠现有说明和预览无法补齐实拍证据。参数包及完整数据仍按原标定适用条件核对。
- `parameters/`已复制既有Brown4/恒等、关闭仿射/Gamma指令。离线核对4帧的长度、校验、Q16.16顺序均通过，均未下发。
- `UART约束共同部分_仅供审阅.fdc.txt`不进入构建，不是可签核完整约束。

用户实际板型/连接和镜头是否改变的问题已发出，当前无回复，因此模板保留未知，不擅自确认。旧交付ZIP保持不变，本包是增量证据。
''')
files=[p for p in sorted(ROOT.rglob('*')) if p.is_file()]
manifest=[dict(file=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
out=WW/'待转交/给设计方及执行方_UART依据与实测准备_20261024.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,'board_preparation_20261024/'+p.relative_to(ROOT).as_posix())
    z.writestr('board_preparation_20261024/files_sha256.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for item in manifest:assert hashlib.sha256(z.read('board_preparation_20261024/'+item['file'])).hexdigest()==item['sha256']
receipt=dict(status='ZIP_CRC_SHA256_PASS',date='2026-10-24',utc=datetime.now(timezone.utc).isoformat(),
    file=str(out),bytes=out.stat().st_size,sha256=sha(out),files=len(manifest),
    validation='UART_DOCUMENTS_AND_PARAMETERS_OFFLINE_ONLY',physical_board='UNCONFIRMED',board_test='PAUSED')
dump(WW/'待转交/UART准备包核验_20261024.json',receipt)
print(json.dumps(receipt,ensure_ascii=False,indent=2))
