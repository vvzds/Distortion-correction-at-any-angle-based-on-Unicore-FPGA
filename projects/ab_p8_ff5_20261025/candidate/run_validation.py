"""R2: per-run include/vector/tool/command hashes; historical evidence untouched."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse, hashlib, json, re, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEFAULT_TOOL=ROOT.parents[2]/'work/simulator/iverilog/app'
CORE=['source/rtl/'+n+'.v' for n in ('undistort_core','undistort_map','undistort_bilinear','undistort_cache_ab')]
SUB=['integration/source/rtl/'+n+'.v' for n in ('corr_top','param_mgr','gamma_lut','rect_wr_if')]
INC=[ROOT/'verification_data',ROOT/'host_ab',ROOT/'sim']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def plan(name):
    args=[];vectors=[];data=False
    tops={'cache72':'undistort_line_cache_tb','segment':'segment_cache_tb','mode_switch':'cache_mode_switch_tb','r3_boundary':'cache_boundary_r3_tb','c6_display':'c6_display_bridge_tb','legacy_sim':'undistort_core_sim_tb','integration':'corr_top_tb','c6_real_subsystem':'c6_real_subsystem_tb','c6_host_arb':'c6_host_arb_tb'}
    if name in ('cache72','segment','mode_switch','r3_boundary'):
        tb={'cache72':'cache72_ab_tb.v','segment':'segment_cache_tb.v','mode_switch':'cache_mode_switch_tb.v','r3_boundary':'cache_boundary_r3_tb.v'}[name]
        files=['sim/'+tb,CORE[-1]]
    elif name=='c6_display':files=['sim/c6_display_bridge_tb.v','reference/corr_read_bridge.v']
    elif name=='legacy_sim':files=['sim/legacy_sim_tb.v']+CORE
    elif name=='integration':files=CORE+SUB+['integration/sim_models/ideal_link.v','integration/tb/corr_top_tb.v']
    elif name in ('c6_real_subsystem','c6_host_arb'):
        files=['sim/'+tops[name]+'.v']+CORE+SUB+['reference/corr_read_bridge.v']
        if name=='c6_host_arb':files+=['host_ab/source/rtl/'+n+'.v' for n in ('corr_slot_ctrl','corr_write_pack','corr_write_arb')]
        args=['+MODE=1'];vectors=['source_words_1.hex','real_pixels_1.hex','real_uart_bytes.hex'];data=True
    else:
        configs={'identity':(0,0,0,0),'real_standard':(1,0,0,0),'real_first64':(1,64,0,0),'real_period2':(1,0,2,0),'real_grant32':(1,0,0,32),'real_joint':(1,64,2,32)}
        mode,latency,period,grant=configs[name]
        files=['sim/calibration_core_ab_tb.v']+CORE
        vector='identity_pixels.hex' if mode==0 else 'real_pixels_1.hex'
        args=[f'+MODE={mode}','+PATTERN=1','+SLOT=3','+VECTOR=vectors/'+vector,f'+LATENCY={latency}',f'+PERIOD={period}',f'+GRANT={grant}','+GATE=1']
        vectors=[vector,'source_words_1.hex']+(['map_expected.hex'] if mode else []);data=True
    return dict(top=tops.get(name,'calibration_core_ab_tb'),files=[ROOT/f for f in files],plusargs=args,vectors=[ROOT/'verification_data/vectors'/v for v in vectors],data_cwd=data)

def dependencies(files):
    result=set(files);pending=list(files)
    while pending:
        source=pending.pop()
        for name in re.findall(r'`include\s+"([^"]+)"',source.read_text(encoding='utf-8-sig')):
            found=next((d/name for d in [source.parent]+INC if (d/name).is_file()),None)
            if found is None:raise FileNotFoundError(f'include {name} from {source}')
            if found not in result:result.add(found);pending.append(found)
    return sorted(result)

def execute(command,cwd,log,timeout):
    start=now();tick=time.monotonic()
    with log.open('wb') as stream:
        try:code=subprocess.run(list(map(str,command)),cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout).returncode
        except subprocess.TimeoutExpired:code=124
        except OSError as exc:stream.write(str(exc).encode('utf-8'));code=127
    return dict(command=list(map(str,command)),cwd=str(cwd),start_utc=start,end_utc=now(),elapsed_seconds=time.monotonic()-tick,exit_code=code,log=log.name,log_sha256=sha(log))

def run_case(name,outroot,engine,tool,timeout,versions):
    out=outroot/name;out.mkdir(exist_ok=False);item=plan(name)
    cwd=ROOT/'verification_data' if item['data_cwd'] else out
    anchored=sorted(set(dependencies(item['files'])+item['vectors']+[Path(__file__).resolve(),ROOT/'run_sim.ps1',ROOT/'build_candidate_sources.py']))
    before=[dict(file=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in anchored]
    dump(out/'inputs.json',dict(case=name,engine=engine,recorded_at_utc=now(),inputs=before,compile_files=[p.relative_to(ROOT).as_posix() for p in item['files']],runtime_vectors=[p.relative_to(ROOT).as_posix() for p in item['vectors']],plusargs=item['plusargs'],working_directory=str(cwd),tools=versions))
    print('START',engine,name,flush=True);steps=[]
    if engine=='icarus':
        binary=out/'simulation.vvp'
        cmd=[tool/'bin/iverilog.exe','-B',tool/'lib/ivl','-g2012']
        for d in INC:cmd+=['-I',d]
        steps.append(execute(cmd+['-s',item['top'],'-o',binary]+item['files'],ROOT,out/'compile.log',120))
        cmd=[tool/'bin/vvp.exe','-i',binary]+item['plusargs']
    else:
        steps.append(execute([tool/'vlib.exe',out/'work'],out,out/'vlib.log',60))
        for tb in (False,True):
            files=[f for f in item['files'] if f.name.endswith('_tb.v')==tb]
            cmd=[tool/'vlog.exe']+(['-sv'] if tb else [])+['-work',out/'work']+['+incdir+'+d.as_posix() for d in INC]+files
            steps.append(execute(cmd,out,out/('compile_tb.log' if tb else 'compile_rtl.log'),120))
        do=out/'run.do';do.write_text('onerror {quit -code 2 -f}\nonbreak {quit -code 0 -f}\nrun -all\nquit -code 0 -f\n',encoding='ascii')
        cmd=[tool/'vsim.exe','-c','-onfinish','stop','-voptargs=+acc',str(out/'work')+'.'+item['top'],'-l',out/'transcript.log','-do',do]+item['plusargs']
    if all(s['exit_code']==0 for s in steps):steps.append(execute(cmd,cwd,out/'simulation.log',timeout))
    body=(out/'simulation.log').read_text(encoding='utf-8',errors='replace') if (out/'simulation.log').exists() else ''
    markers={'cache72':'ALL TESTS PASSED (err=0)','segment':'SEGMENT_CACHE PASS cache72=72','mode_switch':'CACHE_MODE_SWITCH PASS','r3_boundary':'R3_BOUNDARY PASS','c6_display':'C6_DISPLAY_BRIDGE PASS','c6_host_arb':'C6_HOST_ARB PASS','c6_real_subsystem':'C6_REAL_SUBSYSTEM PASS','legacy_sim':'ALL TESTS PASSED (err=0)','integration':'ALL TESTS PASSED (err=0)'}
    marker=markers.get(name,'CORE PASS');bad=re.findall(r'\b(?:FATAL|FAIL|FAILED|TIMEOUT|MISMATCH|ERROR)\b',body,flags=re.I)
    after=[dict(file=r['file'],sha256=sha(ROOT/r['file'])) for r in before]
    unchanged=all(a['sha256']==b['sha256'] for a,b in zip(before,after))
    passed=all(s['exit_code']==0 for s in steps) and marker in body and not bad and unchanged
    result=dict(case=name,engine=engine,passed=passed,steps=steps,inputs_after=after,inputs_unchanged=unchanged,terminal_marker=marker,terminal_marker_seen=marker in body,bad_tokens=bad,summary_lines=[s for s in body.splitlines() if any(k in s for k in ('PASS','AB_STATS','R3_','R4_'))])
    dump(out/'result.json',result);print('END',engine,name,'PASS' if passed else 'FAIL',flush=True);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cases',nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--engine',choices=('icarus','modelsim'),default='icarus');p.add_argument('--tool-root',type=Path);p.add_argument('--jobs',type=int,default=1);p.add_argument('--timeout',type=int,default=7200);a=p.parse_args()
    if a.jobs<1 or a.timeout<1 or len(a.cases)!=len(set(a.cases)):p.error('positive jobs/timeout and unique cases required')
    tool=(a.tool_root or DEFAULT_TOOL).resolve();exe=tool/('bin/iverilog.exe' if a.engine=='icarus' else 'vlog.exe')
    if not exe.is_file():p.error('tool unavailable: '+str(exe))
    a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
    version=execute([exe]+(['-B',tool/'lib/ivl','-V'] if a.engine=='icarus' else ['-version']),a.out,a.out/'tool_version.log',60)
    versions=dict(compiler_sha256=sha(exe),version_step=version,python=sys.version,platform=sys.platform)
    # This Windows Icarus build needs a short executable path (same workaround
    # as the original launcher). A private subst mapping lasts for this run.
    drive=None
    try:
        if a.engine=='icarus':
            drive=next((letter+':' for letter in 'ZYXWVUTSRQP' if not Path(letter+':/').exists()),None)
            if drive is None:raise RuntimeError('no free temporary tool drive')
            subprocess.run(['subst.exe',drive,str(tool)],check=True,capture_output=True)
            versions['tool_drive_mapping']=dict(drive=drive,target=str(tool))
            tool=Path(drive+'/')
        with ThreadPoolExecutor(max_workers=a.jobs) as pool:results=list(pool.map(lambda n:run_case(n,a.out,a.engine,tool,a.timeout,versions),a.cases))
    finally:
        if drive:subprocess.run(['subst.exe',drive,'/D'],check=True,capture_output=True)
    dump(a.out/'summary.json',dict(engine=a.engine,results=[dict(case=r['case'],passed=r['passed']) for r in results]))
    return 0 if all(r['passed'] for r in results) else 1
if __name__=='__main__':sys.exit(main())
