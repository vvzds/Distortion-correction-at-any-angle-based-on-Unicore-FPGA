# Predictive affine motion control

The desktop controller supports direct rotation, scale, translation and shear, plus a continuous motion mode for smooth rotation and tilt. It uses the existing frame-latched UART protocol; the FPGA datapath and bitstream are unchanged.

## Motion model

Rotation and shear follow one phase-locked sinusoidal trajectory:

```text
angle(t) = center + rotation_amplitude * sin(2*pi*(t + lead)/period)
shear(t) = shear_center + tilt_amplitude * cos(2*pi*(t + lead)/period)
lead     = measured configure-to-active latency EMA + extra lead
```

The sine curve has zero velocity at both ends of its travel, so it returns without a direction-change step. The latency estimate starts when the configuration packet is written. The host brackets activation between the last status sample with the old sequence and the first sample with the new sequence, then estimates the boundary at the midpoint of those observations. A 0.2 EMA smooths the estimate. UART round-trip time bounds the precision; it is not a sensor-to-photon measurement. “Extra lead” is a user bias on top; it is not a universal millisecond constant. Start with 0 ms and adjust only after observing the display.

## Safety and operation

Before motion begins, the host samples one complete trajectory, finds one fixed zoom that covers the sampled path when auto-crop is enabled, and performs the existing full-frame fixed-point and patch preflight at every trajectory sample. It rejects paths whose largest observed patch exceeds 192x192, reserving 64 source pixels against each 256-pixel patch limit. The phase sampling density scales with rotation amplitude, with at least 72 points. Changes to transform controls stop the motion; edit parameters and start again to check a new path.

Connect the FPGA, set rotation amplitude, tilt amplitude, period and extra lead, then start motion. Rotation amplitude is limited to 180 degrees and shear amplitude to 0.75. The selected center, zoom, translation and shear remain the trajectory center. A common zoom is held for the entire path to prevent crop pumping. Stop leaves the last applied transform active.

The selected period keeps peak angular speed below 90 degrees/s (about 3 degrees per 30 fps frame) and peak shear speed below 0.5/s. The sender waits for each frame-boundary activation before sending the next update. During motion it polls status at 5 ms intervals and reuses the latest active/pending sequence telemetry, avoiding an extra status transaction before each configuration packet. The desktop event loop checks worker results every 2 ms during active transactions and backs off to 50 ms while idle. UART serialization still limits update cadence. No host prediction can remove HDMI frame quantization, dropped camera frames, sensor latency, or monitor/capture latency. Board testing must still measure unique camera, corrected and displayed frame identities during motion before claiming visually seamless 1080p30 operation.

Run the host-only math checks with:

```powershell
python tools/check_motion.py
```
