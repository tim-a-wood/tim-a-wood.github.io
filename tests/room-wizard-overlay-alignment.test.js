'use strict';

/**
 * Contract checks for room-layout-editor alignment fixes (layout canvas vs Environment overlay).
 * Reads static HTML; does not execute the editor.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'room-layout-editor.html'), 'utf8');

(function testUniformRoomScaleUsesMinOfAxes() {
  assert.ok(
    html.includes('Math.min(scaleX, scaleY)'),
    'roomScale should letterbox with uniform scale (min of axis scales)'
  );
  assert.ok(
    html.includes('scaleUniform'),
    'roomScale should name uniform scale for clarity'
  );
})();

(function testOverlayBoundsPrefersSemanticsAndRoomHint() {
  assert.ok(
    html.includes('semanticsRoomSize'),
    'roomWizardOverlayBounds should read room_semantics.room_size'
  );
  assert.ok(
    html.includes('roomWizardOverlayBounds(envState, getRoomWizardRoom())'),
    'overlay bounds should receive current wizard room for authoritative size'
  );
  assert.ok(
    html.includes('Math.max(...arr) - Math.min(...arr)'),
    'fallback width/height should use polygon span when needed'
  );
})();

(function testOverlayCopyExplainsLayers() {
  assert.ok(
    html.includes('cyan outline matches your polygon'),
    'Layout overlay copy should explain footprint vs structural slots'
  );
})();
