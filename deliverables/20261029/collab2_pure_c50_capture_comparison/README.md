# RAW8 pure capture versus C50 correction host (2026-10-29)

## Board evidence and acceptance boundary

| Build | Motion-window HDMI samples | Changed adjacent samples | Unique-image cadence |
|---|---:|---:|---:|
| AF961A pure RAW8 pass-through | 751 | 750 | 30/s in each of 24 complete seconds |
| C50 seed7 corrected output | 751 | 452 | 18.056/s over 25 s |

The AF961A result establishes a working 1080p30 camera-to-DDR-to-HDMI
pass-through path for the observed window. It does not establish 30 distinct
corrected frames/s. Source measurements are archived under
`deliverables/20261028/collab2_raw8_pure_30fps_baseline/` and
`deliverables/20261028/collab2_c50_camera_path_probe/`.

## Source comparison

- The 263 OV5640 register writes have identical values in the two builds.
- `raw8_to_rgb565.v`, `wr_buf.v`, `rd_buf.v`, and `sync_vg.v` differ only in
  C50's `video_contract.vh` include and default parameter expressions. Their
  pixel, line-buffer, and timing logic is otherwise identical. The C50 top
  passes explicit 1920x1080, RGB565, and DDR slot-width parameters to the
  relevant modules; the pure and C50 HDMI timing defaults evaluate equally.
- C50 changed the SCCB implementation from a divided-clock state machine to
  a 25 MHz clock-enable implementation. `reg_config.v` and `i2c_com.v` must be
  moved as a pair; the register data itself is unchanged.
- C50 adds UART, correction engine, protected raw source slots, corrected
  output slots, and DDR read/write arbitration. Its `frame_bank_ctrl.v` and
  `fram_buf.v` cannot be replaced byte-for-byte with the pure versions without
  removing correction. `wr_cmd_trans.v` includes a C50 valid-return guard
  that should be retained.

## Fusion trials

The pure-capture/C50-core trial copies six pure RTL files byte-for-byte:
`raw8_to_rgb565.v`, `wr_buf.v`, `rd_buf.v`, `sync_vg.v`, `reg_config.v`, and
`i2c_com.v`. It retains the C50 correction interfaces and adds a one-bit
pending-new-frame gate to `corr_top.v`, so an idle engine does not repeatedly
process the same camera frame. Its independent seed7 setup WNS was -0.117 ns,
so it was rejected. The lighter C63-core variant of the same pure/C50 fusion
passed its initial seed7 timing and 11 full-frame simulations; its source and
evidence are archived in `../collab2_pure_c50_frame_gated_candidate/`.

## Resource and timing reference

| Build | LUT | FF | APM | DRM | Routed DDR setup/hold |
|---|---:|---:|---:|---:|---|
| AF961A pure | 5,626 | 6,110 | 0 | 11.5 | +3.476/+0.133 ns |
| C50 seed7 | 22,118 | 25,996 | 112 | 29.5 | +0.211/+0.134 ns |

These are different functions: the extra C50 resources include the distortion
map, interpolation, buffering, and dynamic parameter path. The fusion's own
post-map resource and post-route timing results must be measured separately.
