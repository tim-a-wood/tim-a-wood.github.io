'use strict';

/**
 * Contract checks for room-layout-editor alignment fixes (layout canvas vs Environment overlay).
 * Reads static HTML; does not execute the editor.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'room-layout-editor.html'), 'utf8');

function readRoomEditorChunkBundle() {
  const ed = path.join(__dirname, '..', 'js/editor');
  let s = '';
  for (let i = 0; i < 20; i += 1) {
    const f = path.join(ed, `chunk-${i}.js`);
    if (!fs.existsSync(f)) break;
    const t = fs.readFileSync(f, 'utf8');
    const m = t.match(/push\((.*)\);\s*$/s);
    if (!m) continue;
    s += JSON.parse(m[1]);
  }
  return s;
}

const editorJs = readRoomEditorChunkBundle();

(function testUniformRoomScaleUsesMinOfAxes() {
  assert.ok(
    editorJs.includes('Math.min(scaleX, scaleY)'),
    'roomScale should letterbox with uniform scale (min of axis scales)'
  );
  assert.ok(
    editorJs.includes('scaleUniform'),
    'roomScale should name uniform scale for clarity'
  );
})();

(function testOverlayBoundsPrefersSemanticsAndRoomHint() {
  assert.ok(
    editorJs.includes('semanticsRoomSize'),
    'roomWizardOverlayBounds should read room_semantics.room_size'
  );
  assert.ok(
    editorJs.includes('roomWizardOverlayBounds(envState, getRoomWizardRoom())'),
    'overlay bounds should receive current wizard room for authoritative size'
  );
  assert.ok(
    editorJs.includes('Math.max(...arr) - Math.min(...arr)'),
    'fallback width/height should use polygon span when needed'
  );
})();

(function testOverlayCopyExplainsLayers() {
  assert.ok(
    typeof editorJs === 'string' && editorJs.includes('function renderRoomWizardResultsOverlay'),
    'Environment results overlay renderer should remain in editor bundle'
  );
})();
