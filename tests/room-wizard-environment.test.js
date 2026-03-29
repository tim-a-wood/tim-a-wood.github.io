/**
 * RW-4 environment helpers.
 */
'use strict';

const assert = require('assert');
const {
  parseTagsInput,
  tagsToInputString,
  ensureRoomEnvironment,
  getThemeLabel,
  buildEnvironmentPreviewModel,
  THEME_PRESETS,
  DEFAULT_THEME_ID
} = require('../room-wizard-environment.js');
const { buildRuntimeRoom, normalizeRuntimeEnvironment } = require('../room-layout-export-package.js');

(function testParseTags() {
  assert.deepStrictEqual(parseTagsInput('a, b; c'), ['a', 'b', 'c']);
  assert.deepStrictEqual(parseTagsInput(''), []);
})();

(function testTagsRoundTrip() {
  const tags = ['wet', 'cold'];
  assert.strictEqual(tagsToInputString(tags), 'wet, cold');
})();

(function testEnsureRoomEnvironment() {
  const room = { id: 'R1' };
  const e = ensureRoomEnvironment(room);
  assert.strictEqual(e.version, 2);
  assert.strictEqual(e.themeId, DEFAULT_THEME_ID);
  assert.deepStrictEqual(e.tags, []);
  assert.ok(e.spec);
  assert.ok(e.spec.components);
  assert.ok(e.spec.components.floor);
  assert.ok(e.spec.scene_schema);
  assert.ok(e.spec.scene_schema.kit);
  assert.ok(e.preview);
  assert.ok(e.template_context);
  assert.ok(e.runtime);
  assert.strictEqual(room.environment, e);
})();

(function testExportNormalize() {
  assert.deepStrictEqual(normalizeRuntimeEnvironment({}), { version: 1, themeId: 'cave', tags: [], spec: {}, preview: {}, runtime: {} });
  assert.deepStrictEqual(
    normalizeRuntimeEnvironment({
      environment: { version: 1, themeId: 'ruins', tags: ['x'] }
    }),
    { version: 1, themeId: 'ruins', tags: ['x'], spec: {}, preview: {}, runtime: {} }
  );
})();

(function testBuildRuntimeRoomIncludesEnvironment() {
  const br = buildRuntimeRoom({
    id: 'R1',
    name: 'A',
    polygon: [],
    size: { width: 100, height: 100 },
    global: { x: 0, y: 0 },
    platforms: [],
    doors: [],
    keys: [],
    abilities: [],
    movingPlatforms: [],
    playerStart: null,
    edgeLinks: []
  });
  assert.ok(br.environment);
  assert.strictEqual(br.environment.themeId, 'cave');
})();

(function testThemePresets() {
  assert.ok(THEME_PRESETS.some((p) => p.id === 'cave'));
})();

(function testThemeLabelLookup() {
  assert.strictEqual(getThemeLabel('forest'), 'Forest / overgrowth');
  assert.strictEqual(getThemeLabel('missing-theme'), 'Cave / hollow');
})();

(function testBuildEnvironmentPreviewModel() {
  const preview = buildEnvironmentPreviewModel('void', ['cold', 'echoing'], 'Sparse and unreal.');
  assert.strictEqual(preview.themeId, 'void');
  assert.strictEqual(preview.themeLabel, 'Void / ethereal');
  assert.deepStrictEqual(preview.tags, ['cold', 'echoing']);
  assert.strictEqual(preview.sceneClass, 'rw-environment-scene--void');
})();

console.log('room-wizard-environment.test.js: all assertions passed');
