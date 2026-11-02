# Integrated Quality Candidate

## Integration

The project base is the complete BNO085 package supplied on 2026-11-02. Camera
capture, calibration, correction, IMU, DDR frame ownership, and corrected-frame
publication remain the existing baseline. Display processing is inserted after
the corrected RGB565 frame is read for HDMI:

`corrected RGB565 -> edge-aware denoise -> bounded sharpen -> four-row OSD -> HDMI`

The denoise and sharpen stages add four pixel clocks total at 74.25 MHz. They add
no frame buffers or DDR traffic and do not change the corrected-frame publication
counter. This source-level latency and bandwidth analysis does not establish routed
timing or board frame rate.

## Denoise and Sharpen

`source/rtl/display_denoise.v` uses a five-sample horizontal median independently
on RGB565 channels. It changes the center sample only when the immediate samples
on either side agree within a small channel-specific threshold. This suppresses
isolated bright/dark pixels and small local noise while rejecting neighborhoods
that cross a strong horizontal edge. Levels 1, 2, and 3 blend the center with the
median at 25%, 50%, and 100%; level 0 is exact bypass. Settings are synchronized
and latched at the next VS frame boundary.

This is a horizontal spatial filter, not a 2D or temporal denoiser. It targets
pixel-sized noise without frame history or extra DDR bandwidth. Vertical-only
noise and broad chroma blotches require captured-board evaluation before claiming
they are removed. Stronger settings can soften one-pixel vertical features; use
level 1 or 2 as the natural starting point.

`source/rtl/display_sharpen.v` is the existing five-tap horizontal sharpening
candidate, following denoise. It retains its edge/black-fill guards and bounded
correction. Level 0 disables it. The host GUI exposes separate selectors for
denoise and sharpening: `关闭`, `柔和`, `标准`, `增强`. Start board evaluation at
denoise 1 or 2 with sharpen 0, then choose sharpening after noise suppression is
accepted.

## OSD and UART

The four-row calibration OSD appears on HDMI and the capture-card USB preview.
The host monitor displays parameters from the host JSON and can measure captured
checker straightness/SFR; those values are not FPGA register readback. The old OSD
protocol used `0x30` for row text, conflicting with the sharpness command. This
candidate assigns `0x30` to sharpen, `0x32` to denoise, `0x34` to OSD row write,
and `0x35` to OSD visibility. Existing OSD bitstreams do not accept the merged
protocol.

## Verification State

- Host Python syntax and `tools/check_host.py`: passed.
- `tools/check_bno085.py`: passed offline.
- ModelSim `vlog` compilation of the denoise testbench, sharpen testbench, and
  merged host-control testbench: 0 errors and 0 warnings.
- ModelSim load/run: blocked by the local Tcl startup error
  `can't read "FileWatch(fileName)"`; no RTL testbench has produced a simulation
  PASS yet.
- PDS 2022.2-SP6.1 seed7 synthesis/place/route and bitstream generation: passed.
  `report_timing` says all constraints met. Slow-corner setup WNS is +0.234 ns
  on `ddrphy_sysclk`; `pix_clk` setup WNS is +1.214 ns. Slow-corner minimum WHS
  is +0.138 ns (`ddrphy_sysclk`); fast-corner minimum WHS is +0.100 ns. No setup
  or hold endpoints fail. Mapped resources: 16,401 LUT, 24,358 FF, 84.5 DRM,
  148 APM. This is timing closure for this routed seed, not a board frame-rate
  or image-quality result.
- Board display, subjective noise/sharpness evaluation, and 1080p30 acceptance:
  pending.

The combined seed7 bitstream is stored under `release/` with its SHA256 and PDS
receipt. Historical bitstreams are preserved for rollback. The combined image
still requires SRAM board programming and visual/frame-rate validation before it
can be treated as accepted hardware.

## Input Provenance

The full BNO085 build base is the user-provided
`pango_bno085_full_unsharpened_20261102(1).zip` (SHA256
`B16877C7128A844F203451F94CDB820FF693717D9793BA76A80FF5B462CABC3F`). The base
software release ZIP SHA256 is
`188BBFBB9A4F7E85B7E898A47F8D9A9A3F996F906038F332F266F93334132A44`; the four-row
OSD ZIP SHA256 is
`C3603A7BDE7D8506D92834A88738F86D1FC7C7EB2E9E2ABC7B9BB3D4B538BF86`. The user
provided `osd_monitor.py` is retained under `reports/input/` as received; SHA256
`96E298E35621C70E762F9A6BC67DC9DDD7AEB97C62991F33A06F919BFDF1FA53`.
