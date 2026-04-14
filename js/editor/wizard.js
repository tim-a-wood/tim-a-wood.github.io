'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Wizard ? root.RoomEditor.Wizard : {};

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
        const lines = mod.doorPlatformOverlapWarnings(room, RoomEditor.Constants.TILE, RoomEditor.Constants.PLATFORM_H);
        if (lines.length === 0) {
          el.innerHTML = '<p class="hint">No door / platform band overlap warnings.</p>';
        } else {
          el.innerHTML = `<ul class="rw-terrain-warn-list">${lines
            .map((t) => `<li>${RoomEditor.Ui.escapeHtml(t)}</li>`)
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

function applyTerrainPresetFromWizard(presetId) {
        const mod = globalThis.RoomWizardTerrain;
        const room = getRoomWizardRoom();
        if (!mod || !room) return;
        if (!mod.isLayoutCompleteForTerrain(room)) {
          RoomEditor.Ui.setStatus('Complete layout (name, id, footprint) before using presets.', 'warning');
          return;
        }
        const r = mod.buildTerrainPresetPlatforms(room, presetId, {
          tile: RoomEditor.Constants.TILE,
          platformH: RoomEditor.Constants.PLATFORM_H,
          tintBase: room.platforms.length
        });
        if (!r.ok || !r.platforms?.length) {
          const msg =
            RoomEditor.Constants.TERRAIN_PRESET_FAIL[r.reason] ||
            (r.reason ? `Terrain preset: ${r.reason}` : 'Terrain preset failed.');
          RoomEditor.Ui.setStatus(msg, 'warning');
          return;
        }
        const addedIds = [];
        for (const p of r.platforms) {
          const id = RoomEditor.Model.nextId(`${room.id}-P`, room.platforms);
          room.platforms.push({ ...p, id });
          addedIds.push(id);
        }
        RoomEditor.State.setSelection(addedIds.map((id) => ({ kind: 'platform', id })));
        RoomEditor.State.roomWizard.touched = true;
        RoomEditor.State.setDirty(true);
        RoomEditor.Storage.updateJsonText();
        RoomEditor.Ui.setStatus(
          `Added ${r.platforms.length} platform(s) (${presetId}). Selected on canvas — switch to Room view if needed.`,
          'success'
        );
        RoomEditor.Render.redraw();
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
          RoomEditor.Ui.setStatus('No platform to duplicate.', 'warning');
          return;
        }
        const step = Number(RoomEditor.Ui.refs.snapSize?.value) || RoomEditor.Constants.TILE;
        const clone = {
          ...selected,
          id: RoomEditor.Model.nextId(`${room.id}-P`, room.platforms),
          x: selected.x + step,
          y: selected.y
        };
        if (!mod.platformFullyInsidePolygon(clone, room.polygon, RoomEditor.Constants.TILE, RoomEditor.Constants.PLATFORM_H)) {
          RoomEditor.Ui.setStatus('Duplicate would leave the room footprint.', 'warning');
          return;
        }
        room.platforms.push(clone);
        RoomEditor.State.roomWizard.touched = true;
        RoomEditor.State.setSelection([{ kind: 'platform', id: clone.id }]);
        RoomEditor.State.setDirty(true);
        RoomEditor.Storage.updateJsonText();
        RoomEditor.Render.redraw();
        refreshTerrainWarnings();
        RoomEditor.Ui.setStatus(`Duplicated ${clone.id}.`, 'success');
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
          RoomEditor.Ui.setStatus('No platform to mirror.', 'warning');
          return;
        }
        const W = Number(room.size?.width) || 800;
        const cx = W / 2;
        const lenPx = selected.len * RoomEditor.Constants.TILE;
        const centerX = selected.x + lenPx / 2;
        const newCenterX = 2 * cx - centerX;
        let newX = newCenterX - lenPx / 2;
        newX = RoomEditor.State.snap(newX);
        const clone = {
          ...selected,
          id: RoomEditor.Model.nextId(`${room.id}-P`, room.platforms),
          x: newX,
          y: selected.y
        };
        if (!mod.platformFullyInsidePolygon(clone, room.polygon, RoomEditor.Constants.TILE, RoomEditor.Constants.PLATFORM_H)) {
          RoomEditor.Ui.setStatus('Mirror copy would leave the room footprint.', 'warning');
          return;
        }
        room.platforms.push(clone);
        RoomEditor.State.roomWizard.touched = true;
        RoomEditor.State.setSelection([{ kind: 'platform', id: clone.id }]);
        RoomEditor.State.setDirty(true);
        RoomEditor.Storage.updateJsonText();
        RoomEditor.Render.redraw();
        refreshTerrainWarnings();
        RoomEditor.Ui.setStatus(`Mirrored to ${clone.id}.`, 'success');
      }

function centerRoom() {
        const room = RoomEditor.Model.currentRoom();
        room.global.x = 600;
        room.global.y = 360;
        RoomEditor.Render.redraw();
      }

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
        RoomEditor.Model.ensureRoomShape(room);
      }

function syncRoomWizardFootprintRadios() {
        const room = getRoomWizardRoom();
        if (!room) return;
        const W = room.size?.width;
        const H = room.size?.height;
        let matched = 'custom';
        Object.keys(RoomEditor.Constants.RW_FOOTPRINT_PRESETS).forEach((key) => {
          const [pw, ph] = RoomEditor.Constants.RW_FOOTPRINT_PRESETS[key];
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
                  <strong>${RoomEditor.Ui.escapeHtml(item.label || item.file_name || 'Reference')}</strong>
                  <p class="rw-reference-meta">${RoomEditor.Ui.escapeHtml([item.file_name, item.file_type, formatRoomWizardFileSize(item.file_size)].filter(Boolean).join(' · '))}</p>
                </div>
                <div class="rw-reference-item-actions">
                  <span class="rw-stage-pill ${pinned ? 'rw-stage-pill--accent' : ''}">${RoomEditor.Ui.escapeHtml(pinned ? 'Pinned to Stylepack' : (item.status || 'uploaded'))}</span>
                  <button type="button" class="btn-secondary btn-sm rw-reference-pin" data-reference-id="${RoomEditor.Ui.escapeHtml(item.id)}" ${locked ? 'disabled' : ''}>${pinned ? 'Pinned' : 'Pin'}</button>
                  <button type="button" class="btn-secondary btn-sm rw-reference-remove" data-reference-id="${RoomEditor.Ui.escapeHtml(item.id)}" ${locked ? 'disabled' : ''}>Remove</button>
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
            RoomEditor.State.setDirty(true);
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
            RoomEditor.State.setDirty(true);
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
        RoomEditor.State.setDirty(true);
        renderRoomWizardReferenceList(room.environment);
        renderRoomWizardEnvironmentOutputSummary(room.environment);
        RoomEditor.Storage.updateJsonText();
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
        if (applyBtn) applyBtn.hidden = !!RoomEditor.State.PROJECT_ID;
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
        if (hinted) RoomEditor.Model.ensureRoomShape(hinted);
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
        const title = label ? `<title>${RoomEditor.Ui.escapeHtml(label)}</title>` : '';
        return `<rect class="${RoomEditor.Ui.escapeHtml(extraClass)}" x="${rect.x}" y="${rect.y}" width="${rect.width}" height="${rect.height}" rx="12" ry="12" fill="${fill}" stroke="${stroke}" stroke-width="8">${title}</rect>`;
      }

function roomWizardLineSvg(line, stroke, label) {
        if (!line || !line.start || !line.end) return '';
        const title = label ? `<title>${RoomEditor.Ui.escapeHtml(label)}</title>` : '';
        return `<line x1="${Number(line.start.x || 0)}" y1="${Number(line.start.y || 0)}" x2="${Number(line.end.x || 0)}" y2="${Number(line.end.y || 0)}" stroke="${stroke}" stroke-width="6" stroke-linecap="round">${title}</line>`;
      }

function roomWizardPointSvg(point, fill, radius, label) {
        if (!point) return '';
        const title = label ? `<title>${RoomEditor.Ui.escapeHtml(label)}</title>` : '';
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
            legend.push(`<span class="rw-environment-overlay-pill ${legendClass}">${RoomEditor.Ui.escapeHtml(`${layerName} ${items.length}`)}</span>`);
            meta.push(`<span>${RoomEditor.Ui.escapeHtml(`${humanizeRoomWizardLabel(layerName)} placements: ${items.length}`)}</span>`);
          }
        };

        addLayerRects(toggleState.structural, 'structural', '#f5d074', 'rgba(245,208,116,0.18)', 'rw-environment-overlay-pill--structural');
        addLayerRects(toggleState.background, 'background', '#6ab7ff', 'rgba(106,183,255,0.16)', 'rw-environment-overlay-pill--background');
        addLayerRects(toggleState.decor, 'decor', '#c084fc', 'rgba(192,132,252,0.18)', 'rw-environment-overlay-pill--decor');
        if (toggleState.decor && !(Array.isArray(manifestLayers.decor) && manifestLayers.decor.length) && plannedDecor.length) {
          plannedDecor.forEach((item, index) => {
            const rect = roomWizardDecorMarkerRect(item, index, bounds);
            const label = `${humanizeRoomWizardLabel(item?.type || 'decor')} · ${humanizeRoomWizardLabel(item?.anchor || 'anchor')} · ${humanizeRoomWizardLabel(item?.zone || 'zone')}`;
            svgParts.push(`<rect x="${rect.x}" y="${rect.y}" width="${rect.width}" height="${rect.height}" rx="12" ry="12" fill="rgba(192,132,252,0.08)" stroke="#c084fc" stroke-width="8" stroke-dasharray="18 12"><title>${RoomEditor.Ui.escapeHtml(label)}</title></rect>`);
          });
          legend.push('<span class="rw-environment-overlay-pill rw-environment-overlay-pill--decor">Decor plan</span>');
          meta.push(`<span>${RoomEditor.Ui.escapeHtml(`Planned decor markers: ${plannedDecor.length}`)}</span>`);
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
          meta.push(`<span>${RoomEditor.Ui.escapeHtml(`Anchors: ${(semanticsOverlay.anchors || []).length} · tops: ${(semanticsOverlay.platform_tops || []).length}`)}</span>`);
        }

        if (toggleState.exclusion) {
          (semanticsOverlay.decor_safe_zones || []).forEach((rect) => {
            svgParts.push(roomWizardRectSvg(rect, '#f472b6', 'rgba(244,114,182,0.12)', humanizeRoomWizardLabel(rect.zone_id || 'decor safe zone')));
          });
          (semanticsOverlay.gameplay_exclusion_zones || []).forEach((rect) => {
            svgParts.push(roomWizardRectSvg(rect, '#fb7185', 'rgba(251,113,133,0.18)', humanizeRoomWizardLabel(rect.zone_id || 'gameplay exclusion zone')));
          });
          legend.push('<span class="rw-environment-overlay-pill rw-environment-overlay-pill--exclusion">Safe and blocked zones</span>');
          meta.push(`<span>${RoomEditor.Ui.escapeHtml(`Safe zones: ${(semanticsOverlay.decor_safe_zones || []).length} · blocked zones: ${(semanticsOverlay.gameplay_exclusion_zones || []).length}`)}</span>`);
        }

        if (toggleState.validation) {
          Object.values(validationHighlights).forEach((items) => {
            (Array.isArray(items) ? items : []).forEach((item) => {
              svgParts.push(roomWizardRectSvg(item, '#f97316', 'rgba(249,115,22,0.14)', 'Validation highlight', 'rw-environment-overlay-highlight'));
            });
          });
          legend.push('<span class="rw-environment-overlay-pill rw-environment-overlay-pill--validation">Validation highlights</span>');
          meta.push(`<span>${RoomEditor.Ui.escapeHtml(`Validation highlights: ${Object.values(validationHighlights).reduce((count, items) => count + (Array.isArray(items) ? items.length : 0), 0)}`)}</span>`);
        }

        if (toggleState.unresolved) {
          (validationHighlights.unresolved_surfaces || []).forEach((item) => {
            svgParts.push(roomWizardRectSvg(item, '#f87171', 'rgba(248,113,113,0.12)', 'Unresolved surface'));
          });
          legend.push('<span class="rw-environment-overlay-pill rw-environment-overlay-pill--unresolved">Unresolved surfaces</span>');
          meta.push(`<span>${RoomEditor.Ui.escapeHtml(`Unresolved surfaces: ${(validationHighlights.unresolved_surfaces || []).length}`)}</span>`);
        }

        return `
          <section class="rw-environment-overlay-card">
            <div class="rw-environment-stage-head">
              <div>
                <p class="rw-environment-preview-label">6. Layout overlay</p>
                <strong>Layout overlay</strong>
              </div>
              <span class="rw-stage-pill">${RoomEditor.Ui.escapeHtml(`${bounds.width} × ${bounds.height}`)}</span>
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
          .map((tag) => `<span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(tag)}</span>`)
          .join('');
        const rationale = preview.rationale
          ? `<p class="rw-environment-preview-rationale">${RoomEditor.Ui.escapeHtml(preview.rationale)}</p>`
          : '';
        return `
          <section class="rw-environment-preview-card">
            <div class="rw-environment-scene ${RoomEditor.Ui.escapeHtml(preview.sceneClass)}" aria-hidden="true">
              <div class="rw-environment-scene__mist"></div>
              <div class="rw-environment-scene__glow"></div>
              <div class="rw-environment-scene__monolith rw-environment-scene__monolith--left"></div>
              <div class="rw-environment-scene__monolith rw-environment-scene__monolith--right"></div>
              <div class="rw-environment-scene__ground"></div>
            </div>
            <div class="rw-environment-preview-copy">
              <p class="rw-environment-preview-label">${RoomEditor.Ui.escapeHtml(heading)}</p>
              <div class="rw-environment-preview-headline">
                <strong>${RoomEditor.Ui.escapeHtml(preview.themeLabel)}</strong>
                <span>${RoomEditor.Ui.escapeHtml(preview.eyebrow)}</span>
              </div>
              <p class="rw-environment-preview-summary">${RoomEditor.Ui.escapeHtml(preview.summary)}</p>
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
          .map((tag) => `<span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(tag)}</span>`)
          .join('');
        return `
          <section class="rw-generated-environment-card">
            <div class="rw-generated-environment-media">
              <img src="${RoomEditor.Ui.escapeHtml(activeUrl)}" alt="${RoomEditor.Ui.escapeHtml(active.label || 'Preview')}" />
            </div>
            <div class="rw-generated-environment-copy">
              <p class="rw-environment-preview-label">Preview</p>
              <div class="rw-environment-preview-headline">
                <strong>${RoomEditor.Ui.escapeHtml(active.label || 'Preview')}</strong>
                <span>${RoomEditor.Ui.escapeHtml((active.render_level || previewState.render_level || '').toUpperCase())}</span>
              </div>
              <p class="rw-environment-preview-summary">
                ${RoomEditor.Ui.escapeHtml(envState.spec?.description || 'Generated environment concept based on the room draft, project art direction, and room layout.')}
              </p>
              ${summaryBits.length ? `<p class="rw-environment-preview-rationale">${RoomEditor.Ui.escapeHtml(summaryBits.join(' · '))}</p>` : ''}
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
          return `<span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(label)}</span>`;
        }).join('');
        const componentSchemaChips = Object.entries(componentSchemas).map(([key, item]) => {
          const status = String((schemaStatuses[key] || {}).status || 'normalized');
          const label = `${key} · ${status}`;
          const intent = String((item || {}).design_intent || '').slice(0, 48);
          return `<span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(`${label}${intent ? ` · ${intent}` : ''}`)}</span>`;
        }).join('');
        const slotGroupChips = Object.entries(slotGroupMap).map(([key, group]) => (
          `<span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(`${key}: ${group.built || 0}/${group.required || 0}`)}</span>`
        )).join('');
        const staleChips = staleComponents.map((item) => (
          `<span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(`Needs refresh: ${String(item).replace(/_/g, ' ')}`)}</span>`
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
              return `<span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(label)}</span>`;
            }).join('')
          : '';
        const coverageChips = pipelineVersion === 'v3'
          ? [
              ...(Array.isArray(plannerCoverage.missing_slots) ? plannerCoverage.missing_slots : []).map((item) => `Coverage gap: ${item}`),
              ...(Array.isArray(reviewValidation.issues) ? reviewValidation.issues : []).map((item) => `Validation: ${item}`),
            ].map((item) => `<span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(String(item).replace(/_/g, ' '))}</span>`).join('')
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
              <button type="button" class="rw-environment-asset-open rw-runtime-review-thumb" data-rw-asset-src="${RoomEditor.Ui.escapeHtml(rrUrl)}" aria-label="View runtime review full size">
                <img src="${RoomEditor.Ui.escapeHtml(rrUrl)}" alt="Runtime review screenshot" />
              </button>
              <div class="rw-runtime-review-meta">
                <span>${RoomEditor.Ui.escapeHtml(`Runtime review · ${runtimeReview.status || 'idle'}`)}</span>
                <small>${RoomEditor.Ui.escapeHtml(`${runtimeReview.review_mode || 'review'}${runtimeReview.capture_issue ? ` · ${runtimeReview.capture_issue}` : ''}`)}</small>
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
              const slotIdAttr = RoomEditor.Ui.escapeHtml(slotIdRaw);
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
                    ? `<button type="button" class="rw-environment-asset-open" data-rw-asset-src="${RoomEditor.Ui.escapeHtml(assetThumbUrl)}" aria-label="${RoomEditor.Ui.escapeHtml(openFullLabel)}">
                        <img src="${RoomEditor.Ui.escapeHtml(assetThumbUrl)}" alt="${RoomEditor.Ui.escapeHtml(item.component_type || 'asset')}" />
                      </button>`
                    : `<div class="rw-environment-asset-thumb-empty">${RoomEditor.Ui.escapeHtml(String(item.generation_source || 'missing'))}</div>`}
                  <span>${RoomEditor.Ui.escapeHtml(item.slot_id || item.component_type || 'asset')}</span>
                  <small>${RoomEditor.Ui.escapeHtml(sub.slice(0, 220))}</small>
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
          if (!list.length) return `<p class="rw-environment-stage-empty">${RoomEditor.Ui.escapeHtml(emptyText)}</p>`;
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
          return `<ul class="rw-environment-stage-list">${formatted.map((item) => `<li>${RoomEditor.Ui.escapeHtml(item)}</li>`).join('')}</ul>`;
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
                  <strong>${RoomEditor.Ui.escapeHtml(spec.theme_name || envState?.themeId || 'Untitled room environment')}</strong>
                </div>
                <div class="rw-environment-status-row">
                  <span class="${stagePillClass(bespokeManifest.status || 'idle')}">${RoomEditor.Ui.escapeHtml(bespokeManifest.status || 'idle')}</span>
                  <span class="${stagePillClass(runtimeReview.status || 'pending')}">${RoomEditor.Ui.escapeHtml(`Runtime ${runtimeReview.status || 'pending'}`)}</span>
                </div>
              </div>
            </div>
            ${generatedImagesSection}
            <details class="rw-env-review-disclosure">
              <summary>
                <p class="rw-environment-preview-label">Build details</p>
                <strong>Theme, pipeline, assets, and references</strong>
              </summary>
              <p class="rw-environment-stage-copy">${RoomEditor.Ui.escapeHtml(`${bits.join(' · ')} · ${assetText} · ${reviewText}`)}</p>
              <div class="rw-environment-chip-row">
                <span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(`Variation seed: ${spec.seed || 'not set'}`)}</span>
                <span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(`${refUploads.length} reference image${refUploads.length === 1 ? '' : 's'}`)}</span>
                <span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(`${pinnedRefs.length} pinned for this room`)}</span>
                <span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(`Room profile: ${envState?.themeId || 'custom'}`)}</span>
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
                    <strong>${RoomEditor.Ui.escapeHtml(spec.theme_name || stylepackSummary.stylepack_id || 'Room stylepack')}</strong>
                  </div>
                  <span class="${stagePillClass(stylepackSummary.status || (spec.lock_stylepack ? 'locked' : 'proposal'))}">${RoomEditor.Ui.escapeHtml(stylepackSummary.status || (spec.lock_stylepack ? 'locked' : 'proposal'))}</span>
                </div>
                <p class="rw-environment-stage-copy">${RoomEditor.Ui.escapeHtml(`Uploads-first reference pack with ${refUploads.length} item(s), ${pinnedRefs.length} pinned to the stylepack, ${stylepackSummary.material_count || 0} material tags, ${stylepackSummary.shape_count || 0} shape rules, and ${stylepackSummary.forbidden_trait_count || 0} forbidden drift traits.`)}</p>
                ${refUploads.length ? `<div class="rw-environment-chip-row">${refUploads.slice(0, 8).map((item) => `<span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(item.label || item.file_name || 'Reference')}</span>`).join('')}</div>` : '<p class="rw-environment-stage-empty">No uploaded references yet.</p>'}
              </article>
              <article class="rw-environment-stage-card">
                <div class="rw-environment-stage-head">
                  <div>
                    <p class="rw-environment-preview-label">2. Walkable layout</p>
                    <strong>${RoomEditor.Ui.escapeHtml(`${semanticsSummary.counts?.top_count || 0} tops · ${semanticsSummary.counts?.opening_count || 0} openings`)}</strong>
                  </div>
                  <span class="${stagePillClass(semanticsSummary.status || 'idle')}">${RoomEditor.Ui.escapeHtml(semanticsSummary.status || 'idle')}</span>
                </div>
                <p class="rw-environment-stage-copy">${RoomEditor.Ui.escapeHtml(`${plannerCoverageText || 'No planner coverage yet.'}${assemblyOverlayText ? ` · ${assemblyOverlayText}` : ''}`)}</p>
                ${Array.isArray(semanticsSummary.overlay_keys) && semanticsSummary.overlay_keys.length ? `<div class="rw-environment-chip-row">${semanticsSummary.overlay_keys.map((item) => `<span class="rw-environment-chip">${RoomEditor.Ui.escapeHtml(item)}</span>`).join('')}</div>` : '<p class="rw-environment-stage-empty">Overlay geometry has not been derived yet.</p>'}
              </article>
              <article class="rw-environment-stage-card">
                <div class="rw-environment-stage-head">
                  <div>
                    <p class="rw-environment-preview-label">3. Room pieces</p>
                    <strong>${RoomEditor.Ui.escapeHtml(`${kitSummary.summary?.component_count || 0} components`)}</strong>
                  </div>
                  <span class="${stagePillClass(kitSummary.status || 'idle')}">${RoomEditor.Ui.escapeHtml(kitSummary.status || 'idle')}</span>
                </div>
                <p class="rw-environment-stage-copy">${RoomEditor.Ui.escapeHtml(`Structural ${kitSummary.summary?.structural_count || 0} · Background ${kitSummary.summary?.background_count || 0} · Decor ${kitSummary.summary?.decor_count || 0}`)}</p>
                ${componentSchemaChips ? `<div class="rw-environment-chip-row">${componentSchemaChips}</div>` : '<p class="rw-environment-stage-empty">Component schema data has not been built yet.</p>'}
              </article>
              <article class="rw-environment-stage-card">
                <div class="rw-environment-stage-head">
                  <div>
                    <p class="rw-environment-preview-label">4. Scene layout</p>
                    <strong>${RoomEditor.Ui.escapeHtml(`${manifestSummary.generation_metadata?.structural_count || 0} structural placements`)}</strong>
                  </div>
                  <span class="${stagePillClass(manifestSummary.status || bespokeManifest.status || 'idle')}">${RoomEditor.Ui.escapeHtml(manifestSummary.status || bespokeManifest.status || 'idle')}</span>
                </div>
                <p class="rw-environment-stage-copy">${RoomEditor.Ui.escapeHtml(`${assetText} · ${plannerCoverageText || 'No planner summary yet.'}`)}</p>
                ${slotGroupChips || assemblyPlanChips ? `<div class="rw-environment-chip-row">${slotGroupChips}${assemblyPlanChips}</div>` : '<p class="rw-environment-stage-empty">Manifest placements are not ready yet.</p>'}
              </article>
              <article class="rw-environment-stage-card rw-environment-stage-card--wide">
                <div class="rw-environment-stage-head">
                  <div>
                    <p class="rw-environment-preview-label">5. Quality check</p>
                    <strong>${RoomEditor.Ui.escapeHtml(describeRoomWizardApprovalStatus(reviewState.approval_status || 'draft'))}</strong>
                  </div>
                  <span class="${stagePillClass(reviewValidation.status || runtimeReview.status || 'pending')}">${RoomEditor.Ui.escapeHtml(describeRoomWizardValidationStatus(reviewValidation.status || runtimeReview.status || 'pending'))}</span>
                </div>
                <p class="rw-environment-stage-copy">${RoomEditor.Ui.escapeHtml(`${reviewStateText || 'Validation has not run yet.'} · ${reviewText}`)}</p>
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
          const imgAlt = RoomEditor.Ui.escapeHtml(previewLabel);
          const imgSrc = RoomEditor.Ui.escapeHtml(imgHref);
          const dataSrcAttr = RoomEditor.Ui.escapeHtml(imgHref);
          const mediaMarkup = imgHref
            ? `<button type="button" class="rw-preview-card-open" data-rw-asset-src="${dataSrcAttr}" title="View full size (dark background)" aria-label="${RoomEditor.Ui.escapeHtml(openLabel)}"><img src="${imgSrc}" alt="${imgAlt}" loading="lazy" /></button>`
            : `<div class="rw-preview-card-media-missing" role="img" aria-label="${imgAlt}">Preview unavailable</div>`;
          return `
            <article class="rw-preview-card${active}">
              <div class="rw-preview-card-media">
                ${mediaMarkup}
              </div>
              <div class="rw-preview-card-copy">
                <div class="rw-preview-card-title"><strong>${RoomEditor.Ui.escapeHtml(item.label || 'Preview')}</strong></div>
                <span class="rw-preview-card-level">${RoomEditor.Ui.escapeHtml(levelText)}</span>
              </div>
              <button type="button" class="btn-secondary rw-preview-approve" data-preview-id="${RoomEditor.Ui.escapeHtml(item.preview_id || '')}">
                ${active ? 'Approved' : 'Approve Preview'}
              </button>
            </article>`;
        }).join('');
        gallery.querySelectorAll('.rw-preview-approve').forEach((btn) => {
          btn.addEventListener('click', () => RoomEditor.Wizard.approveRoomWizardPreview(btn.dataset.previewId || ''));
        });
        const room = getRoomWizardRoom();
        if (RoomEditor.State.PROJECT_ID && room) {
          RoomEditor.Wizard.postRoomWizardFeedback(room, 'preview_viewed');
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
        RoomEditor.Ui.clearActivity();
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
          session_id: RoomEditor.State.ROOM_AI_SESSION_ID,
          task_id: roomWizardTaskId(room),
          tool_surface: 'room-layout-editor:environment-builder',
          workflow_step: `scope:${RoomEditor.State.workflowScope}|phase:${RoomEditor.State.roomWizard.phase}|tab:${RoomEditor.State.roomWizard.lastEnvTab}|env-step:${RoomEditor.State.roomWizard.envStep || 'describe'}`,
          reason_codes: roomWizardReasonCodes(),
          ...extra,
        };
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
        if (RoomEditor.State.PROJECT_ID && room && prior === 'results' && which !== 'results') {
          RoomEditor.Wizard.postRoomWizardFeedback(room, 'workflow_backtrack');
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
        if (!RoomEditor.State.PROJECT_ID) {
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
        RoomEditor.Ui.setActivity({
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
            RoomEditor.Ui.setActivity({
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
          RoomEditor.Ui.setActivity({
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
        if (!RoomEditor.State.PROJECT_ID) {
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
                <img src="${RoomEditor.Ui.escapeHtml(item.url || '')}" alt="${RoomEditor.Ui.escapeHtml(item.label || item.concept_id || 'Art direction concept')}" />
              </div>
              <div class="rw-direction-concept-copy">
                <strong>${RoomEditor.Ui.escapeHtml(item.label || 'Concept')}</strong>
                <p>${RoomEditor.Ui.escapeHtml(item.prompt || '')}</p>
              </div>
              <button type="button" class="btn-secondary rw-direction-concept-toggle" data-concept-id="${RoomEditor.Ui.escapeHtml(item.concept_id || '')}">
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
        const projectMode = !!RoomEditor.State.PROJECT_ID;
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
            <button type="button" class="rw-frozen-concept${active}" data-concept-id="${RoomEditor.Ui.escapeHtml(item.concept_id || '')}" aria-pressed="${selectedIds.has(item.concept_id) ? 'true' : 'false'}">
              <span class="rw-frozen-concept-media">
                <img src="${RoomEditor.Ui.escapeHtml(item.url || '')}" alt="${RoomEditor.Ui.escapeHtml(item.label || item.concept_id || 'Concept anchor')}" />
              </span>
              <span class="rw-frozen-concept-copy">
                <strong>${RoomEditor.Ui.escapeHtml(item.label || item.concept_id || 'Concept')}</strong>
                <span>${RoomEditor.Ui.escapeHtml(status)}</span>
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
        const projectMode = !!RoomEditor.State.PROJECT_ID;
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
        const projectMode = !!RoomEditor.State.PROJECT_ID;
        grid.parentElement.style.display = projectMode ? '' : 'none';
        if (!projectMode) return;
        const active = RoomEditor.State.roomWizard.selectedArchetypeId || '';
        grid.innerHTML = RoomEditor.State.roomEnvironmentArchetypes.map((item) => `
          <button type="button" class="btn-secondary rw-template-chip${active === item.archetype_id ? ' active' : ''}" data-archetype-id="${RoomEditor.Ui.escapeHtml(item.archetype_id)}" title="${RoomEditor.Ui.escapeHtml(item.starter_brief || '')}">
            ${RoomEditor.Ui.escapeHtml(item.label)}
          </button>
        `).join('');
        grid.querySelectorAll('[data-archetype-id]').forEach((btn) => {
          btn.addEventListener('click', async () => {
            RoomEditor.State.roomWizard.selectedArchetypeId = btn.dataset.archetypeId || '';
            renderRoomWizardArchetypeGrid();
            await RoomEditor.Wizard.adaptSelectedRoomArchetype('Adapt this room template to the locked project style.');
          });
        });
      }

function syncRoomWizardLookPreviewExplainer() {
        const el = document.getElementById('roomWizardLookPreviewExplainer');
        if (!el) return;
        if (RoomEditor.State.PROJECT_ID) {
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
          genBtn.textContent = RoomEditor.State.PROJECT_ID ? 'Generate preview pictures' : 'Suggest look (diagram)';
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
                ? ` Last Gemini image error: ${RoomEditor.Ui.escapeHtml(String(snap.message).slice(0, 220))}${snap.recorded_at ? ` (${RoomEditor.Ui.escapeHtml(snap.recorded_at)})` : ''}`
                : '';
            const billingHint =
              snap && snap.message && /spending cap|billing|429|RESOURCE_EXHAUSTED|quota/i.test(String(snap.message))
                ? ' <strong>Billing:</strong> In Google Cloud (project linked to this API key), open <strong>Billing</strong> and raise or remove the <strong>spending cap</strong>, or fix payment. Image calls use the same project quota as text.'
                : '';
            meta.innerHTML = `Image model: <code>${RoomEditor.Ui.escapeHtml(im)}</code>.${errLine}${billingHint}`;
          }
        }
        if (probeRow) {
          probeRow.hidden = !(serverReachable && geminiConfigured);
        }
        if (RoomEditor.State.PROJECT_ID) {
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

        if (RoomEditor.State.PROJECT_ID) {
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
        RoomEditor.Model.ensureRoomShape(room);
        const myCount = RoomEditor.Model.getEdgeCount(room);
        const prevMy = myEl.value;
        myEl.innerHTML = '';
        for (let i = 0; i < myCount; i += 1) {
          const opt = document.createElement('option');
          opt.value = String(i);
          opt.textContent = RoomEditor.Model.edgeLabel(room, i);
          myEl.appendChild(opt);
        }
        if (prevMy && Number(prevMy) < myCount) {
          myEl.value = prevMy;
        } else if (myCount) {
          myEl.value = '0';
        }

        const neighborId = neighborSel?.value;
        const neighbor = neighborId ? RoomEditor.Model.getRoomById(neighborId) : null;
        const prevNb = nbEl.value;
        nbEl.innerHTML = '';
        if (neighbor) {
          RoomEditor.Model.ensureRoomShape(neighbor);
          const nbCount = RoomEditor.Model.getEdgeCount(neighbor);
          for (let i = 0; i < nbCount; i += 1) {
            const opt = document.createElement('option');
            opt.value = String(i);
            opt.textContent = RoomEditor.Model.edgeLabel(neighbor, i);
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
          const neighbor = RoomEditor.Model.getRoomById(pick);
          const link = (room.edgeLinks || []).find((l) => l.targetRoomId === pick);
          const myEl = document.getElementById('roomWizardMyEdge');
          const nbEl = document.getElementById('roomWizardNeighborEdge');
          if (link && neighbor && myEl && nbEl) {
            if (link.edgeIndex >= 0 && link.edgeIndex < RoomEditor.Model.getEdgeCount(room)) {
              myEl.value = String(link.edgeIndex);
            }
            if (link.targetEdgeIndex >= 0 && link.targetEdgeIndex < RoomEditor.Model.getEdgeCount(neighbor)) {
              nbEl.value = String(link.targetEdgeIndex);
            }
          }
        }
      }

function applyRoomWizardAlign() {
        const mod = globalThis.RoomWizardNeighborAlign;
        if (!mod || typeof mod.computeAlignedGlobal !== 'function') {
          RoomEditor.Ui.setStatus('Neighbor align module not loaded.', 'error');
          return;
        }
        const room = getRoomWizardRoom();
        if (!room) return;
        const neighborId = document.getElementById('roomWizardNeighbor')?.value;
        if (!neighborId) {
          RoomEditor.Ui.setStatus('Pick an adjoining room first.', 'warning');
          return;
        }
        const neighbor = RoomEditor.Model.getRoomById(neighborId);
        if (!neighbor) return;
        RoomEditor.Model.ensureRoomShape(room);
        RoomEditor.Model.ensureRoomShape(neighbor);
        const myEdge = Number(document.getElementById('roomWizardMyEdge')?.value);
        const nEdge = Number(document.getElementById('roomWizardNeighborEdge')?.value);
        const result = mod.computeAlignedGlobal(room, neighbor, myEdge, nEdge, mod.ROOM_WIZARD_NEIGHBOR_SCALE);
        if (!result.ok) {
          RoomEditor.Ui.setStatus(`Align: ${result.reason}`, 'error');
          return;
        }
        room.global = { x: result.global.x, y: result.global.y };
        RoomEditor.Topology.setRoomEdgeLink(room.id, myEdge, neighborId, nEdge);
        RoomEditor.State.roomWizard.touched = true;
        RoomEditor.State.setDirty(true);
        RoomEditor.Storage.updateJsonText();
        if (RoomEditor.State.data) {
          RoomEditor.State.lastValidationReport = RoomEditor.Validation.validateLayout(RoomEditor.State.data);
          RoomEditor.Validation.renderValidationResults(RoomEditor.State.lastValidationReport);
        }
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus('Aligned to neighbor; edge link saved.', 'success');
      }

function applyRoomWizardHatch() {
        const mod = globalThis.RoomWizardNeighborAlign;
        if (!mod || typeof mod.computeHatchHeightDelta !== 'function') {
          RoomEditor.Ui.setStatus('Neighbor align module not loaded.', 'error');
          return;
        }
        const room = getRoomWizardRoom();
        if (!room) return;
        const neighborId = document.getElementById('roomWizardNeighbor')?.value;
        if (!neighborId) {
          RoomEditor.Ui.setStatus('Pick an adjoining room first.', 'warning');
          return;
        }
        const neighbor = RoomEditor.Model.getRoomById(neighborId);
        if (!neighbor) return;
        RoomEditor.Model.ensureRoomShape(room);
        RoomEditor.Model.ensureRoomShape(neighbor);
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
          RoomEditor.Ui.setStatus(msg, 'warning');
          return;
        }
        const gx = Number.isFinite(Number(room.global?.x)) ? Number(room.global.x) : 0;
        const gy = Number.isFinite(Number(room.global?.y)) ? Number(room.global.y) : 0;
        room.global = { x: gx + d.deltaX, y: gy + d.deltaY };
        RoomEditor.State.roomWizard.touched = true;
        RoomEditor.State.setDirty(true);
        RoomEditor.Storage.updateJsonText();
        if (RoomEditor.State.data) {
          RoomEditor.State.lastValidationReport = RoomEditor.Validation.validateLayout(RoomEditor.State.data);
          RoomEditor.Validation.renderValidationResults(RoomEditor.State.lastValidationReport);
        }
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus('Adjusted position along the opening (doors or edge midpoints).', 'success');
      }

function applyRoomWizardMatchWallLength() {
        const mod = globalThis.RoomWizardNeighborAlign;
        if (!mod || typeof mod.computeMatchWallLengthPatch !== 'function') {
          RoomEditor.Ui.setStatus('Neighbor align module not loaded.', 'error');
          return;
        }
        const room = getRoomWizardRoom();
        if (!room) return;
        const neighborId = document.getElementById('roomWizardNeighbor')?.value;
        if (!neighborId) {
          RoomEditor.Ui.setStatus('Pick an adjoining room first.', 'warning');
          return;
        }
        const neighbor = RoomEditor.Model.getRoomById(neighborId);
        if (!neighbor) return;
        RoomEditor.Model.ensureRoomShape(room);
        RoomEditor.Model.ensureRoomShape(neighbor);
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
          RoomEditor.Ui.setStatus(map[result.reason] || `Match wall length: ${result.reason}`, 'warning');
          return;
        }
        room.size = { width: result.size.width, height: result.size.height };
        room.polygon = result.polygon.map((pt) => [pt[0], pt[1]]);
        RoomEditor.State.roomWizard.touched = true;
        RoomEditor.State.setDirty(true);
        RoomEditor.Storage.updateJsonText();
        if (RoomEditor.State.data) {
          RoomEditor.State.lastValidationReport = RoomEditor.Validation.validateLayout(RoomEditor.State.data);
          RoomEditor.Validation.renderValidationResults(RoomEditor.State.lastValidationReport);
        }
        RoomEditor.Render.redraw();
        RoomEditor.Ui.setStatus('Resized this room so the selected wall length matches the neighbor (recheck doors/platforms).', 'success');
      }

function setRoomWizardPhase(phase) {
        const allowed = ['identity', 'layout', 'environment', 'entities', 'review'];
        if (!allowed.includes(phase)) return;
        RoomEditor.State.roomWizard.phase = phase;
        const dock = document.getElementById('roomWizardDock');
        if (dock) dock.dataset.phase = phase;
        const panL = document.getElementById('roomWizardPanelLayout');
        const panE = document.getElementById('roomWizardPanelEnvironment');
        const panEnt = document.getElementById('roomWizardPanelEntities');
        const panA = document.getElementById('roomWizardPanelArtDirection');
        const panR = document.getElementById('roomWizardPanelReview');
        const artScope = RoomEditor.State.workflowScope === 'art-direction';
        const layoutPanelPhases = ['identity', 'layout'];
        if (panL) panL.hidden = artScope || !layoutPanelPhases.includes(phase);
        if (panE) panE.hidden = artScope || phase !== 'environment';
        if (panEnt) panEnt.hidden = artScope || phase !== 'entities';
        if (panA) panA.hidden = !artScope;
        if (panR) panR.hidden = artScope || phase !== 'review';
        RoomEditor.WizardOptionB?.syncLayoutSubpanels?.();
        RoomEditor.Workflow.updateWorkflowRailPills();
        if (phase === 'review') {
          updateRoomWizardReviewPanel();
        }
        if (phase === 'layout' || phase === 'identity') {
          updateRoomWizardTerrainControls();
          refreshTerrainWarnings();
        }
        if (phase === 'environment') {
          syncRoomWizardEnvironmentFromRoom();
          RoomEditor.Wizard.loadRoomEnvironmentProjectData();
          RoomEditor.Storage.refreshCopilotStatus();
          setRoomWizardEnvStep(RoomEditor.State.roomWizard.envStep || 'describe');
        }
        RoomEditor.Workflow.syncRoomWizardScopePanels();
        RoomEditor.WizardOptionB?.syncShell?.();
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
                .map((l) => `${RoomEditor.Ui.escapeHtml(room.id)}[${l.edgeIndex}] ↔ ${RoomEditor.Ui.escapeHtml(l.targetRoomId)}[${l.targetEdgeIndex}]`)
                .join('<br/>')}</dd>`
            : '<dt>Edge links</dt><dd>None yet</dd>';
        const envMod = globalThis.RoomWizardEnvironment;
        let envBlock = '';
        if (envMod) {
          envMod.ensureRoomEnvironment(room);
          const e = room.environment;
          const tagStr = e.tags && e.tags.length ? e.tags.join(', ') : '—';
          envBlock = `<dt>Environment</dt><dd>${RoomEditor.Ui.escapeHtml(e.themeId)} · tags: ${RoomEditor.Ui.escapeHtml(tagStr)}</dd>`;
        }
        summary.innerHTML = `
          <dl>
            <dt>Room</dt><dd>${RoomEditor.Ui.escapeHtml(room.name)} (${RoomEditor.Ui.escapeHtml(room.id)})</dd>
            <dt>Footprint</dt><dd>${RoomEditor.Ui.escapeHtml(String(W))} × ${RoomEditor.Ui.escapeHtml(String(H))} px</dd>
            ${envBlock}
            ${neighborLine}
          </dl>`;
        if (!RoomEditor.State.data) return;
        const report = RoomEditor.Validation.validateLayout(RoomEditor.State.data);
        RoomEditor.State.lastValidationReport = report;
        RoomEditor.Validation.renderValidationResults(report);
        if (inline) {
          const checks = [...report.level_1.checks, ...report.level_2.checks];
          if (checks.length === 0) {
            inline.innerHTML = '<div class="vw-item">No structural or traversal issues reported.</div>';
          } else {
            inline.innerHTML = checks
              .map((c) => {
                const cl = c.severity === 'error' ? 'err' : 'warn';
                return `<div class="vw-item ${cl}">${RoomEditor.Ui.escapeHtml(c.id)}: ${RoomEditor.Ui.escapeHtml(c.message)}</div>`;
              })
              .join('');
          }
        }
      }

function openRoomWizard(roomId) {
        if (!RoomEditor.State.data || !roomId) return;
        RoomEditor.State.workflowScope = 'room';
        RoomEditor.State.syncLegacyEditorWorkflowStep();
        RoomEditor.State.setViewMode('room');
        RoomEditor.State.roomWizard.active = true;
        RoomEditor.State.roomWizard.roomId = roomId;
        RoomEditor.State.roomWizard.phase = 'identity';
        RoomEditor.State.roomWizard.touched = false;
        RoomEditor.State.roomWizard.envStep = 'describe';
        clearRoomWizardCopilotPreview();
        RoomEditor.State.currentRoomId = roomId;
        RoomEditor.Ui.populateRoomSelect();
        RoomEditor.Ui.refs.roomSelect.value = roomId;
        syncRoomWizardFormFromRoom();
        setRoomWizardPhase('identity');
        RoomEditor.Workflow.syncRoomWizardDock();
        RoomEditor.Workflow.syncWorkflowRailVisibility();
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
            RoomEditor.State.setViewMode('global');
            RoomEditor.State.syncLegacyEditorWorkflowStep();
            RoomEditor.Workflow.updateWorkflowScopeToggle();
            RoomEditor.Workflow.updateWorldWorkflowPills();
            RoomEditor.Workflow.syncWorldPlaceholderPanel();
            RoomEditor.Workflow.syncWorldWorkflowRailVisibility();
            RoomEditor.Workflow.updateWorkflowRailPills();
            RoomEditor.Workflow.syncEditorWorkflowSecondaryRail();
            RoomEditor.Workflow.syncRoomWizardDock();
            RoomEditor.Render.redraw();
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
        RoomEditor.State.roomWizard.phase = 'identity';
        RoomEditor.State.roomWizard.touched = false;
        syncRoomWizardFormFromRoom();
        RoomEditor.Workflow.syncRoomWizardDock();
        RoomEditor.WizardOptionB?.syncShell?.();
        RoomEditor.Workflow.updateWorkflowRailPills();
        RoomEditor.Workflow.updateWorldWorkflowPills();
        RoomEditor.Workflow.updateWorkflowScopeToggle();
        RoomEditor.Workflow.syncWorldWorkflowRailVisibility();
        RoomEditor.Workflow.syncEditorWorkflowSecondaryRail();
        RoomEditor.Render.redraw();
      }

function requestCloseRoomWizard() {
        closeRoomWizard(false);
      }

function installRoomWizardQaHooks() {
        window.__ROOM_WIZARD_QA__ = {
          applyResultsEnvironment(environmentPayload) {
            const room = getRoomWizardRoom() || RoomEditor.Model.currentRoom();
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

  Module.refreshTerrainWarnings = refreshTerrainWarnings;
  Module.updateRoomWizardTerrainControls = updateRoomWizardTerrainControls;
  Module.applyTerrainPresetFromWizard = applyTerrainPresetFromWizard;
  Module.roomWizardTerrainDuplicate = roomWizardTerrainDuplicate;
  Module.roomWizardTerrainMirror = roomWizardTerrainMirror;
  Module.centerRoom = centerRoom;
  Module.getRoomWizardRoom = getRoomWizardRoom;
  Module.applyFootprintDimensionsToRoom = applyFootprintDimensionsToRoom;
  Module.syncRoomWizardFootprintRadios = syncRoomWizardFootprintRadios;
  Module.populateRoomWizardThemeSelect = populateRoomWizardThemeSelect;
  Module.ensureRoomWizardEnvironmentAuthoringFields = ensureRoomWizardEnvironmentAuthoringFields;
  Module.cloneRoomWizardEnvironmentAuthoringFields = cloneRoomWizardEnvironmentAuthoringFields;
  Module.applyRoomWizardEnvironmentAuthoringFields = applyRoomWizardEnvironmentAuthoringFields;
  Module.formatRoomWizardFileSize = formatRoomWizardFileSize;
  Module.roomWizardResultsToggleMap = roomWizardResultsToggleMap;
  Module.syncRoomWizardResultsToggles = syncRoomWizardResultsToggles;
  Module.bindRoomWizardResultsToggleInputs = bindRoomWizardResultsToggleInputs;
  Module.renderRoomWizardResultsToggleControls = renderRoomWizardResultsToggleControls;
  Module.renderRoomWizardReferenceList = renderRoomWizardReferenceList;
  Module.updateRoomWizardResultsEmptyState = updateRoomWizardResultsEmptyState;
  Module.syncRoomWizardEnvironmentAuthoringFromInputs = syncRoomWizardEnvironmentAuthoringFromInputs;
  Module.syncRoomWizardEnvironmentFromRoom = syncRoomWizardEnvironmentFromRoom;
  Module.replaceRoomWizardEnvironmentPreservingAuthoring = replaceRoomWizardEnvironmentPreservingAuthoring;
  Module.roomWizardComponentFieldMap = roomWizardComponentFieldMap;
  Module.syncRoomWizardComponentFields = syncRoomWizardComponentFields;
  Module.collectRoomWizardComponentPrompts = collectRoomWizardComponentPrompts;
  Module.clearRoomWizardCopilotPreview = clearRoomWizardCopilotPreview;
  Module.buildRoomWizardEnvironmentPreviewModel = buildRoomWizardEnvironmentPreviewModel;
  Module.assetUrlWithVersion = assetUrlWithVersion;
  Module.openRoomEnvironmentAssetPreviewWindow = openRoomEnvironmentAssetPreviewWindow;
  Module.humanizeRoomWizardLabel = humanizeRoomWizardLabel;
  Module.describeRoomWizardApprovalStatus = describeRoomWizardApprovalStatus;
  Module.describeRoomWizardValidationStatus = describeRoomWizardValidationStatus;
  Module.describeRoomWizardRuntimeReviewStatus = describeRoomWizardRuntimeReviewStatus;
  Module.roomWizardOverlayBounds = roomWizardOverlayBounds;
  Module.roomWizardRectFromPlacement = roomWizardRectFromPlacement;
  Module.roomWizardRectSvg = roomWizardRectSvg;
  Module.roomWizardLineSvg = roomWizardLineSvg;
  Module.roomWizardPointSvg = roomWizardPointSvg;
  Module.roomWizardDecorMarkerRect = roomWizardDecorMarkerRect;
  Module.renderRoomWizardResultsOverlay = renderRoomWizardResultsOverlay;
  Module.renderEnvironmentPreviewMarkup = renderEnvironmentPreviewMarkup;
  Module.renderGeneratedEnvironmentPreviewMarkup = renderGeneratedEnvironmentPreviewMarkup;
  Module.renderRoomWizardEnvironmentPreview = renderRoomWizardEnvironmentPreview;
  Module.roomWizardHasGeneratedPreview = roomWizardHasGeneratedPreview;
  Module.renderRoomWizardEnvironmentOutputSummary = renderRoomWizardEnvironmentOutputSummary;
  Module.renderRoomWizardPreviewGalleryInto = renderRoomWizardPreviewGalleryInto;
  Module.renderRoomWizardPreviewGallery = renderRoomWizardPreviewGallery;
  Module.stopRoomWizardWaitbar = stopRoomWizardWaitbar;
  Module.roomWizardTaskId = roomWizardTaskId;
  Module.roomWizardReasonCodes = roomWizardReasonCodes;
  Module.roomWizardCommaList = roomWizardCommaList;
  Module.roomWizardSuggestionId = roomWizardSuggestionId;
  Module.roomWizardAnalyticsContext = roomWizardAnalyticsContext;
  Module.setRoomWizardEnvTab = setRoomWizardEnvTab;
  Module.normalizeRoomWizardEnvStep = normalizeRoomWizardEnvStep;
  Module.setRoomWizardEnvStep = setRoomWizardEnvStep;
  Module.initRoomWizardEnvTabs = initRoomWizardEnvTabs;
  Module.updateRoomWizardBiomePackSummary = updateRoomWizardBiomePackSummary;
  Module.roomWizardBespokeComponentUsesGemini = roomWizardBespokeComponentUsesGemini;
  Module.roomWizardEstimateBespokeGeminiSlotCount = roomWizardEstimateBespokeGeminiSlotCount;
  Module.roomWizardEstimateBespokeAssetWaitMs = roomWizardEstimateBespokeAssetWaitMs;
  Module.startRoomWizardWaitbar = startRoomWizardWaitbar;
  Module.renderRoomWizardDirectionConceptBoard = renderRoomWizardDirectionConceptBoard;
  Module.renderRoomWizardFrozenConceptGrid = renderRoomWizardFrozenConceptGrid;
  Module.renderRoomWizardArtDirectionUi = renderRoomWizardArtDirectionUi;
  Module.renderRoomWizardArchetypeGrid = renderRoomWizardArchetypeGrid;
  Module.syncRoomWizardLookPreviewExplainer = syncRoomWizardLookPreviewExplainer;
  Module.updateRoomWizardCopilotHintUi = updateRoomWizardCopilotHintUi;
  Module.renderRoomWizardCopilotPreview = renderRoomWizardCopilotPreview;
  Module.syncRoomWizardFormFromRoom = syncRoomWizardFormFromRoom;
  Module.syncRoomWizardEdgeSelects = syncRoomWizardEdgeSelects;
  Module.syncRoomWizardNeighborFromRoom = syncRoomWizardNeighborFromRoom;
  Module.applyRoomWizardAlign = applyRoomWizardAlign;
  Module.applyRoomWizardHatch = applyRoomWizardHatch;
  Module.applyRoomWizardMatchWallLength = applyRoomWizardMatchWallLength;
  Module.setRoomWizardPhase = setRoomWizardPhase;
  Module.updateRoomWizardReviewPanel = updateRoomWizardReviewPanel;
  Module.openRoomWizard = openRoomWizard;
  Module.closeRoomWizard = closeRoomWizard;
  Module.requestCloseRoomWizard = requestCloseRoomWizard;
  Module.installRoomWizardQaHooks = installRoomWizardQaHooks;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Wizard = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
