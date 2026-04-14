'use strict';

/**
 * Contract checks for room-layout-editor alignment fixes (layout canvas vs Environment overlay).
 * Reads static HTML; does not execute the editor.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'room-layout-editor.html'), 'utf8');

function readRoomEditorModuleBundle() {
  const ed = path.join(__dirname, '..', 'js/editor');
  if (!fs.existsSync(ed)) return '';
  const files = fs.readdirSync(ed).filter((f) => f.endsWith('.js')).sort();
  return files.map((f) => fs.readFileSync(path.join(ed, f), 'utf8')).join('\n');
}

const editorJs = readRoomEditorModuleBundle();

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
