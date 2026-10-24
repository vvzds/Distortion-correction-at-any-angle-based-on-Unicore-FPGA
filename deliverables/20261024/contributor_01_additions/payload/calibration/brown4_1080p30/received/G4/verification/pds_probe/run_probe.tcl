set_arch -family Logos2 -device PG2L100H -package FBG676 -speedgrade -6
add_design probe.v
compile -top_module probe
synthesize -ads
exit
