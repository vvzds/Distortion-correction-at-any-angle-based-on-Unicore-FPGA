# Later SRAM board validation

Do not write Flash. Keep the original C50 seed7 SRAM image available as a
fallback. A power cycle clears the FPGA bitstream and runtime parameters.

1. Verify `C50_pure_capture_C63_frame_gate_seed7.sbit` has SHA256
   `069737CD5B58F2D583C424AA45C13B8AE108DE55C7FCD23264FA99933F4FD2B9`,
   then load that exact file to SRAM with PDS. Check that the camera and HDMI
   picture appear and DDR initializes.
2. Send the repository's measured calibration CSV with
   `uart_tool.py send-file --port COM11 --csv <real_parameters.csv>`.
   This package includes `parameters/real_parameters.csv`, copied from the
   earlier C22 seed7 board-trial reference.
   Confirm status reports valid parameters and a non-stuck correction engine.
3. Move a hand or calibration target continuously through the view for at
   least 30 seconds. In parallel, run
   `probe_c50.py --port COM11 --seconds 30 --csv four_stage_counts.csv`.
   Its status marker must be `D`; the four reported rates are camera VSYNC,
   complete raw frames, corrected publications, and actual HDMI slot changes.
4. Capture Hagibis at 1920x1080 MJPEG 30 fps, convert every received frame
   to 320x180 grayscale SHA256 with FFmpeg `framehash`, and analyze it with
   `deliverables/20261028/collab2_c50_camera_path_probe/analyze_framehash.py`.
   Retain the original framehash and CSV files. Compare only complete seconds
   in a sustained-motion interval, not the partial first/last seconds.

Acceptance requires at least 30 distinct corrected HDMI images/s during the
motion interval, with camera/raw/publication/display stage counts consistent
with that result and no source or DDR errors. A 30 fps capture setting or
correction publication rate alone is insufficient. Repeat with the measured
calibration parameters and a representative small-angle affine change before
promoting the bitstream. A later wide-angle target needs separate timing and
frame-rate validation.
