'use strict';
(function (root) {
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Wizard = root.RoomEditor.Wizard || {};
function wireRoomWizardEvents() {
        RoomEditor.Wizard.initRoomWizardEnvTabs();
        document.getElementById('roomWizardClose')?.addEventListener('click', requestCloseRoomWizard);
        document.getElementById('workflowScopeWorld')?.addEventListener('click', () => RoomEditor.Workflow.setWorkflowScope('world'));
        document.getElementById('workflowScopeRoom')?.addEventListener('click', () => RoomEditor.Workflow.setWorkflowScope('room'));
        document.getElementById('workflowScopeArtDirection')?.addEventListener('click', () => RoomEditor.Workflow.setWorkflowScope('art-direction'));
        document.querySelectorAll('#worldWorkflowRail [data-world-workflow-step]').forEach((btn) => {
          btn.addEventListener('click', () => RoomEditor.Workflow.setWorldWorkflowStep(Number(btn.dataset.worldWorkflowStep)));
        });
        document.getElementById('roomWizardTabIdentity')?.addEventListener('click', () => {
          if (RoomEditor.State.viewMode === 'global') RoomEditor.State.setViewMode('room');
          if (!RoomEditor.State.currentRoomId || !RoomEditor.State.data) return;
          if (RoomEditor.State.workflowScope !== 'room') {
            RoomEditor.Workflow.setWorkflowScope('room');
          } else if (!RoomEditor.State.roomWizard.active) {
            RoomEditor.Wizard.openRoomWizard(RoomEditor.State.currentRoomId);
          }
          RoomEditor.Wizard.setRoomWizardPhase('identity');
          RoomEditor.Workflow.updateWorldWorkflowPills();
          RoomEditor.Workflow.syncEditorWorkflowSecondaryRail();
          RoomEditor.Render.redraw();
        });
        document.getElementById('roomWizardTabLayout')?.addEventListener('click', () => {
          if (RoomEditor.State.viewMode === 'global') RoomEditor.State.setViewMode('room');
          if (!RoomEditor.State.currentRoomId || !RoomEditor.State.data) return;
          if (RoomEditor.State.workflowScope !== 'room') {
            RoomEditor.Workflow.setWorkflowScope('room');
          } else if (!RoomEditor.State.roomWizard.active) {
            RoomEditor.Wizard.openRoomWizard(RoomEditor.State.currentRoomId);
          }
          RoomEditor.Wizard.setRoomWizardPhase('layout');
          RoomEditor.Workflow.updateWorldWorkflowPills();
          RoomEditor.Workflow.syncEditorWorkflowSecondaryRail();
          RoomEditor.Render.redraw();
        });
        document.getElementById('roomWizardTabReview')?.addEventListener('click', () => {
          if (RoomEditor.State.viewMode === 'global') RoomEditor.State.setViewMode('room');
          if (!RoomEditor.State.currentRoomId || !RoomEditor.State.data) return;
          if (RoomEditor.State.workflowScope !== 'room') {
            RoomEditor.Workflow.setWorkflowScope('room');
          } else if (!RoomEditor.State.roomWizard.active) {
            RoomEditor.Wizard.openRoomWizard(RoomEditor.State.currentRoomId);
          }
          RoomEditor.Wizard.setRoomWizardPhase('review');
          RoomEditor.Workflow.updateWorldWorkflowPills();
          RoomEditor.Workflow.syncEditorWorkflowSecondaryRail();
          RoomEditor.Render.redraw();
        });
        document.getElementById('roomWizardTabEnvironment')?.addEventListener('click', () => {
          if (RoomEditor.State.viewMode === 'global') RoomEditor.State.setViewMode('room');
          if (!RoomEditor.State.currentRoomId || !RoomEditor.State.data) return;
          const mod = globalThis.RoomWizardTerrain;
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          if (!mod || !room || !mod.isLayoutCompleteForTerrain(room)) {
            RoomEditor.Ui.setStatus('Complete layout (name, id, footprint) before Environment.', 'warning');
            return;
          }
          if (RoomEditor.State.workflowScope !== 'room') {
            RoomEditor.Workflow.setWorkflowScope('room');
          } else if (!RoomEditor.State.roomWizard.active) {
            RoomEditor.Wizard.openRoomWizard(RoomEditor.State.currentRoomId);
          }
          RoomEditor.Wizard.setRoomWizardPhase('environment');
          RoomEditor.Workflow.updateWorldWorkflowPills();
          RoomEditor.Workflow.syncEditorWorkflowSecondaryRail();
          RoomEditor.Render.redraw();
        });
        document.getElementById('roomWizardPhasePrev')?.addEventListener('click', () => {
          RoomEditor.WizardOptionB?.navigatePhase?.(-1);
        });
        document.getElementById('roomWizardPhaseNext')?.addEventListener('click', () => {
          RoomEditor.WizardOptionB?.navigatePhase?.(1);
        });
        document.getElementById('roomWizardBackToLayoutFromEnv')?.addEventListener('click', () => RoomEditor.Wizard.setRoomWizardPhase('layout'));
        document.getElementById('roomWizardBackToEnvironment')?.addEventListener('click', () => RoomEditor.Wizard.setRoomWizardPhase('environment'));
        document.getElementById('roomWizardBackToLayout')?.addEventListener('click', () => RoomEditor.Wizard.setRoomWizardPhase('layout'));
        Object.entries(RoomEditor.Wizard.roomWizardComponentFieldMap()).forEach(([key, el]) => {
          el?.addEventListener('input', () => {
            const room = RoomEditor.Wizard.getRoomWizardRoom();
            const envMod = globalThis.RoomWizardEnvironment;
            if (!room || !envMod) return;
            envMod.ensureRoomEnvironment(room);
            if (typeof envMod.ensureEnvironmentComponents === 'function') {
              envMod.ensureEnvironmentComponents(room.environment.spec);
            }
            room.environment.spec.components[key].prompt = String(el.value || '').trim();
            RoomEditor.State.roomWizard.touched = true;
            RoomEditor.State.setDirty(true);
            RoomEditor.Storage.updateJsonText();
          });
        });
        document.getElementById('roomWizardThemeSelect')?.addEventListener('change', () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          const envMod = globalThis.RoomWizardEnvironment;
          if (!room || !envMod) return;
          envMod.ensureRoomEnvironment(room);
          const v = document.getElementById('roomWizardThemeSelect')?.value;
          if (v) room.environment.themeId = v;
          RoomEditor.State.roomWizard.touched = true;
          RoomEditor.State.setDirty(true);
          RoomEditor.Storage.updateJsonText();
        });
        document.getElementById('roomWizardTagsInput')?.addEventListener('input', () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          const envMod = globalThis.RoomWizardEnvironment;
          if (!room || !envMod) return;
          envMod.ensureRoomEnvironment(room);
          room.environment.tags = envMod.parseTagsInput(document.getElementById('roomWizardTagsInput')?.value);
          RoomEditor.State.roomWizard.touched = true;
          RoomEditor.State.setDirty(true);
          RoomEditor.Storage.updateJsonText();
        });
        document.getElementById('roomWizardUseV3Pipeline')?.addEventListener('change', () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          const envMod = globalThis.RoomWizardEnvironment;
          if (!room || !envMod) return;
          envMod.ensureRoomEnvironment(room);
          const checked = !!document.getElementById('roomWizardUseV3Pipeline')?.checked;
          room.environment.environment_pipeline_version = checked ? 'v3' : 'v2';
          RoomEditor.State.roomWizard.touched = true;
          RoomEditor.State.setDirty(true);
          RoomEditor.Storage.updateJsonText();
          RoomEditor.Wizard.renderRoomWizardEnvironmentOutputSummary(room.environment);
        });
        ['roomWizardThemeName', 'roomWizardEnvironmentNotes', 'roomWizardEnvironmentSeed', 'roomWizardLockStylepack'].forEach((id) => {
          const eventName = id === 'roomWizardLockStylepack' ? 'change' : 'input';
          document.getElementById(id)?.addEventListener(eventName, syncRoomWizardEnvironmentAuthoringFromInputs);
        });
        Object.entries(RoomEditor.Wizard.roomWizardResultsToggleMap()).forEach(([key, el]) => {
          el?.addEventListener('change', () => {
            RoomEditor.State.roomWizard.resultsToggles[key] = !!el.checked;
            const room = RoomEditor.Wizard.getRoomWizardRoom();
            if (room?.environment) {
              RoomEditor.Wizard.renderRoomWizardEnvironmentOutputSummary(room.environment);
            }
          });
        });
        document.getElementById('roomWizardReferenceUpload')?.addEventListener('change', (event) => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          const envMod = globalThis.RoomWizardEnvironment;
          if (!room || !envMod) return;
          envMod.ensureRoomEnvironment(room);
          RoomEditor.Wizard.ensureRoomWizardEnvironmentAuthoringFields(room.environment);
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
          RoomEditor.State.setDirty(true);
          RoomEditor.Wizard.renderRoomWizardReferenceList(room.environment);
          RoomEditor.Wizard.renderRoomWizardEnvironmentOutputSummary(room.environment);
          RoomEditor.Storage.updateJsonText();
          event.target.value = '';
        });
        document.getElementById('roomWizardArtDirectionSave')?.addEventListener('click', saveProjectArtDirectionFromWizard);
        document.getElementById('roomWizardGenerateArtDirectionConcepts')?.addEventListener('click', generateArtDirectionConceptBoard);
        document.getElementById('roomWizardAdaptTemplate')?.addEventListener('click', () => {
          RoomEditor.Wizard.adaptSelectedRoomArchetype('Rewrite this room draft so it fits the locked project style.');
        });
        document.getElementById('roomWizardGenerateComponentPrompts')?.addEventListener('click', async () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          const promptEl = document.getElementById('roomWizardCopilotPrompt');
          const st = document.getElementById('roomWizardCopilotStatus');
          if (!RoomEditor.State.PROJECT_ID || !room || !promptEl) return;
          const description = String(promptEl.value || '').trim();
          if (!description) {
            if (st) st.textContent = 'Write a short room draft first.';
            return;
          }
          RoomEditor.Wizard.startRoomWizardWaitbar('copilot', 'Generating component prompts from the current art direction and room draft.');
          if (st) st.textContent = 'Generating component prompts…';
          try {
            const res = await fetch(RoomEditor.State.projectRoomEnvironmentApiUrl(room.id, 'component-prompts'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                description,
                components: RoomEditor.Wizard.collectRoomWizardComponentPrompts()
              })
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.ok) throw new Error(json.error || 'Could not generate component prompts');
            const envMod = globalThis.RoomWizardEnvironment;
            if (envMod) envMod.ensureRoomEnvironment(room);
            room.environment.spec.description = description;
            room.environment.spec.components = json.components || room.environment.spec.components || {};
            RoomEditor.Wizard.syncRoomWizardComponentFields(room.environment);
            RoomEditor.Storage.updateJsonText();
            RoomEditor.State.setDirty(true);
            if (st) st.textContent = 'Component prompts ready — tweak them if needed, then build the environment.';
            RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
          } catch (e) {
            RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
            if (st) st.textContent = (e && e.message) || 'Component prompt generation failed';
          }
        });
        document.getElementById('roomWizardSimplifyDraft')?.addEventListener('click', () => {
          RoomEditor.Wizard.adaptSelectedRoomArchetype('Simplify this room draft so a novice creator can understand and edit it quickly.');
        });
        document.getElementById('roomWizardBiomeGenerateVisuals')?.addEventListener('click', async () => {
          const st = document.getElementById('roomWizardBiomeVisualStatus');
          const btn = document.getElementById('roomWizardBiomeGenerateVisuals');
          if (!RoomEditor.State.PROJECT_ID || !RoomEditor.State.PROJECT_BIOME_GENERATE_VISUALS_URL) {
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
          RoomEditor.Wizard.startRoomWizardWaitbar('copilot', 'Generating biome template visuals (Gemini).');
          try {
            const res = await fetch(RoomEditor.State.PROJECT_BIOME_GENERATE_VISUALS_URL, {
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
            RoomEditor.Wizard.updateRoomWizardBiomePackSummary();
            const failed = Array.isArray(json.results) ? json.results.filter((r) => r && !r.ok) : [];
            if (!json.used_ai) {
              if (st) st.textContent = 'Gemini did not return images — check server logs and GEMINI_IMAGE_MODEL.';
            } else if (failed.length) {
              if (st) st.textContent = `Partial: ${failed.length} layer(s) failed (${failed.map((f) => f.component_type).join(', ')}).`;
            } else {
              if (st) st.textContent = 'Biome template PNGs updated.';
              RoomEditor.Ui.showToast('Biome template visuals updated.', 'success');
            }
            RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
          } catch (e) {
            RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
            if (st) st.textContent = (e && e.message) || 'Biome generation failed';
          } finally {
            if (btn) btn.disabled = false;
          }
        });
        document.getElementById('roomWizardGeminiImageProbeBtn')?.addEventListener('click', async () => {
          const st = document.getElementById('roomWizardGeminiProbeStatus');
          if (st) st.textContent = 'Testing…';
          try {
            const r = await fetch(`${RoomEditor.Constants.API_PING_URL}?probe=1`, { cache: 'no-store' });
            const j = await r.json().catch(() => ({}));
            const probe = j.copilot && j.copilot.geminiImageProbe;
            if (j.copilot && j.copilot.lastGeminiImageError !== undefined) {
              RoomEditor.State.copilot.geminiLastError = j.copilot.lastGeminiImageError;
            }
            if (st) {
              if (probe && probe.ok) st.textContent = 'Image API returned an image.';
              else st.textContent = probe && probe.error ? `Failed: ${probe.error}` : 'Probe did not succeed.';
            }
            RoomEditor.Wizard.updateRoomWizardCopilotHintUi();
          } catch (e) {
            if (st) st.textContent = (e && e.message) ? String(e.message) : 'Request failed';
          }
        });
        document.getElementById('roomWizardCopilotGenerate')?.addEventListener('click', async () => {
          const copilotMod = globalThis.RoomWizardEnvironmentCopilot;
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          const promptEl = document.getElementById('roomWizardCopilotPrompt');
          const st = document.getElementById('roomWizardCopilotStatus');
          const btn = document.getElementById('roomWizardCopilotGenerate');
          if (!copilotMod || !room || !promptEl) return;
          const prompt = String(promptEl.value || '').trim();
          if (!prompt) {
            if (st) st.textContent = 'Enter a short description first.';
            return;
          }
          if (RoomEditor.State.PROJECT_ID) {
            RoomEditor.Wizard.clearRoomWizardCopilotPreview();
            if (st) st.textContent = 'Building room spec…';
            if (btn) btn.disabled = true;
            RoomEditor.State.roomWizard.aiRequestPending = true;
            RoomEditor.Wizard.startRoomWizardWaitbar('copilot', 'Building the room environment spec.');
            try {
              const specRes = await fetch(RoomEditor.State.projectRoomEnvironmentApiUrl(room.id, 'spec'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  environment_pipeline_version: room.environment?.environment_pipeline_version || 'v2',
                  description: prompt,
                  components: RoomEditor.Wizard.collectRoomWizardComponentPrompts()
                })
              });
              const specJson = await specRes.json().catch(() => ({}));
              if (!specRes.ok || !specJson.ok) {
                throw new Error(specJson.error || 'Could not build room environment spec');
              }
              RoomEditor.Wizard.replaceRoomWizardEnvironmentPreservingAuthoring(room, specJson.environment || room.environment);
              RoomEditor.Wizard.syncRoomWizardEnvironmentFromRoom();
              if (st) st.textContent = 'Rendering previews…';
              RoomEditor.Wizard.startRoomWizardWaitbar('copilot', 'Rendering room-aware environment previews.');
              const previewRes = await fetch(RoomEditor.State.projectRoomEnvironmentApiUrl(room.id, 'previews'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  spec: room.environment?.spec || {},
                  ...RoomEditor.Wizard.roomWizardAnalyticsContext(room, { request_kind: 'generate' }),
                })
              });
              const previewJson = await previewRes.json().catch(() => ({}));
              if (!previewRes.ok || !previewJson.ok) {
                throw new Error(previewJson.error || 'Could not generate previews');
              }
              RoomEditor.Wizard.replaceRoomWizardEnvironmentPreservingAuthoring(room, previewJson.environment || room.environment);
              RoomEditor.State.roomWizard.copilotPreview = {
                themeId: room.environment?.themeId || 'custom',
                tags: room.environment?.tags || [],
                rationale: room.environment?.spec?.description || ''
              };
              RoomEditor.Wizard.renderRoomWizardCopilotPreview(RoomEditor.State.roomWizard.copilotPreview);
              RoomEditor.Wizard.renderRoomWizardEnvironmentPreview(room.environment);
              RoomEditor.Wizard.renderRoomWizardPreviewGallery(room.environment?.preview || {});
              RoomEditor.Wizard.renderRoomWizardEnvironmentOutputSummary(room.environment);
              RoomEditor.Storage.updateJsonText();
              if (st) st.textContent = 'Pictures ready — open 2 · Preview & build to approve one.';
              RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
            } catch (e) {
              RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
              if (st) st.textContent = (e && e.message) || 'Environment generation failed';
              RoomEditor.Wizard.postRoomWizardFeedback(room, 'generation_error', { message: (e && e.message) || 'Environment generation failed' });
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
          RoomEditor.Wizard.clearRoomWizardCopilotPreview();
          if (st) st.textContent = 'Generating…';
          if (btn) btn.disabled = true;
          RoomEditor.Wizard.startRoomWizardWaitbar('copilot', 'Generating a Gemini environment suggestion.');
          try {
            const res = await fetch(RoomEditor.Constants.API_COPILOT_URL, {
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
              RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
              return;
            }
            const raw = json.data;
            let payload;
            try {
              payload = copilotMod.normalizeCopilotPayload(raw);
            } catch (e) {
              if (st) st.textContent = (e && e.message) || 'Invalid Copilot payload';
              RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
              return;
            }
            RoomEditor.State.roomWizard.copilotPreview = payload;
            RoomEditor.Wizard.renderRoomWizardCopilotPreview(payload);
            if (st) st.textContent = 'Diagram ready — apply or discard. For photo previews, Load Room with a workbench project (?project_id) first.';
            RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
          } catch (e) {
            RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
            if (st) st.textContent = (e && e.message) || 'Network error';
          } finally {
            if (btn) btn.disabled = false;
          }
        });
        document.getElementById('roomWizardCopilotApply')?.addEventListener('click', () => {
          const copilotMod = globalThis.RoomWizardEnvironmentCopilot;
          const envMod = globalThis.RoomWizardEnvironment;
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          const preview = RoomEditor.State.roomWizard.copilotPreview;
          if (!envMod || !room || !preview) return;
          if (RoomEditor.State.PROJECT_ID) {
            envMod.ensureRoomEnvironment(room);
            room.environment.themeId = preview.themeId;
            room.environment.tags = Array.isArray(preview.tags) ? [...preview.tags] : [];
            room.environment.spec.description = preview.rationale || room.environment.spec.description || '';
          } else {
            if (!copilotMod) return;
            copilotMod.applyCopilotPayloadToRoom(room, preview, envMod);
          }
          RoomEditor.State.roomWizard.touched = true;
          RoomEditor.State.setDirty(true);
          RoomEditor.Storage.updateJsonText();
          RoomEditor.Wizard.syncRoomWizardEnvironmentFromRoom();
          RoomEditor.Wizard.clearRoomWizardCopilotPreview();
          RoomEditor.Ui.setStatus(RoomEditor.State.PROJECT_ID ? 'Applied planner suggestion to local room fields.' : 'Applied Copilot suggestion to theme and tags.', 'success');
        });
        document.getElementById('roomWizardPreviewRevise')?.addEventListener('click', async () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          const st = document.getElementById('roomWizardCopilotStatus');
          const revisionEl = document.getElementById('roomWizardPreviewRevision');
          const promptEl = document.getElementById('roomWizardCopilotPrompt');
          if (!RoomEditor.State.PROJECT_ID || !room || !revisionEl || !promptEl) return;
          const instruction = String(revisionEl.value || '').trim();
          if (!instruction) {
            if (st) st.textContent = 'Add a revision request first.';
            return;
          }
          RoomEditor.Wizard.startRoomWizardWaitbar('copilot', 'Revising the room environment and regenerating previews.');
          RoomEditor.State.roomWizard.aiRequestPending = true;
          if (st) st.textContent = 'Revising environment…';
          try {
            const reviseRes = await fetch(RoomEditor.State.projectRoomEnvironmentApiUrl(room.id, 'revise'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                instruction,
                ...RoomEditor.Wizard.roomWizardAnalyticsContext(room, { request_kind: 'revise' }),
              })
            });
            const reviseJson = await reviseRes.json().catch(() => ({}));
            if (!reviseRes.ok || !reviseJson.ok) throw new Error(reviseJson.error || 'Could not revise room environment');
            promptEl.value = reviseJson.draft_description || promptEl.value;
            if (st) st.textContent = 'Building revised room spec…';
            const specRes = await fetch(RoomEditor.State.projectRoomEnvironmentApiUrl(room.id, 'spec'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ description: promptEl.value, components: RoomEditor.Wizard.collectRoomWizardComponentPrompts() })
            });
            const specJson = await specRes.json().catch(() => ({}));
            if (!specRes.ok || !specJson.ok) throw new Error(specJson.error || 'Could not build revised room spec');
            RoomEditor.Wizard.replaceRoomWizardEnvironmentPreservingAuthoring(room, specJson.environment || room.environment);
            if (st) st.textContent = 'Rendering revised previews…';
            const previewRes = await fetch(RoomEditor.State.projectRoomEnvironmentApiUrl(room.id, 'previews'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                spec: room.environment?.spec || {},
                ...RoomEditor.Wizard.roomWizardAnalyticsContext(room, { request_kind: 'revise' }),
              })
            });
            const previewJson = await previewRes.json().catch(() => ({}));
            if (!previewRes.ok || !previewJson.ok) throw new Error(previewJson.error || 'Could not render revised previews');
            RoomEditor.Wizard.replaceRoomWizardEnvironmentPreservingAuthoring(room, previewJson.environment || room.environment);
            revisionEl.value = '';
            RoomEditor.Wizard.renderRoomWizardEnvironmentPreview(room.environment);
            RoomEditor.Wizard.renderRoomWizardCopilotPreview({
              themeId: room.environment?.themeId || 'custom',
              tags: room.environment?.tags || [],
              rationale: room.environment?.spec?.description || ''
            });
            RoomEditor.Wizard.renderRoomWizardPreviewGallery(room.environment?.preview || {});
            RoomEditor.Wizard.renderRoomWizardEnvironmentOutputSummary(room.environment);
            RoomEditor.Storage.updateJsonText();
            RoomEditor.State.setDirty(true);
            if (st) st.textContent = 'Revised previews ready — approve one to push it into Open Game.';
            RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
          } catch (e) {
            RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
            if (st) st.textContent = (e && e.message) || 'Revision failed';
            RoomEditor.Wizard.postRoomWizardFeedback(room, 'generation_error', { message: (e && e.message) || 'Revision failed' });
          } finally {
            RoomEditor.State.roomWizard.aiRequestPending = false;
          }
        });
        document.getElementById('roomWizardReviewGoDescribe')?.addEventListener('click', () => {
          RoomEditor.Wizard.setRoomWizardEnvStep('describe');
        });
        document.getElementById('roomWizardEnvironmentOutputSummary')?.addEventListener('click', async (event) => {
          const slotBtn = event.target.closest('[data-rw-bespoke-slot-action]');
          if (slotBtn) {
            event.preventDefault();
            const action = slotBtn.getAttribute('data-rw-bespoke-slot-action');
            const slotId = slotBtn.getAttribute('data-rw-bespoke-slot-id');
            if (!slotId || (action !== 'regen' && action !== 'iterate')) return;
            const room = RoomEditor.Wizard.getRoomWizardRoom();
            const st = document.getElementById('roomWizardCopilotStatus');
            if (!RoomEditor.State.PROJECT_ID || !room?.id) return;
            if (!room.environment?.preview?.approved_image_id) {
              if (st) st.textContent = 'Approve a room preview before regenerating assets.';
              return;
            }
            if (RoomEditor.State.roomWizard.aiRequestPending) return;
            RoomEditor.State.roomWizard.aiRequestPending = true;
            const iterate = action === 'iterate';
            const waitMs = RoomEditor.Wizard.roomWizardEstimateBespokeAssetWaitMs(room, { slotId });
            const waitMin = Math.max(1, Math.round(waitMs / 60000));
            RoomEditor.Wizard.startRoomWizardWaitbar(
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
              const res = await fetch(RoomEditor.State.projectRoomEnvironmentApiUrl(room.id, 'generate-assets'), {
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
              RoomEditor.Wizard.replaceRoomWizardEnvironmentPreservingAuthoring(room, json.environment || room.environment);
              RoomEditor.Wizard.renderRoomWizardEnvironmentPreview(room.environment);
              RoomEditor.Wizard.renderRoomWizardPreviewGallery(room.environment.preview || {});
              RoomEditor.Wizard.renderRoomWizardEnvironmentOutputSummary(room.environment);
              RoomEditor.Storage.updateJsonText();
              RoomEditor.State.setDirty(true);
              RoomEditor.GamePreview.refreshOpenGamePreviewIfVisible(room.id);
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
              RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
            }
            return;
          }
          const openGameBtn = event.target.closest('.rw-runtime-review-open-game');
          if (openGameBtn) {
            const room = RoomEditor.Wizard.getRoomWizardRoom();
            if (!room?.id) return;
            RoomEditor.Wizard.postRoomWizardFeedback(room, 'open_game_preview');
            RoomEditor.GamePreview.openGameWithLayout(room.id);
          }
        });
        document.getElementById('roomWizardDock')?.addEventListener('click', (event) => {
          const previewBtn = event.target.closest('button.rw-preview-card-open[data-rw-asset-src]');
          if (previewBtn) {
            event.preventDefault();
            RoomEditor.Wizard.openRoomEnvironmentAssetPreviewWindow(previewBtn.getAttribute('data-rw-asset-src'));
            return;
          }
          const assetBtn = event.target.closest('button.rw-environment-asset-open');
          if (assetBtn) {
            const src = assetBtn.getAttribute('data-rw-asset-src');
            if (src) {
              event.preventDefault();
              RoomEditor.Wizard.openRoomEnvironmentAssetPreviewWindow(src);
            }
          }
        });
        document.getElementById('roomWizardBuildEnvironmentAssets')?.addEventListener('click', async () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          const st = document.getElementById('roomWizardCopilotStatus');
          const buildButton = document.getElementById('roomWizardBuildEnvironmentAssets');
          if (!RoomEditor.State.PROJECT_ID || !room?.id) return;
          if (!room.environment?.preview?.approved_image_id) {
            if (st) st.textContent = 'Approve a room preview before building final room assets.';
            return;
          }
          if (buildButton) {
            buildButton.disabled = true;
            buildButton.textContent = 'Building final room assets…';
          }
          const fullWaitMs = RoomEditor.Wizard.roomWizardEstimateBespokeAssetWaitMs(room, { forFullBuild: true });
          const fullWaitMin = Math.max(1, Math.round(fullWaitMs / 60000));
          const geminiSlots = RoomEditor.Wizard.roomWizardEstimateBespokeGeminiSlotCount(room, { forFullBuild: true });
          RoomEditor.Wizard.startRoomWizardWaitbar(
            'copilot',
            `Building bespoke kit (~${fullWaitMin} min est., ~${geminiSlots} Gemini slots)…`,
            fullWaitMs
          );
          if (st) {
            st.textContent = `Building bespoke production assets… about ${fullWaitMin} min estimated (${geminiSlots} Gemini slots × multi-reference image time).`;
          }
          try {
            const res = await fetch(RoomEditor.State.projectRoomEnvironmentApiUrl(room.id, 'generate-assets'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                preview_id: room.environment.preview.approved_image_id,
                environment_pipeline_version: room.environment?.environment_pipeline_version || 'v2'
              })
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.ok) throw new Error(json.error || 'Could not build production assets');
            RoomEditor.Wizard.replaceRoomWizardEnvironmentPreservingAuthoring(room, json.environment || room.environment);
            RoomEditor.Wizard.renderRoomWizardEnvironmentPreview(room.environment);
            RoomEditor.Wizard.renderRoomWizardPreviewGallery(room.environment.preview || {});
            RoomEditor.Wizard.renderRoomWizardEnvironmentOutputSummary(room.environment);
            RoomEditor.Storage.updateJsonText();
            RoomEditor.State.setDirty(true);
            RoomEditor.GamePreview.refreshOpenGamePreviewIfVisible(room.id);
            const bespoke = room.environment?.runtime?.bespoke_asset_manifest || {};
            const builtCount = Array.isArray(bespoke.built_slots) ? bespoke.built_slots.length : Object.values(bespoke.assets || {}).filter((item) => item && item.url).length;
            const requiredCount = Array.isArray(bespoke.required_slots) ? bespoke.required_slots.length : (Array.isArray(bespoke.generation_plan) ? bespoke.generation_plan.length : builtCount);
            const review = bespoke.runtime_review || bespoke.review || {};
            const reviewWarnings = Array.isArray(review.warning_reasons) ? review.warning_reasons : [];
            if (st) st.textContent = room.environment?.runtime?.bespoke_asset_manifest?.status === 'ready'
              ? `Bespoke biome assets complete: ${builtCount}/${requiredCount || builtCount} required slots built and runtime review passed${reviewWarnings.length ? ` with warnings: ${reviewWarnings.join(', ')}` : ''}. Open Game now uses the generated room-piece kit.`
              : `Bespoke asset generation incomplete: ${builtCount}/${requiredCount || builtCount} slots built. Runtime review: ${review.status || 'blocked'}${Array.isArray(review.fail_reasons) && review.fail_reasons.length ? ` · ${review.fail_reasons.join(', ')}` : ''}.`;
            RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
          } catch (e) {
            RoomEditor.Wizard.stopRoomWizardWaitbar('copilot', 100);
            if (st) st.textContent = (e && e.message) || 'Asset generation failed';
            if (buildButton) {
              buildButton.disabled = false;
              buildButton.textContent = 'Retry final room assets';
            }
          }
        });
        document.getElementById('roomWizardCopilotDiscard')?.addEventListener('click', () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          if (room) RoomEditor.Wizard.postRoomWizardFeedback(room, 'discarded');
          RoomEditor.Wizard.clearRoomWizardCopilotPreview();
        });
        document.querySelectorAll('#roomWizardTerrainPresets [data-terrain-preset]').forEach((btn) => {
          btn.addEventListener('click', () => RoomEditor.Wizard.applyTerrainPresetFromWizard(btn.getAttribute('data-terrain-preset')));
        });
        document.getElementById('roomWizardTerrainDuplicate')?.addEventListener('click', roomWizardTerrainDuplicate);
        document.getElementById('roomWizardTerrainMirror')?.addEventListener('click', roomWizardTerrainMirror);
        document.getElementById('roomWizardRoomName')?.addEventListener('input', () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          if (!room) return;
          RoomEditor.State.roomWizard.touched = true;
          room.name = document.getElementById('roomWizardRoomName').value;
          RoomEditor.State.setDirty(true);
          RoomEditor.Workflow.updateWorkflowRailPills();
          RoomEditor.Render.redraw();
        });
        document.getElementById('roomWizardRoomId')?.addEventListener('change', () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          if (!room) return;
          RoomEditor.State.roomWizard.touched = true;
          const raw = document.getElementById('roomWizardRoomId').value.trim();
          const next = raw || room.id;
          if (!/^(?:[A-Z][A-Z0-9]*-)?R\d+$/i.test(next)) {
            RoomEditor.Ui.setStatus('Room id must look like R1 or a scoped id like RG-R1.', 'error');
            document.getElementById('roomWizardRoomId').value = room.id;
            return;
          }
          const canonical = next.replace(/(^|-)r(?=\d+$)/i, '$1R');
          const clash = RoomEditor.State.data.rooms.some((r) => r.id === canonical && r !== room);
          if (clash) {
            RoomEditor.Ui.setStatus(`Room id ${canonical} is already in use.`, 'error');
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
          RoomEditor.Ui.populateRoomSelect();
          RoomEditor.Ui.refs.roomSelect.value = canonical;
          RoomEditor.State.setDirty(true);
          RoomEditor.Workflow.updateWorkflowRailPills();
          RoomEditor.Render.redraw();
        });
        document.querySelectorAll('input[name="roomWizardFootprint"]').forEach((radio) => {
          radio.addEventListener('change', () => {
            const room = RoomEditor.Wizard.getRoomWizardRoom();
            if (!room) return;
            RoomEditor.State.roomWizard.touched = true;
            const v = radio.value;
            if (v === 'custom') {
              document.getElementById('roomWizardCustomFootprint').hidden = false;
              return;
            }
            document.getElementById('roomWizardCustomFootprint').hidden = true;
            const dims = RoomEditor.Constants.RW_FOOTPRINT_PRESETS[v];
            if (dims) {
              RoomEditor.Wizard.applyFootprintDimensionsToRoom(room, dims[0], dims[1]);
              RoomEditor.State.setDirty(true);
              RoomEditor.Workflow.updateWorkflowRailPills();
              RoomEditor.Render.redraw();
            }
          });
        });
        document.getElementById('roomWizardApplyCustomFootprint')?.addEventListener('click', () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          if (!room) return;
          RoomEditor.State.roomWizard.touched = true;
          const w = Number(document.getElementById('roomWizardCustomW').value);
          const h = Number(document.getElementById('roomWizardCustomH').value);
          if (!Number.isFinite(w) || !Number.isFinite(h)) {
            RoomEditor.Ui.setStatus('Enter valid width and height.', 'error');
            return;
          }
          RoomEditor.Wizard.applyFootprintDimensionsToRoom(room, w, h);
          RoomEditor.State.setDirty(true);
          RoomEditor.Workflow.updateWorkflowRailPills();
          RoomEditor.Render.redraw();
        });
        document.getElementById('roomWizardNeighbor')?.addEventListener('change', () => {
          const room = RoomEditor.Wizard.getRoomWizardRoom();
          const neighborId = document.getElementById('roomWizardNeighbor')?.value;
          if (!room) return;
          RoomEditor.Wizard.syncRoomWizardEdgeSelects();
          if (!neighborId) return;
          const neighbor = RoomEditor.Model.getRoomById(neighborId);
          const myEdge = document.getElementById('roomWizardMyEdge');
          const nbEdge = document.getElementById('roomWizardNeighborEdge');
          const link = (room.edgeLinks || []).find((l) => l.targetRoomId === neighborId);
          if (link && neighbor && myEdge && nbEdge) {
            if (link.edgeIndex >= 0 && link.edgeIndex < RoomEditor.Model.getEdgeCount(room)) {
              myEdge.value = String(link.edgeIndex);
            }
            if (link.targetEdgeIndex >= 0 && link.targetEdgeIndex < RoomEditor.Model.getEdgeCount(neighbor)) {
              nbEdge.value = String(link.targetEdgeIndex);
            }
          }
        });
        document.getElementById('roomWizardBtnAlign')?.addEventListener('click', () => RoomEditor.Wizard.applyRoomWizardAlign());
        document.getElementById('roomWizardBtnHatch')?.addEventListener('click', () => RoomEditor.Wizard.applyRoomWizardHatch());
        document.getElementById('roomWizardBtnMatchWallLen')?.addEventListener('click', () => RoomEditor.Wizard.applyRoomWizardMatchWallLength());
        document.getElementById('roomWizardBtnExportJson')?.addEventListener('click', () => {
          RoomEditor.Storage.downloadJson();
        });
        document.getElementById('roomWizardBtnExportRuntime')?.addEventListener('click', () => {
          RoomEditor.Storage.downloadExportPackage();
        });
        document.getElementById('roomWizardBtnOpenGame')?.addEventListener('click', () => {
          const id = RoomEditor.State.roomWizard.roomId || RoomEditor.State.currentRoomId;
          RoomEditor.GamePreview.openGameWithLayout(id);
        });
      }

  root.RoomEditor.Wizard.wireRoomWizardEvents = wireRoomWizardEvents;
})(typeof globalThis !== 'undefined' ? globalThis : this);
