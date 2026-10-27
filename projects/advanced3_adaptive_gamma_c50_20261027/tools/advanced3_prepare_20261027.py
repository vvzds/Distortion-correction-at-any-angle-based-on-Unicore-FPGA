from pathlib import Path
import difflib, hashlib, json, shutil, subprocess, sys

sys.stdout.reconfigure(encoding='utf-8')
W = Path(__file__).resolve().parents[1]
R = Path(r'C:/Users/lenovo/Desktop/ww/高阶任务三_仓库审查与启动_20261027')
A = R / 'received_candidate/adaptive_gamma_v1'
B = Path(r'C:/Users/lenovo/Desktop/ww/C50_独立复核与优化_20261027/received/C50_board_delivery_20261027/01_PDS_project')
P = R / 'engineering_candidate'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assert not P.exists(), 'Do not overwrite an existing candidate'
    out = R / 'verification'
    out.mkdir(exist_ok=True)
    checked = subprocess.run([sys.executable, str(A/'tools/verify_delivery.py')], capture_output=True)
    (out/'received_delivery_verify.log').write_bytes(checked.stdout+checked.stderr)
    assert checked.returncode == 0 and b'DELIVERY VERIFIED (err=0)' in checked.stdout
    for name in ('source', 'ipcore'):
        shutil.copytree(B/name, P/name)
    shutil.copy2(B/'HDMI_DDR3_OV5640_test.fdc', P/'HDMI_DDR3_OV5640_test.fdc')
    r = P/'source/rtl/corr_subsys'
    old = (r/'corr_top.v').read_text(encoding='utf-8')
    reference = (A/'reference/corr_top.v').read_text(encoding='utf-8')
    legacy = (A/'rtl/corr_top.v').read_text(encoding='utf-8')
    anchor = '    parameter integer CLK_FREQ = 125_000_000,   // 时钟频率（透传 param_mgr）\n'
    assert old.count(anchor) == 1
    start = '    gamma_lut u_gamma ('
    end = '\n    //==================================================================\n    // rect_wr_if'
    block = reference[reference.index(start):reference.index(end)]
    assert old.count(block) == 1
    new_block = legacy[legacy.index('    // 仅替换Gamma节点'):legacy.index(end)]
    new = old.replace(anchor, anchor+'    parameter integer ADAPTIVE_GAMMA = 1, // Existing UART bit0 enables adaptive branch\n').replace(block, new_block)
    (r/'corr_top.v').write_text(new, encoding='utf-8')
    for name in ('adaptive_gamma.v', 'adaptive_gamma_curve.v'):
        shutil.copy2(A/'rtl'/name, r/name)
    # Retain current sink credit wiring. No candidate reference core is copied.
    for anchor in ('.USE_SINK_CREDIT(1)', '.i_sink_ready(w_sink_ready)', '.o_pix_ready(w_sink_ready)'):
        assert anchor in new
    for file in (B/'source').rglob('*'):
        if file.is_file() and file.name != 'corr_top.v':
            assert sha(file) == sha(P/file.relative_to(B))
    for name in ('adaptive_gamma.v','adaptive_gamma_curve.v'):
        assert sha(A/'rtl'/name) == sha(r/name)
    tcl = (B/'run_host.tcl').read_text(encoding='utf-8')
    anchor = 'add_design "source/rtl/corr_subsys/gamma_lut.v"\n'
    assert tcl.count(anchor) == 1
    tcl = tcl.replace(anchor, anchor+''.join('add_design "source/rtl/corr_subsys/'+n+'"\n' for n in ('adaptive_gamma.v','adaptive_gamma_curve.v')))
    (P/'run_host.tcl').write_text(tcl, encoding='utf-8')
    pds = (B/'run_host.pds').read_text(encoding='utf-8')
    anchor = '                (_file "source/rtl/corr_subsys/gamma_lut.v"'
    assert pds.count(anchor) == 1
    blocks = ''.join('                (_file "source/rtl/corr_subsys/'+n+'"\n                    (_format verilog)\n                )\n' for n in ('adaptive_gamma.v','adaptive_gamma_curve.v'))
    (P/'run_host.pds').write_text(pds.replace(anchor,blocks+anchor),encoding='utf-8')
    (out/'corr_top_C50_to_adaptive.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='original_C50/corr_top.v',tofile='adaptive_candidate/corr_top.v')),encoding='utf-8')
    receipt = dict(status='RECEIVED_AND_OVERLAY_READY', repository='vvzds/Distortion-correction-at-any-angle-based-on-Unicore-FPGA',
                   main_commit=json.loads((R/'main_commit.json').read_text(encoding='utf-8'))['sha'],
                   source_package='deliverables/20261024/collab2_adaptive_gamma_v1',
                   historical_tests='Six ModelSim receipts verified; not rerun locally',
                   preserved=dict(core=sha(r/'undistort_core.v'),cache=sha(r/'undistort_cache_ab.v'),writer=sha(r/'rect_wr_if.v'),params=sha(r/'param_mgr.v')),
                   modifications=['corr_top ADAPTIVE_GAMMA default 1, replace gamma node only','Two unmodified Gamma RTL files added','PDS/Tcl source lists extended'],
                   baseline_modified=False,physical_timing='NOT_RUN',board_test='NOT_RUN',bitstream_generated=False,
                   files={p.relative_to(P).as_posix():sha(p) for p in P.rglob('*') if p.is_file()})
    (out/'receive_and_overlay_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(__file__,R/Path(__file__).name)
    print('RECEIVE PASS; C50 adaptive candidate ready:',P)

if __name__ == '__main__':
    main()
