const fs = require('fs');

const [tracePath, resultPath] = process.argv.slice(2);
if (!tracePath || !resultPath) {
  throw new Error('usage: node analyze_output_tiles.js map_xy.hex result.json');
}

const width = 1920;
const height = 1080;
const pixels = width * height;
const words = Uint32Array.from(fs.readFileSync(tracePath, 'ascii').trimEnd()
  .split(/\r?\n/), line => Number.parseInt(line, 16));
if (words.length !== pixels) throw new Error(`bad trace length ${words.length}`);

function assess(tileW, tileH, order) {
  const cachedRows = new Int16Array(4).fill(-1);
  let replace = 0;
  let rowReads = 0;
  const sampleRow = row => {
    if (cachedRows.includes(row)) return;
    rowReads++;
    cachedRows[replace] = row;
    replace = (replace + 1) & 3;
  };
  function tile(x0, y0) {
    const rows = Math.min(tileH, height - y0);
    const cols = Math.min(tileW, width - x0);
    for (let dy = 0; dy < rows; dy++) {
      const offset = (y0 + dy) * width + x0;
      for (let dx = 0; dx < cols; dx++) {
        const value = words[offset + dx];
        const sy = (value >>> 11) & 2047;
        sampleRow(height - 1 - sy);
        sampleRow(sy === height - 1 ? 0 : height - 2 - sy);
      }
    }
  }
  if (order === 'horizontal') {
    for (let y = 0; y < height; y += tileH)
      for (let x = 0; x < width; x += tileW) tile(x, y);
  } else {
    for (let x = 0; x < width; x += tileW)
      for (let y = 0; y < height; y += tileH) tile(x, y);
  }
  const sourceReadBeats = rowReads * 120;
  return {tileW, tileH, order, sourceRowReads: rowReads,
    sourceReadBeats, sourceReadBytes: sourceReadBeats * 32,
    readBytesPerOutputPixel: sourceReadBeats * 32 / pixels,
    outputBufferBytes: tileW * tileH * 2};
}

const cases = [];
cases.push(assess(width, height, 'horizontal'));
for (const tileH of [16, 32, 64, 128]) {
  for (const tileW of [32, 64, 128, 256]) {
    for (const order of ['horizontal', 'vertical'])
      cases.push(assess(tileW, tileH, order));
  }
}
const result = {
  trace: tracePath,
  model: 'RTL-shaped locality estimate: four cached source rows, round-robin replacement, each miss loads a full 1920-pixel row (120 x 256-bit beats)',
  limitations: [
    'This is a trace-based source-read estimate, not cycle-accurate DDR simulation or FPS evidence.',
    'The RTL cache also protects currently queried rows during prefetch; this conservative model does not model that protection.',
    'Tiled output order is incompatible with rect_wr_if/corr_write_pack, which require a complete frame in contiguous address order and pack 64 consecutive 32-bit words per packet.',
    'A deployable tiled scheduler needs output reordering storage, address/slot lifecycle support, and display integration; none are included here.'
  ],
  cases
};
fs.writeFileSync(resultPath, JSON.stringify(result, null, 2) + '\n');
console.log(cases.map(({tileW, tileH, order, sourceRowReads, sourceReadBeats,
  readBytesPerOutputPixel}) => ({tileW, tileH, order, sourceRowReads,
  sourceReadBeats, readBytesPerOutputPixel: Number(readBytesPerOutputPixel.toFixed(2))})));
