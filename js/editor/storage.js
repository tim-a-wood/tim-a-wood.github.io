'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Storage ? root.RoomEditor.Storage : {};

function listLocalProjectSlots() {
        const out = [];
        try {
          for (let i = 0; i < window.localStorage.length; i += 1) {
            const k = window.localStorage.key(i);
            if (k && k.startsWith(RoomEditor.Constants.LOCAL_STORAGE_PREFIX)) {
              out.push(k.slice(RoomEditor.Constants.LOCAL_STORAGE_PREFIX.length));
            }
          }
        } catch (_) {}
        return out.sort((a, b) => a.localeCompare(b));
      }

function persistCurrentLayoutToStorage() {
        if (!RoomEditor.State.data) return;
        try {
          window.localStorage.setItem(RoomEditor.State.LAYOUT_STORAGE_KEY, JSON.stringify(RoomEditor.State.data, null, 2));
          if (!RoomEditor.State.LOCAL_SLOT || RoomEditor.State.PROJECT_ID) {
            window.localStorage.setItem(RoomEditor.State.getLayoutPreferBrowserKey(), '1');
          }
        } catch (err) {
          RoomEditor.Ui.setStatus(`Could not save to browser storage: ${err.message}`, 'error');
        }
      }

function navigateToRoomEditorUrl(url) {
        if (RoomEditor.State.isDirty) {
          persistCurrentLayoutToStorage();
          RoomEditor.State.setDirty(false);
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
        const slot = RoomEditor.State.sanitizeLocalSlot(raw);
        if (!slot) {
          RoomEditor.Ui.setStatus('Invalid id. Use 1–64 chars: start with a letter or number, then letters, numbers, - or _.', 'error');
          return;
        }
        navigateToRoomEditorUrl(RoomEditor.Ui.roomEditorLocalSlotUrl(slot));
      }

function deleteLocalProjectSlot(slot) {
        const s = RoomEditor.State.sanitizeLocalSlot(slot);
        if (!s) return;
        const key = `${RoomEditor.Constants.LOCAL_STORAGE_PREFIX}${s}`;
        if (!window.confirm(`Remove saved data for local project “${s}” from this browser? This does not delete other projects.`)) {
          return;
        }
        try {
          window.localStorage.removeItem(key);
        } catch (_) {}
        if (RoomEditor.State.LOCAL_SLOT === s) {
          window.location.href = RoomEditor.Ui.roomEditorProjectUrl('');
          return;
        }
        refreshProjectList().catch(() => {});
        RoomEditor.Ui.setStatus(`Removed local project “${s}”.`, 'success');
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
          RoomEditor.Ui.setStatus(
            `Workbench project list unavailable (${detail}). Run ./scripts/start_sprite_workbench_with_env.sh and open this page from http://127.0.0.1:8766 (same host as the API). Local Layout and sandbox rows below still work.`,
            'warning'
          );
        }
        RoomEditor.Ui.syncSidebarProjectName();
        RoomEditor.Ui.renderProjectList();
      }

function updateJsonText() {
        RoomEditor.Ui.refs.jsonText.value = JSON.stringify(RoomEditor.State.data, null, 2);
        try {
          window.localStorage.setItem(RoomEditor.State.LAYOUT_STORAGE_KEY, RoomEditor.Ui.refs.jsonText.value);
          if (!RoomEditor.State.LOCAL_SLOT || RoomEditor.State.PROJECT_ID) {
            window.localStorage.setItem(RoomEditor.State.getLayoutPreferBrowserKey(), '1');
          }
        } catch (_) {}
      }

async function refreshCopilotStatus() {
        try {
          const r = await fetch(RoomEditor.Constants.API_PING_URL, { cache: 'no-store' });
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
        RoomEditor.Wizard.updateRoomWizardCopilotHintUi();
      }

function initializeData(data, message) {
        if (RoomEditor.State.roomWizard.active) {
          RoomEditor.Wizard.closeRoomWizard(true);
        }
        RoomEditor.State.data = data;
        if (!Array.isArray(RoomEditor.State.data.rooms)) RoomEditor.State.data.rooms = [];
        RoomEditor.State.data.rooms.forEach(ensureRoomShape);
        RoomEditor.State.currentRoomId = RoomEditor.State.data.rooms[0]?.id ?? null;
        RoomEditor.State.selectedGlobalEdge = null;
        RoomEditor.State.globalSnapPreview = null;
        RoomEditor.Ui.populateRoomSelect();
        RoomEditor.Ui.updateEmptyStates();
        RoomEditor.State.setDirty(false);
        RoomEditor.State.workflowScope = 'world';
        RoomEditor.State.worldWorkflowStep = 1;
        RoomEditor.State.syncLegacyEditorWorkflowStep();
        RoomEditor.State.setViewMode('global');
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus(message);
      }

function loadSavedLayout() {
        try {
          const raw = window.localStorage.getItem(RoomEditor.State.LAYOUT_STORAGE_KEY);
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
          const response = await fetch(RoomEditor.State.PROJECT_LAYOUT_API_URL, { cache: 'no-store' });
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
        if (RoomEditor.State.LOCAL_SLOT && !RoomEditor.State.PROJECT_ID) {
          RoomEditor.State.apiAvailable = false;
          RoomEditor.State.updateSyncButtonState();
          const saved = loadSavedLayout();
          if (saved) {
            initializeData(
              saved,
              forceDisk
                ? `Reloaded ${saved.rooms.length} rooms from local project “${RoomEditor.State.LOCAL_SLOT}”.`
                : `Loaded ${saved.rooms.length} rooms from local project “${RoomEditor.State.LOCAL_SLOT}”.`
            );
          } else {
            initializeData(
              RoomEditor.Model.createEmptyLayoutData(),
              `New local project “${RoomEditor.State.LOCAL_SLOT}” — one room (R1). Save to persist in this browser.`
            );
          }
          return;
        }

        if (forceDisk) {
          try {
            window.localStorage.removeItem(RoomEditor.State.getLayoutPreferBrowserKey());
          } catch (_) {}
        }

        const apiLayout = await loadCanonicalLayoutFromApi();
        if (apiLayout) {
          RoomEditor.State.apiAvailable = true;
          RoomEditor.State.updateSyncButtonState();
          const saved = !forceDisk ? loadSavedLayout() : null;
          const preferBrowser = !forceDisk && window.localStorage.getItem(RoomEditor.State.getLayoutPreferBrowserKey()) === '1';
          if (preferBrowser && (!saved || !Array.isArray(saved.rooms) || saved.rooms.length === 0)) {
            try {
              window.localStorage.removeItem(RoomEditor.State.getLayoutPreferBrowserKey());
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
              ? `Reloaded ${apiLayout.rooms.length} rooms from ${RoomEditor.State.PROJECT_ID ? 'the active workbench project' : 'local canonical room-layout-data.json'}`
              : `Loaded ${apiLayout.rooms.length} rooms from ${RoomEditor.State.PROJECT_ID ? 'the active workbench project' : 'local canonical room-layout-data.json'}`
          );
          return;
        }

        RoomEditor.State.apiAvailable = false;
        RoomEditor.State.updateSyncButtonState();

        const savedOffline = !forceDisk ? loadSavedLayout() : null;
        if (savedOffline && Array.isArray(savedOffline.rooms) && savedOffline.rooms.length > 0) {
          initializeData(
            savedOffline,
            RoomEditor.State.PROJECT_ID
              ? `Workbench layout API unavailable — restored ${savedOffline.rooms.length} rooms from your last browser save. Reconnect and use Sync canonical when the server is back.`
              : `Canonical layout API unavailable — restored ${savedOffline.rooms.length} rooms from your last browser save.`
          );
          return;
        }

        try {
          const response = await fetch(RoomEditor.Constants.DATA_URL, { cache: 'no-store' });
          if (!response.ok) throw new Error(`Failed to load ${RoomEditor.Constants.DATA_URL}`);
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
          const seedSnapshot =
            RoomEditor.State.SEED_DATA && typeof RoomEditor.State.SEED_DATA === 'object'
              ? structuredClone(RoomEditor.State.SEED_DATA)
              : RoomEditor.Model.createEmptyLayoutData();
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
          RoomEditor.Ui.populateRoomSelect();
          RoomEditor.State.setDirty(true);
          RoomEditor.Render.redraw();
          RoomEditor.Ui.setStatus('Applied JSON from editor.');
        } catch (error) {
          RoomEditor.Ui.setStatus(`JSON error: ${error.message}`, 'error');
        }
      }

async function downloadJson() {
        const serialized = JSON.stringify(RoomEditor.State.data, null, 2);
        const blob = new Blob([serialized], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = RoomEditor.State.PROJECT_LAYOUT_DOWNLOAD_NAME;
        a.click();
        URL.revokeObjectURL(url);
        RoomEditor.Ui.setStatus(`Downloaded ${RoomEditor.State.PROJECT_LAYOUT_DOWNLOAD_NAME}`);
      }

function sleep(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
      }

async function downloadExportPackage() {
        if (!RoomEditor.State.data) {
          RoomEditor.Ui.setStatus('No layout data to export', 'error');
          return;
        }
        const gen = globalThis.RoomLayoutExportPackage && globalThis.RoomLayoutExportPackage.generateExportPackage;
        if (typeof gen !== 'function') {
          RoomEditor.Ui.setStatus('Runtime export module failed to load (js/wizard/export-package.js).', 'error');
          return;
        }
        const report = RoomEditor.State.lastValidationReport || RoomEditor.Validation.validateLayout(RoomEditor.State.data);
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
        RoomEditor.Ui.setStatus(
          `Runtime export: ${downloads.length} files (manifest, full layout, world graph, ${roomFileCount} room file${roomFileCount === 1 ? '' : 's'}). Allow multiple downloads if the browser prompts.`,
          'success'
        );
      }

function encodeLayoutForHash() {
        return encodeURIComponent(btoa(unescape(encodeURIComponent(JSON.stringify(RoomEditor.State.data)))));
      }

async function savePermanent() {
        const serialized = JSON.stringify(RoomEditor.State.data, null, 2);
        try {
          window.localStorage.setItem(RoomEditor.State.LAYOUT_STORAGE_KEY, serialized);
          window.localStorage.setItem(RoomEditor.State.getLayoutPreferBrowserKey(), '1');
        } catch (_) {}

        if (RoomEditor.State.fileHandle) {
          try {
            const writable = await RoomEditor.State.fileHandle.createWritable();
            await writable.write(serialized);
            await writable.close();
            RoomEditor.State.setDirty(false);
            // Task 2.5c: Show "Saved ✓" briefly — use text-node manipulation to preserve dirty dot span
            const saveBtn = document.getElementById('savePermanent');
            const textNode = Array.from(saveBtn.childNodes).find((n) => n.nodeType === Node.TEXT_NODE);
            const originalText = textNode ? textNode.textContent : 'Save Local';
            if (textNode) textNode.textContent = ' Local Saved ✓ ';
            setTimeout(() => {
              if (textNode) textNode.textContent = originalText;
            }, 1800);
            RoomEditor.Ui.setStatus('Saved locally to this device and to the selected file.', 'success');
            return;
          } catch (_) {}
        }

        RoomEditor.State.setDirty(false);
        // Task 2.5c: Show "Saved ✓" briefly — use text-node manipulation to preserve dirty dot span
        const saveBtn = document.getElementById('savePermanent');
        const textNode = Array.from(saveBtn.childNodes).find((n) => n.nodeType === Node.TEXT_NODE);
        const originalText = textNode ? textNode.textContent : 'Save Local';
        if (textNode) textNode.textContent = ' Local Saved ✓ ';
        setTimeout(() => {
          if (textNode) textNode.textContent = originalText;
        }, 1800);
        RoomEditor.Ui.setStatus('Saved locally to this device. Use Sync Canonical to update the active workbench project.', 'success');
      }

async function syncCanonicalJson() {
        if (!RoomEditor.State.apiAvailable) {
          RoomEditor.Ui.setStatus('Canonical sync requires the Sprite Workbench server (same origin as this page). Use Export JSON instead.');
          return;
        }
        try {
          const serialized = JSON.stringify(RoomEditor.State.data, null, 2);
          const response = await fetch(RoomEditor.State.PROJECT_LAYOUT_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: serialized
          });
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          RoomEditor.State.setDirty(false);
          try {
            window.localStorage.setItem(RoomEditor.State.LAYOUT_STORAGE_KEY, serialized);
          } catch (_) {}
          try {
            window.localStorage.removeItem(RoomEditor.State.getLayoutPreferBrowserKey());
          } catch (_) {}
          RoomEditor.Ui.setStatus(RoomEditor.State.PROJECT_ID
            ? 'Saved current layout into the active workbench project.'
            : 'Synced current layout into canonical room-layout-data.json. Commit and push next.');
          RoomEditor.Ui.showToast('Canonical layout synced successfully.');
        } catch (error) {
          RoomEditor.Ui.setStatus(`Canonical sync cancelled or failed: ${error.message}`);
        }
      }

function clearSavedLayout() {
        window.localStorage.removeItem(RoomEditor.State.LAYOUT_STORAGE_KEY);
        try {
          window.localStorage.removeItem(RoomEditor.State.getLayoutPreferBrowserKey());
        } catch (_) {}
        RoomEditor.Ui.setStatus('Cleared saved layout from local storage.');
      }

async function saveJsonToFile() {
        try {
          if (!window.showSaveFilePicker) {
            downloadJson();
            RoomEditor.Ui.setStatus('File System Access API unavailable. Downloaded JSON instead.');
            return;
          }
          if (!RoomEditor.State.fileHandle) {
            RoomEditor.State.fileHandle = await window.showSaveFilePicker({
              suggestedName: RoomEditor.State.PROJECT_LAYOUT_DOWNLOAD_NAME,
              types: [{ description: 'JSON Files', accept: { 'application/json': ['.json'] } }]
            });
          }
          const writable = await RoomEditor.State.fileHandle.createWritable();
          await writable.write(JSON.stringify(RoomEditor.State.data, null, 2));
          await writable.close();
          RoomEditor.Ui.setStatus('Saved JSON to file.', 'success');
        } catch (error) {
          RoomEditor.Ui.setStatus(`Save cancelled or failed: ${error.message}`, 'error');
        }
      }

  Module.listLocalProjectSlots = listLocalProjectSlots;
  Module.persistCurrentLayoutToStorage = persistCurrentLayoutToStorage;
  Module.navigateToRoomEditorUrl = navigateToRoomEditorUrl;
  Module.createNewLocalProject = createNewLocalProject;
  Module.deleteLocalProjectSlot = deleteLocalProjectSlot;
  Module.refreshProjectList = refreshProjectList;
  Module.updateJsonText = updateJsonText;
  Module.refreshCopilotStatus = refreshCopilotStatus;
  Module.initializeData = initializeData;
  Module.loadSavedLayout = loadSavedLayout;
  Module.loadCanonicalLayoutFromApi = loadCanonicalLayoutFromApi;
  Module.loadData = loadData;
  Module.applyJsonText = applyJsonText;
  Module.downloadJson = downloadJson;
  Module.sleep = sleep;
  Module.downloadExportPackage = downloadExportPackage;
  Module.encodeLayoutForHash = encodeLayoutForHash;
  Module.savePermanent = savePermanent;
  Module.syncCanonicalJson = syncCanonicalJson;
  Module.clearSavedLayout = clearSavedLayout;
  Module.saveJsonToFile = saveJsonToFile;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Storage = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
