# Candidate Validation 2026-11-04

## Outcome

- Full software verification suite: 29/29 cases passed, including mapping,
  pixel RTL/DDR path, IMU mapping, Gamma, denoise/sharpen, function keys, host
  software, and four-row OSD.
- After adding explicit bad-CRC and UART-busy cases, `host_control_tb` was run
  again and passed. Invalid or busy quality commands do not change levels or
  produce a success acknowledgement.
- Host checks passed for sequence-matched QACK handling, partial confirmation,
  malformed responses, the four calibration-only OSD rows, and the static
  strong-light preview.
- PDS 2022.2-SP6.1 completed PG2L100H-6 FBG676 seed-1 placement, routing, timing
  analysis, and bitstream generation. `Design Summary : All Constraints Met.`
- No physical board test was performed. This proves simulation and route
  status, not live camera quality or 1080p30 behavior.

## Timing and image

- Slow-corner setup WNS: `+0.378 ns` on `ddrphy_sysclk`.
- Slow-corner hold WHS: `+0.138 ns` on `ddrphy_sysclk`.
- Setup, hold, recovery, and removal reports show zero failing endpoints on
  constrained clocks.
- Generated SRAM image:
  `bitstreams/pango_quality_gamma_highlight_key4_pkg676_seed1_20261104.sbit`
- SHA-256: `E0F79C42EEEC47798C46AC3E98C9C314BAD2B0EDF360B5FCB70BE6B69A18DB07`

## Remaining checks

The highlight curve can compress near-white values that still exist in the
RGB565 input. It cannot recreate detail already clipped by the OV5640 sensor;
exposure, analog gain, and real-scene image quality require board testing.
The OSD protocol has no per-row acknowledgement, so host status means the rows
were sent to the cache, not read back from HDMI.
