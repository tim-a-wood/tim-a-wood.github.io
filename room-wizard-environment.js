/**
 * RW-4 Environment — room theme + tags (authoring metadata for export / future visuals).
 */
'use strict';

const ENVIRONMENT_SCHEMA_VERSION = 1;
const DEFAULT_THEME_ID = 'cave';

/** @type {{ id: string, label: string }[]} */
const THEME_PRESETS = [
  { id: 'cave', label: 'Cave / hollow' },
  { id: 'ruins', label: 'Ruins' },
  { id: 'forest', label: 'Forest / overgrowth' },
  { id: 'shrine', label: 'Shrine / temple' },
  { id: 'sewer', label: 'Sewer / underworks' },
  { id: 'void', label: 'Void / ethereal' },
  { id: 'custom', label: 'Custom (tags only)' }
];

/**
 * @param {string} raw
 * @returns {string[]}
 */
function parseTagsInput(raw) {
  if (raw == null || String(raw).trim() === '') return [];
  return String(raw)
    .split(/[,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * @param {string[]} tags
 * @returns {string}
 */
function tagsToInputString(tags) {
  if (!Array.isArray(tags) || tags.length === 0) return '';
  return tags.join(', ');
}

/**
 * @param {object} room
 * @returns {{ version: number, themeId: string, tags: string[] } | null}
 */
function ensureRoomEnvironment(room) {
  if (!room || typeof room !== 'object') return null;
  if (!room.environment || typeof room.environment !== 'object') {
    room.environment = {
      version: ENVIRONMENT_SCHEMA_VERSION,
      themeId: DEFAULT_THEME_ID,
      tags: []
    };
  }
  const e = room.environment;
  if (e.version == null) e.version = ENVIRONMENT_SCHEMA_VERSION;
  if (typeof e.themeId !== 'string' || !e.themeId.trim()) {
    e.themeId = DEFAULT_THEME_ID;
  }
  if (!Array.isArray(e.tags)) e.tags = [];
  e.tags = e.tags.map((t) => String(t).trim()).filter(Boolean);
  return e;
}

/**
 * Layout must be complete before Environment phase (same gate as platform tools).
 * @param {object} room
 * @returns {boolean}
 */
function isEnvironmentPhaseUnlocked(room) {
  const mod = typeof globalThis !== 'undefined' ? globalThis.RoomWizardTerrain : null;
  if (!mod || typeof mod.isLayoutCompleteForTerrain !== 'function') return false;
  return mod.isLayoutCompleteForTerrain(room);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    ENVIRONMENT_SCHEMA_VERSION,
    DEFAULT_THEME_ID,
    THEME_PRESETS,
    parseTagsInput,
    tagsToInputString,
    ensureRoomEnvironment,
    isEnvironmentPhaseUnlocked
  };
}
if (typeof globalThis !== 'undefined') {
  globalThis.RoomWizardEnvironment = {
    ENVIRONMENT_SCHEMA_VERSION,
    DEFAULT_THEME_ID,
    THEME_PRESETS,
    parseTagsInput,
    tagsToInputString,
    ensureRoomEnvironment,
    isEnvironmentPhaseUnlocked
  };
}
