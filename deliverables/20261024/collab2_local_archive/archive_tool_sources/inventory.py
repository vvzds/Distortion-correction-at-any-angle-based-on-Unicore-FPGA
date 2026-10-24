"""Inventory project artifacts only; never read account or credential stores."""
from pathlib import Path
import os,json,re,time,collections

HERE=Path(__file__).resolve().parent
OUT=HERE/'inventory.json'
USER=Path('C:/Users/叶翔')
SKIP_DIR={'.git','__pycache__','.venv','venv','node_modules','.pytest_cache','pip_cache','pip_tmp','host_validation_deps','yosys_cache','yosys40','python_tools','wheels_v12','tools_tmp_v12','computer_use_repair_20261020','pds_sp64_setup'}
SKIP_FILE={'hosts.yml','.git-credentials','.netrc','credentials.json','auth.json'}
PROJECT=re.compile(r'fpga|ov5640|undistort|stereo|collab|affine|校正|矫正|标定|畸变|设计方|管理方|协作者|回执|回件|复核|门禁|选题二|模块分工|核心证据|接收核查|G[1-9][0-9]?[_ _]|M0[1-9][_-]|host_pc|host_review|补证|裁定|接收回复|阶段1实现|上位机包',re.I)
rows=[]; exclusions=[]; errors=[]; roots=[]

def scan(root,label,filtered=False,top_only=False):
    root=Path(root)
    if not root.exists():return
    roots.append({'root':str(root),'label':label,'filtered':filtered})
    print('SCAN '+label+' '+str(root),flush=True)
    for base,dirs,files in os.walk(root):
        if top_only:dirs[:]=[]
        for name in list(dirs):
            p=Path(base)/name
            if name in SKIP_DIR or p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 or (label=='workspace' and p==HERE) or (name=='github_repository_setup_20261024'):
                dirs.remove(name);exclusions.append({'path':str(p),'reason':'generated archive output, dependency runtime, Git metadata or account setup'})
        for name in files:
            p=Path(base)/name
            if name.lower() in SKIP_FILE or name.endswith(('.pyc','.lnk')):
                exclusions.append({'path':str(p),'reason':'credential/cache/shortcut'});continue
            if filtered and not PROJECT.search(name):continue
            try:
                st=p.stat()
                if p.is_symlink():continue
                rows.append({'path':str(p),'root':label,'rel':p.relative_to(root).as_posix(),'size':st.st_size,'mtime_ns':st.st_mtime_ns})
            except OSError as e:errors.append({'path':str(p),'error':str(e)})
    print('DONE '+label+' total_files='+str(len(rows)),flush=True)

for sub in ['yx','last','sty','ww','fpgaled','resouce']:
    scan(Path('D:/FPGA PDS')/sub,'pds_'+sub)
# Only top-level project files outside the known project directories.
scan(USER/'Desktop/yx','desktop_yx')
scan(USER/'Desktop/photo','calibration_photo')
scan(USER/'Desktop/FPGA','desktop_FPGA')
scan(USER/'Desktop','desktop_project_docs',True,True)
scan(USER/'Downloads','downloads_project',True,True)
scan(Path('C:/Users/叶翔/Documents/Codex/2026-10-10/x20'),'workspace')
for sub in ['2026-09-15/new-chat','2026-09-17/wo','2026-10-13/new-chat','2026-10-14/new-chat','2026-10-14/new-chat-2','2026-10-20/new-chat','2026-10-20/new-chat-2','a1024m01/M01']:
    scan(USER/'Documents/Codex'/sub,'codex_'+sub.replace('/','_'),True)
wx=USER/'xwechat_files/wxid_qanrp2aqlq8h22_bb90/msg'
for sub in ['file/2026-10','attach']:
    scan(wx/sub,'wechat_'+sub.replace('/','_'),True)
# Remove overlapping Desktop and workspace visits, retaining the specific root.
dedup={}
for row in rows:
    key=os.path.normcase(row['path'])
    if key not in dedup:dedup[key]=row
rows=list(dedup.values())
counts=collections.defaultdict(lambda:{'files':0,'bytes':0})
for row in rows:
    c=counts[row['root']];c['files']+=1;c['bytes']+=row['size']
result={'created':time.strftime('%Y-%m-%dT%H:%M:%S'),'scope':'FPGA project only','roots':roots,'files':rows,'exclusions':exclusions,'errors':errors,'summary':dict(counts)}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'files':len(rows),'bytes':sum(x['size'] for x in rows),'summary':dict(counts),'errors':errors,'largest':sorted(rows,key=lambda x:x['size'],reverse=True)[:15]},ensure_ascii=False,indent=2))
