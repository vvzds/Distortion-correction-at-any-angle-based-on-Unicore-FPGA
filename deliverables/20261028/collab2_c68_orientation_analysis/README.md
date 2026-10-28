# C68 source-layout decision analysis (2026-10-28)

This is an architecture-selection experiment, not a hardware build. It uses full-frame coordinates emitted by the C63 fixed-point mapping RTL for calibrated 15-degree and 90-degree rotations. `map_xy_tb.v` writes the clamped integer source coordinates. The resulting 15-degree and 90-degree traces have SHA256 `D711DB988697431C7344E850D0A274AEA265D6729AE3FAEBFA2B05C356812336` and `E7E2A50049AA27D096AC61BA417CB35449A7BE16BA1AC43B1C7F2EF4D494AC23`; traces are regenerated, not stored in Git.

The `analyze_orientation.js` model replays all 2,073,600 output pixels through the C63/C66 256-tag, 32-set, eight-way cache geometry. It counts ideal LRU misses and useful 256-bit source beats. Output is grouped in 16-line strips, with either 64-pixel microtiles or direct raster order.

| Mapping / source layout / output traversal | Ideal source reads | Useful source beats |
| --- | ---: | ---: |
| 15 degrees / normal / 64-pixel microtiles | 42,024 | 336,192 |
| 15 degrees / transposed / 64-pixel microtiles | 120,767 | 937,608 |
| 90 degrees / normal / 64-pixel microtiles | 82,171 | 657,368 |
| 90 degrees / transposed / 64-pixel microtiles | 10,580 | 79,012 |
| 90 degrees / normal / direct raster | 1,176,481 | 9,411,848 |
| 90 degrees / transposed / direct raster | 9,123 | 69,060 |

Normal source layout is preferable at small angles. A transposed source frame is strongly preferable near 90 degrees and permits direct raster output, avoiding the C66 strip-reorder memory. A transposed row is 1,080 RGB565 pixels, padded to 1,088 pixels for 256-bit alignment. The 1,920-row frame occupies 4,177,920 bytes, below the 4,194,304-byte source-slot limit. Edge segments use four rather than eight 256-bit beats. This is a proposed storage layout; the current camera writer does not produce it.

`analyze_blocked.js` explores one source layout for multiple angles. A 16x8-pixel, 256-byte block gives 21,573 ideal misses at 15 degrees and 17,682 at 90 degrees with 64-pixel output microtiles. Since 1,920 and 1,080 are divisible by 16 and 8 respectively, this layout needs no padding and occupies 4,147,200 bytes. This may avoid maintaining both normal and transposed source copies, but has no RTL or end-to-end frame-rate proof. The blocked model uses a linear block-index set hash, not the row/segment hash, so compare its counts as architectural estimates only.

The full C66 90-degree regression was rerun with its DDR model's 64-cycle first-return wait changed to zero while retaining all other settings. `rotate90_wait0_result.txt` records exact protocol pass, maximum one-channel-level pixel error, and publication at 16.393032 modeled fps. Thus eliminating first-return latency alone cannot meet 30 fps on C66's normal source layout.

Reproduce the coordinate traces in an ASCII-only scratch directory with `vlog undistort_map.v map_xy_tb.v`, `vopt work.map_xy_tb +acc -o xy_opt`, then run `vsim work.xy_opt +ROT90=0` and `+ROT90=1`. Use the C59 `undistort_map.v`. Run `node analyze_orientation.js map_xy_90.hex rotate90.json [64|1920]` and `node analyze_blocked.js map_xy_90.hex blocked90.json`; repeat for 15 degrees. The trace models omit tag pinning, DDR arbitration, transpose production, physical timing, and board effects. They are not measured camera-input or HDMI-display FPS.
