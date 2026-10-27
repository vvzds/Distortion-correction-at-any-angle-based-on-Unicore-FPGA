const fs = require('fs');

const [tracePath, outputPath] = process.argv.slice(2);
if (!tracePath || !outputPath) {
  throw new Error('usage: node analyze_segment_width.js map_keys.hex result.json');
}
const width = 1920;
const height = 1080;
const stripHeight = 16;
const tileWidth = 64;
const words = Uint32Array.from(fs.readFileSync(tracePath, 'ascii').trimEnd()
  .split(/\r?\n/), line => Number.parseInt(line, 16));
if (words.length !== width * height) throw new Error(`bad trace: ${words.length}`);

function simulate(segmentPixels, capacityTags) {
  const factor = segmentPixels / 128;
  const setsCount = capacityTags / 8;
  const hashBits = Math.log2(setsCount) - 1;
  const hashMask = (1 << hashBits) - 1;
  const sets = Array.from({length: setsCount}, () => []);
  let loads = 0;
  let lastTag = -1;
  let consecutiveReuse = 0;
  function access(row, oldSegment) {
    const segment = oldSegment / factor | 0;
    const tag = row * (32 / factor) + segment;
    if (tag === lastTag) consecutiveReuse++;
    lastTag = tag;
    const set = ((row & 1) << hashBits) |
      (((row >>> 1) ^ segment) & hashMask);
    const ways = sets[set];
    const hit = ways.indexOf(tag);
    if (hit >= 0) ways.splice(hit, 1);
    else {
      loads++;
      if (ways.length === 8) ways.shift();
    }
    ways.push(tag);
  }
  for (let base = 0; base < height; base += stripHeight) {
    const rows = Math.min(stripHeight, height - base);
    for (let tileX = 0; tileX < width; tileX += tileWidth) {
      for (let dy = 0; dy < rows; dy++) {
        for (let x = tileX; x < Math.min(tileX + tileWidth, width); x++) {
          const word = words[(base + dy) * width + x];
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
  return {segmentPixels, capacityTags, cacheBytes: segmentPixels * 2 * capacityTags,
    idealLruLoads: loads, payloadBeats256: loads * segmentPixels / 16,
    consecutiveReuse};
}

const result = {
  model: '8-way LRU, row/segment XOR set hash; 16-line strips and 64-pixel tiles',
  scenarios: [128, 256, 512].flatMap(segmentPixels =>
    [65536, 131072, 262144].map(cacheBytes =>
      simulate(segmentPixels, cacheBytes / (segmentPixels * 2)))),
};
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result.scenarios));
