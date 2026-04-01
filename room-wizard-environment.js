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
const ENVIRONMENT_COMPONENT_SCHEMA_DEFS = {
  walls: {
    label: 'Walls',
    visual_role: 'structural',
    fields: ['enclosure_read', 'bay_rhythm', 'column_width_class', 'wall_face_depth', 'ceiling_junction', 'base_trim', 'edge_darkening', 'repetition_interval']
  },
  floor: {
    label: 'Floor',
    visual_role: 'traversal',
    fields: ['top_lip_thickness', 'face_height', 'seam_pattern', 'top_plane_read', 'edge_breakup', 'underside_darkening', 'modular_repeat_width']
  },
  platforms: {
    label: 'Platforms',
    visual_role: 'traversal',
    fields: ['top_lip_thickness', 'face_height', 'endcap_style', 'support_style', 'ledge_read', 'underside_variation', 'modular_repeat_width']
  },
  doors: {
    label: 'Doors',
    visual_role: 'threshold',
    fields: ['frame_mass', 'opening_read', 'threshold_depth', 'gate_panel_style', 'lock_overlay_style', 'side_clearance']
  },
  pits: {
    label: 'Pits',
    visual_role: 'hazard',
    fields: ['rim_profile', 'wall_drop_profile', 'interior_fill_mode', 'hazard_read', 'fog_fill', 'left_right_edge_rules']
  },
  background: {
    label: 'Background',
    visual_role: 'far_depth',
    fields: ['enclosure_architecture', 'center_openness', 'far_depth_layers', 'focal_suppression', 'floor_plane_suppression', 'atmospheric_falloff']
  },
  midground: {
    label: 'Midground',
    visual_role: 'side_frame',
    fields: ['side_mass_only', 'center_clearance_ratio', 'occluder_types', 'alpha_profile', 'floor_crossing_forbidden', 'route_overlap_forbidden']
  }
};
const ENVIRONMENT_COMPONENT_SCHEMA_COMMON_FIELDS = [
  'design_intent',
  'visual_role',
  'material_family',
  'silhouette_rules',
  'detail_density',
  'value_contrast',
  'damage_profile',
  'readability_constraints',
  'negative_constraints',
  'variation_rules'
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

function defaultEnvironmentComponentSchemas(description = '', components = {}) {
  const base = String(description || '').trim() || 'Keep this room aligned to the current project art direction.';
  const legacyPrompt = (key) => String(((components || {})[key] || {}).prompt || '').trim();
  return {
    walls: {
      design_intent: legacyPrompt('walls') || `${base} Walls should read as enclosing architecture rather than scenic concept art.`,
      visual_role: 'structural',
      material_family: 'weathered structural stone',
      silhouette_rules: ['repeat wall bays', 'clear enclosing shell'],
      detail_density: 'medium',
      value_contrast: 'low_to_medium with darker edges',
      damage_profile: 'broken masonry and restrained collapse',
      readability_constraints: ['read as enclosure', 'avoid scenic perspective'],
      negative_constraints: ['no altar scene', 'no brazier focal energy'],
      variation_rules: ['repeat with subtle block shifts'],
      enclosure_read: 'readable wall shell',
      bay_rhythm: 'measured repeating bays',
      column_width_class: 'heavy',
      wall_face_depth: 'shallow recesses',
      ceiling_junction: 'arched or lintel tie-in',
      base_trim: 'stone base trim',
      edge_darkening: 'darker outer edges',
      repetition_interval: 'medium_repeat'
    },
    floor: {
      design_intent: legacyPrompt('floor') || `${base} Floor should feel structural, modular, and easy to read for traversal.`,
      visual_role: 'traversal',
      material_family: 'weathered structural stone',
      silhouette_rules: ['clear top lip', 'straight side-view slab'],
      detail_density: 'medium',
      value_contrast: 'top plane lighter than face',
      damage_profile: 'chips, seams, and worn edges',
      readability_constraints: ['top plane must read immediately', 'face must separate from background'],
      negative_constraints: ['no giant ritual circle', 'no scenic floor perspective'],
      variation_rules: ['quiet masonry seam variation'],
      top_lip_thickness: 'clear 4-8px lip',
      face_height: 'moderate readable face',
      seam_pattern: 'quiet masonry seams',
      top_plane_read: 'top plane brighter and calmer than face',
      edge_breakup: 'small chips only',
      underside_darkening: 'underside darker than top plane',
      modular_repeat_width: 'tileable medium repeat'
    },
    platforms: {
      design_intent: legacyPrompt('platforms') || `${base} Platforms should read clearly as gameplay surfaces in the same architectural family as the floor.`,
      visual_role: 'traversal',
      material_family: 'weathered structural stone',
      silhouette_rules: ['clear top lip', 'simple readable endcaps'],
      detail_density: 'medium',
      value_contrast: 'top plane lighter than face',
      damage_profile: 'light ledge wear',
      readability_constraints: ['ledge top must pop from background'],
      negative_constraints: ['no scenic attachments', 'no ritual symbols'],
      variation_rules: ['vary seams without changing proportions'],
      top_lip_thickness: 'clear 4-8px lip',
      face_height: 'compact readable face',
      endcap_style: 'broken masonry endcap',
      support_style: 'minimal implied support',
      ledge_read: 'strong traversal ledge read',
      underside_variation: 'light underside breakup only',
      modular_repeat_width: 'tileable medium repeat'
    },
    doors: {
      design_intent: legacyPrompt('doors') || `${base} Doors should read as strong thresholds with a clear opening.`,
      visual_role: 'threshold',
      material_family: 'stone frame with aged gate insert',
      silhouette_rules: ['centered opening', 'strong outer frame'],
      detail_density: 'medium',
      value_contrast: 'opening darker than frame',
      damage_profile: 'aged but intact threshold hardware',
      readability_constraints: ['opening must read at a glance'],
      negative_constraints: ['no chamber scene around the door'],
      variation_rules: ['vary panel wear while keeping frame proportions stable'],
      frame_mass: 'heavy readable frame',
      opening_read: 'dark centered opening',
      threshold_depth: 'visible threshold recess',
      gate_panel_style: 'aged inset panels',
      lock_overlay_style: 'small readable lock overlay only when needed',
      side_clearance: 'clear side clearance around opening'
    },
    pits: {
      design_intent: `${base} Pits should read instantly as hazards rather than scenic voids.`,
      visual_role: 'hazard',
      material_family: 'broken stone drop with dark void interior',
      silhouette_rules: ['clear rim read', 'open non-walkable void'],
      detail_density: 'low_to_medium',
      value_contrast: 'rim lighter than interior void',
      damage_profile: 'broken lip and damp erosion',
      readability_constraints: ['hazard must read immediately'],
      negative_constraints: ['no fake floor fill', 'no scenic bridge treatment'],
      variation_rules: ['vary rim chips and wall streaks'],
      rim_profile: 'clear chipped rim silhouette',
      wall_drop_profile: 'vertical stone wall drop',
      interior_fill_mode: 'deep shadow or void fog',
      hazard_read: 'non-walkable and dangerous at a glance',
      fog_fill: 'subtle low fog only if void stays readable',
      left_right_edge_rules: 'rim edges stay crisp enough to read jumps'
    },
    background: {
      design_intent: legacyPrompt('background') || `${base} Background must read as a far-depth enclosing room shell with a calm open center.`,
      visual_role: 'far_depth',
      material_family: 'far-depth architectural stone shell',
      silhouette_rules: ['enclosing hall shell', 'open center lane'],
      detail_density: 'medium',
      value_contrast: 'muted far-depth values',
      damage_profile: 'aged architecture without focal props',
      readability_constraints: ['must read as enclosing shell', 'center lane stays calm'],
      negative_constraints: ['no altar', 'no brazier', 'no center dais', 'no near framing'],
      variation_rules: ['vary arch spacing and recess depth'],
      enclosure_architecture: 'rear wall, side walls, arches, and pillars read as one hall shell',
      center_openness: 'fully open and calm center lane',
      far_depth_layers: 'at least two depth bands',
      focal_suppression: 'explicitly suppress altar, brazier, shrine, and dais imagery',
      floor_plane_suppression: 'no near floor strip or scenic floor carryover',
      atmospheric_falloff: 'soft haze into distance without bright focal hotspots'
    },
    midground: {
      design_intent: `${base} Midground should be side framing only, never center clutter.`,
      visual_role: 'side_frame',
      material_family: 'side-frame stone or column mass',
      silhouette_rules: ['side-only framing', 'transparent open center'],
      detail_density: 'low_to_medium',
      value_contrast: 'subdued side mass with center transparency',
      damage_profile: 'light edge wear and cracks',
      readability_constraints: ['center route stays readable'],
      negative_constraints: ['no center object', 'no full-width arch', 'no floor-crossing silhouette'],
      variation_rules: ['vary side cluster placement while keeping center clear ratio stable'],
      side_mass_only: 'true',
      center_clearance_ratio: '0.45',
      occluder_types: 'arches, columns, side buttresses',
      alpha_profile: 'solid on edges, transparent through center',
      floor_crossing_forbidden: 'true',
      route_overlap_forbidden: 'true'
    }
  };
}

function ensureEnvironmentComponentSchemas(spec) {
  if (!spec.component_schemas || typeof spec.component_schemas !== 'object') {
    spec.component_schemas = {};
  }
  const fallback = defaultEnvironmentComponentSchemas(spec.description || '', spec.components || {});
  Object.entries(ENVIRONMENT_COMPONENT_SCHEMA_DEFS).forEach(([key, def]) => {
    const item = spec.component_schemas[key];
    if (!item || typeof item !== 'object') {
      spec.component_schemas[key] = { ...fallback[key] };
      return;
    }
    ENVIRONMENT_COMPONENT_SCHEMA_COMMON_FIELDS.forEach((field) => {
      const value = item[field];
      if (Array.isArray(fallback[key][field])) {
        if (!Array.isArray(value) || !value.length) item[field] = [...fallback[key][field]];
      } else if (typeof value !== 'string' || !value.trim()) {
        item[field] = fallback[key][field];
      }
    });
    def.fields.forEach((field) => {
      if (typeof item[field] !== 'string' || !String(item[field]).trim()) item[field] = fallback[key][field];
    });
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
  ensureEnvironmentComponentSchemas(e.spec);
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
  if (typeof e.runtime.bespoke_asset_manifest.schema_version !== 'number') e.runtime.bespoke_asset_manifest.schema_version = 2;
  if (typeof e.runtime.bespoke_asset_manifest.status !== 'string') e.runtime.bespoke_asset_manifest.status = 'idle';
  if (typeof e.runtime.bespoke_asset_manifest.biome_id !== 'string' && e.runtime.bespoke_asset_manifest.biome_id !== null) {
    e.runtime.bespoke_asset_manifest.biome_id = null;
  }
  if (typeof e.runtime.bespoke_asset_manifest.source_preview_id !== 'string' && e.runtime.bespoke_asset_manifest.source_preview_id !== null) {
    e.runtime.bespoke_asset_manifest.source_preview_id = null;
  }
  if (!Array.isArray(e.runtime.bespoke_asset_manifest.generation_plan)) e.runtime.bespoke_asset_manifest.generation_plan = [];
  if (!Array.isArray(e.runtime.bespoke_asset_manifest.required_slots)) e.runtime.bespoke_asset_manifest.required_slots = [];
  if (!Array.isArray(e.runtime.bespoke_asset_manifest.built_slots)) e.runtime.bespoke_asset_manifest.built_slots = [];
  if (!e.runtime.bespoke_asset_manifest.slot_groups || typeof e.runtime.bespoke_asset_manifest.slot_groups !== 'object') {
    e.runtime.bespoke_asset_manifest.slot_groups = {};
  }
  if (!e.runtime.bespoke_asset_manifest.schema_validation || typeof e.runtime.bespoke_asset_manifest.schema_validation !== 'object') {
    e.runtime.bespoke_asset_manifest.schema_validation = { status: 'idle', valid: false, errors: [], component_statuses: {} };
  }
  if (!e.runtime.bespoke_asset_manifest.runtime_review || typeof e.runtime.bespoke_asset_manifest.runtime_review !== 'object') {
    e.runtime.bespoke_asset_manifest.runtime_review = { status: 'idle', fail_reasons: [], metrics: {}, screenshot_url: null, review_mode: null };
  }
  if (!e.runtime.bespoke_asset_manifest.review || typeof e.runtime.bespoke_asset_manifest.review !== 'object') {
    e.runtime.bespoke_asset_manifest.review = { ...e.runtime.bespoke_asset_manifest.runtime_review };
  }
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
    defaultEnvironmentComponentSchemas,
    ensureEnvironmentComponentSchemas,
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
    defaultEnvironmentComponentSchemas,
    getThemeLabel,
    buildEnvironmentPreviewModel,
    parseTagsInput,
    tagsToInputString,
    ensureRoomEnvironment,
    isEnvironmentPhaseUnlocked
  };
}
