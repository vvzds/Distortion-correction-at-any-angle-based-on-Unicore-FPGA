# C63 seed7 initial board-test SOP

## Before programming

1. Confirm the board is PG2L100H FBG676 and that the USB-UART and HDMI/capture wiring match the C50 setup.
2. Keep the C50 seed7 bitstream and its original package available. The C50 board-tested bitstream SHA256 is `FF98EB4F5F8C0B47DB29F7FE318400441EF64585A500D783C63360799A830565`.
3. Verify `hdmi_ddr_ov5640_top_C63_seed7.sbit` against SHA256 `A3FDEDA15E3538FA23B3E188608C79592B1816E558EF66403BC8321D64A58943`.
4. Program SRAM only for this first trial. Do not overwrite board flash or remove the fallback image.

## Test sequence

1. Power-cycle the board, load the C63 SRAM image with PDS, and wait for DDR calibration, camera initialization, and HDMI timing to settle.
2. Read status over the existing UART tool. Confirm firmware version `0x12`, valid parameters, and observe the frame-busy/publication fields during operation.
3. Send the known-good real calibration parameters from `deliverables/20261026/collab2_C22_seed7_board_trial/reference/parameters/real_parameters.csv` after every power cycle. Runtime parameters are volatile. Keep affine and Gamma disabled for the first comparison.
4. Observe identity correction first, then the known small-angle setting. Check stable HDMI sync, visible corrected image, no persistent black frame, no DDR/protocol error, and repeated whole-frame publication.
5. Record board temperature, elapsed run time, UART status before/after, parameter values, camera scene, capture device, repeated-frame observations, and any recovery or reset.
6. If the image is invalid, DDR initialization fails, or the design faults, stop the trial and restore the C50 seed7 SRAM image. Do not attempt wide-angle stress with C63: its 15-degree full-frame simulation did not complete within the 500 ms timeout.

## Acceptance boundary

This first pass checks whether the routed C63 candidate starts and produces a stable corrected video image on the actual board. It does not establish 1080p30 unique camera frames, arbitrary-angle real-time performance, or final task acceptance. For an FPS claim, count unique input frames and displayed frames independently; the correction publication counter alone is insufficient.
