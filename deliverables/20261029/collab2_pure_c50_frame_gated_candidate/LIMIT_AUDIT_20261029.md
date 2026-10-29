# Constraints and limits audit for the board-validated 1080p30 candidate

Scope: the exact `complete_PDS_project.zip` associated with SHA256
`069737CD5B58F2D583C424AA45C13B8AE108DE55C7FCD23264FA99933F4FD2B9`.
This audit changes no RTL, timing constraint, host parameter limit, or SRAM
image. The 2026-10-29 board result remains the small-angle baseline.

| Layer | Present restriction | Purpose and consequence | Recommendation |
| --- | --- | --- | --- |
| Video geometry | `video_contract.vh` fixes 1920x1080 RGB565, 20-bit word slot offset, four raw and four corrected banks; `rect_wr_if.v` requires exactly 2,073,600 pixels/1,036,800 words | Address math, cache row size, and HDMI timing all depend on it | Keep for this 1080p30 target; changing resolution is a separate system variant |
| Camera front end | `raw8_to_rgb565.v` uses 2x2 Bayer reconstruction, `BAYER_PHASE=0`, and `FRAME_GUARD=512` | Sensor phase and end-of-frame flushing must match physical camera | Do not simply remove; characterize a different sensor/phase separately |
| Host numeric range | `uart_tool.py` allows fx/fy 128..32767.99, centers inside image, k1/k2 +/-0.5, p1/p2 +/-0.01, affine matrix entries +/-2, translations +/-4096; `--force` bypasses host range precheck only | Prevents invalid Q16.16 and model inputs | Keep until wider calibration values are supplied; `--force` alone cannot bypass FPGA checks |
| FPGA parameter gate | `param_mgr.v` applies the same Q16.16 bounds to the complete shadow group only between frames; `undistort_core.v` rechecks them before starting | Avoids divide-by-zero, overflow/invalid mapping and mid-frame parameter mixtures | Keep both gates. A wider coefficient range needs numeric proof and full-frame simulation first |
| Host warning | `uart_tool.py` still warns translations beyond +/-256 may be rejected, while this candidate's `param_mgr.v` actually permits +/-4096 | Stale text, not an FPGA limit | Correct the warning separately; no RTL relaxation is needed |
| Mapping output | `undistort_map.v` clips mapped coordinates to x=0..1919 and y=0..1079 | Keeps DDR reads in range; out-of-frame samples replicate border pixels | Do not remove without an explicit border-fill policy and cache/address proof |
| Coordinate queue | `undistort_core.v` has 512-entry coordinate/key RAMs, a 4-entry head queue, <256 prepared distance, and <480 combined FIFO/inflight issuance | Prevents overwrite of coordinates still needed downstream | Tuning requires occupancy and retirement invariants; do not remove guards |
| Cache geometry | `undistort_cache_ab.v` requires `LINES_PER_SET=2`, 256 tags, eight ways per set, 128-pixel segments, and protected/pending tags | Prevents eviction of pixels used by in-flight bilinear samples | Do not cancel pinning. Larger cache or geometry is a measured architectural experiment |
| Source DDR reads | `undistort_core.v` waits for `load_done` before the next segment request; `corr_read_bridge.v` accepts one correction command and runs one native burst in flight, with display priority at burst boundaries and 16-beat/column splitting | Serial first-return latency dominates large-angle cache misses | Best candidate for an approved isolated redesign: bounded multiple outstanding reads with ordered/tagged completions and unchanged display arbitration |
| Corrected writes | `rect_wr_if.v` has 2048 complete-word capacity, a registered `<2016` ready threshold, exact SOF/EOF/word-count checks, and a full+same-cycle-drain bypass | Maintains lossless frame boundaries and absorbs sink stalls. The current routed worst setup path crosses the writer/packer grant into FIFO RAM WEA | Optimize the grant/write-enable path with equivalent behavior first; never simply disable overflow or frame checks |
| Write ownership | `corr_slot_ctrl.v` reserves a single target until publication, while `corr_write_pack.v` demands sequential addresses, exact frame word count and complete return before publish | Prevents partial frames and display/write aliasing | More overlap requires new slot ownership proof; no immediate need for tested 30 fps mode |
| Fault policy | `rect_wr_if.v` latches input, overflow, queue or slot fault until system reset | Never publishes a damaged frame; a transient fault can halt correction indefinitely | Candidate for frame-boundary recovery only with explicit discard/flush semantics and tests |
| Input frame gate | `corr_top.v` coalesces new raw-frame completions while busy; it does not queue every source frame | Keeps one latest pending frame and avoids rereading stale input. Under overload, intermediate source frames can be skipped | Keep unless throughput and slot count are redesigned together |
| Timing constraints | FDC constrains the DDR domain at 125 MHz, camera raw input, HDMI outputs and clock-domain groups. Routed setup WNS is +0.324 ns; worst path is writer state through packer grant to FIFO RAM WEA; minimum hold WHS is +0.102 ns | Positive slack is real margin; weakening constraints could hide a failing path | Do not relax clocks, uncertainty or false-path declarations merely to raise WNS |

The source-read limit is the only item above with clear evidence of blocking
larger-angle 30 fps performance. Prior C67 modeling estimated 42,024 reads at
15 degrees and 82,171 at 90 degrees for 128-pixel segments; 64 cycles of
serialized first-return wait alone cost about 2.69 million and 5.26 million
cycles, respectively, against a 4.17 million-cycle/frame 30 fps budget.
C68 also found that removing first-return wait alone did not make a normal
source layout reach 30 fps at 90 degrees. A two- or four-request redesign
therefore still needs full-frame accuracy, DDR contention, timing and board
proof; it is not a promised 30 fps solution.

Proposed approval boundary: first permit an **isolated two-outstanding-source-
read trial**, preserving the validated bitstream, parameter gates, range
checks, cache pinning and timing constraints. Only after that trial passes
simulation and route should it be considered for SRAM testing. Frame-level
fault recovery is a separate approval decision. No restriction is relaxed by
this audit.
