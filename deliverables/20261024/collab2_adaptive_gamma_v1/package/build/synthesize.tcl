# 独立模块综合入口，不含板卡引脚、不产生下载位流。
set_arch -family Logos2 -device PG2L100H -package FBG676 -speedgrade -6
add_design rtl/adaptive_gamma_curve.v
add_design rtl/adaptive_gamma.v
compile -top_module adaptive_gamma
synthesize -ads -disable_io_insertion -frequency 125
puts "ADAPTIVE_GAMMA_SYNTHESIS_COMPLETE"
exit
