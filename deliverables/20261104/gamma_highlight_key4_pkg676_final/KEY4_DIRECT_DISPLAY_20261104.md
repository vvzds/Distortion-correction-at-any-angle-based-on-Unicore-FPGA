# KEY4 Calibration Display

KEY4 toggles a four-line HDMI overlay. It contains only the calibration terms
shown in the project requirement:

| Line | Values | Meaning |
|---|---|---|
| 1 | FX, FY | Focal lengths |
| 2 | CX, CY | Principal point |
| 3 | K1, K2 | Radial distortion |
| 4 | P1, P2 | Tangential distortion |

When the host connects, it sends the selected calibration JSON to the FPGA OSD
cache and leaves the overlay hidden. Press KEY4 to show or hide it. Loading a
different calibration while connected refreshes the four cached lines. No
affine matrix, zoom, denoise/sharpen level, Gamma mode, or debug status is drawn
inside the KEY4 overlay. OSD rows are sent without per-row acknowledgements; the
host reports that they were sent to the cache, not that a display readback
confirmed them.

The RTL also preloads the bundled OV5640 calibration as a startup default so
KEY4 can display readable values before the host has connected. Those startup
values are defaults, not readback of a different camera calibration.

## Verification

- `video_osd_tb` checks the four default rows, glyph output, video pass-through,
  blanking, and frame-boundary visibility.
- `check_host.py` checks that the host emits exactly these four calibration
  rows and no affine or quality fields.
- `host_control_tb` checks the OSD row protocol and range 0..3.
- Full PDS route: PG2L100H-6 FBG676, PDS 2022.2-SP6.1, seed 1; all constrained
  timing checks pass. Slow-corner setup WNS is `+0.378 ns` and hold WHS is
  `+0.138 ns` on `ddrphy_sysclk`.

The image is not yet board-tested. See `BOARD_TEST.md` before programming SRAM.
