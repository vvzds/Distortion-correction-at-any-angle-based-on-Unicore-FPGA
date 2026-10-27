# Advanced Task 3 C50 Adaptive Gamma Candidate

This is an isolated Pangu 100Pro 1920x1080@30 project candidate. Source baseline: C50 board delivery, 2026-10-27. Adaptive Gamma RTL: collaborator 2's repository package `deliverables/20261024/collab2_adaptive_gamma_v1`.

The only functional integration change is in `source/rtl/corr_subsys/corr_top.v`: compile-time `ADAPTIVE_GAMMA=1` selects the new one-cycle adaptive Gamma branch. C50 sink-credit wiring and original core/cache/writer/param manager are retained. `run_host.tcl` and `run_host.pds` include both new RTL files.

The existing UART command `AA 55 04 04 01 00 00 00 01` enables Gamma after valid calibration parameters are active. `AA 55 04 04 00 00 00 00 00` disables it. Gamma should be off during geometry/calibration comparisons. No new UART command, status bit, or runtime manual/auto switch is introduced.

Evidence and exact source hashes are in the sibling `verification` directory. Historical delivery checks, two local module tests, a 128-pixel C50 write-boundary smoke, and full board-top PDS compile passed. The new three-frame full-HD C50 pressure test timed out at 600 seconds and has no PASS. No whole-project PNR, bitstream generation, or board test has been performed. Do not program this candidate as a qualified image.
