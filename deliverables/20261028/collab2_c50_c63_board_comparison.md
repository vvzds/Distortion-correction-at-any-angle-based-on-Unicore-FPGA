# C50 / C63 board and frame-rate comparison

Date: 2026-10-28

## Result

For measured board behavior, C50 has the stronger and more comparable evidence. C63 has a higher modeled identity-frame publication rate, but it has not demonstrated a stable 30 distinct corrected images per second under real calibrated distortion and motion. Neither candidate has passed strict 1080p30 unique-frame acceptance.

## Modeled corrected-frame publication

These are complete corrected-frame publication rates in the 125 MHz DDR simulation model. They are not independent camera-input or HDMI-display FPS.

| Candidate | Identity | Real calibration | 1-degree rotation |
| --- | ---: | ---: | ---: |
| C50 seed7 | 30.128519 fps | 37.842436 fps | 37.000409 fps |
| C63 seed7 | 44.330045 fps | 37.491872 fps | 36.762576 fps |

C63 is faster for identity in this model. C50 is slightly faster with the real calibration and 1-degree rotation. C63's 15-degree full-frame simulation timed out after 1,673,417 of 2,073,600 output pixels, so it does not establish wide-angle real-time performance.

## Board measurements

- C50's repository capture records 28.5 content changes/s in a 12-second static-chart sequence and 23.6 changes/s in a 10-second motion sequence. The motion capture was decoded at 59.9 fps and compared by exact hashes of consecutive 320x180 downsampled frames. The separate UART publication counter measured 48.009 complete corrected-frame writes/s; it is explicitly not a camera or HDMI unique-frame rate.
- C63 is now visible in OBS scene 2. A 139.38-second 1920x1080 recording decoded as 8,363 frames at 60 fps. A low-resolution denoised difference analysis of its best 20-second window estimated 31.6 low-threshold changes/s (minimum 27/s; 16/20 seconds at or above 30) and 23.3 more-salient changes/s (minimum 19/s). This threshold-based estimate is not directly comparable to C50's exact-hash method and does not prove stable 30 unique frames/s.
- The C63 raw recording remains at `C:\Users\叶翔\Videos\2026-10-28 19-48-24.mp4` (about 1.1 GB). This summary preserves the measurements without adding the oversized raw capture to the Git repository.

## 125 MHz post-route timing

| Candidate | Setup WNS | Hold WHS | Interpretation |
| --- | ---: | ---: | --- |
| C50 seed7 | +0.211 ns | +0.134 ns | Setup and hold closed |
| C63 seed7 final board-trial build | +0.521 ns | +0.083 ns | Setup margin increased by 0.310 ns; hold margin decreased by 0.051 ns; both closed |

WNS is setup slack; WHS is hold slack. The C63 values above are from the final board-trial rebuild, not the earlier archived C63 run (+0.445/+0.064 ns).

## Decision

C50 remains the better-supported board fallback. C63 improves setup timing and modeled identity throughput, but its real-calibration modeled publication is slightly lower, the 15-degree simulation does not finish, and its board capture does not establish 30 distinct motion frames/s. Keep the two rates separate: corrected-frame publication is not camera/display cadence.

## Source records

- C50 board cadence and publication: `deliverables/20261027/collab2_c50_board_trial/cadence_check.json`, `motion_capture.json`, `board_status.json`, and `板测回传.md`.
- C50 simulation and P&R: `deliverables/20261027/collab2_advanced_task2_audit/README.md` and `evidence/timing/c50_final_holdfix.txt`.
- C63 simulation and route: `deliverables/20261028/collab2_c63_initial_board_trial/C63_simulation_and_route_evidence.md` and `README.md`.
