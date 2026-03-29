/**
 * Runtime export package for room-layout-editor (Sprint 4).
 * Shared between room-layout-editor.html (browser) and tests/room-editor-export.test.js (Node).
 */
'use strict';

/**
 * RW-4 — stable `environment` slice for runtime room JSON.
 * @param {object} room
 * @returns {{ version: number, themeId: string, tags: string[], spec: object, preview: object, runtime: object }}
 */
function normalizeRuntimeEnvironment(room) {
  const defaults = { version: 1, themeId: 'cave', tags: [], spec: {}, preview: {}, runtime: {} };
  const e = room && room.environment && typeof room.environment === 'object' ? room.environment : null;
  if (!e) return { ...defaults };
  const tags = Array.isArray(e.tags) ? e.tags.map((t) => String(t).trim()).filter(Boolean) : [];
  const themeId =
    typeof e.themeId === 'string' && e.themeId.trim() ? e.themeId.trim() : defaults.themeId;
  const version = typeof e.version === 'number' && e.version >= 1 ? e.version : defaults.version;
  const spec = e.spec && typeof e.spec === 'object' ? e.spec : {};
  const preview = e.preview && typeof e.preview === 'object' ? e.preview : {};
  const runtime = e.runtime && typeof e.runtime === 'object' ? e.runtime : {};
  return { version, themeId, tags, spec, preview, runtime };
}

/**
 * @param {object|null} room
 * @returns {object|null}
 */
function buildRuntimeRoom(room) {
  if (!room || room.id == null) return null;
  const removed =
    room.removedEdges != null
      ? room.removedEdges
      : Array.isArray(room.openEdges)
        ? room.openEdges
        : undefined;
  const environment = normalizeRuntimeEnvironment(room);
  return {
    id: room.id,
    name: room.name,
    polygon: room.polygon,
    size: room.size,
    global: room.global,
    platforms: room.platforms,
    doors: room.doors,
    keys: room.keys,
    abilities: room.abilities,
    movingPlatforms: room.movingPlatforms,
    playerStart: room.playerStart,
    edgeLinks: room.edgeLinks,
    environment,
    ...(removed != null ? { removedEdges: removed } : {})
  };
}

/**
 * @param {object} data - full layout document (version, meta, rooms)
 * @param {object|null} validationReport - from validateLayout()
 * @returns {{ roomFiles: Record<string, object>, worldGraph: object, manifest: object, roomLayout: object }}
 */
function generateExportPackage(data, validationReport) {
  const timestamp = new Date().toISOString();
  const rooms = (data && data.rooms) || [];

  const roomFiles = {};
  rooms.forEach((room) => {
    const runtime = buildRuntimeRoom(room);
    if (!runtime) return;
    const safe =
      String(room.id).replace(/[^a-zA-Z0-9_-]/g, '_') || 'room';
    roomFiles[`${safe}.json`] = runtime;
  });

  const worldGraph = {
    rooms: rooms.map((room) => ({
      id: room.id,
      name: room.name,
      global: room.global,
      size: room.size,
      environment: normalizeRuntimeEnvironment(room),
      connections: (room.edgeLinks || []).map((link) => ({
        toRoom: link.targetRoomId,
        fromEdge: link.edgeIndex,
        toEdge: link.targetEdgeIndex
      })),
      doors: (room.doors || []).map((d) => ({
        id: d.id,
        targetRoom: d.targetRoom,
        kind: d.kind,
        locked: d.locked || false
      }))
    }))
  };

  const dataStr = JSON.stringify(data);
  let hash = 0;
  for (let i = 0; i < dataStr.length; i += 1) {
    hash = (hash << 5) - hash + dataStr.charCodeAt(i);
    hash |= 0;
  }
  const hexHash = (hash >>> 0).toString(16).padStart(8, '0');

  const meta = (data && data.meta) || {};
  const vr = validationReport;
  let validationHighestPassingLevel = null;
  if (vr) {
    if (vr.level_1 && vr.level_1.passed) {
      validationHighestPassingLevel = vr.level_2 && vr.level_2.passed ? 2 : 1;
    } else {
      validationHighestPassingLevel = 0;
    }
  }

  const manifest = {
    exported_at: timestamp,
    layout_version: data && data.version != null ? data.version : null,
    room_count: rooms.length,
    validation_l1_passed: vr ? vr.level_1.passed : null,
    validation_l2_passed: vr ? vr.level_2.passed : null,
    validation_errors: vr ? vr.summary.errors : null,
    validation_warnings: vr ? vr.summary.warnings : null,
    validation_run_at: vr ? vr.run_at : null,
    validation_highest_passing_level: validationHighestPassingLevel,
    sha_simple: hexHash,
    engine_hints: {
      grid_size: meta.grid != null ? meta.grid : 32,
      world_width: meta.worldWidth != null ? meta.worldWidth : 1600,
      world_height: meta.worldHeight != null ? meta.worldHeight : 1200
    }
  };

  return {
    roomFiles,
    worldGraph,
    manifest,
    roomLayout: data
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    generateExportPackage,
    buildRuntimeRoom,
    normalizeRuntimeEnvironment
  };
}
if (typeof globalThis !== 'undefined') {
  globalThis.RoomLayoutExportPackage = {
    generateExportPackage,
    buildRuntimeRoom,
    normalizeRuntimeEnvironment
  };
}
