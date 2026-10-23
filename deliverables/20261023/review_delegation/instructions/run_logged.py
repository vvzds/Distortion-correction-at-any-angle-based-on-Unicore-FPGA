"""Run one explicitly supplied command, preserving process and input/output evidence."""
from pathlib import Path
import argparse,datetime,hashlib,json,subprocess,os,shutil,sys,time
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cwd',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--timeout',type=int,default=7200);p.add_argument('--tool-version',default='UNVERIFIED_SEE_NATIVE_LOG');p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
 cmd=a.command[1:] if a.command[:1]==['--'] else a.command
 cwd=a.cwd.resolve();out=a.out.resolve()
 if not cmd or not cwd.is_dir() or out.exists() or out.is_relative_to(cwd) or a.timeout<=0:raise ValueError('New output outside cwd, existing cwd, command and positive timeout required')
 exe=shutil.which(cmd[0])
 if not exe:raise FileNotFoundError(cmd[0])
 cmd[0]=str(Path(exe).resolve());out.mkdir(parents=True)
 before={f.relative_to(cwd).as_posix():sha(f) for f in cwd.rglob('*') if f.is_file()}
 dump(out/'inputs_before.json',before)
 rec=dict(status='STARTING',argv=cmd,cwd=str(cwd),tool_sha256=sha(Path(exe)),declared_tool_version=a.tool_version,version_confirmed=False,started_at=now(),timeout_seconds=a.timeout,pid=None,exit_code=None)
 dump(out/'process_receipt.json',rec)
 proc=None;termination=None
 try:
  with (out/'console_full.log').open('wb') as f:
   proc=subprocess.Popen(cmd,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
   rec.update(status='RUNNING',pid=proc.pid);dump(out/'process_started.json',rec);dump(out/'process_receipt.json',rec)
   try:code=proc.wait(timeout=a.timeout);status='FINISHED'
   except (subprocess.TimeoutExpired,KeyboardInterrupt) as e:
    status='TIMEOUT' if isinstance(e,subprocess.TimeoutExpired) else 'INTERRUPTED'
    if os.name=='nt':
     kill=subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=30);termination=dict(exit_code=kill.returncode,stdout=kill.stdout.decode(errors='replace'),stderr=kill.stderr.decode(errors='replace'))
    else:proc.kill();termination={'scope':'direct_process_only'}
    try:code=proc.wait(timeout=30)
    except subprocess.TimeoutExpired:code=None
 except Exception as e:status='LAUNCH_OR_WRAPPER_ERROR';code=None;rec['exception']=repr(e)
 after={};errors=[]
 for n,h in before.items():
  try:after[n]=sha(cwd/n) if (cwd/n).is_file() else None
  except OSError as e:after[n]=None;errors.append(dict(path=n,error=repr(e)))
 changed=[n for n,h in before.items() if after[n]!=h]
 dump(out/'inputs_after.json',after)
 artifacts=[]
 for f in cwd.rglob('*'):
  if f.is_file():
   try:artifacts.append(dict(path=f.relative_to(cwd).as_posix(),bytes=f.stat().st_size,sha256=sha(f)))
   except OSError as e:errors.append(dict(path=str(f),error=repr(e)))
 dump(out/'artifacts_sha256.json',artifacts)
 rec.update(status=status,exit_code=code,finished_at=now(),termination=termination,changed_input_files=changed,artifact_read_errors=errors,console_sha256=sha(out/'console_full.log'),physics_pass='NOT_ASSESSED')
 dump(out/'process_receipt.json',rec);print(json.dumps(rec,ensure_ascii=False,indent=2))
 return 0 if status=='FINISHED' and code==0 and not errors else 2
if __name__=='__main__':sys.exit(main())
