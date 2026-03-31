/**
 * RW-4 Environment — room theme + tags (authoring metadata for export / future visuals).
 */
'use strict';

const ENVIRONMENT_SCHEMA_VERSION = 1;
const ENVIRONMENT_RENDER_SCHEMA_VERSION = 2;
const DEFAULT_THEME_ID = 'cave';
const ENVIRONMENT_COMPONENTS = [
  ['floor', 'Floor'],
  ['platforms', 'Platforms'],
  ['walls', 'Walls'],
  ['doors', 'Doors'],
  ['background', 'Background']
];

function defaultEnvironmentComponents(description = '') {
  const base = String(description || '').trim() || 'Keep this room aligned to the current project art direction.';
  return {
    floor: { label: 'Floor', prompt: `${base} Describe the floor surface, pattern, wear, cracks, and traversal readability.` },
    platforms: { label: 'Platforms', prompt: `${base} Describe platform tops, faces, edge damage, supports, and ledge readability.` },
    walls: { label: 'Walls', prompt: `${base} Describe the wall structure, repeating architecture, depth, and damage.` },
    doors: { label: 'Doors', prompt: `${base} Describe the doorway treatment, frame, gate material, and motifs.` },
    background: { label: 'Background', prompt: `${base} Describe the background and midground architecture, silhouettes, depth, and atmosphere.` }
  };
}

function ensureEnvironmentComponents(spec) {
  if (!spec.components || typeof spec.components !== 'object') {
    spec.components = {};
  }
  const fallback = defaultEnvironmentComponents(spec.description || '');
  ENVIRONMENT_COMPONENTS.forEach(([key, label]) => {
    const item = spec.components[key];
    if (!item || typeof item !== 'object') {
      spec.components[key] = { ...fallback[key] };
      return;
    }
    if (typeof item.label !== 'string' || !item.label.trim()) item.label = label;
    if (typeof item.prompt !== 'string' || !item.prompt.trim()) item.prompt = fallback[key].prompt;
  });
}

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

const THEME_PREVIEW_COPY = {
  cave: {
    eyebrow: 'Stone and shadow',
    summary: 'A compressed chamber with damp stone, soft echo, and narrow pools of light.',
    defaults: ['damp', 'echoing', 'stone']
  },
  ruins: {
    eyebrow: 'Broken masonry',
    summary: 'Collapsed architecture, old dust, and fractured sightlines through age-worn walls.',
    defaults: ['crumbled', 'ancient', 'dusty']
  },
  forest: {
    eyebrow: 'Overgrowth and mist',
    summary: 'Root-tangled ground, soft moisture, and filtered light pushing through growth.',
    defaults: ['overgrown', 'mossy', 'misty']
  },
  shrine: {
    eyebrow: 'Ritual stillness',
    summary: 'Ordered stone, faint sacred glow, and a calm surface hiding latent danger.',
    defaults: ['sacred', 'still', 'glowing']
  },
  sewer: {
    eyebrow: 'Runoff and pressure',
    summary: 'Low channels, slick surfaces, and stale air carrying movement through the dark.',
    defaults: ['wet', 'stagnant', 'industrial']
  },
  void: {
    eyebrow: 'Unreal space',
    summary: 'Thin geometry, distant drift, and unstable light with more atmosphere than mass.',
    defaults: ['ethereal', 'cold', 'weightless']
  },
  custom: {
    eyebrow: 'Mixed signals',
    summary: 'A custom mood blend shaped more by tags than by a single preset atmosphere.',
    defaults: ['custom', 'hybrid', 'moody']
  }
};

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
 * @param {string} themeId
 * @returns {string}
 */
function getThemeLabel(themeId) {
  const match = THEME_PRESETS.find((preset) => preset.id === themeId);
  return match ? match.label : THEME_PRESETS.find((preset) => preset.id === DEFAULT_THEME_ID).label;
}

/**
 * @param {string} themeId
 * @param {string[]} tags
 * @param {string=} rationale
 * @returns {{
 *   themeId: string,
 *   themeLabel: string,
 *   eyebrow: string,
 *   summary: string,
 *   rationale: string,
 *   tags: string[],
 *   sceneClass: string
 * }}
 */
function buildEnvironmentPreviewModel(themeId, tags, rationale) {
  const normalizedThemeId =
    typeof themeId === 'string' && THEME_PREVIEW_COPY[themeId] ? themeId : DEFAULT_THEME_ID;
  const copy = THEME_PREVIEW_COPY[normalizedThemeId] || THEME_PREVIEW_COPY[DEFAULT_THEME_ID];
  const cleanedTags = Array.isArray(tags)
    ? tags.map((tag) => String(tag).trim()).filter(Boolean).slice(0, 6)
    : [];
  return {
    themeId: normalizedThemeId,
    themeLabel: getThemeLabel(normalizedThemeId),
    eyebrow: copy.eyebrow,
    summary: copy.summary,
    rationale: typeof rationale === 'string' ? rationale.trim() : '',
    tags: cleanedTags.length ? cleanedTags : copy.defaults.slice(),
    sceneClass: `rw-environment-scene--${normalizedThemeId}`
  };
}

/**
 * @param {object} room
 * @returns {{ version: number, themeId: string, tags: string[] } | null}
 */
function ensureRoomEnvironment(room) {
  if (!room || typeof room !== 'object') return null;
  if (!room.environment || typeof room.environment !== 'object') {
    room.environment = {
      version: ENVIRONMENT_RENDER_SCHEMA_VERSION,
      themeId: DEFAULT_THEME_ID,
      tags: [],
      spec: {},
      preview: {},
      template_context: {},
      runtime: {}
    };
  }
  const e = room.environment;
  if (e.version == null) e.version = ENVIRONMENT_RENDER_SCHEMA_VERSION;
  if (typeof e.themeId !== 'string' || !e.themeId.trim()) {
    e.themeId = DEFAULT_THEME_ID;
  }
  if (!Array.isArray(e.tags)) e.tags = [];
  e.tags = e.tags.map((t) => String(t).trim()).filter(Boolean);
  if (!e.spec || typeof e.spec !== 'object') e.spec = {};
  if (!e.preview || typeof e.preview !== 'object') e.preview = {};
  if (!e.template_context || typeof e.template_context !== 'object') e.template_context = {};
  if (!e.runtime || typeof e.runtime !== 'object') e.runtime = {};
  if (typeof e.spec.theme_id !== 'string' || !e.spec.theme_id.trim()) e.spec.theme_id = e.themeId;
  if (!Array.isArray(e.spec.tags)) e.spec.tags = [...e.tags];
  if (typeof e.spec.description !== 'string') e.spec.description = '';
  if (typeof e.spec.mood !== 'string') e.spec.mood = '';
  if (typeof e.spec.lighting !== 'string') e.spec.lighting = '';
  if (typeof e.spec.fog !== 'string') e.spec.fog = '';
  if (!Array.isArray(e.spec.materials)) e.spec.materials = [];
  if (!Array.isArray(e.spec.landmarks)) e.spec.landmarks = [];
  if (!Array.isArray(e.spec.hazards)) e.spec.hazards = [];
  if (typeof e.spec.composition_focus !== 'string') e.spec.composition_focus = '';
  if (!Array.isArray(e.spec.readability_notes)) e.spec.readability_notes = [];
  ensureEnvironmentComponents(e.spec);
  if (!e.spec.scene_schema || typeof e.spec.scene_schema !== 'object') e.spec.scene_schema = {};
  if (!Array.isArray(e.spec.scene_schema.background_layers)) e.spec.scene_schema.background_layers = [];
  if (!Array.isArray(e.spec.scene_schema.set_dressing)) e.spec.scene_schema.set_dressing = [];
  if (!e.spec.scene_schema.effects || typeof e.spec.scene_schema.effects !== 'object') e.spec.scene_schema.effects = {};
  if (!e.spec.scene_schema.kit || typeof e.spec.scene_schema.kit !== 'object') e.spec.scene_schema.kit = {};
  if (typeof e.preview.status !== 'string') e.preview.status = 'idle';
  if (typeof e.preview.render_level !== 'string' && e.preview.render_level !== null) e.preview.render_level = null;
  if (!Array.isArray(e.preview.images)) e.preview.images = [];
  if (typeof e.preview.approved_image_id !== 'string' && e.preview.approved_image_id !== null) {
    e.preview.approved_image_id = null;
  }
  if (typeof e.preview.fallback_reason !== 'string' && e.preview.fallback_reason !== null) {
    e.preview.fallback_reason = null;
  }
  if (typeof e.preview.last_generated_at !== 'string' && e.preview.last_generated_at !== null) {
    e.preview.last_generated_at = null;
  }
  if (typeof e.preview.approved_palette !== 'object' && e.preview.approved_palette !== null) {
    e.preview.approved_palette = null;
  }
  if (typeof e.template_context.source_template_id !== 'string' && e.template_context.source_template_id !== null) {
    e.template_context.source_template_id = null;
  }
  if (typeof e.template_context.source_template_label !== 'string' && e.template_context.source_template_label !== null) {
    e.template_context.source_template_label = null;
  }
  if (
    typeof e.template_context.adapted_from_art_direction_template_id !== 'string' &&
    e.template_context.adapted_from_art_direction_template_id !== null
  ) {
    e.template_context.adapted_from_art_direction_template_id = null;
  }
  if (typeof e.template_context.last_adapted_at !== 'string' && e.template_context.last_adapted_at !== null) {
    e.template_context.last_adapted_at = null;
  }
  if (typeof e.runtime.status !== 'string') e.runtime.status = 'idle';
  if (typeof e.runtime.source !== 'string' && e.runtime.source !== null) e.runtime.source = null;
  if (typeof e.runtime.applied_preview_id !== 'string' && e.runtime.applied_preview_id !== null) {
    e.runtime.applied_preview_id = null;
  }
  if (typeof e.runtime.surface_palette !== 'object' && e.runtime.surface_palette !== null) {
    e.runtime.surface_palette = null;
  }
  if (!Array.isArray(e.runtime.material_keywords)) e.runtime.material_keywords = [];
  if (typeof e.runtime.lighting_mode !== 'string') e.runtime.lighting_mode = '';
  if (typeof e.runtime.last_applied_at !== 'string' && e.runtime.last_applied_at !== null) {
    e.runtime.last_applied_at = null;
  }
  if (!e.runtime.asset_pack || typeof e.runtime.asset_pack !== 'object') e.runtime.asset_pack = {};
  if (typeof e.runtime.asset_pack.asset_schema_version !== 'number' && e.runtime.asset_pack.asset_schema_version !== null) {
    e.runtime.asset_pack.asset_schema_version = null;
  }
  if (typeof e.runtime.asset_pack.status !== 'string') e.runtime.asset_pack.status = 'idle';
  if (typeof e.runtime.asset_pack.used_ai !== 'boolean') e.runtime.asset_pack.used_ai = false;
  if (typeof e.runtime.asset_pack.generated_at !== 'string' && e.runtime.asset_pack.generated_at !== null) {
    e.runtime.asset_pack.generated_at = null;
  }
  if (typeof e.runtime.asset_pack.source_preview_id !== 'string' && e.runtime.asset_pack.source_preview_id !== null) {
    e.runtime.asset_pack.source_preview_id = null;
  }
  if (typeof e.runtime.asset_pack.layout_fingerprint !== 'string' && e.runtime.asset_pack.layout_fingerprint !== null) {
    e.runtime.asset_pack.layout_fingerprint = null;
  }
  if (!e.runtime.asset_pack.component_dependencies || typeof e.runtime.asset_pack.component_dependencies !== 'object') {
    e.runtime.asset_pack.component_dependencies = {};
  }
  if (!e.runtime.asset_pack.component_fingerprints || typeof e.runtime.asset_pack.component_fingerprints !== 'object') {
    e.runtime.asset_pack.component_fingerprints = {};
  }
  if (!Array.isArray(e.runtime.asset_pack.stale_components)) e.runtime.asset_pack.stale_components = [];
  if (!e.runtime.asset_pack.assets || typeof e.runtime.asset_pack.assets !== 'object') e.runtime.asset_pack.assets = {};
  if (!e.runtime.bespoke_asset_manifest || typeof e.runtime.bespoke_asset_manifest !== 'object') {
    e.runtime.bespoke_asset_manifest = {};
  }
  if (typeof e.runtime.bespoke_asset_manifest.schema_version !== 'number') e.runtime.bespoke_asset_manifest.schema_version = 1;
  if (typeof e.runtime.bespoke_asset_manifest.status !== 'string') e.runtime.bespoke_asset_manifest.status = 'idle';
  if (typeof e.runtime.bespoke_asset_manifest.biome_id !== 'string' && e.runtime.bespoke_asset_manifest.biome_id !== null) {
    e.runtime.bespoke_asset_manifest.biome_id = null;
  }
  if (typeof e.runtime.bespoke_asset_manifest.source_preview_id !== 'string' && e.runtime.bespoke_asset_manifest.source_preview_id !== null) {
    e.runtime.bespoke_asset_manifest.source_preview_id = null;
  }
  if (!Array.isArray(e.runtime.bespoke_asset_manifest.generation_plan)) e.runtime.bespoke_asset_manifest.generation_plan = [];
  if (!e.runtime.bespoke_asset_manifest.assets || typeof e.runtime.bespoke_asset_manifest.assets !== 'object') {
    e.runtime.bespoke_asset_manifest.assets = {};
  }
  if (!Array.isArray(e.runtime.bespoke_asset_manifest.failed_assets)) e.runtime.bespoke_asset_manifest.failed_assets = [];
  if (typeof e.runtime.bespoke_asset_manifest.used_ai !== 'boolean') e.runtime.bespoke_asset_manifest.used_ai = false;
  if (typeof e.runtime.bespoke_asset_manifest.generated_at !== 'string' && e.runtime.bespoke_asset_manifest.generated_at !== null) {
    e.runtime.bespoke_asset_manifest.generated_at = null;
  }
  if (!Array.isArray(e.runtime.bespoke_asset_manifest.validation_errors)) e.runtime.bespoke_asset_manifest.validation_errors = [];
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
    ENVIRONMENT_RENDER_SCHEMA_VERSION,
    DEFAULT_THEME_ID,
    ENVIRONMENT_COMPONENTS,
    THEME_PRESETS,
    defaultEnvironmentComponents,
    ensureEnvironmentComponents,
    getThemeLabel,
    buildEnvironmentPreviewModel,
    parseTagsInput,
    tagsToInputString,
    ensureRoomEnvironment,
    isEnvironmentPhaseUnlocked
  };
}
if (typeof globalThis !== 'undefined') {
  globalThis.RoomWizardEnvironment = {
    ENVIRONMENT_SCHEMA_VERSION,
    ENVIRONMENT_RENDER_SCHEMA_VERSION,
    DEFAULT_THEME_ID,
    THEME_PRESETS,
    getThemeLabel,
    buildEnvironmentPreviewModel,
    parseTagsInput,
    tagsToInputString,
    ensureRoomEnvironment,
    isEnvironmentPhaseUnlocked
  };
}
