"""Generate consistent PDS GUI and batch source lists from the audited host."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BOARD=['hdmi_ddr_ov5640_top','raw8_to_rgb565','frame_bank_ctrl','corr_read_bridge',
       'corr_write_arb','corr_slot_ctrl','fram_buf','i2c_com','iic_dri','ms72xx_ctl',
       'ms7200_ctl','ms7210_ctl','power_on_delay','rd_buf','rd_ctrl','reg_config',
       'sync_vg','wr_buf','wr_cmd_trans','wr_ctrl','wr_rd_ctrl_top']
NEW=['projective_divide','mul32_pipe','brown_map','patch_store','bilinear_rgb','adaptive_gamma','tile_engine',
     'tile_write_pack','uart_phy','host_control','bno_spi_byte','bno085_bridge',
     'imu_projective_map']
IP=['pll','rd_fram_buf','wr_fram_buf','ddr3_test']
FILES=[f'source/rtl/{n}.v' for n in BOARD+NEW]+[f'ipcore/{n}/{n}.idf' for n in IP]
script='''cd [file dirname [info script]]
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
'''+''.join(f'add_design "{f}"\n' for f in FILES)+'''add_constraint "HDMI_DDR3_OV5640_test.fdc"
compile -top_module hdmi_ddr_ov5640_top
synthesize -ads -selected_syn_tool_opt 2
if {[info exists ::env(FPGA_SYNTH_ONLY)] && $::env(FPGA_SYNTH_ONLY) eq "1"} {exit}
dev_map
if {[info exists ::env(FPGA_PNR_SEED)]} {
    pnr -gplace_seed $::env(FPGA_PNR_SEED) -groute_seed $::env(FPGA_PNR_SEED) -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 20
} else {pnr}
report_timing -max_path 30
gen_bit_stream
'''
(ROOT/'build.tcl').write_text(script)
template=(ROOT/'tools/vendor_host_template.pds').read_text(encoding='utf-8-sig')
start=template.index('        (_widget wgt_my_design_src')
end=template.index('        (_widget ',start+20)
widget='        (_widget wgt_my_design_src\n            (_input\n'
for file in FILES:
    # Vendor IPs belong to the preserved wgt_my_ips_src widget. Registering
    # their .idf files as ordinary design sources breaks GUI elaboration.
    if file.endswith('.v'):
        widget+=f'                (_file "{file}" (_format verilog))\n'
widget+='            )\n        )\n'
(ROOT/'pango_undistort.pds').write_text(template[:start]+widget+template[end:],encoding='utf-8')
