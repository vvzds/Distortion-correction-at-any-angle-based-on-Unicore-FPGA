# C71 output-tile locality screen (2026-10-28)

## Verdict

Do not implement output-tile scheduling from this result. Reordering output tiles conflicts with the current full-frame sequential writer, while the tested 90-degree trace still causes more than 140 million 256-bit source beats per frame in a four-row cache model. This rejects the tile-order path as a practical 1080p30 optimization candidate.

C50 seed7 remains the board-tested fallback. C69/C70 remain transposed-source experiments and do not establish a camera capture-to-display deployment path.

## Method

`analyze_output_tiles.js` consumes the existing full-frame packed coordinate traces for 15 and 90 degrees. It models four cached source rows with round-robin replacement, and charges each missing row as the RTL's complete 120-beat row load. It compares raster order with rectangular output-tile traversal. It reports source-row loads, source beats, read bytes per output pixel, and the output reorder buffer size implied by a tile.

This is a locality screen, not a cycle-accurate DDR model. It omits arbitration, bank/row timing, capture and display traffic, and the RTL's protection of active sample rows during prefetch. Tile traversal also violates the current writer contract: `rect_wr_if` emits a sequential full-frame address stream, and `corr_write_pack` assembles 64 consecutive 32-bit words into each eight-beat packet. The current display path expects the published frame in the existing slot layout. A tile scheduler would need explicit reorder storage plus writer, slot lifecycle, and display integration.

## Selected results

The results below use horizontal tile traversal. Larger tiles are the most favorable tested widths; changing tile height has little effect in this trace screen.

| Mapping | Traversal | Tile | Source row loads/frame | 256-bit beats/frame | Read bytes/output pixel | Tile RGB565 buffer |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 15 degrees | raster | full frame | 448,710 | 53,845,200 | 830.94 | 4,147,200 B |
| 15 degrees | horizontal tiles | 256x16 | 461,288 | 55,354,560 | 854.24 | 8 KiB |
| 90 degrees | raster | full frame | 1,166,400 | 139,968,000 | 2,160.00 | 4,147,200 B |
| 90 degrees | horizontal tiles | 256x16 | 1,170,765 | 140,491,800 | 2,168.08 | 8 KiB |

The raster result is the same four-row replacement model run as one full-frame tile, not a measured RTL transaction count. Actual line-cache row protection and prefetch make the RTL behavior different, so do not compare these estimates directly with measured C70 traffic. The 256x16 tile barely changes the row-read total (about 2.8% worse at 15 degrees and 0.38% worse at 90 degrees) while requiring output reordering. This gives no justification for the added scheduler and writer complexity.

## Reproduction

Run from the repository root with Node.js:

```powershell
node deliverables/20261028/collab2_c71_output_tile_analysis/analyze_output_tiles.js 'D:\FPGA PDS\yx\C59_cache_trace_20261027\map_xy_15.hex' deliverables/20261028/collab2_c71_output_tile_analysis/rotate15.json
node deliverables/20261028/collab2_c71_output_tile_analysis/analyze_output_tiles.js 'D:\FPGA PDS\yx\C59_cache_trace_20261027\map_xy_90.hex' deliverables/20261028/collab2_c71_output_tile_analysis/rotate90.json
```

The coordinate trace files are local PDS artifacts and are not copied into this deliverable. The JSON outputs preserve every tested tile dimension and traversal order.

## Next optimization direction

Keep output pixels in raster order and target work that preserves the current writer and display contracts: pipeline the correction compute and request/return overlap, then use exact arbitration-aware full-frame simulation and multi-seed post-route timing to judge changes. The transposed-source experiments can inform read locality only after a real capture transpose producer and its concurrent DDR costs are included.
