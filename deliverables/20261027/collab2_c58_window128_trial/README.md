# C58 bounded-lookahead trial (2026-10-27)

Status: rejected after targeted simulation. No PDS run, bitstream, or board programming was performed. C50 seed7 remains the board-tested fallback.

C58 starts from C57. It limits the coordinate preparation lead from 256 to 128 pixels and computes the bounded producer-consumer distance from the low eight counter bits. The core RTL SHA256 is `6D77405472AED99E8D09AED31408B903D3AD83E2AD3789E0295214EF4C90E035`; the cache RTL is unchanged from C57 (SHA256 `ACF45ED28B1A37BE27C1AF3912B787F9BE37D7B6A9D78732092864D57DDEC20E`). The new distance is exact while the lead remains in `[0,128]`, including low-bit wraparound.

The full-frame identity and calibrated-parameter tests passed exact-pixel/protocol checks. Identity retained 44.330045 modeled corrected-frame publications/s. Calibrated parameters fell from C57's 37.491872 to C58's 36.938185. The 15-degree rotation test again timed out at 500 ms simulation time: 1,673,357/2,073,600 pixels output, 387,882 segment loads, and 60,826,482 data-stall cycles. C57 at the same timeout had 1,673,417 pixels, 387,900 loads, and 60,826,422 data-stall cycles. The 128-pixel window did not materially change the large-angle bottleneck. `evidence/` contains the raw results.

The remaining routine regression was intentionally stopped after this decisive failure; no 11/11 claim is made for C58. Without a throughput gain in the target case, a physical WNS run would not make this variant eligible for promotion.

The measurements point to inter-output-line source-segment reuse, not lookahead depth, as the next optimization target. A 15-degree scan across 1920 output pixels moves roughly 497 source rows before distortion; 256 cache tags cannot retain that entire working set for the next output line. A larger source-segment cache and output traversal/reorder scheme may help, but they require explicit capacity analysis, a widened bank-ID contract, complete regression, routed 125 MHz setup/hold, and board validation before replacing C50. This is a design direction, not a demonstrated performance result.
