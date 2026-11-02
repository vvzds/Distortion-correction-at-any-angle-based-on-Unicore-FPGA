# Board Test Status

Status: pending for the five-key candidate. No board test was performed after
integrating the keys. The board acceptance report from 2026-10-29 is retained
as `BOARD_TEST_BASELINE_20261029.md` and applies only to its explicitly listed
baseline bitstream SHA256.

## Candidate images

- Main: seed 1, SHA256 `B1E48484A99C551B5E9D5BAD07ACCCEF715B268CD161E309FED0D3F18E19D5BD`.
- Backup: seed 2, SHA256 `2CCF7B0C63D327F944A779C9DBE5C4066713A9CF3A7D3981628E3D9043C3E480`.

Program the main candidate to SRAM through ordinary JTAG. Do not write Flash.
Before testing, verify the file hash and confirm PDS reports the expected
PG2L100H-6 FBG676 device. Stop if PDS reports a different device or the image
does not start normally.

## Test sequence

1. Confirm the unmodified live video and host status counters are normal.
2. Press and release each key separately, holding it longer than 20 ms; verify
   one state change per press and no repeats while held.
3. Check KEY0 Brown toggle, KEY2 Gamma toggle, KEY3 preset cycle, and KEY4 OSD
   visibility against `KEY_FUNCTIONS_20261103.md`.
4. Enable KEY1 while the BNO085 pose is valid. Verify it captures the current
   reference and the camera continues showing live frames; disable it again.
5. Send the matching host command after using KEY1, KEY3, and KEY4. Confirm the
   documented host/key priority and that key toggles remain usable afterward.
6. Measure corrected frame-counter deltas for at least ten minutes with the
   selected features enabled and with repeated key changes. Record the bitstream
   SHA, command/press sequence, new-frame FPS, errors, and observed image
   quality.

This procedure has not yet been run. PDS timing and module-level simulation do
not establish board-level 1080p30 or visual quality.
