"""Reproducible ModelSim batch runner; any compile/simulation error fails."""
import argparse,subprocess,json,time,hashlib,shutil,os,re
from pathlib import Path

_root_override = os.environ.get('FPGA_SIM_ROOT')
ROOT = Path(_root_override).absolute() if _root_override else Path(__file__).resolve().parents[1]
BIN=Path(os.environ.get('MODELSIM_BIN','D:/FPGA/MODELSIM/win64'))
FAILURE_RE=re.compile(r'(?im)^\s*(?:#\s*)?(?:\*\*\s*)?(?:Error:|Fatal:)|AUDIT_FATAL')
BREAK_RE=re.compile(r'(?im)^\s*#?\s*Break at\s+(.+?)\s+line\s+(\d+)\s*$')

def run(name,sources,plusargs=()):
    folder=ROOT/'build'/'sim'/name/str(time.time_ns());folder.mkdir(parents=True,exist_ok=False)
    file_keys={'+CONFIG','+CONFIG2','+VECTORS','+VECTORS2','+SOURCE','+SOURCE2',
               '+GOLDEN','+GOLDEN2','+RESULT','+RESULT2'}
    output_keys={'+RESULT','+RESULT2'}
    original_root=Path(__file__).resolve().parents[1]

    def resolve_file(value):
        path=Path(value)
        if path.is_absolute():
            try:path=ROOT/path.relative_to(original_root)
            except ValueError:pass
        else:path=ROOT/path
        return path

    sim_plusargs=[]
    for argument in plusargs:
        if '=' not in argument:
            sim_plusargs.append(argument);continue
        key,value=argument.split('=',1)
        if key in file_keys:
            path=resolve_file(value)
            if key not in output_keys and not path.is_file():
                raise FileNotFoundError(f'{key} input does not exist: {path}')
            value=os.path.relpath(path,folder).replace('\\','/')
            sim_plusargs.append(key+'='+value)
        else:sim_plusargs.append(argument)
    inputs=[ROOT/s for s in sources]+list((ROOT/'source/rtl').glob('*.vh'))
    for argument in plusargs:
        if '=' in argument:
            key,value=argument.split('=',1)
            if key in file_keys and key not in output_keys:
                path=resolve_file(value)
                if not path.is_file():raise FileNotFoundError(f'{key} input does not exist: {path}')
                inputs.append(path)
    hashes={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
    (folder/'inputs.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    log=[]
    optimized=name+'_optimized'
    do_script='set FileWatch(fileName) {}; vsim '+optimized
    if sim_plusargs:do_script+=' '+' '.join('{'+arg.replace('}','\\}')+'}' for arg in sim_plusargs)
    do_script+='; onfinish stop; run -all; puts SIMULATION_COMPLETE; quit -code 0'
    commands=[[str(BIN/'vlib.exe'),'work'],
              [str(BIN/'vlog.exe'),'-sv','+incdir+'+str(ROOT),*[str(ROOT/s) for s in sources]],
              [str(BIN/'vopt.exe'),'work.'+name,'-o',optimized],
              [str(BIN/'vsim.exe'),'-c','-do',do_script]]
    start=time.monotonic()
    for command in commands:
        p=subprocess.run(command,cwd=folder,capture_output=True,text=True,errors='replace')
        out=p.stdout+p.stderr;log.append(out)
        (folder/'run.log').write_text('\n'.join(log),encoding='utf-8')
        if p.returncode or FAILURE_RE.search(out):
            (folder/'receipt.json').write_text(json.dumps({'passed':False,'command':command,'exit_code':p.returncode},indent=2))
            raise RuntimeError(out[-9000:])
    transcript='\n'.join(log)
    verdict_error=None
    if 'SIMULATION_COMPLETE' not in transcript:
        verdict_error='Simulation did not reach normal completion'
    elif FAILURE_RE.search(transcript):
        verdict_error='Simulation log contains an error/fatal marker'
    else:
        break_match=BREAK_RE.findall(transcript)
        if not break_match:
            verdict_error='Simulator did not report a normal $finish stop location'
        else:
            break_path,break_line=break_match[-1]
            source_name=Path(break_path.replace('\\','/')).name
            source_candidates=[resolve_file(source) for source in sources
                               if Path(source).name.lower()==source_name.lower()]
            finish_text=None
            try:
                for candidate in source_candidates:
                    lines=candidate.read_text(encoding='utf-8-sig',errors='replace').splitlines()
                    line_index=int(break_line)-1
                    if 0<=line_index<len(lines):
                        finish_text=lines[line_index]
                        break
            except OSError:
                pass
            if finish_text is None or not re.search(r'\$finish\b',finish_text):
                verdict_error=f'Simulation stopped at a source line other than $finish: {break_path}:{break_line}'
            elif not any(re.search(r'\$(?:f?display)\s*\([^\n]*"[^"\n]*\bPASS\b',
                                    resolve_file(source).read_text(encoding='utf-8-sig',errors='replace'))
                         for source in sources):
                verdict_error='Testbench has no explicit PASS marker before normal completion'
    if verdict_error:
        (folder/'receipt.json').write_text(json.dumps({'passed':False,'reason':verdict_error},indent=2),encoding='utf-8')
        raise RuntimeError(verdict_error)
    artifacts={}
    for argument in plusargs:
        if argument.startswith(('+RESULT=','+RESULT2=')):
            path=resolve_file(argument.split('=',1)[1])
            if path.exists():
                shutil.copy2(path,folder/path.name)
                artifacts[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt={'passed':True,'verdict':'explicit testbench PASS marker and normal $finish',
             'elapsed_seconds':time.monotonic()-start,'commands':commands,
             'inputs_manifest_sha256':hashlib.sha256((folder/'inputs.json').read_bytes()).hexdigest(),
             'artifacts':artifacts}
    (folder/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('\n'.join(log)[-3000:])
    print(f'{name}: {time.monotonic()-start:.1f} seconds')
    return folder

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('sources',nargs='+')
    a=p.parse_args();run(a.name,a.sources)
