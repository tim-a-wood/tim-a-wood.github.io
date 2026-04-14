'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Topology ? root.RoomEditor.Topology : {};

function getEdgeLink(roomId, edgeIndex) {
        const room = RoomEditor.Model.getRoomById(roomId);
        if (!room) return null;
        RoomEditor.Model.ensureRoomShape(room);
        return room.edgeLinks.find((link) => Number(link.edgeIndex) === Number(edgeIndex)) || null;
      }

function clearRoomEdgeLink(roomId, edgeIndex, clearReciprocal = true) {
        const room = RoomEditor.Model.getRoomById(roomId);
        if (!room) return;
        RoomEditor.Model.ensureRoomShape(room);
        const existing = getEdgeLink(roomId, edgeIndex);
        room.edgeLinks = room.edgeLinks.filter((link) => Number(link.edgeIndex) !== Number(edgeIndex));
        if (!clearReciprocal || !existing) return;

        const targetRoom = RoomEditor.Model.getRoomById(existing.targetRoomId);
        if (!targetRoom) return;
        RoomEditor.Model.ensureRoomShape(targetRoom);
        targetRoom.edgeLinks = targetRoom.edgeLinks.filter((link) => Number(link.edgeIndex) !== Number(existing.targetEdgeIndex));
      }

function clearAllRoomEdgeLinks(roomId) {
        const room = RoomEditor.Model.getRoomById(roomId);
        if (!room) return;
        RoomEditor.Model.ensureRoomShape(room);
        const links = [...room.edgeLinks];
        links.forEach((link) => clearRoomEdgeLink(roomId, link.edgeIndex, true));
      }

function remapRoomEdgeLinks(roomId, remapEdgeIndex) {
        const room = RoomEditor.Model.getRoomById(roomId);
        if (!room) return;
        RoomEditor.Model.ensureRoomShape(room);
        const previousLinks = [...room.edgeLinks];
        previousLinks.forEach((link) => clearRoomEdgeLink(roomId, link.edgeIndex, true));
        previousLinks.forEach((link) => {
          const nextEdgeIndex = remapEdgeIndex(Number(link.edgeIndex), link);
          const targetRoom = RoomEditor.Model.getRoomById(link.targetRoomId);
          if (!Number.isInteger(nextEdgeIndex) || nextEdgeIndex < 0 || !targetRoom) return;
          RoomEditor.Model.ensureRoomShape(targetRoom);
          if (nextEdgeIndex >= RoomEditor.Model.getEdgeCount(room) || Number(link.targetEdgeIndex) >= RoomEditor.Model.getEdgeCount(targetRoom)) return;
          setRoomEdgeLink(roomId, nextEdgeIndex, link.targetRoomId, Number(link.targetEdgeIndex));
        });
      }

function isRoomEdgeRemoved(room, edgeIndex) {
        RoomEditor.Model.ensureRoomShape(room);
        return room.removedEdges.includes(Number(edgeIndex));
      }

function remapRoomRemovedEdges(roomId, remapEdgeIndex) {
        const room = RoomEditor.Model.getRoomById(roomId);
        if (!room) return;
        RoomEditor.Model.ensureRoomShape(room);
        const nextRemovedEdges = [];
        room.removedEdges.forEach((edgeIndex) => {
          const nextEdge = remapEdgeIndex(Number(edgeIndex));
          if (Array.isArray(nextEdge)) {
            nextEdge.forEach((value) => {
              if (Number.isInteger(value) && value >= 0) nextRemovedEdges.push(value);
            });
            return;
          }
          if (Number.isInteger(nextEdge) && nextEdge >= 0) nextRemovedEdges.push(nextEdge);
        });
        room.removedEdges = [...new Set(nextRemovedEdges.filter((edgeIndex) => edgeIndex < RoomEditor.Model.getEdgeCount(room)))].sort((a, b) => a - b);
      }

function toggleRoomEdgeRemoved(roomId, edgeIndex) {
        const room = RoomEditor.Model.getRoomById(roomId);
        if (!room) return false;
        RoomEditor.Model.ensureRoomShape(room);
        const normalizedIndex = ((Number(edgeIndex) % RoomEditor.Model.getEdgeCount(room)) + RoomEditor.Model.getEdgeCount(room)) % RoomEditor.Model.getEdgeCount(room);
        if (room.removedEdges.includes(normalizedIndex)) {
          room.removedEdges = room.removedEdges.filter((value) => value !== normalizedIndex);
          return false;
        }
        room.removedEdges = [...room.removedEdges, normalizedIndex].sort((a, b) => a - b);
        return true;
      }

function setRoomEdgeLink(roomId, edgeIndex, targetRoomId, targetEdgeIndex) {
        if (!roomId || !targetRoomId || roomId === targetRoomId) return false;
        const room = RoomEditor.Model.getRoomById(roomId);
        const targetRoom = RoomEditor.Model.getRoomById(targetRoomId);
        if (!room || !targetRoom) return false;
        if (edgeIndex < 0 || targetEdgeIndex < 0) return false;
        if (edgeIndex >= RoomEditor.Model.getEdgeCount(room) || targetEdgeIndex >= RoomEditor.Model.getEdgeCount(targetRoom)) return false;

        clearRoomEdgeLink(roomId, edgeIndex, true);
        clearRoomEdgeLink(targetRoomId, targetEdgeIndex, true);

        room.edgeLinks.push({ edgeIndex, targetRoomId, targetEdgeIndex });
        targetRoom.edgeLinks.push({ edgeIndex: targetEdgeIndex, targetRoomId: roomId, targetEdgeIndex: edgeIndex });
        room.edgeLinks.sort((a, b) => a.edgeIndex - b.edgeIndex);
        targetRoom.edgeLinks.sort((a, b) => a.edgeIndex - b.edgeIndex);
        return true;
      }

function getLinkedEdgeGuide(roomId, edgeIndex) {
        const link = getEdgeLink(roomId, edgeIndex);
        if (!link) return null;
        const room = RoomEditor.Model.getRoomById(roomId);
        const targetRoom = RoomEditor.Model.getRoomById(link.targetRoomId);
        if (!room || !targetRoom) return null;
        const sourceEdge = RoomEditor.Model.getEdgeCanvasPoints(room, edgeIndex);
        const targetEdge = RoomEditor.Model.getEdgeCanvasPoints(targetRoom, link.targetEdgeIndex);
        if (!sourceEdge || !targetEdge) return null;
        return {
          sourceRoomId: roomId,
          edgeIndex,
          targetRoomId: link.targetRoomId,
          targetEdgeIndex: link.targetEdgeIndex,
          sourceEdge,
          targetEdge
        };
      }

function getRoomLinkedEdgeGuide(roomId, edgeIndex) {
        const link = getEdgeLink(roomId, edgeIndex);
        if (!link) return null;
        const room = RoomEditor.Model.getRoomById(roomId);
        const targetRoom = RoomEditor.Model.getRoomById(link.targetRoomId);
        if (!room || !targetRoom) return null;

        const sourceEdge = RoomEditor.Model.getRoomEdge(room, edgeIndex);
        const targetEdge = RoomEditor.Model.getRoomEdge(targetRoom, link.targetEdgeIndex);
        const targetGlobalEdge = RoomEditor.Model.getEdgeGlobalPoints(targetRoom, link.targetEdgeIndex, targetRoom.global);
        const sourceLength = RoomEditor.Model.edgeLength(sourceEdge);
        const targetLength = RoomEditor.Model.edgeLength(targetEdge);
        if (!sourceEdge || !targetEdge || !targetGlobalEdge || sourceLength <= 0.001 || targetLength <= 0.001) return null;

        const guideLocal = {
          start: RoomEditor.Model.globalPointToRoomLocal(room, targetGlobalEdge.start),
          end: RoomEditor.Model.globalPointToRoomLocal(room, targetGlobalEdge.end)
        };
        return {
          roomId,
          edgeIndex,
          targetRoomId: link.targetRoomId,
          targetEdgeIndex: link.targetEdgeIndex,
          sourceEdge,
          targetEdge,
          sourceLength,
          targetLength,
          guideLocal,
          guideCanvas: {
            start: RoomEditor.Viewport.roomToCanvasPoint(guideLocal.start.x, guideLocal.start.y),
            end: RoomEditor.Viewport.roomToCanvasPoint(guideLocal.end.x, guideLocal.end.y)
          }
        };
      }

function getRoomVertexLinkSnapTargets(room, vertexIndex) {
        RoomEditor.Model.ensureRoomShape(room);
        if (!room.polygon.length) return [];
        const count = room.polygon.length;
        const targets = [];

        const outgoingGuide = getRoomLinkedEdgeGuide(room.id, vertexIndex);
        if (outgoingGuide) {
          targets.push({
            roomId: room.id,
            vertexIndex,
            edgeIndex: outgoingGuide.edgeIndex,
            guideLocal: outgoingGuide.guideLocal,
            guideCanvas: outgoingGuide.guideCanvas
          });
        }

        const incomingEdgeIndex = ((vertexIndex - 1) % count + count) % count;
        const incomingGuide = getRoomLinkedEdgeGuide(room.id, incomingEdgeIndex);
        if (incomingGuide) {
          targets.push({
            roomId: room.id,
            vertexIndex,
            edgeIndex: incomingGuide.edgeIndex,
            guideLocal: incomingGuide.guideLocal,
            guideCanvas: incomingGuide.guideCanvas
          });
        }

        return targets;
      }

function getNearestRoomVertexLinkSnap(room, vertexIndex, mouse) {
        const targets = getRoomVertexLinkSnapTargets(room, vertexIndex);
        let best = null;
        targets.forEach((target) => {
          const projected = RoomEditor.Input.distanceToSegment(mouse, target.guideCanvas.start, target.guideCanvas.end);
          const point = RoomEditor.Viewport.canvasToRoomPointRaw(projected.point.x, projected.point.y);
          if (!best || projected.distance < best.distance) {
            best = {
              ...target,
              point,
              canvas: projected.point,
              distance: projected.distance
            };
          }
        });
        if (!best || best.distance > RoomEditor.Constants.HIT_LINK_GUIDE_PAD) return null;
        return best;
      }

function worldDistancePointToSegment(px, py, ax, ay, bx, by) {
        const abx = bx - ax;
        const aby = by - ay;
        const apx = px - ax;
        const apy = py - ay;
        const l2 = abx * abx + aby * aby;
        if (l2 < 1e-18) return Math.hypot(px - ax, py - ay);
        let t = (apx * abx + apy * aby) / l2;
        t = Math.max(0, Math.min(1, t));
        const qx = ax + t * abx;
        const qy = ay + t * aby;
        return Math.hypot(px - qx, py - qy);
      }

function edgeSnapAlignmentErrorWorld(snappedEdge, targetEdge) {
        const aToB = Math.max(
          worldDistancePointToSegment(
            snappedEdge.start.x,
            snappedEdge.start.y,
            targetEdge.start.x,
            targetEdge.start.y,
            targetEdge.end.x,
            targetEdge.end.y
          ),
          worldDistancePointToSegment(
            snappedEdge.end.x,
            snappedEdge.end.y,
            targetEdge.start.x,
            targetEdge.start.y,
            targetEdge.end.x,
            targetEdge.end.y
          )
        );
        const bToA = Math.max(
          worldDistancePointToSegment(
            targetEdge.start.x,
            targetEdge.start.y,
            snappedEdge.start.x,
            snappedEdge.start.y,
            snappedEdge.end.x,
            snappedEdge.end.y
          ),
          worldDistancePointToSegment(
            targetEdge.end.x,
            targetEdge.end.y,
            snappedEdge.start.x,
            snappedEdge.start.y,
            snappedEdge.end.x,
            snappedEdge.end.y
          )
        );
        return Math.max(aToB, bToA);
      }

function getRoomSnapCandidate(room) {
        RoomEditor.Model.ensureRoomShape(room);
        if (!room.edgeLinks.length) return null;

        const projection = RoomEditor.Viewport.globalScale();
        const snapThreshold = 36 / projection.scale;
        let best = null;

        room.edgeLinks.forEach((link) => {
          const targetRoom = RoomEditor.Model.getRoomById(link.targetRoomId);
          if (!targetRoom) return;

          const sourceEdge = RoomEditor.Model.getEdgeGlobalPoints(room, link.edgeIndex, room.global);
          const targetEdge = RoomEditor.Model.getEdgeGlobalPoints(targetRoom, link.targetEdgeIndex, targetRoom.global);
          if (!sourceEdge || !targetEdge) return;

          const sourceMid = {
            x: (sourceEdge.start.x + sourceEdge.end.x) / 2,
            y: (sourceEdge.start.y + sourceEdge.end.y) / 2
          };
          const targetMid = {
            x: (targetEdge.start.x + targetEdge.end.x) / 2,
            y: (targetEdge.start.y + targetEdge.end.y) / 2
          };
          const candidateDeltas = [
            {
              proposedGlobal: {
                x: room.global.x + (targetMid.x - sourceMid.x),
                y: room.global.y + (targetMid.y - sourceMid.y)
              }
            },
            {
              proposedGlobal: {
                x: room.global.x + (targetEdge.start.x - sourceEdge.start.x),
                y: room.global.y + (targetEdge.start.y - sourceEdge.start.y)
              }
            },
            {
              proposedGlobal: {
                x: room.global.x + (targetEdge.end.x - sourceEdge.end.x),
                y: room.global.y + (targetEdge.end.y - sourceEdge.end.y)
              }
            },
            {
              proposedGlobal: {
                x: room.global.x + (targetEdge.end.x - sourceEdge.start.x),
                y: room.global.y + (targetEdge.end.y - sourceEdge.start.y)
              }
            },
            {
              proposedGlobal: {
                x: room.global.x + (targetEdge.start.x - sourceEdge.end.x),
                y: room.global.y + (targetEdge.start.y - sourceEdge.end.y)
              }
            }
          ];

          candidateDeltas.forEach((entry) => {
            const snappedEdge = RoomEditor.Model.getEdgeGlobalPoints(room, link.edgeIndex, entry.proposedGlobal);
            if (!snappedEdge) return;
            const error = edgeSnapAlignmentErrorWorld(snappedEdge, targetEdge);
            const candidate = {
              roomId: room.id,
              edgeIndex: link.edgeIndex,
              targetRoomId: link.targetRoomId,
              targetEdgeIndex: link.targetEdgeIndex,
              proposedGlobal: entry.proposedGlobal,
              error
            };
            if (!best || candidate.error < best.error) best = candidate;
          });
        });

        if (!best || best.error > snapThreshold) return null;
        return best;
      }

function applyRoomSnapCandidate(room, candidate) {
        if (!room || !candidate) return false;
        const groupRoomIds = RoomEditor.Model.getSnapRoomGroup(candidate);
        if (!groupRoomIds.length || groupRoomIds.includes(candidate.targetRoomId)) {
          return false;
        }
        const snapshot = RoomEditor.Model.snapshotGlobalRoomGroup(groupRoomIds);
        const dx = candidate.proposedGlobal.x - room.global.x;
        const dy = candidate.proposedGlobal.y - room.global.y;
        RoomEditor.Model.applyGlobalRoomGroupDelta(snapshot, dx, dy);
        return true;
      }

function getSpecificEdgeSnapCandidate(roomId, edgeIndex) {
        const room = RoomEditor.Model.getRoomById(roomId);
        const link = getEdgeLink(roomId, edgeIndex);
        if (!room || !link) return null;
        const originalLinks = room.edgeLinks;
        try {
          room.edgeLinks = room.edgeLinks.filter((entry) => Number(entry.edgeIndex) === Number(edgeIndex));
          return getRoomSnapCandidate(room);
        } finally {
          room.edgeLinks = originalLinks;
        }
      }

  Module.getEdgeLink = getEdgeLink;
  Module.clearRoomEdgeLink = clearRoomEdgeLink;
  Module.clearAllRoomEdgeLinks = clearAllRoomEdgeLinks;
  Module.remapRoomEdgeLinks = remapRoomEdgeLinks;
  Module.isRoomEdgeRemoved = isRoomEdgeRemoved;
  Module.remapRoomRemovedEdges = remapRoomRemovedEdges;
  Module.toggleRoomEdgeRemoved = toggleRoomEdgeRemoved;
  Module.setRoomEdgeLink = setRoomEdgeLink;
  Module.getLinkedEdgeGuide = getLinkedEdgeGuide;
  Module.getRoomLinkedEdgeGuide = getRoomLinkedEdgeGuide;
  Module.getRoomVertexLinkSnapTargets = getRoomVertexLinkSnapTargets;
  Module.getNearestRoomVertexLinkSnap = getNearestRoomVertexLinkSnap;
  Module.worldDistancePointToSegment = worldDistancePointToSegment;
  Module.edgeSnapAlignmentErrorWorld = edgeSnapAlignmentErrorWorld;
  Module.getRoomSnapCandidate = getRoomSnapCandidate;
  Module.applyRoomSnapCandidate = applyRoomSnapCandidate;
  Module.getSpecificEdgeSnapCandidate = getSpecificEdgeSnapCandidate;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Topology = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
