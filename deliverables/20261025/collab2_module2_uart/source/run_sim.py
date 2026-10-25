from pathlib import Path
import datetime,hashlib,json,os,re,shutil,subprocess,uuid
W=Path(__file__).resolve().parent
VSIM=Path('D:/FPGA PDS/site/modelsim-win64-10.7-se/win64/vsim.exe')
scratch=Path('D:/FPGA PDS/yx/module2_uart_sim_20261025')/('sim_'+uuid.uuid4().hex[:10])
scratch.mkdir(parents=True)
for name in ('reference','tb'):shutil.copytree(W/name,scratch/name)
out=W/'evidence'/scratch.name;out.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=dict(started=datetime.datetime.now().astimezone().isoformat(),scratch=str(scratch),tool=str(VSIM),tool_sha256=sha(VSIM),cases=[])
for top,tb in [('param_mgr_tb','reference/param_mgr_tb.v'),('param_mgr_extended_tb','tb/param_mgr_extended_tb.v')]:
    script='onerror {quit -code 2 -f}\n'
    if not (scratch/'work').exists():script+='vlib work\n'
    script+='vlog -vlog01compat reference/param_mgr.v '+tb+'\n'
    script+='vopt work.'+top+' +acc -o '+top+'_opt\nvsim work.'+top+'_opt\nonfinish stop\nrun -all\nquit -code 0 -f\n'
    (scratch/'run.do').write_text(script,encoding='ascii');(out/(top+'.do')).write_text(script,encoding='ascii')
    with (out/(top+'.log')).open('wb') as f:
        p=subprocess.run([str(VSIM),'-batch','-do','do run.do'],cwd=scratch,stdout=f,stderr=subprocess.STDOUT,
            env=dict(os.environ,TEMP=str(scratch),TMP=str(scratch)),timeout=180)
    s=(out/(top+'.log')).read_text(encoding='utf-8',errors='replace')
    passed=p.returncode==0 and '=== ALL TESTS PASSED (err=0' in s and not re.search(r'FAIL|\*\* (Error|Fatal)|watchdog timeout',s)
    r['cases'].append(dict(top=top,exit=p.returncode,passed=passed,rtl_sha256=sha(scratch/'reference/param_mgr.v'),tb_sha256=sha(scratch/tb),log_sha256=sha(out/(top+'.log'))))
    (out/'receipt.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    print(top,passed,flush=True)
    if not passed:print(s[-8000:]);raise SystemExit(1)
r['status']='PASS';(out/'receipt.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print('ALL RTL TESTS PASSED')
