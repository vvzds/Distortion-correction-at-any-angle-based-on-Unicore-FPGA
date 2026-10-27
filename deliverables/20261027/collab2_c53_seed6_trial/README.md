# C53 seed6 fixed-seed timing trial (2026-10-27)

This is a physical-only retry of the functional C53 line-cache pipeline in `../collab2_advanced_task2_audit/candidates/c53/`. RTL and constraints match the prior seed8 run; `run_host.tcl` changes only `-gplace_seed` and `-groute_seed` from 8 to 6. The cache RTL SHA256 is `9DA0C2EFCB07797BAE2FD4726A22D4B917F84A4CB02DB4A7A07C6AEB2390D1FB` and the FDC SHA256 is `DBC2C1903AF628F90EFAAE0B3165D471778DFE64DF378AE117D26980F0DFFC73`.

Compile, synthesis, and device map completed. Detailed placement had positive preliminary slack, but detailed routing remained incomplete: after iteration 790, 1,126 networks were unrouted. The operator stopped the PDS child after the predeclared 750-iteration budget. The parent reported `Flow-0189` because its child was interrupted; this is not evidence of a spontaneous PDS failure. `place_route_stopped.log` is the raw child log. There is no final routed setup/hold report and no bitstream.

C53's 11 full-system functional scenarios and identity modeled publication rate of 44.330045 fps remain valid for this unchanged RTL. Physical promotion still fails: seed7 routed setup is -0.068 ns, seed8 routed setup is -0.340 ns, and seed6 has no routed timing result. C50 seed7 remains the board-tested, timing-closed fallback.
