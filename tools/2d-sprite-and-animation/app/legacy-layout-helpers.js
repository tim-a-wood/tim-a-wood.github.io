function selectedRevisionHistory() {
    return state.activeProject?.sprite_model_history?.revisions || [];
}

function activeRigLayout(project = state.activeProject) {
    return project?.rig_layout || null;
}

function rigLayoutPartDefinition(part, project = state.activeProject) {
    const layout = activeRigLayout(project);
    const name = part?.part_role || part?.part_name || part;
    return layout?.parts?.find((item) => item.part_name === name || item.part_role === name) || null;
}

function rigLayoutHistory(project = state.activeProject) {
    return project?.rig_layout_history?.revisions || [];
}

function rigLayoutPartNames(project = state.activeProject) {
    const layout = activeRigLayout(project);
    return Array.isArray(layout?.parts)
        ? layout.parts.map((part) => part?.part_name).filter(Boolean)
        : [];
}

function rigLayoutJointNames(project = state.activeProject) {
    const layout = activeRigLayout(project);
    const joints = layout?.joint_schema?.joints;
    if (Array.isArray(joints)) {
        return joints
            .map((joint) => (typeof joint === "string" ? joint : joint?.name || joint?.joint_name || ""))
            .filter(Boolean);
    }
    return ["root", "pelvis", "torso", "neck", "head", "shoulder_left", "elbow_left", "wrist_left", "shoulder_right", "elbow_right", "wrist_right", "hip_left", "knee_left", "ankle_left", "hip_right", "knee_right", "ankle_right"];
}

function clipEditorParts(project = state.activeProject) {
    const parts = project?.sprite_model?.parts || project?.layered_character?.parts || [];
    return sortPartsByRigLayout(parts, project);
}

function selectedClipEditorPart(project = state.activeProject) {
    const parts = clipEditorParts(project);
    if (!parts.length) return null;
    if (!parts.some((part) => part.part_name === state.selectedClipPart)) {
        state.selectedClipPart = parts[0]?.part_name || null;
    }
    return parts.find((part) => part.part_name === state.selectedClipPart) || parts[0];
}

function clipPartOverrideBinding(part, project = state.activeProject) {
    if (!part) return null;
    const rigProfile = project?.rig?.rig_profile || project?.rig_layout?.rig_profile || "";
    const partName = part.part_name || "";
    const role = part.part_role || partName;
    const sideBindings = {
        head: { overrideKey: "head_rotation", label: "Rotation" },
        torso_pelvis: { overrideKey: "torso_rotation", label: "Rotation" },
        front_arm: { overrideKey: "shoulder_front_rotation", label: "Rotation" },
        front_leg: { overrideKey: "hip_front_rotation", label: "Rotation" },
        back_leg: { overrideKey: "hip_back_rotation", label: "Rotation" },
        weapon: { overrideKey: "weapon_rotation", label: "Local Rotation" },
        cape_back: { overrideKey: "cape_back_rotation_bias", label: "Rotation Bias" },
        front_cloth: { overrideKey: "front_cloth_rotation_bias", label: "Rotation Bias" },
    };
    if (rigProfile === "side_knight_simple_7" || rigProfile === "side_knight_dual_leg_8") {
        return sideBindings[partName] || sideBindings[role] || null;
    }
    const genericBindings = {
        hair_back: { overrideKey: "head_rotation", label: "Rotation" },
        head: { overrideKey: "head_rotation", label: "Rotation" },
        hair_front: { overrideKey: "head_rotation", label: "Rotation" },
        torso: { overrideKey: "torso_rotation", label: "Rotation" },
        pelvis: { overrideKey: "pelvis_rotation", label: "Rotation" },
        upper_arm_left: { overrideKey: "shoulder_left_rotation", label: "Rotation" },
        lower_arm_left: { overrideKey: "elbow_left_rotation", label: "Chain Rotation" },
        hand_left: { overrideKey: "elbow_left_rotation", label: "Chain Rotation" },
        upper_arm_right: { overrideKey: "shoulder_right_rotation", label: "Rotation" },
        lower_arm_right: { overrideKey: "elbow_right_rotation", label: "Chain Rotation" },
        hand_right: { overrideKey: "elbow_right_rotation", label: "Chain Rotation" },
        upper_leg_left: { overrideKey: "hip_left_rotation", label: "Rotation" },
        lower_leg_left: { overrideKey: "knee_left_rotation", label: "Chain Rotation" },
        foot_left: { overrideKey: "ankle_left_rotation", label: "Chain Rotation" },
        upper_leg_right: { overrideKey: "hip_right_rotation", label: "Rotation" },
        lower_leg_right: { overrideKey: "knee_right_rotation", label: "Chain Rotation" },
        foot_right: { overrideKey: "ankle_right_rotation", label: "Chain Rotation" },
        prop: { overrideKey: "prop_rotation", label: "Local Rotation" },
        weapon: { overrideKey: "prop_rotation", label: "Local Rotation" },
        accessory_front: { overrideKey: "torso_rotation", label: "Rotation" },
        accessory_back: { overrideKey: "torso_rotation", label: "Rotation" },
    };
    if (genericBindings[partName] || genericBindings[role]) {
        return genericBindings[partName] || genericBindings[role];
    }
    if (role === "prop" || role === "weapon") {
        return { overrideKey: "prop_rotation", label: "Local Rotation" };
    }
    const parentJoint = part.parent_joint || "";
    const jointBindings = {
        neck: { overrideKey: "head_rotation", label: "Rotation" },
        head: { overrideKey: "head_rotation", label: "Rotation" },
        torso: { overrideKey: "torso_rotation", label: "Rotation" },
        pelvis: { overrideKey: "pelvis_rotation", label: "Rotation" },
        shoulder_left: { overrideKey: "shoulder_left_rotation", label: "Rotation" },
        elbow_left: { overrideKey: "elbow_left_rotation", label: "Chain Rotation" },
        wrist_left: { overrideKey: "elbow_left_rotation", label: "Chain Rotation" },
        shoulder_right: { overrideKey: "shoulder_right_rotation", label: "Rotation" },
        elbow_right: { overrideKey: "elbow_right_rotation", label: "Chain Rotation" },
        wrist_right: { overrideKey: "elbow_right_rotation", label: "Chain Rotation" },
        shoulder_front: { overrideKey: "shoulder_front_rotation", label: "Rotation" },
        wrist_front: { overrideKey: "weapon_rotation", label: "Local Rotation" },
        hip_left: { overrideKey: "hip_left_rotation", label: "Rotation" },
        knee_left: { overrideKey: "knee_left_rotation", label: "Chain Rotation" },
        ankle_left: { overrideKey: "ankle_left_rotation", label: "Chain Rotation" },
        hip_right: { overrideKey: "hip_right_rotation", label: "Rotation" },
        knee_right: { overrideKey: "knee_right_rotation", label: "Chain Rotation" },
        ankle_right: { overrideKey: "ankle_right_rotation", label: "Chain Rotation" },
        hip_front: { overrideKey: "hip_front_rotation", label: "Rotation" },
        hip_back: { overrideKey: "hip_back_rotation", label: "Rotation" },
    };
    return jointBindings[parentJoint] || null;
}

function sortPartsByRigLayout(parts, project = state.activeProject) {
    const orderedNames = rigLayoutPartNames(project);
    if (!orderedNames.length) return [...parts];
    const rank = new Map(orderedNames.map((name, index) => [name, index]));
    return [...parts].sort((left, right) => {
        const leftRank = rank.has(left.part_name) ? rank.get(left.part_name) : Number.MAX_SAFE_INTEGER;
        const rightRank = rank.has(right.part_name) ? rank.get(right.part_name) : Number.MAX_SAFE_INTEGER;
        if (leftRank !== rightRank) return leftRank - rightRank;
        return String(left.part_name || "").localeCompare(String(right.part_name || ""));
    });
}

function selectedRecoveryVariants() {
    const partName = selectedSpritePart()?.part_name;
    return partName ? (state.spriteRecoveryVariants[partName] || []) : [];
}

function overlayMarkup(imagePath, bbox, pivot) {
    if (!validBBox(bbox)) return `<div class="empty">No overlay data yet.</div>`;
    const [x0, y0, x1, y1] = bbox;
    const width = Math.max(1, x1 - x0);
    const height = Math.max(1, y1 - y0);
    return `
        <div class="preview-card overlay-stack">
            <img src="${imagePath}" alt="Source preview">
            <div class="overlay-box" style="left:${(x0 / 640) * 100}%;top:${(y0 / 768) * 100}%;width:${(width / 640) * 100}%;height:${(height / 768) * 100}%;"></div>
            ${pivot ? `<div class="overlay-pivot" style="left:${((x0 + pivot[0]) / 640) * 100}%;top:${((y0 + pivot[1]) / 768) * 100}%;"></div>` : ""}
        </div>
    `;
}

function layoutOverlayMarkup(project, layout) {
    const imagePath = approvedConceptSourcePath(project);
    if (!layout) return `<div class="empty">No rig layout yet.</div>`;
    const boxes = (layout.parts || []).map((part) => {
        const region = Array.isArray(part.extraction_region) ? part.extraction_region : null;
        if (!region || region.length !== 4) return "";
        const [x0, y0, x1, y1] = region.map(Number);
        const width = Math.max(0.5, (x1 - x0) * 100);
        const height = Math.max(0.5, (y1 - y0) * 100);
        return `
            <div class="overlay-box" style="left:${x0 * 100}%;top:${y0 * 100}%;width:${width}%;height:${height}%;"></div>
            <div class="overlay-pivot" title="${part.part_name}" style="left:${((x0 + x1) / 2) * 100}%;top:${((y0 + y1) / 2) * 100}%;"></div>
        `;
    }).join("");
    return `
        <div class="preview-card overlay-stack">
            <img src="${imagePath}?v=${project.updated_at}" alt="Approved concept source">
            ${boxes}
        </div>
    `;
}

function syncLegacyModeControls() {
    const legacy = aiWorkflowLegacyMode();
    const selectors = [
        "#intake", "#concepts", "#character", "#animations", "#review-export",
    ];
    const allowInLegacy = new Set(["confirm-describe-step", "create-project-workbench", "refresh-projects-workbench"]);
    selectors.forEach((selector) => {
        const root = document.querySelector(selector);
        if (!root) return;
        root.querySelectorAll("button, input, textarea, select").forEach((node) => {
            if (legacy && (node.id && allowInLegacy.has(node.id))) return;
            node.disabled = legacy;
        });
    });
}
