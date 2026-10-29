# Pango predictive affine motion control

This deliverable adds a host-side continuous affine motion mode to the supplied Pango core package. The FPGA RTL, UART packet format, constraints, and board-tested bitstream remain unchanged.

## Package files

- `pango_motion_control_20261029.zip` is the complete updated software release. Verify it with `pango_motion_control_20261029.sha256`.
- `gui.py` replaces `pango-undistort/host/gui.py`.
- `motion.py` is added as `pango-undistort/host/motion.py`.
- `protocol.py` replaces `pango-undistort/host/protocol.py` and adds timed activation reporting while preserving `configure()` behavior.
- `check_motion.py` is added as `pango-undistort/tools/check_motion.py`.
- `MOTION_CONTROL.md` is added at the package root.
- `package_README.md` and `release_README.txt` are the corrected package documentation copied into the full release ZIP.
- `package_overlay.py` reproducibly rebuilds the full ZIP from the original archive and these overlay files.

## Behavior

The desktop GUI has a continuous affine-motion section. Rotation and shear tilt move together on a phase-locked sinusoid, which slows to zero at each reversal. The period is constrained so peak rotation stays below 90 degrees/second (about 3 degrees per 30 fps output frame), and peak shear stays below 0.5/second. Default values are +/-45 degrees, +/-0.10 shear, and a 6 second round trip.

Before starting, the host samples a full cycle, computes one common auto-crop zoom, and runs fixed-point full-resolution preflight for the entire sampled path. It requires 100% valid coverage when auto-crop is on and rejects sampled patches above 192x192, leaving margin under the RTL 256x256 patch capacity. The validated zoom remains fixed during movement to prevent crop pumping.

Each update is predicted forward by an estimated activation time. The host timestamps status samples after each query packet drains, then brackets the frame-boundary update between the last old-sequence sample and the first new-sequence sample. Their midpoint is smoothed with a 0.2 exponential moving average; the longer response transmission does not skew the timestamp. Motion polls at 1 ms and reuses active/pending sequence telemetry to avoid a redundant status query before each configuration packet. After activation, the next update is queued immediately without an extra fixed idle delay. The desktop event loop checks worker results every 2 ms during active transactions and backs off to 50 ms while idle. Serial response time and OS scheduling bound timing precision and update rate. The operator can add a lead in milliseconds; the default is zero. Stop leaves the last successfully applied transform. UART/FPGA errors or nonzero patch-overflow telemetry stop the motion.

## Validation

`python tools/check_motion.py` checks sinusoid phase and reversal, full angular coverage, phase lead, latency smoothing, midpoint activation timing, and default full-resolution path preflight. Python bytecode compilation passes. The desktop GUI was visually inspected without connecting to hardware. The default 45 degree sweep with 0.10 shear passed 90 phases: common zoom 1.8996, 100% valid coverage, maximum patch 64x38. Full +/-180 degree rotation with 0.10 shear passed 360 phases: common zoom 1.9578, 100% valid coverage, maximum patch 64x39.

The continuous motion has not been board-tested. These host-model checks and the package's prior publication-rate evidence do not prove 30 unique camera-to-HDMI frames per second or visually seamless motion. A lossless moving-target capture must confirm camera, corrected, and displayed frame progression before making that claim.
