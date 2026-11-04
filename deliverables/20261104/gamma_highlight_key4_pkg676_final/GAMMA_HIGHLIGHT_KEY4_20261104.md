# Strong-Light Gamma and KEY4 Candidate

## Gamma behavior

The existing adaptive Gamma path has two frame-wide modes: gamma 0.60 for a
dark scene and gamma 1.60 for a broadly bright scene. This update adds mode 3,
a highlight shoulder for scenes with a substantial near-white region but a
moderate overall mean. It reuses the existing per-channel RGB565 lookup path;
it adds no image buffer, DDR access, or pixel pipeline stage.

At each frame boundary the next mode is selected from the previous frame's
valid, pre-enhancement pixels. The approximate luma is `2*(R5+G6+B5)` and
out-of-image fill is excluded. A mean below 70 selects brightening; it remains
active below 90. A mean above 190 selects global darkening; it remains active
above 170. Otherwise, mode 3 is selected when at least 1/16 of valid pixels
have approximate luma at least 220; while mode 3 is active, 1/32 is the exit
threshold. This hysteresis and frame-boundary latch avoid mode chatter within a
frame. Statistics create one frame of adaptation delay.

Mode 3 leaves channel values at or below 75% unchanged. Above the knee, the
generated 5-bit and 6-bit LUTs apply `knee + span * z^1.6`; the exact maximum
input remains maximum output. This keeps midtones and most colors intact while
lowering near-white, non-clipped highlights. It does not reconstruct sensor
detail already clipped to RGB565 white. If the sensor has lost the texture,
exposure or analog-gain control is needed; digital Gamma cannot infer it.

The host's offline preview uses the same RGB565 curve and steady-frame
statistics, but it does not model the RTL's frame-to-frame hysteresis or the
display pipeline. Preview is a functional reference, not proof of physical
image quality.

## KEY4 overlay

The host automatically sends only these four calibration rows to the FPGA OSD
cache on connect and when a calibration file is reloaded:

1. `FX`, `FY`: focal lengths
2. `CX`, `CY`: principal point
3. `K1`, `K2`: radial distortion
4. `P1`, `P2`: tangential distortion

KEY4 shows or hides the overlay. It contains no affine, zoom, quality, or
diagnostic values. The OSD row command does not have a per-row ACK, so software
reports sent-to-cache, not HDMI readback confirmation.

## Quality command acknowledgement

The host sends the existing 0x32 denoise and 0x30 sharpen requests serially.
The new firmware answers with 0xB2/0xB0 and a 48-byte `QACK` payload, carrying
the original request sequence, command, accepted level, and result. A timeout,
bad CRC, busy transmitter, malformed ACK, or old firmware is reported as
unconfirmed; generic `valid_packets` counters are not used as a substitute.
An ACK confirms control-register acceptance only. It does not prove that the
pixel-domain filters or visible HDMI result passed a visual test.

## Resource and timing

The fixed video contract is 1920x1080. One frame has 2,073,600 pixels, which
fits in the 21-bit sample/highlight counters. The RGB565 luma sum is at most
250 per pixel, so the 29-bit accumulator covers the full frame. The counters
were narrowed to these derived widths; pixel arithmetic, thresholds, pipeline
latency, and DDR traffic were not changed.

PDS 2022.2-SP6.1, PG2L100H-6 FBG676, seed 1:

| Resource | Used | Available | Utilization |
|---|---:|---:|---:|
| LUT | 16,261 | 66,600 | 24.4% |
| FF | 23,322 | 133,200 | 17.5% |
| APM | 104 | 240 | 43.3% |
| DRM | 84.5 | 155 | 54.5% |
| Distributed RAM | 110 | 19,900 | 0.6% |
| IO | 144 | 300 | 48.0% |

Slow-corner setup WNS is `+0.378 ns`; hold WHS is `+0.138 ns` on
`ddrphy_sysclk`. PDS reports `All Constraints Met` with zero failing endpoints
on constrained clocks. Unconstrained top-level IO timing warnings remain in
the report and are not represented as constrained path closure.

The supplied KEY4 package's report listed 16,389 LUT and 24,829 FF. The current
total is 128 LUT and 1,507 FF lower, while APM, DRM, distributed RAM, and IO are
unchanged. This comparison includes the combined candidate updates, especially
reducing the OSD from eight rows to four; the full difference is not attributed
to the four-register Gamma counter-width reduction. No additional pixel-pipeline
or memory architecture rewrite was attempted because it could alter behavior
and the existing memory-heavy design already uses 54.5% DRM.

## Validation boundary

The 29-case software suite passed, followed by a focused UART RTL rerun covering
bad CRC and a quality request received during an in-flight reply. Gamma
simulation covers transitions, hysteresis, highlight roll-off, invalid-pixel
exclusion, and disable behavior. The route produced:

- Image: `bitstreams/pango_quality_gamma_highlight_key4_pkg676_seed1_20261104.sbit`
- SHA-256: `E0F79C42EEEC47798C46AC3E98C9C314BAD2B0EDF360B5FCB70BE6B69A18DB07`
- Timing report: `pds_evidence/gamma_highlight_key4_seed1_timing_20261104.rtr`

The board has not been programmed with this image. Strong-light effectiveness,
visible color naturalness, stable camera FPS, and OSD appearance still need
physical validation with the OV5640 and HDMI capture/display setup.
