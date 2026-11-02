# FPGA RTL Comment Audit

Scope: all project-owned Verilog and include files under `source/rtl/` (42 files).
Vendor-generated DDR, PLL, and frame-buffer IP under `ipcore/` is preserved
byte-for-byte; vendor source is not rewritten. Existing inline comments were
retained, including the original encoding of legacy vendor-derived sources.

The audit found generic/blank vendor template headers and undocumented shared
include files. Functional module descriptions were added for camera reset and
SCCB control, HDMI receiver/transmitter setup, DDR read/write adapters and frame
buffers, raster timing, and the DDR arbitration wrapper. Shared include comments
now describe the default calibration register order, gamma table generation,
video/frame-slot contract, and production correction hook. The legacy-formatted
`sync_vg.v` header remains intact; its active-pixel/read-request timing is
documented immediately below the timescale directive.

The denoiser, sharpener, host protocol, OSD CDC, UART PHY, frame-store broker,
HDMI top, BNO bridge, projective map, arithmetic pipelines, and correction/tile
engines have algorithm, protocol, clock-domain, latency, or ownership notes near
their logic. Inline comments focus on non-obvious state transitions and data
alignment rather than restating each assignment. Generated lookup tables remain
generator-owned; DDR/PLL/frame-buffer IP remains vendor-owned.

Comments explain algorithms, RGB565 representation, frame-boundary controls,
bypass behavior, clock domains, latency, and DDR/frame ownership. Comments are
documentation only and do not claim subjective image quality or board acceptance.
