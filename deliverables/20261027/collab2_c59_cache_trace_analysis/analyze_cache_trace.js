const fs = require('fs');
const crypto = require('crypto');

const [tracePath, outputPath] = process.argv.slice(2);
if (!tracePath || !outputPath) {
  throw new Error('usage: node analyze_cache_trace.js map_keys.hex summary.json');
}

const source = fs.readFileSync(tracePath);
const lines = source.toString('ascii').trimEnd().split(/\r?\n/);
const width = 1920;
const height = 1080;
if (lines.length !== width * height) {
  throw new Error(`expected ${width * height} keys, got ${lines.length}`);
}
const keys = Uint32Array.from(lines, line => {
  if (!/^[0-9a-fA-F]{8}$/.test(line)) throw new Error(`invalid key: ${line}`);
  return Number.parseInt(line, 16);
});

function assess(ways, serpentine) {
  const sets = Array.from({length: 32}, () => []);
  const lineMisses = new Uint32Array(height);
  let misses = 0;
  let prefixMisses = 0;
  let maxLineKeys = 0;
  for (let y = 0; y < height; y++) {
    const lineKeys = new Set();
    for (let step = 0; step < width; step++) {
      const x = serpentine && (y & 1) ? width - 1 - step : step;
      const word = keys[y * width + x];
      const rows = [word >>> 21, (word >>> 10) & 2047];
      const segments = [(word >>> 5) & 31, word & 31];
      for (const row of rows) for (const segment of segments) {
        const tag = (row << 5) | segment;
        const set = ((row & 1) << 4) | (((row >>> 1) ^ segment) & 15);
        lineKeys.add(tag);
        const entries = sets[set];
        const position = entries.indexOf(tag);
        if (position >= 0) entries.splice(position, 1);
        else {
          misses++;
          lineMisses[y]++;
          if (entries.length === ways) entries.shift();
        }
        entries.push(tag);
      }
      if (y * width + step === 1673416) prefixMisses = misses;
    }
    if (lineKeys.size > maxLineKeys) maxLineKeys = lineKeys.size;
  }
  return {
    tagCapacity: ways * 32,
    waysPerSet: ways,
    traversal: serpentine ? 'alternating scanline direction' : 'raster',
    idealLruMisses: misses,
    idealLruMissesAtC57TimeoutPixel: prefixMisses,
    missesPerOutputPixel: misses / keys.length,
    maxDistinctKeysInOneOutputLine: maxLineKeys,
    medianMissesPerLine: Array.from(lineMisses).sort((a, b) => a - b)[height >>> 1],
    lastLineMisses: lineMisses[height - 1],
  };
}

const result = {
  traceSha256: crypto.createHash('sha256').update(source).digest('hex').toUpperCase(),
  pixels: keys.length,
  model: '32 sets with the RTL row/segment XOR hash; perfect LRU, no pinning or DDR timing',
  scenarios: [
    assess(8, false), assess(16, false), assess(32, false),
    assess(8, true), assess(16, true), assess(32, true),
  ],
};
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result.scenarios, null, 2));
