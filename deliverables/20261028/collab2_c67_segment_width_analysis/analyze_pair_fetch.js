const fs = require('fs');

const [tracePath, outputPath] = process.argv.slice(2);
if (!tracePath || !outputPath) {
  throw new Error('usage: node analyze_pair_fetch.js map_keys.hex result.json');
}
const width = 1920;
const height = 1080;
const words = Uint32Array.from(fs.readFileSync(tracePath, 'ascii').trimEnd()
  .split(/\r?\n/), line => Number.parseInt(line, 16));
if (words.length !== width * height) throw new Error(`bad trace: ${words.length}`);

function assess(prefetchPair) {
  const sets = Array.from({length: 32}, () => []);
  let commands = 0;
  let beats = 0;
  let demandedMisses = 0;
  let usefulPrefetches = 0;
  let wastedPrefetches = 0;
  function locate(row, seg) {
    const tag = row * 32 + seg;
    const set = ((row & 1) << 4) | (((row >>> 1) ^ seg) & 15);
    const ways = sets[set];
    return {tag, ways, index: ways.indexOf(tag)};
  }
  function insert(row, seg) {
    const {tag, ways, index} = locate(row, seg);
    if (index >= 0) ways.splice(index, 1);
    else if (ways.length === 8) ways.shift();
    ways.push(tag);
  }
  function access(row, seg) {
    const hit = locate(row, seg);
    if (hit.index >= 0) {
      hit.ways.splice(hit.index, 1);
      hit.ways.push(hit.tag);
      return;
    }
    demandedMisses++;
    commands++;
    beats += 8;
    insert(row, seg);
    if (!prefetchPair) return;
    const neighbor = seg ^ 1;
    if (neighbor > 14) return;
    if (locate(row, neighbor).index >= 0) {
      wastedPrefetches++;
      return;
    }
    beats += 8;
    usefulPrefetches++;
    insert(row, neighbor);
  }
  for (let base = 0; base < height; base += 16) {
    const rows = Math.min(16, height - base);
    for (let tileX = 0; tileX < width; tileX += 64) {
      for (let dy = 0; dy < rows; dy++) {
        for (let x = tileX; x < Math.min(tileX + 64, width); x++) {
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
  return {prefetchPair, commands, payloadBeats256: beats,
    demandedMisses, usefulPrefetches, wastedPrefetches};
}

const result = {
  model: '256 tags, 8-way LRU, 16-line strips, 64-pixel microtiles; pair fills two independent cache entries',
  scenarios: [assess(false), assess(true)],
};
fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result.scenarios));
