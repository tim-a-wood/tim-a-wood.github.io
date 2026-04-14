'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.GamePreview ? root.RoomEditor.GamePreview : {};

function closeGamePreview() {
        const iframe = document.getElementById('gamePreviewFrame');
        const overlay = document.getElementById('gamePreviewOverlay');
        if (iframe) iframe.src = 'about:blank';
        if (overlay) {
          overlay.hidden = true;
          overlay.setAttribute('aria-hidden', 'true');
        }
        document.body.classList.remove('game-preview-open');
      }

function openGameWithLayout(previewRoomId, options = {}) {
        if (!RoomEditor.State.data) return;
        const preserveFocus = Boolean(options && options.preserveFocus);
        const encoded = RoomEditor.Storage.encodeLayoutForHash();
        const startArg =
          previewRoomId && RoomEditor.State.data.rooms.some((r) => r.id === previewRoomId) ? previewRoomId : null;
        let hash = `preview=embed&layout=${encoded}`;
        if (startArg) hash += `&start=${encodeURIComponent(startArg)}`;
        const iframe = document.getElementById('gamePreviewFrame');
        const overlay = document.getElementById('gamePreviewOverlay');
        if (!iframe || !overlay) return;
        const origin = window.location.origin;
        const cacheBust = `preview_v=${Date.now()}`;
        const payload = {
          type: 'ASHEN_HOLLOW_PREVIEW',
          layout: RoomEditor.State.data,
          startRoom: startArg
        };
        const sendPreviewToFrame = () => {
          try {
            iframe.contentWindow?.postMessage(payload, origin);
          } catch (_) {}
        };
        const onChildReady = (event) => {
          if (event.origin !== origin) return;
          if (event.data?.type !== 'ASHEN_HOLLOW_PREVIEW_READY') return;
          clearTimeout(readyFallbackTimer);
          window.removeEventListener('message', onChildReady);
          sendPreviewToFrame();
        };
        window.addEventListener('message', onChildReady);
        const readyFallbackTimer = setTimeout(() => {
          window.removeEventListener('message', onChildReady);
        }, 8000);
        iframe.src = `./index.html?${cacheBust}#${hash}`;
        overlay.hidden = false;
        overlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('game-preview-open');
        if (!preserveFocus) document.getElementById('gamePreviewClose')?.focus();
      }

function refreshOpenGamePreviewIfVisible(previewRoomId) {
        const overlay = document.getElementById('gamePreviewOverlay');
        if (!overlay || overlay.hidden) return;
        openGameWithLayout(previewRoomId, { preserveFocus: true });
      }

function wireGamePreview() {
        if (wireGamePreview.__wired) return;
        wireGamePreview.__wired = true;
        document.getElementById('gamePreviewClose')?.addEventListener('click', closeGamePreview);
        document.getElementById('gamePreviewBackdrop')?.addEventListener('click', closeGamePreview);
      }

  Module.closeGamePreview = closeGamePreview;
  Module.openGameWithLayout = openGameWithLayout;
  Module.refreshOpenGamePreviewIfVisible = refreshOpenGamePreviewIfVisible;
  Module.wireGamePreview = wireGamePreview;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.GamePreview = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
