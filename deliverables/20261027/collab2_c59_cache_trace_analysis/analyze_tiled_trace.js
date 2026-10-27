const fs = require('fs');

const [tracePath, outputPath] = process.argv.slice(2);
if (!tracePath || !outputPath) {
  throw new Error('usage: node analyze_tiled_trace.js map_keys.hex summary.json');
}

const width = 1920;
const height = 1080;
const keys = Uint32Array.from(fs.readFileSync(tracePath, 'ascii').trimEnd()
  .split(/\r?\n/), line => Number.parseInt(line, 16));
if (keys.length !== width * height) throw new Error(`bad trace: ${keys.length}`);

function assess(stripHeight, setCount) {
  const ways = 8;
  const sets = Array.from({length: setCount}, () => []);
  const hashBits = Math.log2(setCount) - 1;
  const hashMask = (1 << hashBits) - 1;
  let misses = 0;
  let maxKeysPerStrip = 0;
  for (let base = 0; base < height; base += stripHeight) {
    const stripKeys = new Set();
    const rowsInStrip = Math.min(stripHeight, height - base);
    for (let x = 0; x < width; x++) {
      for (let offset = 0; offset < rowsInStrip; offset++) {
        const y = base + offset;
        const word = keys[y * width + x];
        const rows = [word >>> 21, (word >>> 10) & 2047];
        const segments = [(word >>> 5) & 31, word & 31];
        for (const row of rows) for (const segment of segments) {
          const tag = (row << 5) | segment;
          const set = ((row & 1) << hashBits) |
            (((row >>> 1) ^ segment) & hashMask);
          stripKeys.add(tag);
          const entries = sets[set];
          const position = entries.indexOf(tag);
          if (position >= 0) entries.splice(position, 1);
          else {
            misses++;
            if (entries.length === ways) entries.shift();
          }
          entries.push(tag);
        }
      }
    }
    maxKeysPerStrip = Math.max(maxKeysPerStrip, stripKeys.size);
  }
  return {
    stripHeight,
    tagCapacity: setCount * ways,
    outputBufferBytesPerBank: stripHeight * width * 2,
    idealLruMisses: misses,
    maxDistinctKeysInStrip: maxKeysPerStrip,
  };
}

const result = {
  pixels: keys.length,
  traversal: 'row strips, column-major within each strip, then raster readback',
  model: '8-way RTL hash, LRU replacement, no pinning or DDR timing',
  scenarios: [1, 2, 4, 8, 16, 32].flatMap(h =>
    [32, 64, 128].map(sets => assess(h, sets))),
};
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result.scenarios, null, 2));
