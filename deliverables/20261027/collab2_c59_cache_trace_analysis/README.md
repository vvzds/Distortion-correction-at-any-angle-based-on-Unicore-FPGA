# C59 mapped-key cache capacity analysis (2026-10-27)

The unmodified C50/C53/C57 `undistort_map.v` generated 2,073,600 valid mapped keys for the exact 15-degree calibrated test parameters. ModelSim reported `TRACE PASS pixels=2073600`. The full local trace has SHA256 `596C425EDCC1437599AD22DCE4DF62B510B47B37A10C9E5212D80276DAAAC5CE`; it is 20.7 MB and is regenerated with `map_trace_tb.v` rather than stored in Git. The source map RTL has SHA256 `89E31CC0CBB9D149523CE908DFB9104CE5A8FC5A6CB35762DCAC597E05475731`.

`analyze_cache_trace.js` replays all four bilinear source-segment keys per output pixel through the RTL's 32-set row/segment XOR hash. It uses ideal LRU and tests 8, 16, and 32 ways per set. `evidence/cache_scenarios.json` is the generated result.

| Tag capacity | Raster ideal misses/full frame | Alternating-line ideal misses/full frame |
| ---: | ---: | ---: |
| 256 (current) | 475,750 | 213,166 |
| 512 | 38,091 | 17,693 |
| 1024 | 13,242 | 13,242 |

The maximum distinct keys in one output scanline is 466. For the first 1,673,417 output pixels, the ideal 256-tag raster model predicts 388,049 misses, only 149 (0.038%) more than the C57 system simulation's 387,900 segment loads at timeout. This agreement strongly supports cache-capacity thrashing as the dominant large-angle limitation. A 512-tag cache reduces modeled full-frame misses by 12.5x in the existing raster order. Alternating scanline direction would require output reordering and is an architectural option, not current hardware behavior.

This is a cache miss model, not a DDR-cycle or frame-rate prediction. It omits pinning, pending fetches, bank-write contention, route timing, and display order. The 512-tag candidate must be implemented and run through exact-pixel/protocol regression, full 15-degree DDR simulation, 125 MHz routed setup/hold, and board validation before it can replace C50. C57 used 29.5 of 155 DRM units at device mapping, but this figure alone does not prove that an enlarged cache will route or meet WNS.

To reproduce in an ASCII-path scratch directory, compile `map_trace_tb.v` with `../collab2_c57_cache_wns_trial/rtl/undistort_map.v` and run ModelSim to produce `map_keys.hex`, then run `node analyze_cache_trace.js map_keys.hex cache_scenarios.json`. The testbench uses the same 15-degree Q16.16 parameters as the C57 full-system test. The raw output order remains the original raster order; the JavaScript model alone reverses odd scanlines for the comparison.
