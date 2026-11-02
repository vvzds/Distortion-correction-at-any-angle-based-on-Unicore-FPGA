# 2026-11-03 FPGA Quality Fusion Candidate

This delivery contains the complete project archive, the separate SRAM bitstream,
source/build manifests, PDS timing evidence, and the FPGA RTL comment audit.

The project combines the BNO085 correction base with RGB565 display denoising,
bounded sharpening, four-row calibration OSD, and host controls. The PDS seed7
build completed full place and route and reports all constrained setup/hold paths
passing. It has not been programmed on the board. Stable 1080p30, visible noise
reduction, sharpness, and OSD behavior still require physical validation.

The denoiser is a horizontal spatial filter and both quality controls reset to
bypass. It adds no frame buffer or DDR traffic. Begin board evaluation with
denoise level 1 or 2 and sharpening disabled, then enable sharpening separately.

The exact bitstream identity and resource/timing figures are in
`bitstream_manifest.json` and `PDS_BUILD_REPORT.md`. Verify SHA256 before SRAM
programming. Do not write this candidate to Flash before board acceptance.
