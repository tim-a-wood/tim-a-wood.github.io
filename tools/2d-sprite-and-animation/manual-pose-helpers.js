function currentBuildReport() {
    return state.activeProject?.sprite_model?.build_report || state.activeProject?.layered_character?.build_report || null;
}

function currentClipData() {
    const clips = state.activeProject?.animation_clips || {};
    if (!clips[state.selectedClip]) {
        state.selectedClip = clips.idle ? "idle" : clips.walk ? "walk" : "idle";
    }
    return clips[state.selectedClip] || null;
}

function clampSelectedClipFrame() {
    const clip = currentClipData();
    const frameCount = clip?.frame_count || 1;
    state.selectedClipFrame = clamp(Number(state.selectedClipFrame) || 0, 0, Math.max(0, frameCount - 1));
}

function currentClipFrameData() {
    clampSelectedClipFrame();
    const clip = currentClipData();
    return clip?.joint_transforms_per_frame?.[state.selectedClipFrame] || null;
}

function manualClipStore(project = state.activeProject) {
    return project?.manual_animation_clips?.clips || {};
}

function manualClipList(project = state.activeProject) {
    return Object.values(manualClipStore(project)).sort((left, right) =>
        String(left.clip_name || left.clip_id || "").localeCompare(String(right.clip_name || right.clip_id || ""))
    );
}

function selectedManualClip(project = state.activeProject) {
    const clips = manualClipList(project);
    if (!clips.length) return null;
    if (!clips.some((clip) => clip.clip_id === state.selectedManualClipId)) {
        state.selectedManualClipId = clips[0]?.clip_id || null;
    }
    return clips.find((clip) => clip.clip_id === state.selectedManualClipId) || clips[0];
}

function clampSelectedManualClipFrame(project = state.activeProject) {
    const clip = selectedManualClip(project);
    const frameCount = clip?.frame_count || 1;
    state.selectedManualClipFrame = clamp(Number(state.selectedManualClipFrame) || 0, 0, Math.max(0, frameCount - 1));
}

function manualFrameEntry(frame) {
    if (frame && (frame.transforms || frame.part_repairs || frame.corrective_patches)) {
        return {
            transforms: cloneJson(frame.transforms || {}),
            part_repairs: cloneJson(frame.part_repairs || {}),
            corrective_patches: cloneJson(frame.corrective_patches || {}),
        };
    }
    return {
        transforms: cloneJson(frame || {}),
        part_repairs: {},
        corrective_patches: {},
    };
}

function manualFrameTransforms(frame) {
    return manualFrameEntry(frame).transforms || {};
}

function manualFrameRepairs(frame) {
    return manualFrameEntry(frame).part_repairs || {};
}

function manualFramePatches(frame) {
    return manualFrameEntry(frame).corrective_patches || {};
}

function manualPatchableParts(project = state.activeProject) {
    return (project?.sprite_model?.parts || [])
        .filter((part) => Boolean(part?.part_name && part?.image_path))
        .sort((left, right) => Number(left.draw_order || 0) - Number(right.draw_order || 0) || String(left.part_name || "").localeCompare(String(right.part_name || "")));
}

function selectedManualPatchSourcePart(project = state.activeProject) {
    const parts = manualPatchableParts(project);
    if (!parts.length) return null;
    if (!parts.some((part) => part.part_name === state.selectedManualPatchSourcePart)) {
        state.selectedManualPatchSourcePart = parts[0]?.part_name || null;
    }
    return parts.find((part) => part.part_name === state.selectedManualPatchSourcePart) || parts[0] || null;
}

function manualPatchOccluderParts(project = state.activeProject, sourcePartName = state.selectedManualPatchSourcePart) {
    const sourcePart = manualPatchableParts(project).find((part) => part.part_name === sourcePartName);
    const sourceDrawOrder = Number(sourcePart?.draw_order || 0);
    return manualPatchableParts(project).filter((part) => part.part_name !== sourcePartName && Number(part.draw_order || 0) >= sourceDrawOrder);
}

function selectedManualPatchOccluderPart(project = state.activeProject) {
    const sourcePart = selectedManualPatchSourcePart(project);
    if (!sourcePart) return null;
    const options = manualPatchOccluderParts(project, sourcePart.part_name);
    if (!options.length) return null;
    if (!options.some((part) => part.part_name === state.selectedManualPatchOccluderPart)) {
        state.selectedManualPatchOccluderPart = options[0]?.part_name || null;
    }
    return options.find((part) => part.part_name === state.selectedManualPatchOccluderPart) || options[0] || null;
}

function manualPoseDraftKey(clipId = state.selectedManualClipId, frameIndex = state.selectedManualClipFrame) {
    return `${clipId || "none"}:${frameIndex}`;
}

function syncManualPoseDraft(project = state.activeProject) {
    const clip = selectedManualClip(project);
    if (!clip) {
        state.manualPoseDraft = null;
        state.manualPoseDraftKey = null;
        return null;
    }
    clampSelectedManualClipFrame(project);
    const key = manualPoseDraftKey(clip.clip_id, state.selectedManualClipFrame);
    if (state.manualPoseDraftKey !== key) {
        state.manualPoseDraft = cloneJson(manualFrameTransforms(clip.frames?.[state.selectedManualClipFrame] || {}));
        state.manualPoseDraftKey = key;
    }
    return state.manualPoseDraft;
}

function currentManualClipFrame(project = state.activeProject) {
    const clip = selectedManualClip(project);
    if (!clip) return null;
    syncManualPoseDraft(project);
    return state.manualPoseDraft || manualFrameTransforms(clip.frames?.[state.selectedManualClipFrame] || {}) || null;
}

function currentManualClipFrameEntry(project = state.activeProject) {
    const clip = selectedManualClip(project);
    if (!clip) return null;
    syncManualPoseDraft(project);
    const stored = manualFrameEntry(clip.frames?.[state.selectedManualClipFrame] || {});
    return {
        transforms: cloneJson(state.manualPoseDraft || stored.transforms || {}),
        part_repairs: cloneJson(stored.part_repairs || {}),
        corrective_patches: cloneJson(stored.corrective_patches || {}),
    };
}

function addPosePoints(a, b) {
    return [Number(a[0] || 0) + Number(b[0] || 0), Number(a[1] || 0) + Number(b[1] || 0)];
}

function rotatePoseVector(vector, degrees) {
    const radians = (Number(degrees || 0) * Math.PI) / 180;
    const cos = Math.cos(radians);
    const sin = Math.sin(radians);
    return [
        (Number(vector[0] || 0) * cos) - (Number(vector[1] || 0) * sin),
        (Number(vector[0] || 0) * sin) + (Number(vector[1] || 0) * cos),
    ];
}

function angleDegrees(from, to) {
    return (Math.atan2((to[1] || 0) - (from[1] || 0), (to[0] || 0) - (from[0] || 0)) * 180) / Math.PI;
}

function normalizeAngle(value) {
    let next = Number(value || 0);
    while (next > 180) next -= 360;
    while (next < -180) next += 360;
    return next;
}

function computeManualPoseJoints(rig, frame) {
    if (!rig) return {};
    const base = rig.rig_joint_map || {};
    const vectors = rig.joint_vectors || {};
    const frameData = frame || {};
    if (rig.rig_profile === "side_knight_simple_7" || rig.rig_profile === "side_knight_dual_leg_8") {
        const root = addPosePoints(base.root || [0, 0], frameData.root_offset || [0, 0]);
        const torsoRotation = Number(frameData.torso_rotation || 0);
        const headRotation = Number(frameData.head_rotation || 0);
        const shoulderFrontRotation = Number(frameData.shoulder_front_rotation || 0);
        const hipFrontRotation = Number(frameData.hip_front_rotation || 0);
        const weaponRotation = Number(frameData.weapon_rotation || 0);
        const capeBackRotationBias = Number(frameData.cape_back_rotation_bias || 0);
        const frontClothRotationBias = Number(frameData.front_cloth_rotation_bias || 0);
        const torso = addPosePoints(root, rotatePoseVector(vectors.torso_from_root || [0, 0], torsoRotation * 0.1));
        const neck = addPosePoints(torso, rotatePoseVector(vectors.neck_from_torso || [0, 0], torsoRotation));
        const head = addPosePoints(neck, rotatePoseVector(vectors.head_from_neck || [0, 0], torsoRotation + headRotation));
        const shoulderFront = addPosePoints(torso, rotatePoseVector(vectors.shoulder_front_from_torso || [0, 0], torsoRotation));
        const wristFront = addPosePoints(shoulderFront, rotatePoseVector(vectors.wrist_front_from_shoulder || [0, 0], shoulderFrontRotation + (torsoRotation * 0.2)));
        const hipFront = addPosePoints(root, rotatePoseVector(vectors.hip_front_from_root || [0, 0], torsoRotation * 0.1));
        const ankleFront = addPosePoints(hipFront, rotatePoseVector(vectors.ankle_front_from_hip || [0, 0], hipFrontRotation));
        const weaponTip = addPosePoints(wristFront, rotatePoseVector([26, 2], shoulderFrontRotation + weaponRotation + (torsoRotation * 0.2)));
        const capeTip = addPosePoints(torso, rotatePoseVector([-18, 28], torsoRotation + capeBackRotationBias));
        const frontClothTip = addPosePoints(root, rotatePoseVector([10, 30], (torsoRotation * 0.45) + frontClothRotationBias));
        const joints = {
            root,
            torso,
            neck,
            head,
            shoulder_front: shoulderFront,
            wrist_front: wristFront,
            hip_front: hipFront,
            ankle_front: ankleFront,
            weapon_tip: weaponTip,
            cape_tip: capeTip,
            front_cloth_tip: frontClothTip,
        };
        if (rig.rig_profile === "side_knight_dual_leg_8") {
            const hipBackRotation = Number(frameData.hip_back_rotation || 0);
            const hipBack = addPosePoints(root, rotatePoseVector(vectors.hip_back_from_root || [0, 0], torsoRotation * 0.1));
            const ankleBack = addPosePoints(hipBack, rotatePoseVector(vectors.ankle_back_from_hip || [0, 0], hipBackRotation));
            joints.hip_back = hipBack;
            joints.ankle_back = ankleBack;
        }
        return joints;
    }
    const root = addPosePoints(base.root || [0, 0], frameData.root_offset || [0, 0]);
    const pelvisRotation = Number(frameData.pelvis_rotation || 0);
    const torsoRotation = Number(frameData.torso_rotation || 0);
    const headRotation = Number(frameData.head_rotation || 0);
    const shoulderLeftRotation = Number(frameData.shoulder_left_rotation || 0);
    const elbowLeftRotation = Number(frameData.elbow_left_rotation || 0);
    const shoulderRightRotation = Number(frameData.shoulder_right_rotation || 0);
    const elbowRightRotation = Number(frameData.elbow_right_rotation || 0);
    const hipLeftRotation = Number(frameData.hip_left_rotation || 0);
    const kneeLeftRotation = Number(frameData.knee_left_rotation || 0);
    const hipRightRotation = Number(frameData.hip_right_rotation || 0);
    const kneeRightRotation = Number(frameData.knee_right_rotation || 0);
    const pelvis = addPosePoints(root, rotatePoseVector(vectors.pelvis_from_root || [0, 0], pelvisRotation));
    const torso = addPosePoints(pelvis, rotatePoseVector(vectors.torso_from_pelvis || [0, 0], torsoRotation));
    const neck = addPosePoints(torso, rotatePoseVector(vectors.neck_from_torso || [0, 0], torsoRotation * 0.6));
    const head = addPosePoints(neck, rotatePoseVector(vectors.head_from_neck || [0, 0], headRotation + (torsoRotation * 0.15)));
    const shoulderLeft = addPosePoints(torso, rotatePoseVector(vectors.shoulder_left_from_torso || [0, 0], torsoRotation));
    const elbowLeft = addPosePoints(shoulderLeft, rotatePoseVector(vectors.elbow_left_from_shoulder || [0, 0], shoulderLeftRotation + (torsoRotation * 0.2)));
    const wristLeft = addPosePoints(elbowLeft, rotatePoseVector(vectors.wrist_left_from_elbow || [0, 0], shoulderLeftRotation + elbowLeftRotation + (torsoRotation * 0.2)));
    const shoulderRight = addPosePoints(torso, rotatePoseVector(vectors.shoulder_right_from_torso || [0, 0], torsoRotation));
    const elbowRight = addPosePoints(shoulderRight, rotatePoseVector(vectors.elbow_right_from_shoulder || [0, 0], shoulderRightRotation + (torsoRotation * 0.2)));
    const wristRight = addPosePoints(elbowRight, rotatePoseVector(vectors.wrist_right_from_elbow || [0, 0], shoulderRightRotation + elbowRightRotation + (torsoRotation * 0.2)));
    const hipLeft = addPosePoints(pelvis, rotatePoseVector(vectors.hip_left_from_pelvis || [0, 0], pelvisRotation * 0.25));
    const kneeLeft = addPosePoints(hipLeft, rotatePoseVector(vectors.knee_left_from_hip || [0, 0], hipLeftRotation));
    const ankleLeft = addPosePoints(kneeLeft, rotatePoseVector(vectors.ankle_left_from_knee || [0, 0], hipLeftRotation + kneeLeftRotation));
    const hipRight = addPosePoints(pelvis, rotatePoseVector(vectors.hip_right_from_pelvis || [0, 0], pelvisRotation * 0.25));
    const kneeRight = addPosePoints(hipRight, rotatePoseVector(vectors.knee_right_from_hip || [0, 0], hipRightRotation));
    const ankleRight = addPosePoints(kneeRight, rotatePoseVector(vectors.ankle_right_from_knee || [0, 0], hipRightRotation + kneeRightRotation));
    return {
        root,
        pelvis,
        torso,
        neck,
        head,
        shoulder_left: shoulderLeft,
        elbow_left: elbowLeft,
        wrist_left: wristLeft,
        shoulder_right: shoulderRight,
        elbow_right: elbowRight,
        wrist_right: wristRight,
        hip_left: hipLeft,
        knee_left: kneeLeft,
        ankle_left: ankleLeft,
        hip_right: hipRight,
        knee_right: kneeRight,
        ankle_right: ankleRight,
    };
}

function manualFrameAdjustmentEntries(frame) {
    const transforms = manualFrameTransforms(frame);
    const repairs = manualFrameRepairs(frame);
    const patches = manualFramePatches(frame);
    return [
        ...Object.entries(transforms || {}).flatMap(([key, value]) => {
        if (key === "root_offset") {
            if (!Array.isArray(value) || (!value[0] && !value[1])) return [];
            return [{ label: "Root Offset", value: `${Number(value[0] || 0).toFixed(1)}, ${Number(value[1] || 0).toFixed(1)}` }];
        }
        if (typeof value !== "number" || Math.abs(value) < 0.01) return [];
        return [{ label: humanizeKey(key), value: `${value.toFixed(1)}deg` }];
        }),
        ...Object.entries(repairs || {}).map(([partName, repair]) => ({
            label: `${humanizeKey(partName)} Repair`,
            value: repair?.summary || repair?.variant_id || "custom variant",
        })),
        ...Object.values(patches || {}).map((patch) => ({
            label: `${humanizeKey(patch?.source_part_name || "part")} Patch`,
            value: `behind ${humanizeKey(patch?.keep_behind_part_name || "selected part")}`,
        })),
    ];
}

function manualFrameHasEdits(frame) {
    return manualFrameAdjustmentEntries(frame).length > 0;
}

function manualPoseRole(part) {
    return part?.part_role || part?.part_name || "";
}

function manualPosePreviewRotations(project, rig, transforms) {
    const values = transforms || {};
    if (rig?.rig_profile === "side_knight_simple_7" || rig?.rig_profile === "side_knight_dual_leg_8") {
        const propChainRotation = Number(values.shoulder_front_rotation || 0) + Number(values.weapon_rotation || 0);
        const rotations = {
            head: Number(values.head_rotation || 0),
            torso_pelvis: Number(values.torso_rotation || 0),
            front_arm: Number(values.shoulder_front_rotation || 0),
            front_leg: Number(values.hip_front_rotation || 0),
            weapon: propChainRotation,
            cape_back: Number(values.torso_rotation || 0) + Number(values.cape_back_rotation_bias || 0),
            front_cloth: (Number(values.torso_rotation || 0) * 0.45) + Number(values.front_cloth_rotation_bias || 0),
            shield: Number(values.torso_rotation || 0),
            back_leg: rig?.rig_profile === "side_knight_dual_leg_8" ? Number(values.hip_back_rotation || 0) : Number(values.torso_rotation || 0) * 0.35,
        };
        return rotations;
    }
    const propRotation = Number(values.prop_rotation || 0);
    return {
        hair_back: Number(values.head_rotation || 0),
        head: Number(values.head_rotation || 0),
        hair_front: Number(values.head_rotation || 0),
        torso: Number(values.torso_rotation || 0),
        pelvis: Number(values.pelvis_rotation || 0),
        upper_arm_left: Number(values.shoulder_left_rotation || 0),
        lower_arm_left: Number(values.shoulder_left_rotation || 0) + Number(values.elbow_left_rotation || 0),
        hand_left: Number(values.shoulder_left_rotation || 0) + Number(values.elbow_left_rotation || 0),
        upper_arm_right: Number(values.shoulder_right_rotation || 0),
        lower_arm_right: Number(values.shoulder_right_rotation || 0) + Number(values.elbow_right_rotation || 0),
        hand_right: Number(values.shoulder_right_rotation || 0) + Number(values.elbow_right_rotation || 0),
        upper_leg_left: Number(values.hip_left_rotation || 0),
        lower_leg_left: Number(values.hip_left_rotation || 0) + Number(values.knee_left_rotation || 0),
        foot_left: Number(values.hip_left_rotation || 0) + Number(values.knee_left_rotation || 0) + Number(values.ankle_left_rotation || 0),
        upper_leg_right: Number(values.hip_right_rotation || 0),
        lower_leg_right: Number(values.hip_right_rotation || 0) + Number(values.knee_right_rotation || 0),
        foot_right: Number(values.hip_right_rotation || 0) + Number(values.knee_right_rotation || 0) + Number(values.ankle_right_rotation || 0),
        prop: propRotation,
        weapon: propRotation,
        accessory_front: Number(values.torso_rotation || 0),
        accessory_back: Number(values.torso_rotation || 0),
    };
}

function manualPosePreviewParts(project, rig, transforms) {
    const parts = [...(project?.sprite_model?.parts || [])].sort((left, right) => Number(left.draw_order || 0) - Number(right.draw_order || 0));
    if (!parts.length || !rig) return [];
    const frameEntry = manualFrameEntry(transforms);
    const frameTransforms = frameEntry.transforms || {};
    const partRepairs = frameEntry.part_repairs || {};
    const correctivePatches = frameEntry.corrective_patches || {};
    const partsByName = Object.fromEntries(parts.map((part) => [part.part_name, part]));
    const joints = computeManualPoseJoints(rig, frameTransforms || {});
    const neutralJoints = rig.rig_joint_map || {};
    const rotations = manualPosePreviewRotations(project, rig, frameTransforms || {});
    const renderPart = (part, imagePath, extra = {}) => {
        const parentJoint = part.parent_joint;
        const currentJoint = joints[parentJoint];
        const neutralJoint = neutralJoints[parentJoint];
        const bbox = validBBox(part.bbox) ? part.bbox.map((value) => Number(value)) : null;
        const pivot = Array.isArray(part.pivot_point) ? [Number(part.pivot_point[0] || 0), Number(part.pivot_point[1] || 0)] : [0, 0];
        if (!currentJoint || !neutralJoint || !bbox || !imagePath) return null;
        const neutralPivot = [bbox[0] + pivot[0], bbox[1] + pivot[1]];
        const neutralOffset = [neutralPivot[0] - Number(neutralJoint[0] || 0), neutralPivot[1] - Number(neutralJoint[1] || 0)];
        const rotation = Number(rotations[manualPoseRole(part)] || 0);
        const rotatedOffset = rotatePoseVector(neutralOffset, rotation);
        const pivotWorld = [Number(currentJoint[0] || 0) + rotatedOffset[0], Number(currentJoint[1] || 0) + rotatedOffset[1]];
        const width = Math.max(1, bbox[2] - bbox[0]);
        const height = Math.max(1, bbox[3] - bbox[1]);
        const translateX = pivotWorld[0] - pivot[0];
        const translateY = pivotWorld[1] - pivot[1];
        return {
            src: `${projectAsset(project, imagePath)}?v=${project.updated_at}`,
            alt: extra.alt || part.part_name,
            width,
            height,
            translateX,
            translateY,
            rotation,
            pivotX: pivot[0],
            pivotY: pivot[1],
            repaired: Boolean(extra.repaired),
            patched: Boolean(extra.patched),
            drawOrder: Number(extra.drawOrder ?? part.draw_order ?? 0),
        };
    };
    const rendered = [];
    parts.forEach((part) => {
        Object.values(correctivePatches)
            .filter((patch) => patch?.keep_behind_part_name === part.part_name)
            .forEach((patch) => {
                const sourcePart = partsByName[patch?.source_part_name];
                if (!sourcePart) return;
                const patchRendered = renderPart(sourcePart, patch?.image_path, {
                    alt: patch?.patch_id || `patch-${sourcePart.part_name}`,
                    patched: true,
                    drawOrder: Number(part.draw_order || 0) - 0.5,
                });
                if (patchRendered) rendered.push(patchRendered);
            });
        const repair = partRepairs[part.part_name];
        const imagePath = repair?.image_path || part.image_path;
        const partRendered = renderPart(part, imagePath, { repaired: Boolean(repair) });
        if (partRendered) rendered.push(partRendered);
    });
    return rendered.sort((left, right) => Number(left.drawOrder || 0) - Number(right.drawOrder || 0));
}

function manualPosePreviewMarkup(project, rig, transforms, { compact = false } = {}) {
    const rendered = manualPosePreviewParts(project, rig, transforms);
    if (!rendered.length) return `<div class="empty">No sprite parts available for live pose preview yet.</div>`;
    if (compact) {
        const sw = SPRITE_EDITOR_SIZE.width;
        const sh = SPRITE_EDITOR_SIZE.height;
        const svgParts = rendered.map((p) =>
            `<image href="${p.src}" x="0" y="0" width="${p.width}" height="${p.height}" transform="translate(${p.translateX},${p.translateY}) rotate(${p.rotation},${p.pivotX},${p.pivotY})" />`
        ).join("");
        return `<svg class="manual-pose-thumb-svg" viewBox="0 0 ${sw} ${sh}" preserveAspectRatio="xMidYMid meet">${svgParts}</svg>`;
    }
    const partMarkup = rendered.map((p) =>
        `<img class="manual-pose-live-part" src="${p.src}" alt="${p.alt}" style="width:${p.width}px;height:${p.height}px;transform:translate(${p.translateX}px, ${p.translateY}px) rotate(${p.rotation}deg);transform-origin:${p.pivotX}px ${p.pivotY}px;">`
    ).join("");
    return `<div class="manual-pose-live-stage">${partMarkup}</div>`;
}

function manualPoseHandles(project = state.activeProject) {
    const rig = project?.rig;
    if (!rig) return [];
    const limits = rig.per_joint_rotation_limits || {};
    if (rig.rig_profile === "side_knight_simple_7" || rig.rig_profile === "side_knight_dual_leg_8") {
        return [
            { id: "root", label: "Body", mode: "translate", joint: "root" },
            { id: "torso_rotation", label: "Torso", mode: "rotate", channel: "torso_rotation", parent: "root", child: "torso", min: limits.torso?.min ?? -12, max: limits.torso?.max ?? 12, baseOffset: () => 0 },
            { id: "head_rotation", label: "Head", mode: "rotate", channel: "head_rotation", parent: "neck", child: "head", min: limits.head?.min ?? -18, max: limits.head?.max ?? 18, baseOffset: (frame) => Number(frame?.torso_rotation || 0) },
            { id: "shoulder_front_rotation", label: "Arm", mode: "rotate", channel: "shoulder_front_rotation", parent: "shoulder_front", child: "wrist_front", min: limits.shoulder_front?.min ?? -40, max: limits.shoulder_front?.max ?? 40, baseOffset: (frame) => Number(frame?.torso_rotation || 0) * 0.2 },
            { id: "hip_front_rotation", label: "Front Leg", mode: "rotate", channel: "hip_front_rotation", parent: "hip_front", child: "ankle_front", min: limits.hip_front?.min ?? -22, max: limits.hip_front?.max ?? 22, baseOffset: () => 0 },
            { id: "weapon_rotation", label: "Weapon", mode: "rotate", channel: "weapon_rotation", parent: "wrist_front", child: "weapon_tip", neutralVector: [26, 2], min: -45, max: 45, baseOffset: (frame) => Number(frame?.shoulder_front_rotation || 0) + (Number(frame?.torso_rotation || 0) * 0.2) },
            { id: "cape_back_rotation_bias", label: "Cape", mode: "rotate", channel: "cape_back_rotation_bias", parent: "torso", child: "cape_tip", neutralVector: [-18, 28], min: -35, max: 35, baseOffset: (frame) => Number(frame?.torso_rotation || 0) },
            { id: "front_cloth_rotation_bias", label: "Front Cloth", mode: "rotate", channel: "front_cloth_rotation_bias", parent: "root", child: "front_cloth_tip", neutralVector: [10, 30], min: -25, max: 25, baseOffset: (frame) => Number(frame?.torso_rotation || 0) * 0.45 },
            ...(rig.rig_profile === "side_knight_dual_leg_8"
                ? [{ id: "hip_back_rotation", label: "Back Leg", mode: "rotate", channel: "hip_back_rotation", parent: "hip_back", child: "ankle_back", min: limits.hip_back?.min ?? -18, max: limits.hip_back?.max ?? 18, baseOffset: () => 0 }]
                : []),
        ];
    }
    return [
        { id: "root", label: "Body", mode: "translate", joint: "root" },
        { id: "pelvis_rotation", label: "Pelvis", mode: "rotate", channel: "pelvis_rotation", parent: "root", child: "pelvis", min: limits.pelvis?.min ?? -20, max: limits.pelvis?.max ?? 20, baseOffset: () => 0 },
        { id: "torso_rotation", label: "Torso", mode: "rotate", channel: "torso_rotation", parent: "pelvis", child: "torso", min: limits.torso?.min ?? -12, max: limits.torso?.max ?? 12, baseOffset: () => 0 },
        { id: "head_rotation", label: "Head", mode: "rotate", channel: "head_rotation", parent: "neck", child: "head", min: limits.head?.min ?? -18, max: limits.head?.max ?? 18, baseOffset: (frame) => Number(frame?.torso_rotation || 0) * 0.15 },
        { id: "shoulder_left_rotation", label: "L Arm", mode: "rotate", channel: "shoulder_left_rotation", parent: "shoulder_left", child: "elbow_left", min: limits.shoulder_left?.min ?? -40, max: limits.shoulder_left?.max ?? 40, baseOffset: (frame) => Number(frame?.torso_rotation || 0) * 0.2 },
        { id: "elbow_left_rotation", label: "L Forearm", mode: "rotate", channel: "elbow_left_rotation", parent: "elbow_left", child: "wrist_left", min: limits.elbow_left?.min ?? -5, max: limits.elbow_left?.max ?? 55, baseOffset: (frame) => Number(frame?.shoulder_left_rotation || 0) + (Number(frame?.torso_rotation || 0) * 0.2) },
        { id: "shoulder_right_rotation", label: "R Arm", mode: "rotate", channel: "shoulder_right_rotation", parent: "shoulder_right", child: "elbow_right", min: limits.shoulder_right?.min ?? -40, max: limits.shoulder_right?.max ?? 40, baseOffset: (frame) => Number(frame?.torso_rotation || 0) * 0.2 },
        { id: "elbow_right_rotation", label: "R Forearm", mode: "rotate", channel: "elbow_right_rotation", parent: "elbow_right", child: "wrist_right", min: limits.elbow_right?.min ?? -5, max: limits.elbow_right?.max ?? 55, baseOffset: (frame) => Number(frame?.shoulder_right_rotation || 0) + (Number(frame?.torso_rotation || 0) * 0.2) },
        { id: "hip_left_rotation", label: "L Leg", mode: "rotate", channel: "hip_left_rotation", parent: "hip_left", child: "knee_left", min: limits.hip_left?.min ?? -28, max: limits.hip_left?.max ?? 28, baseOffset: () => 0 },
        { id: "knee_left_rotation", label: "L Shin", mode: "rotate", channel: "knee_left_rotation", parent: "knee_left", child: "ankle_left", min: limits.knee_left?.min ?? -4, max: limits.knee_left?.max ?? 45, baseOffset: (frame) => Number(frame?.hip_left_rotation || 0) },
        { id: "hip_right_rotation", label: "R Leg", mode: "rotate", channel: "hip_right_rotation", parent: "hip_right", child: "knee_right", min: limits.hip_right?.min ?? -28, max: limits.hip_right?.max ?? 28, baseOffset: () => 0 },
        { id: "knee_right_rotation", label: "R Shin", mode: "rotate", channel: "knee_right_rotation", parent: "knee_right", child: "ankle_right", min: limits.knee_right?.min ?? -4, max: limits.knee_right?.max ?? 45, baseOffset: (frame) => Number(frame?.hip_right_rotation || 0) },
    ];
}

function updateManualPoseDraft(handle, point, project = state.activeProject) {
    const clip = selectedManualClip(project);
    const rig = project?.rig;
    const draft = syncManualPoseDraft(project);
    if (!clip || !rig || !draft) return;
    if (handle.mode === "translate") {
        const origin = rig.rig_joint_map?.[handle.joint] || [0, 0];
        draft.root_offset = [
            Number((point[0] - origin[0]).toFixed(2)),
            Number((point[1] - origin[1]).toFixed(2)),
        ];
        return;
    }
    const joints = computeManualPoseJoints(rig, draft);
    const neutralParent = rig.rig_joint_map?.[handle.parent];
    const neutralChild = rig.rig_joint_map?.[handle.child];
    if (!joints[handle.parent]) return;
    const neutralAngle = neutralParent && neutralChild
        ? angleDegrees(neutralParent, neutralChild)
        : handle.neutralVector
            ? angleDegrees([0, 0], handle.neutralVector)
            : null;
    if (neutralAngle == null) return;
    const pointerAngle = angleDegrees(joints[handle.parent], point);
    const baseOffset = typeof handle.baseOffset === "function" ? Number(handle.baseOffset(draft) || 0) : 0;
    const raw = normalizeAngle(pointerAngle - neutralAngle - baseOffset);
    draft[handle.channel] = Number(clamp(raw, handle.min, handle.max).toFixed(2));
}

function updateManualPoseStageDOM(stage, project, draftFrame, dragState) {
    if (!stage || !project) return;
    const rig = project?.rig;
    const handles = manualPoseHandles(project);
    const joints = computeManualPoseJoints(rig, draftFrame || {});
    const svg = stage.querySelector("svg");
    if (!svg || !joints) return;
    const activeId = dragState?.activeHandleId;
    const activePoint = dragState?.activeHandlePoint;
    const rotateHandles = handles.filter((h) => h.mode === "rotate" && joints[h.parent] && joints[h.child]);
    const lines = svg.querySelectorAll("line.manual-pose-line");
    rotateHandles.forEach((handle, i) => {
        const line = lines[i];
        if (!line) return;
        const [x1, y1] = joints[handle.parent];
        const [x2, y2] = joints[handle.child];
        line.setAttribute("x1", String(x1));
        line.setAttribute("y1", String(y1));
        line.setAttribute("x2", String(x2));
        line.setAttribute("y2", String(y2));
    });
    svg.querySelectorAll("[data-manual-handle]").forEach((g) => {
        const handle = handles.find((h) => h.id === g.dataset.manualHandle);
        if (!handle) return;
        const isActive = activeId === handle.id && Array.isArray(activePoint) && activePoint.length >= 2;
        const point = isActive ? activePoint : (handle.mode === "translate" ? joints[handle.joint] : joints[handle.child]);
        if (!point) return;
        const circle = g.querySelector("circle");
        const text = g.querySelector("text");
        if (circle) {
            circle.setAttribute("cx", String(point[0]));
            circle.setAttribute("cy", String(point[1]));
        }
        if (text) {
            text.setAttribute("x", String(point[0] + 12));
            text.setAttribute("y", String(point[1] - 12));
        }
    });
    if (activeId) {
        const activeGroup = svg.querySelector(`[data-manual-handle="${activeId}"]`);
        if (activeGroup && activeGroup.parentNode === svg) {
            svg.appendChild(activeGroup);
        }
    }
}

async function saveManualPoseFrame(project, clip, transforms, successMessage = "") {
    if (!project || !clip) return;
    const payloadTransforms = manualFrameTransforms(transforms);
    await api(`/api/projects/${project.project_id}/manual-clips/${clip.clip_id}/frame/${state.selectedManualClipFrame}`, {
        method: "POST",
        body: JSON.stringify({ transforms: payloadTransforms || {} }),
    });
    state.manualPoseDraft = null;
    await loadProject(project.project_id, currentMode());
    if (successMessage) notify(successMessage, "success");
}

function bindManualPoseStageInteractions(stage, project, clip, frame, handles) {
    if (!stage || !project || !clip) return;
    stage.querySelectorAll("[data-manual-handle]").forEach((node) => {
        const handle = handles.find((item) => item.id === node.dataset.manualHandle);
        if (!handle) return;
        const dragTarget = node.querySelector("circle.manual-pose-handle");
        if (!dragTarget) return;
        dragTarget.addEventListener("mousedown", (event) => {
            event.preventDefault();
            state.manualPoseDrag = { clipId: clip.clip_id, frameIndex: state.selectedManualClipFrame, handleId: handle.id };
            const move = (moveEvent) => {
                const point = sourcePointFromEvent(moveEvent, stage);
                updateManualPoseDraft(handle, point, project);
                const pointForDisplay = sourcePointFromEvent(moveEvent, stage, false);
                updateManualPoseStageDOM(stage, project, state.manualPoseDraft, {
                    activeHandleId: handle.id,
                    activeHandlePoint: pointForDisplay,
                });
                const liveEl = document.getElementById("manual-pose-live-preview-container");
                if (liveEl && project?.rig) {
                    liveEl.innerHTML = manualPosePreviewMarkup(project, project.rig, currentManualClipFrameEntry(project) || {});
                }
            };
            const finish = () => {
                window.removeEventListener("mousemove", move);
                window.removeEventListener("mouseup", finish);
                state.manualPoseDrag = null;
                updateManualPoseStageDOM(stage, project, state.manualPoseDraft);
            };
            window.addEventListener("mousemove", move);
            window.addEventListener("mouseup", finish, { once: true });
        });
    });
}
