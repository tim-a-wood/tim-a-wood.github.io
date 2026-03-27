/**
 * RW-2: align axis-aligned room footprints to neighbors in world space (shared with tests).
 * Uses the same world transform as room-layout-editor: local point → world
 *   world = global + (local - size/2) * scale
 */
'use strict';

var ROOM_WIZARD_NEIGHBOR_SCALE = 0.12;

function ensureSize(room) {
  const W = Math.max(1, Number(room?.size?.width || 800));
  const H = Math.max(1, Number(room?.size?.height || 600));
  return { width: W, height: H };
}

function getPolygon(room) {
  const poly = Array.isArray(room?.polygon) ? room.polygon : [];
  return poly.length >= 3 ? poly : null;
}

/**
 * @returns {{ start: {x:number,y:number}, end: {x:number,y:number} } | null}
 */
function getEdgeSegmentLocal(room, edgeIndex) {
  const poly = getPolygon(room);
  if (!poly) return null;
  const n = poly.length;
  const i = ((Number(edgeIndex) % n) + n) % n;
  const a = poly[i];
  const b = poly[(i + 1) % n];
  if (!a || !b) return null;
  return {
    edgeIndex: i,
    start: { x: Number(a[0]), y: Number(a[1]) },
    end: { x: Number(b[0]), y: Number(b[1]) }
  };
}

function localToWorld(global, size, lx, ly, scale) {
  const W = size.width;
  const H = size.height;
  return {
    x: global.x + (lx - W / 2) * scale,
    y: global.y + (ly - H / 2) * scale
  };
}

function edgeOrientation(seg) {
  if (!seg) return null;
  const dx = Math.abs(seg.end.x - seg.start.x);
  const dy = Math.abs(seg.end.y - seg.start.y);
  const eps = 1e-4;
  if (dx < eps && dy > eps) return 'vertical';
  if (dy < eps && dx > eps) return 'horizontal';
  if (dx < eps && dy < eps) return 'point';
  return 'other';
}

/**
 * Snap room A's global position so edge A lies on the same infinite line as edge B (room B fixed).
 * Requires parallel edges; uses midpoint translation in world space (works for any polygon, not only quads).
 * @returns {{ ok: true, global: {x:number,y:number} } | { ok: false, reason: string }}
 */
function computeAlignedGlobal(roomA, roomB, edgeIndexA, edgeIndexB, scale) {
  const s = scale == null ? ROOM_WIZARD_NEIGHBOR_SCALE : Number(scale);
  if (!roomA || !roomB || roomA === roomB) return { ok: false, reason: 'bad_room' };
  const gA = roomA.global && Number.isFinite(roomA.global.x) && Number.isFinite(roomA.global.y)
    ? { x: Number(roomA.global.x), y: Number(roomA.global.y) }
    : { x: 0, y: 0 };
  const gB = roomB.global && Number.isFinite(roomB.global.x) && Number.isFinite(roomB.global.y)
    ? { x: Number(roomB.global.x), y: Number(roomB.global.y) }
    : { x: 0, y: 0 };
  const sizeA = ensureSize(roomA);
  const sizeB = ensureSize(roomB);
  const segA = getEdgeSegmentLocal(roomA, edgeIndexA);
  const segB = getEdgeSegmentLocal(roomB, edgeIndexB);
  if (!segA || !segB) return { ok: false, reason: 'bad_edge' };
  const uAx = segA.end.x - segA.start.x;
  const uAy = segA.end.y - segA.start.y;
  const uBx = segB.end.x - segB.start.x;
  const uBy = segB.end.y - segB.start.y;
  const lenA = Math.hypot(uAx, uAy);
  const lenB = Math.hypot(uBx, uBy);
  if (lenA < 1e-9 || lenB < 1e-9) return { ok: false, reason: 'degenerate_edge' };
  const cross = uAx * uBy - uAy * uBx;
  const parallelEps = Math.max(1e-6, 1e-9 * lenA * lenB);
  if (Math.abs(cross) > parallelEps) {
    return { ok: false, reason: 'edges_not_parallel' };
  }

  const midAx = (segA.start.x + segA.end.x) / 2;
  const midAy = (segA.start.y + segA.end.y) / 2;
  const midBx = (segB.start.x + segB.end.x) / 2;
  const midBy = (segB.start.y + segB.end.y) / 2;

  const midAWorld = localToWorld(gA, sizeA, midAx, midAy, s);
  const midBWorld = localToWorld(gB, sizeB, midBx, midBy, s);

  return {
    ok: true,
    global: {
      x: gA.x + (midBWorld.x - midAWorld.x),
      y: gA.y + (midBWorld.y - midAWorld.y)
    }
  };
}

function distancePointToSegment(px, py, ax, ay, bx, by) {
  const abx = bx - ax;
  const aby = by - ay;
  const apx = px - ax;
  const apy = py - ay;
  const l2 = abx * abx + aby * aby;
  if (l2 < 1e-12) return Math.hypot(px - ax, py - ay);
  let t = (apx * abx + apy * aby) / l2;
  t = Math.max(0, Math.min(1, t));
  const qx = ax + t * abx;
  const qy = ay + t * aby;
  return Math.hypot(px - qx, py - qy);
}

/**
 * Doors whose foot is near the given edge segment (room-local px).
 */
function doorsNearEdge(doors, seg, maxDistPx) {
  const dmax = maxDistPx == null ? 72 : Number(maxDistPx);
  const list = Array.isArray(doors) ? doors : [];
  return list.filter((door) => {
    const px = Number(door?.x);
    const py = Number(door?.y);
    if (!Number.isFinite(px) || !Number.isFinite(py)) return false;
    return distancePointToSegment(px, py, seg.start.x, seg.start.y, seg.end.x, seg.end.y) <= dmax;
  });
}

function meanWorldYForDoors(global, size, doors, scale) {
  const s = scale == null ? ROOM_WIZARD_NEIGHBOR_SCALE : Number(scale);
  const ys = doors.map((d) => localToWorld(global, size, Number(d.x), Number(d.y), s).y).filter((y) => Number.isFinite(y));
  if (!ys.length) return null;
  return ys.reduce((a, b) => a + b, 0) / ys.length;
}

function meanWorldXForDoors(global, size, doors, scale) {
  const s = scale == null ? ROOM_WIZARD_NEIGHBOR_SCALE : Number(scale);
  const xs = doors.map((d) => localToWorld(global, size, Number(d.x), Number(d.y), s).x).filter((x) => Number.isFinite(x));
  if (!xs.length) return null;
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function edgeMidpointWorld(room, edgeIndex, global, size, scale) {
  const seg = getEdgeSegmentLocal(room, edgeIndex);
  if (!seg) return null;
  const mx = (seg.start.x + seg.end.x) / 2;
  const my = (seg.start.y + seg.end.y) / 2;
  return localToWorld(global, size, mx, my, scale);
}

/**
 * After edges are aligned, nudge room A's global along the opening (tangential to the wall):
 * prefers average door world position on each edge when doors exist within ~72px of the edge;
 * otherwise uses edge midpoints in world space (same axis as before: vertical wall → Y, horizontal → X).
 * Parallel slanted edges: nudge along the wall direction in world space.
 * @returns {{ deltaX: number, deltaY: number, reason?: string }}
 */
function computeHatchHeightDelta(roomA, roomB, edgeIndexA, edgeIndexB, scale) {
  const s = scale == null ? ROOM_WIZARD_NEIGHBOR_SCALE : Number(scale);
  const gA = roomA.global && Number.isFinite(roomA.global.x)
    ? { x: Number(roomA.global.x), y: Number(roomA.global.y) }
    : { x: 0, y: 0 };
  const gB = roomB.global && Number.isFinite(roomB.global.x)
    ? { x: Number(roomB.global.x), y: Number(roomB.global.y) }
    : { x: 0, y: 0 };
  const sizeA = ensureSize(roomA);
  const sizeB = ensureSize(roomB);
  const segA = getEdgeSegmentLocal(roomA, edgeIndexA);
  const segB = getEdgeSegmentLocal(roomB, edgeIndexB);
  if (!segA || !segB) return { deltaX: 0, deltaY: 0, reason: 'bad_edge' };

  const nearA = doorsNearEdge(roomA.doors, segA);
  const nearB = doorsNearEdge(roomB.doors, segB);

  const oA = edgeOrientation(segA);
  if (oA === 'vertical' || oA === 'horizontal') {
    if (oA === 'vertical') {
      let yA = meanWorldYForDoors(gA, sizeA, nearA, s);
      let yB = meanWorldYForDoors(gB, sizeB, nearB, s);
      if (yA == null) {
        const m = edgeMidpointWorld(roomA, edgeIndexA, gA, sizeA, s);
        yA = m ? m.y : null;
      }
      if (yB == null) {
        const m = edgeMidpointWorld(roomB, edgeIndexB, gB, sizeB, s);
        yB = m ? m.y : null;
      }
      if (yA == null || yB == null) return { deltaX: 0, deltaY: 0, reason: 'bad_edge' };
      const dy = yB - yA;
      if (Math.abs(dy) < 1e-9) return { deltaX: 0, deltaY: 0, reason: 'already_aligned' };
      return { deltaX: 0, deltaY: dy };
    }

    let xA = meanWorldXForDoors(gA, sizeA, nearA, s);
    let xB = meanWorldXForDoors(gB, sizeB, nearB, s);
    if (xA == null) {
      const m = edgeMidpointWorld(roomA, edgeIndexA, gA, sizeA, s);
      xA = m ? m.x : null;
    }
    if (xB == null) {
      const m = edgeMidpointWorld(roomB, edgeIndexB, gB, sizeB, s);
      xB = m ? m.x : null;
    }
    if (xA == null || xB == null) return { deltaX: 0, deltaY: 0, reason: 'bad_edge' };
    const dx = xB - xA;
    if (Math.abs(dx) < 1e-9) return { deltaX: 0, deltaY: 0, reason: 'already_aligned' };
    return { deltaX: dx, deltaY: 0 };
  }

  const wa = edgeEndpointsWorld(roomA, edgeIndexA, gA, sizeA, s);
  const wb = edgeEndpointsWorld(roomB, edgeIndexB, gB, sizeB, s);
  if (!wa || !wb) return { deltaX: 0, deltaY: 0, reason: 'bad_edge' };
  const uAx = wa.b.x - wa.a.x;
  const uAy = wa.b.y - wa.a.y;
  const uBx = wb.b.x - wb.a.x;
  const uBy = wb.b.y - wb.a.y;
  const lenA = Math.hypot(uAx, uAy);
  const lenB = Math.hypot(uBx, uBy);
  if (lenA < 1e-9 || lenB < 1e-9) return { deltaX: 0, deltaY: 0, reason: 'degenerate_edge' };
  const cross = uAx * uBy - uAy * uBx;
  const parallelEps = Math.max(1e-6, 1e-9 * lenA * lenB);
  if (Math.abs(cross) > parallelEps) {
    return { deltaX: 0, deltaY: 0, reason: 'edges_not_parallel' };
  }

  const tx = uBx / lenB;
  const ty = uBy / lenB;
  const midAx = (wa.a.x + wa.b.x) / 2;
  const midAy = (wa.a.y + wa.b.y) / 2;
  const midBx = (wb.a.x + wb.b.x) / 2;
  const midBy = (wb.a.y + wb.b.y) / 2;
  const d = (midBx - midAx) * tx + (midBy - midAy) * ty;
  if (Math.abs(d) < 1e-9) return { deltaX: 0, deltaY: 0, reason: 'already_aligned' };
  return { deltaX: d * tx, deltaY: d * ty };
}

function edgeEndpointsWorld(room, edgeIndex, global, size, scale) {
  const seg = getEdgeSegmentLocal(room, edgeIndex);
  if (!seg) return null;
  const a = localToWorld(global, size, seg.start.x, seg.start.y, scale);
  const b = localToWorld(global, size, seg.end.x, seg.end.y, scale);
  return { a, b };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    ROOM_WIZARD_NEIGHBOR_SCALE,
    getEdgeSegmentLocal,
    computeAlignedGlobal,
    computeHatchHeightDelta,
    edgeOrientation,
    doorsNearEdge,
    localToWorld
  };
}
if (typeof globalThis !== 'undefined') {
  globalThis.RoomWizardNeighborAlign = {
    ROOM_WIZARD_NEIGHBOR_SCALE,
    getEdgeSegmentLocal,
    computeAlignedGlobal,
    computeHatchHeightDelta,
    edgeOrientation,
    doorsNearEdge,
    localToWorld
  };
}
