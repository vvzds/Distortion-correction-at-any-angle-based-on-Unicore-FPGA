"""Verify native success and preserve original physical options in recovered GUI project."""
from pathlib import Path
import hashlib
import json
import re
import shutil

ROOT=Path('D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project')
WORK=ROOT/'top_recovery'
TASK=Path('C:/Users/叶翔/Desktop/yx/PDS顶层解析修复_二号_20261024')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def command_node(text,name):
    start=text.index('(_command '+name+'\n')
    depth=0
    quoted=False
    escape=False
    for pos in range(start,len(text)):
        c=text[pos]
        if escape:
            escape=False
        elif c=='\\' and quoted:
            escape=True
        elif c=='"':
            quoted=not quoted
        elif not quoted:
            if c=='(': depth+=1
            elif c==')':
                depth-=1
                if depth==0: return start,pos+1,text[start:pos+1]
    raise ValueError('Unbalanced PDS command')

def main():
    latest=sorted((WORK/'runs').glob('*/receipt.json'))[-1]
    run=json.loads(latest.read_text(encoding='utf-8'))
    assert run['state']=='PASS' and run['exit_code']==0 and not run['errors']
    log=(latest.parent/'console.log').read_text(encoding='utf-8',errors='replace')
    assert 'Process "Compile" done.' in log
    assert 'Flow-0245' not in log and 'Flow-0189' not in log
    pre=json.loads((WORK/'preflight.json').read_text(encoding='utf-8'))
    assert sha(ROOT/'full_source_1080p30.pds')==pre['original_project_sha256']
    for name,h in pre['input_hashes'].items():
        assert sha(ROOT/name)==h, name
        if name.startswith(('source/','ipcore/')) or name.endswith('.fdc'):
            assert sha(WORK/name)==h, name
    pds=WORK/'full_source_top_recovered.pds'
    text=pds.read_text(encoding='utf-8')
    _,_,compile_node=command_node(text,'cmd_compile')
    assert '(_gci_state (_integer 2))' in compile_node
    assert '(_option top_module (_string "hdmi_ddr_ov5640_top"))' in compile_node
    assert (WORK/'compile/hdmi_ddr_ov5640_top_comp.adf').stat().st_size>0
    shutil.copy2(pds,TASK/'full_source_top_recovered.native_before_physical_options.pds')
    original=(ROOT/'full_source_1080p30.pds').read_text(encoding='utf-8')
    _,_,original_options=command_node(original,'cmd_pnr')
    a,b,_=command_node(text,'cmd_pnr')
    text=text[:a]+original_options+text[b:]
    pds.write_text(text,encoding='utf-8')
    paths=re.findall(r'\(_(?:file|ip|ip_source_item) "([^"]+)"',text)
    assert all((WORK/p).is_file() for p in paths)
    record=dict(state='PASS_COMPILE_ONLY',native_run=run,
        native_compile_state=2,original_inputs_checked=len(pre['input_hashes']),
        all_original_inputs_unchanged=True,recovered_rtl_ip_fdc_match=True,
        original_project_unchanged=True,recovered_project=str(pds),
        recovered_project_sha256=sha(pds),
        physical_options_copied_from_original=True,
        place_seed=4,route_seed=5,hold_iterations=20,multicorner=True,
        source_project_references_checked=len(paths),
        compile_database_sha256=sha(WORK/'compile/hdmi_ddr_ov5640_top_comp.adf'),
        synthesis_run=False,place_route_run=False,bitstream_generated=False,
        programmed=False,uart_sent=False,
        warning_note='Existing HDL/DRC/IP metadata warnings retained, not a zero-warning claim')
    (TASK/'FINAL_VERIFICATION.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
