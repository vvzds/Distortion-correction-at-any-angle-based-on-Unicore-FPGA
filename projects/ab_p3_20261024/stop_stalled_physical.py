"""Stop only this task's nonconverging PDS process tree, preserving evidence."""
from pathlib import Path
import subprocess,json,re,datetime,hashlib
R=Path(__file__).resolve().parent
p=R/'results/physical_seed2/process_receipt.json'
record=json.loads(p.read_text(encoding='utf-8'))
assert record['state']=='RUNNING'
assert record['pid']==36444 and record['mapping']['target']==str(R/'physical/host_seed2')
log=R/'results/physical_seed2/console.log'
body=log.read_text(errors='replace').split('Total 69393 subnets.')[-1]
rows=[(int(m[2]),int(m[1])) for m in re.finditer(r'Unrouted nets (\d+) at the end of iteration (\d+)',body)]
best=min(rows,key=lambda x:x[1]);last=rows[-1]
assert last[0]-best[0]>=250 and last[1]>best[1]>0
out={'requested_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
     'pid':record['pid'],'reason':'Stop this isolated offline attempt after >250 routing iterations without improving its minimum unresolved count; continue structural cache candidate P4. Not a final timing verdict.',
     'best_iteration_unrouted':best,'last_iteration_unrouted':last,
     'last100_min':min(rows[-100:],key=lambda x:x[1]),'last100_max':max(rows[-100:],key=lambda x:x[1]),
     'console_sha256_before_stop':hashlib.sha256(log.read_bytes()).hexdigest(),
     'command':['taskkill','/PID',str(record['pid']),'/T','/F']}
(R/'results/physical_seed2/controlled_stop.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
result=subprocess.run(out['command'],capture_output=True)
out.update(exit_code=result.returncode,stdout=result.stdout.decode('mbcs',errors='replace'),stderr=result.stderr.decode('mbcs',errors='replace'))
(R/'results/physical_seed2/controlled_stop.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
assert result.returncode==0
