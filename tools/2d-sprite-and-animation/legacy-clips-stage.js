function renderRigReview() {
    const rig = state.activeProject?.rig;
    const summary = document.querySelector("#rig-summary");
    const preview = document.querySelector("#rig-preview");
    if (!rig) {
        summary.innerHTML = `<div class="empty">No rig data yet.</div>`;
        preview.innerHTML = "";
        return;
    }
    summary.innerHTML = "";
    [
        ["Source mode", rig.source_mode],
        ["Prop attachment", rig.prop_attachment_joint],
        ["Approved for production", rig.approved_for_production ? "yes" : "no"],
        ["Joint count", rig.joints?.length || 0],
        ["Pivot map entries", Object.keys(rig.pivot_map || {}).length],
        ["Foot anchors", `${rig.foot_anchor_reference?.left?.join(", ") || "n/a"} · ${rig.foot_anchor_reference?.right?.join(", ") || "n/a"}`],
    ].forEach(([label, value]) => {
        const row = document.createElement("div");
        row.className = "check-row wrap";
        row.innerHTML = `<span>${label}</span><span class="small-note">${value}</span>`;
        summary.appendChild(row);
    });
    const jointMarkers = Object.entries(rig.rig_joint_map || {})
        .map(([name, point]) => `<div class="overlay-pivot" title="${name}" style="left:${(point[0] / 640) * 100}%;top:${(point[1] / 768) * 100}%;"></div>`)
        .join("");
    const propPoint = rig.rig_joint_map?.[rig.prop_attachment_joint];
    const propMarker = propPoint
        ? `<div class="overlay-pivot prop" title="prop attachment" style="left:${(propPoint[0] / 640) * 100}%;top:${(propPoint[1] / 768) * 100}%;"></div>`
        : "";
    const approvedSource = approvedConceptSourcePath(state.activeProject);
    preview.innerHTML = `
        <div class="grid-2">
            <div class="preview-card overlay-stack">
                <img src="${approvedSource}?v=${state.activeProject.updated_at}" alt="Approved concept source">
                ${jointMarkers}
                ${propMarker}
            </div>
            <div class="thumb">
                <img src="${projectAsset(state.activeProject, rig.neutral_pose_render)}?v=${state.activeProject.updated_at}" alt="Neutral pose">
                <div class="small-note" style="margin-top: 8px;">neutral pose</div>
            </div>
        </div>
    `;
}

function renderClipSummary() {
    const root = document.querySelector("#clip-summary");
    root.innerHTML = "";
    const project = state.activeProject;
    if (!project) {
        root.innerHTML = `<div class="empty">Open a project to inspect clip settings.</div>`;
        return;
    }
    if (externalAuthoringEnabled(project)) {
        const bundle = externalAuthoringBundle(project);
        root.innerHTML = `
            <div class="check-row wrap">
                <span>External authoring mode</span>
                <span class="small-note">SkelForm replaces the legacy split, rig, and manual pose authoring workflow for this project.</span>
            </div>
            <div class="check-row wrap">
                <span>Imported bundle</span>
                <span class="small-note">${bundle ? `${bundle.animation_names?.length || 0} animation(s) · ${bundle.frame_count || 0} atlas frame(s)` : "No SkelForm export bundle imported yet."}</span>
            </div>
        `;
        return;
    }
    const clips = project.animation_clips || {};
    ["idle", "walk"].forEach((name) => {
        const clip = clips[name];
        const row = document.createElement("div");
        row.className = "check-row wrap";
        row.innerHTML = clip ? `
            <span>${humanizeKey(name)} clip</span>
            <span class="small-note">${clip.frame_count} frames · ${clip.fps} fps · ${clip.root_motion_policy} root · ${project.build_status?.[`${name}_render_complete`] ? "built" : "pending"} · bob ${clip.controls?.body_bob ?? "n/a"} · arm ${clip.controls?.arm_swing ?? "n/a"}</span>
        ` : `
            <span>${humanizeKey(name)} clip</span>
            <span class="small-note">No clip data yet.</span>
        `;
        root.appendChild(row);
    });
    manualClipList(project).forEach((clip) => {
        const row = document.createElement("div");
        row.className = "check-row wrap";
        row.innerHTML = `
            <span>Manual: ${clip.clip_name}</span>
            <span class="small-note">
                ${clip.frame_count} frames · ${clip.fps} fps · ${clip.loop ? "loop" : "one-shot"} ·
                ${clip.preview_render_complete ? "preview ready" : "preview pending"} ·
                ${clip.approval_status || "draft"}${clip.is_stale ? " · stale" : ""}
            </span>
        `;
        root.appendChild(row);
    });
}

function renderClipEditor() {
    const editorRoot = document.querySelector("#clip-editor");
    const previewRoot = document.querySelector("#clip-preview");
    editorRoot.innerHTML = "";
    previewRoot.innerHTML = "";
    const project = state.activeProject;
    if (externalAuthoringEnabled(project)) {
        const store = externalAuthoringStore(project);
        const bundle = externalAuthoringBundle(project);
        editorRoot.innerHTML = `
            <div class="clip-editor-card">
                <div class="check-row wrap">
                    <span>SkelForm Studio</span>
                    <span class="small-note">${store?.provider_profile?.license || "MIT"} · hosted editor embed</span>
                </div>
                <div class="small-note" style="margin-top: 8px;">
                    This project is using the browser-embedded SkelForm path. The old deterministic clip controls are replaced by external skeletal authoring plus import/export normalization.
                </div>
                <div class="actions" style="margin-top: 12px;">
                    <button id="open-skelform-session">Open SkelForm Session</button>
                    <button class="secondary" id="disable-skelform-session">Return To Legacy Pipeline</button>
                </div>
                <div class="check-list" style="margin-top: 12px;">
                    <div class="check-row"><span>Docs</span><a href="${store?.provider_profile?.docs_url || "#"}" target="_blank">open</a></div>
                    <div class="check-row"><span>Imported bundle</span><span class="small-note">${bundle ? bundle.source_label || "ready" : "pending import"}</span></div>
                </div>
            </div>
        `;
        previewRoot.innerHTML = bundle?.preview_gif_path
            ? `<div class="preview-card skelform-bundle-gif"><img src="${projectAsset(project, bundle.preview_gif_path)}?v=${project.updated_at}" alt="Imported SkelForm preview"><div class="small-note" style="margin-top: 8px;">Imported preview GIF</div></div>`
            : `<div class="empty">Import a SkelForm bundle to preview its GIF here.</div>`;
        const openButton = editorRoot.querySelector("#open-skelform-session");
        if (openButton) openButton.onclick = async () => {
            try {
                await api(`/api/projects/${project.project_id}/external-authoring/session`, {
                    method: "POST",
                    body: JSON.stringify({ provider: "skelform" }),
                });
                await loadProject(project.project_id, currentMode());
                notify("Opened the embedded SkelForm session for this project.", "success");
            } catch (error) {
                log(normalizeErrorMessage(error.message), "error");
                notify(normalizeErrorMessage(error.message), "error");
            }
        };
        const disableButton = editorRoot.querySelector("#disable-skelform-session");
        if (disableButton) disableButton.onclick = async () => {
            try {
                await api(`/api/projects/${project.project_id}/external-authoring/update`, {
                    method: "POST",
                    body: JSON.stringify({ enabled: false, provider: "skelform" }),
                });
                await loadProject(project.project_id, currentMode());
                notify("Returned this project to the legacy deterministic pipeline.", "success");
            } catch (error) {
                log(normalizeErrorMessage(error.message), "error");
                notify(normalizeErrorMessage(error.message), "error");
            }
        };
        return;
    }
    const clip = currentClipData();
    if (!project || !clip) {
        editorRoot.innerHTML = `<div class="empty">Build the rig to author idle and walk clips.</div>`;
        previewRoot.innerHTML = `<div class="empty">Neutral pose and rendered frame previews will appear here.</div>`;
        return;
    }

    clampSelectedClipFrame();
    const frame = currentClipFrameData() || {};
    const frameOverrides = clip.frame_overrides || Array.from({ length: clip.frame_count || 0 }, () => ({}));
    const activeFrameOverride = frameOverrides[state.selectedClipFrame] || {};
    const clipParts = clipEditorParts(project);
    const selectedClipPart = selectedClipEditorPart(project);
    const selectedBinding = clipPartOverrideBinding(selectedClipPart, project);
    const neutralPosePath = project.rig?.neutral_pose_render ? `${projectAsset(project, project.rig.neutral_pose_render)}?v=${project.updated_at}` : null;
    const builtFramePath = animationClipFramePreviewUrl(project, state.selectedClip, state.selectedClipFrame);

    editorRoot.innerHTML = `
        <div class="clip-editor-card">
            <div class="clip-tab-row">
                ${["idle", "walk"].map((name) => `
                    <button class="clip-tab ${state.selectedClip === name ? "active" : ""}" data-select-clip="${name}">${humanizeKey(name)}</button>
                `).join("")}
            </div>
            <div class="check-row wrap">
                <span>${humanizeKey(state.selectedClip)} frame scrubber</span>
                <span class="small-note">Frame ${state.selectedClipFrame + 1} of ${clip.frame_count}</span>
            </div>
            <label>
                <span class="field-label">Current Frame</span>
                <input id="clip-frame-scrubber" type="range" min="0" max="${Math.max(0, clip.frame_count - 1)}" step="1" value="${state.selectedClipFrame}">
            </label>
            <div class="clip-control-grid">
                ${Object.entries(CLIP_CONTROL_META).map(([key, meta]) => `
                    <div class="clip-control-card">
                        <div class="range-row">
                            <span class="field-label">${meta.label}</span>
                            <span class="range-value" data-range-value="${key}">${Number(clip.controls?.[key] ?? 0).toFixed(1)}</span>
                        </div>
                        <input type="range" data-clip-control="${key}" min="${meta.min}" max="${meta.max}" step="${meta.step}" value="${clip.controls?.[key] ?? 0}">
                    </div>
                `).join("")}
            </div>
            <div class="actions">
                <button id="save-clip-controls">Save ${humanizeKey(state.selectedClip)} Changes</button>
                <button class="secondary" id="clear-clip-frame-overrides">Clear Frame Overrides</button>
                <button class="secondary" id="reset-clip-controls">Reset ${humanizeKey(state.selectedClip)}</button>
                <button class="secondary" id="rebuild-neutral-pose">Rebuild Neutral Pose</button>
            </div>
            <div class="small-note">Clip controls update canonical <code>animation_clips.json</code>. Frame overrides below are generated dynamically from the current sprite parts and replace the selected frame's motion channels when saved.</div>
            <div class="clip-part-card">
                <div class="check-row wrap">
                    <span>${humanizeKey(state.selectedClip)} part selector</span>
                    <span class="small-note">${clipParts.length} dynamic option${clipParts.length === 1 ? "" : "s"} from the current sprite model</span>
                </div>
                <label>
                    <span class="field-label">Selected Part</span>
                    <select id="clip-part-select">
                        ${clipParts.map((part) => `
                            <option value="${part.part_name}" ${part.part_name === selectedClipPart?.part_name ? "selected" : ""}>
                                ${part.part_label || humanizeKey(part.part_name)}
                            </option>
                        `).join("")}
                    </select>
                </label>
                ${selectedClipPart ? `
                    <div class="check-row wrap">
                        <span><strong>${selectedClipPart.part_label || humanizeKey(selectedClipPart.part_name)}</strong></span>
                        <span class="pill">${selectedClipPart.part_name}</span>
                    </div>
                    <div class="small-note">
                        Role ${selectedClipPart.part_role || "n/a"} · parent joint ${selectedClipPart.parent_joint || "n/a"} · draw ${selectedClipPart.draw_order ?? "?"}
                    </div>
                    ${selectedBinding ? `
                        <div class="small-note">
                            Bound to <code>${selectedBinding.overrideKey}</code> for frame ${state.selectedClipFrame + 1}. Current ${Number(frame?.[selectedBinding.overrideKey] ?? 0).toFixed(2)}deg.
                        </div>
                        <label>
                            <span class="field-label">${selectedBinding.label} Override</span>
                            <input
                                type="number"
                                step="0.1"
                                id="clip-selected-part-override"
                                data-part-override-key="${selectedBinding.overrideKey}"
                                value="${typeof activeFrameOverride?.[selectedBinding.overrideKey] === "number" ? activeFrameOverride[selectedBinding.overrideKey] : ""}"
                                placeholder="${Number(frame?.[selectedBinding.overrideKey] ?? 0).toFixed(2)}"
                            >
                        </label>
                        <div class="small-note">Leave blank to keep the generated motion for this frame.</div>
                    ` : `
                        <div class="small-note">This part has no dedicated clip override channel yet, but it is still available as a dynamic selectable part in the Clips workflow.</div>
                    `}
                ` : `<div class="empty">No sprite parts available yet.</div>`}
            </div>
        </div>
    `;
    previewRoot.innerHTML = `
        <div class="detail-grid">
            <div class="comparison-grid">
                <div class="comparison-panel">
                    ${neutralPosePath ? `<img src="${neutralPosePath}" alt="Neutral pose">` : `<div class="empty">No neutral pose yet.</div>`}
                    <div class="small-note">Neutral pose</div>
                </div>
                <div class="comparison-panel">
                    ${builtFramePath ? `<img src="${builtFramePath}" alt="${state.selectedClip} frame ${state.selectedClipFrame + 1}">` : `<div class="empty">Render ${humanizeKey(state.selectedClip)} to preview this frame.</div>`}
                    <div class="small-note">${humanizeKey(state.selectedClip)} frame ${state.selectedClipFrame + 1}</div>
                </div>
            </div>
            <div class="frame-metrics">
                ${Object.entries(frame).map(([key, value]) => `
                    <div class="metric-chip">
                        <span class="small-note">${humanizeKey(key)}</span>
                        <strong>${Array.isArray(value) ? value.join(", ") : value}</strong>
                    </div>
                `).join("") || `<div class="empty">No frame data available.</div>`}
            </div>
        </div>
    `;

    editorRoot.querySelectorAll("[data-select-clip]").forEach((button) => {
        button.onclick = () => {
            state.selectedClip = button.dataset.selectClip;
            state.selectedClipFrame = 0;
            renderClipEditor();
            renderClipSummary();
        };
    });
    editorRoot.querySelector("#clip-frame-scrubber").oninput = (event) => {
        state.selectedClipFrame = Number(event.target.value || 0);
        renderClipEditor();
    };
    const clipPartSelect = editorRoot.querySelector("#clip-part-select");
    if (clipPartSelect) {
        clipPartSelect.onchange = (event) => {
            state.selectedClipPart = event.target.value || null;
            renderClipEditor();
        };
    }
    editorRoot.querySelectorAll("[data-clip-control]").forEach((input) => {
        input.oninput = () => {
            const valueNode = editorRoot.querySelector(`[data-range-value="${input.dataset.clipControl}"]`);
            if (valueNode) valueNode.textContent = Number(input.value || 0).toFixed(1);
        };
    });
    editorRoot.querySelector("#save-clip-controls").onclick = async () => {
        try {
            const controls = {};
            editorRoot.querySelectorAll("[data-clip-control]").forEach((input) => {
                controls[input.dataset.clipControl] = Number(input.value || 0);
            });
            const nextFrameOverrides = cloneJson(frameOverrides);
            const nextSelectedFrame = { ...(nextFrameOverrides[state.selectedClipFrame] || {}) };
            editorRoot.querySelectorAll("[data-part-override-key]").forEach((input) => {
                const key = input.dataset.partOverrideKey;
                const rawValue = String(input.value || "").trim();
                if (!rawValue.length) {
                    delete nextSelectedFrame[key];
                    return;
                }
                nextSelectedFrame[key] = Number(rawValue);
            });
            nextFrameOverrides[state.selectedClipFrame] = nextSelectedFrame;
            await api(`/api/projects/${project.project_id}/clips/${state.selectedClip}/update`, {
                method: "POST",
                body: JSON.stringify({ controls, frame_overrides: nextFrameOverrides }),
            });
            await loadProject(project.project_id, currentMode());
            notify(`Saved ${state.selectedClip} controls and frame overrides.`, "success");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    editorRoot.querySelector("#clear-clip-frame-overrides").onclick = async () => {
        try {
            const nextFrameOverrides = cloneJson(frameOverrides);
            nextFrameOverrides[state.selectedClipFrame] = {};
            await api(`/api/projects/${project.project_id}/clips/${state.selectedClip}/update`, {
                method: "POST",
                body: JSON.stringify({ frame_overrides: nextFrameOverrides }),
            });
            await loadProject(project.project_id, currentMode());
            notify(`Cleared frame ${state.selectedClipFrame + 1} overrides for ${state.selectedClip}.`, "success");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    editorRoot.querySelector("#reset-clip-controls").onclick = async () => {
        try {
            await api(`/api/projects/${project.project_id}/clips/${state.selectedClip}/reset`, { method: "POST", body: "{}" });
            await loadProject(project.project_id, currentMode());
            notify(`Reset ${state.selectedClip} to defaults.`, "success");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    editorRoot.querySelector("#rebuild-neutral-pose").onclick = async () => {
        try {
            await runJob(`/api/projects/${project.project_id}/rig/build`);
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
}

function renderAnimationGallery(name) {
    const root = document.querySelector(`#${name}-gallery`);
    root.innerHTML = "";
    const project = state.activeProject;
    if (!project) {
        clearClipLoopPreview(name);
        const previewRoot = document.querySelector(`#${name}-loop-preview`);
        if (previewRoot) previewRoot.innerHTML = "";
        return;
    }
    if (externalAuthoringEnabled(project)) {
        clearClipLoopPreview(name);
        const previewRoot = document.querySelector(`#${name}-loop-preview`);
        if (previewRoot) previewRoot.innerHTML = `<div class="small-note">Legacy ${humanizeKey(name)} frame previews are disabled while SkelForm authoring is active.</div>`;
        root.innerHTML = `<div class="empty">SkelForm bundle import replaces this gallery.</div>`;
        return;
    }
    const clip = project.animation_clips?.[name];
    const bridgeRels = pixellabAnimationClipFrameRels(project, name);
    if (bridgeRels) {
        const urls = bridgeRels.map((rel) => `${projectAsset(project, rel)}?v=${project.updated_at}`);
        const fps = clip?.fps || (name === "idle" ? 8 : 10);
        renderClipLoopPreview(name, urls.length, { frameUrls: urls, fps });
        bridgeRels.forEach((rel, index) => {
            const label = rel.split("/").pop() || `frame_${String(index).padStart(2, "0")}.png`;
            const thumb = document.createElement("div");
            thumb.className = "thumb";
            thumb.innerHTML = `
                <img src="${projectAsset(project, rel)}?v=${project.updated_at}" alt="${label}" onerror="this.parentElement.style.display='none'">
                <div class="small-note" style="margin-top: 8px;">${label}</div>
            `;
            root.appendChild(thumb);
        });
        return;
    }
    const count = clip?.frame_count || (name === "idle" ? 6 : 8);
    renderClipLoopPreview(name, count);
    for (let index = 0; index < count; index += 1) {
        const frame = `${name}_${String(index).padStart(2, "0")}.png`;
        const thumb = document.createElement("div");
        thumb.className = "thumb";
        thumb.innerHTML = `
            <img src="${projectAsset(project, `animations/${name}/${frame}`)}?v=${project.updated_at}" alt="${frame}" onerror="this.parentElement.style.display='none'">
            <div class="small-note" style="margin-top: 8px;">${frame}</div>
        `;
        root.appendChild(thumb);
    }
}

function clearClipLoopPreview(name) {
    if (state.clipPreviewTimers[name]) {
        window.clearInterval(state.clipPreviewTimers[name]);
        delete state.clipPreviewTimers[name];
    }
}

function renderClipLoopPreview(name, count, opts = {}) {
    const root = opts.root ?? document.querySelector(`#${name}-loop-preview`);
    const timerKey = opts.timerKey ?? name;
    clearClipLoopPreview(timerKey);
    if (!root) return;
    root.innerHTML = "";
    const project = state.activeProject;
    const frameUrls = opts.frameUrls;
    const n = frameUrls?.length || count;
    if (!project || !n) return;
    const fps =
        opts.fps ??
        project.animation_clips?.[name]?.fps ??
        (name === "idle" ? 8 : 10);
    const frames =
        frameUrls && frameUrls.length
            ? frameUrls
            : Array.from({ length: n }, (_, index) =>
                  `${projectAsset(project, `animations/${name}/${name}_${String(index).padStart(2, "0")}.png`)}?v=${project.updated_at}`
              );
    const preview = document.createElement("div");
    preview.className = "thumb";
    preview.style.maxWidth = "min(100%, 240px)";
    preview.innerHTML = `
        <img alt="${humanizeKey(name)} preview" style="display:block;width:100%;max-width:240px;max-height:min(32vh,220px);height:auto;object-fit:contain;margin-inline:auto;">
    `;
    const image = preview.querySelector("img");
    image.onerror = () => {
        clearClipLoopPreview(timerKey);
        root.innerHTML = "";
    };
    let frameIndex = 0;
    const paintFrame = () => {
        image.src = frames[frameIndex];
        frameIndex = (frameIndex + 1) % frames.length;
    };
    paintFrame();
    state.clipPreviewTimers[timerKey] = window.setInterval(paintFrame, Math.max(80, Math.round(1000 / fps)));
    root.appendChild(preview);
}
