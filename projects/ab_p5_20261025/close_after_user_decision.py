"""Stop this P5 candidate after the user's explicit decision; preserve partial evidence."""
from pathlib import Path
import json,ctypes,subprocess,sys,time,hashlib,datetime
from ctypes import wintypes
from process_snapshot import snapshot
R=Path(__file__).resolve().parent;O=R/'results'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
class UNICODE_STRING(ctypes.Structure):
    _fields_=[('Length',wintypes.USHORT),('MaximumLength',wintypes.USHORT),('Buffer',ctypes.c_void_p)]
k=ctypes.WinDLL('kernel32',use_last_error=True);nt=ctypes.WinDLL('ntdll')
k.OpenProcess.restype=wintypes.HANDLE;k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
k.CloseHandle.argtypes=[wintypes.HANDLE]
nt.NtQueryInformationProcess.argtypes=[wintypes.HANDLE,wintypes.ULONG,ctypes.c_void_p,wintypes.ULONG,ctypes.POINTER(wintypes.ULONG)]
def commandline(pid):
    h=k.OpenProcess(0x1000,False,pid)
    if not h:return ''
    try:
        size=wintypes.ULONG();nt.NtQueryInformationProcess(h,60,None,0,ctypes.byref(size))
        if not size.value:return ''
        buf=ctypes.create_string_buffer(size.value)
        status=nt.NtQueryInformationProcess(h,60,buf,size,ctypes.byref(size))
        if status<0:return ''
        u=UNICODE_STRING.from_buffer(buf);return ctypes.wstring_at(u.Buffer,u.Length//2)
    finally:k.CloseHandle(h)
reason='User explicitly approved ending P5 and seeking another method; area regression and unfavorable intermediate routing; not a completed timing failure.'
physical=O/'physical_seed2/cancel_requested.json';assert not physical.exists()
dump(physical,dict(reason=reason,requested_utc=now()))
rows=snapshot();parents={x['ppid'] for x in rows if x['name'].lower()=='vvp.exe'}
owned=[]
for pid in parents:
    cmd=commandline(pid)
    if str(R/'candidate/run_validation.py').casefold() in cmd.casefold():owned.append((pid,cmd))
assert len(owned)<=1,owned
record=dict(reason=reason,requested_utc=now(),runner_found=bool(owned),stopped_processes=[])
if owned:
    pid,cmd=owned[0];ids={pid}
    while True:
        expanded=ids|{x['pid'] for x in rows if x['ppid'] in ids}
        if expanded==ids:break
        ids=expanded
    targets=sorted([x for x in rows if x['pid'] in ids],key=lambda x:x['pid']!=pid)
    record.update(verified_runner_argv=cmd,stopped_processes=targets)
    dump(O/'controlled_stop_regression.json',record)
    # Stop coordinator first so it cannot launch queued cases after a child exits.
    for target in targets:
        subprocess.run(['powershell.exe','-NoProfile','-Command',f"Stop-Process -Id {target['pid']} -Force -ErrorAction SilentlyContinue"],capture_output=True)
    record['owned_processes_remaining']=[x for x in snapshot() if x['pid'] in ids]
    assert not record['owned_processes_remaining']
    # This runner's private subst mapping is anchored by its recorded input JSON.
    source=next((O/'regression_p5').glob('*/inputs.json'))
    mapping=json.loads(source.read_text(encoding='utf-8'))['tools']['tool_drive_mapping']
    expected=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app')
    assert Path(mapping['target'])==expected
    listing=subprocess.run(['subst'],capture_output=True,text=True).stdout
    line=next((s for s in listing.splitlines() if s.startswith(mapping['drive']+chr(92))),None)
    if line:
        assert str(expected).casefold() in line.casefold(),line
        subprocess.run(['subst',mapping['drive'],'/D'],check=True)
        record['removed_tool_mapping']=mapping
record['finished_utc']=now();dump(O/'controlled_stop_regression.json',record)
cases=[]
for name in ('identity','real_joint','legacy_sim','integration','c6_real_subsystem','c6_host_arb'):
    d=O/'regression_p5'/name
    state='NOT_RUN'
    if (d/'result.json').exists():
        r=json.loads((d/'result.json').read_text(encoding='utf-8'));state='PASS' if r['passed'] else 'FAIL'
    elif d.exists():state='CONTROLLED_STOP_INCOMPLETE'
    cases.append(dict(case=name,state=state,log_sha256=sha(d/'simulation.log') if (d/'simulation.log').exists() else None))
dump(O/'regression_controlled_status.json',dict(completed=False,reason=reason,cases=cases))
print(json.dumps(dict(stopped_processes=record['stopped_processes'],cases=cases),ensure_ascii=False,indent=2))
