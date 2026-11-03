# 2026-11-03 Function-Key Candidate

This delivery adds five debounced board keys to the quality pipeline project.
Read `FEATURE_KEYS_BUILD_REPORT_20261103.md` for implementation evidence and
limitations, and `KEY_FUNCTIONS_20261103.md` for the exact key mapping.

## Files

- `pango_bno085_quality_keys_seed1_20261103.sbit`: recommended first board test.
- `pango_bno085_quality_keys_seed2_20261103.sbit`: backup routed image.
- `pango_quality_function_keys_project_20261103.zip`: complete portable PDS
  project, matching RTL/IP/host tools, board procedure, simulation receipts,
  PDS timing evidence, selected images and the preserved pre-key seed 7 image.
- `SHA256SUMS.txt`: hashes for all delivered top-level artifacts.

Seed 1 has the strongest routed setup margin among the selected key-enabled
images: +0.081 ns. Seed 2 is +0.052 ns. Both have zero reported setup and hold
failures. Board validation is still pending; these results do not prove stable
1080p30. PDS also warns that two frame-buffer IP metadata packages say FBG484
while the project target is FBG676; see the build report before production use.

The GitHub push is separate from creating these local deliverables. Do not
interpret the presence of this directory as proof that the remote branch was
updated; report the verified commit and remote status after the push attempt.
