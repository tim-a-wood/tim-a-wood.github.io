function createStorage() {
    try {
        const storage = window.localStorage;
        const probeKey = "__spriteWorkbenchProbe__";
        storage.setItem(probeKey, "1");
        storage.removeItem(probeKey);
        return storage;
    } catch (error) {
        const memory = new Map();
        return {
            getItem(key) {
                return memory.has(key) ? memory.get(key) : null;
            },
            setItem(key, value) {
                memory.set(key, String(value));
            },
            removeItem(key) {
                memory.delete(key);
            },
        };
    }
}

function detectWorkbenchOrigin() {
    const explicit = new URLSearchParams(window.location.search).get("api");
    if (explicit) return explicit.replace(/\/$/, "");
    if (window.location.protocol === "file:") return `http://127.0.0.1:${DEFAULT_WORKBENCH_PORT}`;
    if (!window.location.hostname) return `http://127.0.0.1:${DEFAULT_WORKBENCH_PORT}`;
    // HTTP(S): `sprite_workbench_server.py` serves both `/api/...` and static files from the same
    // origin as this page. Do not assume DEFAULT_WORKBENCH_PORT — users may run `--port` otherwise
    // previews would 404 while JSON still loads if a proxy mixed origins. Use `?api=` to override.
    return "";
}

const storage = createStorage();
const WORKBENCH_ORIGIN = detectWorkbenchOrigin();
const WORKBENCH_BASE = WORKBENCH_ORIGIN
    ? `${WORKBENCH_ORIGIN}/tools/2d-sprite-and-animation`
    : `${window.location.origin}/tools/2d-sprite-and-animation`;
const SPRITE_EDITOR_SIZE = { width: 640, height: 768 };
const CLIP_CONTROL_META = {
    body_bob: { label: "Body Bob", min: 0, max: 16, step: 0.5 },
    torso_lean: { label: "Torso Lean", min: 0, max: 12, step: 0.5 },
    arm_swing: { label: "Arm Swing", min: 0, max: 28, step: 0.5 },
    leg_swing: { label: "Leg Swing", min: 0, max: 28, step: 0.5 },
    foot_lift: { label: "Foot Lift", min: 0, max: 24, step: 0.5 },
    prop_lag: { label: "Prop Lag", min: 0, max: 12, step: 0.5 },
};

const state = {
    health: null,
    projects: [],
    activeProject: null,
    includeArchived: storage.getItem(STORAGE_KEYS.includeArchived) === "1",
    selectedRunId: null,
    compareRightId: null,
    zoomConceptId: null,
    swapCompareView: false,
    selectedSpritePart: null,
    selectedRevisionId: null,
    selectedClip: "idle",
    selectedClipFrame: 0,
    selectedClipPart: null,
    selectedManualClipId: null,
    selectedManualClipFrame: 0,
    selectedManualPatchSourcePart: null,
    selectedManualPatchOccluderPart: null,
    manualPatchCandidates: [],
    manualPatchBusy: false,
    manualPoseDraft: null,
    manualPoseDraftKey: null,
    manualPoseDrag: null,
    manualPoseModalOpen: false,
    manualPreviewZoom: 1,
    manualPreviewPanX: 0,
    manualPreviewPanY: 0,
    previousSpriteModel: null,
    spriteEditorMode: "move",
    selectedShapePart: null,
    partShapeHistory: [],
    partShapeHistoryIndex: -1,
    partShapeView: { zoom: 1, panX: 0, panY: 0, fitted: false, sourceOpacity: 0.7 },
    spriteRecoveryVariants: {},
    uiMode: "wizard",
    activity: null,
    clipPreviewTimers: {},
    conceptSourceMode: "text",
    lastConceptScaffold: null,
    lastIterationScaffold: null,
    conceptUiSelectedId: null,
    lastIteratedConceptId: null,
    conceptPreviewDisplayCache: {},
    exportSheetPreviewDisplayCache: {},
    pixellabShowSkeleton: false,
    pixellabAnimTimers: {},
    pixellabCreateCharacterBusy: false,
    /** While set, Animations panel shows a wait bar and disables generate/build controls. */
    pixellabAnimGenBusy: null,
};

function stageDisplayName(stage) {
    return FRIENDLY_STAGE_NAMES[stage] || stage || "Idle";
}

function jobDisplayName(jobType) {
    return JOB_TYPE_LABELS[jobType] || jobType || "Working";
}

function humanizeKey(value) {
    return String(value || "")
        .replace(/_/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

const FLIGHTDECK_PHASES = [
    { key: "describe", label: "Describe", description: "Creative brief", sectionId: "intake" },
    { key: "concepts", label: "Concepts", description: "Pick the look", sectionId: "concepts" },
    { key: "animations", label: "Animations", description: "Motion passes", sectionId: "animations" },
    { key: "export", label: "Review & Export", description: "Package output", sectionId: "review-export" },
];

function phaseKeyForStep(step) {
    if (["describe", "project", "brief", "references"].includes(step)) return "describe";
    if (["concepts", "review", "character", "rig_layout", "part_manifest", "part_shape_edit", "split_build", "split_review", "sprite_model", "rig"].includes(step)) return "concepts";
    if (["animations", "clips", "qa"].includes(step)) return "animations";
    if (step === "export") return "export";
    return "describe";
}

function phaseMetaByKey(key) {
    return FLIGHTDECK_PHASES.find((phase) => phase.key === key) || FLIGHTDECK_PHASES[0];
}

function activePhaseMeta(project = state.activeProject) {
    const step = project?.wizard_state?.current_step || project?.recommended_next_step || activeWizardStep();
    return phaseMetaByKey(phaseKeyForStep(step));
}

function pixellabResolveDirectionBlock(directions, direction) {
    const normDir = String(direction || "east").trim();
    if (!directions || typeof directions !== "object") return { block: null, key: null };
    if (Object.prototype.hasOwnProperty.call(directions, normDir)) {
        return { block: directions[normDir], key: normDir };
    }
    const key = Object.keys(directions).find((k) => k.toLowerCase() === normDir.toLowerCase());
    if (key) return { block: directions[key], key };
    return { block: null, key: null };
}

function pixellabDirectionHasFramesInEntry(animEntry, direction) {
    const dirs = animEntry?.directions;
    const { block } = pixellabResolveDirectionBlock(dirs, direction);
    const frames = block?.frames;
    return Array.isArray(frames) && frames.length > 0;
}

function pixellabAnyDirectionHasFrames(animEntry) {
    if (!animEntry?.directions || typeof animEntry.directions !== "object") return false;
    return Object.keys(animEntry.directions).some((k) => {
        const fr = animEntry.directions[k]?.frames;
        return Array.isArray(fr) && fr.length > 0;
    });
}

/** Prefer first character direction that actually has frames (custom anims are often east-only). */
function pixellabFirstPreviewDirection(characterDirs, animEntry) {
    const order = Array.isArray(characterDirs) && characterDirs.length ? characterDirs : ["east"];
    for (const d of order) {
        if (pixellabDirectionHasFramesInEntry(animEntry, d)) return d;
    }
    if (animEntry?.directions && typeof animEntry.directions === "object") {
        for (const k of Object.keys(animEntry.directions)) {
            const fr = animEntry.directions[k]?.frames;
            if (Array.isArray(fr) && fr.length > 0) return k;
        }
    }
    return order[0] || "east";
}

function pixellabPreviewFrameUrls(project, animName, direction) {
    const normDir = String(direction || "east").trim();
    const anim = project?.pixellab_animations?.animations?.[animName];
    let block = null;
    let resolvedKey = null;
    if (anim?.directions) {
        const r = pixellabResolveDirectionBlock(anim.directions, normDir);
        block = r.block;
        resolvedKey = r.key;
    }
    let frames = Array.isArray(block?.frames) ? block.frames : [];

    const store = project?.pixellab_animations;
    const v = encodeURIComponent(
        [
            project?.updated_at || "",
            store && typeof store === "object" ? store.updated_at || "" : "",
            block?.updated_at || "",
            resolvedKey || "",
            anim?.frame_count ?? "",
            anim?.fps ?? "",
        ].join("|"),
    );
    return frames.map((rel) => `${projectAsset(project, rel)}?v=${v}`);
}

function pixellabAnimationStoreHasFrames(project) {
    const anims = project?.pixellab_animations?.animations;
    if (!anims || typeof anims !== "object") return false;
    for (const entry of Object.values(anims)) {
        if (!entry || typeof entry !== "object") continue;
        const dirs = entry.directions;
        if (!dirs || typeof dirs !== "object") continue;
        for (const data of Object.values(dirs)) {
            const frames = data && Array.isArray(data.frames) ? data.frames : [];
            if (frames.length > 0) {
                return true;
            }
        }
    }
    return false;
}

function pixellabCharacterApproved(project) {
    if (!project) return false;
    if (project.pixellab_character_approved) return true;
    const c = project.pixellab_character;
    if (!c || typeof c !== "object") return false;
    return Boolean(c.approved || c.pixellab_character_approved);
}

/** Cache-bust asset URLs when the Pixel Lab character or project changes (updated_at alone may stay stale). */
function pixellabCharacterAssetVersion(project, pix = project?.pixellab_character) {
    const p = project || {};
    const c = pix && typeof pix === "object" ? pix : {};
    return encodeURIComponent(
        [p.updated_at || "", c.character_id || "", c.created_at || "", String(c.seed ?? "")].join("|"),
    );
}

function aiWorkflowStore(project = state.activeProject) {
    return project?.ai_workflow || null;
}

function aiWorkflowEnabled(project = state.activeProject) {
    return Boolean(aiWorkflowStore(project)?.enabled) && !Boolean(aiWorkflowStore(project)?.legacy_mode);
}

function aiWorkflowLegacyMode(project = state.activeProject) {
    return Boolean(aiWorkflowStore(project)?.legacy_mode);
}

function aiWorkflowRunGroup(groupName, clipName = null, project = state.activeProject) {
    const store = aiWorkflowStore(project);
    if (!store) return null;
    if (!clipName) return store[groupName] || null;
    return store[groupName]?.[clipName] || null;
}

function aiWorkflowApprovedRun(groupName, clipName = null, project = state.activeProject) {
    const group = aiWorkflowRunGroup(groupName, clipName, project);
    if (!group) return null;
    const runId = group.approved_run_id;
    return runId ? group.runs?.[runId] || null : null;
}

function visibleWizardSteps(project = state.activeProject) {
    if (!aiWorkflowEnabled(project)) return WIZARD_STEPS;
    // Phase 7.7: five Pixel Lab steps or four steps for other AI backends (no Animations panel).
    if (String(project?.brief?.backend_mode || "") === "pixellab") {
        return ["describe", "concepts", "character", "animations", "export"];
    }
    return ["describe", "concepts", "character", "export"];
}

function wizardProgressSummary(project) {
    const statuses = project?.step_statuses || {};
    const completed = Object.values(statuses).filter((status) => status === "complete").length;
    const total = visibleWizardSteps(project).length;
    return `${completed}/${total} steps complete`;
}

function normalizeErrorMessage(message) {
    const text = String(message || "").replace(/\s+/g, " ").trim();
    if (!text) return "Something went wrong. Try again.";
    if (text.includes("ComfyUI backend unavailable") || text.includes("Connection refused")) {
        return "The image generator is not reachable. Make sure ComfyUI is running, then try again.";
    }
    if (text.includes("Unsupported input:")) {
        return "This version only supports one side-view humanoid character with one main held item. Simplify the prompt and try again.";
    }
    if (text.includes("Refinement target value is required")) {
        return "Describe what you want to change before generating adjusted looks.";
    }
    if (text.includes("Refinement must change exactly one supported major attribute group")) {
        return "Change one major thing at a time when adjusting a look.";
    }
    if (text.includes("master-pose/select requires candidate_id")) {
        return "That legacy project still expects a master pose selection.";
    }
    if (text.includes("Master pose approval is required")) {
        return "Accept a valid concept source before building the sprite model.";
    }
    if (text.includes("Sprite model build is required")) {
        return "Build and approve the sprite model before rigging.";
    }
    if (text.includes("Sprite-model approval is required")) {
        return "Approve the sprite model before approving the rig.";
    }
    if (text.includes("Sprite model approval is blocked until build failures are resolved")) {
        return "Fix sprite-model build failures before approving it.";
    }
    if (text.includes("Layer review cannot be approved")) {
        return "Build the sprite model first, then approve it.";
    }
    if (text.includes("Rig review approval is required before production")) {
        return "Approve the rig before building animations.";
    }
    if (text.includes("Build the rig before editing clips")) {
        return "Build the rig before editing idle or walk controls.";
    }
    if (text.includes("Export blocked: QA must pass first")) {
        return "Checks must pass before export is available.";
    }
    if (text.includes("Pixel Lab character approval is required")) {
        return "Approve the character on the Character step before generating animations.";
    }
    if (text.includes("animate requires template_animation_id")) {
        return "Pick a template in the Animations panel, then try Generate again.";
    }
    if (text.includes("Pixel Lab client unavailable") && text.includes("PIXELLAB_API_KEY")) {
        return "Set PIXELLAB_API_KEY for the workbench server, or use debug_procedural in the project brief for offline tests.";
    }
    if (text.includes("Cannot identify image") || text.includes("not raw RGBA")) {
        return "Pixel Lab returned an image the server could not decode. Check credits/API status; try again or use a smaller canvas.";
    }
    if (text.includes("Missing frame:")) {
        return "At least one animation frame is missing. Rebuild the animation and run checks again.";
    }
    if (text.includes("No earlier revision is available")) {
        return "No earlier sprite-model revision is available yet.";
    }
    if (text.includes("Revision not found")) {
        return "That sprite-model revision is no longer available.";
    }
    if (text.includes("promote-recovery requires")) {
        return "Generate recovery variants first, then choose one to promote.";
    }
    return text;
}

function notify(message, tone = "info", title = "") {
    const root = document.querySelector("#toast-stack");
    if (!root) return;
    const node = document.createElement("div");
    node.className = `toast ${tone}`;
    node.innerHTML = `
        <strong>${title || (tone === "error" ? "Something needs attention" : tone === "success" ? "Done" : "Update")}</strong>
        <p>${message}</p>
    `;
    root.appendChild(node);
    window.setTimeout(() => {
        node.remove();
    }, tone === "error" ? 6500 : 4000);
}

function setActivity(activity) {
    state.activity = activity;
    renderActivity();
}

function clearActivity() {
    state.activity = null;
    renderActivity();
}

function externalAuthoringStore(project = state.activeProject) {
    return project?.external_authoring || null;
}

function externalAuthoringEnabled(project = state.activeProject) {
    return Boolean(externalAuthoringStore(project)?.enabled);
}

function externalAuthoringBundle(project = state.activeProject) {
    return externalAuthoringStore(project)?.imported_bundle || null;
}

function syncWorkflowModeControls() {
    const aiEnabled = aiWorkflowEnabled();
    const backendMode = (state.activeProject?.brief?.backend_mode) || "comfyui";
    const productionWarning = document.querySelector("#production-warning");
    if (productionWarning) {
        if (!aiEnabled) {
            productionWarning.textContent = "Clip output is deterministic. Rebuilds from the same approved sprite model and rig should match exactly.";
        } else if (backendMode === "pixellab") {
            productionWarning.textContent = "Pixel Lab mode: approve a concept to lock the east-facing source, then generate animations from that locked source. This legacy Production panel is hidden in the guided wizard.";
        } else if (backendMode === "debug_procedural") {
            productionWarning.textContent = "AI workflow mode is active in Debug Placeholder mode. Legacy motion, extraction, and cleanup use deterministic local transforms only.";
        } else {
            productionWarning.textContent = "AI workflow mode is active. Legacy motion uses ComfyUI when configured; extraction and pixel cleanup stay local.";
        }
    }
    ["#render-idle", "#render-walk"].forEach((selector) => {
        const node = document.querySelector(selector);
        if (node) node.hidden = aiEnabled;
    });
}

function log(message, tone = "info") {
    const row = document.createElement("li");
    row.textContent = `${new Date().toLocaleTimeString()}  ${message}`;
    if (tone === "error") row.style.borderColor = "rgba(211, 122, 122, 0.32)";
    if (tone === "success") row.style.borderColor = "rgba(117, 196, 152, 0.32)";
    document.querySelector("#job-log").prepend(row);
}

async function api(path, options = {}) {
    let response;
    try {
        response = await fetch(`${WORKBENCH_ORIGIN}${path}`, {
            headers: { "Content-Type": "application/json" },
            cache: "no-store",
            ...options,
        });
    } catch (error) {
        const target = WORKBENCH_ORIGIN || window.location.origin;
        throw new Error(normalizeErrorMessage(`${error.message} (API origin: ${target})`));
    }
    if (!response.ok) {
        let message = "";
        const contentType = response.headers.get("Content-Type") || "";
        if (contentType.includes("application/json")) {
            const payload = await response.json();
            message = payload.error || payload.message || JSON.stringify(payload);
        } else {
            const text = await response.text();
            message = text.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
        }
        throw new Error(normalizeErrorMessage(message));
    }
    return response.json();
}

function stageConfig(stage) {
    const config = state.activeProject?.stage_maturity || state.health?.stage_maturity || {};
    return config[stage] || { maturity: "experimental", label: stage, description: "" };
}

function projectStageKey(stageName) {
    if (!stageName) return "intake";
    if (stageName.startsWith("production_")) return "production";
    return stageName;
}

function projectAsset(project, relativePath) {
    if (!project || !relativePath) return "";
    const rel = String(relativePath).trim().replace(/\\/g, "/").replace(/^\/+/, "");
    const encodedRel = rel
        .split("/")
        .filter((s) => s.length)
        .map((seg) => encodeURIComponent(seg))
        .join("/");
    const pid = encodeURIComponent(String(project.project_id));
    return `${WORKBENCH_BASE}/projects-data/${pid}/${encodedRel}`;
}

function roomCreationUrl(project = state.activeProject) {
    const origin = WORKBENCH_ORIGIN || (window.location.origin && window.location.origin !== "null" ? window.location.origin : "http://127.0.0.1:8766");
    const url = new URL(`${origin}/room-layout-editor.html`);
    if (project?.project_id) {
        url.searchParams.set("project_id", project.project_id);
    }
    return url.toString();
}

function updateRoomCreationLink() {
    const link = document.getElementById("room-creation-link");
    if (!link) return;
    link.href = roomCreationUrl();
}

function paidActionAllowed(label) {
    const settings = state.health?.settings || {};
    if (settings.safe_mode) {
        notify("Safe mode is enabled for this workbench, so paid generation is currently blocked.", "error");
        return false;
    }
    if (settings.confirm_paid_actions !== false) {
        const ok = window.confirm(`${label} will call an external model and may spend credits. Continue?`);
        if (!ok) return false;
    }
    return true;
}

/** Relative paths from animation_clips when Pixel Lab wrote per-frame PNGs (e.g. animations/idle/south/frame_00.png). */
function pixellabAnimationClipFrameRels(project, clipName) {
    if (!project || clipName == null) return null;
    if (String(project.brief?.backend_mode || "") !== "pixellab") return null;
    const frames = project.animation_clips?.[clipName]?.frames;
    return Array.isArray(frames) && frames.length ? frames : null;
}

/** Built frame preview URL: Pixel Lab bridge uses animation_clips.*.frames; deterministic rig uses animations/<clip>/<clip>_NN.png. */
function animationClipFramePreviewUrl(project, clipName, frameIndex) {
    if (!project || clipName == null) return null;
    const rels = pixellabAnimationClipFrameRels(project, clipName);
    const idx = Math.max(0, Number(frameIndex) || 0);
    if (rels && rels[idx]) {
        return `${projectAsset(project, rels[idx])}?v=${project.updated_at}`;
    }
    if (project.build_status?.[`${clipName}_render_complete`]) {
        return `${projectAsset(project, `animations/${clipName}/${clipName}_${String(idx).padStart(2, "0")}.png`)}?v=${project.updated_at}`;
    }
    return null;
}

function formatDate(value) {
    if (!value) return "n/a";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
}

function formatDuration(seconds) {
    if (seconds == null) return "n/a";
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
}

function renderStageMeta() {
    document.querySelectorAll(".stage-meta").forEach((node) => {
        const stage = node.dataset.stage;
        const config = stageConfig(stage);
        node.innerHTML = `
            <span class="badge ${config.maturity}">${config.maturity}</span>
            <p>${config.description || ""}</p>
        `;
    });
}

function getReviewCounts(metrics) {
    const approvals = Object.values(metrics?.approvals_per_run || {}).reduce((sum, value) => sum + value, 0);
    const promptIterations = state.activeProject?.prompt_history?.length || 0;
    return { approvals, refinements: promptIterations };
}


function renderStatus() {
    const project = state.activeProject;
    const backend = state.health?.backend;
    const pixellab = state.health?.pixellab;

    document.querySelector("#status-project").textContent = project ? project.project_name : "None";
    document.querySelector("#status-stage").textContent = project ? stageDisplayName(project.current_stage) : "Idle";
    document.querySelector("#status-backend").textContent = project?.brief?.backend_mode === "debug_procedural"
        ? "Debug (offline)"
        : project?.brief?.backend_mode === "pixellab"
            ? "Pixel Lab"
            : backend?.ok
                ? "ComfyUI (legacy, ready)"
                : backend?.backend === "comfyui"
                    ? "ComfyUI (legacy, unavailable)"
                    : "Unknown";
    document.querySelector("#status-qa").textContent = project?.qa_report?.status || "Blocked";

    const pixellabCredits = document.querySelector("#status-pixellab-credits");
    if (pixellabCredits) {
        if (!pixellab) {
            pixellabCredits.textContent = "PL: unknown";
        } else if (!pixellab.configured) {
            pixellabCredits.textContent = "PL: not configured";
        } else if (pixellab.error) {
            pixellabCredits.textContent = "PL: error";
        } else {
            const credits = pixellab.credits_remaining ?? pixellab.balance?.usd ?? pixellab.balance?.credits_remaining;
            const numeric = credits == null ? null : Number(credits);
            const formatted = numeric == null || Number.isNaN(numeric) ? String(credits) : numeric.toFixed(2).replace(/\.00$/, "");
            pixellabCredits.textContent = `PL: ${formatted} credits`;
        }
    }
    const projectName = project?.project_name || "No project selected";
    const sidebarName = document.querySelector("#sidebar-project-name");
    const mobileName = document.querySelector("#mobile-project-name");
    if (sidebarName) sidebarName.textContent = projectName;
    if (mobileName) mobileName.textContent = projectName;
}

function renderSidebarWarnings() {
    const block = document.querySelector("#sidebar-warning-block");
    const root = document.querySelector("#sidebar-warning-summary");
    if (!block || !root) return;
    const project = state.activeProject;
    if (!project) {
        block.hidden = true;
        root.innerHTML = "";
        return;
    }
    const report = project.health_report || {};
    const warnings = Array.isArray(report.warnings) ? report.warnings : [];
    const actions = Array.isArray(report.recommended_actions) ? report.recommended_actions : [];
    const items = [
        ...warnings.map((item) => ({ tone: "warning-box", title: "Warning", text: humanizeKey(item) })),
        ...actions.map((item) => ({ tone: "info-box", title: "Suggested action", text: humanizeKey(item) })),
    ];
    if (!items.length) {
        block.hidden = true;
        root.innerHTML = "";
        return;
    }
    block.hidden = false;
    root.innerHTML = items.slice(0, 4).map((item) => `
        <div class="${item.tone}">
            <p><strong>${escapeHtml(item.title)}</strong></p>
            <p class="small-note" style="margin-top:6px;">${escapeHtml(item.text)}</p>
        </div>
    `).join("");
}

function renderActivity() {
    const node = document.querySelector("#activity-dock");
    const activity = state.activity;
    if (!node || !activity) {
        node?.classList.remove("open");
        return;
    }
    document.querySelector("#activity-state").textContent = activity.state || "Working";
    document.querySelector("#activity-job-type").textContent = jobDisplayName(activity.jobType);
    document.querySelector("#activity-label").textContent = activity.label || "Working";
    document.querySelector("#activity-detail").textContent = activity.detail || "Waiting for the next update.";
    document.querySelector("#activity-progress").style.width = `${Math.max(0, Math.min(100, activity.percent || 0))}%`;
    document.querySelector("#activity-progress-text").textContent = `${Math.round(activity.percent || 0)}%`;
    document.querySelector("#activity-hint").textContent = activity.hint || "You can keep browsing while this runs.";
    node.classList.add("open");
}
