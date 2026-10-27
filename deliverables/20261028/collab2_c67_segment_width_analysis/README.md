# C67 source-read transaction analysis (2026-10-28)

Status: analytical rejection of wider source segments and unconditional paired prefetch. No RTL or board build was changed. These models use the same full-frame 15-degree and 90-degree mapped-key traces as C59/C66, 16-line strips, 64-pixel horizontal microtiles, 256 baseline tags, eight ways per set, and the RTL row/segment hash.

| Scheme | Cache bytes | 15-degree read commands | 15-degree 256-bit beats | 90-degree read commands | 90-degree 256-bit beats |
| --- | ---: | ---: | ---: | ---: | ---: |
| 128-pixel segments, 256 tags | 65,536 | 42,024 | 336,192 | 82,171 | 657,368 |
| 256-pixel segments, 256 tags | 131,072 | 35,371 | 565,936 | 77,809 | 1,244,944 |
| 512-pixel segments, 128 tags | 131,072 | 32,034 | 1,025,088 | 75,633 | 2,420,256 |
| 128-pixel tags, unconditional paired fill | 65,536 | 35,371 | 562,864 | 77,809 | 1,244,944 |

Wider reads cut too few commands and substantially increase payload, especially at 90 degrees. The paired-fill model retains separate 128-pixel cache tags but fetches an absent aligned neighbor; it has the same problem. These are idealized LRU results, not measured bus transactions. The 512-pixel model counts a full 32-beat transfer at the right image edge, so its beat count is conservative if a partial-burst implementation were possible.

At 125 MHz, 30 corrected frames/s allow 4,166,667 cycles per frame. C66's 90-degree case requires 82,171 source reads; the behavioral DDR model imposes 64 cycles of first-return wait per serialized read, totaling 5,258,944 serial wait cycles before transfer and arbitration cost. Paired fetch still needs 77,809 commands, or 4,979,776 wait cycles. Thus neither design can reach 30 fps under the current one-outstanding-read contract, even if pixel work overlaps every wait. At 15 degrees, 42,024 commands account for 2,689,536 serial wait cycles; this leaves only 1,477,131 cycles for transfer, arbitration, and any pixel work that cannot overlap reads. C66 actually takes 8,957,351 publication cycles, so the present implementation is far from this limit.

Increasing strip height can reduce misses, but double-buffering 64 output lines at RGB565 consumes an estimated 128 DRM blocks. The C63 full top already maps to 29.5/155 DRM, so 128 additional blocks exceed device capacity before routing. A viable next architecture must overlap multiple source reads, avoid full per-segment first-return latency, or move strip reordering into external DDR with an addressable write path; all options require new full-system bandwidth and timing proof. The current C63 route remains the best timing-closed small-angle experiment, while C50 remains the board-tested fallback.

Reproduce with `node analyze_segment_width.js map_keys.hex result.json` and `node analyze_pair_fetch.js map_keys.hex result.json`. The four JSON files store the 15-degree and 90-degree outputs. The source traces have SHA256 `596C425EDCC1437599AD22DCE4DF62B510B47B37A10C9E5212D80276DAAAC5CE` and `005F3DCBDA1AE559DAE08A9372B54273E8409878EED822BF1A39A2F443F30733` and are regenerated using C59's `map_trace_tb.v`.
