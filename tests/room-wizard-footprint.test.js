/**
 * Unit tests for room-layout-wizard-footprint.js
 */
const assert = require('assert');
const { applyAxisAlignedFootprint, ROOM_WIZARD_FOOTPRINT_MARGIN } = require('../js/wizard/footprint.js');

const room = { size: {}, polygon: [] };
applyAxisAlignedFootprint(room, 1600, 1200);
assert.strictEqual(room.size.width, 1600);
assert.strictEqual(room.size.height, 1200);
assert.strictEqual(room.polygon.length, 4);
assert.strictEqual(room.polygon[0][0], ROOM_WIZARD_FOOTPRINT_MARGIN);

const room2 = { size: {}, polygon: [] };
applyAxisAlignedFootprint(room2, 400, 400, 40);
assert.strictEqual(room2.polygon[0][0], 40);

console.log('room-wizard-footprint.test.js: all assertions passed');
