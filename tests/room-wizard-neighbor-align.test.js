/**
 * RW-2 neighbor alignment helpers.
 */
'use strict';

const assert = require('assert');
const {
  computeAlignedGlobal,
  computeHatchHeightDelta,
  getEdgeSegmentLocal,
  edgeOrientation,
  localToWorld,
  ROOM_WIZARD_NEIGHBOR_SCALE
} = require('../room-wizard-neighbor-align.js');

const S = ROOM_WIZARD_NEIGHBOR_SCALE;

function axisRoom(id, W, H, inset, gx, gy) {
  const m = inset;
  return {
    id,
    global: { x: gx, y: gy },
    size: { width: W, height: H },
    polygon: [
      [m, m],
      [W - m, m],
      [W - m, H - m],
      [m, H - m]
    ],
    doors: []
  };
}

(function testVerticalFlushLeftToRight() {
  const B = axisRoom('B', 1000, 800, 100, 0, 0);
  const A = axisRoom('A', 1000, 800, 100, 200, 50);
  const r = computeAlignedGlobal(A, B, 3, 1, S);
  assert.strictEqual(r.ok, true);
  assert.ok(r.global);
  assert.ok(Math.abs(r.global.x - 96) < 1e-6, `expected x≈96, got ${r.global.x}`);
  assert.ok(Math.abs(r.global.y - 0) < 1e-6, `expected y≈0, got ${r.global.y}`);
})();

(function testHorizontalFlushBottomToTop() {
  const B = axisRoom('B', 800, 600, 80, 10, 20);
  const A = axisRoom('A', 800, 600, 80, 0, 0);
  const r = computeAlignedGlobal(A, B, 0, 2, S);
  assert.strictEqual(r.ok, true);
  const segB = getEdgeSegmentLocal(B, 2);
  assert.strictEqual(edgeOrientation(segB), 'horizontal');
  const worldYB = localToWorld(B.global, B.size, segB.start.x, segB.start.y, S).y;
  const segA = getEdgeSegmentLocal(A, 0);
  const worldYA = localToWorld(r.global, A.size, segA.start.x, segA.start.y, S).y;
  assert.ok(Math.abs(worldYA - worldYB) < 1e-5);
})();

(function testNonParallelEdges() {
  const A = axisRoom('A', 800, 600, 80, 0, 0);
  const B = axisRoom('B', 800, 600, 80, 100, 0);
  const r = computeAlignedGlobal(A, B, 0, 1, S);
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.reason, 'edges_not_parallel');
})();

(function testParallelDiagonalEdges() {
  const roomA = {
    id: 'A',
    global: { x: 0, y: 0 },
    size: { width: 400, height: 400 },
    polygon: [
      [0, 0],
      [200, 100],
      [0, 200],
      [-200, 100]
    ],
    doors: []
  };
  const roomB = {
    id: 'B',
    global: { x: 50, y: 25 },
    size: { width: 400, height: 400 },
    polygon: [
      [0, 0],
      [100, 50],
      [0, 100],
      [-100, 50]
    ],
    doors: []
  };
  const r = computeAlignedGlobal(roomA, roomB, 0, 0, S);
  assert.strictEqual(r.ok, true);
  assert.ok(r.global && Number.isFinite(r.global.x));
})();

(function testHatchDeltaVertical() {
  const B = axisRoom('B', 1000, 800, 100, 0, 0);
  B.doors = [{ x: 900, y: 400 }];
  const A = axisRoom('A', 1000, 800, 100, 96, 0);
  A.doors = [{ x: 100, y: 500 }];
  const d = computeHatchHeightDelta(A, B, 3, 1, S);
  const yA = localToWorld(A.global, A.size, 100, 500, S).y;
  const yB = localToWorld(B.global, B.size, 900, 400, S).y;
  assert.ok(Math.abs(d.deltaX) < 1e-9);
  assert.ok(Math.abs(d.deltaY - (yB - yA)) < 1e-5);
})();

(function testHatchHorizontalNoDoorsMidpointFallback() {
  const A = axisRoom('A', 1000, 800, 100, 0, 0);
  const B = axisRoom('B', 1000, 800, 100, 200, 0);
  const d = computeHatchHeightDelta(A, B, 2, 2, S);
  assert.ok(Math.abs(d.deltaX - 200) < 1e-5, `deltaX ${d.deltaX}`);
  assert.ok(Math.abs(d.deltaY) < 1e-9);
})();

(function testHatchVerticalNoDoorsMidpointFallback() {
  const A = axisRoom('A', 1000, 800, 100, 0, 0);
  const B = axisRoom('B', 1000, 800, 100, 0, 80);
  const d = computeHatchHeightDelta(A, B, 1, 3, S);
  assert.ok(Math.abs(d.deltaX) < 1e-9);
  assert.ok(Math.abs(d.deltaY - 80) < 1e-5, `deltaY ${d.deltaY}`);
})();

(function testHatchAlreadyAlignedMidpoints() {
  const A = axisRoom('A', 1000, 800, 100, 0, 0);
  const B = axisRoom('B', 1000, 800, 100, 0, 0);
  const d = computeHatchHeightDelta(A, B, 1, 3, S);
  assert.strictEqual(d.reason, 'already_aligned');
})();

console.log('room-wizard-neighbor-align.test.js: all assertions passed');
