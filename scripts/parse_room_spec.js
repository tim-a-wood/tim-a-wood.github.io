/**
 * Parses room_spec_ascii.txt and outputs ledges + key/start positions for 1000×600 world.
 * Usage: node scripts/parse_room_spec.js
 */

const fs = require('fs');
const path = require('path');

const TILE = 32;
const W = 1000;
const H = 600;
const SPEC_W = 90;
const SPEC_H = 28;

const specPath = path.join(__dirname, '../prompts/room_spec_ascii.txt');
const raw = fs.readFileSync(specPath, 'utf8');
const lines = raw.split('\n').filter(Boolean);

// Normalize each line to SPEC_W chars; treat # as solid, else empty. Capture G and S.
let keyPos = null;
let startPos = null;
const grid = [];
for (let r = 0; r < lines.length; r++) {
    let line = lines[r];
    if (line.length > SPEC_W) line = line.slice(0, SPEC_W);
    while (line.length < SPEC_W) line += (r === 0 || r === SPEC_H - 1) ? '#' : '.';
    const row = [];
    for (let c = 0; c < SPEC_W; c++) {
        const ch = line[c] || '.';
        if (ch === 'G') keyPos = { row: r, col: c };
        if (ch === 'S') startPos = { row: r, col: c };
        row.push(ch === '#' || ch === 'G' || ch === '[' || ch === ']' ? 1 : 0);
    }
    grid.push(row);
}

// Reduce to tile grid: 31 cols (W/TILE), rows 1 to 26 (skip ceiling 0 and floor 27)
const nTileCols = Math.floor(W / TILE); // 31
const nContentRows = SPEC_H - 2; // 26

function tileSolid(row, tileCol) {
    const c0 = (tileCol * SPEC_W) / nTileCols;
    const c1 = ((tileCol + 1) * SPEC_W) / nTileCols;
    for (let c = Math.floor(c0); c < Math.ceil(c1) && c < SPEC_W; c++) {
        if (grid[row][c] === 1) return true;
    }
    return false;
}

const ledges = [];
const CORRIDOR_Y = 500;

// Helper: get horizontal runs of solid tiles for a spec row
function getRuns(specRow) {
    const runs = [];
    let runStart = null;
    for (let t = 0; t < nTileCols; t++) {
        const solid = tileSolid(specRow, t);
        if (solid && runStart === null) runStart = t;
        if (!solid && runStart !== null) {
            runs.push({ start: runStart, len: t - runStart });
            runStart = null;
        }
    }
    if (runStart !== null) runs.push({ start: runStart, len: nTileCols - runStart });
    return runs;
}

// 1. Corridor first (spec row 26 = index 26 = start/corridor row)
ledges.push({ x: 0, y: CORRIDOR_Y, len: 8, tint: 0 });
// Rest of bottom platform (row 26) to the right of corridor
ledges.push({ x: 8 * TILE, y: CORRIDOR_Y, len: nTileCols - 8, tint: 0 });

// 2. Content rows 1..25 (platforms at various heights)
for (let specRow = 1; specRow <= 25; specRow++) {
    const y = 100 + Math.floor((specRow - 1) * (380 / 25));
    const runs = getRuns(specRow);
    for (const run of runs) {
        const x = run.start * TILE;
        const tint = specRow % 5;
        ledges.push({ x, y, len: run.len, tint });
    }
}

// Key: [ G ] is at spec row 2; platform below is row 3 (#######)
const keyLedgeY = 100 + Math.floor(3 * (380 / 25)); // platform center y
const keyX = keyPos ? Math.round((keyPos.col / SPEC_W) * W) : 820;
const keyY = keyLedgeY - 7 - 12; // above platform for pickup

// Start on corridor
const startX = 128;
const startY = CORRIDOR_Y - 7 - 20; // platform top minus half player

console.log(JSON.stringify({
    ledges,
    key: { x: keyX, y: Math.round(keyY) },
    relic: { x: 256, y: 436 },
    start: { x: startX, y: Math.round(startY) }
}, null, 2));
