document.querySelector("#build-layers")?.addEventListener("click", async () => {
    try {
        await runJob(`/api/projects/${state.activeProject.project_id}/sprite-model/build`);
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

function closeRigLayoutMenus() {
    document.querySelectorAll("#rig-layout .panel-menu[open]").forEach((node) => node.removeAttribute("open"));
}

document.querySelector("#generate-rig-layout")?.addEventListener("click", async () => {
    try {
        closeRigLayoutMenus();
        await api(`/api/projects/${state.activeProject.project_id}/rig-layout/generate`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        notify("Rig layout generated.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#copy-rig-layout-prompt")?.addEventListener("click", async () => {
    try {
        closeRigLayoutMenus();
        const prompt = state.activeProject?.rig_layout_handoff_prompt;
        if (!prompt) throw new Error("No Codex handoff prompt is available yet.");
        await navigator.clipboard.writeText(prompt);
        notify("Copied the Codex handoff prompt.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#save-rig-layout")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/rig-layout/update`, {
            method: "POST",
            body: JSON.stringify({
                operation: "apply_codex_response",
                response_text: document.querySelector("#rig-layout-json").value || "",
            }),
        });
        await loadProject(state.activeProject.project_id, currentMode());
        document.querySelector("#rig-layout-json").value = "";
        notify("Applied Codex rig check.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#approve-rig-layout")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/rig-layout/approve`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        if (currentMode() === "wizard" && state.activeProject) {
            const synced = await persistWizardState({
                completed_steps: ["rig_layout"],
                current_step: "part_manifest",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
        }
        notify("Rig layout approved.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#generate-part-manifest")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/part-manifest/generate`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        if (state.activeProject) {
            const synced = await persistWizardState({
                completed_steps: ["part_manifest"],
                current_step: "part_manifest",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
        }
        notify("Part manifest generated.", "success");
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#copy-part-manifest-prompt")?.addEventListener("click", async () => {
    try {
        const prompt = state.activeProject?.part_manifest_handoff_prompt;
        if (!prompt) throw new Error("No Codex manifest prompt is available yet.");
        await navigator.clipboard.writeText(prompt);
        notify("Copied the Codex manifest prompt.", "success");
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#apply-part-manifest")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/part-manifest/update`, {
            method: "POST",
            body: JSON.stringify({
                operation: "apply_codex_response",
                response_text: document.querySelector("#part-manifest-json").value || "",
            }),
        });
        document.querySelector("#part-manifest-json").value = "";
        await loadProject(state.activeProject.project_id, currentMode());
        notify("Applied Codex manifest response.", "success");
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#approve-part-manifest")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/part-manifest/approve`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        if (state.activeProject) {
            const synced = await persistWizardState({
                completed_steps: ["part_manifest"],
                current_step: "part_shape_edit",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
        }
        notify("Part manifest approved.", "success");
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#add-optional-manifest-part")?.addEventListener("click", async () => {
    const partName = window.prompt("Optional part name", "optional_overlay");
    if (!partName) return;
    try {
        await api(`/api/projects/${state.activeProject.project_id}/part-manifest/update`, {
            method: "POST",
            body: JSON.stringify({
                operation: "add_optional_part",
                part_name: partName,
                part_label: humanizeKey(partName),
            }),
        });
        await loadProject(state.activeProject.project_id, currentMode());
        notify("Optional part added.", "success");
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#initialize-part-shapes")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/part-shapes/initialize`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        if (state.activeProject) {
            const synced = await persistWizardState({
                completed_steps: ["part_manifest", "part_shape_edit"],
                current_step: "part_shape_edit",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
        }
        notify("Part shapes initialized.", "success");
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#copy-part-shapes-prompt")?.addEventListener("click", async () => {
    try {
        const prompt = state.activeProject?.part_shapes_handoff_prompt;
        if (!prompt) throw new Error("No Codex shape prompt is available yet.");
        await navigator.clipboard.writeText(prompt);
        notify("Copied the Codex shape prompt.", "success");
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#apply-part-shapes")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/part-shapes/update`, {
            method: "POST",
            body: JSON.stringify({
                operation: "apply_codex_response",
                response_text: document.querySelector("#part-shapes-json").value || "",
            }),
        });
        document.querySelector("#part-shapes-json").value = "";
        await loadProject(state.activeProject.project_id, currentMode());
        notify("Applied Codex shape response.", "success");
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#approve-part-shapes")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/part-shapes/approve`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        if (state.activeProject) {
            const synced = await persistWizardState({
                completed_steps: ["part_manifest", "part_shape_edit"],
                current_step: "split_build",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
        }
        notify("Part shapes approved.", "success");
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#shape-undo")?.addEventListener("click", async () => {
    if (state.partShapeHistoryIndex <= 0) return;
    state.partShapeHistoryIndex -= 1;
    const snapshot = cloneJson(state.partShapeHistory[state.partShapeHistoryIndex]);
    replaceLocalPartShapes(snapshot, { pushHistory: false });
    renderPartShapeEdit();
    try {
        await persistLocalPartShapes(snapshot);
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#shape-redo")?.addEventListener("click", async () => {
    if (state.partShapeHistoryIndex >= state.partShapeHistory.length - 1) return;
    state.partShapeHistoryIndex += 1;
    const snapshot = cloneJson(state.partShapeHistory[state.partShapeHistoryIndex]);
    replaceLocalPartShapes(snapshot, { pushHistory: false });
    renderPartShapeEdit();
    try {
        await persistLocalPartShapes(snapshot);
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#shape-fit-view")?.addEventListener("click", () => {
    state.partShapeView.fitted = false;
    ensureShapeViewFit(state.activeProject);
    renderPartShapeEdit();
});

document.querySelector("#shape-zoom-in")?.addEventListener("click", () => {
    state.partShapeView.zoom = Math.min(3.5, state.partShapeView.zoom + 0.15);
    state.partShapeView.fitted = true;
    renderPartShapeEdit();
});

document.querySelector("#shape-zoom-out")?.addEventListener("click", () => {
    state.partShapeView.zoom = Math.max(0.35, state.partShapeView.zoom - 0.15);
    state.partShapeView.fitted = true;
    renderPartShapeEdit();
});

document.querySelector("#shape-reset-selected")?.addEventListener("click", async () => {
    if (!state.selectedShapePart) return;
    try {
        await api(`/api/projects/${state.activeProject.project_id}/part-shapes/update`, {
            method: "POST",
            body: JSON.stringify({ operation: "reset_part_shape", part_name: state.selectedShapePart }),
        });
        await loadProject(state.activeProject.project_id, currentMode());
        notify("Selected part shape reset.", "success");
    } catch (error) {
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#part-shapes-opacity")?.addEventListener("input", (event) => {
    state.partShapeView.sourceOpacity = Number(event.target.value) / 100;
    renderPartShapeEdit();
});

document.querySelector("#generate-part-split")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/split-build`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        if (state.activeProject) {
            const synced = await persistWizardState({
                completed_steps: ["split_build"],
                current_step: "split_review",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
        }
        notify("Split assets built.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#copy-part-split-prompt")?.addEventListener("click", async () => {
    try {
        const prompt = state.activeProject?.part_split_handoff_prompt;
        if (!prompt) throw new Error("No Codex split prompt is available yet.");
        await navigator.clipboard.writeText(prompt);
        notify("Copied the Codex split prompt.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#approve-part-split")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/part-split/approve`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        if (state.activeProject) {
            const synced = await persistWizardState({
                completed_steps: ["split_build", "split_review"],
                current_step: "sprite_model",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
        }
        notify("Split parts approved.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#approve-layers")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/sprite-model/approve`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        if (currentMode() === "wizard" && state.activeProject) {
            const synced = await persistWizardState({
                completed_steps: ["sprite_model"],
                current_step: "rig",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
        }
        log("Approved sprite model", "success");
        notify("Sprite model approved.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#build-rig")?.addEventListener("click", async () => {
    try {
        await runJob(`/api/projects/${state.activeProject.project_id}/rig/build`);
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#approve-rig")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/rig/approve`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        if (currentMode() === "wizard" && state.activeProject) {
            const synced = await persistWizardState({
                completed_steps: ["rig"],
                current_step: "clips",
                last_ui_mode: "wizard",
            });
            if (synced) state.activeProject = synced;
        }
        log("Approved rig", "success");
        notify("Rig approved.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#render-idle")?.addEventListener("click", async () => {
    try {
        await runJob(`/api/projects/${state.activeProject.project_id}/clips/idle/render`);
        if (currentMode() === "wizard" && state.activeProject?.build_status?.idle_render_complete && state.activeProject?.build_status?.walk_render_complete) {
            const synced = await persistWizardState({
                completed_steps: ["animations"],
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

document.querySelector("#render-walk")?.addEventListener("click", async () => {
    try {
        await runJob(`/api/projects/${state.activeProject.project_id}/clips/walk/render`);
        if (currentMode() === "wizard" && state.activeProject?.build_status?.idle_render_complete && state.activeProject?.build_status?.walk_render_complete) {
            const synced = await persistWizardState({
                completed_steps: ["animations"],
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

document.querySelector("#sprite-undo-last")?.addEventListener("click", async () => {
    try {
        await api(`/api/projects/${state.activeProject.project_id}/sprite-model/undo`, { method: "POST", body: "{}" });
        await loadProject(state.activeProject.project_id, currentMode());
        notify("Reverted to the previous sprite-model revision.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-restore-revision")?.addEventListener("click", async () => {
    try {
        const revisionId = document.querySelector("#sprite-revision-select").value;
        if (!revisionId) throw new Error("Choose a revision to restore.");
        await api(`/api/projects/${state.activeProject.project_id}/sprite-model/restore`, {
            method: "POST",
            body: JSON.stringify({ revision_id: revisionId }),
        });
        await loadProject(state.activeProject.project_id, currentMode());
        notify("Restored the selected sprite-model revision.", "success");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-draw-order-back")?.addEventListener("click", async () => {
    try {
        const active = selectedSpritePart();
        if (!active) throw new Error("Choose a sprite-model part first.");
        await applySpriteOperation("set_draw_order", { draw_order: Number(active.draw_order || 0) - 1 });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-draw-order-forward")?.addEventListener("click", async () => {
    try {
        const active = selectedSpritePart();
        if (!active) throw new Error("Choose a sprite-model part first.");
        await applySpriteOperation("set_draw_order", { draw_order: Number(active.draw_order || 0) + 1 });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-set-pivot")?.addEventListener("click", async () => {
    try {
        await applySpriteOperation("set_pivot", {
            pivot_point: [
                Number(document.querySelector("#sprite-pivot-x").value || 0),
                Number(document.querySelector("#sprite-pivot-y").value || 0),
            ],
        });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-set-parent")?.addEventListener("click", async () => {
    try {
        await applySpriteOperation("set_parent_joint", { parent_joint: document.querySelector("#sprite-parent-joint").value });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-set-draw-order")?.addEventListener("click", async () => {
    try {
        await applySpriteOperation("set_draw_order", { draw_order: Number(document.querySelector("#sprite-draw-order").value || 0) });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-rename-part")?.addEventListener("click", async () => {
    try {
        await applySpriteOperation("rename_part", { new_part_name: document.querySelector("#sprite-rename").value.trim() });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-translate-part")?.addEventListener("click", async () => {
    try {
        const [dx, dy] = parsePairInput(document.querySelector("#sprite-translate").value);
        await applySpriteOperation("translate_part", { dx: dx || 0, dy: dy || 0 });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-rotate-part")?.addEventListener("click", async () => {
    try {
        await applySpriteOperation("rotate_part", { degrees: Number(document.querySelector("#sprite-rotate").value || 0) });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-scale-part")?.addEventListener("click", async () => {
    try {
        await applySpriteOperation("scale_part", { scale: Number(document.querySelector("#sprite-scale").value || 1) });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-cleanup-alpha")?.addEventListener("click", async () => {
    try {
        await applySpriteOperation("cleanup_alpha");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-normalize-outline")?.addEventListener("click", async () => {
    try {
        await applySpriteOperation("normalize_outline");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-apply-palette")?.addEventListener("click", async () => {
    try {
        const replacements = spritePaletteReplacements();
        if (!replacements) throw new Error("Add at least one palette replacement first.");
        await applySpriteOperation("apply_palette_change", { replacements });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-add-mask")?.addEventListener("click", async () => {
    try {
        const region = parsePairInput(document.querySelector("#sprite-mask-region").value);
        if (region.length !== 4) throw new Error("Enter mask region as x0,y0,x1,y1.");
        await applySpriteOperation("add_to_mask", { region });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-remove-mask")?.addEventListener("click", async () => {
    try {
        const region = parsePairInput(document.querySelector("#sprite-mask-region").value);
        if (region.length !== 4) throw new Error("Enter mask region as x0,y0,x1,y1.");
        await applySpriteOperation("remove_from_mask", { region });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-mirror-part")?.addEventListener("click", async () => {
    try {
        await applySpriteOperation("mirror_part");
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-duplicate-part")?.addEventListener("click", async () => {
    try {
        const active = selectedSpritePart();
        await applySpriteOperation("duplicate_part", { new_part_name: `${active.part_name}_copy` });
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#sprite-recover-occlusion")?.addEventListener("click", async () => {
    try {
        const active = selectedSpritePart();
        const result = await api(`/api/projects/${state.activeProject.project_id}/sprite-model/recover-occlusion`, {
            method: "POST",
            body: JSON.stringify({ part_name: active.part_name }),
        });
        log(`Recovered occlusion variants for ${active.part_name}`, "success");
        notify(`Saved ${result.variants.length} recovery variant(s) for ${active.part_name}.`, "success");
        await loadProject(state.activeProject.project_id, currentMode());
    } catch (error) {
        log(normalizeErrorMessage(error.message), "error");
        notify(normalizeErrorMessage(error.message), "error");
    }
});

document.querySelector("#close-zoom")?.addEventListener("click", closeZoom);
document.querySelector("#zoom-modal")?.addEventListener("click", (event) => {
    if (event.target === document.querySelector("#zoom-modal")) closeZoom();
});
document.querySelector("#manual-pose-modal")?.addEventListener("click", (event) => {
    if (event.target === document.querySelector("#manual-pose-modal")) closeManualPoseEditor();
});
