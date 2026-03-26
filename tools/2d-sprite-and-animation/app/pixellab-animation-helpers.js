const PIXELLAB_COMMON_ANIMATION_PRESETS = [
    { clipName: "idle", label: "Idle", prompt: "subtle breathing idle, slight shield sway, stable side-view stance" },
    { clipName: "walk", label: "Walk", prompt: "steady side-scrolling walk cycle with readable footfalls and gentle torso motion" },
    { clipName: "run", label: "Run", prompt: "fast side-scrolling run cycle with stronger stride, forward lean, and energetic arm swing" },
    { clipName: "jump", label: "Jump", prompt: "two-footed jump with clear anticipation, lift, hang time, and landing recovery" },
    { clipName: "attack", label: "Attack", prompt: "side-view melee attack with clear anticipation, strike, and recovery silhouette" },
    { clipName: "parry", label: "Parry", prompt: "quick defensive parry with a sharp guard motion and compact recovery" },
    { clipName: "hurt", label: "Hurt", prompt: "brief hit reaction with recoil, balance loss, and quick reset to stance" },
    { clipName: "cast", label: "Cast", prompt: "spell-casting motion with a deliberate windup, release, and magical follow-through" },
    { clipName: "die", label: "Die", prompt: "clear death or collapse animation with impact, fall, and final resting pose" },
];

const PIXELLAB_COMMON_ANIMATION_NAMES = PIXELLAB_COMMON_ANIMATION_PRESETS.map((preset) => preset.clipName);

function pixellabAnimationPresetByName(name) {
    return PIXELLAB_COMMON_ANIMATION_PRESETS.find((preset) => preset.clipName === name) || null;
}

function sortPixellabAnimationNames(names) {
    const order = new Map(PIXELLAB_COMMON_ANIMATION_NAMES.map((name, index) => [name, index]));
    return [...names].sort((a, b) => {
        const ai = order.has(a) ? order.get(a) : Number.MAX_SAFE_INTEGER;
        const bi = order.has(b) ? order.get(b) : Number.MAX_SAFE_INTEGER;
        if (ai !== bi) return ai - bi;
        return a.localeCompare(b);
    });
}

/** Normalize user input to server slug (a-z, 0-9, underscore; max 48). Returns "" if invalid. */
function normalizePixellabCustomAnimName(raw) {
    const s = String(raw || "")
        .trim()
        .toLowerCase()
        .replace(/\s+/g, "_")
        .replace(/[^a-z0-9_]/g, "");
    if (!/^[a-z][a-z0-9_]{0,47}$/.test(s)) return "";
    return s;
}

const JOB_TYPE_LABELS = {
    "concepts.generate": "Generating Gemini prompt",
    "part_split.generate": "Building split assets",
    "part_manifest.generate": "Generating part manifest",
    "part_shapes.generate": "Initializing part shapes",
    "sprite_model.build": "Building sprite model",
    "layers.build": "Building sprite model",
    "rig.build": "Building rig",
    "clips.idle.render": "Building idle clip",
    "clips.walk.render": "Building walk clip",
    "animations.idle.render": "Building idle clip",
    "animations.walk.render": "Building walk clip",
    "qa.run": "Running checks",
    export: "Exporting files",
    "pixellab.create_character": "Creating Pixel Lab character",
};

const DEFAULT_WORKBENCH_PORT = "8766";
