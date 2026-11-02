# Simulation Fix and Rebuild Report

## Acceptance rule

Functional behavior is the gate for this candidate. The feature-control,
host-control, image-map, frame-ownership, display-filter and OSD regressions
must pass before a routed image is packaged. Resource and timing improvements
are accepted only when they use the same RTL snapshot and still pass that
regression suite.

## Fixes

- KEY1 now gates only automatic BNO085 pose mapping. It no longer overwrites
  host `0x10` affine/projective matrices; disabling IMU mapping falls back to
  the latest host matrix.
- Brown and Gamma bypass controls are isolated in a testable configuration
  gate and preserve unrelated host parameters.
- The affine smoothing test now seeds the state established after a completed
  frame publication. The OSD test expects the configured glyph color.
- The angle sweep compares each fixed-point transform against the matching
  floating-point transform, including nonzero rotations.
- The ModelSim runner normalizes vector/result paths, requires an explicit
  testbench `PASS` and normal `$finish`, and rejects simulator errors.
- The full-frame RTL regression uses a checked-in 1920x1080 image fixture. The
  fixture is derived from a prior reference-rendered calibration image and is
  used only to check the RTL pixel/DDR path; it is not a raw-camera quality
  sample.

## Verification

The final suite is run with `tools/run_verification.py`; it covers 29 ModelSim
runs, including more than 380,000 randomized map coordinates, 72 angles in
5-degree steps, host/key priority, Gamma, IMU mapping, affine smoothing, frame
ownership, denoise/sharpen, OSD, sequential 0-to-45-degree frame changes, and
a complete 1920x1080 RGB565 comparison through the production correction RTL
and DDR brokers. Each archived run contains its input hashes, receipt and
simulator log under the suite-specific directory in `reports/simulation/`.

The five held-out raw-camera photographs and their `SESSION.json` are not
available at the configured `D:/FPGA/photo/session_203513` location. Therefore
offline real-image straightness/SFR analysis is marked as skipped in
`reports/verification_summary.json`; the checked-in RTL fixture is not used to
claim camera image quality. No board test was performed.

## Routed candidate

PDS 2022.2-SP6.1, PG2L100H-6 FBG676, seed 1, current repaired source snapshot.
PDS reports `All Constraints Met` with zero failing setup/hold endpoints.

| Metric | Result |
|---|---:|
| Slow-corner DDR PHY setup WNS | +0.206 ns |
| Slow-corner DDR PHY hold WHS | +0.141 ns |
| Fast-corner DDR PHY setup WNS | +2.909 ns |
| Fast-corner DDR PHY hold WHS | +0.100 ns |
| LUT | 16,020 / 66,600 (24.1%) |
| FF | 23,292 / 133,200 (17.5%) |
| APM | 104 / 240 (43.3%) |
| DRM | 84.5 / 155 (54.5%) |
| Distributed RAM | 110 / 19,900 (0.6%) |

The seed 1 image is a better timing candidate than the current-source seed 2
route (`+0.012 ns` slow DDR PHY setup WNS). The existing baseline artifacts,
seed bitstreams and original ZIP are retained unchanged. The new seed 1 image
is separately named `pango_bno085_quality_keys_resource_opt_simfix_seed1_20261103.sbit`;
its SHA256 is recorded in `SHA256SUMS.txt`.

This build includes the shared 32-bit multiplier/pipeline resource optimization
already present in the project baseline. This repair did not restructure the
pixel pipeline, so it introduces no intended image-quality or pixel-latency
change beyond the corrected feature gating and the fixes to the verification
harness. The inherited DDR IP FBG484 metadata versus project FBG676 warning
still needs resolution before production qualification. Routing and
simulation do not prove stable 1080p30 on the physical board.
