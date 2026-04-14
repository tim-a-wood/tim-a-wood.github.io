'use strict';
(function (root) {
  const RoomEditor = root.RoomEditor || {};
  const RW_PHASE_ORDER = ['identity', 'layout', 'environment', 'entities', 'review'];

  const PHASE_COPY = {
    identity: {
      title: 'Identity',
      sub: 'Set the display name, canonical id, and footprint before drawing geometry on the canvas.',
      eyebrow: 'Phase 0 · Identity',
    },
    layout: {
      title: 'Layout',
      sub: 'Align neighbors, drop presets, and shape platforms — the canvas and task drawer stay in focus.',
      eyebrow: 'Phase 1 · Layout',
    },
    environment: {
      title: 'Environment',
      sub: 'Describe the room, preview pictures, then build final art when you are ready.',
      eyebrow: 'Phase 2 · Environment',
    },
    entities: {
      title: 'Entities',
      sub: 'Entity-focused authoring will land here; use canvas tools and the inspector today.',
      eyebrow: 'Phase 3 · Entities',
    },
    review: {
      title: 'Review',
      sub: 'Validate structure, skim summaries, then export or open the game.',
      eyebrow: 'Phase 4 · Review',
    },
  };

  function phaseCopy(phase) {
    return PHASE_COPY[phase] || PHASE_COPY.layout;
  }

  function updateSheetCopy(phase) {
    const c = phaseCopy(phase);
    const titleEl = document.getElementById('roomWizardTitle');
    const subEl = document.getElementById('roomWizardSub');
    if (titleEl) titleEl.textContent = c.title;
    if (subEl) subEl.textContent = c.sub;
  }

  function syncLayoutSubpanels() {
    const ph = RoomEditor.State.roomWizard.phase;
    const idBlock = document.getElementById('roomWizardLayoutIdentityBlock');
    const geoBlock = document.getElementById('roomWizardLayoutGeometryBlock');
    if (!idBlock || !geoBlock) return;
    const onLayoutPanel = ph === 'identity' || ph === 'layout';
    if (!onLayoutPanel) return;
    if (ph === 'identity') {
      idBlock.hidden = false;
      geoBlock.hidden = true;
    } else {
      idBlock.hidden = true;
      geoBlock.hidden = false;
    }
  }

  function updateStageBarFromRoom() {
    const titleEl = document.getElementById('rwStageRoomTitle');
    const metaEl = document.getElementById('rwStageRoomMeta');
    const room = RoomEditor.Wizard.getRoomWizardRoom() || RoomEditor.Model.currentRoom();
    if (!titleEl || !metaEl) return;
    if (!room) {
      titleEl.textContent = 'Room';
      metaEl.textContent = '—';
      return;
    }
    const W = room.size?.width ?? '—';
    const H = room.size?.height ?? '—';
    const tile = RoomEditor.Constants.TILE || 32;
    titleEl.textContent = room.name || room.id || 'Room';
    metaEl.textContent = `${room.id} · ${W} × ${H} px · grid ${tile}`;
  }

  function updateStageZoomActiveButton() {
    const z = Math.round(RoomEditor.State.roomZoom * 100);
    document.querySelectorAll('.rw-stage-zoom-btn').forEach((btn) => btn.classList.remove('rw-stage-zoom-btn--active'));
    const map = { 25: 'rwStageZoom25', 50: 'rwStageZoom50', 100: 'rwStageZoom100', 200: 'rwStageZoom200' };
    const id = map[z];
    if (id) document.getElementById(id)?.classList.add('rw-stage-zoom-btn--active');
  }

  function setRoomZoomPct(pct) {
    const z = RoomEditor.Viewport.clampZoom(pct / 100, RoomEditor.Constants.ROOM_ZOOM_MIN, RoomEditor.Constants.ROOM_ZOOM_MAX);
    RoomEditor.State.roomZoom = z;
    RoomEditor.Viewport.updateViewControlReadouts();
    updateStageZoomActiveButton();
    RoomEditor.Render.redraw();
  }

  function updateTaskDrawerForPhase() {
    const drawer = document.getElementById('rwTaskDrawer');
    const label = document.getElementById('rwTaskDrawerPhaseLabel');
    const badge = document.getElementById('rwTaskDrawerBadge');
    const scroll = document.getElementById('rwTaskScroll');
    if (!drawer || !label || !scroll) return;
    const ph = RoomEditor.State.roomWizard.phase;
    const mod = globalThis.RoomWizardTerrain;
    const room = RoomEditor.Wizard.getRoomWizardRoom();
    const layoutOk = !!(room && mod && mod.isLayoutCompleteForTerrain(room));

    if (ph !== 'identity' && ph !== 'layout') {
      scroll.innerHTML = '';
      if (badge) badge.textContent = '';
      return;
    }

    const tasks = [];
    if (ph === 'identity') {
      tasks.push({ id: 'name', label: 'Room name', done: !!(room && String(room.name || '').trim()) });
      tasks.push({ id: 'id', label: 'Room id', done: !!(room && String(room.id || '').trim()) });
      tasks.push({ id: 'fp', label: 'Footprint', done: layoutOk });
    } else {
      tasks.push({ id: 'id', label: 'Identity complete', done: layoutOk });
      tasks.push({ id: 'nb', label: 'Neighbors (optional)', done: true });
      tasks.push({ id: 'plat', label: 'Platforms / presets', done: !!(room && room.platforms && room.platforms.length > 0) });
    }
    const doneCt = tasks.filter((t) => t.done).length;
    label.textContent = phaseCopy(ph).eyebrow;
    if (badge) badge.textContent = `${doneCt} of ${tasks.length} tasks`;

    scroll.innerHTML = tasks
      .map((t, i) => {
        const cls = t.done ? 'done' : i === doneCt && !t.done ? 'active' : 'pending';
        const mark = t.done ? '\u2713' : '\u25a3';
        return `<div class="rw-task-card rw-task-card--${cls}" role="listitem"><span class="rw-task-check" aria-hidden="true">${mark}</span><span class="rw-task-label"><b>${RoomEditor.Ui.escapeHtml(t.label)}</b></span></div>`;
      })
      .join('');
  }

  function updateFocusRailVisibility(phase) {
    document.querySelectorAll('[data-rw-focus]').forEach((el) => {
      const key = el.getAttribute('data-rw-focus');
      el.hidden = key !== phase;
    });
  }

  function restoreSheetToDock() {
    const sheetRoot = document.getElementById('roomWizardSheetRoot');
    const top = document.getElementById('rwWizardSheetTop');
    const scroll = document.getElementById('rwWizardSheetScroll');
    if (!sheetRoot || !top || !scroll) return;
    sheetRoot.appendChild(top);
    sheetRoot.appendChild(scroll);
  }

  function syncShell() {
    const sheetRoot = document.getElementById('roomWizardSheetRoot');
    const top = document.getElementById('rwWizardSheetTop');
    const scroll = document.getElementById('rwWizardSheetScroll');
    const dock = document.getElementById('roomWizardDock');
    const optbMain = document.getElementById('rwOptbMain');
    const canvasWrap = document.querySelector('.canvas-wrap');
    if (!sheetRoot || !top || !scroll || !dock || !optbMain || !canvasWrap) return;

    const st = RoomEditor.State;
    const active =
      st.roomWizard.active && (st.workflowScope === 'room' || st.workflowScope === 'art-direction');
    const artScope = st.workflowScope === 'art-direction';
    const phase = st.roomWizard.phase;

    if (!active || artScope) {
      restoreSheetToDock();
      optbMain.classList.remove('rw-optb--wizard-on', 'rw-optb--focus-mode');
      canvasWrap.classList.remove('rw-optb-wizard-on', 'rw-optb-focus-mode');
      document.getElementById('rwWizardInspectorHost')?.setAttribute('hidden', '');
      document.getElementById('rwStageBar')?.setAttribute('hidden', '');
      document.getElementById('rwTaskDrawer')?.setAttribute('hidden', '');
      document.getElementById('rwStageFocus')?.setAttribute('hidden', '');
      dock.classList.remove('rw-option-b-reparented');
      return;
    }

    const canvasPhases = ['identity', 'layout'];
    const useFocus = !canvasPhases.includes(phase);

    dock.classList.add('rw-option-b-reparented');
    updateSheetCopy(phase);
    syncLayoutSubpanels();

    if (useFocus) {
      const fh = document.getElementById('rwFocusHeadSlot');
      const fm = document.getElementById('rwFocusMainSlot');
      fh?.appendChild(top);
      fm?.appendChild(scroll);
      optbMain.classList.add('rw-optb--wizard-on', 'rw-optb--focus-mode');
      optbMain.classList.remove('rw-optb--canvas-phase');
      canvasWrap.classList.add('rw-optb-wizard-on', 'rw-optb-focus-mode');
      canvasWrap.classList.remove('rw-optb-canvas-phase');
      document.getElementById('rwStageFocus')?.removeAttribute('hidden');
      document.getElementById('rwWizardInspectorHost')?.setAttribute('hidden', '');
      document.getElementById('rwStageBar')?.setAttribute('hidden', '');
      document.getElementById('rwTaskDrawer')?.setAttribute('hidden', '');
    } else {
      const ih = document.getElementById('rwWizardInsHeadSlot');
      const ib = document.getElementById('rwWizardInsBodySlot');
      ih?.appendChild(top);
      ib?.appendChild(scroll);
      optbMain.classList.add('rw-optb--wizard-on', 'rw-optb--canvas-phase');
      optbMain.classList.remove('rw-optb--focus-mode');
      canvasWrap.classList.add('rw-optb-wizard-on', 'rw-optb-canvas-phase');
      canvasWrap.classList.remove('rw-optb-focus-mode');
      document.getElementById('rwStageFocus')?.setAttribute('hidden', '');
      document.getElementById('rwWizardInspectorHost')?.removeAttribute('hidden');
      document.getElementById('rwStageBar')?.removeAttribute('hidden');
      document.getElementById('rwTaskDrawer')?.removeAttribute('hidden');
    }

    updateStageBarFromRoom();
    RoomEditor.Viewport.updateViewControlReadouts();
    updateStageZoomActiveButton();
    updateTaskDrawerForPhase();
    updateFocusRailVisibility(phase);
  }

  function openPreviewModal(kind) {
    const modal = document.getElementById('rwOptbPreviewModal');
    const title = document.getElementById('rwOptbPreviewTitle');
    const cvs = document.getElementById('rwOptbPreviewCanvas');
    const src = RoomEditor.Viewport.roomCanvas;
    if (!modal || !cvs || !src) return;
    if (title) title.textContent = kind === 'decor' ? 'Decorated preview' : 'Layout preview';
    const w = 320;
    const h = 240;
    cvs.width = w;
    cvs.height = h;
    const ctx = cvs.getContext('2d');
    if (ctx) {
      ctx.imageSmoothingEnabled = false;
      ctx.fillStyle = '#081018';
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(src, 0, 0, src.width, src.height, 0, 0, w, h);
    }
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    document.getElementById('rwOptbPreviewClose')?.focus();
  }

  function closePreviewModal() {
    const modal = document.getElementById('rwOptbPreviewModal');
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
  }

  function wireChromeEvents() {
    document.getElementById('rwStageZoomFit')?.addEventListener('click', () => {
      RoomEditor.Viewport.fitRoomToCanvas();
      updateStageZoomActiveButton();
    });
    document.getElementById('rwStageZoom25')?.addEventListener('click', () => setRoomZoomPct(25));
    document.getElementById('rwStageZoom50')?.addEventListener('click', () => setRoomZoomPct(50));
    document.getElementById('rwStageZoom100')?.addEventListener('click', () => setRoomZoomPct(100));
    document.getElementById('rwStageZoom200')?.addEventListener('click', () => setRoomZoomPct(200));

    document.getElementById('rwOptbPreviewClose')?.addEventListener('click', closePreviewModal);
    document.getElementById('rwOptbPreviewBackdrop')?.addEventListener('click', closePreviewModal);

    document.querySelectorAll('.rw-focus-preview-btn').forEach((btn) => {
      btn.addEventListener('click', () => openPreviewModal(btn.dataset.rwPreview === 'decor' ? 'decor' : 'layout'));
    });
  }

  function navigatePhase(delta, depth) {
    const st = RoomEditor.State;
    if (!st.roomWizard.active || st.workflowScope === 'art-direction') return;
    const guard = depth || 0;
    if (guard > RW_PHASE_ORDER.length) return;
    const i = RW_PHASE_ORDER.indexOf(st.roomWizard.phase);
    if (i < 0) return;
    let next = i + delta;
    if (next < 0) next = RW_PHASE_ORDER.length - 1;
    if (next >= RW_PHASE_ORDER.length) next = 0;
    const target = RW_PHASE_ORDER[next];
    const rail = document.getElementById('roomWizardPhaseRail');
    const pill = rail?.querySelector(`.phase-pill[data-rw-phase="${target}"]`);
    if (pill?.disabled) {
      navigatePhase(delta + (delta > 0 ? 1 : -1), guard + 1);
      return;
    }
    RoomEditor.Wizard.setRoomWizardPhase(target);
    RoomEditor.Render.redraw();
  }

  function onGlobalKeydown(event) {
    const st = RoomEditor.State;
    if (!st.roomWizard.active || st.workflowScope === 'art-direction') return;
    const target = event.target;
    const tagName = target?.tagName;
    const isTypingTarget = target?.isContentEditable || tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT';
    if (isTypingTarget || event.metaKey || event.ctrlKey || event.altKey) return;

    if (event.key === '[' || event.key === 'ArrowLeft') {
      navigatePhase(-1);
      event.preventDefault();
    } else if (event.key === ']' || event.key === 'ArrowRight') {
      navigatePhase(1);
      event.preventDefault();
    }
  }

  RoomEditor.WizardOptionB = {
    RW_PHASE_ORDER,
    phaseCopy,
    syncShell,
    syncLayoutSubpanels,
    updateStageBarFromRoom,
    updateTaskDrawerForPhase,
    wireChromeEvents,
    openPreviewModal,
    closePreviewModal,
    navigatePhase,
    restoreSheetToDock,
  };

  root.RoomEditor = RoomEditor;
})(typeof globalThis !== 'undefined' ? globalThis : this);
