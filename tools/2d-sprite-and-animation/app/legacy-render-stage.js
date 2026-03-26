function renderRigLayout() {
    const previewRoot = document.querySelector("#rig-layout-preview");
    const summaryRoot = document.querySelector("#rig-layout-summary");
    const metricsRoot = document.querySelector("#rig-layout-metrics");
    const partsRoot = document.querySelector("#rig-layout-parts");
    const historyRoot = document.querySelector("#rig-layout-history");
    const jsonRoot = document.querySelector("#rig-layout-json");
    const approveButton = document.querySelector("#approve-rig-layout");
    const promptRoot = document.querySelector("#rig-layout-handoff-prompt");
    if (!previewRoot || !summaryRoot || !metricsRoot || !partsRoot || !historyRoot || !jsonRoot || !approveButton) return;
    const project = state.activeProject;
    const layout = activeRigLayout(project);
    previewRoot.innerHTML = "";
    summaryRoot.innerHTML = "";
    metricsRoot.innerHTML = "";
    partsRoot.innerHTML = "";
    historyRoot.innerHTML = "";
    jsonRoot.value = "";
    if (promptRoot) promptRoot.textContent = project?.rig_layout_handoff_prompt || "No Codex handoff prompt available yet.";
    if (!project || !layout) {
        previewRoot.innerHTML = `<div class="empty">Accept a concept to generate the rig layout.</div>`;
        summaryRoot.innerHTML = `<div class="empty">No rig layout data yet.</div>`;
        metricsRoot.innerHTML = `<div class="empty">No summary yet.</div>`;
        partsRoot.innerHTML = `<div class="empty">No parts yet.</div>`;
        approveButton.disabled = true;
        return;
    }
    const validation = layout.validation || { status: "warning", errors: [] };
    const codexCheck = layout.codex_check || null;
    document.querySelector("#rig-layout-warning").textContent = layout.approved
        ? "Rig layout approved. Sprite extraction and rigging now consume the internal layout deterministically."
        : codexCheck && codexCheck.valid === false
            ? `Codex rejected this image: ${codexCheck.summary || "No summary provided."}`
            : validation.status === "fail"
                ? "The internal layout is still invalid. Re-run the Codex check or reset the suggested layout."
                : "Paste a Codex response for this image, then approve the resulting internal layout when the summary and part breakdown look right.";
    approveButton.disabled = validation.status === "fail";
    previewRoot.innerHTML = layoutOverlayMarkup(project, layout);
    [
        ["Profile", layout.rig_profile || "unknown"],
        ["Approved", layout.approved ? "yes" : "no"],
        ["Codex check", codexCheck ? (codexCheck.valid ? "valid" : "invalid") : "not applied"],
        ["Parts", layout.parts?.length || 0],
        ["Joint-driving", layout.joint_driving_parts?.length || 0],
        ["Overlays", layout.overlay_parts?.length || 0],
        ["Validation", validation.status || "unknown"],
    ].forEach(([label, value]) => {
        const metric = document.createElement("div");
        metric.className = "rig-metric";
        metric.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
        metricsRoot.appendChild(metric);
    });
    if (validation.errors?.length) {
        const box = document.createElement("div");
        box.className = "warning-box";
        box.innerHTML = `<p><strong>Validation Errors</strong></p><div class="history-list" style="margin-top: 8px;">${validation.errors.map((item) => `<div class="history-item">${item}</div>`).join("")}</div>`;
        summaryRoot.appendChild(box);
    }
    if (codexCheck?.summary) {
        const box = document.createElement("div");
        box.className = codexCheck.valid ? "success-box" : "warning-box";
        box.innerHTML = `<p><strong>Codex Summary</strong></p><div class="history-item">${codexCheck.summary}</div>`;
        summaryRoot.appendChild(box);
    }
    if (!validation.errors?.length && !codexCheck?.summary) {
        summaryRoot.innerHTML = `<div class="empty">No validation notes yet. Apply a Codex response to populate this area.</div>`;
    }
    (layout.parts || []).forEach((part) => {
        const row = document.createElement("div");
        row.className = "rig-layout-part";
        row.innerHTML = `
            <div class="meta-line">
                <span class="pill">${part.part_name}</span>
                <span class="pill">${part.parent_joint}</span>
                <span class="pill">overlay_only=${part.overlay_only ? "true" : "false"}</span>
                <span class="pill">draw_order=${part.draw_order}</span>
            </div>
            <div class="rig-layout-part-copy">${part.part_role || part.coverage || "No guidance."}</div>
        `;
        partsRoot.appendChild(row);
    });
    if (!layout.parts?.length) {
        partsRoot.innerHTML = `<div class="empty">No parts defined yet.</div>`;
    }
    rigLayoutHistory(project).slice(-6).reverse().forEach((revision) => {
        const row = document.createElement("div");
        row.className = "history-item";
        row.innerHTML = `
            <div class="meta-line">
                <span class="pill">${revision.revision_id === project.rig_layout_history?.current_revision_id ? "selected" : "revision"}</span>
                <span class="pill">${humanizeKey(revision.reason || "snapshot")}</span>
            </div>
            <div class="small-note" style="margin-top: 8px;">${formatDate(revision.created_at)}</div>
        `;
        historyRoot.appendChild(row);
    });
    if (!rigLayoutHistory(project).length) {
        historyRoot.innerHTML = `<div class="empty">No revisions yet.</div>`;
    }
}

function approvedSourceAsset(project) {
    const accepted = project?.concepts?.find((concept) => concept.concept_id === project?.selected_concept_id);
    const source = accepted?.approved_source_image || project?.sprite_model?.approved_source_image || project?.master_pose_manifest?.approved_image || "";
    return source ? projectAsset(project, source) : "";
}

function cloneJson(value) {
    return value == null ? value : JSON.parse(JSON.stringify(value));
}

function syncPartShapeHistory(project) {
    const signature = JSON.stringify(project?.part_shapes || null);
    if (state.partShapeSourceSignature === signature) return;
    state.partShapeSourceSignature = signature;
    state.partShapeHistory = project?.part_shapes ? [cloneJson(project.part_shapes)] : [];
    state.partShapeHistoryIndex = state.partShapeHistory.length ? 0 : -1;
    if (project?.part_shapes?.parts?.length && !project.part_shapes.parts.some((part) => part.part_name === state.selectedShapePart)) {
        state.selectedShapePart = project.part_shapes.parts[0].part_name;
    }
}

function localPartShapes() {
    if (state.partShapeHistoryIndex >= 0) return cloneJson(state.partShapeHistory[state.partShapeHistoryIndex]);
    return cloneJson(state.activeProject?.part_shapes || null);
}

function replaceLocalPartShapes(partShapes, { pushHistory = true } = {}) {
    if (!state.activeProject) return;
    const snapshot = cloneJson(partShapes);
    state.activeProject.part_shapes = snapshot;
    state.partShapeSourceSignature = JSON.stringify(snapshot);
    if (pushHistory) {
        state.partShapeHistory = state.partShapeHistory.slice(0, state.partShapeHistoryIndex + 1);
        state.partShapeHistory.push(cloneJson(snapshot));
        state.partShapeHistoryIndex = state.partShapeHistory.length - 1;
    } else if (state.partShapeHistoryIndex >= 0) {
        state.partShapeHistory[state.partShapeHistoryIndex] = cloneJson(snapshot);
    } else if (snapshot) {
        state.partShapeHistory = [cloneJson(snapshot)];
        state.partShapeHistoryIndex = 0;
    }
}

async function persistLocalPartShapes(partShapes) {
    if (!state.activeProject) return;
    await api(`/api/projects/${state.activeProject.project_id}/part-shapes/update`, {
        method: "POST",
        body: JSON.stringify({
            operation: "replace_shapes",
            part_shapes: partShapes,
        }),
    });
    await loadProject(state.activeProject.project_id, currentMode());
}

function ensureShapeViewFit(project) {
    if (!project) return;
    const source = approvedSourceAsset(project);
    if (!source || state.partShapeView.fitted) return;
    const width = 640;
    const height = 768;
    const surface = document.querySelector("#part-shapes-editor .shape-editor-surface");
    if (!surface) return;
    const zoom = Math.min(surface.clientWidth / width, surface.clientHeight / height, 1);
    state.partShapeView.zoom = zoom;
    state.partShapeView.panX = (surface.clientWidth - width * zoom) / 2;
    state.partShapeView.panY = (surface.clientHeight - height * zoom) / 2;
    state.partShapeView.fitted = true;
}

function renderPartManifest() {
    const project = state.activeProject;
    const manifest = project?.part_manifest;
    const sourceRoot = document.querySelector("#part-manifest-source");
    const summaryRoot = document.querySelector("#part-manifest-summary");
    const listRoot = document.querySelector("#part-manifest-list");
    const checksRoot = document.querySelector("#part-manifest-checks");
    const warning = document.querySelector("#part-manifest-warning");
    const approveButton = document.querySelector("#approve-part-manifest");
    const promptButton = document.querySelector("#copy-part-manifest-prompt");
    [sourceRoot, summaryRoot, listRoot, checksRoot].forEach((node) => {
        if (node) node.innerHTML = "";
    });
    if (!sourceRoot || !summaryRoot || !listRoot || !checksRoot || !warning || !approveButton || !promptButton) return;
    if (!project || !manifest) {
        sourceRoot.innerHTML = `<div class="empty">Approve the rig layout, then generate the part manifest.</div>`;
        summaryRoot.innerHTML = `<div class="empty">No manifest summary yet.</div>`;
        listRoot.innerHTML = `<div class="empty">No manifest parts yet.</div>`;
        checksRoot.innerHTML = `<div class="empty">No manifest validation yet.</div>`;
        approveButton.disabled = true;
        promptButton.disabled = true;
        return;
    }
    promptButton.disabled = !project.part_manifest_handoff_prompt;
    const sourcePath = approvedSourceAsset(project);
    sourceRoot.innerHTML = sourcePath
        ? `<div class="preview-card"><img src="${sourcePath}?v=${project.updated_at}" alt="Approved source"></div>`
        : `<div class="empty">No approved source image found.</div>`;
    const validation = manifest.validation || {};
    warning.textContent = manifest.approved
        ? "Part manifest approved. The next stage now authors actual shapes for this exact part list."
        : validation.status === "fail"
            ? "Manifest approval is blocked. Resolve duplicate names or missing required metadata first."
            : "Review the current part list, adjust optional parts if needed, then approve the manifest.";
    approveButton.disabled = validation.status === "fail";
    summaryRoot.innerHTML = `
        <div class="frame-metrics">
            <div class="metric-chip"><span>Profile</span><strong>${manifest.rig_profile || "unknown"}</strong></div>
            <div class="metric-chip"><span>Total Parts</span><strong>${manifest.parts?.length || 0}</strong></div>
            <div class="metric-chip"><span>Required</span><strong>${validation.required_count || 0}</strong></div>
            <div class="metric-chip"><span>Optional</span><strong>${validation.optional_count || 0}</strong></div>
        </div>
    `;
    (manifest.parts || []).forEach((part) => {
        const row = document.createElement("div");
        row.className = "shape-editor-part-row";
        row.innerHTML = `
            <div class="meta-line">
                <span class="pill">${part.part_name}</span>
                <span class="pill">${part.required ? "required" : "optional"}</span>
                <span class="pill">${part.overlay_only ? "overlay" : "driven"}</span>
                <span class="pill">${part.source || "manual"}</span>
            </div>
            <div class="small-note">${part.part_label || part.part_name} · parent ${part.parent_joint || "unset"} · draw ${part.draw_order ?? "?"}</div>
            <div class="shape-editor-part-actions">
                <button class="secondary manifest-rename" data-part-name="${part.part_name}">Rename</button>
                <button class="secondary manifest-overlay" data-part-name="${part.part_name}">${part.overlay_only ? "Mark Driven" : "Mark Overlay"}</button>
                ${part.required ? "" : `<button class="secondary manifest-delete" data-part-name="${part.part_name}">Delete Optional</button>`}
            </div>
        `;
        listRoot.appendChild(row);
    });
    if (!manifest.parts?.length) listRoot.innerHTML = `<div class="empty">No manifest parts yet.</div>`;
    checksRoot.innerHTML = [
        buildIssueMarkup("Failures", validation.failures || [], "fail"),
        buildIssueMarkup("Warnings", validation.warnings || [], "warning"),
    ].join("") || `<div class="success-box"><p><strong>Manifest Ready</strong></p><div class="history-item">No blocking manifest issues.</div></div>`;

    listRoot.querySelectorAll(".manifest-rename").forEach((button) => {
        button.addEventListener("click", async () => {
            const partName = button.dataset.partName;
            const nextLabel = window.prompt("Rename part label", partName);
            if (!nextLabel) return;
            try {
                await api(`/api/projects/${project.project_id}/part-manifest/update`, {
                    method: "POST",
                    body: JSON.stringify({ operation: "update_part", part_name: partName, part_label: nextLabel }),
                });
                await loadProject(project.project_id, currentMode());
            } catch (error) {
                notify(normalizeErrorMessage(error.message), "error");
            }
        });
    });
    listRoot.querySelectorAll(".manifest-overlay").forEach((button) => {
        button.addEventListener("click", async () => {
            const partName = button.dataset.partName;
            const current = manifest.parts.find((part) => part.part_name === partName);
            if (!current) return;
            try {
                await api(`/api/projects/${project.project_id}/part-manifest/update`, {
                    method: "POST",
                    body: JSON.stringify({ operation: "update_part", part_name: partName, overlay_only: !current.overlay_only }),
                });
                await loadProject(project.project_id, currentMode());
            } catch (error) {
                notify(normalizeErrorMessage(error.message), "error");
            }
        });
    });
    listRoot.querySelectorAll(".manifest-delete").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await api(`/api/projects/${project.project_id}/part-manifest/update`, {
                    method: "POST",
                    body: JSON.stringify({ operation: "delete_optional_part", part_name: button.dataset.partName }),
                });
                await loadProject(project.project_id, currentMode());
            } catch (error) {
                notify(normalizeErrorMessage(error.message), "error");
            }
        });
    });
}

function shapeEditorSourcePoint(event, surface) {
    const rect = surface.getBoundingClientRect();
    return [
        (event.clientX - rect.left - state.partShapeView.panX) / state.partShapeView.zoom,
        (event.clientY - rect.top - state.partShapeView.panY) / state.partShapeView.zoom,
    ];
}

function insertVertexOnNearestEdge(vertices, point) {
    const list = Array.isArray(vertices) ? vertices : [];
    if (list.length < 2) return [...list, point];
    let bestIndex = list.length;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (let index = 0; index < list.length; index += 1) {
        const start = list[index];
        const end = list[(index + 1) % list.length];
        const ax = Number(start[0]);
        const ay = Number(start[1]);
        const bx = Number(end[0]);
        const by = Number(end[1]);
        const dx = bx - ax;
        const dy = by - ay;
        const lengthSquared = dx * dx + dy * dy;
        const t = lengthSquared <= 0 ? 0 : Math.max(0, Math.min(1, (((point[0] - ax) * dx) + ((point[1] - ay) * dy)) / lengthSquared));
        const px = ax + dx * t;
        const py = ay + dy * t;
        const distance = ((point[0] - px) ** 2) + ((point[1] - py) ** 2);
        if (distance < bestDistance) {
            bestDistance = distance;
            bestIndex = index + 1;
        }
    }
    const next = [...list];
    next.splice(bestIndex, 0, point);
    return next;
}

function renderPartShapeEdit() {
    const project = state.activeProject;
    syncPartShapeHistory(project);
    const shapes = localPartShapes();
    const editorRoot = document.querySelector("#part-shapes-editor");
    const listRoot = document.querySelector("#part-shapes-list");
    const checksRoot = document.querySelector("#part-shapes-checks");
    const select = document.querySelector("#part-shapes-select");
    const opacityInput = document.querySelector("#part-shapes-opacity");
    const warning = document.querySelector("#part-shapes-warning");
    const approveButton = document.querySelector("#approve-part-shapes");
    const promptButton = document.querySelector("#copy-part-shapes-prompt");
    [editorRoot, listRoot, checksRoot, select].forEach((node) => {
        if (node) node.innerHTML = "";
    });
    if (!editorRoot || !listRoot || !checksRoot || !select || !warning || !approveButton || !promptButton) return;
    if (!project || !shapes) {
        editorRoot.innerHTML = `<div class="empty">Approve the part manifest, then initialize the part shapes.</div>`;
        listRoot.innerHTML = `<div class="empty">No shapes yet.</div>`;
        checksRoot.innerHTML = `<div class="empty">No shape validation yet.</div>`;
        approveButton.disabled = true;
        promptButton.disabled = true;
        document.querySelector("#shape-undo").disabled = true;
        document.querySelector("#shape-redo").disabled = true;
        document.querySelector("#shape-reset-selected").disabled = true;
        return;
    }
    const activeShapes = localPartShapes();
    if (!activeShapes?.parts?.some((part) => part.part_name === state.selectedShapePart)) {
        state.selectedShapePart = activeShapes?.parts?.[0]?.part_name || null;
    }
    const activePart = selectedShapePart(activeShapes);
    if (opacityInput) opacityInput.value = String(Math.round(state.partShapeView.sourceOpacity * 100));
    promptButton.disabled = !project.part_shapes_handoff_prompt;
    approveButton.disabled = activeShapes.validation?.status === "fail";
    document.querySelector("#shape-undo").disabled = state.partShapeHistoryIndex <= 0;
    document.querySelector("#shape-redo").disabled = state.partShapeHistoryIndex >= state.partShapeHistory.length - 1;
    document.querySelector("#shape-reset-selected").disabled = !activePart;
    warning.textContent = activeShapes.approved
        ? "Part shapes approved. Split build will now cut assets from these exact shapes."
        : activeShapes.validation?.status === "fail"
            ? "Shape approval is blocked. Fix empty or invalid required shapes first."
            : "Pan with Shift-drag, zoom with the wheel, and refine vertices until the shapes look right.";
    (activeShapes.parts || []).forEach((part) => {
        const option = document.createElement("option");
        option.value = part.part_name;
        option.textContent = part.part_label || part.part_name;
        if (part.part_name === activePart?.part_name) option.selected = true;
        select.appendChild(option);
    });
    select.onchange = () => {
        state.selectedShapePart = select.value;
        renderPartShapeEdit();
    };

    const sourcePath = approvedSourceAsset(project);
    const width = 640;
    const height = 768;
    const paths = (activeShapes.parts || []).map((part) => {
        const points = (part.vertices || []).map((point) => point.join(",")).join(" ");
        const opacity = part.visible === false ? 0.06 : part.part_name === activePart?.part_name ? 0.38 : 0.18;
        const stroke = part.color || "#7cb5dc";
        return `
            <polygon data-part-name="${part.part_name}" points="${points}" fill="${stroke}" fill-opacity="${opacity}" stroke="${stroke}" stroke-width="${part.part_name === activePart?.part_name ? 3 : 1.5}" ${part.visible === false ? `stroke-dasharray="6 6"` : ""}></polygon>
        `;
    }).join("");
    const vertices = (activePart?.vertices || []).map((point, index) => `
        <circle class="shape-editor-vertex" data-vertex-index="${index}" cx="${point[0]}" cy="${point[1]}" r="7" fill="#f1d9a2" stroke="#11161c" stroke-width="2"></circle>
    `).join("");
    editorRoot.innerHTML = `
        <div class="shape-editor-shell">
            <div class="shape-editor-toolbar">
                <div class="small-note">${activePart ? `${activePart.part_name}: ${activePart.vertices?.length || 0} vertices` : "Select a part to edit."}</div>
                <div class="shape-editor-meta">
                    <span class="shape-editor-chip">Zoom ${state.partShapeView.zoom.toFixed(2)}x</span>
                    <span class="shape-editor-chip">${activeShapes.validation?.status || "candidate"}</span>
                </div>
            </div>
            <div class="shape-editor-surface" id="shape-editor-surface">
                <div class="shape-editor-stage" id="shape-editor-stage" style="width:${width}px; height:${height}px; transform: translate(${state.partShapeView.panX}px, ${state.partShapeView.panY}px) scale(${state.partShapeView.zoom});">
                    ${sourcePath ? `<img src="${sourcePath}?v=${project.updated_at}" alt="Approved source" style="width:${width}px; height:${height}px; opacity:${state.partShapeView.sourceOpacity};">` : ""}
                    <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" aria-label="Part shape editor">
                        ${paths}
                        ${vertices}
                    </svg>
                </div>
            </div>
        </div>
    `;
    ensureShapeViewFit(project);
    const surface = editorRoot.querySelector("#shape-editor-surface");
    const stage = editorRoot.querySelector("#shape-editor-stage");
    if (stage) {
        stage.style.transform = `translate(${state.partShapeView.panX}px, ${state.partShapeView.panY}px) scale(${state.partShapeView.zoom})`;
    }
    const applyShapes = async (nextShapes, { pushHistory = true } = {}) => {
        replaceLocalPartShapes(nextShapes, { pushHistory });
        renderPartShapeEdit();
        try {
            await persistLocalPartShapes(nextShapes);
        } catch (error) {
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    surface.addEventListener("wheel", (event) => {
        event.preventDefault();
        const oldZoom = state.partShapeView.zoom;
        const nextZoom = Math.max(0.35, Math.min(3.5, oldZoom + (event.deltaY < 0 ? 0.12 : -0.12)));
        const rect = surface.getBoundingClientRect();
        const offsetX = event.clientX - rect.left;
        const offsetY = event.clientY - rect.top;
        const sourceX = (offsetX - state.partShapeView.panX) / oldZoom;
        const sourceY = (offsetY - state.partShapeView.panY) / oldZoom;
        state.partShapeView.zoom = nextZoom;
        state.partShapeView.panX = offsetX - sourceX * nextZoom;
        state.partShapeView.panY = offsetY - sourceY * nextZoom;
        state.partShapeView.fitted = true;
        renderPartShapeEdit();
    }, { passive: false });
    surface.addEventListener("pointerdown", (event) => {
        let panning = false;
        let draggingVertex = null;
        let startPan = null;
        if (event.shiftKey || event.button === 1) {
            panning = true;
            surface.classList.add("panning");
            startPan = { clientX: event.clientX, clientY: event.clientY, panX: state.partShapeView.panX, panY: state.partShapeView.panY };
        } else {
            const vertex = event.target.closest(".shape-editor-vertex");
            if (vertex && activePart && !activePart.locked) {
                if (event.altKey) {
                    const nextShapes = cloneJson(activeShapes);
                    const nextPart = nextShapes.parts.find((part) => part.part_name === activePart.part_name);
                    nextPart.vertices.splice(Number(vertex.dataset.vertexIndex), 1);
                    applyShapes(nextShapes);
                    return;
                }
                draggingVertex = Number(vertex.dataset.vertexIndex);
            } else {
                const polygon = event.target.closest("polygon[data-part-name]");
                if (polygon && polygon.dataset.partName) {
                    if (polygon.dataset.partName === activePart?.part_name && !activePart.locked) {
                        const point = shapeEditorSourcePoint(event, surface);
                        const nextShapes = cloneJson(activeShapes);
                        const nextPart = nextShapes.parts.find((part) => part.part_name === activePart.part_name);
                        nextPart.vertices = insertVertexOnNearestEdge(nextPart.vertices || [], [Math.round(point[0]), Math.round(point[1])]);
                        applyShapes(nextShapes);
                        return;
                    }
                    state.selectedShapePart = polygon.dataset.partName;
                    renderPartShapeEdit();
                    return;
                }
                if (!activePart || activePart.locked) return;
                const point = shapeEditorSourcePoint(event, surface);
                const nextShapes = cloneJson(activeShapes);
                const nextPart = nextShapes.parts.find((part) => part.part_name === activePart.part_name);
                nextPart.vertices = [...(nextPart.vertices || []), [Math.round(point[0]), Math.round(point[1])]];
                applyShapes(nextShapes);
                return;
            }
        }
        const onMove = (moveEvent) => {
            if (panning && startPan) {
                state.partShapeView.panX = startPan.panX + (moveEvent.clientX - startPan.clientX);
                state.partShapeView.panY = startPan.panY + (moveEvent.clientY - startPan.clientY);
                stage.style.transform = `translate(${state.partShapeView.panX}px, ${state.partShapeView.panY}px) scale(${state.partShapeView.zoom})`;
                return;
            }
            if (draggingVertex == null || !activePart || activePart.locked) return;
            const point = shapeEditorSourcePoint(moveEvent, surface);
            const circles = editorRoot.querySelectorAll(".shape-editor-vertex");
            const circle = circles[draggingVertex];
            if (circle) {
                circle.setAttribute("cx", Math.round(point[0]));
                circle.setAttribute("cy", Math.round(point[1]));
            }
        };
        const onUp = async (upEvent) => {
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            if (panning) {
                surface.classList.remove("panning");
                return;
            }
            if (draggingVertex == null || !activePart || activePart.locked) return;
            const point = shapeEditorSourcePoint(upEvent, surface);
            const nextShapes = cloneJson(activeShapes);
            const nextPart = nextShapes.parts.find((part) => part.part_name === activePart.part_name);
            nextPart.vertices[draggingVertex] = [Math.round(point[0]), Math.round(point[1])];
            draggingVertex = null;
            await applyShapes(nextShapes);
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
    });

    (activeShapes.parts || []).forEach((part) => {
        const row = document.createElement("div");
        row.className = `shape-editor-part-row${part.part_name === activePart?.part_name ? " active" : ""}`;
        row.innerHTML = `
            <div class="meta-line">
                <span class="pill">${part.part_name}</span>
                <span class="pill">${part.status || "candidate"}</span>
                <span class="pill">${part.source_method || "manual"}</span>
            </div>
            <div class="shape-editor-part-actions">
                <label class="shape-editor-chip"><input type="checkbox" data-shape-visible="${part.part_name}" ${part.visible === false ? "" : "checked"}> Visible</label>
                <label class="shape-editor-chip"><input type="checkbox" data-shape-locked="${part.part_name}" ${part.locked ? "checked" : ""}> Locked</label>
                <button class="secondary shape-focus" data-part-name="${part.part_name}">Focus</button>
                <button class="secondary shape-reset" data-part-name="${part.part_name}">Reset</button>
            </div>
        `;
        listRoot.appendChild(row);
    });
    if (!activeShapes.parts?.length) listRoot.innerHTML = `<div class="empty">No shape parts yet.</div>`;
    checksRoot.innerHTML = [
        buildIssueMarkup("Failures", activeShapes.validation?.failures || [], "fail"),
        buildIssueMarkup("Warnings", activeShapes.validation?.warnings || [], "warning"),
    ].join("") || `<div class="success-box"><p><strong>Shapes Ready</strong></p><div class="history-item">No blocking shape issues.</div></div>`;

    listRoot.querySelectorAll("[data-shape-visible]").forEach((input) => {
        input.addEventListener("change", async () => {
            const nextShapes = cloneJson(activeShapes);
            const part = nextShapes.parts.find((item) => item.part_name === input.dataset.shapeVisible);
            if (!part) return;
            part.visible = input.checked;
            await applyShapes(nextShapes);
        });
    });
    listRoot.querySelectorAll("[data-shape-locked]").forEach((input) => {
        input.addEventListener("change", async () => {
            const nextShapes = cloneJson(activeShapes);
            const part = nextShapes.parts.find((item) => item.part_name === input.dataset.shapeLocked);
            if (!part) return;
            part.locked = input.checked;
            await applyShapes(nextShapes);
        });
    });
    listRoot.querySelectorAll(".shape-focus").forEach((button) => {
        button.addEventListener("click", () => {
            state.selectedShapePart = button.dataset.partName;
            renderPartShapeEdit();
        });
    });
    listRoot.querySelectorAll(".shape-reset").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await api(`/api/projects/${project.project_id}/part-shapes/update`, {
                    method: "POST",
                    body: JSON.stringify({ operation: "reset_part_shape", part_name: button.dataset.partName }),
                });
                await loadProject(project.project_id, currentMode());
            } catch (error) {
                notify(normalizeErrorMessage(error.message), "error");
            }
        });
    });
}

function renderPartSplit() {
    const project = state.activeProject;
    const split = project?.part_split;
    const sourceRoot = document.querySelector("#part-split-source");
    const previewRoot = document.querySelector("#part-split-preview");
    const galleryRoot = document.querySelector("#part-split-gallery");
    const checksRoot = document.querySelector("#part-split-checks");
    const splitSourceReview = document.querySelector("#split-review-source");
    const splitPreviewReview = document.querySelector("#split-review-preview");
    const splitChecksReview = document.querySelector("#split-review-checks");
    const warning = document.querySelector("#part-split-warning");
    const approveButton = document.querySelector("#approve-part-split");
    [sourceRoot, previewRoot, galleryRoot, checksRoot, splitSourceReview, splitPreviewReview, splitChecksReview].forEach((node) => {
        if (node) node.innerHTML = "";
    });
    if (approveButton) approveButton.disabled = true;
    if (!sourceRoot || !previewRoot || !galleryRoot || !checksRoot || !splitSourceReview || !splitPreviewReview || !splitChecksReview || !warning) return;
    if (!project || !split) {
        sourceRoot.innerHTML = `<div class="empty">Approve the rig layout, then generate split parts.</div>`;
        previewRoot.innerHTML = `<div class="empty">No reconstruction preview yet.</div>`;
        galleryRoot.innerHTML = `<div class="empty">No split parts yet.</div>`;
        checksRoot.innerHTML = `<div class="empty">No validation yet.</div>`;
        splitSourceReview.innerHTML = `<div class="empty">No source preview yet.</div>`;
        splitPreviewReview.innerHTML = `<div class="empty">No reconstruction preview yet.</div>`;
        splitChecksReview.innerHTML = `<div class="empty">No split review state yet.</div>`;
        return;
    }
    const sourcePath = split.source_image ? projectAsset(project, split.source_image) : approvedSourceAsset(project);
    const previewPath = split.reconstruction_preview?.path ? projectAsset(project, split.reconstruction_preview.path) : "";
    if (sourcePath) {
        const card = `<div class="preview-card"><img src="${sourcePath}?v=${project.updated_at}" alt="Approved source"></div>`;
        sourceRoot.innerHTML = card;
        splitSourceReview.innerHTML = card;
    } else {
        sourceRoot.innerHTML = `<div class="empty">No source image found.</div>`;
        splitSourceReview.innerHTML = `<div class="empty">No source image found.</div>`;
    }
    if (previewPath) {
        const card = `<div class="preview-card"><img src="${previewPath}?v=${project.updated_at}" alt="Split reconstruction"></div>`;
        previewRoot.innerHTML = card;
        splitPreviewReview.innerHTML = card;
    } else {
        previewRoot.innerHTML = `<div class="empty">No reconstruction preview yet.</div>`;
        splitPreviewReview.innerHTML = `<div class="empty">No reconstruction preview yet.</div>`;
    }
    const validation = split.validation || {};
    warning.textContent = split.approved
        ? "Split parts approved. Sprite-model build now consumes the approved separated parts directly."
        : validation.status === "fail"
            ? "Split approval is blocked. Fix missing or contaminated parts before continuing."
            : "Generate or import candidate parts, then review the reconstruction before approval.";
    if (approveButton) approveButton.disabled = validation.status === "fail";
    (split.parts || []).forEach((part) => {
        const card = document.createElement("div");
        card.className = "preview-card";
        const imagePath = part.image_path ? projectAsset(project, part.image_path) : "";
        card.innerHTML = imagePath
            ? `<img src="${imagePath}?v=${project.updated_at}" alt="${part.part_name}"><div class="small-note" style="margin-top:8px;">${part.part_name}</div>`
            : `<div class="empty">${part.part_name}</div>`;
        galleryRoot.appendChild(card);
    });
    if (!split.parts?.length) galleryRoot.innerHTML = `<div class="empty">No split parts yet.</div>`;
    const issueMarkup = [
        buildIssueMarkup("Failures", validation.failures || [], "fail"),
        buildIssueMarkup("Warnings", validation.warnings || [], "warning"),
    ].join("");
    checksRoot.innerHTML = issueMarkup || `<div class="empty">No validation notes yet.</div>`;
    splitChecksReview.innerHTML = issueMarkup || `<div class="success-box"><p><strong>Split Ready</strong></p><div class="history-item">No blocking split issues.</div></div>`;
}

function paletteSwatchesMarkup(palette) {
    const swatches = palette?.swatches || [];
    if (!swatches.length) return `<div class="empty">No palette extracted yet.</div>`;
    return `
        <div class="swatch-row">
            ${swatches.map((swatch) => `<div class="swatch" title="${swatch}" style="background:${swatch};"></div>`).join("")}
        </div>
    `;
}

function buildIssueMarkup(title, items, tone = "warning") {
    if (!items?.length) return "";
    const klass = tone === "fail" ? "warning-box" : tone === "ok" ? "success-box" : "info-box";
    return `
        <div class="${klass}">
            <p><strong>${title}</strong></p>
            <div class="history-list" style="margin-top: 10px;">
                ${items.map((item) => `<div class="history-item">${item}</div>`).join("")}
            </div>
        </div>
    `;
}

function updateSpriteEditorPreview(editor, bbox, pivot, maskRegion) {
    const box = editor.querySelector(".sprite-editor-box");
    const pivotHandle = editor.querySelector(".editor-pivot-handle");
    const maskPreview = editor.querySelector(".editor-mask-preview");
    if (box) box.style.cssText = bboxStyleString(bbox);
    if (pivotHandle) pivotHandle.style.cssText = pivotStyleString(bbox, pivot);
    editor.querySelectorAll(".editor-handle").forEach((handle) => {
        handle.style.cssText = handlePositionStyle(bbox, handle.dataset.handle);
    });
    if (maskPreview) {
        if (maskRegion) {
            maskPreview.hidden = false;
            maskPreview.style.cssText = bboxStyleString(maskRegion);
        } else {
            maskPreview.hidden = true;
            maskPreview.style.cssText = "";
        }
    }
}

function bindSpriteEditorInteractions(editor, activePart) {
    if (!editor || !activePart) return;
    const activeBBox = normalizeSourceBBox(activePart.bbox);
    const activePivot = Array.isArray(activePart.pivot_point) ? [Number(activePart.pivot_point[0]), Number(activePart.pivot_point[1])] : [0, 0];
    const mode = state.spriteEditorMode;

    const startGesture = (kind, event, extra = {}) => {
        event.preventDefault();
        event.stopPropagation();
        const startPoint = sourcePointFromEvent(event, editor);
        const startBBox = normalizeSourceBBox(activeBBox);
        const startPivot = [...activePivot];
        let previewBBox = [...startBBox];
        let previewPivot = [...startPivot];
        let previewMask = null;

        const onMove = (moveEvent) => {
            const point = sourcePointFromEvent(moveEvent, editor);
            if (kind === "move") {
                const dx = point[0] - startPoint[0];
                const dy = point[1] - startPoint[1];
                previewBBox = normalizeSourceBBox([
                    startBBox[0] + dx,
                    startBBox[1] + dy,
                    startBBox[2] + dx,
                    startBBox[3] + dy,
                ]);
            } else if (kind === "resize") {
                previewBBox = [...startBBox];
                if (extra.handle.includes("w")) previewBBox[0] = point[0];
                if (extra.handle.includes("e")) previewBBox[2] = point[0];
                if (extra.handle.includes("n")) previewBBox[1] = point[1];
                if (extra.handle.includes("s")) previewBBox[3] = point[1];
                previewBBox = normalizeSourceBBox(previewBBox);
            } else if (kind === "pivot") {
                previewPivot = pointToLocalPivot(point, startBBox);
            } else if (kind === "mask") {
                previewMask = normalizeSourceBBox([startPoint[0], startPoint[1], point[0], point[1]]);
            }
            updateSpriteEditorPreview(editor, previewBBox, previewPivot, previewMask);
        };

        const onUp = async (upEvent) => {
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            const endPoint = sourcePointFromEvent(upEvent, editor);
            try {
                if (kind === "move" || kind === "resize") {
                    const finalBBox = previewBBox || normalizeSourceBBox([startBBox[0], startBBox[1], endPoint[0], endPoint[1]]);
                    if (JSON.stringify(finalBBox) !== JSON.stringify(startBBox)) {
                        await applySpriteOperation("set_bbox", { bbox: finalBBox });
                    } else {
                        updateSpriteEditorPreview(editor, startBBox, startPivot, null);
                    }
                } else if (kind === "pivot") {
                    if (JSON.stringify(previewPivot) !== JSON.stringify(startPivot)) {
                        await applySpriteOperation("set_pivot", { pivot_point: previewPivot });
                    } else {
                        updateSpriteEditorPreview(editor, startBBox, startPivot, null);
                    }
                } else if (kind === "mask" && previewMask) {
                    const operation = mode === "mask_remove" ? "remove_from_mask" : "add_to_mask";
                    await applySpriteOperation(operation, { region: previewMask });
                } else {
                    updateSpriteEditorPreview(editor, startBBox, startPivot, null);
                }
            } catch (error) {
                log(normalizeErrorMessage(error.message), "error");
                notify(normalizeErrorMessage(error.message), "error");
            }
        };

        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
    };

    editor.querySelector(".sprite-editor-box")?.addEventListener("pointerdown", (event) => {
        startGesture(mode === "mask_add" || mode === "mask_remove" ? "mask" : "move", event);
    });
    editor.querySelector(".editor-pivot-handle")?.addEventListener("pointerdown", (event) => {
        if (mode === "mask_add" || mode === "mask_remove") {
            startGesture("mask", event);
            return;
        }
        startGesture("pivot", event);
    });
    editor.querySelectorAll(".editor-handle").forEach((handle) => {
        handle.addEventListener("pointerdown", (event) => {
            if (mode === "mask_add" || mode === "mask_remove") {
                startGesture("mask", event);
                return;
            }
            startGesture("resize", event, { handle: handle.dataset.handle });
        });
    });
    editor.querySelectorAll(".editor-hitbox").forEach((hitbox) => {
        hitbox.addEventListener("click", () => {
            state.selectedSpritePart = hitbox.dataset.partName;
            renderLayerReview();
        });
    });
    editor.addEventListener("pointerdown", (event) => {
        if (mode !== "mask_add" && mode !== "mask_remove") return;
        if (event.target.closest(".editor-hitbox")) return;
        startGesture("mask", event);
    });
}

function renderLayerReview() {
    const checksRoot = document.querySelector("#layer-checks");
    const galleryRoot = document.querySelector("#layer-gallery");
    const sourceRoot = document.querySelector("#sprite-model-source");
    const selectedRoot = document.querySelector("#sprite-model-selected");
    const select = document.querySelector("#sprite-part-select");
    const parentJoint = document.querySelector("#sprite-parent-joint");
    const revisionSelect = document.querySelector("#sprite-revision-select");
    checksRoot.innerHTML = "";
    galleryRoot.innerHTML = "";
    sourceRoot.innerHTML = "";
    selectedRoot.innerHTML = "";
    select.innerHTML = "";
    parentJoint.innerHTML = "";
    revisionSelect.innerHTML = "";
    const layered = state.activeProject?.sprite_model || state.activeProject?.layered_character;
    const project = state.activeProject;
    if (!project || !layered) {
        checksRoot.innerHTML = `<div class="empty">Sprite model has not run yet.</div>`;
        sourceRoot.innerHTML = `<div class="empty">Build the sprite model to inspect source overlays.</div>`;
        selectedRoot.innerHTML = `<div class="empty">No selected part yet.</div>`;
        document.querySelector("#approve-layers").disabled = true;
        document.querySelector("#sprite-undo-last").disabled = true;
        document.querySelector("#sprite-restore-revision").disabled = true;
        document.querySelector("#sprite-draw-order-back").disabled = true;
        document.querySelector("#sprite-draw-order-forward").disabled = true;
        return;
    }

    const buildReport = currentBuildReport();
    const parts = sortPartsByRigLayout(layered.parts || [], project);
    if (!parts.some((part) => part.part_name === state.selectedSpritePart)) {
        state.selectedSpritePart = parts[0]?.part_name || null;
    }
    const activePart = selectedSpritePart();
    const previousPart = activePart ? previousSpritePart(activePart.part_name) : null;
    const partReport = buildReport?.per_part?.find((item) => item.part_name === activePart?.part_name);
    const activeGuide = activePart ? spritePartGuide(activePart, project) : null;
    const approvedImage = `${approvedConceptSourcePath(project)}?v=${project.updated_at}`;
    const revisions = selectedRevisionHistory();
    const currentRevisionId = state.selectedRevisionId || project.sprite_model_history?.current_revision_id || revisions.slice(-1)[0]?.revision_id || null;
    state.selectedRevisionId = currentRevisionId;

    document.querySelector("#layer-warning").textContent = layered.approved_for_rigging
        ? "Sprite model approved for rigging."
        : buildReport?.status === "fail"
            ? "Build failures block approval. Fix the failing parts before continuing."
            : buildReport?.status === "warning"
                ? "Warnings are visible below. You can still approve once the risks are understood."
                : "Use the direct editor to correct pivots, bbox placement, and mask issues before approval.";
    document.querySelector("#approve-layers").disabled = !layered || buildReport?.status === "fail";
    document.querySelector("#approve-layers").textContent = buildReport?.status === "warning" ? "Approve With Warnings" : "Approve Sprite Model";
    document.querySelector("#sprite-undo-last").disabled = revisions.length < 2;
    document.querySelector("#sprite-restore-revision").disabled = !currentRevisionId;
    document.querySelector("#sprite-draw-order-back").disabled = !activePart;
    document.querySelector("#sprite-draw-order-forward").disabled = !activePart;

    parts.forEach((part) => {
        const option = document.createElement("option");
        option.value = part.part_name;
        option.textContent = part.part_name;
        if (activePart?.part_name === part.part_name) option.selected = true;
        select.appendChild(option);
    });
    select.onchange = () => {
        state.selectedSpritePart = select.value;
        renderLayerReview();
    };

    const joints = [...new Set([
        ...rigLayoutJointNames(project),
        ...parts.map((part) => part.parent_joint).filter(Boolean),
        activePart?.parent_joint,
    ].filter(Boolean))];
    joints.forEach((joint) => {
        const option = document.createElement("option");
        option.value = joint;
        option.textContent = joint;
        if (activePart?.parent_joint === joint) option.selected = true;
        parentJoint.appendChild(option);
    });
    parentJoint.onchange = async () => {
        if (!activePart) return;
        try {
            await applySpriteOperation("set_parent_joint", { parent_joint: parentJoint.value });
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };

    revisions.slice().reverse().forEach((revision) => {
        const option = document.createElement("option");
        option.value = revision.revision_id;
        option.textContent = `${formatDate(revision.created_at)} · ${humanizeKey(revision.reason || revision.operation || "revision")}`;
        if (revision.revision_id === currentRevisionId) option.selected = true;
        revisionSelect.appendChild(option);
    });
    revisionSelect.onchange = () => {
        state.selectedRevisionId = revisionSelect.value;
    };

    if (activePart) {
        sourceRoot.innerHTML = `
            <div class="sprite-editor-panel">
                <div class="sprite-editor-toolbar">
                    <div class="inline-actions">
                        <button class="${state.spriteEditorMode === "move" ? "" : "secondary"}" data-editor-mode="move">Move Or Resize</button>
                        <button class="${state.spriteEditorMode === "mask_add" ? "" : "secondary"}" data-editor-mode="mask_add">Add Mask Rect</button>
                        <button class="${state.spriteEditorMode === "mask_remove" ? "" : "secondary"}" data-editor-mode="mask_remove">Remove Mask Rect</button>
                    </div>
                    <div class="small-note">${activePart.part_name}: ${activeGuide?.coverage || "Drag the gold bbox to move it, drag the corner handles to resize it, and drag the green pivot to retarget the joint anchor."}</div>
                </div>
                <div class="preview-card overlay-stack sprite-editor mode-${state.spriteEditorMode.replace("_", "-")}" id="sprite-editor-interactive">
                    <img src="${approvedImage}" alt="Approved source image">
                    ${parts.map((part) => `<button class="editor-hitbox ${part.part_name === activePart.part_name ? "selected" : ""}" data-part-name="${part.part_name}" style="${bboxStyleString(part.bbox)}" aria-label="${part.part_name}"></button>`).join("")}
                    <div class="overlay-box sprite-editor-box" style="${bboxStyleString(activePart.bbox)}"></div>
                    <div class="editor-part-label"><strong>${activePart.part_name}</strong><span>${activeGuide?.coverage || ""}</span></div>
                    <button class="editor-pivot-handle" data-editor-target="pivot" style="${pivotStyleString(activePart.bbox, activePart.pivot_point)}" aria-label="Move pivot"></button>
                    ${["nw", "ne", "sw", "se"].map((handle) => `<button class="editor-handle" data-handle="${handle}" style="${handlePositionStyle(activePart.bbox, handle)}" aria-label="Resize ${handle}"></button>`).join("")}
                    <div class="editor-mask-preview ${state.spriteEditorMode === "mask_remove" ? "remove" : ""}" hidden></div>
                </div>
                <div class="small-note">Draw-order preview is live: use the forward and backward buttons above, then rebuild the rig to propagate positional changes.</div>
            </div>
        `;
        sourceRoot.querySelectorAll("[data-editor-mode]").forEach((button) => {
            button.onclick = () => {
                state.spriteEditorMode = button.dataset.editorMode;
                renderLayerReview();
            };
        });
        bindSpriteEditorInteractions(sourceRoot.querySelector("#sprite-editor-interactive"), activePart);
    } else {
        sourceRoot.innerHTML = `<div class="empty">No part selected.</div>`;
    }

    const variants = selectedRecoveryVariants();
    selectedRoot.innerHTML = activePart ? `
        <div class="detail-grid">
            <div class="${previousPart ? "grid-2" : "detail-grid"}">
                ${previousPart ? `
                    <div class="detail-grid">
                        ${overlayMarkup(approvedImage, previousPart?.bbox, previousPart?.pivot_point)}
                        <div class="small-note">Before last edit</div>
                    </div>
                ` : ""}
                <div class="preview-card">
                    <img src="${projectAsset(project, activePart.image_path)}?v=${project.updated_at}" alt="${activePart.part_name}">
                    <div class="meta-line" style="margin-top: 10px;">
                        <span class="pill">${activePart.part_name}</span>
                        <span class="pill">${activePart.parent_joint}</span>
                        <span class="pill">draw_order=${activePart.draw_order}</span>
                        <span class="pill ${statusTone(partReport?.status || buildReport?.status || "warning")}">${partReport?.status || buildReport?.status || "warning"}</span>
                    </div>
                    <div class="small-note" style="margin-top: 10px;">${activeGuide?.coverage || "Current extracted asset."} Promote a recovery variant below if the part was occluded or badly cropped.</div>
                </div>
            </div>
            <div class="check-list">
                <div class="check-row wrap"><span>What this should cover</span><span class="small-note">${activeGuide?.coverage || "Keep the box tight to the intended body part."}</span></div>
                <div class="check-row wrap"><span>Selected bbox</span><span class="small-note">${formatBBox(activePart.bbox)}</span></div>
                <div class="check-row wrap"><span>Pivot</span><span class="small-note">${activePart.pivot_point?.join(", ") || "none"}</span></div>
                <div class="check-row wrap"><span>Mirror source</span><span class="small-note">${activePart.mirror_of || "original extraction"}</span></div>
                <div class="check-row wrap"><span>Mask area</span><span class="small-note">${partReport?.mask_area ?? "n/a"}</span></div>
                <div class="check-row wrap"><span>BBox size</span><span class="small-note">${partReport?.bbox_size?.join(" × ") || bboxDimensions(activePart.bbox).join(" × ")}</span></div>
            </div>
            ${buildIssueMarkup("Selected Part Warnings", partReport?.warnings || [], "warning")}
            ${buildIssueMarkup("Selected Part Failures", partReport?.failures || [], "fail")}
            <div>
                <div class="meta-line" style="margin-bottom: 10px;">
                    <span class="pill">${variants.length} recovery variant${variants.length === 1 ? "" : "s"}</span>
                </div>
                ${variants.length ? `
                    <div class="recovery-grid">
                        ${variants.map((variant) => `
                            <div class="recovery-card">
                                <img src="${projectAsset(project, variant.image_path)}?v=${project.updated_at}" alt="${variant.variant_id}">
                                <div class="small-note" style="margin-top: 8px;">${variant.summary || variant.variant_id}</div>
                                <div class="actions" style="margin-top: 10px;">
                                    <button class="secondary" data-promote-recovery="${variant.variant_id}" data-image-path="${variant.image_path}" data-mask-path="${variant.mask_path}">Promote Variant</button>
                                </div>
                            </div>
                        `).join("")}
                    </div>
                ` : `<div class="empty">Run occlusion recovery for the selected part if you need alternates.</div>`}
            </div>
        </div>
    ` : `<div class="empty">No part selected.</div>`;
    selectedRoot.querySelectorAll("[data-promote-recovery]").forEach((button) => {
        button.onclick = async () => {
            try {
                await api(`/api/projects/${project.project_id}/sprite-model/promote-recovery`, {
                    method: "POST",
                    body: JSON.stringify({
                        part_name: activePart.part_name,
                        image_path: button.dataset.imagePath,
                        mask_path: button.dataset.maskPath,
                    }),
                });
                state.spriteRecoveryVariants[activePart.part_name] = [];
                await loadProject(project.project_id, currentMode());
                notify(`Promoted a recovery variant for ${activePart.part_name}.`, "success");
            } catch (error) {
                log(normalizeErrorMessage(error.message), "error");
                notify(normalizeErrorMessage(error.message), "error");
            }
        };
    });

    document.querySelector("#sprite-rename").value = activePart?.part_name || "";
    document.querySelector("#sprite-pivot-x").value = activePart?.pivot_point?.[0] ?? "";
    document.querySelector("#sprite-pivot-y").value = activePart?.pivot_point?.[1] ?? "";
    document.querySelector("#sprite-draw-order").value = activePart?.draw_order ?? "";

    const summaryRows = [
        ["Build status", `<span class="pill ${statusTone(buildReport?.status || "warning")}">${buildReport?.status || "warning"}</span>`],
        ["Approval", layered.approved_for_rigging ? `<span class="pill ok">approved for rigging</span>` : `<span class="pill warning">awaiting approval</span>`],
        ["Parts", `${parts.length} / ${buildReport?.summary?.required_part_count || parts.length}`],
        ["Warnings", buildReport?.summary?.warning_count ?? 0],
        ["Failures", buildReport?.summary?.fail_count ?? 0],
        ["Mirrored fallbacks", buildReport?.summary?.mirrored_fallback_count ?? 0],
        ["Facing", layered.source_facing || "unknown"],
        ["Palette", paletteSwatchesMarkup(layered.palette || project.palette)],
    ];
    summaryRows.forEach(([key, value]) => {
        const row = document.createElement("div");
        row.className = "check-row wrap";
        row.innerHTML = key === "Palette"
            ? `<span>${key}</span><span>${value}</span>`
            : key === "Build status" || key === "Approval"
                ? `<span>${key}</span><span>${value}</span>`
                : `<span>${key}</span><span class="small-note">${value}</span>`;
        checksRoot.appendChild(row);
    });

    if (buildReport) {
        const reportBox = document.createElement("div");
        reportBox.className = "detail-grid";
        reportBox.innerHTML = `
            ${buildIssueMarkup("Build Failures", buildReport.failures || [], "fail")}
            ${buildIssueMarkup("Build Warnings", buildReport.warnings || [], "warning")}
            ${buildIssueMarkup("Overlap Warnings", (buildReport.overlap_warnings || []).map((item) => `${item.parts.join(" vs ")} · overlap ${item.ratio}`), "warning")}
            ${buildIssueMarkup("Prop Separation Warnings", (buildReport.prop_separation_warnings || []).map((item) => `${item.parts.join(" vs ")} · overlap ${item.ratio}`), "warning")}
        `;
        if (reportBox.textContent.trim()) checksRoot.appendChild(reportBox);
    }

    const perPart = document.createElement("div");
    perPart.className = "revision-list";
    (buildReport?.per_part || []).forEach((item) => {
        const guide = spritePartGuide(item, project);
        const row = document.createElement("div");
        row.className = "history-item";
        row.innerHTML = `
            <div class="meta-line">
                <span class="pill ${statusTone(item.status)}">${item.status}</span>
                <span class="pill">${item.part_name}</span>
                <span class="pill">${item.bbox_size?.join(" × ") || "n/a"}</span>
                ${item.used_mirrored_fallback ? `<span class="pill warning">mirrored fallback</span>` : ""}
            </div>
            <div class="small-note" style="margin-top: 8px;">${guide.coverage} mask area ${item.mask_area} · bbox ${item.bbox.join(", ")}</div>
        `;
        perPart.appendChild(row);
    });
    if (perPart.childElementCount) checksRoot.appendChild(perPart);

    const historyEvents = (project.sprite_model_history?.events || []).slice(-6).reverse();
    if (historyEvents.length || revisions.length) {
        const history = document.createElement("div");
        history.className = "revision-list";
        history.innerHTML = `
            ${revisions.slice(-6).reverse().map((revision) => `
                <div class="history-item">
                    <div class="meta-line">
                        <span class="pill ${revision.revision_id === currentRevisionId ? "ok" : ""}">${revision.revision_id === currentRevisionId ? "selected" : "revision"}</span>
                        <span class="pill">${humanizeKey(revision.reason || revision.operation || "snapshot")}</span>
                        ${revision.part_name ? `<span class="pill">${revision.part_name}</span>` : ""}
                    </div>
                    <div class="small-note" style="margin-top: 8px;">${formatDate(revision.created_at)} · hash ${String(revision.sprite_model_hash || "").slice(0, 12)}</div>
                </div>
            `).join("")}
            ${historyEvents.map((event) => `
                <div class="history-item">
                    <div class="meta-line">
                        <span class="pill">${humanizeKey(event.type || "update")}</span>
                        ${event.operation ? `<span class="pill">${humanizeKey(event.operation)}</span>` : ""}
                        ${event.part_name ? `<span class="pill">${event.part_name}</span>` : ""}
                    </div>
                    <div class="small-note" style="margin-top: 8px;">${formatDate(event.created_at)}</div>
                </div>
            `).join("")}
        `;
        checksRoot.appendChild(history);
    }

    (parts || []).slice(0, 20).forEach((part) => {
        const guide = spritePartGuide(part, project);
        const report = buildReport?.per_part?.find((item) => item.part_name === part.part_name);
        const thumb = document.createElement("div");
        thumb.className = "thumb";
        thumb.innerHTML = `
            <img src="${projectAsset(project, part.image_path)}?v=${project.updated_at}" alt="${part.part_name}">
            <div class="small-note" style="margin-top: 8px;"><strong>${part.part_name}</strong><br>${guide.coverage}</div>
            <div class="meta-line" style="justify-content:center; margin-top: 8px;">
                <span class="pill">${part.parent_joint}</span>
                <span class="pill">draw_order=${part.draw_order}</span>
                ${report ? `<span class="pill ${statusTone(report.status)}">${report.status}</span>` : ""}
            </div>
        `;
        thumb.addEventListener("click", () => {
            state.selectedSpritePart = part.part_name;
            renderLayerReview();
        });
        galleryRoot.appendChild(thumb);
    });
}
