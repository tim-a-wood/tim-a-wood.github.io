'use strict';
      const DATA_URL = './room-layout-data.json';
      const API_PING_URL = '/api/ping';
      const API_LAYOUT_URL = '/api/layout';
      const API_COPILOT_URL = '/api/copilot';
      const PAGE_PARAMS = new URLSearchParams(window.location.search);
      const ROOM_EDITOR_SESSION_PROJECT_KEY = 'room-editor:last-project-id';

      function sanitizeLocalSlot(raw) {
        const s = String(raw ?? '')
          .trim()
          .slice(0, 64);
        if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(s)) return '';
        return s;
      }

      let PROJECT_ID = (PAGE_PARAMS.get('project_id') || '').trim();
      const localSlotFromUrl = sanitizeLocalSlot(PAGE_PARAMS.get('local_slot') || '');
      /** If the URL drops ?project_id= (refresh/bookmark), restore last workbench project for this tab so storage keys and /api/projects/... stay aligned. */
      if (!PROJECT_ID && !localSlotFromUrl && PAGE_PARAMS.get('no_session_project') !== '1') {
        try {
          const recovered = (sessionStorage.getItem(ROOM_EDITOR_SESSION_PROJECT_KEY) || '').trim();
          if (recovered && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$/.test(recovered)) {
            const url = new URL(window.location.href);
            url.searchParams.set('project_id', recovered);
            window.history.replaceState({}, '', url.toString());
            PROJECT_ID = recovered;
          }
        } catch (_) {}
      }

      /** Separate browser projects for workflow testing; does not touch default scratch storage when unset. */
      const LOCAL_SLOT = !PROJECT_ID ? localSlotFromUrl : '';
      if (PROJECT_ID) {
        try {
          sessionStorage.setItem(ROOM_EDITOR_SESSION_PROJECT_KEY, PROJECT_ID);
        } catch (_) {}
      }

      const PROJECT_ART_DIRECTION_URL = PROJECT_ID
        ? `/api/projects/${encodeURIComponent(PROJECT_ID)}/art-direction`
        : '';
      const PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL = PROJECT_ID
        ? `/api/projects/${encodeURIComponent(PROJECT_ID)}/art-direction/generate-concepts`
        : '';
      const PROJECT_BIOME_GENERATE_VISUALS_URL = PROJECT_ID
        ? `/api/projects/${encodeURIComponent(PROJECT_ID)}/art-direction/biome/generate-visuals`
        : '';
      const PROJECT_ART_DIRECTION_TEMPLATES_URL = PROJECT_ID
        ? `/api/projects/${encodeURIComponent(PROJECT_ID)}/art-direction/templates`
        : '';
      const ROOM_ENV_ARCHETYPES_URL = '/api/room-environment/archetypes';
      const LOCAL_STORAGE_PREFIX = 'ashen-hollow-room-layout-v1:local:';
      const SIDEBAR_KEY = 'roomCreator.sidebarCollapsed';
      const WORKBENCH_URL = new URL('./tools/2d-sprite-and-animation/index.html', window.location.href);
      const ROOM_EDITOR_URL = new URL('./room-layout-editor.html', window.location.href);
      const PROJECT_LAYOUT_API_URL = PROJECT_ID
        ? `/api/projects/${encodeURIComponent(PROJECT_ID)}/room-layout`
        : API_LAYOUT_URL;
      function projectRoomEnvironmentApiUrl(roomId, action) {
        if (!PROJECT_ID || !roomId) return '';
        return `/api/projects/${encodeURIComponent(PROJECT_ID)}/rooms/${encodeURIComponent(roomId)}/environment/${action}`;
      }
      function projectRoomEnvironmentFeedbackApiUrl(roomId) {
        return projectRoomEnvironmentApiUrl(roomId, 'feedback');
      }
      const PROJECT_LAYOUT_DOWNLOAD_NAME = PROJECT_ID
        ? `${PROJECT_ID}-room-layout.json`
        : LOCAL_SLOT
          ? `local-${LOCAL_SLOT}-room-layout.json`
          : 'room-layout-data.json';
      const LAYOUT_STORAGE_KEY = PROJECT_ID
        ? `ashen-hollow-room-layout-v1:${PROJECT_ID}`
        : LOCAL_SLOT
          ? `${LOCAL_STORAGE_PREFIX}${LOCAL_SLOT}`
          : 'ashen-hollow-room-layout-v1';
      /** After Save (or dirty navigate), prefer this copy on reload until Sync canonical or Reload from disk (server would otherwise overwrite). */
      function getLayoutPreferBrowserKey() {
        if (LOCAL_SLOT && !PROJECT_ID) return `ashen-hollow-room-layout-v1:prefer-browser:local:${LOCAL_SLOT}`;
        if (PROJECT_ID) return `ashen-hollow-room-layout-v1:prefer-browser:${PROJECT_ID}`;
        return 'ashen-hollow-room-layout-v1:prefer-browser:default';
      }
      const SEED_DATA = JSON.parse(document.getElementById('seedData').textContent);
      const ROOM_AI_SESSION_ID = `rwai-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
      const ROOM_W = 1600;
      const ROOM_H = 1200;
      const TILE = 32;
      /** Level 2 traversal warnings — advisory only; tune via window.VALIDATION_L2. See docs/room-layout-validation.md (DOC-ROOM-VALIDATION-001). */
      const VALIDATION_L2 = {
        /** Warn if vertical drop to the nearest “related” platform below exceeds this. */
        maxVerticalStepPx: 240,
        /**
         * Horizontal gap between paired platforms (see maxHorizontalSeparationForPairPx).
         * Kept equal to the pair cap so we do not warn on gaps we already allowed when pairing —
         * otherwise 400–520px gaps spuriously warn (see L2-002).
         */
        maxHorizontalGapPx: 520,
        /** Doors / keys / abilities farther than this from any platform surface (Manhattan-ish via spec). */
        interactMaxDistPx: 240,
        /** Only pair platform A→B for L2-001/L2-002 when x-interval gap ≤ this (overlap = 0 gap). */
        maxHorizontalSeparationForPairPx: 520
      };
      const PLATFORM_H = 14;
      const ROOM_MARGIN_LEFT = 132;
      const ROOM_MARGIN_RIGHT = 236;
      const ROOM_MARGIN_TOP = 16;
      const ROOM_MARGIN_BOTTOM = 16;
      const GLOBAL_ROOM_PREVIEW_SCALE = 0.12;
      const HIT_VERTEX = 18;
      const HIT_DOOR_X = 24;
      const HIT_DOOR_Y = 36;
      const HIT_PLATFORM_PAD = 12;
      const HIT_GLOBAL_PAD = 18;
      const HIT_LINK_GUIDE_PAD = 18;
      const HIT_ROOM_EDGE_PAD = 14;
      const GLOBAL_DRAG_START_DISTANCE = 6;
      const VIEW_PAN_STEP = 96;
      const ROOM_ZOOM_MIN = 0.5;
      const ROOM_ZOOM_MAX = 3;
      const GLOBAL_ZOOM_MIN = 0.4;
      const GLOBAL_ZOOM_MAX = 2;
      const ABILITY_DEFS = Object.freeze([
        { id: 'double_jump', label: 'Double Jump' }
      ]);
      const roomCanvas = document.getElementById('roomCanvas');
      const roomCtx = roomCanvas.getContext('2d');
      const globalCanvas = document.getElementById('globalCanvas');
      const globalCtx = globalCanvas.getContext('2d');

      function configureNav() {
        const navHome = document.getElementById('navHome');
        const navSpriteCreation = document.getElementById('navSpriteCreation');
        const navRoomCreation = document.getElementById('navRoomCreation');
        const navDocs = document.getElementById('navDocs');
        const navLogo = document.getElementById('navLogo');
        const roomUrl = new URL(ROOM_EDITOR_URL.toString());
        const spriteUrl = new URL(WORKBENCH_URL.toString());
        const homeUrl = new URL(WORKBENCH_URL.toString());
        const docsUrl = new URL(WORKBENCH_URL.toString());

        if (PROJECT_ID) {
          roomUrl.searchParams.set('project_id', PROJECT_ID);
          spriteUrl.searchParams.set('project_id', PROJECT_ID);
          homeUrl.searchParams.set('project_id', PROJECT_ID);
          docsUrl.searchParams.set('project_id', PROJECT_ID);
        } else if (LOCAL_SLOT) {
          roomUrl.searchParams.set('local_slot', LOCAL_SLOT);
        }
        docsUrl.hash = 'docs';

        if (navLogo) navLogo.href = homeUrl.toString();
        if (navHome) navHome.href = homeUrl.toString();
        if (navSpriteCreation) navSpriteCreation.href = spriteUrl.toString();
        if (navRoomCreation) navRoomCreation.href = roomUrl.toString();
        if (navDocs) navDocs.href = docsUrl.toString();
      }
      configureNav();

      function roomEditorProjectUrl(projectId) {
        const url = new URL(ROOM_EDITOR_URL.toString());
        if (projectId) url.searchParams.set('project_id', projectId);
        return url.toString();
      }

      function roomEditorLocalSlotUrl(slot) {
        const url = new URL(ROOM_EDITOR_URL.toString());
        const s = sanitizeLocalSlot(slot);
        if (s) url.searchParams.set('local_slot', s);
        return url.toString();
      }

      function listLocalProjectSlots() {
        const out = [];
        try {
          for (let i = 0; i < window.localStorage.length; i += 1) {
            const k = window.localStorage.key(i);
            if (k && k.startsWith(LOCAL_STORAGE_PREFIX)) {
              out.push(k.slice(LOCAL_STORAGE_PREFIX.length));
            }
          }
        } catch (_) {}
        return out.sort((a, b) => a.localeCompare(b));
      }

      function persistCurrentLayoutToStorage() {
        if (!RoomEditor.State.data) return;
        try {
          window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(RoomEditor.State.data, null, 2));
          if (!LOCAL_SLOT || PROJECT_ID) {
            window.localStorage.setItem(getLayoutPreferBrowserKey(), '1');
          }
        } catch (err) {
          setStatus(`Could not save to browser storage: ${err.message}`, 'error');
        }
      }

      function navigateToRoomEditorUrl(url) {
        if (RoomEditor.State.isDirty) {
          persistCurrentLayoutToStorage();
          setDirty(false);
        }
        window.location.href = url;
      }

      function createNewLocalProject() {
        const suggested = `sandbox-${Date.now()}`;
        const raw = window.prompt(
          'New local project id (letters, numbers, dashes, underscores; must start with a letter or number). Your other saved projects are not changed.',
          suggested
        );
        if (raw == null) return;
        const slot = sanitizeLocalSlot(raw);
        if (!slot) {
          setStatus('Invalid id. Use 1–64 chars: start with a letter or number, then letters, numbers, - or _.', 'error');
          return;
        }
        navigateToRoomEditorUrl(roomEditorLocalSlotUrl(slot));
      }

      function deleteLocalProjectSlot(slot) {
        const s = sanitizeLocalSlot(slot);
        if (!s) return;
        const key = `${LOCAL_STORAGE_PREFIX}${s}`;
        if (!window.confirm(`Remove saved data for local project “${s}” from this browser? This does not delete other projects.`)) {
          return;
        }
        try {
          window.localStorage.removeItem(key);
        } catch (_) {}
        if (LOCAL_SLOT === s) {
          window.location.href = roomEditorProjectUrl('');
          return;
        }
        refreshProjectList().catch(() => {});
        setStatus(`Removed local project “${s}”.`, 'success');
      }

      function spriteWorkbenchProjectUrl(projectId) {
        const url = new URL(WORKBENCH_URL.toString());
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

      RoomEditor.State = {
        data: null,
        currentRoomId: null,
        viewMode: 'room',
        tool: 'select',
        roomZoom: 1,
        roomPan: { x: 0, y: 0 },
        globalZoom: 1,
        globalPan: { x: 0, y: 0 },
        selected: null,
        selectionItems: [],
        drag: null,
        pendingMoverStart: null,
        hoverLocal: null,
        selectedGlobalEdge: null,
        globalSnapPreview: null,
        fileHandle: null,
        apiAvailable: false,
        toastTimer: null,
        activity: null,
        projects: [],
        projectsListLoadError: null,
        isDirty: false,
        lastPlacedId: null,
        lastValidationReport: null,
        roomWizard: {
          active: false,
          phase: 'layout',
          roomId: null,
          touched: false,
          copilotPreview: null,
          selectedArchetypeId: '',
          approvedPreviewId: null,
          progressTimers: {},
          lastEnvTab: 'setup',
          envStep: 'describe',
          aiRequestPending: false,
          resultsToggles: {
            structural: true,
            background: true,
            decor: true,
            semantics: false,
            exclusion: false,
            unresolved: false,
            validation: false
          }
        },
        copilot: {
          serverReachable: false,
          geminiConfigured: false,
          geminiImageModel: '',
          geminiLastError: null
        },
        artDirection: null,
        artDirectionTemplates: [],
        artDirectionConceptOptions: [],
        roomEnvironmentArchetypes: [],
        /** 'world' | 'room' | 'art-direction' — top toggle; room uses the existing room wizard rail. */
        workflowScope: 'world',
        /** 1–4 when scope is world: layout, placeholder, placeholder, review/export. */
        worldWorkflowStep: 1,
        /** Mirrors legacy 1=world, 2=room, 3=review for tests and older call sites. */
        editorWorkflowStep: 1
      };

      function syncLegacyEditorWorkflowStep() {
        if (RoomEditor.State.workflowScope === 'room' || RoomEditor.State.workflowScope === 'art-direction') RoomEditor.State.editorWorkflowStep = 2;
        else if (RoomEditor.State.worldWorkflowStep === 4) RoomEditor.State.editorWorkflowStep = 3;
        else RoomEditor.State.editorWorkflowStep = 1;
      }

      function syncSidebarProjectName() {
        if (!RoomEditor.Ui.refs.sidebarProjectName) return;
        if (!PROJECT_ID) {
          if (LOCAL_SLOT) {
            RoomEditor.Ui.refs.sidebarProjectName.textContent = `Local · ${LOCAL_SLOT}`;
          } else {
            RoomEditor.Ui.refs.sidebarProjectName.textContent = 'Local Layout';
          }
          return;
        }
        const project = RoomEditor.State.projects.find((entry) => entry.project_id === PROJECT_ID);
        RoomEditor.Ui.refs.sidebarProjectName.textContent = project?.project_name || PROJECT_ID;
      }

      function initSidebarToggle() {
        const appShell = document.querySelector('.app-shell');
        const toggle = document.querySelector('.rail-toggle');
        if (!appShell || !toggle) return;
        // Do not restore the old persisted collapsed state here. It hid the entire
        // project list, making existing workbench projects look like they vanished.
        appShell.classList.remove('sidebar-collapsed');
        try {
          window.localStorage.removeItem(SIDEBAR_KEY);
        } catch (_) {}
        const sync = () => {
          const collapsed = appShell.classList.contains('sidebar-collapsed');
          toggle.setAttribute('aria-label', collapsed ? 'Expand project panel' : 'Collapse project panel');
          toggle.textContent = collapsed ? '›' : '‹';
        };
        sync();
        toggle.addEventListener('click', () => {
          appShell.classList.toggle('sidebar-collapsed');
          window.localStorage.setItem(SIDEBAR_KEY, appShell.classList.contains('sidebar-collapsed') ? '1' : '0');
          sync();
        });
      }

      function renderProjectList() {
        if (!RoomEditor.Ui.refs.roomProjectList) return;
        const cards = [];
        const defaultLocalActive = !PROJECT_ID && !LOCAL_SLOT ? 'active' : '';
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
        listLocalProjectSlots().forEach((slot) => {
          const active = !PROJECT_ID && LOCAL_SLOT === slot ? 'active' : '';
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
        if (RoomEditor.State.projectsListLoadError) {
          cards.push(`
            <div class="project-card project-card--load-error" tabindex="0">
              <strong>Workbench projects did not load</strong>
              <div class="small-note project-card__error-detail">${escapeHtml(RoomEditor.State.projectsListLoadError)}</div>
              <div class="small-note">Open this page from <code>http://127.0.0.1:8766/room-layout-editor.html</code> with <code>./scripts/start_sprite_workbench_with_env.sh</code> running. GitHub Pages and <code>file://</code> cannot reach <code>/api/projects</code>.</div>
              <div class="small-note">If you already did that, hard-refresh so scripts reload (Safari: Shift+Reload, or Develop menu, Empty Caches). The <code>?v=</code> on each script URL changes when the editor updates.</div>
            </div>
          `);
        }
        [...RoomEditor.State.projects]
          .sort((a, b) => (a.archived_at ? 1 : 0) - (b.archived_at ? 1 : 0))
          .forEach((project) => {
          const active = project.project_id === PROJECT_ID ? 'active' : '';
          const archivedLine = project.archived_at
            ? '<div class="small-note">Archived in Sprite Workbench (sidebar <strong>Delete</strong> only hid it from the default list). You can still open room layout or Sprite Creation.</div>'
            : '';
          cards.push(`
            <div class="project-card ${active}" data-room-url="${escapeHtml(roomEditorProjectUrl(project.project_id))}" data-sprite-url="${escapeHtml(spriteWorkbenchProjectUrl(project.project_id))}">
              <strong>${escapeHtml(project.project_name || project.project_id)}</strong>
              <small>${escapeHtml(project.current_stage || 'Sprite Creation')} · Last modified ${escapeHtml(formatDate(project.updated_at))}</small>
              ${archivedLine}
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
            if (roomUrl) navigateToRoomEditorUrl(roomUrl);
          });
          card.querySelector('[data-action="open-room"]')?.addEventListener('click', (event) => {
            event.stopPropagation();
            if (roomUrl) navigateToRoomEditorUrl(roomUrl);
          });
          card.querySelector('[data-action="delete-local"]')?.addEventListener('click', (event) => {
            event.stopPropagation();
            const slot = card.dataset.localSlot;
            if (slot) deleteLocalProjectSlot(slot);
          });
          card.querySelector('[data-action="open-sprite"]')?.addEventListener('click', (event) => {
            event.stopPropagation();
            if (spriteUrl) window.location.href = spriteUrl;
          });
        });
      }

      async function refreshProjectList() {
        try {
          const response = await fetch('/api/projects?include_archived=1', { cache: 'no-store' });
          if (!response.ok) throw new Error(`Project load failed (${response.status})`);
          const payload = await response.json();
          RoomEditor.State.projects = Array.isArray(payload.projects) ? payload.projects : [];
          RoomEditor.State.projectsListLoadError = null;
        } catch (err) {
          RoomEditor.State.projects = [];
          const detail = err && err.message ? err.message : 'offline or blocked';
          RoomEditor.State.projectsListLoadError = detail;
          setStatus(
            `Workbench project list unavailable (${detail}). Run ./scripts/start_sprite_workbench_with_env.sh and open this page from http://127.0.0.1:8766 (same host as the API). Local Layout and sandbox rows below still work.`,
            'warning'
          );
        }
        syncSidebarProjectName();
        renderProjectList();
      }

      function getAbilityDef(type) {
        return ABILITY_DEFS.find((entry) => entry.id === type) || ABILITY_DEFS[0];
      }

      function getAbilityLabel(type) {
        return getAbilityDef(type)?.label || type || 'Ability';
      }

      function populateAbilityOptions() {
        RoomEditor.Ui.refs.abilityType.innerHTML = ABILITY_DEFS
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

      function selectionKey(item) {
        if (item.kind === 'vertex') return `${item.kind}:${item.index}`;
        if (item.kind === 'room-edge') return `${item.kind}:${item.edgeIndex}`;
        if (item.kind === 'mover-start' || item.kind === 'mover-end') return `${item.kind}:${item.id}`;
        if (item.kind === 'room-shell' || item.kind === 'start') return item.kind;
        return `${item.kind}:${item.id}`;
      }

      function setSelection(items) {
        RoomEditor.State.selectionItems = items.slice();
        RoomEditor.State.selected = RoomEditor.State.selectionItems[0] || null;
      }

      function setViewMode(view) {
        RoomEditor.State.viewMode = view === 'global' ? 'global' : 'room';
        updateWorkflowRailPills();
      }

      function fitRoomToCanvas() {
        resetRoomView();
      }

      function dismissSelection() {
        RoomEditor.State.pendingMoverStart = null;
        RoomEditor.State.hoverLocal = null;
        setSelection([]);
        redraw();
      }

      function selectionContains(item) {
        const key = selectionKey(item);
        return RoomEditor.State.selectionItems.some((selected) => selectionKey(selected) === key);
      }

      function updateSyncButtonState() {
        RoomEditor.Ui.refs.syncCanonicalJson.disabled = !RoomEditor.State.apiAvailable;
        RoomEditor.Ui.refs.syncCanonicalJson.title = RoomEditor.State.apiAvailable
          ? (PROJECT_ID ? 'Save this layout into the active workbench project' : 'Overwrite room-layout-data.json on this dev machine')
          : 'Open from the Sprite Workbench server (same origin as /api/layout) to enable canonical sync';
      }

      function snap(value) {
        const size = Number(RoomEditor.Ui.refs.snapSize.value || 0);
        if (!size) return Math.round(value);
        return Math.round(value / size) * size;
      }

      function currentRoom() {
        return RoomEditor.State.data.rooms.find((room) => room.id === RoomEditor.State.currentRoomId);
      }

      function ensureRoomShape(room) {
        if (!room.size) room.size = { width: ROOM_W, height: ROOM_H };
        room.size.width = Math.max(320, Number(room.size.width || ROOM_W));
        room.size.height = Math.max(320, Number(room.size.height || ROOM_H));
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
          type: getAbilityDef(ability?.type)?.id || ABILITY_DEFS[0].id
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

      function getEdgeLink(roomId, edgeIndex) {
        const room = getRoomById(roomId);
        if (!room) return null;
        ensureRoomShape(room);
        return room.edgeLinks.find((link) => Number(link.edgeIndex) === Number(edgeIndex)) || null;
      }

      function clearRoomEdgeLink(roomId, edgeIndex, clearReciprocal = true) {
        const room = getRoomById(roomId);
        if (!room) return;
        ensureRoomShape(room);
        const existing = getEdgeLink(roomId, edgeIndex);
        room.edgeLinks = room.edgeLinks.filter((link) => Number(link.edgeIndex) !== Number(edgeIndex));
        if (!clearReciprocal || !existing) return;

        const targetRoom = getRoomById(existing.targetRoomId);
        if (!targetRoom) return;
        ensureRoomShape(targetRoom);
        targetRoom.edgeLinks = targetRoom.edgeLinks.filter((link) => Number(link.edgeIndex) !== Number(existing.targetEdgeIndex));
      }

      function clearAllRoomEdgeLinks(roomId) {
        const room = getRoomById(roomId);
        if (!room) return;
        ensureRoomShape(room);
        const links = [...room.edgeLinks];
        links.forEach((link) => clearRoomEdgeLink(roomId, link.edgeIndex, true));
      }

      function remapRoomEdgeLinks(roomId, remapEdgeIndex) {
        const room = getRoomById(roomId);
        if (!room) return;
        ensureRoomShape(room);
        const previousLinks = [...room.edgeLinks];
        previousLinks.forEach((link) => clearRoomEdgeLink(roomId, link.edgeIndex, true));
        previousLinks.forEach((link) => {
          const nextEdgeIndex = remapEdgeIndex(Number(link.edgeIndex), link);
          const targetRoom = getRoomById(link.targetRoomId);
          if (!Number.isInteger(nextEdgeIndex) || nextEdgeIndex < 0 || !targetRoom) return;
          ensureRoomShape(targetRoom);
          if (nextEdgeIndex >= getEdgeCount(room) || Number(link.targetEdgeIndex) >= getEdgeCount(targetRoom)) return;
          setRoomEdgeLink(roomId, nextEdgeIndex, link.targetRoomId, Number(link.targetEdgeIndex));
        });
      }

      function isRoomEdgeRemoved(room, edgeIndex) {
        ensureRoomShape(room);
        return room.removedEdges.includes(Number(edgeIndex));
      }

      function remapRoomRemovedEdges(roomId, remapEdgeIndex) {
        const room = getRoomById(roomId);
        if (!room) return;
        ensureRoomShape(room);
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
        room.removedEdges = [...new Set(nextRemovedEdges.filter((edgeIndex) => edgeIndex < getEdgeCount(room)))].sort((a, b) => a - b);
      }

      function toggleRoomEdgeRemoved(roomId, edgeIndex) {
        const room = getRoomById(roomId);
        if (!room) return false;
        ensureRoomShape(room);
        const normalizedIndex = ((Number(edgeIndex) % getEdgeCount(room)) + getEdgeCount(room)) % getEdgeCount(room);
        if (room.removedEdges.includes(normalizedIndex)) {
          room.removedEdges = room.removedEdges.filter((value) => value !== normalizedIndex);
          return false;
        }
        room.removedEdges = [...room.removedEdges, normalizedIndex].sort((a, b) => a - b);
        return true;
      }

      function setRoomEdgeLink(roomId, edgeIndex, targetRoomId, targetEdgeIndex) {
        if (!roomId || !targetRoomId || roomId === targetRoomId) return false;
        const room = getRoomById(roomId);
        const targetRoom = getRoomById(targetRoomId);
        if (!room || !targetRoom) return false;
        if (edgeIndex < 0 || targetEdgeIndex < 0) return false;
        if (edgeIndex >= getEdgeCount(room) || targetEdgeIndex >= getEdgeCount(targetRoom)) return false;

        clearRoomEdgeLink(roomId, edgeIndex, true);
        clearRoomEdgeLink(targetRoomId, targetEdgeIndex, true);

        room.edgeLinks.push({ edgeIndex, targetRoomId, targetEdgeIndex });
        targetRoom.edgeLinks.push({ edgeIndex: targetEdgeIndex, targetRoomId: roomId, targetEdgeIndex: edgeIndex });
        room.edgeLinks.sort((a, b) => a.edgeIndex - b.edgeIndex);
        targetRoom.edgeLinks.sort((a, b) => a.edgeIndex - b.edgeIndex);
        return true;
      }

      function getEdgeGlobalPoints(room, edgeIndex, roomGlobal = room.global) {
        const edge = getRoomEdge(room, edgeIndex);
        if (!edge) return null;
        const start = {
          x: roomGlobal.x + ((edge.start.x - (room.size.width / 2)) * GLOBAL_ROOM_PREVIEW_SCALE),
          y: roomGlobal.y + ((edge.start.y - (room.size.height / 2)) * GLOBAL_ROOM_PREVIEW_SCALE)
        };
        const end = {
          x: roomGlobal.x + ((edge.end.x - (room.size.width / 2)) * GLOBAL_ROOM_PREVIEW_SCALE),
          y: roomGlobal.y + ((edge.end.y - (room.size.height / 2)) * GLOBAL_ROOM_PREVIEW_SCALE)
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

      function getLinkedEdgeGuide(roomId, edgeIndex) {
        const link = getEdgeLink(roomId, edgeIndex);
        if (!link) return null;
        const room = getRoomById(roomId);
        const targetRoom = getRoomById(link.targetRoomId);
        if (!room || !targetRoom) return null;
        const sourceEdge = getEdgeCanvasPoints(room, edgeIndex);
        const targetEdge = getEdgeCanvasPoints(targetRoom, link.targetEdgeIndex);
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

      function edgeLength(edge) {
        if (!edge) return 0;
        return Math.hypot(edge.end.x - edge.start.x, edge.end.y - edge.start.y);
      }

      function globalPointToRoomLocal(room, point) {
        ensureRoomShape(room);
        return {
          x: (room.size.width / 2) + ((point.x - room.global.x) / GLOBAL_ROOM_PREVIEW_SCALE),
          y: (room.size.height / 2) + ((point.y - room.global.y) / GLOBAL_ROOM_PREVIEW_SCALE)
        };
      }

      function getRoomLinkedEdgeGuide(roomId, edgeIndex) {
        const link = getEdgeLink(roomId, edgeIndex);
        if (!link) return null;
        const room = getRoomById(roomId);
        const targetRoom = getRoomById(link.targetRoomId);
        if (!room || !targetRoom) return null;

        const sourceEdge = getRoomEdge(room, edgeIndex);
        const targetEdge = getRoomEdge(targetRoom, link.targetEdgeIndex);
        const targetGlobalEdge = getEdgeGlobalPoints(targetRoom, link.targetEdgeIndex, targetRoom.global);
        const sourceLength = edgeLength(sourceEdge);
        const targetLength = edgeLength(targetEdge);
        if (!sourceEdge || !targetEdge || !targetGlobalEdge || sourceLength <= 0.001 || targetLength <= 0.001) return null;

        const guideLocal = {
          start: globalPointToRoomLocal(room, targetGlobalEdge.start),
          end: globalPointToRoomLocal(room, targetGlobalEdge.end)
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
            start: roomToCanvasPoint(guideLocal.start.x, guideLocal.start.y),
            end: roomToCanvasPoint(guideLocal.end.x, guideLocal.end.y)
          }
        };
      }

      function getRoomVertexLinkSnapTargets(room, vertexIndex) {
        ensureRoomShape(room);
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
          const projected = distanceToSegment(mouse, target.guideCanvas.start, target.guideCanvas.end);
          const point = canvasToRoomPointRaw(projected.point.x, projected.point.y);
          if (!best || projected.distance < best.distance) {
            best = {
              ...target,
              point,
              canvas: projected.point,
              distance: projected.distance
            };
          }
        });
        if (!best || best.distance > HIT_LINK_GUIDE_PAD) return null;
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

      /** How far two edge segments are from lying on each other (world space); works for different edge lengths. */
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
        ensureRoomShape(room);
        if (!room.edgeLinks.length) return null;

        const projection = globalScale();
        const snapThreshold = 36 / projection.scale;
        let best = null;

        room.edgeLinks.forEach((link) => {
          const targetRoom = getRoomById(link.targetRoomId);
          if (!targetRoom) return;

          const sourceEdge = getEdgeGlobalPoints(room, link.edgeIndex, room.global);
          const targetEdge = getEdgeGlobalPoints(targetRoom, link.targetEdgeIndex, targetRoom.global);
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
            const snappedEdge = getEdgeGlobalPoints(room, link.edgeIndex, entry.proposedGlobal);
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
        const groupRoomIds = getSnapRoomGroup(candidate);
        if (!groupRoomIds.length || groupRoomIds.includes(candidate.targetRoomId)) {
          return false;
        }
        const snapshot = snapshotGlobalRoomGroup(groupRoomIds);
        const dx = candidate.proposedGlobal.x - room.global.x;
        const dy = candidate.proposedGlobal.y - room.global.y;
        applyGlobalRoomGroupDelta(snapshot, dx, dy);
        return true;
      }

      function currentRoomSize() {
        const room = currentRoom();
        ensureRoomShape(room);
        return room.size;
      }

      function clampZoom(value, min, max) {
        return Math.max(min, Math.min(max, value));
      }

      function roomViewport() {
        return {
          x: ROOM_MARGIN_LEFT,
          y: ROOM_MARGIN_TOP,
          width: roomCanvas.width - ROOM_MARGIN_LEFT - ROOM_MARGIN_RIGHT,
          height: roomCanvas.height - ROOM_MARGIN_TOP - ROOM_MARGIN_BOTTOM
        };
      }

      function roomScale() {
        const roomSize = currentRoomSize();
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
          ensureRoomShape(room);
          const previewHalfWidth = (room.size.width * GLOBAL_ROOM_PREVIEW_SCALE) / 2;
          const previewHalfHeight = (room.size.height * GLOBAL_ROOM_PREVIEW_SCALE) / 2;
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
        const sx = (globalCanvas.width - 80) / width;
        const sy = (globalCanvas.height - 80) / height;
        const scale = Math.min(sx, sy) * RoomEditor.State.globalZoom;
        return {
          bounds,
          scale,
          offsetX: ((globalCanvas.width - (width * scale)) / 2) + RoomEditor.State.globalPan.x,
          offsetY: ((globalCanvas.height - (height * scale)) / 2) + RoomEditor.State.globalPan.y
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
          x: snap(local.x),
          y: snap(local.y)
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
          x: snap(bounds.minX + ((x - offsetX) / scale)),
          y: snap(bounds.minY + ((y - offsetY) / scale))
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
        RoomEditor.State.roomZoom = clampZoom(Number((RoomEditor.State.roomZoom + delta).toFixed(2)), ROOM_ZOOM_MIN, ROOM_ZOOM_MAX);
        redraw();
      }

      function resetRoomView() {
        RoomEditor.State.roomZoom = 1;
        RoomEditor.State.roomPan.x = 0;
        RoomEditor.State.roomPan.y = 0;
        redraw();
      }

      function panRoomView(dx, dy) {
        RoomEditor.State.roomPan.x += dx;
        RoomEditor.State.roomPan.y += dy;
        redraw();
      }

      function adjustGlobalZoom(delta) {
        RoomEditor.State.globalZoom = clampZoom(Number((RoomEditor.State.globalZoom + delta).toFixed(2)), GLOBAL_ZOOM_MIN, GLOBAL_ZOOM_MAX);
        redraw();
      }

      function resetGlobalView() {
        RoomEditor.State.globalZoom = 1;
        RoomEditor.State.globalPan.x = 0;
        RoomEditor.State.globalPan.y = 0;
        redraw();
      }

      function panGlobalView(dx, dy) {
        RoomEditor.State.globalPan.x += dx;
        RoomEditor.State.globalPan.y += dy;
        redraw();
      }

      function drawRoomGrid(projection, color) {
        const stepX = TILE * projection.x;
        const stepY = TILE * projection.y;
        if (stepX <= 0.001 || stepY <= 0.001) return;
        const { viewport } = projection;
        roomCtx.save();
        roomCtx.strokeStyle = color;
        roomCtx.lineWidth = 1;
        roomCtx.beginPath();
        const startX = projection.offsetX + (Math.floor((viewport.x - projection.offsetX) / stepX) * stepX);
        for (let x = startX; x <= viewport.x + viewport.width + stepX; x += stepX) {
          roomCtx.moveTo(x + 0.5, viewport.y);
          roomCtx.lineTo(x + 0.5, viewport.y + viewport.height);
        }
        const startY = projection.offsetY + (Math.floor((viewport.y - projection.offsetY) / stepY) * stepY);
        for (let y = startY; y <= viewport.y + viewport.height + stepY; y += stepY) {
          roomCtx.moveTo(viewport.x, y + 0.5);
          roomCtx.lineTo(viewport.x + viewport.width, y + 0.5);
        }
        roomCtx.stroke();
        roomCtx.restore();
      }

      function getGlobalRoomPoints(room) {
        ensureRoomShape(room);
        const globalProjection = globalScale();
        const previewScale = globalProjection.scale * GLOBAL_ROOM_PREVIEW_SCALE;
        const center = globalToCanvasPoint(room.global.x, room.global.y);
        return room.polygon.map(([x, y]) => {
          const dx = (x - room.size.width / 2) * previewScale;
          const dy = (y - room.size.height / 2) * previewScale;
          return { x: center.x + dx, y: center.y + dy };
        });
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
        if (l2 === 0) return pointDistance(point, a);
        let t = ((point.x - a.x) * (b.x - a.x) + (point.y - a.y) * (b.y - a.y)) / l2;
        t = Math.max(0, Math.min(1, t));
        return pointDistance(point, {
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

      function updateJsonText() {
        RoomEditor.Ui.refs.jsonText.value = JSON.stringify(RoomEditor.State.data, null, 2);
        try {
          window.localStorage.setItem(LAYOUT_STORAGE_KEY, RoomEditor.Ui.refs.jsonText.value);
          if (!LOCAL_SLOT || PROJECT_ID) {
            window.localStorage.setItem(getLayoutPreferBrowserKey(), '1');
          }
        } catch (_) {}
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
          const room = currentRoom();
          const stateLabel = room && isRoomEdgeRemoved(room, RoomEditor.State.selected.edgeIndex) ? 'open' : 'solid';
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
        const room = currentRoom();
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
        const room = currentRoom();
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
          RoomEditor.Ui.refs.abilityType.value = ABILITY_DEFS[0].id;
          updateSelectionSummary();
          updateInspector();
          renderInventory(null);
          return;
        }
        ensureRoomShape(room);
        RoomEditor.Ui.refs.roomWidth.value = room.size.width;
        RoomEditor.Ui.refs.roomHeight.value = room.size.height;
        RoomEditor.Ui.refs.globalX.value = room.global.x;
        RoomEditor.Ui.refs.globalY.value = room.global.y;

        const selected = resolveSelected();
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
          RoomEditor.Ui.refs.abilityType.value = ABILITY_DEFS[0].id;
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
        RoomEditor.Ui.refs.abilityType.value = getAbilityDef(selected.item.type)?.id || ABILITY_DEFS[0].id;
        updateSelectionSummary();
        updateInspector();
        renderInventory(room);
      }

      function setSelectedGlobalEdge(selection) {
        RoomEditor.State.selectedGlobalEdge = selection ? { roomId: selection.roomId, edgeIndex: selection.edgeIndex } : null;
        RoomEditor.State.globalSnapPreview = null;
        RoomEditor.Ui.refs.edgeTargetRoom.value = '';
        RoomEditor.Ui.refs.edgeTargetIndex.value = '';
        updateGlobalLinkControls();
      }

      function populateTargetEdgeOptions(roomId, preferredEdgeIndex = null) {
        const targetRoom = getRoomById(roomId);
        if (!targetRoom) {
          RoomEditor.Ui.refs.edgeTargetIndex.innerHTML = '<option value="">No edge</option>';
          RoomEditor.Ui.refs.edgeTargetIndex.value = '';
          return;
        }

        const options = [];
        for (let edgeIndex = 0; edgeIndex < getEdgeCount(targetRoom); edgeIndex += 1) {
          options.push(`<option value="${edgeIndex}">${edgeLabel(targetRoom, edgeIndex)}</option>`);
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

        const room = getRoomById(selected.roomId);
        const existingLink = getEdgeLink(selected.roomId, selected.edgeIndex);
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

        const sourceLabel = edgeLabel(room, selected.edgeIndex);
        if (!existingLink) {
          RoomEditor.Ui.refs.globalLinkSummary.innerHTML = `<strong>${room.id}</strong> · ${sourceLabel}<br>Not linked yet. Choose a target room and edge, then click Link Edge.`;
          return;
        }

        const targetRoom = getRoomById(existingLink.targetRoomId);
        const targetLabel = targetRoom ? edgeLabel(targetRoom, existingLink.targetEdgeIndex) : `Edge ${existingLink.targetEdgeIndex + 1}`;
        RoomEditor.Ui.refs.globalLinkSummary.innerHTML = `<strong>${room.id}</strong> · ${sourceLabel}<br>Linked to <strong>${existingLink.targetRoomId}</strong> · ${targetLabel}. Drag the room or click Snap Room to align the connected walls.`;
      }

      function linkSelectedGlobalEdge() {
        const selected = RoomEditor.State.selectedGlobalEdge;
        if (!selected) return;
        const targetRoomId = RoomEditor.Ui.refs.edgeTargetRoom.value;
        const targetEdgeIndex = Number(RoomEditor.Ui.refs.edgeTargetIndex.value);
        if (!targetRoomId || !Number.isInteger(targetEdgeIndex)) return;
        const linked = setRoomEdgeLink(selected.roomId, selected.edgeIndex, targetRoomId, targetEdgeIndex);
        if (!linked) {
          setStatus('Edge link failed. Check that both rooms and edges are valid.');
          return;
        }
        RoomEditor.State.globalSnapPreview = null;
        updateGlobalLinkControls();
        redraw();
        setStatus(`Linked ${selected.roomId} edge ${selected.edgeIndex + 1} to ${targetRoomId} edge ${targetEdgeIndex + 1}.`);
      }

      function clearSelectedGlobalEdgeLink() {
        const selected = RoomEditor.State.selectedGlobalEdge;
        if (!selected) return;
        const existingLink = getEdgeLink(selected.roomId, selected.edgeIndex);
        if (!existingLink) return;
        clearRoomEdgeLink(selected.roomId, selected.edgeIndex, true);
        RoomEditor.State.globalSnapPreview = null;
        updateGlobalLinkControls();
        redraw();
        setStatus(`Cleared link for ${selected.roomId} edge ${selected.edgeIndex + 1}.`);
      }

      function getSpecificEdgeSnapCandidate(roomId, edgeIndex) {
        const room = getRoomById(roomId);
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

      function snapSelectedGlobalEdge() {
        const selected = RoomEditor.State.selectedGlobalEdge;
        if (!selected) return;
        const room = getRoomById(selected.roomId);
        const candidate = getSpecificEdgeSnapCandidate(selected.roomId, selected.edgeIndex);
        if (!room || !candidate) {
          setStatus('No snap target available for the selected edge.');
          return;
        }
        if (!applyRoomSnapCandidate(room, candidate)) {
          setStatus('Snap could not move this room group without pulling the target side with it.');
          return;
        }
        RoomEditor.State.globalSnapPreview = candidate;
        redraw();
        setStatus(`Snapped ${selected.roomId} edge ${selected.edgeIndex + 1} to ${candidate.targetRoomId} edge ${candidate.targetEdgeIndex + 1}.`);
      }

      function resolveSelected() {
        const room = currentRoom();
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
        globalCtx.save();
        globalCtx.strokeStyle = strokeStyle;
        globalCtx.lineWidth = lineWidth;
        globalCtx.setLineDash(dash);
        globalCtx.beginPath();
        globalCtx.moveTo(edgeCanvas.start.x, edgeCanvas.start.y);
        globalCtx.lineTo(edgeCanvas.end.x, edgeCanvas.end.y);
        globalCtx.stroke();
        globalCtx.setLineDash([]);
        if (endpointFill) {
          [edgeCanvas.start, edgeCanvas.end].forEach((point) => {
            globalCtx.beginPath();
            globalCtx.arc(point.x, point.y, 5, 0, Math.PI * 2);
            globalCtx.fillStyle = endpointFill;
            globalCtx.fill();
          });
        }
        globalCtx.restore();
      }

      function drawRoomEdge(edgeCanvas, options = {}) {
        if (!edgeCanvas) return;
        const {
          strokeStyle = '#4ff5be',
          lineWidth = 5,
          dash = [],
          endpointFill = null
        } = options;
        roomCtx.save();
        roomCtx.strokeStyle = strokeStyle;
        roomCtx.lineWidth = lineWidth;
        roomCtx.setLineDash(dash);
        roomCtx.beginPath();
        roomCtx.moveTo(edgeCanvas.start.x, edgeCanvas.start.y);
        roomCtx.lineTo(edgeCanvas.end.x, edgeCanvas.end.y);
        roomCtx.stroke();
        roomCtx.setLineDash([]);
        if (endpointFill) {
          [edgeCanvas.start, edgeCanvas.end].forEach((point) => {
            roomCtx.beginPath();
            roomCtx.arc(point.x, point.y, 5, 0, Math.PI * 2);
            roomCtx.fillStyle = endpointFill;
            roomCtx.fill();
          });
        }
        roomCtx.restore();
      }

      function getRoomLocalEdgeCanvasPoints(room, edgeIndex) {
        const edge = getRoomEdge(room, edgeIndex);
        if (!edge) return null;
        return {
          start: roomToCanvasPoint(edge.start.x, edge.start.y),
          end: roomToCanvasPoint(edge.end.x, edge.end.y)
        };
      }

      function drawRoomView() {
        const room = currentRoom();
        const projection = roomScale();
        const scale = projection;
        const { viewport } = projection;
        roomCtx.clearRect(0, 0, roomCanvas.width, roomCanvas.height);
        roomCtx.fillStyle = '#071018';
        roomCtx.fillRect(0, 0, roomCanvas.width, roomCanvas.height);
        roomCtx.fillStyle = 'rgba(9, 26, 38, 0.92)';
        roomCtx.fillRect(
          viewport.x,
          viewport.y,
          viewport.width,
          viewport.height
        );
        roomCtx.strokeStyle = 'rgba(127, 178, 223, 0.35)';
        roomCtx.strokeRect(
          viewport.x + 0.5,
          viewport.y + 0.5,
          viewport.width - 1,
          viewport.height - 1
        );

        roomCtx.save();
        roomCtx.beginPath();
        roomCtx.rect(viewport.x, viewport.y, viewport.width, viewport.height);
        roomCtx.clip();
        drawRoomGrid(projection, 'rgba(72, 99, 124, 0.22)');

        roomCtx.save();
        roomCtx.beginPath();
        room.polygon.forEach(([x, y], index) => {
          const pt = roomToCanvasPoint(x, y);
          if (index === 0) roomCtx.moveTo(pt.x, pt.y);
          else roomCtx.lineTo(pt.x, pt.y);
        });
        roomCtx.closePath();
        roomCtx.fillStyle = 'rgba(27, 57, 80, 0.65)';
        roomCtx.strokeStyle = selectionContains({ kind: 'room-shell' }) ? '#ffd166' : '#9bd1ff';
        roomCtx.lineWidth = selectionContains({ kind: 'room-shell' }) ? 4 : 2;
        roomCtx.fill();
        roomCtx.stroke();
        roomCtx.restore();

        for (let edgeIndex = 0; edgeIndex < getEdgeCount(room); edgeIndex += 1) {
          const edgeCanvas = getRoomLocalEdgeCanvasPoints(room, edgeIndex);
          const isRemoved = isRoomEdgeRemoved(room, edgeIndex);
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

          const guide = getRoomLinkedEdgeGuide(room.id, link.edgeIndex);
          if (!guide) return;
          drawRoomEdge(guide.guideCanvas, {
            strokeStyle: isSelectedEdge ? '#ffd166' : '#3ee6b8',
            lineWidth: isSelectedEdge ? 5 : 4,
            dash: [10, 6],
            endpointFill: isSelectedEdge ? '#ffd166' : '#3ee6b8'
          });
        });

        if (room.playerStart) {
          const p = roomToCanvasPoint(room.playerStart.x, room.playerStart.y);
          const selected = selectionContains({ kind: 'start' });
          roomCtx.save();
          roomCtx.strokeStyle = selected ? '#ffe27a' : '#8ff7d5';
          roomCtx.fillStyle = selected ? 'rgba(255, 226, 122, 0.16)' : 'rgba(143, 247, 213, 0.16)';
          roomCtx.lineWidth = selected ? 3 : 2;
          roomCtx.beginPath();
          roomCtx.arc(p.x, p.y, 14, 0, Math.PI * 2);
          roomCtx.fill();
          roomCtx.stroke();
          roomCtx.beginPath();
          roomCtx.moveTo(p.x - 10, p.y);
          roomCtx.lineTo(p.x + 10, p.y);
          roomCtx.moveTo(p.x, p.y - 10);
          roomCtx.lineTo(p.x, p.y + 10);
          roomCtx.stroke();
          roomCtx.fillStyle = '#dffff5';
          roomCtx.font = '11px sans-serif';
          roomCtx.fillText('START', p.x + 18, p.y - 8);
          roomCtx.restore();
        }

        room.platforms.forEach((platform) => {
          const p = roomToCanvasPoint(platform.x, platform.y - PLATFORM_H / 2);
          const width = platform.len * TILE * scale.x;
          const height = PLATFORM_H * scale.y;
          const selected = selectionContains({ kind: 'platform', id: platform.id });
          const justPlaced = platform.id === RoomEditor.State.lastPlacedId;
          roomCtx.fillStyle = selected ? '#ffd166' : justPlaced ? '#a8d8ff' : '#6eaef6';
          roomCtx.fillRect(p.x, p.y, width, height);
          roomCtx.strokeStyle = '#102334';
          roomCtx.strokeRect(p.x, p.y, width, height);
        });

        room.movingPlatforms.forEach((mover) => {
          const start = roomToCanvasPoint(mover.x, mover.y - PLATFORM_H / 2);
          const end = roomToCanvasPoint(mover.endX, mover.endY - PLATFORM_H / 2);
          const width = mover.len * TILE * scale.x;
          const height = PLATFORM_H * scale.y;
          const selected = selectionContains({ kind: 'mover', id: mover.id });
          const startSelected = selectionContains({ kind: 'mover-start', id: mover.id });
          const endSelected = selectionContains({ kind: 'mover-end', id: mover.id });
          roomCtx.save();
          roomCtx.strokeStyle = selected ? '#ffde7a' : '#8fd0ff';
          roomCtx.lineWidth = selected ? 3 : 2;
          roomCtx.setLineDash([8, 6]);
          roomCtx.beginPath();
          roomCtx.moveTo(start.x + (width / 2), start.y + (height / 2));
          roomCtx.lineTo(end.x + (width / 2), end.y + (height / 2));
          roomCtx.stroke();
          roomCtx.setLineDash([]);
          roomCtx.fillStyle = selected ? '#ffd166' : '#64c6ff';
          roomCtx.fillRect(start.x, start.y, width, height);
          roomCtx.strokeStyle = '#102334';
          roomCtx.strokeRect(start.x, start.y, width, height);
          roomCtx.strokeStyle = 'rgba(255,255,255,0.55)';
          roomCtx.strokeRect(end.x, end.y, width, height);
          roomCtx.fillStyle = startSelected ? '#ffe27a' : '#dff5ff';
          roomCtx.beginPath();
          roomCtx.arc(start.x + (width / 2), start.y + (height / 2), 7, 0, Math.PI * 2);
          roomCtx.fill();
          roomCtx.strokeStyle = '#102334';
          roomCtx.stroke();
          roomCtx.fillStyle = endSelected ? '#ffe27a' : 'rgba(223,245,255,0.7)';
          roomCtx.beginPath();
          roomCtx.arc(end.x + (width / 2), end.y + (height / 2), 7, 0, Math.PI * 2);
          roomCtx.fill();
          roomCtx.strokeStyle = '#102334';
          roomCtx.stroke();
          roomCtx.fillStyle = '#dff5ff';
          roomCtx.font = '11px sans-serif';
          roomCtx.fillText(mover.id, start.x + 4, start.y - 8);
          roomCtx.restore();
        });

        room.doors.forEach((door) => {
          const p = roomToCanvasPoint(door.x, door.y);
          const selected = selectionContains({ kind: 'door', id: door.id });
          const justPlaced = door.id === RoomEditor.State.lastPlacedId;
          roomCtx.fillStyle = selected ? '#ffe0b3' : justPlaced ? '#ffc59f' : '#f5986e';
          roomCtx.fillRect(p.x - 10, p.y - 24, 20, 48);
          roomCtx.strokeStyle = '#3e2315';
          roomCtx.strokeRect(p.x - 10, p.y - 24, 20, 48);
          roomCtx.fillStyle = '#ffe8d1';
          roomCtx.font = '11px sans-serif';
          roomCtx.fillText(door.id, p.x + 14, p.y - 10);
        });

        room.keys.forEach((key) => {
          const p = roomToCanvasPoint(key.x, key.y);
          const selected = selectionContains({ kind: 'key', id: key.id });
          roomCtx.save();
          roomCtx.fillStyle = selected ? '#fff09f' : '#e8d26e';
          roomCtx.strokeStyle = '#4f3f00';
          roomCtx.lineWidth = 2;
          roomCtx.beginPath();
          roomCtx.arc(p.x, p.y, 10, 0, Math.PI * 2);
          roomCtx.fill();
          roomCtx.stroke();
          roomCtx.fillRect(p.x + 8, p.y - 2, 18, 4);
          roomCtx.strokeRect(p.x + 8, p.y - 2, 18, 4);
          roomCtx.beginPath();
          roomCtx.arc(p.x + 30, p.y, 4, 0, Math.PI * 2);
          roomCtx.stroke();
          roomCtx.fillStyle = '#fff5bf';
          roomCtx.font = '11px sans-serif';
          roomCtx.fillText(key.id, p.x + 14, p.y - 12);
          roomCtx.restore();
        });

        room.abilities.forEach((ability) => {
          const p = roomToCanvasPoint(ability.x, ability.y);
          const selected = selectionContains({ kind: 'ability', id: ability.id });
          roomCtx.save();
          roomCtx.translate(p.x, p.y);
          roomCtx.rotate(Math.PI / 4);
          roomCtx.fillStyle = selected ? '#9ae5ff' : '#52c7ff';
          roomCtx.strokeStyle = '#0b3750';
          roomCtx.lineWidth = 2;
          roomCtx.fillRect(-10, -10, 20, 20);
          roomCtx.strokeRect(-10, -10, 20, 20);
          roomCtx.restore();
          roomCtx.fillStyle = '#dff6ff';
          roomCtx.font = '11px sans-serif';
          roomCtx.fillText(ability.id, p.x + 14, p.y - 12);
          roomCtx.fillText(getAbilityLabel(ability.type), p.x + 14, p.y + 4);
        });

        room.polygon.forEach(([x, y], index) => {
          const p = roomToCanvasPoint(x, y);
          const selected = selectionContains({ kind: 'vertex', index });
          roomCtx.beginPath();
          roomCtx.arc(p.x, p.y, selected ? 7 : 5, 0, Math.PI * 2);
          roomCtx.fillStyle = selected ? '#fff1b0' : '#ff6b8a';
          roomCtx.fill();
          roomCtx.strokeStyle = '#1a0e13';
          roomCtx.stroke();
        });

        if (RoomEditor.State.drag && RoomEditor.State.drag.type === 'marquee') {
          const rect = normalizeRect(RoomEditor.State.drag.startCanvas, RoomEditor.State.drag.currentCanvas);
          roomCtx.strokeStyle = '#ffd166';
          roomCtx.setLineDash([6, 4]);
          roomCtx.strokeRect(rect.x1, rect.y1, rect.x2 - rect.x1, rect.y2 - rect.y1);
          roomCtx.fillStyle = 'rgba(255, 209, 102, 0.12)';
          roomCtx.fillRect(rect.x1, rect.y1, rect.x2 - rect.x1, rect.y2 - rect.y1);
          roomCtx.setLineDash([]);
        }

        if (RoomEditor.State.tool === 'mover' && RoomEditor.State.pendingMoverStart) {
          const preview = RoomEditor.State.hoverLocal || RoomEditor.State.pendingMoverStart;
          const start = roomToCanvasPoint(RoomEditor.State.pendingMoverStart.x, RoomEditor.State.pendingMoverStart.y - PLATFORM_H / 2);
          const end = roomToCanvasPoint(preview.x, preview.y - PLATFORM_H / 2);
          roomCtx.save();
          roomCtx.strokeStyle = '#ffd166';
          roomCtx.lineWidth = 2;
          roomCtx.setLineDash([8, 6]);
          roomCtx.beginPath();
          roomCtx.moveTo(start.x, start.y);
          roomCtx.lineTo(end.x, end.y);
          roomCtx.stroke();
          roomCtx.setLineDash([]);
          roomCtx.beginPath();
          roomCtx.arc(start.x, start.y, 6, 0, Math.PI * 2);
          roomCtx.fillStyle = '#ffd166';
          roomCtx.fill();
          roomCtx.restore();
        }
        roomCtx.restore();
      }

      function drawGlobalView() {
        globalCtx.clearRect(0, 0, globalCanvas.width, globalCanvas.height);
        const globalProjection = globalScale();
        drawGrid(globalCtx, globalCanvas.width, globalCanvas.height, Math.max(24, 48 * globalProjection.scale), 'rgba(72, 99, 124, 0.15)');
        globalCtx.fillStyle = '#071018';
        globalCtx.fillRect(0, 0, globalCanvas.width, globalCanvas.height);

        RoomEditor.State.data.rooms.forEach((room) => {
          const points = getGlobalRoomPoints(room).map((point) => [point.x, point.y]);
          const center = globalToCanvasPoint(room.global.x, room.global.y);
          globalCtx.beginPath();
          points.forEach(([x, y], index) => {
            if (index === 0) globalCtx.moveTo(x, y);
            else globalCtx.lineTo(x, y);
          });
          globalCtx.closePath();
          globalCtx.fillStyle = room.id === RoomEditor.State.currentRoomId ? 'rgba(70, 126, 173, 0.65)' : 'rgba(24, 48, 70, 0.75)';
          globalCtx.strokeStyle = room.id === RoomEditor.State.currentRoomId ? '#ffd166' : '#7fb2df';
          globalCtx.lineWidth = room.id === RoomEditor.State.currentRoomId ? 2.5 : 1.5;
          globalCtx.fill();
          globalCtx.stroke();

          globalCtx.fillStyle = '#f0f7ff';
          globalCtx.font = '12px sans-serif';
          globalCtx.fillText(room.id, center.x - 10, center.y + 4);
        });

        RoomEditor.State.data.rooms.forEach((room) => {
          ensureRoomShape(room);
          room.edgeLinks.forEach((link) => {
            const edgeCanvas = getEdgeCanvasPoints(room, link.edgeIndex);
            drawGlobalEdge(edgeCanvas, {
              strokeStyle: '#3ee6b8',
              lineWidth: 4
            });
          });
        });

        if (RoomEditor.State.selectedGlobalEdge) {
          const room = getRoomById(RoomEditor.State.selectedGlobalEdge.roomId);
          const selectedEdge = room ? getEdgeCanvasPoints(room, RoomEditor.State.selectedGlobalEdge.edgeIndex) : null;
          drawGlobalEdge(selectedEdge, {
            strokeStyle: '#ffd166',
            lineWidth: 5,
            endpointFill: '#ffd166'
          });

          const linkedGuide = getLinkedEdgeGuide(RoomEditor.State.selectedGlobalEdge.roomId, RoomEditor.State.selectedGlobalEdge.edgeIndex);
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
            const draggingRoom = getRoomById(dragRoomId);
            if (!draggingRoom) return;
            draggingRoom.edgeLinks.forEach((link) => {
              if (groupRoomIds.has(link.targetRoomId)) return;
              const targetRoom = getRoomById(link.targetRoomId);
              if (!targetRoom) return;
              const targetEdge = getEdgeCanvasPoints(targetRoom, link.targetEdgeIndex);
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
          const sourceRoom = getRoomById(RoomEditor.State.globalSnapPreview.roomId);
          const targetRoom = getRoomById(RoomEditor.State.globalSnapPreview.targetRoomId);
          const sourceEdge = sourceRoom ? getEdgeCanvasPoints(sourceRoom, RoomEditor.State.globalSnapPreview.edgeIndex) : null;
          const targetEdge = targetRoom ? getEdgeCanvasPoints(targetRoom, RoomEditor.State.globalSnapPreview.targetEdgeIndex) : null;
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
        const room = currentRoom();
        updateEmptyStates();
        if (!room) {
          setViewMode(RoomEditor.State.viewMode);
          syncPropertyInputs();
          updateViewControlReadouts();
          RoomEditor.Ui.refs.toggleSelectedEdge.disabled = true;
          RoomEditor.Ui.refs.roomCanvasBox.classList.add('hidden');
          RoomEditor.Ui.refs.globalCanvasBox.classList.toggle('hidden', RoomEditor.State.viewMode !== 'global');
          RoomEditor.Ui.refs.globalLinkPanel.classList.toggle('hidden', RoomEditor.State.viewMode !== 'global');
          document.getElementById('canvasToolButtons').classList.add('hidden');
          RoomEditor.Ui.refs.selectionInspector.classList.add('hidden');
          updateGlobalLinkControls();
          roomCtx.clearRect(0, 0, roomCanvas.width, roomCanvas.height);
          roomCtx.fillStyle = '#071018';
          roomCtx.fillRect(0, 0, roomCanvas.width, roomCanvas.height);
          drawGlobalView();
          updateJsonText();
          syncWorkflowRailVisibility();
          syncRoomWizardDock();
          updateWorkflowRailPills();
          if (RoomEditor.State.roomWizard.active && RoomEditor.State.roomWizard.phase === 'layout') {
            updateRoomWizardTerrainControls();
            refreshTerrainWarnings();
          }
          return;
        }
        setViewMode(RoomEditor.State.viewMode);
        updateCounts(room);
        renderInventory(room);
        syncPropertyInputs();
        updateViewControlReadouts();
        const showRoomCanvas =
          RoomEditor.State.viewMode === 'room' &&
          !(RoomEditor.State.roomWizard.active && RoomEditor.State.roomWizard.phase === 'environment');
        RoomEditor.Ui.refs.toggleSelectedEdge.disabled = !(RoomEditor.State.viewMode === 'room' && RoomEditor.State.selectionItems.length === 1 && RoomEditor.State.selected?.kind === 'room-edge');
        RoomEditor.Ui.refs.roomCanvasBox.classList.toggle('hidden', !showRoomCanvas);
        RoomEditor.Ui.refs.globalCanvasBox.classList.toggle('hidden', RoomEditor.State.viewMode !== 'global');
        RoomEditor.Ui.refs.globalLinkPanel.classList.toggle('hidden', RoomEditor.State.viewMode !== 'global');
        document.getElementById('canvasToolButtons').classList.toggle('hidden', !showRoomCanvas);
        const optionBRoomStageChrome =
          RoomEditor.State.roomWizard.active &&
          RoomEditor.State.workflowScope === 'room' &&
          (RoomEditor.State.roomWizard.phase === 'identity' || RoomEditor.State.roomWizard.phase === 'layout');
        document
          .getElementById('roomViewControls')
          ?.classList.toggle('hidden', !showRoomCanvas || optionBRoomStageChrome);
        if (!showRoomCanvas) RoomEditor.Ui.refs.selectionInspector.classList.add('hidden');
        updateGlobalLinkControls();
        if (showRoomCanvas) {
          drawRoomView();
          renderEmptyRoomHint();
        }
        drawGlobalView();
        updateJsonText();
        syncWorkflowRailVisibility();
        syncRoomWizardDock();
        updateWorkflowRailPills();
        if (RoomEditor.State.roomWizard.active && RoomEditor.State.roomWizard.phase === 'layout') {
          updateRoomWizardTerrainControls();
          refreshTerrainWarnings();
        }
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

      function buildSelectionFromRect(startLocal, endLocal) {
        const room = currentRoom();
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
            y1: platform.y - PLATFORM_H,
            x2: platform.x + (platform.len * TILE),
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
          const y1 = Math.min(mover.y, mover.endY) - PLATFORM_H;
          const x2 = Math.max(mover.x + (mover.len * TILE), mover.endX + (mover.len * TILE));
          const y2 = Math.max(mover.y, mover.endY);
          if (rectIntersectsRect(rect, { x1, y1, x2, y2 })) items.push({ kind: 'mover', id: mover.id });
        });

        const roomBounds = getRoomBounds();
        const coversRoom = rect.x1 <= roomBounds.x1 && rect.y1 <= roomBounds.y1 &&
          rect.x2 >= roomBounds.x2 && rect.y2 >= roomBounds.y2;
        if (coversRoom) return [{ kind: 'room-shell' }];

        return items;
      }

      function snapshotSelectionItems() {
        const room = currentRoom();
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
        const room = currentRoom();
        snapshot.forEach((item) => {
          if (item.kind === 'vertex') {
            room.polygon[item.index] = [snap(item.x + dx), snap(item.y + dy)];
          }
          if (item.kind === 'platform') {
            const platform = room.platforms.find((entry) => entry.id === item.id);
            if (platform) {
              platform.x = snap(item.x + dx);
              platform.y = snap(item.y + dy);
            }
          }
          if (item.kind === 'door') {
            const door = room.doors.find((entry) => entry.id === item.id);
            if (door) {
              door.x = snap(item.x + dx);
              door.y = snap(item.y + dy);
            }
          }
          if (item.kind === 'key') {
            const key = room.keys.find((entry) => entry.id === item.id);
            if (key) {
              key.x = snap(item.x + dx);
              key.y = snap(item.y + dy);
            }
          }
          if (item.kind === 'ability') {
            const ability = room.abilities.find((entry) => entry.id === item.id);
            if (ability) {
              ability.x = snap(item.x + dx);
              ability.y = snap(item.y + dy);
            }
          }
          if (item.kind === 'mover') {
            const mover = room.movingPlatforms.find((entry) => entry.id === item.id);
            if (mover) {
              mover.x = snap(item.x + dx);
              mover.y = snap(item.y + dy);
              mover.endX = snap(item.endX + dx);
              mover.endY = snap(item.endY + dy);
            }
          }
          if (item.kind === 'start' && room.playerStart) {
            room.playerStart.x = snap(item.x + dx);
            room.playerStart.y = snap(item.y + dy);
          }
          if (item.kind === 'room-shell') {
            room.polygon = item.polygon.map(([x, y]) => [snap(x + dx), snap(y + dy)]);
            item.platforms.forEach((platformState) => {
              const platform = room.platforms.find((entry) => entry.id === platformState.id);
              if (platform) {
                platform.x = snap(platformState.x + dx);
                platform.y = snap(platformState.y + dy);
              }
            });
            item.doors.forEach((doorState) => {
              const door = room.doors.find((entry) => entry.id === doorState.id);
              if (door) {
                door.x = snap(doorState.x + dx);
                door.y = snap(doorState.y + dy);
              }
            });
            item.keys.forEach((keyState) => {
              const key = room.keys.find((entry) => entry.id === keyState.id);
              if (key) {
                key.x = snap(keyState.x + dx);
                key.y = snap(keyState.y + dy);
              }
            });
            item.abilities.forEach((abilityState) => {
              const ability = room.abilities.find((entry) => entry.id === abilityState.id);
              if (ability) {
                ability.x = snap(abilityState.x + dx);
                ability.y = snap(abilityState.y + dy);
              }
            });
            item.movingPlatforms.forEach((moverState) => {
              const mover = room.movingPlatforms.find((entry) => entry.id === moverState.id);
              if (mover) {
                mover.x = snap(moverState.x + dx);
                mover.y = snap(moverState.y + dy);
                mover.endX = snap(moverState.endX + dx);
                mover.endY = snap(moverState.endY + dy);
              }
            });
            if (item.playerStart && room.playerStart) {
              room.playerStart.x = snap(item.playerStart.x + dx);
              room.playerStart.y = snap(item.playerStart.y + dy);
            }
          }
        });
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

      function hitTestRoomEditor(mouse) {
        const room = currentRoom();
        if (room.playerStart) {
          const p = roomToCanvasPoint(room.playerStart.x, room.playerStart.y);
          if (pointDistance(mouse, p) < 20) {
            return { kind: 'start' };
          }
        }
        for (let i = 0; i < room.polygon.length; i += 1) {
          const p = roomToCanvasPoint(room.polygon[i][0], room.polygon[i][1]);
          if (pointDistance(mouse, p) < HIT_VERTEX) {
            return { kind: 'vertex', index: i };
          }
        }
        for (const door of room.doors) {
          const p = roomToCanvasPoint(door.x, door.y);
          if (mouse.x >= p.x - HIT_DOOR_X && mouse.x <= p.x + HIT_DOOR_X && mouse.y >= p.y - HIT_DOOR_Y && mouse.y <= p.y + HIT_DOOR_Y) {
            return { kind: 'door', id: door.id };
          }
        }
        for (const key of room.keys) {
          const p = roomToCanvasPoint(key.x, key.y);
          if (mouse.x >= p.x - 18 && mouse.x <= p.x + 34 && mouse.y >= p.y - 18 && mouse.y <= p.y + 18) {
            return { kind: 'key', id: key.id };
          }
        }
        for (const ability of room.abilities) {
          const p = roomToCanvasPoint(ability.x, ability.y);
          if (mouse.x >= p.x - 18 && mouse.x <= p.x + 18 && mouse.y >= p.y - 18 && mouse.y <= p.y + 18) {
            return { kind: 'ability', id: ability.id };
          }
        }
        for (const mover of room.movingPlatforms) {
          const start = roomToCanvasPoint(mover.x, mover.y - PLATFORM_H / 2);
          const end = roomToCanvasPoint(mover.endX, mover.endY - PLATFORM_H / 2);
          const width = mover.len * TILE * roomScale().x;
          const height = PLATFORM_H * roomScale().y;
          const startHandle = { x: start.x + (width / 2), y: start.y + (height / 2) };
          const endHandle = { x: end.x + (width / 2), y: end.y + (height / 2) };
          if (pointDistance(mouse, startHandle) < 14) {
            return { kind: 'mover-start', id: mover.id };
          }
          if (pointDistance(mouse, endHandle) < 14) {
            return { kind: 'mover-end', id: mover.id };
          }
          const bounds = {
            x1: Math.min(start.x, end.x) - HIT_PLATFORM_PAD,
            y1: Math.min(start.y, end.y) - HIT_PLATFORM_PAD,
            x2: Math.max(start.x + width, end.x + width) + HIT_PLATFORM_PAD,
            y2: Math.max(start.y + height, end.y + height) + HIT_PLATFORM_PAD
          };
          if (mouse.x >= bounds.x1 && mouse.x <= bounds.x2 && mouse.y >= bounds.y1 && mouse.y <= bounds.y2) {
            return { kind: 'mover', id: mover.id };
          }
        }
        for (const platform of room.platforms) {
          const p = roomToCanvasPoint(platform.x, platform.y - PLATFORM_H / 2);
          const width = platform.len * TILE * roomScale().x;
          const height = PLATFORM_H * roomScale().y;
          if (mouse.x >= p.x - HIT_PLATFORM_PAD && mouse.x <= p.x + width + HIT_PLATFORM_PAD && mouse.y >= p.y - HIT_PLATFORM_PAD && mouse.y <= p.y + height + HIT_PLATFORM_PAD) {
            return { kind: 'platform', id: platform.id };
          }
        }
        for (let edgeIndex = 0; edgeIndex < getEdgeCount(room); edgeIndex += 1) {
          const edgeCanvas = getRoomLocalEdgeCanvasPoints(room, edgeIndex);
          if (!edgeCanvas) continue;
          const result = distanceToSegment(mouse, edgeCanvas.start, edgeCanvas.end);
          if (result.distance <= HIT_ROOM_EDGE_PAD) {
            return { kind: 'room-edge', edgeIndex };
          }
        }
        return null;
      }

      function hitTestGlobal(mouse) {
        const reversed = [...RoomEditor.State.data.rooms].reverse();
        let nearest = null;

        for (const room of reversed) {
          const polygon = getGlobalRoomPoints(room);
          let nearestEdge = null;
          for (let edgeIndex = 0; edgeIndex < polygon.length; edgeIndex += 1) {
            const a = polygon[edgeIndex];
            const b = polygon[(edgeIndex + 1) % polygon.length];
            const distance = distanceToCanvasSegment(mouse, a, b);
            if (!nearestEdge || distance < nearestEdge.distance) {
              nearestEdge = { kind: 'edge', roomId: room.id, edgeIndex, distance };
            }
          }
          if (nearestEdge && nearestEdge.distance <= HIT_GLOBAL_PAD) {
            return nearestEdge;
          }

          if (pointInCanvasPolygon(mouse, polygon)) {
            return { kind: 'room', roomId: room.id };
          }

          const distance = distanceToCanvasPolygon(mouse, polygon);
          if (!nearest || distance < nearest.distance) {
            nearest = { kind: 'room', roomId: room.id, distance };
          }
        }

        if (nearest && nearest.distance <= HIT_GLOBAL_PAD) {
          return nearest;
        }

        return null;
      }

      function addVertexAt(mouse) {
        const room = currentRoom();
        if (RoomEditor.State.selectedGlobalEdge?.roomId === room.id) {
          RoomEditor.State.selectedGlobalEdge = null;
          RoomEditor.State.globalSnapPreview = null;
        }
        const oldEdgeCount = getEdgeCount(room);
        const local = canvasToRoomPoint(mouse.x, mouse.y);
        let best = { index: 0, distance: Infinity };
        for (let i = 0; i < room.polygon.length; i += 1) {
          const a = { x: room.polygon[i][0], y: room.polygon[i][1] };
          const b = { x: room.polygon[(i + 1) % room.polygon.length][0], y: room.polygon[(i + 1) % room.polygon.length][1] };
          const result = distanceToSegment(local, a, b);
          if (result.distance < best.distance) {
            best = { index: i + 1, distance: result.distance, point: result.point };
          }
        }
        room.polygon.splice(best.index, 0, [snap(best.point.x), snap(best.point.y)]);
        const splitEdgeIndex = ((best.index - 1) % oldEdgeCount + oldEdgeCount) % oldEdgeCount;
        remapRoomEdgeLinks(room.id, (edgeIndex) => {
          if (edgeIndex === splitEdgeIndex) return null;
          return edgeIndex >= best.index ? edgeIndex + 1 : edgeIndex;
        });
        remapRoomRemovedEdges(room.id, (edgeIndex) => {
          if (edgeIndex === splitEdgeIndex) {
            const firstEdgeIndex = edgeIndex >= best.index ? edgeIndex + 1 : edgeIndex;
            return [firstEdgeIndex, best.index];
          }
          return edgeIndex >= best.index ? edgeIndex + 1 : edgeIndex;
        });
        setSelection([{ kind: 'vertex', index: best.index }]);
        setDirty(true);
        syncRoomWizardEdgeSelects();
      }

      function addPlatformAt(mouse) {
        const room = currentRoom();
        const local = canvasToRoomPoint(mouse.x, mouse.y);
        const platform = {
          id: nextId(`${room.id}-P`, room.platforms),
          x: local.x,
          y: local.y,
          len: 4,
          tint: 0
        };
        room.platforms.push(platform);
        // Task 2.5a: glow pulse on placement
        RoomEditor.State.lastPlacedId = platform.id;
        setTimeout(() => { RoomEditor.State.lastPlacedId = null; redraw(); }, 600);
        setSelection([{ kind: 'platform', id: platform.id }]);
        setDirty(true);
      }

      function addDoorAt(mouse) {
        const room = currentRoom();
        const local = canvasToRoomPoint(mouse.x, mouse.y);
        const door = {
          id: nextId(`${room.id}-D`, room.doors),
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
        setTimeout(() => { RoomEditor.State.lastPlacedId = null; redraw(); }, 600);
        setSelection([{ kind: 'door', id: door.id }]);
        setDirty(true);
        setStatus(`Added door ${door.id} at ${door.x}, ${door.y}`);
      }

      function addKeyAt(mouse) {
        const room = currentRoom();
        const local = canvasToRoomPoint(mouse.x, mouse.y);
        const key = {
          id: nextId(`${room.id}-K`, room.keys),
          x: local.x,
          y: local.y,
          label: 'New Key',
          unlocksTarget: ''
        };
        room.keys.push(key);
        RoomEditor.State.lastPlacedId = key.id;
        setTimeout(() => { RoomEditor.State.lastPlacedId = null; redraw(); }, 600);
        setSelection([{ kind: 'key', id: key.id }]);
        setDirty(true);
        setStatus(`Added key ${key.id} at ${key.x}, ${key.y}.`);
      }

      function addAbilityAt(mouse) {
        const room = currentRoom();
        const local = canvasToRoomPoint(mouse.x, mouse.y);
        const ability = {
          id: nextId(`${room.id}-A`, room.abilities),
          x: local.x,
          y: local.y,
          type: RoomEditor.Ui.refs.abilityType.value || ABILITY_DEFS[0].id
        };
        room.abilities.push(ability);
        RoomEditor.State.lastPlacedId = ability.id;
        setTimeout(() => { RoomEditor.State.lastPlacedId = null; redraw(); }, 600);
        setSelection([{ kind: 'ability', id: ability.id }]);
        setDirty(true);
        setStatus(`Added ${getAbilityLabel(ability.type)} ${ability.id} at ${ability.x}, ${ability.y}.`);
      }

      function addMoverPoint(mouse) {
        const room = currentRoom();
        const local = canvasToRoomPoint(mouse.x, mouse.y);
        if (!RoomEditor.State.pendingMoverStart) {
          RoomEditor.State.pendingMoverStart = local;
          RoomEditor.State.hoverLocal = local;
          setStatus(`Mover start set at ${local.x}, ${local.y}. Tap end point.`);
          redraw();
          return;
        }

        const start = RoomEditor.State.pendingMoverStart;
        const rawDx = local.x - start.x;
        const rawDy = local.y - start.y;
        const horizontal = Math.abs(rawDx) >= Math.abs(rawDy);
        const mover = {
          id: nextId(`${room.id}-M`, room.movingPlatforms),
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
        setTimeout(() => { RoomEditor.State.lastPlacedId = null; redraw(); }, 600);
        setSelection([{ kind: 'mover', id: mover.id }]);
        setDirty(true);
        setStatus(`Added mover ${mover.id} from ${mover.x},${mover.y} to ${mover.endX},${mover.endY}.`);
      }

      function setPlayerStartAt(mouse) {
        const room = currentRoom();
        const local = canvasToRoomPoint(mouse.x, mouse.y);
        room.playerStart = { x: local.x, y: local.y };
        setSelection([{ kind: 'start' }]);
        setDirty(true);
        setStatus(`Set player start for ${room.id} at ${room.playerStart.x}, ${room.playerStart.y}.`);
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

      function onRoomPointerDown(event) {
        if (event.cancelable) event.preventDefault();
        if (!currentRoom()) return;
        if (typeof event.pointerId === 'number' && roomCanvas.setPointerCapture) {
          roomCanvas.setPointerCapture(event.pointerId);
        }
        const mouse = getCanvasPointer(event, roomCanvas);
        const hit = hitTestRoomEditor(mouse);
        const local = canvasToRoomPoint(mouse.x, mouse.y);

        if (RoomEditor.State.tool === 'vertex') {
          addVertexAt(mouse);
          redraw();
          return;
        }
        if (RoomEditor.State.tool === 'platform') {
          addPlatformAt(mouse);
          redraw();
          return;
        }
        if (RoomEditor.State.tool === 'door') {
          addDoorAt(mouse);
          redraw();
          return;
        }
        if (RoomEditor.State.tool === 'key') {
          addKeyAt(mouse);
          redraw();
          return;
        }
        if (RoomEditor.State.tool === 'ability') {
          addAbilityAt(mouse);
          redraw();
          return;
        }
        if (RoomEditor.State.tool === 'mover') {
          addMoverPoint(mouse);
          return;
        }
        if (RoomEditor.State.tool === 'start') {
          setPlayerStartAt(mouse);
          redraw();
          return;
        }

        if (hit) {
          const alreadySelected = selectionContains(hit);
          if (!alreadySelected || RoomEditor.State.selectionItems.length <= 1) {
            setSelection([hit]);
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
          redraw();
        } else {
          setSelection([]);
          RoomEditor.State.drag = {
            type: 'marquee',
            startCanvas: mouse,
            currentCanvas: mouse,
            startLocal: local,
            currentLocal: local
          };
          redraw();
        }
      }

      function onRoomPointerMove(event) {
        if (event.cancelable) event.preventDefault();
        if (!currentRoom()) return;
        const mouse = getCanvasPointer(event, roomCanvas);
        const local = canvasToRoomPoint(mouse.x, mouse.y);
        if (!RoomEditor.State.drag) {
          if (RoomEditor.State.tool === 'mover' && RoomEditor.State.pendingMoverStart) {
            RoomEditor.State.hoverLocal = local;
            redraw();
          }
          return;
        }
        const room = currentRoom();
        RoomEditor.State.hoverLocal = local;

        if (RoomEditor.State.drag.type === 'marquee') {
          RoomEditor.State.drag.currentCanvas = mouse;
          RoomEditor.State.drag.currentLocal = local;
          redraw();
          return;
        }

        if (RoomEditor.State.drag.type === 'selection-move') {
          const dx = local.x - RoomEditor.State.drag.startLocal.x;
          const dy = local.y - RoomEditor.State.drag.startLocal.y;
          moveSelection(dx, dy, RoomEditor.State.drag.snapshot);
          redraw();
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
            snapTarget = getNearestRoomVertexLinkSnap(room, RoomEditor.State.drag.index, mouse);
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
            mover.x = snap(RoomEditor.State.drag.snapshot.x + dx);
            mover.y = snap(RoomEditor.State.drag.snapshot.y + dy);
            mover.endX = snap(RoomEditor.State.drag.snapshot.endX + dx);
            mover.endY = snap(RoomEditor.State.drag.snapshot.endY + dy);
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
        redraw();
      }

      function onGlobalPointerDown(event) {
        if (event.cancelable) event.preventDefault();
        const mouse = getCanvasPointer(event, globalCanvas);
        const hit = hitTestGlobal(mouse);
        RoomEditor.State.globalSnapPreview = null;
        if (!hit) {
          setSelectedGlobalEdge(null);
          redraw();
          return;
        }
        RoomEditor.State.currentRoomId = hit.roomId;
        RoomEditor.Ui.refs.roomSelect.value = hit.roomId;
        if (hit.kind === 'edge') {
          setSelectedGlobalEdge({ roomId: hit.roomId, edgeIndex: hit.edgeIndex });
        } else if (RoomEditor.State.selectedGlobalEdge && RoomEditor.State.selectedGlobalEdge.roomId !== hit.roomId) {
          setSelectedGlobalEdge(null);
        }
        const groupRoomIds = getLinkedRoomGroup(hit.roomId);
        RoomEditor.State.drag = {
          type: 'room',
          roomId: hit.roomId,
          groupRoomIds,
          startCanvas: mouse,
          startGlobal: canvasToGlobalPoint(mouse.x, mouse.y),
          snapshot: snapshotGlobalRoomGroup(groupRoomIds),
          pending: true
        };
        redraw();
      }

      function onGlobalPointerMove(event) {
        if (!RoomEditor.State.drag || RoomEditor.State.drag.type !== 'room') return;
        if (event.cancelable) event.preventDefault();
        const mouse = getCanvasPointer(event, globalCanvas);
        if (RoomEditor.State.drag.pending) {
          if (pointDistance(mouse, RoomEditor.State.drag.startCanvas) < GLOBAL_DRAG_START_DISTANCE) {
            return;
          }
          RoomEditor.State.drag.pending = false;
        }
        const local = canvasToGlobalPoint(mouse.x, mouse.y);
        const dx = local.x - RoomEditor.State.drag.startGlobal.x;
        const dy = local.y - RoomEditor.State.drag.startGlobal.y;
        applyGlobalRoomGroupDelta(RoomEditor.State.drag.snapshot, dx, dy);
        RoomEditor.State.globalSnapPreview = null;
        redraw();
      }

      function endDrag() {
        const hadGlobalRoomDrag = RoomEditor.State.drag && RoomEditor.State.drag.type === 'room';
        const hadMoveDrag = RoomEditor.State.drag && ['selection-move', 'vertex', 'platform', 'door', 'key', 'ability', 'mover', 'mover-start', 'mover-end', 'start'].includes(RoomEditor.State.drag.type);
        if (RoomEditor.State.drag && RoomEditor.State.drag.type === 'marquee') {
          const items = buildSelectionFromRect(RoomEditor.State.drag.startLocal, RoomEditor.State.drag.currentLocal);
          setSelection(items);
          redraw();
        }
        RoomEditor.State.globalSnapPreview = null;
        RoomEditor.State.drag = null;
        if (RoomEditor.State.tool !== 'mover') {
          RoomEditor.State.hoverLocal = null;
        }
        if (hadMoveDrag || hadGlobalRoomDrag) setDirty(true);
        if (hadGlobalRoomDrag) redraw();
      }

      function applyPropertyInputs() {
        const room = currentRoom();
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
            selected.item.type = getAbilityDef(RoomEditor.Ui.refs.abilityType.value)?.id || ABILITY_DEFS[0].id;
          }
        }
        setDirty(true);
        redraw();
      }

      function applyRoomSizeInputs() {
        const room = currentRoom();
        ensureRoomShape(room);
        room.size.width = Math.max(320, snap(Number(RoomEditor.Ui.refs.roomWidth.value || room.size.width)));
        room.size.height = Math.max(320, snap(Number(RoomEditor.Ui.refs.roomHeight.value || room.size.height)));
        RoomEditor.Ui.refs.roomWidth.value = room.size.width;
        RoomEditor.Ui.refs.roomHeight.value = room.size.height;
        setDirty(true);
        redraw();
        setStatus(`Resized ${room.id} workspace to ${room.size.width} x ${room.size.height}.`);
      }

      function toggleSelectedRoomEdge() {
        if (RoomEditor.State.viewMode !== 'room' || RoomEditor.State.selectionItems.length !== 1 || RoomEditor.State.selected?.kind !== 'room-edge') return;
        const room = currentRoom();
        const isRemoved = toggleRoomEdgeRemoved(room.id, RoomEditor.State.selected.edgeIndex);
        setDirty(true);
        redraw();
        setStatus(`${room.id} edge ${RoomEditor.State.selected.edgeIndex + 1} is now ${isRemoved ? 'open' : 'solid'}.`);
      }

      function deleteSelected() {
        const room = currentRoom();
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
          const oldEdgeCount = getEdgeCount(room);
          const removedIndexesAsc = [...vertexIndexes].sort((a, b) => a - b);
          const removedIndexes = new Set(removedIndexesAsc);
          vertexIndexes.forEach((index) => room.polygon.splice(index, 1));
          remapRoomEdgeLinks(room.id, (edgeIndex) => {
            if (removedIndexes.has(edgeIndex) || removedIndexes.has((edgeIndex + 1) % oldEdgeCount)) {
              return null;
            }
            const shift = removedIndexesAsc.filter((index) => index < edgeIndex).length;
            return edgeIndex - shift;
          });
          remapRoomRemovedEdges(room.id, (edgeIndex) => {
            if (removedIndexes.has(edgeIndex) || removedIndexes.has((edgeIndex + 1) % oldEdgeCount)) {
              return null;
            }
            const shift = removedIndexesAsc.filter((index) => index < edgeIndex).length;
            return edgeIndex - shift;
          });
          syncRoomWizardEdgeSelects();
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
        setSelection([]);
        setDirty(true);
        redraw();
      }

      function duplicatePlatform() {
        const room = currentRoom();
        const platforms = RoomEditor.State.selectionItems.filter((item) => item.kind === 'platform');
        if (platforms.length !== 1) return;
        const selected = room.platforms.find((platform) => platform.id === platforms[0].id);
        if (!selected) return;
        const step = Number(RoomEditor.Ui.refs.snapSize?.value) || TILE;
        const clone = {
          ...selected,
          id: nextId(`${room.id}-P`, room.platforms),
          x: selected.x + step,
          y: selected.y
        };
        room.platforms.push(clone);
        setSelection([{ kind: 'platform', id: clone.id }]);
        setDirty(true);
        redraw();
      }

      function selectCanvasTool(tool) {
        RoomEditor.State.tool = tool;
        if (RoomEditor.State.tool !== 'mover') {
          RoomEditor.State.pendingMoverStart = null;
          RoomEditor.State.hoverLocal = null;
        }
        RoomEditor.Ui.refs.toolButtons.forEach((button) => button.classList.toggle('active', button.dataset.tool === tool));
        redraw();
      }

      function refreshTerrainWarnings() {
        const el = document.getElementById('roomWizardTerrainWarnings');
        const mod = globalThis.RoomWizardTerrain;
        const room = getRoomWizardRoom();
        if (!el || !mod || !room) return;
        if (!mod.isLayoutCompleteForTerrain(room)) {
          el.innerHTML =
            '<p class="hint">Complete name, id, and footprint to use presets and see door/platform checks.</p>';
          return;
        }
        const lines = mod.doorPlatformOverlapWarnings(room, TILE, PLATFORM_H);
        if (lines.length === 0) {
          el.innerHTML = '<p class="hint">No door / platform band overlap warnings.</p>';
        } else {
          el.innerHTML = `<ul class="rw-terrain-warn-list">${lines
            .map((t) => `<li>${escapeHtml(t)}</li>`)
            .join('')}</ul>`;
        }
      }

      function updateRoomWizardTerrainControls() {
        const mod = globalThis.RoomWizardTerrain;
        const room = getRoomWizardRoom();
        const layoutOk = !!(room && mod && mod.isLayoutCompleteForTerrain(room));
        document.querySelectorAll('#roomWizardTerrainPresets [data-terrain-preset]').forEach((b) => {
          b.disabled = !layoutOk;
        });
        const dup = document.getElementById('roomWizardTerrainDuplicate');
        const mir = document.getElementById('roomWizardTerrainMirror');
        if (dup) dup.disabled = !layoutOk;
        if (mir) mir.disabled = !layoutOk;
      }

      const TERRAIN_PRESET_FAIL = {
        layout_incomplete: 'Finish Layout first (name, id, footprint).',
        room_too_tight: 'Room is too small for that preset.',
        bad_polygon: 'Invalid room polygon.',
        preset_outside_footprint:
          'Could not fit preset inside this room outline — try another preset or place platforms manually.',
        unknown_preset: 'Unknown preset.'
      };

      function applyTerrainPresetFromWizard(presetId) {
        const mod = globalThis.RoomWizardTerrain;
        const room = getRoomWizardRoom();
        if (!mod || !room) return;
        if (!mod.isLayoutCompleteForTerrain(room)) {
          setStatus('Complete layout (name, id, footprint) before using presets.', 'warning');
          return;
        }
        const r = mod.buildTerrainPresetPlatforms(room, presetId, {
          tile: TILE,
          platformH: PLATFORM_H,
          tintBase: room.platforms.length
        });
        if (!r.ok || !r.platforms?.length) {
          const msg =
            TERRAIN_PRESET_FAIL[r.reason] ||
            (r.reason ? `Terrain preset: ${r.reason}` : 'Terrain preset failed.');
          setStatus(msg, 'warning');
          return;
        }
        const addedIds = [];
        for (const p of r.platforms) {
          const id = nextId(`${room.id}-P`, room.platforms);
          room.platforms.push({ ...p, id });
          addedIds.push(id);
        }
        setSelection(addedIds.map((id) => ({ kind: 'platform', id })));
        RoomEditor.State.roomWizard.touched = true;
        setDirty(true);
        updateJsonText();
        setStatus(
          `Added ${r.platforms.length} platform(s) (${presetId}). Selected on canvas — switch to Room view if needed.`,
          'success'
        );
        redraw();
        refreshTerrainWarnings();
      }

      function roomWizardTerrainDuplicate() {
        const mod = globalThis.RoomWizardTerrain;
        const room = getRoomWizardRoom();
        if (!room || !mod) return;
        const fromSel = RoomEditor.State.selectionItems.find((i) => i.kind === 'platform');
        const selected = fromSel
          ? room.platforms.find((p) => p.id === fromSel.id)
          : room.platforms[room.platforms.length - 1];
        if (!selected) {
          setStatus('No platform to duplicate.', 'warning');
          return;
        }
        const step = Number(RoomEditor.Ui.refs.snapSize?.value) || TILE;
        const clone = {
          ...selected,
          id: nextId(`${room.id}-P`, room.platforms),
          x: selected.x + step,
          y: selected.y
        };
        if (!mod.platformFullyInsidePolygon(clone, room.polygon, TILE, PLATFORM_H)) {
          setStatus('Duplicate would leave the room footprint.', 'warning');
          return;
        }
        room.platforms.push(clone);
        RoomEditor.State.roomWizard.touched = true;
        setSelection([{ kind: 'platform', id: clone.id }]);
        setDirty(true);
        updateJsonText();
        redraw();
        refreshTerrainWarnings();
        setStatus(`Duplicated ${clone.id}.`, 'success');
      }

      function roomWizardTerrainMirror() {
        const mod = globalThis.RoomWizardTerrain;
        const room = getRoomWizardRoom();
        if (!room || !mod) return;
        const fromSel = RoomEditor.State.selectionItems.find((i) => i.kind === 'platform');
        const selected = fromSel
          ? room.platforms.find((p) => p.id === fromSel.id)
          : room.platforms[room.platforms.length - 1];
        if (!selected) {
          setStatus('No platform to mirror.', 'warning');
          return;
        }
        const W = Number(room.size?.width) || 800;
        const cx = W / 2;
        const lenPx = selected.len * TILE;
        const centerX = selected.x + lenPx / 2;
        const newCenterX = 2 * cx - centerX;
        let newX = newCenterX - lenPx / 2;
        newX = snap(newX);
        const clone = {
          ...selected,
          id: nextId(`${room.id}-P`, room.platforms),
          x: newX,
          y: selected.y
        };
        if (!mod.platformFullyInsidePolygon(clone, room.polygon, TILE, PLATFORM_H)) {
          setStatus('Mirror copy would leave the room footprint.', 'warning');
          return;
        }
        room.platforms.push(clone);
        RoomEditor.State.roomWizard.touched = true;
        setSelection([{ kind: 'platform', id: clone.id }]);
        setDirty(true);
        updateJsonText();
        redraw();
        refreshTerrainWarnings();
        setStatus(`Mirrored to ${clone.id}.`, 'success');
      }

      function centerRoom() {
        const room = currentRoom();
        room.global.x = 600;
        room.global.y = 360;
        redraw();
      }

      const RW_FOOTPRINT_PRESETS = {
        small: [960, 720],
        medium: [1600, 1200],
        large: [2240, 1200]
      };

      function getRoomWizardRoom() {
        if (!RoomEditor.State.data) return null;
        const id = RoomEditor.State.roomWizard.roomId || RoomEditor.State.currentRoomId;
        if (!id) return null;
        return RoomEditor.State.data.rooms.find((r) => r.id === id) || null;
      }

      function applyFootprintDimensionsToRoom(room, w, h) {
        const fn = globalThis.RoomLayoutWizardFootprint && globalThis.RoomLayoutWizardFootprint.applyAxisAlignedFootprint;
        if (typeof fn === 'function') {
          fn(room, w, h);
        } else {
          room.size = { width: Math.max(320, w), height: Math.max(320, h) };
        }
        ensureRoomShape(room);
      }

      function syncRoomWizardFootprintRadios() {
        const room = getRoomWizardRoom();
        if (!room) return;
        const W = room.size?.width;
        const H = room.size?.height;
        let matched = 'custom';
        Object.keys(RW_FOOTPRINT_PRESETS).forEach((key) => {
          const [pw, ph] = RW_FOOTPRINT_PRESETS[key];
          if (Math.abs(W - pw) < 2 && Math.abs(H - ph) < 2) matched = key;
        });
        const radios = document.querySelectorAll('input[name="roomWizardFootprint"]');
        radios.forEach((r) => {
          r.checked = r.value === matched;
        });
        const customEl = document.getElementById('roomWizardCustomFootprint');
        const showCustom = matched === 'custom';
        if (customEl) {
          customEl.hidden = !showCustom;
        }
        const cw = document.getElementById('roomWizardCustomW');
        const ch = document.getElementById('roomWizardCustomH');
        if (cw) cw.value = String(Math.round(W));
        if (ch) ch.value = String(Math.round(H));
      }

      function populateRoomWizardThemeSelect() {
        const envMod = globalThis.RoomWizardEnvironment;
        const sel = document.getElementById('roomWizardThemeSelect');
        if (!envMod || !sel || sel.options.length) return;
        envMod.THEME_PRESETS.forEach((p) => {
          const opt = document.createElement('option');
          opt.value = p.id;
          opt.textContent = p.label;
          sel.appendChild(opt);
        });
      }

      function ensureRoomWizardEnvironmentAuthoringFields(envState) {
        if (!envState || typeof envState !== 'object') return envState;
        envState.spec = envState.spec && typeof envState.spec === 'object' ? envState.spec : {};
        if (typeof envState.spec.theme_name !== 'string') envState.spec.theme_name = '';
        if (typeof envState.spec.notes !== 'string') envState.spec.notes = '';
        if (typeof envState.spec.seed !== 'string') envState.spec.seed = '';
        envState.spec.lock_stylepack = !!envState.spec.lock_stylepack;
        if (!Array.isArray(envState.spec.reference_uploads)) envState.spec.reference_uploads = [];
        envState.spec.reference_uploads = envState.spec.reference_uploads
          .filter((item) => item && typeof item === 'object')
          .map((item, index) => ({
            id: String(item.id || item.reference_id || `reference-${index + 1}`),
            label: String(item.label || item.file_name || item.name || `Reference ${index + 1}`),
            file_name: String(item.file_name || item.name || item.label || `reference-${index + 1}`),
            file_type: String(item.file_type || item.type || ''),
            file_size: Number(item.file_size || item.size || 0) || 0,
            status: String(item.status || 'uploaded'),
            pinned_to: String(item.pinned_to || ''),
            source_value: String(item.source_value || item.file_name || item.label || ''),
            uploaded_at: String(item.uploaded_at || ''),
          }));
        return envState;
      }

      function cloneRoomWizardEnvironmentAuthoringFields(envState) {
        ensureRoomWizardEnvironmentAuthoringFields(envState);
        return {
          theme_name: String(envState?.spec?.theme_name || ''),
          notes: String(envState?.spec?.notes || ''),
          seed: String(envState?.spec?.seed || ''),
          lock_stylepack: !!envState?.spec?.lock_stylepack,
          reference_uploads: (envState?.spec?.reference_uploads || []).map((item) => ({ ...item })),
        };
      }

      function applyRoomWizardEnvironmentAuthoringFields(envState, snapshot) {
        ensureRoomWizardEnvironmentAuthoringFields(envState);
        if (!snapshot || typeof snapshot !== 'object') return envState;
        envState.spec.theme_name = String(snapshot.theme_name || '');
        envState.spec.notes = String(snapshot.notes || '');
        envState.spec.seed = String(snapshot.seed || '');
        envState.spec.lock_stylepack = !!snapshot.lock_stylepack;
        envState.spec.reference_uploads = Array.isArray(snapshot.reference_uploads)
          ? snapshot.reference_uploads.map((item) => ({ ...item }))
          : [];
        return envState;
      }

      function formatRoomWizardFileSize(bytes) {
        const value = Number(bytes || 0);
        if (!value) return 'metadata only';
        if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
        if (value >= 1024) return `${Math.round(value / 1024)} KB`;
        return `${value} B`;
      }

      function roomWizardResultsToggleMap() {
        return {
          structural: document.getElementById('roomWizardToggleStructural'),
          background: document.getElementById('roomWizardToggleBackground'),
          decor: document.getElementById('roomWizardToggleDecor'),
          semantics: document.getElementById('roomWizardToggleSemantics'),
          exclusion: document.getElementById('roomWizardToggleExclusion'),
          unresolved: document.getElementById('roomWizardToggleUnresolved'),
          validation: document.getElementById('roomWizardToggleValidation'),
        };
      }

      function syncRoomWizardResultsToggles() {
        const toggles = RoomEditor.State.roomWizard.resultsToggles || {};
        Object.entries(roomWizardResultsToggleMap()).forEach(([key, el]) => {
          if (!el) return;
          el.checked = !!toggles[key];
        });
      }

      function bindRoomWizardResultsToggleInputs() {
        Object.entries(roomWizardResultsToggleMap()).forEach(([key, el]) => {
          if (!el || el.dataset.bound === '1') return;
          el.dataset.bound = '1';
          el.addEventListener('change', () => {
            RoomEditor.State.roomWizard.resultsToggles[key] = !!el.checked;
            const room = getRoomWizardRoom();
            if (room?.environment) {
              renderRoomWizardEnvironmentOutputSummary(room.environment);
            }
          });
        });
      }

      function renderRoomWizardResultsToggleControls(toggleState) {
        const checked = (key) => toggleState?.[key] ? 'checked' : '';
        return `
          <div class="rw-environment-overlay-tools">
            <div class="rw-results-toggle-grid" id="roomWizardResultsToggleGrid">
              <div class="rw-toggle-card">
                <strong>Layers</strong>
                <label><input type="checkbox" id="roomWizardToggleStructural" ${checked('structural')} /> Structure</label>
                <label><input type="checkbox" id="roomWizardToggleBackground" ${checked('background')} /> Background</label>
                <label><input type="checkbox" id="roomWizardToggleDecor" ${checked('decor')} /> Decor</label>
              </div>
              <div class="rw-toggle-card">
                <strong>Debug view</strong>
                <label><input type="checkbox" id="roomWizardToggleSemantics" ${checked('semantics')} /> Room overlay</label>
                <label><input type="checkbox" id="roomWizardToggleExclusion" ${checked('exclusion')} /> Blocked zones</label>
                <label><input type="checkbox" id="roomWizardToggleUnresolved" ${checked('unresolved')} /> Missing surfaces</label>
                <label><input type="checkbox" id="roomWizardToggleValidation" ${checked('validation')} /> Warnings</label>
              </div>
            </div>
          </div>`;
      }

      function renderRoomWizardReferenceList(envState) {
        const target = document.getElementById('roomWizardReferenceList');
        if (!target) return;
        ensureRoomWizardEnvironmentAuthoringFields(envState);
        const refs = envState?.spec?.reference_uploads || [];
        if (!refs.length) {
          target.innerHTML = '<div class="rw-reference-item"><p class="rw-environment-stage-empty">No room-level reference pack items yet. Upload images here to keep this room’s stylepack grounded in the workbench.</p></div>';
          return;
        }
        const locked = !!envState?.spec?.lock_stylepack;
        target.innerHTML = refs.map((item) => {
          const pinned = String(item.pinned_to || '').trim() === 'stylepack';
          return `
            <article class="rw-reference-item">
              <div class="rw-reference-item-head">
                <div>
                  <strong>${escapeHtml(item.label || item.file_name || 'Reference')}</strong>
                  <p class="rw-reference-meta">${escapeHtml([item.file_name, item.file_type, formatRoomWizardFileSize(item.file_size)].filter(Boolean).join(' · '))}</p>
                </div>
                <div class="rw-reference-item-actions">
                  <span class="rw-stage-pill ${pinned ? 'rw-stage-pill--accent' : ''}">${escapeHtml(pinned ? 'Pinned to Stylepack' : (item.status || 'uploaded'))}</span>
                  <button type="button" class="btn-secondary btn-sm rw-reference-pin" data-reference-id="${escapeHtml(item.id)}" ${locked ? 'disabled' : ''}>${pinned ? 'Pinned' : 'Pin'}</button>
                  <button type="button" class="btn-secondary btn-sm rw-reference-remove" data-reference-id="${escapeHtml(item.id)}" ${locked ? 'disabled' : ''}>Remove</button>
                </div>
              </div>
            </article>`;
        }).join('');
        target.querySelectorAll('.rw-reference-pin').forEach((btn) => {
          btn.addEventListener('click', () => {
            const room = getRoomWizardRoom();
            if (!room?.environment) return;
            ensureRoomWizardEnvironmentAuthoringFields(room.environment);
            room.environment.spec.reference_uploads = room.environment.spec.reference_uploads.map((item) => ({
              ...item,
              pinned_to: item.id === btn.dataset.referenceId ? 'stylepack' : '',
            }));
            setDirty(true);
            renderRoomWizardReferenceList(room.environment);
            renderRoomWizardEnvironmentOutputSummary(room.environment);
          });
        });
        target.querySelectorAll('.rw-reference-remove').forEach((btn) => {
          btn.addEventListener('click', () => {
            const room = getRoomWizardRoom();
            if (!room?.environment) return;
            ensureRoomWizardEnvironmentAuthoringFields(room.environment);
            room.environment.spec.reference_uploads = room.environment.spec.reference_uploads.filter((item) => item.id !== btn.dataset.referenceId);
            setDirty(true);
            renderRoomWizardReferenceList(room.environment);
            renderRoomWizardEnvironmentOutputSummary(room.environment);
          });
        });
      }

      function updateRoomWizardResultsEmptyState(hasResult) {
        const empty = document.getElementById('roomWizardResultsEmptyState');
        if (!empty) return;
        empty.hidden = !!hasResult;
      }

      function syncRoomWizardEnvironmentAuthoringFromInputs() {
        const room = getRoomWizardRoom();
        const envMod = globalThis.RoomWizardEnvironment;
        if (!room || !envMod) return;
        envMod.ensureRoomEnvironment(room);
        ensureRoomWizardEnvironmentAuthoringFields(room.environment);
        const themeNameEl = document.getElementById('roomWizardThemeName');
        const notesEl = document.getElementById('roomWizardEnvironmentNotes');
        const seedEl = document.getElementById('roomWizardEnvironmentSeed');
        const lockEl = document.getElementById('roomWizardLockStylepack');
        room.environment.spec.theme_name = String(themeNameEl?.value || '').trim();
        room.environment.spec.notes = String(notesEl?.value || '').trim();
        room.environment.spec.seed = String(seedEl?.value || '').trim();
        room.environment.spec.lock_stylepack = !!lockEl?.checked;
        setDirty(true);
        renderRoomWizardReferenceList(room.environment);
        renderRoomWizardEnvironmentOutputSummary(room.environment);
        updateJsonText();
      }

      function syncRoomWizardEnvironmentFromRoom() {
        const room = getRoomWizardRoom();
        const envMod = globalThis.RoomWizardEnvironment;
        if (!room || !envMod) return;
        populateRoomWizardThemeSelect();
        envMod.ensureRoomEnvironment(room);
        const e = room.environment;
        ensureRoomWizardEnvironmentAuthoringFields(e);
        const sel = document.getElementById('roomWizardThemeSelect');
        const tagsEl = document.getElementById('roomWizardTagsInput');
        const v3Toggle = document.getElementById('roomWizardUseV3Pipeline');
        const themeNameEl = document.getElementById('roomWizardThemeName');
        const notesEl = document.getElementById('roomWizardEnvironmentNotes');
        const seedEl = document.getElementById('roomWizardEnvironmentSeed');
        const lockEl = document.getElementById('roomWizardLockStylepack');
        if (sel) {
          const ids = envMod.THEME_PRESETS.map((p) => p.id);
          sel.value = ids.includes(e.themeId) ? e.themeId : 'custom';
        }
        if (tagsEl) tagsEl.value = envMod.tagsToInputString(e.tags);
        if (v3Toggle) v3Toggle.checked = String(e.environment_pipeline_version || '').trim().toLowerCase() === 'v3';
        if (themeNameEl) themeNameEl.value = String(e.spec?.theme_name || '');
        if (notesEl) notesEl.value = String(e.spec?.notes || '');
        if (seedEl) seedEl.value = String(e.spec?.seed || '');
        if (lockEl) lockEl.checked = !!e.spec?.lock_stylepack;
        const promptEl = document.getElementById('roomWizardCopilotPrompt');
        const previewBox = document.getElementById('roomWizardCopilotPreview');
        if (promptEl && !String(promptEl.value || '').trim()) {
          promptEl.value = e.spec?.description || '';
        }
        syncRoomWizardComponentFields(e);
        syncRoomWizardResultsToggles();
        renderRoomWizardReferenceList(e);
        renderRoomWizardEnvironmentPreview(e);
        renderRoomWizardPreviewGallery(e.preview || {});
        renderRoomWizardEnvironmentOutputSummary(e);
        const hasPreviewImages = !!(Array.isArray(e.preview?.images) && e.preview.images.length);
        if (previewBox) previewBox.hidden = !hasPreviewImages;
        updateRoomWizardResultsEmptyState(hasPreviewImages);
        const applyBtn = document.getElementById('roomWizardCopilotApply');
        if (applyBtn) applyBtn.hidden = !!PROJECT_ID;
      }

      function replaceRoomWizardEnvironmentPreservingAuthoring(room, nextEnvironment) {
        const envMod = globalThis.RoomWizardEnvironment;
        if (!room || !envMod) return;
        envMod.ensureRoomEnvironment(room);
        const authoring = cloneRoomWizardEnvironmentAuthoringFields(room.environment);
        room.environment = nextEnvironment || room.environment;
        envMod.ensureRoomEnvironment(room);
        applyRoomWizardEnvironmentAuthoringFields(room.environment, authoring);
      }

      function roomWizardComponentFieldMap() {
        return {
          floor: document.getElementById('roomWizardComponentFloor'),
          platforms: document.getElementById('roomWizardComponentPlatforms'),
          walls: document.getElementById('roomWizardComponentWalls'),
          doors: document.getElementById('roomWizardComponentDoors'),
          background: document.getElementById('roomWizardComponentBackground')
        };
      }

      function syncRoomWizardComponentFields(envState) {
        const envMod = globalThis.RoomWizardEnvironment;
        if (!envMod || !envState?.spec) return;
        if (typeof envMod.ensureEnvironmentComponents === 'function') {
          envMod.ensureEnvironmentComponents(envState.spec);
        }
        const fields = roomWizardComponentFieldMap();
        const components = envState.spec.components || {};
        Object.entries(fields).forEach(([key, el]) => {
          if (!el) return;
          el.value = String((components[key] || {}).prompt || '');
        });
      }

      function collectRoomWizardComponentPrompts() {
        const envMod = globalThis.RoomWizardEnvironment;
        const fields = roomWizardComponentFieldMap();
        const room = getRoomWizardRoom();
        const description = String(document.getElementById('roomWizardCopilotPrompt')?.value || room?.environment?.spec?.description || '').trim();
        let fallback = {};
        if (envMod && typeof envMod.defaultEnvironmentComponents === 'function') {
          fallback = envMod.defaultEnvironmentComponents(description);
        }
        return {
          floor: { label: 'Floor', prompt: String(fields.floor?.value || fallback.floor?.prompt || '').trim() },
          platforms: { label: 'Platforms', prompt: String(fields.platforms?.value || fallback.platforms?.prompt || '').trim() },
          walls: { label: 'Walls', prompt: String(fields.walls?.value || fallback.walls?.prompt || '').trim() },
          doors: { label: 'Doors', prompt: String(fields.doors?.value || fallback.doors?.prompt || '').trim() },
          background: { label: 'Background', prompt: String(fields.background?.value || fallback.background?.prompt || '').trim() }
        };
      }

      function clearRoomWizardCopilotPreview() {
        RoomEditor.State.roomWizard.copilotPreview = null;
        const prev = document.getElementById('roomWizardCopilotPreview');
        const prevVisual = document.getElementById('roomWizardCopilotPreviewVisual');
        const lookStrip = document.getElementById('roomWizardLookPreviewStrip');
        const lookVisual = document.getElementById('roomWizardLookPreviewVisual');
        const lookGallery = document.getElementById('roomWizardLookPreviewGallery');
        const gallery = document.getElementById('roomWizardPreviewGallery');
        const output = document.getElementById('roomWizardEnvironmentOutputSummary');
        const revision = document.getElementById('roomWizardPreviewRevision');
        const st = document.getElementById('roomWizardCopilotStatus');
        if (prev) prev.hidden = true;
        if (prevVisual) prevVisual.innerHTML = '';
        if (lookStrip) lookStrip.hidden = true;
        if (lookVisual) lookVisual.innerHTML = '';
        if (lookGallery) lookGallery.innerHTML = '';
        if (gallery) gallery.innerHTML = '';
        if (output) output.innerHTML = '';
        if (revision) revision.value = '';
        if (st) st.textContent = '';
        updateRoomWizardResultsEmptyState(false);
      }

      function buildRoomWizardEnvironmentPreviewModel(themeId, tags, rationale) {
        const envMod = globalThis.RoomWizardEnvironment;
        if (envMod && typeof envMod.buildEnvironmentPreviewModel === 'function') {
          return envMod.buildEnvironmentPreviewModel(themeId, tags, rationale);
        }
        const normalizedThemeId = typeof themeId === 'string' && themeId.trim() ? themeId.trim() : 'cave';
        const cleanedTags = Array.isArray(tags)
          ? tags.map((tag) => String(tag).trim()).filter(Boolean).slice(0, 6)
          : [];
        const fallbackLabel =
          envMod && Array.isArray(envMod.THEME_PRESETS)
            ? (envMod.THEME_PRESETS.find((preset) => preset.id === normalizedThemeId) || {}).label
            : '';
        return {
          themeId: normalizedThemeId,
          themeLabel: fallbackLabel || normalizedThemeId,
          eyebrow: 'Room atmosphere',
          summary: 'Preview available after the environment helpers finish loading.',
          rationale: typeof rationale === 'string' ? rationale.trim() : '',
          tags: cleanedTags,
          sceneClass: `rw-environment-scene--${normalizedThemeId}`
        };
      }

      function assetUrlWithVersion(url, version) {
        const raw = String(url || '').trim();
        if (!raw) return '';
        const stamp = String(version || '').trim();
        if (!stamp) return raw;
        return `${raw}${raw.includes('?') ? '&' : '?'}v=${encodeURIComponent(stamp)}`;
      }

      function openRoomEnvironmentAssetPreviewWindow(srcUrl) {
        const raw = String(srcUrl || '').trim();
        if (!raw) return;
        const viewerBase = new URL('/room-environment-preview-full.html', window.location.origin).href;
        const fullUrl = `${viewerBase}?src=${encodeURIComponent(raw)}`;
        const w = Math.min(1200, window.screen.availWidth - 48);
        const h = Math.min(900, window.screen.availHeight - 80);
        const left = Math.max(0, Math.round((window.screen.availWidth - w) / 2));
        const top = Math.max(0, Math.round((window.screen.availHeight - h) / 2));
        const features = [
          `width=${w}`,
          `height=${h}`,
          `left=${left}`,
          `top=${top}`,
          'scrollbars=yes',
          'resizable=yes',
        ].join(',');
        const win = window.open(fullUrl, 'rwRoomEnvAssetPreview', features);
        if (win) {
          try {
            win.opener = null;
          } catch (e) {
            /* ignore cross-origin */
          }
        }
      }

      function humanizeRoomWizardLabel(value) {
        return String(value || '').replace(/_/g, ' ').trim();
      }

      function describeRoomWizardApprovalStatus(value) {
        const normalized = String(value || '').trim().toLowerCase();
        if (normalized === 'runtime_review_pending') return 'Runtime review pending';
        if (normalized === 'generating') return 'Generating';
        if (normalized === 'partial') return 'Partial';
        if (normalized === 'locked') return 'Locked';
        if (normalized === 'ready') return 'Ready';
        if (normalized === 'empty') return 'Empty';
        if (normalized === 'approved') return 'Approved';
        if (normalized === 'blocked') return 'Blocked';
        if (normalized === 'draft') return 'Draft';
        return humanizeRoomWizardLabel(value || 'draft');
      }

      function describeRoomWizardValidationStatus(value) {
        const normalized = String(value || '').trim().toLowerCase();
        if (normalized === 'complete') return 'Ready';
        if (normalized === 'ready') return 'Ready';
        if (normalized === 'generating' || normalized === 'running') return 'Generating';
        if (normalized === 'partial') return 'Partial';
        if (normalized === 'locked') return 'Locked';
        if (normalized === 'empty') return 'Empty';
        if (normalized === 'blocked') return 'Blocked';
        if (normalized === 'warning') return 'Warning';
        if (normalized === 'pass') return 'Pass';
        if (normalized === 'idle' || normalized === 'pending') return 'Pending';
        return humanizeRoomWizardLabel(value || 'pending');
      }

      function describeRoomWizardRuntimeReviewStatus(value) {
        const normalized = String(value || '').trim().toLowerCase();
        if (normalized === 'pass') return 'Reviewed';
        if (normalized === 'fail') return 'Review failed';
        if (normalized === 'idle' || normalized === 'running') return 'Review pending';
        return humanizeRoomWizardLabel(value || 'pending');
      }

      function roomWizardOverlayBounds(envState, roomHint) {
        const assemblyOverlay = envState?.assembly_plan?.overlay_geometry || {};
        const semanticsOverlay = envState?.room_semantics?.overlay_geometry || {};
        const semanticsRoomSize = envState?.room_semantics?.room_size || {};
        const size = assemblyOverlay.size || {};
        const polygon = Array.isArray(semanticsOverlay.room_polygon) && semanticsOverlay.room_polygon.length
          ? semanticsOverlay.room_polygon
          : Array.isArray(assemblyOverlay.room_polygon) ? assemblyOverlay.room_polygon : [];
        const xs = polygon.map((point) => Number(Array.isArray(point) ? point[0] : point?.x || 0)).filter(Number.isFinite);
        const ys = polygon.map((point) => Number(Array.isArray(point) ? point[1] : point?.y || 0)).filter(Number.isFinite);
        const hinted = roomHint && typeof roomHint === 'object' ? roomHint : null;
        if (hinted) ensureRoomShape(hinted);
        const dim = (axisSize, semanticKey, hintKey, arr, fallback) => {
          const fromAssembly = Number(axisSize?.[semanticKey] || 0);
          if (Number.isFinite(fromAssembly) && fromAssembly > 0) return fromAssembly;
          const fromSemantics = Number(semanticsRoomSize?.[semanticKey] || 0);
          if (Number.isFinite(fromSemantics) && fromSemantics > 0) return fromSemantics;
          const fromHint = Number(hinted?.size?.[hintKey] || 0);
          if (Number.isFinite(fromHint) && fromHint > 0) return fromHint;
          if (arr.length >= 2) {
            const span = Math.max(...arr) - Math.min(...arr);
            if (Number.isFinite(span) && span > 0) return span;
          }
          if (arr.length) {
            const m = Math.max(...arr);
            if (Number.isFinite(m) && m > 0) return m;
          }
          return fallback;
        };
        const width = Math.max(1, Math.round(dim(size, 'width', 'width', xs, 1600)));
        const height = Math.max(1, Math.round(dim(size, 'height', 'height', ys, 1200)));
        return { width, height, polygon };
      }

      function roomWizardRectFromPlacement(placement = {}, targetDimensions = {}) {
        const width = Number(placement.display_width || placement.width || targetDimensions.width || 0);
        const height = Number(placement.display_height || placement.height || targetDimensions.height || 0);
        const originX = Number(placement.origin_x ?? 0);
        const originY = Number(placement.origin_y ?? 0);
        const x = Number(placement.x || 0) - (width * originX);
        const y = Number(placement.y || 0) - (height * originY);
        return {
          x,
          y,
          width,
          height,
        };
      }

      function roomWizardRectSvg(rect, stroke, fill, label, extraClass = '') {
        if (!rect || !Number.isFinite(rect.width) || !Number.isFinite(rect.height) || rect.width <= 0 || rect.height <= 0) return '';
        const title = label ? `<title>${escapeHtml(label)}</title>` : '';
        return `<rect class="${escapeHtml(extraClass)}" x="${rect.x}" y="${rect.y}" width="${rect.width}" height="${rect.height}" rx="12" ry="12" fill="${fill}" stroke="${stroke}" stroke-width="8">${title}</rect>`;
      }

      function roomWizardLineSvg(line, stroke, label) {
        if (!line || !line.start || !line.end) return '';
        const title = label ? `<title>${escapeHtml(label)}</title>` : '';
        return `<line x1="${Number(line.start.x || 0)}" y1="${Number(line.start.y || 0)}" x2="${Number(line.end.x || 0)}" y2="${Number(line.end.y || 0)}" stroke="${stroke}" stroke-width="6" stroke-linecap="round">${title}</line>`;
      }

      function roomWizardPointSvg(point, fill, radius, label) {
        if (!point) return '';
        const title = label ? `<title>${escapeHtml(label)}</title>` : '';
        return `<circle cx="${Number(point.x || 0)}" cy="${Number(point.y || 0)}" r="${radius}" fill="${fill}">${title}</circle>`;
      }

      function roomWizardDecorMarkerRect(item, index, bounds) {
        const width = Math.max(64, Math.round(bounds.width * 0.05));
        const height = Math.max(64, Math.round(bounds.height * 0.08));
        const zoneMap = {
          left: 0.22,
          center: 0.5,
          right: 0.78,
          focal: 0.5,
          side: index % 2 === 0 ? 0.22 : 0.78,
        };
        const anchorMap = {
          ceiling: 0.16,
          wall: 0.38,
          platform: 0.56,
          floor: 0.8,
        };
        const zone = String(item?.zone || '').trim().toLowerCase();
        const anchor = String(item?.anchor || '').trim().toLowerCase();
        const count = Math.max(1, Number(item?.count || 1));
        const spreadIndex = count > 1 ? (index % count) - ((count - 1) / 2) : 0;
        const xCenter = Math.round(bounds.width * (zoneMap[zone] || 0.5) + (spreadIndex * (width + 24)));
        const yCenter = Math.round(bounds.height * (anchorMap[anchor] || 0.5));
        return {
          x: Math.max(12, Math.min(bounds.width - width - 12, xCenter - (width / 2))),
          y: Math.max(12, Math.min(bounds.height - height - 12, yCenter - (height / 2))),
          width,
          height,
        };
      }

      function renderRoomWizardResultsOverlay(envState, toggleState) {
        const semanticsOverlay = envState?.room_semantics?.overlay_geometry || {};
        const manifestLayers = envState?.environment_manifest?.layers || {};
        const validationHighlights = envState?.validation_report?.validation_highlights || {};
        const sceneSchema = envState?.spec?.scene_schema || {};
        const plannedDecor = Array.isArray(sceneSchema?.set_dressing)
          ? sceneSchema.set_dressing
          : Array.isArray(sceneSchema?.setDressing)
            ? sceneSchema.setDressing
            : [];
        const bounds = roomWizardOverlayBounds(envState, getRoomWizardRoom());
        const polygon = bounds.polygon || [];
        const hasRoomShape = polygon.length >= 3;
        const controlsMarkup = renderRoomWizardResultsToggleControls(toggleState);
        if (!hasRoomShape) {
          return `<section class="rw-environment-overlay-card"><div class="rw-environment-stage-head"><div><p class="rw-environment-preview-label">6. Layout overlay</p><strong>Layout overlay</strong></div></div><p class="rw-environment-stage-copy">Use these controls to inspect placements and debug geometry once the room footprint is available.</p>${controlsMarkup}<div class="rw-environment-overlay-empty">Overlay geometry will appear here once semantics and placements are available.</div></section>`;
        }

        const polygonPoints = polygon.map((point) => `${Number(point[0] || 0)},${Number(point[1] || 0)}`).join(' ');
        const svgParts = [
          `<polygon points="${polygonPoints}" fill="rgba(157,221,242,0.06)" stroke="#9dddf2" stroke-width="4"></polygon>`
        ];
        const legend = ['<span class="rw-environment-overlay-pill rw-environment-overlay-pill--room">Room shell</span>'];
        const meta = [];

        const addLayerRects = (enabled, layerName, stroke, fill, legendClass) => {
          if (!enabled) return;
          const items = Array.isArray(manifestLayers[layerName]) ? manifestLayers[layerName] : [];
          items.forEach((item) => {
            const rect = roomWizardRectFromPlacement(item?.placement || {}, item?.target_dimensions || {});
            svgParts.push(roomWizardRectSvg(rect, stroke, fill, `${humanizeRoomWizardLabel(layerName)} · ${humanizeRoomWizardLabel(item?.component_type || item?.slot_id || 'placement')}`));
          });
          if (items.length) {
            legend.push(`<span class="rw-environment-overlay-pill ${legendClass}">${escapeHtml(`${layerName} ${items.length}`)}</span>`);
            meta.push(`<span>${escapeHtml(`${humanizeRoomWizardLabel(layerName)} placements: ${items.length}`)}</span>`);
          }
        };

        addLayerRects(toggleState.structural, 'structural', '#f5d074', 'rgba(245,208,116,0.18)', 'rw-environment-overlay-pill--structural');
        addLayerRects(toggleState.background, 'background', '#6ab7ff', 'rgba(106,183,255,0.16)', 'rw-environment-overlay-pill--background');
        addLayerRects(toggleState.decor, 'decor', '#c084fc', 'rgba(192,132,252,0.18)', 'rw-environment-overlay-pill--decor');
        if (toggleState.decor && !(Array.isArray(manifestLayers.decor) && manifestLayers.decor.length) && plannedDecor.length) {
          plannedDecor.forEach((item, index) => {
            const rect = roomWizardDecorMarkerRect(item, index, bounds);
            const label = `${humanizeRoomWizardLabel(item?.type || 'decor')} · ${humanizeRoomWizardLabel(item?.anchor || 'anchor')} · ${humanizeRoomWizardLabel(item?.zone || 'zone')}`;
            svgParts.push(`<rect x="${rect.x}" y="${rect.y}" width="${rect.width}" height="${rect.height}" rx="12" ry="12" fill="rgba(192,132,252,0.08)" stroke="#c084fc" stroke-width="8" stroke-dasharray="18 12"><title>${escapeHtml(label)}</title></rect>`);
          });
          legend.push('<span class="rw-environment-overlay-pill rw-environment-overlay-pill--decor">Decor plan</span>');
          meta.push(`<span>${escapeHtml(`Planned decor markers: ${plannedDecor.length}`)}</span>`);
        }

        if (toggleState.semantics) {
          (semanticsOverlay.platform_tops || []).forEach((rect) => {
            svgParts.push(roomWizardRectSvg(rect, '#4ade80', 'rgba(74,222,128,0.2)', 'Traversal top'));
          });
          (semanticsOverlay.vertical_faces || []).forEach((rect) => {
            svgParts.push(roomWizardRectSvg(rect, '#34d399', 'rgba(52,211,153,0.16)', 'Vertical face'));
          });
          (semanticsOverlay.shell_surfaces || []).forEach((line) => {
            svgParts.push(roomWizardLineSvg(line, '#22c55e', humanizeRoomWizardLabel(line.surface_type || 'shell surface')));
          });
          (semanticsOverlay.anchors || []).forEach((point) => {
            svgParts.push(roomWizardPointSvg(point, '#4ade80', 14, humanizeRoomWizardLabel(point.anchor_type || 'anchor')));
          });
          legend.push('<span class="rw-environment-overlay-pill rw-environment-overlay-pill--semantics">Semantics</span>');
          meta.push(`<span>${escapeHtml(`Anchors: ${(semanticsOverlay.anchors || []).length} · tops: ${(semanticsOverlay.platform_tops || []).length}`)}</span>`);
        }

        if (toggleState.exclusion) {
          (semanticsOverlay.decor_safe_zones || []).forEach((rect) => {
            svgParts.push(roomWizardRectSvg(rect, '#f472b6', 'rgba(244,114,182,0.12)', humanizeRoomWizardLabel(rect.zone_id || 'decor safe zone')));
          });
          (semanticsOverlay.gameplay_exclusion_zones || []).forEach((rect) => {
            svgParts.push(roomWizardRectSvg(rect, '#fb7185', 'rgba(251,113,133,0.18)', humanizeRoomWizardLabel(rect.zone_id || 'gameplay exclusion zone')));
          });
          legend.push('<span class="rw-environment-overlay-pill rw-environment-overlay-pill--exclusion">Safe and blocked zones</span>');
          meta.push(`<span>${escapeHtml(`Safe zones: ${(semanticsOverlay.decor_safe_zones || []).length} · blocked zones: ${(semanticsOverlay.gameplay_exclusion_zones || []).length}`)}</span>`);
        }

        if (toggleState.validation) {
          Object.values(validationHighlights).forEach((items) => {
            (Array.isArray(items) ? items : []).forEach((item) => {
              svgParts.push(roomWizardRectSvg(item, '#f97316', 'rgba(249,115,22,0.14)', 'Validation highlight', 'rw-environment-overlay-highlight'));
            });
          });
          legend.push('<span class="rw-environment-overlay-pill rw-environment-overlay-pill--validation">Validation highlights</span>');
          meta.push(`<span>${escapeHtml(`Validation highlights: ${Object.values(validationHighlights).reduce((count, items) => count + (Array.isArray(items) ? items.length : 0), 0)}`)}</span>`);
        }

        if (toggleState.unresolved) {
          (validationHighlights.unresolved_surfaces || []).forEach((item) => {
            svgParts.push(roomWizardRectSvg(item, '#f87171', 'rgba(248,113,113,0.12)', 'Unresolved surface'));
          });
          legend.push('<span class="rw-environment-overlay-pill rw-environment-overlay-pill--unresolved">Unresolved surfaces</span>');
          meta.push(`<span>${escapeHtml(`Unresolved surfaces: ${(validationHighlights.unresolved_surfaces || []).length}`)}</span>`);
        }

        return `
          <section class="rw-environment-overlay-card">
            <div class="rw-environment-stage-head">
              <div>
                <p class="rw-environment-preview-label">6. Layout overlay</p>
                <strong>Layout overlay</strong>
              </div>
              <span class="rw-stage-pill">${escapeHtml(`${bounds.width} × ${bounds.height}`)}</span>
            </div>
            <p class="rw-environment-stage-copy">Compare layers against the Layout footprint: the cyan outline matches your polygon; green lines are boundary edges. Gold structural boxes follow planned asset slots (often a chamber rectangle for unified shell)—they may differ from concave outlines on purpose.</p>
            ${controlsMarkup}
            <div class="rw-environment-overlay-shell">
              <svg viewBox="0 0 ${bounds.width} ${bounds.height}" role="img" aria-label="Room environment overlay view">
                ${svgParts.join('')}
              </svg>
            </div>
            <div class="rw-environment-overlay-legend">${legend.join('')}</div>
            ${meta.length ? `<div class="rw-environment-overlay-meta">${meta.join('')}</div>` : ''}
          </section>`;
      }

      function renderEnvironmentPreviewMarkup(preview, heading) {
        const chips = (preview.tags || [])
          .map((tag) => `<span class="rw-environment-chip">${escapeHtml(tag)}</span>`)
          .join('');
        const rationale = preview.rationale
          ? `<p class="rw-environment-preview-rationale">${escapeHtml(preview.rationale)}</p>`
          : '';
        return `
          <section class="rw-environment-preview-card">
            <div class="rw-environment-scene ${escapeHtml(preview.sceneClass)}" aria-hidden="true">
              <div class="rw-environment-scene__mist"></div>
              <div class="rw-environment-scene__glow"></div>
              <div class="rw-environment-scene__monolith rw-environment-scene__monolith--left"></div>
              <div class="rw-environment-scene__monolith rw-environment-scene__monolith--right"></div>
              <div class="rw-environment-scene__ground"></div>
            </div>
            <div class="rw-environment-preview-copy">
              <p class="rw-environment-preview-label">${escapeHtml(heading)}</p>
              <div class="rw-environment-preview-headline">
                <strong>${escapeHtml(preview.themeLabel)}</strong>
                <span>${escapeHtml(preview.eyebrow)}</span>
              </div>
              <p class="rw-environment-preview-summary">${escapeHtml(preview.summary)}</p>
              ${rationale}
              <div class="rw-environment-chip-row">${chips}</div>
            </div>
          </section>`;
      }

      function renderGeneratedEnvironmentPreviewMarkup(envState) {
        const previewState = envState?.preview || {};
        const items = Array.isArray(previewState.images) ? previewState.images : [];
        if (!items.length) return '';
        const approvedId = previewState.approved_image_id || '';
        const active = items.find((item) => item.preview_id === approvedId) || items[0];
        const activeUrl = assetUrlWithVersion(active.url || '', previewState.last_generated_at || active.preview_id || '');
        const scenePlan = previewState.scene_plan || {};
        const summaryBits = [
          scenePlan.lighting ? `Lighting: ${scenePlan.lighting}` : '',
          scenePlan.fog ? `Atmosphere: ${scenePlan.fog}` : '',
          Array.isArray(scenePlan.landmarks) && scenePlan.landmarks.length ? `Landmarks: ${scenePlan.landmarks.slice(0, 3).join(', ')}` : '',
          previewState.fallback_reason ? `Fallback: ${String(previewState.fallback_reason).replace(/_/g, ' ')}` : '',
          scenePlan.used_ai === false ? 'Renderer fallback used' : 'AI-assisted preview'
        ].filter(Boolean);
        const chips = (envState.tags || [])
          .map((tag) => `<span class="rw-environment-chip">${escapeHtml(tag)}</span>`)
          .join('');
        return `
          <section class="rw-generated-environment-card">
            <div class="rw-generated-environment-media">
              <img src="${escapeHtml(activeUrl)}" alt="${escapeHtml(active.label || 'Preview')}" />
            </div>
            <div class="rw-generated-environment-copy">
              <p class="rw-environment-preview-label">Preview</p>
              <div class="rw-environment-preview-headline">
                <strong>${escapeHtml(active.label || 'Preview')}</strong>
                <span>${escapeHtml((active.render_level || previewState.render_level || '').toUpperCase())}</span>
              </div>
              <p class="rw-environment-preview-summary">
                ${escapeHtml(envState.spec?.description || 'Generated environment concept based on the room draft, project art direction, and room layout.')}
              </p>
              ${summaryBits.length ? `<p class="rw-environment-preview-rationale">${escapeHtml(summaryBits.join(' · '))}</p>` : ''}
              <div class="rw-environment-chip-row">${chips}</div>
            </div>
          </section>`;
      }

      function renderRoomWizardEnvironmentPreview(envState) {
        const resultsTarget = document.getElementById('roomWizardEnvironmentPreview');
        const lookTarget = document.getElementById('roomWizardLookPreviewVisual');
        if ((!resultsTarget && !lookTarget) || !envState) return;
        const generatedMarkup = renderGeneratedEnvironmentPreviewMarkup(envState);
        const hasGalleryImages = Array.isArray(envState?.preview?.images) && envState.preview.images.length > 0;
        if (generatedMarkup) {
          if (resultsTarget) {
            resultsTarget.innerHTML = hasGalleryImages ? '' : generatedMarkup;
          }
          if (lookTarget) {
            lookTarget.innerHTML = generatedMarkup;
          }
          return;
        }
        const preview = buildRoomWizardEnvironmentPreviewModel(envState.themeId, envState.tags || []);
        const markup = renderEnvironmentPreviewMarkup(preview, 'Current room mood');
        [resultsTarget, lookTarget].filter(Boolean).forEach((target) => {
          target.innerHTML = markup;
        });
      }

      function roomWizardHasGeneratedPreview(previewState) {
        const room = getRoomWizardRoom();
        const envState = room?.environment || null;
        if (Array.isArray(previewState?.images) && previewState.images.length) return true;
        return !!(previewState && String(previewState.status || '').trim().toLowerCase() === 'ready' && envState);
      }

      function renderRoomWizardEnvironmentOutputSummary(envState) {
        const target = document.getElementById('roomWizardEnvironmentOutputSummary');
        if (!target) return;
        ensureRoomWizardEnvironmentAuthoringFields(envState);
        const preview = envState?.preview || {};
        const runtime = envState?.runtime || {};
        const assetPack = runtime?.asset_pack || {};
        const bespokeManifest = runtime?.bespoke_asset_manifest || {};
        const generationPlan = Array.isArray(bespokeManifest.generation_plan) ? bespokeManifest.generation_plan : [];
        const requiredSlots = Array.isArray(bespokeManifest.required_slots) ? bespokeManifest.required_slots : generationPlan.map((item) => item?.slot_id).filter(Boolean);
        const builtSlots = Array.isArray(bespokeManifest.built_slots) ? bespokeManifest.built_slots : [];
        const generatedAssets = bespokeManifest.assets && typeof bespokeManifest.assets === 'object'
          ? Object.values(bespokeManifest.assets).filter((item) => item && typeof item === 'object')
          : [];
        const builtAssetCount = builtSlots.length || generatedAssets.filter((item) => item.url).length;
        const requiredAssetCount = requiredSlots.length || generationPlan.length;
        const staleComponents = Array.isArray(assetPack.stale_components) ? assetPack.stale_components : [];
        const spec = envState?.spec || {};
        const sceneSchema = spec?.scene_schema || {};
        const kit = sceneSchema?.kit || {};
        const components = spec?.components || {};
        const componentSchemas = spec?.component_schemas || {};
        const schemaValidation = bespokeManifest.schema_validation || {};
        const schemaStatuses = schemaValidation.component_statuses || {};
        const slotGroupMap = bespokeManifest.slot_groups || {};
        const runtimeReview = bespokeManifest.runtime_review || bespokeManifest.review || {};
        const pipelineVersion = String(envState?.environment_pipeline_version || 'v2').trim().toLowerCase() === 'v3' ? 'v3' : 'v2';
        const assemblyPlan = envState?.assembly_plan || {};
        const reviewState = envState?.review_state || {};
        const reviewValidation = reviewState?.validation_status || {};
        const plannerCoverage = assemblyPlan?.planner_coverage_summary || {};
        const overlayGeometry = assemblyPlan?.overlay_geometry || {};
        const assemblySlots = Array.isArray(assemblyPlan?.slots) ? assemblyPlan.slots : [];
        const validationErrs = Array.isArray(bespokeManifest.validation_errors) ? bespokeManifest.validation_errors : [];
        const buildButton = document.getElementById('roomWizardBuildEnvironmentAssets');
        const approved = Array.isArray(preview.images)
          ? preview.images.find((item) => item.preview_id === preview.approved_image_id)
          : null;
        const editorPayload = envState?.editor_results_payload || {};
        const stylepackSummary = editorPayload.stylepack || {};
        const semanticsSummary = editorPayload.semantics || {};
        const kitSummary = editorPayload.kit || {};
        const manifestSummary = editorPayload.manifest || {};
        const validationSummary = editorPayload.validation || {};
        const manifestDoc = envState?.environment_manifest || {};
        const validationDoc = envState?.validation_report || {};
        const refUploads = Array.isArray(spec.reference_uploads) ? spec.reference_uploads : [];
        const pinnedRefs = refUploads.filter((item) => String(item.pinned_to || '') === 'stylepack');
        const toggleState = RoomEditor.State.roomWizard.resultsToggles || {};

        const bits = [];
        bits.push(`Theme: ${envState?.themeId || 'custom'}`);
        bits.push(`Pipeline: ${pipelineVersion.toUpperCase()}`);
        if (preview.render_level) bits.push(`Preview source: ${String(preview.render_level).toUpperCase()}`);
        if (preview.fallback_reason) bits.push(`Fallback: ${String(preview.fallback_reason).replace(/_/g, ' ')}`);
        if (approved?.label) bits.push(`Approved: ${approved.label}`);
        if (runtime.status === 'ready') {
          bits.push('Open Game will style walls, platforms, movers, and doors from the approved preview palette.');
        } else if (Array.isArray(preview.images) && preview.images.length) {
          bits.push('Approve one preview to push its palette and materials into the playable room preview.');
        } else {
          bits.push('Generate previews to produce a room image, then approve one to drive runtime surfaces.');
        }
        if (bespokeManifest.status === 'ready') {
          const warningReasons = Array.isArray(runtimeReview.warning_reasons) ? runtimeReview.warning_reasons : [];
          bits.push(`Bespoke biome assets complete: ${builtAssetCount}/${requiredAssetCount || builtAssetCount} required slots built and runtime review passed${warningReasons.length ? ` with warnings: ${warningReasons.join(', ')}` : ''}.`);
        } else if (bespokeManifest.status === 'failed') {
          bits.push(`Bespoke asset generation incomplete: ${builtAssetCount}/${requiredAssetCount || builtAssetCount} slots built.`);
        } else if (preview.approved_image_id) {
          bits.push('Build the bespoke biome asset set for this room to generate structural room slots, then run runtime screenshot QA.');
        }
        if (staleComponents.length) bits.push(`Impacted by the latest room changes: ${staleComponents.join(', ').replace(/_/g, ' ')}.`);

        const materialText = Array.isArray(spec.materials) && spec.materials.length
          ? spec.materials.slice(0, 4).join(', ')
          : 'No materials planned yet';
        const lightingText = spec.lighting || 'Lighting not planned yet';
        const templateText = envState?.template_context?.source_template_label || 'Freeform draft';
        const assetText = bespokeManifest.status === 'ready'
          ? `Assets: ${builtAssetCount}/${requiredAssetCount || builtAssetCount} required slots live in runtime · Generated ${bespokeManifest.generated_at || 'recently'}`
          : bespokeManifest.status === 'failed'
            ? `Assets: incomplete (${builtAssetCount}/${requiredAssetCount || builtAssetCount} built)`
            : 'Assets: not built yet';
        const schemaText = `Schema: ${(sceneSchema.background_layers || []).length} background layer${(sceneSchema.background_layers || []).length === 1 ? '' : 's'}, ${(sceneSchema.set_dressing || []).length} dressing rule${(sceneSchema.set_dressing || []).length === 1 ? '' : 's'}, effects ${Object.keys(sceneSchema.effects || {}).length}`;
        const kitText = [kit.shell_family, kit.wall_family, kit.platform_family, kit.door_family, kit.backdrop_family].filter(Boolean).join(', ');
        const componentChips = Object.entries(components).map(([key, item]) => {
          const label = `${String((item || {}).label || key)} · ${String((item || {}).prompt || '').slice(0, 44)}`;
          return `<span class="rw-environment-chip">${escapeHtml(label)}</span>`;
        }).join('');
        const componentSchemaChips = Object.entries(componentSchemas).map(([key, item]) => {
          const status = String((schemaStatuses[key] || {}).status || 'normalized');
          const label = `${key} · ${status}`;
          const intent = String((item || {}).design_intent || '').slice(0, 48);
          return `<span class="rw-environment-chip">${escapeHtml(`${label}${intent ? ` · ${intent}` : ''}`)}</span>`;
        }).join('');
        const slotGroupChips = Object.entries(slotGroupMap).map(([key, group]) => (
          `<span class="rw-environment-chip">${escapeHtml(`${key}: ${group.built || 0}/${group.required || 0}`)}</span>`
        )).join('');
        const staleChips = staleComponents.map((item) => (
          `<span class="rw-environment-chip">${escapeHtml(`Needs refresh: ${String(item).replace(/_/g, ' ')}`)}</span>`
        )).join('');
        const plannerCoverageText = pipelineVersion === 'v3'
          ? `Assembly plan: ${assemblySlots.length} slot${assemblySlots.length === 1 ? '' : 's'} · Coverage ${plannerCoverage.status || 'idle'} · Doors ${(plannerCoverage.major_structures || {}).planned_door_slots || 0}/${(plannerCoverage.major_structures || {}).door_count || 0} · Traversal ${(plannerCoverage.major_structures || {}).planned_platform_slots || 0}/${(plannerCoverage.major_structures || {}).platform_count || 0}`
          : '';
        const reviewStateText = pipelineVersion === 'v3'
          ? `Validation: ${describeRoomWizardValidationStatus(reviewValidation.status || 'pending')} · Approval: ${describeRoomWizardApprovalStatus(reviewState.approval_status || 'draft')}`
          : '';
        const assemblyPlanChips = pipelineVersion === 'v3'
          ? assemblySlots.slice(0, 14).map((item) => {
              const placement = item?.placement || {};
              const width = placement.display_width || item?.target_dimensions?.width || 0;
              const height = placement.display_height || item?.target_dimensions?.height || 0;
              const label = `${String(item?.component_type || 'slot')} · ${String(item?.schema_key || 'component')} · ${width}x${height}`;
              return `<span class="rw-environment-chip">${escapeHtml(label)}</span>`;
            }).join('')
          : '';
        const coverageChips = pipelineVersion === 'v3'
          ? [
              ...(Array.isArray(plannerCoverage.missing_slots) ? plannerCoverage.missing_slots : []).map((item) => `Coverage gap: ${item}`),
              ...(Array.isArray(reviewValidation.issues) ? reviewValidation.issues : []).map((item) => `Validation: ${item}`),
            ].map((item) => `<span class="rw-environment-chip">${escapeHtml(String(item).replace(/_/g, ' '))}</span>`).join('')
          : '';
        const assemblyOverlayText = pipelineVersion === 'v3'
          ? `Overlay geometry: ${(Array.isArray(overlayGeometry.slot_overlays) ? overlayGeometry.slot_overlays.length : 0)} overlay region${(Array.isArray(overlayGeometry.slot_overlays) ? overlayGeometry.slot_overlays.length : 0) === 1 ? '' : 's'} · Doors ${(Array.isArray(overlayGeometry.doors) ? overlayGeometry.doors.length : 0)} · Platforms ${(Array.isArray(overlayGeometry.platforms) ? overlayGeometry.platforms.length : 0)}`
          : '';
        const runtimeReviewMarkup = runtimeReview?.screenshot_url
          ? (() => {
              const rrUrl = assetUrlWithVersion(
                runtimeReview.screenshot_url || '',
                runtimeReview.generated_at || bespokeManifest.generated_at || ''
              );
              return `
            <div class="rw-runtime-review-block">
              <button type="button" class="rw-environment-asset-open rw-runtime-review-thumb" data-rw-asset-src="${escapeHtml(rrUrl)}" aria-label="View runtime review full size">
                <img src="${escapeHtml(rrUrl)}" alt="Runtime review screenshot" />
              </button>
              <div class="rw-runtime-review-meta">
                <span>${escapeHtml(`Runtime review · ${runtimeReview.status || 'idle'}`)}</span>
                <small>${escapeHtml(`${runtimeReview.review_mode || 'review'}${runtimeReview.capture_issue ? ` · ${runtimeReview.capture_issue}` : ''}`)}</small>
                <button type="button" class="btn-secondary rw-runtime-review-open-game">Open in game</button>
              </div>
            </div>`;
            })()
          : '';
        const reviewBlockedSlots = Array.isArray(runtimeReview?.fail_reasons) && runtimeReview.fail_reasons.includes('slot_generation_failed');
        const slotGenFailed = reviewBlockedSlots;
        const browserCaptureReviewTip =
          (Array.isArray(runtimeReview?.fail_reasons) && runtimeReview.fail_reasons.includes('browser_capture_required'))
          || (Array.isArray(runtimeReview?.warning_reasons) && runtimeReview.warning_reasons.includes('browser_capture_degraded'))
            ? ' Tip: true runtime screenshots need headless Chrome/Chromium (ROOM_ENVIRONMENT_REVIEW_BROWSER) and the game reachable at ROOM_ENVIRONMENT_REVIEW_BASE_URL (workbench port, e.g. 8766). If capture fails, the workbench falls back to a static composite — check the server log for capture_runtime_review errors.'
            : '';
        const reviewText = runtimeReview?.status
          ? (slotGenFailed
              ? `Build blocked: one or more bespoke slots failed image generation (runtime screenshot review was not run).${Array.isArray(runtimeReview.fail_reasons) && runtimeReview.fail_reasons.length ? ` Reasons: ${runtimeReview.fail_reasons.map((item) => humanizeRoomWizardLabel(item)).join(', ')}.` : ''}${validationErrs.length ? ` Details: ${validationErrs.slice(0, 8).map((item) => humanizeRoomWizardLabel(item)).join('; ')}.` : ''}`
              : `Runtime review: ${describeRoomWizardRuntimeReviewStatus(runtimeReview.status || 'pending')}${Array.isArray(runtimeReview.fail_reasons) && runtimeReview.fail_reasons.length ? ` · ${runtimeReview.fail_reasons.map((item) => humanizeRoomWizardLabel(item)).join(', ')}` : ''}${reviewBlockedSlots && validationErrs.length ? ` · ${validationErrs.slice(0, 5).map((item) => humanizeRoomWizardLabel(item)).join('; ')}` : ''}${browserCaptureReviewTip}`)
          : 'Runtime review: not run yet';
        const assetThumbs = ['ready', 'failed'].includes(bespokeManifest.status)
          ? Object.values(bespokeManifest.assets || {}).map((item) => {
              const vErrs = item && item.validation && Array.isArray(item.validation.errors) ? item.validation.errors : [];
              const lastAtt = Array.isArray(item.attempts) && item.attempts.length ? item.attempts[item.attempts.length - 1] : null;
              const geminiErr = lastAtt && typeof lastAtt.gemini_error === 'string' ? lastAtt.gemini_error.trim() : '';
              const failHint = !item.url && (vErrs.length
                ? vErrs.join(', ')
                : (geminiErr || (lastAtt && lastAtt.status ? String(lastAtt.status) : '')));
              const sub = item.url
                ? String(item.generation_source || 'ok')
                : [String(item.generation_source || 'failed'), failHint].filter(Boolean).join(' · ');
              const slotIdRaw = String(item.slot_id || '').trim();
              const slotIdAttr = escapeHtml(slotIdRaw);
              const canIterate = Boolean(item.url && String(item.generation_source || '').toLowerCase() === 'ai');
              const slotActions = slotIdRaw
                ? `<div class="rw-bespoke-slot-actions">
                    <button type="button" data-rw-bespoke-slot-action="regen" data-rw-bespoke-slot-id="${slotIdAttr}" title="Rebuild only this slot from the approved preview">Regenerate</button>
                    ${canIterate ? `<button type="button" data-rw-bespoke-slot-action="iterate" data-rw-bespoke-slot-id="${slotIdAttr}" title="Use the current image as the first reference for Gemini">Iterate</button>` : ''}
                  </div>`
                : '';
              const assetThumbUrl = item.url ? assetUrlWithVersion(item.url || '', bespokeManifest.generated_at || '') : '';
              const openFullLabel = `Open full size: ${item.slot_id || item.component_type || 'asset'}`;
              return `
                <div class="rw-environment-asset-thumb">
                  ${item.url
                    ? `<button type="button" class="rw-environment-asset-open" data-rw-asset-src="${escapeHtml(assetThumbUrl)}" aria-label="${escapeHtml(openFullLabel)}">
                        <img src="${escapeHtml(assetThumbUrl)}" alt="${escapeHtml(item.component_type || 'asset')}" />
                      </button>`
                    : `<div class="rw-environment-asset-thumb-empty">${escapeHtml(String(item.generation_source || 'missing'))}</div>`}
                  <span>${escapeHtml(item.slot_id || item.component_type || 'asset')}</span>
                  <small>${escapeHtml(sub.slice(0, 220))}</small>
                  ${slotActions}
                </div>`;
            }).join('')
          : '';

        const stagePillClass = (statusText) => {
          const value = String(statusText || '').toLowerCase();
          if (['locked', 'ready', 'complete', 'approved', 'pass'].includes(value)) return 'rw-stage-pill rw-stage-pill--good';
          if (['blocked', 'failed', 'fail', 'error'].includes(value)) return 'rw-stage-pill rw-stage-pill--error';
          if (['warning', 'partial', 'pending', 'proposal', 'draft', 'running', 'generating', 'idle', 'empty'].includes(value)) return 'rw-stage-pill rw-stage-pill--warning';
          return 'rw-stage-pill';
        };
        const humanizeStageText = (value) => humanizeRoomWizardLabel(value);
        const compactRefDetail = (ref) => {
          if (!ref || typeof ref !== 'object') return '';
          if (ref.layer) return `Layer: ${humanizeStageText(ref.layer)}`;
          if (ref.zone_type) return `Zone: ${humanizeStageText(ref.zone_type)}`;
          if (ref.code) return `Area: ${humanizeStageText(ref.code)}`;
          if (ref.artifact) return `Source: ${humanizeStageText(ref.artifact)}`;
          return '';
        };
        const stageList = (items, emptyText) => {
          const list = Array.isArray(items) ? items.filter(Boolean) : [];
          if (!list.length) return `<p class="rw-environment-stage-empty">${escapeHtml(emptyText)}</p>`;
          const seen = new Set();
          const formatItem = (item) => {
            if (item && typeof item === 'object') {
              const severity = String(item.severity || '').trim();
              const code = humanizeStageText(item.code || '');
              const message = String(item.message || '').trim();
              const ref = compactRefDetail(item.ref);
              const parts = [
                severity ? severity.toUpperCase() : '',
                message || code,
                ref,
              ].filter(Boolean);
              return parts.join(' · ');
            }
            return humanizeStageText(item);
          };
          const formatted = list
            .map((item) => formatItem(item))
            .filter((item) => {
              if (!item || seen.has(item)) return false;
              seen.add(item);
              return true;
            });
          return `<ul class="rw-environment-stage-list">${formatted.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
        };
        if (buildButton) {
          buildButton.disabled = !preview.approved_image_id;
          buildButton.textContent = bespokeManifest.status === 'ready'
            ? 'Rebuild final room assets'
            : bespokeManifest.status === 'failed'
              ? 'Retry final room assets'
              : 'Build final room assets';
        }

        const overlayMarkup = pipelineVersion === 'v3'
          ? renderRoomWizardResultsOverlay({
            ...envState,
            environment_manifest: manifestDoc,
            validation_report: validationDoc,
          }, toggleState)
          : '';

        const generatedImagesSection = (runtimeReviewMarkup || assetThumbs)
          ? `<div class="rw-env-generated-images-surface" aria-label="Generated room images">
              <div class="rw-env-generated-images-head">
                <p class="rw-environment-preview-label">Generated images</p>
                <p class="rw-environment-stage-copy rw-env-generated-images-lede">In-game capture and exported room images for a quick visual pass. Regenerate one slot, or use <strong>Iterate</strong> on AI-built pieces to send the current image back as the primary reference.</p>
              </div>
              ${runtimeReviewMarkup ? `<div class="rw-runtime-review-row">${runtimeReviewMarkup}</div>` : ''}
              ${assetThumbs ? `<div class="rw-environment-asset-grid">${assetThumbs}</div>` : ''}
            </div>`
          : '';

        target.innerHTML = `
          <section class="rw-environment-output-card">
            <div class="rw-environment-stage-hero">
              <div class="rw-environment-stage-metahead">
                <div>
                  <p class="rw-environment-preview-label">Build summary</p>
                  <strong>${escapeHtml(spec.theme_name || envState?.themeId || 'Untitled room environment')}</strong>
                </div>
                <div class="rw-environment-status-row">
                  <span class="${stagePillClass(bespokeManifest.status || 'idle')}">${escapeHtml(bespokeManifest.status || 'idle')}</span>
                  <span class="${stagePillClass(runtimeReview.status || 'pending')}">${escapeHtml(`Runtime ${runtimeReview.status || 'pending'}`)}</span>
                </div>
              </div>
            </div>
            ${generatedImagesSection}
            <details class="rw-env-review-disclosure">
              <summary>
                <p class="rw-environment-preview-label">Build details</p>
                <strong>Theme, pipeline, assets, and references</strong>
              </summary>
              <p class="rw-environment-stage-copy">${escapeHtml(`${bits.join(' · ')} · ${assetText} · ${reviewText}`)}</p>
              <div class="rw-environment-chip-row">
                <span class="rw-environment-chip">${escapeHtml(`Variation seed: ${spec.seed || 'not set'}`)}</span>
                <span class="rw-environment-chip">${escapeHtml(`${refUploads.length} reference image${refUploads.length === 1 ? '' : 's'}`)}</span>
                <span class="rw-environment-chip">${escapeHtml(`${pinnedRefs.length} pinned for this room`)}</span>
                <span class="rw-environment-chip">${escapeHtml(`Room profile: ${envState?.themeId || 'custom'}`)}</span>
              </div>
            </details>
            <details class="rw-env-review-disclosure">
              <summary>
                <p class="rw-environment-preview-label">Build checklist</p>
                <strong>Build checklist</strong>
              </summary>
              <p class="rw-environment-stage-copy">Open each row to see how that part of the build is doing before you rebuild or playtest.</p>
              <div class="rw-environment-stage-grid">
              <article class="rw-environment-stage-card">
                <div class="rw-environment-stage-head">
                  <div>
                    <p class="rw-environment-preview-label">1. Visual style</p>
                    <strong>${escapeHtml(spec.theme_name || stylepackSummary.stylepack_id || 'Room stylepack')}</strong>
                  </div>
                  <span class="${stagePillClass(stylepackSummary.status || (spec.lock_stylepack ? 'locked' : 'proposal'))}">${escapeHtml(stylepackSummary.status || (spec.lock_stylepack ? 'locked' : 'proposal'))}</span>
                </div>
                <p class="rw-environment-stage-copy">${escapeHtml(`Uploads-first reference pack with ${refUploads.length} item(s), ${pinnedRefs.length} pinned to the stylepack, ${stylepackSummary.material_count || 0} material tags, ${stylepackSummary.shape_count || 0} shape rules, and ${stylepackSummary.forbidden_trait_count || 0} forbidden drift traits.`)}</p>
                ${refUploads.length ? `<div class="rw-environment-chip-row">${refUploads.slice(0, 8).map((item) => `<span class="rw-environment-chip">${escapeHtml(item.label || item.file_name || 'Reference')}</span>`).join('')}</div>` : '<p class="rw-environment-stage-empty">No uploaded references yet.</p>'}
              </article>
              <article class="rw-environment-stage-card">
                <div class="rw-environment-stage-head">
                  <div>
                    <p class="rw-environment-preview-label">2. Walkable layout</p>
                    <strong>${escapeHtml(`${semanticsSummary.counts?.top_count || 0} tops · ${semanticsSummary.counts?.opening_count || 0} openings`)}</strong>
                  </div>
                  <span class="${stagePillClass(semanticsSummary.status || 'idle')}">${escapeHtml(semanticsSummary.status || 'idle')}</span>
                </div>
                <p class="rw-environment-stage-copy">${escapeHtml(`${plannerCoverageText || 'No planner coverage yet.'}${assemblyOverlayText ? ` · ${assemblyOverlayText}` : ''}`)}</p>
                ${Array.isArray(semanticsSummary.overlay_keys) && semanticsSummary.overlay_keys.length ? `<div class="rw-environment-chip-row">${semanticsSummary.overlay_keys.map((item) => `<span class="rw-environment-chip">${escapeHtml(item)}</span>`).join('')}</div>` : '<p class="rw-environment-stage-empty">Overlay geometry has not been derived yet.</p>'}
              </article>
              <article class="rw-environment-stage-card">
                <div class="rw-environment-stage-head">
                  <div>
                    <p class="rw-environment-preview-label">3. Room pieces</p>
                    <strong>${escapeHtml(`${kitSummary.summary?.component_count || 0} components`)}</strong>
                  </div>
                  <span class="${stagePillClass(kitSummary.status || 'idle')}">${escapeHtml(kitSummary.status || 'idle')}</span>
                </div>
                <p class="rw-environment-stage-copy">${escapeHtml(`Structural ${kitSummary.summary?.structural_count || 0} · Background ${kitSummary.summary?.background_count || 0} · Decor ${kitSummary.summary?.decor_count || 0}`)}</p>
                ${componentSchemaChips ? `<div class="rw-environment-chip-row">${componentSchemaChips}</div>` : '<p class="rw-environment-stage-empty">Component schema data has not been built yet.</p>'}
              </article>
              <article class="rw-environment-stage-card">
                <div class="rw-environment-stage-head">
                  <div>
                    <p class="rw-environment-preview-label">4. Scene layout</p>
                    <strong>${escapeHtml(`${manifestSummary.generation_metadata?.structural_count || 0} structural placements`)}</strong>
                  </div>
                  <span class="${stagePillClass(manifestSummary.status || bespokeManifest.status || 'idle')}">${escapeHtml(manifestSummary.status || bespokeManifest.status || 'idle')}</span>
                </div>
                <p class="rw-environment-stage-copy">${escapeHtml(`${assetText} · ${plannerCoverageText || 'No planner summary yet.'}`)}</p>
                ${slotGroupChips || assemblyPlanChips ? `<div class="rw-environment-chip-row">${slotGroupChips}${assemblyPlanChips}</div>` : '<p class="rw-environment-stage-empty">Manifest placements are not ready yet.</p>'}
              </article>
              <article class="rw-environment-stage-card rw-environment-stage-card--wide">
                <div class="rw-environment-stage-head">
                  <div>
                    <p class="rw-environment-preview-label">5. Quality check</p>
                    <strong>${escapeHtml(describeRoomWizardApprovalStatus(reviewState.approval_status || 'draft'))}</strong>
                  </div>
                  <span class="${stagePillClass(reviewValidation.status || runtimeReview.status || 'pending')}">${escapeHtml(describeRoomWizardValidationStatus(reviewValidation.status || runtimeReview.status || 'pending'))}</span>
                </div>
                <p class="rw-environment-stage-copy">${escapeHtml(`${reviewStateText || 'Validation has not run yet.'} · ${reviewText}`)}</p>
                <div class="rw-environment-stage-grid">
                  <div class="rw-environment-stage-summary">
                    <div class="rw-environment-stage-head">
                      <strong>Problems to fix</strong>
                    </div>
                    ${stageList([...(validationSummary.blockers || []), ...(validationSummary.warnings || []), ...validationErrs], 'No warnings or blockers recorded yet.')}
                  </div>
                  <div class="rw-environment-stage-summary">
                    <div class="rw-environment-stage-head">
                      <strong>Missing or unclear parts</strong>
                    </div>
                    ${stageList([...(validationSummary.unresolved_surfaces || []), ...(plannerCoverage.missing_slots || [])], 'No unresolved surfaces recorded yet.')}
                  </div>
                </div>
                ${(coverageChips || staleChips || componentChips) ? `<div class="rw-environment-chip-row">${coverageChips}${staleChips}${componentChips}</div>` : ''}
              </article>
              </div>
            </details>
            ${overlayMarkup ? `<details class="rw-env-review-disclosure"><summary><strong>Room overlay (advanced)</strong></summary>${overlayMarkup}</details>` : ''}
          </section>`;
        syncRoomWizardResultsToggles();
        bindRoomWizardResultsToggleInputs();
      }

      function renderRoomWizardPreviewGalleryInto(gallery, previewState) {
        if (!gallery) return;
        const items = Array.isArray(previewState?.images) ? previewState.images : [];
        if (!items.length) {
          if (roomWizardHasGeneratedPreview(previewState)) {
            gallery.innerHTML = '<div class="rw-reference-item"><p class="rw-environment-stage-empty">Preview is ready. Candidate cards will appear here as soon as the preview image list finishes syncing.</p></div>';
          } else {
            gallery.innerHTML = '';
          }
          return;
        }
        const approved = previewState?.approved_image_id || null;
        const version = previewState?.last_generated_at || '';
        gallery.innerHTML = items.map((item) => {
          const active = approved && approved === item.preview_id ? ' active' : '';
          const imgHref = assetUrlWithVersion(item.url || '', version || item.preview_id || '');
          const previewLabel = item.label || 'Room preview';
          const openLabel = `Open full-size preview in a popup: ${previewLabel}`;
          const levelText = (item.render_level || '').toUpperCase();
          const imgAlt = escapeHtml(previewLabel);
          const imgSrc = escapeHtml(imgHref);
          const dataSrcAttr = escapeHtml(imgHref);
          const mediaMarkup = imgHref
            ? `<button type="button" class="rw-preview-card-open" data-rw-asset-src="${dataSrcAttr}" title="View full size (dark background)" aria-label="${escapeHtml(openLabel)}"><img src="${imgSrc}" alt="${imgAlt}" loading="lazy" /></button>`
            : `<div class="rw-preview-card-media-missing" role="img" aria-label="${imgAlt}">Preview unavailable</div>`;
          return `
            <article class="rw-preview-card${active}">
              <div class="rw-preview-card-media">
                ${mediaMarkup}
              </div>
              <div class="rw-preview-card-copy">
                <div class="rw-preview-card-title"><strong>${escapeHtml(item.label || 'Preview')}</strong></div>
                <span class="rw-preview-card-level">${escapeHtml(levelText)}</span>
              </div>
              <button type="button" class="btn-secondary rw-preview-approve" data-preview-id="${escapeHtml(item.preview_id || '')}">
                ${active ? 'Approved' : 'Approve Preview'}
              </button>
            </article>`;
        }).join('');
        gallery.querySelectorAll('.rw-preview-approve').forEach((btn) => {
          btn.addEventListener('click', () => approveRoomWizardPreview(btn.dataset.previewId || ''));
        });
        const room = getRoomWizardRoom();
        if (PROJECT_ID && room) {
          postRoomWizardFeedback(room, 'preview_viewed');
        }
      }

      function renderRoomWizardPreviewGallery(previewState) {
        const gallery = document.getElementById('roomWizardPreviewGallery');
        const lookGallery = document.getElementById('roomWizardLookPreviewGallery');
        const lookStrip = document.getElementById('roomWizardLookPreviewStrip');
        const items = Array.isArray(previewState?.images) ? previewState.images : [];
        if (lookStrip) lookStrip.hidden = !items.length && !roomWizardHasGeneratedPreview(previewState);
        renderRoomWizardPreviewGalleryInto(gallery, previewState);
        renderRoomWizardPreviewGalleryInto(lookGallery, previewState);
      }

      function stopRoomWizardWaitbar(slot, finalPercent = 100) {
        const root = document.getElementById(slot === 'art-direction' ? 'roomWizardArtDirectionProgress' : 'roomWizardCopilotProgress');
        const fill = document.getElementById(slot === 'art-direction' ? 'roomWizardArtDirectionProgressFill' : 'roomWizardCopilotProgressFill');
        const pct = document.getElementById(slot === 'art-direction' ? 'roomWizardArtDirectionProgressPct' : 'roomWizardCopilotProgressPct');
        const timer = RoomEditor.State.roomWizard?.progressTimers?.[slot];
        if (timer) {
          clearInterval(timer);
          RoomEditor.State.roomWizard.progressTimers[slot] = null;
        }
        if (fill) fill.style.width = `${Math.max(0, Math.min(100, finalPercent))}%`;
        if (pct) pct.textContent = `${Math.round(Math.max(0, Math.min(100, finalPercent)))}%`;
        if (root) {
          window.setTimeout(() => {
            root.hidden = true;
          }, 180);
        }
        clearActivity();
      }

      function roomWizardTaskId(room) {
        if (!room?.id) return '';
        if (!RoomEditor.State.roomWizard.taskIds) RoomEditor.State.roomWizard.taskIds = {};
        if (!RoomEditor.State.roomWizard.taskIds[room.id]) {
          RoomEditor.State.roomWizard.taskIds[room.id] = `task-${room.id}-${Date.now().toString(36)}`;
        }
        return RoomEditor.State.roomWizard.taskIds[room.id];
      }

      function roomWizardReasonCodes() {
        const value = String(document.getElementById('roomWizardHelpfulnessReason')?.value || '').trim();
        return value ? [value] : [];
      }

      function roomWizardCommaList(value) {
        return String(value || '')
          .split(',')
          .map((item) => String(item || '').trim())
          .filter(Boolean);
      }

      function roomWizardSuggestionId(room) {
        return String(room?.environment?.preview?.suggestion_id || room?.environment?.ai_helpfulness?.active_suggestion_id || '').trim();
      }

      function roomWizardAnalyticsContext(room, extra = {}) {
        return {
          session_id: ROOM_AI_SESSION_ID,
          task_id: roomWizardTaskId(room),
          tool_surface: 'room-layout-editor:environment-builder',
          workflow_step: `scope:${RoomEditor.State.workflowScope}|phase:${RoomEditor.State.roomWizard.phase}|tab:${RoomEditor.State.roomWizard.lastEnvTab}|env-step:${RoomEditor.State.roomWizard.envStep || 'describe'}`,
          reason_codes: roomWizardReasonCodes(),
          ...extra,
        };
      }

      async function postRoomWizardFeedback(room, eventType, extra = {}, options = {}) {
        if (!PROJECT_ID || !room?.id) return null;
        const payload = {
          event_type: eventType,
          suggestion_id: roomWizardSuggestionId(room),
          ...roomWizardAnalyticsContext(room, extra),
        };
        const url = projectRoomEnvironmentFeedbackApiUrl(room.id);
        if (!url) return null;
        if (options.keepalive && navigator.sendBeacon) {
          const body = JSON.stringify(payload);
          const blob = new Blob([body], { type: 'application/json' });
          navigator.sendBeacon(url, blob);
          return null;
        }
        try {
          const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            keepalive: !!options.keepalive,
          });
          const json = await res.json().catch(() => ({}));
          if (json?.environment && room?.environment) {
            room.environment = json.environment;
          }
          return json;
        } catch (_) {
          return null;
        }
      }

      function setRoomWizardEnvTab(which) {
        const map = {
          setup: { tab: 'rwEnvTabSetup', panel: 'rwEnvPanelSetup' },
          results: { tab: 'rwEnvTabResults', panel: 'rwEnvPanelResults' }
        };
        const order = ['setup', 'results'];
        const pick = map[which] || map.setup;
        order.forEach((key) => {
          const ids = map[key];
          const p = document.getElementById(ids.panel);
          const on = ids.panel === pick.panel;
          if (p) p.hidden = !on;
        });
        const prior = RoomEditor.State.roomWizard.lastEnvTab;
        RoomEditor.State.roomWizard.lastEnvTab = which;
        const room = getRoomWizardRoom();
        if (PROJECT_ID && room && prior === 'results' && which !== 'results') {
          postRoomWizardFeedback(room, 'workflow_backtrack');
        }
      }

      function normalizeRoomWizardEnvStep(step) {
        const legacyToDescribe = new Set(['look', 'details', 'references', 'parts']);
        if (legacyToDescribe.has(step)) return 'describe';
        return step === 'review' ? 'review' : 'describe';
      }

      function setRoomWizardEnvStep(step) {
        const nextStep = normalizeRoomWizardEnvStep(step);
        RoomEditor.State.roomWizard.envStep = nextStep;
        const stepPanels = {
          describe: 'rwEnvStepPanelDescribe',
          review: 'rwEnvStepPanelReview'
        };
        Object.entries(stepPanels).forEach(([key, panelId]) => {
          const panel = document.getElementById(panelId);
          if (panel) panel.hidden = key !== nextStep;
        });
        document.querySelectorAll('[data-rw-env-step]').forEach((btn) => {
          const on = btn.getAttribute('data-rw-env-step') === nextStep;
          btn.setAttribute('aria-selected', on ? 'true' : 'false');
          btn.classList.toggle('rw-env-step-btn--active', on);
        });
        const room = getRoomWizardRoom();
        if (room?.environment) {
          if (nextStep === 'describe' || nextStep === 'review') {
            renderRoomWizardEnvironmentPreview(room.environment);
            renderRoomWizardPreviewGallery(room.environment.preview || {});
          }
          if (nextStep === 'review') {
            renderRoomWizardEnvironmentOutputSummary(room.environment);
          }
        }
        setRoomWizardEnvTab(nextStep === 'review' ? 'results' : 'setup');
      }

      function initRoomWizardEnvTabs() {
        document.querySelectorAll('[data-rw-env-step]').forEach((btn) => {
          btn.addEventListener('click', () => setRoomWizardEnvStep(btn.getAttribute('data-rw-env-step') || 'describe'));
        });
        document.querySelectorAll('[data-rw-env-step-target]').forEach((btn) => {
          btn.addEventListener('click', () => setRoomWizardEnvStep(btn.getAttribute('data-rw-env-step-target') || 'describe'));
        });
        setRoomWizardEnvStep('describe');
      }

      function updateRoomWizardBiomePackSummary() {
        const el = document.getElementById('roomWizardBiomePackSummary');
        if (!el) return;
        if (!PROJECT_ID) {
          el.textContent =
            'Open a project with locked art direction to generate Gemini biome PNGs (background, midground, floor, platform, door).';
          return;
        }
        const packs = RoomEditor.State.artDirection?.biome_packs;
        const pack = Array.isArray(packs) && packs[0] ? packs[0] : null;
        if (!pack) {
          el.textContent = 'Save art direction to seed a biome pack, then generate visuals.';
          return;
        }
        const bid = pack.biome_id || 'biome';
        const label = String(pack.label || bid).trim() || bid;
        const n = Array.isArray(pack.template_library) ? pack.template_library.length : 0;
        el.textContent = `Active pack: ${label} (${bid}) · ${n} template layer${n === 1 ? '' : 's'}. Frozen concepts are used as references when available. Confirm to overwrite PNGs on disk.`;
      }

      /**
       * Mirrors scripts/room_environment_system._component_adaptation_mode for bespoke slots:
       * only "gemini" adaptation calls the image API; direct/stretch use template paths.
       */
      function roomWizardBespokeComponentUsesGemini(componentType) {
        const ct = String(componentType || '');
        if (ct === 'room_shell_foreground') return true;
        const direct = new Set([
          'background_plate',
          'midground_frame',
          'midground_side_frame',
          'door_piece',
          'door_frame',
        ]);
        if (direct.has(ct)) return false;
        const stretch = new Set([
          'foreground_frame',
          'primary_floor_piece',
          'hero_platform_piece',
          'hero_platform_top',
          'hero_platform_face',
          'pit_interior',
        ]);
        if (stretch.has(ct)) return false;
        return true;
      }

      /**
       * Counts bespoke plan entries that trigger Gemini (matches server loop).
       * Single-slot regen / iterate: always 1 API-bound slot from the UI's perspective.
       */
      function roomWizardEstimateBespokeGeminiSlotCount(room, opts) {
        const options = opts || {};
        if (options.slotId) return 1;
        const plan = room?.environment?.runtime?.bespoke_asset_manifest?.generation_plan;
        if (Array.isArray(plan) && plan.length) {
          let n = 0;
          for (let i = 0; i < plan.length; i++) {
            const row = plan[i];
            if (roomWizardBespokeComponentUsesGemini(row && row.component_type)) n += 1;
          }
          return Math.max(1, n);
        }
        if (options.forFullBuild) {
          const plats = Array.isArray(room?.platforms) ? room.platforms.length : 0;
          const pits = Array.isArray(room?.pits || room?.voidSpans)
            ? (room.pits || room.voidSpans).length
            : 0;
          const extras = Math.max(0, plats - 1) + pits;
          return Math.min(20, Math.max(7, 7 + extras));
        }
        return 1;
      }

      /**
       * Wall-clock estimate: geminiSlots × (baseline × multiref factor × expected attempts) + tail.
       * Research: public Gemini 2.5 Flash Image writeups often cite ~3–8s for light single-image
       * requests; bespoke jobs send several reference PNGs and target ~1600×1200-class outputs, so
       * we scale well above that. Server may run up to 3 validation attempts per slot — use ~1.45
       * mean attempts so the bar is neither wildly pessimistic nor optimistic.
       */
      function roomWizardEstimateBespokeAssetWaitMs(room, opts) {
        const options = opts || {};
        const geminiSlots = roomWizardEstimateBespokeGeminiSlotCount(room, options);
        const RW_GEMINI_LIGHT_REQUEST_UPPER_SEC = 8;
        const RW_GEMINI_BESPOKE_MULTIREF_RESOLUTION_FACTOR = 12;
        const RW_GEMINI_EXPECTED_ATTEMPTS = 1.45;
        const RW_BESPOKE_TAIL_SEC = 40;
        const secPerSlot =
          RW_GEMINI_LIGHT_REQUEST_UPPER_SEC *
          RW_GEMINI_BESPOKE_MULTIREF_RESOLUTION_FACTOR *
          RW_GEMINI_EXPECTED_ATTEMPTS;
        const totalSec = geminiSlots * secPerSlot + RW_BESPOKE_TAIL_SEC;
        return Math.round(Math.max(45000, totalSec * 1000));
      }

      function startRoomWizardWaitbar(slot, detail, estimatedDurationMs) {
        if (slot === 'copilot') setRoomWizardEnvTab('results');
        const root = document.getElementById(slot === 'art-direction' ? 'roomWizardArtDirectionProgress' : 'roomWizardCopilotProgress');
        const fill = document.getElementById(slot === 'art-direction' ? 'roomWizardArtDirectionProgressFill' : 'roomWizardCopilotProgressFill');
        const pct = document.getElementById(slot === 'art-direction' ? 'roomWizardArtDirectionProgressPct' : 'roomWizardCopilotProgressPct');
        const label = document.getElementById(slot === 'art-direction' ? 'roomWizardArtDirectionProgressDetail' : 'roomWizardCopilotProgressDetail');
        stopRoomWizardWaitbar(slot, 6);
        if (label) label.textContent = detail || 'Working…';
        if (root) root.hidden = false;
        let value = 6;
        if (fill) fill.style.width = `${value}%`;
        if (pct) pct.textContent = `${value}%`;
        setActivity({
          label: slot === 'art-direction' ? 'Art Direction Processing' : 'Environment Processing',
          detail: detail || 'Working…',
          state: 'Working',
          percent: value
        });
        const useTimed =
          typeof estimatedDurationMs === 'number' && estimatedDurationMs >= 15000 && slot === 'copilot';
        if (useTimed) {
          const startTs = Date.now();
          RoomEditor.State.roomWizard.progressTimers[slot] = window.setInterval(() => {
            const elapsed = Date.now() - startTs;
            const t = Math.min(1, elapsed / estimatedDurationMs);
            value = Math.min(92, 6 + t * 86);
            if (fill) fill.style.width = `${value}%`;
            if (pct) pct.textContent = `${Math.round(value)}%`;
            setActivity({
              label: 'Environment Processing',
              detail: detail || 'Working…',
              state: 'Working',
              percent: value
            });
          }, 380);
          return;
        }
        RoomEditor.State.roomWizard.progressTimers[slot] = window.setInterval(() => {
          value = Math.min(92, value + (value < 30 ? 8 : value < 60 ? 5 : 3));
          if (fill) fill.style.width = `${value}%`;
          if (pct) pct.textContent = `${Math.round(value)}%`;
          setActivity({
            label: slot === 'art-direction' ? 'Art Direction Processing' : 'Environment Processing',
            detail: detail || 'Working…',
            state: 'Working',
            percent: value
          });
        }, 420);
      }

      function renderRoomWizardDirectionConceptBoard() {
        const grid = document.getElementById('roomWizardDirectionConceptBoardGrid');
        const status = document.getElementById('roomWizardGenerateArtDirectionConceptsStatus');
        if (!grid || !status) return;
        if (!PROJECT_ID) {
          grid.innerHTML = '';
          status.textContent = 'Open this room through a project to generate art direction concepts.';
          return;
        }
        const items = Array.isArray(RoomEditor.State.artDirectionConceptOptions) ? RoomEditor.State.artDirectionConceptOptions : [];
        if (!items.length) {
          grid.innerHTML = '';
          status.textContent = 'No art direction concepts yet. Generate a first concept board from the direction summary above.';
          return;
        }
        const selectedIds = new Set(Array.isArray(RoomEditor.State.artDirection?.frozen_concept_ids) ? RoomEditor.State.artDirection.frozen_concept_ids : []);
        const boardStatus = RoomEditor.State.artDirection?.concept_board?.generation_error;
        status.textContent = boardStatus === 'gemini_image_unavailable_fallback_used'
          ? 'Gemini image generation was unavailable, so the concept board used local fallback images.'
          : `${items.length} art direction concept${items.length === 1 ? '' : 's'} ready. Click cards below to freeze the strongest anchors.`;
        grid.innerHTML = items.map((item) => {
          const active = selectedIds.has(item.concept_id) ? ' active' : '';
          return `
            <article class="rw-direction-concept-card${active}">
              <div class="rw-direction-concept-media">
                <img src="${escapeHtml(item.url || '')}" alt="${escapeHtml(item.label || item.concept_id || 'Art direction concept')}" />
              </div>
              <div class="rw-direction-concept-copy">
                <strong>${escapeHtml(item.label || 'Concept')}</strong>
                <p>${escapeHtml(item.prompt || '')}</p>
              </div>
              <button type="button" class="btn-secondary rw-direction-concept-toggle" data-concept-id="${escapeHtml(item.concept_id || '')}">
                ${active ? 'Frozen Anchor' : 'Freeze As Anchor'}
              </button>
            </article>
          `;
        }).join('');
        grid.querySelectorAll('.rw-direction-concept-toggle').forEach((btn) => {
          btn.addEventListener('click', () => {
            const conceptId = btn.dataset.conceptId || '';
            if (!conceptId) return;
            const direction = RoomEditor.State.artDirection || {};
            const current = Array.isArray(direction.frozen_concept_ids) ? [...direction.frozen_concept_ids] : [];
            const set = new Set(current);
            if (set.has(conceptId)) set.delete(conceptId);
            else if (set.size < 3) set.add(conceptId);
            else {
              const saveStatus = document.getElementById('roomWizardArtDirectionStatus');
              if (saveStatus) saveStatus.textContent = 'Keep at most 3 frozen anchors so the art direction stays coherent.';
              return;
            }
            RoomEditor.State.artDirection = { ...direction, frozen_concept_ids: Array.from(set) };
            renderRoomWizardDirectionConceptBoard();
            renderRoomWizardFrozenConceptGrid();
          });
        });
      }

      function renderRoomWizardFrozenConceptGrid() {
        const grid = document.getElementById('roomWizardFrozenConceptGrid');
        const summary = document.getElementById('roomWizardFrozenConceptsSummary');
        if (!grid || !summary) return;
        const projectMode = !!PROJECT_ID;
        if (!projectMode) {
          grid.innerHTML = '';
          summary.textContent = 'Open this room through a workbench project to freeze concept anchors.';
          return;
        }
        const options = Array.isArray(RoomEditor.State.artDirectionConceptOptions) ? RoomEditor.State.artDirectionConceptOptions : [];
        const selectedIds = new Set(Array.isArray(RoomEditor.State.artDirection?.frozen_concept_ids) ? RoomEditor.State.artDirection.frozen_concept_ids : []);
        if (!options.length) {
          grid.innerHTML = '';
          summary.textContent = 'Generate an art direction concept board above, then freeze the concepts you want to keep referencing.';
          return;
        }
        const selected = options.filter((item) => selectedIds.has(item.concept_id));
        const selectedCount = selected.length;
        summary.textContent = selectedCount
          ? `Frozen anchors: ${selected.map((item) => item.label || item.concept_id).join(', ')}.`
          : 'Choose 1-3 concepts to freeze as recurring visual anchors for the project.';
        grid.innerHTML = options.map((item) => {
          const active = selectedIds.has(item.concept_id) ? ' active' : '';
          const status = item.approved ? 'Approved' : (item.selected ? 'Selected' : 'Available');
          return `
            <button type="button" class="rw-frozen-concept${active}" data-concept-id="${escapeHtml(item.concept_id || '')}" aria-pressed="${selectedIds.has(item.concept_id) ? 'true' : 'false'}">
              <span class="rw-frozen-concept-media">
                <img src="${escapeHtml(item.url || '')}" alt="${escapeHtml(item.label || item.concept_id || 'Concept anchor')}" />
              </span>
              <span class="rw-frozen-concept-copy">
                <strong>${escapeHtml(item.label || item.concept_id || 'Concept')}</strong>
                <span>${escapeHtml(status)}</span>
              </span>
            </button>
          `;
        }).join('');
        grid.querySelectorAll('[data-concept-id]').forEach((btn) => {
          btn.addEventListener('click', () => {
            const conceptId = btn.dataset.conceptId || '';
            if (!conceptId) return;
            const direction = RoomEditor.State.artDirection || {};
            const current = Array.isArray(direction.frozen_concept_ids) ? [...direction.frozen_concept_ids] : [];
            const set = new Set(current);
            if (set.has(conceptId)) {
              set.delete(conceptId);
            } else if (set.size < 3) {
              set.add(conceptId);
            } else {
              const status = document.getElementById('roomWizardArtDirectionStatus');
              if (status) status.textContent = 'Keep at most 3 frozen concepts so the visual direction stays focused.';
              return;
            }
            RoomEditor.State.artDirection = { ...direction, frozen_concept_ids: Array.from(set) };
            renderRoomWizardFrozenConceptGrid();
          });
        });
      }

      function renderRoomWizardArtDirectionUi() {
        const card = document.getElementById('roomWizardArtDirectionCard');
        const hint = document.getElementById('roomWizardArtDirectionHint');
        const sel = document.getElementById('roomWizardArtDirectionTemplate');
        const summary = document.getElementById('roomWizardArtDirectionSummary');
        const negative = document.getElementById('roomWizardArtDirectionNegative');
        const btn = document.getElementById('roomWizardArtDirectionSave');
        if (!card || !hint || !sel || !summary || !negative || !btn) return;
        const projectMode = !!PROJECT_ID;
        card.style.display = projectMode ? '' : 'none';
        if (!projectMode) return;
        if (!sel.options.length) {
          RoomEditor.State.artDirectionTemplates.forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.template_id;
            opt.textContent = item.label;
            sel.appendChild(opt);
          });
        }
        const direction = RoomEditor.State.artDirection || {};
        if (direction.template_id) sel.value = direction.template_id;
        summary.value = direction.high_level_direction || '';
        negative.value = direction.negative_direction || '';
        hint.textContent = direction.locked
          ? 'Project art direction is locked. New room drafts and previews must stay inside this direction.'
          : 'Choose a direction template, adjust it if needed, then lock it before generating room previews.';
        btn.textContent = direction.locked ? 'Update Locked Direction' : 'Save & lock direction';
        renderRoomWizardDirectionConceptBoard();
        renderRoomWizardFrozenConceptGrid();
      }

      function renderRoomWizardArchetypeGrid() {
        const grid = document.getElementById('roomWizardArchetypeGrid');
        if (!grid) return;
        const projectMode = !!PROJECT_ID;
        grid.parentElement.style.display = projectMode ? '' : 'none';
        if (!projectMode) return;
        const active = RoomEditor.State.roomWizard.selectedArchetypeId || '';
        grid.innerHTML = RoomEditor.State.roomEnvironmentArchetypes.map((item) => `
          <button type="button" class="btn-secondary rw-template-chip${active === item.archetype_id ? ' active' : ''}" data-archetype-id="${escapeHtml(item.archetype_id)}" title="${escapeHtml(item.starter_brief || '')}">
            ${escapeHtml(item.label)}
          </button>
        `).join('');
        grid.querySelectorAll('[data-archetype-id]').forEach((btn) => {
          btn.addEventListener('click', async () => {
            RoomEditor.State.roomWizard.selectedArchetypeId = btn.dataset.archetypeId || '';
            renderRoomWizardArchetypeGrid();
            await adaptSelectedRoomArchetype('Adapt this room template to the locked project style.');
          });
        });
      }

      async function loadRoomEnvironmentProjectData() {
        if (!PROJECT_ID) return;
        try {
          const [templateRes, archetypeRes] = await Promise.all([
            fetch(PROJECT_ART_DIRECTION_TEMPLATES_URL, { cache: 'no-store' }),
            fetch(ROOM_ENV_ARCHETYPES_URL, { cache: 'no-store' })
          ]);
          const templateJson = await templateRes.json().catch(() => ({}));
          const archetypeJson = await archetypeRes.json().catch(() => ({}));
          RoomEditor.State.artDirectionTemplates = Array.isArray(templateJson.templates) ? templateJson.templates : [];
          RoomEditor.State.artDirection = templateJson.art_direction || null;
          RoomEditor.State.artDirectionConceptOptions = Array.isArray(templateJson.available_concepts) ? templateJson.available_concepts : [];
          RoomEditor.State.roomEnvironmentArchetypes = Array.isArray(archetypeJson.archetypes) ? archetypeJson.archetypes : [];
          renderRoomWizardArtDirectionUi();
          renderRoomWizardArchetypeGrid();
          updateRoomWizardCopilotHintUi();
        } catch (_) {
          const hint = document.getElementById('roomWizardArtDirectionHint');
          if (hint) hint.textContent = 'Could not load project art-direction templates.';
          showToast('Could not load project art-direction templates.', 'warning');
        }
      }

      async function saveProjectArtDirectionFromWizard() {
        if (!PROJECT_ID || !PROJECT_ART_DIRECTION_URL) return;
        const sel = document.getElementById('roomWizardArtDirectionTemplate');
        const summary = document.getElementById('roomWizardArtDirectionSummary');
        const negative = document.getElementById('roomWizardArtDirectionNegative');
        const status = document.getElementById('roomWizardArtDirectionStatus');
        if (!sel || !summary || !negative) return;
        if (status) status.textContent = 'Saving direction…';
        startRoomWizardWaitbar('art-direction', 'Saving project art direction.');
        try {
          const res = await fetch(PROJECT_ART_DIRECTION_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              template_id: sel.value,
              high_level_direction: summary.value,
              negative_direction: negative.value,
              frozen_concept_ids: Array.isArray(RoomEditor.State.artDirection?.frozen_concept_ids) ? RoomEditor.State.artDirection.frozen_concept_ids : [],
              locked: true
            })
          });
          const json = await res.json().catch(() => ({}));
          if (!res.ok || !json.ok) throw new Error(json.error || 'Could not save art direction');
          RoomEditor.State.artDirection = json.art_direction || null;
          (RoomEditor.State.data?.rooms || []).forEach((room) => {
            const envMod = globalThis.RoomWizardEnvironment;
            if (!envMod) return;
            envMod.ensureRoomEnvironment(room);
            room.environment.preview.status = 'outdated';
            room.environment.preview.fallback_reason = 'art_direction_changed';
            room.environment.preview.approved_image_id = null;
            room.environment.preview.approved_palette = null;
            room.environment.runtime.status = 'outdated';
            room.environment.runtime.source = null;
            room.environment.runtime.applied_preview_id = null;
            room.environment.runtime.surface_palette = null;
            room.environment.runtime.last_applied_at = null;
            room.environment.runtime.bespoke_asset_manifest.status = 'idle';
            room.environment.runtime.bespoke_asset_manifest.biome_id = null;
            room.environment.runtime.bespoke_asset_manifest.source_preview_id = null;
            room.environment.runtime.bespoke_asset_manifest.generation_plan = [];
            room.environment.runtime.bespoke_asset_manifest.required_slots = [];
            room.environment.runtime.bespoke_asset_manifest.built_slots = [];
            room.environment.runtime.bespoke_asset_manifest.slot_groups = {};
            room.environment.runtime.bespoke_asset_manifest.schema_validation = { status: 'idle', valid: false, errors: [], component_statuses: {} };
            room.environment.runtime.bespoke_asset_manifest.runtime_review = { status: 'idle', fail_reasons: [], metrics: {}, screenshot_url: null, review_mode: null };
            room.environment.runtime.bespoke_asset_manifest.review = { status: 'idle', fail_reasons: [], metrics: {}, screenshot_url: null, review_mode: null };
            room.environment.runtime.bespoke_asset_manifest.assets = {};
            room.environment.runtime.bespoke_asset_manifest.failed_assets = [];
            room.environment.runtime.bespoke_asset_manifest.used_ai = false;
            room.environment.runtime.bespoke_asset_manifest.generated_at = null;
            room.environment.runtime.bespoke_asset_manifest.validation_errors = [];
            room.environment.runtime.asset_pack.status = 'idle';
            room.environment.runtime.asset_pack.used_ai = false;
            room.environment.runtime.asset_pack.generated_at = null;
            room.environment.runtime.asset_pack.source_preview_id = null;
            room.environment.runtime.asset_pack.assets = {};
          });
          renderRoomWizardArtDirectionUi();
          updateRoomWizardCopilotHintUi();
          if (status) status.textContent = 'Project direction locked.';
          showToast('Project direction locked.', 'success');
          stopRoomWizardWaitbar('art-direction', 100);
        } catch (e) {
          stopRoomWizardWaitbar('art-direction', 100);
          const message = (e && e.message) || 'Save failed';
          if (status) status.textContent = message;
          setStatus(message, 'error');
        }
      }

      async function generateArtDirectionConceptBoard() {
        if (!PROJECT_ID || !PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL) return;
        const sel = document.getElementById('roomWizardArtDirectionTemplate');
        const summary = document.getElementById('roomWizardArtDirectionSummary');
        const negative = document.getElementById('roomWizardArtDirectionNegative');
        const status = document.getElementById('roomWizardGenerateArtDirectionConceptsStatus');
        const btn = document.getElementById('roomWizardGenerateArtDirectionConcepts');
        if (!sel || !summary || !negative || !status || !btn) return;
        status.textContent = 'Generating art direction concepts…';
        btn.disabled = true;
        startRoomWizardWaitbar('art-direction', 'Generating art direction concept board.');
        try {
          const res = await fetch(PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              template_id: sel.value,
              high_level_direction: summary.value,
              negative_direction: negative.value,
              frozen_concept_ids: Array.isArray(RoomEditor.State.artDirection?.frozen_concept_ids) ? RoomEditor.State.artDirection.frozen_concept_ids : []
            })
          });
          const json = await res.json().catch(() => ({}));
          if (!res.ok || !json.ok) throw new Error(json.error || 'Could not generate art direction concepts');
          RoomEditor.State.artDirection = json.art_direction || RoomEditor.State.artDirection;
          RoomEditor.State.artDirectionConceptOptions = Array.isArray(json.available_concepts) ? json.available_concepts : [];
          renderRoomWizardArtDirectionUi();
          updateRoomWizardCopilotHintUi();
          showToast('Art direction concepts are ready to review.', 'success');
          stopRoomWizardWaitbar('art-direction', 100);
        } catch (e) {
          stopRoomWizardWaitbar('art-direction', 100);
          const message = (e && e.message) || 'Generation failed';
          status.textContent = message;
          setStatus(message, 'error');
        } finally {
          btn.disabled = false;
        }
      }

      async function adaptSelectedRoomArchetype(instruction) {
        const room = getRoomWizardRoom();
        const promptEl = document.getElementById('roomWizardCopilotPrompt');
        const st = document.getElementById('roomWizardCopilotStatus');
        if (!PROJECT_ID || !room || !promptEl) return;
        if (!RoomEditor.State.roomWizard.selectedArchetypeId && !String(promptEl.value || '').trim()) {
          if (st) st.textContent = 'Choose a room template or enter a draft first.';
          setStatus('Choose a room template or enter a draft first.', 'warning');
          return;
        }
        if (st) st.textContent = 'Adapting draft…';
        startRoomWizardWaitbar('copilot', 'Adapting the room draft to the current art direction.');
        try {
          const res = await fetch(projectRoomEnvironmentApiUrl(room.id, 'adapt-template'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              archetype_id: RoomEditor.State.roomWizard.selectedArchetypeId || null,
              user_text: promptEl.value,
              instruction
            })
          });
          const json = await res.json().catch(() => ({}));
          if (!res.ok || !json.ok) throw new Error(json.error || 'Could not adapt room template');
          promptEl.value = json.draft_description || promptEl.value;
          if (st) st.textContent = 'Draft updated for the current project direction.';
          showToast('Draft updated for the current project direction.', 'success');
          stopRoomWizardWaitbar('copilot', 100);
        } catch (e) {
          stopRoomWizardWaitbar('copilot', 100);
          const message = (e && e.message) || 'Adaptation failed';
          if (st) st.textContent = message;
          setStatus(message, 'error');
        }
      }

      async function approveRoomWizardPreview(previewId) {
        const room = getRoomWizardRoom();
        const st = document.getElementById('roomWizardCopilotStatus');
        if (!PROJECT_ID || !room || !previewId) return;
        startRoomWizardWaitbar('copilot', 'Approving the selected preview.');
        try {
          const res = await fetch(projectRoomEnvironmentApiUrl(room.id, 'approve-preview'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              preview_id: previewId,
              ...roomWizardAnalyticsContext(room),
            })
          });
          const json = await res.json().catch(() => ({}));
          if (!res.ok || !json.ok) throw new Error(json.error || 'Approve failed');
          const envMod = globalThis.RoomWizardEnvironment;
          replaceRoomWizardEnvironmentPreservingAuthoring(room, json.environment || room.environment);
          renderRoomWizardEnvironmentPreview(room.environment);
          renderRoomWizardPreviewGallery(room.environment.preview || {});
          renderRoomWizardEnvironmentOutputSummary(room.environment);
          renderRoomWizardCopilotPreview({
            themeId: room.environment?.themeId || 'custom',
            tags: room.environment?.tags || [],
            rationale: room.environment?.spec?.description || ''
          });
          RoomEditor.State.roomWizard.approvedPreviewId = previewId;
          if (st) st.textContent = 'Preview approved. Open Game now uses this preview’s palette on room surfaces.';
          showToast('Preview approved. Open Game will use it now.', 'success');
          updateJsonText();
          setDirty(true);
          refreshOpenGamePreviewIfVisible(room.id);
          stopRoomWizardWaitbar('copilot', 100);
        } catch (e) {
          stopRoomWizardWaitbar('copilot', 100);
          const message = (e && e.message) || 'Approve failed';
          if (st) st.textContent = message;
          setStatus(message, 'error');
        }
      }

      function syncRoomWizardLookPreviewExplainer() {
        const el = document.getElementById('roomWizardLookPreviewExplainer');
        if (!el) return;
        if (PROJECT_ID) {
          el.innerHTML =
            'Quick peek after generation. To approve a picture and build final art, switch to <strong>2 · Preview &amp; build</strong> in the room workflow bar above.';
          return;
        }
        el.innerHTML =
          'Shows a <strong>layout diagram</strong> from the style copilot (not photos). For <strong>Gemini preview images</strong>, use <strong>Load Room</strong> on the left so the URL includes <code>?project_id=…</code>, then click Generate again.';
      }

      function updateRoomWizardCopilotHintUi() {
        const hint = document.getElementById('roomWizardCopilotServerHint');
        if (!hint) return;
        const genBtn = document.getElementById('roomWizardCopilotGenerate');
        if (genBtn) {
          genBtn.textContent = PROJECT_ID ? 'Generate preview pictures' : 'Suggest look (diagram)';
        }
        syncRoomWizardLookPreviewExplainer();
        const { serverReachable, geminiConfigured } = RoomEditor.State.copilot;
        const meta = document.getElementById('roomWizardGeminiMeta');
        const probeRow = document.getElementById('roomWizardGeminiProbeRow');
        if (meta) {
          if (!serverReachable || !geminiConfigured) {
            meta.hidden = true;
            meta.innerHTML = '';
          } else {
            meta.hidden = false;
            const im = RoomEditor.State.copilot.geminiImageModel || 'gemini-2.5-flash-image';
            const snap = RoomEditor.State.copilot.geminiLastError;
            const errLine =
              snap && snap.message
                ? ` Last Gemini image error: ${escapeHtml(String(snap.message).slice(0, 220))}${snap.recorded_at ? ` (${escapeHtml(snap.recorded_at)})` : ''}`
                : '';
            const billingHint =
              snap && snap.message && /spending cap|billing|429|RESOURCE_EXHAUSTED|quota/i.test(String(snap.message))
                ? ' <strong>Billing:</strong> In Google Cloud (project linked to this API key), open <strong>Billing</strong> and raise or remove the <strong>spending cap</strong>, or fix payment. Image calls use the same project quota as text.'
                : '';
            meta.innerHTML = `Image model: <code>${escapeHtml(im)}</code>.${errLine}${billingHint}`;
          }
        }
        if (probeRow) {
          probeRow.hidden = !(serverReachable && geminiConfigured);
        }
        if (PROJECT_ID) {
          const frozenCount = Array.isArray(RoomEditor.State.artDirection?.frozen_concept_ids) ? RoomEditor.State.artDirection.frozen_concept_ids.length : 0;
          hint.innerHTML = RoomEditor.State.artDirection?.locked
            ? `Project direction is locked${frozenCount ? ` with ${frozenCount} frozen concept anchor${frozenCount === 1 ? '' : 's'}` : ''}. Generate room-aware previews from a room template or your own room draft.`
            : 'Lock a project art direction first so room drafts and previews stay consistent.';
          updateRoomWizardBiomePackSummary();
          return;
        }
        if (!serverReachable) {
          hint.innerHTML =
            'Run the <strong>Sprite Workbench</strong> server (e.g. <code>./scripts/start_sprite_workbench_with_env.sh</code> or <code>python3 scripts/sprite_workbench_server.py</code>) and open this page from that server so Copilot and Sync Canonical can use your <code>.env.local</code> key.';
          return;
        }
        if (!geminiConfigured) {
          hint.innerHTML =
            'Server is up, but <code>GEMINI_API_KEY</code> was not found. Add it to <code>.env.local</code> in the project root and restart the Sprite Workbench server.';
          return;
        }
        hint.innerHTML =
          'Gemini is on, but you are <strong>not</strong> in a workbench project URL (<code>?project_id=…</code>). The button runs the <strong>text</strong> copilot (theme, tags, layout <strong>diagram</strong>)—not Gemini photos. For <strong>preview images</strong>, click <strong>Load Room</strong> on a project in the left panel, then use <strong>Generate preview pictures</strong>.';
        updateRoomWizardBiomePackSummary();
      }

      async function refreshCopilotStatus() {
        try {
          const r = await fetch(API_PING_URL, { cache: 'no-store' });
          if (!r.ok) throw new Error('bad status');
          const j = await r.json();
          RoomEditor.State.copilot.serverReachable = true;
          RoomEditor.State.copilot.geminiConfigured = !!(j.copilot && j.copilot.geminiConfigured);
          RoomEditor.State.copilot.geminiImageModel = (j.copilot && j.copilot.geminiImageModel) || '';
          RoomEditor.State.copilot.geminiLastError = (j.copilot && j.copilot.lastGeminiImageError) || null;
        } catch (_) {
          RoomEditor.State.copilot.serverReachable = false;
          RoomEditor.State.copilot.geminiConfigured = false;
          RoomEditor.State.copilot.geminiImageModel = '';
          RoomEditor.State.copilot.geminiLastError = null;
        }
        updateRoomWizardCopilotHintUi();
      }

      function renderRoomWizardCopilotPreview(payload) {
        const prev = document.getElementById('roomWizardCopilotPreview');
        const prevVisual = document.getElementById('roomWizardCopilotPreviewVisual');
        const lookStrip = document.getElementById('roomWizardLookPreviewStrip');
        const lookVisual = document.getElementById('roomWizardLookPreviewVisual');
        if (!prev || !prevVisual || !payload) return;

        function mirrorDescribeStepPreview(markup) {
          const html = String(markup || '');
          prevVisual.innerHTML = html;
          prev.hidden = false;
          if (lookVisual && lookStrip) {
            lookVisual.innerHTML = html;
            lookStrip.hidden = !html.trim();
          }
        }

        if (PROJECT_ID) {
          const room = getRoomWizardRoom();
          if (room?.environment?.preview?.images?.length) {
            mirrorDescribeStepPreview(renderGeneratedEnvironmentPreviewMarkup(room.environment));
            updateRoomWizardResultsEmptyState(true);
            return;
          }
        }
        const preview = buildRoomWizardEnvironmentPreviewModel(
          payload.themeId,
          payload.tags || [],
          payload.rationale || ''
        );
        mirrorDescribeStepPreview(renderEnvironmentPreviewMarkup(preview, 'Copilot suggestion'));
        updateRoomWizardResultsEmptyState(true);
      }

      function syncRoomWizardFormFromRoom() {
        const room = getRoomWizardRoom();
        if (!room) return;
        const nameEl = document.getElementById('roomWizardRoomName');
        const idEl = document.getElementById('roomWizardRoomId');
        if (nameEl) nameEl.value = room.name || '';
        if (idEl) idEl.value = room.id || '';
        syncRoomWizardFootprintRadios();
        syncRoomWizardNeighborFromRoom();
        syncRoomWizardEnvironmentFromRoom();
      }

      function syncRoomWizardEdgeSelects() {
        const room = getRoomWizardRoom();
        const myEl = document.getElementById('roomWizardMyEdge');
        const nbEl = document.getElementById('roomWizardNeighborEdge');
        const neighborSel = document.getElementById('roomWizardNeighbor');
        if (!myEl || !nbEl) return;
        if (!room || !RoomEditor.State.data) {
          myEl.innerHTML = '';
          nbEl.innerHTML = '<option value="">—</option>';
          return;
        }
        ensureRoomShape(room);
        const myCount = getEdgeCount(room);
        const prevMy = myEl.value;
        myEl.innerHTML = '';
        for (let i = 0; i < myCount; i += 1) {
          const opt = document.createElement('option');
          opt.value = String(i);
          opt.textContent = edgeLabel(room, i);
          myEl.appendChild(opt);
        }
        if (prevMy && Number(prevMy) < myCount) {
          myEl.value = prevMy;
        } else if (myCount) {
          myEl.value = '0';
        }

        const neighborId = neighborSel?.value;
        const neighbor = neighborId ? getRoomById(neighborId) : null;
        const prevNb = nbEl.value;
        nbEl.innerHTML = '';
        if (neighbor) {
          ensureRoomShape(neighbor);
          const nbCount = getEdgeCount(neighbor);
          for (let i = 0; i < nbCount; i += 1) {
            const opt = document.createElement('option');
            opt.value = String(i);
            opt.textContent = edgeLabel(neighbor, i);
            nbEl.appendChild(opt);
          }
          if (prevNb && Number(prevNb) < nbCount) {
            nbEl.value = prevNb;
          } else if (nbCount) {
            nbEl.value = '0';
          }
        } else {
          const opt = document.createElement('option');
          opt.value = '';
          opt.textContent = '— Pick neighbor first —';
          nbEl.appendChild(opt);
        }
      }

      function syncRoomWizardNeighborFromRoom() {
        const room = getRoomWizardRoom();
        const sel = document.getElementById('roomWizardNeighbor');
        const card = document.getElementById('roomWizardNeighborsCard');
        if (!sel || !room || !RoomEditor.State.data) return;
        const cur = room.id;
        const prev = sel.value;
        sel.innerHTML = '';
        const empty = document.createElement('option');
        empty.value = '';
        empty.textContent = '— None yet —';
        sel.appendChild(empty);
        const others = RoomEditor.State.data.rooms.filter((r) => r.id !== cur);
        others.forEach((r) => {
          const opt = document.createElement('option');
          opt.value = r.id;
          opt.textContent = `${r.name || r.id} (${r.id})`;
          sel.appendChild(opt);
        });
        if (card) card.style.opacity = others.length ? '' : '0.65';
        let pick = prev;
        const prevOk = pick && others.some((r) => r.id === pick);
        if (!prevOk) {
          const link = (room.edgeLinks || [])[0];
          pick = link && link.targetRoomId ? link.targetRoomId : '';
        }
        sel.value = pick;

        syncRoomWizardEdgeSelects();

        if (pick) {
          const neighbor = getRoomById(pick);
          const link = (room.edgeLinks || []).find((l) => l.targetRoomId === pick);
          const myEl = document.getElementById('roomWizardMyEdge');
          const nbEl = document.getElementById('roomWizardNeighborEdge');
          if (link && neighbor && myEl && nbEl) {
            if (link.edgeIndex >= 0 && link.edgeIndex < getEdgeCount(room)) {
              myEl.value = String(link.edgeIndex);
            }
            if (link.targetEdgeIndex >= 0 && link.targetEdgeIndex < getEdgeCount(neighbor)) {
              nbEl.value = String(link.targetEdgeIndex);
            }
          }
        }
      }

      function applyRoomWizardAlign() {
        const mod = globalThis.RoomWizardNeighborAlign;
        if (!mod || typeof mod.computeAlignedGlobal !== 'function') {
          setStatus('Neighbor align module not loaded.', 'error');
          return;
        }
        const room = getRoomWizardRoom();
        if (!room) return;
        const neighborId = document.getElementById('roomWizardNeighbor')?.value;
        if (!neighborId) {
          setStatus('Pick an adjoining room first.', 'warning');
          return;
        }
        const neighbor = getRoomById(neighborId);
        if (!neighbor) return;
        ensureRoomShape(room);
        ensureRoomShape(neighbor);
        const myEdge = Number(document.getElementById('roomWizardMyEdge')?.value);
        const nEdge = Number(document.getElementById('roomWizardNeighborEdge')?.value);
        const result = mod.computeAlignedGlobal(room, neighbor, myEdge, nEdge, mod.ROOM_WIZARD_NEIGHBOR_SCALE);
        if (!result.ok) {
          setStatus(`Align: ${result.reason}`, 'error');
          return;
        }
        room.global = { x: result.global.x, y: result.global.y };
        setRoomEdgeLink(room.id, myEdge, neighborId, nEdge);
        RoomEditor.State.roomWizard.touched = true;
        setDirty(true);
        updateJsonText();
        if (RoomEditor.State.data) {
          RoomEditor.State.lastValidationReport = validateLayout(RoomEditor.State.data);
          renderValidationResults(RoomEditor.State.lastValidationReport);
        }
        redraw();
        setStatus('Aligned to neighbor; edge link saved.', 'success');
      }

      function applyRoomWizardHatch() {
        const mod = globalThis.RoomWizardNeighborAlign;
        if (!mod || typeof mod.computeHatchHeightDelta !== 'function') {
          setStatus('Neighbor align module not loaded.', 'error');
          return;
        }
        const room = getRoomWizardRoom();
        if (!room) return;
        const neighborId = document.getElementById('roomWizardNeighbor')?.value;
        if (!neighborId) {
          setStatus('Pick an adjoining room first.', 'warning');
          return;
        }
        const neighbor = getRoomById(neighborId);
        if (!neighbor) return;
        ensureRoomShape(room);
        ensureRoomShape(neighbor);
        const myEdge = Number(document.getElementById('roomWizardMyEdge')?.value);
        const nEdge = Number(document.getElementById('roomWizardNeighborEdge')?.value);
        const d = mod.computeHatchHeightDelta(room, neighbor, myEdge, nEdge, mod.ROOM_WIZARD_NEIGHBOR_SCALE);
        if (!d.deltaX && !d.deltaY) {
          const r = d.reason;
          let msg =
            'Could not adjust along the opening — check that the selected edges exist and (for slanted walls) are parallel.';
          if (r === 'already_aligned') {
            msg = 'Opening positions already match (using doors or edge midpoints).';
          } else if (r === 'edges_not_parallel') {
            msg = 'Match opening height needs parallel edges along the opening (for slanted walls, align first).';
          } else if (r === 'degenerate_edge') {
            msg = 'Selected edge is too short to use.';
          }
          setStatus(msg, 'warning');
          return;
        }
        const gx = Number.isFinite(Number(room.global?.x)) ? Number(room.global.x) : 0;
        const gy = Number.isFinite(Number(room.global?.y)) ? Number(room.global.y) : 0;
        room.global = { x: gx + d.deltaX, y: gy + d.deltaY };
        RoomEditor.State.roomWizard.touched = true;
        setDirty(true);
        updateJsonText();
        if (RoomEditor.State.data) {
          RoomEditor.State.lastValidationReport = validateLayout(RoomEditor.State.data);
          renderValidationResults(RoomEditor.State.lastValidationReport);
        }
        redraw();
        setStatus('Adjusted position along the opening (doors or edge midpoints).', 'success');
      }

      function applyRoomWizardMatchWallLength() {
        const mod = globalThis.RoomWizardNeighborAlign;
        if (!mod || typeof mod.computeMatchWallLengthPatch !== 'function') {
          setStatus('Neighbor align module not loaded.', 'error');
          return;
        }
        const room = getRoomWizardRoom();
        if (!room) return;
        const neighborId = document.getElementById('roomWizardNeighbor')?.value;
        if (!neighborId) {
          setStatus('Pick an adjoining room first.', 'warning');
          return;
        }
        const neighbor = getRoomById(neighborId);
        if (!neighbor) return;
        ensureRoomShape(room);
        ensureRoomShape(neighbor);
        const myEdge = Number(document.getElementById('roomWizardMyEdge')?.value);
        const nEdge = Number(document.getElementById('roomWizardNeighborEdge')?.value);
        const fp = globalThis.RoomLayoutWizardFootprint;
        const margin = fp && Number.isFinite(fp.ROOM_WIZARD_FOOTPRINT_MARGIN)
          ? fp.ROOM_WIZARD_FOOTPRINT_MARGIN
          : 160;
        const result = mod.computeMatchWallLengthPatch(room, neighbor, myEdge, nEdge, margin);
        if (!result.ok) {
          const map = {
            need_axis_aligned_rectangles: 'Match wall length needs both rooms to be axis-aligned rectangle footprints (4 straight walls).',
            edge_orientation_mismatch: 'Pick matching edge types (e.g. top to top), both horizontal or both vertical.',
            bad_polygon: 'Room polygon missing or invalid.'
          };
          setStatus(map[result.reason] || `Match wall length: ${result.reason}`, 'warning');
          return;
        }
        room.size = { width: result.size.width, height: result.size.height };
        room.polygon = result.polygon.map((pt) => [pt[0], pt[1]]);
        RoomEditor.State.roomWizard.touched = true;
        setDirty(true);
        updateJsonText();
        if (RoomEditor.State.data) {
          RoomEditor.State.lastValidationReport = validateLayout(RoomEditor.State.data);
          renderValidationResults(RoomEditor.State.lastValidationReport);
        }
        redraw();
        setStatus('Resized this room so the selected wall length matches the neighbor (recheck doors/platforms).', 'success');
      }

      function updateWorkflowScopeToggle() {
        const w = document.getElementById('workflowScopeWorld');
        const r = document.getElementById('workflowScopeRoom');
        const a = document.getElementById('workflowScopeArtDirection');
        const stack = document.getElementById('workflowRailsStack');
        if (!w || !r || !a) return;
        const world = RoomEditor.State.workflowScope === 'world';
        const room = RoomEditor.State.workflowScope === 'room';
        const artDirection = RoomEditor.State.workflowScope === 'art-direction';
        w.classList.toggle('active', world);
        r.classList.toggle('active', room);
        a.classList.toggle('active', artDirection);
        w.setAttribute('aria-selected', world ? 'true' : 'false');
        r.setAttribute('aria-selected', room ? 'true' : 'false');
        a.setAttribute('aria-selected', artDirection ? 'true' : 'false');
        stack?.classList.toggle('workflow-rails-stack--room', room || artDirection);
        stack?.classList.toggle('workflow-rails-stack--world', world);
      }

      function syncWorldWorkflowRailVisibility() {
        const rail = document.getElementById('worldWorkflowRail');
        if (!rail) return;
        const show = RoomEditor.State.workflowScope === 'world';
        rail.hidden = !show;
        rail.setAttribute('aria-hidden', show ? 'false' : 'true');
      }

      function syncWorldPlaceholderPanel() {
        const el = document.getElementById('worldWorkflowPlaceholderPanel');
        if (!el) return;
        const show =
          RoomEditor.State.workflowScope === 'world' && (RoomEditor.State.worldWorkflowStep === 2 || RoomEditor.State.worldWorkflowStep === 3);
        el.hidden = !show;
        el.setAttribute('aria-hidden', show ? 'false' : 'true');
      }

      function updateWorldWorkflowPills() {
        const rail = document.getElementById('worldWorkflowRail');
        if (!rail) return;
        const step = RoomEditor.State.worldWorkflowStep;
        rail.querySelectorAll('[data-world-workflow-step]').forEach((pill) => {
          const n = Number(pill.dataset.worldWorkflowStep);
          pill.classList.remove('active', 'available');
          if (n === step) pill.classList.add('active');
          else pill.classList.add('available');
        });
      }

      function updateEditorWorkflowPrimaryPills() {
        updateWorldWorkflowPills();
      }

      function syncEditorWorkflowSecondaryRail() {
        const wrap = document.getElementById('roomWizardPhaseRailWrap');
        if (!wrap) return;
        const show = RoomEditor.State.workflowScope === 'room' && !!RoomEditor.State.data;
        wrap.hidden = !show;
        wrap.setAttribute('aria-hidden', show ? 'false' : 'true');
      }

      function syncRoomWizardScopePanels() {
        const panL = document.getElementById('roomWizardPanelLayout');
        const panE = document.getElementById('roomWizardPanelEnvironment');
        const panA = document.getElementById('roomWizardPanelArtDirection');
        const panR = document.getElementById('roomWizardPanelReview');
        const artScope = RoomEditor.State.workflowScope === 'art-direction';
        if (panA) {
          panA.hidden = !artScope;
          panA.setAttribute('aria-hidden', artScope ? 'false' : 'true');
        }
        if (artScope) {
          if (panL) panL.hidden = true;
          if (panE) panE.hidden = true;
          if (panR) panR.hidden = true;
        }
      }

      function setWorldWorkflowStep(step) {
        if (step < 1 || step > 4) return;
        if (RoomEditor.State.workflowScope !== 'world') return;
        RoomEditor.State.worldWorkflowStep = step;
        closeRoomWizard(true);
        setViewMode('global');
        if (step === 4 && RoomEditor.State.data) {
          const report = validateLayout(RoomEditor.State.data);
          RoomEditor.State.lastValidationReport = report;
          renderValidationResults(report);
          document.getElementById('validationPanel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        syncLegacyEditorWorkflowStep();
        updateWorldWorkflowPills();
        syncWorldPlaceholderPanel();
        syncWorldWorkflowRailVisibility();
        syncEditorWorkflowSecondaryRail();
        updateWorkflowRailPills();
        syncRoomWizardDock();
        redraw();
      }

      function setWorkflowScope(scope) {
        if (scope !== 'world' && scope !== 'room' && scope !== 'art-direction') return;
        if (scope === 'room' && (!RoomEditor.State.data?.rooms?.length)) {
          setStatus('Add a room first (world layout, or + Add Room in settings).', 'warning');
          return;
        }
        if (scope === 'art-direction' && !PROJECT_ID) {
          setStatus('Open a workbench project to edit project-wide art direction.', 'warning');
          return;
        }
        RoomEditor.State.workflowScope = scope;
        updateWorkflowScopeToggle();
        syncWorldWorkflowRailVisibility();
        if (scope === 'world') {
          closeRoomWizard(true);
          setWorldWorkflowStep(RoomEditor.State.worldWorkflowStep);
        } else if (scope === 'art-direction') {
          if (RoomEditor.State.currentRoomId && !RoomEditor.State.roomWizard.active) {
            openRoomWizard(RoomEditor.State.currentRoomId);
          }
          setViewMode('room');
          loadRoomEnvironmentProjectData();
          syncLegacyEditorWorkflowStep();
          updateWorldWorkflowPills();
          syncWorldPlaceholderPanel();
          syncEditorWorkflowSecondaryRail();
          updateWorkflowRailPills();
          syncRoomWizardDock();
          syncRoomWizardScopePanels();
          redraw();
        } else {
          setViewMode('room');
          if (RoomEditor.State.currentRoomId && !RoomEditor.State.roomWizard.active) {
            openRoomWizard(RoomEditor.State.currentRoomId);
          } else {
            syncLegacyEditorWorkflowStep();
            updateWorldWorkflowPills();
            syncWorldPlaceholderPanel();
            syncEditorWorkflowSecondaryRail();
            updateWorkflowRailPills();
            syncRoomWizardDock();
            redraw();
          }
        }
      }

      function setEditorWorkflowStep(step) {
        if (step !== 1 && step !== 2 && step !== 3) return;
        if (step === 2 && (!RoomEditor.State.data?.rooms?.length)) {
          setStatus('Add a room first (world layout, or + Add Room in settings).', 'warning');
          return;
        }
        if (step === 1) {
          RoomEditor.State.worldWorkflowStep = 1;
          setWorkflowScope('world');
        } else if (step === 2) {
          setWorkflowScope('room');
        } else {
          RoomEditor.State.worldWorkflowStep = 4;
          setWorkflowScope('world');
        }
      }

      function updateWorkflowRailPills() {
        const ph = RoomEditor.State.roomWizard.phase;
        const wizardOn = RoomEditor.State.roomWizard.active;
        const vm = RoomEditor.State.viewMode;
        const rail = document.getElementById('roomWizardPhaseRail');
        if (!rail) return;
        const room = getRoomWizardRoom();
        const mod = globalThis.RoomWizardTerrain;
        const layoutOk = !!(room && mod && mod.isLayoutCompleteForTerrain(room));

        rail.querySelectorAll('.phase-pill[data-rw-phase]').forEach((pill) => {
          const key = pill.dataset.rwPhase;
          pill.classList.remove('active', 'available', 'locked', 'complete');
          if (key === 'layout') {
            if (wizardOn && ph === 'layout') {
              pill.classList.add('active');
            } else if (!wizardOn && vm === 'room' && RoomEditor.State.workflowScope === 'room') {
              pill.classList.add('active');
            } else {
              pill.classList.add('available');
            }
            return;
          }
          if (key === 'environment') {
            if (!layoutOk) {
              pill.classList.add('locked');
              pill.disabled = true;
              pill.title = 'Complete layout (name, id, footprint) first.';
              return;
            }
            pill.disabled = false;
            pill.title = '';
            if (wizardOn && ph === 'environment') {
              pill.classList.add('active');
            } else {
              pill.classList.add('available');
            }
            return;
          }
          if (key === 'objects') {
            pill.classList.add('locked');
            pill.disabled = true;
            pill.title = 'Coming in a later update';
            return;
          }
          if (key === 'review') {
            pill.disabled = false;
            pill.title = '';
            if (wizardOn && ph === 'review') {
              pill.classList.add('active');
            } else {
              pill.classList.add('available');
            }
          }
        });
      }

      function setRoomWizardPhase(phase) {
        if (phase !== 'layout' && phase !== 'environment' && phase !== 'review') return;
        RoomEditor.State.roomWizard.phase = phase;
        const dock = document.getElementById('roomWizardDock');
        if (dock) dock.dataset.phase = phase;
        const panL = document.getElementById('roomWizardPanelLayout');
        const panE = document.getElementById('roomWizardPanelEnvironment');
        const panA = document.getElementById('roomWizardPanelArtDirection');
        const panR = document.getElementById('roomWizardPanelReview');
        const artScope = RoomEditor.State.workflowScope === 'art-direction';
        if (panL) panL.hidden = artScope || phase !== 'layout';
        if (panE) panE.hidden = artScope || phase !== 'environment';
        if (panA) panA.hidden = !artScope;
        if (panR) panR.hidden = artScope || phase !== 'review';
        updateWorkflowRailPills();
        if (phase === 'review') {
          updateRoomWizardReviewPanel();
        }
        if (phase === 'layout') {
          updateRoomWizardTerrainControls();
          refreshTerrainWarnings();
        }
        if (phase === 'environment') {
          syncRoomWizardEnvironmentFromRoom();
          loadRoomEnvironmentProjectData();
          refreshCopilotStatus();
          setRoomWizardEnvStep(RoomEditor.State.roomWizard.envStep || 'describe');
        }
        syncRoomWizardScopePanels();
      }

      function updateRoomWizardReviewPanel() {
        const room = getRoomWizardRoom();
        const summary = document.getElementById('roomWizardReviewSummary');
        const inline = document.getElementById('roomWizardValidationInline');
        if (!room || !summary) return;
        const W = room.size?.width ?? '?';
        const H = room.size?.height ?? '?';
        const links = room.edgeLinks || [];
        const neighborLine =
          links.length > 0
            ? `<dt>Edge links</dt><dd>${links
                .map((l) => `${escapeHtml(room.id)}[${l.edgeIndex}] ↔ ${escapeHtml(l.targetRoomId)}[${l.targetEdgeIndex}]`)
                .join('<br/>')}</dd>`
            : '<dt>Edge links</dt><dd>None yet</dd>';
        const envMod = globalThis.RoomWizardEnvironment;
        let envBlock = '';
        if (envMod) {
          envMod.ensureRoomEnvironment(room);
          const e = room.environment;
          const tagStr = e.tags && e.tags.length ? e.tags.join(', ') : '—';
          envBlock = `<dt>Environment</dt><dd>${escapeHtml(e.themeId)} · tags: ${escapeHtml(tagStr)}</dd>`;
        }
        summary.innerHTML = `
          <dl>
            <dt>Room</dt><dd>${escapeHtml(room.name)} (${escapeHtml(room.id)})</dd>
            <dt>Footprint</dt><dd>${escapeHtml(String(W))} × ${escapeHtml(String(H))} px</dd>
            ${envBlock}
            ${neighborLine}
          </dl>`;
        if (!RoomEditor.State.data) return;
        const report = validateLayout(RoomEditor.State.data);
        RoomEditor.State.lastValidationReport = report;
        renderValidationResults(report);
        if (inline) {
          const checks = [...report.level_1.checks, ...report.level_2.checks];
          if (checks.length === 0) {
            inline.innerHTML = '<div class="vw-item">No structural or traversal issues reported.</div>';
          } else {
            inline.innerHTML = checks
              .map((c) => {
                const cl = c.severity === 'error' ? 'err' : 'warn';
                return `<div class="vw-item ${cl}">${escapeHtml(c.id)}: ${escapeHtml(c.message)}</div>`;
              })
              .join('');
          }
        }
      }

      function syncWorkflowRailVisibility() {
        const stack = document.getElementById('workflowRailsStack');
        if (!stack) return;
        const show = !!RoomEditor.State.data;
        stack.hidden = !show;
        stack.setAttribute('aria-hidden', show ? 'false' : 'true');
        syncEditorWorkflowSecondaryRail();
        syncWorldWorkflowRailVisibility();
        updateWorkflowScopeToggle();
        updateWorldWorkflowPills();
        syncWorldPlaceholderPanel();
        updateWorkflowRailPills();
        syncRoomWizardScopePanels();
      }

      function syncRoomWizardDock() {
        const dock = document.getElementById('roomWizardDock');
        if (!dock) return;
        if (RoomEditor.State.roomWizard.active && RoomEditor.State.data && RoomEditor.State.roomWizard.roomId) {
          const exists = RoomEditor.State.data.rooms.some((r) => r.id === RoomEditor.State.roomWizard.roomId);
          if (!exists) {
            closeRoomWizard(true);
            return;
          }
        }
        const room =
          RoomEditor.State.currentRoomId && RoomEditor.State.data
            ? RoomEditor.State.data.rooms.find((r) => r.id === RoomEditor.State.currentRoomId)
            : null;
        const show =
          (RoomEditor.State.workflowScope === 'room' || RoomEditor.State.workflowScope === 'art-direction') &&
          RoomEditor.State.viewMode === 'room' &&
          !!RoomEditor.State.data &&
          (RoomEditor.State.workflowScope === 'art-direction' ? !!PROJECT_ID : !!room);
        dock.hidden = !show;
        dock.setAttribute('aria-hidden', show ? 'false' : 'true');
        dock.classList.toggle('room-wizard-dock--compact', show);
        if (RoomEditor.Ui.refs.roomSetupBtn) {
          RoomEditor.Ui.refs.roomSetupBtn.disabled = !RoomEditor.State.currentRoomId || !RoomEditor.State.data?.rooms?.length;
        }
      }

      function openRoomWizard(roomId) {
        if (!RoomEditor.State.data || !roomId) return;
        RoomEditor.State.workflowScope = 'room';
        syncLegacyEditorWorkflowStep();
        setViewMode('room');
        RoomEditor.State.roomWizard.active = true;
        RoomEditor.State.roomWizard.roomId = roomId;
        RoomEditor.State.roomWizard.phase = 'layout';
        RoomEditor.State.roomWizard.touched = false;
        RoomEditor.State.roomWizard.envStep = 'describe';
        clearRoomWizardCopilotPreview();
        RoomEditor.State.currentRoomId = roomId;
        populateRoomSelect();
        RoomEditor.Ui.refs.roomSelect.value = roomId;
        syncRoomWizardFormFromRoom();
        setRoomWizardPhase('layout');
        syncRoomWizardDock();
        syncWorkflowRailVisibility();
        const nameInput = document.getElementById('roomWizardRoomName');
        if (nameInput) {
          setTimeout(() => nameInput.focus(), 0);
        }
      }

      function closeRoomWizard(skipConfirm) {
        if (!RoomEditor.State.roomWizard.active) {
          if (RoomEditor.State.workflowScope === 'room' || RoomEditor.State.workflowScope === 'art-direction') {
            RoomEditor.State.workflowScope = 'world';
            RoomEditor.State.worldWorkflowStep = 1;
            setViewMode('global');
            syncLegacyEditorWorkflowStep();
            updateWorkflowScopeToggle();
            updateWorldWorkflowPills();
            syncWorldPlaceholderPanel();
            syncWorldWorkflowRailVisibility();
            updateWorkflowRailPills();
            syncEditorWorkflowSecondaryRail();
            syncRoomWizardDock();
            redraw();
          }
          return;
        }
        if (!skipConfirm && RoomEditor.State.roomWizard.touched) {
          const ok = window.confirm(
            'Dismiss room setup? Your edits stay in this session — use Save or Export to write files.'
          );
          if (!ok) return;
        }
        RoomEditor.State.roomWizard.active = false;
        RoomEditor.State.roomWizard.roomId = null;
        RoomEditor.State.roomWizard.phase = 'layout';
        RoomEditor.State.roomWizard.touched = false;
        syncRoomWizardFormFromRoom();
        syncRoomWizardDock();
        updateWorkflowRailPills();
        updateWorldWorkflowPills();
        updateWorkflowScopeToggle();
        syncWorldWorkflowRailVisibility();
        syncEditorWorkflowSecondaryRail();
        redraw();
      }

      function requestCloseRoomWizard() {
        closeRoomWizard(false);
      }

      function wireRoomWizardEvents() {
        initRoomWizardEnvTabs();
        document.getElementById('roomWizardClose')?.addEventListener('click', requestCloseRoomWizard);
        document.getElementById('workflowScopeWorld')?.addEventListener('click', () => setWorkflowScope('world'));
        document.getElementById('workflowScopeRoom')?.addEventListener('click', () => setWorkflowScope('room'));
        document.getElementById('workflowScopeArtDirection')?.addEventListener('click', () => setWorkflowScope('art-direction'));
        document.querySelectorAll('#worldWorkflowRail [data-world-workflow-step]').forEach((btn) => {
          btn.addEventListener('click', () => setWorldWorkflowStep(Number(btn.dataset.worldWorkflowStep)));
        });
        document.getElementById('roomWizardTabLayout')?.addEventListener('click', () => {
          if (RoomEditor.State.viewMode === 'global') setViewMode('room');
          if (!RoomEditor.State.currentRoomId || !RoomEditor.State.data) return;
          if (RoomEditor.State.workflowScope !== 'room') {
            setWorkflowScope('room');
          } else if (!RoomEditor.State.roomWizard.active) {
            openRoomWizard(RoomEditor.State.currentRoomId);
          }
          setRoomWizardPhase('layout');
          updateWorldWorkflowPills();
          syncEditorWorkflowSecondaryRail();
          redraw();
        });
        document.getElementById('roomWizardTabReview')?.addEventListener('click', () => {
          if (RoomEditor.State.viewMode === 'global') setViewMode('room');
          if (!RoomEditor.State.currentRoomId || !RoomEditor.State.data) return;
          if (RoomEditor.State.workflowScope !== 'room') {
            setWorkflowScope('room');
          } else if (!RoomEditor.State.roomWizard.active) {
            openRoomWizard(RoomEditor.State.currentRoomId);
          }
          setRoomWizardPhase('review');
          updateWorldWorkflowPills();
          syncEditorWorkflowSecondaryRail();
          redraw();
        });
        document.getElementById('roomWizardTabEnvironment')?.addEventListener('click', () => {
          if (RoomEditor.State.viewMode === 'global') setViewMode('room');
          if (!RoomEditor.State.currentRoomId || !RoomEditor.State.data) return;
          const mod = globalThis.RoomWizardTerrain;
          const room = getRoomWizardRoom();
          if (!mod || !room || !mod.isLayoutCompleteForTerrain(room)) {
            setStatus('Complete layout (name, id, footprint) before Environment.', 'warning');
            return;
          }
          if (RoomEditor.State.workflowScope !== 'room') {
            setWorkflowScope('room');
          } else if (!RoomEditor.State.roomWizard.active) {
            openRoomWizard(RoomEditor.State.currentRoomId);
          }
          setRoomWizardPhase('environment');
          updateWorldWorkflowPills();
          syncEditorWorkflowSecondaryRail();
          redraw();
        });
        document.getElementById('roomWizardBackToLayoutFromEnv')?.addEventListener('click', () => setRoomWizardPhase('layout'));
        document.getElementById('roomWizardBackToEnvironment')?.addEventListener('click', () => setRoomWizardPhase('environment'));
        document.getElementById('roomWizardBackToLayout')?.addEventListener('click', () => setRoomWizardPhase('layout'));
        Object.entries(roomWizardComponentFieldMap()).forEach(([key, el]) => {
          el?.addEventListener('input', () => {
            const room = getRoomWizardRoom();
            const envMod = globalThis.RoomWizardEnvironment;
            if (!room || !envMod) return;
            envMod.ensureRoomEnvironment(room);
            if (typeof envMod.ensureEnvironmentComponents === 'function') {
              envMod.ensureEnvironmentComponents(room.environment.spec);
            }
            room.environment.spec.components[key].prompt = String(el.value || '').trim();
            RoomEditor.State.roomWizard.touched = true;
            setDirty(true);
            updateJsonText();
          });
        });
        document.getElementById('roomWizardThemeSelect')?.addEventListener('change', () => {
          const room = getRoomWizardRoom();
          const envMod = globalThis.RoomWizardEnvironment;
          if (!room || !envMod) return;
          envMod.ensureRoomEnvironment(room);
          const v = document.getElementById('roomWizardThemeSelect')?.value;
          if (v) room.environment.themeId = v;
          RoomEditor.State.roomWizard.touched = true;
          setDirty(true);
          updateJsonText();
        });
        document.getElementById('roomWizardTagsInput')?.addEventListener('input', () => {
          const room = getRoomWizardRoom();
          const envMod = globalThis.RoomWizardEnvironment;
          if (!room || !envMod) return;
          envMod.ensureRoomEnvironment(room);
          room.environment.tags = envMod.parseTagsInput(document.getElementById('roomWizardTagsInput')?.value);
          RoomEditor.State.roomWizard.touched = true;
          setDirty(true);
          updateJsonText();
        });
        document.getElementById('roomWizardUseV3Pipeline')?.addEventListener('change', () => {
          const room = getRoomWizardRoom();
          const envMod = globalThis.RoomWizardEnvironment;
          if (!room || !envMod) return;
          envMod.ensureRoomEnvironment(room);
          const checked = !!document.getElementById('roomWizardUseV3Pipeline')?.checked;
          room.environment.environment_pipeline_version = checked ? 'v3' : 'v2';
          RoomEditor.State.roomWizard.touched = true;
          setDirty(true);
          updateJsonText();
          renderRoomWizardEnvironmentOutputSummary(room.environment);
        });
        ['roomWizardThemeName', 'roomWizardEnvironmentNotes', 'roomWizardEnvironmentSeed', 'roomWizardLockStylepack'].forEach((id) => {
          const eventName = id === 'roomWizardLockStylepack' ? 'change' : 'input';
          document.getElementById(id)?.addEventListener(eventName, syncRoomWizardEnvironmentAuthoringFromInputs);
        });
        Object.entries(roomWizardResultsToggleMap()).forEach(([key, el]) => {
          el?.addEventListener('change', () => {
            RoomEditor.State.roomWizard.resultsToggles[key] = !!el.checked;
            const room = getRoomWizardRoom();
            if (room?.environment) {
              renderRoomWizardEnvironmentOutputSummary(room.environment);
            }
          });
        });
        document.getElementById('roomWizardReferenceUpload')?.addEventListener('change', (event) => {
          const room = getRoomWizardRoom();
          const envMod = globalThis.RoomWizardEnvironment;
          if (!room || !envMod) return;
          envMod.ensureRoomEnvironment(room);
          ensureRoomWizardEnvironmentAuthoringFields(room.environment);
          const files = Array.from(event.target?.files || []);
          if (!files.length) return;
          const timestamp = new Date().toISOString();
          const nextEntries = files.map((file, index) => ({
            id: `reference-${Date.now()}-${index + 1}`,
            label: file.name.replace(/\.[^.]+$/, '').slice(0, 80),
            file_name: file.name,
            file_type: file.type || 'image',
            file_size: file.size || 0,
            status: 'uploaded',
            pinned_to: '',
            source_value: file.name,
            uploaded_at: timestamp,
          }));
          room.environment.spec.reference_uploads = [...room.environment.spec.reference_uploads, ...nextEntries];
          setDirty(true);
          renderRoomWizardReferenceList(room.environment);
          renderRoomWizardEnvironmentOutputSummary(room.environment);
          updateJsonText();
          event.target.value = '';
        });
        document.getElementById('roomWizardArtDirectionSave')?.addEventListener('click', saveProjectArtDirectionFromWizard);
        document.getElementById('roomWizardGenerateArtDirectionConcepts')?.addEventListener('click', generateArtDirectionConceptBoard);
        document.getElementById('roomWizardAdaptTemplate')?.addEventListener('click', () => {
          adaptSelectedRoomArchetype('Rewrite this room draft so it fits the locked project style.');
        });
        document.getElementById('roomWizardGenerateComponentPrompts')?.addEventListener('click', async () => {
          const room = getRoomWizardRoom();
          const promptEl = document.getElementById('roomWizardCopilotPrompt');
          const st = document.getElementById('roomWizardCopilotStatus');
          if (!PROJECT_ID || !room || !promptEl) return;
          const description = String(promptEl.value || '').trim();
          if (!description) {
            if (st) st.textContent = 'Write a short room draft first.';
            return;
          }
          startRoomWizardWaitbar('copilot', 'Generating component prompts from the current art direction and room draft.');
          if (st) st.textContent = 'Generating component prompts…';
          try {
            const res = await fetch(projectRoomEnvironmentApiUrl(room.id, 'component-prompts'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                description,
                components: collectRoomWizardComponentPrompts()
              })
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.ok) throw new Error(json.error || 'Could not generate component prompts');
            const envMod = globalThis.RoomWizardEnvironment;
            if (envMod) envMod.ensureRoomEnvironment(room);
            room.environment.spec.description = description;
            room.environment.spec.components = json.components || room.environment.spec.components || {};
            syncRoomWizardComponentFields(room.environment);
            updateJsonText();
            setDirty(true);
            if (st) st.textContent = 'Component prompts ready — tweak them if needed, then build the environment.';
            stopRoomWizardWaitbar('copilot', 100);
          } catch (e) {
            stopRoomWizardWaitbar('copilot', 100);
            if (st) st.textContent = (e && e.message) || 'Component prompt generation failed';
          }
        });
        document.getElementById('roomWizardSimplifyDraft')?.addEventListener('click', () => {
          adaptSelectedRoomArchetype('Simplify this room draft so a novice creator can understand and edit it quickly.');
        });
        document.getElementById('roomWizardBiomeGenerateVisuals')?.addEventListener('click', async () => {
          const st = document.getElementById('roomWizardBiomeVisualStatus');
          const btn = document.getElementById('roomWizardBiomeGenerateVisuals');
          if (!PROJECT_ID || !PROJECT_BIOME_GENERATE_VISUALS_URL) {
            if (st) st.textContent = 'Open this room from a workbench project to generate biome visuals.';
            return;
          }
          if (!RoomEditor.State.copilot.serverReachable || !RoomEditor.State.copilot.geminiConfigured) {
            if (st) st.textContent = 'Server or Gemini key unavailable — check the hint above.';
            return;
          }
          if (!RoomEditor.State.artDirection?.locked) {
            if (st) st.textContent = 'Lock project art direction first.';
            return;
          }
          const ok = window.confirm(
            'Replace biome template PNGs under art_direction_biomes with Gemini output? This may take a minute and uses API quota.'
          );
          if (!ok) return;
          const draft = String(document.getElementById('roomWizardCopilotPrompt')?.value || '').trim().slice(0, 500);
          if (btn) btn.disabled = true;
          if (st) st.textContent = 'Generating biome visuals…';
          startRoomWizardWaitbar('copilot', 'Generating biome template visuals (Gemini).');
          try {
            const res = await fetch(PROJECT_BIOME_GENERATE_VISUALS_URL, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                confirm_overwrite: true,
                extra_prompt: draft || undefined
              })
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.ok) {
              throw new Error(json.error || 'Biome visual generation failed');
            }
            RoomEditor.State.artDirection = json.art_direction || RoomEditor.State.artDirection;
            updateRoomWizardBiomePackSummary();
            const failed = Array.isArray(json.results) ? json.results.filter((r) => r && !r.ok) : [];
            if (!json.used_ai) {
              if (st) st.textContent = 'Gemini did not return images — check server logs and GEMINI_IMAGE_MODEL.';
            } else if (failed.length) {
              if (st) st.textContent = `Partial: ${failed.length} layer(s) failed (${failed.map((f) => f.component_type).join(', ')}).`;
            } else {
              if (st) st.textContent = 'Biome template PNGs updated.';
              showToast('Biome template visuals updated.', 'success');
            }
            stopRoomWizardWaitbar('copilot', 100);
          } catch (e) {
            stopRoomWizardWaitbar('copilot', 100);
            if (st) st.textContent = (e && e.message) || 'Biome generation failed';
          } finally {
            if (btn) btn.disabled = false;
          }
        });
        document.getElementById('roomWizardGeminiImageProbeBtn')?.addEventListener('click', async () => {
          const st = document.getElementById('roomWizardGeminiProbeStatus');
          if (st) st.textContent = 'Testing…';
          try {
            const r = await fetch(`${API_PING_URL}?probe=1`, { cache: 'no-store' });
            const j = await r.json().catch(() => ({}));
            const probe = j.copilot && j.copilot.geminiImageProbe;
            if (j.copilot && j.copilot.lastGeminiImageError !== undefined) {
              RoomEditor.State.copilot.geminiLastError = j.copilot.lastGeminiImageError;
            }
            if (st) {
              if (probe && probe.ok) st.textContent = 'Image API returned an image.';
              else st.textContent = probe && probe.error ? `Failed: ${probe.error}` : 'Probe did not succeed.';
            }
            updateRoomWizardCopilotHintUi();
          } catch (e) {
            if (st) st.textContent = (e && e.message) ? String(e.message) : 'Request failed';
          }
        });
        document.getElementById('roomWizardCopilotGenerate')?.addEventListener('click', async () => {
          const copilotMod = globalThis.RoomWizardEnvironmentCopilot;
          const room = getRoomWizardRoom();
          const promptEl = document.getElementById('roomWizardCopilotPrompt');
          const st = document.getElementById('roomWizardCopilotStatus');
          const btn = document.getElementById('roomWizardCopilotGenerate');
          if (!copilotMod || !room || !promptEl) return;
          const prompt = String(promptEl.value || '').trim();
          if (!prompt) {
            if (st) st.textContent = 'Enter a short description first.';
            return;
          }
          if (PROJECT_ID) {
            clearRoomWizardCopilotPreview();
            if (st) st.textContent = 'Building room spec…';
            if (btn) btn.disabled = true;
            RoomEditor.State.roomWizard.aiRequestPending = true;
            startRoomWizardWaitbar('copilot', 'Building the room environment spec.');
            try {
              const specRes = await fetch(projectRoomEnvironmentApiUrl(room.id, 'spec'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  environment_pipeline_version: room.environment?.environment_pipeline_version || 'v2',
                  description: prompt,
                  components: collectRoomWizardComponentPrompts()
                })
              });
              const specJson = await specRes.json().catch(() => ({}));
              if (!specRes.ok || !specJson.ok) {
                throw new Error(specJson.error || 'Could not build room environment spec');
              }
              replaceRoomWizardEnvironmentPreservingAuthoring(room, specJson.environment || room.environment);
              syncRoomWizardEnvironmentFromRoom();
              if (st) st.textContent = 'Rendering previews…';
              startRoomWizardWaitbar('copilot', 'Rendering room-aware environment previews.');
              const previewRes = await fetch(projectRoomEnvironmentApiUrl(room.id, 'previews'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  spec: room.environment?.spec || {},
                  ...roomWizardAnalyticsContext(room, { request_kind: 'generate' }),
                })
              });
              const previewJson = await previewRes.json().catch(() => ({}));
              if (!previewRes.ok || !previewJson.ok) {
                throw new Error(previewJson.error || 'Could not generate previews');
              }
              replaceRoomWizardEnvironmentPreservingAuthoring(room, previewJson.environment || room.environment);
              RoomEditor.State.roomWizard.copilotPreview = {
                themeId: room.environment?.themeId || 'custom',
                tags: room.environment?.tags || [],
                rationale: room.environment?.spec?.description || ''
              };
              renderRoomWizardCopilotPreview(RoomEditor.State.roomWizard.copilotPreview);
              renderRoomWizardEnvironmentPreview(room.environment);
              renderRoomWizardPreviewGallery(room.environment?.preview || {});
              renderRoomWizardEnvironmentOutputSummary(room.environment);
              updateJsonText();
              if (st) st.textContent = 'Pictures ready — open 2 · Preview & build to approve one.';
              stopRoomWizardWaitbar('copilot', 100);
            } catch (e) {
              stopRoomWizardWaitbar('copilot', 100);
              if (st) st.textContent = (e && e.message) || 'Environment generation failed';
              postRoomWizardFeedback(room, 'generation_error', { message: (e && e.message) || 'Environment generation failed' });
            } finally {
              RoomEditor.State.roomWizard.aiRequestPending = false;
              if (btn) btn.disabled = false;
            }
            return;
          }
          if (!RoomEditor.State.copilot.serverReachable || !RoomEditor.State.copilot.geminiConfigured) {
            if (st) st.textContent = 'Workbench API or Gemini key unavailable — see note above.';
            return;
          }
          clearRoomWizardCopilotPreview();
          if (st) st.textContent = 'Generating…';
          if (btn) btn.disabled = true;
          startRoomWizardWaitbar('copilot', 'Generating a Gemini environment suggestion.');
          try {
            const res = await fetch(API_COPILOT_URL, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                prompt,
                roomName: room.name || '',
                roomId: room.id || ''
              })
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.ok) {
              const err = (json && json.error) || res.statusText || 'Request failed';
              if (st) st.textContent = String(err).slice(0, 200);
              stopRoomWizardWaitbar('copilot', 100);
              return;
            }
            const raw = json.data;
            let payload;
            try {
              payload = copilotMod.normalizeCopilotPayload(raw);
            } catch (e) {
              if (st) st.textContent = (e && e.message) || 'Invalid Copilot payload';
              stopRoomWizardWaitbar('copilot', 100);
              return;
            }
            RoomEditor.State.roomWizard.copilotPreview = payload;
            renderRoomWizardCopilotPreview(payload);
            if (st) st.textContent = 'Diagram ready — apply or discard. For photo previews, Load Room with a workbench project (?project_id) first.';
            stopRoomWizardWaitbar('copilot', 100);
          } catch (e) {
            stopRoomWizardWaitbar('copilot', 100);
            if (st) st.textContent = (e && e.message) || 'Network error';
          } finally {
            if (btn) btn.disabled = false;
          }
        });
        document.getElementById('roomWizardCopilotApply')?.addEventListener('click', () => {
          const copilotMod = globalThis.RoomWizardEnvironmentCopilot;
          const envMod = globalThis.RoomWizardEnvironment;
          const room = getRoomWizardRoom();
          const preview = RoomEditor.State.roomWizard.copilotPreview;
          if (!envMod || !room || !preview) return;
          if (PROJECT_ID) {
            envMod.ensureRoomEnvironment(room);
            room.environment.themeId = preview.themeId;
            room.environment.tags = Array.isArray(preview.tags) ? [...preview.tags] : [];
            room.environment.spec.description = preview.rationale || room.environment.spec.description || '';
          } else {
            if (!copilotMod) return;
            copilotMod.applyCopilotPayloadToRoom(room, preview, envMod);
          }
          RoomEditor.State.roomWizard.touched = true;
          setDirty(true);
          updateJsonText();
          syncRoomWizardEnvironmentFromRoom();
          clearRoomWizardCopilotPreview();
          setStatus(PROJECT_ID ? 'Applied planner suggestion to local room fields.' : 'Applied Copilot suggestion to theme and tags.', 'success');
        });
        document.getElementById('roomWizardPreviewRevise')?.addEventListener('click', async () => {
          const room = getRoomWizardRoom();
          const st = document.getElementById('roomWizardCopilotStatus');
          const revisionEl = document.getElementById('roomWizardPreviewRevision');
          const promptEl = document.getElementById('roomWizardCopilotPrompt');
          if (!PROJECT_ID || !room || !revisionEl || !promptEl) return;
          const instruction = String(revisionEl.value || '').trim();
          if (!instruction) {
            if (st) st.textContent = 'Add a revision request first.';
            return;
          }
          startRoomWizardWaitbar('copilot', 'Revising the room environment and regenerating previews.');
          RoomEditor.State.roomWizard.aiRequestPending = true;
          if (st) st.textContent = 'Revising environment…';
          try {
            const reviseRes = await fetch(projectRoomEnvironmentApiUrl(room.id, 'revise'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                instruction,
                ...roomWizardAnalyticsContext(room, { request_kind: 'revise' }),
              })
            });
            const reviseJson = await reviseRes.json().catch(() => ({}));
            if (!reviseRes.ok || !reviseJson.ok) throw new Error(reviseJson.error || 'Could not revise room environment');
            promptEl.value = reviseJson.draft_description || promptEl.value;
            if (st) st.textContent = 'Building revised room spec…';
            const specRes = await fetch(projectRoomEnvironmentApiUrl(room.id, 'spec'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ description: promptEl.value, components: collectRoomWizardComponentPrompts() })
            });
            const specJson = await specRes.json().catch(() => ({}));
            if (!specRes.ok || !specJson.ok) throw new Error(specJson.error || 'Could not build revised room spec');
            replaceRoomWizardEnvironmentPreservingAuthoring(room, specJson.environment || room.environment);
            if (st) st.textContent = 'Rendering revised previews…';
            const previewRes = await fetch(projectRoomEnvironmentApiUrl(room.id, 'previews'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                spec: room.environment?.spec || {},
                ...roomWizardAnalyticsContext(room, { request_kind: 'revise' }),
              })
            });
            const previewJson = await previewRes.json().catch(() => ({}));
            if (!previewRes.ok || !previewJson.ok) throw new Error(previewJson.error || 'Could not render revised previews');
            replaceRoomWizardEnvironmentPreservingAuthoring(room, previewJson.environment || room.environment);
            revisionEl.value = '';
            renderRoomWizardEnvironmentPreview(room.environment);
            renderRoomWizardCopilotPreview({
              themeId: room.environment?.themeId || 'custom',
              tags: room.environment?.tags || [],
              rationale: room.environment?.spec?.description || ''
            });
            renderRoomWizardPreviewGallery(room.environment?.preview || {});
            renderRoomWizardEnvironmentOutputSummary(room.environment);
            updateJsonText();
            setDirty(true);
            if (st) st.textContent = 'Revised previews ready — approve one to push it into Open Game.';
            stopRoomWizardWaitbar('copilot', 100);
          } catch (e) {
            stopRoomWizardWaitbar('copilot', 100);
            if (st) st.textContent = (e && e.message) || 'Revision failed';
            postRoomWizardFeedback(room, 'generation_error', { message: (e && e.message) || 'Revision failed' });
          } finally {
            RoomEditor.State.roomWizard.aiRequestPending = false;
          }
        });
        document.getElementById('roomWizardReviewGoDescribe')?.addEventListener('click', () => {
          setRoomWizardEnvStep('describe');
        });
        document.getElementById('roomWizardEnvironmentOutputSummary')?.addEventListener('click', async (event) => {
          const slotBtn = event.target.closest('[data-rw-bespoke-slot-action]');
          if (slotBtn) {
            event.preventDefault();
            const action = slotBtn.getAttribute('data-rw-bespoke-slot-action');
            const slotId = slotBtn.getAttribute('data-rw-bespoke-slot-id');
            if (!slotId || (action !== 'regen' && action !== 'iterate')) return;
            const room = getRoomWizardRoom();
            const st = document.getElementById('roomWizardCopilotStatus');
            if (!PROJECT_ID || !room?.id) return;
            if (!room.environment?.preview?.approved_image_id) {
              if (st) st.textContent = 'Approve a room preview before regenerating assets.';
              return;
            }
            if (RoomEditor.State.roomWizard.aiRequestPending) return;
            RoomEditor.State.roomWizard.aiRequestPending = true;
            const iterate = action === 'iterate';
            const waitMs = roomWizardEstimateBespokeAssetWaitMs(room, { slotId });
            const waitMin = Math.max(1, Math.round(waitMs / 60000));
            startRoomWizardWaitbar(
              'copilot',
              `${iterate ? 'Iterating one asset' : 'Regenerating one asset'} (~${waitMin} min est., Gemini)…`,
              waitMs
            );
            if (st) {
              st.textContent = iterate
                ? `Iterating with Gemini… about ${waitMin} min typical for one slot.`
                : `Regenerating with Gemini… about ${waitMin} min typical for one slot.`;
            }
            try {
              const res = await fetch(projectRoomEnvironmentApiUrl(room.id, 'generate-assets'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  preview_id: room.environment.preview.approved_image_id,
                  environment_pipeline_version: room.environment?.environment_pipeline_version || 'v2',
                  slot_id: slotId,
                  iterate_from_current: iterate,
                }),
              });
              const json = await res.json().catch(() => ({}));
              if (!res.ok || !json.ok) throw new Error(json.error || 'Could not regenerate this asset');
              replaceRoomWizardEnvironmentPreservingAuthoring(room, json.environment || room.environment);
              renderRoomWizardEnvironmentPreview(room.environment);
              renderRoomWizardPreviewGallery(room.environment.preview || {});
              renderRoomWizardEnvironmentOutputSummary(room.environment);
              updateJsonText();
              setDirty(true);
              refreshOpenGamePreviewIfVisible(room.id);
              const bespoke = room.environment?.runtime?.bespoke_asset_manifest || {};
              const builtCount = Array.isArray(bespoke.built_slots) ? bespoke.built_slots.length : Object.values(bespoke.assets || {}).filter((a) => a && a.url).length;
              const requiredCount = Array.isArray(bespoke.required_slots) ? bespoke.required_slots.length : (Array.isArray(bespoke.generation_plan) ? bespoke.generation_plan.length : builtCount);
              const review = bespoke.runtime_review || bespoke.review || {};
              const reviewWarnings = Array.isArray(review.warning_reasons) ? review.warning_reasons : [];
              if (st) {
                st.textContent = bespoke.status === 'ready'
                  ? `Slot updated. ${builtCount}/${requiredCount || builtCount} slots built; runtime review ${review.status || 'idle'}${reviewWarnings.length ? ` · warnings: ${reviewWarnings.join(', ')}` : ''}.`
                  : `Slot run finished with issues: ${builtCount}/${requiredCount || builtCount} slots · ${review.status || 'blocked'}${Array.isArray(review.fail_reasons) && review.fail_reasons.length ? ` · ${review.fail_reasons.join(', ')}` : ''}.`;
              }
            } catch (e) {
              if (st) st.textContent = (e && e.message) || 'Asset regeneration failed';
            } finally {
              RoomEditor.State.roomWizard.aiRequestPending = false;
              stopRoomWizardWaitbar('copilot', 100);
            }
            return;
          }
          const openGameBtn = event.target.closest('.rw-runtime-review-open-game');
          if (openGameBtn) {
            const room = getRoomWizardRoom();
            if (!room?.id) return;
            postRoomWizardFeedback(room, 'open_game_preview');
            openGameWithLayout(room.id);
          }
        });
        document.getElementById('roomWizardDock')?.addEventListener('click', (event) => {
          const previewBtn = event.target.closest('button.rw-preview-card-open[data-rw-asset-src]');
          if (previewBtn) {
            event.preventDefault();
            openRoomEnvironmentAssetPreviewWindow(previewBtn.getAttribute('data-rw-asset-src'));
            return;
          }
          const assetBtn = event.target.closest('button.rw-environment-asset-open');
          if (assetBtn) {
            const src = assetBtn.getAttribute('data-rw-asset-src');
            if (src) {
              event.preventDefault();
              openRoomEnvironmentAssetPreviewWindow(src);
            }
          }
        });
        document.getElementById('roomWizardBuildEnvironmentAssets')?.addEventListener('click', async () => {
          const room = getRoomWizardRoom();
          const st = document.getElementById('roomWizardCopilotStatus');
          const buildButton = document.getElementById('roomWizardBuildEnvironmentAssets');
          if (!PROJECT_ID || !room?.id) return;
          if (!room.environment?.preview?.approved_image_id) {
            if (st) st.textContent = 'Approve a room preview before building final room assets.';
            return;
          }
          if (buildButton) {
            buildButton.disabled = true;
            buildButton.textContent = 'Building final room assets…';
          }
          const fullWaitMs = roomWizardEstimateBespokeAssetWaitMs(room, { forFullBuild: true });
          const fullWaitMin = Math.max(1, Math.round(fullWaitMs / 60000));
          const geminiSlots = roomWizardEstimateBespokeGeminiSlotCount(room, { forFullBuild: true });
          startRoomWizardWaitbar(
            'copilot',
            `Building bespoke kit (~${fullWaitMin} min est., ~${geminiSlots} Gemini slots)…`,
            fullWaitMs
          );
          if (st) {
            st.textContent = `Building bespoke production assets… about ${fullWaitMin} min estimated (${geminiSlots} Gemini slots × multi-reference image time).`;
          }
          try {
            const res = await fetch(projectRoomEnvironmentApiUrl(room.id, 'generate-assets'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                preview_id: room.environment.preview.approved_image_id,
                environment_pipeline_version: room.environment?.environment_pipeline_version || 'v2'
              })
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.ok) throw new Error(json.error || 'Could not build production assets');
            replaceRoomWizardEnvironmentPreservingAuthoring(room, json.environment || room.environment);
            renderRoomWizardEnvironmentPreview(room.environment);
            renderRoomWizardPreviewGallery(room.environment.preview || {});
            renderRoomWizardEnvironmentOutputSummary(room.environment);
            updateJsonText();
            setDirty(true);
            refreshOpenGamePreviewIfVisible(room.id);
            const bespoke = room.environment?.runtime?.bespoke_asset_manifest || {};
            const builtCount = Array.isArray(bespoke.built_slots) ? bespoke.built_slots.length : Object.values(bespoke.assets || {}).filter((item) => item && item.url).length;
            const requiredCount = Array.isArray(bespoke.required_slots) ? bespoke.required_slots.length : (Array.isArray(bespoke.generation_plan) ? bespoke.generation_plan.length : builtCount);
            const review = bespoke.runtime_review || bespoke.review || {};
            const reviewWarnings = Array.isArray(review.warning_reasons) ? review.warning_reasons : [];
            if (st) st.textContent = room.environment?.runtime?.bespoke_asset_manifest?.status === 'ready'
              ? `Bespoke biome assets complete: ${builtCount}/${requiredCount || builtCount} required slots built and runtime review passed${reviewWarnings.length ? ` with warnings: ${reviewWarnings.join(', ')}` : ''}. Open Game now uses the generated room-piece kit.`
              : `Bespoke asset generation incomplete: ${builtCount}/${requiredCount || builtCount} slots built. Runtime review: ${review.status || 'blocked'}${Array.isArray(review.fail_reasons) && review.fail_reasons.length ? ` · ${review.fail_reasons.join(', ')}` : ''}.`;
            stopRoomWizardWaitbar('copilot', 100);
          } catch (e) {
            stopRoomWizardWaitbar('copilot', 100);
            if (st) st.textContent = (e && e.message) || 'Asset generation failed';
            if (buildButton) {
              buildButton.disabled = false;
              buildButton.textContent = 'Retry final room assets';
            }
          }
        });
        document.getElementById('roomWizardCopilotDiscard')?.addEventListener('click', () => {
          const room = getRoomWizardRoom();
          if (room) postRoomWizardFeedback(room, 'discarded');
          clearRoomWizardCopilotPreview();
        });
        document.querySelectorAll('#roomWizardTerrainPresets [data-terrain-preset]').forEach((btn) => {
          btn.addEventListener('click', () => applyTerrainPresetFromWizard(btn.getAttribute('data-terrain-preset')));
        });
        document.getElementById('roomWizardTerrainDuplicate')?.addEventListener('click', roomWizardTerrainDuplicate);
        document.getElementById('roomWizardTerrainMirror')?.addEventListener('click', roomWizardTerrainMirror);
        document.getElementById('roomWizardRoomName')?.addEventListener('input', () => {
          const room = getRoomWizardRoom();
          if (!room) return;
          RoomEditor.State.roomWizard.touched = true;
          room.name = document.getElementById('roomWizardRoomName').value;
          setDirty(true);
          updateWorkflowRailPills();
          redraw();
        });
        document.getElementById('roomWizardRoomId')?.addEventListener('change', () => {
          const room = getRoomWizardRoom();
          if (!room) return;
          RoomEditor.State.roomWizard.touched = true;
          const raw = document.getElementById('roomWizardRoomId').value.trim();
          const next = raw || room.id;
          if (!/^(?:[A-Z][A-Z0-9]*-)?R\d+$/i.test(next)) {
            setStatus('Room id must look like R1 or a scoped id like RG-R1.', 'error');
            document.getElementById('roomWizardRoomId').value = room.id;
            return;
          }
          const canonical = next.replace(/(^|-)r(?=\d+$)/i, '$1R');
          const clash = RoomEditor.State.data.rooms.some((r) => r.id === canonical && r !== room);
          if (clash) {
            setStatus(`Room id ${canonical} is already in use.`, 'error');
            document.getElementById('roomWizardRoomId').value = room.id;
            return;
          }
          const oldId = room.id;
          room.id = canonical;
          if (RoomEditor.State.currentRoomId === oldId) RoomEditor.State.currentRoomId = canonical;
          if (RoomEditor.State.roomWizard.roomId === oldId) RoomEditor.State.roomWizard.roomId = canonical;
          RoomEditor.State.data.rooms.forEach((r) => {
            (r.doors || []).forEach((d) => {
              if (d.targetRoom === oldId) d.targetRoom = canonical;
            });
            (r.edgeLinks || []).forEach((link) => {
              if (link.targetRoomId === oldId) link.targetRoomId = canonical;
            });
            (r.keys || []).forEach((k) => {
              if (k.unlocksTarget === oldId) k.unlocksTarget = canonical;
            });
          });
          populateRoomSelect();
          RoomEditor.Ui.refs.roomSelect.value = canonical;
          setDirty(true);
          updateWorkflowRailPills();
          redraw();
        });
        document.querySelectorAll('input[name="roomWizardFootprint"]').forEach((radio) => {
          radio.addEventListener('change', () => {
            const room = getRoomWizardRoom();
            if (!room) return;
            RoomEditor.State.roomWizard.touched = true;
            const v = radio.value;
            if (v === 'custom') {
              document.getElementById('roomWizardCustomFootprint').hidden = false;
              return;
            }
            document.getElementById('roomWizardCustomFootprint').hidden = true;
            const dims = RW_FOOTPRINT_PRESETS[v];
            if (dims) {
              applyFootprintDimensionsToRoom(room, dims[0], dims[1]);
              setDirty(true);
              updateWorkflowRailPills();
              redraw();
            }
          });
        });
        document.getElementById('roomWizardApplyCustomFootprint')?.addEventListener('click', () => {
          const room = getRoomWizardRoom();
          if (!room) return;
          RoomEditor.State.roomWizard.touched = true;
          const w = Number(document.getElementById('roomWizardCustomW').value);
          const h = Number(document.getElementById('roomWizardCustomH').value);
          if (!Number.isFinite(w) || !Number.isFinite(h)) {
            setStatus('Enter valid width and height.', 'error');
            return;
          }
          applyFootprintDimensionsToRoom(room, w, h);
          setDirty(true);
          updateWorkflowRailPills();
          redraw();
        });
        document.getElementById('roomWizardNeighbor')?.addEventListener('change', () => {
          const room = getRoomWizardRoom();
          const neighborId = document.getElementById('roomWizardNeighbor')?.value;
          if (!room) return;
          syncRoomWizardEdgeSelects();
          if (!neighborId) return;
          const neighbor = getRoomById(neighborId);
          const myEdge = document.getElementById('roomWizardMyEdge');
          const nbEdge = document.getElementById('roomWizardNeighborEdge');
          const link = (room.edgeLinks || []).find((l) => l.targetRoomId === neighborId);
          if (link && neighbor && myEdge && nbEdge) {
            if (link.edgeIndex >= 0 && link.edgeIndex < getEdgeCount(room)) {
              myEdge.value = String(link.edgeIndex);
            }
            if (link.targetEdgeIndex >= 0 && link.targetEdgeIndex < getEdgeCount(neighbor)) {
              nbEdge.value = String(link.targetEdgeIndex);
            }
          }
        });
        document.getElementById('roomWizardBtnAlign')?.addEventListener('click', () => applyRoomWizardAlign());
        document.getElementById('roomWizardBtnHatch')?.addEventListener('click', () => applyRoomWizardHatch());
        document.getElementById('roomWizardBtnMatchWallLen')?.addEventListener('click', () => applyRoomWizardMatchWallLength());
        document.getElementById('roomWizardBtnExportJson')?.addEventListener('click', () => {
          downloadJson();
        });
        document.getElementById('roomWizardBtnExportRuntime')?.addEventListener('click', () => {
          downloadExportPackage();
        });
        document.getElementById('roomWizardBtnOpenGame')?.addEventListener('click', () => {
          const id = RoomEditor.State.roomWizard.roomId || RoomEditor.State.currentRoomId;
          openGameWithLayout(id);
        });
      }

      function addRoom() {
        const roomId = nextRoomId();
        const room = {
          id: roomId,
          name: `New Room ${roomId}`,
          global: { x: 600, y: 360 },
          size: { width: ROOM_W, height: ROOM_H },
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
        applyFootprintDimensionsToRoom(room, ROOM_W, ROOM_H);
        RoomEditor.State.data.rooms.push(room);
        RoomEditor.State.currentRoomId = roomId;
        RoomEditor.State.selectedGlobalEdge = null;
        setSelection([]);
        populateRoomSelect();
        updateEmptyStates();
        setDirty(true);
        redraw();
        setStatus(`Added ${roomId}.`);
        openRoomWizard(roomId);
      }

      function createEmptyLayoutData() {
        const roomId = 'R1';
        const room = {
          id: roomId,
          name: 'Room 1',
          global: { x: 600, y: 360 },
          size: { width: ROOM_W, height: ROOM_H },
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
        applyFootprintDimensionsToRoom(room, ROOM_W, ROOM_H);
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
          closeRoomWizard(true);
        }
        if (RoomEditor.State.data.rooms.length <= 1) {
          if (!window.confirm('Delete the last room? The layout will be empty until you add a room (settings panel: + Add Room).')) {
            return;
          }
          clearAllRoomEdgeLinks(roomId);
          RoomEditor.State.data.rooms = [];
          RoomEditor.State.currentRoomId = null;
          RoomEditor.State.selectedGlobalEdge = null;
          setSelection([]);
          populateRoomSelect();
          updateEmptyStates();
          setDirty(true);
          redraw();
          setStatus('All rooms removed. Add a room to continue editing.');
          return;
        }
        clearAllRoomEdgeLinks(roomId);
        RoomEditor.State.data.rooms = RoomEditor.State.data.rooms.filter((room) => room.id !== roomId);
        RoomEditor.State.currentRoomId = RoomEditor.State.data.rooms[0].id;
        if (RoomEditor.State.selectedGlobalEdge && RoomEditor.State.selectedGlobalEdge.roomId === roomId) {
          RoomEditor.State.selectedGlobalEdge = null;
        }
        setSelection([]);
        populateRoomSelect();
        updateEmptyStates();
        setDirty(true);
        redraw();
        setStatus(`Deleted ${roomId}.`);
      }

      function initializeData(data, message) {
        if (RoomEditor.State.roomWizard.active) {
          closeRoomWizard(true);
        }
        RoomEditor.State.data = data;
        if (!Array.isArray(RoomEditor.State.data.rooms)) RoomEditor.State.data.rooms = [];
        RoomEditor.State.data.rooms.forEach(ensureRoomShape);
        RoomEditor.State.currentRoomId = RoomEditor.State.data.rooms[0]?.id ?? null;
        RoomEditor.State.selectedGlobalEdge = null;
        RoomEditor.State.globalSnapPreview = null;
        populateRoomSelect();
        updateEmptyStates();
        setDirty(false);
        RoomEditor.State.workflowScope = 'world';
        RoomEditor.State.worldWorkflowStep = 1;
        syncLegacyEditorWorkflowStep();
        setViewMode('global');
        redraw();
        setStatus(message);
      }

      function loadSavedLayout() {
        try {
          const raw = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
          if (!raw) return null;
          const parsed = JSON.parse(raw);
          if (!parsed || !Array.isArray(parsed.rooms)) return null;
          return parsed;
        } catch (_) {
          return null;
        }
      }

      async function loadCanonicalLayoutFromApi() {
        try {
          const response = await fetch(PROJECT_LAYOUT_API_URL, { cache: 'no-store' });
          if (!response.ok) return null;
          const parsed = await response.json();
          if (!parsed || !Array.isArray(parsed.rooms)) return null;
          return parsed;
        } catch (_) {
          return null;
        }
      }

      async function loadData(forceDisk = false) {
        // Local sandbox (?local_slot=): own storage only — do not seed or API-load the big layout.
        if (LOCAL_SLOT && !PROJECT_ID) {
          RoomEditor.State.apiAvailable = false;
          updateSyncButtonState();
          const saved = loadSavedLayout();
          if (saved) {
            initializeData(
              saved,
              forceDisk
                ? `Reloaded ${saved.rooms.length} rooms from local project “${LOCAL_SLOT}”.`
                : `Loaded ${saved.rooms.length} rooms from local project “${LOCAL_SLOT}”.`
            );
          } else {
            initializeData(
              createEmptyLayoutData(),
              `New local project “${LOCAL_SLOT}” — one room (R1). Save to persist in this browser.`
            );
          }
          return;
        }

        if (forceDisk) {
          try {
            window.localStorage.removeItem(getLayoutPreferBrowserKey());
          } catch (_) {}
        }

        const apiLayout = await loadCanonicalLayoutFromApi();
        if (apiLayout) {
          RoomEditor.State.apiAvailable = true;
          updateSyncButtonState();
          const saved = !forceDisk ? loadSavedLayout() : null;
          const preferBrowser = !forceDisk && window.localStorage.getItem(getLayoutPreferBrowserKey()) === '1';
          if (preferBrowser && (!saved || !Array.isArray(saved.rooms) || saved.rooms.length === 0)) {
            try {
              window.localStorage.removeItem(getLayoutPreferBrowserKey());
            } catch (_) {}
          } else if (preferBrowser && saved && Array.isArray(saved.rooms) && saved.rooms.length > 0) {
            initializeData(
              saved,
              `Loaded ${saved.rooms.length} rooms from your last browser save (overrides server until you Sync canonical or Reload from disk).`
            );
            return;
          }
          initializeData(
            apiLayout,
            forceDisk
              ? `Reloaded ${apiLayout.rooms.length} rooms from ${PROJECT_ID ? 'the active workbench project' : 'local canonical room-layout-data.json'}`
              : `Loaded ${apiLayout.rooms.length} rooms from ${PROJECT_ID ? 'the active workbench project' : 'local canonical room-layout-data.json'}`
          );
          return;
        }

        RoomEditor.State.apiAvailable = false;
        updateSyncButtonState();

        const savedOffline = !forceDisk ? loadSavedLayout() : null;
        if (savedOffline && Array.isArray(savedOffline.rooms) && savedOffline.rooms.length > 0) {
          initializeData(
            savedOffline,
            PROJECT_ID
              ? `Workbench layout API unavailable — restored ${savedOffline.rooms.length} rooms from your last browser save. Reconnect and use Sync canonical when the server is back.`
              : `Canonical layout API unavailable — restored ${savedOffline.rooms.length} rooms from your last browser save.`
          );
          return;
        }

        try {
          const response = await fetch(DATA_URL, { cache: 'no-store' });
          if (!response.ok) throw new Error(`Failed to load ${DATA_URL}`);
          const fetched = await response.json();
          initializeData(
            fetched,
            forceDisk
              ? `Reloaded ${fetched.rooms.length} rooms from room-layout-data.json`
              : `Loaded ${fetched.rooms.length} rooms from room-layout-data.json`
          );
          return;
        } catch (error) {
          const saved = !forceDisk ? loadSavedLayout() : null;
          if (saved) {
            initializeData(saved, `Loaded ${saved.rooms.length} rooms from browser scratch save.`);
            return;
          }
          const sd = RoomEditor.State.SEED_DATA;
          const seedSnapshot =
            sd && typeof sd === 'object'
              ? structuredClone(sd)
              : createEmptyLayoutData();
          initializeData(
            seedSnapshot,
            forceDisk
              ? `Disk reload unavailable under file:// (${error.message}) — showing embedded seed layout.`
              : `Using embedded seed data. Canonical file unavailable and no scratch save found (${error.message})`
          );
        }
      }

      function applyJsonText() {
        try {
          const parsed = JSON.parse(RoomEditor.Ui.refs.jsonText.value);
          if (!parsed.rooms || !Array.isArray(parsed.rooms) || parsed.rooms.length === 0) {
            throw new Error('JSON must contain a non-empty rooms array.');
          }
          RoomEditor.State.data = parsed;
          RoomEditor.State.data.rooms.forEach(ensureRoomShape);
          if (!RoomEditor.State.data.rooms.find((room) => room.id === RoomEditor.State.currentRoomId)) {
            RoomEditor.State.currentRoomId = RoomEditor.State.data.rooms[0].id;
          }
          RoomEditor.State.selectedGlobalEdge = null;
          RoomEditor.State.globalSnapPreview = null;
          populateRoomSelect();
          setDirty(true);
          redraw();
          setStatus('Applied JSON from editor.');
        } catch (error) {
          setStatus(`JSON error: ${error.message}`, 'error');
        }
      }

      async function downloadJson() {
        const serialized = JSON.stringify(RoomEditor.State.data, null, 2);
        const blob = new Blob([serialized], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = PROJECT_LAYOUT_DOWNLOAD_NAME;
        a.click();
        URL.revokeObjectURL(url);
        setStatus(`Downloaded ${PROJECT_LAYOUT_DOWNLOAD_NAME}`);
      }

      function sleep(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
      }

      async function downloadExportPackage() {
        if (!RoomEditor.State.data) {
          setStatus('No layout data to export', 'error');
          return;
        }
        const gen = globalThis.RoomLayoutExportPackage && globalThis.RoomLayoutExportPackage.generateExportPackage;
        if (typeof gen !== 'function') {
          setStatus('Runtime export module failed to load (js/wizard/export-package.js).', 'error');
          return;
        }
        const report = RoomEditor.State.lastValidationReport || validateLayout(RoomEditor.State.data);
        RoomEditor.State.lastValidationReport = report;
        const pkg = gen(RoomEditor.State.data, report);

        const downloads = [
          { name: 'level_manifest.json', data: pkg.manifest },
          { name: 'room_layout.json', data: pkg.roomLayout },
          { name: 'world_graph.json', data: pkg.worldGraph },
          ...Object.entries(pkg.roomFiles).map(([fname, data]) => ({
            name: `room_${fname}`,
            data
          }))
        ];

        for (let i = 0; i < downloads.length; i += 1) {
          const { name, data } = downloads[i];
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = name;
          a.click();
          URL.revokeObjectURL(url);
          if (i < downloads.length - 1) await sleep(200);
        }

        const roomFileCount = Object.keys(pkg.roomFiles).length;
        setStatus(
          `Runtime export: ${downloads.length} files (manifest, full layout, world graph, ${roomFileCount} room file${roomFileCount === 1 ? '' : 's'}). Allow multiple downloads if the browser prompts.`,
          'success'
        );
      }

      function encodeLayoutForHash() {
        return encodeURIComponent(btoa(unescape(encodeURIComponent(JSON.stringify(RoomEditor.State.data)))));
      }

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
        const encoded = encodeLayoutForHash();
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

      async function savePermanent() {
        const serialized = JSON.stringify(RoomEditor.State.data, null, 2);
        try {
          window.localStorage.setItem(LAYOUT_STORAGE_KEY, serialized);
          window.localStorage.setItem(getLayoutPreferBrowserKey(), '1');
        } catch (_) {}

        if (RoomEditor.State.fileHandle) {
          try {
            const writable = await RoomEditor.State.fileHandle.createWritable();
            await writable.write(serialized);
            await writable.close();
            setDirty(false);
            // Task 2.5c: Show "Saved ✓" briefly — use text-node manipulation to preserve dirty dot span
            const saveBtn = document.getElementById('savePermanent');
            const textNode = Array.from(saveBtn.childNodes).find((n) => n.nodeType === Node.TEXT_NODE);
            const originalText = textNode ? textNode.textContent : 'Save Local';
            if (textNode) textNode.textContent = ' Local Saved ✓ ';
            setTimeout(() => {
              if (textNode) textNode.textContent = originalText;
            }, 1800);
            setStatus('Saved locally to this device and to the selected file.', 'success');
            return;
          } catch (_) {}
        }

        setDirty(false);
        // Task 2.5c: Show "Saved ✓" briefly — use text-node manipulation to preserve dirty dot span
        const saveBtn = document.getElementById('savePermanent');
        const textNode = Array.from(saveBtn.childNodes).find((n) => n.nodeType === Node.TEXT_NODE);
        const originalText = textNode ? textNode.textContent : 'Save Local';
        if (textNode) textNode.textContent = ' Local Saved ✓ ';
        setTimeout(() => {
          if (textNode) textNode.textContent = originalText;
        }, 1800);
        setStatus('Saved locally to this device. Use Sync Canonical to update the active workbench project.', 'success');
      }

      async function syncCanonicalJson() {
        if (!RoomEditor.State.apiAvailable) {
          setStatus('Canonical sync requires the Sprite Workbench server (same origin as this page). Use Export JSON instead.');
          return;
        }
        try {
          const serialized = JSON.stringify(RoomEditor.State.data, null, 2);
          const response = await fetch(PROJECT_LAYOUT_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: serialized
          });
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          setDirty(false);
          try {
            window.localStorage.setItem(LAYOUT_STORAGE_KEY, serialized);
          } catch (_) {}
          try {
            window.localStorage.removeItem(getLayoutPreferBrowserKey());
          } catch (_) {}
          setStatus(PROJECT_ID
            ? 'Saved current layout into the active workbench project.'
            : 'Synced current layout into canonical room-layout-data.json. Commit and push next.');
          showToast('Canonical layout synced successfully.');
        } catch (error) {
          setStatus(`Canonical sync cancelled or failed: ${error.message}`);
        }
      }

      function clearSavedLayout() {
        window.localStorage.removeItem(LAYOUT_STORAGE_KEY);
        try {
          window.localStorage.removeItem(getLayoutPreferBrowserKey());
        } catch (_) {}
        setStatus('Cleared saved layout from local storage.');
      }

      async function saveJsonToFile() {
        try {
          if (!window.showSaveFilePicker) {
            downloadJson();
            setStatus('File System Access API unavailable. Downloaded JSON instead.');
            return;
          }
          if (!RoomEditor.State.fileHandle) {
            RoomEditor.State.fileHandle = await window.showSaveFilePicker({
              suggestedName: PROJECT_LAYOUT_DOWNLOAD_NAME,
              types: [{ description: 'JSON Files', accept: { 'application/json': ['.json'] } }]
            });
          }
          const writable = await RoomEditor.State.fileHandle.createWritable();
          await writable.write(JSON.stringify(RoomEditor.State.data, null, 2));
          await writable.close();
          setStatus('Saved JSON to file.', 'success');
        } catch (error) {
          setStatus(`Save cancelled or failed: ${error.message}`, 'error');
        }
      }

      // ── Task 2.4: Dirty State ──
      function setDirty(isDirty) {
        RoomEditor.State.isDirty = isDirty;
        const dot = document.getElementById('dirtyDot');
        if (dot) dot.style.display = isDirty ? 'inline-block' : 'none';
        document.title = isDirty
          ? '• Room Layout Editor'
          : 'Room Layout Editor';
      }

      // ── Task 2.2: renderInventory and renderInventorySection ──
      function selectItemById(itemId) {
        const room = currentRoom();
        if (!room) return;
        // Check all item types
        for (const platform of room.platforms) {
          if (platform.id === itemId) {
            setSelection([{ kind: 'platform', id: itemId }]);
            syncPropertyInputs();
            redraw();
            return;
          }
        }
        for (const door of room.doors) {
          if (door.id === itemId) {
            setSelection([{ kind: 'door', id: itemId }]);
            syncPropertyInputs();
            redraw();
            return;
          }
        }
        for (const key of room.keys) {
          if (key.id === itemId) {
            setSelection([{ kind: 'key', id: itemId }]);
            syncPropertyInputs();
            redraw();
            return;
          }
        }
        for (const ability of room.abilities) {
          if (ability.id === itemId) {
            setSelection([{ kind: 'ability', id: itemId }]);
            syncPropertyInputs();
            redraw();
            return;
          }
        }
        for (const mover of room.movingPlatforms) {
          if (mover.id === itemId) {
            setSelection([{ kind: 'mover', id: itemId }]);
            syncPropertyInputs();
            redraw();
            return;
          }
        }
      }

      function deleteItemById(itemId) {
        const room = currentRoom();
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
          setSelection([]);
        }
        setDirty(true);
        redraw();
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
            selectItemById(item.id);
          });
          delBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteItemById(item.id);
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
        renderInventorySection('abilities', room.abilities || [], (a) => getAbilityLabel(a.type) || a.id, 'invListAbilities', 'invCountAbilities');
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

      // ── Task 2.3: Empty States ──
      function updateEmptyStates() {
        const noRooms = !RoomEditor.State.data || !RoomEditor.State.data.rooms || RoomEditor.State.data.rooms.length === 0;
        const noRoomsEl = document.getElementById('emptyStateNoRooms');
        const noDataEl = document.getElementById('emptyStateNoData');
        const roomCanvasEl = document.getElementById('roomCanvas');
        if (noRoomsEl) noRoomsEl.style.display = noRooms ? 'flex' : 'none';
        if (noDataEl) noDataEl.style.display = 'none';
        if (roomCanvasEl) roomCanvasEl.style.display = noRooms ? 'none' : 'block';
      }

      // ── Task 2.3: Empty canvas hint ──
      function renderEmptyRoomHint() {
        const room = currentRoom();
        if (!room || (room.polygon && room.polygon.length > 0)) return;
        const ctx = roomCanvas.getContext('2d');
        ctx.save();
        ctx.fillStyle = 'rgba(93, 120, 112, 0.6)';
        ctx.font = '14px "Plus Jakarta Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Click to place vertices and define this room\'s shape', roomCanvas.width / 2, roomCanvas.height / 2 - 10);
        ctx.font = '12px "Plus Jakarta Sans", sans-serif';
        ctx.fillStyle = 'rgba(93, 120, 112, 0.4)';
        ctx.fillText('Hold Shift and click to close the polygon', roomCanvas.width / 2, roomCanvas.height / 2 + 14);
        ctx.restore();
      }

      // ── Sprint 3: validateLayout (pure) + validation UI — docs/room-layout-validation.md ──
      function validateLayout(data) {
        const report = {
          run_at: new Date().toISOString(),
          level_1: { passed: true, checks: [] },
          level_2: { passed: true, checks: [] },
          summary: { errors: 0, warnings: 0 }
        };

        function fail(level, id, roomId, msg) {
          report[`level_${level}`].passed = false;
          report[`level_${level}`].checks.push({ id, room: roomId, severity: 'error', message: msg });
          report.summary.errors += 1;
        }

        function warn(level, id, roomId, msg) {
          report[`level_${level}`].checks.push({ id, room: roomId, severity: 'warning', message: msg });
          report.summary.warnings += 1;
        }

        const rooms = (data && data.rooms) || [];
        const roomIds = new Set(rooms.map((r) => r && r.id).filter(Boolean));

        const seenIds = {};
        rooms.forEach((r) => {
          const rid = r && r.id;
          if (rid == null || rid === '') return;
          if (seenIds[rid]) fail(1, 'L1-001', rid, `Duplicate room ID: ${rid}`);
          seenIds[rid] = true;
        });

        rooms.forEach((room) => {
          const rid = room && room.id != null ? room.id : '?';

          if (!room.polygon || room.polygon.length < 3) {
            fail(1, 'L1-002', rid, `Room ${rid} has fewer than 3 vertices (has ${(room.polygon || []).length})`);
          }

          (room.doors || []).forEach((door) => {
            if (door.targetRoom && !roomIds.has(door.targetRoom)) {
              fail(1, 'L1-003', rid, `Door ${door.id} targets non-existent room: ${door.targetRoom}`);
            }
          });

          (room.edgeLinks || []).forEach((link) => {
            const polyLen = (room.polygon || []).length;
            const targetRoom = rooms.find((r) => r.id === link.targetRoomId);
            const ei = Number(link.edgeIndex);
            if (Number.isInteger(ei) && ei >= polyLen) {
              fail(1, 'L1-004', rid, `Edge link in ${rid} references edge index ${link.edgeIndex} but room only has ${polyLen} edges`);
            }
            if (targetRoom) {
              const targetPolyLen = (targetRoom.polygon || []).length;
              const tei = Number(link.targetEdgeIndex);
              if (Number.isInteger(tei) && tei >= targetPolyLen) {
                fail(1, 'L1-004', rid, `Edge link in ${rid} targets edge index ${link.targetEdgeIndex} in ${link.targetRoomId} which only has ${targetPolyLen} edges`);
              }
            } else if (link.targetRoomId) {
              fail(1, 'L1-003', rid, `Edge link in ${rid} targets non-existent room: ${link.targetRoomId}`);
            }
          });

          const elementIds = new Set();
          [room.platforms, room.doors, room.keys, room.abilities, room.movingPlatforms].forEach((list) => {
            (list || []).forEach((el) => {
              if (!el || el.id == null) return;
              if (elementIds.has(el.id)) fail(1, 'L1-005', rid, `Duplicate element ID ${el.id} in room ${rid}`);
              elementIds.add(el.id);
            });
          });
        });

        const hasPlayerStart = rooms.some((r) => {
          const p = r.playerStart;
          return p && Number.isFinite(Number(p.x)) && Number.isFinite(Number(p.y));
        });
        if (!hasPlayerStart) fail(1, 'L1-006', null, 'No player start position defined in any room');

        function platformSpanX(p) {
          const w = (p.len || 1) * TILE;
          return { left: p.x, right: p.x + w };
        }

        function horizontalGapBetweenPlatforms(a, b) {
          const A = platformSpanX(a);
          const B = platformSpanX(b);
          return Math.max(0, Math.max(B.left - A.right, A.left - B.right));
        }

        rooms.forEach((room) => {
          const rid = room && room.id != null ? room.id : '?';
          const platforms = room.platforms || [];
          if (platforms.length < 2) return;

          const pairCap = VALIDATION_L2.maxHorizontalSeparationForPairPx;
          const vMax = VALIDATION_L2.maxVerticalStepPx;
          const hMax = VALIDATION_L2.maxHorizontalGapPx;
          const interactD = VALIDATION_L2.interactMaxDistPx;

          for (let ai = 0; ai < platforms.length; ai += 1) {
            const a = platforms[ai];
            let best = null;
            let bestY = Infinity;
            for (let bi = 0; bi < platforms.length; bi += 1) {
              if (bi === ai) continue;
              const b = platforms[bi];
              if (b.y <= a.y) continue;
              const gx = horizontalGapBetweenPlatforms(a, b);
              if (gx > pairCap) continue;
              if (b.y < bestY) {
                bestY = b.y;
                best = b;
              }
            }
            if (!best) continue;
            const verticalDelta = best.y - a.y;
            const hGap = horizontalGapBetweenPlatforms(a, best);
            if (verticalDelta > vMax) {
              warn(
                2,
                'L2-001',
                rid,
                `Platforms ${a.id} and ${best.id} in ${rid}: vertical step ${Math.round(verticalDelta)}px exceeds ${vMax}px (nearest related platform below)`
              );
            }
            if (hGap > hMax) {
              warn(
                2,
                'L2-002',
                rid,
                `Platforms ${a.id} and ${best.id} in ${rid}: horizontal gap ${Math.round(hGap)}px exceeds ${hMax}px (nearest related platform below)`
              );
            }
          }

          const allInteractable = [
            ...(room.doors || []),
            ...(room.keys || []),
            ...(room.abilities || [])
          ];
          allInteractable.forEach((item) => {
            if (item.x == null || item.y == null) return;
            const nearPlatform = platforms.some((p) => {
              const pRight = p.x + (p.len || 1) * TILE;
              const dx = Math.max(0, Math.max(p.x - item.x, item.x - pRight));
              const dy = Math.abs(item.y - p.y);
              return Math.sqrt(dx * dx + dy * dy) <= interactD;
            });
            if (!nearPlatform) {
              warn(2, 'L2-003', rid, `Element ${item.id} in ${rid} is more than ${interactD}px from any platform`);
            }
          });
        });

        report.level_1.passed = report.level_1.checks.filter((c) => c.severity === 'error').length === 0;
        report.level_2.passed = report.level_2.checks.filter((c) => c.severity === 'error').length === 0;

        return report;
      }

      function renderValidationResults(report) {
        const container = document.getElementById('validationResults');
        const badge = document.getElementById('validationSummaryBadge');
        if (!container) return;

        const allChecks = [...report.level_1.checks, ...report.level_2.checks];

        if (badge) {
          if (report.summary.errors > 0) {
            badge.textContent = `${report.summary.errors} error${report.summary.errors > 1 ? 's' : ''}`;
            badge.className = 'validation-summary-badge fail';
          } else if (report.summary.warnings > 0) {
            badge.textContent = `${report.summary.warnings} warning${report.summary.warnings > 1 ? 's' : ''}`;
            badge.className = 'validation-summary-badge warn';
          } else {
            badge.textContent = 'All checks passed';
            badge.className = 'validation-summary-badge pass';
          }
        }

        if (allChecks.length === 0) {
          container.innerHTML = '<div class="validation-pass-row">✓ All structural and traversal checks passed</div>';
          return;
        }

        container.innerHTML = allChecks
          .map((check) => {
            const sev = check.severity === 'error' ? 'error' : 'warning';
            const roomAttr = check.room != null && check.room !== '' ? ` data-room="${escapeHtml(String(check.room))}"` : '';
            return `
    <div class="validation-result-item ${sev}"${roomAttr}>
      <div class="validation-result-icon"></div>
      <div class="validation-result-body">
        <div class="validation-result-id">${escapeHtml(String(check.id))}</div>
        <div class="validation-result-msg">${escapeHtml(String(check.message))}</div>
        ${check.room ? `<div class="validation-result-room">Room: ${escapeHtml(String(check.room))}</div>` : ''}
      </div>
    </div>`;
          })
          .join('');

        container.querySelectorAll('.validation-result-item[data-room]').forEach((el) => {
          const roomId = el.getAttribute('data-room');
          if (!roomId) return;
          el.addEventListener('click', () => {
            const roomSelect = document.getElementById('roomSelect');
            if (!roomSelect) return;
            const opt = Array.from(roomSelect.options).find((o) => o.value === roomId);
            if (!opt) return;
            roomSelect.value = roomId;
            roomSelect.dispatchEvent(new Event('change'));
          });
        });
      }

      function wireEvents() {
        if (wireEvents.__wired) return;
        wireEvents.__wired = true;
        updateSyncButtonState();
        document.getElementById('runValidation')?.addEventListener('click', () => {
          if (!RoomEditor.State.data) return;
          const report = validateLayout(RoomEditor.State.data);
          RoomEditor.State.lastValidationReport = report;
          renderValidationResults(report);
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
            closeRoomWizard(true);
          }
          RoomEditor.State.currentRoomId = RoomEditor.Ui.refs.roomSelect.value;
          RoomEditor.State.pendingMoverStart = null;
          RoomEditor.State.hoverLocal = null;
          if (!RoomEditor.State.selectedGlobalEdge || RoomEditor.State.selectedGlobalEdge.roomId !== RoomEditor.State.currentRoomId) {
            RoomEditor.State.selectedGlobalEdge = null;
          }
          setSelection([]);
          if (RoomEditor.State.workflowScope === 'room' || RoomEditor.State.workflowScope === 'art-direction') {
            syncRoomWizardFormFromRoom();
          }
          // ── Task 2.5b: Room switch canvas fade ──
          roomCanvas.style.transition = 'opacity 80ms ease';
          roomCanvas.style.opacity = '0';
          setTimeout(() => {
            redraw();
            roomCanvas.style.opacity = '1';
          }, 80);
        });
        RoomEditor.Ui.refs.globalZoom?.addEventListener('input', () => {
          RoomEditor.State.globalZoom = clampZoom(Number(RoomEditor.Ui.refs.globalZoom.value || 100) / 100, GLOBAL_ZOOM_MIN, GLOBAL_ZOOM_MAX);
          updateViewControlReadouts();
          if (RoomEditor.State.viewMode === 'global') redraw();
        });
        RoomEditor.Ui.refs.roomZoomOut.addEventListener('click', () => adjustRoomZoom(-0.1));
        RoomEditor.Ui.refs.roomZoomIn.addEventListener('click', () => adjustRoomZoom(0.1));
        RoomEditor.Ui.refs.roomZoomFit?.addEventListener('click', fitRoomToCanvas);
        RoomEditor.Ui.refs.roomZoomReset.addEventListener('click', resetRoomView);
        RoomEditor.Ui.refs.roomPanLeft.addEventListener('click', () => panRoomView(-VIEW_PAN_STEP, 0));
        RoomEditor.Ui.refs.roomPanUp.addEventListener('click', () => panRoomView(0, -VIEW_PAN_STEP));
        RoomEditor.Ui.refs.roomPanDown.addEventListener('click', () => panRoomView(0, VIEW_PAN_STEP));
        RoomEditor.Ui.refs.roomPanRight.addEventListener('click', () => panRoomView(VIEW_PAN_STEP, 0));
        RoomEditor.Ui.refs.globalZoomOut.addEventListener('click', () => adjustGlobalZoom(-0.1));
        RoomEditor.Ui.refs.globalZoomIn.addEventListener('click', () => adjustGlobalZoom(0.1));
        RoomEditor.Ui.refs.globalZoomReset.addEventListener('click', resetGlobalView);
        RoomEditor.Ui.refs.globalPanLeft.addEventListener('click', () => panGlobalView(-VIEW_PAN_STEP, 0));
        RoomEditor.Ui.refs.globalPanUp.addEventListener('click', () => panGlobalView(0, -VIEW_PAN_STEP));
        RoomEditor.Ui.refs.globalPanDown.addEventListener('click', () => panGlobalView(0, VIEW_PAN_STEP));
        RoomEditor.Ui.refs.globalPanRight.addEventListener('click', () => panGlobalView(VIEW_PAN_STEP, 0));
        RoomEditor.Ui.refs.roomWidth.addEventListener('change', applyRoomSizeInputs);
        RoomEditor.Ui.refs.roomHeight.addEventListener('change', applyRoomSizeInputs);
        RoomEditor.Ui.refs.addRoom.addEventListener('click', addRoom);
        RoomEditor.Ui.refs.roomSetupBtn?.addEventListener('click', () => {
          const id = RoomEditor.State.currentRoomId;
          if (!id || !RoomEditor.State.data) return;
          openRoomWizard(id);
          redraw();
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
            redraw();
          });
        });
        RoomEditor.Ui.refs.applyProps.addEventListener('click', applyPropertyInputs);
        RoomEditor.Ui.refs.deleteSelected.addEventListener('click', deleteSelected);
        RoomEditor.Ui.refs.toggleSelectedEdge.addEventListener('click', toggleSelectedRoomEdge);
        RoomEditor.Ui.refs.duplicatePlatform.addEventListener('click', duplicatePlatform);
        RoomEditor.Ui.refs.centerRoom.addEventListener('click', centerRoom);
        RoomEditor.Ui.refs.edgeTargetRoom.addEventListener('change', () => {
          populateTargetEdgeOptions(RoomEditor.Ui.refs.edgeTargetRoom.value, null);
          updateGlobalLinkControls();
        });
        RoomEditor.Ui.refs.edgeTargetIndex.addEventListener('change', updateGlobalLinkControls);
        RoomEditor.Ui.refs.linkSelectedEdge.addEventListener('click', linkSelectedGlobalEdge);
        RoomEditor.Ui.refs.clearSelectedEdgeLink.addEventListener('click', clearSelectedGlobalEdgeLink);
        RoomEditor.Ui.refs.snapSelectedEdge.addEventListener('click', snapSelectedGlobalEdge);
        RoomEditor.Ui.refs.reloadJson.addEventListener('click', () => loadData(true));
        RoomEditor.Ui.refs.applyJson.addEventListener('click', applyJsonText);
        RoomEditor.Ui.refs.downloadJson.addEventListener('click', downloadJson);
        RoomEditor.Ui.refs.downloadRuntimePackage?.addEventListener('click', downloadExportPackage);
        RoomEditor.Ui.refs.saveJsonFile.addEventListener('click', saveJsonToFile);
        RoomEditor.Ui.refs.savePermanent.addEventListener('click', savePermanent);
        RoomEditor.Ui.refs.syncCanonicalJson.addEventListener('click', syncCanonicalJson);
        RoomEditor.Ui.refs.openGameWithLayout.addEventListener('click', () => openGameWithLayout(RoomEditor.State.currentRoomId));
        RoomEditor.Ui.refs.clearSavedLayout.addEventListener('click', clearSavedLayout);
        RoomEditor.Ui.refs.inspectorClose?.addEventListener('click', dismissSelection);

        roomCanvas.addEventListener('pointerdown', onRoomPointerDown);
        roomCanvas.addEventListener('pointermove', onRoomPointerMove);
        roomCanvas.addEventListener('touchstart', onRoomPointerDown, { passive: false });
        roomCanvas.addEventListener('touchmove', onRoomPointerMove, { passive: false });
        globalCanvas.addEventListener('pointerdown', onGlobalPointerDown);
        globalCanvas.addEventListener('pointermove', onGlobalPointerMove);
        globalCanvas.addEventListener('touchstart', onGlobalPointerDown, { passive: false });
        globalCanvas.addEventListener('touchmove', onGlobalPointerMove, { passive: false });
        window.addEventListener('pointerup', endDrag);
        window.addEventListener('pointercancel', endDrag);
        window.addEventListener('touchend', endDrag, { passive: false });
        window.addEventListener('touchcancel', endDrag, { passive: false });
        window.addEventListener('pagehide', () => {
          if (!RoomEditor.State.data || !RoomEditor.State.isDirty) return;
          try {
            window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(RoomEditor.State.data, null, 2));
            if (!LOCAL_SLOT || PROJECT_ID) {
              window.localStorage.setItem(getLayoutPreferBrowserKey(), '1');
            }
          } catch (_) {}
        });
        window.addEventListener('error', () => {
          const room = getRoomWizardRoom();
          if (RoomEditor.State.roomWizard.aiRequestPending && room) {
            postRoomWizardFeedback(room, 'crash_near_ai_use', {}, { keepalive: true });
          }
        });
        window.addEventListener('unhandledrejection', () => {
          const room = getRoomWizardRoom();
          if (RoomEditor.State.roomWizard.aiRequestPending && room) {
            postRoomWizardFeedback(room, 'crash_near_ai_use', {}, { keepalive: true });
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
              closeGamePreview();
              event.preventDefault();
              return;
            }
            if (RoomEditor.State.roomWizard.active) {
              requestCloseRoomWizard();
              event.preventDefault();
              return;
            }
            if (RoomEditor.State.selectionItems.length) {
              dismissSelection();
              event.preventDefault();
            }
            return;
          }
          if (isTypingTarget || event.metaKey || event.ctrlKey || event.altKey) return;
          const toolMap = {
            v: 'select',
            e: 'vertex',
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
          redraw();
          event.preventDefault();
        });
      }

      function installRoomWizardQaHooks() {
        window.__ROOM_WIZARD_QA__ = {
          applyResultsEnvironment(environmentPayload) {
            const room = getRoomWizardRoom() || currentRoom();
            const envMod = globalThis.RoomWizardEnvironment;
            if (!room || !envMod) {
              return { ok: false, error: 'room_or_environment_module_unavailable' };
            }
            openRoomWizard(room.id);
            setRoomWizardPhase('environment');
            room.environment = environmentPayload || room.environment;
            envMod.ensureRoomEnvironment(room);
            ensureRoomWizardEnvironmentAuthoringFields(room.environment);
            syncRoomWizardEnvironmentFromRoom();
            renderRoomWizardEnvironmentOutputSummary(room.environment);
            renderRoomWizardPreviewGallery(room.environment.preview || {});
            renderRoomWizardEnvironmentPreview(room.environment);
            setRoomWizardEnvStep('review');
            const dock = document.getElementById('roomWizardDock');
            const envPanel = document.getElementById('roomWizardPanelEnvironment');
            const setupPanel = document.getElementById('rwEnvPanelSetup');
            const resultsPanel = document.getElementById('rwEnvPanelResults');
            if (dock) {
              dock.hidden = false;
              dock.setAttribute('aria-hidden', 'false');
              dock.dataset.phase = 'environment';
            }
            if (envPanel) envPanel.hidden = false;
            if (setupPanel) setupPanel.hidden = true;
            if (resultsPanel) {
              resultsPanel.hidden = false;
              resultsPanel.scrollIntoView({ block: 'start' });
            }
            return this.inspectResultsSurface();
          },
          inspectResultsSurface() {
            const resultsPanel = document.getElementById('rwEnvPanelResults');
            const resultsTab = document.getElementById('rwEnvStepReview');
            const buildButton = document.getElementById('roomWizardBuildEnvironmentAssets');
            return {
              ok: true,
              panel_hidden: !!resultsPanel?.hidden,
              tab_selected: resultsTab?.getAttribute('aria-selected') || null,
              build_button_text: buildButton?.textContent?.trim() || '',
              build_button_disabled: !!buildButton?.disabled,
              stage_labels: Array.from(document.querySelectorAll('#rwEnvPanelResults .rw-environment-preview-label')).map((node) => node.textContent.trim()),
            };
          }
        };
      }

      window.validateLayout = validateLayout;
      window.VALIDATION_L2 = VALIDATION_L2;

      populateAbilityOptions();
      initSidebarToggle();
      installRoomWizardQaHooks();
      document.getElementById('btnNewLocalProject')?.addEventListener('click', createNewLocalProject);
      wireRoomWizardEvents();
      wireGamePreview();
      wireEvents();
      refreshProjectList().catch(() => {});
      loadData().catch((error) => {
        setStatus(`Load failed: ${error.message}`, 'error');
      });
      refreshCopilotStatus().catch(() => {});
