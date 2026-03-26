async function reviewConcept(conceptId, action, value) {
    if (!state.activeProject) return;
    const isPixellab = String(state.activeProject?.brief?.backend_mode || "") === "pixellab";
    const project = await api(`/api/projects/${state.activeProject.project_id}/concepts/${conceptId}/${action}`, {
        method: "POST",
        body: JSON.stringify({ value }),
    });
    state.activeProject = project;
    log(`${action} updated for ${conceptId}`, "success");
    if (action === "approve") notify(isPixellab ? `${conceptId} is now the chosen look and locked animation source.` : `${conceptId} is now the chosen look.`, "success");
    if (action === "favorite") notify(value ? `${conceptId} saved to the shortlist.` : `${conceptId} removed from the shortlist.`, "info");
    if (action === "reject") notify(value ? `${conceptId} hidden from consideration.` : `${conceptId} restored.`, "info");
    await refreshProjects();
    if (currentMode() === "wizard" && action === "approve" && value) {
        const synced = await persistWizardState({
            completed_steps: ["review"],
            current_step: aiWorkflowEnabled(project)
                ? (String(project?.brief?.backend_mode || "") === "pixellab" ? "animations" : "export")
                : "rig_layout",
            last_ui_mode: "wizard",
        });
        if (synced) state.activeProject = synced;
    }
    renderAll();
}

async function validateConceptAttempt(conceptId, validationStatus, feedback = "") {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const project = await api(`/api/projects/${state.activeProject.project_id}/concepts/${conceptId}/validate`, {
        method: "POST",
        body: JSON.stringify({
            validation_status: validationStatus,
            feedback: feedback.trim(),
        }),
    });
    state.activeProject = project;
    await refreshProjects();
    log(`Marked ${conceptId} as ${validationStatus}`, "success");
    notify(`${conceptId} marked ${validationStatus}.`, validationStatus === "invalid" ? "info" : "success");
    renderAll();
}

async function revalidateConceptAttempt(conceptId) {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const project = await api(`/api/projects/${state.activeProject.project_id}/concepts/${conceptId}/revalidate`, {
        method: "POST",
        body: "{}",
    });
    state.activeProject = project;
    await refreshProjects();
    log(`Retried Gemini validation for ${conceptId}`, "success");
    notify(`Retried Gemini validation for ${conceptId}.`, "info");
    renderAll();
}

async function generateImprovedPrompt(conceptId, feedback = "") {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const result = await api(`/api/projects/${state.activeProject.project_id}/concepts/${conceptId}/improve-prompt`, {
        method: "POST",
        body: JSON.stringify({ feedback: feedback.trim() }),
    });
    await loadProject(state.activeProject.project_id, currentMode());
    log(`Generated improved Gemini prompt from ${conceptId}`, "success");
    notify(`Generated Gemini prompt v${result.prompt_version}.`, "success");
}

async function persistConceptScaffoldPrompt(options = {}) {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const { notifyUser = true, reloadProject = true } = options;
    const result = await api(`/api/projects/${state.activeProject.project_id}/concepts/persist-scaffold-prompt`, {
        method: "POST",
        body: "{}",
    });
    state.lastConceptScaffold = result;
    const ta = document.querySelector("#concept-scaffold-prompt");
    if (ta) ta.value = result.display_prompt || "";
    if (notifyUser) {
        notify("Prompt scaffold saved.", "success");
    }
    if (reloadProject) {
        await loadProject(state.activeProject.project_id, currentMode());
    }
}

async function copyConceptScaffoldPrompt() {
    const text = (state.lastConceptScaffold && state.lastConceptScaffold.display_prompt)
        || document.querySelector("#concept-scaffold-prompt")?.value
        || "";
    if (!String(text).trim()) throw new Error('Use "Build Prompt Only" or create a concept first.');
    await navigator.clipboard.writeText(text);
    notify("Copied scaffold prompt.", "success");
}

async function generateConceptViaPixellab(sourceMode = "text") {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    if (!state.lastConceptScaffold?.pixellab_params) throw new Error('Build the prompt first, or use the main Create Concept action.');
    if (!paidActionAllowed(sourceMode === "custom_init" ? "Generate concept from custom init image" : "Generate concept via Pixel Lab")) return;
    const pixellabParams = { ...state.lastConceptScaffold.pixellab_params };
    const payload = {
        mode: "pixflux",
        pixellab_params: pixellabParams,
    };
    if (sourceMode === "custom_init") {
        const file = document.querySelector("#concept-init-upload-file")?.files?.[0];
        if (!file) throw new Error("Choose an init image upload first.");
        payload.init_image_name = file.name;
        payload.init_image_data_url = await readFileAsDataUrl(file);
        payload.init_image_strength = 820;
    }
    setActivity({
        state: "Working",
        jobType: "concepts.generate_pixellab",
        label: sourceMode === "custom_init" ? "Post-processing uploaded init image" : "Generating concept via Pixel Lab",
        detail: sourceMode === "custom_init"
            ? "Using the uploaded image as Pixel Lab init input."
            : "Calling Pixel Lab to generate a fresh 128x128 concept.",
        percent: 25,
    });
    try {
        const concept = await api(`/api/projects/${state.activeProject.project_id}/concepts/generate-pixellab`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
        const initInput = document.querySelector("#concept-init-upload-file");
        if (initInput) initInput.value = "";
        state.lastIteratedConceptId = null;
        await loadProject(state.activeProject.project_id, currentMode());
        state.conceptUiSelectedId = concept.concept_id;
        log(`Pixel Lab concept ${concept.concept_id}`, "success");
        notify(
            sourceMode === "custom_init"
                ? `Created ${concept.concept_id} from the uploaded init image.`
                : `Created ${concept.concept_id} via Pixel Lab.`,
            "success"
        );
        renderAll();
    } finally {
        clearActivity();
    }
}

async function createConceptFromSelectedSource() {
    const mode = state.conceptSourceMode || "text";
    await persistConceptScaffoldPrompt({ notifyUser: false, reloadProject: false });
    await generateConceptViaPixellab(mode);
}

async function buildConceptIterationPrompt() {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const cid = state.conceptUiSelectedId;
    if (!cid) throw new Error("Select a concept in the grid first.");
    const element = document.querySelector("#concept-iterate-element")?.value;
    const changeText = document.querySelector("#concept-iterate-change")?.value?.trim();
    if (!changeText) throw new Error("Describe what to change.");
    const result = await api(`/api/projects/${state.activeProject.project_id}/concepts/build-iteration-prompt`, {
        method: "POST",
        body: JSON.stringify({ concept_id: cid, element, change_text: changeText }),
    });
    state.lastIterationScaffold = result;
    const ta = document.querySelector("#concept-iteration-prompt");
    if (ta) ta.value = result.display_prompt || "";
    notify("Iteration prompt ready.", "success");
}

async function generateConceptIterationViaGemini() {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const cid = state.conceptUiSelectedId;
    if (!cid) throw new Error("Select a source concept first.");
    const element = document.querySelector("#concept-iterate-element")?.value;
    const changeText = document.querySelector("#concept-iterate-change")?.value?.trim();
    if (!changeText) throw new Error("Describe what to change.");
    if (!paidActionAllowed("Run Gemini concept iteration")) return;
    setActivity({
        state: "Working",
        jobType: "concepts.iterate_gemini",
        label: "Gemini image iteration",
        detail: "Sending sprite to Gemini for editing…",
        percent: 25,
    });
    try {
        const concept = await api(`/api/projects/${state.activeProject.project_id}/concepts/iterate-gemini`, {
            method: "POST",
            body: JSON.stringify({ concept_id: cid, element, change_text: changeText }),
        });
        state.lastIteratedConceptId = concept.concept_id;
        await loadProject(state.activeProject.project_id, currentMode());
        log(`Gemini iteration ${concept.concept_id}`, "success");
        notify(`Saved iteration as ${concept.concept_id}.`, "success");
        renderAll();
    } finally {
        clearActivity();
    }
}

async function generateConceptIterationViaPixellab() {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    if (!state.lastIterationScaffold?.pixellab_params) throw new Error('Use "Build Iteration Prompt" first.');
    const cid = state.conceptUiSelectedId;
    if (!cid) throw new Error("Select a source concept.");
    if (!paidActionAllowed("Run Pixel Lab concept iteration")) return;
    setActivity({
        state: "Working",
        jobType: "concepts.iterate_pixellab",
        label: "Pixel Lab inpaint iteration",
        detail: "Running inpaint or debug placeholders.",
        percent: 25,
    });
    try {
        const strength = parseInt(document.querySelector("#concept-iterate-strength")?.value || "750", 10);
        const params = { ...state.lastIterationScaffold.pixellab_params, init_image_strength: strength };
        const concept = await api(`/api/projects/${state.activeProject.project_id}/concepts/iterate-pixellab`, {
            method: "POST",
            body: JSON.stringify({ concept_id: cid, pixellab_params: params }),
        });
        state.lastIteratedConceptId = concept.concept_id;
        await loadProject(state.activeProject.project_id, currentMode());
        log(`Pixel Lab iteration ${concept.concept_id}`, "success");
        notify(`Saved iteration as ${concept.concept_id}.`, "success");
        renderAll();
    } finally {
        clearActivity();
    }
}

async function importConceptImage() {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const anchor = state.lastConceptScaffold?.anchor_concept_id;
    if (!anchor) throw new Error('Use "Build Prompt Only" first so the server can create an import anchor.');
    const file = document.querySelector("#concept-import-file")?.files?.[0];
    const localPath = document.querySelector("#concept-import-path")?.value?.trim() || "";
    if (!file && !localPath) throw new Error("Choose an upload or enter a local image path.");
    let payload = { source_prompt_id: anchor };
    if (file) {
        const dataUrl = await readFileAsDataUrl(file);
        payload = { ...payload, name: file.name, data_url: dataUrl };
    } else {
        payload = { ...payload, local_path: localPath };
    }
    setActivity({
        state: "Working",
        jobType: "concepts.import",
        label: "Importing concept image",
        detail: "Uploading and normalizing; server may run validation.",
        percent: 35,
    });
    try {
        await api(`/api/projects/${state.activeProject.project_id}/concepts/import`, {
            method: "POST",
            body: JSON.stringify(payload),
        });
    } finally {
        clearActivity();
    }
    const fileInput = document.querySelector("#concept-import-file");
    const pathInput = document.querySelector("#concept-import-path");
    if (fileInput) fileInput.value = "";
    if (pathInput) pathInput.value = "";
    await loadProject(state.activeProject.project_id, currentMode());
    await refreshProjects();
    log("Imported concept image", "success");
    notify("Imported concept image.", "success");
    renderAll();
}

async function importIteratedConceptFile() {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const parentId = state.conceptUiSelectedId;
    if (!parentId) throw new Error("Select a concept to attach this import to.");
    const file = document.querySelector("#concept-iterate-import-file")?.files?.[0];
    if (!file) throw new Error("Choose an image file.");
    const dataUrl = await readFileAsDataUrl(file);
    setActivity({
        state: "Working",
        jobType: "concepts.import",
        label: "Importing edited concept",
        detail: "Uploading iteration image.",
        percent: 35,
    });
    try {
        await api(`/api/projects/${state.activeProject.project_id}/concepts/import`, {
            method: "POST",
            body: JSON.stringify({
                source_prompt_id: parentId,
                name: file.name,
                data_url: dataUrl,
            }),
        });
    } finally {
        clearActivity();
    }
    const iterInput = document.querySelector("#concept-iterate-import-file");
    if (iterInput) iterInput.value = "";
    await loadProject(state.activeProject.project_id, currentMode());
    await refreshProjects();
    notify("Imported edited image as a new concept.", "success");
    renderAll();
}

function focusLatestIteration() {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const concept = state.lastIteratedConceptId ? conceptById(state.lastIteratedConceptId) : null;
    if (!concept) throw new Error("Generate an iteration first.");
    state.conceptUiSelectedId = concept.concept_id;
    renderAll();
    notify(`Selected saved iteration ${concept.concept_id}.`, "success");
}

function downloadLatestIteration() {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    const concept = state.lastIteratedConceptId ? conceptById(state.lastIteratedConceptId) : null;
    const path = conceptDisplayImagePath(concept);
    if (!concept || !path) throw new Error("Generate an iteration first.");
    const link = document.createElement("a");
    link.href = `${projectAsset(state.activeProject, path)}?v=${state.activeProject.updated_at}`;
    link.download = `${concept.concept_id}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    notify(`Downloading ${concept.concept_id}.png`, "success");
}

async function deleteConceptById(conceptId) {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    await api(`/api/projects/${state.activeProject.project_id}/concepts/${encodeURIComponent(conceptId)}/delete`, {
        method: "POST",
        body: "{}",
    });
    if (state.lastConceptScaffold?.anchor_concept_id === conceptId) {
        state.lastConceptScaffold = null;
        const sc = document.querySelector("#concept-scaffold-prompt");
        if (sc) sc.value = "";
    }
    if (state.conceptUiSelectedId === conceptId) state.conceptUiSelectedId = null;
    if (state.lastIteratedConceptId === conceptId) state.lastIteratedConceptId = null;
    await loadProject(state.activeProject.project_id, currentMode());
    await refreshProjects();
    notify("Concept deleted.", "success");
    renderAll();
}

let conceptWorkbenchControlsWired = false;

function wireConceptWorkbenchControlsOnce() {
    if (conceptWorkbenchControlsWired) return;
    conceptWorkbenchControlsWired = true;
    document.querySelectorAll('input[name="concept-source-mode"]').forEach((radio) => {
        radio.addEventListener("change", () => {
            if (radio.checked) {
                state.conceptSourceMode = radio.value;
                syncConceptPanelMode();
            }
        });
    });
    const bind = (selector, fn) => {
        const el = document.querySelector(selector);
        if (el) el.addEventListener("click", fn);
    };
    bind("#build-concept-prompt", async () => {
        try {
            await persistConceptScaffoldPrompt();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    bind("#generate-concept-primary", async () => {
        try {
            await createConceptFromSelectedSource();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    bind("#copy-scaffold-prompt", async () => {
        try {
            await copyConceptScaffoldPrompt();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    bind("#build-iteration-prompt", async () => {
        try {
            await buildConceptIterationPrompt();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    document.querySelector("#concept-iterate-strength")?.addEventListener("input", (e) => {
        document.querySelector("#iterate-strength-value").textContent = e.target.value;
    });
    bind("#generate-concept-iterate-gemini", async () => {
        try {
            await generateConceptIterationViaGemini();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    bind("#generate-concept-iterate-pixellab", async () => {
        try {
            await generateConceptIterationViaPixellab();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    bind("#import-iterated-concept-file", async () => {
        try {
            await importIteratedConceptFile();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    bind("#select-latest-iteration", async () => {
        try {
            focusLatestIteration();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    bind("#download-latest-iteration", async () => {
        try {
            downloadLatestIteration();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
}

function syncConceptPanelMode() {
    const mode = state.conceptSourceMode || "text";
    document.querySelectorAll('input[name="concept-source-mode"]').forEach((r) => {
        r.checked = r.value === mode;
    });
    document.querySelectorAll(".concept-init-only").forEach((n) => {
        n.hidden = mode !== "custom_init";
    });
    const primary = document.querySelector("#generate-concept-primary");
    const summary = document.querySelector("#concept-source-summary");
    if (primary) {
        primary.textContent = mode === "custom_init"
            ? "Post-process Upload to 128x128"
            : "Generate 128x128 from Brief";
    }
    if (summary) {
        summary.innerHTML = mode === "custom_init"
            ? "Use an uploaded image as the starting point, then normalize it into a clean <code>128x128</code> concept."
            : "Generate a fresh <code>128x128</code> concept from your saved brief. The workbench will rebuild the prompt automatically before it runs.";
    }
}

document.querySelector("#import-concept-image")?.addEventListener("click", async () => {
    try {
        await importConceptImage();
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});
