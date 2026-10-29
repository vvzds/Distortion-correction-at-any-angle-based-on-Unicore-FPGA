# Arbitrary-angle source-layout foundation (2026-10-29)

Status: architecture selection and verified address-contract RTL only. This is
not an integrated PDS project or a bitstream, and no arbitrary-angle 30 fps
claim is made. The board-tested small-angle baseline remains
`../collab2_pure_c50_frame_gated_candidate/` (bitstream SHA256
`069737CD5B58F2D583C424AA45C13B8AE108DE55C7FCD23264FA99933F4FD2B9`,
125 MHz setup WNS +0.324 ns, hold WHS +0.102 ns).

## Decision

Target one **directly written 16x8 blocked source-frame layout**, with 240x16
output microtiles and two-bank raster reorder. Keep the AF961A-tested OV5640
RAW8 acquisition, Bayer conversion, camera timing, C50 frame ownership,
parameter gates, corrected-frame writer, and HDMI display contract. Replace
the raw DDR writer after RGB565 packing; adapt the C63 cache keys, 2x2 sample
banking, and source-read addresses. The C63 fixed-point mapper and bilinear
arithmetic remain the starting implementation. Commit one complete source
frame before correction may hold its slot. Do not weaken frame/slot protection,
FIFO checks, parameter bounds, the 125 MHz FDC, or the one-outstanding source
read rule without the user's separate approval.

The three considered paths have different system costs:

| Path | Advantage | Material cost / risk | Decision |
| --- | --- | --- | --- |
| Row-major capture plus transposed copy | C70 has a verified 90-degree read-side experiment: 43.975 modeled correction publications/s | Extra full-frame read/write and slots; switches format with angle; 30-75 degrees still need proof; C70 excludes transpose production | Useful comparison, not the common foundation |
| Row-major capture plus blocked copy | Preserves the board-tested raw writer; isolates the blocked reader | Adds 4,147,200-byte read and write per converted frame, extra slot ownership, and conversion latency; may consume the 30 fps margin | Integration fallback and read-side test vehicle |
| Direct blocked capture | One source layout for all angles, no extra DDR frame copy or new source slot; strongest steady-state bandwidth budget | Needs a ping-pong eight-line camera-to-DDR stripe buffer and a new raw writer; must revalidate acquisition and raw preview | Chosen target |

## Full-frame comparison

The same C63 fixed-point `undistort_map.v` (SHA256
`89E31CC0CBB9D149523CE908DFB9104CE5A8FC5A6CB35762DCAC597E05475731`)
generated 2,073,600 clamped source coordinates at each angle, with measured
distortion coefficients and centered rotation. Each trace passed its exact
pixel-count check. The JSON files under `evidence/` replay four bilinear
neighbours per output pixel through an **ideal** 256-tag, 32-set, eight-way LRU
cache and 16-line output strips. Values are source-block misses/frame, not
real DDR transactions or frame rates.

| Rotation | Row 128x1, tile 64 | Block 16x8, tile 64 | Block 16x8, tile 240 |
| ---: | ---: | ---: | ---: |
| 0 | 17,835 | 19,571 | 19,096 |
| 15 | 42,023 | 21,573 | 21,339 |
| 30 | 62,465 | 22,614 | 22,269 |
| 45 | 76,410 | 22,369 | 21,802 |
| 60 | 82,975 | 21,033 | 19,782 |
| 75 | 82,559 | 19,028 | 14,014 |
| 90 | 82,171 | 17,682 | 17,673 |

Among the tested 128-pixel block shapes with 64-pixel output microtiles,
16x8 has the smallest seven-angle worst case (22,614 misses). The 240-pixel
microtile lowers its observed worst case to 22,269. A 320-pixel tile caused
85,372 misses at 90 degrees, so larger is not monotonically better. The
underlying set hash and ideal replacement are architectural estimates; they
omit cache pinning, DDR arbitration, writer contention, and physical timing.
In C66, a 64-pixel-tile row-major system produced only 13.955 modeled fps at
15 degrees and 6.878 at 90 degrees. Fewer block misses make the chosen layout
promising but do not establish 30 fps with one read in flight.

## Storage and interface contract

- Pixel format: RGB565, 1920x1080. There are 120 blocks per 8-row band, 135
  bands, and 16,200 blocks/frame. Each block is 16x8 pixels = 256 bytes =
  eight 256-bit DDR beats. Total is 4,147,200 bytes / 1,036,800 32-bit words,
  within the existing 4 MiB / 1,048,576-word source slot.
- Block index = `(y_storage >> 3) * 120 + (x >> 4)`. Native word offset =
  `block_index * 64`; each in-block row is one 256-bit beat. `y_storage` is
  `1079 - source_y`, matching the current C63 raw-frame orientation.
- Four bilinear neighbours use x, clamped x+1, `y_storage`, and clamped
  `y_storage-1`. The `source_block_quad.v` stage computes all four block keys
  using one base calculation and constant increments. The cache must protect
  all four keys through sample retirement, including right/bottom crossings.
- The direct writer needs two alternating eight-line RGB565 stripe banks,
  61,440 bytes total, to collect one band while draining the previous one.
  It must check exact line/frame counts and never publish an incomplete raw
  frame. The 240x16 output traversal requires two 16-line reorder banks,
  122,880 bytes total, before the existing sequential corrected writer.

`source_block_addr.v` and `source_block_quad.v` are reusable address stages;
neither is wired into the baseline top yet. ModelSim 10.7 compiled both and
their testbenches with zero warnings. Exhaustive tests passed all 2,073,600
valid coordinates, including block boundaries and image-edge clamping, and
rejected x=1920/y=1080. The full-frame coordinate traces are kept in the
local ASCII-path simulation directory and can be regenerated with
`map_angles_tb.v` and the baseline mapper; only compact JSON and source files
are committed. `analyze_tiles.js` scans output tile widths. The C68
`analyze_blocked.js` produced the `blocked_*.json` files.

## Promotion gates

1. Build and simulate the direct stripe writer with asynchronous camera/DDR
   clocks, DDR stalls, exact-frame publication, slot ownership, and no input
   loss. Keep the existing raw capture bitstream untouched.
2. Adapt the C63 cache and core to four block keys, eight-beat loads, 240x16
   traversal, and raster reorder. Compare every output pixel to an independent
   bilinear reference for identity, calibrated distortion, positive/negative
   rotations, edge clamps, and dynamic parameter changes between frames.
3. Run complete concurrent capture/correction/display DDR simulation at
   0, 15, 30, 45, 60, 75, and 90 degrees. At 125 MHz, a 30 fps frame budget is
   4,166,667 cycles; require strict sub-budget completion with margin and no
   lost input or display frames. If one outstanding source read cannot pass,
   present measured evidence and request approval before changing that limit.
4. Route the complete PG2L100H-6 FBG676 project using the unchanged FDC;
   require positive setup WNS and hold WHS, zero failing endpoints, and report
   LUT/FF/APM/DRM use. Then generate a separate SRAM bitstream and measure 30
   distinct corrected HDMI frames per complete second on board at the worst
   tested angles before promoting it.
