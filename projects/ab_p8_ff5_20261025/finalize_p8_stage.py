from pathlib import Path
import json,hashlib,re,collections,datetime,zipfile,shutil,ctypes
W=Path(r'C:\Users\lenovo\Desktop\ww');R=W/'AB_P8触摸译码局部化_20261025';B=W/'AB_P7R1标签RAM与共享比较_20261025'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
gate=load(R/'results/synthesis_gate/result.json');proc=load(R/'results/synthesis_gate/process_receipt.json')
assert not gate['passed'] and [k for k,v in gate['gates'].items() if not v]==['ff_budget']
assert proc['state']=='FINISHED' and proc['exit_code']==0 and not proc['changed_input_files'] and not proc['bitstreams_present']
assert gate['no_pnr_executed']
assert len(load(R/'results/equivalence_p7/summary.json')['results'])==5 and all(x['pass'] for x in load(R/'results/equivalence_p7/summary.json')['results'])
assert all(x['pass'] for x in load(R/'results/banks_p7/summary.json')['results'])
assert len(load(R/'results/negative_checks_p7/summary.json'))==22 and all(x['detected'] for x in load(R/'results/negative_checks_p7/summary.json'))
assert load(R/'results/touch_exhaustive_retry/result.json')['passed']
assert load(R/'results/input_audit.json')['passed']
assert load(R/'results/synthesis_gate/touch_network.json')['all_48_qualifiers_preserved']
delta=load(R/'results/synthesis_gate/ff_delta_diagnosis.json');assert delta['added_count']==300 and not delta['removed_count']
def warning_counts(p):
    lines=[s for s in p.read_text(encoding='utf-8',errors='replace').splitlines() if re.match(r'^[WEC]:',s)]
    counts=collections.Counter();unique=set()
    for line in lines:
        line=re.sub(r'[A-Z]:/source/',r'ROOT/source/',line)
        line=re.sub(r'\(line number: \d+\)','(line number: N)',line)
        m=re.match(r'^([WEC]):\s+([A-Za-z]+-\d+):',line)
        code=':'.join(m.groups()) if m else 'UNCODED'
        counts[code]+=1;unique.add(line)
    return dict(sha256=sha(p),counts=dict(counts),error_count=sum(s.startswith('E:') for s in lines)),unique
wa,sa=warning_counts(B/'results/synthesis_gate/console.log');wb,sb=warning_counts(R/'results/synthesis_gate/console.log')
suspect=sorted(s for s in sb-sa if re.search(r'(?i)latch|multiple.driver|multi.driver|truncat|width.mismatch|unsupported|illegal|conflict|unconn|not driven',s))
(R/'results/synthesis_gate/warning_review.json').write_text(json.dumps(dict(p7r1=wa,p8=wb,new_keyword_hits=suspect,scope='Synthesis-only normalized category and keyword triage, not a full-design sign-off; original warnings retained.'),indent=2),encoding='utf-8')
assert wb['error_count']==0
text='''# P8阶段结果：局部译码功能通过，FF早筛不通过

本轮按照用户“继续优化时序问题”执行，只在P7R1缓存中局部化touch组合译码。P7完整归档及生产G4均未修改；核心、外部接口、输出周期、1080p30、原FDC/IP保持。

## 已实际完成

- 5组逐拍测试全部通过；all-hit仍为7拍。
- 192槽公开分配、标签写读、加载及再命中通过，24种局部和2种全局重复优先级通过；强化TB共468组/7318沿。
- 原18个负例加4个touch负例，共22项均被非超时FATAL检出。
- 新增2752组touch穷举：四路各遍历256种ID及enable=0/1，含192..255无效ID、192组重复ID、512组混合及reset/frame-clear抑制。
- 81项候选/139项物理输入核对通过；只cache RTL发生变化，两个副本SHA一致。P7归档清单完整复核通过。
- PDS SP6.1综合/映射自然exit0，无E错误；全部12标签银行仍为RAM，无标签FF。

## 资源与结构实测

| 缓存指标 | P4固定筛选基准 | P7R1 | P8 |
|---|---:|---:|---:|
| LUT总量 | 16359 | 14919 | 15394 |
| 逻辑LUT | 13191 | 13255 | 13730 |
| FF | 8268 | 8268 | 8568 |
| 分布式RAM | 3168 | 1664 | 1664 |
| DRM | 8 | 8 | 8 |

沿用原门槛FF<=8268×1.02，即整数最多8433；实际8568，增加300/+3.63%，超过整数上限135。其余筛选项通过。逻辑LUT相对P4增加4.09%，仍在+5%内；与P7R1相比LUT总量增加475，FF增加300。

48个保留的组合touch限定全部在综合网表中找到，各自原语引脚负载8..17。它证明综合器保留了局部边界；不是物理扇出，也不是时序改善证据。旧版i_touch在综合网表中存在别名/合并，不能拿脚本显示的同名端口负载0当作旧负载为0。

## +300FF定位与含义

逐原语名称对照：last_use[0..191][21]共192，victim_leaf[0..95][29]共96，victim_age[0..11][21]共12；没有其他新增/删除FF。RTL没有新reg，差异来自原有年龄最高位在P8中未被综合消除。

典型last_use[0][21]的数据驱动为i_lookup_seq[21]与分配/完成条件组合；宿主将i_lookup_seq和i_touch_seq接到同一prepared_count。core的复用命中受prepared_count<2073600限制，而2073600<2^21。保留touch边界可能阻碍了原先跨控制条件的蕴含/常量优化，这是依据现有网表和源码的推测，工具没有给出优化器内部证明；不能把该推测写成已确认的工具bug。

不能为省FF而擅自将22位接口缩窄或把MSB绑0，独立cache仍须保留完整参数语义。P8也没有重新开启P6年龄存储/替换树局部分组路线。

## 本轮停止位置

FF早筛未通过，因此没有执行P8完整帧六项回归、PNR、定向STA或生成位流；没有P8的WNS、125MHz或板端结论。P7实际WNS=-1.273ns仅作为旧版参考，不能套给P8。已有小测试通过也不等于完整整机验收。新增穷举测试首次启动因Icarus Windows -B路径斜杠格式失败，修正为原已验证Path格式后复跑通过；两次原日志都保留。

## 后续建议，需用户选择后执行

P7R1继续作为当前可交接首选。对本次“保留局部组合边界”的路线，最直接的证伪办法是：若用户接受一项明确的新试验预算，将缓存FF上限由P4的+2%改为+5%，只对现有P8再做一次原125MHz/seed2完整PNR，其余资源门槛、核心/接口/输出周期/FDC/IP不改。+5%整数上限8681，可容纳8568；这仅允许测量，不是将旧早筛FAIL改成PASS，更不意味着125MHz必能闭合。

这样能用真实布线判断额外300FF是否换来收益。若用户不愿付此代价，就结束P8并保留P7，等G7明确版本后从跨core/cache路径整体处理；当前没有证据支持在同一限制下反复强保留译码必能成功。用户已要求方法无前景时先询问，不自动再开下一候选。

证据入口：results/synthesis_gate/result.json、touch_network.json、ff_delta_diagnosis.json；results/input_audit.json、negative_checks_p7/summary.json、touch_exhaustive_retry/result.json。完整源码和139项物理输入均包含；PDS入口physical/host_seed2/analysis.tcl只用于后续获准后的固定流程，不含gen_bit_stream。

转交：二号可接收本轮原语级定位、cache RTL和脚本，避免重复诊断；管理方可接收本说明及筛选回执，记录“资源早筛未通过，未做PNR”；执行方目前无需烧录任何新文件。
'''
(R/'P8阶段结果与下一步选择.md').write_text(text,encoding='utf-8')
(R/'README_当前进度.md').write_text('# P8已完成当前早筛，等待用户决定下一步\n\n功能小矩阵和穷举通过；FF8568超过固定+2%门槛，因此未执行PNR/全帧/位流。当前交接首选仍为P7R1。详见P8阶段结果与下一步选择.md。\n',encoding='utf-8')
receipt=dict(state='COMPLETED_EARLY_GATE_FAILED',candidate='P8',cache_sha256=sha(R/'candidate/source/rtl/undistort_cache_ab.v'),functional_small_passed=True,exhaustive_touch_cases=2752,negative_mutations=22,synthesis_completed=True,resource_gate_passed=False,failed_gates=['ff_budget'],p8_pnr_executed=False,p8_full_regression_executed=False,p8_timing_known=False,bitstream_generated=False,board_tested=False,current_preferred_candidate='P7R1',next_action_requires_user_decision=True,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(R/'results/stage_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
entry=f'''# P8本轮结果与续接（2026-10-25）

用户“继续优化时序问题”已执行到新隔离候选P8资源早筛。目录：{R}。

5组逐拍、192槽、22负例、2752组touch穷举通过。综合自然exit0；48局部限定保留，但FF8268→8568（+3.63%），超固定+2%门槛。新增300FF已定位为192+96+12个年龄MSB。其它资源门槛通过。没有本轮PNR、WNS、完整六项回归、位流或上板。

当前P7R1仍是可交接首选，归档未变。等待用户选择：是否为现有P8单独授权+5%FF的诊断预算并做一次125MHz/seed2 PNR（保留原失败结论，其它门槛/核心/接口/周期/FDC/IP不变）；或结束P8等待G7。未获新选择不自行布线/放宽门槛/开新路线。完整资料在本目录P8阶段结果与下一步选择.md，交付包位于ww/待转交。GitHub上传回执另在ww。
'''
(W/'P8当前续接_20261025.md').write_text(entry,encoding='utf-8')
cwd=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m')/'当前任务续接.md';old=cwd.read_text(encoding='utf-8');cwd.write_text(entry+'\n---\n\n'+old,encoding='utf-8')
shutil.copy2(__file__,R/'finalize_p8_stage.py')
# This snapshot is frozen now; regenerable simulation executables are omitted.
files=[]
for p in sorted(R.rglob('*')):
    if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.vvp') and p.name!='DELIVERY_MANIFEST.json':
        files.append(dict(file=p.relative_to(R).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
(R/'DELIVERY_MANIFEST.json').write_text(json.dumps(files,ensure_ascii=False,indent=2),encoding='utf-8')
dest=W/'待转交';dest.mkdir(exist_ok=True);archive=dest/'给二号与管理方_AB_P8局部译码_早筛结果_20261025.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for row in files:z.write(R/row['file'],'P8/'+row['file'])
    z.write(R/'DELIVERY_MANIFEST.json','P8/DELIVERY_MANIFEST.json')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(files)+1
    for row in files:assert hashlib.sha256(z.read('P8/'+row['file'])).hexdigest()==row['sha256']
out=dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,file_count=len(files)+1,all_crcs_passed=True,all_file_sha256_passed=True,state=receipt['state'])
(dest/'AB_P8交付包校验回执_20261025.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
