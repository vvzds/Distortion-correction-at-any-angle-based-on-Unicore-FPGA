# Feature-Key Candidate Build Report

## Result

The five hardware keys are integrated into the current quality-pipeline RTL.
All five focused ModelSim regressions passed, and PDS routed seed 1 and seed 2
with positive slow-corner setup slack and zero failing setup/hold endpoints.
This is a simulation and implementation result only: the key-enabled candidate
has not been tested on the board, so no 1080p30 or image-quality claim is made.

## Key behavior

| Key | Behavior | Power-on state |
|---|---|---|
| KEY0 | Toggle Brown radial/tangential terms; off zeros `k1`, `k2`, `p1`, `p2` | On |
| KEY1 | Toggle live affine/IMU transform; enabling captures a valid IMU reference pose | Off |
| KEY2 | Toggle adaptive Gamma | On |
| KEY3 | Cycle host, DN1, DN1+SH1, DN2+SH1, host | Host |
| KEY4 | Toggle OSD visibility | Hidden |

Inputs are active-low, synchronized and debounced for 20 ms at 125 MHz. The
host affine command controls KEY1 state; host quality commands return KEY3 to
host control; host OSD commands set KEY4 state. KEY1 leaves the video live.
Control changes use the existing frame/display boundaries and add no image
buffer or DDR traffic. Full wiring and behavior are described in
`KEY_FUNCTIONS_20261103.md`.

## PDS route comparison

Target: PG2L100H-6 FBG676, PDS 2022.2-SP6.1 build 138931.

| Seed | Slow setup WNS | Slow hold WHS | Setup failures | Hold failures | Decision |
|---|---:|---:|---:|---:|---|
| 1 | +0.081 ns | +0.140 ns | 0 | 0 | Recommended main image |
| 2 | +0.052 ns | +0.135 ns | 0 | 0 | Backup image |
| 7 | +0.006 ns | +0.123 ns | 0 | 0 | Passed, lower setup margin |
| 3 | -0.582 ns | +0.137 ns | 11 | 0 | Rejected |

Seed 1 and seed 2 both report `All Constraints Met`. Seed 1 has the largest
positive setup WNS among the three passing key-enabled routes and is selected
as the main candidate. Seed 3 is excluded from the deliverable bitstreams.

The seed 1 routed snapshot was compared byte-for-byte with the delivery
project: every file under `source/` and `ipcore/`, the board FDC and `build.tcl`
match. The saved PDS file also records generated run metadata and output paths;
the portable package omits those large rebuildable databases and retains the
complete RTL/IP inputs and the selected generated bitstreams.

Seed 1 PDS Device Utilization Summary, with percentages recalculated from the
reported used/available counts:

| Resource | Used / available | Utilization |
|---|---:|---:|
| LUT | 16,705 / 66,600 | 25.08% |
| FF | 24,500 / 133,200 | 18.39% |
| APM | 148 / 240 | 61.67% |
| DRM | 84.5 / 155 | 54.52% |
| Distributed RAM | 110 / 19,900 | 0.55% |
| IO | 144 / 300 | 48.00% |
| RCKB | 2 / 24 | 8.33% |
| SCANCHAIN | 0 / 1 | 0.00% |
| USCM | 7 / 32 | 21.88% |
| CCS | 1 / 1 | 100.00% |
| ADC | 0 / 1 | 0.00% |
| DDR_PHY | 7 / 24 | 29.17% |
| HSSTLP | 0 / 2 | 0.00% |
| GPLL | 3 / 6 | 50.00% |
| PPLL | 2 / 6 | 33.33% |
| DDRPHY_CPD | 1 / 12 | 8.33% |
| HCKB | 0 / 96 | 0.00% |
| IOCKB | 0 / 24 | 0.00% |
| MRCKB | 1 / 12 | 8.33% |
| PCIE | 0 / 1 | 0.00% |
| DDRPHY_IOCLK_DIV | 2 / 6 | 33.33% |
| ANALOG | 0 / 1 | 0.00% |
| TSERDES | 14 / 48 | 29.17% |
| KEYRAM | 0 / 1 | 0.00% |

These are total design counts from the seed 1 PDS device-map report, not the
incremental cost of the five keys. PDS reports `CCS` at 1/1 (100%); treat that
single-instance category as fully occupied for any future feature that may
need it. The saved PDS outputs do not include a separate post-route resource
inventory, so the table is the device-map utilization associated with the
routed candidate, not an independent post-route recount.

| Image | Bytes | SHA256 |
|---|---:|---|
| Seed 1 | 3,791,112 | `B1E48484A99C551B5E9D5BAD07ACCCEF715B268CD161E309FED0D3F18E19D5BD` |
| Seed 2 | 3,791,112 | `2CCF7B0C63D327F944A779C9DBE5C4066713A9CF3A7D3981628E3D9043C3E480` |
| Seed 7, current key-enabled route | 3,791,112 | `C663B4E92A5E942EC5A2EE9D6069E187529E91CF7447EB730ABC1DF4FDBED502` |

The inherited file `release/pango_bno085_quality_denoise_sharpen_osd_seed7_20261103.sbit`
is preserved unchanged. Its hash is `B9530A24C5551CE9BA03B670A3E2F0F093F5407A63A75BC728DA426084E3EA1C`
and its source manifest differs from the key-enabled route. It is a pre-key
historical image, not an alternate build of these five controls.

The package metadata issue noted by the original runs has been resolved in a
follow-up build. Both frame-buffer RAM IPs were regenerated for FBG676, and the
fresh seed 1 build completed without `Flow-4058`; its detailed verification is
in `PACKAGE_FBG676_VERIFICATION_20261103.md`. Older console logs under
`pds_evidence/` remain unchanged so they continue to describe the original
warning accurately.

## RTL simulation

ModelSim SE-64 10.7 ran the following current-source testbenches on 2026-11-03;
all reached normal finish with zero compile errors and warnings:

| Testbench | Main checks |
|---|---|
| `feature_key_control_tb` | Synchronization, debounce, one event per press, defaults, KEY1 host/key state, KEY3 cycle and KEY4 host/key priority |
| `display_denoise_tb` | Flat field, impulse, edge guard and bypass |
| `display_sharpen_tb` | Flat field, black guard, hard edge, bypass and data enable |
| `video_osd_tb` | Overlay, passthrough, blanking and frame-boundary visibility |
| `host_control_tb` | UART framing/CRC, parameter bounds, atomic update, status and IMU commands |

Each receipt, input manifest and raw simulation log is retained under
`reports/simulation/feature_keys_regression_20261103/`. These are focused
module tests, not full-system video throughput simulation or board acceptance.

## Board status and next acceptance

The older board-test report covers only the bitstream hash written in that
report. It does not cover these key changes. After programming the seed 1
image to SRAM, verify each key independently and together with its matching
host command. Confirm the video stays live during KEY1 changes; then measure
new corrected frames using the FPGA frame counter over a sustained interval.
Do not infer corrected frame rate from HDMI refresh rate or the PDS route.
