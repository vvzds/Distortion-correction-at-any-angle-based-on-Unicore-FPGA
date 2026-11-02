"""Reproducible ModelSim batch runner; any compile/simulation error fails."""
import argparse,subprocess,json,time,hashlib,shutil,os
from pathlib import Path

_root_override = os.environ.get('FPGA_SIM_ROOT')
ROOT = Path(_root_override).absolute() if _root_override else Path(__file__).resolve().parents[1]
BIN=Path(os.environ.get('MODELSIM_BIN','D:/FPGA/MODELSIM/win64'))

def run(name,sources,plusargs=()):
    folder=ROOT/'build'/'sim'/name/str(time.time_ns());folder.mkdir(parents=True,exist_ok=False)
    file_keys={'+CONFIG','+VECTORS','+SOURCE','+GOLDEN','+RESULT'}
    sim_plusargs=[]
    for argument in plusargs:
        if '=' not in argument:
            sim_plusargs.append(argument);continue
        key,value=argument.split('=',1)
        if key in file_keys:
            path=Path(value)
            if path.is_absolute():
                try:path=ROOT/path.relative_to(Path(__file__).resolve().parents[1])
                except ValueError:pass
            else:path=ROOT/path
            value=os.path.relpath(path,folder).replace('\\','/')
            sim_plusargs.append(key+'='+value)
        else:sim_plusargs.append(argument)
    inputs=[ROOT/s for s in sources]+list((ROOT/'source/rtl').glob('*.vh'))
    for argument in plusargs:
        if '=' in argument:
            key,value=argument.split('=',1)
            if key!='+RESULT' and Path(value).is_file():inputs.append(Path(value))
    hashes={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
    (folder/'inputs.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    log=[]
    optimized=name+'_optimized'
    do_script='set FileWatch(fileName) {}; vsim '+optimized
    if sim_plusargs:do_script+=' '+' '.join('{'+arg.replace('}','\\}')+'}' for arg in sim_plusargs)
    do_script+='; onerror {quit -code 1}; onbreak {quit -code 1}; onfinish stop; run -all; puts SIMULATION_COMPLETE; quit -code 0'
    commands=[[str(BIN/'vlib.exe'),'work'],
              [str(BIN/'vlog.exe'),'-sv','+incdir+'+str(ROOT),*[str(ROOT/s) for s in sources]],
              [str(BIN/'vopt.exe'),'work.'+name,'-o',optimized],
              [str(BIN/'vsim.exe'),'-c','-do',do_script]]
    start=time.monotonic()
    for command in commands:
        p=subprocess.run(command,cwd=folder,capture_output=True,text=True,errors='replace')
        out=p.stdout+p.stderr;log.append(out)
        (folder/'run.log').write_text('\n'.join(log),encoding='utf-8')
        if p.returncode or '** Error' in out or '** Fatal' in out:
            (folder/'receipt.json').write_text(json.dumps({'passed':False,'command':command,'exit_code':p.returncode},indent=2))
            raise RuntimeError(out[-9000:])
    if 'SIMULATION_COMPLETE' not in log[-1]:raise RuntimeError('Simulation did not reach normal completion')
    artifacts={}
    for argument in plusargs:
        if argument.startswith('+RESULT='):
            path=Path(argument.split('=',1)[1])
            if not path.is_absolute():path=ROOT/path
            if path.exists():
                shutil.copy2(path,folder/path.name)
                artifacts[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt={'passed':True,'elapsed_seconds':time.monotonic()-start,'commands':commands,
             'inputs_manifest_sha256':hashlib.sha256((folder/'inputs.json').read_bytes()).hexdigest(),
             'artifacts':artifacts}
    (folder/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('\n'.join(log)[-3000:])
    print(f'{name}: {time.monotonic()-start:.1f} seconds')
    return folder

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('sources',nargs='+')
    a=p.parse_args();run(a.name,a.sources)
