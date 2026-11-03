"""Build an immutable source snapshot and retain hash-bound native evidence."""
import argparse,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
_root_override = os.environ.get('FPGA_BUILD_ROOT')
ROOT = Path(_root_override).absolute() if _root_override else Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--name',default='initial');p.add_argument('--synth-only',action='store_true')
p.add_argument('--pds',default='D:/pango/PDS_2022.2-SP6.4')
p.add_argument('--seed',type=int)
a=p.parse_args();dest=ROOT/'build/pds'/a.name
if dest.exists(): raise SystemExit(f'Build name already exists: {dest}; choose a new name')
dest.mkdir(parents=True)
for folder in ['source','ipcore']:
    shutil.copytree(ROOT/folder,dest/folder)
for name in ['build.tcl','HDMI_DDR3_OV5640_test.fdc']:
    shutil.copy2(ROOT/name,dest/name)
manifest={str(f.relative_to(dest)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest()
          for f in sorted(dest.rglob('*')) if f.is_file()}
(dest/'source_hashes.json').write_text(json.dumps(manifest,indent=2))
env=os.environ.copy();env['FPGA_SYNTH_ONLY']='1' if a.synth_only else '0'
if a.seed is not None:env['FPGA_PNR_SEED']=str(a.seed)
command=[str(Path(a.pds)/'bin/pds_shell.exe'),'-file',str(dest/'build.tcl').replace('\\','/'),
         '-work_dir',str(dest).replace('\\','/'),'-project_name','pango_undistort']
work_dir=str(dest);mapped_drive=None
if os.name=='nt' and len(command[2])>120:
    for letter in 'ZYXWVUTSRQPONMLKJIHGFED':
        drive=f'{letter}:\\'
        if not Path(drive).exists():
            mapped=subprocess.run(['subst',f'{letter}:',str(dest)],capture_output=True)
            if mapped.returncode==0:
                mapped_drive=letter;work_dir=drive
                command[2]=f'{letter}:/build.tcl';command[4]=drive.replace('\\','/')
                break
    if mapped_drive is None:
        raise SystemExit('PDS path exceeds the supported limit and no SUBST drive is available')
start=time.time()
try:
    with (dest/'console.log').open('w',encoding='utf-8') as log:
        result=subprocess.run(command,cwd=work_dir,env=env,stdout=log,stderr=subprocess.STDOUT)
finally:
    if mapped_drive:
        subprocess.run(['subst',f'{mapped_drive}:','/d'],capture_output=True)
receipt={'exit_code':result.returncode,'elapsed_seconds':time.time()-start,'command':command,
         'seed':a.seed,'mapped_drive':mapped_drive,
         'source_manifest_sha256':hashlib.sha256((dest/'source_hashes.json').read_bytes()).hexdigest()}
reports=list((dest/'report_timing').glob('*.rtr'))
report_text=[r.read_text(errors='replace') for r in reports]
receipt['timing_passed']=bool(reports) and all(
    'Design Summary : All Constraints Met.' in text and 'Slack (VIOLATED)' not in text
    for text in report_text)
(dest/'receipt.json').write_text(json.dumps(receipt,indent=2))
text=(dest/'console.log').read_text(encoding='utf-8',errors='replace')
print(text[-8000:]);print(json.dumps(receipt,indent=2))
if result.returncode or any(line.startswith('E:') for line in text.splitlines()):
    raise SystemExit('PDS failed; no bitstream qualification')
if not a.synth_only and not list(dest.rglob('*.sbit')):
    raise SystemExit('PDS generated no bitstream')
if not a.synth_only and not receipt['timing_passed']:
    raise SystemExit('Timing did not pass; generated bitstream is unqualified')
