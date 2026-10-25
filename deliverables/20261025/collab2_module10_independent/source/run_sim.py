from pathlib import Path
import datetime,hashlib,json,os,re,shutil,subprocess,uuid
W=Path(__file__).resolve().parent
VSIM=Path('D:/FPGA PDS/site/modelsim-win64-10.7-se/win64/vsim.exe')
scratch=Path('D:/FPGA PDS/yx/module10_independent_sim_20261025')/('sim_'+uuid.uuid4().hex[:10])
scratch.mkdir(parents=True)
for name in ('rtl','tb'):shutil.copytree(W/name,scratch/name)
out=W/'evidence'/scratch.name;out.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=dict(started=datetime.datetime.now().astimezone().isoformat(),scratch=str(scratch),tool=str(VSIM),tool_sha256=sha(VSIM),
       sources={str(p.relative_to(W)):sha(p) for d in ('rtl','tb') for p in (W/d).glob('*.v')},cases=[],physical_timing='NOT_RUN',board_application='NOT_RUN')
for top in ('tb_quality_lock','tb_sccb_access','tb_quality_control'):
    script='onerror {quit -code 2 -f}\n'
    if not (scratch/'work').exists():script+='vlib work\n'
    script+='vlog -vlog01compat rtl/ov5640_quality_lock.v rtl/ov5640_sccb_access.v rtl/ov5640_quality_control.v tb/'+top+'.v\n'
    script+='vopt work.'+top+' +acc -o '+top+'_opt\nvsim work.'+top+'_opt\nonfinish stop\nrun -all\nquit -code 0 -f\n'
    (scratch/'run.do').write_text(script,encoding='ascii');(out/(top+'.do')).write_text(script,encoding='ascii')
    with (out/(top+'.log')).open('wb') as f:
        p=subprocess.run([str(VSIM),'-batch','-do','do run.do'],cwd=scratch,stdout=f,stderr=subprocess.STDOUT,
            env=dict(os.environ,TEMP=str(scratch),TMP=str(scratch)),timeout=120)
    s=(out/(top+'.log')).read_text(encoding='utf-8',errors='replace')
    passed=p.returncode==0 and s.count('=== ALL TESTS PASSED (err=0) ===')==1 and not re.search(r'FAIL|\*\* (Error|Fatal)|TEST TIMEOUT',s)
    r['cases'].append(dict(top=top,exit=p.returncode,passed=passed,log_sha256=sha(out/(top+'.log'))))
    (out/'receipt.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    print(top,passed,flush=True)
    if not passed:print(s[-8000:]);raise SystemExit(1)
r['status']='PASS';(out/'receipt.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print('ALL RTL TESTS PASSED')
