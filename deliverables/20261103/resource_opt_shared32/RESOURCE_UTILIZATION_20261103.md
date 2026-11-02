# Final Resource Utilization

## Build identity

- Project: `hdmi_ddr_ov5640_top`
- Device: PG2L100H-6 FBG676
- Tool: PDS 2022.2-SP6.1, build 138931
- Route seed: 1
- Bitstream: `bitstreams/pango_bno085_quality_keys_resource_opt_simfix_seed1_20261103.sbit`
- Bitstream SHA256: `3FF00AA537E48E8EDC1112E02788D72CF2694B0878343D91A7B119D31F9512B1`

The source passed the 29-run ModelSim suite before this route. The figures below
are from PDS device mapping and placement/routing reports, not estimates from
RTL source. The device-map logical totals and post-route physical packing table
are separate reports; their overlapping categories must not be added together.

## Main logic resources

Device-map counts, with percentages recalculated from the reported used and
available counts:

| Resource | Used | Available | Utilization |
|---|---:|---:|---:|
| LUT | 16,020 | 66,600 | 24.1% |
| Flip-flops | 23,292 | 133,200 | 17.5% |
| APM (DSP/MAC blocks) | 104 | 240 | 43.3% |
| DRM (dedicated RAM blocks) | 84.5 | 155 | 54.5% |
| Distributed RAM | 110 | 19,900 | 0.6% |
| IO | 144 | 300 | 48.0% |

## Post-route architecture resources

PDS placement/routing summary:

| Resource | Used | Available | Utilization |
|---|---:|---:|---:|
| APM | 104 | 240 | 44% |
| BKCL | 6 | 6 | 100% |
| CCS | 1 | 1 | 100% |
| CLMA | 4,921 | 11,675 | 43% |
| CLMA flip-flops | 16,960 | 93,400 | 19% |
| CLMA LUT | 11,478 | 46,700 | 25% |
| CLMA LUT-FF pairs | 5,732 | 46,700 | 13% |
| CLMS | 1,938 | 4,975 | 39% |
| CLMS flip-flops | 6,334 | 39,800 | 16% |
| CLMS LUT | 4,367 | 19,900 | 22% |
| CLMS LUT-FF pairs | 2,215 | 19,900 | 12% |
| Distributed RAM | 110 | 19,900 | 1% |
| DRM | 84.5 | 155 | 55% |
| HARD0 | 2,233 | 10,550 | 22% |
| IO | 144 | 300 | 48% |
| IOBD | 72 | 144 | 50% |
| IOBS | 72 | 156 | 47% |
| IOLHR | 143 | 300 | 48% |
| DDR_PHY | 7 | 24 | 30% |
| DDRPHY_CPD | 1 | 12 | 9% |
| DDRPHY_IOCLK_DIV | 2 | 6 | 34% |
| GPLL | 3 | 6 | 50% |
| PPLL | 2 | 6 | 34% |
| TSERDES | 14 | 48 | 30% |
| USCM | 7 | 32 | 22% |
| HCKB | 26 | 96 | 28% |
| MRCKB | 1 | 12 | 9% |
| RCKB | 3 | 24 | 13% |

PDS reports `BKCL` and `CCS` fully occupied. Keep this in mind if later changes
need those exact resource classes. The following reported categories use zero:
ADC, ANALOG, GSEB, HSSTLP, IOCKB, KEYRAM, MFG_TEST, PCIE, SCANCHAIN, SFB and
SPAD; the mux-test categories are also unused.

## Interpretation

The largest primary logic-memory use is DRM at 54.5%; APM is 43.3%, LUT is
24.1%, and flip-flops are 17.5%. These totals describe this complete design,
including camera interfaces, DDR, HDMI, BNO085, OSD, Gamma, denoise/sharpen and
the function keys. They are not the incremental cost of any one feature.

PDS reported `All Constraints Met` for this routed image. There was no board
test in this run, so resource closure does not establish real-board frame rate
or image behavior. The inherited DDR IP package-metadata warning is documented
in `SIMULATION_FIX_REPORT_20261103.md`.
