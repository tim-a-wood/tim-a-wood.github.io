'use strict';
(function (root) {
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Wizard = root.RoomEditor.Wizard || {};
async function postRoomWizardFeedback(room, eventType, extra = {}, options = {}) {
        if (!RoomEditor.State.PROJECT_ID || !room?.id) return null;
        const payload = {
          event_type: eventType,
          suggestion_id: RoomEditor.Wizard.roomWizardSuggestionId(room),
          ...RoomEditor.Wizard.roomWizardAnalyticsContext(room, extra),
        };
        const url = RoomEditor.State.projectRoomEnvironmentFeedbackApiUrl(room.id);
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

async function loadRoomEnvironmentProjectData() {
        if (!RoomEditor.State.PROJECT_ID) return;
        try {
          const [templateRes, archetypeRes] = await Promise.all([
            fetch(RoomEditor.State.PROJECT_ART_DIRECTION_TEMPLATES_URL, { cache: 'no-store' }),
            fetch(RoomEditor.Constants.ROOM_ENV_ARCHETYPES_URL, { cache: 'no-store' })
          ]);
          const templateJson = await templateRes.json().catch(() => ({}));
          const archetypeJson = await archetypeRes.json().catch(() => ({}));
          RoomEditor.State.artDirectionTemplates = Array.isArray(templateJson.templates) ? templateJson.templates : [];
          RoomEditor.State.artDirection = templateJson.art_direction || null;
          RoomEditor.State.artDirectionConceptOptions = Array.isArray(templateJson.available_concepts) ? templateJson.available_concepts : [];
          RoomEditor.State.roomEnvironmentArchetypes = Array.isArray(archetypeJson.archetypes) ? archetypeJson.archetypes : [];
          RoomEditor.Wizard.renderRoomWizardArtDirectionUi();
          RoomEditor.Wizard.renderRoomWizardArchetypeGrid();
          RoomEditor.Wizard.updateRoomWizardCopilotHintUi();
        } catch (_) {
          const hint = document.getElementById('roomWizardArtDirectionHint');
          if (hint) hint.textContent = 'Could not load project art-direction templates.';
          RoomEditor.Ui.showToast('Could not load project art-direction templates.', 'warning');
        }
      }

async function saveProjectArtDirectionFromWizard() {
        if (!RoomEditor.State.PROJECT_ID || !RoomEditor.State.PROJECT_ART_DIRECTION_URL) return;
        const sel = document.getElementById('roomWizardArtDirectionTemplate');
        const summary = document.getElementById('roomWizardArtDirectionSummary');
        const negative = document.getElementById('roomWizardArtDirectionNegative');
        const status = document.getElementById('roomWizardArtDirectionStatus');
        if (!sel || !summary || !negative) return;
        if (status) status.textContent = 'Saving direction…';
        RoomEditor.Wizard.startRoomWizardWaitbar('art-direction', 'Saving project art direction.');
        try {
          const res = await fetch(RoomEditor.State.PROJECT_ART_DIRECTION_URL, {
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
          RoomEditor.Wizard.renderRoomWizardArtDirectionUi();
          RoomEditor.Wizard.updateRoomWizardCopilotHintUi();
          if (status) status.textContent = 'Project direction locked.';
          RoomEditor.Ui.showToast('Project direction locked.', 'success');
          RoomEditor.Wizard.stopRoomWizardWaitbar('art-direction', 100);
        } catch (e) {
          RoomEditor.Wizard.stopRoomWizardWaitbar('art-direction', 100);
          const message = (e && e.message) || 'Save failed';
          if (status) status.textContent = message;
          RoomEditor.Ui.setStatus(message, 'error');
        }
      }

async function generateArtDirectionConceptBoard() {
        if (!RoomEditor.State.PROJECT_ID || !RoomEditor.State.PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL) return;
        const sel = document.getElementById('roomWizardArtDirectionTemplate');
        const summary = document.getElementById('roomWizardArtDirectionSummary');
        const negative = document.getElementById('roomWizardArtDirectionNegative');
        const status = document.getElementById('roomWizardGenerateArtDirectionConceptsStatus');
        const btn = document.getElementById('roomWizardGenerateArtDirectionConcepts');
        if (!sel || !summary || !negative || !status || !btn) return;
        status.textContent = 'Generating art direction concepts…';
        btn.disabled = true;
        RoomEditor.Wizard.startRoomWizardWaitbar('art-direction', 'Generating art direction concept board.');
        try {
          const res = await fetch(RoomEditor.State.PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL, {
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
          RoomEditor.Wizard.renderRoomWizardArtDirectionUi();
          RoomEditor.Wizard.updateRoomWizardCopilotHintUi();
          RoomEditor.Ui.showToast('Art direction concepts are ready to review.', 'success');
          RoomEditor.Wizard.stopRoomWizardWaitbar('art-direction', 100);
        } catch (e) {
          RoomEditor.Wizard.stopRoomWizardWaitbar('art-direction', 100);
          const message = (e && e.message) || 'Generation failed';
          status.textContent = message;
          RoomEditor.Ui.setStatus(message, 'error');
        } finally {
          btn.disabled = false;
        }
      }

async function adaptSelectedRoomArchetype(instruction) {
        const room = RoomEditor.Wizard.getRoomWizardRoom();
        const promptEl = document.getElementById('roomWizardCopilotPrompt');
        const st = document.getElementById('roomWizardCopilotStatus');
        if (!RoomEditor.State.PROJECT_ID || !room || !promptEl) return;
        if (!RoomEditor.State.roomWizard.selectedArchetypeId && !String(promptEl.value || '').trim()) {
          if (st) st.textContent = 'Choose a room template or enter a draft first.';
          RoomEditor.Ui.setStatus('Choose a room template or enter a draft first.', 'warning');
          return;
        }
        if (st) st.textContent = 'Adapting draft…';
        RoomEditor.Wizard.startRoomWizardWaitbar('copilot', 'Adapting the room draft to the current art direction.');
        try {
          const res = await fetch(RoomEditor.State.projectRoomEnvironmentApiUrl(room.id, 'adapt-template'), {
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
          RoomEditor.Ui.showToast('Draft updated for the current project direction.', 'success');
          RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
        } catch (e) {
          RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
          const message = (e && e.message) || 'Adaptation failed';
          if (st) st.textContent = message;
          RoomEditor.Ui.setStatus(message, 'error');
        }
      }

async function approveRoomWizardPreview(previewId) {
        const room = RoomEditor.Wizard.getRoomWizardRoom();
        const st = document.getElementById('roomWizardCopilotStatus');
        if (!RoomEditor.State.PROJECT_ID || !room || !previewId) return;
        RoomEditor.Wizard.startRoomWizardWaitbar('copilot', 'Approving the selected preview.');
        try {
          const res = await fetch(RoomEditor.State.projectRoomEnvironmentApiUrl(room.id, 'approve-preview'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              preview_id: previewId,
              ...RoomEditor.Wizard.roomWizardAnalyticsContext(room),
            })
          });
          const json = await res.json().catch(() => ({}));
          if (!res.ok || !json.ok) throw new Error(json.error || 'Approve failed');
          const envMod = globalThis.RoomWizardEnvironment;
          RoomEditor.Wizard.replaceRoomWizardEnvironmentPreservingAuthoring(room, json.environment || room.environment);
          RoomEditor.Wizard.renderRoomWizardEnvironmentPreview(room.environment);
          RoomEditor.Wizard.renderRoomWizardPreviewGallery(room.environment.preview || {});
          RoomEditor.Wizard.renderRoomWizardEnvironmentOutputSummary(room.environment);
          RoomEditor.Wizard.renderRoomWizardCopilotPreview({
            themeId: room.environment?.themeId || 'custom',
            tags: room.environment?.tags || [],
            rationale: room.environment?.spec?.description || ''
          });
          RoomEditor.State.roomWizard.approvedPreviewId = previewId;
          if (st) st.textContent = 'Preview approved. Open Game now uses this preview’s palette on room surfaces.';
          RoomEditor.Ui.showToast('Preview approved. Open Game will use it now.', 'success');
          RoomEditor.Storage.updateJsonText();
          RoomEditor.State.setDirty(true);
          RoomEditor.GamePreview.refreshOpenGamePreviewIfVisible(room.id);
          RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
        } catch (e) {
          RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
          const message = (e && e.message) || 'Approve failed';
          if (st) st.textContent = message;
          RoomEditor.Ui.setStatus(message, 'error');
        }
      }

  root.RoomEditor.Wizard.postRoomWizardFeedback = postRoomWizardFeedback;
  root.RoomEditor.Wizard.loadRoomEnvironmentProjectData = loadRoomEnvironmentProjectData;
  root.RoomEditor.Wizard.saveProjectArtDirectionFromWizard = saveProjectArtDirectionFromWizard;
  root.RoomEditor.Wizard.generateArtDirectionConceptBoard = generateArtDirectionConceptBoard;
  root.RoomEditor.Wizard.adaptSelectedRoomArchetype = adaptSelectedRoomArchetype;
  root.RoomEditor.Wizard.approveRoomWizardPreview = approveRoomWizardPreview;
})(typeof globalThis !== 'undefined' ? globalThis : this);
