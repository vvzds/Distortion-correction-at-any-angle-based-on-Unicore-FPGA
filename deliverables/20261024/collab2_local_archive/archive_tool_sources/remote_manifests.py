from pathlib import Path
import json,sys,subprocess
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'github_repository_setup_20261024'))
from repo_git import GIT,environment
REPO=Path('C:/Users/叶翔/Documents/Codex/fpga-main')
d=json.loads((HERE/'remote_git_objects.json').read_text(encoding='utf-8'))
env=environment();out=HERE/'remote_manifests';out.mkdir(exist_ok=True)
index=[]
for oid,refs in d['objects'].items():
    r=refs[0];name=Path(r['path']).name.lower()
    if name not in {'parts_manifest.json','sha256sums.txt','sha256.json','snapshot_manifest.json'}:continue
    target=out/(oid+'.json' if name.endswith('.json') else oid+'.txt')
    if not target.exists():
        result=subprocess.run([str(GIT),'-C',str(REPO),'show',r['commit']+':'+r['path']],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace'))
        target.write_bytes(result.stdout)
    index.append({'file':target.name,**r})
(out/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(index,ensure_ascii=False,indent=2))
