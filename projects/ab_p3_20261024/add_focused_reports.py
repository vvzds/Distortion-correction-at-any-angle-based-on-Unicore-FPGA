"""Reporting-only update before physical run; refuses active/finished runs."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent
assert not (R/'results/physical_seed2').exists(), 'Do not mutate an active run'
addon='''# Preserve unrestricted report/CSV; focused reports are diagnostics only.
file rename report_timing report_timing_full_saved
file copy -force multiseed_summary.csv multiseed_summary_full_saved.csv
'''
for name,option,pattern in [('map','-from','u_correction/u_core/u_map/*'),
                            ('cache_from','-from','u_correction/u_core/u_cache/*'),
                            ('cache_to','-to','u_correction/u_core/u_cache/*')]:
    addon+=f'''puts "P3_{name.upper()}_DIAG_BEGIN"
if {{[catch {{report_timing {option} [get_cells {{{pattern}}}] -max_path 20 -nworst 1}} diag_error]}} {{
    puts "P3_{name.upper()}_DIAG_FAILED: $diag_error"
}} else {{
    puts "P3_{name.upper()}_DIAG_COMPLETED"
}}
if {{[file exists report_timing]}} {{file rename report_timing report_timing_{name}_diagnostic}}
'''
addon+='''file rename report_timing_full_saved report_timing
file copy -force multiseed_summary_full_saved.csv multiseed_summary.csv
puts "P3_UNRESTRICTED_REPORT_RESTORED"
'''
driver=R/'physical/host_seed2/analysis.tcl'
s=driver.read_text(encoding='utf-8')
s=s[:s.index('# Preserve the unrestricted final report')]+addon+'exit\n'
driver.write_text(s,encoding='utf-8',newline='\n')
(R/'report_only_addon.tcl').write_text(addon,encoding='utf-8',newline='\n')
path=R/'physical/input_identity.json'
d=json.loads(path.read_text(encoding='utf-8'))
next(x for x in d['inputs'] if x['file']=='analysis.tcl')['sha256']=hashlib.sha256(driver.read_bytes()).hexdigest()
d['reporting_only_change']='Unrestricted top20 plus optional map-from/cache-from/cache-to reports; restore unrestricted report and CSV; unchanged synthesis/PNR/FDC/IP/seed'
path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print('REPORT_SELECTION_UPDATED; inputs=139; no physical run started')
