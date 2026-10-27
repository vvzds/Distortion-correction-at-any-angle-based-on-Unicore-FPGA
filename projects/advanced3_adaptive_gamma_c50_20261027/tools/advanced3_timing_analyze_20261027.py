from advanced3_timing_prepare_20261027 import *
import re

BASE_REPORT=BASE/'evidence_c50_seed7_final/hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt'
BASE_PRR=BASE/'evidence_c50_seed7_final/hdmi_ddr_ov5640_top.prr'
BASE_RTR=BASE/'evidence_c50_seed7_final/hdmi_ddr_ov5640_top.rtr'

def parse_summary(p):
    text=p.read_text(encoding='utf-8',errors='replace')
    sections={}
    for corner in ('Slow','Fast'):
        for kind in ('Setup','Hold'):
            header=kind+' Summary('+corner+' Corner):'
            if header not in text:continue
            tail=text.split(header,1)[1].split('====',1)[0]
            m=re.search(r'^\s*ddrphy_sysclk\s+ddrphy_sysclk\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)',tail,re.M)
            assert m,(header,p)
            sections[corner.lower()+'_'+kind.lower()]=dict(wns_or_whs_ns=float(m[1]),
                tns_or_ths_ns=float(m[2]),failing_endpoints=int(m[3]),endpoints=int(m[4]))
    return {'overall':text.splitlines()[0],'ddr_125mhz':sections,'sha256':sha(p)}

def parse_resources(p):
    text=p.read_text(encoding='utf-8',errors='replace')
    usage=text.split('Device Utilization Summary :',1)[1].split('Design Hierarchy',1)[0]
    def one(name):
        m=re.search(r'^\|\s*'+re.escape(name)+r'\s*\|\s*([0-9.]+)\s*\|',usage,re.M)
        assert m,(name,p)
        return float(m[1]) if '.' in m[1] else int(m[1])
    lut=[int(x) for x in re.findall(r'^\|\s*LUT\s*\|\s*(\d+)\s*\|',usage,re.M)]
    ff=[int(x) for x in re.findall(r'^\|\s*FF\s*\|\s*(\d+)\s*\|',usage,re.M)]
    assert len(lut)==2 and len(ff)==2,(p,lut,ff)
    return dict(lut=sum(lut),ff=sum(ff),distributed_ram=one('Distributed RAM'),
                apm=one('Use of APM'),drm=one('Use of DRM'),sha256=sha(p))

def critical_path(p):
    data=p.read_text(encoding='utf-8',errors='replace')
    sections=re.split(r'\n(?=Startpoint  :)',data)
    rows=[]
    for section in sections:
        if 'Path Group  : ddrphy_sysclk' not in section or 'Path Type   : max (slow corner)' not in section:continue
        start=re.search(r'^Startpoint\s*:\s*(.+)$',section,re.M)
        end=re.search(r'^Endpoint\s*:\s*(.+)$',section,re.M)
        slack=re.search(r'Slack \((MET|VIOLATED)\)\s+(-?\d+\.\d+)',section)
        if start and end and slack:rows.append(dict(start=start[1],end=end[1],slack_ns=float(slack[2]),status=slack[1]))
    rows.sort(key=lambda r:r['slack_ns'])
    return {'count_in_top30_report':len(rows),'worst':rows[:8],
            'gamma_paths_in_top30':sum('G_ADAPTIVE' in x['start'] or 'G_ADAPTIVE' in x['end'] for x in rows),
            'sha256':sha(p)}

def main():
    reports={'baseline_seed7':(BASE_REPORT,BASE_PRR,BASE_RTR)}
    for seed in (7,2):
        folder=R/'verification'/('timing_physical_seed'+str(seed))
        paths=tuple(folder/name for name in ('hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt',
                                          'hdmi_ddr_ov5640_top.prr','hdmi_ddr_ov5640_top.rtr'))
        if all(p.exists() for p in paths):reports['gamma_seed'+str(seed)]=paths
    result={name:dict(summary=parse_summary(paths[0]),resources=parse_resources(paths[1]),critical=critical_path(paths[2]))
            for name,paths in reports.items()}
    base=result['baseline_seed7']['resources']
    gamma=result['gamma_seed7']['resources']
    result['same_seed7_resource_delta']={key:gamma[key]-base[key] for key in ('lut','ff','distributed_ram','apm','drm')}
    result['same_seed7_setup_delta_ns']=result['gamma_seed7']['summary']['ddr_125mhz']['slow_setup']['wns_or_whs_ns']-result['baseline_seed7']['summary']['ddr_125mhz']['slow_setup']['wns_or_whs_ns']
    path=R/'verification/timing_comparison.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
