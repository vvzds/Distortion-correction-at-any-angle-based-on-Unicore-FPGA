const fs = require('fs');

const [tracePath, outputPath, stripHeightArg] = process.argv.slice(2);
if (!tracePath || !outputPath) {
  throw new Error('usage: node analyze_microtile.js map_keys.hex result.json [stripHeight]');
}

const width = 1920;
const height = 1080;
const stripHeight = stripHeightArg ? Number(stripHeightArg) : 16;
if (!Number.isInteger(stripHeight) || stripHeight < 1 || stripHeight > height) {
  throw new Error(`invalid stripHeight: ${stripHeightArg}`);
}
const keys = Uint32Array.from(fs.readFileSync(tracePath, 'ascii').trimEnd()
  .split(/\r?\n/), line => Number.parseInt(line, 16));
if (keys.length !== width * height) throw new Error(`bad trace: ${keys.length}`);

function assess(tileWidth) {
  const sets = Array.from({length: 32}, () => []);
  let misses = 0;
  let consecutiveKeyReuse = 0;
  let previousWord = -1;
  function access(row, segment) {
    const tag = (row << 5) | segment;
    const set = ((row & 1) << 4) | (((row >>> 1) ^ segment) & 15);
    const entries = sets[set];
    const position = entries.indexOf(tag);
    if (position >= 0) entries.splice(position, 1);
    else {
      misses++;
      if (entries.length === 8) entries.shift();
    }
    entries.push(tag);
  }
  for (let base = 0; base < height; base += stripHeight) {
    const rows = Math.min(stripHeight, height - base);
    for (let tileX = 0; tileX < width; tileX += tileWidth) {
      const tileEnd = Math.min(tileX + tileWidth, width);
      for (let dy = 0; dy < rows; dy++) {
        for (let x = tileX; x < tileEnd; x++) {
          const word = keys[(base + dy) * width + x];
          if (word === previousWord) consecutiveKeyReuse++;
          previousWord = word;
          const rowA = word >>> 21;
          const rowB = (word >>> 10) & 2047;
          const segA = (word >>> 5) & 31;
          const segB = word & 31;
          access(rowA, segA);
          access(rowA, segB);
          access(rowB, segA);
          access(rowB, segB);
        }
      }
    }
  }
  return {tileWidth, stripHeight, idealLruMisses: misses,
    consecutiveKeyReuse, pixels: keys.length};
}

const result = {
  model: '256 tags, 32 sets, 8-way LRU, RTL row/segment hash; no pinning or DDR timing',
  traversal: `${stripHeight}-row strips, output row-major within each horizontal microtile`,
  scenarios: [1, 2, 4, 8, 16, 32, 64, 128, 256, 1920].map(assess),
};
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result.scenarios));
