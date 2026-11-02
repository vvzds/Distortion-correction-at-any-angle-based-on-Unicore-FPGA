# Final Quality Fusion Build

The final commented source snapshot was built with PDS 2022.2-SP6.1 (build
138931), PG2L100H-6 FBG676, seed 7. PDS completed synthesis, device mapping,
placement, detailed routing, timing analysis, and bitstream generation. The
timing report states `Design Summary : All Constraints Met.` and the route log
states the design was placed and routed successfully.

Slow-corner setup WNS is +0.234 ns on `ddrphy_sysclk` and +1.214 ns on `pix_clk`.
The minimum slow-corner WHS is +0.138 ns; minimum fast-corner WHS is +0.100 ns.
There are no failing setup or hold endpoints among constrained paths. The PDS
logs also report unconstrained external ports; this timing result only covers
the paths and interfaces represented by the supplied constraints.

Mapped resources are 16,401 LUT, 24,358 FF, 84.5 DRM, and 148 APM. The bitstream
is `release/pango_bno085_quality_denoise_sharpen_osd_seed7_20261103.sbit`; its
SHA256 and source manifest identity are recorded in
`release/quality_fusion_seed7_manifest.json`.

The added denoiser/sharpener/OSD path is display-only and adds no frame-buffer
traffic. Denoise and sharpen both default to bypass after reset. Board download,
noise/sharpness viewing, and distinct 1080p30 frame-rate acceptance remain
pending; this candidate must not be described as board-validated.
