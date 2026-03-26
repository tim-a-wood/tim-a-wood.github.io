function renderManualClipStudio() {
    const editorRoot = document.querySelector("#manual-clips-editor");
    const previewRoot = document.querySelector("#manual-clips-preview");
    const poseModal = document.querySelector("#manual-pose-modal");
    const poseModalContent = document.querySelector("#manual-pose-modal-content");
    if (!editorRoot || !previewRoot || !poseModal || !poseModalContent) return;
    editorRoot.innerHTML = "";
    previewRoot.innerHTML = "";
    poseModalContent.innerHTML = "";
    const project = state.activeProject;
    const studioLayout = editorRoot.closest(".manual-studio-layout");
    if (studioLayout) {
        studioLayout.classList.toggle("skelform-active", externalAuthoringEnabled(project));
    }
    if (externalAuthoringEnabled(project)) {
        const store = externalAuthoringStore(project);
        const bundle = externalAuthoringBundle(project);
        const embedUrl = store?.session?.embed_url || store?.session?.editor_url || store?.provider_profile?.editor_url || "https://skelform.org/editor/";
        editorRoot.innerHTML = `
            <div class="manual-clip-shell skelform-studio-shell">
                <div class="manual-clip-workspace skelform-editor-column">
                    <div class="clip-control-card skelform-embed-card">
                        <div class="check-row wrap">
                            <span>Embedded editor</span>
                            <span class="small-note">SkelForm hosted session</span>
                        </div>
                        <div class="small-note">The editor now uses the full workspace column. Bundle import stays in the side rail so the canvas can occupy most of the screen.</div>
                        <iframe class="skelform-embed-frame" src="${embedUrl}" title="SkelForm editor"></iframe>
                    </div>
                </div>
                <div class="manual-clip-sidebar">
                    <div class="clip-part-card skelform-import-card">
                        <div class="check-row wrap">
                            <span>Import SkelForm export bundle</span>
                            <span class="small-note">Spritesheet + atlas + animations are required.</span>
                        </div>
                        <label>
                            <span class="field-label">Bundle Label</span>
                            <input id="skelform-source-label" type="text" value="${bundle?.source_label || "SkelForm export"}">
                        </label>
                        <label>
                            <span class="field-label">Spritesheet PNG</span>
                            <input id="skelform-spritesheet-file" type="file" accept="image/png,image/*">
                            <input id="skelform-spritesheet-path" type="text" placeholder="/absolute/path/to/spritesheet.png">
                        </label>
                        <label>
                            <span class="field-label">Atlas JSON</span>
                            <input id="skelform-atlas-file" type="file" accept="application/json,.json">
                            <input id="skelform-atlas-path" type="text" placeholder="/absolute/path/to/atlas.json">
                        </label>
                        <label>
                            <span class="field-label">Animations JSON</span>
                            <input id="skelform-animations-file" type="file" accept="application/json,.json">
                            <input id="skelform-animations-path" type="text" placeholder="/absolute/path/to/animations.json">
                        </label>
                        <label>
                            <span class="field-label">Preview GIF (optional)</span>
                            <input id="skelform-preview-gif-file" type="file" accept="image/gif,image/*">
                            <input id="skelform-preview-gif-path" type="text" placeholder="/absolute/path/to/preview.gif">
                        </label>
                        <label>
                            <span class="field-label">Notes</span>
                            <textarea id="skelform-import-notes" placeholder="Optional notes about this export bundle.">${bundle?.notes || ""}</textarea>
                        </label>
                        <div class="actions">
                            <button id="import-skelform-bundle">Import Bundle</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        previewRoot.innerHTML = bundle ? `
            <div class="manual-context-stack">
                <div class="clip-control-card">
                    <div class="check-row wrap">
                        <span>Imported bundle</span>
                        <span class="small-note">${bundle.animation_names?.length || 0} animation(s) · ${bundle.frame_count || 0} atlas frame(s)</span>
                    </div>
                    <div class="check-list" style="margin-top: 10px;">
                        <div class="check-row"><span>Spritesheet</span><a href="${projectAsset(project, bundle.spritesheet_image_path)}" target="_blank">open</a></div>
                        <div class="check-row"><span>Atlas</span><a href="${projectAsset(project, bundle.atlas_path)}" target="_blank">open</a></div>
                        <div class="check-row"><span>Animations</span><a href="${projectAsset(project, bundle.animations_path)}" target="_blank">open</a></div>
                        ${bundle.preview_gif_path ? `<div class="check-row"><span>Preview GIF</span><a href="${projectAsset(project, bundle.preview_gif_path)}" target="_blank">open</a></div>` : ""}
                    </div>
                    ${bundle.preview_gif_path ? `<div class="preview-card skelform-bundle-gif" style="margin-top: 12px;"><img src="${projectAsset(project, bundle.preview_gif_path)}?v=${project.updated_at}" alt="SkelForm preview gif"><div class="small-note" style="margin-top: 8px;">${bundle.source_label || "Imported bundle"}</div></div>` : `<div class="small-note" style="margin-top: 12px;">No preview GIF imported yet.</div>`}
                </div>
            </div>
        ` : `<div class="empty">Import a SkelForm bundle to unlock QA and export.</div>`;
        const importButton = editorRoot.querySelector("#import-skelform-bundle");
        if (importButton) importButton.onclick = async () => {
            const readFileAsDataUrl = (file) => new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
                reader.readAsDataURL(file);
            });
            try {
                const spritesheetFile = editorRoot.querySelector("#skelform-spritesheet-file").files[0];
                const atlasFile = editorRoot.querySelector("#skelform-atlas-file").files[0];
                const animationsFile = editorRoot.querySelector("#skelform-animations-file").files[0];
                const previewGifFile = editorRoot.querySelector("#skelform-preview-gif-file").files[0];
                const payload = {
                    source_label: editorRoot.querySelector("#skelform-source-label").value.trim(),
                    notes: editorRoot.querySelector("#skelform-import-notes").value.trim(),
                    spritesheet_local_path: editorRoot.querySelector("#skelform-spritesheet-path").value.trim(),
                    atlas_local_path: editorRoot.querySelector("#skelform-atlas-path").value.trim(),
                    animations_local_path: editorRoot.querySelector("#skelform-animations-path").value.trim(),
                    preview_gif_local_path: editorRoot.querySelector("#skelform-preview-gif-path").value.trim(),
                };
                if (spritesheetFile) {
                    payload.spritesheet_name = spritesheetFile.name;
                    payload.spritesheet_data_url = await readFileAsDataUrl(spritesheetFile);
                }
                if (atlasFile) {
                    payload.atlas_name = atlasFile.name;
                    payload.atlas_data_url = await readFileAsDataUrl(atlasFile);
                }
                if (animationsFile) {
                    payload.animations_name = animationsFile.name;
                    payload.animations_data_url = await readFileAsDataUrl(animationsFile);
                }
                if (previewGifFile) {
                    payload.preview_gif_name = previewGifFile.name;
                    payload.preview_gif_data_url = await readFileAsDataUrl(previewGifFile);
                }
                await api(`/api/projects/${project.project_id}/external-authoring/import-bundle`, {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
                await loadProject(project.project_id, currentMode());
                notify("Imported the SkelForm bundle. QA and export now use the external-authoring adapter path.", "success");
            } catch (error) {
                log(normalizeErrorMessage(error.message), "error");
                notify(normalizeErrorMessage(error.message), "error");
            }
        };
        return;
    }
    const rig = project?.rig;
    if (!project || !rig) {
        closeManualPoseEditor();
        editorRoot.innerHTML = `<div class="empty">Build and approve the rig before authoring manual clips.</div>`;
        previewRoot.innerHTML = `<div class="empty">Manual clip GIF review will appear here.</div>`;
        return;
    }
    const clips = manualClipList(project);
    const clip = selectedManualClip(project);
    if (!clip && state.manualPoseModalOpen) closeManualPoseEditor();
    if (clip) clampSelectedManualClipFrame(project);
    const frame = currentManualClipFrame(project);
    const frameEntry = currentManualClipFrameEntry(project);
    const joints = computeManualPoseJoints(rig, frame || {});
    const handles = manualPoseHandles(project);
    const sourceImage = approvedConceptSourcePath(project);
    const previewFramePath = clip?.preview_render?.frames?.[state.selectedManualClipFrame]
        ? `${projectAsset(project, clip.preview_render.frames[state.selectedManualClipFrame])}?v=${project.updated_at}`
        : null;
    const previewGifPath = clip?.preview_render?.gif_path
        ? `${projectAsset(project, clip.preview_render.gif_path)}?v=${project.updated_at}`
        : null;
    const draftFrame = frameEntry || manualFrameEntry(frame || {});
    const frameAdjustments = manualFrameAdjustmentEntries(draftFrame);
    const frameAdjustmentMarkup = frameAdjustments.length
        ? frameAdjustments.map((item) => `
            <div class="manual-adjustment-row">
                <strong>${item.label}</strong>
                <span>${item.value}</span>
            </div>
        `).join("")
        : `<div class="empty">No manual offsets saved for this frame yet.</div>`;
    const statusLabel = clip
        ? `${clip.approval_status || "draft"}${clip.is_stale ? ` · stale (${(clip.stale_reasons || []).join(", ")})` : ""}`
        : "No clip selected";
    const selectedPatchSourcePart = selectedManualPatchSourcePart(project);
    const selectedPatchOccluder = selectedManualPatchOccluderPart(project);
    const appliedPatches = manualFramePatches(draftFrame);
    const appliedPatchMarkup = Object.values(appliedPatches).length
        ? Object.values(appliedPatches).map((patch) => `
            <div class="manual-adjustment-row">
                <strong>${humanizeKey(patch?.source_part_name || "part")}</strong>
                <span>${patch?.summary || patch?.variant_id || "gap patch"} · behind ${humanizeKey(patch?.keep_behind_part_name || "selected part")}</span>
            </div>
        `).join("")
        : `<div class="empty">No corrective patches applied on this frame.</div>`;
    const patchCandidateMarkup = state.manualPatchCandidates?.length
        ? state.manualPatchCandidates.map((candidate) => `
            <button class="secondary" data-manual-patch-variant="${candidate.variant_id}" style="justify-content: space-between;">
                <span>${candidate.summary || candidate.variant_id}</span>
                <span class="small-note">${candidate.variant_id}</span>
            </button>
        `).join("")
        : `<div class="small-note">Use the gap workflow below. The first patch is auto-applied, and you can swap to another generated variant afterward if needed.</div>`;
    const rigGuidance = rig?.rig_profile === "side_knight_simple_7"
        ? "This project is using the simplified side-view rig, so you get one arm/weapon chain and one front-leg chain instead of fully separate left/right limbs."
        : rig?.rig_profile === "side_knight_dual_leg_8"
            ? "This project is using the dual-leg side-view rig, so you can pose both front and back leg chains."
            : "This project is using the full rig profile, so left/right arms and legs can be posed independently.";
    const handleGuideMarkup = handles.length
        ? handles.map((handle) => `
            <div class="manual-adjustment-row">
                <strong>${handle.label}</strong>
                <span>${handle.mode === "translate" ? "move body" : humanizeKey(handle.channel || "rotation")}</span>
            </div>
        `).join("")
        : `<div class="empty">No pose handles are available until the rig is ready.</div>`;
    const livePreviewMarkup = manualPosePreviewMarkup(project, rig, draftFrame);
    const lineMarkup = handles
        .filter((handle) => handle.mode === "rotate" && joints[handle.parent] && joints[handle.child])
        .map((handle) => `
            <line class="manual-pose-line" x1="${joints[handle.parent][0]}" y1="${joints[handle.parent][1]}" x2="${joints[handle.child][0]}" y2="${joints[handle.child][1]}"></line>
        `)
        .join("");
    const handleMarkup = handles
        .map((handle) => {
            const point = handle.mode === "translate" ? joints[handle.joint] : joints[handle.child];
            if (!point) return "";
            return `
                <g data-manual-handle="${handle.id}">
                    <circle class="manual-pose-handle ${handle.mode === "translate" ? "root" : ""}" cx="${point[0]}" cy="${point[1]}" r="${handle.mode === "translate" ? 11 : 9}"></circle>
                    <text class="manual-pose-label" x="${point[0] + 12}" y="${point[1] - 12}">${handle.label}</text>
                </g>
            `;
        })
        .join("");
    editorRoot.innerHTML = `
        <div class="manual-clip-shell">
            <div class="manual-clip-sidebar">
                <div class="clip-control-card">
                    <div class="check-row wrap">
                        <span>Manual clip library</span>
                        <span class="small-note">${clips.length} named clip${clips.length === 1 ? "" : "s"}</span>
                    </div>
                    <div class="actions">
                        <input id="manual-clip-create-name" type="text" placeholder="New clip name">
                        <button id="manual-clip-create">Create Manual Clip</button>
                    </div>
                    ${clip ? `
                        <label>
                            <span class="field-label">Selected Clip</span>
                            <select id="manual-clip-select">
                                ${clips.map((item) => `<option value="${item.clip_id}" ${item.clip_id === clip.clip_id ? "selected" : ""}>${item.clip_name}</option>`).join("")}
                            </select>
                        </label>
                    ` : `<div class="small-note">Create your first manual clip to unlock the pose workspace.</div>`}
                </div>
                ${clip ? `
                    <div class="clip-part-card">
                        <div class="check-row wrap">
                            <span>Clip settings</span>
                            <span class="small-note">${statusLabel}</span>
                        </div>
                        <label>
                            <span class="field-label">Clip Name</span>
                            <input id="manual-clip-name" type="text" value="${clip.clip_name || ""}">
                        </label>
                        <label>
                            <span class="field-label">Frame Count</span>
                            <input id="manual-clip-frame-count" type="number" min="1" max="64" value="${clip.frame_count || 1}">
                        </label>
                        <label>
                            <span class="field-label">FPS</span>
                            <input id="manual-clip-fps" type="number" min="1" max="60" value="${clip.fps || 12}">
                        </label>
                        <label class="shape-editor-chip"><input id="manual-clip-loop" type="checkbox" ${clip.loop ? "checked" : ""}> Loop playback</label>
                        <div class="actions">
                            <button id="manual-clip-save-meta">Save Clip Meta</button>
                            <button class="secondary" id="open-manual-pose-editor">Open Pose Editor</button>
                        </div>
                    </div>
                ` : ""}
            </div>
            ${clip ? `
                <div class="manual-clip-workspace">
                    <div class="manual-clip-toolbar">
                        <div class="clip-part-card">
                            <span class="small-note">Selected frame</span>
                            <strong>F${state.selectedManualClipFrame + 1}</strong>
                        </div>
                        <div class="clip-part-card">
                            <span class="small-note">Clip status</span>
                            <strong>${clip.approval_status || "draft"}</strong>
                        </div>
                        <div class="clip-part-card">
                            <span class="small-note">Preview rendered</span>
                            <strong>${clip.preview_render_complete ? "Yes" : "No"}</strong>
                        </div>
                        <div class="clip-part-card">
                            <span class="small-note">Frame edits</span>
                            <strong>${frameAdjustments.length}</strong>
                        </div>
                    </div>
                    <div class="manual-pose-card manual-pose-launcher">
                        <div class="manual-stage-hint">
                            <div>
                                <strong>Dedicated pose editor</strong>
                                <div class="small-note">Open the larger popup workspace for joint dragging, timeline work, and frame context.</div>
                            </div>
                            <button class="secondary" id="open-manual-pose-editor-secondary">Open Large Editor</button>
                        </div>
                        ${sourceImage ? `<img src="${sourceImage}?v=${project.updated_at}" alt="Manual pose source preview">` : `<div class="empty">No approved source image.</div>`}
                        <div class="small-note">The manual pose editor now opens in its own popup so the source image and handles can use most of the screen.</div>
                    </div>
                </div>
            ` : `<div class="manual-pose-card"><div class="empty">Create a manual clip to start posing frames.</div></div>`}
        </div>
    `;
    previewRoot.innerHTML = clip ? `
        <div class="manual-context-stack">
            <div class="manual-preview-grid">
                <div class="comparison-panel manual-context-window">
                    ${previewGifPath && clip.preview_render_complete ? `<img src="${previewGifPath}" alt="${clip.clip_name} preview gif">` : `<div class="empty">Render a preview GIF to review the clip loop.</div>`}
                    <div class="small-note">${clip.clip_name} loop preview</div>
                </div>
                <div class="comparison-panel manual-context-window">
                    ${previewFramePath && clip.preview_render_complete ? `<img src="${previewFramePath}" alt="${clip.clip_name} frame ${state.selectedManualClipFrame + 1}">` : `<div class="empty">No rendered snapshot for the selected frame yet.</div>`}
                    <div class="small-note">Rendered frame F${state.selectedManualClipFrame + 1}</div>
                </div>
                <div class="manual-context-window">
                    <div class="check-row wrap">
                        <span>Selected frame context</span>
                        <span class="small-note">${frameAdjustments.length} stored adjustment${frameAdjustments.length === 1 ? "" : "s"}</span>
                    </div>
                    <div class="manual-adjustment-list">
                        ${frameAdjustmentMarkup}
                    </div>
                </div>
                <div class="frame-metrics">
                    <div class="metric-chip"><span class="small-note">Approval</span><strong>${clip.approval_status || "draft"}</strong></div>
                    <div class="metric-chip"><span class="small-note">Rendered</span><strong>${clip.preview_render_complete ? "yes" : "no"}</strong></div>
                    <div class="metric-chip"><span class="small-note">FPS</span><strong>${clip.fps || 12}</strong></div>
                    <div class="metric-chip"><span class="small-note">Frames</span><strong>${clip.frame_count || 0}</strong></div>
                </div>
            </div>
        </div>
    ` : `<div class="empty">Manual clip review will appear here.</div>`;
    poseModalContent.innerHTML = clip ? `
        <div class="manual-pose-modal-shell">
            <div class="modal-head">
                <div>
                    <h3 style="margin: 0; text-transform: uppercase; letter-spacing: 0.08em;">Manual Pose Editor</h3>
                    <p class="muted" style="margin: 8px 0 0;">${clip.clip_name} · Frame ${state.selectedManualClipFrame + 1} of ${clip.frame_count}</p>
                </div>
                <div class="actions">
                    <button id="manual-clip-capture-frame">Capture Frame</button>
                    <button class="secondary" id="manual-clip-render">Render Preview GIF</button>
                    <button class="secondary" id="manual-clip-approve">${clip.approval_status === "approved" ? "Unapprove" : "Approve"}</button>
                    <button class="secondary" id="close-manual-pose">Close</button>
                </div>
            </div>
            <div class="manual-pose-modal-body">
                <div class="manual-clip-workspace">
                    <div class="manual-pose-editor-grid">
                        <div class="manual-pose-card">
                            <div class="manual-stage-hint">
                                <div>
                                    <strong>Pose workspace</strong>
                                    <div class="small-note">Drag labeled joints directly on the source image, then capture the frame.</div>
                                </div>
                                <div class="small-note">1. Pick a frame 2. Drag controls 3. Press Capture Frame 4. Move to the next frame.</div>
                            </div>
                            <div class="manual-pose-stage" id="manual-pose-stage-modal">
                                ${sourceImage ? `<img src="${sourceImage}?v=${project.updated_at}" alt="Manual pose source">` : `<div class="empty">No approved source image.</div>`}
                                <svg viewBox="0 0 ${SPRITE_EDITOR_SIZE.width} ${SPRITE_EDITOR_SIZE.height}" aria-hidden="true">
                                    ${lineMarkup}
                                    ${handleMarkup}
                                </svg>
                            </div>
                        </div>
                        <div class="manual-pose-card">
                            <div class="manual-stage-hint">
                                <div>
                                    <strong>Live pose preview</strong>
                                    <div class="small-note">This is the character composition that updates as you pose the rig.</div>
                                </div>
                                <div class="small-note">Current draft for F${state.selectedManualClipFrame + 1}</div>
                            </div>
                            <div class="manual-pose-live-viewport" id="manual-pose-live-viewport">
                                <div id="manual-pose-live-preview-container" style="transform: translate(${state.manualPreviewPanX}px, ${state.manualPreviewPanY}px) scale(${state.manualPreviewZoom}); transform-origin: 0 0;">${livePreviewMarkup}</div>
                            </div>
                            <div class="actions" style="margin-top:6px;">
                                <button class="secondary" id="manual-preview-zoom-in" title="Zoom in">+</button>
                                <button class="secondary" id="manual-preview-zoom-out" title="Zoom out">−</button>
                                <button class="secondary" id="manual-preview-zoom-reset" title="Reset view">Reset</button>
                                <span class="small-note" style="margin-left:8px;">${Math.round(state.manualPreviewZoom * 100)}%</span>
                            </div>
                        </div>
                    </div>
                    <div class="clip-part-card">
                        <div class="check-row wrap">
                            <span>Timeline dock</span>
                            <span class="small-note">Frame ${state.selectedManualClipFrame + 1} of ${clip.frame_count}</span>
                        </div>
                        <div class="manual-frame-strip">
                            ${Array.from({ length: clip.frame_count }, (_, index) => `
                                <button class="manual-frame-chip ${index === state.selectedManualClipFrame ? "active" : ""} ${manualFrameHasEdits(clip.frames?.[index] || {}) ? "captured" : ""}" data-manual-frame="${index}">
                                    <div class="manual-frame-chip-preview">${manualPosePreviewMarkup(project, rig, clip.frames?.[index] || {}, { compact: true })}</div>
                                    <div class="manual-frame-chip-label">F${index + 1}</div>
                                </button>
                            `).join("")}
                        </div>
                        <div class="actions">
                            <button class="secondary" id="manual-clip-prev-frame">Previous Frame</button>
                            <button class="secondary" id="manual-clip-next-frame">Next Frame</button>
                            <button class="secondary" id="manual-clip-copy-prev">Copy Previous</button>
                            <button class="secondary" id="manual-clip-clear-frame">Clear Frame</button>
                        </div>
                    </div>
                </div>
                <div class="manual-pose-modal-rail">
                    <div class="manual-context-window">
                        <div class="check-row wrap">
                            <span>How to use</span>
                            <span class="small-note">Quick workflow</span>
                        </div>
                        <div class="small-note" style="margin-bottom: 8px;">${rigGuidance}</div>
                        <div class="manual-adjustment-list">
                            <div class="manual-adjustment-row"><strong>1</strong><span>Select a frame in the timeline.</span></div>
                            <div class="manual-adjustment-row"><strong>2</strong><span>Drag body controls in the large pose view.</span></div>
                            <div class="manual-adjustment-row"><strong>3</strong><span>Press Capture Frame to save the snapshot.</span></div>
                            <div class="manual-adjustment-row"><strong>4</strong><span>Repeat, then render the preview GIF.</span></div>
                        </div>
                    </div>
                    <div class="manual-context-window">
                        <div class="check-row wrap">
                            <span>Available controls</span>
                            <span class="small-note">${handles.length} total</span>
                        </div>
                        <div class="manual-adjustment-list">
                            ${handleGuideMarkup}
                        </div>
                    </div>
                    <div class="manual-context-window">
                        <div class="check-row wrap">
                            <span>Fix Exposed Gap</span>
                            <span class="small-note">${selectedPatchSourcePart?.part_name ? humanizeKey(selectedPatchSourcePart.part_name) : "no source part"}</span>
                        </div>
                        <div class="small-note">Use this when moving one part exposes missing pixels behind it. Example: fill from <strong>shield</strong>, keep the patch behind <strong>sword</strong>.</div>
                        <label>
                            <span class="field-label">1. Fill pixels from</span>
                            <select id="manual-patch-source-select">
                                ${manualPatchableParts(project).map((part) => `<option value="${part.part_name}" ${part.part_name === selectedPatchSourcePart?.part_name ? "selected" : ""}>${humanizeKey(part.part_name)}</option>`).join("")}
                            </select>
                        </label>
                        <label>
                            <span class="field-label">2. Keep patch behind</span>
                            <select id="manual-patch-occluder-select">
                                ${manualPatchOccluderParts(project, selectedPatchSourcePart?.part_name).map((part) => `<option value="${part.part_name}" ${part.part_name === selectedPatchOccluder?.part_name ? "selected" : ""}>${humanizeKey(part.part_name)}</option>`).join("")}
                            </select>
                        </label>
                        <div class="actions">
                            <button id="manual-patch-generate" ${(selectedPatchSourcePart && selectedPatchOccluder) ? "" : "disabled"}>${state.manualPatchBusy ? "Generating..." : "Create Gap Patch"}</button>
                            <button class="secondary" id="manual-patch-clear" ${selectedPatchSourcePart && appliedPatches[`patch:${selectedPatchSourcePart.part_name}`] ? "" : "disabled"}>Clear Patch</button>
                        </div>
                        <div class="manual-adjustment-list" style="margin-top: 8px;">
                            ${patchCandidateMarkup}
                        </div>
                    </div>
                    <div class="comparison-panel manual-context-window">
                        ${previewFramePath && clip.preview_render_complete ? `<img src="${previewFramePath}" alt="${clip.clip_name} frame ${state.selectedManualClipFrame + 1}">` : `<div class="empty">No rendered snapshot for the selected frame yet.</div>`}
                        <div class="small-note">Rendered frame F${state.selectedManualClipFrame + 1}</div>
                    </div>
                    <div class="manual-context-window">
                        <div class="check-row wrap">
                            <span>Patches on this frame</span>
                            <span class="small-note">${Object.keys(appliedPatches).length} applied</span>
                        </div>
                        <div class="manual-adjustment-list">
                            ${appliedPatchMarkup}
                        </div>
                    </div>
                    <div class="manual-context-window">
                        <div class="check-row wrap">
                            <span>Selected frame context</span>
                            <span class="small-note">${frameAdjustments.length} stored adjustment${frameAdjustments.length === 1 ? "" : "s"}</span>
                        </div>
                        <div class="manual-adjustment-list">
                            ${frameAdjustmentMarkup}
                        </div>
                    </div>
                    <div class="frame-metrics">
                        <div class="metric-chip"><span class="small-note">Approval</span><strong>${clip.approval_status || "draft"}</strong></div>
                        <div class="metric-chip"><span class="small-note">Rendered</span><strong>${clip.preview_render_complete ? "yes" : "no"}</strong></div>
                        <div class="metric-chip"><span class="small-note">FPS</span><strong>${clip.fps || 12}</strong></div>
                        <div class="metric-chip"><span class="small-note">Frames</span><strong>${clip.frame_count || 0}</strong></div>
                    </div>
                </div>
            </div>
        </div>
    ` : "";
    poseModal.classList.toggle("open", Boolean(clip && state.manualPoseModalOpen));

    const createButton = editorRoot.querySelector("#manual-clip-create");
    if (createButton) {
        createButton.onclick = async () => {
            try {
                const clipName = editorRoot.querySelector("#manual-clip-create-name").value.trim() || "Manual Clip";
                await api(`/api/projects/${project.project_id}/manual-clips/create`, {
                    method: "POST",
                    body: JSON.stringify({ clip_name: clipName }),
                });
                await loadProject(project.project_id, currentMode());
                notify(`Created manual clip ${clipName}.`, "success");
            } catch (error) {
                log(normalizeErrorMessage(error.message), "error");
                notify(normalizeErrorMessage(error.message), "error");
            }
        };
    }
    if (!clip) return;
    const openPoseButtons = [
        editorRoot.querySelector("#open-manual-pose-editor"),
        editorRoot.querySelector("#open-manual-pose-editor-secondary"),
    ].filter(Boolean);
    openPoseButtons.forEach((button) => {
        button.onclick = () => openManualPoseEditor();
    });
    editorRoot.querySelector("#manual-clip-select").onchange = (event) => {
        state.selectedManualClipId = event.target.value || null;
        state.selectedManualClipFrame = 0;
        state.manualPatchCandidates = [];
        state.manualPoseDraft = null;
        state.manualPoseDraftKey = null;
        renderManualClipStudio();
    };
    poseModalContent.querySelectorAll("[data-manual-frame]").forEach((button) => {
        button.onclick = () => {
            state.selectedManualClipFrame = Number(button.dataset.manualFrame || 0);
            state.manualPatchCandidates = [];
            state.manualPoseDraft = null;
            state.manualPoseDraftKey = null;
            renderManualClipStudio();
        };
    });
    const prevFrameButton = poseModalContent.querySelector("#manual-clip-prev-frame");
    if (prevFrameButton) prevFrameButton.onclick = () => {
        state.selectedManualClipFrame = Math.max(0, state.selectedManualClipFrame - 1);
        state.manualPatchCandidates = [];
        state.manualPoseDraft = null;
        state.manualPoseDraftKey = null;
        renderManualClipStudio();
    };
    const nextFrameButton = poseModalContent.querySelector("#manual-clip-next-frame");
    if (nextFrameButton) nextFrameButton.onclick = () => {
        state.selectedManualClipFrame = Math.min((clip.frame_count || 1) - 1, state.selectedManualClipFrame + 1);
        state.manualPatchCandidates = [];
        state.manualPoseDraft = null;
        state.manualPoseDraftKey = null;
        renderManualClipStudio();
    };
    const patchSourceSelect = poseModalContent.querySelector("#manual-patch-source-select");
    if (patchSourceSelect) patchSourceSelect.onchange = (event) => {
        state.selectedManualPatchSourcePart = event.target.value || null;
        state.selectedManualPatchOccluderPart = null;
        state.manualPatchCandidates = [];
        renderManualClipStudio();
    };
    const patchOccluderSelect = poseModalContent.querySelector("#manual-patch-occluder-select");
    if (patchOccluderSelect) patchOccluderSelect.onchange = (event) => {
        state.selectedManualPatchOccluderPart = event.target.value || null;
        state.manualPatchCandidates = [];
        renderManualClipStudio();
    };
    const patchGenerateButton = poseModalContent.querySelector("#manual-patch-generate");
    if (patchGenerateButton) patchGenerateButton.onclick = async () => {
        const sourcePartName = state.selectedManualPatchSourcePart || selectedManualPatchSourcePart(project)?.part_name;
        const keepBehindPartName = state.selectedManualPatchOccluderPart || selectedManualPatchOccluderPart(project)?.part_name;
        if (!sourcePartName || !keepBehindPartName) return;
        state.manualPatchBusy = true;
        state.manualPatchCandidates = [];
        renderManualClipStudio();
        try {
            const result = await api(`/api/projects/${project.project_id}/manual-clips/${clip.clip_id}/frame/${state.selectedManualClipFrame}/patch/${sourcePartName}/generate`, {
                method: "POST",
                body: JSON.stringify({}),
            });
            state.manualPatchCandidates = result.variants || [];
            if (!state.manualPatchCandidates.length) {
                notify(`No patch candidates were generated for ${humanizeKey(sourcePartName)}.`, "info");
            } else {
                const bestCandidate = state.manualPatchCandidates[0];
                await api(`/api/projects/${project.project_id}/manual-clips/${clip.clip_id}/frame/${state.selectedManualClipFrame}/patch/${sourcePartName}/apply`, {
                    method: "POST",
                    body: JSON.stringify({
                        ...bestCandidate,
                        keep_behind_part_name: keepBehindPartName,
                    }),
                });
                await loadProject(project.project_id, currentMode());
                notify(`Applied a gap patch from ${humanizeKey(sourcePartName)} behind ${humanizeKey(keepBehindPartName)} on F${state.selectedManualClipFrame + 1}.`, "success");
            }
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        } finally {
            state.manualPatchBusy = false;
            renderManualClipStudio();
        }
    };
    poseModalContent.querySelectorAll("[data-manual-patch-variant]").forEach((button) => {
        button.onclick = async () => {
            const sourcePartName = state.selectedManualPatchSourcePart || selectedManualPatchSourcePart(project)?.part_name;
            const keepBehindPartName = state.selectedManualPatchOccluderPart || selectedManualPatchOccluderPart(project)?.part_name;
            const candidate = (state.manualPatchCandidates || []).find((item) => item.variant_id === button.dataset.manualPatchVariant);
            if (!sourcePartName || !keepBehindPartName || !candidate) return;
            try {
                await api(`/api/projects/${project.project_id}/manual-clips/${clip.clip_id}/frame/${state.selectedManualClipFrame}/patch/${sourcePartName}/apply`, {
                    method: "POST",
                    body: JSON.stringify({
                        ...candidate,
                        keep_behind_part_name: keepBehindPartName,
                    }),
                });
                await loadProject(project.project_id, currentMode());
                notify(`Applied patch variant for ${humanizeKey(sourcePartName)} on F${state.selectedManualClipFrame + 1}.`, "success");
            } catch (error) {
                log(normalizeErrorMessage(error.message), "error");
                notify(normalizeErrorMessage(error.message), "error");
            }
        };
    });
    const patchClearButton = poseModalContent.querySelector("#manual-patch-clear");
    if (patchClearButton) patchClearButton.onclick = async () => {
        const sourcePartName = state.selectedManualPatchSourcePart || selectedManualPatchSourcePart(project)?.part_name;
        if (!sourcePartName) return;
        try {
            await api(`/api/projects/${project.project_id}/manual-clips/${clip.clip_id}/frame/${state.selectedManualClipFrame}/patch/${sourcePartName}/clear`, {
                method: "POST",
                body: JSON.stringify({}),
            });
            await loadProject(project.project_id, currentMode());
            notify(`Cleared gap patch for ${humanizeKey(sourcePartName)} on F${state.selectedManualClipFrame + 1}.`, "success");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    editorRoot.querySelector("#manual-clip-save-meta").onclick = async () => {
        try {
            await api(`/api/projects/${project.project_id}/manual-clips/${clip.clip_id}/update-meta`, {
                method: "POST",
                body: JSON.stringify({
                    clip_name: editorRoot.querySelector("#manual-clip-name").value.trim(),
                    frame_count: Number(editorRoot.querySelector("#manual-clip-frame-count").value || clip.frame_count),
                    fps: Number(editorRoot.querySelector("#manual-clip-fps").value || clip.fps),
                    loop: editorRoot.querySelector("#manual-clip-loop").checked,
                }),
            });
            await loadProject(project.project_id, currentMode());
            notify(`Saved ${clip.clip_name} metadata.`, "success");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    const captureFrameButton = poseModalContent.querySelector("#manual-clip-capture-frame");
    if (captureFrameButton) captureFrameButton.onclick = async () => {
        try {
            await saveManualPoseFrame(project, clip, state.manualPoseDraft || draftFrame || {}, `Captured frame ${state.selectedManualClipFrame + 1}.`);
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    const copyPrevButton = poseModalContent.querySelector("#manual-clip-copy-prev");
    if (copyPrevButton) copyPrevButton.onclick = async () => {
        try {
            await api(`/api/projects/${project.project_id}/manual-clips/${clip.clip_id}/frame/${state.selectedManualClipFrame}/copy`, {
                method: "POST",
                body: JSON.stringify({ source_index: Math.max(0, state.selectedManualClipFrame - 1) }),
            });
            await loadProject(project.project_id, currentMode());
            notify(`Copied frame ${Math.max(1, state.selectedManualClipFrame)} into frame ${state.selectedManualClipFrame + 1}.`, "success");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    const clearFrameButton = poseModalContent.querySelector("#manual-clip-clear-frame");
    if (clearFrameButton) clearFrameButton.onclick = async () => {
        try {
            await api(`/api/projects/${project.project_id}/manual-clips/${clip.clip_id}/frame/${state.selectedManualClipFrame}/reset`, {
                method: "POST",
                body: JSON.stringify({}),
            });
            await loadProject(project.project_id, currentMode());
            notify(`Cleared frame ${state.selectedManualClipFrame + 1}.`, "success");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    const renderButton = poseModalContent.querySelector("#manual-clip-render");
    if (renderButton) renderButton.onclick = async () => {
        try {
            await runJob(`/api/projects/${project.project_id}/manual-clips/${clip.clip_id}/render-preview`);
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    const approveButton = poseModalContent.querySelector("#manual-clip-approve");
    if (approveButton) approveButton.onclick = async () => {
        try {
            await api(`/api/projects/${project.project_id}/manual-clips/${clip.clip_id}/${clip.approval_status === "approved" ? "unapprove" : "approve"}`, {
                method: "POST",
                body: JSON.stringify({}),
            });
            await loadProject(project.project_id, currentMode());
            notify(`${clip.approval_status === "approved" ? "Unapproved" : "Approved"} ${clip.clip_name}.`, "success");
        } catch (error) {
            log(normalizeErrorMessage(error.message), "error");
            notify(normalizeErrorMessage(error.message), "error");
        }
    };
    const closePoseButton = poseModalContent.querySelector("#close-manual-pose");
    if (closePoseButton) closePoseButton.onclick = closeManualPoseEditor;

    const liveViewport = poseModalContent.querySelector("#manual-pose-live-viewport");
    const liveContainer = poseModalContent.querySelector("#manual-pose-live-preview-container");
    function applyPreviewTransform() {
        if (liveContainer) liveContainer.style.transform = `translate(${state.manualPreviewPanX}px, ${state.manualPreviewPanY}px) scale(${state.manualPreviewZoom})`;
        const zoomLabel = poseModalContent.querySelector("#manual-preview-zoom-in")?.parentElement?.querySelector(".small-note");
        if (zoomLabel) zoomLabel.textContent = `${Math.round(state.manualPreviewZoom * 100)}%`;
    }
    if (liveViewport) {
        liveViewport.addEventListener("wheel", (e) => {
            e.preventDefault();
            const rect = liveViewport.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;
            const oldZoom = state.manualPreviewZoom;
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            state.manualPreviewZoom = clamp(oldZoom * delta, 0.25, 8);
            const ratio = state.manualPreviewZoom / oldZoom;
            state.manualPreviewPanX = mx - ratio * (mx - state.manualPreviewPanX);
            state.manualPreviewPanY = my - ratio * (my - state.manualPreviewPanY);
            applyPreviewTransform();
        }, { passive: false });
        liveViewport.addEventListener("mousedown", (e) => {
            if (e.button !== 0) return;
            e.preventDefault();
            const startX = e.clientX, startY = e.clientY;
            const startPanX = state.manualPreviewPanX, startPanY = state.manualPreviewPanY;
            const onMove = (me) => {
                state.manualPreviewPanX = startPanX + (me.clientX - startX);
                state.manualPreviewPanY = startPanY + (me.clientY - startY);
                applyPreviewTransform();
            };
            const onUp = () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
            window.addEventListener("mousemove", onMove);
            window.addEventListener("mouseup", onUp, { once: true });
        });
    }
    const zoomInBtn = poseModalContent.querySelector("#manual-preview-zoom-in");
    const zoomOutBtn = poseModalContent.querySelector("#manual-preview-zoom-out");
    const zoomResetBtn = poseModalContent.querySelector("#manual-preview-zoom-reset");
    if (zoomInBtn) zoomInBtn.onclick = () => { state.manualPreviewZoom = clamp(state.manualPreviewZoom * 1.25, 0.25, 8); applyPreviewTransform(); };
    if (zoomOutBtn) zoomOutBtn.onclick = () => { state.manualPreviewZoom = clamp(state.manualPreviewZoom * 0.8, 0.25, 8); applyPreviewTransform(); };
    if (zoomResetBtn) zoomResetBtn.onclick = () => { state.manualPreviewZoom = 1; state.manualPreviewPanX = 0; state.manualPreviewPanY = 0; applyPreviewTransform(); };

    bindManualPoseStageInteractions(poseModalContent.querySelector("#manual-pose-stage-modal"), project, clip, frame, handles);
}
