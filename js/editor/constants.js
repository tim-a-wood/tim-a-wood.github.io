'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Constants ? root.RoomEditor.Constants : {};

Module.DATA_URL = './room-layout-data.json';

Module.API_PING_URL = '/api/ping';

Module.API_LAYOUT_URL = '/api/layout';

Module.API_COPILOT_URL = '/api/copilot';

Module.ROOM_ENV_ARCHETYPES_URL = '/api/room-environment/archetypes';

Module.LOCAL_STORAGE_PREFIX = 'ashen-hollow-room-layout-v1:local:';

Module.SIDEBAR_KEY = 'roomCreator.sidebarCollapsed';

Module.WORKBENCH_URL = new URL('./tools/2d-sprite-and-animation/index.html', window.location.href);

Module.ROOM_EDITOR_URL = new URL('./room-layout-editor.html', window.location.href);

Module.ROOM_W = 1600;

Module.ROOM_H = 1200;

Module.TILE = 32;

Module.VALIDATION_L2 = {
        /** Warn if vertical drop to the nearest “related” platform below exceeds this. */
        maxVerticalStepPx: 240,
        /**
         * Horizontal gap between paired platforms (see maxHorizontalSeparationForPairPx).
         * Kept equal to the pair cap so we do not warn on gaps we already allowed when pairing —
         * otherwise 400–520px gaps spuriously warn (see L2-002).
         */
        maxHorizontalGapPx: 520,
        /** Doors / keys / abilities farther than this from any platform surface (Manhattan-ish via spec). */
        interactMaxDistPx: 240,
        /** Only pair platform A→B for L2-001/L2-002 when x-interval gap ≤ this (overlap = 0 gap). */
        maxHorizontalSeparationForPairPx: 520
      };

Module.PLATFORM_H = 14;

Module.ROOM_MARGIN_LEFT = 132;

Module.ROOM_MARGIN_RIGHT = 236;

Module.ROOM_MARGIN_TOP = 16;

Module.ROOM_MARGIN_BOTTOM = 16;

Module.GLOBAL_ROOM_PREVIEW_SCALE = 0.12;

Module.HIT_VERTEX = 18;

Module.HIT_DOOR_X = 24;

Module.HIT_DOOR_Y = 36;

Module.HIT_PLATFORM_PAD = 12;

Module.HIT_GLOBAL_PAD = 18;

Module.HIT_LINK_GUIDE_PAD = 18;

Module.HIT_ROOM_EDGE_PAD = 14;

Module.GLOBAL_DRAG_START_DISTANCE = 6;

Module.VIEW_PAN_STEP = 96;

Module.ROOM_ZOOM_MIN = 0.5;

Module.ROOM_ZOOM_MAX = 3;

Module.GLOBAL_ZOOM_MIN = 0.4;

Module.GLOBAL_ZOOM_MAX = 2;

Module.ABILITY_DEFS = Object.freeze([
        { id: 'double_jump', label: 'Double Jump' }
      ]);

Module.TERRAIN_PRESET_FAIL = {
        layout_incomplete: 'Finish Layout first (name, id, footprint).',
        room_too_tight: 'Room is too small for that preset.',
        bad_polygon: 'Invalid room polygon.',
        preset_outside_footprint:
          'Could not fit preset inside this room outline — try another preset or place platforms manually.',
        unknown_preset: 'Unknown preset.'
      };

Module.RW_FOOTPRINT_PRESETS = {
        small: [960, 720],
        medium: [1600, 1200],
        large: [2240, 1200]
      };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Constants = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
