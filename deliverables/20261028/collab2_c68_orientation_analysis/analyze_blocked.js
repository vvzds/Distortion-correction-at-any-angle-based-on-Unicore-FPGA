const fs = require('fs');

const [tracePath, outputPath] = process.argv.slice(2);
if (!tracePath || !outputPath) {
  throw new Error('usage: node analyze_blocked.js map_xy.hex result.json');
}
const width = 1920;
const height = 1080;
const values = Uint32Array.from(fs.readFileSync(tracePath, 'ascii').trimEnd()
  .split(/\r?\n/), line => Number.parseInt(line, 16));
if (values.length !== width * height) throw new Error(`bad trace length ${values.length}`);

function assess(blockW, blockH, outputTileW) {
  if (blockW * blockH !== 128 || width % blockW !== 0 || outputTileW > width) {
    throw new Error('bad block geometry');
  }
  const sets = Array.from({length: 32}, () => []);
  let misses = 0;
  function access(x, y) {
    const blockX = Math.floor(x / blockW);
    const blockY = Math.floor(y / blockH);
    const block = blockY * (width / blockW) + blockX;
    const set = block & 31;
    const entries = sets[set];
    const position = entries.indexOf(block);
    if (position >= 0) entries.splice(position, 1);
    else {
      misses++;
      if (entries.length === 8) entries.shift();
    }
    entries.push(block);
  }
  for (let base = 0; base < height; base += 16) {
    const rows = Math.min(16, height - base);
    for (let tileX = 0; tileX < width; tileX += outputTileW) {
      for (let dy = 0; dy < rows; dy++) {
        const offset = (base + dy) * width + tileX;
        for (let dx = 0; dx < outputTileW; dx++) {
          const value = values[offset + dx];
          const sx = value & 2047;
          const sy = (value >>> 11) & 2047;
          access(sx, sy);
          access(Math.min(sx + 1, width - 1), sy);
          access(sx, Math.min(sy + 1, height - 1));
          access(Math.min(sx + 1, width - 1), Math.min(sy + 1, height - 1));
        }
      }
    }
  }
  return {blockW, blockH, outputTileW, misses, payloadBeats: misses * 8};
}

const result = {
  model: '128-pixel blocks, 256 entries, 32 sets, 8-way LRU; ideal replacement only',
  sourceBytes: width * 1088 * 2,
  cases: [
    [128, 1], [64, 2], [32, 4], [16, 8], [8, 16], [4, 32], [2, 64], [1, 128],
  ].flatMap(([w, h]) => [64, 1920].map(tile => assess(w, h, tile))),
};
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result.cases));
