# C56 line-tag path trial (2026-10-27)

Status: isolated candidate; physical implementation pending. C50 seed7 remains the board-tested fallback. No C56 bitstream has been generated or programmed.

This trial starts from C53 and registers the missing row, segment, and set before cache victim selection. The set member index is formed by concatenation. `rtl/undistort_core.v` is unchanged from C53. The functional simulation uses `../rtl/*.v` in `evidence/system/run.do`; PDS uses the same two candidate RTL files in its `host/source/rtl/corr_subsys/` tree. The older copies under `full_regression/source/rtl/corr_subsys/` are not selected by `run.do`.

Source SHA256:

- `rtl/undistort_cache_ab.v`: `E7AAAF4F8F587AD400AD26A10471872BC5B4E22550C24BE3E3FA969100DF0341`
- `rtl/undistort_core.v`: `A374876B7430FF14FE0E524492CF3AB9F94778596F73A9FE3FB30EE2B0ABF58B`

The 11 complete 1920x1080 system scenarios in `evidence/system/` all report `ALL TESTS PASSED (err=0)`. Under the existing 125 MHz DDR model, identity publishes in 2,819,758 cycles (44.330045 modeled fps), real calibrated parameters in 3,303,170 cycles (37.842436 modeled fps), and 1-degree rotation in 3,378,341 cycles (37.000409 modeled fps). These are modeled whole-frame publication rates, not measured distinct input or displayed frame rates. The candidate preserves C53 throughput; its intended benefit is physical timing, which is not established until the full routed setup and hold reports are available.

Promotion gate: routed 125 MHz setup and hold must both close under the C50 constraints, and the source hashes must match the tested RTL. Until then this is evidence for an optimization attempt, not a replacement for C50.
