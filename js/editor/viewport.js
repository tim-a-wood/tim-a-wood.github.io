'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Viewport ? root.RoomEditor.Viewport : {};

function fitRoomToCanvas() {
        resetRoomView();
      }

function clampZoom(value, min, max) {
        return Math.max(min, Math.min(max, value));
      }

function roomViewport() {
        return {
          x: RoomEditor.Constants.ROOM_MARGIN_LEFT,
          y: RoomEditor.Constants.ROOM_MARGIN_TOP,
          width: RoomEditor.Viewport.roomCanvas.width - RoomEditor.Constants.ROOM_MARGIN_LEFT - RoomEditor.Constants.ROOM_MARGIN_RIGHT,
          height: RoomEditor.Viewport.roomCanvas.height - RoomEditor.Constants.ROOM_MARGIN_TOP - RoomEditor.Constants.ROOM_MARGIN_BOTTOM
        };
      }

function roomScale() {
        const roomSize = RoomEditor.Model.currentRoomSize();
        const viewport = roomViewport();
        const usableWidth = viewport.width;
        const usableHeight = viewport.height;
        const scaleX = (usableWidth / roomSize.width) * RoomEditor.State.roomZoom;
        const scaleY = (usableHeight / roomSize.height) * RoomEditor.State.roomZoom;
        /* Uniform scale + letterboxing so room pixels stay square and match Environment layout overlay SVG (single viewBox aspect). */
        const scaleUniform = Math.min(scaleX, scaleY);
        return {
          x: scaleUniform,
          y: scaleUniform,
          offsetX: viewport.x + ((usableWidth - (roomSize.width * scaleUniform)) / 2) + RoomEditor.State.roomPan.x,
          offsetY: viewport.y + ((usableHeight - (roomSize.height * scaleUniform)) / 2) + RoomEditor.State.roomPan.y,
          viewport
        };
      }

function globalBounds() {
        const xs = [];
        const ys = [];
        RoomEditor.State.data.rooms.forEach((room) => {
          RoomEditor.Model.ensureRoomShape(room);
          const previewHalfWidth = (room.size.width * RoomEditor.Constants.GLOBAL_ROOM_PREVIEW_SCALE) / 2;
          const previewHalfHeight = (room.size.height * RoomEditor.Constants.GLOBAL_ROOM_PREVIEW_SCALE) / 2;
          xs.push(room.global.x - previewHalfWidth, room.global.x + previewHalfWidth);
          ys.push(room.global.y - previewHalfHeight, room.global.y + previewHalfHeight);
        });
        if (!xs.length) {
          return { minX: -800, maxX: 800, minY: -600, maxY: 600 };
        }
        const minX = Math.min(...xs) - 220;
        const maxX = Math.max(...xs) + 220;
        const minY = Math.min(...ys) - 220;
        const maxY = Math.max(...ys) + 220;
        return { minX, maxX, minY, maxY };
      }

function globalScale() {
        const bounds = globalBounds();
        const width = Math.max(bounds.maxX - bounds.minX, 1);
        const height = Math.max(bounds.maxY - bounds.minY, 1);
        const sx = (RoomEditor.Viewport.globalCanvas.width - 80) / width;
        const sy = (RoomEditor.Viewport.globalCanvas.height - 80) / height;
        const scale = Math.min(sx, sy) * RoomEditor.State.globalZoom;
        return {
          bounds,
          scale,
          offsetX: ((RoomEditor.Viewport.globalCanvas.width - (width * scale)) / 2) + RoomEditor.State.globalPan.x,
          offsetY: ((RoomEditor.Viewport.globalCanvas.height - (height * scale)) / 2) + RoomEditor.State.globalPan.y
        };
      }

function roomToCanvasPoint(x, y) {
        const projection = roomScale();
        return {
          x: projection.offsetX + (x * projection.x),
          y: projection.offsetY + (y * projection.y)
        };
      }

function canvasToRoomPointRaw(x, y) {
        const projection = roomScale();
        return {
          x: (x - projection.offsetX) / projection.x,
          y: (y - projection.offsetY) / projection.y
        };
      }

function canvasToRoomPoint(x, y) {
        const local = canvasToRoomPointRaw(x, y);
        return {
          x: RoomEditor.State.snap(local.x),
          y: RoomEditor.State.snap(local.y)
        };
      }

function globalToCanvasPoint(x, y) {
        const { bounds, scale, offsetX, offsetY } = globalScale();
        return {
          x: offsetX + (x - bounds.minX) * scale,
          y: offsetY + (y - bounds.minY) * scale
        };
      }

function canvasToGlobalPoint(x, y) {
        const { bounds, scale, offsetX, offsetY } = globalScale();
        return {
          x: RoomEditor.State.snap(bounds.minX + ((x - offsetX) / scale)),
          y: RoomEditor.State.snap(bounds.minY + ((y - offsetY) / scale))
        };
      }

function updateViewControlReadouts() {
        if (RoomEditor.Ui.refs.roomZoomReadout) {
          RoomEditor.Ui.refs.roomZoomReadout.textContent = `${Math.round(RoomEditor.State.roomZoom * 100)}%`;
        }
        if (RoomEditor.Ui.refs.globalZoomReadout) {
          RoomEditor.Ui.refs.globalZoomReadout.textContent = `${Math.round(RoomEditor.State.globalZoom * 100)}%`;
        }
        if (RoomEditor.Ui.refs.globalZoom) {
          RoomEditor.Ui.refs.globalZoom.value = String(Math.round(RoomEditor.State.globalZoom * 100));
        }
      }

function adjustRoomZoom(delta) {
        RoomEditor.State.roomZoom = clampZoom(Number((RoomEditor.State.roomZoom + delta).toFixed(2)), RoomEditor.Constants.ROOM_ZOOM_MIN, RoomEditor.Constants.ROOM_ZOOM_MAX);
        RoomEditor.Render.redraw();
      }

function resetRoomView() {
        RoomEditor.State.roomZoom = 1;
        RoomEditor.State.roomPan.x = 0;
        RoomEditor.State.roomPan.y = 0;
        RoomEditor.Render.redraw();
      }

function panRoomView(dx, dy) {
        RoomEditor.State.roomPan.x += dx;
        RoomEditor.State.roomPan.y += dy;
        RoomEditor.Render.redraw();
      }

function adjustGlobalZoom(delta) {
        RoomEditor.State.globalZoom = clampZoom(Number((RoomEditor.State.globalZoom + delta).toFixed(2)), RoomEditor.Constants.GLOBAL_ZOOM_MIN, RoomEditor.Constants.GLOBAL_ZOOM_MAX);
        RoomEditor.Render.redraw();
      }

function resetGlobalView() {
        RoomEditor.State.globalZoom = 1;
        RoomEditor.State.globalPan.x = 0;
        RoomEditor.State.globalPan.y = 0;
        RoomEditor.Render.redraw();
      }

function panGlobalView(dx, dy) {
        RoomEditor.State.globalPan.x += dx;
        RoomEditor.State.globalPan.y += dy;
        RoomEditor.Render.redraw();
      }

function getCanvasPointer(event, canvas) {
        const rect = canvas.getBoundingClientRect();
        const point = event.touches && event.touches[0]
          ? event.touches[0]
          : event.changedTouches && event.changedTouches[0]
            ? event.changedTouches[0]
            : event;
        const scaleX = rect.width ? (canvas.width / rect.width) : 1;
        const scaleY = rect.height ? (canvas.height / rect.height) : 1;
        return {
          x: (point.clientX - rect.left) * scaleX,
          y: (point.clientY - rect.top) * scaleY
        };
      }
  Module.fitRoomToCanvas = fitRoomToCanvas;
  Module.clampZoom = clampZoom;
  Module.roomViewport = roomViewport;
  Module.roomScale = roomScale;
  Module.globalBounds = globalBounds;
  Module.globalScale = globalScale;
  Module.roomToCanvasPoint = roomToCanvasPoint;
  Module.canvasToRoomPointRaw = canvasToRoomPointRaw;
  Module.canvasToRoomPoint = canvasToRoomPoint;
  Module.globalToCanvasPoint = globalToCanvasPoint;
  Module.canvasToGlobalPoint = canvasToGlobalPoint;
  Module.updateViewControlReadouts = updateViewControlReadouts;
  Module.adjustRoomZoom = adjustRoomZoom;
  Module.resetRoomView = resetRoomView;
  Module.panRoomView = panRoomView;
  Module.adjustGlobalZoom = adjustGlobalZoom;
  Module.resetGlobalView = resetGlobalView;
  Module.panGlobalView = panGlobalView;
  Module.getCanvasPointer = getCanvasPointer;

  function init() {
    RoomEditor.Viewport.roomCanvas = document.getElementById('roomCanvas');
    RoomEditor.Viewport.roomCtx = RoomEditor.Viewport.roomCanvas.getContext('2d');
    RoomEditor.Viewport.globalCanvas = document.getElementById('globalCanvas');
    RoomEditor.Viewport.globalCtx = RoomEditor.Viewport.globalCanvas.getContext('2d');
  }
  Module.init = init;


  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Viewport = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
