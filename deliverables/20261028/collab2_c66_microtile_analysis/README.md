# Microtile cache-trace analysis (2026-10-28)

`analyze_microtile.js` replays the original full-frame mapped-key traces through the C63/C66 256-tag, 32-set, eight-way row/segment hash. It compares 16- and 32-line strips and horizontal microtile widths from one pixel to a full line. The 15-degree and 90-degree trace SHA256 values are `596C425EDCC1437599AD22DCE4DF62B510B47B37A10C9E5212D80276DAAAC5CE` and `005F3DCBDA1AE559DAE08A9372B54273E8409878EED822BF1A39A2F443F30733` respectively. Traces are regenerated using C59's `map_trace_tb.v`, not stored here.

| Traversal | 15-degree ideal LRU misses | 90-degree ideal LRU misses |
| --- | ---: | ---: |
| Raster (1920-pixel tile), 16-line strip | 475,750 | 1,176,481 |
| 64-pixel microtile, 16-line strip | 42,024 | 82,171 |
| 64-pixel microtile, 32-line strip | 27,463 | 45,408 |

C66's measured behavioral-model segment loads exactly equal the 16-line, 64-pixel counts for both angles. The 16-line microtile improved cache locality, but whole-frame publication was only 13.955019 and 6.877998 frames/s at 15 and 90 degrees. The 32-line counts are predictions only; they have no full-system DDR, route, or board result. Wider strips increase the output-buffer cost: a double 32-line RGB565 buffer holds 245,760 bytes, versus 122,880 bytes for 16 lines.

Reproduce with `node analyze_microtile.js map_keys.hex result.json 16` or change the final argument to `32`. Outputs are `rotate15.json`, `rotate90.json`, `rotate15_h32.json`, and `rotate90_h32.json`. This LRU model omits protected entries, pending fetches, DDR scheduling, writeback contention, and route timing; it is a traversal-selection tool, not a frame-rate estimate.
