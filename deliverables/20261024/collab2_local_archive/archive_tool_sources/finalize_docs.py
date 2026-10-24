from pathlib import Path
import json,gzip,shutil,hashlib,re,collections,os
HERE=Path(__file__).resolve().parent
REPO=Path('C:/Users/叶翔/Documents/Codex/fpga-main')
BASE=REPO/'deliverables/20261024/collab2_local_archive'
DESKTOP=Path('C:/Users/叶翔/Desktop/yx/本机项目全量归档上传_二号_20261024')

def main():
    verification=json.loads((BASE/'VERIFICATION.json').read_text(encoding='utf-8'))
    assert verification['state']=='PASS'
    summary=json.loads((BASE/'SUMMARY.json').read_text(encoding='utf-8'))
    if (BASE/'PATHS.jsonl').exists():
        with (BASE/'PATHS.jsonl').open('rb') as source,gzip.open(BASE/'PATHS.jsonl.gz','wb',compresslevel=6) as out:shutil.copyfileobj(source,out)
        (BASE/'PATHS.jsonl').unlink()
    shutil.copy2(HERE/'restore_archive.py',BASE/'restore_archive.py')
    shutil.copy2(HERE/'verify_downloaded_archive.py',BASE/'verify_downloaded_archive.py')
    tools=BASE/'archive_tool_sources';tools.mkdir(exist_ok=True)
    for source in HERE.glob('*.py'):
        shutil.copy2(source,tools/source.name)
    rows=[]
    with gzip.open(BASE/'PATHS.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:rows.append(json.loads(line))
    families=collections.defaultdict(dict)
    version_pattern=re.compile(r'(?i)(?:\bv|_v|V)(\d+(?:\.\d+){1,3})')
    for row in rows:
        name=Path(row['rel']).name;m=version_pattern.search(name)
        if not m:continue
        version=tuple(int(x) for x in m.group(1).split('.'))
        family=version_pattern.sub('_VERSION_',name)
        family=re.sub(r'[_-]?20\d{6}','',family)
        family=re.sub(r'\(\d+\)(?=\.[^.]+$)','',family)
        obj=families[family].setdefault(version,{'files':{}})
        obj['files'].setdefault(row['sha256'],{'sha256':row['sha256'],'root':row['root'],'rel':row['rel']})
    remote=json.loads((HERE/'remote_git_objects.json').read_text(encoding='utf-8'))
    for oid,refs in remote['objects'].items():
        for ref in refs:
            name=Path(ref['path']).name;m=version_pattern.search(name)
            if not m:continue
            version=tuple(int(x) for x in m.group(1).split('.'))
            family=version_pattern.sub('_VERSION_',name)
            family=re.sub(r'[_-]?20\d{6}','',family);family=re.sub(r'\(\d+\)(?=\.[^.]+$)','',family)
            obj=families[family].setdefault(version,{'files':{}})
            obj['files'].setdefault('git:'+oid,{'git_oid':oid,'path':ref['path'],'commit':ref['commit']})
    version_index={}
    for family,versions in sorted(families.items()):
        latest=max(versions)
        version_index[family]={'highest_declared_version':'.'.join(map(str,latest)),'versions':[{'version':'.'.join(map(str,v)),'candidates':list(info['files'].values())} for v,info in sorted(versions.items(),reverse=True)],'rule':'Prefer highest explicit semantic version within the same filename family; different contents at the same version are parallel variants, not automatically replaceable production RTL.'}
    (BASE/'VERSION_INDEX.json').write_text(json.dumps(version_index,ensure_ascii=False,indent=2),encoding='utf-8')
    counts=collections.Counter(r['root'] for r in rows)
    tasks=collections.Counter()
    for r in rows:
        parts=r['rel'].split('/')
        depth=2 if r['root']=='workspace' and parts[0] in {'work','outputs'} else 1
        tasks[(r['root'],'/'.join(parts[:depth]))]+=1
    task_lines=['# 按任务查找全部历史资料','','接收方：管理方/执行者、一号协作者、二号协作者。','','在仓库根目录使用 restore_archive.py 的 --root、--prefix 和 --destination 恢复；此表中前两列对应前两个参数。','','| --root | --prefix | 文件数 |','|---|---|---:|']
    task_lines.extend('| '+root+' | '+prefix.replace('|','\\|')+' | '+str(count)+' |' for (root,prefix),count in sorted(tasks.items()))
    (BASE/'TASK_INDEX.md').write_text('\n'.join(task_lines)+'\n',encoding='utf-8')
    lines=['# 项目本机资料全量归档（二号）','','接收方：管理方/执行者、一号协作者、二号协作者。','','本归档汇总本机已知项目目录，包含工程、RTL/IP、约束、位流、参数、标定原图、采集视频、原始交接包、仿真与物理证据，以及本机工具脚本。','','## 完整性与去重','',f"- 文件路径：{summary['files']:,}；不重复文件内容：{summary['unique_files']:,}。",f"- 原始文件合计：{summary['original_bytes']:,} 字节；新增归档载荷：{summary['new_payload_bytes']:,} 字节。",f"- 复用仓库已有内容：{summary['reused_remote_objects']} 份，含G7/G8原始分片包。",'- 所有对象已完整解码并检查 SHA256/长度；复用的Git对象已与本地原始字节比对Git blob哈希。见 VERIFICATION.json。','- ZIP字节、旧报告和旧参数原样保留；没有重新压缩原件后冒充原哈希。','- 软件安装器、依赖运行时缓存、Git登录配置/令牌、无关个人资料不入库；排除项见 filtered_exclusions.json。','','## 当前入口与版本规则','','- [当前G4静态校正整机候选](../collab2_G4_static_timing_pass/README.md)：1080p30、DDR125MHz，WNS +0.183ns；尚未板测。','- [按显式版本号排列的全部版本索引](VERSION_INDEX.json)：同一文件族优先较高版本，较低版本保持可恢复。','- 同版本、不同哈希的文件保留为并行候选；G4/G6/G8算法、门禁和生产整机属于不同工作线，不能仅按数字大小互相替换。','- 已合并管理方主线、一号资料分支、二号仓库接入与G4时序交付分支；原分支和提交保留。','- 主工程根目录的RTL/IP/FDC不因资料同步被混合替换；新增候选通过明确的版本入口提供。','- 历史失败报告、合成测试数据、软件候选与实机验收证据各按原路径保留，不把历史失败认作当前通过，也不把仿真/时序通过认作板测通过。','','## 查找和恢复','','无需第三方Python包。先在仓库根目录运行：','','```powershell','python deliverables/20261024/collab2_local_archive/restore_archive.py --list','```','','恢复桌面某次任务（替换为 --list 中的任务目录）：','','```powershell','python deliverables/20261024/collab2_local_archive/restore_archive.py --root desktop_yx --prefix "G8_自动门禁与执行检查工具_20261023" --destination "D:/FPGA_restore"','```','','恢复原D盘工程：','','```powershell','python deliverables/20261024/collab2_local_archive/restore_archive.py --root pds_yx --prefix "static_G4_timing_resume_20261024/seed_4_hold20_r5" --destination "D:/FPGA_restore"','```','','- 仅下载本目录ZIP分片不等于完整恢复；需同时保留 MANIFEST.json、PATHS.jsonl.gz 和工具引用的已有仓库对象。','- 需要普通 Git 访问已有对象；部分克隆可在需要时按Git对象取回。恢复工具默认不覆盖不同内容的已有文件。','- 恢复到同名工程目录并校验哈希后，再按对应工程SOP操作；不能混用不同候选的位流和参数。','','## 本机目录覆盖','', '| 根标签 | 文件数 |','|---|---:|']
    lines.extend(f'| {root} | {count:,} |' for root,count in sorted(counts.items()))
    lines+=['','PATHS.jsonl.gz 保存每个原始绝对路径、根标签、相对路径、大小、时间戳和SHA256。ORIGINAL_IMAGES.json 另记本机仍存在的原始附件图；已不在本机的历史临时图片仅记录缺失，不伪造。','']
    lines+=['','## 快速入口','','- [按任务目录查找](TASK_INDEX.md)','- [补充的M01完整源码](supplemental_M01_sources.zip)；其335个补充源文件与报告生成脚本的原路径和单独校验见 SUPPLEMENTAL_FILES.json。','- [本机仍存在的项目原始附件图](ORIGINAL_IMAGES.json)；桌面独立旧位流与G6原说明在 standalone_project_files。','- 本地下载完成后运行 `python verify_downloaded_archive.py` 核验全部新增归档文件；完整逐对象解码证据见 VERIFICATION.json。','']
    (BASE/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    (BASE/'.gitattributes').write_text('* -text\npacks/*.zip -diff\nMANIFEST.json -diff\nPATHS.jsonl.gz -diff\nstandalone_project_files/** -diff -whitespace\n',encoding='utf-8')
    # Include two standalone project artifacts not matched by keyword-only root scanning.
    supplemental=BASE/'standalone_project_files';supplemental.mkdir(exist_ok=True)
    for name in ['CMOS2_RAW8_HDMI1080p60_待上板.sbit','README.md']:
        p=Path('C:/Users/叶翔/Desktop')/name
        if p.exists():shutil.copy2(p,supplemental/name)
    root_readme=REPO/'README.md'
    root_text=root_readme.read_text(encoding='utf-8')
    link='[二号本机全部项目资料与旧版恢复索引](deliverables/20261024/collab2_local_archive/README.md)'
    if link not in root_text:root_readme.write_text(root_text.rstrip()+'\n\n'+link+'\n',encoding='utf-8')
    # Reuse verified pack hashes; hash all small metadata and originals independently.
    manifests=json.loads((BASE/'MANIFEST.json').read_text(encoding='utf-8'))
    pack_hashes={p['path']:p['sha256'] for p in manifests['packs']}
    sums=[]
    for p in sorted(BASE.rglob('*')):
        if not p.is_file() or p.name=='SHA256SUMS.txt':continue
        rel=p.relative_to(BASE).as_posix()
        if p.stat().st_size>=95*1024**2:raise RuntimeError('Oversized Git file: '+str(p))
        sha=pack_hashes.get(rel) or hashlib.sha256(p.read_bytes()).hexdigest()
        sums.append(sha+'  '+rel)
    (BASE/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='utf-8')
    DESKTOP.mkdir(exist_ok=True)
    # Immutable payload ZIPs are hard linked on the same C: volume to avoid a
    # second 2.86GB copy. The desktop contains complete readable archive files.
    for p in BASE.rglob('*'):
        if not p.is_file():continue
        target=DESKTOP/'完整归档'/p.relative_to(BASE)
        target.parent.mkdir(parents=True,exist_ok=True)
        if p.suffix=='.zip' and target.exists():continue
        if p.suffix=='.zip':os.link(p,target)
        else:shutil.copy2(p,target)
    (DESKTOP/'01_结果与仓库入口_给管理方及一号.md').write_text('# 本机归档上传\n\n归档在本文件夹的“完整归档”目录，GitHub路径为 deliverables/20261024/collab2_local_archive。\n\n原始文件、去重索引、旧版恢复入口、校验结果和排除项均已整理。网络上传最终状态以02_仓库上传回执.json为准。\n\n本目录保存新增载荷与完整索引；相同旧内容复用仓库已有对象。从桌面运行恢复工具时，请用 --repo 指定本机仓库 C:/Users/叶翔/Documents/Codex/fpga-main，或在已克隆的仓库内按README执行。\n',encoding='utf-8')
    print(json.dumps({'version_families':len(version_index),'desktop':str(DESKTOP),'metadata_complete':True},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
