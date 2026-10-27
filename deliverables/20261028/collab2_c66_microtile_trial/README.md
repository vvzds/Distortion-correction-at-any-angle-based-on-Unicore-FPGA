# C66 64-pixel microtile integration trial (2026-10-28)

Status: **rejected for real-time promotion**. This isolated C63-derived experiment passes selected full-frame simulations but does not meet the 30 fps publication target at 15 or 90 degrees. No C66 PDS route, bitstream, or board validation was performed. C50 seed7 remains the board-tested fallback; C63 remains the timing-closed small-angle candidate.

C66 adds two 16-line RGB565 output banks and traverses each strip in 64-pixel horizontal tiles, row-major within each tile. The reorder block restores raster output before the existing `rect_wr_if` and DDR writer. A 32-entry FIFO decouples bilinear output from strip-buffer writes, and sampling stops with 24 pixels of headroom when the strip buffer applies backpressure. Identity mode keeps C63's original direct path. The altered core SHA256 is `D9E4BFBEC7F30AB61BF2A484A66A6E8A2B5E2F1C8821E7C9CE8195D71E5E889E`; reorder RTL SHA256 is `688320E874EDD20CE1C474371BA28CE96666CBF264A34DB9A8CAD474EE8B4EB5`.

The isolated 125 MHz shared-DDR model passed full 1920x1080 identity (exact pixels), calibrated parameters, 15-degree and 90-degree rotations, and fractional clamp, with protocol and writeback checks. Calibrated and rotated checks had maximum one RGB-channel level of pixel error. Corrected-frame publication results:

| Case | C66 modeled fps | Source segment loads | Result |
| --- | ---: | ---: | --- |
| Identity | 44.330045 | 0 | PASS |
| Calibrated | 29.340540 | 16,700 | PASS, below 30 fps |
| 15 degrees | 13.955019 | 42,024 | PASS, below 30 fps |
| 90 degrees | 6.877998 | 82,171 | PASS, below 30 fps |

The earlier pure column-major C65 variant also passed calibrated pixels but published only 11.572118 modeled fps, with 3,084,344 preparation-stall cycles. C66's microtiles reduced those stalls to 7,518 cycles, but source-data waits still dominate: 6,230,814 cycles at 15 degrees and 13,269,741 at 90 degrees. Actual segment loads exactly match the idealized LRU counts for 64-pixel tiles in `../collab2_c66_microtile_analysis/`. Those model counts are useful for choosing traversal but cannot predict DDR latency by themselves.

`rtl/` and `evidence/system/` contain the tested files, selected raw results, and a ModelSim regression script. Reproduce from an ASCII-only copy of this trial directory by running `vsim -batch -do "do run.do"` in `evidence/system/`. The original isolated simulation tree is `D:/FPGA PDS/yx/C66_microtile_integrate_20261028/`.

C64 proved the two-bank reorder block alone can route at 125 MHz, but C66 has no integrated route. Larger on-chip strips would reduce source misses but consume DRM rapidly; 16-line double buffering already uses 32 DRM before the C63 cache. A credible arbitrary-angle design needs fewer DDR source transactions or a different source-storage/writeback schedule, followed by complete frame-rate, resource, timing, and board proof. The numbers above are corrected-frame publication in a behavioral DDR model, not distinct camera-input or HDMI-display frame rates.
