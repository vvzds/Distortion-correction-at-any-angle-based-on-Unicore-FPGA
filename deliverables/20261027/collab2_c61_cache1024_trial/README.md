# C61 1024-tag cache trial (2026-10-27)

Status: rejected for promotion. This isolated candidate has no completed route, final timing report, bitstream, or board validation. C50 seed7 remains the board-tested fallback.

C61 doubles C60's cache to 1024 tags, retains eight ways per set, and expands the row/segment hash to 128 sets. Core bank IDs and queues are 10 bits. Changed RTL SHA256: `undistort_core.v` `3EF48275B6FB1B55796DE72494286EE575FE3B742ACE38C95857B70FA4423FEC`; `undistort_cache_ab.v` `0EBD006881BC06779FF26C61D8346F9682FD0D4CC2B928F3D00AE78A5D981BE0`. The map and bilinear modules are byte-identical to C57.

All 11 standard 1920x1080 system scenarios passed exact-pixel/protocol checks. Targeted angle results under the existing 125 MHz DDR model:

| Rotation | Full-frame result | Corrected-frame publication model | Segment loads |
| ---: | --- | ---: | ---: |
| 15 degrees | PASS, 2,073,600 pixels | 30.383065/s | 13,255 |
| 30 degrees | PASS, 2,073,600 pixels | 21.603797/s | 21,099 |
| 45 degrees | PASS, 2,073,600 pixels | 4.299239/s | 172,985 |
| 90 degrees | TIMEOUT at 500 ms, 158,148 pixels | Not a complete-frame measurement | 46,713 at timeout |

The calibrated unrotated case published at 38.465847 modeled frames/s; identity at 44.330045. The 15-degree result is only 0.383 fps above 30 in this model. These publication counts are not independent camera-input or HDMI-display FPS. The 90-degree timeout diagnostic recorded 62,341,691 data-stall cycles. `evidence/system/` holds the raw result files and the extended testbench. The 30/45-degree parameters rotate about the calibrated principal point; the 15/90-degree parameters match the original system testbench.

Seed7 PDS used the same 125 MHz constraint file as C50/C53. Device mapping succeeded, using 43,643/66,600 LUTs (66%) and 73.5/155 DRM units (48%). Placement showed positive preliminary slack, but detailed routing was manually stopped after iteration 8 with 59,474 unrouted nets; each late iteration was taking minutes. The PDS process was still active when stopped, so this is an operator decision, not an independent tool crash. `evidence/timing/c61_seed7_stopped_logs.zip` contains the original logs (SHA256 `C689BC7A4115FB0FA4E531450E855CDE59B9ED0F50CE86491CBE59F4FD7BFD42`). No routed setup/hold WNS exists. Positive placement slack is not a timing-closure result.

The 15-degree performance gain is real in simulation, but 30/45/90-degree results and physical cost reject this as a general arbitrary-angle real-time implementation. It must not replace C50. The next optimization direction is source-local tiled processing with ordered output writeback; the C59 trace study quantifies why a larger tag table alone is insufficient.
