# 2026-10-29 SRAM board result: pure RAW8 capture + C50 correction

## Result

The candidate achieved nominal 1920x1080 30 distinct corrected HDMI images/s
on the tested PG2L100H board with the measured distortion parameters. The
40.03 s Hagibis run contained 1201 captured frames and 1200 consecutive
frame-hash changes; every interior complete second had 30 changes. A separate
30.03 s run with 1-degree affine enabled contained 901 frames and 900 changes,
again 30 changes in every interior complete second. The first second has 29
transitions because the first frame has no predecessor; the final second is
partial. This is a board measurement, not the earlier modeled publication
rate. It covers these two parameter sets and these run lengths, not unlimited
continuous operation or all possible transforms.

## Setup

- Bitstream: `C50_pure_capture_C63_frame_gate_seed7.sbit`, SHA256
  `069737CD5B58F2D583C424AA45C13B8AE108DE55C7FCD23264FA99933F4FD2B9`.
  The user loaded it to SRAM through PDS Boundary Scan. Flash was not changed.
- Board/device: PG2L100H-6 FBG676. Camera: connected OV5640 RAW8 module.
  HDMI capture: Hagibis, DirectShow MJPEG 1920x1080 30 fps. Status: COM11 at
  115200 baud. The `0xD` status marker verified the diagnostic bitstream.
- The real distortion CSV under `parameters/` was sent with `uart_tool.py
  send-file`. The affine run additionally sent `a11=0.999847695,
  a12=-0.017452406,a21=0.017452406,a22=0.999847695,tx=0,ty=0`, enabled.
  This tests a representative small-angle affine setting, not in-flight
  parameter changes or every angle and calibration.
- A hand moved through the scene against a checkerboard. The 1920x1080 image
  was visibly live; `board_evidence_20261029/c50_pure_board_snapshot_20261029.png`
  is a representative captured frame.

## Four-stage counters

All values are independent 16-bit counter deltas between the first and last
sample of each stage. Slight differences in elapsed time and stage count come
from UART page sampling on successive requests, so a reported 29.96-30.03/s
does not imply a measured sustained drop below a 30 Hz cadence.

| Test | Camera VSYNC | Raw complete | Corrected publish | HDMI slot advance |
| --- | ---: | ---: | ---: | ---: |
| Before parameters, 2.97-2.98 s | 90 (30.16/s) | 90 (30.16/s) | 0 | 0 |
| Real distortion, 39.94-39.98 s | 1200 (30.01/s) | 1199 (30.01/s) | 1198 (30.00/s) | 1198 (29.96/s) |
| Real distortion + 1-degree affine, 29.97-29.98 s | 900 (30.02/s) | 900 (30.03/s) | 899 (29.98/s) | 900 (30.02/s) |

The two-event skew in the 40 s window is consistent with stage sampling and
pipeline occupancy. These counters show no accumulating throughput deficit in
the measured windows, but they do not expose a complete DDR error register.

## HDMI frame evidence

FFmpeg DirectShow captured Hagibis at its negotiated 1920x1080 MJPEG 30 fps.
Each frame was reduced to 320x180 grayscale and SHA256-hashed. The saved
framehash files contain 1201 and 901 consecutive zero-based PTS records;
neither has an adjacent equal hash. For an independent content check, the
included 320x180 lossless FFV1 video excerpts were decoded, median-filtered
with a 3x3 kernel, and compared using mean absolute grayscale difference.
All 600 distortion-only transitions in 20.03 s and all 300 affine transitions
in 10.03 s exceeded a 0.5 gray-level threshold. Minimum filtered differences
were 1.946 and 1.108 respectively. This reduces the chance that a hash-only
result is caused by codec or sensor noise, although the test cannot prove
every source exposure is semantically distinct under a static scene.

Recompute the counters from the CSV, the hashes with
`deliverables/20261028/collab2_c50_camera_path_probe/analyze_framehash.py`,
and filtered differences with `board_evidence_20261029/analyze_corrected_motion.py`.
The lossless excerpts reproduce the latter analysis. The original 1080p MJPEG
recordings remain in the local task `work/` directory due to their size (205 MB
and 89 MB); their reduced lossless excerpts, raw counter CSV, framehash text,
and snapshot are archived here. The full 40 s and 30 s runs used framehash
output, while the lossless excerpts were additional recordings in each mode.

## Remaining scope

The measured result supports promoting this candidate as the first
board-validated 1080p30 correction baseline. Before claiming long-term or
wide-angle reliability, run a longer soak and test the intended range of
calibration and affine parameters. The original C50 seed7 bitstream remains
available as fallback.
