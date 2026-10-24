"""Run native compile only, using a separate workspace and fresh evidence."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import time

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    root = Path(__file__).resolve().parent
    pre = json.loads((root/'preflight.json').read_text(encoding='utf-8'))
    for name,h in pre['input_hashes'].items():
        if name.startswith(('source/','ipcore/')) or name.endswith('.fdc'):
            assert sha(root/name) == h, 'INPUT_CHANGED: '+name
    stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    run = root/'runs'/stamp
    run.mkdir(parents=True)
    log = run/'console.log'
    receipt = run/'receipt.json'
    tool = Path('D:/FPGA PDS/site/PDS_2022.2-SP6.1-win64/bin/pds_shell.exe')
    env = dict(os.environ)
    tmp = root/'task_temp'
    tmp.mkdir(exist_ok=True)
    env.update(TEMP=str(tmp),TMP=str(tmp))
    env['PATH'] = str(tool.parent)+os.pathsep+env.get('PATH','')
    args = [str(tool),'-file',str(root/'compile_only.tcl'),'-work_dir',str(root),
        '-project_name','full_source_top_recovered']
    data = dict(state='RUNNING',started=dt.datetime.now().astimezone().isoformat(),
        top='hdmi_ddr_ov5640_top',command=args,programmed=False,uart_sent=False,
        synthesis_run=False,place_route_run=False)
    def save():
        receipt.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    print('Native compile log: '+str(log),flush=True)
    start = time.time()
    with log.open('wb') as stream:
        proc = subprocess.Popen(args,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT)
        data['pid'] = proc.pid
        save()
        code = proc.wait()
    raw = log.read_text(encoding='utf-8',errors='replace')
    errors = re.findall(r'^E:.*$',raw,re.M)
    passed = code == 0 and not errors and '=== EXPLICIT TOP COMPILE COMPLETED ===' in raw
    project = root/'full_source_top_recovered.pds'
    passed = passed and project.is_file() and 'hdmi_ddr_ov5640_top' in project.read_text(encoding='utf-8',errors='replace')
    if passed:
        # 重跑后仍保留交付工程的物理实现设置；本脚本不运行布局布线。
        text = project.read_text(encoding='utf-8')
        start = text.index('(_command cmd_pnr\n')
        depth = 0
        for end in range(start,len(text)):
            if text[end]=='(': depth += 1
            elif text[end]==')':
                depth -= 1
                if depth==0: break
        options = ('(_command cmd_pnr\n'
            '            (_gci_state (_integer 0))\n'
            '            (_option gplace_seed (_integer 4))\n'
            '            (_option groute_seed (_integer 5))\n'
            '            (_option optimize_multi_corner_timing (_switch ON))\n'
            '            (_option fix_hold_violation (_switch ON))\n'
            '            (_option fix_hold_violation_iterations (_integer 20))\n'
            '        )')
        project.write_text(text[:start]+options+text[end+1:],encoding='utf-8')
    data.update(state='PASS' if passed else 'FAILED',exit_code=code,errors=errors,
        elapsed_s=round(time.time()-start,2),log_sha256=sha(log))
    save()
    print(json.dumps(data,ensure_ascii=False,indent=2),flush=True)
    return 0 if passed else 1

if __name__ == '__main__':
    raise SystemExit(main())
