function aiDependencySummaryMarkup(store) {
    const entries = Object.entries(store?.dependency_status?.dependencies || {});
    if (!entries.length) return `<div class="empty">Dependency health has not been checked yet.</div>`;
    return entries.map(([name, item]) => `
        <div class="check-row wrap">
            <span>${humanizeKey(name)}</span>
            <span class="small-note"><span class="pill ${item.status === "pass" ? "ok" : "fail"}">${item.status}</span> ${item.detail || ""}</span>
        </div>
    `).join("");
}

function pixellabCharacterDirectionOrder(charData) {
    const dirs = charData?.directions;
    if (Array.isArray(dirs) && dirs.length) return dirs;
    const images = charData?.images;
    if (images && typeof images === "object") return Object.keys(images);
    return [];
}

function drawPixellabSkeletonOnCanvas(canvas, img, skeletonJson, visible) {
    if (!canvas || !img) return;
    const ctx = canvas.getContext("2d");
    const w = img.clientWidth || img.naturalWidth;
    const h = img.clientHeight || img.naturalHeight;
    if (!w || !h) return;
    canvas.width = w;
    canvas.height = h;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.clearRect(0, 0, w, h);
    if (!visible || !skeletonJson?.skeleton_keypoints) return;
    const pts = skeletonJson.skeleton_keypoints;
    if (!Array.isArray(pts)) return;
    const iw = Number(skeletonJson.image_size?.width) || img.naturalWidth || 64;
    const ih = Number(skeletonJson.image_size?.height) || img.naturalHeight || 64;
    const sx = w / iw;
    const sy = h / ih;
    ctx.fillStyle = "rgba(255, 92, 135, 0.95)";
    ctx.strokeStyle = "rgba(12, 16, 22, 0.9)";
    ctx.lineWidth = 2;
    pts.forEach((p) => {
        if (!Array.isArray(p) || p.length < 2) return;
        const x = Number(p[0]) * sx;
        const y = Number(p[1]) * sy;
        ctx.beginPath();
        ctx.arc(x, y, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    });
}

async function runPixellabCreateCharacter(pid, selId, directions) {
    if (!selId || !pid) return;
    if (!paidActionAllowed(directions === 8 ? "Create 8-direction Pixel Lab character" : "Create 4-direction Pixel Lab character")) return;
    const detail =
        directions === 8
            ? "Creating 8-direction character (Pixel Lab may take 1–3 minutes)…"
            : "Creating 4-direction character (Pixel Lab may take 1–3 minutes)…";
    state.pixellabCreateCharacterBusy = true;
    renderPixellabCharacterBoard();
    notify(directions === 8 ? "Creating 8-direction character…" : "Creating 4-direction character…", "info");

    const jobType = "pixellab.create_character";
    setActivity({
        state: "Working",
        jobType,
        label: "Creating Pixel Lab character",
        detail,
        percent: 6,
    });

    const root = document.querySelector("#pixellab-character-board");
    const fill = root?.querySelector("[data-pixellab-char-progress-fill]");
    const pctText = root?.querySelector("[data-pixellab-char-progress-pct]");
    const started = Date.now();
    const durationMs = directions === 8 ? 150000 : 120000;
    const tick = window.setInterval(() => {
        const elapsed = Date.now() - started;
        const pct = Math.min(92, 6 + (elapsed / durationMs) * 86);
        if (fill) fill.style.width = `${pct}%`;
        if (pctText) pctText.textContent = `${Math.round(pct)}%`;
        if (state.activity && state.activity.jobType === jobType) {
            setActivity({ ...state.activity, percent: pct, detail });
        }
    }, 350);

    let ok = false;
    let charPayload = null;
    try {
        charPayload = await api(`/api/projects/${pid}/pixellab/create-character`, {
            method: "POST",
            body: JSON.stringify({ directions, color_concept_id: selId }),
        });
        ok = true;
        notify(directions === 8 ? "8-direction character created." : "4-direction character created.", "success");
        if (state.activity && state.activity.jobType === jobType) {
            setActivity({ ...state.activity, state: "Done", detail: "Almost done…", percent: 100 });
        }
        if (fill) fill.style.width = "100%";
        if (pctText) pctText.textContent = "100%";
        await new Promise((r) => setTimeout(r, 220));
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    } finally {
        window.clearInterval(tick);
        state.pixellabCreateCharacterBusy = false;
        clearActivity();
    }
    if (ok && charPayload && state.activeProject?.project_id === pid) {
        state.activeProject.pixellab_character = charPayload;
        state.activeProject.pixellab_character_ready = true;
        state.activeProject.pixellab_character_approved = false;
        renderAll();
    }
    if (ok) {
        await loadProject(pid, currentMode());
        if (charPayload && state.activeProject?.project_id === pid && !state.activeProject.pixellab_character) {
            state.activeProject.pixellab_character = charPayload;
            state.activeProject.pixellab_character_ready = true;
            state.activeProject.pixellab_character_approved = false;
        }
        if (String(state.activeProject?.brief?.backend_mode || "") === "pixellab") {
            try {
                await persistWizardState({ current_step: "animations", last_ui_mode: "wizard" });
            } catch (err) {
                log(normalizeErrorMessage(err.message), "error");
            }
        }
        renderAll();
        document.getElementById("panel-scroll").scrollTop = 0;
    } else {
        renderPixellabCharacterBoard();
    }
}

function renderPixellabCharacterBoard() {
    const root = document.querySelector("#pixellab-character-board");
    if (!root) return;
    const project = state.activeProject;
    root.innerHTML = "";
    if (!project) {
        root.innerHTML = `<div class="empty">Open or create a project to use the Character panel.</div>`;
        return;
    }
    const brief = project.brief || {};
    if (String(brief.backend_mode || "") !== "pixellab") {
        root.innerHTML = pixellabBackendModeMismatchBox(brief.backend_mode);
        wirePixellabSwitchBackendButton(root);
        return;
    }
    const sel = selectedConcept();
    const selId = project.selected_concept_id;
    const pix = project.pixellab_character;
    const skel = project.pixellab_skeleton;
    const approved = pixellabCharacterApproved(project);
    const eastOnlySource = Boolean(pix?.east_only_source);
    const dirCount = pix
        ? (Array.isArray(pix.directions) && pix.directions.length ? pix.directions.length : Object.keys(pix.images || {}).length)
        : 0;
    const conceptPath = sel?.preview_image || sel?.original_preview_image;
    const assetV = pixellabCharacterAssetVersion(project, pix);
    const conceptPreview = sel && conceptPath
        ? `<div class="pixellab-character-source-preview"><img src="${projectAsset(project, conceptPath)}?v=${assetV}" alt="Chosen concept"></div>`
        : `<div class="empty">Choose a concept in the Concepts panel first.</div>`;

    const hasEastAsset = Boolean(pix?.images?.east);
    const busyCreate = state.pixellabCreateCharacterBusy;
    const charActions = `
        <div class="actions" style="margin-top: 12px; flex-wrap: wrap; gap: 8px;">
            <button type="button" id="pixellab-use-east-source" ${selId && !busyCreate ? "" : "disabled"}>Use Concept as Character (East Only)</button>
            <button type="button" class="secondary" id="pixellab-create-4" ${selId && !busyCreate ? "" : "disabled"}>Create Character (4 dir)</button>
            <button type="button" class="secondary" id="pixellab-create-8" ${selId && !busyCreate ? "" : "disabled"}>Create Character (8 dir)</button>
            <button type="button" class="secondary" id="pixellab-estimate-sk" ${hasEastAsset ? "" : "disabled"}>Estimate skeleton (east)</button>
            <button type="button" id="pixellab-approve-char" ${pix && !approved ? "" : "disabled"}>Approve Character</button>
        </div>
        ${busyCreate
        ? `<div class="pixellab-char-progress workbench-waitbar" role="status" aria-live="polite" aria-busy="true">
            <div class="small-note workbench-waitbar-detail">Creating character — this can take a few minutes while Pixel Lab generates all directions.</div>
            <div class="progress-track">
                <div class="progress-fill" data-pixellab-char-progress-fill style="width:6%"></div>
            </div>
            <div class="progress-meta">
                <span data-pixellab-char-progress-pct>6%</span>
                <span class="small-note">Progress is estimated until the server finishes.</span>
            </div>
        </div>`
        : ""}
    `;

    let directionsHtml = "";
    if (pix?.images && typeof pix.images === "object") {
        const order = pixellabCharacterDirectionOrder(pix);
        directionsHtml = `<details class="flow-collapsible" style="margin-top:18px;" open>
            <summary>
                <span>Direction previews</span>
                <span class="small-note">${order.length} view${order.length === 1 ? "" : "s"}</span>
            </summary>
            <div class="flow-collapsible-body">
                <div class="pixellab-direction-grid">${order.map((dir) => {
            const rel = pix.images[dir];
            const src = rel ? `${projectAsset(project, rel)}?v=${assetV}` : "";
            const isEast = dir === "east";
            if (isEast) {
                return `<div class="pixellab-direction-cell">
                    <div class="small-note">${humanizeKey(dir)}</div>
                    <div class="pixellab-east-stack">
                        <img data-pixellab-east-img src="${src}" alt="${dir}">
                        <canvas class="pixellab-skeleton-overlay" data-pixellab-skeleton-canvas></canvas>
                    </div>
                    ${skel?.skeleton_keypoints ? `<label class="small-note" style="display:flex;gap:6px;align-items:center;justify-content:center;margin-top:6px;">
                        <input type="checkbox" id="pixellab-toggle-skeleton" ${state.pixellabShowSkeleton ? "checked" : ""}> Skeleton overlay
                    </label>` : `<div class="small-note" style="margin-top:6px;">Run <strong>Estimate skeleton</strong> to overlay keypoints.</div>`}
                </div>`;
            }
            return `<div class="pixellab-direction-cell">
                <div class="small-note">${humanizeKey(dir)}</div>
                <img src="${src}" alt="${dir}">
            </div>`;
        }).join("")}</div>
            </div>
        </details>`;
    }

    root.innerHTML = `
        <div class="stage-primary-grid character-stage-layout">
            <div class="clip-control-card stage-card">
                <div class="stage-card-head">
                    <h4>Chosen concept</h4>
                    <p class="small-note">This is the approved look you are carrying into the character stage.</p>
                </div>
                ${conceptPreview}
            </div>
            <div class="clip-control-card stage-card">
                <div class="stage-card-head">
                    <h4>Character actions</h4>
                    <p class="small-note">Lock the concept as east-only or generate multi-direction character sheets, then approve when the identity feels stable.</p>
                </div>
                <div class="small-note" style="margin-bottom:10px;">
                    ${pix
        ? eastOnlySource
            ? "Using the approved concept directly as the east-facing character source."
            : `${dirCount} direction${dirCount !== 1 ? "s" : ""} generated.`
        : "No character yet — create from the concept on the left."}
                    ${approved ? ` <span class="pill ok">Approved</span>` : pix ? ` <span class="pill warn">Not approved</span>` : ""}
                </div>
                ${eastOnlySource ? `<div class="info-box" style="margin-bottom:10px;"><p><strong>East-only source mode</strong> keeps the approved concept unchanged. You can estimate skeleton on the east image and approve it for downstream use. East-facing custom animation generation remains available from the Animations panel.</p></div>` : ""}
                ${charActions}
                ${pix ? `<details class="advanced-settings" style="margin-top:10px;"><summary>Technical details</summary><div class="advanced-content"><p class="small-note" style="margin:0;">Character id: <code>${escapeHtml(String(pix.character_id || ""))}</code></p>${skel ? `<p class="small-note" style="margin:6px 0 0;">Skeleton (${escapeHtml(String(skel.direction || "?"))}): ${(skel.skeleton_keypoints || []).length} keypoints.</p>` : ""}</div></details>` : ""}
            </div>
        </div>
        ${directionsHtml || ""}
    `;

    const eastImg = root.querySelector("[data-pixellab-east-img]");
    const eastCanvas = root.querySelector("[data-pixellab-skeleton-canvas]");
    const syncEastOverlay = () => {
        if (eastImg && eastCanvas) drawPixellabSkeletonOnCanvas(eastCanvas, eastImg, skel, state.pixellabShowSkeleton);
    };
    if (eastImg) {
        eastImg.addEventListener("load", syncEastOverlay);
        if (eastImg.complete) syncEastOverlay();
    }
    const toggle = root.querySelector("#pixellab-toggle-skeleton");
    if (toggle) {
        toggle.addEventListener("change", () => {
            state.pixellabShowSkeleton = toggle.checked;
            syncEastOverlay();
        });
    }

    const pid = project.project_id;
    const reload = async () => {
        await loadProject(pid, currentMode());
        renderAll();
    };

    root.querySelector("#pixellab-create-4")?.addEventListener("click", async () => {
        if (!selId || state.pixellabCreateCharacterBusy) return;
        await runPixellabCreateCharacter(pid, selId, 4);
    });
    root.querySelector("#pixellab-create-8")?.addEventListener("click", async () => {
        if (!selId || state.pixellabCreateCharacterBusy) return;
        await runPixellabCreateCharacter(pid, selId, 8);
    });
    root.querySelector("#pixellab-use-east-source")?.addEventListener("click", async () => {
        if (!selId || state.pixellabCreateCharacterBusy) return;
        try {
            await api(`/api/projects/${pid}/pixellab/use-concept-character`, {
                method: "POST",
                body: JSON.stringify({ concept_id: selId }),
            });
            notify("Using the chosen concept directly as the east-facing character source.", "success");
            await reload();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    root.querySelector("#pixellab-estimate-sk")?.addEventListener("click", async () => {
        try {
            if (!paidActionAllowed("Estimate skeleton via Pixel Lab")) return;
            notify("Estimating skeleton on east frame…", "info");
            await api(`/api/projects/${pid}/pixellab/estimate-skeleton`, {
                method: "POST",
                body: JSON.stringify({ direction: "east" }),
            });
            notify("Skeleton saved.", "success");
            await reload();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
    root.querySelector("#pixellab-approve-char")?.addEventListener("click", async () => {
        try {
            await api(`/api/projects/${pid}/pixellab/approve-character`, { method: "POST", body: "{}" });
            notify("Character approved for animations.", "success");
            await reload();
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    });
}

function clearPixellabAnimTimer(clipName) {
    const t = state.pixellabAnimTimers?.[clipName];
    if (t != null) window.clearInterval(t);
    if (state.pixellabAnimTimers && Object.prototype.hasOwnProperty.call(state.pixellabAnimTimers, clipName)) {
        delete state.pixellabAnimTimers[clipName];
    }
}

async function withPixellabAnimationProgress(pid, run, options) {
    const {
        detail = "Generating animation…",
        estimatedMs = 360000,
        jobType = "pixellab.animation",
        label = "Pixel Lab animation",
    } = options || {};
    state.pixellabAnimGenBusy = { detail, estimatedMs, jobType };
    renderPixellabAnimationsBoard();
    setActivity({
        state: "Working",
        jobType,
        label,
        detail,
        percent: 6,
    });
    const board = () => document.querySelector("#pixellab-animations-board");
    let fill = board()?.querySelector("[data-pixellab-anim-progress-fill]");
    let pctText = board()?.querySelector("[data-pixellab-anim-progress-pct]");
    const started = Date.now();
    const tick = window.setInterval(() => {
        const elapsed = Date.now() - started;
        const pct = Math.min(92, 6 + (elapsed / estimatedMs) * 86);
        if (fill) fill.style.width = `${pct}%`;
        if (pctText) pctText.textContent = `${Math.round(pct)}%`;
        if (state.activity && state.activity.jobType === jobType) {
            setActivity({ ...state.activity, percent: pct, detail });
        }
    }, 350);
    try {
        const result = await run();
        if (state.activity && state.activity.jobType === jobType) {
            setActivity({ ...state.activity, state: "Done", detail: "Finishing…", percent: 100 });
        }
        fill = board()?.querySelector("[data-pixellab-anim-progress-fill]");
        pctText = board()?.querySelector("[data-pixellab-anim-progress-pct]");
        if (fill) fill.style.width = "100%";
        if (pctText) pctText.textContent = "100%";
        await new Promise((r) => setTimeout(r, 200));
        return result;
    } finally {
        window.clearInterval(tick);
        state.pixellabAnimGenBusy = null;
        clearActivity();
        renderPixellabAnimationsBoard();
    }
}

function renderPixellabAnimationsBoard() {
    const root = document.querySelector("#pixellab-animations-board");
    if (!root) return;
    const project = state.activeProject;
    const prevAnims = project?.pixellab_animations?.animations || {};
    sortPixellabAnimationNames(Object.keys(prevAnims)).forEach((clipName) => clearPixellabAnimTimer(clipName));
    root.innerHTML = "";
    if (!project) {
        renderPixellabAnimationsPrimaryAction(null);
        root.innerHTML = `<div class="empty">Open a project to manage Pixel Lab animations.</div>`;
        return;
    }
    if (String(project.brief?.backend_mode || "") !== "pixellab") {
        renderPixellabAnimationsPrimaryAction(project);
        root.innerHTML = pixellabBackendModeMismatchBox(project.brief?.backend_mode);
        wirePixellabSwitchBackendButton(root);
        return;
    }
    if (!pixellabCharacterApproved(project)) {
        renderPixellabAnimationsPrimaryAction(project);
        root.innerHTML = `<div class="warning-box"><p>Approve and lock a concept source first in Concepts. That locked east-facing source becomes the animation input.</p></div>`;
        return;
    }
    const store = project.pixellab_animations || { animations: {} };
    const anims = store.animations || {};
    const clipsBridge = project.animation_clips || {};
    const existingClipNames = sortPixellabAnimationNames(Object.keys(anims));
    const clipsBridgeBits = existingClipNames
        .map((name) => {
            const count = Array.isArray(clipsBridge[name]?.frames) ? clipsBridge[name].frames.length : null;
            return count != null ? `${escapeHtml(name)}: ${count}` : null;
        })
        .filter(Boolean);
    const clipsBridgeHtml = clipsBridgeBits.length
        ? `<p class="small-note" style="margin-top:8px;"><strong>Export bridge (<code>animation_clips.json</code>):</strong> ${clipsBridgeBits.join(" · ")}. Synced automatically from your current generated clips.</p>`
        : `<p class="small-note" style="margin-top:8px;"><strong>Export bridge:</strong> The workbench syncs <code>animation_clips.json</code> automatically from whatever generated clips currently exist.</p>`;
    renderPixellabAnimationsPrimaryAction(project, { existingClipNames, clipsBridge });
    const dirList = project.pixellab_character?.directions;
    const pid = project.project_id;
    const reload = async () => {
        await loadProject(pid, currentMode());
        renderAll();
    };
    const previewServeNote =
        window.location.protocol === "file:"
            ? `<div class="warning-box" style="margin-bottom:12px;"><p><strong>Previews need the dev server.</strong> Frame thumbnails load from <code>http://127.0.0.1:${DEFAULT_WORKBENCH_PORT}/…</code>. Open the tool from that URL (not <code>file://</code>) if images stay blank or never update.</p></div>`
            : "";
    const animBusy = Boolean(state.pixellabAnimGenBusy);
    const animBusyDetail = animBusy ? escapeHtml(String(state.pixellabAnimGenBusy.detail || "Working…")) : "";
    const animProgressBlock = animBusy
        ? `<div class="pixellab-char-progress pixellab-anim-gen-progress workbench-waitbar" role="status" aria-live="polite" aria-busy="true" style="margin-bottom:14px;">
            <div class="small-note workbench-waitbar-detail"><strong>${animBusyDetail}</strong> — this can take several minutes while Pixel Lab renders (especially for all directions).</div>
            <div class="progress-track">
                <div class="progress-fill" data-pixellab-anim-progress-fill style="width:6%"></div>
            </div>
            <div class="progress-meta">
                <span data-pixellab-anim-progress-pct>6%</span>
                <span class="small-note">Progress is estimated until the server finishes.</span>
            </div>
        </div>`
        : "";
    const composerPresetOptions = [
        ...PIXELLAB_COMMON_ANIMATION_PRESETS.map((preset) => `<option value="${escapeHtml(preset.clipName)}">${escapeHtml(preset.label)}</option>`),
        `<option value="__custom__">Custom</option>`,
    ].join("");
    const initialPreset = PIXELLAB_COMMON_ANIMATION_PRESETS[0];

    function clipCard(clipName) {
        const meta = anims[clipName] || {};
        const previewDefault = pixellabFirstPreviewDirection(dirList, meta);
        const dis = animBusy ? " disabled" : "";
        const dirOptions = (dirList && dirList.length ? dirList : ["east"])
            .map((dir) => {
                const has = pixellabDirectionHasFramesInEntry(meta, dir);
                const label = `${humanizeKey(dir)}${has ? "" : " (no frames)"}`;
                return `<option value="${escapeHtml(dir)}"${dir === previewDefault ? " selected" : ""}>${escapeHtml(label)}</option>`;
            })
            .join("");
        const preset = pixellabAnimationPresetByName(clipName);
        const isCommon = Boolean(preset);
        const subtitle = isCommon
            ? `Common animation <code>${escapeHtml(clipName)}</code> with a reusable motion prompt.`
            : `Custom animation <code>${escapeHtml(clipName)}</code> — included in <code>animation_clips.json</code> automatically when frames exist.`;
        const defaultActionPlaceholder = preset?.prompt || "e.g. heavy overhead slash";
        const actionLabel = isCommon ? "Motion description" : "Custom motion description";
        return `
        <details class="pixellab-clip-details clip-control-card" data-pixellab-clip-details="${escapeHtml(clipName)}" style="margin-bottom:10px;">
            <summary class="pixellab-clip-summary">
                <span><strong>${escapeHtml(humanizeKey(clipName))}</strong> <span class="small-note">${isCommon ? "· common" : "· custom"}</span></span>
                <span class="pixellab-clip-chevron small-note" aria-hidden="true">▾</span>
            </summary>
            <div class="pixellab-clip-details-body" style="margin-top:12px;border-top:1px solid var(--stroke);padding-top:12px;">
            <div class="small-note">${subtitle}</div>
            <label class="small-note" style="display:block;margin-top:14px;">${escapeHtml(actionLabel)}</label>
            <input type="text" class="pixellab-custom-action" data-clip="${escapeHtml(clipName)}" placeholder="${escapeHtml(defaultActionPlaceholder)}" style="width:100%;"${dis}>
            <div class="actions" style="margin-top:8px;">
                <button type="button" class="pixellab-gen-custom" data-clip="${escapeHtml(clipName)}"${dis}>Generate animation</button>
            </div>
            <label class="small-note" style="display:block;margin-top:14px;">Edit existing frames</label>
            <textarea class="pixellab-edit-desc" data-clip="${escapeHtml(clipName)}" rows="2" placeholder="Describe the change for Pixel Lab edit…" style="width:100%;"${dis}></textarea>
            <div class="actions" style="margin-top:8px;">
                <button type="button" class="secondary pixellab-edit-anim" data-clip="${escapeHtml(clipName)}"${dis}>Edit animation</button>
            </div>
            <div class="pixellab-anim-preview-wrap" style="margin-top:14px;">
                <div class="check-row wrap">
                    <span class="small-note">Preview direction</span>
                    <select class="pixellab-preview-dir" data-clip="${escapeHtml(clipName)}"${dis}>${dirOptions}</select>
                    <button type="button" class="secondary pixellab-preview-play" data-clip="${escapeHtml(clipName)}"${dis}>Play</button>
                    <button type="button" class="secondary pixellab-preview-stop" data-clip="${escapeHtml(clipName)}"${dis}>Stop</button>
                    <span class="small-note pixellab-preview-label" data-clip="${escapeHtml(clipName)}">—</span>
                </div>
                <img class="pixellab-preview-img" data-clip="${escapeHtml(clipName)}" alt="" onerror="this.alt='Preview failed to load'; this.style.outline='2px solid rgba(220,90,90,0.9)';" style="max-height:min(62vh,360px);min-height:160px;max-width:min(100%,420px);margin-top:8px;background:rgba(0,0,0,0.25);border-radius:8px;object-fit:contain;image-rendering:pixelated;">
                <div class="pixellab-anim-strip" data-clip="${escapeHtml(clipName)}" style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px;"></div>
            </div>
            </div>
        </details>`;
    }

    const existingCardsHtml = existingClipNames.map((clipName) => clipCard(clipName)).join("");

    root.innerHTML = `
        ${previewServeNote}
        ${animProgressBlock}
        <div class="stage-primary-grid animations-stage-layout" style="margin-bottom:14px;">
            <div class="stage-card">
                <div class="stage-card-head">
                    <h4>Create animation</h4>
                    <p class="small-note">Choose a common animation to prefill the motion prompt, or change the name and description to create your own.</p>
                </div>
                <label class="small-note" style="display:block;">Common animation preset</label>
                <select id="pixellab-animation-preset"${animBusy ? " disabled" : ""}>${composerPresetOptions}</select>
                <label class="small-note" style="display:block;">Animation name</label>
                <input type="text" id="pixellab-animation-name" value="${escapeHtml(initialPreset.clipName)}" maxlength="48" autocomplete="off"
                    style="width:100%;padding:8px;border-radius:8px;border:1px solid var(--stroke);background:var(--panel);color:inherit;"${animBusy ? " disabled" : ""}>
                <label class="small-note" style="display:block;">Motion description</label>
                <textarea id="pixellab-animation-description" rows="3" style="width:100%;"${animBusy ? " disabled" : ""}>${escapeHtml(initialPreset.prompt)}</textarea>
                <div class="actions" style="margin-top:4px;">
                    <button type="button" id="pixellab-generate-animation"${animBusy ? " disabled" : ""}>Generate animation</button>
                </div>
                <p class="small-note">Generated clips are synced into <code>animation_clips.json</code> automatically for review, checks, and export.</p>
                ${clipsBridgeHtml}
            </div>
        </div>
        <div class="animations-main-stack">
            <div class="stage-card">
                <div class="stage-card-head">
                    <h4>Existing animations</h4>
                    <p class="small-note">${existingClipNames.length ? "Open any clip to regenerate, edit, or preview it." : "Generate your first animation above to start building the set."}</p>
                </div>
                <div class="pixellab-anim-clips-stack compact-panel-stack">
                    ${existingCardsHtml || `<div class="empty">No animations yet.</div>`}
                </div>
            </div>
        </div>
    `;

    root.querySelectorAll("details[data-pixellab-clip-details]").forEach((det) => {
        const clipName = det.getAttribute("data-pixellab-clip-details") || "";
        const key = `pixellab_anim_open_${pid}_${clipName}`;
        const saved = storage.getItem(key);
        if (saved === "1") det.open = true;
        else if (saved === "0") det.open = false;
        else det.open = clipName === existingClipNames[0];
        det.addEventListener("toggle", () => {
            storage.setItem(key, det.open ? "1" : "0");
        });
    });

    function fillStrip(clipName, direction) {
        const urls = pixellabPreviewFrameUrls(project, clipName, direction);
        const strip = root.querySelector(`.pixellab-anim-strip[data-clip="${clipName}"]`);
        const img = root.querySelector(`.pixellab-preview-img[data-clip="${clipName}"]`);
        if (!strip || !img) return;
        strip.innerHTML = urls.map((url, index) => `<img src="${url}" alt="f${index}" title="Frame ${index}" loading="lazy" onerror="this.style.boxShadow='inset 0 0 0 2px rgba(255,100,100,0.8)'; this.alt='×';" style="width:72px;height:72px;object-fit:contain;background:rgba(0,0,0,0.2);border-radius:6px;image-rendering:pixelated;">`).join("");
        img.src = urls[0] || "";
        const lab = root.querySelector(`.pixellab-preview-label[data-clip="${clipName}"]`);
        if (lab) lab.textContent = urls.length ? `0 / ${urls.length}` : "No frames";
    }

    async function syncPixellabCanonicalClips() {
        await api(`/api/projects/${pid}/pixellab/build-clips`, { method: "POST", body: "{}" });
    }

    existingClipNames.forEach((clipName) => {
        const dirSel = root.querySelector(`.pixellab-preview-dir[data-clip="${clipName}"]`);
        const direction = dirSel?.value || "east";
        fillStrip(clipName, direction);
        dirSel?.addEventListener("change", () => fillStrip(clipName, dirSel.value));
    });

    const presetSelect = root.querySelector("#pixellab-animation-preset");
    const nameInput = root.querySelector("#pixellab-animation-name");
    const descriptionInput = root.querySelector("#pixellab-animation-description");
    presetSelect?.addEventListener("change", () => {
        if (!nameInput || !descriptionInput) return;
        if (presetSelect.value === "__custom__") {
            nameInput.value = "";
            descriptionInput.value = "";
            return;
        }
        const preset = pixellabAnimationPresetByName(presetSelect.value);
        if (!preset) return;
        nameInput.value = preset.clipName;
        descriptionInput.value = preset.prompt;
    });

    async function generatePixellabAnimation(clip, action) {
        if (!paidActionAllowed(`Generate ${clip} animation`)) return;
        notify(`Generating ${clip}…`, "info");
        await withPixellabAnimationProgress(
            pid,
            () => api(`/api/projects/${pid}/pixellab/animate-custom`, {
                method: "POST",
                body: JSON.stringify({ animation_name: clip, action }),
            }),
            {
                detail: `${humanizeKey(clip)} (east-facing)`,
                estimatedMs: 420000,
                jobType: "pixellab.animate_custom",
                label: `Pixel Lab: ${clip}`,
            },
        );
        await syncPixellabCanonicalClips();
    }

    root.querySelector("#pixellab-generate-animation")?.addEventListener("click", async () => {
        const clip = normalizePixellabCustomAnimName(nameInput?.value || "");
        const action = descriptionInput?.value?.trim() || "";
        if (!clip) {
            notify("Enter a valid animation name: start with a letter; only a-z, 0-9, underscore; max 48 chars.", "error");
            return;
        }
        if (!action) {
            notify("Enter a motion description.", "error");
            return;
        }
        try {
            await generatePixellabAnimation(clip, action);
            notify(`${humanizeKey(clip)} animation saved.`, "success");
            await reload();
        } catch (error) {
            notify(normalizeErrorMessage(error.message), "error");
        }
    });

    root.querySelectorAll(".pixellab-gen-custom").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const clip = btn.dataset.clip;
            const input = root.querySelector(`.pixellab-custom-action[data-clip="${clip}"]`);
            const action = input?.value?.trim();
            if (!action) {
                notify("Enter a motion description.", "error");
                return;
            }
            try {
                await generatePixellabAnimation(clip, action);
                notify(`${humanizeKey(clip)} animation saved.`, "success");
                await reload();
            } catch (error) {
                notify(normalizeErrorMessage(error.message), "error");
            }
        });
    });

    root.querySelectorAll(".pixellab-edit-anim").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const clip = btn.dataset.clip;
            const textarea = root.querySelector(`.pixellab-edit-desc[data-clip="${clip}"]`);
            const description = textarea?.value?.trim();
            if (!description) {
                notify("Enter an edit description.", "error");
                return;
            }
            try {
                if (!paidActionAllowed(`Edit ${clip} animation`)) return;
                notify(`Editing ${clip} animation…`, "info");
                await withPixellabAnimationProgress(
                    pid,
                    () => api(`/api/projects/${pid}/pixellab/edit-animation`, {
                        method: "POST",
                        body: JSON.stringify({ animation_name: clip, description }),
                    }),
                    {
                        detail: `Editing ${clip} frames`,
                        estimatedMs: 420000,
                        jobType: "pixellab.edit_animation",
                        label: `Pixel Lab: edit ${clip}`,
                    },
                );
                await syncPixellabCanonicalClips();
                notify(`${clip} edit applied.`, "success");
                await reload();
            } catch (error) {
                notify(normalizeErrorMessage(error.message), "error");
            }
        });
    });

    root.querySelectorAll(".pixellab-preview-play").forEach((btn) => {
        btn.addEventListener("click", () => {
            const clip = btn.dataset.clip;
            const dirSel = root.querySelector(`.pixellab-preview-dir[data-clip="${clip}"]`);
            const urls = pixellabPreviewFrameUrls(state.activeProject, clip, dirSel?.value || "east");
            const img = root.querySelector(`.pixellab-preview-img[data-clip="${clip}"]`);
            const lab = root.querySelector(`.pixellab-preview-label[data-clip="${clip}"]`);
            const meta = state.activeProject?.pixellab_animations?.animations?.[clip];
            const fps = Number(meta?.fps) || 12;
            if (!urls.length || !img) {
                notify("No frames for this clip/direction — generate the animation first.", "error");
                return;
            }
            clearPixellabAnimTimer(clip);
            let idx = 0;
            img.src = urls[0];
            if (lab) lab.textContent = `1 / ${urls.length}`;
            state.pixellabAnimTimers = state.pixellabAnimTimers || {};
            state.pixellabAnimTimers[clip] = window.setInterval(() => {
                idx = (idx + 1) % urls.length;
                img.src = urls[idx];
                if (lab) lab.textContent = `${idx + 1} / ${urls.length}`;
            }, Math.max(40, Math.round(1000 / fps)));
        });
    });

    root.querySelectorAll(".pixellab-preview-stop").forEach((btn) => {
        btn.addEventListener("click", () => {
            clearPixellabAnimTimer(btn.dataset.clip);
        });
    });
}

function renderPixellabAnimationsPrimaryAction(project, context = {}) {
    const note = document.querySelector("#animations-stage-note");
    const button = document.querySelector("#confirm-animations-step");
    if (!note || !button) return;

    const backendMode = String(project?.brief?.backend_mode || "");
    const clipsBridge = context.clipsBridge || project?.animation_clips || {};
    const generatedClipNames = (context.existingClipNames || sortPixellabAnimationNames(Object.keys(project?.pixellab_animations?.animations || {})))
        .filter((name) => pixellabAnyDirectionHasFrames((project?.pixellab_animations?.animations || {})[name]));
    const syncedClipNames = Object.keys(clipsBridge).filter((name) => Array.isArray(clipsBridge[name]?.frames) && clipsBridge[name].frames.length);
    const ready = generatedClipNames.length > 0 || syncedClipNames.length > 0;

    button.disabled = true;
    if (!project) {
        note.textContent = "Open a project to continue the animation stage.";
        return;
    }
    if (backendMode !== "pixellab") {
        note.textContent = "Switch this project to Pixel Lab mode if you want to use the current animation flow.";
        return;
    }
    if (!pixellabCharacterApproved(project)) {
        note.textContent = "Approve and lock a concept source in Concepts before continuing here.";
        return;
    }

    if (!ready) {
        note.textContent = "Create at least one clip, then confirm this step to continue.";
        return;
    }

    const generatedSummary = generatedClipNames.length
        ? `${generatedClipNames.length} generated clip${generatedClipNames.length === 1 ? "" : "s"}`
        : `${syncedClipNames.length} synced clip${syncedClipNames.length === 1 ? "" : "s"}`;
    note.textContent = `${generatedSummary} ready. Confirm this step to continue.`;
    button.disabled = false;
}

document.querySelector("#confirm-animations-step")?.addEventListener("click", async () => {
    if (!state.activeProject) return;
    try {
        await persistWizardState({
            completed_steps: ["animations"],
            current_step: "export",
            last_ui_mode: "wizard",
        });
        renderAll();
        document.getElementById("panel-scroll").scrollTop = 0;
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

function renderAiCharacterLockBoard() {
    /* Phase 7.2: Character Lock panel removed; server may still persist ai_workflow character_lock data. */
}

function renderAiKeyPoseBoard() {
    /* Phase 7.2: Key Pose Board panel removed. */
}
