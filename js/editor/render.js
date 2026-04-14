'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Render ? root.RoomEditor.Render : {};

function drawRoomGrid(projection, color) {
        const stepX = RoomEditor.Constants.TILE * projection.x;
        const stepY = RoomEditor.Constants.TILE * projection.y;
        if (stepX <= 0.001 || stepY <= 0.001) return;
        const { viewport } = projection;
        RoomEditor.Viewport.roomCtx.save();
        RoomEditor.Viewport.roomCtx.strokeStyle = color;
        RoomEditor.Viewport.roomCtx.lineWidth = 1;
        RoomEditor.Viewport.roomCtx.beginPath();
        const startX = projection.offsetX + (Math.floor((viewport.x - projection.offsetX) / stepX) * stepX);
        for (let x = startX; x <= viewport.x + viewport.width + stepX; x += stepX) {
          RoomEditor.Viewport.roomCtx.moveTo(x + 0.5, viewport.y);
          RoomEditor.Viewport.roomCtx.lineTo(x + 0.5, viewport.y + viewport.height);
        }
        const startY = projection.offsetY + (Math.floor((viewport.y - projection.offsetY) / stepY) * stepY);
        for (let y = startY; y <= viewport.y + viewport.height + stepY; y += stepY) {
          RoomEditor.Viewport.roomCtx.moveTo(viewport.x, y + 0.5);
          RoomEditor.Viewport.roomCtx.lineTo(viewport.x + viewport.width, y + 0.5);
        }
        RoomEditor.Viewport.roomCtx.stroke();
        RoomEditor.Viewport.roomCtx.restore();
      }

function pointInCanvasPolygon(point, polygon) {
        let inside = false;
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
          const xi = polygon[i].x;
          const yi = polygon[i].y;
          const xj = polygon[j].x;
          const yj = polygon[j].y;
          const intersects = ((yi > point.y) !== (yj > point.y)) &&
            (point.x < ((xj - xi) * (point.y - yi) / ((yj - yi) || 1e-9)) + xi);
          if (intersects) inside = !inside;
        }
        return inside;
      }

function distanceToCanvasSegment(point, a, b) {
        const l2 = ((b.x - a.x) ** 2) + ((b.y - a.y) ** 2);
        if (l2 === 0) return RoomEditor.Input.pointDistance(point, a);
        let t = ((point.x - a.x) * (b.x - a.x) + (point.y - a.y) * (b.y - a.y)) / l2;
        t = Math.max(0, Math.min(1, t));
        return RoomEditor.Input.pointDistance(point, {
          x: a.x + t * (b.x - a.x),
          y: a.y + t * (b.y - a.y)
        });
      }

function distanceToCanvasPolygon(point, polygon) {
        let minDistance = Infinity;
        for (let i = 0; i < polygon.length; i += 1) {
          const a = polygon[i];
          const b = polygon[(i + 1) % polygon.length];
          minDistance = Math.min(minDistance, distanceToCanvasSegment(point, a, b));
        }
        return minDistance;
      }

function drawGrid(ctx, width, height, cell, color) {
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let x = 0; x <= width; x += cell) {
          ctx.moveTo(x + 0.5, 0);
          ctx.lineTo(x + 0.5, height);
        }
        for (let y = 0; y <= height; y += cell) {
          ctx.moveTo(0, y + 0.5);
          ctx.lineTo(width, y + 0.5);
        }
        ctx.stroke();
        ctx.restore();
      }

function drawGlobalEdge(edgeCanvas, options = {}) {
        if (!edgeCanvas) return;
        const {
          strokeStyle = '#4ff5be',
          lineWidth = 4,
          dash = [],
          endpointFill = null
        } = options;
        RoomEditor.Viewport.globalCtx.save();
        RoomEditor.Viewport.globalCtx.strokeStyle = strokeStyle;
        RoomEditor.Viewport.globalCtx.lineWidth = lineWidth;
        RoomEditor.Viewport.globalCtx.setLineDash(dash);
        RoomEditor.Viewport.globalCtx.beginPath();
        RoomEditor.Viewport.globalCtx.moveTo(edgeCanvas.start.x, edgeCanvas.start.y);
        RoomEditor.Viewport.globalCtx.lineTo(edgeCanvas.end.x, edgeCanvas.end.y);
        RoomEditor.Viewport.globalCtx.stroke();
        RoomEditor.Viewport.globalCtx.setLineDash([]);
        if (endpointFill) {
          [edgeCanvas.start, edgeCanvas.end].forEach((point) => {
            RoomEditor.Viewport.globalCtx.beginPath();
            RoomEditor.Viewport.globalCtx.arc(point.x, point.y, 5, 0, Math.PI * 2);
            RoomEditor.Viewport.globalCtx.fillStyle = endpointFill;
            RoomEditor.Viewport.globalCtx.fill();
          });
        }
        RoomEditor.Viewport.globalCtx.restore();
      }

function drawRoomEdge(edgeCanvas, options = {}) {
        if (!edgeCanvas) return;
        const {
          strokeStyle = '#4ff5be',
          lineWidth = 5,
          dash = [],
          endpointFill = null
        } = options;
        RoomEditor.Viewport.roomCtx.save();
        RoomEditor.Viewport.roomCtx.strokeStyle = strokeStyle;
        RoomEditor.Viewport.roomCtx.lineWidth = lineWidth;
        RoomEditor.Viewport.roomCtx.setLineDash(dash);
        RoomEditor.Viewport.roomCtx.beginPath();
        RoomEditor.Viewport.roomCtx.moveTo(edgeCanvas.start.x, edgeCanvas.start.y);
        RoomEditor.Viewport.roomCtx.lineTo(edgeCanvas.end.x, edgeCanvas.end.y);
        RoomEditor.Viewport.roomCtx.stroke();
        RoomEditor.Viewport.roomCtx.setLineDash([]);
        if (endpointFill) {
          [edgeCanvas.start, edgeCanvas.end].forEach((point) => {
            RoomEditor.Viewport.roomCtx.beginPath();
            RoomEditor.Viewport.roomCtx.arc(point.x, point.y, 5, 0, Math.PI * 2);
            RoomEditor.Viewport.roomCtx.fillStyle = endpointFill;
            RoomEditor.Viewport.roomCtx.fill();
          });
        }
        RoomEditor.Viewport.roomCtx.restore();
      }

function getRoomLocalEdgeCanvasPoints(room, edgeIndex) {
        const edge = RoomEditor.Model.getRoomEdge(room, edgeIndex);
        if (!edge) return null;
        return {
          start: RoomEditor.Viewport.roomToCanvasPoint(edge.start.x, edge.start.y),
          end: RoomEditor.Viewport.roomToCanvasPoint(edge.end.x, edge.end.y)
        };
      }

function drawRoomView() {
        const room = RoomEditor.Model.currentRoom();
        const projection = RoomEditor.Viewport.roomScale();
        const scale = projection;
        const { viewport } = projection;
        RoomEditor.Viewport.roomCtx.clearRect(0, 0, RoomEditor.Viewport.roomCanvas.width, RoomEditor.Viewport.roomCanvas.height);
        RoomEditor.Viewport.roomCtx.fillStyle = '#071018';
        RoomEditor.Viewport.roomCtx.fillRect(0, 0, RoomEditor.Viewport.roomCanvas.width, RoomEditor.Viewport.roomCanvas.height);
        RoomEditor.Viewport.roomCtx.fillStyle = 'rgba(9, 26, 38, 0.92)';
        RoomEditor.Viewport.roomCtx.fillRect(
          viewport.x,
          viewport.y,
          viewport.width,
          viewport.height
        );
        RoomEditor.Viewport.roomCtx.strokeStyle = 'rgba(127, 178, 223, 0.35)';
        RoomEditor.Viewport.roomCtx.strokeRect(
          viewport.x + 0.5,
          viewport.y + 0.5,
          viewport.width - 1,
          viewport.height - 1
        );

        RoomEditor.Viewport.roomCtx.save();
        RoomEditor.Viewport.roomCtx.beginPath();
        RoomEditor.Viewport.roomCtx.rect(viewport.x, viewport.y, viewport.width, viewport.height);
        RoomEditor.Viewport.roomCtx.clip();
        drawRoomGrid(projection, 'rgba(72, 99, 124, 0.22)');

        RoomEditor.Viewport.roomCtx.save();
        RoomEditor.Viewport.roomCtx.beginPath();
        room.polygon.forEach(([x, y], index) => {
          const pt = RoomEditor.Viewport.roomToCanvasPoint(x, y);
          if (index === 0) RoomEditor.Viewport.roomCtx.moveTo(pt.x, pt.y);
          else RoomEditor.Viewport.roomCtx.lineTo(pt.x, pt.y);
        });
        RoomEditor.Viewport.roomCtx.closePath();
        RoomEditor.Viewport.roomCtx.fillStyle = 'rgba(27, 57, 80, 0.65)';
        RoomEditor.Viewport.roomCtx.strokeStyle = RoomEditor.State.selectionContains({ kind: 'room-shell' }) ? '#ffd166' : '#9bd1ff';
        RoomEditor.Viewport.roomCtx.lineWidth = RoomEditor.State.selectionContains({ kind: 'room-shell' }) ? 4 : 2;
        RoomEditor.Viewport.roomCtx.fill();
        RoomEditor.Viewport.roomCtx.stroke();
        RoomEditor.Viewport.roomCtx.restore();

        for (let edgeIndex = 0; edgeIndex < RoomEditor.Model.getEdgeCount(room); edgeIndex += 1) {
          const edgeCanvas = getRoomLocalEdgeCanvasPoints(room, edgeIndex);
          const isRemoved = RoomEditor.Topology.isRoomEdgeRemoved(room, edgeIndex);
          const isSelectedEdge = RoomEditor.State.selected?.kind === 'room-edge' && RoomEditor.State.selected.edgeIndex === edgeIndex;
          if (!isRemoved && !isSelectedEdge) continue;
          drawRoomEdge(edgeCanvas, {
            strokeStyle: isSelectedEdge ? '#ffd166' : '#ff8f5a',
            lineWidth: isSelectedEdge ? 5 : 4,
            dash: isRemoved ? [12, 8] : [],
            endpointFill: isSelectedEdge ? '#ffd166' : null
          });
        }

        room.edgeLinks.forEach((link) => {
          const isSelectedEdge = RoomEditor.State.selectedGlobalEdge?.roomId === room.id &&
            RoomEditor.State.selectedGlobalEdge.edgeIndex === link.edgeIndex;
          const localEdge = getRoomLocalEdgeCanvasPoints(room, link.edgeIndex);
          drawRoomEdge(localEdge, {
            strokeStyle: isSelectedEdge ? '#ffd166' : '#64c6ff',
            lineWidth: isSelectedEdge ? 5 : 4
          });

          const guide = RoomEditor.Topology.getRoomLinkedEdgeGuide(room.id, link.edgeIndex);
          if (!guide) return;
          drawRoomEdge(guide.guideCanvas, {
            strokeStyle: isSelectedEdge ? '#ffd166' : '#3ee6b8',
            lineWidth: isSelectedEdge ? 5 : 4,
            dash: [10, 6],
            endpointFill: isSelectedEdge ? '#ffd166' : '#3ee6b8'
          });
        });

        if (room.playerStart) {
          const p = RoomEditor.Viewport.roomToCanvasPoint(room.playerStart.x, room.playerStart.y);
          const selected = RoomEditor.State.selectionContains({ kind: 'start' });
          RoomEditor.Viewport.roomCtx.save();
          RoomEditor.Viewport.roomCtx.strokeStyle = selected ? '#ffe27a' : '#8ff7d5';
          RoomEditor.Viewport.roomCtx.fillStyle = selected ? 'rgba(255, 226, 122, 0.16)' : 'rgba(143, 247, 213, 0.16)';
          RoomEditor.Viewport.roomCtx.lineWidth = selected ? 3 : 2;
          RoomEditor.Viewport.roomCtx.beginPath();
          RoomEditor.Viewport.roomCtx.arc(p.x, p.y, 14, 0, Math.PI * 2);
          RoomEditor.Viewport.roomCtx.fill();
          RoomEditor.Viewport.roomCtx.stroke();
          RoomEditor.Viewport.roomCtx.beginPath();
          RoomEditor.Viewport.roomCtx.moveTo(p.x - 10, p.y);
          RoomEditor.Viewport.roomCtx.lineTo(p.x + 10, p.y);
          RoomEditor.Viewport.roomCtx.moveTo(p.x, p.y - 10);
          RoomEditor.Viewport.roomCtx.lineTo(p.x, p.y + 10);
          RoomEditor.Viewport.roomCtx.stroke();
          RoomEditor.Viewport.roomCtx.fillStyle = '#dffff5';
          RoomEditor.Viewport.roomCtx.font = '11px sans-serif';
          RoomEditor.Viewport.roomCtx.fillText('START', p.x + 18, p.y - 8);
          RoomEditor.Viewport.roomCtx.restore();
        }

        room.platforms.forEach((platform) => {
          const p = RoomEditor.Viewport.roomToCanvasPoint(platform.x, platform.y - RoomEditor.Constants.PLATFORM_H / 2);
          const width = platform.len * RoomEditor.Constants.TILE * scale.x;
          const height = RoomEditor.Constants.PLATFORM_H * scale.y;
          const selected = RoomEditor.State.selectionContains({ kind: 'platform', id: platform.id });
          const justPlaced = platform.id === RoomEditor.State.lastPlacedId;
          RoomEditor.Viewport.roomCtx.fillStyle = selected ? '#ffd166' : justPlaced ? '#a8d8ff' : '#6eaef6';
          RoomEditor.Viewport.roomCtx.fillRect(p.x, p.y, width, height);
          RoomEditor.Viewport.roomCtx.strokeStyle = '#102334';
          RoomEditor.Viewport.roomCtx.strokeRect(p.x, p.y, width, height);
        });

        room.movingPlatforms.forEach((mover) => {
          const start = RoomEditor.Viewport.roomToCanvasPoint(mover.x, mover.y - RoomEditor.Constants.PLATFORM_H / 2);
          const end = RoomEditor.Viewport.roomToCanvasPoint(mover.endX, mover.endY - RoomEditor.Constants.PLATFORM_H / 2);
          const width = mover.len * RoomEditor.Constants.TILE * scale.x;
          const height = RoomEditor.Constants.PLATFORM_H * scale.y;
          const selected = RoomEditor.State.selectionContains({ kind: 'mover', id: mover.id });
          const startSelected = RoomEditor.State.selectionContains({ kind: 'mover-start', id: mover.id });
          const endSelected = RoomEditor.State.selectionContains({ kind: 'mover-end', id: mover.id });
          RoomEditor.Viewport.roomCtx.save();
          RoomEditor.Viewport.roomCtx.strokeStyle = selected ? '#ffde7a' : '#8fd0ff';
          RoomEditor.Viewport.roomCtx.lineWidth = selected ? 3 : 2;
          RoomEditor.Viewport.roomCtx.setLineDash([8, 6]);
          RoomEditor.Viewport.roomCtx.beginPath();
          RoomEditor.Viewport.roomCtx.moveTo(start.x + (width / 2), start.y + (height / 2));
          RoomEditor.Viewport.roomCtx.lineTo(end.x + (width / 2), end.y + (height / 2));
          RoomEditor.Viewport.roomCtx.stroke();
          RoomEditor.Viewport.roomCtx.setLineDash([]);
          RoomEditor.Viewport.roomCtx.fillStyle = selected ? '#ffd166' : '#64c6ff';
          RoomEditor.Viewport.roomCtx.fillRect(start.x, start.y, width, height);
          RoomEditor.Viewport.roomCtx.strokeStyle = '#102334';
          RoomEditor.Viewport.roomCtx.strokeRect(start.x, start.y, width, height);
          RoomEditor.Viewport.roomCtx.strokeStyle = 'rgba(255,255,255,0.55)';
          RoomEditor.Viewport.roomCtx.strokeRect(end.x, end.y, width, height);
          RoomEditor.Viewport.roomCtx.fillStyle = startSelected ? '#ffe27a' : '#dff5ff';
          RoomEditor.Viewport.roomCtx.beginPath();
          RoomEditor.Viewport.roomCtx.arc(start.x + (width / 2), start.y + (height / 2), 7, 0, Math.PI * 2);
          RoomEditor.Viewport.roomCtx.fill();
          RoomEditor.Viewport.roomCtx.strokeStyle = '#102334';
          RoomEditor.Viewport.roomCtx.stroke();
          RoomEditor.Viewport.roomCtx.fillStyle = endSelected ? '#ffe27a' : 'rgba(223,245,255,0.7)';
          RoomEditor.Viewport.roomCtx.beginPath();
          RoomEditor.Viewport.roomCtx.arc(end.x + (width / 2), end.y + (height / 2), 7, 0, Math.PI * 2);
          RoomEditor.Viewport.roomCtx.fill();
          RoomEditor.Viewport.roomCtx.strokeStyle = '#102334';
          RoomEditor.Viewport.roomCtx.stroke();
          RoomEditor.Viewport.roomCtx.fillStyle = '#dff5ff';
          RoomEditor.Viewport.roomCtx.font = '11px sans-serif';
          RoomEditor.Viewport.roomCtx.fillText(mover.id, start.x + 4, start.y - 8);
          RoomEditor.Viewport.roomCtx.restore();
        });

        room.doors.forEach((door) => {
          const p = RoomEditor.Viewport.roomToCanvasPoint(door.x, door.y);
          const selected = RoomEditor.State.selectionContains({ kind: 'door', id: door.id });
          const justPlaced = door.id === RoomEditor.State.lastPlacedId;
          RoomEditor.Viewport.roomCtx.fillStyle = selected ? '#ffe0b3' : justPlaced ? '#ffc59f' : '#f5986e';
          RoomEditor.Viewport.roomCtx.fillRect(p.x - 10, p.y - 24, 20, 48);
          RoomEditor.Viewport.roomCtx.strokeStyle = '#3e2315';
          RoomEditor.Viewport.roomCtx.strokeRect(p.x - 10, p.y - 24, 20, 48);
          RoomEditor.Viewport.roomCtx.fillStyle = '#ffe8d1';
          RoomEditor.Viewport.roomCtx.font = '11px sans-serif';
          RoomEditor.Viewport.roomCtx.fillText(door.id, p.x + 14, p.y - 10);
        });

        room.keys.forEach((key) => {
          const p = RoomEditor.Viewport.roomToCanvasPoint(key.x, key.y);
          const selected = RoomEditor.State.selectionContains({ kind: 'key', id: key.id });
          RoomEditor.Viewport.roomCtx.save();
          RoomEditor.Viewport.roomCtx.fillStyle = selected ? '#fff09f' : '#e8d26e';
          RoomEditor.Viewport.roomCtx.strokeStyle = '#4f3f00';
          RoomEditor.Viewport.roomCtx.lineWidth = 2;
          RoomEditor.Viewport.roomCtx.beginPath();
          RoomEditor.Viewport.roomCtx.arc(p.x, p.y, 10, 0, Math.PI * 2);
          RoomEditor.Viewport.roomCtx.fill();
          RoomEditor.Viewport.roomCtx.stroke();
          RoomEditor.Viewport.roomCtx.fillRect(p.x + 8, p.y - 2, 18, 4);
          RoomEditor.Viewport.roomCtx.strokeRect(p.x + 8, p.y - 2, 18, 4);
          RoomEditor.Viewport.roomCtx.beginPath();
          RoomEditor.Viewport.roomCtx.arc(p.x + 30, p.y, 4, 0, Math.PI * 2);
          RoomEditor.Viewport.roomCtx.stroke();
          RoomEditor.Viewport.roomCtx.fillStyle = '#fff5bf';
          RoomEditor.Viewport.roomCtx.font = '11px sans-serif';
          RoomEditor.Viewport.roomCtx.fillText(key.id, p.x + 14, p.y - 12);
          RoomEditor.Viewport.roomCtx.restore();
        });

        room.abilities.forEach((ability) => {
          const p = RoomEditor.Viewport.roomToCanvasPoint(ability.x, ability.y);
          const selected = RoomEditor.State.selectionContains({ kind: 'ability', id: ability.id });
          RoomEditor.Viewport.roomCtx.save();
          RoomEditor.Viewport.roomCtx.translate(p.x, p.y);
          RoomEditor.Viewport.roomCtx.rotate(Math.PI / 4);
          RoomEditor.Viewport.roomCtx.fillStyle = selected ? '#9ae5ff' : '#52c7ff';
          RoomEditor.Viewport.roomCtx.strokeStyle = '#0b3750';
          RoomEditor.Viewport.roomCtx.lineWidth = 2;
          RoomEditor.Viewport.roomCtx.fillRect(-10, -10, 20, 20);
          RoomEditor.Viewport.roomCtx.strokeRect(-10, -10, 20, 20);
          RoomEditor.Viewport.roomCtx.restore();
          RoomEditor.Viewport.roomCtx.fillStyle = '#dff6ff';
          RoomEditor.Viewport.roomCtx.font = '11px sans-serif';
          RoomEditor.Viewport.roomCtx.fillText(ability.id, p.x + 14, p.y - 12);
          RoomEditor.Viewport.roomCtx.fillText(RoomEditor.Model.getAbilityLabel(ability.type), p.x + 14, p.y + 4);
        });

        room.polygon.forEach(([x, y], index) => {
          const p = RoomEditor.Viewport.roomToCanvasPoint(x, y);
          const selected = RoomEditor.State.selectionContains({ kind: 'vertex', index });
          RoomEditor.Viewport.roomCtx.beginPath();
          RoomEditor.Viewport.roomCtx.arc(p.x, p.y, selected ? 7 : 5, 0, Math.PI * 2);
          RoomEditor.Viewport.roomCtx.fillStyle = selected ? '#fff1b0' : '#ff6b8a';
          RoomEditor.Viewport.roomCtx.fill();
          RoomEditor.Viewport.roomCtx.strokeStyle = '#1a0e13';
          RoomEditor.Viewport.roomCtx.stroke();
        });

        if (RoomEditor.State.drag && RoomEditor.State.drag.type === 'marquee') {
          const rect = RoomEditor.Input.normalizeRect(RoomEditor.State.drag.startCanvas, RoomEditor.State.drag.currentCanvas);
          RoomEditor.Viewport.roomCtx.strokeStyle = '#ffd166';
          RoomEditor.Viewport.roomCtx.setLineDash([6, 4]);
          RoomEditor.Viewport.roomCtx.strokeRect(rect.x1, rect.y1, rect.x2 - rect.x1, rect.y2 - rect.y1);
          RoomEditor.Viewport.roomCtx.fillStyle = 'rgba(255, 209, 102, 0.12)';
          RoomEditor.Viewport.roomCtx.fillRect(rect.x1, rect.y1, rect.x2 - rect.x1, rect.y2 - rect.y1);
          RoomEditor.Viewport.roomCtx.setLineDash([]);
        }

        if (RoomEditor.State.tool === 'mover' && RoomEditor.State.pendingMoverStart) {
          const preview = RoomEditor.State.hoverLocal || RoomEditor.State.pendingMoverStart;
          const start = RoomEditor.Viewport.roomToCanvasPoint(RoomEditor.State.pendingMoverStart.x, RoomEditor.State.pendingMoverStart.y - RoomEditor.Constants.PLATFORM_H / 2);
          const end = RoomEditor.Viewport.roomToCanvasPoint(preview.x, preview.y - RoomEditor.Constants.PLATFORM_H / 2);
          RoomEditor.Viewport.roomCtx.save();
          RoomEditor.Viewport.roomCtx.strokeStyle = '#ffd166';
          RoomEditor.Viewport.roomCtx.lineWidth = 2;
          RoomEditor.Viewport.roomCtx.setLineDash([8, 6]);
          RoomEditor.Viewport.roomCtx.beginPath();
          RoomEditor.Viewport.roomCtx.moveTo(start.x, start.y);
          RoomEditor.Viewport.roomCtx.lineTo(end.x, end.y);
          RoomEditor.Viewport.roomCtx.stroke();
          RoomEditor.Viewport.roomCtx.setLineDash([]);
          RoomEditor.Viewport.roomCtx.beginPath();
          RoomEditor.Viewport.roomCtx.arc(start.x, start.y, 6, 0, Math.PI * 2);
          RoomEditor.Viewport.roomCtx.fillStyle = '#ffd166';
          RoomEditor.Viewport.roomCtx.fill();
          RoomEditor.Viewport.roomCtx.restore();
        }
        RoomEditor.Viewport.roomCtx.restore();
      }

function drawGlobalView() {
        RoomEditor.Viewport.globalCtx.clearRect(0, 0, RoomEditor.Viewport.globalCanvas.width, RoomEditor.Viewport.globalCanvas.height);
        const globalProjection = RoomEditor.Viewport.globalScale();
        drawGrid(RoomEditor.Viewport.globalCtx, RoomEditor.Viewport.globalCanvas.width, RoomEditor.Viewport.globalCanvas.height, Math.max(24, 48 * globalProjection.scale), 'rgba(72, 99, 124, 0.15)');
        RoomEditor.Viewport.globalCtx.fillStyle = '#071018';
        RoomEditor.Viewport.globalCtx.fillRect(0, 0, RoomEditor.Viewport.globalCanvas.width, RoomEditor.Viewport.globalCanvas.height);

        RoomEditor.State.data.rooms.forEach((room) => {
          const points = RoomEditor.Model.getGlobalRoomPoints(room).map((point) => [point.x, point.y]);
          const center = RoomEditor.Viewport.globalToCanvasPoint(room.global.x, room.global.y);
          RoomEditor.Viewport.globalCtx.beginPath();
          points.forEach(([x, y], index) => {
            if (index === 0) RoomEditor.Viewport.globalCtx.moveTo(x, y);
            else RoomEditor.Viewport.globalCtx.lineTo(x, y);
          });
          RoomEditor.Viewport.globalCtx.closePath();
          RoomEditor.Viewport.globalCtx.fillStyle = room.id === RoomEditor.State.currentRoomId ? 'rgba(70, 126, 173, 0.65)' : 'rgba(24, 48, 70, 0.75)';
          RoomEditor.Viewport.globalCtx.strokeStyle = room.id === RoomEditor.State.currentRoomId ? '#ffd166' : '#7fb2df';
          RoomEditor.Viewport.globalCtx.lineWidth = room.id === RoomEditor.State.currentRoomId ? 2.5 : 1.5;
          RoomEditor.Viewport.globalCtx.fill();
          RoomEditor.Viewport.globalCtx.stroke();

          RoomEditor.Viewport.globalCtx.fillStyle = '#f0f7ff';
          RoomEditor.Viewport.globalCtx.font = '12px sans-serif';
          RoomEditor.Viewport.globalCtx.fillText(room.id, center.x - 10, center.y + 4);
        });

        RoomEditor.State.data.rooms.forEach((room) => {
          RoomEditor.Model.ensureRoomShape(room);
          room.edgeLinks.forEach((link) => {
            const edgeCanvas = RoomEditor.Model.getEdgeCanvasPoints(room, link.edgeIndex);
            drawGlobalEdge(edgeCanvas, {
              strokeStyle: '#3ee6b8',
              lineWidth: 4
            });
          });
        });

        if (RoomEditor.State.selectedGlobalEdge) {
          const room = RoomEditor.Model.getRoomById(RoomEditor.State.selectedGlobalEdge.roomId);
          const selectedEdge = room ? RoomEditor.Model.getEdgeCanvasPoints(room, RoomEditor.State.selectedGlobalEdge.edgeIndex) : null;
          drawGlobalEdge(selectedEdge, {
            strokeStyle: '#ffd166',
            lineWidth: 5,
            endpointFill: '#ffd166'
          });

          const linkedGuide = RoomEditor.Topology.getLinkedEdgeGuide(RoomEditor.State.selectedGlobalEdge.roomId, RoomEditor.State.selectedGlobalEdge.edgeIndex);
          if (linkedGuide) {
            drawGlobalEdge(linkedGuide.targetEdge, {
              strokeStyle: '#ff8ec7',
              lineWidth: 5,
              dash: [10, 6],
              endpointFill: '#ff8ec7'
            });
          }
        }

        if (RoomEditor.State.drag && RoomEditor.State.drag.type === 'room' && !RoomEditor.State.drag.pending) {
          const groupRoomIds = new Set(RoomEditor.State.drag.groupRoomIds || [RoomEditor.State.drag.roomId]);
          groupRoomIds.forEach((dragRoomId) => {
            const draggingRoom = RoomEditor.Model.getRoomById(dragRoomId);
            if (!draggingRoom) return;
            draggingRoom.edgeLinks.forEach((link) => {
              if (groupRoomIds.has(link.targetRoomId)) return;
              const targetRoom = RoomEditor.Model.getRoomById(link.targetRoomId);
              if (!targetRoom) return;
              const targetEdge = RoomEditor.Model.getEdgeCanvasPoints(targetRoom, link.targetEdgeIndex);
              drawGlobalEdge(targetEdge, {
                strokeStyle: 'rgba(255, 142, 199, 0.85)',
                lineWidth: 4,
                dash: [8, 6],
                endpointFill: '#ff8ec7'
              });
            });
          });
        }

        if (RoomEditor.State.globalSnapPreview) {
          const sourceRoom = RoomEditor.Model.getRoomById(RoomEditor.State.globalSnapPreview.roomId);
          const targetRoom = RoomEditor.Model.getRoomById(RoomEditor.State.globalSnapPreview.targetRoomId);
          const sourceEdge = sourceRoom ? RoomEditor.Model.getEdgeCanvasPoints(sourceRoom, RoomEditor.State.globalSnapPreview.edgeIndex) : null;
          const targetEdge = targetRoom ? RoomEditor.Model.getEdgeCanvasPoints(targetRoom, RoomEditor.State.globalSnapPreview.targetEdgeIndex) : null;
          drawGlobalEdge(targetEdge, {
            strokeStyle: '#ff8ec7',
            lineWidth: 6,
            dash: [8, 6],
            endpointFill: '#ff8ec7'
          });
          drawGlobalEdge(sourceEdge, {
            strokeStyle: '#ffe08a',
            lineWidth: 4,
            endpointFill: '#ffe08a'
          });
        }
      }

function redraw() {
        const room = RoomEditor.Model.currentRoom();
        RoomEditor.Ui.updateEmptyStates();
        if (!room) {
          RoomEditor.State.setViewMode(RoomEditor.State.viewMode);
          RoomEditor.Ui.syncPropertyInputs();
          RoomEditor.Viewport.updateViewControlReadouts();
          RoomEditor.Ui.refs.toggleSelectedEdge.disabled = true;
          RoomEditor.Ui.refs.roomCanvasBox.classList.add('hidden');
          RoomEditor.Ui.refs.globalCanvasBox.classList.toggle('hidden', RoomEditor.State.viewMode !== 'global');
          RoomEditor.Ui.refs.globalLinkPanel.classList.toggle('hidden', RoomEditor.State.viewMode !== 'global');
          document.getElementById('canvasToolButtons').classList.add('hidden');
          RoomEditor.Ui.refs.selectionInspector.classList.add('hidden');
          RoomEditor.Ui.updateGlobalLinkControls();
          RoomEditor.Viewport.roomCtx.clearRect(0, 0, RoomEditor.Viewport.roomCanvas.width, RoomEditor.Viewport.roomCanvas.height);
          RoomEditor.Viewport.roomCtx.fillStyle = '#071018';
          RoomEditor.Viewport.roomCtx.fillRect(0, 0, RoomEditor.Viewport.roomCanvas.width, RoomEditor.Viewport.roomCanvas.height);
          drawGlobalView();
          RoomEditor.Storage.updateJsonText();
          RoomEditor.Workflow.syncWorkflowRailVisibility();
          RoomEditor.Workflow.syncRoomWizardDock();
          RoomEditor.Workflow.updateWorkflowRailPills();
          if (RoomEditor.State.roomWizard.active && RoomEditor.State.roomWizard.phase === 'layout') {
            RoomEditor.Wizard.updateRoomWizardTerrainControls();
            RoomEditor.Wizard.refreshTerrainWarnings();
          }
          return;
        }
        RoomEditor.State.setViewMode(RoomEditor.State.viewMode);
        RoomEditor.Ui.updateCounts(room);
        RoomEditor.Ui.renderInventory(room);
        RoomEditor.Ui.syncPropertyInputs();
        RoomEditor.Viewport.updateViewControlReadouts();
        const showRoomCanvas =
          RoomEditor.State.viewMode === 'room' &&
          !(RoomEditor.State.roomWizard.active && RoomEditor.State.roomWizard.phase === 'environment');
        RoomEditor.Ui.refs.toggleSelectedEdge.disabled = !(RoomEditor.State.viewMode === 'room' && RoomEditor.State.selectionItems.length === 1 && RoomEditor.State.selected?.kind === 'room-edge');
        RoomEditor.Ui.refs.roomCanvasBox.classList.toggle('hidden', !showRoomCanvas);
        RoomEditor.Ui.refs.globalCanvasBox.classList.toggle('hidden', RoomEditor.State.viewMode !== 'global');
        RoomEditor.Ui.refs.globalLinkPanel.classList.toggle('hidden', RoomEditor.State.viewMode !== 'global');
        document.getElementById('canvasToolButtons').classList.toggle('hidden', !showRoomCanvas);
        document.getElementById('roomViewControls')?.classList.toggle('hidden', !showRoomCanvas);
        if (!showRoomCanvas) RoomEditor.Ui.refs.selectionInspector.classList.add('hidden');
        RoomEditor.Ui.updateGlobalLinkControls();
        if (showRoomCanvas) {
          drawRoomView();
          RoomEditor.Ui.renderEmptyRoomHint();
        }
        drawGlobalView();
        RoomEditor.Storage.updateJsonText();
        RoomEditor.Workflow.syncWorkflowRailVisibility();
        RoomEditor.Workflow.syncRoomWizardDock();
        RoomEditor.Workflow.updateWorkflowRailPills();
        if (RoomEditor.State.roomWizard.active && RoomEditor.State.roomWizard.phase === 'layout') {
          RoomEditor.Wizard.updateRoomWizardTerrainControls();
          RoomEditor.Wizard.refreshTerrainWarnings();
        }
      }

  Module.drawRoomGrid = drawRoomGrid;
  Module.pointInCanvasPolygon = pointInCanvasPolygon;
  Module.distanceToCanvasSegment = distanceToCanvasSegment;
  Module.distanceToCanvasPolygon = distanceToCanvasPolygon;
  Module.drawGrid = drawGrid;
  Module.drawGlobalEdge = drawGlobalEdge;
  Module.drawRoomEdge = drawRoomEdge;
  Module.getRoomLocalEdgeCanvasPoints = getRoomLocalEdgeCanvasPoints;
  Module.drawRoomView = drawRoomView;
  Module.drawGlobalView = drawGlobalView;
  Module.redraw = redraw;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Render = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
