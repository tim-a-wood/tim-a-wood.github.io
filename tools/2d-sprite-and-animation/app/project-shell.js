const SAMPLE_PROJECT_CANDIDATES = [
    "canonical-sprite-model",
    "canonical-fixture-46ad415d",
    "test-40b4b333",
];

function requestedProjectIdFromUrl() {
    try {
        const params = new URLSearchParams(window.location.search || "");
        const direct = params.get("project");
        if (direct) return direct.trim();
        const hash = String(window.location.hash || "").replace(/^#/, "");
        if (!hash) return "";
        if (hash.startsWith("project=")) return hash.slice("project=".length).trim();
        return "";
    } catch (_) {
        return "";
    }
}

function syncProjectUrl(projectId) {
    try {
        const url = new URL(window.location.href);
        if (projectId) {
            url.searchParams.set("project", projectId);
        } else {
            url.searchParams.delete("project");
        }
        url.hash = "";
        window.history.replaceState({}, "", url.toString());
    } catch (_) {
        // Ignore URL sync failures so local project loading keeps working.
    }
}

async function openWorkbenchMode() {
    if (!state.activeProject) {
        state.uiMode = "wizard";
        const storedId = storage.getItem(STORAGE_KEYS.activeProjectId);
        if (storedId) {
            await loadProject(storedId, "wizard");
            return;
        }
        renderAll();
        return;
    }
    await setUiMode("wizard");
}

async function startNewSpriteWizard() {
    state.uiMode = "wizard";
    state.activeProject = null;
    state.selectedRunId = null;
    state.compareRightId = null;
    state.swapCompareView = false;
    resetReferenceEditor();
    renderAll();
    document.getElementById("panel-scroll").scrollTop = 0;
}

async function openProjectFromList(project, mode = "wizard") {
    await loadProject(project.project_id, mode);
    document.getElementById("panel-scroll").scrollTop = 0;
}

function attachProjectCard(card, project) {
    card.addEventListener("click", async (event) => {
        if (event.target.closest("button")) return;
        try {
            await openProjectFromList(project, "wizard");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    card.querySelector("[data-action='load']").addEventListener("click", async (event) => {
        event.stopPropagation();
        try {
            await openProjectFromList(project, "wizard");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    card.querySelector("[data-action='duplicate']").addEventListener("click", async (event) => {
        event.stopPropagation();
        try {
            const clone = await api(`/api/projects/${project.project_id}/duplicate`, { method: "POST", body: "{}" });
            log(`Duplicated ${project.project_name}`, "success");
            notify(`Duplicated ${project.project_name}.`, "success");
            await refreshProjects();
            await loadProject(clone.project_id, "workbench");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    card.querySelector("[data-action='backup']").addEventListener("click", async (event) => {
        event.stopPropagation();
        try {
            downloadProjectBundle(project);
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    card.querySelector("[data-action='delete']").addEventListener("click", async (event) => {
        event.stopPropagation();
        if (!confirm(`Delete "${project.project_name}"? This cannot be undone.`)) return;
        try {
            await api(`/api/projects/${project.project_id}/archive`, { method: "POST", body: "{}" });
            log(`Deleted ${project.project_name}`, "success");
            notify(`Deleted ${project.project_name}.`, "success");
            if (state.activeProject?.project_id === project.project_id) {
                state.activeProject = null;
                storage.removeItem(STORAGE_KEYS.activeProjectId);
            }
            await refreshProjects();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
}

function selectSampleProject(projects) {
    for (const candidate of SAMPLE_PROJECT_CANDIDATES) {
        const match = projects.find((project) => project.project_id === candidate);
        if (match) return match;
    }
    return projects.find((project) => String(project.project_name || "").toLowerCase() === "canonical fixture") || null;
}

function renderSampleProjectCard(project) {
    const block = document.querySelector("#sample-project-block");
    const root = document.querySelector("#sample-project-card");
    if (!block || !root) return;
    if (!project) {
        block.hidden = true;
        root.innerHTML = "";
        return;
    }
    block.hidden = false;
    const nextStep = WIZARD_META[project.wizard_state?.current_step || "describe"]?.label || "Describe";
    root.innerHTML = `
        <div class="sample-project-card">
            <span class="sample-project-kicker">Sample flow</span>
            <strong>${project.project_name}</strong>
            <div class="small-note">${stageDisplayName(project.current_stage)} · ${nextStep}</div>
            <p class="sample-project-note">Open this populated project to walk the flow, inspect the export, and test the game handoff without running generation.</p>
            <div class="project-actions">
                <button data-action="load-sample">Open Sample</button>
                <button class="secondary" data-action="backup-sample">Export Project</button>
            </div>
        </div>
    `;
    root.querySelector("[data-action='load-sample']")?.addEventListener("click", async () => {
        try {
            await openProjectFromList(project, "wizard");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    root.querySelector("[data-action='backup-sample']")?.addEventListener("click", (event) => {
        event.stopPropagation();
        try {
            downloadProjectBundle(project);
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
}

function renderProjectList() {
    const root = document.querySelector("#project-list");
    root.innerHTML = "";
    const sampleProject = selectSampleProject(state.projects);
    renderSampleProjectCard(sampleProject);
    const regularProjects = sampleProject
        ? state.projects.filter((project) => project.project_id !== sampleProject.project_id)
        : state.projects.slice();
    regularProjects.sort((a, b) => (a.archived_at ? 1 : 0) - (b.archived_at ? 1 : 0));
    if (!regularProjects.length) {
        root.innerHTML = `<div class="empty">${sampleProject ? "No other projects yet." : "No projects yet."}</div>`;
        return;
    }
    regularProjects.forEach((project) => {
        const warningCount = Number(project.project_health_warning_count || 0);
        const missingCount = Number(project.project_health_missing_file_count || 0);
        const card = document.createElement("div");
        card.className = `project-card ${state.activeProject?.project_id === project.project_id ? "active" : ""}`;
        const nextStep = WIZARD_META[project.wizard_state?.current_step || "describe"]?.label || "Describe";
        const archivedNote = project.archived_at
            ? `<div class="small-note">Archived — opened from full list (Delete in this UI only archives).</div>`
            : "";
        card.innerHTML = `
            <strong>${project.project_name}</strong>
            <small>${stageDisplayName(project.current_stage)} · ${nextStep}</small>
            ${archivedNote}
            <div class="small-note">Last modified ${formatDate(project.updated_at)}</div>
            ${warningCount || missingCount ? `<div class="small-note" style="margin-top:8px;">Needs attention: ${warningCount} warning${warningCount === 1 ? "" : "s"}${missingCount ? ` · ${missingCount} missing file${missingCount === 1 ? "" : "s"}` : ""}</div>` : ""}
            <div class="project-actions">
                <button class="secondary" data-action="load">Load Project</button>
                <button class="secondary" data-action="backup">Export Project</button>
                <button class="secondary" data-action="duplicate">Duplicate</button>
                <button class="danger" data-action="delete">Delete</button>
            </div>
        `;
        attachProjectCard(card, project);
        root.appendChild(card);
    });
}

async function refreshProjects() {
    const data = await api(`/api/projects?include_archived=1`);
    state.projects = data.projects;
    renderProjectList();
}

async function loadProject(projectId, mode = "wizard") {
    if (state.activeProject?.project_id !== projectId) {
        state.previousSpriteModel = null;
        state.spriteRecoveryVariants = {};
        state.selectedRevisionId = null;
        state.selectedClipFrame = 0;
        state.selectedClipPart = null;
        state.selectedManualClipId = null;
        state.selectedManualClipFrame = 0;
        state.selectedManualPatchSourcePart = null;
        state.selectedManualPatchOccluderPart = null;
        state.manualPatchCandidates = [];
        state.manualPatchBusy = false;
        state.manualPoseDraft = null;
        state.manualPoseDraftKey = null;
        state.manualPoseModalOpen = false;
        state.lastConceptScaffold = null;
        state.lastIterationScaffold = null;
        state.conceptUiSelectedId = null;
        state.lastIteratedConceptId = null;
        const sc = document.querySelector("#concept-scaffold-prompt");
        const it = document.querySelector("#concept-iteration-prompt");
        if (sc) sc.value = "";
        if (it) it.value = "";
    }
    const project = await api(`/api/projects/${projectId}`);
    state.activeProject = project;
    state.uiMode = mode;
    storage.setItem(STORAGE_KEYS.activeProjectId, projectId);
    syncProjectUrl(projectId);
    if (!state.lastIteratedConceptId) {
        const iterateConcepts = (project.concepts || [])
            .filter((concept) => concept.run_kind === "pixellab_iterate")
            .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
        if (iterateConcepts.length) {
            state.lastIteratedConceptId = iterateConcepts[0].concept_id;
            if (!state.conceptUiSelectedId) {
                const parentId = iterateConcepts[0]?.lineage?.parent_concept_id;
                if (parentId) state.conceptUiSelectedId = parentId;
            }
        }
    }
    state.compareRightId = null;
    state.swapCompareView = false;
    state.selectedSpritePart = project.sprite_model?.parts?.[0]?.part_name || null;
    if (!clipEditorParts(project).some((part) => part.part_name === state.selectedClipPart)) {
        state.selectedClipPart = clipEditorParts(project)[0]?.part_name || null;
    }
    state.selectedRevisionId = state.selectedRevisionId || project.sprite_model_history?.current_revision_id || project.sprite_model_history?.revisions?.slice(-1)[0]?.revision_id || null;
    if (!project.animation_clips?.[state.selectedClip]) {
        state.selectedClip = project.animation_clips?.idle ? "idle" : project.animation_clips?.walk ? "walk" : "idle";
    }
    clampSelectedClipFrame();
    if (!manualClipList(project).some((clip) => clip.clip_id === state.selectedManualClipId)) {
        state.selectedManualClipId = manualClipList(project)[0]?.clip_id || null;
    }
    clampSelectedManualClipFrame(project);
    if (mode !== project.last_ui_mode) {
        const synced = await persistWizardState({
            last_ui_mode: mode,
            current_step: mode === "wizard"
                ? (project.wizard_state?.current_step || project.recommended_next_step || "describe")
                : project.wizard_state?.current_step,
        });
        if (synced) state.activeProject = synced;
    }
    renderAll();
}

async function restoreProjectSelection() {
    if (!state.projects.length) {
        state.activeProject = null;
        syncProjectUrl("");
        renderAll();
        return;
    }
    const requestedId = requestedProjectIdFromUrl();
    const requestedMatch = requestedId
        ? state.projects.find((project) => project.project_id === requestedId)
        : null;
    const storedId = storage.getItem(STORAGE_KEYS.activeProjectId);
    const match = requestedMatch
        || state.projects.find((project) => project.project_id === storedId)
        || state.projects[0];
    await loadProject(match.project_id, "workbench");
}

async function readFileAsDataUrl(file) {
    return await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
        reader.readAsDataURL(file);
    });
}

async function importProjectBundleFile(file) {
    if (!file) throw new Error("Choose a project backup zip first.");
    const dataUrl = await readFileAsDataUrl(file);
    setActivity({
        state: "Working",
        jobType: "projects.import_bundle",
        label: "Importing project backup",
        detail: "Restoring the project bundle into the workbench.",
        percent: 35,
    });
    try {
        const project = await api(`/api/projects/import-bundle`, {
            method: "POST",
            body: JSON.stringify({
                name: file.name,
                data_url: dataUrl,
            }),
        });
        await refreshProjects();
        await loadProject(project.project_id, "wizard");
        log(`Imported backup as ${project.project_name}`, "success");
        notify(`Imported project backup as ${project.project_name}.`, "success");
    } finally {
        clearActivity();
    }
}

["#refresh-projects-workbench"].forEach((selector) => {
    document.querySelector(selector)?.addEventListener("click", async () => {
        try {
            await refreshProjects();
            if (state.activeProject) {
                await loadProject(state.activeProject.project_id, currentMode());
            }
            notify("Project list refreshed.", "info");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
});

document.querySelector("#launch-wizard")?.addEventListener("click", async () => {
    try {
        if (state.activeProject) {
            document.getElementById("panel-scroll").scrollTop = 0;
        } else {
            await startNewSpriteWizard();
        }
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#open-workbench")?.addEventListener("click", async () => {
    try {
        document.getElementById("panel-scroll").scrollTop = 0;
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

["#sidebar-new-project", "#mobile-new-project"].forEach((selector) => {
    document.querySelector(selector)?.addEventListener("click", async () => {
        try {
            await startNewSpriteWizard();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
});

document.querySelector("#sidebar-import-project")?.addEventListener("click", () => {
    document.querySelector("#project-bundle-import-file")?.click();
});

document.querySelector("#project-bundle-import-file")?.addEventListener("change", async (event) => {
    const file = event.target?.files?.[0];
    try {
        await importProjectBundleFile(file);
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    } finally {
        if (event.target) event.target.value = "";
    }
});

document.querySelector("#mode-workbench")?.addEventListener("click", async () => {
    try {
        await openWorkbenchMode();
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#mode-wizard")?.addEventListener("click", async () => {
    try {
        if (state.activeProject) {
            await resumeWizardForCurrentProject();
        } else {
            await startNewSpriteWizard();
        }
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

async function boot() {
    resetReferenceEditor();
    initSidebarToggle();
    renderAll();
    await loadHealth();
    await refreshProjects();
    await restoreProjectSelection();
}
