'use strict';
(function (root) {
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Ui = root.RoomEditor.Ui || { refs: null };
function configureNav() {
        const navHome = document.getElementById('navHome');
        const navSpriteCreation = document.getElementById('navSpriteCreation');
        const navRoomCreation = document.getElementById('navRoomCreation');
        const navDocs = document.getElementById('navDocs');
        const navLogo = document.getElementById('navLogo');
        const roomUrl = new URL(RoomEditor.Constants.ROOM_EDITOR_URL.toString());
        const spriteUrl = new URL(RoomEditor.Constants.WORKBENCH_URL.toString());
        const homeUrl = new URL(RoomEditor.Constants.WORKBENCH_URL.toString());
        const docsUrl = new URL(RoomEditor.Constants.WORKBENCH_URL.toString());

        if (RoomEditor.State.PROJECT_ID) {
          roomUrl.searchParams.set('project_id', RoomEditor.State.PROJECT_ID);
          spriteUrl.searchParams.set('project_id', RoomEditor.State.PROJECT_ID);
          homeUrl.searchParams.set('project_id', RoomEditor.State.PROJECT_ID);
          docsUrl.searchParams.set('project_id', RoomEditor.State.PROJECT_ID);
        } else if (RoomEditor.State.LOCAL_SLOT) {
          roomUrl.searchParams.set('local_slot', RoomEditor.State.LOCAL_SLOT);
        }
        docsUrl.hash = 'docs';

        if (navLogo) navLogo.href = homeUrl.toString();
        if (navHome) navHome.href = homeUrl.toString();
        if (navSpriteCreation) navSpriteCreation.href = spriteUrl.toString();
        if (navRoomCreation) navRoomCreation.href = roomUrl.toString();
        if (navDocs) navDocs.href = docsUrl.toString();
      }

function roomEditorProjectUrl(projectId) {
        const url = new URL(RoomEditor.Constants.ROOM_EDITOR_URL.toString());
        if (projectId) url.searchParams.set('project_id', projectId);
        return url.toString();
      }

function roomEditorLocalSlotUrl(slot) {
        const url = new URL(RoomEditor.Constants.ROOM_EDITOR_URL.toString());
        const s = RoomEditor.State.sanitizeLocalSlot(slot);
        if (s) url.searchParams.set('local_slot', s);
        return url.toString();
      }

function spriteWorkbenchProjectUrl(projectId) {
        const url = new URL(RoomEditor.Constants.WORKBENCH_URL.toString());
        if (projectId) url.searchParams.set('project_id', projectId);
        return url.toString();
      }

function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (match) => ({
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#39;'
        }[match]));
      }

function formatDate(value) {
        if (!value) return 'Unknown';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString([], {
          month: 'numeric',
          day: 'numeric',
          year: 'numeric',
          hour: 'numeric',
          minute: '2-digit'
        });
      }

RoomEditor.Ui.refs = {
        sidebarProjectName: document.getElementById('sidebar-project-name'),
        roomProjectList: document.getElementById('room-project-list'),
        roomSelect: document.getElementById('roomSelect'),
        roomSetupBtn: document.getElementById('roomSetupBtn'),
        snapSize: document.getElementById('snapSize'),
        globalZoom: document.getElementById('globalZoom'),
        roomZoomOut: document.getElementById('roomZoomOut'),
        roomZoomIn: document.getElementById('roomZoomIn'),
        roomZoomFit: document.getElementById('roomZoomFit'),
        roomZoomReset: document.getElementById('roomZoomReset'),
        roomZoomReadout: document.getElementById('roomZoomReadout'),
        roomPanLeft: document.getElementById('roomPanLeft'),
        roomPanUp: document.getElementById('roomPanUp'),
        roomPanDown: document.getElementById('roomPanDown'),
        roomPanRight: document.getElementById('roomPanRight'),
        globalZoomOut: document.getElementById('globalZoomOut'),
        globalZoomIn: document.getElementById('globalZoomIn'),
        globalZoomReset: document.getElementById('globalZoomReset'),
        globalZoomReadout: document.getElementById('globalZoomReadout'),
        globalPanLeft: document.getElementById('globalPanLeft'),
        globalPanUp: document.getElementById('globalPanUp'),
        globalPanDown: document.getElementById('globalPanDown'),
        globalPanRight: document.getElementById('globalPanRight'),
        toolButtons: Array.from(document.querySelectorAll('#canvasToolButtons button[data-tool]')),
        selectionSummary: document.getElementById('selectionSummary'),
        selectionInspector: document.getElementById('selectionInspector'),
        inspectorTitle: document.getElementById('inspectorTitle'),
        inspectorTypeIcon: document.getElementById('inspectorTypeIcon'),
        inspectorClose: document.getElementById('inspectorClose'),
        globalFields: document.getElementById('globalFields'),
        platformFields: document.getElementById('platformFields'),
        moverFields: document.getElementById('moverFields'),
        doorFields: document.getElementById('doorFields'),
        keyFields: document.getElementById('keyFields'),
        abilityFields: document.getElementById('abilityFields'),
        deleteSelected: document.getElementById('deleteSelected'),
        duplicatePlatform: document.getElementById('duplicatePlatform'),
        centerRoom: document.getElementById('centerRoom'),
        roomWidth: document.getElementById('roomWidth'),
        roomHeight: document.getElementById('roomHeight'),
        addRoom: document.getElementById('addRoom'),
        deleteRoom: document.getElementById('deleteRoom'),
        globalX: document.getElementById('globalX'),
        globalY: document.getElementById('globalY'),
        itemX: document.getElementById('itemX'),
        itemY: document.getElementById('itemY'),
        itemLen: document.getElementById('itemLen'),
        itemTint: document.getElementById('itemTint'),
        moverEndX: document.getElementById('moverEndX'),
        moverEndY: document.getElementById('moverEndY'),
        moverLen: document.getElementById('moverLen'),
        moverTint: document.getElementById('moverTint'),
        moverInitialState: document.getElementById('moverInitialState'),
        doorLabel: document.getElementById('doorLabel'),
        doorTarget: document.getElementById('doorTarget'),
        doorStateForward: document.getElementById('doorStateForward'),
        doorStateReverse: document.getElementById('doorStateReverse'),
        keyLabel: document.getElementById('keyLabel'),
        keyDoorTarget: document.getElementById('keyDoorTarget'),
        abilityType: document.getElementById('abilityType'),
        applyProps: document.getElementById('applyProps'),
        toggleSelectedEdge: document.getElementById('toggleSelectedEdge'),
        vertexCount: document.getElementById('vertexCount'),
        platformCount: document.getElementById('platformCount'),
        doorCount: document.getElementById('doorCount'),
        keyCount: document.getElementById('keyCount'),
        abilityCount: document.getElementById('abilityCount'),
        moverCount: document.getElementById('moverCount'),
        roomCanvasBox: document.getElementById('roomCanvasBox'),
        globalCanvasBox: document.getElementById('globalCanvasBox'),
        globalLinkPanel: document.getElementById('globalLinkPanel'),
        globalLinkSummary: document.getElementById('globalLinkSummary'),
        edgeTargetRoom: document.getElementById('edgeTargetRoom'),
        edgeTargetIndex: document.getElementById('edgeTargetIndex'),
        linkSelectedEdge: document.getElementById('linkSelectedEdge'),
        clearSelectedEdgeLink: document.getElementById('clearSelectedEdgeLink'),
        snapSelectedEdge: document.getElementById('snapSelectedEdge'),
        advancedToggle: document.getElementById('advancedToggle'),
        advancedBody: document.getElementById('advancedBody'),
        jsonText: document.getElementById('jsonText'),
        reloadJson: document.getElementById('reloadJson'),
        applyJson: document.getElementById('applyJson'),
        downloadJson: document.getElementById('downloadJson'),
        downloadRuntimePackage: document.getElementById('downloadRuntimePackage'),
        saveJsonFile: document.getElementById('saveJsonFile'),
        savePermanent: document.getElementById('savePermanent'),
        syncCanonicalJson: document.getElementById('syncCanonicalJson'),
        openGameWithLayout: document.getElementById('openGameWithLayout'),
        clearSavedLayout: document.getElementById('clearSavedLayout'),
        statusText: document.getElementById('statusText'),
        toastStack: document.getElementById('toast-stack'),
        activityDock: document.getElementById('activity-dock'),
        activityTitle: document.getElementById('activity-title'),
        activityDetail: document.getElementById('activity-detail'),
        activityState: document.getElementById('activity-state'),
        activityProgress: document.getElementById('activity-progress'),
        activityProgressText: document.getElementById('activity-progress-text')
      };

function syncSidebarProjectName() {
        if (!RoomEditor.Ui.refs.sidebarProjectName) return;
        if (!RoomEditor.State.PROJECT_ID) {
          if (RoomEditor.State.LOCAL_SLOT) {
            RoomEditor.Ui.refs.sidebarProjectName.textContent = `Local · ${RoomEditor.State.LOCAL_SLOT}`;
          } else {
            RoomEditor.Ui.refs.sidebarProjectName.textContent = 'Local Layout';
          }
          return;
        }
        const project = RoomEditor.State.projects.find((entry) => entry.project_id === RoomEditor.State.PROJECT_ID);
        RoomEditor.Ui.refs.sidebarProjectName.textContent = project?.project_name || RoomEditor.State.PROJECT_ID;
      }

function initSidebarToggle() {
        const appShell = document.querySelector('.app-shell');
        const toggle = document.querySelector('.rail-toggle');
        if (!appShell || !toggle) return;
        if (window.localStorage.getItem(RoomEditor.Constants.SIDEBAR_KEY) === '1') {
          appShell.classList.add('sidebar-collapsed');
        }
        const sync = () => {
          const collapsed = appShell.classList.contains('sidebar-collapsed');
          toggle.setAttribute('aria-label', collapsed ? 'Expand project panel' : 'Collapse project panel');
          toggle.textContent = collapsed ? '›' : '‹';
        };
        sync();
        toggle.addEventListener('click', () => {
          appShell.classList.toggle('sidebar-collapsed');
          window.localStorage.setItem(RoomEditor.Constants.SIDEBAR_KEY, appShell.classList.contains('sidebar-collapsed') ? '1' : '0');
          sync();
        });
      }

function renderProjectList() {
        if (!RoomEditor.Ui.refs.roomProjectList) return;
        const cards = [];
        const defaultLocalActive = !RoomEditor.State.PROJECT_ID && !RoomEditor.State.LOCAL_SLOT ? 'active' : '';
        cards.push(`
          <div class="project-card ${defaultLocalActive}" data-room-url="${escapeHtml(roomEditorProjectUrl(''))}">
            <strong>Local Layout</strong>
            <small>Default scratch · <code>ashen-hollow-room-layout-v1</code></small>
            <div class="small-note">Your original browser save and canonical file workflow. Not replaced when you create sandbox projects.</div>
            <div class="project-actions">
              <button class="secondary" data-action="open-room">Open</button>
            </div>
          </div>
        `);
        RoomEditor.Storage.listLocalProjectSlots().forEach((slot) => {
          const active = !RoomEditor.State.PROJECT_ID && RoomEditor.State.LOCAL_SLOT === slot ? 'active' : '';
          cards.push(`
            <div class="project-card ${active}" data-room-url="${escapeHtml(roomEditorLocalSlotUrl(slot))}" data-local-slot="${escapeHtml(slot)}">
              <strong>Local · ${escapeHtml(slot)}</strong>
              <small>Browser sandbox</small>
              <div class="small-note">Separate storage key. Safe for experiments.</div>
              <div class="project-actions">
                <button class="secondary" data-action="open-room">Open</button>
                <button class="secondary" data-action="delete-local" type="button">Remove</button>
              </div>
            </div>
          `);
        });
        RoomEditor.State.projects.forEach((project) => {
          const active = project.project_id === RoomEditor.State.PROJECT_ID ? 'active' : '';
          cards.push(`
            <div class="project-card ${active}" data-room-url="${escapeHtml(roomEditorProjectUrl(project.project_id))}" data-sprite-url="${escapeHtml(spriteWorkbenchProjectUrl(project.project_id))}">
              <strong>${escapeHtml(project.project_name || project.project_id)}</strong>
              <small>${escapeHtml(project.current_stage || 'Sprite Creation')} · Last modified ${escapeHtml(formatDate(project.updated_at))}</small>
              <div class="small-note">Open this project’s room layout without leaving the shared workbench project structure. After a refresh, keep <code>?project_id=…</code> in the address bar (reopen via <strong>Load Room</strong> here if it dropped) so platforms and doors load from the same workbench file.</div>
              <div class="project-actions">
                <button class="secondary" data-action="open-room">Load Room</button>
                <button class="secondary" data-action="open-sprite">Sprite Creation</button>
              </div>
            </div>
          `);
        });
        RoomEditor.Ui.refs.roomProjectList.innerHTML = cards.join('');
        Array.from(RoomEditor.Ui.refs.roomProjectList.querySelectorAll('.project-card')).forEach((card) => {
          const roomUrl = card.dataset.roomUrl;
          const spriteUrl = card.dataset.spriteUrl;
          card.addEventListener('click', (event) => {
            if (event.target.closest('button')) return;
            if (roomUrl) RoomEditor.Storage.navigateToRoomEditorUrl(roomUrl);
          });
          card.querySelector('[data-action="open-room"]')?.addEventListener('click', (event) => {
            event.stopPropagation();
            if (roomUrl) RoomEditor.Storage.navigateToRoomEditorUrl(roomUrl);
          });
          card.querySelector('[data-action="delete-local"]')?.addEventListener('click', (event) => {
            event.stopPropagation();
            const slot = card.dataset.localSlot;
            if (slot) RoomEditor.Storage.deleteLocalProjectSlot(slot);
          });
          card.querySelector('[data-action="open-sprite"]')?.addEventListener('click', (event) => {
            event.stopPropagation();
            if (spriteUrl) window.location.href = spriteUrl;
          });
        });
      }

function populateAbilityOptions() {
        RoomEditor.Ui.refs.abilityType.innerHTML = RoomEditor.Constants.ABILITY_DEFS
          .map((ability) => `<option value="${ability.id}">${ability.label}</option>`)
          .join('');
      }

function setStatus(message, type = 'info') {
        if (!RoomEditor.Ui.refs.statusText) return;
        const normalized = String(message || '');
        let resolvedType = type;
        if (resolvedType === 'info') {
          if (/warning/i.test(normalized)) resolvedType = 'warning';
          else if (/(error|failed|cancelled)/i.test(normalized)) resolvedType = 'error';
          else if (/(saved|applied|downloaded|linked|cleared|added|deleted|set |snapped|resized)/i.test(normalized)) resolvedType = 'success';
        }
        window.clearTimeout(RoomEditor.Ui.refs.statusText._clearTimer);
        RoomEditor.Ui.refs.statusText.textContent = normalized;
        RoomEditor.Ui.refs.statusText.className = 'status' + (resolvedType !== 'info' ? ` status-${resolvedType}` : '');
        if (resolvedType === 'success') {
          RoomEditor.Ui.refs.statusText._clearTimer = window.setTimeout(() => {
            RoomEditor.Ui.refs.statusText.className = 'status';
            RoomEditor.Ui.refs.statusText.textContent = 'Ready';
          }, 2500);
        }
        if (resolvedType === 'warning' || resolvedType === 'error') {
          showToast(normalized, resolvedType);
        }
      }

function showToast(message, kind = 'success', title = '') {
        if (!RoomEditor.Ui.refs.toastStack) return;
        const node = document.createElement('div');
        node.className = `toast ${kind || 'info'}`;
        const resolvedTitle =
          title ||
          (kind === 'error'
            ? 'Something Needs Attention'
            : kind === 'warning'
              ? 'Warning'
              : kind === 'success'
                ? 'Done'
                : 'Update');
        node.innerHTML = `<strong>${escapeHtml(resolvedTitle)}</strong><p>${escapeHtml(String(message || ''))}</p>`;
        RoomEditor.Ui.refs.toastStack.appendChild(node);
        window.setTimeout(() => {
          node.remove();
        }, kind === 'error' ? 6500 : 4000);
      }

function setActivity(activity) {
        RoomEditor.State.activity = activity || null;
        const root = RoomEditor.Ui.refs.activityDock;
        if (!root) return;
        if (!activity) {
          root.hidden = true;
          return;
        }
        root.hidden = false;
        if (RoomEditor.Ui.refs.activityTitle) RoomEditor.Ui.refs.activityTitle.textContent = String(activity.label || 'Working');
        if (RoomEditor.Ui.refs.activityDetail) RoomEditor.Ui.refs.activityDetail.textContent = String(activity.detail || 'Still running…');
        if (RoomEditor.Ui.refs.activityState) RoomEditor.Ui.refs.activityState.textContent = String(activity.state || 'Working');
        const pct = Math.max(0, Math.min(100, Number(activity.percent || 0)));
        if (RoomEditor.Ui.refs.activityProgress) RoomEditor.Ui.refs.activityProgress.style.width = `${pct}%`;
        if (RoomEditor.Ui.refs.activityProgressText) RoomEditor.Ui.refs.activityProgressText.textContent = `${Math.round(pct)}%`;
      }

function clearActivity() {
        setActivity(null);
      }

function updateCounts(room) {
        RoomEditor.Ui.refs.vertexCount.textContent = String(room.polygon.length);
        RoomEditor.Ui.refs.platformCount.textContent = String(room.platforms.length);
        RoomEditor.Ui.refs.doorCount.textContent = String(room.doors.length);
        RoomEditor.Ui.refs.keyCount.textContent = String(room.keys.length);
        RoomEditor.Ui.refs.abilityCount.textContent = String(room.abilities.length);
        RoomEditor.Ui.refs.moverCount.textContent = String(room.movingPlatforms.length);
      }

function updateSelectionSummary() {
        if (!RoomEditor.State.selected || RoomEditor.State.selectionItems.length === 0) {
          RoomEditor.Ui.refs.selectionSummary.textContent = 'Nothing selected.';
          return;
        }
        if (RoomEditor.State.selectionItems.length > 1) {
          const kinds = [...new Set(RoomEditor.State.selectionItems.map((item) => item.kind))].join(', ');
          RoomEditor.Ui.refs.selectionSummary.textContent = `${RoomEditor.State.selectionItems.length} selected (${kinds}).`;
          return;
        }
        if (RoomEditor.State.selected.kind === 'vertex') {
          RoomEditor.Ui.refs.selectionSummary.textContent = `Selected vertex ${RoomEditor.State.selected.index + 1} in ${RoomEditor.State.currentRoomId}.`;
          return;
        }
        if (RoomEditor.State.selected.kind === 'room-edge') {
          const room = RoomEditor.Model.currentRoom();
          const stateLabel = room && RoomEditor.Topology.isRoomEdgeRemoved(room, RoomEditor.State.selected.edgeIndex) ? 'open' : 'solid';
          RoomEditor.Ui.refs.selectionSummary.textContent = `Selected edge ${RoomEditor.State.selected.edgeIndex + 1} in ${RoomEditor.State.currentRoomId} (${stateLabel}).`;
          return;
        }
        if (RoomEditor.State.selected.kind === 'room-shell') {
          RoomEditor.Ui.refs.selectionSummary.textContent = `Selected entire room ${RoomEditor.State.currentRoomId}.`;
          return;
        }
        if (RoomEditor.State.selected.kind === 'start') {
          RoomEditor.Ui.refs.selectionSummary.textContent = `Selected player start in ${RoomEditor.State.currentRoomId}.`;
          return;
        }
        if (RoomEditor.State.selected.kind === 'mover-start' || RoomEditor.State.selected.kind === 'mover-end') {
          RoomEditor.Ui.refs.selectionSummary.textContent = `Selected ${RoomEditor.State.selected.kind === 'mover-start' ? 'mover start' : 'mover end'} for ${RoomEditor.State.selected.id}.`;
          return;
        }
        RoomEditor.Ui.refs.selectionSummary.textContent = `Selected ${RoomEditor.State.selected.kind} ${RoomEditor.State.selected.id}.`;
      }

function updateInspector() {
        const room = RoomEditor.Model.currentRoom();
        const typeColors = {
          vertex: 'var(--vertex)',
          platform: 'var(--platform)',
          door: 'var(--door)',
          key: 'var(--color-key)',
          ability: 'var(--color-ability)',
          mover: 'var(--color-mover)',
          'mover-start': 'var(--color-mover)',
          'mover-end': 'var(--color-mover)',
          start: 'var(--color-start)',
          'room-shell': 'var(--accent)',
          'room-edge': 'var(--muted)'
        };
        if (!room || !RoomEditor.State.selected || RoomEditor.State.viewMode !== 'room' || RoomEditor.State.selectionItems.length !== 1) {
          RoomEditor.Ui.refs.selectionInspector.classList.add('hidden');
          return;
        }

        RoomEditor.Ui.refs.selectionInspector.classList.remove('hidden');
        // Task 2.5d: Inspector slide-in animation
        RoomEditor.Ui.refs.selectionInspector.classList.add('showing');
        setTimeout(() => RoomEditor.Ui.refs.selectionInspector.classList.remove('showing'), 120);
        if (RoomEditor.Ui.refs.inspectorTypeIcon) {
          RoomEditor.Ui.refs.inspectorTypeIcon.style.background = typeColors[RoomEditor.State.selected.kind] || 'var(--muted)';
        }
        RoomEditor.Ui.refs.globalFields.classList.add('field-hidden');
        RoomEditor.Ui.refs.platformFields.classList.add('field-hidden');
        RoomEditor.Ui.refs.moverFields.classList.add('field-hidden');
        RoomEditor.Ui.refs.doorFields.classList.add('field-hidden');
        RoomEditor.Ui.refs.keyFields.classList.add('field-hidden');
        RoomEditor.Ui.refs.abilityFields.classList.add('field-hidden');

        if (RoomEditor.State.selected.kind === 'vertex') {
          RoomEditor.Ui.refs.inspectorTitle.textContent = `Vertex ${RoomEditor.State.selected.index + 1}`;
          return;
        }

        if (RoomEditor.State.selected.kind === 'room-edge') {
          RoomEditor.Ui.refs.selectionInspector.classList.add('hidden');
          return;
        }

        if (RoomEditor.State.selected.kind === 'room-shell') {
          RoomEditor.Ui.refs.inspectorTitle.textContent = `${RoomEditor.State.currentRoomId} shell`;
          return;
        }

        if (RoomEditor.State.selected.kind === 'start') {
          RoomEditor.Ui.refs.inspectorTitle.textContent = `${RoomEditor.State.currentRoomId} player start`;
          return;
        }

        if (RoomEditor.State.selected.kind === 'platform') {
          RoomEditor.Ui.refs.inspectorTitle.textContent = RoomEditor.State.selected.id;
          RoomEditor.Ui.refs.platformFields.classList.remove('field-hidden');
          return;
        }

        if (RoomEditor.State.selected.kind === 'mover') {
          RoomEditor.Ui.refs.inspectorTitle.textContent = RoomEditor.State.selected.id;
          RoomEditor.Ui.refs.moverFields.classList.remove('field-hidden');
          return;
        }

        if (RoomEditor.State.selected.kind === 'mover-start' || RoomEditor.State.selected.kind === 'mover-end') {
          RoomEditor.Ui.refs.inspectorTitle.textContent = RoomEditor.State.selected.id;
          RoomEditor.Ui.refs.moverFields.classList.remove('field-hidden');
          return;
        }

        if (RoomEditor.State.selected.kind === 'door') {
          RoomEditor.Ui.refs.inspectorTitle.textContent = RoomEditor.State.selected.id;
          RoomEditor.Ui.refs.doorFields.classList.remove('field-hidden');
          return;
        }

        if (RoomEditor.State.selected.kind === 'key') {
          RoomEditor.Ui.refs.inspectorTitle.textContent = RoomEditor.State.selected.id;
          RoomEditor.Ui.refs.keyFields.classList.remove('field-hidden');
          return;
        }

        if (RoomEditor.State.selected.kind === 'ability') {
          RoomEditor.Ui.refs.inspectorTitle.textContent = RoomEditor.State.selected.id;
          RoomEditor.Ui.refs.abilityFields.classList.remove('field-hidden');
          return;
        }
      }

function populateRoomSelect() {
        if (!RoomEditor.State.data?.rooms?.length) {
          RoomEditor.Ui.refs.roomSelect.innerHTML = '';
          RoomEditor.Ui.refs.roomSelect.value = '';
          return;
        }
        RoomEditor.State.data.rooms.forEach(ensureRoomShape);
        RoomEditor.Ui.refs.roomSelect.innerHTML = RoomEditor.State.data.rooms
          .map((room) => `<option value="${room.id}">${room.id} - ${room.name}</option>`)
          .join('');
        RoomEditor.Ui.refs.roomSelect.value = RoomEditor.State.currentRoomId;
      }

function syncPropertyInputs() {
        const room = RoomEditor.Model.currentRoom();
        if (!room) {
          RoomEditor.Ui.refs.itemX.value = '';
          RoomEditor.Ui.refs.itemY.value = '';
          RoomEditor.Ui.refs.itemLen.value = '';
          RoomEditor.Ui.refs.itemTint.value = '';
          RoomEditor.Ui.refs.moverEndX.value = '';
          RoomEditor.Ui.refs.moverEndY.value = '';
          RoomEditor.Ui.refs.moverLen.value = '';
          RoomEditor.Ui.refs.moverTint.value = '';
          RoomEditor.Ui.refs.moverInitialState.value = 'unlocked';
          RoomEditor.Ui.refs.doorLabel.value = '';
          RoomEditor.Ui.refs.doorTarget.value = '';
          RoomEditor.Ui.refs.doorStateForward.value = 'unlocked';
          RoomEditor.Ui.refs.doorStateReverse.value = 'unlocked';
          RoomEditor.Ui.refs.keyLabel.value = '';
          RoomEditor.Ui.refs.keyDoorTarget.value = '';
          RoomEditor.Ui.refs.abilityType.value = RoomEditor.Constants.ABILITY_DEFS[0].id;
          updateSelectionSummary();
          updateInspector();
          renderInventory(null);
          return;
        }
        RoomEditor.Model.ensureRoomShape(room);
        RoomEditor.Ui.refs.roomWidth.value = room.size.width;
        RoomEditor.Ui.refs.roomHeight.value = room.size.height;
        RoomEditor.Ui.refs.globalX.value = room.global.x;
        RoomEditor.Ui.refs.globalY.value = room.global.y;

        const selected = RoomEditor.Input.resolveSelected();
        if (!selected || RoomEditor.State.selectionItems.length !== 1) {
          RoomEditor.Ui.refs.itemX.value = '';
          RoomEditor.Ui.refs.itemY.value = '';
          RoomEditor.Ui.refs.itemLen.value = '';
          RoomEditor.Ui.refs.itemTint.value = '';
          RoomEditor.Ui.refs.moverEndX.value = '';
          RoomEditor.Ui.refs.moverEndY.value = '';
          RoomEditor.Ui.refs.moverLen.value = '';
          RoomEditor.Ui.refs.moverTint.value = '';
          RoomEditor.Ui.refs.moverInitialState.value = 'unlocked';
          RoomEditor.Ui.refs.doorLabel.value = '';
          RoomEditor.Ui.refs.doorTarget.value = '';
          RoomEditor.Ui.refs.doorStateForward.value = 'unlocked';
          RoomEditor.Ui.refs.doorStateReverse.value = 'unlocked';
          RoomEditor.Ui.refs.keyLabel.value = '';
          RoomEditor.Ui.refs.keyDoorTarget.value = '';
          RoomEditor.Ui.refs.abilityType.value = RoomEditor.Constants.ABILITY_DEFS[0].id;
          updateSelectionSummary();
          updateInspector();
          renderInventory(room);
          return;
        }
        RoomEditor.Ui.refs.itemX.value = selected.item.x ?? '';
        RoomEditor.Ui.refs.itemY.value = selected.item.y ?? '';
        RoomEditor.Ui.refs.itemLen.value = selected.item.len ?? '';
        RoomEditor.Ui.refs.itemTint.value = selected.item.tint ?? '';
        RoomEditor.Ui.refs.moverEndX.value = selected.item.endX ?? '';
        RoomEditor.Ui.refs.moverEndY.value = selected.item.endY ?? '';
        RoomEditor.Ui.refs.moverLen.value = selected.item.len ?? '';
        RoomEditor.Ui.refs.moverTint.value = selected.item.tint ?? '';
        RoomEditor.Ui.refs.moverInitialState.value = selected.item.initialState ?? 'unlocked';
        RoomEditor.Ui.refs.doorLabel.value = selected.item.label ?? '';
        RoomEditor.Ui.refs.doorTarget.value = selected.item.targetRoom ?? '';
        RoomEditor.Ui.refs.doorStateForward.value = selected.item.initialState?.forward ?? 'unlocked';
        RoomEditor.Ui.refs.doorStateReverse.value = selected.item.initialState?.reverse ?? 'unlocked';
        RoomEditor.Ui.refs.keyLabel.value = selected.item.label ?? '';
        RoomEditor.Ui.refs.keyDoorTarget.value = selected.item.unlocksTarget ?? '';
        RoomEditor.Ui.refs.abilityType.value = RoomEditor.Model.getAbilityDef(selected.item.type)?.id || RoomEditor.Constants.ABILITY_DEFS[0].id;
        updateSelectionSummary();
        updateInspector();
        renderInventory(room);
      }

function populateTargetEdgeOptions(roomId, preferredEdgeIndex = null) {
        const targetRoom = RoomEditor.Model.getRoomById(roomId);
        if (!targetRoom) {
          RoomEditor.Ui.refs.edgeTargetIndex.innerHTML = '<option value="">No edge</option>';
          RoomEditor.Ui.refs.edgeTargetIndex.value = '';
          return;
        }

        const options = [];
        for (let edgeIndex = 0; edgeIndex < RoomEditor.Model.getEdgeCount(targetRoom); edgeIndex += 1) {
          options.push(`<option value="${edgeIndex}">${RoomEditor.Model.edgeLabel(targetRoom, edgeIndex)}</option>`);
        }
        RoomEditor.Ui.refs.edgeTargetIndex.innerHTML = options.join('');
        const fallbackValue = options.length ? '0' : '';
        RoomEditor.Ui.refs.edgeTargetIndex.value = options.some((_, index) => String(index) === String(preferredEdgeIndex))
          ? String(preferredEdgeIndex)
          : fallbackValue;
      }

function updateGlobalLinkControls() {
        const isGlobalView = RoomEditor.State.viewMode === 'global';
        RoomEditor.Ui.refs.globalLinkPanel.classList.toggle('hidden', !isGlobalView);
        if (!isGlobalView) return;

        const selected = RoomEditor.State.selectedGlobalEdge;
        const requestedTargetRoomId = RoomEditor.Ui.refs.edgeTargetRoom.value;
        const requestedTargetEdgeIndex = RoomEditor.Ui.refs.edgeTargetIndex.value;
        if (!selected) {
          RoomEditor.Ui.refs.globalLinkSummary.textContent = 'Select an edge in the global map to create or edit a room connection.';
          RoomEditor.Ui.refs.edgeTargetRoom.innerHTML = '<option value="">No edge selected</option>';
          RoomEditor.Ui.refs.edgeTargetIndex.innerHTML = '<option value="">No edge selected</option>';
          RoomEditor.Ui.refs.edgeTargetRoom.disabled = true;
          RoomEditor.Ui.refs.edgeTargetIndex.disabled = true;
          RoomEditor.Ui.refs.linkSelectedEdge.disabled = true;
          RoomEditor.Ui.refs.clearSelectedEdgeLink.disabled = true;
          RoomEditor.Ui.refs.snapSelectedEdge.disabled = true;
          return;
        }

        const room = RoomEditor.Model.getRoomById(selected.roomId);
        const existingLink = RoomEditor.Topology.getEdgeLink(selected.roomId, selected.edgeIndex);
        const targetRooms = RoomEditor.State.data.rooms.filter((entry) => entry.id !== selected.roomId);
        RoomEditor.Ui.refs.edgeTargetRoom.innerHTML = targetRooms.length
          ? targetRooms.map((entry) => `<option value="${entry.id}">${entry.id} - ${entry.name}</option>`).join('')
          : '<option value="">No target rooms</option>';

        const selectedTargetRoomId = targetRooms.find((entry) => entry.id === requestedTargetRoomId)?.id
          || existingLink?.targetRoomId
          || targetRooms[0]?.id
          || '';
        RoomEditor.Ui.refs.edgeTargetRoom.value = selectedTargetRoomId;
        const preferredTargetEdgeIndex = requestedTargetRoomId === selectedTargetRoomId && requestedTargetEdgeIndex !== ''
          ? Number(requestedTargetEdgeIndex)
          : existingLink?.targetRoomId === selectedTargetRoomId
            ? existingLink.targetEdgeIndex
            : null;
        populateTargetEdgeOptions(selectedTargetRoomId, preferredTargetEdgeIndex);

        RoomEditor.Ui.refs.edgeTargetRoom.disabled = targetRooms.length === 0;
        RoomEditor.Ui.refs.edgeTargetIndex.disabled = !selectedTargetRoomId;
        RoomEditor.Ui.refs.linkSelectedEdge.disabled = targetRooms.length === 0 || RoomEditor.Ui.refs.edgeTargetIndex.value === '';
        RoomEditor.Ui.refs.clearSelectedEdgeLink.disabled = !existingLink;
        RoomEditor.Ui.refs.snapSelectedEdge.disabled = !existingLink;

        const sourceLabel = RoomEditor.Model.edgeLabel(room, selected.edgeIndex);
        if (!existingLink) {
          RoomEditor.Ui.refs.globalLinkSummary.innerHTML = `<strong>${room.id}</strong> · ${sourceLabel}<br>Not linked yet. Choose a target room and edge, then click Link Edge.`;
          return;
        }

        const targetRoom = RoomEditor.Model.getRoomById(existingLink.targetRoomId);
        const targetLabel = targetRoom ? RoomEditor.Model.edgeLabel(targetRoom, existingLink.targetEdgeIndex) : `Edge ${existingLink.targetEdgeIndex + 1}`;
        RoomEditor.Ui.refs.globalLinkSummary.innerHTML = `<strong>${room.id}</strong> · ${sourceLabel}<br>Linked to <strong>${existingLink.targetRoomId}</strong> · ${targetLabel}. Drag the room or click Snap Room to align the connected walls.`;
      }

function renderInventorySection(type, items, labelFn, listId, countId) {
        const list = document.getElementById(listId);
        const count = document.getElementById(countId);
        if (!list) return;
        if (count) count.textContent = items.length;
        list.innerHTML = '';
        items.forEach((item) => {
          const row = document.createElement('div');
          row.className = 'inventory-item';
          row.dataset.id = item.id;
          if (RoomEditor.State.selected && RoomEditor.State.selected.id === item.id) row.classList.add('active');
          const idSpan = document.createElement('span');
          idSpan.className = 'inventory-item-id';
          idSpan.textContent = item.id;
          const infoSpan = document.createElement('span');
          infoSpan.className = 'inventory-item-info';
          infoSpan.textContent = labelFn(item);
          const delBtn = document.createElement('button');
          delBtn.className = 'inventory-item-delete';
          delBtn.dataset.itemId = item.id;
          delBtn.title = 'Delete';
          delBtn.type = 'button';
          delBtn.textContent = '×';
          row.appendChild(idSpan);
          row.appendChild(infoSpan);
          row.appendChild(delBtn);
          row.addEventListener('click', (e) => {
            if (e.target.classList.contains('inventory-item-delete')) return;
            RoomEditor.Input.selectItemById(item.id);
          });
          delBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            RoomEditor.Input.deleteItemById(item.id);
          });
          list.appendChild(row);
        });
      }

function renderInventory(room) {
        if (!room) {
          const nameEl = document.getElementById('inventoryRoomName');
          if (nameEl) nameEl.textContent = 'No room';
          ['vertexCount', 'platformCount', 'doorCount', 'keyCount', 'abilityCount', 'moverCount'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.textContent = '0';
          });
          renderInventorySection('platforms', [], () => '', 'invListPlatforms', 'invCountPlatforms');
          renderInventorySection('doors', [], () => '', 'invListDoors', 'invCountDoors');
          renderInventorySection('keys', [], () => '', 'invListKeys', 'invCountKeys');
          renderInventorySection('abilities', [], () => '', 'invListAbilities', 'invCountAbilities');
          renderInventorySection('movers', [], () => '', 'invListMovers', 'invCountMovers');
          const valBadge = document.getElementById('inventoryValidationBadge');
          if (valBadge) {
            valBadge.textContent = '';
            valBadge.className = 'validation-badge';
          }
          return;
        }
        const nameEl = document.getElementById('inventoryRoomName');
        if (nameEl) nameEl.textContent = room.name || room.id;

        // Update count badges (existing IDs stay updated via updateCounts too)
        const vc = document.getElementById('vertexCount');
        if (vc) vc.textContent = (room.polygon || []).length;
        const pc = document.getElementById('platformCount');
        if (pc) pc.textContent = (room.platforms || []).length;
        const dc = document.getElementById('doorCount');
        if (dc) dc.textContent = (room.doors || []).length;
        const kc = document.getElementById('keyCount');
        if (kc) kc.textContent = (room.keys || []).length;
        const ac = document.getElementById('abilityCount');
        if (ac) ac.textContent = (room.abilities || []).length;
        const mc = document.getElementById('moverCount');
        if (mc) mc.textContent = (room.movingPlatforms || []).length;

        renderInventorySection('platforms', room.platforms || [], (p) => `x:${p.x} y:${p.y} len:${p.len}`, 'invListPlatforms', 'invCountPlatforms');
        renderInventorySection('doors', room.doors || [], (d) => `${d.label || ''} → ${d.targetRoom || '?'} (${d.kind})`, 'invListDoors', 'invCountDoors');
        renderInventorySection('keys', room.keys || [], (k) => k.label || k.id, 'invListKeys', 'invCountKeys');
        renderInventorySection('abilities', room.abilities || [], (a) => RoomEditor.Model.getAbilityLabel(a.type) || a.id, 'invListAbilities', 'invCountAbilities');
        renderInventorySection('movers', room.movingPlatforms || [], (m) => `(${m.x},${m.y})→(${m.endX},${m.endY})`, 'invListMovers', 'invCountMovers');

        const valBadge = document.getElementById('inventoryValidationBadge');
        if (valBadge) {
          const vertCount = (room.polygon || []).length;
          if (vertCount >= 3) {
            valBadge.textContent = 'Shape OK';
            valBadge.className = 'validation-badge pass';
          } else {
            valBadge.textContent = vertCount ? 'Open shape' : 'No shell';
            valBadge.className = 'validation-badge warn';
          }
        }
      }

function updateEmptyStates() {
        const noRooms = !RoomEditor.State.data || !RoomEditor.State.data.rooms || RoomEditor.State.data.rooms.length === 0;
        const noRoomsEl = document.getElementById('emptyStateNoRooms');
        const noDataEl = document.getElementById('emptyStateNoData');
        const roomCanvasEl = document.getElementById('roomCanvas');
        if (noRoomsEl) noRoomsEl.style.display = noRooms ? 'flex' : 'none';
        if (noDataEl) noDataEl.style.display = 'none';
        if (roomCanvasEl) roomCanvasEl.style.display = noRooms ? 'none' : 'block';
      }

function renderEmptyRoomHint() {
        const room = RoomEditor.Model.currentRoom();
        if (!room || (room.polygon && room.polygon.length > 0)) return;
        const ctx = RoomEditor.Viewport.roomCanvas.getContext('2d');
        ctx.save();
        ctx.fillStyle = 'rgba(93, 120, 112, 0.6)';
        ctx.font = '14px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Click to place vertices and define this room\'s shape', RoomEditor.Viewport.roomCanvas.width / 2, RoomEditor.Viewport.roomCanvas.height / 2 - 10);
        ctx.font = '12px "Plus Jakarta Sans", sans-serif';
        ctx.fillStyle = 'rgba(93, 120, 112, 0.4)';
        ctx.fillText('Hold Shift and click to close the polygon', RoomEditor.Viewport.roomCanvas.width / 2, RoomEditor.Viewport.roomCanvas.height / 2 + 14);
        ctx.restore();
      }

  RoomEditor.Ui.configureNav = configureNav;
  RoomEditor.Ui.roomEditorProjectUrl = roomEditorProjectUrl;
  RoomEditor.Ui.roomEditorLocalSlotUrl = roomEditorLocalSlotUrl;
  RoomEditor.Ui.spriteWorkbenchProjectUrl = spriteWorkbenchProjectUrl;
  RoomEditor.Ui.escapeHtml = escapeHtml;
  RoomEditor.Ui.formatDate = formatDate;
  RoomEditor.Ui.syncSidebarProjectName = syncSidebarProjectName;
  RoomEditor.Ui.initSidebarToggle = initSidebarToggle;
  RoomEditor.Ui.renderProjectList = renderProjectList;
  RoomEditor.Ui.populateAbilityOptions = populateAbilityOptions;
  RoomEditor.Ui.setStatus = setStatus;
  RoomEditor.Ui.showToast = showToast;
  RoomEditor.Ui.setActivity = setActivity;
  RoomEditor.Ui.clearActivity = clearActivity;
  RoomEditor.Ui.updateCounts = updateCounts;
  RoomEditor.Ui.updateSelectionSummary = updateSelectionSummary;
  RoomEditor.Ui.updateInspector = updateInspector;
  RoomEditor.Ui.populateRoomSelect = populateRoomSelect;
  RoomEditor.Ui.syncPropertyInputs = syncPropertyInputs;
  RoomEditor.Ui.populateTargetEdgeOptions = populateTargetEdgeOptions;
  RoomEditor.Ui.updateGlobalLinkControls = updateGlobalLinkControls;
  RoomEditor.Ui.renderInventorySection = renderInventorySection;
  RoomEditor.Ui.renderInventory = renderInventory;
  RoomEditor.Ui.updateEmptyStates = updateEmptyStates;
  RoomEditor.Ui.renderEmptyRoomHint = renderEmptyRoomHint;

  function init() {
    configureNav();
    initSidebarToggle();
  }
  RoomEditor.Ui.init = init;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = RoomEditor.Ui;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
