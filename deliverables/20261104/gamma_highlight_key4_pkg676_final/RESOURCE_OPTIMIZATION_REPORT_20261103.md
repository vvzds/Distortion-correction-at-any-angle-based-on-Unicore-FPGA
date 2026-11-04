# Resource Optimization Report

## Result

The recommended image is `bitstreams/pango_bno085_quality_keys_resource_opt_seed2_20261103.sbit`.
It uses one II=1 registered 32x32 multiplier for the twelve control-rate
matrix products in `source/rtl/imu_projective_map.v`. Products are issued on
consecutive clocks and returned by a four-stage tag pipeline. The mapper and
all video-rate blocks keep their original arithmetic, widths, truncation, map
format, and frame timing. The shared unit is used only when the IMU pose or
base calibration changes.

The optimization was checked against the original fixed-point model with four
reference/pose cases. All eight published coefficients match exactly. The
change adds control-update latency while leaving the per-pixel path and DDR
traffic unchanged; the control update is not part of the 1080p pixel budget.

## Routed resource comparison

Target: PG2L100H-6 FBG676, PDS 2022.2-SP6.1 build 138931. The original values
are the routed function-key seed-1 report in
`FEATURE_KEYS_BUILD_REPORT_20261103.md`; optimized values are from the PDS
device-map reports for both optimized seeds.

| Resource | Original | Optimized | Change | Optimized utilization |
|---|---:|---:|---:|---:|
| LUT | 16,705 / 66,600 | 16,113 / 66,600 | -592 (-3.54%) | 24.19% |
| FF | 24,500 / 133,200 | 23,293 / 133,200 | -1,207 (-4.93%) | 17.49% |
| APM | 148 / 240 | 104 / 240 | -44 (-29.73%) | 43.33% |
| DRM | 84.5 / 155 | 84.5 / 155 | 0 | 54.52% |

The remaining device-map categories are unchanged for this RTL change. CCS
remains a single fully occupied device resource in the project.

## Timing

| Seed | Setup WNS, slow | Hold WHS, slow | Recovery WNS, slow | Report |
|---|---:|---:|---:|---|
| 1 | +0.119 ns | +0.139 ns | -0.496 ns | `pds_evidence/seed1_timing.rtr` |
| 2 | +0.266 ns | +0.142 ns | +1.373 ns | `pds_evidence/seed2_timing.rtr` |

Seed 2 reports `Design Summary : All Constraints Met`, zero setup failures,
zero hold failures, and zero recovery/removal failures. It is the recommended
image. Seed 1 is retained as a fallback bitstream, but its recovery result is
not promoted as the primary image.

The optimized seed-2 bitstream has SHA256
`6B36A24CD09FAB0DC248E8730EBB9DE2B5BE358714F2029501D513E3BDE1F9C3`.
The optimized seed-1 bitstream has SHA256
`36B67736DEA2B914A3DC4333045051ED88CF18D81E603260B061F007850CC858`.

## Verification

Passed checks include:

- Exact IMU projective-map coefficient comparison: 4/4 cases.
- Native map and video checks at 0, 45, 90 degrees, 90 degrees with zoom,
  angle transition, and the 430-cycle stress period.
- 72-angle resource/read-beat sweep and host protocol checks.
- ModelSim: host control, feature keys, denoise, sharpen, OSD, adaptive Gamma,
  frame ownership, and the exact IMU mapper.

The two native image checks that depend on `D:\FPGA\photo\session_203513`
could not run because that external photo directory is absent on this machine.
The quality plotting check was not run because matplotlib is not installed.
These are environment gaps, not RTL failures.

## Acceptance boundary

This package contains PDS-routed bitstreams and simulation evidence. No board
programming or live camera measurement was performed in this optimization
pass, so stable physical 1080p30 and image quality remain board-acceptance
items.
