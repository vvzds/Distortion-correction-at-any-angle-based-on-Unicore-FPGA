from pathlib import Path
import hashlib, json, shutil, sys

sys.stdout.reconfigure(encoding='utf-8')
R = Path(r'C:/Users/lenovo/Desktop/ww/高阶任务三_仓库审查与启动_20261027')
BASE = Path(r'C:/Users/lenovo/Desktop/ww/C50_独立复核与优化_20261027/received/C50_board_delivery_20261027/01_PDS_project')
CANDIDATE = R/'engineering_candidate'
PROJECT = R/'physical_seed7'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assert not PROJECT.exists(), 'Physical project exists; preserve its results'
    manifest={}
    for folder in ('source','ipcore'):
        old={p.relative_to(BASE).as_posix():p for p in (BASE/folder).rglob('*') if p.is_file()}
        new={p.relative_to(CANDIDATE).as_posix():p for p in (CANDIDATE/folder).rglob('*') if p.is_file()}
        for name in old.keys() & new.keys():
            if name != 'source/rtl/corr_subsys/corr_top.v':
                assert sha(old[name])==sha(new[name]), 'Unexpected RTL/IP difference: '+name
        assert set(new)-set(old)=={'source/rtl/corr_subsys/adaptive_gamma.v','source/rtl/corr_subsys/adaptive_gamma_curve.v'} if folder=='source' else not(set(new)-set(old)), 'Unexpected added files in '+folder
        assert not set(old)-set(new), 'Baseline files missing in '+folder
        shutil.copytree(CANDIDATE/folder,PROJECT/folder)
        for name,p in new.items():manifest[name]={'candidate':sha(p),'baseline':sha(old[name]) if name in old else None}
    assert sha(BASE/'HDMI_DDR3_OV5640_test.fdc')==sha(CANDIDATE/'HDMI_DDR3_OV5640_test.fdc')
    shutil.copy2(CANDIDATE/'HDMI_DDR3_OV5640_test.fdc',PROJECT/'HDMI_DDR3_OV5640_test.fdc')
    original=(CANDIDATE/'run_host.tcl').read_text(encoding='utf-8')
    script=original.replace('puts "G7_PHASE=DEV_MAP_DONE"','puts "ADV3_PHASE=DEV_MAP_DONE"')
    script=script.replace('puts "G7_PHASE=PNR_DONE"','puts "ADV3_PHASE=PNR_DONE"')
    script=script.replace('puts "G7_PHASE=FINISHED"','puts "ADV3_PHASE=FINISHED"')
    for marker in ('ADV3_PHASE=DEV_MAP_DONE','ADV3_PHASE=PNR_DONE','ADV3_PHASE=FINISHED'):
        assert script.count(marker)==1
    (PROJECT/'run_physical.tcl').write_text(script,encoding='utf-8')
    synthesis=script.split('puts "ADV3_PHASE=DEV_MAP_DONE"')[0]
    synthesis+='puts "ADV3_PHASE=SYNTHESIS_DONE"\nexit\n'
    (PROJECT/'run_synthesis.tcl').write_text(synthesis,encoding='utf-8')
    receipt={'baseline':str(BASE),'candidate':str(CANDIDATE),'project':str(PROJECT),
             'device':'PG2L100H -6 FBG676','constraint_sha256':sha(PROJECT/'HDMI_DDR3_OV5640_test.fdc'),
             'baseline_seed7_report':str(BASE/'evidence_c50_seed7_final/hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt'),
             'seed':7,'only_existing_file_difference':'source/rtl/corr_subsys/corr_top.v',
             'new_files':['source/rtl/corr_subsys/adaptive_gamma.v','source/rtl/corr_subsys/adaptive_gamma_curve.v'],
             'source_hashes':manifest,'physical_script_sha256':sha(PROJECT/'run_physical.tcl'),
             'synthesis_script_sha256':sha(PROJECT/'run_synthesis.tcl')}
    (R/'verification/timing_input_identity.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print('TIMING INPUTS VERIFIED',len(manifest),'files')

if __name__=='__main__':main()
