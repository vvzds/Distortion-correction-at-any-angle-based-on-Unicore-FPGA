# FBG676 RAM IP Metadata Verification

## Result

The frame-buffer RAM IP package mismatch is corrected in the project source.
Both `rd_fram_buf` and `wr_fram_buf` now identify `PG2L100H-6 FBG676`, matching
the project target. The previous seed 1 bitstream and historical PDS evidence
remain preserved; the new image is separately named and is not board-tested.

## IP generation

The two IPs were copied to an isolated ASCII-only temporary path and regenerated
with the installed PDS IP Generator 2022.2-SP6.1 build 138931 using:

```text
ip_generate.exe -i <instance>.idf -family Logos2 -device PG2L100H -pack FBG676 -speed -6
```

Both generator runs and their embedded synthesis completed with zero errors and
zero warnings. Each IP retained all 26 parameters and 9 pins. The configured
RAM modes and widths are unchanged: `rd_fram_buf` remains 18K, 256-bit write
and 32-bit read; `wr_fram_buf` remains 36K, 32-bit write and 256-bit read.
The wrapper and synthesized RAM RTL hashes are byte-identical to the previous
source, confirming this was a package metadata correction with no logic change.

## Full PDS rebuild

A clean project copy ran compile, synthesis, device mapping, seed 1 placement and
routing, timing analysis, and bitstream generation with PDS 2022.2-SP6.1 build
138931. The process returned 0, routed successfully, and the fresh console
contains zero `Flow-4058` warnings. The timing report says `All Constraints
Met`:

| Check | Result |
|---|---:|
| Slow-corner setup WNS, `ddrphy_sysclk` at 125 MHz | +0.206 ns |
| Slow-corner hold WHS, `ddrphy_sysclk` at 125 MHz | +0.141 ns |
| Setup failing endpoints | 0 |
| Hold failing endpoints | 0 |

Device-map resources match the previous seed 1 source snapshot:

| Resource | Used / available | Utilization |
|---|---:|---:|
| LUT | 16,020 / 66,600 | 24.1% |
| FF | 23,292 / 133,200 | 17.5% |
| APM | 104 / 240 | 43.3% |
| DRM | 84.5 / 155 | 54.5% |
| Distributed RAM | 110 / 19,900 | 0.6% |

The new bitstream is
`bitstreams/pango_bno085_quality_keys_resource_opt_pkg676_seed1_20261103.sbit`,
3,791,112 bytes, SHA256
`383DAA2D21270EDA53D94D79F05F464FEB8BAE2A4710288CD600F535355C55D0`.
Its byte size matches the previous seed 1 image, but its hash differs; keep the
two files distinct until the new image is tested on the board.

## Evidence and limits

`pds_evidence/seed1_pkg676_ip_regen_console_20261103.log` and
`pds_evidence/seed1_pkg676_ip_regen_timing_20261103.rtr` preserve the fresh
full-build output. The two `ip_generate_*` logs and
`seed1_pkg676_source_hashes_20261103.json` bind the generator results to the
source. Earlier PDS logs are retained unchanged and describe builds made before
this correction.

The RTL did not change during IP regeneration. The full software/RTL regression
was rerun against this FBG676 source snapshot on 2026-11-03 and passed all 29
simulation runs. Its per-run receipts and logs are under
`reports/simulation/1793663314050972800/`; the summary is
`reports/verification_summary.json`. Real-camera image-quality analysis was
skipped because the held-out photo dataset was unavailable. The fresh PDS run
and simulation validate implementation, timing and modeled behavior only; they
do not establish board behavior or stable 1080p30. The new bitstream still
needs board validation before promotion.
