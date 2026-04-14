'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Input ? root.RoomEditor.Input : {};

function linkSelectedGlobalEdge() {
        const selected = RoomEditor.State.selectedGlobalEdge;
        if (!selected) return;
        const targetRoomId = RoomEditor.Ui.refs.edgeTargetRoom.value;
        const targetEdgeIndex = Number(RoomEditor.Ui.refs.edgeTargetIndex.value);
        if (!targetRoomId || !Number.isInteger(targetEdgeIndex)) return;
        const linked = RoomEditor.Topology.setRoomEdgeLink(selected.roomId, selected.edgeIndex, targetRoomId, targetEdgeIndex);
        if (!linked) {
          RoomEditor.Ui.setStatus('Edge link failed. Check that both rooms and edges are valid.');
          return;
        }
        RoomEditor.State.globalSnapPreview = null;
        RoomEditor.Ui.updateGlobalLinkControls();
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus(`Linked ${selected.roomId} edge ${selected.edgeIndex + 1} to ${targetRoomId} edge ${targetEdgeIndex + 1}.`);
      }

function clearSelectedGlobalEdgeLink() {
        const selected = RoomEditor.State.selectedGlobalEdge;
        if (!selected) return;
        const existingLink = RoomEditor.Topology.getEdgeLink(selected.roomId, selected.edgeIndex);
        if (!existingLink) return;
        RoomEditor.Topology.clearRoomEdgeLink(selected.roomId, selected.edgeIndex, true);
        RoomEditor.State.globalSnapPreview = null;
        RoomEditor.Ui.updateGlobalLinkControls();
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus(`Cleared link for ${selected.roomId} edge ${selected.edgeIndex + 1}.`);
      }

function snapSelectedGlobalEdge() {
        const selected = RoomEditor.State.selectedGlobalEdge;
        if (!selected) return;
        const room = RoomEditor.Model.getRoomById(selected.roomId);
        const candidate = RoomEditor.Topology.getSpecificEdgeSnapCandidate(selected.roomId, selected.edgeIndex);
        if (!room || !candidate) {
          RoomEditor.Ui.setStatus('No snap target available for the selected edge.');
          return;
        }
        if (!RoomEditor.Topology.applyRoomSnapCandidate(room, candidate)) {
          RoomEditor.Ui.setStatus('Snap could not move this room group without pulling the target side with it.');
          return;
        }
        RoomEditor.State.globalSnapPreview = candidate;
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus(`Snapped ${selected.roomId} edge ${selected.edgeIndex + 1} to ${candidate.targetRoomId} edge ${candidate.targetEdgeIndex + 1}.`);
      }

function resolveSelected() {
        const room = RoomEditor.Model.currentRoom();
        if (!RoomEditor.State.selected) return null;
        if (RoomEditor.State.selected.kind === 'room-shell') {
          return { room, item: room, kind: 'room-shell' };
        }
        if (RoomEditor.State.selected.kind === 'vertex') {
          const point = room.polygon[RoomEditor.State.selected.index];
          if (point) {
            return {
              room,
              item: { x: point[0], y: point[1] },
              kind: 'vertex'
            };
          }
        }
        if (RoomEditor.State.selected.kind === 'platform') {
          const item = room.platforms.find((platform) => platform.id === RoomEditor.State.selected.id);
          if (item) return { room, item, collection: room.platforms };
        }
        if (RoomEditor.State.selected.kind === 'mover') {
          const item = room.movingPlatforms.find((mover) => mover.id === RoomEditor.State.selected.id);
          if (item) return { room, item, collection: room.movingPlatforms };
        }
        if (RoomEditor.State.selected.kind === 'mover-start' || RoomEditor.State.selected.kind === 'mover-end') {
          const item = room.movingPlatforms.find((mover) => mover.id === RoomEditor.State.selected.id);
          if (item) return { room, item, collection: room.movingPlatforms };
        }
        if (RoomEditor.State.selected.kind === 'door') {
          const item = room.doors.find((door) => door.id === RoomEditor.State.selected.id);
          if (item) return { room, item, collection: room.doors };
        }
        if (RoomEditor.State.selected.kind === 'key') {
          const item = room.keys.find((key) => key.id === RoomEditor.State.selected.id);
          if (item) return { room, item, collection: room.keys };
        }
        if (RoomEditor.State.selected.kind === 'ability') {
          const item = room.abilities.find((ability) => ability.id === RoomEditor.State.selected.id);
          if (item) return { room, item, collection: room.abilities };
        }
        if (RoomEditor.State.selected.kind === 'start' && room.playerStart) {
          return { room, item: room.playerStart, kind: 'start' };
        }
        return null;
      }

function pointDistance(a, b) {
        return Math.hypot(a.x - b.x, a.y - b.y);
      }

function distanceToSegment(point, a, b) {
        const l2 = ((b.x - a.x) ** 2) + ((b.y - a.y) ** 2);
        if (l2 === 0) {
          return {
            distance: pointDistance(point, a),
            point: { x: a.x, y: a.y }
          };
        }
        let t = ((point.x - a.x) * (b.x - a.x) + (point.y - a.y) * (b.y - a.y)) / l2;
        t = Math.max(0, Math.min(1, t));
        const proj = {
          x: a.x + t * (b.x - a.x),
          y: a.y + t * (b.y - a.y)
        };
        return { distance: pointDistance(point, proj), point: proj };
      }

function normalizeRect(a, b) {
        return {
          x1: Math.min(a.x, b.x),
          y1: Math.min(a.y, b.y),
          x2: Math.max(a.x, b.x),
          y2: Math.max(a.y, b.y)
        };
      }

function pointInRect(point, rect) {
        return point.x >= rect.x1 && point.x <= rect.x2 && point.y >= rect.y1 && point.y <= rect.y2;
      }

function rectIntersectsRect(a, b) {
        return !(a.x2 < b.x1 || a.x1 > b.x2 || a.y2 < b.y1 || a.y1 > b.y2);
      }

function buildSelectionFromRect(startLocal, endLocal) {
        const room = RoomEditor.Model.currentRoom();
        const rect = normalizeRect(startLocal, endLocal);
        const items = [];

        if (room.playerStart && pointInRect(room.playerStart, rect)) {
          items.push({ kind: 'start' });
        }

        room.polygon.forEach(([x, y], index) => {
          if (pointInRect({ x, y }, rect)) items.push({ kind: 'vertex', index });
        });

        room.platforms.forEach((platform) => {
          const bounds = {
            x1: platform.x,
            y1: platform.y - RoomEditor.Constants.PLATFORM_H,
            x2: platform.x + (platform.len * RoomEditor.Constants.TILE),
            y2: platform.y
          };
          if (rectIntersectsRect(rect, bounds)) items.push({ kind: 'platform', id: platform.id });
        });

        room.doors.forEach((door) => {
          const bounds = {
            x1: door.x - 24,
            y1: door.y - 36,
            x2: door.x + 24,
            y2: door.y + 36
          };
          if (rectIntersectsRect(rect, bounds)) items.push({ kind: 'door', id: door.id });
        });

        room.keys.forEach((key) => {
          const bounds = {
            x1: key.x - 16,
            y1: key.y - 16,
            x2: key.x + 36,
            y2: key.y + 16
          };
          if (rectIntersectsRect(rect, bounds)) items.push({ kind: 'key', id: key.id });
        });

        room.abilities.forEach((ability) => {
          const bounds = {
            x1: ability.x - 18,
            y1: ability.y - 18,
            x2: ability.x + 18,
            y2: ability.y + 18
          };
          if (rectIntersectsRect(rect, bounds)) items.push({ kind: 'ability', id: ability.id });
        });

        room.movingPlatforms.forEach((mover) => {
          const x1 = Math.min(mover.x, mover.endX);
          const y1 = Math.min(mover.y, mover.endY) - RoomEditor.Constants.PLATFORM_H;
          const x2 = Math.max(mover.x + (mover.len * RoomEditor.Constants.TILE), mover.endX + (mover.len * RoomEditor.Constants.TILE));
          const y2 = Math.max(mover.y, mover.endY);
          if (rectIntersectsRect(rect, { x1, y1, x2, y2 })) items.push({ kind: 'mover', id: mover.id });
        });

        const roomBounds = RoomEditor.Model.getRoomBounds();
        const coversRoom = rect.x1 <= roomBounds.x1 && rect.y1 <= roomBounds.y1 &&
          rect.x2 >= roomBounds.x2 && rect.y2 >= roomBounds.y2;
        if (coversRoom) return [{ kind: 'room-shell' }];

        return items;
      }

function snapshotSelectionItems() {
        const room = RoomEditor.Model.currentRoom();
        return RoomEditor.State.selectionItems.map((item) => {
          if (item.kind === 'vertex') {
            const point = room.polygon[item.index];
            return { ...item, x: point[0], y: point[1] };
          }
          if (item.kind === 'platform') {
            const platform = room.platforms.find((entry) => entry.id === item.id);
            return { ...item, x: platform.x, y: platform.y };
          }
          if (item.kind === 'door') {
            const door = room.doors.find((entry) => entry.id === item.id);
            return { ...item, x: door.x, y: door.y };
          }
          if (item.kind === 'key') {
            const key = room.keys.find((entry) => entry.id === item.id);
            return { ...item, x: key.x, y: key.y };
          }
          if (item.kind === 'ability') {
            const ability = room.abilities.find((entry) => entry.id === item.id);
            return { ...item, x: ability.x, y: ability.y };
          }
          if (item.kind === 'mover') {
            const mover = room.movingPlatforms.find((entry) => entry.id === item.id);
            return { ...item, x: mover.x, y: mover.y, endX: mover.endX, endY: mover.endY };
          }
          if (item.kind === 'start' && room.playerStart) {
            return { kind: 'start', x: room.playerStart.x, y: room.playerStart.y };
          }
          if (item.kind === 'room-shell') {
            return {
              kind: 'room-shell',
              polygon: room.polygon.map(([x, y]) => [x, y]),
              platforms: room.platforms.map((platform) => ({ id: platform.id, x: platform.x, y: platform.y })),
              doors: room.doors.map((door) => ({ id: door.id, x: door.x, y: door.y })),
              keys: room.keys.map((key) => ({ id: key.id, x: key.x, y: key.y })),
              abilities: room.abilities.map((ability) => ({ id: ability.id, x: ability.x, y: ability.y })),
              movingPlatforms: room.movingPlatforms.map((mover) => ({ id: mover.id, x: mover.x, y: mover.y, endX: mover.endX, endY: mover.endY })),
              playerStart: room.playerStart ? { x: room.playerStart.x, y: room.playerStart.y } : null
            };
          }
          return item;
        });
      }

function moveSelection(dx, dy, snapshot) {
        const room = RoomEditor.Model.currentRoom();
        snapshot.forEach((item) => {
          if (item.kind === 'vertex') {
            room.polygon[item.index] = [RoomEditor.State.snap(item.x + dx), RoomEditor.State.snap(item.y + dy)];
          }
          if (item.kind === 'platform') {
            const platform = room.platforms.find((entry) => entry.id === item.id);
            if (platform) {
              platform.x = RoomEditor.State.snap(item.x + dx);
              platform.y = RoomEditor.State.snap(item.y + dy);
            }
          }
          if (item.kind === 'door') {
            const door = room.doors.find((entry) => entry.id === item.id);
            if (door) {
              door.x = RoomEditor.State.snap(item.x + dx);
              door.y = RoomEditor.State.snap(item.y + dy);
            }
          }
          if (item.kind === 'key') {
            const key = room.keys.find((entry) => entry.id === item.id);
            if (key) {
              key.x = RoomEditor.State.snap(item.x + dx);
              key.y = RoomEditor.State.snap(item.y + dy);
            }
          }
          if (item.kind === 'ability') {
            const ability = room.abilities.find((entry) => entry.id === item.id);
            if (ability) {
              ability.x = RoomEditor.State.snap(item.x + dx);
              ability.y = RoomEditor.State.snap(item.y + dy);
            }
          }
          if (item.kind === 'mover') {
            const mover = room.movingPlatforms.find((entry) => entry.id === item.id);
            if (mover) {
              mover.x = RoomEditor.State.snap(item.x + dx);
              mover.y = RoomEditor.State.snap(item.y + dy);
              mover.endX = RoomEditor.State.snap(item.endX + dx);
              mover.endY = RoomEditor.State.snap(item.endY + dy);
            }
          }
          if (item.kind === 'start' && room.playerStart) {
            room.playerStart.x = RoomEditor.State.snap(item.x + dx);
            room.playerStart.y = RoomEditor.State.snap(item.y + dy);
          }
          if (item.kind === 'room-shell') {
            room.polygon = item.polygon.map(([x, y]) => [RoomEditor.State.snap(x + dx), RoomEditor.State.snap(y + dy)]);
            item.platforms.forEach((platformState) => {
              const platform = room.platforms.find((entry) => entry.id === platformState.id);
              if (platform) {
                platform.x = RoomEditor.State.snap(platformState.x + dx);
                platform.y = RoomEditor.State.snap(platformState.y + dy);
              }
            });
            item.doors.forEach((doorState) => {
              const door = room.doors.find((entry) => entry.id === doorState.id);
              if (door) {
                door.x = RoomEditor.State.snap(doorState.x + dx);
                door.y = RoomEditor.State.snap(doorState.y + dy);
              }
            });
            item.keys.forEach((keyState) => {
              const key = room.keys.find((entry) => entry.id === keyState.id);
              if (key) {
                key.x = RoomEditor.State.snap(keyState.x + dx);
                key.y = RoomEditor.State.snap(keyState.y + dy);
              }
            });
            item.abilities.forEach((abilityState) => {
              const ability = room.abilities.find((entry) => entry.id === abilityState.id);
              if (ability) {
                ability.x = RoomEditor.State.snap(abilityState.x + dx);
                ability.y = RoomEditor.State.snap(abilityState.y + dy);
              }
            });
            item.movingPlatforms.forEach((moverState) => {
              const mover = room.movingPlatforms.find((entry) => entry.id === moverState.id);
              if (mover) {
                mover.x = RoomEditor.State.snap(moverState.x + dx);
                mover.y = RoomEditor.State.snap(moverState.y + dy);
                mover.endX = RoomEditor.State.snap(moverState.endX + dx);
                mover.endY = RoomEditor.State.snap(moverState.endY + dy);
              }
            });
            if (item.playerStart && room.playerStart) {
              room.playerStart.x = RoomEditor.State.snap(item.playerStart.x + dx);
              room.playerStart.y = RoomEditor.State.snap(item.playerStart.y + dy);
            }
          }
        });
      }

function hitTestRoomEditor(mouse) {
        const room = RoomEditor.Model.currentRoom();
        if (room.playerStart) {
          const p = RoomEditor.Viewport.roomToCanvasPoint(room.playerStart.x, room.playerStart.y);
          if (pointDistance(mouse, p) < 20) {
            return { kind: 'start' };
          }
        }
        for (let i = 0; i < room.polygon.length; i += 1) {
          const p = RoomEditor.Viewport.roomToCanvasPoint(room.polygon[i][0], room.polygon[i][1]);
          if (pointDistance(mouse, p) < RoomEditor.Constants.HIT_VERTEX) {
            return { kind: 'vertex', index: i };
          }
        }
        for (const door of room.doors) {
          const p = RoomEditor.Viewport.roomToCanvasPoint(door.x, door.y);
          if (mouse.x >= p.x - RoomEditor.Constants.HIT_DOOR_X && mouse.x <= p.x + RoomEditor.Constants.HIT_DOOR_X && mouse.y >= p.y - RoomEditor.Constants.HIT_DOOR_Y && mouse.y <= p.y + RoomEditor.Constants.HIT_DOOR_Y) {
            return { kind: 'door', id: door.id };
          }
        }
        for (const key of room.keys) {
          const p = RoomEditor.Viewport.roomToCanvasPoint(key.x, key.y);
          if (mouse.x >= p.x - 18 && mouse.x <= p.x + 34 && mouse.y >= p.y - 18 && mouse.y <= p.y + 18) {
            return { kind: 'key', id: key.id };
          }
        }
        for (const ability of room.abilities) {
          const p = RoomEditor.Viewport.roomToCanvasPoint(ability.x, ability.y);
          if (mouse.x >= p.x - 18 && mouse.x <= p.x + 18 && mouse.y >= p.y - 18 && mouse.y <= p.y + 18) {
            return { kind: 'ability', id: ability.id };
          }
        }
        for (const mover of room.movingPlatforms) {
          const start = RoomEditor.Viewport.roomToCanvasPoint(mover.x, mover.y - RoomEditor.Constants.PLATFORM_H / 2);
          const end = RoomEditor.Viewport.roomToCanvasPoint(mover.endX, mover.endY - RoomEditor.Constants.PLATFORM_H / 2);
          const width = mover.len * RoomEditor.Constants.TILE * RoomEditor.Viewport.roomScale().x;
          const height = RoomEditor.Constants.PLATFORM_H * RoomEditor.Viewport.roomScale().y;
          const startHandle = { x: start.x + (width / 2), y: start.y + (height / 2) };
          const endHandle = { x: end.x + (width / 2), y: end.y + (height / 2) };
          if (pointDistance(mouse, startHandle) < 14) {
            return { kind: 'mover-start', id: mover.id };
          }
          if (pointDistance(mouse, endHandle) < 14) {
            return { kind: 'mover-end', id: mover.id };
          }
          const bounds = {
            x1: Math.min(start.x, end.x) - RoomEditor.Constants.HIT_PLATFORM_PAD,
            y1: Math.min(start.y, end.y) - RoomEditor.Constants.HIT_PLATFORM_PAD,
            x2: Math.max(start.x + width, end.x + width) + RoomEditor.Constants.HIT_PLATFORM_PAD,
            y2: Math.max(start.y + height, end.y + height) + RoomEditor.Constants.HIT_PLATFORM_PAD
          };
          if (mouse.x >= bounds.x1 && mouse.x <= bounds.x2 && mouse.y >= bounds.y1 && mouse.y <= bounds.y2) {
            return { kind: 'mover', id: mover.id };
          }
        }
        for (const platform of room.platforms) {
          const p = RoomEditor.Viewport.roomToCanvasPoint(platform.x, platform.y - RoomEditor.Constants.PLATFORM_H / 2);
          const width = platform.len * RoomEditor.Constants.TILE * RoomEditor.Viewport.roomScale().x;
          const height = RoomEditor.Constants.PLATFORM_H * RoomEditor.Viewport.roomScale().y;
          if (mouse.x >= p.x - RoomEditor.Constants.HIT_PLATFORM_PAD && mouse.x <= p.x + width + RoomEditor.Constants.HIT_PLATFORM_PAD && mouse.y >= p.y - RoomEditor.Constants.HIT_PLATFORM_PAD && mouse.y <= p.y + height + RoomEditor.Constants.HIT_PLATFORM_PAD) {
            return { kind: 'platform', id: platform.id };
          }
        }
        for (let edgeIndex = 0; edgeIndex < RoomEditor.Model.getEdgeCount(room); edgeIndex += 1) {
          const edgeCanvas = RoomEditor.Render.getRoomLocalEdgeCanvasPoints(room, edgeIndex);
          if (!edgeCanvas) continue;
          const result = distanceToSegment(mouse, edgeCanvas.start, edgeCanvas.end);
          if (result.distance <= RoomEditor.Constants.HIT_ROOM_EDGE_PAD) {
            return { kind: 'room-edge', edgeIndex };
          }
        }
        return null;
      }

function hitTestGlobal(mouse) {
        const reversed = [...RoomEditor.State.data.rooms].reverse();
        let nearest = null;

        for (const room of reversed) {
          const polygon = RoomEditor.Model.getGlobalRoomPoints(room);
          let nearestEdge = null;
          for (let edgeIndex = 0; edgeIndex < polygon.length; edgeIndex += 1) {
            const a = polygon[edgeIndex];
            const b = polygon[(edgeIndex + 1) % polygon.length];
            const distance = RoomEditor.Render.distanceToCanvasSegment(mouse, a, b);
            if (!nearestEdge || distance < nearestEdge.distance) {
              nearestEdge = { kind: 'edge', roomId: room.id, edgeIndex, distance };
            }
          }
          if (nearestEdge && nearestEdge.distance <= RoomEditor.Constants.HIT_GLOBAL_PAD) {
            return nearestEdge;
          }

          if (RoomEditor.Render.pointInCanvasPolygon(mouse, polygon)) {
            return { kind: 'room', roomId: room.id };
          }

          const distance = RoomEditor.Render.distanceToCanvasPolygon(mouse, polygon);
          if (!nearest || distance < nearest.distance) {
            nearest = { kind: 'room', roomId: room.id, distance };
          }
        }

        if (nearest && nearest.distance <= RoomEditor.Constants.HIT_GLOBAL_PAD) {
          return nearest;
        }

        return null;
      }

function addVertexAt(mouse) {
        const room = RoomEditor.Model.currentRoom();
        if (RoomEditor.State.selectedGlobalEdge?.roomId === room.id) {
          RoomEditor.State.selectedGlobalEdge = null;
          RoomEditor.State.globalSnapPreview = null;
        }
        const oldEdgeCount = RoomEditor.Model.getEdgeCount(room);
        const local = RoomEditor.Viewport.canvasToRoomPoint(mouse.x, mouse.y);
        let best = { index: 0, distance: Infinity };
        for (let i = 0; i < room.polygon.length; i += 1) {
          const a = { x: room.polygon[i][0], y: room.polygon[i][1] };
          const b = { x: room.polygon[(i + 1) % room.polygon.length][0], y: room.polygon[(i + 1) % room.polygon.length][1] };
          const result = distanceToSegment(local, a, b);
          if (result.distance < best.distance) {
            best = { index: i + 1, distance: result.distance, point: result.point };
          }
        }
        room.polygon.splice(best.index, 0, [RoomEditor.State.snap(best.point.x), RoomEditor.State.snap(best.point.y)]);
        const splitEdgeIndex = ((best.index - 1) % oldEdgeCount + oldEdgeCount) % oldEdgeCount;
        RoomEditor.Topology.remapRoomEdgeLinks(room.id, (edgeIndex) => {
          if (edgeIndex === splitEdgeIndex) return null;
          return edgeIndex >= best.index ? edgeIndex + 1 : edgeIndex;
        });
        RoomEditor.Topology.remapRoomRemovedEdges(room.id, (edgeIndex) => {
          if (edgeIndex === splitEdgeIndex) {
            const firstEdgeIndex = edgeIndex >= best.index ? edgeIndex + 1 : edgeIndex;
            return [firstEdgeIndex, best.index];
          }
          return edgeIndex >= best.index ? edgeIndex + 1 : edgeIndex;
        });
        RoomEditor.State.setSelection([{ kind: 'vertex', index: best.index }]);
        RoomEditor.State.setDirty(true);
        RoomEditor.Wizard.syncRoomWizardEdgeSelects();
      }

function addPlatformAt(mouse) {
        const room = RoomEditor.Model.currentRoom();
        const local = RoomEditor.Viewport.canvasToRoomPoint(mouse.x, mouse.y);
        const platform = {
          id: RoomEditor.Model.nextId(`${room.id}-P`, room.platforms),
          x: local.x,
          y: local.y,
          len: 4,
          tint: 0
        };
        room.platforms.push(platform);
        // Task 2.5a: glow pulse on placement
        RoomEditor.State.lastPlacedId = platform.id;
        setTimeout(() => { RoomEditor.State.lastPlacedId = null; RoomEditor.Render.redraw(); }, 600);
        RoomEditor.State.setSelection([{ kind: 'platform', id: platform.id }]);
        RoomEditor.State.setDirty(true);
      }

function addDoorAt(mouse) {
        const room = RoomEditor.Model.currentRoom();
        const local = RoomEditor.Viewport.canvasToRoomPoint(mouse.x, mouse.y);
        const door = {
          id: RoomEditor.Model.nextId(`${room.id}-D`, room.doors),
          x: local.x,
          y: local.y,
          kind: 'transition',
          label: 'New Door',
          targetRoom: '',
          initialState: {
            forward: 'unlocked',
            reverse: 'unlocked'
          }
        };
        room.doors.push(door);
        RoomEditor.State.lastPlacedId = door.id;
        setTimeout(() => { RoomEditor.State.lastPlacedId = null; RoomEditor.Render.redraw(); }, 600);
        RoomEditor.State.setSelection([{ kind: 'door', id: door.id }]);
        RoomEditor.State.setDirty(true);
        RoomEditor.Ui.setStatus(`Added door ${door.id} at ${door.x}, ${door.y}`);
      }

function addKeyAt(mouse) {
        const room = RoomEditor.Model.currentRoom();
        const local = RoomEditor.Viewport.canvasToRoomPoint(mouse.x, mouse.y);
        const key = {
          id: RoomEditor.Model.nextId(`${room.id}-K`, room.keys),
          x: local.x,
          y: local.y,
          label: 'New Key',
          unlocksTarget: ''
        };
        room.keys.push(key);
        RoomEditor.State.lastPlacedId = key.id;
        setTimeout(() => { RoomEditor.State.lastPlacedId = null; RoomEditor.Render.redraw(); }, 600);
        RoomEditor.State.setSelection([{ kind: 'key', id: key.id }]);
        RoomEditor.State.setDirty(true);
        RoomEditor.Ui.setStatus(`Added key ${key.id} at ${key.x}, ${key.y}.`);
      }

function addAbilityAt(mouse) {
        const room = RoomEditor.Model.currentRoom();
        const local = RoomEditor.Viewport.canvasToRoomPoint(mouse.x, mouse.y);
        const ability = {
          id: RoomEditor.Model.nextId(`${room.id}-A`, room.abilities),
          x: local.x,
          y: local.y,
          type: RoomEditor.Ui.refs.abilityType.value || RoomEditor.Constants.ABILITY_DEFS[0].id
        };
        room.abilities.push(ability);
        RoomEditor.State.lastPlacedId = ability.id;
        setTimeout(() => { RoomEditor.State.lastPlacedId = null; RoomEditor.Render.redraw(); }, 600);
        RoomEditor.State.setSelection([{ kind: 'ability', id: ability.id }]);
        RoomEditor.State.setDirty(true);
        RoomEditor.Ui.setStatus(`Added ${RoomEditor.Model.getAbilityLabel(ability.type)} ${ability.id} at ${ability.x}, ${ability.y}.`);
      }

function addMoverPoint(mouse) {
        const room = RoomEditor.Model.currentRoom();
        const local = RoomEditor.Viewport.canvasToRoomPoint(mouse.x, mouse.y);
        if (!RoomEditor.State.pendingMoverStart) {
          RoomEditor.State.pendingMoverStart = local;
          RoomEditor.State.hoverLocal = local;
          RoomEditor.Ui.setStatus(`Mover start set at ${local.x}, ${local.y}. Tap end point.`);
          RoomEditor.Render.redraw();
          return;
        }

        const start = RoomEditor.State.pendingMoverStart;
        const rawDx = local.x - start.x;
        const rawDy = local.y - start.y;
        const horizontal = Math.abs(rawDx) >= Math.abs(rawDy);
        const mover = {
          id: RoomEditor.Model.nextId(`${room.id}-M`, room.movingPlatforms),
          x: start.x,
          y: start.y,
          endX: horizontal ? local.x : start.x,
          endY: horizontal ? start.y : local.y,
          len: 4,
          tint: 0,
          initialState: 'unlocked'
        };
        room.movingPlatforms.push(mover);
        RoomEditor.State.pendingMoverStart = null;
        RoomEditor.State.hoverLocal = null;
        RoomEditor.State.lastPlacedId = mover.id;
        setTimeout(() => { RoomEditor.State.lastPlacedId = null; RoomEditor.Render.redraw(); }, 600);
        RoomEditor.State.setSelection([{ kind: 'mover', id: mover.id }]);
        RoomEditor.State.setDirty(true);
        RoomEditor.Ui.setStatus(`Added mover ${mover.id} from ${mover.x},${mover.y} to ${mover.endX},${mover.endY}.`);
      }

function setPlayerStartAt(mouse) {
        const room = RoomEditor.Model.currentRoom();
        const local = RoomEditor.Viewport.canvasToRoomPoint(mouse.x, mouse.y);
        room.playerStart = { x: local.x, y: local.y };
        RoomEditor.State.setSelection([{ kind: 'start' }]);
        RoomEditor.State.setDirty(true);
        RoomEditor.Ui.setStatus(`Set player start for ${room.id} at ${room.playerStart.x}, ${room.playerStart.y}.`);
      }

function onRoomPointerDown(event) {
        if (event.cancelable) event.preventDefault();
        if (!RoomEditor.Model.currentRoom()) return;
        if (typeof event.pointerId === 'number' && RoomEditor.Viewport.roomCanvas.setPointerCapture) {
          RoomEditor.Viewport.roomCanvas.setPointerCapture(event.pointerId);
        }
        const mouse = RoomEditor.Viewport.getCanvasPointer(event, RoomEditor.Viewport.roomCanvas);
        const hit = hitTestRoomEditor(mouse);
        const local = RoomEditor.Viewport.canvasToRoomPoint(mouse.x, mouse.y);

        if (RoomEditor.State.tool === 'vertex') {
          addVertexAt(mouse);
          RoomEditor.Render.redraw();
          return;
        }
        if (RoomEditor.State.tool === 'platform') {
          addPlatformAt(mouse);
          RoomEditor.Render.redraw();
          return;
        }
        if (RoomEditor.State.tool === 'door') {
          addDoorAt(mouse);
          RoomEditor.Render.redraw();
          return;
        }
        if (RoomEditor.State.tool === 'key') {
          addKeyAt(mouse);
          RoomEditor.Render.redraw();
          return;
        }
        if (RoomEditor.State.tool === 'ability') {
          addAbilityAt(mouse);
          RoomEditor.Render.redraw();
          return;
        }
        if (RoomEditor.State.tool === 'mover') {
          addMoverPoint(mouse);
          return;
        }
        if (RoomEditor.State.tool === 'start') {
          setPlayerStartAt(mouse);
          RoomEditor.Render.redraw();
          return;
        }

        if (hit) {
          const alreadySelected = RoomEditor.State.selectionContains(hit);
          if (!alreadySelected || RoomEditor.State.selectionItems.length <= 1) {
            RoomEditor.State.setSelection([hit]);
          }
          if (RoomEditor.State.selectionItems.length > 1 || RoomEditor.State.selected?.kind === 'room-shell') {
            RoomEditor.State.drag = {
              type: 'selection-move',
              startLocal: local,
              snapshot: snapshotSelectionItems()
            };
          } else if (hit.kind === 'mover-start' || hit.kind === 'mover-end') {
            RoomEditor.State.drag = {
              type: hit.kind,
              id: hit.id
            };
          } else if (hit.kind === 'mover') {
            const mover = room.movingPlatforms.find((item) => item.id === hit.id);
            RoomEditor.State.drag = {
              type: 'mover',
              id: hit.id,
              startLocal: local,
              snapshot: { x: mover.x, y: mover.y, endX: mover.endX, endY: mover.endY }
            };
          } else if (hit.kind === 'start') {
            RoomEditor.State.drag = { type: 'start' };
          } else if (hit.kind === 'room-edge') {
            RoomEditor.State.drag = null;
          } else if (hit.kind === 'vertex') {
            RoomEditor.State.drag = {
              type: 'vertex',
              index: hit.index,
              startCanvas: { ...mouse },
              snapReleased: false,
              snapRearmBlocked: true
            };
          } else {
            RoomEditor.State.drag = { type: hit.kind, id: hit.id };
          }
          RoomEditor.Render.redraw();
        } else {
          RoomEditor.State.setSelection([]);
          RoomEditor.State.drag = {
            type: 'marquee',
            startCanvas: mouse,
            currentCanvas: mouse,
            startLocal: local,
            currentLocal: local
          };
          RoomEditor.Render.redraw();
        }
      }

function onRoomPointerMove(event) {
        if (event.cancelable) event.preventDefault();
        if (!RoomEditor.Model.currentRoom()) return;
        const mouse = RoomEditor.Viewport.getCanvasPointer(event, RoomEditor.Viewport.roomCanvas);
        const local = RoomEditor.Viewport.canvasToRoomPoint(mouse.x, mouse.y);
        if (!RoomEditor.State.drag) {
          if (RoomEditor.State.tool === 'mover' && RoomEditor.State.pendingMoverStart) {
            RoomEditor.State.hoverLocal = local;
            RoomEditor.Render.redraw();
          }
          return;
        }
        const room = RoomEditor.Model.currentRoom();
        RoomEditor.State.hoverLocal = local;

        if (RoomEditor.State.drag.type === 'marquee') {
          RoomEditor.State.drag.currentCanvas = mouse;
          RoomEditor.State.drag.currentLocal = local;
          RoomEditor.Render.redraw();
          return;
        }

        if (RoomEditor.State.drag.type === 'selection-move') {
          const dx = local.x - RoomEditor.State.drag.startLocal.x;
          const dy = local.y - RoomEditor.State.drag.startLocal.y;
          moveSelection(dx, dy, RoomEditor.State.drag.snapshot);
          RoomEditor.Render.redraw();
          return;
        }

        if (RoomEditor.State.drag.type === 'vertex') {
          let snapTarget = null;
          const dragDistance = pointDistance(mouse, RoomEditor.State.drag.startCanvas);
          if (!RoomEditor.State.drag.snapReleased && dragDistance > 4) {
            RoomEditor.State.drag.snapReleased = true;
          }
          if (RoomEditor.State.drag.snapRearmBlocked && dragDistance > 10) {
            RoomEditor.State.drag.snapRearmBlocked = false;
          } else if (RoomEditor.State.drag.snapReleased) {
            snapTarget = RoomEditor.Topology.getNearestRoomVertexLinkSnap(room, RoomEditor.State.drag.index, mouse);
          }
          const nextPoint = snapTarget ? snapTarget.point : local;
          room.polygon[RoomEditor.State.drag.index] = [nextPoint.x, nextPoint.y];
        }
        if (RoomEditor.State.drag.type === 'platform') {
          const platform = room.platforms.find((item) => item.id === RoomEditor.State.drag.id);
          if (platform) {
            platform.x = local.x;
            platform.y = local.y;
          }
        }
        if (RoomEditor.State.drag.type === 'door') {
          const door = room.doors.find((item) => item.id === RoomEditor.State.drag.id);
          if (door) {
            door.x = local.x;
            door.y = local.y;
          }
        }
        if (RoomEditor.State.drag.type === 'key') {
          const key = room.keys.find((item) => item.id === RoomEditor.State.drag.id);
          if (key) {
            key.x = local.x;
            key.y = local.y;
          }
        }
        if (RoomEditor.State.drag.type === 'ability') {
          const ability = room.abilities.find((item) => item.id === RoomEditor.State.drag.id);
          if (ability) {
            ability.x = local.x;
            ability.y = local.y;
          }
        }
        if (RoomEditor.State.drag.type === 'mover') {
          const mover = room.movingPlatforms.find((item) => item.id === RoomEditor.State.drag.id);
          if (mover) {
            const dx = local.x - RoomEditor.State.drag.startLocal.x;
            const dy = local.y - RoomEditor.State.drag.startLocal.y;
            mover.x = RoomEditor.State.snap(RoomEditor.State.drag.snapshot.x + dx);
            mover.y = RoomEditor.State.snap(RoomEditor.State.drag.snapshot.y + dy);
            mover.endX = RoomEditor.State.snap(RoomEditor.State.drag.snapshot.endX + dx);
            mover.endY = RoomEditor.State.snap(RoomEditor.State.drag.snapshot.endY + dy);
          }
        }
        if (RoomEditor.State.drag.type === 'mover-start') {
          const mover = room.movingPlatforms.find((item) => item.id === RoomEditor.State.drag.id);
          if (mover) {
            mover.x = local.x;
            mover.y = local.y;
          }
        }
        if (RoomEditor.State.drag.type === 'mover-end') {
          const mover = room.movingPlatforms.find((item) => item.id === RoomEditor.State.drag.id);
          if (mover) {
            mover.endX = local.x;
            mover.endY = local.y;
          }
        }
        if (RoomEditor.State.drag.type === 'start' && room.playerStart) {
          room.playerStart.x = local.x;
          room.playerStart.y = local.y;
        }
        RoomEditor.Render.redraw();
      }

function onGlobalPointerDown(event) {
        if (event.cancelable) event.preventDefault();
        const mouse = RoomEditor.Viewport.getCanvasPointer(event, RoomEditor.Viewport.globalCanvas);
        const hit = hitTestGlobal(mouse);
        RoomEditor.State.globalSnapPreview = null;
        if (!hit) {
          RoomEditor.State.setSelectedGlobalEdge(null);
          RoomEditor.Render.redraw();
          return;
        }
        RoomEditor.State.currentRoomId = hit.roomId;
        RoomEditor.Ui.refs.roomSelect.value = hit.roomId;
        if (hit.kind === 'edge') {
          RoomEditor.State.setSelectedGlobalEdge({ roomId: hit.roomId, edgeIndex: hit.edgeIndex });
        } else if (RoomEditor.State.selectedGlobalEdge && RoomEditor.State.selectedGlobalEdge.roomId !== hit.roomId) {
          RoomEditor.State.setSelectedGlobalEdge(null);
        }
        const groupRoomIds = RoomEditor.Model.getLinkedRoomGroup(hit.roomId);
        RoomEditor.State.drag = {
          type: 'room',
          roomId: hit.roomId,
          groupRoomIds,
          startCanvas: mouse,
          startGlobal: RoomEditor.Viewport.canvasToGlobalPoint(mouse.x, mouse.y),
          snapshot: RoomEditor.Model.snapshotGlobalRoomGroup(groupRoomIds),
          pending: true
        };
        RoomEditor.Render.redraw();
      }

function onGlobalPointerMove(event) {
        if (!RoomEditor.State.drag || RoomEditor.State.drag.type !== 'room') return;
        if (event.cancelable) event.preventDefault();
        const mouse = RoomEditor.Viewport.getCanvasPointer(event, RoomEditor.Viewport.globalCanvas);
        if (RoomEditor.State.drag.pending) {
          if (pointDistance(mouse, RoomEditor.State.drag.startCanvas) < RoomEditor.Constants.GLOBAL_DRAG_START_DISTANCE) {
            return;
          }
          RoomEditor.State.drag.pending = false;
        }
        const local = RoomEditor.Viewport.canvasToGlobalPoint(mouse.x, mouse.y);
        const dx = local.x - RoomEditor.State.drag.startGlobal.x;
        const dy = local.y - RoomEditor.State.drag.startGlobal.y;
        RoomEditor.Model.applyGlobalRoomGroupDelta(RoomEditor.State.drag.snapshot, dx, dy);
        RoomEditor.State.globalSnapPreview = null;
        RoomEditor.Render.redraw();
      }

function endDrag() {
        const hadGlobalRoomDrag = RoomEditor.State.drag && RoomEditor.State.drag.type === 'room';
        const hadMoveDrag = RoomEditor.State.drag && ['selection-move', 'vertex', 'platform', 'door', 'key', 'ability', 'mover', 'mover-start', 'mover-end', 'start'].includes(RoomEditor.State.drag.type);
        if (RoomEditor.State.drag && RoomEditor.State.drag.type === 'marquee') {
          const items = buildSelectionFromRect(RoomEditor.State.drag.startLocal, RoomEditor.State.drag.currentLocal);
          RoomEditor.State.setSelection(items);
          RoomEditor.Render.redraw();
        }
        RoomEditor.State.globalSnapPreview = null;
        RoomEditor.State.drag = null;
        if (RoomEditor.State.tool !== 'mover') {
          RoomEditor.State.hoverLocal = null;
        }
        if (hadMoveDrag || hadGlobalRoomDrag) RoomEditor.State.setDirty(true);
        if (hadGlobalRoomDrag) RoomEditor.Render.redraw();
      }

function applyPropertyInputs() {
        const room = RoomEditor.Model.currentRoom();
        const selected = resolveSelected();
        if (selected) {
          const nextX = Number(RoomEditor.Ui.refs.itemX.value || selected.item.x || 0);
          const nextY = Number(RoomEditor.Ui.refs.itemY.value || selected.item.y || 0);
          if (RoomEditor.State.selected.kind === 'vertex') {
            room.polygon[RoomEditor.State.selected.index] = [nextX, nextY];
          } else {
            selected.item.x = nextX;
            selected.item.y = nextY;
          }
          if (RoomEditor.State.selected.kind === 'platform') {
            selected.item.len = Math.max(1, Number(RoomEditor.Ui.refs.itemLen.value || selected.item.len || 1));
            selected.item.tint = Number(RoomEditor.Ui.refs.itemTint.value || selected.item.tint || 0);
          }
          if (RoomEditor.State.selected.kind === 'mover' || RoomEditor.State.selected.kind === 'mover-start' || RoomEditor.State.selected.kind === 'mover-end') {
            selected.item.endX = Number(RoomEditor.Ui.refs.moverEndX.value || selected.item.endX || selected.item.x || 0);
            selected.item.endY = Number(RoomEditor.Ui.refs.moverEndY.value || selected.item.endY || selected.item.y || 0);
            selected.item.len = Math.max(1, Number(RoomEditor.Ui.refs.moverLen.value || selected.item.len || 1));
            selected.item.tint = Number(RoomEditor.Ui.refs.moverTint.value || selected.item.tint || 0);
            selected.item.initialState = RoomEditor.Ui.refs.moverInitialState.value === 'locked' ? 'locked' : 'unlocked';
          }
          if (RoomEditor.State.selected.kind === 'door') {
            selected.item.label = RoomEditor.Ui.refs.doorLabel.value;
            selected.item.targetRoom = RoomEditor.Ui.refs.doorTarget.value;
            selected.item.initialState = {
              forward: RoomEditor.Ui.refs.doorStateForward.value === 'locked' ? 'locked' : 'unlocked',
              reverse: RoomEditor.Ui.refs.doorStateReverse.value === 'locked' ? 'locked' : 'unlocked'
            };
          }
          if (RoomEditor.State.selected.kind === 'key') {
            selected.item.label = RoomEditor.Ui.refs.keyLabel.value;
            selected.item.unlocksTarget = RoomEditor.Ui.refs.keyDoorTarget.value.trim();
          }
          if (RoomEditor.State.selected.kind === 'ability') {
            selected.item.type = RoomEditor.Model.getAbilityDef(RoomEditor.Ui.refs.abilityType.value)?.id || RoomEditor.Constants.ABILITY_DEFS[0].id;
          }
        }
        RoomEditor.State.setDirty(true);
        RoomEditor.Render.redraw();
      }

function applyRoomSizeInputs() {
        const room = RoomEditor.Model.currentRoom();
        RoomEditor.Model.ensureRoomShape(room);
        room.size.width = Math.max(320, RoomEditor.State.snap(Number(RoomEditor.Ui.refs.roomWidth.value || room.size.width)));
        room.size.height = Math.max(320, RoomEditor.State.snap(Number(RoomEditor.Ui.refs.roomHeight.value || room.size.height)));
        RoomEditor.Ui.refs.roomWidth.value = room.size.width;
        RoomEditor.Ui.refs.roomHeight.value = room.size.height;
        RoomEditor.State.setDirty(true);
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus(`Resized ${room.id} workspace to ${room.size.width} x ${room.size.height}.`);
      }

function toggleSelectedRoomEdge() {
        if (RoomEditor.State.viewMode !== 'room' || RoomEditor.State.selectionItems.length !== 1 || RoomEditor.State.selected?.kind !== 'room-edge') return;
        const room = RoomEditor.Model.currentRoom();
        const isRemoved = RoomEditor.Topology.toggleRoomEdgeRemoved(room.id, RoomEditor.State.selected.edgeIndex);
        RoomEditor.State.setDirty(true);
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus(`${room.id} edge ${RoomEditor.State.selected.edgeIndex + 1} is now ${isRemoved ? 'open' : 'solid'}.`);
      }

function deleteSelected() {
        const room = RoomEditor.Model.currentRoom();
        if (!RoomEditor.State.selected || RoomEditor.State.selectionItems.length === 0) return;
        if (RoomEditor.State.selectionItems.length === 1 && RoomEditor.State.selected.kind === 'room-edge') {
          toggleSelectedRoomEdge();
          return;
        }
        const vertexIndexes = RoomEditor.State.selectionItems
          .filter((item) => item.kind === 'vertex')
          .map((item) => item.index)
          .sort((a, b) => b - a);
        const platformIds = new Set(RoomEditor.State.selectionItems.filter((item) => item.kind === 'platform').map((item) => item.id));
        const moverIds = new Set(RoomEditor.State.selectionItems.filter((item) => item.kind === 'mover').map((item) => item.id));
        const doorIds = new Set(RoomEditor.State.selectionItems.filter((item) => item.kind === 'door').map((item) => item.id));
        const keyIds = new Set(RoomEditor.State.selectionItems.filter((item) => item.kind === 'key').map((item) => item.id));
        const abilityIds = new Set(RoomEditor.State.selectionItems.filter((item) => item.kind === 'ability').map((item) => item.id));
        const clearPlayerStart = RoomEditor.State.selectionItems.some((item) => item.kind === 'start');

        if (vertexIndexes.length && room.polygon.length - vertexIndexes.length >= 3) {
          if (RoomEditor.State.selectedGlobalEdge?.roomId === room.id) {
            RoomEditor.State.selectedGlobalEdge = null;
            RoomEditor.State.globalSnapPreview = null;
          }
          const oldEdgeCount = RoomEditor.Model.getEdgeCount(room);
          const removedIndexesAsc = [...vertexIndexes].sort((a, b) => a - b);
          const removedIndexes = new Set(removedIndexesAsc);
          vertexIndexes.forEach((index) => room.polygon.splice(index, 1));
          RoomEditor.Topology.remapRoomEdgeLinks(room.id, (edgeIndex) => {
            if (removedIndexes.has(edgeIndex) || removedIndexes.has((edgeIndex + 1) % oldEdgeCount)) {
              return null;
            }
            const shift = removedIndexesAsc.filter((index) => index < edgeIndex).length;
            return edgeIndex - shift;
          });
          RoomEditor.Topology.remapRoomRemovedEdges(room.id, (edgeIndex) => {
            if (removedIndexes.has(edgeIndex) || removedIndexes.has((edgeIndex + 1) % oldEdgeCount)) {
              return null;
            }
            const shift = removedIndexesAsc.filter((index) => index < edgeIndex).length;
            return edgeIndex - shift;
          });
          RoomEditor.Wizard.syncRoomWizardEdgeSelects();
        }
        if (platformIds.size) {
          room.platforms = room.platforms.filter((item) => !platformIds.has(item.id));
        }
        if (moverIds.size) {
          room.movingPlatforms = room.movingPlatforms.filter((item) => !moverIds.has(item.id));
        }
        if (doorIds.size) {
          room.doors = room.doors.filter((item) => !doorIds.has(item.id));
        }
        if (keyIds.size) {
          room.keys = room.keys.filter((item) => !keyIds.has(item.id));
        }
        if (abilityIds.size) {
          room.abilities = room.abilities.filter((item) => !abilityIds.has(item.id));
        }
        if (clearPlayerStart) {
          room.playerStart = null;
        }
        RoomEditor.State.setSelection([]);
        RoomEditor.State.setDirty(true);
        RoomEditor.Render.redraw();
      }

function duplicatePlatform() {
        const room = RoomEditor.Model.currentRoom();
        const platforms = RoomEditor.State.selectionItems.filter((item) => item.kind === 'platform');
        if (platforms.length !== 1) return;
        const selected = room.platforms.find((platform) => platform.id === platforms[0].id);
        if (!selected) return;
        const step = Number(RoomEditor.Ui.refs.snapSize?.value) || RoomEditor.Constants.TILE;
        const clone = {
          ...selected,
          id: RoomEditor.Model.nextId(`${room.id}-P`, room.platforms),
          x: selected.x + step,
          y: selected.y
        };
        room.platforms.push(clone);
        RoomEditor.State.setSelection([{ kind: 'platform', id: clone.id }]);
        RoomEditor.State.setDirty(true);
        RoomEditor.Render.redraw();
      }

function selectCanvasTool(tool) {
        RoomEditor.State.tool = tool;
        if (RoomEditor.State.tool !== 'mover') {
          RoomEditor.State.pendingMoverStart = null;
          RoomEditor.State.hoverLocal = null;
        }
        RoomEditor.Ui.refs.toolButtons.forEach((button) => button.classList.toggle('active', button.dataset.tool === tool));
        RoomEditor.Render.redraw();
      }

function selectItemById(itemId) {
        const room = RoomEditor.Model.currentRoom();
        if (!room) return;
        // Check all item types
        for (const platform of room.platforms) {
          if (platform.id === itemId) {
            RoomEditor.State.setSelection([{ kind: 'platform', id: itemId }]);
            RoomEditor.Ui.syncPropertyInputs();
            RoomEditor.Render.redraw();
            return;
          }
        }
        for (const door of room.doors) {
          if (door.id === itemId) {
            RoomEditor.State.setSelection([{ kind: 'door', id: itemId }]);
            RoomEditor.Ui.syncPropertyInputs();
            RoomEditor.Render.redraw();
            return;
          }
        }
        for (const key of room.keys) {
          if (key.id === itemId) {
            RoomEditor.State.setSelection([{ kind: 'key', id: itemId }]);
            RoomEditor.Ui.syncPropertyInputs();
            RoomEditor.Render.redraw();
            return;
          }
        }
        for (const ability of room.abilities) {
          if (ability.id === itemId) {
            RoomEditor.State.setSelection([{ kind: 'ability', id: itemId }]);
            RoomEditor.Ui.syncPropertyInputs();
            RoomEditor.Render.redraw();
            return;
          }
        }
        for (const mover of room.movingPlatforms) {
          if (mover.id === itemId) {
            RoomEditor.State.setSelection([{ kind: 'mover', id: itemId }]);
            RoomEditor.Ui.syncPropertyInputs();
            RoomEditor.Render.redraw();
            return;
          }
        }
      }

function deleteItemById(itemId) {
        const room = RoomEditor.Model.currentRoom();
        if (!room) return;
        const prevSelected = RoomEditor.State.selected;
        // Find and remove from whichever collection
        if (room.platforms.some((p) => p.id === itemId)) {
          room.platforms = room.platforms.filter((p) => p.id !== itemId);
        } else if (room.doors.some((d) => d.id === itemId)) {
          room.doors = room.doors.filter((d) => d.id !== itemId);
        } else if (room.keys.some((k) => k.id === itemId)) {
          room.keys = room.keys.filter((k) => k.id !== itemId);
        } else if (room.abilities.some((a) => a.id === itemId)) {
          room.abilities = room.abilities.filter((a) => a.id !== itemId);
        } else if (room.movingPlatforms.some((m) => m.id === itemId)) {
          room.movingPlatforms = room.movingPlatforms.filter((m) => m.id !== itemId);
        }
        if (prevSelected && prevSelected.id === itemId) {
          RoomEditor.State.setSelection([]);
        }
        RoomEditor.State.setDirty(true);
        RoomEditor.Render.redraw();
      }

function wireEvents() {
        if (wireEvents.__wired) return;
        wireEvents.__wired = true;
        RoomEditor.State.updateSyncButtonState();
        document.getElementById('runValidation')?.addEventListener('click', () => {
          if (!RoomEditor.State.data) return;
          const report = RoomEditor.Validation.validateLayout(RoomEditor.State.data);
          RoomEditor.State.lastValidationReport = report;
          RoomEditor.Validation.renderValidationResults(report);
        });
        RoomEditor.Ui.refs.advancedToggle?.addEventListener('click', () => {
          const expanded = RoomEditor.Ui.refs.advancedToggle.getAttribute('aria-expanded') === 'true';
          RoomEditor.Ui.refs.advancedToggle.setAttribute('aria-expanded', String(!expanded));
          if (RoomEditor.Ui.refs.advancedBody) RoomEditor.Ui.refs.advancedBody.hidden = expanded;
        });
        // ── Task 2.1: Settings toggle ──
        document.getElementById('settingsToggle')?.addEventListener('click', () => {
          const body = document.getElementById('canvasSettingsBody');
          if (body) body.hidden = !body.hidden;
        });
        // ── Task 2.2: Section collapse toggles ──
        document.querySelectorAll('.inventory-section-header').forEach((btn) => {
          btn.addEventListener('click', () => {
            const expanded = btn.getAttribute('aria-expanded') !== 'false';
            btn.setAttribute('aria-expanded', String(!expanded));
            const chevron = btn.querySelector('.collapsible-chevron');
            if (chevron) chevron.style.transform = expanded ? 'rotate(-90deg)' : '';
            const body = btn.nextElementSibling;
            if (body) body.style.display = expanded ? 'none' : '';
          });
        });
        RoomEditor.Ui.refs.roomSelect.addEventListener('change', () => {
          if (!RoomEditor.Ui.refs.roomSelect.value) return;
          if (RoomEditor.State.roomWizard.active && RoomEditor.State.roomWizard.roomId && RoomEditor.Ui.refs.roomSelect.value !== RoomEditor.State.roomWizard.roomId) {
            RoomEditor.Wizard.closeRoomWizard(true);
          }
          RoomEditor.State.currentRoomId = RoomEditor.Ui.refs.roomSelect.value;
          RoomEditor.State.pendingMoverStart = null;
          RoomEditor.State.hoverLocal = null;
          if (!RoomEditor.State.selectedGlobalEdge || RoomEditor.State.selectedGlobalEdge.roomId !== RoomEditor.State.currentRoomId) {
            RoomEditor.State.selectedGlobalEdge = null;
          }
          RoomEditor.State.setSelection([]);
          if (RoomEditor.State.workflowScope === 'room' || RoomEditor.State.workflowScope === 'art-direction') {
            RoomEditor.Wizard.syncRoomWizardFormFromRoom();
          }
          // ── Task 2.5b: Room switch canvas fade ──
          RoomEditor.Viewport.roomCanvas.style.transition = 'opacity 80ms ease';
          RoomEditor.Viewport.roomCanvas.style.opacity = '0';
          setTimeout(() => {
            RoomEditor.Render.redraw();
            RoomEditor.Viewport.roomCanvas.style.opacity = '1';
          }, 80);
        });
        RoomEditor.Ui.refs.globalZoom?.addEventListener('input', () => {
          RoomEditor.State.globalZoom = RoomEditor.Viewport.clampZoom(Number(RoomEditor.Ui.refs.globalZoom.value || 100) / 100, RoomEditor.Constants.GLOBAL_ZOOM_MIN, RoomEditor.Constants.GLOBAL_ZOOM_MAX);
          RoomEditor.Viewport.updateViewControlReadouts();
          if (RoomEditor.State.viewMode === 'global') RoomEditor.Render.redraw();
        });
        RoomEditor.Ui.refs.roomZoomOut.addEventListener('click', () => RoomEditor.Viewport.adjustRoomZoom(-0.1));
        RoomEditor.Ui.refs.roomZoomIn.addEventListener('click', () => RoomEditor.Viewport.adjustRoomZoom(0.1));
        RoomEditor.Ui.refs.roomZoomFit?.addEventListener('click', fitRoomToCanvas);
        RoomEditor.Ui.refs.roomZoomReset.addEventListener('click', resetRoomView);
        RoomEditor.Ui.refs.roomPanLeft.addEventListener('click', () => RoomEditor.Viewport.panRoomView(-RoomEditor.Constants.VIEW_PAN_STEP, 0));
        RoomEditor.Ui.refs.roomPanUp.addEventListener('click', () => RoomEditor.Viewport.panRoomView(0, -RoomEditor.Constants.VIEW_PAN_STEP));
        RoomEditor.Ui.refs.roomPanDown.addEventListener('click', () => RoomEditor.Viewport.panRoomView(0, RoomEditor.Constants.VIEW_PAN_STEP));
        RoomEditor.Ui.refs.roomPanRight.addEventListener('click', () => RoomEditor.Viewport.panRoomView(RoomEditor.Constants.VIEW_PAN_STEP, 0));
        RoomEditor.Ui.refs.globalZoomOut.addEventListener('click', () => RoomEditor.Viewport.adjustGlobalZoom(-0.1));
        RoomEditor.Ui.refs.globalZoomIn.addEventListener('click', () => RoomEditor.Viewport.adjustGlobalZoom(0.1));
        RoomEditor.Ui.refs.globalZoomReset.addEventListener('click', resetGlobalView);
        RoomEditor.Ui.refs.globalPanLeft.addEventListener('click', () => RoomEditor.Viewport.panGlobalView(-RoomEditor.Constants.VIEW_PAN_STEP, 0));
        RoomEditor.Ui.refs.globalPanUp.addEventListener('click', () => RoomEditor.Viewport.panGlobalView(0, -RoomEditor.Constants.VIEW_PAN_STEP));
        RoomEditor.Ui.refs.globalPanDown.addEventListener('click', () => RoomEditor.Viewport.panGlobalView(0, RoomEditor.Constants.VIEW_PAN_STEP));
        RoomEditor.Ui.refs.globalPanRight.addEventListener('click', () => RoomEditor.Viewport.panGlobalView(RoomEditor.Constants.VIEW_PAN_STEP, 0));
        RoomEditor.Ui.refs.roomWidth.addEventListener('change', applyRoomSizeInputs);
        RoomEditor.Ui.refs.roomHeight.addEventListener('change', applyRoomSizeInputs);
        RoomEditor.Ui.refs.addRoom.addEventListener('click', addRoom);
        RoomEditor.Ui.refs.roomSetupBtn?.addEventListener('click', () => {
          const id = RoomEditor.State.currentRoomId;
          if (!id || !RoomEditor.State.data) return;
          RoomEditor.Wizard.openRoomWizard(id);
          RoomEditor.Render.redraw();
        });
        RoomEditor.Ui.refs.deleteRoom.addEventListener('click', deleteRoom);
        RoomEditor.Ui.refs.toolButtons.forEach((button) => {
          button.addEventListener('click', () => {
            RoomEditor.State.tool = button.dataset.tool;
            if (RoomEditor.State.tool !== 'mover') {
              RoomEditor.State.pendingMoverStart = null;
              RoomEditor.State.hoverLocal = null;
            }
            RoomEditor.Ui.refs.toolButtons.forEach((item) => item.classList.toggle('active', item === button));
            RoomEditor.Render.redraw();
          });
        });
        RoomEditor.Ui.refs.applyProps.addEventListener('click', applyPropertyInputs);
        RoomEditor.Ui.refs.deleteSelected.addEventListener('click', deleteSelected);
        RoomEditor.Ui.refs.toggleSelectedEdge.addEventListener('click', toggleSelectedRoomEdge);
        RoomEditor.Ui.refs.duplicatePlatform.addEventListener('click', duplicatePlatform);
        RoomEditor.Ui.refs.centerRoom.addEventListener('click', centerRoom);
        RoomEditor.Ui.refs.edgeTargetRoom.addEventListener('change', () => {
          RoomEditor.Ui.populateTargetEdgeOptions(RoomEditor.Ui.refs.edgeTargetRoom.value, null);
          RoomEditor.Ui.updateGlobalLinkControls();
        });
        RoomEditor.Ui.refs.edgeTargetIndex.addEventListener('change', updateGlobalLinkControls);
        RoomEditor.Ui.refs.linkSelectedEdge.addEventListener('click', linkSelectedGlobalEdge);
        RoomEditor.Ui.refs.clearSelectedEdgeLink.addEventListener('click', clearSelectedGlobalEdgeLink);
        RoomEditor.Ui.refs.snapSelectedEdge.addEventListener('click', snapSelectedGlobalEdge);
        RoomEditor.Ui.refs.reloadJson.addEventListener('click', () => RoomEditor.Storage.loadData(true));
        RoomEditor.Ui.refs.applyJson.addEventListener('click', applyJsonText);
        RoomEditor.Ui.refs.downloadJson.addEventListener('click', downloadJson);
        RoomEditor.Ui.refs.downloadRuntimePackage?.addEventListener('click', downloadExportPackage);
        RoomEditor.Ui.refs.saveJsonFile.addEventListener('click', saveJsonToFile);
        RoomEditor.Ui.refs.savePermanent.addEventListener('click', savePermanent);
        RoomEditor.Ui.refs.syncCanonicalJson.addEventListener('click', syncCanonicalJson);
        RoomEditor.Ui.refs.openGameWithLayout.addEventListener('click', () => RoomEditor.GamePreview.openGameWithLayout(RoomEditor.State.currentRoomId));
        RoomEditor.Ui.refs.clearSavedLayout.addEventListener('click', clearSavedLayout);
        RoomEditor.Ui.refs.inspectorClose?.addEventListener('click', dismissSelection);

        RoomEditor.Viewport.roomCanvas.addEventListener('pointerdown', onRoomPointerDown);
        RoomEditor.Viewport.roomCanvas.addEventListener('pointermove', onRoomPointerMove);
        RoomEditor.Viewport.roomCanvas.addEventListener('touchstart', onRoomPointerDown, { passive: false });
        RoomEditor.Viewport.roomCanvas.addEventListener('touchmove', onRoomPointerMove, { passive: false });
        RoomEditor.Viewport.globalCanvas.addEventListener('pointerdown', onGlobalPointerDown);
        RoomEditor.Viewport.globalCanvas.addEventListener('pointermove', onGlobalPointerMove);
        RoomEditor.Viewport.globalCanvas.addEventListener('touchstart', onGlobalPointerDown, { passive: false });
        RoomEditor.Viewport.globalCanvas.addEventListener('touchmove', onGlobalPointerMove, { passive: false });
        window.addEventListener('pointerup', endDrag);
        window.addEventListener('pointercancel', endDrag);
        window.addEventListener('touchend', endDrag, { passive: false });
        window.addEventListener('touchcancel', endDrag, { passive: false });
        window.addEventListener('pagehide', () => {
          if (!RoomEditor.State.data || !RoomEditor.State.isDirty) return;
          try {
            window.localStorage.setItem(RoomEditor.State.LAYOUT_STORAGE_KEY, JSON.stringify(RoomEditor.State.data, null, 2));
            if (!RoomEditor.State.LOCAL_SLOT || RoomEditor.State.PROJECT_ID) {
              window.localStorage.setItem(RoomEditor.State.getLayoutPreferBrowserKey(), '1');
            }
          } catch (_) {}
        });
        window.addEventListener('error', () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          if (RoomEditor.State.roomWizard.aiRequestPending && room) {
            RoomEditor.Wizard.postRoomWizardFeedback(room, 'crash_near_ai_use', {}, { keepalive: true });
          }
        });
        window.addEventListener('unhandledrejection', () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          if (RoomEditor.State.roomWizard.aiRequestPending && room) {
            RoomEditor.Wizard.postRoomWizardFeedback(room, 'crash_near_ai_use', {}, { keepalive: true });
          }
        });
        window.addEventListener('keydown', (event) => {
          if (event.defaultPrevented) return;
          const target = event.target;
          const tagName = target?.tagName;
          const isTypingTarget = target?.isContentEditable || tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT';
          if (event.key === 'Escape') {
            const gp = document.getElementById('gamePreviewOverlay');
            if (gp && !gp.hidden) {
              RoomEditor.GamePreview.closeGamePreview();
              event.preventDefault();
              return;
            }
            const rwPrev = document.getElementById('rwOptbPreviewModal');
            if (rwPrev && !rwPrev.hidden) {
              RoomEditor.WizardOptionB?.closePreviewModal?.();
              event.preventDefault();
              return;
            }
            if (RoomEditor.State.roomWizard.active) {
              RoomEditor.Wizard.requestCloseRoomWizard();
              event.preventDefault();
              return;
            }
            if (RoomEditor.State.selectionItems.length) {
              RoomEditor.State.dismissSelection();
              event.preventDefault();
            }
            return;
          }
          if (isTypingTarget || event.metaKey || event.ctrlKey || event.altKey) return;
          if (RoomEditor.State.roomWizard.active && RoomEditor.State.workflowScope !== 'art-direction') {
            if (event.key === '[' || event.key === 'ArrowLeft') {
              RoomEditor.WizardOptionB?.navigatePhase?.(-1);
              event.preventDefault();
              return;
            }
            if (event.key === ']' || event.key === 'ArrowRight') {
              RoomEditor.WizardOptionB?.navigatePhase?.(1);
              event.preventDefault();
              return;
            }
          }
          const toolMap = {
            v: 'select',
            e: 'vertex',
            n: 'vertex',
            p: 'platform',
            d: 'door',
            k: 'key',
            a: 'ability',
            m: 'mover',
            s: 'start',
            g: 'room-move'
          };
          const tool = toolMap[event.key.toLowerCase()];
          if (!tool) return;
          RoomEditor.State.tool = tool;
          if (RoomEditor.State.tool !== 'mover') {
            RoomEditor.State.pendingMoverStart = null;
            RoomEditor.State.hoverLocal = null;
          }
          RoomEditor.Ui.refs.toolButtons.forEach((button) => button.classList.toggle('active', button.dataset.tool === tool));
          RoomEditor.Render.redraw();
          event.preventDefault();
        });
      }

  Module.linkSelectedGlobalEdge = linkSelectedGlobalEdge;
  Module.clearSelectedGlobalEdgeLink = clearSelectedGlobalEdgeLink;
  Module.snapSelectedGlobalEdge = snapSelectedGlobalEdge;
  Module.resolveSelected = resolveSelected;
  Module.pointDistance = pointDistance;
  Module.distanceToSegment = distanceToSegment;
  Module.normalizeRect = normalizeRect;
  Module.pointInRect = pointInRect;
  Module.rectIntersectsRect = rectIntersectsRect;
  Module.buildSelectionFromRect = buildSelectionFromRect;
  Module.snapshotSelectionItems = snapshotSelectionItems;
  Module.moveSelection = moveSelection;
  Module.hitTestRoomEditor = hitTestRoomEditor;
  Module.hitTestGlobal = hitTestGlobal;
  Module.addVertexAt = addVertexAt;
  Module.addPlatformAt = addPlatformAt;
  Module.addDoorAt = addDoorAt;
  Module.addKeyAt = addKeyAt;
  Module.addAbilityAt = addAbilityAt;
  Module.addMoverPoint = addMoverPoint;
  Module.setPlayerStartAt = setPlayerStartAt;
  Module.onRoomPointerDown = onRoomPointerDown;
  Module.onRoomPointerMove = onRoomPointerMove;
  Module.onGlobalPointerDown = onGlobalPointerDown;
  Module.onGlobalPointerMove = onGlobalPointerMove;
  Module.endDrag = endDrag;
  Module.applyPropertyInputs = applyPropertyInputs;
  Module.applyRoomSizeInputs = applyRoomSizeInputs;
  Module.toggleSelectedRoomEdge = toggleSelectedRoomEdge;
  Module.deleteSelected = deleteSelected;
  Module.duplicatePlatform = duplicatePlatform;
  Module.selectCanvasTool = selectCanvasTool;
  Module.selectItemById = selectItemById;
  Module.deleteItemById = deleteItemById;
  Module.wireEvents = wireEvents;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Input = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
