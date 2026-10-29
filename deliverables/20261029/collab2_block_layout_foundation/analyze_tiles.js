const fs = require('fs');

const [tracePath, outputPath] = process.argv.slice(2);
if (!tracePath || !outputPath) throw new Error('usage: node analyze_tiles.js trace.hex result.json');
const width = 1920, height = 1080;
const values = Uint32Array.from(fs.readFileSync(tracePath, 'ascii').trimEnd()
  .split(/\r?\n/), line => Number.parseInt(line, 16));
if (values.length !== width * height) throw new Error(`bad trace length ${values.length}`);

function assess(tileWidth) {
  const sets = Array.from({length: 32}, () => []);
  let misses = 0;
  function access(x, y) {
    const block = (y >> 3) * 120 + (x >> 4);
    const entries = sets[block & 31];
    const pos = entries.indexOf(block);
    if (pos < 0) {
      misses++;
      if (entries.length === 8) entries.shift();
    } else entries.splice(pos, 1);
    entries.push(block);
  }
  for (let stripY = 0; stripY < height; stripY += 16)
    for (let tileX = 0; tileX < width; tileX += tileWidth)
      for (let dy = 0; dy < Math.min(16, height - stripY); dy++)
        for (let dx = 0; dx < tileWidth; dx++) {
          const value = values[(stripY + dy) * width + tileX + dx];
          const x = value & 2047, y = (value >>> 11) & 2047;
          const xr = Math.min(x + 1, width - 1), yb = Math.min(y + 1, height - 1);
          access(x, y); access(xr, y); access(x, yb); access(xr, yb);
        }
  return {tileWidth, misses, beats: misses * 8};
}

const tileWidths = [32, 40, 48, 64, 80, 96, 120, 128, 160, 192,
  240, 320, 384, 480, 640, 960, 1920];
const result = {model: '16x8 block, 256 tags, 32 sets, eight-way ideal LRU, 16-line strips',
  cases: tileWidths.map(assess)};
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
console.log(result.cases.map(x => `${x.tileWidth}:${x.misses}`).join(' '));
