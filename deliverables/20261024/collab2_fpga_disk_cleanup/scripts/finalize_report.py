from pathlib import Path
import json,hashlib,collections,shutil,zipfile,datetime
W=Path(__file__).resolve().parent
P=W/'report';P.mkdir(exist_ok=True)
repo=Path('C:/Users/叶翔/Documents/Codex/fpga-main')
desktop=Path('C:/Users/叶翔/Desktop/yx/FPGA磁盘清理_二号_20261024')
plan=json.loads((W/'plan.json').read_text(encoding='utf-8-sig'))
result=json.loads((W/'cleanup_result.json').read_text(encoding='utf-8-sig'))
rows=[json.loads(s) for s in (W/'deletion_journal.jsonl').read_text(encoding='utf-8').splitlines()]
deleted={r['path'] for r in rows if r['status']=='DELETED'}
groups=collections.defaultdict(lambda:[0,0])
for r in plan['files']:
    if r['path'] in deleted:
        groups[r['target']][0]+=1;groups[r['target']][1]+=r['bytes']
errors=[r for r in rows if r['status']!='DELETED']
if any(Path(p).exists() for p in deleted):raise ValueError('Deleted file reappeared; review before reporting')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
bit=Path('D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project/top_recovery/generate_bitstream/hdmi_ddr_ov5640_top.sbit')
if sha(bit)!='67ce6939f03abe9e9594f6bd071a567988eeda96fecb4eec2c3f5b8ed6cdf317':raise ValueError('Current bitstream changed')
out=['# FPGA本机磁盘清理结果','', '制作：二号协作者；接收：用户、执行者/管理方；一号无需重新编译或提交回执。','',
    f"已删除 {result['deleted_files']} 个文件，文件逻辑大小合计 **{result['deleted_logical_bytes']/1024**3:.2f} GiB**。本次清理的是磁盘空间，不是运行内存。",'',
    '磁盘可用空间变化还受其他程序写入、文件系统压缩及分配单元影响，以下同时记录文件合计和实际可用空间。','',
    '| 磁盘 | 清理前可用GiB | 清理后可用GiB | 净增加GiB |','|---|---:|---:|---:|']
before={r['Name']:r['Free'] for r in result['before']}
for r in result['after']:out.append(f"| {r['Name']} | {before[r['Name']]/1024**3:.2f} | {r['Free']/1024**3:.2f} | {(r['Free']-before[r['Name']])/1024**3:.2f} |")
out+=['','## 已清理范围','','| 原目录或文件 | 已删除文件数 | 合计GiB |','|---|---:|---:|']
for p,(n,b) in groups.items():out.append(f'| `{p}` | {n} | {b/1024**3:.3f} |')
out+=['','## 保留和跳过','','- 当前静态矫正完整工程 D:\\FPGA PDS\\yx\\DCSjingtaijiaozheng 保留；当前位流SHA256仍为 `67ce6939f03abe9e9594f6bd071a567988eeda96fecb4eec2c3f5b8ed6cdf317`。',
      '- 自适应Gamma候选、标定照片和参数、软件安装目录、官方配套资料、其他协作者工程及旧双目功能工程保留。',
      '- 仓库本地全量归档及GitHub历史版本保留，删除桌面重复归档不影响历史版本恢复。',
      '- 两份SP6.4文件仅为未使用安装介质，按冗余安装文件删除；安装好的PDS未修改。',
      f"- 计划阶段跳过 {len(plan['skipped'])} 个目录；删除阶段跳过或失败 {len(errors)} 个文件，详见plan.json和deletion_journal.jsonl。"]
for s in plan['skipped']:out.append(f"- 跳过 `{s['target']}`：{s['reason']}。")
out+=['','## 历史文件恢复','','保留归档位于：',
    '`C:\\Users\\叶翔\\Documents\\Codex\\fpga-main\\deliverables\\20261024\\collab2_local_archive`','',
    '执行清理前已逐文件比对SHA256，并通过解码归档对象或核对清单以外保留的等价文件验证恢复来源；recovery_verification.json包含检查结果、保留副本位置和计划哈希。无法在本机完成恢复验证的目录整目录保留，不依赖尚未下载的Git对象删除唯一资料。',
    'plan.json的每条记录提供原路径、SHA256、archive.root及archive.rel。用仓库内restore_archive.py按指定root和prefix恢复到原根目录或新目录；完整参数见下例。不要直接把历史文件覆盖到正在用的工程。','',
    '```powershell',
    'python "C:\\Users\\叶翔\\Documents\\Codex\\fpga-main\\deliverables\\20261024\\collab2_local_archive\\restore_archive.py" --repo "C:\\Users\\叶翔\\Documents\\Codex\\fpga-main" --git "C:\\Users\\叶翔\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\native\\git\\cmd\\git.exe" --root pds_yx --prefix static_G4_timing_resume_20261024 --destination "D:\\FPGA_restore"',
    '```','',
    '桌面重复归档可从保留的仓库目录重新复制。无用安装介质未作备份，未来如确需安装，应从官方渠道重新取得。',
    '', '## 证据文件','','- plan.json：逐文件计划、备份引用及跳过原因。','- deletion_journal.jsonl：真实逐文件删除结果。','- recovery_verification.json：归档可恢复性验证。','- cleanup_result.json：文件合计和清理前后磁盘空间。','- scripts/：本轮盘点、验证和删除脚本，删除脚本存在已有执行日志时拒绝直接重跑。','']
(P/'README.md').write_text('\n'.join(out),encoding='utf-8')
for name in ['00_清理开工声明_给执行者.md','plan.json','recovery_verification.json','deletion_journal.jsonl','cleanup_result.json','inventory.json','detail.json']:
    shutil.copy2(W/name,P/name)
(P/'scripts').mkdir(exist_ok=True)
for name in ['inventory.py','detail.py','prepare_cleanup.py','execute_cleanup.ps1','finalize_report.py']:
    shutil.copy2(W/name,P/'scripts'/name)
manifest={p.relative_to(P).as_posix():sha(p) for p in P.rglob('*') if p.is_file() and p.name!='MANIFEST_SHA256.json'}
(P/'MANIFEST_SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
dest=repo/'deliverables/20261024/collab2_fpga_disk_cleanup'
shutil.copytree(P,dest)
shutil.copytree(P,desktop/'清理结果')
z=desktop/'FPGA磁盘清理记录_二号_20261024.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as f:
    for p in P.rglob('*'):
        if p.is_file():f.write(p,p.relative_to(P).as_posix())
shutil.copy2(z,dest/z.name)
(desktop/'SHA256SUMS.txt').write_text(sha(z)+'  '+z.name+'\n',encoding='utf-8')
print('FINAL',result['deleted_files'],result['deleted_logical_bytes']/1024**3,'GiB; errors',len(errors))
print('ZIP',sha(z))
