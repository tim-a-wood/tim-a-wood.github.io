function initSidebarToggle() {
    const app = document.querySelector(".app-shell");
    const btn = document.querySelector(".rail-toggle");
    if (!app || !btn) return;
    if (localStorage.getItem(SIDEBAR_KEY) === "1") app.classList.add("sidebar-collapsed");
    const sync = () => {
        const collapsed = app.classList.contains("sidebar-collapsed");
        btn.setAttribute("aria-label", collapsed ? "Expand project panel" : "Collapse project panel");
        btn.textContent = collapsed ? "›" : "‹";
    };
    sync();
    btn.addEventListener("click", () => {
        app.classList.toggle("sidebar-collapsed");
        localStorage.setItem(SIDEBAR_KEY, app.classList.contains("sidebar-collapsed") ? "1" : "0");
        sync();
    });
}

function addReferenceRow(data = {}) {
    const root = document.querySelector("#reference-editor");
    const row = document.createElement("div");
    row.className = "reference-row";
    row.innerHTML = `
        <label>
            <span class="field-label-inline">Role</span>
            <select class="ref-role">
                <option value="identity">identity</option>
                <option value="costume">costume</option>
                <option value="style">style</option>
                <option value="prop">prop</option>
            </select>
        </label>
        <label>
            <span class="field-label-inline">Weight</span>
            <input class="ref-weight" type="number" min="0.1" max="2.0" step="0.05" value="${data.weight || 1}">
        </label>
        <label>
            <span class="field-label-inline">Local Path</span>
            <input class="ref-path" placeholder="/absolute/path/to/reference.png" value="${data.path || ""}">
        </label>
        <label>
            <span class="field-label-inline">Upload File</span>
            <input class="ref-file" type="file" accept="image/*">
        </label>
        <div class="inline-actions">
            <button class="danger ref-remove" type="button">Remove</button>
        </div>
    `;
    row.querySelector(".ref-role").value = data.role || "identity";
    row.querySelector(".ref-remove").addEventListener("click", () => row.remove());
    root.appendChild(row);
}

function resetReferenceEditor() {
    const root = document.querySelector("#reference-editor");
    root.innerHTML = "";
    addReferenceRow();
}

function renderAttachedReferences() {
    const root = document.querySelector("#attached-references");
    root.innerHTML = "";
    const references = state.activeProject?.brief?.references || [];
    if (!references.length) {
        root.innerHTML = `<div class="empty">No stored references yet. Add them when you need help with face, outfit, prop, or overall style direction.</div>`;
        return;
    }
    references.forEach((reference) => {
        const item = document.createElement("div");
        item.className = "reference-chip";
        const imagePath = reference.local_path ? projectAsset(state.activeProject, reference.local_path) : "";
        item.innerHTML = `
            ${imagePath ? `<img src="${imagePath}?v=${state.activeProject.updated_at}" alt="${reference.role} reference">` : `<div class="reference-thumb-empty">No preview</div>`}
            <div class="detail-grid">
                <div class="meta-line">
                    <span class="pill">${reference.role}</span>
                    <span class="pill">weight ${reference.weight}</span>
                    ${reference.usable_for_concepts === false ? `<span class="pill fail">ignored for concepts</span>` : ""}
                </div>
                <div class="small-note">${reference.local_path || reference.source_value || "legacy reference"}</div>
                ${reference.reference_warning ? `<div class="warning-box"><p>${reference.reference_warning}</p></div>` : ""}
            </div>
        `;
        root.appendChild(item);
    });
}

async function collectReferencePayload() {
    const rows = Array.from(document.querySelectorAll(".reference-row"));
    const references = [];
    for (const row of rows) {
        const role = row.querySelector(".ref-role").value;
        const weight = Number(row.querySelector(".ref-weight").value || 1);
        const path = row.querySelector(".ref-path").value.trim();
        const file = row.querySelector(".ref-file").files[0];
        if (!path && !file) continue;
        if (file) {
            const dataUrl = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
                reader.readAsDataURL(file);
            });
            references.push({
                role,
                weight,
                name: file.name,
                data_url: dataUrl,
            });
        } else {
            references.push({ role, weight, path });
        }
    }
    return references;
}

async function collectIntakePayload(options = {}) {
    const preserveRuntimeFields = options.preserveRuntimeFields !== false;
    const payload = {
        project_name: document.querySelector("#project-name").value.trim(),
        prompt_text: document.querySelector("#prompt-text").value.trim(),
        role_archetype: document.querySelector("#role-archetype").value.trim(),
        silhouette_intent: document.querySelector("#silhouette-intent").value.trim(),
        outfit_materials: document.querySelector("#outfit-materials").value.trim(),
        prop: document.querySelector("#prop").value.trim(),
        palette_mood: document.querySelector("#palette-mood").value.trim(),
        shape_language: document.querySelector("#shape-language").value.trim(),
        mood_tone: document.querySelector("#mood-tone").value.trim(),
        side_view_constraints: document.querySelector("#side-view-constraints").value.trim(),
        negative_prompt: document.querySelector("#negative-prompt").value.trim(),
        outline_style: document.querySelector("#pixellab-outline-style").value,
        shading_style: document.querySelector("#pixellab-shading-style").value,
        detail_level: document.querySelector("#pixellab-detail-level").value,
        canvas_size: Number(document.querySelector("#pixellab-canvas-size").value),
        character_template: document.querySelector("#pixellab-character-template").value,
        references: await collectReferencePayload(),
    };
    // Phase 7.1: Pixel Lab UI always uses pixellab backend.
    // ComfyUI checkpoint is preserved from stored brief for projects that still reference it.
    payload.backend_mode = "pixellab";
    if (preserveRuntimeFields && state.activeProject?.brief?.comfyui_checkpoint) {
        payload.comfyui_checkpoint = state.activeProject.brief.comfyui_checkpoint;
    }
    return payload;
}

/** Legacy projects may still have brief.backend_mode comfyui; Pixel Lab Character/Animations need pixellab. */
async function switchProjectBackendToPixellab() {
    const pid = state.activeProject?.project_id;
    if (!pid) throw new Error("No active project.");
    const project = await api(`/api/projects/${pid}/brief`, {
        method: "POST",
        body: JSON.stringify({ backend_mode: "pixellab" }),
    });
    state.activeProject = project;
    await refreshProjects();
    notify("Switched this project to Pixel Lab (brief backend_mode=pixellab).", "success");
    renderAll();
}

function pixellabBackendModeMismatchBox(currentMode) {
    const m = escapeHtml(String(currentMode || "unset"));
    return `
        <div class="warning-box">
            <p><strong>These steps need Pixel Lab.</strong> This project&apos;s brief still has <code>backend_mode</code> = <code>${m}</code> (older projects default to ComfyUI).</p>
            <p class="small-note">Or open <strong>Describe Your Character</strong> and click save — the form always saves as Pixel Lab.</p>
            <div class="actions" style="margin-top:10px;">
                <button type="button" class="pixellab-switch-backend-btn">Switch project to Pixel Lab</button>
            </div>
        </div>`;
}

function wirePixellabSwitchBackendButton(root) {
    root.querySelector(".pixellab-switch-backend-btn")?.addEventListener("click", async () => {
        try {
            await switchProjectBackendToPixellab();
        } catch (e) {
            notify(normalizeErrorMessage(e.message), "error");
        }
    });
}

function populateIntakeForm() {
    const project = state.activeProject;
    const brief = project?.brief;
    document.querySelector("#project-name").value = project?.project_name || "";
    document.querySelector("#prompt-text").value = project?.prompt_text || "";
    document.querySelector("#role-archetype").value = brief?.role_archetype || "";
    document.querySelector("#silhouette-intent").value = brief?.silhouette_intent || "";
    document.querySelector("#outfit-materials").value = brief?.outfit_materials || "";
    document.querySelector("#prop").value = brief?.prop || "";
    document.querySelector("#palette-mood").value = brief?.palette_mood || "";
    document.querySelector("#shape-language").value = brief?.shape_language || "";
    document.querySelector("#mood-tone").value = brief?.mood_tone || "";
    document.querySelector("#side-view-constraints").value = brief?.side_view_constraints || "";
    document.querySelector("#negative-prompt").value = brief?.negative_prompt || "";
    const outlineSel = document.querySelector("#pixellab-outline-style");
    const shadingSel = document.querySelector("#pixellab-shading-style");
    const detailSel = document.querySelector("#pixellab-detail-level");
    const canvasSel = document.querySelector("#pixellab-canvas-size");
    const templateSel = document.querySelector("#pixellab-character-template");
    if (outlineSel) outlineSel.value = brief?.outline_style || "single color black outline";
    if (shadingSel) shadingSel.value = brief?.shading_style || "medium shading";
    if (detailSel) detailSel.value = brief?.detail_level || "medium detail";
    if (canvasSel) canvasSel.value = String(brief?.canvas_size != null ? brief.canvas_size : 64);
    if (templateSel) templateSel.value = brief?.character_template || "mannequin";
    renderAttachedReferences();
}

document.querySelector("#add-reference-row")?.addEventListener("click", () => addReferenceRow());
