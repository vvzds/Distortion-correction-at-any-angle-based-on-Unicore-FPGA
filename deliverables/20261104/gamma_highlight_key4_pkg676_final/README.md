# Pango Quality Pipeline with Board Function Keys

This candidate combines the OV5640 correction pipeline, BNO085 affine input,
adaptive Gamma, denoise/sharpen presets, HDMI OSD, and five board-key controls.
The target is PG2L100H-6 FBG676 with PDS 2022.2-SP6.1. Start with this README;
`README_BASELINE_20261031.md` is preserved historical package context and does
not describe the current candidate by itself.

## Current Candidate 2026-11-04

The current deliverable adds frame-adaptive strong-light highlight compression,
sequence-matched quality-command acknowledgements, and a four-row calibration
OSD. The host sends only `FX/FY`, `CX/CY`, `K1/K2`, and `P1/P2` when connected;
KEY4 controls whether those values appear on HDMI. See
`GAMMA_HIGHLIGHT_KEY4_20261104.md` for behavior, limits, test results, resources,
and the board-test boundary.

Recommended SRAM image:
`bitstreams/pango_quality_gamma_highlight_key4_pkg676_seed1_20261104.sbit`
(SHA-256 `E0F79C42EEEC47798C46AC3E98C9C314BAD2B0EDF360B5FCB70BE6B69A18DB07`).
The fresh seed-1 route reports `All Constraints Met`, slow-corner setup WNS
`+0.378 ns`, and hold WHS `+0.138 ns`. The 29-case software suite passed; the
updated busy/bad-CRC UART regression was also rerun and passed. This image has
not been programmed or visually tested on the physical board.

## Function keys

All five keys are active low, synchronized and debounced for 20 ms on the
125 MHz control clock. Reset remains dedicated to reset. The key pins are
KEY0=C22, KEY1=C23, KEY2=B22, KEY3=A22, KEY4=B20, all LVCMOS33 with pull-ups.

| Key | Function | Startup state |
|---|---|---|
| KEY0 | Toggle Brown radial/tangential correction terms (`k1`, `k2`, `p1`, `p2`) | Enabled |
| KEY1 | Toggle live BNO085 pose mapping; enabling captures the current valid IMU pose as reference | Disabled |
| KEY2 | Toggle adaptive Gamma | Enabled |
| KEY3 | Cycle host control, DN1, DN1+SH1, DN2+SH1, then host control | Host control |
| KEY4 | Toggle HDMI OSD visibility | Hidden |

The camera image stays live when KEY1 is used; it does not freeze the frame.
KEY1 and host `0x26` control only automatic IMU pose mapping. Host `0x10`
affine/projective matrices continue to work when KEY1 is off, and disabling
IMU mapping falls back to the latest host matrix. Host denoise/sharpen commands
return KEY3 to host-controlled settings, and host OSD visibility commands set
KEY4's state. State changes are synchronized to the video frame boundary where
required. The controls add no frame buffer or DDR transaction.

See `KEY_FUNCTIONS_20261103.md` for the detailed behavior and host interaction.

## Build and validation

Open `pango_undistort.pds` in PDS. The project includes the RTL, IP, PDS
constraints and build script. The feature-key regression evidence is under
`reports/simulation/feature_keys_regression_20261103/`. The selected PDS
bitstreams and route evidence are in `release/` and `reports/pds/`.

Seed 1 is the recommended first board-test image; seed 2 is the backup. Their
SHA256 values and timing results are recorded in
`FEATURE_KEYS_BUILD_REPORT_20261103.md`. Seed 3 failed setup timing and is not
included as a release image. A pre-key seed 7 file is retained separately for
historical comparison; it does not contain the new key controls.

The current key-enabled candidate has not been board tested. PDS timing closure
and module simulation do not prove stable 1080p30 or image-quality behavior on
the board. The prior baseline board report is retained as
`BOARD_TEST_BASELINE_20261029.md`; its results apply only to its recorded
bitstream hash, not to the current key-enabled build. See `BOARD_TEST.md` for
the pending board acceptance procedure.

The repaired candidate is documented in `SIMULATION_FIX_REPORT_20261103.md`.
Full device-map and post-route resource details are in
`RESOURCE_UTILIZATION_20261103.md`.
The latest seed 1 image, rebuilt after the RAM IP metadata was regenerated for
FBG676, is
`bitstreams/pango_bno085_quality_keys_resource_opt_pkg676_seed1_20261103.sbit`
(SHA256 `383DAA2D21270EDA53D94D79F05F464FEB8BAE2A4710288CD600F535355C55D0`).
It passed the full PDS route with +0.206 ns slow-corner DDR PHY setup WNS and
zero setup/hold failing endpoints. The earlier
`pango_bno085_quality_keys_resource_opt_simfix_seed1_20261103.sbit` remains
preserved as a pre-IP-regeneration comparison image. The candidate passed 29
archived ModelSim runs; real-camera image-quality analysis and board testing
are still pending.

The updated full-project archive is
`pango_quality_function_keys_pkg676_full_20261103.zip`; verify it with the
adjacent `.zip.sha256` file. The earlier
`pango_quality_function_keys_simfix_full_20261103.zip` remains a pre-FBG676-fix
archive. `SHA256SUMS.txt` covers project and evidence files, excluding generated
build directories, Python bytecode and ZIP containers.

## Package metadata follow-up

The read/write frame-buffer RAM IPs have been regenerated for PG2L100H-6
FBG676 with PDS IP Generator 2022.2-SP6.1. A fresh seed 1 full PDS build
completed with zero `Flow-4058` package warnings, `All Constraints Met`,
slow-corner setup WNS `+0.206 ns`, and hold WHS `+0.141 ns`. The new image is
`bitstreams/pango_bno085_quality_keys_resource_opt_pkg676_seed1_20261103.sbit`;
the verification record and raw timing report are in
`PACKAGE_FBG676_VERIFICATION_20261103.md` and `pds_evidence/`.

Earlier PDS logs are retained unchanged as historical records and still show
the original warning. The updated full-project archive contains the new FBG676
seed 1 image; this routed candidate has not been board-tested.
