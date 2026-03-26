function conceptById(conceptId) {
    return state.activeProject?.concepts?.find((concept) => concept.concept_id === conceptId) || null;
}

function selectedConcept() {
    const project = state.activeProject;
    return conceptById(project?.selected_concept_id) || null;
}

function triageClass(status) {
    if (status === "system-demoted") return "fail";
    if (status === "warning") return "warning";
    return "ok";
}

function renderRunGrid() {
    /* Phase 7.2: Gemini prompt run grid removed; scaffold lives in #concept-scaffold-prompt. */
}

function ensureConceptUiSelection() {
    const project = state.activeProject;
    const withPreview = (project?.concepts || []).filter((c) => conceptDisplayImagePath(c));
    if (!withPreview.length) {
        state.conceptUiSelectedId = null;
        return;
    }
    const ok = state.conceptUiSelectedId && withPreview.some((c) => c.concept_id === state.conceptUiSelectedId);
    if (!ok) {
        const preferred = project.selected_concept_id;
        state.conceptUiSelectedId = preferred && withPreview.some((c) => c.concept_id === preferred)
            ? preferred
            : withPreview[0].concept_id;
    }
}

function conceptDisplayImagePath(concept) {
    if (!concept) return "";
    return concept.processed_preview_image
        || concept.preview_image
        || concept.original_preview_image
        || concept.approved_source_image
        || concept.image_path
        || "";
}

async function conceptPreviewDisplayUrl(url) {
    if (!url) return "";
    if (state.conceptPreviewDisplayCache[url]) return state.conceptPreviewDisplayCache[url];

    const trimmedPromise = new Promise((resolve) => {
        const source = new Image();
        source.decoding = "async";
        source.onload = () => {
            try {
                const width = source.naturalWidth || source.width || 0;
                const height = source.naturalHeight || source.height || 0;
                if (!width || !height) {
                    resolve(url);
                    return;
                }

                const canvas = document.createElement("canvas");
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext("2d", { willReadFrequently: true });
                if (!ctx) {
                    resolve(url);
                    return;
                }
                ctx.drawImage(source, 0, 0, width, height);
                const data = ctx.getImageData(0, 0, width, height).data;

                let minX = width;
                let minY = height;
                let maxX = -1;
                let maxY = -1;
                for (let y = 0; y < height; y += 1) {
                    for (let x = 0; x < width; x += 1) {
                        const alpha = data[(y * width + x) * 4 + 3];
                        if (alpha <= 8) continue;
                        if (x < minX) minX = x;
                        if (y < minY) minY = y;
                        if (x > maxX) maxX = x;
                        if (y > maxY) maxY = y;
                    }
                }

                if (maxX < minX || maxY < minY) {
                    resolve(url);
                    return;
                }

                const contentWidth = maxX - minX + 1;
                const contentHeight = maxY - minY + 1;
                const widthPadding = Math.max(8, Math.round(contentWidth * 0.06));
                const heightPadding = Math.max(8, Math.round(contentHeight * 0.06));
                const left = Math.max(0, minX - widthPadding);
                const top = Math.max(0, minY - heightPadding);
                const right = Math.min(width, maxX + widthPadding + 1);
                const bottom = Math.min(height, maxY + heightPadding + 1);
                const trimmedWidth = right - left;
                const trimmedHeight = bottom - top;

                if (
                    trimmedWidth >= width * 0.96 &&
                    trimmedHeight >= height * 0.96
                ) {
                    resolve(url);
                    return;
                }

                const trimmed = document.createElement("canvas");
                trimmed.width = trimmedWidth;
                trimmed.height = trimmedHeight;
                const trimmedCtx = trimmed.getContext("2d");
                if (!trimmedCtx) {
                    resolve(url);
                    return;
                }
                trimmedCtx.drawImage(canvas, left, top, trimmedWidth, trimmedHeight, 0, 0, trimmedWidth, trimmedHeight);
                resolve(trimmed.toDataURL("image/png"));
            } catch (_error) {
                resolve(url);
            }
        };
        source.onerror = () => resolve(url);
        source.src = url;
    });

    state.conceptPreviewDisplayCache[url] = trimmedPromise;
    const resolved = await trimmedPromise;
    state.conceptPreviewDisplayCache[url] = resolved;
    return resolved;
}

async function exportSheetPreviewDisplayUrl(url) {
    if (!url) return "";
    if (state.exportSheetPreviewDisplayCache[url]) return state.exportSheetPreviewDisplayCache[url];

    const trimmedPromise = new Promise((resolve) => {
        const source = new Image();
        source.decoding = "async";
        source.onload = () => {
            try {
                const width = source.naturalWidth || source.width || 0;
                const height = source.naturalHeight || source.height || 0;
                if (!width || !height) {
                    resolve(url);
                    return;
                }

                const canvas = document.createElement("canvas");
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext("2d", { willReadFrequently: true });
                if (!ctx) {
                    resolve(url);
                    return;
                }
                ctx.drawImage(source, 0, 0, width, height);
                const data = ctx.getImageData(0, 0, width, height).data;

                let minY = height;
                let maxY = -1;
                for (let y = 0; y < height; y += 1) {
                    for (let x = 0; x < width; x += 1) {
                        const alpha = data[(y * width + x) * 4 + 3];
                        if (alpha <= 8) continue;
                        if (y < minY) minY = y;
                        if (y > maxY) maxY = y;
                    }
                }

                if (maxY < minY) {
                    resolve(url);
                    return;
                }

                const contentHeight = maxY - minY + 1;
                const verticalPadding = Math.max(2, Math.round(contentHeight * 0.03));
                const top = Math.max(0, minY - verticalPadding);
                const bottom = Math.min(height, maxY + verticalPadding + 1);
                const trimmedHeight = bottom - top;

                if (trimmedHeight >= height * 0.96) {
                    resolve(url);
                    return;
                }

                const trimmed = document.createElement("canvas");
                trimmed.width = width;
                trimmed.height = trimmedHeight;
                const trimmedCtx = trimmed.getContext("2d");
                if (!trimmedCtx) {
                    resolve(url);
                    return;
                }
                trimmedCtx.drawImage(canvas, 0, top, width, trimmedHeight, 0, 0, width, trimmedHeight);
                resolve(trimmed.toDataURL("image/png"));
            } catch (_error) {
                resolve(url);
            }
        };
        source.onerror = () => resolve(url);
        source.src = url;
    });

    state.exportSheetPreviewDisplayCache[url] = trimmedPromise;
    const resolved = await trimmedPromise;
    state.exportSheetPreviewDisplayCache[url] = resolved;
    return resolved;
}

function renderConceptLargePreview() {
    const root = document.querySelector("#concept-large-preview");
    if (!root) return;
    const emptyEl = root.querySelector("[data-concept-preview-empty]");
    const stackEl = root.querySelector("[data-concept-preview-stack]");
    const img = root.querySelector("[data-concept-preview-img]");
    const stage = root.querySelector("[data-concept-preview-stage]");
    const zoomBtn = root.querySelector("[data-concept-preview-open-zoom]");
    const approveBtn = root.querySelector("[data-concept-preview-approve-lock]");
    const skeletonBtn = root.querySelector("[data-concept-preview-estimate-skeleton]");
    const statusEl = root.querySelector("[data-concept-preview-status]");
    const project = state.activeProject;
    const concept = state.conceptUiSelectedId ? conceptById(state.conceptUiSelectedId) : null;
    const path = conceptDisplayImagePath(concept);
    if (!path) {
        if (emptyEl) emptyEl.hidden = false;
        if (stackEl) stackEl.hidden = true;
        if (zoomBtn) zoomBtn.disabled = true;
        if (approveBtn) approveBtn.disabled = true;
        if (skeletonBtn) {
            skeletonBtn.disabled = true;
            skeletonBtn.hidden = true;
        }
        if (statusEl) statusEl.textContent = "";
        return;
    }
    if (emptyEl) emptyEl.hidden = true;
    if (stackEl) stackEl.hidden = false;
    if (stage) stage.style.transform = "translate(0px, 0px) scale(1)";
    if (img) {
        img.alt = concept.concept_id;
        const url = `${projectAsset(project, path)}?v=${project.updated_at}`;
        const previewToken = `${concept.concept_id}|${url}`;
        img.dataset.previewToken = previewToken;
        img.src = url;
        conceptPreviewDisplayUrl(url).then((displayUrl) => {
            if (img.dataset.previewToken !== previewToken) return;
            if (displayUrl) img.src = displayUrl;
        });
    }
    if (zoomBtn) {
        zoomBtn.disabled = false;
        zoomBtn.onclick = () => openZoom(concept.concept_id);
    }
    const isPixellab = String(project?.brief?.backend_mode || "") === "pixellab";
    const isApproved = Boolean(concept?.review_state?.approved);
    const hasEastSource = Boolean(project?.pixellab_character?.images?.east);
    const sourceMatchesSelection = project?.pixellab_character?.source_concept_id === concept?.concept_id;
    const sourceLocked = Boolean(sourceMatchesSelection && pixellabCharacterApproved(project));
    if (approveBtn) {
        approveBtn.hidden = false;
        approveBtn.textContent = isPixellab ? (sourceLocked ? "Source locked" : "Approve & lock source") : (isApproved ? "Approved source" : "Approve source");
        approveBtn.disabled = concept?.validation_status !== "valid" || sourceLocked;
        approveBtn.onclick = async () => {
            await reviewConcept(concept.concept_id, "approve", true);
        };
    }
    if (skeletonBtn) {
        skeletonBtn.hidden = !isPixellab;
        skeletonBtn.disabled = !sourceLocked || !hasEastSource;
        skeletonBtn.onclick = async () => {
            try {
                if (!paidActionAllowed("Estimate skeleton via Pixel Lab")) return;
                notify("Estimating skeleton on east frame…", "info");
                await api(`/api/projects/${project.project_id}/pixellab/estimate-skeleton`, {
                    method: "POST",
                    body: JSON.stringify({ direction: "east" }),
                });
                notify("Skeleton saved.", "success");
                await loadProject(project.project_id, currentMode());
                renderAll();
            } catch (error) {
                log(normalizeErrorMessage(error.message), "error");
                notify(normalizeErrorMessage(error.message), "error");
            }
        };
    }
    if (statusEl) {
        if (isPixellab) {
            statusEl.textContent = sourceLocked
                ? "This concept is locked as the east-facing source for animation. Skeleton estimation is optional."
                : "Approving a valid concept also locks it as the east-facing source for animation.";
        } else {
            statusEl.textContent = isApproved
                ? "This concept is approved as the current source."
                : "Select a valid concept and approve it to continue.";
        }
    }
}

function renderIterationCompare() {
    const beforeRoot = document.querySelector("#concept-iterate-before");
    const afterRoot = document.querySelector("#concept-iterate-after");
    const selectBtn = document.querySelector("#select-latest-iteration");
    const downloadBtn = document.querySelector("#download-latest-iteration");
    const statusEl = document.querySelector("#latest-iteration-status");
    const project = state.activeProject;
    if (!project) return;
    const selected = state.conceptUiSelectedId ? conceptById(state.conceptUiSelectedId) : null;
    const after = state.lastIteratedConceptId ? conceptById(state.lastIteratedConceptId) : null;
    if (beforeRoot) {
        const path = conceptDisplayImagePath(selected);
        if (path) {
            beforeRoot.innerHTML = `<img src="${projectAsset(project, path)}?v=${project.updated_at}" alt="before">`;
        } else {
            beforeRoot.innerHTML = `<div class="empty">No selection</div>`;
        }
    }
    if (afterRoot) {
        const path = conceptDisplayImagePath(after);
        if (path) {
            afterRoot.innerHTML = `<img src="${projectAsset(project, path)}?v=${project.updated_at}" alt="after">`;
        } else {
            afterRoot.innerHTML = `<div class="empty">—</div>`;
        }
    }
    const hasAfter = !!after && !!conceptDisplayImagePath(after);
    if (selectBtn) {
        selectBtn.disabled = !hasAfter;
    }
    if (downloadBtn) {
        downloadBtn.disabled = !hasAfter;
    }
    if (statusEl) {
        statusEl.textContent = hasAfter
            ? `Latest iteration ${after.concept_id} is already saved as a new concept.`
            : "Generated iterations are saved as new concepts automatically.";
    }
}

function renderConceptGrid() {
    const root = document.querySelector("#concept-grid");
    const countEl = document.querySelector("#concept-grid-count");
    if (!root) return;
    root.innerHTML = "";
    wireConceptWorkbenchControlsOnce();
    syncConceptPanelMode();
    ensureConceptUiSelection();
    const concepts = (state.activeProject?.concepts || []).filter((concept) => conceptDisplayImagePath(concept));
    if (countEl) {
        countEl.textContent = `${concepts.length} item${concepts.length === 1 ? "" : "s"}`;
    }
    if (!concepts.length) {
        root.innerHTML = `<div class="empty">No concept images yet. Use Pixel Lab or Manual import.</div>`;
        return;
    }
    concepts.forEach((concept) => {
        const card = document.createElement("div");
        card.className = "concept-card";
        if (concept.concept_id === state.conceptUiSelectedId) card.classList.add("selected");
        const triage = concept.triage || {};
        const previewPath = conceptDisplayImagePath(concept);
        const hasProcessed = Boolean(concept.processed_preview_image);
        const triageLabel = triage.status === "ok"
            ? "heuristics ok"
            : triage.status === "warning"
                ? "heuristics warning"
                : triage.status === "system-demoted"
                    ? "heuristics fail"
                    : triage.status || "heuristics";
        const summary = concept.difference_summary || concept.codex_review_summary || concept.validation_feedback || (triage.flags || []).join(", ") || "—";
        const canApprove = concept.validation_status === "valid";
        card.innerHTML = `
            <img src="${projectAsset(state.activeProject, previewPath)}?v=${state.activeProject.updated_at}" alt="${concept.concept_id}">
            <div class="body">
                <div class="concept-top">
                    <div class="concept-title">
                        <strong>${concept.concept_id}</strong>
                        <span class="muted">v${concept.prompt_version || "?"} · ${concept.import_source || concept.run_kind || "concept"}</span>
                    </div>
                </div>
                ${concept.review_state?.approved ? `<div class="meta-line"><span class="pill ok">approved source</span></div>` : ""}
                <div class="small-note">${summary}</div>
                ${concept.validation_error ? `<div class="warning-box"><p>${concept.validation_error}</p></div>` : ""}
                <div class="actions">
                    <button class="secondary" data-action="select">Select</button>
                    <button class="secondary" data-action="mark-valid" ${concept.validation_status === "valid" ? "disabled" : ""}>Mark valid</button>
                    <button data-action="approve" ${canApprove ? "" : "disabled"}>Approve &amp; lock source</button>
                    <button class="secondary" data-action="zoom">Zoom</button>
                    <button class="secondary danger" data-action="delete" title="Remove this concept from the project">Delete</button>
                </div>
            </div>
        `;
        card.querySelector("[data-action='select']").addEventListener("click", () => {
            state.conceptUiSelectedId = concept.concept_id;
            renderConceptReview();
        });
        card.querySelector("[data-action='mark-valid']").addEventListener("click", () => validateConceptAttempt(concept.concept_id, "valid", ""));
        card.querySelector("[data-action='approve']").addEventListener("click", () => reviewConcept(concept.concept_id, "approve", true));
        card.querySelector("[data-action='zoom']").addEventListener("click", () => openZoom(concept.concept_id));
        card.querySelector("[data-action='delete']").addEventListener("click", async () => {
            const approved = Boolean(concept.review_state?.approved);
            const msg = approved
                ? `Delete ${concept.concept_id}? It is the approved character source — rig, sprite model, and later stages will be reset.`
                : `Delete ${concept.concept_id}? This removes the image and record from the project.`;
            if (!confirm(msg)) return;
            try {
                await deleteConceptById(concept.concept_id);
            } catch (error) {
                log(normalizeErrorMessage(error.message), "error");
                notify(normalizeErrorMessage(error.message), "error");
            }
        });
        root.appendChild(card);
    });
}

function renderConceptReview() {
    renderRunGrid();
    renderConceptGrid();
    renderConceptLargePreview();
    renderIterationCompare();
}
