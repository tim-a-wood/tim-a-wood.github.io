async function createProject(mode = "workbench") {
    if (mode === "wizard" && !document.querySelector("#project-name").value.trim()) {
        throw new Error("Add a project name before starting the wizard.");
    }
    const payload = await collectIntakePayload({ preserveRuntimeFields: false });
    payload.last_ui_mode = mode;
    const project = await api("/api/projects", { method: "POST", body: JSON.stringify(payload) });
    log(`Created project ${project.project_id}`, "success");
    notify(`Project "${project.project_name}" is ready.`, "success", "Project created");
    resetReferenceEditor();
    await refreshProjects();
    await loadProject(project.project_id, mode);
}

async function saveBrief(mode = currentMode(), nextStep = null) {
    if (!state.activeProject) throw new Error("Select or create a project first.");
    if (!document.querySelector("#prompt-text").value.trim()) {
        throw new Error("Add a character description before continuing.");
    }
    const payload = await collectIntakePayload();
    const project = await api(`/api/projects/${state.activeProject.project_id}/brief`, {
        method: "POST",
        body: JSON.stringify(payload),
    });
    state.activeProject = project;
    resetReferenceEditor();
    log(`Updated intake for ${project.project_name}`, "success");
    notify("Saved the character description.", "success");
    await refreshProjects();
    if (mode === "wizard") {
        const synced = await persistWizardState({
            completed_steps: ["brief", "describe"],
            current_step: nextStep || "references",
            last_ui_mode: "wizard",
        });
        if (synced) state.activeProject = synced;
        state.uiMode = "wizard";
    }
    renderAll();
}

async function confirmDescribeStep() {
    if (!document.querySelector("#project-name").value.trim()) {
        throw new Error("Add a project name before continuing.");
    }
    if (!document.querySelector("#prompt-text").value.trim()) {
        throw new Error("Add a character description before continuing.");
    }
    if (!state.activeProject) {
        await createProject("wizard");
        const synced = await persistWizardState({
            completed_steps: ["brief", "describe"],
            current_step: "concepts",
            last_ui_mode: "wizard",
        });
        if (synced) state.activeProject = synced;
        renderAll();
        return;
    }
    await saveBrief("wizard", "concepts");
}

function renderDescribePrimaryAction() {
    const button = document.querySelector("#confirm-describe-step");
    if (!button) return;
    button.textContent = state.activeProject ? "Confirm & Continue" : "Create Project & Continue";
}

document.querySelector("#confirm-describe-step")?.addEventListener("click", async () => {
    try {
        await confirmDescribeStep();
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#create-project-workbench")?.addEventListener("click", async () => {
    try {
        await createProject("workbench");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#save-brief-workbench")?.addEventListener("click", async () => {
    try {
        await saveBrief("workbench");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});
