"""Prepare readable reports, immutable-input manifests, and verified handoff ZIPs."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib, json, re, zipfile

ROOT = Path(__file__).resolve().parents[1]
WW = ROOT.parent

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + '\n', encoding='utf-8')

def dump(rel, obj):
    write(rel, json.dumps(obj, ensure_ascii=False, indent=2))

frozen = {}
warnings = {}
for kind in ('core', 'host'):
    base = ROOT / 'evidence' / ('synth_' + kind)
    r = json.loads((base / 'process_receipt.json').read_text(encoding='utf-8'))
    audit = json.loads((base / 'fixed_input_audit.json').read_text(encoding='utf-8'))
    if audit['audit_status'] != 'PASS':
        raise RuntimeError('Fixed-input audit failed')
    for p, expected in r['inputs_before'].items():
        if sha(ROOT / p) != expected:
            raise RuntimeError('Changed frozen input: ' + p)
        frozen[p] = expected
    log = (base / 'console.log').read_text(encoding='utf-8', errors='replace')
    selected = [dict(line=i, text=line) for i, line in enumerate(log.splitlines(), 1)
                if re.match(r'^[CW]:', line)]
    codes = Counter(re.match(r'^[CW]:\s*([^:]+):', x['text']).group(1)
                    if re.match(r'^[CW]:\s*([^:]+):', x['text']) else 'OTHER' for x in selected)
    critical = [x for x in selected if x['text'].startswith('C:')]
    warnings[kind] = dict(console_sha256=sha(base / 'console.log'),
                          warning_and_critical_line_count=len(selected),
                          critical_line_count=len(critical), code_counts=dict(codes),
                          critical_lines=critical, count_scope='console occurrences, not deduplicated DRC categories')
    write(f'evidence/synth_{kind}/warning_lines.txt', '\n'.join(f"{x['line']}: {x['text']}" for x in selected))
dump('evidence/warning_index.json', warnings)
dump('handoff/frozen_execution_inputs.json', dict(scope='ORIGINAL_INPUT_SET_BEFORE_SP6_1_RUN', files=frozen))

write('docs/AB新哈希综合与独立任务交付报告.md', '''
# A+B新哈希综合与独立任务交付报告

2026-10-24整理交付，综合实际执行于2026-10-23。一号协作者。本报告追加新实跑事实，不替换管理方v2.0.4、不宣告生产晋升。用户本轮安排：优先A+B独立任务，G4接核/板测暂停，等待新的优化核心。

## 本轮结论

冻结A+B新core哈希 `9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68` 的独立核和真实宿主均完成本机PDS综合，但125MHz时序均未通过。没有修改RTL、生产G4或原FDC；没有加入新map/G8，没有执行dev_map/布局布线、生成位流或烧板。

| 本轮实际任务 | 工具 | LUT | FF | APM | DRM（36K等效） | 125MHz综合WNS | 结论 |
|---|---|---:|---:|---:|---:|---:|---|
| 独立A+B核 | PDS2022.2-SP6.1 build138931 | 21461 | 11548 | 105 | 9.0 | −0.796ns | 综合完成，时序FAIL |
| 真实A+B宿主 | 同上 | 28830 | 23310 | 105 | 22.5 | −1.226ns | 综合完成，时序FAIL |

器件PG2L100H/FBG676/−6；SIM_MODE=0；配置1920×1080@30。独立核121.844秒，宿主334.063秒，两个PDS进程均退出0，均有Synthesize done。原生报告记录本次2026-10-23生成时间。数值虽与旧报告相同，本次有新哈希输入/命令/PID/起止/日志及原生产物，未套用修正前结果。SP6.4复验仍未执行。

原生报告：`core/synthesize/undistort_core.snr`、`host/synthesize/hdmi_ddr_ov5640_top.snr`。完整命令、运行前后哈希及产物索引：`evidence/synth_core/process_receipt.json`与`synth_host/process_receipt.json`。

## 记录器误报与复核

v1记录器把PDS新生成的`ab_r1r4_core.pds`/`ab_r1r4_host.pds`误算成输入集合变化，因此两份原始receipt为FAILED，启动器返回1；这不等于PDS综合失败。原始receipt、console、v1脚本全部保留，未改成PASS。

`fixed_input_audit.json`固定运行前路径集合核验：core6项、host141项原输入均未变，各19项compile/synthesize产物、console及工具SHA均匹配。仅新增上述两个工具项目文件。独立复核PASS，综合完成；时序仍FAIL。

新增v2启动器按原路径集合复核，把新增项目文件单列；拒绝覆盖已有compile/synthesize目录。`evidence/runner_v2_check.json`记录6项记录逻辑/CLI检查PASS（包含修改、删除原输入的检测）。本轮PDS实际由v1执行，v2未重新跑PDS，不能混记。

## 关键路径及资源口径

独立核最差路径：`u_map/N46_m4/CLK → u_map/kr2_4[63]/D`；宿主：`u_correction/u_core/u_map/N46_m4/CLK → …/kr2_4[63]/D`，位于125MHz的`ddrphy_sysclk`域。两者均为原map宽乘法后的收敛路径；本轮未扩大map修改范围。

独立核原生单元为8个DRM36K＋2个DRM18K＝9.0等效；宿主16个DRM36K＋13个DRM18K＝22.5等效。map占87 APM、bilinear占18，总105；cache模块占8 DRM，独立核cache统计16677 LUT/8074 FF，宿主cache16670 LUT/8074 FF。分层优化会影响LUT/FF，不能直接按模块粗加替代设备总表。24KiB为缓存有效图像容量，不是“24KiB就等于全部物理RAM”；标签/LRU/FIFO及分布式存储另占资源。本轮没有dev_map资源表，不伪造综合与物理两表一致性。

## 警告及物理评估限制

完整警告原文和行号见`evidence/warning_index.json`、各`warning_lines.txt`及原console。计数按console出现次数，core1条、host54条C级诊断，不套用其他候选的38条。

- 独立核C级SDC-2025提示clk需要显式时钟约束。当前仅`-frequency 125`内部综合估计，外部参数等路径也有未约束提示；不能据此宣布全路径约束/收敛。PNR须冻结专用wrapper与FDC、I/O测量边界。
- 宿主18条未驱动诊断对应旧`cmos2_d_16bit[15:0]`、href/pclk调试网；检索当前top仅有带MARK_DEBUG的声明，无实际数据通路使用。保留原样并回传，不擅自删冻结网。另36条为原FDC share-pin提示，应按实际板卡/配置审阅。
- 宿主原FDC缺UART RX/TX引脚、电气和I/O约束；不猜引脚，不用自动分配结果发布下载位流。
- rd/wr_fram_buf IP元数据为FBG484而宿主为FBG676，日志有Flow-4058；需执行方核对IP适用性及是否需要重新生成，不能把综合完成当成此项闭环。
- 缓存存在last_use多写RAM不支持、反馈mux等综合提示；完整原件保留供资源/时序复核，不按警告条数直接认定功能失败或全部豁免。

`multiseed_summary.csv`中的PNR单种子栏全部NA，0%不是“已跑多个种子全部失败”；实际未做PNR。综合WNS、模型fps和板端新帧发布率三个证据层次分别保留。原生hold/setup物理结论尚缺，不生成可下载位流。

## 其他独立交付

T02 V1.1合并稿、原文/裁定/已收到ModelSim日志、diff及算术核对在`T02/`。已将R01恢复总历时3728与接受拍3724的口径及前提并入正文；没有改RTL/TB，也未重跑已闭环W0–W8。该稿由一号按已生效裁定整理，待设计方审阅归档，非设计方新签发版本。

新核心接入前检查、最终网表W9/W10与FIFO记录准备、待协作者统一材料清单均已完成。新优化核心未收到，兼容性实际核验/融合未开始。M01软件已有普通/−O独立复验；P10及真实FIFO/画质素材受本轮暂停安排影响，保持未测。全部任务状态见`任务台账与续接.md`。
''')

write('任务台账与续接.md', '''
# 一号任务台账与续接

更新2026-10-24。以后工程、资料、回执及续接统一保存在桌面ww；现行管理资料v2.0.4保持不变。最新用户安排优先于旧任务表：暂停以G4接核为前提的实机任务，等待优化核心；A+B独立评估继续，禁止自动融合或生产晋升。

| 任务 | 当前状态 | 本轮交付/下一动作 |
|---|---|---|
| WP-2 A+B RTL/cache72/C6/R1–R4 | 既有范围已完成，不重做 | 本轮原RTL不改；已有Icarus16项与设计方ModelSim4项来自前序证据 |
| WP-2 新哈希独立核+真实宿主综合 | 本轮完成，125MHz时序FAIL | 新原生SNR、日志、输入/产物哈希及记录器误报复核；SP6.1不是SP6.4 |
| WP-2 SP6.4/独立物理评估 | WAIT_EXTERNAL，尚未PNR | E01–E04材料：实际执行工具、可信约束、测量范围、IP与警告审查；不得猜管脚 |
| A+B与新优化核心兼容/融合准备 | 检查清单完成；实现待包/裁定 | N01–N04收到后核对版本、周期、数值/复位/资源。未改map、未吸收G8、未融合 |
| WP-1 G4静态接核板测 | PAUSED_BY_USER | 待新核/唯一整机及恢复板测安排；当前不要求用户采集旧G4素材 |
| WP-3 同条件RTL性能 | 已有二号六帧证据核对完成 | AB/G8共12441600像素零差异；真实快速/压力AB折算30.138514/30.036005fps，125MHz模型假设，非板测 |
| WP-3 真实新帧发布率 | PAUSED_BY_USER，未测 | 恢复后位流/参数/干净会话/原始计数与时间边界 |
| M01 软件 | 已完成并有二号软件复验 | P01–P09普通/−O、UART U0–U5及CLI已有PASS/SYNTHETIC，无新功能待开发；P10实机未测 |
| rect_wr_if T02 V1.1 | 本轮合并/算术核对完成；待设计方审阅归档 | 正文、diff、R01前提、3728历时/3724接受拍及原始证据；不重开已闭环裁定 |
| 板端FIFO水位/压力 | 准备完成，实机PAUSED_BY_USER | 模板已备；无实测值，不填假数 |
| W9/W10最终网表 | 准备完成，WAIT_FINAL_NETLIST | 需最终网表/库/SDF/角点/输入身份，再按U1–U6+D1–D3+R01执行；NOT_RUN |
| M03实际画质/PC闭环 | 条件待办、二号负责分析 | 一号后续供B03同条件素材；不重复制作二号软件，不声称画质已验证 |
| H01/H02/H03、H04最终融合 | 未派工/条件未达 | 协议、预算、算法或唯一融合输入未冻结；不占用预留命令/位域，不提前实施 |
| M02/R03 | 管理方/二号责任 | 不擅自改派一号、不重复828项矩阵 |

下一步：把`待转交`两个ZIP分别交执行方和二号/设计方；按`docs/待协作者统一提供材料清单.md`的ID一次性收齐回件。只对新输入、实际失败或未决问题复验。当前没有后台PDS/全帧仿真在运行，没有生成新sbit，也没有烧录。

不要将原v1 receipt的FAILED抹掉；新的fixed_input_audit是追加证据。后续重跑请解压干净输入ZIP，用v2且换新目录，保留原失败/中断轮。所有新源文件/文档仍放ww，旧目录只留续接指针。
''')

write('README.md', '''
# A+B独立任务交付（20261024，综合记录20261023）

2026-10-24已恢复并完成本轮整理；`暂停续接_20261023.md`、`保存核验_20261023.json`仅为历史快照，其“尚未生成”不代表当前状态。

先读`docs/AB新哈希综合与独立任务交付报告.md`和`任务台账与续接.md`。本轮新哈希综合已完成，独立核/宿主125MHz WNS为−0.796/−1.226ns，时序未通过；未PNR、未产位流、未烧板。G4板级任务按用户要求暂停。

- `core/`、`host/`：冻结A+B源码、IP及本轮原生综合产物，适合查证，不在此目录重跑覆盖。
- `evidence/`：原v1执行回执、完整日志、固定输入集合追加复核及v2记录逻辑检查。原receipt为FAILED的原因见报告，不隐藏。
- `handoff/AB_frozen_synthesis_inputs.zip`：干净输入包，供执行方另行解压重跑。具体入口看`docs/AB执行方SOP.md`。
- `T02/`：合并正文、差异、裁定及既有ModelSim证据；等待设计方归档。
- `docs/待协作者统一提供材料清单.md`：一次性需要的回执/源码/约束/日志/数据，按ID回复。
- `docs/新优化核心接入前检查.md`、`templates/`：准备材料，不代表融合/网表/实机测试完成。
- `sim/`、`verification_data/`、`integration/`、`reference/`及`comparison_reference/`：沿用验证输入/参考，非本轮新增RTL测试结果。历史生成器`build_candidate_sources.py`原样存档，其路径布局不适配当前core子目录，勿当作本包重建入口；综合使用Tcl和干净输入包。
- `docs/*原件.md`等历史接收材料不改历史表述；旧“新哈希未综合”状态以本轮报告为准，不改写旧证据。

本轮文件不是可直接下载的板级合格工程。继承`host/build.tcl`含全流程/位流步骤，保留用于核对，不能绕过UART约束及物理门禁直接使用。
''')

# Additional issues found in this actual run: fold into one request list.
p = ROOT / 'docs/待协作者统一提供材料清单.md'
s = p.read_text(encoding='utf-8')
if '| E04 |' not in s:
    row = '| E04 | 设计方/执行方 | 审阅本轮warning_index及原日志：独立核显式时钟/未约束输入、宿主36条share-pin与18条旧调试网、FBG484 IP元数据/FBG676工程差异、last_use RAM综合映射；按项给依据/处理或例外意见，变更须附diff及新输入身份 | 新哈希物理准备；不把54条C级诊断套用其他候选38条，也不擅自删冻结调试网或重生成IP |\n'
    s = s.replace('| D01 |', row + '| D01 |', 1)
    p.write_text(s, encoding='utf-8')

# Construct a clean execution tree without inheriting generated PDS/results.
entries = {k: (ROOT / k).read_bytes() for k in frozen}
entries['tools/run_synthesis_v2.py'] = (ROOT / 'tools/run_synthesis_v2.py').read_bytes()
entries['tools/verify_package.py'] = (ROOT / 'tools/verify_package.py').read_bytes()
entries['README.md'] = '''# 冻结A+B综合输入

本包只有输入，不含前轮compile/synthesize。Python标准库即可。ZIP可用外层tools/verify_package.py独立校验；源文件完整性不等于技术验收。

python -B -X utf8 tools/run_synthesis_v2.py --pds D:/tools/PDS/bin/pds_shell.exe --timeout 1800 --run-label executor_sp64_01

将--pds替换为实际PDS；工具版本以原生报告为准。每轮重新解压到新目录，不覆盖证据。core/synth.tcl和host/synth_only.tcl为综合入口；旧.pds可能含历史路径，勿用其GUI默认配置冒充此入口。host/build.tcl包含位流生成，本批不执行。

仅综合，125MHz；未冻结PNR约束/测量wrapper/UART实际引脚前不得发布可下载位流。具体待办见执行方交付外层SOP和材料清单。原run_synthesis.py保留用于关联旧输入身份；重跑使用v2。
'''.encode('utf-8')
entries['original_frozen_input_hashes.json'] = json.dumps(frozen, indent=2).encode('utf-8')

def make_zip(path, prefix, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = [dict(file=k, bytes=len(v), sha256=hashlib.sha256(v).hexdigest()) for k, v in sorted(files.items())]
    if 'files_sha256.json' in files:
        raise RuntimeError('reserved manifest filename')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for k, data in sorted(files.items()):
            z.writestr(prefix + '/' + k, data)
        z.writestr(prefix + '/files_sha256.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise RuntimeError('ZIP CRC failed')
        if len(z.namelist()) != len(manifest) + 1:
            raise RuntimeError('ZIP count mismatch')
        for e in manifest:
            data = z.read(prefix + '/' + e['file'])
            if len(data) != e['bytes'] or hashlib.sha256(data).hexdigest() != e['sha256']:
                raise RuntimeError('ZIP digest mismatch: ' + e['file'])
    return dict(file=str(path), bytes=path.stat().st_size, sha256=sha(path),
                entries=len(manifest) + 1, status='CRC_AND_ALL_FILE_SHA256_PASS')

inner = make_zip(ROOT / 'handoff/AB_frozen_synthesis_inputs.zip', 'AB_inputs', entries)
dump('handoff/input_zip_verification.json', inner)

all_files = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sorted(ROOT.rglob('*'))
             if p.is_file() and '__pycache__' not in p.parts}
out = WW / '待转交'
out.mkdir(parents=True, exist_ok=True)
(out / 'verify_package.py').write_bytes((ROOT / 'tools/verify_package.py').read_bytes())
executor = make_zip(out / '给执行方_AB新哈希综合证据与物理评估输入_20261024.zip', ROOT.name, all_files)
review = {k: v for k, v in all_files.items()
          if k.startswith(('docs/', 'T02/', 'templates/', 'evidence/'))
          or k in ('README.md', '任务台账与续接.md', 'handoff/frozen_execution_inputs.json')
          or k.endswith(('.snr', 'multiseed_summary.csv'))
          or k.startswith('tools/')}
review['交付范围说明.md'] = '''# 给二号与设计方

这是审查资料包：本轮综合报告/原生日志和SNR、T02合并及差异、统一材料清单、接入与W9/W10准备。完整RTL/IP、综合数据库及干净执行输入在同批“给执行方”ZIP中，本精简包不重复大文件。原回执输入清单仍完整保留；其中源码/数据库相对路径在完整包内有效。audit_synthesis.py依赖完整包与本机原工具，不能在本精简包里独立重放。

请按材料清单ID回复具体技术意见或原件，已通过事项不重复索取。G4板测暂停，T02仅文档归档待审，不是重新申请R01裁定。
'''.encode('utf-8')
designer = make_zip(out / '给二号及设计方_独立进展T02合并与材料清单_20261024.zip', 'AB_review_20261024', review)
result = dict(generated_utc=datetime.now(timezone.utc).isoformat(), packages=[executor, designer])
(out / '打包核验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(out / 'SHA256SUMS.txt').write_text(''.join(p['sha256'] + '  ' + Path(p['file']).name + '\n' for p in result['packages']), encoding='utf-8')
(WW / 'README_从这里开始.md').write_text('''# 一号协作者资料入口

用户安排：A+B独立工作优先，G4接核/板测暂停，等优化核心；以后新工程、资料、回执都放这里。

## 转交这两个包

1. **给执行方**：`待转交/给执行方_AB新哈希综合证据与物理评估输入_20261024.zip`。含完整源码/IP、原生综合证据及内层干净输入ZIP；按SOP执行。
2. **给二号和设计方**：`待转交/给二号及设计方_独立进展T02合并与材料清单_20261024.zip`。含进展、原生日志/SNR、T02合并/diff、统一待提供清单及接入准备。

两个包均已逐文件SHA256和ZIP CRC核验；校验值在`待转交/SHA256SUMS.txt`。接收方可用Python标准库执行`python -B -X utf8 verify_package.py 包名.zip`核验完整性。文件只是准备好，没有自动发送。

## 查工程与进度

- 工程及资料总目录：`AB_independent_20261023/`。
- 任务不漏项表及下次入口：`AB_independent_20261023/任务台账与续接.md`。
- 统一向协作者要的材料：`AB_independent_20261023/docs/待协作者统一提供材料清单.md`；优先N01–N04和E01–E04，D01为文档归档，B类实机项暂停、W01等最终网表。
- 本轮报告：`AB_independent_20261023/docs/AB新哈希综合与独立任务交付报告.md`。

本轮A+B新哈希独立核/宿主综合完成，125MHz时序均FAIL（−0.796/−1.226ns）；只有SP6.1实跑，没有SP6.4/PNR/新位流/板验。T02文档合并完成，待设计方审阅归档。已通过的M01软件及AB功能不重复制作。原v1记录器误报保留并附复核，不能把综成功写成整机通过。
''', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
