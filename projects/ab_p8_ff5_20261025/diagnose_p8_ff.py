from pathlib import Path
import re,json,hashlib,shutil
W=Path(r'C:\Users\lenovo\Desktop\ww');R=W/'AB_P8触摸译码局部化_20261025';B=W/'AB_P7R1标签RAM与共享比较_20261025'
def read_cells(p):
    t=p.read_text();a=t.index('\nmodule undistort_cache_ab\n');b=t.index('\nendmodule',a);t=t[a:b]
    starts=list(re.finditer(r'^    (GTP_\w+)\s+/\*\s*(.*?)\s*\*/',t,re.M));cells={}
    for i,m in enumerate(starts):
        block=t[m.start():starts[i+1].start() if i+1<len(starts) else len(t)]
        name=m[2].strip('\\ ')
        cells[name]=dict(type=m[1],name=name,ports={pin:v.strip() for pin,v in re.findall(r'\.(\w+)\s+\(([^()]*)\)',block)},block=block)
    return cells
data={name:read_cells(root/'physical/host_seed2/synthesize/hdmi_ddr_ov5640_top_syn.vm') for name,root in [('p7r1',B),('p8',R)]}
ff={name:{k:v for k,v in cells.items() if v['type'].startswith('GTP_DFF')} for name,cells in data.items()}
added=sorted(ff['p8'].keys()-ff['p7r1'].keys());removed=sorted(ff['p7r1'].keys()-ff['p8'].keys())
categories={
 'timestamp_msb':[n for n in added if re.fullmatch(r'last_use\[\d+\]\[21\]',n)],
 'leaf_age_msb':[n for n in added if re.fullmatch(r'victim_leaf\[\d+\]\[29\]',n)],
 'group_age_msb':[n for n in added if re.fullmatch(r'victim_age\[\d+\]\[21\]',n)],
}
assert len(added)==300 and not removed
assert {k:len(v) for k,v in categories.items()}==dict(timestamp_msb=192,leaf_age_msb=96,group_age_msb=12)
assert set(added)==set().union(*map(set,categories.values()))
# Trace a representative retained MSB FF to its synthesis LUT driver.
example=ff['p8']['last_use[0][21]'];net=example['ports']['D']
drivers=[c for c in data['p8'].values() if any(c['ports'].get(p)==net for p in ('Z','Z5','Q','O'))]
result=dict(passed=True,p7r1_ff_primitives=len(ff['p7r1']),p8_ff_primitives=len(ff['p8']),added_count=len(added),removed_count=len(removed),categories=categories,
 representative_timestamp_ff=example,representative_data_drivers=drivers,
 interpretation='All +300 FFs are retained MSBs in existing 22-bit age state and its replacement pipeline. No new RTL registers were declared. P7 eliminated these MSBs; P8 preserved them. Exact optimizer care-set/reachability reasoning is not exposed by the tool, so its internal reason is a hypothesis, not a proven timing or functional defect.',
 code_evidence='Core bounds prep_available by prepared_count<2073600; i_touch=prep_reuse. Host connects both i_lookup_seq and i_touch_seq to prepared_count. 2073600<2**21. Kept touch qualifiers may prevent cross-boundary implication optimization. Do not truncate the frozen 22-bit cache interface or force an MSB to zero to pass a gate.')
(R/'results/synthesis_gate/ff_delta_diagnosis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
shutil.copy2(__file__,R/'diagnose_p8_ff.py');shutil.copy2(Path(__file__).parent/'inspect_p8_touch.py',R/'inspect_p8_touch.py')
print(json.dumps(dict(added_count=len(added),removed_count=len(removed),categories={k:len(v) for k,v in categories.items()},data_driver_count=len(drivers)),indent=2))
