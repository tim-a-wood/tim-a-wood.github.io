function currentMode() {
    return "wizard";
}

function isWizardMode() {
    return true;
}

function normalizeWizardVisibility(value) {
    return String(value || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

function wizardSectionIds(step) {
    return WIZARD_SECTION_MAP[step] || [];
}

function phaseKeyForStep(step) {
    if (["describe", "project", "brief", "references"].includes(step)) return "describe";
    if (["concepts", "review", "character", "rig_layout", "part_manifest", "part_shape_edit", "split_build", "split_review", "sprite_model", "rig"].includes(step)) return "concepts";
    if (["animations", "clips", "qa"].includes(step)) return "animations";
    if (step === "export") return "export";
    return "describe";
}

function phaseMetaByKey(key) {
    return FLIGHTDECK_PHASES.find((phase) => phase.key === key) || FLIGHTDECK_PHASES[0];
}

function activePhaseMeta(project = state.activeProject) {
    const step = project?.wizard_state?.current_step || project?.recommended_next_step || activeWizardStep();
    return phaseMetaByKey(phaseKeyForStep(step));
}

function visibleWizardSteps(project = state.activeProject) {
    if (!aiWorkflowEnabled(project)) return WIZARD_STEPS;
    if (String(project?.brief?.backend_mode || "") === "pixellab") {
        return ["describe", "concepts", "character", "animations", "export"];
    }
    return ["describe", "concepts", "character", "export"];
}

function wizardProgressSummary(project) {
    const statuses = project?.step_statuses || {};
    const completed = Object.values(statuses).filter((status) => status === "complete").length;
    const total = visibleWizardSteps(project).length;
    return `${completed}/${total} steps complete`;
}

function blankWizardModel() {
    return {
        current_step: "describe",
        recommended_next_step: "describe",
        step_statuses: {
            describe: "active",
            concepts: "locked",
            animations: "locked",
            export: "locked",
            project: "active",
            brief: "locked",
            references: "locked",
            review: "locked",
            rig_layout: "locked",
            part_manifest: "locked",
            part_shape_edit: "locked",
            split_build: "locked",
            split_review: "locked",
            sprite_model: "locked",
            rig: "locked",
            clips: "locked",
            qa: "locked",
        },
        blocking_reasons: {
            describe: ["Create a project first."],
            concepts: ["Save the character description first."],
            animations: ["Approve and lock a concept source first."],
            export: ["Finish animations and canonical clips before review and export."],
            brief: ["Create a project first."],
            references: ["Save the character description first."],
            review: ["Generate or import at least one valid concept image first."],
            rig_layout: ["Approve a source concept before continuing."],
            part_manifest: ["Complete rig layout approval before part manifest."],
            part_shape_edit: ["Approve the part manifest first."],
            split_build: ["Approve the part shapes first."],
            split_review: ["Build split assets first."],
            sprite_model: ["Approve the split parts first."],
            rig: ["Build and approve the sprite model first."],
            clips: ["Approve the rig first."],
            qa: ["Render the clips first."],
        },
    };
}

function wizardModel() {
    const project = state.activeProject;
    if (!project) return blankWizardModel();
    return {
        current_step: project.wizard_state?.current_step || project.recommended_next_step || "describe",
        recommended_next_step: project.recommended_next_step || project.wizard_state?.current_step || "describe",
        step_statuses: project.step_statuses || {},
        blocking_reasons: project.blocking_reasons || {},
    };
}

function activeWizardStep() {
    return wizardModel().current_step || wizardModel().recommended_next_step || "describe";
}

const WIZARD_LEGACY_LABELS = {
    rig_layout: "Rig Layout",
    part_manifest: "Part Manifest",
    clips: "Build Animations",
    qa: "Check Results",
};

function wizardStepLabel(step, project = state.activeProject) {
    if (aiWorkflowLegacyMode(project) && WIZARD_LEGACY_LABELS[step]) {
        return WIZARD_LEGACY_LABELS[step];
    }
    return WIZARD_META[step]?.label || step;
}

function wizardSummaryText(step) {
    const project = state.activeProject;
    if (!project) {
        if (step === "project") return "No project yet.";
        return "Not started.";
    }
    switch (step) {
        case "describe":
            return `${project.project_name} · ${project.brief?.references?.length || 0} ref(s)`;
        case "project":
            return project.project_name;
        case "brief":
            return project.prompt_text || project.brief?.role_archetype || "Description saved.";
        case "references":
            return `${project.brief?.references?.length || 0} stored reference(s)`;
        case "concepts":
            return project.latest_prompt ? `Prompt v${project.latest_prompt.prompt_version}` : "No prompt generated yet.";
        case "review":
            return project.selected_concept_id ? `Chosen ${project.selected_concept_id}` : "No valid concept chosen yet.";
        case "rig_layout":
            if (aiWorkflowEnabled(project)) {
                if (String(project.brief?.backend_mode || "") === "pixellab") {
                    return project.selected_concept_id ? `Locked ${project.selected_concept_id}` : "Choose a concept first.";
                }
                return project.ai_workflow?.character_lock?.approved_asset_id || "Character Lock not approved yet.";
            }
            return project.rig_layout_approved ? `${project.rig_layout?.rig_profile || "layout"} approved` : project.rig_layout ? `${project.rig_layout?.parts?.length || 0} parts in layout` : "Rig layout not generated yet.";
        case "part_manifest":
            if (aiWorkflowEnabled(project)) {
                if (String(project.brief?.backend_mode || "") === "pixellab") {
                    return pixellabCharacterApproved(project) ? "Source locked for animation." : "Approve and lock a look first.";
                }
                return project.ai_workflow?.key_pose_set?.approved_run_id || "Key Pose Board not approved yet.";
            }
            return project.part_manifest_approved ? `${project.part_manifest?.parts?.length || 0} manifest parts approved` : project.part_manifest ? `${project.part_manifest?.parts?.length || 0} manifest parts` : "Part manifest not generated yet.";
        case "part_shape_edit":
            return project.part_shapes_approved ? `${project.part_shapes?.parts?.length || 0} shapes approved` : project.part_shapes ? `${project.part_shapes?.parts?.length || 0} shape drafts` : "Part shapes not initialized yet.";
        case "split_build":
            return project.part_split?.parts?.length ? `${project.part_split.parts.length} candidate parts` : "Split assets not built yet.";
        case "split_review":
            return project.part_split_approved ? "Split approved." : project.part_split ? (project.part_split.validation?.status || "candidate") : "Split not ready.";
        case "sprite_model":
            return project.sprite_model?.parts?.length ? `${project.sprite_model.parts.length} parts extracted` : "Sprite model not built yet.";
        case "rig":
            return project.rig_review_approved ? "Rig approved." : project.rig ? "Rig built." : "Rig not built.";
        case "character":
        case "clips":
            if (aiWorkflowEnabled(project)) {
                if (String(project.brief?.backend_mode || "") === "pixellab") {
                    if (pixellabCharacterApproved(project)) return "Source locked for animation.";
                    if (project.pixellab_character) return "Source prepared — approve from Concepts to continue.";
                    return "Approve and lock a concept source.";
                }
                const idleRun = aiWorkflowApprovedRun("cleanup_runs", "idle", project);
                const walkRun = aiWorkflowApprovedRun("cleanup_runs", "walk", project);
                return `${idleRun ? "idle cleaned" : "idle pending"} · ${walkRun ? "walk cleaned" : "walk pending"}`;
            }
            return `${project.build_status?.idle_render_complete ? "idle ready" : "idle pending"} · ${project.build_status?.walk_render_complete ? "walk ready" : "walk pending"}`;
        case "animations":
            if (String(project.brief?.backend_mode || "") === "pixellab") {
                const animations = project.pixellab_animations?.animations || {};
                const generatedNames = Object.keys(animations).filter((name) => pixellabAnyDirectionHasFrames(animations[name]));
                const clips = project.animation_clips || {};
                const built = Object.values(clips).some((clip) => Array.isArray(clip?.frames) && clip.frames.length);
                return `${generatedNames.length} clip${generatedNames.length === 1 ? "" : "s"} generated${built ? " · synced" : ""}`;
            }
            return "N/A";
        case "qa":
            return project.qa_report?.status || (aiWorkflowEnabled(project) ? "Cleanup & QA not run." : "Checks not run.");
        case "export":
            return project.last_export?.export_dir || "No export yet.";
        default:
            return "";
    }
}

function syncWizardPanelHeadings() {
    const sectionIds = [...new Set(Object.values(WIZARD_SECTION_MAP).flat())];
    sectionIds.forEach((id) => {
        const section = document.querySelector(`#${id}`);
        if (!section) return;
        const title = section.querySelector(".section-head h3");
        const description = section.querySelector(".section-head p");
        if (title && !section.dataset.defaultTitle) section.dataset.defaultTitle = title.textContent;
        if (description && !section.dataset.defaultDescription) section.dataset.defaultDescription = description.textContent;
    });

    if (!isWizardMode()) {
        sectionIds.forEach((id) => {
            const section = document.querySelector(`#${id}`);
            if (!section) return;
            const title = section.querySelector(".section-head h3");
            const description = section.querySelector(".section-head p");
            if (title && section.dataset.defaultTitle) title.textContent = section.dataset.defaultTitle;
            if (description && section.dataset.defaultDescription) description.textContent = section.dataset.defaultDescription;
        });
        return;
    }

    const step = activeWizardStep();
    const meta = WIZARD_META[step];
    const sectionId = wizardSectionIds(step)[0];
    const section = sectionId ? document.querySelector(`#${sectionId}`) : null;
    if (!section || !meta) return;
    const title = section.querySelector(".section-head h3");
    const description = section.querySelector(".section-head p");
    if (title) title.textContent = wizardStepLabel(step);
    if (description) description.textContent = meta.description;
}

async function persistWizardState(payload) {
    if (!state.activeProject) return null;
    const project = await api(`/api/projects/${state.activeProject.project_id}/wizard-state`, {
        method: "POST",
        body: JSON.stringify(payload),
    });
    state.activeProject = project;
    await refreshProjects();
    return project;
}

async function setUiMode(mode) {
    state.uiMode = "wizard";
    renderAll();
}

async function goToWizardStep(step) {
    const model = wizardModel();
    if (model.step_statuses?.[step] === "locked") return;
    if (!state.activeProject) {
        state.uiMode = "wizard";
        renderAll();
        return;
    }
    const project = await persistWizardState({ current_step: step, last_ui_mode: "wizard" });
    if (project) {
        state.uiMode = "wizard";
        renderAll();
    }
}

function nextClipAction() {
    const project = state.activeProject;
    if (!project?.build_status?.idle_render_complete) {
        return { label: "Build Idle", run: () => runJob(`/api/projects/${project.project_id}/clips/idle/render`) };
    }
    if (!project?.build_status?.walk_render_complete) {
        return { label: "Build Walk", run: () => runJob(`/api/projects/${project.project_id}/clips/walk/render`) };
    }
    return {
        label: "Continue to review & export",
        run: () => persistWizardState({ completed_steps: ["animations"], current_step: "export", last_ui_mode: "wizard" }),
    };
}

function applyModeVisibility() {
    const mode = "wizard";
    const activeStep = activeWizardStep();
    const aiEnabled = aiWorkflowEnabled();
    const hiddenForAi = new Set([]);
    document.body.classList.toggle("wizard-mode", mode === "wizard");
    const allowedSections = new Set(mode === "wizard" ? wizardSectionIds(activeStep) : WORKBENCH_SECTION_IDS);
    WORKBENCH_SECTION_IDS.forEach((id) => {
        const node = document.querySelector(`#${id}`);
        if (!node) return;
        const shouldHide = (mode === "wizard" && !allowedSections.has(id)) || (aiEnabled && hiddenForAi.has(id));
        const wasHidden = node.classList.contains("hidden-by-mode");
        node.classList.toggle("hidden-by-mode", shouldHide);
        node.hidden = shouldHide;
        if (wasHidden && !shouldHide) {
            node.classList.remove("phase-entering");
            requestAnimationFrame(() => requestAnimationFrame(() => node.classList.add("phase-entering")));
        }
    });
    document.querySelectorAll(".nav-link").forEach((node) => {
        const href = node.getAttribute("href");
        const sectionId = href?.startsWith("#") ? href.slice(1) : "";
        node.hidden = Boolean(aiEnabled && hiddenForAi.has(sectionId));
    });
    document.querySelectorAll("[data-wizard-view]").forEach((node) => {
        const steps = normalizeWizardVisibility(node.dataset.wizardView);
        const show = mode !== "wizard" ? true : steps.includes(activeStep);
        node.classList.toggle("wizard-hidden", !show);
        node.hidden = !show;
    });
    document.querySelectorAll(".wizard-only").forEach((node) => {
        node.classList.toggle("wizard-hidden", mode !== "wizard");
        if (mode !== "wizard") {
            node.hidden = true;
        } else if (!node.hasAttribute("data-wizard-view")) {
            node.hidden = false;
        }
    });
    syncWizardPanelHeadings();
}

function syncWorkflowModeControls() {
    const aiEnabled = aiWorkflowEnabled();
    const backendMode = state.activeProject?.brief?.backend_mode || "comfyui";
    const productionWarning = document.querySelector("#production-warning");
    if (productionWarning) {
        if (!aiEnabled) {
            productionWarning.textContent = "Clip output is deterministic. Rebuilds from the same approved sprite model and rig should match exactly.";
        } else if (backendMode === "pixellab") {
            productionWarning.textContent = "Pixel Lab mode: approve a concept to lock the east-facing source, then generate animations from that locked source. This legacy Production panel is hidden in the guided wizard.";
        } else if (backendMode === "debug_procedural") {
            productionWarning.textContent = "AI workflow mode is active in Debug Placeholder mode. Legacy motion, extraction, and cleanup use deterministic local transforms only.";
        } else {
            productionWarning.textContent = "AI workflow mode is active. Legacy motion uses ComfyUI when configured; extraction and pixel cleanup stay local.";
        }
    }
    ["#render-idle", "#render-walk"].forEach((selector) => {
        const node = document.querySelector(selector);
        if (node) node.hidden = aiEnabled;
    });
}

function getPhaseStateClass(phaseKey) {
    const model = wizardModel();
    const stepStatuses = model.step_statuses || {};
    const currentPhase = activePhaseMeta(state.activeProject);
    const rawStatus = stepStatuses[phaseKey] || (phaseKey === "describe" ? "active" : "locked");
    if (rawStatus === "locked") return "locked";
    if (phaseKey === currentPhase.key) return "active";
    if (rawStatus === "complete") return "complete";
    return "available";
}

function renderPhaseHeaders() {
    FLIGHTDECK_PHASES.forEach((phase, index) => {
        const section = document.getElementById(phase.sectionId);
        if (!section) return;
        section.querySelector(".phase-header")?.remove();
        const stateClass = getPhaseStateClass(phase.key);
        const number = stateClass === "complete" ? "✓" : String(index + 1).padStart(2, "0");
        const header = document.createElement("div");
        header.className = "phase-header";
        header.innerHTML = `
            <div class="phase-header-left">
                <div class="phase-header-eyebrow">
                    <span class="phase-header-num ${stateClass}">${number}</span>
                </div>
                <h2>${phase.label}</h2>
                <p class="phase-header-desc">${phase.description}</p>
            </div>
        `;
        section.insertBefore(header, section.firstChild);
    });
}

function renderModeShell() {
    const phaseRail = document.querySelector("#phase-rail");
    const mobileTabs = document.querySelector("#mobile-tabs");
    const model = wizardModel();
    const currentPhase = activePhaseMeta(state.activeProject);
    const stepStatuses = model.step_statuses || {};

    const pillMarkup = () => FLIGHTDECK_PHASES.map((phase, index) => {
        const rawStatus = stepStatuses[phase.key] || (phase.key === "describe" ? "active" : "locked");
        const stateClass = rawStatus === "locked"
            ? "locked"
            : phase.key === currentPhase.key
                ? "active"
                : rawStatus === "complete"
                    ? "complete"
                    : "available";
        const number = stateClass === "complete" ? "✓" : String(index + 1).padStart(2, "0");
        return `
            <a class="phase-pill ${stateClass}" href="#${phase.sectionId}" data-step="${phase.key}" data-section="${phase.sectionId}">
                <span class="phase-number">${number}</span>
                <span class="phase-pill-copy">
                    <strong>${phase.label}</strong>
                    <small>${phase.description}</small>
                </span>
            </a>
        `;
    }).join("");

    if (phaseRail) {
        phaseRail.innerHTML = pillMarkup();
    }
    if (mobileTabs) {
        mobileTabs.innerHTML = FLIGHTDECK_PHASES.map((phase) => {
            const tabState = getPhaseStateClass(phase.key);
            const shortLabel = phase.key === "describe" ? "Brief" : phase.key === "concepts" ? "Looks" : phase.key === "character" ? "Lock" : phase.key === "animations" ? "Move" : "Export";
            return `<a class="mobile-tab ${tabState}" href="#${phase.sectionId}" data-step="${phase.key}" data-section="${phase.sectionId}">${shortLabel}</a>`;
        }).join("");
    }
    renderPhaseHeaders();

    document.querySelectorAll("[data-step][data-section]").forEach((link) => {
        link.addEventListener("click", async (event) => {
            event.preventDefault();
            if (link.classList.contains("locked")) return;
            try {
                await goToWizardStep(link.dataset.step);
                document.getElementById("panel-scroll").scrollTop = 0;
            } catch (error) {
                log(normalizeErrorMessage(error.message), "error");
                notify(normalizeErrorMessage(error.message), "error");
            }
        });
    });
}

async function resumeWizardForCurrentProject() {
    if (!state.activeProject) return;
    const project = await persistWizardState({
        last_ui_mode: "wizard",
        current_step: state.activeProject.recommended_next_step || state.activeProject.wizard_state?.current_step || "describe",
    });
    if (project) {
        state.uiMode = "wizard";
        renderAll();
    }
}

async function handleWizardAction(actionId, currentStep) {
    switch (actionId) {
        case "wizard-back": {
            const sequence = visibleWizardSteps();
            const index = Math.max(0, sequence.indexOf(currentStep) - 1);
            await goToWizardStep(sequence[index] || "describe");
            return;
        }
        case "wizard-create-project":
            await createProject("wizard");
            return;
        case "wizard-save-brief":
            await saveBrief("wizard", "references");
            return;
        case "wizard-save-references":
            await saveBrief("wizard", "concepts");
            return;
        case "wizard-skip-references":
            if (!state.activeProject) return;
            await persistWizardState({
                skipped_optional_steps: ["references"],
                completed_steps: ["references"],
                current_step: "concepts",
                last_ui_mode: "wizard",
            });
            renderAll();
            return;
        case "wizard-generate-concepts":
            if (!state.activeProject) return;
            await persistConceptScaffoldPrompt();
            await persistWizardState({
                completed_steps: ["concepts"],
                current_step: "concepts",
                last_ui_mode: "wizard",
            });
            renderAll();
            return;
        case "wizard-go-review":
            await persistWizardState({ current_step: "concepts", last_ui_mode: "wizard" });
            renderAll();
            return;
        case "wizard-continue-review":
            if (!selectedConcept()) return;
            if (aiWorkflowEnabled()) {
                await persistWizardState({
                    completed_steps: ["concepts"],
                    current_step: String(state.activeProject?.brief?.backend_mode || "") === "pixellab" ? "animations" : "export",
                    last_ui_mode: "wizard",
                });
            } else {
                await persistWizardState({
                    completed_steps: ["review"],
                    current_step: "rig_layout",
                    last_ui_mode: "wizard",
                });
            }
            renderAll();
            return;
        case "wizard-generate-rig-layout":
            await api(`/api/projects/${state.activeProject.project_id}/rig-layout/generate`, { method: "POST", body: "{}" });
            await loadProject(state.activeProject.project_id, "wizard");
            await persistWizardState({ current_step: "rig_layout", last_ui_mode: "wizard" });
            renderAll();
            return;
        case "wizard-approve-rig-layout":
            await api(`/api/projects/${state.activeProject.project_id}/rig-layout/approve`, { method: "POST", body: "{}" });
            await loadProject(state.activeProject.project_id, "wizard");
            await persistWizardState({ completed_steps: ["rig_layout"], current_step: "part_manifest", last_ui_mode: "wizard" });
            renderAll();
            return;
        case "wizard-generate-part-split":
            await api(`/api/projects/${state.activeProject.project_id}/part-split/generate`, { method: "POST", body: "{}" });
            await loadProject(state.activeProject.project_id, "wizard");
            await persistWizardState({ completed_steps: ["split_build"], current_step: "split_review", last_ui_mode: "wizard" });
            renderAll();
            return;
        case "wizard-approve-part-split":
            await api(`/api/projects/${state.activeProject.project_id}/part-split/approve`, { method: "POST", body: "{}" });
            await loadProject(state.activeProject.project_id, "wizard");
            await persistWizardState({ completed_steps: ["split_build", "split_review"], current_step: "sprite_model", last_ui_mode: "wizard" });
            renderAll();
            return;
        case "wizard-build-sprite-model":
            await runJob(`/api/projects/${state.activeProject.project_id}/sprite-model/build`);
            if (state.activeProject) {
                await persistWizardState({ current_step: "sprite_model", last_ui_mode: "wizard" });
            }
            renderAll();
            return;
        case "wizard-approve-sprite-model":
            await api(`/api/projects/${state.activeProject.project_id}/sprite-model/approve`, { method: "POST", body: "{}" });
            await loadProject(state.activeProject.project_id, "wizard");
            await persistWizardState({ completed_steps: ["sprite_model"], current_step: "rig", last_ui_mode: "wizard" });
            renderAll();
            return;
        case "wizard-go-rig":
            await persistWizardState({ completed_steps: ["sprite_model"], current_step: "rig", last_ui_mode: "wizard" });
            renderAll();
            return;
        case "wizard-build-rig":
            await runJob(`/api/projects/${state.activeProject.project_id}/rig/build`);
            if (state.activeProject) {
                await persistWizardState({ current_step: "rig", last_ui_mode: "wizard" });
            }
            renderAll();
            return;
        case "wizard-approve-rig":
            await api(`/api/projects/${state.activeProject.project_id}/rig/approve`, { method: "POST", body: "{}" });
            await loadProject(state.activeProject.project_id, "wizard");
            await persistWizardState({ completed_steps: ["rig"], current_step: "clips", last_ui_mode: "wizard" });
            renderAll();
            return;
        case "wizard-go-clips":
            await persistWizardState({ completed_steps: ["rig"], current_step: "clips", last_ui_mode: "wizard" });
            renderAll();
            return;
        case "wizard-build-clips-next": {
            const action = nextClipAction();
            if (!action) return;
            await action.run();
            if (state.activeProject?.build_status?.idle_render_complete && state.activeProject?.build_status?.walk_render_complete) {
                await persistWizardState({ completed_steps: ["animations"], current_step: "export", last_ui_mode: "wizard" });
            }
            renderAll();
            return;
        }
        case "wizard-run-qa":
            if (state.activeProject?.qa_report?.status === "pass") {
                await persistWizardState({ completed_steps: ["export"], current_step: "export", last_ui_mode: "wizard" });
                renderAll();
                return;
            }
            await runJob(`/api/projects/${state.activeProject.project_id}/qa/run`);
            if (state.activeProject?.qa_report) {
                await persistWizardState({
                    completed_steps: ["export"],
                    current_step: "export",
                    last_ui_mode: "wizard",
                });
            }
            renderAll();
            return;
        case "wizard-run-export":
            await runJob(`/api/projects/${state.activeProject.project_id}/export`);
            if (state.activeProject?.last_export) {
                await persistWizardState({ completed_steps: ["export"], current_step: "export", last_ui_mode: "wizard" });
            }
            renderAll();
            return;
        default:
            return;
    }
}
