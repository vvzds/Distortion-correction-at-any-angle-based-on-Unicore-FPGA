from pathlib import Path
import sys,subprocess,json,hashlib
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/'github_repository_setup_20261024'))
from repo_git import GIT,environment
BASE=Path('C:/Users/叶翔/Documents/Codex/fpga-main/deliverables/20261024/collab2_local_archive')
script=BASE/'restore_archive.py'
list_result=subprocess.run([sys.executable,str(script),'--list','--root','desktop_FPGA'],env=environment(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
assert list_result.returncode==0,list_result.stderr.decode('utf-8','replace')
dest=HERE/'restore_smoke_result'
result=subprocess.run([sys.executable,str(script),'--root','desktop_FPGA','--destination',str(dest),'--git',str(GIT)],env=environment(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace'))
receipt={'state':'PASS','restoration':result.stdout.decode('utf-8','replace').strip(),'list_command_passed':True,'destination':str(dest),'files':[{'path':str(p.relative_to(dest)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in dest.rglob('*') if p.is_file()]}
(BASE/'RESTORE_SMOKE_TEST.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
