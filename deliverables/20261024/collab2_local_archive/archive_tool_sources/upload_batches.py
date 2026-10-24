"""Push archive payload in bounded commits; never force-push shared branches."""
from pathlib import Path
import sys,subprocess,json,time,hashlib
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'github_repository_setup_20261024'))
from repo_git import GIT,environment
REPO=Path('C:/Users/叶翔/Documents/Codex/fpga-main')
REL=Path('deliverables/20261024/collab2_local_archive')
BRANCH='collab2/local-complete-archive-20261024'
env=environment()
receipt_file=HERE/'push_batches_receipt.json'
receipt=json.loads(receipt_file.read_text(encoding='utf-8')) if receipt_file.exists() else {'branch':BRANCH,'batches':[]}
def git(*args,timeout=900):
    p=subprocess.run([str(GIT),'-C',str(REPO),*args],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace')[-2500:])
    return p.stdout.decode('utf-8','replace').strip()
summary=json.loads((REPO/REL/'SUMMARY.json').read_text(encoding='utf-8'))
manifest=json.loads((REPO/REL/'MANIFEST.json').read_text(encoding='utf-8'))
tracked=set(git('ls-files','--',str(REL/'packs').replace('\\','/')).splitlines())
todo=[]
for part in manifest['packs']:
    path=REL/part['path'];p=REPO/path
    if p.stat().st_size>=95*1024**2:raise RuntimeError('GitHub single-file size exceeds safety limit')
    if hashlib.sha256(p.read_bytes()).hexdigest()!=part['sha256']:raise RuntimeError('Payload changed: '+str(p))
    if path.as_posix() not in tracked:todo.append(path.as_posix())
if git('branch','--show-current')!=BRANCH:raise RuntimeError('Wrong branch')
for start in range(0,len(todo),3):
    batch=todo[start:start+3]
    print('COMMIT '+str(start+1)+'-'+str(start+len(batch))+'/'+str(len(todo)),flush=True)
    git('add','-f','--',*batch)
    git('commit','-m','Archive collaborator 02 local artifacts: payload batch '+Path(batch[0]).stem+'-'+Path(batch[-1]).stem)
    commit=git('rev-parse','HEAD')
    print('PUSH '+commit[:12],flush=True)
    for attempt in range(3):
        try:
            git('push','origin','HEAD:refs/heads/'+BRANCH,timeout=900)
            break
        except Exception as e:
            if attempt==2:raise
            print('RETRY '+str(attempt+1)+' '+str(e)[-700:],flush=True)
    receipt['batches'].append({'commit':commit,'parts':batch,'remote_confirmed':True,'finished':time.strftime('%Y-%m-%dT%H:%M:%S')})
    receipt_file.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PUSHED '+str(len(receipt['batches']))+' batches',flush=True)
print('ALL PAYLOAD BATCHES PUSHED',flush=True)
