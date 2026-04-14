'use strict';
(function (root) {
  root.RoomEditor = root.RoomEditor || {};
const PAGE_PARAMS = new URLSearchParams(window.location.search);

const ROOM_EDITOR_SESSION_PROJECT_KEY = 'room-editor:last-project-id';

function sanitizeLocalSlot(raw) {
        const s = String(raw ?? '')
          .trim()
          .slice(0, 64);
        if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(s)) return '';
        return s;
      }

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
        isDirty: false,
        lastPlacedId: null,
        lastValidationReport: null,
        roomWizard: {
          active: false,
          phase: 'identity',
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

let PROJECT_ID = (PAGE_PARAMS.get('project_id') || '').trim();
RoomEditor.State.PROJECT_ID = PROJECT_ID;

const localSlotFromUrl = sanitizeLocalSlot(PAGE_PARAMS.get('local_slot') || '');

if (!RoomEditor.State.PROJECT_ID && !localSlotFromUrl && PAGE_PARAMS.get('no_session_project') !== '1') {
        try {
          const recovered = (sessionStorage.getItem(ROOM_EDITOR_SESSION_PROJECT_KEY) || '').trim();
          if (recovered && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$/.test(recovered)) {
            const url = new URL(window.location.href);
            url.searchParams.set('project_id', recovered);
            window.history.replaceState({}, '', url.toString());
            RoomEditor.State.PROJECT_ID = recovered;
          }
        } catch (_) {}
      }

const LOCAL_SLOT = !RoomEditor.State.PROJECT_ID ? localSlotFromUrl : '';
RoomEditor.State.LOCAL_SLOT = LOCAL_SLOT;

if (RoomEditor.State.PROJECT_ID) {
        try {
          sessionStorage.setItem(ROOM_EDITOR_SESSION_PROJECT_KEY, RoomEditor.State.PROJECT_ID);
        } catch (_) {}
      }

const PROJECT_ART_DIRECTION_URL = RoomEditor.State.PROJECT_ID
        ? `/api/projects/${encodeURIComponent(RoomEditor.State.PROJECT_ID)}/art-direction`
        : '';

const PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL = RoomEditor.State.PROJECT_ID
        ? `/api/projects/${encodeURIComponent(RoomEditor.State.PROJECT_ID)}/art-direction/generate-concepts`
        : '';

const PROJECT_BIOME_GENERATE_VISUALS_URL = RoomEditor.State.PROJECT_ID
        ? `/api/projects/${encodeURIComponent(RoomEditor.State.PROJECT_ID)}/art-direction/biome/generate-visuals`
        : '';

const PROJECT_ART_DIRECTION_TEMPLATES_URL = RoomEditor.State.PROJECT_ID
        ? `/api/projects/${encodeURIComponent(RoomEditor.State.PROJECT_ID)}/art-direction/templates`
        : '';

const PROJECT_LAYOUT_API_URL = RoomEditor.State.PROJECT_ID
        ? `/api/projects/${encodeURIComponent(RoomEditor.State.PROJECT_ID)}/room-layout`
        : RoomEditor.Constants.API_LAYOUT_URL;

function projectRoomEnvironmentApiUrl(roomId, action) {
        if (!RoomEditor.State.PROJECT_ID || !roomId) return '';
        return `/api/projects/${encodeURIComponent(RoomEditor.State.PROJECT_ID)}/rooms/${encodeURIComponent(roomId)}/environment/${action}`;
      }

function projectRoomEnvironmentFeedbackApiUrl(roomId) {
        return projectRoomEnvironmentApiUrl(roomId, 'feedback');
      }

const PROJECT_LAYOUT_DOWNLOAD_NAME = RoomEditor.State.PROJECT_ID
        ? `${RoomEditor.State.PROJECT_ID}-room-layout.json`
        : RoomEditor.State.LOCAL_SLOT
          ? `local-${RoomEditor.State.LOCAL_SLOT}-room-layout.json`
          : 'room-layout-data.json';

const LAYOUT_STORAGE_KEY = RoomEditor.State.PROJECT_ID
        ? `ashen-hollow-room-layout-v1:${RoomEditor.State.PROJECT_ID}`
        : RoomEditor.State.LOCAL_SLOT
          ? `${RoomEditor.Constants.LOCAL_STORAGE_PREFIX}${RoomEditor.State.LOCAL_SLOT}`
          : 'ashen-hollow-room-layout-v1';

function getLayoutPreferBrowserKey() {
        if (RoomEditor.State.LOCAL_SLOT && !RoomEditor.State.PROJECT_ID) return `ashen-hollow-room-layout-v1:prefer-browser:local:${RoomEditor.State.LOCAL_SLOT}`;
        if (RoomEditor.State.PROJECT_ID) return `ashen-hollow-room-layout-v1:prefer-browser:${RoomEditor.State.PROJECT_ID}`;
        return 'ashen-hollow-room-layout-v1:prefer-browser:default';
      }

const ROOM_AI_SESSION_ID = `rwai-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

RoomEditor.State.PROJECT_ART_DIRECTION_URL = PROJECT_ART_DIRECTION_URL;
RoomEditor.State.PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL = PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL;
RoomEditor.State.PROJECT_BIOME_GENERATE_VISUALS_URL = PROJECT_BIOME_GENERATE_VISUALS_URL;
RoomEditor.State.PROJECT_ART_DIRECTION_TEMPLATES_URL = PROJECT_ART_DIRECTION_TEMPLATES_URL;
RoomEditor.State.PROJECT_LAYOUT_API_URL = PROJECT_LAYOUT_API_URL;
RoomEditor.State.PROJECT_LAYOUT_DOWNLOAD_NAME = PROJECT_LAYOUT_DOWNLOAD_NAME;
RoomEditor.State.LAYOUT_STORAGE_KEY = LAYOUT_STORAGE_KEY;
RoomEditor.State.ROOM_AI_SESSION_ID = ROOM_AI_SESSION_ID;

function syncLegacyEditorWorkflowStep() {
        if (RoomEditor.State.workflowScope === 'room' || RoomEditor.State.workflowScope === 'art-direction') RoomEditor.State.editorWorkflowStep = 2;
        else if (RoomEditor.State.worldWorkflowStep === 4) RoomEditor.State.editorWorkflowStep = 3;
        else RoomEditor.State.editorWorkflowStep = 1;
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
        RoomEditor.Workflow.updateWorkflowRailPills();
      }

function dismissSelection() {
        RoomEditor.State.pendingMoverStart = null;
        RoomEditor.State.hoverLocal = null;
        setSelection([]);
        RoomEditor.Render.redraw();
      }

function selectionContains(item) {
        const key = selectionKey(item);
        return RoomEditor.State.selectionItems.some((selected) => selectionKey(selected) === key);
      }

function updateSyncButtonState() {
        RoomEditor.Ui.refs.syncCanonicalJson.disabled = !RoomEditor.State.apiAvailable;
        RoomEditor.Ui.refs.syncCanonicalJson.title = RoomEditor.State.apiAvailable
          ? (RoomEditor.State.PROJECT_ID ? 'Save this layout into the active workbench project' : 'Overwrite room-layout-data.json on this dev machine')
          : 'Open from the Sprite Workbench server (same origin as /api/layout) to enable canonical sync';
      }

function snap(value) {
        const size = Number(RoomEditor.Ui.refs.snapSize.value || 0);
        if (!size) return Math.round(value);
        return Math.round(value / size) * size;
      }

function setSelectedGlobalEdge(selection) {
        RoomEditor.State.selectedGlobalEdge = selection ? { roomId: selection.roomId, edgeIndex: selection.edgeIndex } : null;
        RoomEditor.State.globalSnapPreview = null;
        RoomEditor.Ui.refs.edgeTargetRoom.value = '';
        RoomEditor.Ui.refs.edgeTargetIndex.value = '';
        RoomEditor.Ui.updateGlobalLinkControls();
      }

function setDirty(isDirty) {
        RoomEditor.State.isDirty = isDirty;
        const dot = document.getElementById('dirtyDot');
        if (dot) dot.style.display = isDirty ? 'inline-block' : 'none';
        document.title = isDirty
          ? '• Room Layout Editor'
          : 'Room Layout Editor';
      }

  RoomEditor.State.sanitizeLocalSlot = sanitizeLocalSlot;
  RoomEditor.State.projectRoomEnvironmentApiUrl = projectRoomEnvironmentApiUrl;
  RoomEditor.State.projectRoomEnvironmentFeedbackApiUrl = projectRoomEnvironmentFeedbackApiUrl;
  RoomEditor.State.getLayoutPreferBrowserKey = getLayoutPreferBrowserKey;
  RoomEditor.State.syncLegacyEditorWorkflowStep = syncLegacyEditorWorkflowStep;
  RoomEditor.State.selectionKey = selectionKey;
  RoomEditor.State.setSelection = setSelection;
  RoomEditor.State.setViewMode = setViewMode;
  RoomEditor.State.dismissSelection = dismissSelection;
  RoomEditor.State.selectionContains = selectionContains;
  RoomEditor.State.updateSyncButtonState = updateSyncButtonState;
  RoomEditor.State.snap = snap;
  RoomEditor.State.setSelectedGlobalEdge = setSelectedGlobalEdge;
  RoomEditor.State.setDirty = setDirty;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = RoomEditor.State;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
