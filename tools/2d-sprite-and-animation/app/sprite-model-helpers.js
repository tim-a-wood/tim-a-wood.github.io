function spriteModelParts() {
    return state.activeProject?.sprite_model?.parts || state.activeProject?.layered_character?.parts || [];
}

function previousSpritePart(partName) {
    const previousParts = state.previousSpriteModel?.parts || [];
    return previousParts.find((part) => part.part_name === partName) || null;
}

function spriteModelFacing(project) {
    return project?.sprite_model?.source_facing || project?.layered_character?.source_facing || "left";
}

function spritePartGuide(part, project = state.activeProject) {
    const name = part?.part_role || part?.part_name || "";
    const layoutPart = rigLayoutPartDefinition(part, project);
    if (layoutPart?.label || layoutPart?.coverage) {
        return {
            label: layoutPart.label || humanizeKey(name),
            shortLabel: layoutPart.label || humanizeKey(name),
            coverage: layoutPart.coverage || "Keep the box tight to the intended body part.",
        };
    }
    const facing = spriteModelFacing(project);
    const nearSide = facing === "right" ? "right" : "left";
    const sideLabel = (suffix, base) => {
        const isNear = suffix === nearSide;
        return {
            label: `${isNear ? "Front" : "Back"} ${base}`,
            shortLabel: `${isNear ? "Front" : "Back"} ${base}`,
            coverage: isNear
                ? `${base} on the visible side only. Keep it tight to the readable silhouette and exclude cape or torso pixels.`
                : `${base} on the hidden side. If this profile fully hides it, keep the box tiny and tucked behind the body instead of duplicating the visible limb.`,
        };
    };
    const guides = {
        hair_back: {
            label: "Back Hair / Rear Helmet Silhouette",
            shortLabel: "Back Hair",
            coverage: "Only the rear silhouette behind the head. Exclude the face plate and front helmet edge.",
        },
        hair_front: {
            label: "Front Hair / Forehead Silhouette",
            shortLabel: "Front Hair",
            coverage: "Only the front hair or front helmet trim that sits over the face-side silhouette.",
        },
        accessory_back: {
            label: "Back Accessory / Cape",
            shortLabel: "Back Cape",
            coverage: "Rear-hanging cloth, cape, or pack silhouette behind the body. Do not include torso or arm armor.",
        },
        accessory_front: {
            label: "Front Accessory / Cloth",
            shortLabel: "Front Cloth",
            coverage: "Front cloth flap, tabard, sash, or hanging detail over the body. Exclude legs unless the cloth clearly overlaps them.",
        },
        head: {
            label: "Head / Helmet",
            shortLabel: "Head",
            coverage: "The whole head mass, including helmet and neck silhouette. Exclude shoulder, cape, and torso armor.",
        },
        torso: {
            label: "Torso / Chest",
            shortLabel: "Torso",
            coverage: "Chest and ribcage area only. Exclude pelvis, arms, and cape strips.",
        },
        pelvis: {
            label: "Pelvis / Hips",
            shortLabel: "Pelvis",
            coverage: "Belt, hips, and waist block. This should bridge torso to legs without swallowing the front cloth.",
        },
        prop: {
            label: "Held Item / Attachment",
            shortLabel: "Prop",
            coverage: "Only a handheld item or a small attached object. If no visible prop exists in profile, keep this tiny and unobtrusive.",
        },
        upper_arm_left: sideLabel("left", "Upper Arm"),
        upper_arm_right: sideLabel("right", "Upper Arm"),
        lower_arm_left: sideLabel("left", "Forearm"),
        lower_arm_right: sideLabel("right", "Forearm"),
        hand_left: sideLabel("left", "Hand"),
        hand_right: sideLabel("right", "Hand"),
        upper_leg_left: sideLabel("left", "Thigh"),
        upper_leg_right: sideLabel("right", "Thigh"),
        lower_leg_left: sideLabel("left", "Shin"),
        lower_leg_right: sideLabel("right", "Shin"),
        foot_left: sideLabel("left", "Foot"),
        foot_right: sideLabel("right", "Foot"),
    };
    return guides[name] || {
        label: humanizeKey(name),
        shortLabel: humanizeKey(name),
        coverage: "Keep the box tight to this isolated body part and avoid neighboring pixels.",
    };
}

function validBBox(value) {
    return Array.isArray(value) && value.length === 4 && value.every((item) => Number.isFinite(Number(item)));
}

function formatBBox(value) {
    return validBBox(value) ? value.map((item) => Number(item)).join(", ") : "none";
}

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function statusTone(status) {
    if (status === "pass") return "ok";
    if (status === "warning") return "warning";
    return "fail";
}

function normalizeSourceBBox(value) {
    if (!validBBox(value)) return null;
    const [x0, y0, x1, y1] = value.map((item) => Number(item));
    const left = clamp(Math.min(x0, x1), 0, SPRITE_EDITOR_SIZE.width - 1);
    const top = clamp(Math.min(y0, y1), 0, SPRITE_EDITOR_SIZE.height - 1);
    const right = clamp(Math.max(x0, x1), left + 1, SPRITE_EDITOR_SIZE.width);
    const bottom = clamp(Math.max(y0, y1), top + 1, SPRITE_EDITOR_SIZE.height);
    return [Math.round(left), Math.round(top), Math.round(right), Math.round(bottom)];
}

function bboxDimensions(value) {
    if (!validBBox(value)) return [0, 0];
    return [Math.max(0, Number(value[2]) - Number(value[0])), Math.max(0, Number(value[3]) - Number(value[1]))];
}

function bboxStyleString(bbox) {
    const normalized = normalizeSourceBBox(bbox);
    if (!normalized) return "";
    const [x0, y0, x1, y1] = normalized;
    const width = x1 - x0;
    const height = y1 - y0;
    return `left:${(x0 / SPRITE_EDITOR_SIZE.width) * 100}%;top:${(y0 / SPRITE_EDITOR_SIZE.height) * 100}%;width:${(width / SPRITE_EDITOR_SIZE.width) * 100}%;height:${(height / SPRITE_EDITOR_SIZE.height) * 100}%;`;
}

function pivotStyleString(bbox, pivot) {
    const normalized = normalizeSourceBBox(bbox);
    if (!normalized || !Array.isArray(pivot) || pivot.length !== 2) return "";
    const x = clamp(normalized[0] + Number(pivot[0]), normalized[0], normalized[2]);
    const y = clamp(normalized[1] + Number(pivot[1]), normalized[1], normalized[3]);
    return `left:${(x / SPRITE_EDITOR_SIZE.width) * 100}%;top:${(y / SPRITE_EDITOR_SIZE.height) * 100}%;`;
}

function handlePositionStyle(bbox, handle) {
    const normalized = normalizeSourceBBox(bbox);
    if (!normalized) return "";
    const [x0, y0, x1, y1] = normalized;
    const map = {
        nw: [x0, y0],
        ne: [x1, y0],
        sw: [x0, y1],
        se: [x1, y1],
    };
    const point = map[handle] || map.se;
    return `left:${(point[0] / SPRITE_EDITOR_SIZE.width) * 100}%;top:${(point[1] / SPRITE_EDITOR_SIZE.height) * 100}%;`;
}

function sourcePointFromEvent(event, element, round = true) {
    const rect = element.getBoundingClientRect();
    let localX = event.clientX - rect.left;
    let localY = event.clientY - rect.top;
    let viewportWidth = rect.width;
    let viewportHeight = rect.height;
    let sourceWidth = SPRITE_EDITOR_SIZE.width;
    let sourceHeight = SPRITE_EDITOR_SIZE.height;

    // Manual pose editor overlays the rig in an SVG using preserveAspectRatio,
    // so pointer coordinates must map into the rendered SVG viewport rather
    // than the full stage box (which may include letterboxing).
    const svg = element.querySelector?.("svg[viewBox]");
    const viewBox = svg?.viewBox?.baseVal;
    if (viewBox?.width && viewBox?.height && rect.width > 0 && rect.height > 0) {
        sourceWidth = viewBox.width;
        sourceHeight = viewBox.height;
        const sourceAspect = sourceWidth / sourceHeight;
        const rectAspect = rect.width / rect.height;
        if (rectAspect > sourceAspect) {
            viewportHeight = rect.height;
            viewportWidth = viewportHeight * sourceAspect;
            localX -= (rect.width - viewportWidth) / 2;
        } else {
            viewportWidth = rect.width;
            viewportHeight = viewportWidth / sourceAspect;
            localY -= (rect.height - viewportHeight) / 2;
        }
    }

    const x = (localX / Math.max(1, viewportWidth)) * sourceWidth;
    const y = (localY / Math.max(1, viewportHeight)) * sourceHeight;
    const clamped = [clamp(x, 0, sourceWidth), clamp(y, 0, sourceHeight)];
    return round ? [Math.round(clamped[0]), Math.round(clamped[1])] : clamped;
}

function pointToLocalPivot(point, bbox) {
    const normalized = normalizeSourceBBox(bbox);
    if (!normalized) return [0, 0];
    const [x, y] = point;
    return [
        Math.round(clamp(x - normalized[0], 0, Math.max(0, normalized[2] - normalized[0]))),
        Math.round(clamp(y - normalized[1], 0, Math.max(0, normalized[3] - normalized[1]))),
    ];
}

function approvedConceptSourcePath(project) {
    const accepted = project?.concepts?.find((concept) => concept.concept_id === project?.selected_concept_id);
    const source = accepted?.approved_source_image || project?.sprite_model?.approved_source_image || project?.master_pose_manifest?.approved_image || "master_pose/approved_master_pose.png";
    return projectAsset(project, source);
}
