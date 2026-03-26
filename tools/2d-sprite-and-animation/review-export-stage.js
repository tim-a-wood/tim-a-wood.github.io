function renderReviewExportClipPreviews() {
    const row = document.querySelector("#review-export-clip-previews-row");
    if (!row) return;
    Object.keys(state.clipPreviewTimers)
        .filter((key) => key.startsWith("review_"))
        .forEach((key) => clearClipLoopPreview(key));
    row.innerHTML = "";
    const project = state.activeProject;
    if (!project) return;
    if (externalAuthoringEnabled(project)) {
        row.innerHTML = `<div class="small-note">Loop previews are disabled while SkelForm authoring is active.</div>`;
        return;
    }
    const clips = project.animation_clips || {};
    const clipNames = Object.keys(clips);
    if (!clipNames.length) {
        row.innerHTML = `<div class="empty">No animation clips yet.</div>`;
        return;
    }
    clipNames.forEach((clipName) => {
        const clip = clips[clipName];
        const timerKey = `review_${clipName}`;
        const cell = document.createElement("div");
        cell.innerHTML = `<div class="small-note" style="margin-bottom:4px;">${humanizeKey(clipName)}</div>`;
        const previewRoot = document.createElement("div");
        previewRoot.id = `review-export-${clipName}-preview`;
        cell.appendChild(previewRoot);
        row.appendChild(cell);
        const bridge = pixellabAnimationClipFrameRels(project, clipName);
        if (bridge) {
            const urls = bridge.map((rel) => `${projectAsset(project, rel)}?v=${project.updated_at}`);
            renderClipLoopPreview(clipName, urls.length, { root: previewRoot, timerKey, frameUrls: urls, fps: clip?.fps });
        } else {
            const count = clip?.frame_count || (clipName === "idle" ? 6 : 8);
            renderClipLoopPreview(clipName, count, { root: previewRoot, timerKey });
        }
    });
}

function createContextPanel(label = "Context", note = "Open for details") {
    const details = document.createElement("details");
    details.className = "flow-collapsible";
    const summary = document.createElement("summary");
    summary.innerHTML = `<span>${escapeHtml(label)}</span><span class="small-note">${escapeHtml(note)}</span>`;
    const body = document.createElement("div");
    body.className = "flow-collapsible-body";
    details.appendChild(summary);
    details.appendChild(body);
    return { details, body };
}

function renderQa() {
    const root = document.querySelector("#qa-summary");
    root.innerHTML = "";
    const qa = state.activeProject?.qa_report;
    if (!qa) {
        root.innerHTML = `<div class="empty">QA has not run yet.</div>`;
        return;
    }
    const overall = document.createElement("div");
    overall.className = "check-row";
    overall.innerHTML = `<span>Overall status</span><span class="pill ${qa.status === "pass" ? "ok" : "fail"}">${qa.status}</span>`;
    root.appendChild(overall);
    const metadataValues = Object.values(qa.metadata_checks || {});
    const metadataIssues = metadataValues.filter((item) => item?.status && item.status !== "pass").length;
    const animationValues = Object.values(qa.per_animation_checks || {});
    const animationIssues = animationValues.filter((item) => item?.status && item.status !== "pass").length;
    const frameIssues = (qa.per_frame_checks || []).filter((frame) => frame?.status && frame.status !== "pass").length;
    const summary = document.createElement("div");
    summary.className = "check-row wrap";
    summary.innerHTML = `
        <span>Summary</span>
        <span class="small-note">${qa.status === "pass"
            ? "All required QA checks passed."
            : `${metadataIssues} metadata issue${metadataIssues === 1 ? "" : "s"} · ${animationIssues} animation issue${animationIssues === 1 ? "" : "s"} · ${frameIssues} frame issue${frameIssues === 1 ? "" : "s"}`}</span>
    `;
    root.appendChild(summary);
    const { details, body } = createContextPanel("Context", "Full QA breakdown");
    const buildReport = qa.sprite_model_build_report;
    if (buildReport) {
        const nonDeterministicSource = qa.mode === "external_authoring" || qa.mode === "ai_workflow";
        const buildRow = document.createElement("div");
        buildRow.className = "check-row wrap";
        buildRow.innerHTML = `
            <span>${nonDeterministicSource ? "Workflow source gate" : "Sprite-model build gate"}</span>
            <span class="small-note">
                <span class="pill ${statusTone(buildReport.status)}">${buildReport.status}</span>
                ${nonDeterministicSource
                    ? (buildReport.source || "external authoring")
                    : `${buildReport.summary?.warning_count || 0} warning${(buildReport.summary?.warning_count || 0) === 1 ? "" : "s"} · ${buildReport.summary?.fail_count || 0} fail${(buildReport.summary?.fail_count || 0) === 1 ? "" : "s"}`}
            </span>
        `;
        body.appendChild(buildRow);
    }
    Object.entries(qa.metadata_checks || {}).forEach(([name, item]) => {
        const row = document.createElement("div");
        row.className = "check-row";
        row.innerHTML = `<span>${humanizeKey(name)}</span><span class="pill ${item.status === "pass" ? "ok" : "fail"}">${item.status}</span>`;
        body.appendChild(row);
    });
    Object.entries(qa.per_animation_checks || {}).forEach(([animation, payload]) => {
        const row = document.createElement("div");
        row.className = "check-row";
        const checks = Object.entries(payload.checks || {})
            .map(([name, item]) => `${humanizeKey(name)}: ${item.status}`)
            .join(" · ");
        row.innerHTML = `<span>${humanizeKey(animation)}</span><span class="small-note">${checks}</span>`;
        body.appendChild(row);
    });
    const frameGrid = document.createElement("div");
    frameGrid.className = "thumb-grid";
    frameGrid.style.marginTop = "10px";
    (qa.per_frame_checks || []).forEach((frame) => {
        const card = document.createElement("div");
        card.className = "thumb";
        card.style.borderColor = frame.status === "fail" ? "rgba(211, 122, 122, 0.5)" : "rgba(117, 196, 152, 0.35)";
        const failedChecks = Object.entries(frame.checks || {})
            .filter(([, item]) => item.status === "fail")
            .map(([name]) => humanizeKey(name))
            .join(", ");
        card.innerHTML = `
            <div class="meta-line" style="justify-content:center;">
                <span class="pill ${frame.status === "pass" ? "ok" : "fail"}">${frame.status}</span>
            </div>
            <div class="small-note" style="margin-top: 8px;">${frame.frame_name}</div>
            <div class="small-note">${failedChecks || "all checks passed"}</div>
        `;
        frameGrid.appendChild(card);
    });
    body.appendChild(frameGrid);
    if (qa.mode !== "external_authoring" && qa.mode !== "ai_workflow" && (buildReport?.failures?.length || buildReport?.warnings?.length)) {
        const issueBlock = document.createElement("div");
        issueBlock.className = "detail-grid";
        issueBlock.innerHTML = `
            ${buildIssueMarkup("Sprite-Model Failures", buildReport.failures || [], "fail")}
            ${buildIssueMarkup("Sprite-Model Warnings", buildReport.warnings || [], "warning")}
        `;
        body.appendChild(issueBlock);
    }
    root.appendChild(details);
}

function renderExport() {
    const root = document.querySelector("#export-summary");
    root.innerHTML = "";
    const project = state.activeProject;
    if (!project) {
        root.innerHTML = `<div class="empty">Open a project to review exports.</div>`;
        return;
    }
    const exportData = state.activeProject?.last_export;
    const healthReport = project.health_report || {};
    const healthWarnings = Array.isArray(healthReport.warnings) ? healthReport.warnings : [];
    const recommendedActions = Array.isArray(healthReport.recommended_actions) ? healthReport.recommended_actions : [];
    const projectExportRow = document.createElement("div");
    projectExportRow.className = "check-row wrap";
    projectExportRow.innerHTML = `
        <span><strong>Project export</strong></span>
        <span class="small-note">Editable project bundle for restore, transfer, and backup.</span>
        <button type="button" class="secondary" id="export-project-bundle">Export Project</button>
    `;
    root.appendChild(projectExportRow);
    projectExportRow.querySelector("#export-project-bundle")?.addEventListener("click", () => downloadProjectBundle(project));
    const runtimeHeading = document.createElement("div");
    runtimeHeading.className = "check-row wrap";
    runtimeHeading.style.marginTop = "14px";
    runtimeHeading.innerHTML = `
        <span><strong>Runtime export</strong></span>
        <span class="small-note">Game-ready package generated from the current project state.</span>
    `;
    root.appendChild(runtimeHeading);
    if (!exportData) {
        const summary = document.createElement("div");
        summary.className = "check-row wrap";
        summary.innerHTML = `<span>Status</span><span class="small-note">No runtime export package yet.</span>`;
        root.appendChild(summary);
        if (healthWarnings.length || recommendedActions.length) {
            const warning = document.createElement("div");
            warning.className = healthWarnings.length ? "warning-box" : "info-box";
            warning.style.marginTop = "10px";
            warning.innerHTML = `
                <p><strong>What to do next</strong></p>
                <p class="small-note" style="margin-top:8px;">Run checks and export when this project is ready.</p>
            `;
            root.appendChild(warning);
        }
        return;
    }
    const top = document.createElement("div");
    top.className = "check-row";
    top.innerHTML = `<span>Export directory</span><span class="small-note">${exportData.export_dir}</span>`;
    root.appendChild(top);
    const exportSummary = document.createElement("div");
    exportSummary.className = "check-row wrap";
    exportSummary.innerHTML = `
        <span>Summary</span>
        <span class="small-note">${Array.isArray(exportData.files) ? exportData.files.length : 0} files · ${(Array.isArray(exportData.preview_gifs) ? exportData.preview_gifs.length : 0) || (exportData.preview_gif ? 1 : 0)} preview GIF${(((Array.isArray(exportData.preview_gifs) ? exportData.preview_gifs.length : 0) || (exportData.preview_gif ? 1 : 0)) === 1) ? "" : "s"}</span>
    `;
    root.appendChild(exportSummary);
    const { details, body } = createContextPanel("Context", "Export details and previews");
    if (exportData.verification) {
        const verification = document.createElement("div");
        verification.className = "check-row wrap";
        verification.innerHTML = `
            <span>Post-pack verification</span>
            <span class="small-note"><span class="pill ${statusTone(exportData.verification.status)}">${exportData.verification.status}</span></span>
        `;
        body.appendChild(verification);
        Object.entries(exportData.verification.checks || {}).forEach(([name, passed]) => {
            const row = document.createElement("div");
            row.className = "check-row";
            row.innerHTML = `<span>${humanizeKey(name)}</span><span class="pill ${passed ? "ok" : "fail"}">${passed ? "pass" : "fail"}</span>`;
            body.appendChild(row);
        });
    }
    if (healthWarnings.length || recommendedActions.length) {
        const healthBlock = document.createElement("div");
        healthBlock.className = healthWarnings.length ? "warning-box" : "info-box";
        healthBlock.innerHTML = `
            <p><strong>Project health</strong></p>
            ${healthWarnings.length ? `<div class="history-list" style="margin-top:8px;">${healthWarnings.slice(0, 4).map((item) => `<div class="history-item">${escapeHtml(humanizeKey(item))}</div>`).join("")}</div>` : ""}
            ${recommendedActions.length ? `<p class="small-note" style="margin-top:8px;">Suggested next actions: ${recommendedActions.slice(0, 3).map((item) => humanizeKey(item)).join(", ")}</p>` : ""}
        `;
        body.appendChild(healthBlock);
    }
    const previewGifs = Array.isArray(exportData.preview_gifs) && exportData.preview_gifs.length
        ? exportData.preview_gifs
        : exportData.preview_gif
            ? [exportData.preview_gif]
            : [];
    const animationSheets = exportData.animation_sheets && typeof exportData.animation_sheets === "object"
        ? Object.entries(exportData.animation_sheets)
        : [];
    const preview = document.createElement("div");
    preview.className = "export-preview-panel";
    preview.style.marginTop = "10px";
    if (animationSheets.length) {
        const sheetGrid = document.createElement("div");
        sheetGrid.className = "export-preview-sheet-stack";
        animationSheets.forEach(([clipName, meta]) => {
            if (!meta?.image) return;
            const cell = document.createElement("div");
            cell.className = "preview-card export-preview-sheet-card";
            const imageUrl = `${projectAsset(state.activeProject, `${exportData.export_dir}/${meta.image}`)}`;
            const imageToken = `${clipName}|${imageUrl}|${state.activeProject?.updated_at || ""}`;
            cell.innerHTML = `
                <div class="export-preview-sheet-label">${humanizeKey(clipName)} sheet</div>
                <img src="${imageUrl}" alt="${clipName} spritesheet" data-export-sheet-token="${imageToken}">
            `;
            const img = cell.querySelector("img");
            if (img) {
                exportSheetPreviewDisplayUrl(imageUrl).then((displayUrl) => {
                    if (!displayUrl) return;
                    if (img.dataset.exportSheetToken !== imageToken) return;
                    img.src = displayUrl;
                });
            }
            sheetGrid.appendChild(cell);
        });
        if (sheetGrid.childElementCount) {
            preview.appendChild(sheetGrid);
        }
    } else {
        const sheetCard = document.createElement("div");
        sheetCard.className = "preview-card export-preview-spritesheet";
        sheetCard.style.marginBottom = "12px";
        const imageUrl = `${projectAsset(state.activeProject, `${exportData.export_dir}/preview_spritesheet.png`)}`;
        const fallbackUrl = `${projectAsset(state.activeProject, `${exportData.export_dir}/spritesheet.png`)}`;
        const imageToken = `combined|${imageUrl}|${state.activeProject?.updated_at || ""}`;
        sheetCard.innerHTML = `
            <img src="${imageUrl}" alt="Spritesheet preview" data-export-sheet-token="${imageToken}">
            <div class="small-note" style="margin-top: 8px;">spritesheet</div>
        `;
        const img = sheetCard.querySelector("img");
        if (img) {
            img.onerror = () => {
                img.src = fallbackUrl;
                exportSheetPreviewDisplayUrl(fallbackUrl).then((displayUrl) => {
                    if (!displayUrl) return;
                    if (img.dataset.exportSheetToken !== imageToken) return;
                    img.src = displayUrl;
                });
            };
            exportSheetPreviewDisplayUrl(imageUrl).then((displayUrl) => {
                if (!displayUrl) return;
                if (img.dataset.exportSheetToken !== imageToken) return;
                img.src = displayUrl;
            });
        }
        preview.appendChild(sheetCard);
    }
    if (previewGifs.length) {
        const gifGrid = document.createElement("div");
        gifGrid.className = "export-preview-gif-grid";
        previewGifs.forEach((gifName) => {
            const clipLabel = String(gifName).replace(/^preview_/, "").replace(/\.gif$/i, "");
            const cell = document.createElement("div");
            cell.className = "preview-card";
            cell.innerHTML = `
                <img src="${projectAsset(state.activeProject, `${exportData.export_dir}/${gifName}`)}" alt="${clipLabel} preview">
                <div class="small-note" style="margin-top: 8px;">${humanizeKey(clipLabel)}</div>
            `;
            gifGrid.appendChild(cell);
        });
        preview.appendChild(gifGrid);
    } else {
        const empty = document.createElement("div");
        empty.className = "preview-card";
        empty.innerHTML = `<div class="empty">No preview GIF in this export.</div>`;
        preview.appendChild(empty);
    }
    body.appendChild(preview);
    if (!externalAuthoringEnabled(state.activeProject)) {
        const clips = state.activeProject?.animation_clips || {};
        Object.entries(clips).forEach(([clipName, clip]) => {
            const row = document.createElement("div");
            row.className = "check-row wrap";
            row.innerHTML = `
                <span>${humanizeKey(clipName)} runtime order</span>
                <span class="frame-sequence">${Array.from({ length: clip.frame_count }, (_, index) => `<code>${clipName}_${String(index).padStart(2, "0")}.png</code>`).join("")}</span>
            `;
            body.appendChild(row);
        });
    }
    const exportFileList = (() => {
        if (Array.isArray(exportData.files) && exportData.files.length) {
            return exportData.files;
        }
        return [
            exportData.spritesheet,
            exportData.atlas,
            exportData.animations,
            exportData.export_manifest,
            ...(Array.isArray(exportData.preview_gifs) ? exportData.preview_gifs : []),
            exportData.preview_gif,
        ].filter(Boolean);
    })();
    exportFileList.forEach((file) => {
        const row = document.createElement("div");
        row.className = "check-row";
        row.innerHTML = `<span>${file}</span><a href="${projectAsset(state.activeProject, `${exportData.export_dir}/${file}`)}" target="_blank">open</a>`;
        body.appendChild(row);
    });
    root.appendChild(details);
}

function downloadProjectBundle(project) {
    if (!project?.project_id) throw new Error("Select or create a project first.");
    const link = document.createElement("a");
    link.href = `${WORKBENCH_BASE}/api/projects/${encodeURIComponent(project.project_id)}/bundle-export`;
    link.download = `${project.project_name || project.project_id}.spriteworkbench.zip`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    log(`Started project export for ${project.project_name}`, "success");
    notify(`Exporting project ${project.project_name}.`, "success");
}

document.querySelector("#run-qa")?.addEventListener("click", async () => {
    try {
        await runJob(`/api/projects/${state.activeProject.project_id}/qa/run`);
        if (currentMode() === "wizard" && state.activeProject?.qa_report) {
            const synced = await persistWizardState({
                completed_steps: ["export"],
                current_step: "export",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
            renderAll();
        }
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#run-export")?.addEventListener("click", async () => {
    try {
        await runJob(`/api/projects/${state.activeProject.project_id}/export`);
        if (currentMode() === "wizard" && state.activeProject) {
            const synced = await persistWizardState({
                completed_steps: ["export"],
                current_step: "export",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
            renderAll();
        }
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});
