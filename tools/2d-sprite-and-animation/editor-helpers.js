function selectedSpritePart() {
    const parts = spriteModelParts();
    if (!parts.length) return null;
    return parts.find((part) => part.part_name === state.selectedSpritePart) || parts[0];
}

function selectedShapePart(partShapes = localPartShapes()) {
    return partShapes?.parts?.find((part) => part.part_name === state.selectedShapePart) || partShapes?.parts?.[0] || null;
}

function openZoom(conceptId) {
    const concept = conceptById(conceptId);
    if (!concept) return;
    const path = conceptDisplayImagePath(concept);
    if (!path) return;
    state.zoomConceptId = conceptId;
    document.querySelector("#zoom-image").src = `${projectAsset(state.activeProject, path)}?v=${state.activeProject.updated_at}`;
    document.querySelector("#zoom-meta").textContent = `${concept.concept_id} · ${concept.difference_summary || "No summary"}`;
    document.querySelector("#zoom-details").textContent = JSON.stringify({
        run_id: concept.run_id,
        backend_name: concept.backend_name,
        seed: concept.seed,
        triage: concept.triage,
        variation_axes: concept.variation_axes,
        references_used: concept.references_used,
    }, null, 2);
    document.querySelector("#zoom-modal").classList.add("open");
}

function closeZoom() {
    state.zoomConceptId = null;
    document.querySelector("#zoom-modal").classList.remove("open");
}

function openManualPoseEditor() {
    state.manualPoseModalOpen = true;
    renderManualClipStudio();
}

function closeManualPoseEditor() {
    state.manualPoseModalOpen = false;
    document.querySelector("#manual-pose-modal").classList.remove("open");
}
