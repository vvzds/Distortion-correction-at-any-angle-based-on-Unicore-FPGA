const fs = require('fs');

const [tracePath, outputPath] = process.argv.slice(2);
if (!tracePath || !outputPath) throw new Error('usage: node analyze_cache_geometry.js trace.hex result.json');
const width = 1920, height = 1080;
const values = Uint32Array.from(fs.readFileSync(tracePath, 'ascii').trimEnd()
  .split(/\r?\n/), line => Number.parseInt(line, 16));
if (values.length !== width * height) throw new Error(`bad trace length ${values.length}`);

function assess(tileWidth, setCount, hash, reversedRows) {
  const sets = Array.from({length: setCount}, () => []);
  let misses = 0;
  function access(x, y) {
    const bx = x >> 4, by = (reversedRows ? height - 1 - y : y) >> 3;
    const block = by * 120 + bx;
    const set = (hash === 'linear' ? block : bx ^ by) & (setCount - 1);
    const entries = sets[set];
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
  return {tileWidth, setCount, ways: 8, hash,
    storage: reversedRows ? 'camera-order' : 'logical-y-order', misses};
}

const cases = [];
for (const tileWidth of [240, 960])
  for (const setCount of [32, 64, 128])
    for (const hash of ['linear', 'xor'])
      for (const reversedRows of [false, true])
        cases.push(assess(tileWidth, setCount, hash, reversedRows));
const result = {model: '16x8 block, ideal eight-way LRU and 16-line strips', cases};
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
console.log(cases.map(x => `${x.tileWidth}/${x.setCount}/${x.hash}:${x.misses}`).join(' '));
