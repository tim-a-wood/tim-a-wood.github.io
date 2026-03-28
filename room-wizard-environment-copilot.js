/**
 * RW-4b — Environment Copilot: validate/merge AI JSON into room.environment (browser + Node tests).
 */
'use strict';

/** @type {string[]} */
const COPILOT_ALLOWED_THEME_IDS = [
  'cave',
  'ruins',
  'forest',
  'shrine',
  'sewer',
  'void',
  'custom'
];

/**
 * Strip markdown code fences some models wrap JSON in.
 * @param {string} raw
 * @returns {string}
 */
function stripJsonFences(raw) {
  let s = String(raw).trim();
  if (s.startsWith('```')) {
    s = s.replace(/^```(?:json)?\s*/i, '');
    s = s.replace(/\s*```\s*$/i, '');
  }
  return s.trim();
}

/**
 * @param {unknown} parsed
 * @returns {{ themeId: string, tags: string[], rationale: string }}
 */
function normalizeCopilotPayload(parsed) {
  if (!parsed || typeof parsed !== 'object') {
    throw new Error('Copilot response must be a JSON object.');
  }
  const o = /** @type {Record<string, unknown>} */ (parsed);
  let themeId = typeof o.themeId === 'string' ? o.themeId.trim().toLowerCase() : '';
  if (!themeId || !COPILOT_ALLOWED_THEME_IDS.includes(themeId)) {
    themeId = 'custom';
  }
  let tags = [];
  if (Array.isArray(o.tags)) {
    tags = o.tags
      .map((t) => String(t).trim().toLowerCase())
      .filter(Boolean)
      .slice(0, 16);
  }
  const rationale =
    typeof o.rationale === 'string' && o.rationale.trim() ? o.rationale.trim() : '';
  return { themeId, tags, rationale };
}

/**
 * @param {object} room
 * @param {{ themeId: string, tags: string[], rationale?: string }} payload
 * @param {{ ensureRoomEnvironment: (r: object) => object }} envApi
 */
function applyCopilotPayloadToRoom(room, payload, envApi) {
  if (!room || typeof room !== 'object') return;
  const ensure = envApi && envApi.ensureRoomEnvironment;
  if (typeof ensure !== 'function') return;
  ensure(room);
  room.environment.themeId = payload.themeId;
  room.environment.tags = Array.isArray(payload.tags) ? [...payload.tags] : [];
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    COPILOT_ALLOWED_THEME_IDS,
    stripJsonFences,
    normalizeCopilotPayload,
    applyCopilotPayloadToRoom
  };
}
if (typeof globalThis !== 'undefined') {
  globalThis.RoomWizardEnvironmentCopilot = {
    COPILOT_ALLOWED_THEME_IDS,
    stripJsonFences,
    normalizeCopilotPayload,
    applyCopilotPayloadToRoom
  };
}
