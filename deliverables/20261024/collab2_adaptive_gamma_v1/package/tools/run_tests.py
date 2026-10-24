"""ModelSim batch regression; never treats exit zero alone as PASS."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile,time,datetime
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--vsim',default=r'D:\FPGA PDS\site\modelsim-win64-10.7-se\win64\vsim.exe')
    ap.add_argument('--scratch',default='D:/FPGA PDS/sty/undistort_core_g1_verify/adaptive_gamma_20261024')
    ap.add_argument('--integration',action='store_true',help='Run new write-path integration and existing manual-Gamma integration')
    ap.add_argument('--case',action='append',help='Run only a named testbench')
    args=ap.parse_args()
    if not str(Path(args.scratch).resolve()).isascii():
        raise ValueError('ModelSim 10.7 requires an ASCII-only scratch path')
    out=ROOT/'evidence'/datetime.datetime.now().strftime('sim_%Y%m%d_%H%M%S')
    out.mkdir(parents=True)
    subprocess.run([os.sys.executable,str(ROOT/'tools/generate_vectors.py')],check=True)
    scratch=Path(args.scratch)/out.name;scratch.mkdir(parents=True)
    for name in ('rtl','sim','reference'):shutil.copytree(ROOT/name,scratch/name)
    shutil.copy2(ROOT/'sim/vectors.mem',scratch/'vectors.mem')
    receipt={'started':datetime.datetime.now().astimezone().isoformat(),
             'tool':args.vsim,'tool_sha256':sha(Path(args.vsim)),
             'inputs':{str(p.relative_to(ROOT)):sha(p) for folder in ('rtl','sim') for p in (ROOT/folder).glob('*') if p.is_file()},
             'cases':[],'hardware_test':False,'physical_timing':'NOT_RUN'}
    tops=('gamma_lut_tb','gamma_write_path_tb','corr_top_tb') if args.integration else ('adaptive_gamma_curve_tb','adaptive_gamma_tb','adaptive_gamma_full_tb')
    if args.case:
        if any(t not in tops for t in args.case):raise ValueError('Unknown case for selected suite')
        tops=tuple(args.case)
    for top in tops:
        script='onerror {quit -code 2 -f}\n'
        if not (scratch/'work').exists():script+='vlib work\n'
        sources=['rtl/adaptive_gamma_curve.v','rtl/adaptive_gamma.v','rtl/gamma_lut.v']
        if args.integration:
            sources+=['rtl/corr_top.v']+['reference/'+n+'.v' for n in ('param_mgr','rect_wr_if','undistort_core','undistort_map','undistort_line_cache','undistort_bilinear')]+['sim/ideal_link.v']
        script+='vlog -vlog01compat '+' '.join(sources)+' sim/'+top+'.v\n'
        script+='vopt work.'+top+' +acc -o '+top+'_opt\n'
        script+='vsim work.'+top+'_opt\nonfinish stop\nrun -all\nquit -code 0 -f\n'
        (scratch/'run.do').write_text(script,encoding='ascii')
        (out/(top+'.do')).write_text(script,encoding='ascii')
        begin=time.monotonic()
        with (out/(top+'.log')).open('wb') as log:
            p=subprocess.run([args.vsim,'-batch','-do','do run.do'],cwd=scratch,stdout=log,stderr=subprocess.STDOUT,timeout=600,
                             env=dict(os.environ,TEMP=str(scratch),TMP=str(scratch)))
        raw=(out/(top+'.log')).read_text(encoding='utf-8',errors='replace')
        passed=p.returncode==0 and raw.count('=== ALL TESTS PASSED (err=0) ===')==1 and not re.search(r'FAIL|\*\* (?:Error|Fatal)',raw)
        receipt['cases'].append(dict(top=top,passed=passed,exit=p.returncode,seconds=time.monotonic()-begin,log_sha256=sha(out/(top+'.log'))))
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        print(top, 'PASS' if passed else 'FAIL', flush=True)
        if not passed:print(raw[-5000:]);return 1
    receipt['status']='PASS'
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return 0
if __name__=='__main__':raise SystemExit(main())
