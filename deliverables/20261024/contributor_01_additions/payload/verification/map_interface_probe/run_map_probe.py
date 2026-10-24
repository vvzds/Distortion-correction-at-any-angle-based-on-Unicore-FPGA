"""Map-port/latency/reset baseline probe. Does not replace Brown4 equivalence or fullframe tests."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, re, subprocess, sys

ROOT = Path(__file__).resolve().parent

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def dump(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def execute(command, cwd, log):
    start = datetime.now(timezone.utc).isoformat()
    with log.open('wb') as stream:
        try:
            code = subprocess.run(list(map(str, command)), cwd=cwd, stdout=stream,
                                  stderr=subprocess.STDOUT, timeout=60).returncode
        except subprocess.TimeoutExpired:
            code = 124
    return dict(command=list(map(str, command)), cwd=str(cwd), start_utc=start,
                end_utc=datetime.now(timezone.utc).isoformat(), exit_code=code,
                log=log.name, log_sha256=sha(log))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--map', type=Path, required=True)
    p.add_argument('--tool-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--latency', type=int, default=11)
    p.add_argument('--init-limit', type=int, default=128)
    a = p.parse_args()
    source = a.map.resolve(); tool = a.tool_root.resolve(); out = a.out.resolve()
    if not source.is_file() or a.latency<0 or a.init_limit<=0:
        p.error('existing map and nonnegative latency/positive init limit required')
    out.mkdir(parents=True, exist_ok=False)
    tb = ROOT/'sim/map_contract_probe_tb.sv'
    anchored = [source, tb, Path(__file__).resolve()]
    before = {str(f): sha(f) for f in anchored}
    tool_before = {n: sha(tool/'bin'/n) for n in ('iverilog.exe', 'vvp.exe')}
    drive = next((x+':' for x in 'ZYXWVUTSRQP' if not Path(x+':/').exists()), None)
    if drive is None:
        raise RuntimeError('no free subst drive')
    subprocess.run(['subst.exe', drive, str(tool)], check=True, capture_output=True)
    steps=[]
    try:
        short=Path(drive+'/')
        steps.append(execute([short/'bin/iverilog.exe','-B',short/'lib/ivl','-V'],out,out/'compiler_version.log'))
        steps.append(execute([short/'bin/vvp.exe','-V'],out,out/'runtime_version.log'))
        steps.append(execute([short/'bin/iverilog.exe','-B',short/'lib/ivl','-g2012','-Wall',
                              '-s','map_contract_probe_tb','-o',out/'probe.vvp',source,tb],out,out/'compile.log'))
        if steps[-1]['exit_code']==0:
            steps.append(execute([short/'bin/vvp.exe','-i',out/'probe.vvp',
                                  f'+LATENCY={a.latency}',f'+INIT_LIMIT={a.init_limit}'],out,out/'simulation.log'))
    finally:
        subprocess.run(['subst.exe',drive,'/D'],check=True,capture_output=True)
    after={str(f):sha(f) for f in anchored}
    tool_after={n:sha(tool/'bin'/n) for n in tool_before}
    log=(out/'simulation.log').read_text(encoding='utf-8',errors='replace') if (out/'simulation.log').is_file() else ''
    compile_log=(out/'compile.log').read_text(encoding='utf-8',errors='replace')
    port_warning=bool(re.search(r'(?i)(expects \d+ bits|dangling input port|not a port)',compile_log))
    ok=(len(steps)==4 and all(s['exit_code']==0 for s in steps) and 'PROBE_PASS ' in log
        and not re.search(r'\b(FATAL|ERROR|TIMEOUT)\b',log) and not port_warning
        and before==after and tool_before==tool_after)
    result=dict(status='PASS' if ok else 'FAIL', scope='MAP_PORTS_IDENTITY_VALID_INIT_LATCH_RESET_ONLY',
                source=str(source), expected_latency_edge_distance=a.latency, init_limit=a.init_limit,
                inputs_before=before, inputs_after=after, inputs_unchanged=before==after,
                tool_before=tool_before, tool_after=tool_after, port_width_warning=port_warning,
                steps=steps, summary=[l for l in log.splitlines() if l.startswith(('INIT ','PROBE_PASS '))],
                full_brown4_equivalence='NOT_RUN', fullframe='NOT_RUN', physical='NOT_RUN', board='PAUSED_BY_USER')
    dump(out/'result.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if ok else 1

if __name__=='__main__':
    sys.exit(main())
