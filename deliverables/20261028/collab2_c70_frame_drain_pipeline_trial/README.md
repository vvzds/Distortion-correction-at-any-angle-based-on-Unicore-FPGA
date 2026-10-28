# C70 registered frame-drain trial (2026-10-28)

Status: isolated transposed-source read experiment, not a deployable camera-to-HDMI build. C50 seed7 remains the board-tested fallback. The current camera writer still stores row-major source frames, whereas this trial assumes a complete, separately published transposed RGB565 source frame in DDR. Do not program the timing-only bitstream.

C70 derives from C69 and changes one control dependency in `rtl/undistort_core.v`: the last `sample_dispatch` no longer drives the core `state` register combinationally. The registered `consumed_count` reaches 2,073,600, and the following RUN cycle enters DRAIN. This targets C69's routed worst setup path from `headq_rd[1]` through cache readiness and `sample_dispatch` to the `state` clock enable. All other C69 transposed-source mapping, cache, and bilinear behavior is preserved. This mode is selected at elaboration with `TRANSPOSE_SOURCE=1`; normal-source behavior is not regressed here.

The full-frame 90-degree ModelSim system test in `evidence/system/` passed pixel accuracy, DDR read/write protocol, output ordering, and frame lifecycle with the same 125 MHz shared-DDR behavioral model as C69. It published 2,073,600 pixels in 2,842,518 modeled cycles (43.975095 corrected-frame publications/s), with 10,143 source segment reads and 75,084 beats. All 129,600 sampled independent golden pixels were within one RGB-channel level; the writeback scoreboard checked all 2,073,600 pixel words. Reproduce from an ASCII-only copy using `vsim -batch -do "do run.do"` in `evidence/system/`.

`evidence/timing/` contains the full-top PDS scripts, 125 MHz constraints, and raw routed report archives for three independent place/route seeds. The same C70 core SHA256 `8599EB117FE4000777CB9E7DC9FDCE8A5CD802B253B5376B1FBA1C1BF9498CC6` was used for all three. The independent post-route `report_timing` results are:

| Rank | Seed | Setup WNS | Minimum hold WHS | Final verdict | Report ZIP SHA256 |
| --- | ---: | ---: | ---: | --- | --- |
| Best trial | 9 | +0.235 ns | +0.032 ns | All constraints met, zero failing endpoints | `8C7F6C8E4E998A13E8A97D5AA053AAF79125CFB7F433168C6B24DF1E498B378E` |
| Second trial | 8 | +0.186 ns | +0.024 ns | All constraints met, zero failing endpoints | `5935DE67EC7A09AE010397F80AF405BC324351DB1CAFAE6E05C502E122D79BC7` |
| Rejected | 7 | -0.262 ns | positive | One setup-failing endpoint (`sys_clk` to `clk_25M`) | `E39021E23B22431425F77B4A9E0C7F3A936217B725EBA1D598AD3A6313B493CF` |

Seed8's intermediate place/route summary reported three hold failures at -0.007 ns, while the later independent `report_timing` on the routed design reports +0.024 ns and zero failures. Both raw outputs are preserved in its ZIP; use the final report as the acceptance criterion, and retest this discrepancy before any board promotion. Seed9 is the preferred timing result. It maps to 112/240 APM, 29.5/155 DRM, 20,740/66,600 LUT and 25,670/133,200 FF. The full-top timing builds replace only the C63 core and cache with C70 files; the normal camera writer is unchanged and its output would be incorrect with C70. Routing success establishes only resource use and timing of the trial circuitry, not end-to-end 30 distinct camera/display frames/s. The DDR frame-buffer IP retains the existing FBG484-vs-FBG676 metadata warning. The repository's C50 seed7 project, bitstream, and board evidence are left untouched.

The required integration work is to produce the transposed source frame with verified slot ownership and padding, model concurrent capture/transpose/correction/display DDR traffic, and rerun complete simulation, route, and board tests. The 43.975095 figure excludes the transpose producer and cannot establish stable on-board 30 fps.
