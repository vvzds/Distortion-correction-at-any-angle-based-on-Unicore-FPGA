const fs = require('fs');

const [tracePath, outputPath, tileWidthArg] = process.argv.slice(2);
if (!tracePath || !outputPath) {
  throw new Error('usage: node analyze_orientation.js map_xy.hex result.json [tileWidth]');
}
const width = 1920;
const height = 1080;
const tileWidth = tileWidthArg ? Number(tileWidthArg) : 64;
if (!Number.isInteger(tileWidth) || tileWidth < 1 || width % tileWidth !== 0) {
  throw new Error(`invalid tileWidth ${tileWidthArg}`);
}
const pixels = width * height;
const values = Uint32Array.from(fs.readFileSync(tracePath, 'ascii').trimEnd()
  .split(/\r?\n/), line => Number.parseInt(line, 16));
if (values.length !== pixels) throw new Error(`bad trace length ${values.length}`);
for (const value of values) {
  const sx = value & 2047;
  const sy = (value >>> 11) & 2047;
  if (sx >= width || sy >= height) throw new Error(`bad coordinate ${sx},${sy}`);
}

function assess(transposed) {
  const sets = Array.from({length: 32}, () => []);
  let misses = 0;
  let beats = 0;
  let edgeMisses = 0;
  function access(row, segment) {
    const tag = (row << 5) | segment;
    const set = ((row & 1) << 4) | (((row >>> 1) ^ segment) & 15);
    const entries = sets[set];
    const position = entries.indexOf(tag);
    if (position >= 0) entries.splice(position, 1);
    else {
      misses++;
      const segmentWidth = transposed ? height : width;
      const usefulPixels = Math.min(128, segmentWidth - segment * 128);
      beats += Math.ceil(usefulPixels / 16);
      if (usefulPixels < 128) edgeMisses++;
      if (entries.length === 8) entries.shift();
    }
    entries.push(tag);
  }
  for (let base = 0; base < height; base += 16) {
    const rows = Math.min(16, height - base);
    for (let tileX = 0; tileX < width; tileX += tileWidth) {
      for (let dy = 0; dy < rows; dy++) {
        const first = (base + dy) * width + tileX;
        for (let dx = 0; dx < tileWidth; dx++) {
          const value = values[first + dx];
          const sx = value & 2047;
          const sy = (value >>> 11) & 2047;
          const x1 = Math.min(sx + 1, width - 1);
          const rowA = height - 1 - sy;
          const rowB = sy === height - 1 ? 0 : rowA - 1;
          if (transposed) {
            const segA = rowA >>> 7;
            const segB = rowB >>> 7;
            access(sx, segA);
            access(x1, segA);
            access(sx, segB);
            access(x1, segB);
          } else {
            const segA = sx >>> 7;
            const segB = x1 >>> 7;
            access(rowA, segA);
            access(rowA, segB);
            access(rowB, segA);
            access(rowB, segB);
          }
        }
      }
    }
  }
  return {misses, payloadBeats: beats, edgeMisses,
    sourceFrameBytes: transposed ? width * 1088 * 2 : width * height * 2};
}

const result = {
  trace: tracePath,
  geometry: `16 output rows per strip, ${tileWidth}-pixel microtiles, 256 tags, 32 sets, 8-way LRU`,
  normal: assess(false),
  transposed: assess(true),
  limits: 'Ideal replacement only; no pinning, DMA transpose cost, DDR arbitration, or physical timing',
};
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result));
