# Resource Snapshot 2026-11-04

Build: PG2L100H-6 FBG676, PDS 2022.2-SP6.1, seed 1, after the Gamma/KEY4
candidate changes. The data below comes from PDS device mapping and the timing
report, not an RTL estimate.

| Resource | Used | Available | Utilization |
|---|---:|---:|---:|
| LUT | 16,261 | 66,600 | 24.4% |
| Flip-flops | 23,322 | 133,200 | 17.5% |
| APM | 104 | 240 | 43.3% |
| DRM | 84.5 | 155 | 54.5% |
| Distributed RAM | 110 | 19,900 | 0.6% |
| IO | 144 | 300 | 48.0% |

Compared with the resource snapshot in `KEY4_DIRECT_DISPLAY_20261104.md` from
the supplied package, LUT use changes from 16,389 to 16,261 (-128) and FF use
from 24,829 to 23,322 (-1,507). APM, DRM, distributed RAM and IO totals are
unchanged. The OSD row count was cut from eight to four in this candidate, so
that change is a major contributor to the FF difference. Gamma's 22/22/31-bit
statistics were narrowed to 21/21/29 bits using the fixed 1080p sample bound;
this saves four declared counter bits. The aggregate reports do not isolate
each source change, so no larger per-feature saving is claimed.

No frame-buffer, DDR, or pixel-pipeline retiming change was made. The project
uses 54.5% of dedicated RAM, so a more aggressive storage rewrite was not
included without a proven behavior-preserving test and fresh full route.

Timing report: `pds_evidence/gamma_highlight_key4_seed1_timing_20261104.rtr`.
PDS summary: `Design Summary : All Constraints Met.` Slow-corner setup WNS is
`+0.378 ns`; hold WHS is `+0.138 ns` on `ddrphy_sysclk`. There are zero failing
endpoints on constrained clocks. Top-level IO ports reported as unconstrained
remain outside that timing-closure statement.

The routed image is not board-tested. See `BOARD_TEST.md` and
`GAMMA_HIGHLIGHT_KEY4_20261104.md` for acceptance limits.
