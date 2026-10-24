from pathlib import Path
import sys,subprocess,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'github_repository_setup_20261024'))
from repo_git import GIT,environment

HERE=Path(__file__).resolve().parent
REPO=Path('C:/Users/叶翔/Documents/Codex/fpga-main')
env=environment()
def git(*args):
    p=subprocess.run([str(GIT),'-C',str(REPO),*args],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))
    return p.stdout
refs=['origin/main','origin/contributor-01/materials-20261024','origin/collab2/repository-onboarding-20261024','origin/collab2/g4-static-1080p30-timing-20261024']
objects={};commits={}
for ref in refs:
    commit=git('rev-parse',ref).decode().strip();commits[ref]=commit
    for line in git('ls-tree','-rz',ref).split(b'\0'):
        if not line:continue
        meta,path=line.split(b'\t',1);mode,kind,oid=meta.decode().split()
        if kind=='blob':objects.setdefault(oid,[]).append({'ref':ref,'commit':commit,'path':path.decode('utf-8')})
(HERE/'remote_git_objects.json').write_text(json.dumps({'commits':commits,'objects':objects},ensure_ascii=False,indent=2),encoding='utf-8')
manifest_path='deliverables/20261024/contributor_01_additions/SNAPSHOT_MANIFEST.json'
raw=git('show',refs[1]+':'+manifest_path)
(HERE/'contributor01_manifest.json').write_bytes(raw)
print(json.dumps({'refs':commits,'unique_remote_blobs':len(objects),'contributor01_files':len(json.loads(raw)['files'])},indent=2))

desktop=Path('C:/Users/叶翔/Desktop/yx/本机项目全量归档上传_二号_20261024')
desktop.mkdir(exist_ok=True)
declaration='''# 本机项目全量归档上传声明\n\n- 执行方：二号协作者；接收方：管理方/执行者、一号协作者、二号协作者。\n- 范围：本机 FPGA 项目工程、RTL、IP配置、位流、约束、报告、交接包、标定原图、参数、仿真/图像证据及项目工具。\n- 对比仓库 main 与全部已知协作者资料分支；按内容哈希去重，保存原始路径、版本与对应证据。\n- 软件安装目录、第三方运行时缓存、账户凭据及无关个人资料不属于项目归档。排除项另列清单。\n- 旧版工程和旧证据保留可恢复入口；不能证明版本可替换的分支并列保存，不凭修改时间覆盖工程。\n- 不改变板卡状态，不烧录，不下发参数。125MHz/1080p30时序通过候选仍待实机验收。\n'''
(desktop/'00_归档开工声明_给管理方及一号.md').write_text(declaration,encoding='utf-8')
(HERE/'00_归档开工声明_给管理方及一号.md').write_text(declaration,encoding='utf-8')
