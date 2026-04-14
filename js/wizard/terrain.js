/**
 * RW-3 Terrain — axis-aligned platform presets and layout checks (Phaser Arcade–friendly).
 * Loaded by room-layout-editor.html and unit tests.
 */
'use strict';

const DEFAULT_TILE = 32;
const DEFAULT_PLATFORM_H = 14;
const ROOM_ID_PATTERN = /^(?:[A-Z][A-Z0-9]*-)?R\d+$/i;

/**
 * @param {object} room
 * @returns {boolean}
 */
function isLayoutCompleteForTerrain(room) {
  if (!room || typeof room !== 'object') return false;
  const name = String(room.name || '').trim();
  if (!name) return false;
  const id = String(room.id || '').trim();
  if (!ROOM_ID_PATTERN.test(id)) return false;
  const w = Number(room.size?.width);
  const h = Number(room.size?.height);
  if (!Number.isFinite(w) || !Number.isFinite(h) || w < 320 || h < 320) return false;
  const poly = Array.isArray(room.polygon) ? room.polygon : [];
  if (poly.length < 3) return false;
  return true;
}

/**
 * Ray-cast point-in-polygon (room-local space).
 * @param {number} px
 * @param {number} py
 * @param {Array<[number, number]>} polygon
 */
function pointInPolygon(px, py, polygon) {
  if (!Array.isArray(polygon) || polygon.length < 3) return false;
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0];
    const yi = polygon[i][1];
    const xj = polygon[j][0];
    const yj = polygon[j][1];
    const intersect =
      yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi + 1e-12) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function boundingBox(polygon) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const pt of polygon) {
    const x = Number(pt[0]);
    const y = Number(pt[1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  if (!Number.isFinite(minX)) return null;
  return { minX, minY, maxX, maxY };
}

function platformAabb(platform, tile, platformH) {
  const len = Math.max(1, Number(platform.len || 1));
  const x = Number(platform.x);
  const y = Number(platform.y);
  return {
    left: x,
    right: x + len * tile,
    top: y - platformH,
    bottom: y
  };
}

function platformFullyInsidePolygon(platform, polygon, tile, platformH) {
  const b = platformAabb(platform, tile, platformH);
  const corners = [
    [b.left, b.top],
    [b.right, b.top],
    [b.right, b.bottom],
    [b.left, b.bottom]
  ];
  return corners.every(([x, y]) => pointInPolygon(x, y, polygon));
}

/**
 * Shrink length and nudge X so the platform rect lies fully inside the polygon (concave-safe).
 * @returns {Omit<PlatformDef,'id'> | null}
 */
function fitPlatformToFootprint(room, partial, tile, platformH) {
  const poly = room.polygon;
  if (!Array.isArray(poly) || poly.length < 3) return null;
  const bbox = boundingBox(poly);
  if (!bbox) return null;
  const { minX, maxX } = bbox;
  let len = Math.max(1, Math.floor(Number(partial.len)));
  const y = Number(partial.y);
  const tint = Number(partial.tint) || 0;
  const x0 = Number(partial.x);
  if (!Number.isFinite(x0) || !Number.isFinite(y)) return null;

  for (let L = len; L >= 1; L--) {
    for (let dx = -10; dx <= 10; dx++) {
      const tryX = x0 + dx * tile;
      if (tryX < minX) continue;
      if (tryX + L * tile > maxX) continue;
      const test = { x: tryX, y, len: L, tint };
      if (platformFullyInsidePolygon(test, poly, tile, platformH)) {
        return test;
      }
    }
  }
  return null;
}

/**
 * Warnings when a door’s anchor sits inside a platform’s top band (traversal concern).
 * @returns {string[]}
 */
function doorPlatformOverlapWarnings(room, tile, platformH) {
  const out = [];
  if (!room || !Array.isArray(room.platforms) || !Array.isArray(room.doors)) return out;
  const poly = room.polygon;
  if (!Array.isArray(poly) || poly.length < 3) return out;
  for (const door of room.doors) {
    const dx = Number(door.x);
    const dy = Number(door.y);
    if (!Number.isFinite(dx) || !Number.isFinite(dy)) continue;
    if (!pointInPolygon(dx, dy, poly)) continue;
    for (const p of room.platforms) {
      const b = platformAabb(p, tile, platformH);
      if (dx >= b.left && dx <= b.right && dy >= b.top && dy <= b.bottom) {
        out.push(`Door ${door.id} overlaps platform ${p.id} (walkable band).`);
      }
    }
  }
  return out;
}

/**
 * @typedef {{ id: string, x: number, y: number, len: number, tint: number }} PlatformDef
 */

/**
 * Build preset platform rects (no `id`; caller assigns with nextId(prefix, platforms)).
 * @param {object} room
 * @param {string} presetId
 * @param {{ tile?: number, platformH?: number, tintBase?: number }} [ctx]
 * @returns {{ ok: boolean, reason?: string, platforms?: Omit<PlatformDef, 'id'>[] }}
 */
function buildTerrainPresetPlatforms(room, presetId, ctx) {
  ctx = ctx || {};
  const tile = Number(ctx.tile) || DEFAULT_TILE;
  const platformH = Number(ctx.platformH) || DEFAULT_PLATFORM_H;
  const tintBase = Number(ctx.tintBase) || 0;
  if (!isLayoutCompleteForTerrain(room)) return { ok: false, reason: 'layout_incomplete' };
  const bbox = boundingBox(room.polygon);
  if (!bbox) return { ok: false, reason: 'bad_polygon' };
  const { minX, minY, maxX, maxY } = bbox;
  const margin = 72;
  const innerW = maxX - minX - 2 * margin;
  const innerH = maxY - minY - 2 * margin;
  if (innerW < tile * 2 || innerH < platformH * 3) return { ok: false, reason: 'room_too_tight' };

  const bottomY = maxY - margin;
  const midY = minY + innerH * 0.45;
  const upperY = minY + innerH * 0.25;
  const cx = (minX + maxX) / 2;

  /** @type {Omit<PlatformDef, 'id'>[]} */
  const out = [];

  switch (presetId) {
    case 'ground_band': {
      const len = Math.max(1, Math.floor(innerW / tile) - 1);
      const x0 = minX + margin + tile;
      out.push({
        x: x0,
        y: bottomY,
        len,
        tint: tintBase % 8
      });
      break;
    }
    case 'two_level': {
      const len = Math.max(2, Math.floor((innerW * 0.55) / tile));
      const x1 = minX + margin + tile;
      const x2 = minX + margin + Math.floor(innerW * 0.35);
      out.push(
        { x: x1, y: bottomY, len, tint: tintBase % 8 },
        { x: x2, y: upperY, len: Math.max(2, len - 2), tint: (tintBase + 1) % 8 }
      );
      break;
    }
    case 'step_up': {
      const stepLen = Math.max(2, Math.floor(innerW / 12));
      let x = minX + margin + tile;
      let y = bottomY;
      for (let i = 0; i < 3; i += 1) {
        out.push({
          x,
          y,
          len: stepLen,
          tint: (tintBase + i) % 8
        });
        x += stepLen * tile + tile;
        y -= Math.min(80, tile * 2);
      }
      break;
    }
    case 'ledge_pair': {
      const len = Math.max(2, Math.floor(innerW / 6));
      out.push(
        { x: minX + margin, y: midY, len, tint: tintBase % 8 },
        { x: maxX - margin - len * tile, y: midY, len, tint: (tintBase + 1) % 8 }
      );
      break;
    }
    case 'island': {
      const len = Math.max(2, Math.floor(innerW / 10));
      const x = cx - (len * tile) / 2;
      out.push({ x, y: midY, len, tint: tintBase % 8 });
      break;
    }
    default:
      return { ok: false, reason: 'unknown_preset' };
  }

  const fitted = [];
  for (const p of out) {
    const f = fitPlatformToFootprint(room, p, tile, platformH);
    if (f) fitted.push(f);
  }

  if (fitted.length === 0) {
    return { ok: false, reason: 'preset_outside_footprint' };
  }

  return { ok: true, platforms: fitted };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
  DEFAULT_TILE,
  DEFAULT_PLATFORM_H,
  ROOM_ID_PATTERN,
  isLayoutCompleteForTerrain,
    pointInPolygon,
    boundingBox,
    platformAabb,
    platformFullyInsidePolygon,
    fitPlatformToFootprint,
    doorPlatformOverlapWarnings,
    buildTerrainPresetPlatforms
  };
}
if (typeof globalThis !== 'undefined') {
  globalThis.RoomWizardTerrain = {
    DEFAULT_TILE,
    DEFAULT_PLATFORM_H,
    isLayoutCompleteForTerrain,
    pointInPolygon,
    boundingBox,
    platformAabb,
    platformFullyInsidePolygon,
    fitPlatformToFootprint,
    doorPlatformOverlapWarnings,
    buildTerrainPresetPlatforms
  };
}
