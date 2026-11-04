# Board Acceptance: Gamma and Calibration OSD

Status: pending. The candidate has passed simulation and PDS routing, but has
not been programmed or visually checked on the physical board.

## Image to program

- File: `bitstreams/pango_quality_gamma_highlight_key4_pkg676_seed1_20261104.sbit`
- SHA-256: `E0F79C42EEEC47798C46AC3E98C9C314BAD2B0EDF360B5FCB70BE6B69A18DB07`
- Device: PG2L100H-6 FBG676

Verify the hash before loading. Use SRAM/JTAG; do not write SPI Flash. Confirm
video and DDR startup before continuing.

## Checks

1. Connect the matching host software and load the intended OV5640 calibration
   JSON. The host automatically sends the four calibration rows. Press KEY4 and
   verify that the HDMI overlay contains only FX/FY, CX/CY, K1/K2, and P1/P2;
   hide it again with KEY4.
2. In the host, apply denoise and sharpen settings one at a time. Confirm the
   host reports each accepted command, then separately inspect the HDMI image.
   The firmware ACK confirms register acceptance, not visual filter quality.
3. Toggle KEY2 Gamma and use a controlled scene with dark regions and a
   moderate near-white area. The host status reports Gamma mode 1, 2, or 3.
   Mode 3 should reduce non-clipped near-white values while leaving midtones
   unchanged. Compare identical fixed exposure/lighting captures. Do not use a
   sensor-clipped white region to judge recovered detail; none can be restored.
4. Toggle KEY0 Brown correction and cycle KEY3 quality presets. For KEY1, use a
   valid BNO085 pose, verify reference capture, and confirm video remains live.
5. Measure distinct frame-count changes for at least ten minutes with the
   selected features enabled and repeated key changes. Record bitstream hash,
   host version, calibration hash, lighting/exposure, command results, new-frame
   FPS, UART errors, and raw HDMI captures.

Keep the camera, exposure, lighting, and capture path fixed for before/after
image comparisons. PDS timing and module simulation do not establish real
1080p30, stable frame output, or visible Gamma quality.
