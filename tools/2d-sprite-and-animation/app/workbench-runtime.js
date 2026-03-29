function renderAll() {
    updateRoomCreationLink();
    renderStageMeta();
    renderProjectList();
    populateIntakeForm();
    renderDescribePrimaryAction();
    renderStatus();
    renderSidebarWarnings();
    renderModeShell();
    renderConceptReview();
    renderAiCharacterLockBoard();
    renderAiKeyPoseBoard();
    renderPixellabCharacterBoard();
    renderPixellabAnimationsBoard();
    renderQa();
    renderExport();
    renderReviewExportClipPreviews();
    applyModeVisibility();
    syncWorkflowModeControls();
    syncLegacyModeControls();
    renderActivity();
}

async function loadHealth() {
    state.health = await api("/api/health");
    try {
        state.health.pixellab = await api("/api/pixellab/health");
    } catch (error) {
        state.health.pixellab = { ok: false, configured: false, error: error.message || "unknown error" };
    }
    renderStageMeta();
    renderStatus();
    renderSidebarWarnings();
}

async function waitForJob(job) {
    log(`Queued ${job.job_type} as ${job.job_id}`);
    setActivity({
        state: "Queued",
        jobType: job.job_type,
        label: jobDisplayName(job.job_type),
        detail: "Waiting for the server to start work.",
        percent: job.progress_percent || 2,
    });
    while (true) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const update = await api(`/api/projects/${job.project_id}/jobs/${job.job_id}`);
        setActivity({
            state: update.status === "completed" ? "Done" : update.status === "failed" ? "Stopped" : "Working",
            jobType: update.job_type,
            label: update.progress_label || jobDisplayName(update.job_type),
            detail: update.progress_detail || "Still running…",
            percent: update.progress_percent ?? 10,
        });
        if (update.status === "completed") {
            log(`Completed ${update.job_type}`, "success");
            notify(`${jobDisplayName(update.job_type)} finished.`, "success");
            clearActivity();
            await loadProject(job.project_id, currentMode());
            return update.result;
        }
        if (update.status === "failed") {
            clearActivity();
            const message = normalizeErrorMessage(update.error || `${update.job_type} failed`);
            notify(message, "error");
            throw new Error(message);
        }
    }
}

async function runJob(path, payload = {}) {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const job = await api(path, { method: "POST", body: JSON.stringify(payload) });
    return waitForJob(job);
}

function parsePairInput(value) {
    return String(value || "")
        .split(",")
        .map((item) => Number(item.trim()))
        .filter((item) => Number.isFinite(item));
}

function spritePaletteReplacements() {
    const raw = document.querySelector("#sprite-palette-map").value.trim();
    if (!raw) return null;
    const replacements = {};
    raw.split(",").forEach((pair) => {
        const [from, to] = pair.split(":").map((item) => item.trim());
        if (from && to) replacements[from] = to;
    });
    return Object.keys(replacements).length ? replacements : null;
}

async function applySpriteOperation(operation, extra = {}) {
    if (!state.activeProject) throw new Error("Open a project first.");
    const part = selectedSpritePart();
    if (!part && operation !== "merge_parts") throw new Error("Choose a sprite-model part first.");
    state.previousSpriteModel = typeof structuredClone === "function"
        ? structuredClone(state.activeProject.sprite_model || null)
        : JSON.parse(JSON.stringify(state.activeProject.sprite_model || null));
    const payload = {
        operation,
        part_name: part?.part_name,
        ...extra,
    };
    const spriteModel = await api(`/api/projects/${state.activeProject.project_id}/sprite-model/update`, {
        method: "POST",
        body: JSON.stringify(payload),
    });
    state.activeProject.sprite_model = spriteModel;
    state.activeProject.layered_character = spriteModel;
    const preferredPart = extra.new_part_name || part?.part_name || state.selectedSpritePart;
    await loadProject(state.activeProject.project_id, currentMode());
    state.selectedSpritePart = preferredPart;
    renderLayerReview();
    log(`Applied ${operation} to ${part?.part_name || "sprite model"}`, "success");
    notify(`Applied ${operation.replace(/_/g, " ")}.`, "success");
}
