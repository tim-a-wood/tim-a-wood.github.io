'use strict';

const assert = require('assert');
const {
  stripJsonFences,
  normalizeCopilotPayload,
  applyCopilotPayloadToRoom
} = require('../room-wizard-environment-copilot.js');

assert.strictEqual(stripJsonFences('```json\n{"a":1}\n```'), '{"a":1}');
assert.strictEqual(stripJsonFences('{"themeId":"cave"}'), '{"themeId":"cave"}');

const ok = normalizeCopilotPayload({
  themeId: 'void',
  tags: ['cold', 'echo'],
  rationale: 'Echoing space.'
});
assert.strictEqual(ok.themeId, 'void');
assert.deepStrictEqual(ok.tags, ['cold', 'echo']);
assert.ok(ok.rationale.includes('Echo'));

const fallback = normalizeCopilotPayload({ themeId: 'unknown-x', tags: ['a'] });
assert.strictEqual(fallback.themeId, 'custom');
assert.deepStrictEqual(fallback.tags, ['a']);

const room = { id: 'R1', environment: { version: 1, themeId: 'cave', tags: [] } };
applyCopilotPayloadToRoom(
  room,
  { themeId: 'sewer', tags: ['wet'] },
  { ensureRoomEnvironment: require('../room-wizard-environment.js').ensureRoomEnvironment }
);
assert.strictEqual(room.environment.themeId, 'sewer');
assert.deepStrictEqual(room.environment.tags, ['wet']);

console.log('room-wizard-environment-copilot.test.js: all assertions passed');
