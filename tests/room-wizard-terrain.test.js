/**
 * RW-3 terrain helpers.
 */
'use strict';

const assert = require('assert');
const {
  isLayoutCompleteForTerrain,
  pointInPolygon,
  buildTerrainPresetPlatforms,
  doorPlatformOverlapWarnings,
  platformFullyInsidePolygon,
  fitPlatformToFootprint,
  DEFAULT_TILE,
  DEFAULT_PLATFORM_H
} = require('../js/wizard/terrain.js');

(function testLayoutComplete() {
  assert.strictEqual(isLayoutCompleteForTerrain(null), false);
  assert.strictEqual(isLayoutCompleteForTerrain({ name: '  ', id: 'R1', size: { width: 800, height: 600 }, polygon: [[0, 0], [1, 0], [0, 1]] }), false);
  const ok = {
    name: 'Test',
    id: 'R1',
    size: { width: 800, height: 600 },
    polygon: [
      [40, 40],
      [760, 40],
      [760, 560],
      [40, 560]
    ]
  };
  assert.strictEqual(isLayoutCompleteForTerrain(ok), true);
  assert.strictEqual(isLayoutCompleteForTerrain({ ...ok, id: 'RG-R1' }), true);
})();

(function testPointInPolygon() {
  const square = [
    [0, 0],
    [100, 0],
    [100, 100],
    [0, 100]
  ];
  assert.strictEqual(pointInPolygon(50, 50, square), true);
  assert.strictEqual(pointInPolygon(150, 50, square), false);
})();

(function testGroundBandPreset() {
  const room = {
    name: 'A',
    id: 'R9',
    size: { width: 1600, height: 1200 },
    polygon: [
      [32, 32],
      [1568, 32],
      [1568, 1168],
      [32, 1168]
    ],
    platforms: []
  };
  const r = buildTerrainPresetPlatforms(room, 'ground_band', { tile: DEFAULT_TILE, platformH: DEFAULT_PLATFORM_H });
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.platforms.length, 1);
  assert.strictEqual(r.platforms[0].len >= 1, true);
  const withId = { ...r.platforms[0], id: 'R9-P99' };
  assert.strictEqual(platformFullyInsidePolygon(withId, room.polygon, DEFAULT_TILE, DEFAULT_PLATFORM_H), true);
})();

(function testConcaveLFitsGroundBand() {
  const room = {
    name: 'L',
    id: 'R1',
    size: { width: 800, height: 1200 },
    polygon: [
      [0, 0],
      [600, 0],
      [600, 400],
      [200, 400],
      [200, 1000],
      [0, 1000]
    ],
    platforms: []
  };
  const r = buildTerrainPresetPlatforms(room, 'ground_band', { tile: DEFAULT_TILE, platformH: DEFAULT_PLATFORM_H });
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.platforms.length, 1);
  const withId = { ...r.platforms[0], id: 'R1-P1' };
  assert.strictEqual(platformFullyInsidePolygon(withId, room.polygon, DEFAULT_TILE, DEFAULT_PLATFORM_H), true);
})();

(function testFitPlatformShrinksLength() {
  const room = {
    name: 'Narrow',
    id: 'R2',
    size: { width: 400, height: 400 },
    polygon: [
      [0, 0],
      [400, 0],
      [400, 400],
      [0, 400]
    ],
    platforms: []
  };
  const partial = { x: 40, y: 380, len: 20, tint: 0 };
  const f = fitPlatformToFootprint(room, partial, DEFAULT_TILE, DEFAULT_PLATFORM_H);
  assert.ok(f);
  assert.ok(f.len < partial.len);
  assert.strictEqual(platformFullyInsidePolygon({ ...f, id: 'x' }, room.polygon, DEFAULT_TILE, DEFAULT_PLATFORM_H), true);
})();

(function testDoorPlatformWarning() {
  const room = {
    name: 'A',
    id: 'R1',
    size: { width: 400, height: 400 },
    polygon: [
      [0, 0],
      [400, 0],
      [400, 400],
      [0, 400]
    ],
    platforms: [{ id: 'R1-P1', x: 100, y: 200, len: 4, tint: 0 }],
    doors: [{ id: 'R1-D1', x: 120, y: 195 }]
  };
  const w = doorPlatformOverlapWarnings(room, DEFAULT_TILE, DEFAULT_PLATFORM_H);
  assert.ok(w.length >= 1);
})();

console.log('room-wizard-terrain.test.js: all assertions passed');
