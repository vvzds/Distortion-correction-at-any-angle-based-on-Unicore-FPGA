"""Create an isolated, cycle-preserving P8 touch-decode experiment from P7R1."""
from pathlib import Path
import shutil, json, hashlib, datetime

W=Path(r'C:\Users\lenovo\Desktop\ww')
B=W/'AB_P7R1标签RAM与共享比较_20261025'
R=W/'AB_P8触摸译码局部化_20261025'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
assert not R.exists()
assert sha(B/'candidate/source/rtl/undistort_cache_ab.v')=='b2042db9c8d40dafb4c277104d909a76caca140d57e2c549bf1d7665324678c3'
R.mkdir()
for name in ('candidate','baseline','tests','prior_p1'):
    shutil.copytree(B/name,R/name)
P=R/'physical/host_seed2'; P.mkdir(parents=True)
ident=json.loads((B/'physical/input_identity.json').read_text(encoding='utf-8'))
for row in ident['inputs']:
    a=B/'physical/host_seed2'/row['file']; assert sha(a)==row['sha256']
    b=P/row['file'];b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
for name in ('synthesis_only.tcl','analysis.tcl'):
    shutil.copy2(B/'physical/host_seed2'/name,P/name)

src=(B/'candidate/source/rtl/undistort_cache_ab.v').read_text(encoding='utf-8')
old='''else if(i_touch && (i_touch_ids[7:0]==lu ||
                            i_touch_ids[15:8]==lu || i_touch_ids[23:16]==lu ||
                            i_touch_ids[31:24]==lu))last_use[lu]<=i_touch_seq;'''
assert src.count(old)==1
src=src.replace(old,'else if(age_touch_mask[lu])last_use[lu]<=i_touch_seq;')
anchor='    integer i,k,g,j,idx,sel,l,lu;'
assert src.count(anchor)==1
local='''    // P8: preserve four bank-local touch qualifiers per 16-slot bank.
    // No register/latency change: allocation and completion still win per slot.
    // Keeping these combinational boundaries prevents the late i_touch signal
    // from being factored back into one shared 192-slot enable term.
    wire [191:0] age_touch_mask;
    genvar touch_g,touch_s;
    generate for(touch_g=0;touch_g<12;touch_g=touch_g+1)begin:touch_bank
        wire touch0 /* synthesis syn_keep = 1 */;
        wire touch1 /* synthesis syn_keep = 1 */;
        wire touch2 /* synthesis syn_keep = 1 */;
        wire touch3 /* synthesis syn_keep = 1 */;
        assign touch0=i_touch && i_touch_ids[7:4]==touch_g;
        assign touch1=i_touch && i_touch_ids[15:12]==touch_g;
        assign touch2=i_touch && i_touch_ids[23:20]==touch_g;
        assign touch3=i_touch && i_touch_ids[31:28]==touch_g;
        for(touch_s=0;touch_s<16;touch_s=touch_s+1)begin:slot
            assign age_touch_mask[16*touch_g+touch_s]=
                (touch0 && i_touch_ids[3:0]==touch_s) ||
                (touch1 && i_touch_ids[11:8]==touch_s) ||
                (touch2 && i_touch_ids[19:16]==touch_s) ||
                (touch3 && i_touch_ids[27:24]==touch_s);
        end
    end endgenerate
'''
src=src.replace(anchor,local+anchor)
for p in (R/'candidate/source/rtl/undistort_cache_ab.v',P/'source/rtl/undistort_cache_ab.v'):
    p.write_text(src,encoding='utf-8',newline='\n')
for name in ('run_equivalence.py','run_bank_tests.py','run_negative_checks.py','run_synthesis_gate.py',
             'netlist_metrics.py','process_snapshot.py','run_full_regression.py','compare_regression.py',
             'run_physical.py','run_focused_reports.py','run_focused_diagnostic.py','inspect_physical.py',
             'compare_warnings.py'):
    s=(B/name).read_text(encoding='utf-8')
    if name=='run_physical.py':
        s=s.replace(sha(B/'candidate/source/rtl/undistort_cache_ab.v'),sha(R/'candidate/source/rtl/undistort_cache_ab.v'))
    (R/name).write_text(s,encoding='utf-8',newline='\n')
# Preserve the 18 existing mutations and add specific local-decode faults.
p=R/'run_negative_checks.py';s=p.read_text(encoding='utf-8')
anchor="out=R/'results/negative_checks_p7'"
assert s.count(anchor)==1
s=s.replace(anchor,"""faults.update({
 'touch_wrong_bank':('i_touch_ids[7:4]==touch_g','i_touch_ids[7:4]==((touch_g+1)%12)'),
 'touch_wrong_slot':('touch0 && i_touch_ids[3:0]==touch_s','touch0 && i_touch_ids[3:0]==(touch_s^1)'),
 'touch_missing_fourth':('touch3 && i_touch_ids[27:24]==touch_s',\"1'b0 && i_touch_ids[27:24]==touch_s\"),
 'touch_ignore_enable':('assign touch0=i_touch &&','assign touch0=1\'b1 &&'),
})
"""+anchor)
# Avoid quoted Verilog apostrophe inside a Python single-quoted literal.
s=s.replace("'assign touch0=1'b1 &&'",'"assign touch0=1\'b1 &&"')
s=s.replace('len(results)==18','len(results)==22');p.write_text(s,encoding='utf-8')
for name in ('run_synthesis_gate.py','run_physical.py'):
    p=R/name;s=p.read_text(encoding='utf-8').replace('==18','==22');p.write_text(s,encoding='utf-8')
for row in ident['inputs']:row['sha256']=sha(P/row['file'])
ident['scope']='P8 bank-local kept combinational touch decode; P7R1 storage, ages, replacement, core, cycles, original FDC/IP retained'
(R/'physical/input_identity.json').write_text(json.dumps(ident,indent=2),encoding='utf-8')
rows=[]
for p in sorted((R/'candidate').rglob('*')):
    if p.is_file():
        rel=p.relative_to(R/'candidate');rows.append(dict(file=rel.as_posix(),sha256=sha(p),p7r1_sha256=sha(B/'candidate'/rel)))
assert [r['file'] for r in rows if r['sha256']!=r['p7r1_sha256']]==['source/rtl/undistort_cache_ab.v']
(R/'candidate_identity.json').write_text(json.dumps(dict(files=rows),indent=2),encoding='utf-8')
assert sha(R/'candidate/source/rtl/undistort_core.v')=='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68'
(R/'P8设计与预设门槛.md').write_text('''# P8：仅局部化 touch 组合译码

用户2026-10-25明确要求继续优化时序；恢复缓存侧工作，G7最终集成仍等待明确版本。P7归档不修改。

P7实际125MHz/seed2最差cache_to为-1.273ns，年龄路径中touch后合并网扇出192、连线2.392ns；core侧prep_ptr扇出594、连线2.442ns仍保持原样。因此本候选只尝试削减缓存侧后半段分发，不承诺独立消除整条跨边界路径。

实现：12个16槽组各保留四路touch与ID高4位相等的组合限定，再用低4位生成本槽touch条件。使用工程已有syn_keep语法保留组合边界。无新寄存器、无年龄/替换树搬移，不继承P6额外FF路线。原静态writer、分配/DONE优先、reset/frame_clear抑制、192槽逻辑容量、标签RAM、核心、接口、延迟和输出周期不变。只改cache一个文件，两份RTL副本SHA一致。

先验证5组逐拍、192槽与所有优先级、18个原负例加4个touch定向负例；然后综合。沿用固定P4门槛：12银行标签RAM且无标签FF、FF<=102%、逻辑LUT<=105%、总LUT<=100%、DRM<=12、qa/qb局部负载<=75%。另核对48个touch限定在网表中是否存在以及实际负载，组合语法不等于物理改善。

若早筛通过，固定原125MHz/FDC/IP/seed2完成PNR；再核对cache_from/cache_to及年龄、匹配、替换定向STA四种corner/check。改善必须用P7同条件原生PNR结果比较，不能以综合估计或资源下降代替125MHz闭合。若未改善，保存失败证据，不自动再开下一路线。核心map剩余违例由二号负责。

本轮不生成位流、不烧录、不合并main；完整候选按既有授权独立分支/草稿PR交付。沿用p7命名的测试路径是既有测试原名，不是冒用旧结果；新results为空起跑。
''',encoding='utf-8')
(R/'README_当前进度.md').write_text('# P8正在进行\n\n已建立隔离候选，尚未验证/综合/布线。见P8设计与预设门槛.md。P7保持归档。\n',encoding='utf-8')
entry=f'''# 2026-10-25：用户已恢复缓存时序优化，当前P8

候选：{R}。P7R1完整交接保持不变。只改缓存touch组合译码，无新流水，核心/接口/周期/原FDC/IP保持。尚未验证，不得称125MHz通过。按P8设计与预设门槛.md先小测试和资源筛选，再决定完整物理验证。G7最终集成等待明确版本，G4不重复索要。
'''
(W/'P8当前续接_20261025.md').write_text(entry,encoding='utf-8')
cwd=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m')/'当前任务续接.md'
cwd.write_text(entry+'\n---\n\n'+cwd.read_text(encoding='utf-8'),encoding='utf-8')
shutil.copy2(__file__,R/'prepare_ab_p8.py')
print(json.dumps(dict(root=str(R),cache_sha256=sha(R/'candidate/source/rtl/undistort_cache_ab.v')),ensure_ascii=False,indent=2))
