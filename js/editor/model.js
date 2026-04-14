'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Model ? root.RoomEditor.Model : {};

function getAbilityDef(type) {
        return RoomEditor.Constants.ABILITY_DEFS.find((entry) => entry.id === type) || RoomEditor.Constants.ABILITY_DEFS[0];
      }

function getAbilityLabel(type) {
        return getAbilityDef(type)?.label || type || 'Ability';
      }

function currentRoom() {
        return RoomEditor.State.data.rooms.find((room) => room.id === RoomEditor.State.currentRoomId);
      }

function ensureRoomShape(room) {
        if (!room.size) room.size = { width: RoomEditor.Constants.ROOM_W, height: RoomEditor.Constants.ROOM_H };
        room.size.width = Math.max(320, Number(room.size.width || RoomEditor.Constants.ROOM_W));
        room.size.height = Math.max(320, Number(room.size.height || RoomEditor.Constants.ROOM_H));
        room.platforms = Array.isArray(room.platforms) ? room.platforms : [];
        room.doors = Array.isArray(room.doors) ? room.doors : [];
        room.keys = Array.isArray(room.keys) ? room.keys : [];
        room.abilities = Array.isArray(room.abilities) ? room.abilities : [];
        room.movingPlatforms = Array.isArray(room.movingPlatforms) ? room.movingPlatforms : [];
        room.edgeLinks = Array.isArray(room.edgeLinks) ? room.edgeLinks : [];
        room.removedEdges = Array.isArray(room.removedEdges)
          ? room.removedEdges
          : Array.isArray(room.openEdges)
            ? room.openEdges
            : [];
        room.doors = room.doors.map((door) => ({
          ...door,
          initialState: {
            forward: door?.initialState?.forward === 'locked' ? 'locked' : 'unlocked',
            reverse: door?.initialState?.reverse === 'locked' ? 'locked' : 'unlocked'
          }
        }));
        room.keys = room.keys.map((key) => ({
          ...key,
          label: key?.label || 'Key',
          unlocksTarget: key?.unlocksTarget || key?.unlocksDoor || ''
        }));
        room.abilities = room.abilities.map((ability) => ({
          ...ability,
          type: getAbilityDef(ability?.type)?.id || RoomEditor.Constants.ABILITY_DEFS[0].id
        }));
        room.movingPlatforms = room.movingPlatforms.map((mover) => ({
          ...mover,
          endX: Number.isFinite(Number(mover?.endX)) ? Number(mover.endX) : Number(mover?.x || 0),
          endY: Number.isFinite(Number(mover?.endY)) ? Number(mover.endY) : Number(mover?.y || 0),
          len: Math.max(1, Number(mover?.len || 4)),
          tint: Number(mover?.tint || 0),
          initialState: mover?.initialState === 'locked' ? 'locked' : 'unlocked'
        }));
        const legacyLevers = Array.isArray(room.levers) ? room.levers : [];
        legacyLevers.forEach((lever) => {
          const moverId = lever?.controlsMover;
          if (!moverId) return;
          const mover = room.movingPlatforms.find((item) => item.id === moverId);
          if (mover) mover.initialState = lever?.initialState === 'locked' ? 'locked' : 'unlocked';
        });
        delete room.levers;
        room.playerStart = room.playerStart && Number.isFinite(Number(room.playerStart.x)) && Number.isFinite(Number(room.playerStart.y))
          ? { x: Number(room.playerStart.x), y: Number(room.playerStart.y) }
          : null;
        room.polygon = Array.isArray(room.polygon) && room.polygon.length >= 3
          ? room.polygon
          : [[160, 160], [1200, 160], [1200, 980], [160, 980]];
        room.edgeLinks = room.edgeLinks
          .map((link) => ({
            edgeIndex: Number(link?.edgeIndex),
            targetRoomId: String(link?.targetRoomId || ''),
            targetEdgeIndex: Number(link?.targetEdgeIndex)
          }))
          .filter((link) => Number.isInteger(link.edgeIndex) && link.edgeIndex >= 0 && Number.isInteger(link.targetEdgeIndex) && link.targetEdgeIndex >= 0 && link.targetRoomId);
        room.removedEdges = [...new Set(
          room.removedEdges
            .map((edgeIndex) => Number(edgeIndex))
            .filter((edgeIndex) => Number.isInteger(edgeIndex) && edgeIndex >= 0 && edgeIndex < room.polygon.length)
        )].sort((a, b) => a - b);
        delete room.openEdges;
      }

function getRoomById(roomId) {
        return RoomEditor.State.data.rooms.find((room) => room.id === roomId) || null;
      }

function getLinkedRoomGroup(roomId) {
        const visited = new Set();
        const queue = roomId ? [roomId] : [];
        while (queue.length) {
          const currentRoomId = queue.shift();
          if (!currentRoomId || visited.has(currentRoomId)) continue;
          visited.add(currentRoomId);
          const room = getRoomById(currentRoomId);
          if (!room) continue;
          ensureRoomShape(room);
          room.edgeLinks.forEach((link) => {
            if (link.targetRoomId && !visited.has(link.targetRoomId)) {
              queue.push(link.targetRoomId);
            }
          });
        }
        return [...visited];
      }

function getSnapRoomGroup(candidate) {
        if (!candidate?.roomId) return [];
        const visited = new Set();
        const queue = [candidate.roomId];
        while (queue.length) {
          const currentRoomId = queue.shift();
          if (!currentRoomId || visited.has(currentRoomId)) continue;
          visited.add(currentRoomId);
          const room = getRoomById(currentRoomId);
          if (!room) continue;
          ensureRoomShape(room);
          room.edgeLinks.forEach((link) => {
            const isBlockedForward = currentRoomId === candidate.roomId &&
              Number(link.edgeIndex) === Number(candidate.edgeIndex) &&
              link.targetRoomId === candidate.targetRoomId &&
              Number(link.targetEdgeIndex) === Number(candidate.targetEdgeIndex);
            const isBlockedReverse = currentRoomId === candidate.targetRoomId &&
              Number(link.edgeIndex) === Number(candidate.targetEdgeIndex) &&
              link.targetRoomId === candidate.roomId &&
              Number(link.targetEdgeIndex) === Number(candidate.edgeIndex);
            if (isBlockedForward || isBlockedReverse) return;
            if (link.targetRoomId && !visited.has(link.targetRoomId)) {
              queue.push(link.targetRoomId);
            }
          });
        }
        return [...visited];
      }

function snapshotGlobalRoomGroup(roomIds) {
        return roomIds
          .map((roomId) => {
            const room = getRoomById(roomId);
            if (!room) return null;
            return { roomId, x: room.global.x, y: room.global.y };
          })
          .filter(Boolean);
      }

function applyGlobalRoomGroupDelta(snapshot, dx, dy) {
        snapshot.forEach((entry) => {
          const room = getRoomById(entry.roomId);
          if (!room) return;
          room.global.x = Math.round(entry.x + dx);
          room.global.y = Math.round(entry.y + dy);
        });
      }

function getEdgeCount(room) {
        ensureRoomShape(room);
        return room.polygon.length;
      }

function getRoomEdge(room, edgeIndex) {
        ensureRoomShape(room);
        const count = room.polygon.length;
        if (!count) return null;
        const normalizedIndex = ((edgeIndex % count) + count) % count;
        const start = room.polygon[normalizedIndex];
        const end = room.polygon[(normalizedIndex + 1) % count];
        return {
          roomId: room.id,
          edgeIndex: normalizedIndex,
          start: { x: start[0], y: start[1] },
          end: { x: end[0], y: end[1] }
        };
      }

function edgeLabel(room, edgeIndex) {
        const edge = getRoomEdge(room, edgeIndex);
        if (!edge) return `Edge ${edgeIndex + 1}`;
        return `Edge ${edge.edgeIndex + 1} · (${edge.start.x}, ${edge.start.y}) -> (${edge.end.x}, ${edge.end.y})`;
      }

function getEdgeGlobalPoints(room, edgeIndex, roomGlobal = room.global) {
        const edge = getRoomEdge(room, edgeIndex);
        if (!edge) return null;
        const start = {
          x: roomGlobal.x + ((edge.start.x - (room.size.width / 2)) * RoomEditor.Constants.GLOBAL_ROOM_PREVIEW_SCALE),
          y: roomGlobal.y + ((edge.start.y - (room.size.height / 2)) * RoomEditor.Constants.GLOBAL_ROOM_PREVIEW_SCALE)
        };
        const end = {
          x: roomGlobal.x + ((edge.end.x - (room.size.width / 2)) * RoomEditor.Constants.GLOBAL_ROOM_PREVIEW_SCALE),
          y: roomGlobal.y + ((edge.end.y - (room.size.height / 2)) * RoomEditor.Constants.GLOBAL_ROOM_PREVIEW_SCALE)
        };
        return { start, end };
      }

function getEdgeCanvasPoints(room, edgeIndex) {
        const polygon = getGlobalRoomPoints(room);
        if (!polygon.length) return null;
        const normalizedIndex = ((edgeIndex % polygon.length) + polygon.length) % polygon.length;
        return {
          start: polygon[normalizedIndex],
          end: polygon[(normalizedIndex + 1) % polygon.length]
        };
      }

function edgeLength(edge) {
        if (!edge) return 0;
        return Math.hypot(edge.end.x - edge.start.x, edge.end.y - edge.start.y);
      }

function globalPointToRoomLocal(room, point) {
        ensureRoomShape(room);
        return {
          x: (room.size.width / 2) + ((point.x - room.global.x) / RoomEditor.Constants.GLOBAL_ROOM_PREVIEW_SCALE),
          y: (room.size.height / 2) + ((point.y - room.global.y) / RoomEditor.Constants.GLOBAL_ROOM_PREVIEW_SCALE)
        };
      }

function currentRoomSize() {
        const room = currentRoom();
        ensureRoomShape(room);
        return room.size;
      }

function getGlobalRoomPoints(room) {
        ensureRoomShape(room);
        const globalProjection = RoomEditor.Viewport.globalScale();
        const previewScale = globalProjection.scale * RoomEditor.Constants.GLOBAL_ROOM_PREVIEW_SCALE;
        const center = RoomEditor.Viewport.globalToCanvasPoint(room.global.x, room.global.y);
        return room.polygon.map(([x, y]) => {
          const dx = (x - room.size.width / 2) * previewScale;
          const dy = (y - room.size.height / 2) * previewScale;
          return { x: center.x + dx, y: center.y + dy };
        });
      }

function getRoomBounds() {
        const room = currentRoom();
        const xs = room.polygon.map(([x]) => x);
        const ys = room.polygon.map(([, y]) => y);
        return {
          x1: Math.min(...xs),
          y1: Math.min(...ys),
          x2: Math.max(...xs),
          y2: Math.max(...ys)
        };
      }

function nextId(prefix, collection) {
        let count = collection.length + 1;
        let id = `${prefix}${count}`;
        const ids = new Set(collection.map((item) => item.id));
        while (ids.has(id)) {
          count += 1;
          id = `${prefix}${count}`;
        }
        return id;
      }

function nextRoomId() {
        const roomNums = RoomEditor.State.data.rooms
          .map((room) => /^R(\d+)$/.exec(room.id))
          .filter(Boolean)
          .map((match) => Number(match[1]));
        const nextNum = roomNums.length ? Math.max(...roomNums) + 1 : 1;
        return `R${nextNum}`;
      }

function addRoom() {
        const roomId = nextRoomId();
        const room = {
          id: roomId,
          name: `New Room ${roomId}`,
          global: { x: 600, y: 360 },
          size: { width: RoomEditor.Constants.ROOM_W, height: RoomEditor.Constants.ROOM_H },
          polygon: [],
          playerStart: null,
          platforms: [],
          movingPlatforms: [],
          doors: [],
          keys: [],
          abilities: [],
          edgeLinks: [],
          removedEdges: [],
          environment: { version: 1, themeId: 'cave', tags: [] }
        };
        RoomEditor.Wizard.applyFootprintDimensionsToRoom(room, RoomEditor.Constants.ROOM_W, RoomEditor.Constants.ROOM_H);
        RoomEditor.State.data.rooms.push(room);
        RoomEditor.State.currentRoomId = roomId;
        RoomEditor.State.selectedGlobalEdge = null;
        RoomEditor.State.setSelection([]);
        RoomEditor.Ui.populateRoomSelect();
        RoomEditor.Ui.updateEmptyStates();
        RoomEditor.State.setDirty(true);
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus(`Added ${roomId}.`);
        RoomEditor.Wizard.openRoomWizard(roomId);
      }

function createEmptyLayoutData() {
        const roomId = 'R1';
        const room = {
          id: roomId,
          name: 'Room 1',
          global: { x: 600, y: 360 },
          size: { width: RoomEditor.Constants.ROOM_W, height: RoomEditor.Constants.ROOM_H },
          polygon: [],
          playerStart: null,
          platforms: [],
          movingPlatforms: [],
          doors: [],
          keys: [],
          abilities: [],
          edgeLinks: [],
          removedEdges: [],
          environment: { version: 1, themeId: 'cave', tags: [] }
        };
        RoomEditor.Wizard.applyFootprintDimensionsToRoom(room, RoomEditor.Constants.ROOM_W, RoomEditor.Constants.ROOM_H);
        return {
          version: 1,
          meta: {
            worldWidth: 3200,
            worldHeight: 1200,
            grid: 32,
            notes: 'Local sandbox project'
          },
          rooms: [room]
        };
      }

function deleteRoom() {
        const roomId = RoomEditor.State.currentRoomId;
        if (RoomEditor.State.roomWizard.active && RoomEditor.State.roomWizard.roomId === roomId) {
          RoomEditor.Wizard.closeRoomWizard(true);
        }
        if (RoomEditor.State.data.rooms.length <= 1) {
          if (!window.confirm('Delete the last room? The layout will be empty until you add a room (settings panel: + Add Room).')) {
            return;
          }
          RoomEditor.Topology.clearAllRoomEdgeLinks(roomId);
          RoomEditor.State.data.rooms = [];
          RoomEditor.State.currentRoomId = null;
          RoomEditor.State.selectedGlobalEdge = null;
          RoomEditor.State.setSelection([]);
          RoomEditor.Ui.populateRoomSelect();
          RoomEditor.Ui.updateEmptyStates();
          RoomEditor.State.setDirty(true);
          RoomEditor.Render.redraw();
          RoomEditor.Ui.setStatus('All rooms removed. Add a room to continue editing.');
          return;
        }
        RoomEditor.Topology.clearAllRoomEdgeLinks(roomId);
        RoomEditor.State.data.rooms = RoomEditor.State.data.rooms.filter((room) => room.id !== roomId);
        RoomEditor.State.currentRoomId = RoomEditor.State.data.rooms[0].id;
        if (RoomEditor.State.selectedGlobalEdge && RoomEditor.State.selectedGlobalEdge.roomId === roomId) {
          RoomEditor.State.selectedGlobalEdge = null;
        }
        RoomEditor.State.setSelection([]);
        RoomEditor.Ui.populateRoomSelect();
        RoomEditor.Ui.updateEmptyStates();
        RoomEditor.State.setDirty(true);
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus(`Deleted ${roomId}.`);
      }

  Module.getAbilityDef = getAbilityDef;
  Module.getAbilityLabel = getAbilityLabel;
  Module.currentRoom = currentRoom;
  Module.ensureRoomShape = ensureRoomShape;
  Module.getRoomById = getRoomById;
  Module.getLinkedRoomGroup = getLinkedRoomGroup;
  Module.getSnapRoomGroup = getSnapRoomGroup;
  Module.snapshotGlobalRoomGroup = snapshotGlobalRoomGroup;
  Module.applyGlobalRoomGroupDelta = applyGlobalRoomGroupDelta;
  Module.getEdgeCount = getEdgeCount;
  Module.getRoomEdge = getRoomEdge;
  Module.edgeLabel = edgeLabel;
  Module.getEdgeGlobalPoints = getEdgeGlobalPoints;
  Module.getEdgeCanvasPoints = getEdgeCanvasPoints;
  Module.edgeLength = edgeLength;
  Module.globalPointToRoomLocal = globalPointToRoomLocal;
  Module.currentRoomSize = currentRoomSize;
  Module.getGlobalRoomPoints = getGlobalRoomPoints;
  Module.getRoomBounds = getRoomBounds;
  Module.nextId = nextId;
  Module.nextRoomId = nextRoomId;
  Module.addRoom = addRoom;
  Module.createEmptyLayoutData = createEmptyLayoutData;
  Module.deleteRoom = deleteRoom;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Model = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
