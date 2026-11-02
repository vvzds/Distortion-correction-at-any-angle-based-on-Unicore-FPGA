# Pango Quality Pipeline with Board Function Keys

This candidate combines the OV5640 correction pipeline, BNO085 affine input,
adaptive Gamma, denoise/sharpen presets, HDMI OSD, and five board-key controls.
The target is PG2L100H-6 FBG676 with PDS 2022.2-SP6.1. Start with this README;
`README_BASELINE_20261031.md` is preserved historical package context and does
not describe the current candidate by itself.

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
Its current-source seed 1 bitstream is
`bitstreams/pango_bno085_quality_keys_resource_opt_simfix_seed1_20261103.sbit`
(SHA256 `3FF00AA537E48E8EDC1112E02788D72CF2694B0878343D91A7B119D31F9512B1`).
It passed 29 archived ModelSim runs and routes with +0.206 ns slow-corner DDR
PHY setup WNS and zero setup/hold failing endpoints. The existing seed images
and ZIP remain preserved. Real-camera image-quality analysis and board testing
are still pending.

The repaired full-project archive is
`pango_quality_function_keys_simfix_full_20261103.zip`; verify it with the
adjacent `.zip.sha256` file. `SHA256SUMS.txt` covers project and evidence files,
excluding generated build directories and ZIP containers.

## Known build caveat

PDS reported `All Constraints Met` for the selected routes, but also warned
that the read/write frame-buffer IP metadata names package FBG484 while the
project target is FBG676. Resolve this IP metadata mismatch and repeat the PDS
build before treating the candidate as production-qualified.
