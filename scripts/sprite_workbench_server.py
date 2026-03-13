#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import io
import json
import math
import os
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse, unquote
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parent.parent
TOOL_DIR = ROOT / "tools" / "2d-sprite-and-animation"
PROJECTS_ROOT = TOOL_DIR / "projects-data"
WORKFLOW_DIR = TOOL_DIR / "workflows"
STAGE_MATURITY_PATH = TOOL_DIR / "stage-maturity.json"

TOOL_VERSION = "solo-ai-sprite-workbench-v2"
DEFAULT_COMFYUI_BASE_URL = os.environ.get("SPRITE_WORKBENCH_COMFYUI_URL", "http://127.0.0.1:8188")
DEFAULT_COMFYUI_CHECKPOINT = os.environ.get("SPRITE_WORKBENCH_COMFYUI_CHECKPOINT", "sd15.safetensors")


def env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default

CONCEPT_CANVAS = (640, 768)
INITIAL_CONCEPT_COUNT = 6
REFINEMENT_CONCEPT_COUNT = 4
JOB_HISTORY_LIMIT = 50
WIZARD_STEPS = ["project", "brief", "references", "concepts", "review", "refine", "build", "qa", "export"]

FRAME_SIZE = 256
FRAME_PIVOT = (128, 245)
WORKING_CANVAS = (420, 420)
RENDER_SCALE = 0.84
RENDER_CENTER = (210, 220)

COMFYUI_TIMEOUT_SECONDS = env_int("SPRITE_WORKBENCH_COMFYUI_TIMEOUT_SECONDS", 3)
COMFYUI_POLL_SECONDS = env_int("SPRITE_WORKBENCH_COMFYUI_POLL_SECONDS", 1)
COMFYUI_JOB_TIMEOUT_SECONDS = env_int("SPRITE_WORKBENCH_COMFYUI_JOB_TIMEOUT_SECONDS", 600)

REFINEMENT_STRENGTHS = {
    "subtle": 0.25,
    "medium": 0.45,
    "strong": 0.65,
}

REFERENCE_ROLES = ("identity", "costume", "style", "prop")
BACKEND_MODES = ("comfyui", "debug_procedural")
MAJOR_REFINEMENT_LOCKS = {"silhouette", "face_head_shape", "outfit", "palette", "prop"}

DEFAULT_NEGATIVE_PROMPT = (
    "front view, rear view, top-down, isometric, multiple characters, crowd, group shot, "
    "full environment scene, busy background, extra limbs, extra arms, extra weapons, "
    "wings, huge cape, non-humanoid anatomy, mount, vehicle, text, watermark, logo"
)

METROIDVANIA_PROMPT_CONTEXT = (
    "designed for Ashen Hollow, a dark-fantasy 2d side-scrolling metroidvania, "
    "Hollow Knight-inspired atmosphere with ruined chapels, catacombs, and medieval decay, "
    "player-character readability first, strict side-view silhouette, full body visible, "
    "large primary shapes, restrained secondary detail, clustered values for sprite readability, "
    "clear separation between head, torso, limbs, and held item, readable at low resolution, "
    "animation-friendly costume breakup, practical combat silhouette, "
    "plain or minimal background for character extraction"
)

HOUSE_STYLE_PROMPT_RULES = (
    "single character only, centered full body concept, orthographic side profile, no dramatic camera angle, "
    "no environment storytelling shot, one iconic held item, practical traversal and combat gear, "
    "grounded proportions, silhouette readable in motion, restrained ornamental noise"
)

REQUIRED_PARTS = [
    "head",
    "hair_front",
    "hair_back",
    "torso",
    "pelvis",
    "upper_arm_left",
    "lower_arm_left",
    "hand_left",
    "upper_arm_right",
    "lower_arm_right",
    "hand_right",
    "upper_leg_left",
    "lower_leg_left",
    "foot_left",
    "upper_leg_right",
    "lower_leg_right",
    "foot_right",
    "prop",
    "accessory_front",
    "accessory_back",
]

RIG_JOINTS = [
    "root",
    "pelvis",
    "torso",
    "neck",
    "head",
    "shoulder_left",
    "elbow_left",
    "wrist_left",
    "shoulder_right",
    "elbow_right",
    "wrist_right",
    "hip_left",
    "knee_left",
    "ankle_left",
    "hip_right",
    "knee_right",
    "ankle_right",
]

ANIMATION_SPECS = {
    "idle": {"frame_count": 6, "fps": 8, "loop": True},
    "walk": {"frame_count": 8, "fps": 10, "loop": True},
}

REJECT_PATTERNS = {
    "quadrupeds": re.compile(r"\b(quadruped|wolf|dog|cat|horse|beast on all fours)\b", re.I),
    "multi-character scenes": re.compile(r"\b(two characters|group|party|crowd|duo|trio|squad)\b", re.I),
    "wings": re.compile(r"\b(wings?|angelic wings?|feathered wings?)\b", re.I),
    "large flowing capes": re.compile(r"\b(large cape|flowing cape|billowing cape|long cape)\b", re.I),
    "long physics-driven appendages": re.compile(r"\b(tentacles?|long tail|whip-like hair|physics[- ]driven)\b", re.I),
    "multiple weapons": re.compile(r"\b(two swords|dual wield|multiple weapons|arsenal)\b", re.I),
    "top-down designs": re.compile(r"\b(top[- ]down|bird'?s-eye)\b", re.I),
    "isometric designs": re.compile(r"\b(isometric)\b", re.I),
    "highly asymmetric multi-view requirements": re.compile(r"\b(front view|rear view|multi[- ]view|turnaround)\b", re.I),
}

PROP_FAMILIES = {
    "lantern": ["hooded lantern", "cage lantern", "rail lantern", "storm lantern"],
    "staff": ["travel staff", "crooked staff", "war staff", "runed staff"],
    "dagger": ["utility dagger", "stiletto dagger", "hooked dagger", "dirk"],
    "sword": ["arming sword", "saber", "falchion", "longknife"],
    "blade": ["arming blade", "saber", "falchion", "short blade"],
    "tool": ["field tool", "forged hammer", "hook tool", "mechanic rod"],
}

JOBS: Dict[str, Dict[str, Any]] = {}
JOB_LOCK = threading.Lock()

ProgressCallback = Callable[[int, Optional[str], Optional[str]], None]


@dataclass
class ReferenceInput:
    role: str
    local_path: Path
    weight: float


@dataclass
class ConceptRequest:
    project_id: str
    positive_prompt: str
    negative_prompt: str
    width: int
    height: int
    seed: int
    count: int
    references: List[ReferenceInput]
    mode: str
    refine_from_image: Optional[Path] = None
    refine_strength: Optional[float] = None
    variation_axes: Optional[Dict[str, Any]] = None
    output_path: Optional[Path] = None
    checkpoint_name: Optional[str] = None


@dataclass
class GeneratedConcept:
    seed: int
    image_path: Path
    backend_name: str
    backend_run_id: str
    positive_prompt: str
    negative_prompt: str
    variation_axes: Dict[str, Any]
    references_used: List[Dict[str, Any]]


class ConceptBackend(Protocol):
    def healthcheck(self) -> Dict[str, Any]:
        raise NotImplementedError

    def generate(self, request: ConceptRequest) -> List[GeneratedConcept]:
        raise NotImplementedError


@dataclass
class PartSpec:
    name: str
    size: Tuple[int, int]
    color_key: str
    pivot: Tuple[int, int]
    parent_joint: str
    draw_order: int
    kind: str
    mirror_of: Optional[str] = None


PART_LIBRARY = {
    "hair_back": PartSpec("hair_back", (54, 40), "accent", (28, 12), "head", 5, "ellipse"),
    "head": PartSpec("head", (48, 42), "skin", (24, 34), "neck", 10, "ellipse"),
    "hair_front": PartSpec("hair_front", (48, 18), "base", (24, 10), "head", 11, "fringe"),
    "torso": PartSpec("torso", (58, 68), "base", (30, 10), "torso", 20, "torso"),
    "pelvis": PartSpec("pelvis", (44, 22), "accent", (22, 8), "pelvis", 18, "pelvis"),
    "upper_arm_left": PartSpec("upper_arm_left", (18, 36), "accent", (8, 6), "shoulder_left", 14, "limb"),
    "lower_arm_left": PartSpec("lower_arm_left", (16, 34), "skin", (8, 6), "elbow_left", 15, "limb"),
    "hand_left": PartSpec("hand_left", (16, 14), "skin", (6, 4), "wrist_left", 16, "hand"),
    "upper_arm_right": PartSpec("upper_arm_right", (18, 36), "accent", (8, 6), "shoulder_right", 24, "limb"),
    "lower_arm_right": PartSpec("lower_arm_right", (16, 34), "skin", (8, 6), "elbow_right", 25, "limb"),
    "hand_right": PartSpec("hand_right", (16, 14), "skin", (6, 4), "wrist_right", 26, "hand"),
    "upper_leg_left": PartSpec("upper_leg_left", (22, 42), "base", (11, 6), "hip_left", 17, "limb"),
    "lower_leg_left": PartSpec("lower_leg_left", (20, 40), "accent", (10, 6), "knee_left", 17, "limb"),
    "foot_left": PartSpec("foot_left", (28, 14), "prop", (6, 6), "ankle_left", 17, "foot"),
    "upper_leg_right": PartSpec("upper_leg_right", (22, 42), "base", (11, 6), "hip_right", 19, "limb"),
    "lower_leg_right": PartSpec("lower_leg_right", (20, 40), "accent", (10, 6), "knee_right", 19, "limb"),
    "foot_right": PartSpec("foot_right", (28, 14), "prop", (6, 6), "ankle_right", 19, "foot"),
    "prop": PartSpec("prop", (62, 14), "prop", (10, 7), "wrist_right", 30, "prop"),
    "accessory_front": PartSpec("accessory_front", (20, 28), "accent", (10, 4), "torso", 27, "accessory"),
    "accessory_back": PartSpec("accessory_back", (24, 32), "accent", (12, 4), "torso", 6, "accessory"),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


def stable_hash(*parts: str) -> str:
    return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()


def stable_int(*parts: str, mod: int = 1_000_000) -> int:
    return int(stable_hash(*parts)[:12], 16) % mod


def parse_iso(value: Optional[str]) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def ensure_dirs(project_dir: Path) -> None:
    for rel in [
        "concepts",
        "layers",
        "rig",
        "animations/idle",
        "animations/walk",
        "exports",
        "logs",
        "references",
    ]:
        (project_dir / rel).mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def image_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize_filename(name: str, fallback: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.") or fallback
    return base


def guess_extension(name: str, mime_type: str) -> str:
    lowered = name.lower()
    if lowered.endswith(".png"):
        return ".png"
    if lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
        return ".jpg"
    if lowered.endswith(".webp"):
        return ".webp"
    if mime_type == "image/jpeg":
        return ".jpg"
    if mime_type == "image/webp":
        return ".webp"
    return ".png"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def call_progress(progress: Optional[ProgressCallback], percent: int, label: Optional[str], detail: Optional[str] = None) -> None:
    if progress is None:
        return
    progress(percent, label, detail)


def apply_project_defaults(project: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(project or {})
    normalized.setdefault("project_id", "")
    normalized.setdefault("project_name", "Untitled Project")
    normalized.setdefault("prompt_text", "")
    normalized.setdefault("created_at", now_iso())
    normalized.setdefault("updated_at", normalized["created_at"])
    normalized.setdefault("current_stage", "intake")
    normalized.setdefault("status", "ready_for_concepts")
    normalized.setdefault("layer_review_approved", False)
    normalized.setdefault("rig_review_approved", False)
    normalized.setdefault("selected_concept_id", None)
    normalized.setdefault("archived_at", None)
    normalized.setdefault("last_ui_mode", "workbench")
    normalized.setdefault("wizard_state", None)
    return normalized


def default_wizard_state() -> Dict[str, Any]:
    return {
        "current_step": "project",
        "last_completed_step": None,
        "completed_steps": [],
        "skipped_optional_steps": [],
        "last_refine_decision": None,
        "show_advanced": False,
    }


def normalize_wizard_state(payload: Any) -> Dict[str, Any]:
    state = default_wizard_state()
    if isinstance(payload, dict):
        current_step = payload.get("current_step")
        if current_step in WIZARD_STEPS:
            state["current_step"] = current_step
        last_completed = payload.get("last_completed_step")
        if last_completed in WIZARD_STEPS:
            state["last_completed_step"] = last_completed
        completed = [item for item in payload.get("completed_steps", []) if item in WIZARD_STEPS]
        skipped = [item for item in payload.get("skipped_optional_steps", []) if item in WIZARD_STEPS]
        state["completed_steps"] = list(dict.fromkeys(completed))
        state["skipped_optional_steps"] = list(dict.fromkeys(skipped))
        refine_decision = payload.get("last_refine_decision")
        if refine_decision in {"refine_again", "use_current_approved_concept", "skip"}:
            state["last_refine_decision"] = refine_decision
        state["show_advanced"] = bool(payload.get("show_advanced", False))
    return state


def set_wizard_step_complete(state: Dict[str, Any], step: str) -> Dict[str, Any]:
    wizard_state = normalize_wizard_state(state)
    if step not in wizard_state["completed_steps"]:
        wizard_state["completed_steps"].append(step)
    wizard_state["last_completed_step"] = step
    return wizard_state


def set_wizard_optional_step_skipped(state: Dict[str, Any], step: str) -> Dict[str, Any]:
    wizard_state = normalize_wizard_state(state)
    if step not in wizard_state["skipped_optional_steps"]:
        wizard_state["skipped_optional_steps"].append(step)
    return wizard_state


def animation_render_complete(project_dir: Path, animation_name: str) -> bool:
    manifest = load_json(project_dir / "animations" / animation_name / "render_manifest.json", None)
    if not isinstance(manifest, dict):
        return False
    frames = manifest.get("frames") or []
    return len(frames) == ANIMATION_SPECS[animation_name]["frame_count"]


def compute_wizard_context(project: Dict[str, Any]) -> Dict[str, Any]:
    project_dir = PROJECTS_ROOT / project["project_id"]
    wizard_state = normalize_wizard_state(project.get("wizard_state"))
    brief = project.get("brief") or {}
    completed = set(wizard_state.get("completed_steps", []))
    skipped = set(wizard_state.get("skipped_optional_steps", []))

    has_brief = "brief" in completed or bool((project.get("prompt_text") or "").strip())
    has_references = bool(brief.get("references")) or "references" in completed or "references" in skipped
    has_concepts = bool(project.get("concept_runs"))
    has_review = bool(project.get("selected_concept_id"))
    has_refine_decision = wizard_state.get("last_refine_decision") in {"use_current_approved_concept", "skip"} or "refine" in skipped
    has_build = (
        bool(project.get("layer_review_approved"))
        and bool(project.get("rig_review_approved"))
        and animation_render_complete(project_dir, "idle")
        and animation_render_complete(project_dir, "walk")
    )
    has_qa = bool(project.get("qa_report"))
    has_export = bool(project.get("last_export"))

    complete_map = {
        "project": True,
        "brief": has_brief,
        "references": has_references,
        "concepts": has_concepts,
        "review": has_review,
        "refine": has_refine_decision,
        "build": has_build,
        "qa": has_qa,
        "export": has_export,
    }

    blocking_reasons = {
        "brief": [] if complete_map["project"] else ["Create or open a project first."],
        "references": [] if complete_map["brief"] else ["Save the character description before adding or skipping references."],
        "concepts": [] if complete_map["brief"] else ["Save the character description before generating looks."],
        "review": [] if complete_map["concepts"] else ["Generate looks before choosing one."],
        "refine": [] if complete_map["review"] else ["Choose a look before adjusting it."],
        "build": [] if complete_map["review"] and complete_map["refine"] else ["Choose a look and finish the adjustment step before building."],
        "qa": [] if complete_map["build"] else ["Finish the build step before running checks."],
        "export": [] if complete_map["qa"] and project.get("qa_report", {}).get("status") == "pass" else ["Checks must pass before export."],
    }

    step_statuses: Dict[str, str] = {}
    active_step = None
    for step in WIZARD_STEPS:
        blockers = blocking_reasons.get(step, [])
        is_complete = complete_map.get(step, False)
        if step == "project":
            step_statuses[step] = "complete"
            continue
        if blockers:
            step_statuses[step] = "locked"
            continue
        if is_complete:
            step_statuses[step] = "complete"
            continue
        if active_step is None:
            step_statuses[step] = "active"
            active_step = step
        else:
            step_statuses[step] = "ready"

    if project.get("qa_report") and not complete_map["export"]:
        if project["qa_report"].get("status") != "pass":
            step_statuses["qa"] = "attention"
            active_step = "qa"
            if step_statuses.get("export") != "complete":
                step_statuses["export"] = "locked"
                blocking_reasons["export"] = ["QA must pass before export."]

    if project.get("qa_report") and project.get("current_stage", "").startswith("production_"):
        step_statuses["qa"] = "attention"
        active_step = "qa"

    recommended_next_step = active_step or "export"
    persisted_step = wizard_state.get("current_step")
    if persisted_step in WIZARD_STEPS and step_statuses.get(persisted_step) in {"active", "ready", "complete", "attention"}:
        recommended_next_step = persisted_step if step_statuses.get(persisted_step) != "locked" else recommended_next_step

    wizard_state["current_step"] = recommended_next_step
    if has_brief:
        wizard_state = set_wizard_step_complete(wizard_state, "brief")
    if has_references and "references" not in skipped:
        wizard_state = set_wizard_step_complete(wizard_state, "references")
    if has_concepts:
        wizard_state = set_wizard_step_complete(wizard_state, "concepts")
    if has_review:
        wizard_state = set_wizard_step_complete(wizard_state, "review")
    if has_refine_decision:
        wizard_state = set_wizard_step_complete(wizard_state, "refine")
    if has_build:
        wizard_state = set_wizard_step_complete(wizard_state, "build")
    if has_qa:
        wizard_state = set_wizard_step_complete(wizard_state, "qa")
    if has_export:
        wizard_state = set_wizard_step_complete(wizard_state, "export")

    can_resume_wizard = recommended_next_step != "export" or step_statuses.get("export") != "complete"
    return {
        "wizard_state": wizard_state,
        "recommended_next_step": recommended_next_step,
        "step_statuses": step_statuses,
        "blocking_reasons": blocking_reasons,
        "can_resume_wizard": can_resume_wizard,
    }


def default_stage_maturity() -> Dict[str, Any]:
    return {
        "intake": {
            "label": "Setup",
            "maturity": "experimental",
            "description": "Prompt parsing is richer than v1, but still heuristic and local-only.",
        },
        "concepts": {
            "label": "Looks",
            "maturity": "real",
            "description": "ComfyUI is the default concept backend. Debug procedural art is opt-in only.",
        },
        "refine": {
            "label": "Adjust",
            "maturity": "real",
            "description": "Refinement creates new concept images through ComfyUI and records lineage.",
        },
        "layer_review": {
            "label": "Build Layers",
            "maturity": "placeholder",
            "description": "Layers are still synthetic stand-ins, not extracted from approved concept art.",
        },
        "rig_review": {
            "label": "Set Up Motion",
            "maturity": "placeholder",
            "description": "Rigging remains procedural and only validates the placeholder downstream path.",
        },
        "production": {
            "label": "Build Animations",
            "maturity": "experimental",
            "description": "Renderer and packing are deterministic, but still fed by synthetic layer and rig assets.",
        },
        "qa": {
            "label": "Checks",
            "maturity": "experimental",
            "description": "QA only reports implemented image checks; semantic sprite correctness is not automated.",
        },
        "export": {
            "label": "Export",
            "maturity": "experimental",
            "description": "Exports are usable, but inherit the experimental upstream and placeholder downstream stages.",
        },
    }


def load_stage_maturity() -> Dict[str, Any]:
    payload = load_json(STAGE_MATURITY_PATH, None)
    if payload is None:
        return default_stage_maturity()
    return payload


def legacy_reference_entries(brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries = []
    for item in brief.get("reference_images", []) or []:
        entries.append({
            "reference_id": stable_hash("legacy-ref", str(item))[:12],
            "role": "identity",
            "weight": 1.0,
            "source_type": "legacy",
            "source_value": item,
            "local_path": None,
            "added_at": brief.get("created_at") or now_iso(),
        })
    for item in brief.get("style_references", []) or []:
        entries.append({
            "reference_id": stable_hash("legacy-style", str(item))[:12],
            "role": "style",
            "weight": 1.0,
            "source_type": "legacy",
            "source_value": item,
            "local_path": None,
            "added_at": brief.get("created_at") or now_iso(),
        })
    return entries


def normalize_prompt_text(prompt_text: str) -> str:
    return " ".join((prompt_text or "").strip().split())


def validate_prompt_constraints(prompt_text: str) -> None:
    lowered = (prompt_text or "").lower()
    for reason, pattern in REJECT_PATTERNS.items():
        if pattern.search(lowered):
            raise ValueError("Unsupported input: %s." % reason)


def infer_prop(prompt_text: str) -> str:
    lowered = prompt_text.lower()
    if any(word in lowered for word in ["lantern", "lamp"]):
        return "lantern"
    if "staff" in lowered:
        return "staff"
    if any(word in lowered for word in ["dagger", "knife", "dirk"]):
        return "dagger"
    if any(word in lowered for word in ["sword", "blade", "saber", "falchion"]):
        return "sword"
    return "tool"


def infer_brief_defaults(prompt_text: str) -> Dict[str, str]:
    prompt = normalize_prompt_text(prompt_text)
    validate_prompt_constraints(prompt)
    lowered = prompt.lower()
    if not prompt:
        return {
            "role_archetype": "ashen hollow adventurer",
            "silhouette_intent": "clear side-view traveler silhouette with one dominant read",
            "outfit_materials": "layered dark-fantasy travel gear with practical medieval materials",
            "prop": "tool",
            "palette_mood": "storm steel",
            "shape_language": "balanced angular to rounded masses",
            "mood_tone": "watchful, haunted, and grounded",
            "side_view_constraints": "strict side view, one humanoid character, clean background, held item clearly separated from torso, strong low-resolution readability for a 2d metroidvania sprite pipeline",
        }

    if any(word in lowered for word in ["knight", "armored", "guardian", "sentinel", "warden"]):
        role = "ashen hollow sentinel"
        silhouette = "broad guarded profile"
        outfit = "weathered plate fragments over travel layers with matte metal surfaces"
        tone = "stoic, vigilant, and battle-worn"
    elif any(word in lowered for word in ["rogue", "thief", "scout", "nimble", "hunter", "ranger"]):
        role = "ashen hollow scout"
        silhouette = "compact and forward-leaning profile"
        outfit = "light leathers, wraps, utility straps, and worn medieval layers"
        tone = "cautious, severe, and alert"
    elif any(word in lowered for word in ["mage", "witch", "scholar", "mystic", "seer", "pilgrim"]):
        role = "ashen hollow pilgrim"
        silhouette = "tall readable profile with clear head-to-prop separation"
        outfit = "layered cloth, trim armor accents, and weathered ritual fabric"
        tone = "mysterious, austere, and self-possessed"
    else:
        role = "ashen hollow adventurer"
        silhouette = "balanced readable profile with one dominant read"
        outfit = "field-ready medieval layers with one dominant material family"
        tone = "grounded, capable, and somber"

    if any(word in lowered for word in ["green", "jade", "verdant", "moss"]):
        palette = "verdigris slate"
    elif any(word in lowered for word in ["ember", "red", "crimson", "rust"]):
        palette = "ember dusk"
    elif any(word in lowered for word in ["ivory", "bone", "ashen", "pale"]):
        palette = "bone ash"
    else:
        palette = "storm steel"

    if any(word in lowered for word in ["round", "soft", "gentle"]):
        shape = "rounded readable masses"
    elif any(word in lowered for word in ["spike", "sharp", "angular", "blade"]):
        shape = "angular disciplined silhouettes"
    else:
        shape = "balanced angular to rounded mix"

    prop = infer_prop(prompt)
    return {
        "role_archetype": role,
        "silhouette_intent": silhouette,
        "outfit_materials": outfit,
        "prop": prop,
        "palette_mood": palette,
        "shape_language": shape,
        "mood_tone": tone,
        "side_view_constraints": "strict side view, one humanoid character, clean background, held item clearly separated from torso, strong low-resolution readability for a 2d metroidvania sprite pipeline",
    }


def hydrate_brief(brief: Optional[Dict[str, Any]], prompt_text: str) -> Dict[str, Any]:
    source = dict(brief or {})
    prompt = normalize_prompt_text(source.get("raw_prompt") or source.get("normalized_prompt") or prompt_text or "")
    defaults = infer_brief_defaults(prompt)
    hydrated = {
        "raw_prompt": prompt,
        "role_archetype": source.get("role_archetype") or source.get("subject") or defaults["role_archetype"],
        "silhouette_intent": source.get("silhouette_intent") or source.get("silhouette") or defaults["silhouette_intent"],
        "outfit_materials": source.get("outfit_materials") or source.get("outfit") or defaults["outfit_materials"],
        "prop": source.get("prop") or defaults["prop"],
        "palette_mood": source.get("palette_mood") or source.get("palette_direction") or defaults["palette_mood"],
        "shape_language": source.get("shape_language") or defaults["shape_language"],
        "mood_tone": source.get("mood_tone") or defaults["mood_tone"],
        "side_view_constraints": source.get("side_view_constraints") or source.get("side_view_readability_notes") or defaults["side_view_constraints"],
        "negative_prompt": source.get("negative_prompt") or DEFAULT_NEGATIVE_PROMPT,
        "backend_mode": source.get("backend_mode") if source.get("backend_mode") in BACKEND_MODES else "comfyui",
        "comfyui_checkpoint": source.get("comfyui_checkpoint") or DEFAULT_COMFYUI_CHECKPOINT,
    }
    references = source.get("references")
    if not isinstance(references, list):
        references = legacy_reference_entries(source)
    normalized_refs = []
    for item in references:
        if not isinstance(item, dict):
            continue
        role = item.get("role") if item.get("role") in REFERENCE_ROLES else "identity"
        normalized_refs.append({
            "reference_id": item.get("reference_id") or stable_hash(role, str(item.get("local_path") or item.get("source_value") or ""))[:12],
            "role": role,
            "weight": float(item.get("weight", 1.0)),
            "source_type": item.get("source_type") or ("local" if item.get("local_path") else "legacy"),
            "source_value": item.get("source_value"),
            "local_path": item.get("local_path"),
            "added_at": item.get("added_at") or now_iso(),
        })
    hydrated["references"] = normalized_refs
    hydrated["positive_prompt_base"] = build_positive_prompt_base(hydrated)
    return hydrated


def build_positive_prompt_base(brief: Dict[str, Any]) -> str:
    return (
        "single humanoid side-view character concept art, full body, plain light background, "
        "clean silhouette, readable negative space, %s, %s, "
        "character role: %s, silhouette intent: %s, outfit and materials: %s, "
        "primary handheld prop: %s, palette mood: %s, shape language: %s, mood: %s, "
        "readability constraints: %s"
        % (
            METROIDVANIA_PROMPT_CONTEXT,
            HOUSE_STYLE_PROMPT_RULES,
            brief["role_archetype"],
            brief["silhouette_intent"],
            brief["outfit_materials"],
            brief["prop"],
            brief["palette_mood"],
            brief["shape_language"],
            brief["mood_tone"],
            brief["side_view_constraints"],
        )
    )


def build_brief_from_payload(payload: Dict[str, Any], existing_brief: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    prompt_text = normalize_prompt_text(payload.get("prompt_text") or (existing_brief or {}).get("raw_prompt") or "")
    validate_prompt_constraints(prompt_text)
    defaults = infer_brief_defaults(prompt_text)
    source = existing_brief or {}
    raw = {
        "raw_prompt": prompt_text,
        "role_archetype": payload.get("role_archetype") or source.get("role_archetype") or defaults["role_archetype"],
        "silhouette_intent": payload.get("silhouette_intent") or source.get("silhouette_intent") or defaults["silhouette_intent"],
        "outfit_materials": payload.get("outfit_materials") or source.get("outfit_materials") or defaults["outfit_materials"],
        "prop": payload.get("prop") or source.get("prop") or defaults["prop"],
        "palette_mood": payload.get("palette_mood") or source.get("palette_mood") or defaults["palette_mood"],
        "shape_language": payload.get("shape_language") or source.get("shape_language") or defaults["shape_language"],
        "mood_tone": payload.get("mood_tone") or source.get("mood_tone") or defaults["mood_tone"],
        "side_view_constraints": payload.get("side_view_constraints") or source.get("side_view_constraints") or defaults["side_view_constraints"],
        "negative_prompt": payload.get("negative_prompt") or source.get("negative_prompt") or DEFAULT_NEGATIVE_PROMPT,
        "backend_mode": payload.get("backend_mode") if payload.get("backend_mode") in BACKEND_MODES else (source.get("backend_mode") or "comfyui"),
        "comfyui_checkpoint": payload.get("comfyui_checkpoint") or source.get("comfyui_checkpoint") or DEFAULT_COMFYUI_CHECKPOINT,
        "references": list(source.get("references") or []),
    }
    brief = hydrate_brief(raw, prompt_text)
    return brief


def parse_data_url(value: str) -> Tuple[str, bytes]:
    if ";base64," not in value:
        raise ValueError("Unsupported upload encoding.")
    header, encoded = value.split(";base64,", 1)
    mime_type = header.split(":", 1)[1] if ":" in header else "application/octet-stream"
    return mime_type, base64.b64decode(encoded)


def store_reference(project_dir: Path, descriptor: Dict[str, Any]) -> Dict[str, Any]:
    role = descriptor.get("role")
    if role not in REFERENCE_ROLES:
        raise ValueError("Reference role must be one of: %s." % ", ".join(REFERENCE_ROLES))
    try:
        weight = float(descriptor.get("weight", 1.0))
    except (TypeError, ValueError):
        raise ValueError("Reference weight must be numeric.")
    weight = clamp(weight, 0.1, 2.0)

    reference_id = uuid.uuid4().hex[:10]
    references_dir = project_dir / "references"
    references_dir.mkdir(parents=True, exist_ok=True)

    data_url = descriptor.get("data_url")
    local_path = descriptor.get("path")
    original_name = descriptor.get("name") or descriptor.get("filename") or "reference"
    source_type = "upload" if data_url else "local"

    if data_url:
        mime_type, payload = parse_data_url(data_url)
        extension = guess_extension(original_name, mime_type)
        filename = "%s_%s%s" % (role, sanitize_filename(Path(original_name).stem, "reference"), extension)
        output_path = references_dir / filename
        output_path.write_bytes(payload)
        source_value = original_name
    elif local_path:
        source = Path(local_path).expanduser()
        if not source.exists() or not source.is_file():
            raise ValueError("Reference path does not exist: %s" % local_path)
        extension = source.suffix or ".png"
        filename = "%s_%s%s" % (role, sanitize_filename(source.stem, "reference"), extension)
        output_path = references_dir / filename
        shutil.copy2(source, output_path)
        source_value = str(source)
    else:
        raise ValueError("Reference entry must include either a file upload or a local path.")

    return {
        "reference_id": reference_id,
        "role": role,
        "weight": weight,
        "source_type": source_type,
        "source_value": source_value,
        "local_path": str(output_path.relative_to(project_dir)),
        "added_at": now_iso(),
    }


def merge_new_references(project_dir: Path, brief: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    references = list(brief.get("references") or [])
    new_refs = payload.get("references") or payload.get("new_references") or []
    if not isinstance(new_refs, list):
        raise ValueError("references must be an array.")

    legacy_ref_images = payload.get("reference_images") or []
    legacy_style_refs = payload.get("style_references") or []
    for item in legacy_ref_images:
        new_refs.append({"role": "identity", "weight": 1.0, "path": item} if isinstance(item, str) else item)
    for item in legacy_style_refs:
        new_refs.append({"role": "style", "weight": 1.0, "path": item} if isinstance(item, str) else item)

    for descriptor in new_refs:
        if not isinstance(descriptor, dict):
            raise ValueError("Reference entries must be objects.")
        references.append(store_reference(project_dir, descriptor))

    brief["references"] = references
    return brief


def history_path(project_id: str) -> Path:
    return PROJECTS_ROOT / project_id / "history.json"


def load_history(project_id: str) -> Dict[str, Any]:
    payload = load_json(history_path(project_id), None)
    if not isinstance(payload, dict):
        payload = {"project_id": project_id, "events": []}
    payload.setdefault("project_id", project_id)
    payload.setdefault("events", [])
    if not isinstance(payload["events"], list):
        payload["events"] = []
    return payload


def trim_history_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    job_events = [item for item in events if item.get("type") == "job_summary"]
    keep_jobs = set(item["event_id"] for item in job_events[-JOB_HISTORY_LIMIT:] if item.get("event_id"))
    trimmed = []
    for item in events:
        if item.get("type") != "job_summary" or item.get("event_id") in keep_jobs:
            trimmed.append(item)
    return trimmed


def append_history_event(project_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    history = load_history(project_id)
    normalized = dict(event)
    normalized.setdefault("event_id", uuid.uuid4().hex[:12])
    normalized.setdefault("created_at", now_iso())
    history["events"].append(normalized)
    history["events"] = trim_history_events(history["events"])
    write_json(history_path(project_id), history)
    return history


def load_concepts(project_dir: Path) -> List[Dict[str, Any]]:
    concepts = []
    concepts_dir = project_dir / "concepts"
    if not concepts_dir.exists():
        return concepts
    for path in concepts_dir.glob("*.json"):
        payload = load_json(path, None)
        if isinstance(payload, dict):
            concepts.append(payload)
    concepts.sort(key=lambda item: (parse_iso(item.get("created_at")), item.get("concept_id", "")))
    return concepts


def hydrate_concept(concept: Dict[str, Any], fallback_created_at: Optional[str] = None) -> Dict[str, Any]:
    record = dict(concept or {})
    record.setdefault("concept_id", "")
    record.setdefault("run_id", record.get("lineage", {}).get("run_id") if isinstance(record.get("lineage"), dict) else "legacy")
    record.setdefault("run_kind", "legacy")
    record.setdefault("created_at", fallback_created_at or now_iso())
    record.setdefault("positive_prompt", record.get("prompt") or "")
    record.setdefault("negative_prompt", DEFAULT_NEGATIVE_PROMPT)
    record.setdefault("preview_image", "")
    record.setdefault("variation_axes", {})
    review_state = record.get("review_state") or {}
    record["review_state"] = {
        "approved": bool(review_state.get("approved", record.get("approved", False))),
        "favorite": bool(review_state.get("favorite", record.get("favorite", False))),
        "rejected": bool(review_state.get("rejected", record.get("rejected", False))),
    }
    record["approved"] = record["review_state"]["approved"]
    record["favorite"] = record["review_state"]["favorite"]
    record["rejected"] = record["review_state"]["rejected"]
    if "difference_summary" not in record:
        silhouette = record.get("silhouette") or record.get("variation_axes", {}).get("silhouette")
        outfit = record.get("outfit") or record.get("variation_axes", {}).get("outfit_complexity")
        record["difference_summary"] = ", ".join([item for item in [silhouette, outfit] if item]) or "legacy concept"
    record.setdefault("references_used", [])
    record.setdefault("triage", {
        "status": "not_evaluated",
        "flags": [],
        "metrics": {},
    })
    return record


def save_concept(project_dir: Path, concept: Dict[str, Any]) -> None:
    path = project_dir / "concepts" / ("%s.json" % concept["concept_id"])
    write_json(path, concept)


def next_concept_serial(concepts: List[Dict[str, Any]]) -> int:
    highest = 0
    for concept in concepts:
        match = re.search(r"(\d+)$", concept.get("concept_id", ""))
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def palette_from_seed(seed: int, variant_index: int, palette_mood: str) -> Dict[str, str]:
    mood_key = palette_mood.lower()
    bases = {
        "storm steel": [
            ("#1f2630", "#56738f", "#d8c8b0", "#7b5346", "#0f151c"),
            ("#1e252d", "#4d687d", "#d4c5ae", "#755244", "#10161d"),
        ],
        "ember dusk": [
            ("#31201d", "#91574a", "#e0beab", "#a66c3d", "#190f10"),
            ("#382421", "#8f4e57", "#dfc2ad", "#7e5b35", "#1a1110"),
        ],
        "verdigris slate": [
            ("#1f2928", "#4d8076", "#d6c7a9", "#7a6042", "#0d1616"),
            ("#24302d", "#5a8b79", "#d4c2a1", "#6c5641", "#101917"),
        ],
        "bone ash": [
            ("#242020", "#746b67", "#e2d7c4", "#8d7e67", "#111010"),
            ("#2a2321", "#7f746a", "#ded2bf", "#917760", "#141111"),
        ],
    }
    chosen_set = bases.get(mood_key, bases["storm steel"])
    chosen = chosen_set[(seed + variant_index) % len(chosen_set)]
    return {
        "base": chosen[0],
        "accent": chosen[1],
        "skin": chosen[2],
        "prop": chosen[3],
        "outline": chosen[4],
    }


def infer_prop_family(prop_name: str) -> str:
    lowered = (prop_name or "").lower()
    for family in PROP_FAMILIES:
        if family in lowered:
            return family
    return "tool"


def prop_variant_for_family(prop_name: str, variant_index: int) -> str:
    family = infer_prop_family(prop_name)
    variants = PROP_FAMILIES.get(family, PROP_FAMILIES["tool"])
    return variants[variant_index % len(variants)]


def build_initial_variation_axes(brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    prop_variants = [prop_variant_for_family(brief["prop"], index) for index in range(INITIAL_CONCEPT_COUNT)]
    return [
        {
            "silhouette": brief["silhouette_intent"],
            "outfit_complexity": brief["outfit_materials"],
            "palette_direction": brief["palette_mood"],
            "prop_variant": prop_variants[0],
            "summary": "baseline interpretation with the clearest side-view read",
        },
        {
            "silhouette": "slightly leaner version of the same core silhouette",
            "outfit_complexity": "reduced bulk and tighter panel breaks",
            "palette_direction": "%s with lower-value accents" % brief["palette_mood"],
            "prop_variant": prop_variants[1],
            "summary": "leans a little lighter and quicker without changing the identity",
        },
        {
            "silhouette": "slightly taller side-view rhythm",
            "outfit_complexity": "elongated layers and clearer vertical breaks",
            "palette_direction": "%s pushed cooler" % brief["palette_mood"],
            "prop_variant": prop_variants[2],
            "summary": "pushes height and vertical rhythm while staying readable",
        },
        {
            "silhouette": "broader guarded take on the same profile",
            "outfit_complexity": "heavier armor grouping and chunkier masses",
            "palette_direction": "%s with warm metal accents" % brief["palette_mood"],
            "prop_variant": prop_variants[3],
            "summary": "emphasizes armor weight and defensive massing",
        },
        {
            "silhouette": "slightly forward-biased action profile",
            "outfit_complexity": "trim detail concentrated near shoulders and waist",
            "palette_direction": "%s with sharper contrast splits" % brief["palette_mood"],
            "prop_variant": prop_variants[4],
            "summary": "same identity with a clearer action-ready push",
        },
        {
            "silhouette": "steady field-ready profile",
            "outfit_complexity": "functional straps, wraps, and modular panels",
            "palette_direction": "%s desaturated toward workwear values" % brief["palette_mood"],
            "prop_variant": prop_variants[5],
            "summary": "strips the design back toward a practical field version",
        },
    ]


def build_refinement_variation_axes(base_concept: Dict[str, Any], attribute_group: str, target_value: str, strength_label: str, mode: str) -> List[Dict[str, Any]]:
    parent_prop = base_concept.get("prop_variant") or base_concept.get("prop") or "tool"
    prop_family = infer_prop_family(parent_prop)
    nuances = [
        "closest hold to the parent concept",
        "clear target push while preserving parent readability",
        "more assertive change within the same identity family",
        "widest safe variation before drifting off-brief",
    ]
    results = []
    for index in range(REFINEMENT_CONCEPT_COUNT):
        axes = {
            "attribute_group": attribute_group,
            "target_value": target_value,
            "strength": strength_label,
            "preserve": {
                "silhouette": base_concept.get("silhouette"),
                "outfit": base_concept.get("outfit"),
                "palette_direction": base_concept.get("palette_direction"),
                "prop_variant": base_concept.get("prop_variant"),
            },
            "summary": "%s; %s" % (target_value, nuances[index]),
        }
        if attribute_group == "silhouette":
            axes["silhouette"] = target_value
        else:
            axes["silhouette"] = base_concept.get("silhouette")
        if attribute_group == "outfit":
            axes["outfit_complexity"] = target_value
        else:
            axes["outfit_complexity"] = base_concept.get("outfit")
        if attribute_group == "palette":
            axes["palette_direction"] = "%s, %s pass %d" % (target_value, strength_label, index + 1)
        else:
            axes["palette_direction"] = base_concept.get("palette_direction")
        if attribute_group == "prop":
            base_variant = prop_variant_for_family(target_value or prop_family, index)
            axes["prop_variant"] = base_variant
        elif mode == "similar":
            axes["prop_variant"] = prop_variant_for_family(parent_prop, index)
        else:
            axes["prop_variant"] = base_concept.get("prop_variant")
        results.append(axes)
    return results


def build_prompt_bundle(brief: Dict[str, Any], variation_axes: Dict[str, Any], source_concept: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    positive_parts = [
        brief["positive_prompt_base"],
        "gameplay role: player-facing 2d metroidvania character concept intended for side-view animation and sprite extraction",
        "readability priority: silhouette clarity first, world style second, identity consistency third",
        "variant emphasis: %s" % variation_axes.get("summary", "base brief"),
        "silhouette focus: %s" % (variation_axes.get("silhouette") or brief["silhouette_intent"]),
        "outfit focus: %s" % (variation_axes.get("outfit_complexity") or brief["outfit_materials"]),
        "palette focus: %s" % (variation_axes.get("palette_direction") or brief["palette_mood"]),
        "prop silhouette: %s" % (variation_axes.get("prop_variant") or brief["prop"]),
        "avoid cinematic pose or environment-heavy framing; keep the character readable as game art",
    ]
    if source_concept is not None:
        positive_parts.append("preserve the same character identity core as the source concept")
        preserve = variation_axes.get("preserve") or {}
        locked_bits = []
        for key in ["silhouette", "outfit", "palette_direction", "prop_variant"]:
            if preserve.get(key):
                locked_bits.append("%s=%s" % (key, preserve[key]))
        if locked_bits:
            positive_parts.append("locked attributes: %s" % ", ".join(locked_bits))
    return ", ".join(positive_parts), brief["negative_prompt"]


def make_reference_inputs(project_dir: Path, brief: Dict[str, Any]) -> List[ReferenceInput]:
    inputs = []
    for item in brief.get("references") or []:
        local_rel = item.get("local_path")
        if not local_rel:
            continue
        path = project_dir / local_rel
        if path.exists():
            inputs.append(ReferenceInput(role=item["role"], local_path=path, weight=float(item.get("weight", 1.0))))
    return inputs


def fit_image(image: Image.Image, size: Tuple[int, int], background: Tuple[int, int, int, int]) -> Image.Image:
    framed = Image.new("RGBA", size, background)
    contained = ImageOps.contain(image, size)
    x = (size[0] - contained.size[0]) // 2
    y = (size[1] - contained.size[1]) // 2
    framed.alpha_composite(contained, (x, y))
    return framed


def create_conditioning_board(
    project_dir: Path,
    references: List[ReferenceInput],
    base_image_path: Optional[Path],
    size: Tuple[int, int],
    board_name: str,
) -> Optional[Path]:
    if not references and base_image_path is None:
        return None

    board = Image.new("RGBA", size, (17, 21, 27, 255))
    draw = ImageDraw.Draw(board)
    padding = 24
    role_colors = {
        "identity": (127, 184, 214, 255),
        "costume": (217, 164, 65, 255),
        "style": (127, 214, 175, 255),
        "prop": (214, 127, 127, 255),
    }
    groups = {}
    for reference in references:
        groups.setdefault(reference.role, []).append(reference)

    if base_image_path is not None and base_image_path.exists():
        left_width = int(size[0] * 0.62)
        image = Image.open(base_image_path).convert("RGBA")
        panel = fit_image(image, (left_width - padding * 2, size[1] - padding * 2), (27, 32, 40, 255))
        board.alpha_composite(panel, (padding, padding))
        draw.rounded_rectangle((padding, padding, left_width - padding, size[1] - padding), radius=18, outline=(80, 94, 108, 255), width=4)
        draw.text((padding + 16, padding + 12), "source concept", fill=(240, 240, 240, 255))
        right_x = left_width + padding
        column_width = size[0] - right_x - padding
        role_order = [role for role in REFERENCE_ROLES if groups.get(role)]
        if not role_order:
            role_order = []
        block_height = (size[1] - padding * 2 - max(0, len(role_order) - 1) * padding) // max(1, len(role_order))
        for index, role in enumerate(role_order):
            top = padding + index * (block_height + padding)
            refs = groups[role]
            section = Image.new("RGBA", (column_width, block_height), (24, 30, 38, 255))
            inner_width = column_width - 28
            inner_height = block_height - 38
            ref_size = (inner_width, max(64, inner_height // max(1, len(refs))))
            for ref_index, reference in enumerate(refs[:3]):
                image = Image.open(reference.local_path).convert("RGBA")
                framed = fit_image(image, ref_size, (36, 43, 52, 255))
                y = 24 + ref_index * ref_size[1]
                section.alpha_composite(framed, (14, y))
            border = role_colors.get(role, (160, 160, 160, 255))
            draw_section = ImageDraw.Draw(section)
            draw_section.rounded_rectangle((0, 0, column_width - 1, block_height - 1), radius=16, outline=border, width=4)
            draw_section.text((14, 8), "%s refs" % role, fill=(240, 240, 240, 255))
            board.alpha_composite(section, (right_x, top))
    else:
        refs = references[:4]
        columns = 2
        rows = max(1, int(math.ceil(len(refs) / float(columns))))
        cell_width = (size[0] - padding * (columns + 1)) // columns
        cell_height = (size[1] - padding * (rows + 1)) // rows
        for index, reference in enumerate(refs):
            row = index // columns
            col = index % columns
            x = padding + col * (cell_width + padding)
            y = padding + row * (cell_height + padding)
            image = Image.open(reference.local_path).convert("RGBA")
            framed = fit_image(image, (cell_width, cell_height), (28, 35, 43, 255))
            board.alpha_composite(framed, (x, y))
            border = role_colors.get(reference.role, (160, 160, 160, 255))
            draw.rounded_rectangle((x, y, x + cell_width, y + cell_height), radius=18, outline=border, width=4)
            draw.text((x + 16, y + 12), "%s %.2f" % (reference.role, reference.weight), fill=(240, 240, 240, 255))

    output = project_dir / "logs" / ("%s.png" % board_name)
    output.parent.mkdir(parents=True, exist_ok=True)
    board.save(output)
    return output


def detect_mask(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getbbox() and ImageChops.invert(alpha).getbbox():
        return alpha.point(lambda value: 255 if value > 10 else 0)

    width, height = rgba.size
    pixels = rgba.load()
    corners = [
        pixels[0, 0],
        pixels[max(0, width - 1), 0],
        pixels[0, max(0, height - 1)],
        pixels[max(0, width - 1), max(0, height - 1)],
    ]
    background = tuple(int(sum(color[index] for color in corners) / 4.0) for index in range(3))
    mask = Image.new("L", rgba.size, 0)
    mask_pixels = mask.load()
    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y]
            distance = abs(pixel[0] - background[0]) + abs(pixel[1] - background[1]) + abs(pixel[2] - background[2])
            if distance > 42:
                mask_pixels[x, y] = 255
    return mask


def mask_connected_components(mask: Image.Image) -> int:
    sample = mask.resize((96, 96))
    pixels = sample.load()
    width, height = sample.size
    visited = set()
    components = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y] < 40 or (x, y) in visited:
                continue
            components += 1
            queue = [(x, y)]
            visited.add((x, y))
            while queue:
                cx, cy = queue.pop()
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx = cx + dx
                    ny = cy + dy
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if (nx, ny) in visited or pixels[nx, ny] < 40:
                        continue
                    visited.add((nx, ny))
                    queue.append((nx, ny))
    return components


def perceptual_hash(path: Path) -> int:
    image = Image.open(path).convert("L").resize((8, 8))
    values = list(image.getdata())
    average = sum(values) / float(len(values))
    bits = 0
    for index, value in enumerate(values):
        if value >= average:
            bits |= 1 << index
    return bits


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def analyze_concept_image(image_path: Path) -> Dict[str, Any]:
    image = Image.open(image_path).convert("RGBA")
    mask = detect_mask(image)
    bbox = mask.getbbox()
    occupancy = 0.0
    edge_foreground_ratio = 0.0
    if bbox is not None:
        bbox_area = float((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
        occupancy = bbox_area / float(image.size[0] * image.size[1])
        border_pixels = 0
        foreground_on_border = 0
        pixels = mask.load()
        width, height = mask.size
        for x in range(width):
            border_pixels += 2
            if pixels[x, 0] > 0:
                foreground_on_border += 1
            if pixels[x, height - 1] > 0:
                foreground_on_border += 1
        for y in range(1, height - 1):
            border_pixels += 2
            if pixels[0, y] > 0:
                foreground_on_border += 1
            if pixels[width - 1, y] > 0:
                foreground_on_border += 1
        edge_foreground_ratio = foreground_on_border / float(max(1, border_pixels))
    components = mask_connected_components(mask)
    flags = []
    status = "ok"
    if bbox is None:
        flags.append("empty_or_unreadable")
        status = "system-demoted"
    if occupancy and (occupancy < 0.12 or occupancy > 0.82):
        flags.append("bounding_box_occupancy_out_of_range")
        status = "system-demoted"
    elif occupancy and (occupancy < 0.18 or occupancy > 0.74):
        flags.append("bounding_box_occupancy_warning")
        status = "warning"
    if edge_foreground_ratio > 0.03:
        flags.append("background_not_clean")
        status = "system-demoted"
    elif edge_foreground_ratio > 0.015 and status == "ok":
        flags.append("background_edge_noise_warning")
        status = "warning"
    if components > 18:
        flags.append("component_clutter_high")
        status = "system-demoted"
    elif components > 12 and status == "ok":
        flags.append("component_clutter_warning")
        status = "warning"
    return {
        "status": status,
        "flags": flags,
        "metrics": {
            "occupancy": round(occupancy, 4),
            "edge_foreground_ratio": round(edge_foreground_ratio, 4),
            "component_count": components,
        },
    }


def annotate_run_triage(project_dir: Path, concepts: List[Dict[str, Any]]) -> None:
    hash_map = {}
    for concept in concepts:
        image_path = project_dir / concept["preview_image"]
        concept["triage"] = analyze_concept_image(image_path)
        concept["_image_sha"] = image_sha256(image_path)
        concept["_phash"] = perceptual_hash(image_path)
        hash_map.setdefault(concept["_image_sha"], []).append(concept["concept_id"])

    items = list(concepts)
    for index, concept in enumerate(items):
        if len(hash_map.get(concept["_image_sha"], [])) > 1:
            concept["triage"]["flags"].append("exact_duplicate_output")
            concept["triage"]["status"] = "system-demoted"
        for other in items[index + 1:]:
            if hamming_distance(concept["_phash"], other["_phash"]) <= 5:
                if "near_duplicate_output" not in concept["triage"]["flags"]:
                    concept["triage"]["flags"].append("near_duplicate_output")
                if "near_duplicate_output" not in other["triage"]["flags"]:
                    other["triage"]["flags"].append("near_duplicate_output")
                if concept["triage"]["status"] == "ok":
                    concept["triage"]["status"] = "warning"
                if other["triage"]["status"] == "ok":
                    other["triage"]["status"] = "warning"

    for concept in concepts:
        concept["triage"]["flags"] = sorted(set(concept["triage"]["flags"]))
        concept["triage"]["metrics"]["sha256"] = concept.pop("_image_sha")
        concept["triage"]["metrics"]["perceptual_hash"] = concept.pop("_phash")


def summarize_run_triage(concepts: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {"ok": 0, "warning": 0, "system-demoted": 0}
    for concept in concepts:
        status = concept.get("triage", {}).get("status", "ok")
        if status not in summary:
            summary[status] = 0
        summary[status] += 1
    return summary


def derive_metrics(history: Dict[str, Any]) -> Dict[str, Any]:
    concept_runs = [item for item in history.get("events", []) if item.get("type") == "concept_run"]
    review_actions = [item for item in history.get("events", []) if item.get("type") == "review_action"]
    approvals_per_run = {}
    rejects_per_run = {}
    refinements_per_concept = {}
    first_concept_time = None
    first_approval_time = None

    for run in concept_runs:
        run_id = run.get("run_id")
        if run_id and run.get("run_kind") == "initial":
            approvals_per_run.setdefault(run_id, 0)
            rejects_per_run.setdefault(run_id, 0)
        if run.get("run_kind") in ("refinement", "similar") and run.get("source_concept_id"):
            source_id = run["source_concept_id"]
            refinements_per_concept[source_id] = refinements_per_concept.get(source_id, 0) + 1
        created = parse_iso(run.get("created_at"))
        if first_concept_time is None or created < first_concept_time:
            first_concept_time = created

    latest_states = {}
    for action in review_actions:
        concept_id = action.get("concept_id")
        kind = action.get("action")
        if concept_id and kind:
            key = (action.get("run_id"), concept_id, kind)
            existing = latest_states.get(key)
            if existing is None or parse_iso(action.get("created_at")) >= parse_iso(existing.get("created_at")):
                latest_states[key] = action
        if kind == "approve" and action.get("value"):
            created = parse_iso(action.get("created_at"))
            if first_approval_time is None or created < first_approval_time:
                first_approval_time = created

    for (run_id, _, kind), action in latest_states.items():
        approvals_per_run.setdefault(run_id, 0)
        rejects_per_run.setdefault(run_id, 0)
        if kind == "approve" and action.get("value"):
            approvals_per_run[run_id] = approvals_per_run.get(run_id, 0) + 1
        if kind == "reject" and action.get("value"):
            rejects_per_run[run_id] = rejects_per_run.get(run_id, 0) + 1

    time_to_approved_seconds = None
    if first_concept_time is not None and first_approval_time is not None:
        time_to_approved_seconds = max(0, int((first_approval_time - first_concept_time).total_seconds()))

    return {
        "concept_runs_per_project": sum(1 for item in concept_runs if item.get("run_kind") == "initial"),
        "approvals_per_run": approvals_per_run,
        "rejects_per_run": rejects_per_run,
        "refinements_per_selected_concept": refinements_per_concept,
        "time_to_approved_concept_seconds": time_to_approved_seconds,
    }


def build_run_summaries(history: Dict[str, Any], concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    concepts_by_run = {}
    for concept in concepts:
        concepts_by_run.setdefault(concept.get("run_id") or "legacy", []).append(concept)

    summaries = []
    for event in history.get("events", []):
        if event.get("type") != "concept_run":
            continue
        run_concepts = concepts_by_run.get(event.get("run_id"), [])
        summary = {
            "run_id": event.get("run_id"),
            "run_kind": event.get("run_kind"),
            "created_at": event.get("created_at"),
            "completed_at": event.get("completed_at"),
            "status": event.get("status"),
            "concept_ids": event.get("concept_ids") or [item["concept_id"] for item in run_concepts],
            "concept_count": event.get("concept_count") or len(run_concepts),
            "backend_name": event.get("backend_name"),
            "source_concept_id": event.get("source_concept_id"),
            "summary": event.get("summary"),
            "attribute_group": event.get("attribute_group"),
            "target_value": event.get("target_value"),
            "refinement_strength_label": event.get("refinement_strength_label"),
            "triage": summarize_run_triage(run_concepts),
            "references_used": event.get("references_used") or [],
        }
        summaries.append(summary)

    if not summaries and concepts:
        summaries.append({
            "run_id": "legacy",
            "run_kind": "legacy",
            "created_at": concepts[0].get("created_at"),
            "completed_at": concepts[-1].get("created_at"),
            "status": "completed",
            "concept_ids": [item["concept_id"] for item in concepts],
            "concept_count": len(concepts),
            "backend_name": "legacy",
            "source_concept_id": None,
            "summary": "Legacy concept board",
            "attribute_group": None,
            "target_value": None,
            "refinement_strength_label": None,
            "triage": summarize_run_triage(concepts),
            "references_used": [],
        })
    summaries.sort(key=lambda item: parse_iso(item.get("created_at")), reverse=True)
    return summaries


def load_project(project_id: str) -> Dict[str, Any]:
    project_dir = PROJECTS_ROOT / project_id
    project_path = project_dir / "project.json"
    if not project_path.exists():
        raise FileNotFoundError(project_id)

    project = apply_project_defaults(load_json(project_path, {}))
    ensure_dirs(project_dir)
    project["brief"] = hydrate_brief(load_json(project_dir / "brief.json", {}), project.get("prompt_text", ""))
    project["character_spec"] = load_json(project_dir / "character_spec.json")
    project["layered_character"] = load_json(project_dir / "layered_character.json")
    project["rig"] = load_json(project_dir / "rig.json")
    project["animation_templates"] = load_json(project_dir / "animation_templates.json")
    project["qa_report"] = load_json(project_dir / "qa_report.json")
    project["history"] = load_history(project_id)
    project["concepts"] = [hydrate_concept(item, project["created_at"]) for item in load_concepts(project_dir)]
    if project.get("selected_concept_id") is None:
        for concept in project["concepts"]:
            if concept["review_state"]["approved"]:
                project["selected_concept_id"] = concept["concept_id"]
                break
    project["exports"] = [
        str(path.relative_to(project_dir))
        for path in sorted((project_dir / "exports").glob("*"), key=lambda item: item.name)
    ]
    project["project_dir"] = str(project_dir)
    project["stage_maturity"] = load_stage_maturity()
    project["metrics"] = derive_metrics(project["history"])
    project["concept_runs"] = build_run_summaries(project["history"], project["concepts"])
    project["latest_concept_run"] = next((item for item in project["concept_runs"] if item["run_kind"] == "initial"), None)
    project["latest_refinement_run"] = next((item for item in project["concept_runs"] if item["run_kind"] in ("refinement", "similar")), None)
    project["build_status"] = {
        "idle_render_complete": animation_render_complete(project_dir, "idle"),
        "walk_render_complete": animation_render_complete(project_dir, "walk"),
    }
    project["production_warnings"] = [
        "Layer build is still synthetic procedural output, not extracted from concept art.",
        "Rigging and animation templates remain placeholder downstream stages.",
        "QA only covers implemented image heuristics and does not judge semantic sprite correctness.",
    ]
    wizard_context = compute_wizard_context(project)
    project["wizard_state"] = wizard_context["wizard_state"]
    project["recommended_next_step"] = wizard_context["recommended_next_step"]
    project["step_statuses"] = wizard_context["step_statuses"]
    project["blocking_reasons"] = wizard_context["blocking_reasons"]
    project["can_resume_wizard"] = wizard_context["can_resume_wizard"]
    return project


def save_project(project: Dict[str, Any]) -> None:
    project_dir = PROJECTS_ROOT / project["project_id"]
    ensure_dirs(project_dir)
    core = {k: v for k, v in project.items() if k not in {
        "brief",
        "character_spec",
        "layered_character",
        "rig",
        "animation_templates",
        "qa_report",
        "history",
        "concepts",
        "exports",
        "project_dir",
        "stage_maturity",
        "metrics",
        "concept_runs",
        "latest_concept_run",
        "latest_refinement_run",
        "production_warnings",
        "build_status",
        "recommended_next_step",
        "step_statuses",
        "blocking_reasons",
        "can_resume_wizard",
    }}
    write_json(project_dir / "project.json", core)
    write_json(project_dir / "brief.json", project["brief"])
    if project.get("character_spec") is not None:
        write_json(project_dir / "character_spec.json", project["character_spec"])
    if project.get("layered_character") is not None:
        write_json(project_dir / "layered_character.json", project["layered_character"])
    if project.get("rig") is not None:
        write_json(project_dir / "rig.json", project["rig"])
    if project.get("animation_templates") is not None:
        write_json(project_dir / "animation_templates.json", project["animation_templates"])
    if project.get("qa_report") is not None:
        write_json(project_dir / "qa_report.json", project["qa_report"])
    if project.get("history") is not None:
        write_json(project_dir / "history.json", project["history"])
    for concept in project.get("concepts", []) or []:
        save_concept(project_dir, concept)


def list_projects(include_archived: bool) -> List[Dict[str, Any]]:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(PROJECTS_ROOT.iterdir()):
        if not path.is_dir():
            continue
        project = apply_project_defaults(load_json(path / "project.json", {}))
        if not project.get("project_id"):
            continue
        if project.get("archived_at") and not include_archived:
            continue
        items.append(project)
    return items


def project_summary(project: Dict[str, Any]) -> Dict[str, Any]:
    wizard_state = normalize_wizard_state(project.get("wizard_state"))
    return {
        "project_id": project["project_id"],
        "project_name": project["project_name"],
        "created_at": project["created_at"],
        "updated_at": project["updated_at"],
        "current_stage": project["current_stage"],
        "status": project["status"],
        "selected_concept_id": project.get("selected_concept_id"),
        "layer_review_approved": project.get("layer_review_approved", False),
        "rig_review_approved": project.get("rig_review_approved", False),
        "archived_at": project.get("archived_at"),
        "last_export": project.get("last_export"),
        "last_ui_mode": project.get("last_ui_mode", "workbench"),
        "wizard_state": wizard_state,
        "can_resume_wizard": wizard_state.get("current_step") not in {None, "project", "export"},
    }


def read_body(handler: "SpriteWorkbenchHandler") -> Dict[str, Any]:
    try:
        content_length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        raise ValueError("Invalid content length")
    raw = handler.rfile.read(content_length) if content_length > 0 else b"{}"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON: %s" % exc)
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object.")
    return payload


def create_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_name = (payload.get("project_name") or "").strip()
    prompt = normalize_prompt_text(payload.get("prompt_text") or "")
    if not project_name and not prompt:
        raise ValueError("Project name or prompt is required.")

    brief = build_brief_from_payload(payload)
    project_id = "%s-%s" % (
        slugify(project_name or brief["role_archetype"]),
        stable_hash(project_name, prompt, now_iso())[:8],
    )
    project_dir = PROJECTS_ROOT / project_id
    ensure_dirs(project_dir)
    brief = merge_new_references(project_dir, brief, payload)

    now = now_iso()
    initial_mode = payload.get("last_ui_mode") if payload.get("last_ui_mode") in {"wizard", "workbench"} else "workbench"
    wizard_state = normalize_wizard_state(payload.get("wizard_state"))
    wizard_state = set_wizard_step_complete(wizard_state, "project")
    if prompt or any(payload.get(key) for key in [
        "role_archetype",
        "silhouette_intent",
        "outfit_materials",
        "prop",
        "palette_mood",
        "shape_language",
        "mood_tone",
        "side_view_constraints",
        "negative_prompt",
    ]):
        wizard_state = set_wizard_step_complete(wizard_state, "brief")
        if initial_mode == "wizard":
            wizard_state["current_step"] = "references"

    project = {
        "project_id": project_id,
        "project_name": project_name or brief["role_archetype"].title(),
        "prompt_text": prompt,
        "created_at": now,
        "updated_at": now,
        "current_stage": "intake",
        "status": "ready_for_concepts",
        "layer_review_approved": False,
        "rig_review_approved": False,
        "selected_concept_id": None,
        "archived_at": None,
        "last_ui_mode": initial_mode,
        "wizard_state": wizard_state,
        "brief": brief,
        "character_spec": None,
        "layered_character": None,
        "rig": None,
        "animation_templates": None,
        "qa_report": None,
        "history": {"project_id": project_id, "events": []},
        "concepts": [],
    }
    save_project(project)
    return load_project(project_id)


def update_project_brief(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    brief = build_brief_from_payload(payload, project["brief"])
    project_dir = PROJECTS_ROOT / project_id
    brief = merge_new_references(project_dir, brief, payload)
    project["brief"] = brief
    project["prompt_text"] = brief["raw_prompt"]
    project["updated_at"] = now_iso()
    project["status"] = "ready_for_concepts"
    project["wizard_state"] = set_wizard_step_complete(project.get("wizard_state"), "brief")
    if project["last_ui_mode"] == "wizard" and project["wizard_state"]["current_step"] in {"project", "brief"}:
        project["wizard_state"]["current_step"] = "references"
    save_project(project)
    return load_project(project_id)


def duplicate_project(project_id: str) -> Dict[str, Any]:
    source = load_project(project_id)
    new_id = "%s-%s" % (
        slugify("%s copy" % source["project_name"]),
        stable_hash(source["project_id"], now_iso())[:8],
    )
    new_dir = PROJECTS_ROOT / new_id
    ensure_dirs(new_dir)

    for filename in ["brief.json", "character_spec.json", "history.json"]:
        src = PROJECTS_ROOT / project_id / filename
        if src.exists():
            shutil.copy2(src, new_dir / filename)

    for folder in ["concepts", "references"]:
        src_folder = PROJECTS_ROOT / project_id / folder
        dst_folder = new_dir / folder
        dst_folder.mkdir(parents=True, exist_ok=True)
        if src_folder.exists():
            for path in src_folder.iterdir():
                if path.is_file():
                    shutil.copy2(path, dst_folder / path.name)

    project_core = {
        "project_id": new_id,
        "project_name": "%s Copy" % source["project_name"],
        "prompt_text": source["prompt_text"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "current_stage": "concept_lock" if source.get("character_spec") else "concepts",
        "status": "branched_from_%s" % source["project_id"],
        "layer_review_approved": False,
        "rig_review_approved": False,
        "selected_concept_id": source.get("selected_concept_id"),
        "archived_at": None,
        "last_export": None,
        "last_ui_mode": "workbench",
        "wizard_state": normalize_wizard_state(source.get("wizard_state")),
    }
    write_json(new_dir / "project.json", project_core)

    for path in (new_dir / "concepts").glob("*.json"):
        payload = load_json(path, {})
        payload["project_id"] = new_id
        write_json(path, payload)

    history = load_json(new_dir / "history.json", {"project_id": new_id, "events": []})
    history["project_id"] = new_id
    write_json(new_dir / "history.json", history)

    return load_project(new_id)


def archive_project(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    project["archived_at"] = now_iso()
    project["updated_at"] = now_iso()
    project["status"] = "archived"
    save_project(project)
    return load_project(project_id)


def update_wizard_state(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    wizard_state = normalize_wizard_state(project.get("wizard_state"))

    requested_step = payload.get("current_step")
    if requested_step in WIZARD_STEPS:
        wizard_state["current_step"] = requested_step

    if isinstance(payload.get("show_advanced"), bool):
        wizard_state["show_advanced"] = payload["show_advanced"]

    if payload.get("last_refine_decision") in {"refine_again", "use_current_approved_concept", "skip"}:
        wizard_state["last_refine_decision"] = payload["last_refine_decision"]
        if payload["last_refine_decision"] in {"use_current_approved_concept", "skip"}:
            wizard_state = set_wizard_step_complete(wizard_state, "refine")

    for step in payload.get("completed_steps", []) or []:
        if step in WIZARD_STEPS:
            wizard_state = set_wizard_step_complete(wizard_state, step)

    for step in payload.get("skipped_optional_steps", []) or []:
        if step in {"references", "refine"}:
            wizard_state = set_wizard_optional_step_skipped(wizard_state, step)

    requested_mode = payload.get("last_ui_mode")
    if requested_mode in {"wizard", "workbench"}:
        project["last_ui_mode"] = requested_mode

    project["wizard_state"] = wizard_state
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)


def make_character_spec(project: Dict[str, Any], concept: Dict[str, Any]) -> Dict[str, Any]:
    seed_history = [item["seed"] for item in project["concepts"] if item.get("seed") is not None]
    return {
        "approved_concept_id": concept["concept_id"],
        "canonical_prompt": concept["positive_prompt"],
        "negative_prompt": concept["negative_prompt"],
        "locked_attributes": {
            "silhouette": concept.get("silhouette"),
            "face_head_shape": concept.get("face_head_shape") or project["brief"]["shape_language"],
            "outfit": concept.get("outfit"),
            "palette": concept.get("palette_direction"),
            "prop": concept.get("prop_variant") or project["brief"]["prop"],
        },
        "seed_history": seed_history,
        "palette_definition": concept["palette"],
        "prop_definition": {"type": concept.get("prop_variant") or project["brief"]["prop"], "attachment_joint": "wrist_right"},
        "side_view_rules": project["brief"]["side_view_constraints"],
        "production_target": {
            "frame_size": [256, 256],
            "idle": ANIMATION_SPECS["idle"],
            "walk": ANIMATION_SPECS["walk"],
        },
        "model_identifiers_used_during_concept_generation": {
            "mode": concept.get("backend_name"),
            "backend_run_id": concept.get("backend_run_id"),
            "version": TOOL_VERSION,
            "run_id": concept.get("run_id"),
        },
    }


def update_concept_review_state(project_id: str, concept_id: str, action: str, value: Optional[bool]) -> Dict[str, Any]:
    if action not in {"approve", "favorite", "reject"}:
        raise ValueError("Unsupported review action.")

    project = load_project(project_id)
    concept = next((item for item in project["concepts"] if item["concept_id"] == concept_id), None)
    if concept is None:
        raise ValueError("Concept not found.")

    event_value = True if value is None else bool(value)

    if action == "approve":
        event_value = True
        for item in project["concepts"]:
            item["review_state"]["approved"] = item["concept_id"] == concept_id
            item["approved"] = item["review_state"]["approved"]
            save_concept(PROJECTS_ROOT / project_id, item)
        project["selected_concept_id"] = concept_id
        project["character_spec"] = make_character_spec(project, concept)
        project["current_stage"] = "concept_lock"
        project["status"] = "concept_approved"
    else:
        concept["review_state"]["favorite"] = event_value if action == "favorite" else concept["review_state"]["favorite"]
        concept["review_state"]["rejected"] = event_value if action == "reject" else concept["review_state"]["rejected"]
        concept["favorite"] = concept["review_state"]["favorite"]
        concept["rejected"] = concept["review_state"]["rejected"]
        if action == "reject" and project.get("selected_concept_id") == concept_id and event_value:
            concept["review_state"]["approved"] = False
            concept["approved"] = False
            project["selected_concept_id"] = None
            project["character_spec"] = None
        save_concept(PROJECTS_ROOT / project_id, concept)

    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "review_action",
        "run_id": concept.get("run_id"),
        "concept_id": concept_id,
        "action": action,
        "value": event_value,
    })
    return load_project(project_id)


def hex_to_rgba(value: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4)) + (alpha,)


def make_part_image(part: PartSpec, palette: Dict[str, str]) -> Image.Image:
    img = Image.new("RGBA", part.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fill = hex_to_rgba(palette[part.color_key])
    outline = hex_to_rgba(palette["outline"])
    width, height = part.size
    if part.kind == "ellipse":
        draw.ellipse((2, 2, width - 3, height - 3), fill=fill, outline=outline, width=2)
    elif part.kind == "fringe":
        draw.polygon([(2, 6), (width - 4, 2), (width - 6, height - 2), (8, height - 4)], fill=fill, outline=outline)
    elif part.kind == "torso":
        draw.rounded_rectangle((3, 2, width - 3, height - 2), radius=10, fill=fill, outline=outline, width=2)
        draw.rectangle((10, height - 18, width - 10, height - 6), fill=hex_to_rgba(palette["accent"]), outline=outline, width=2)
    elif part.kind == "pelvis":
        draw.rounded_rectangle((2, 3, width - 2, height - 2), radius=6, fill=fill, outline=outline, width=2)
    elif part.kind == "limb":
        draw.rounded_rectangle((3, 2, width - 3, height - 2), radius=7, fill=fill, outline=outline, width=2)
    elif part.kind == "hand":
        draw.ellipse((1, 2, width - 2, height - 2), fill=fill, outline=outline, width=2)
    elif part.kind == "foot":
        draw.rounded_rectangle((1, 4, width - 2, height - 2), radius=5, fill=fill, outline=outline, width=2)
    elif part.kind == "prop":
        draw.rounded_rectangle((1, 3, width - 3, height - 3), radius=5, fill=fill, outline=outline, width=2)
        draw.line((8, height // 2, width - 8, height // 2), fill=hex_to_rgba(palette["accent"]), width=2)
    elif part.kind == "accessory":
        draw.rounded_rectangle((2, 2, width - 2, height - 2), radius=5, fill=fill, outline=outline, width=2)
    return img


def build_layered_character(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    if not project.get("character_spec"):
        raise ValueError("Concept approval is required before layer build.")

    call_progress(progress, 8, "Preparing layers", "Building the temporary layer stack for the selected look.")
    palette = project["character_spec"]["palette_definition"]
    parts = []
    total_parts = len(REQUIRED_PARTS)
    for index, part_name in enumerate(REQUIRED_PARTS):
        call_progress(progress, 12 + int((index / max(1, total_parts)) * 74), "Building layer %d of %d" % (index + 1, total_parts), part_name)
        part = PART_LIBRARY[part_name]
        image = make_part_image(part, palette)
        output_path = project_dir / "layers" / ("%s.png" % part_name)
        image.save(output_path)
        parts.append({
            "part_name": part_name,
            "source_image_path": str(output_path.relative_to(project_dir)),
            "local_bounding_box": [0, 0, image.size[0], image.size[1]],
            "pivot_point": list(part.pivot),
            "draw_order": part.draw_order,
            "parent_joint": part.parent_joint,
            "mask_integrity_status": "pass",
        })

    layered = {
        "project_id": project_id,
        "source_mode": "synthetic_procedural",
        "source_summary": "Synthetic placeholder layers generated from a fixed part library.",
        "parts": parts,
        "qa": {
            "missing_required_part": False,
            "visible_background_contamination": False,
            "broken_mask_edges": False,
            "prop_not_separable_from_hand": False,
            "source_is_extracted_from_concept": "not_implemented",
        },
        "status": "pass",
        "approved_for_rigging": False,
        "created_at": now_iso(),
    }
    project["layered_character"] = layered
    project["current_stage"] = "layer_review"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Layers ready", "Review the temporary layer stack before continuing.")
    return layered


def base_joint_positions() -> Dict[str, Tuple[float, float]]:
    return {
        "root": (210, 258),
        "pelvis": (210, 228),
        "torso": (210, 194),
        "neck": (210, 152),
        "head": (210, 132),
        "shoulder_left": (196, 170),
        "elbow_left": (184, 194),
        "wrist_left": (176, 220),
        "shoulder_right": (224, 170),
        "elbow_right": (238, 194),
        "wrist_right": (246, 220),
        "hip_left": (200, 234),
        "knee_left": (196, 266),
        "ankle_left": (194, 298),
        "hip_right": (220, 234),
        "knee_right": (224, 266),
        "ankle_right": (226, 298),
    }


def build_animation_templates() -> Dict[str, Any]:
    idle_frames = []
    for index in range(ANIMATION_SPECS["idle"]["frame_count"]):
        phase = index / float(ANIMATION_SPECS["idle"]["frame_count"] - 1)
        idle_frames.append({
            "root_offset": [0, round(math.sin(phase * math.tau) * 3, 2)],
            "torso_rotation": round(math.sin(phase * math.tau) * 3, 2),
            "head_rotation": round(math.sin(phase * math.tau + 0.6) * 2, 2),
            "arm_swing": round(math.sin(phase * math.tau) * 6, 2),
            "leg_swing": round(math.sin(phase * math.tau) * 4, 2),
        })

    walk_frames = []
    for index in range(ANIMATION_SPECS["walk"]["frame_count"]):
        phase = index / float(ANIMATION_SPECS["walk"]["frame_count"] - 1)
        walk_frames.append({
            "root_offset": [round(math.sin(phase * math.tau) * 4, 2), round(abs(math.sin(phase * math.tau)) * -6, 2)],
            "torso_rotation": round(math.sin(phase * math.tau) * 5, 2),
            "head_rotation": round(math.sin(phase * math.tau + 0.4) * 3, 2),
            "arm_swing": round(math.sin(phase * math.tau) * 20, 2),
            "leg_swing": round(math.sin(phase * math.tau) * 24, 2),
        })

    return {
        "idle": {
            **ANIMATION_SPECS["idle"],
            "root_motion_policy": "locked",
            "loop_frame_continuity": True,
            "joint_transforms_per_frame": idle_frames,
        },
        "walk": {
            **ANIMATION_SPECS["walk"],
            "root_motion_policy": "in_place",
            "loop_frame_continuity": True,
            "joint_transforms_per_frame": walk_frames,
        },
    }


def composite_part(
    canvas: Image.Image,
    part_image: Image.Image,
    pivot_world: Tuple[float, float],
    pivot_local: Tuple[int, int],
    rotation_deg: float,
) -> None:
    rotated = part_image.rotate(rotation_deg, resample=Image.Resampling.BICUBIC, center=pivot_local, expand=True)
    bbox = rotated.getbbox()
    if bbox is None:
        return
    offset_x = pivot_world[0] - pivot_local[0]
    offset_y = pivot_world[1] - pivot_local[1]
    canvas.alpha_composite(rotated, (int(round(offset_x)), int(round(offset_y))))


def scale_point(point: Tuple[float, float]) -> Tuple[float, float]:
    return (
        RENDER_CENTER[0] + ((point[0] - RENDER_CENTER[0]) * RENDER_SCALE),
        RENDER_CENTER[1] + ((point[1] - RENDER_CENTER[1]) * RENDER_SCALE),
    )


def render_pose(project: Dict[str, Any], transforms: Dict[str, Any], save_path: Optional[Path] = None) -> Tuple[Image.Image, Dict[str, Any]]:
    project_dir = PROJECTS_ROOT / project["project_id"]
    parts_meta = {part["part_name"]: part for part in project["layered_character"]["parts"]}
    part_images = {}
    scaled_pivots = {}
    for name, meta in parts_meta.items():
        image = Image.open(project_dir / meta["source_image_path"]).convert("RGBA")
        scaled_size = (
            max(1, int(round(image.size[0] * RENDER_SCALE))),
            max(1, int(round(image.size[1] * RENDER_SCALE))),
        )
        scaled_image = image.resize(scaled_size, resample=Image.Resampling.BICUBIC)
        part_images[name] = scaled_image
        scaled_pivots[name] = (
            max(0, int(round(meta["pivot_point"][0] * RENDER_SCALE))),
            max(0, int(round(meta["pivot_point"][1] * RENDER_SCALE))),
        )

    base = base_joint_positions()
    root_dx, root_dy = transforms.get("root_offset", [0, 0])
    for key, value in list(base.items()):
        base[key] = scale_point((value[0] + root_dx, value[1] + root_dy))

    canvas = Image.new("RGBA", WORKING_CANVAS, (0, 0, 0, 0))
    render_log = []
    draw_sequence = []

    def add(name: str, joint_key: str, rotation: float = 0.0, extra: Tuple[float, float] = (0, 0)) -> None:
        meta = parts_meta[name]
        world = (base[joint_key][0] + extra[0], base[joint_key][1] + extra[1])
        composite_part(canvas, part_images[name], world, scaled_pivots[name], rotation)
        draw_sequence.append((meta["draw_order"], name))
        render_log.append({
            "part": name,
            "joint": joint_key,
            "rotation": rotation,
            "pivot_world": [round(world[0], 2), round(world[1], 2)],
        })

    arm_swing = float(transforms.get("arm_swing", 0))
    leg_swing = float(transforms.get("leg_swing", 0))
    torso_rotation = float(transforms.get("torso_rotation", 0))
    head_rotation = float(transforms.get("head_rotation", 0))

    add("hair_back", "head", head_rotation * 0.4, (-26, -28))
    add("accessory_back", "torso", torso_rotation * 0.3, (-18, 14))
    add("upper_leg_left", "hip_left", leg_swing * 0.8)
    add("lower_leg_left", "knee_left", leg_swing * 0.55, (-2, 24))
    add("foot_left", "ankle_left", 0.0, (-6, 32))
    add("pelvis", "pelvis", 0.0, (-22, -4))
    add("torso", "torso", torso_rotation, (-28, -10))
    add("upper_arm_left", "shoulder_left", arm_swing * 0.7, (-8, 0))
    add("lower_arm_left", "elbow_left", arm_swing * 0.45, (-8, 10))
    add("hand_left", "wrist_left", 0.0, (-6, 18))
    add("head", "head", head_rotation, (-24, -34))
    add("hair_front", "head", head_rotation * 0.6, (-24, -28))
    add("upper_leg_right", "hip_right", -leg_swing * 0.8)
    add("lower_leg_right", "knee_right", -leg_swing * 0.55, (-2, 24))
    add("foot_right", "ankle_right", 0.0, (-6, 32))
    add("upper_arm_right", "shoulder_right", -arm_swing * 0.7, (-6, 0))
    add("lower_arm_right", "elbow_right", -arm_swing * 0.45, (-6, 10))
    add("hand_right", "wrist_right", 0.0, (-4, 18))
    add("prop", "wrist_right", -arm_swing * 0.4, (0, 10))
    add("accessory_front", "torso", torso_rotation * 0.2, (12, 14))

    if save_path is not None:
        canvas.save(save_path)
    draw_sequence.sort()
    return canvas, {
        "render_log": render_log,
        "draw_sequence": [name for _, name in draw_sequence],
        "foot_anchor": {
            "left": [base["ankle_left"][0] - 6, base["ankle_left"][1] + 32],
            "right": [base["ankle_right"][0] - 6, base["ankle_right"][1] + 32],
        },
    }


def cleanup_frame(image: Image.Image) -> Tuple[Image.Image, Dict[str, Any]]:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("Rendered frame is empty.")
    cropped = image.crop(bbox)
    padded = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
    target_x = FRAME_PIVOT[0] - cropped.size[0] // 2
    target_y = FRAME_PIVOT[1] - cropped.size[1]
    padded.alpha_composite(cropped, (target_x, target_y))
    return padded, {
        "crop_box": list(bbox),
        "output_box": [target_x, target_y, target_x + cropped.size[0], target_y + cropped.size[1]],
        "pivot": list(FRAME_PIVOT),
    }


def border_has_alpha(image: Image.Image) -> bool:
    width, height = image.size
    alpha = image.getchannel("A")
    pixels = alpha.load()
    for x in range(width):
        if pixels[x, 0] > 0 or pixels[x, height - 1] > 0:
            return True
    for y in range(height):
        if pixels[0, y] > 0 or pixels[width - 1, y] > 0:
            return True
    return False


def build_rig(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("layered_character"):
        raise ValueError("Layer review required before rig build.")

    call_progress(progress, 10, "Preparing motion setup", "Loading the temporary layer stack.")
    project_dir = PROJECTS_ROOT / project_id
    templates = build_animation_templates()
    call_progress(progress, 45, "Rendering neutral pose", "Capturing a reference pose for the motion setup.")
    _, neutral_meta = render_pose(project, templates["idle"]["joint_transforms_per_frame"][0], project_dir / "rig" / "neutral_pose.png")
    joint_map = {joint: list(coords) for joint, coords in base_joint_positions().items()}
    rig = {
        "source_mode": "synthetic_procedural",
        "source_summary": "Rig is built for synthetic placeholder layers only.",
        "joints": RIG_JOINTS,
        "default_neutral_pose": joint_map,
        "per_joint_rotation_limits": {
            joint: {"min": -35, "max": 35}
            for joint in RIG_JOINTS
            if joint not in {"root", "pelvis", "torso"}
        },
        "draw_order_rules_for_overlap": neutral_meta["draw_sequence"],
        "foot_anchor_reference": {
            "pivot": list(FRAME_PIVOT),
            "left_ankle": joint_map["ankle_left"],
            "right_ankle": joint_map["ankle_right"],
        },
        "prop_attachment_joint": "wrist_right",
        "rig_joint_map": joint_map,
        "pivot_map": {part["part_name"]: part["pivot_point"] for part in project["layered_character"]["parts"]},
        "occlusion_order_map": neutral_meta["draw_sequence"],
        "neutral_pose_render": "rig/neutral_pose.png",
        "approved_for_production": False,
        "created_at": now_iso(),
    }
    write_json(project_dir / "rig" / "joint_map.json", joint_map)
    write_json(project_dir / "rig" / "pivot_map.json", rig["pivot_map"])
    write_json(project_dir / "rig" / "occlusion_order_map.json", rig["occlusion_order_map"])
    project["rig"] = rig
    project["animation_templates"] = templates
    project["current_stage"] = "rig_review"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Motion setup ready", "Review the temporary motion setup before building animations.")
    return rig


def render_animation(project_id: str, animation_name: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("rig") or not project["rig"].get("approved_for_production"):
        raise ValueError("Rig review approval is required before production.")
    templates = project["animation_templates"][animation_name]
    project_dir = PROJECTS_ROOT / project_id
    output_dir = project_dir / "animations" / animation_name
    manifests = []
    frame_total = len(templates["joint_transforms_per_frame"])
    for frame_index, transforms in enumerate(templates["joint_transforms_per_frame"]):
        call_progress(
            progress,
            10 + int((frame_index / max(1, frame_total)) * 82),
            "Building %s frame %d of %d" % (animation_name, frame_index + 1, frame_total),
            "Rendering and cleaning the frame.",
        )
        raw, render_meta = render_pose(project, transforms)
        final_frame, cleanup = cleanup_frame(raw)
        frame_name = "%s_%02d.png" % (animation_name, frame_index)
        final_path = output_dir / frame_name
        final_frame.save(final_path)
        manifests.append({
            "frame_name": frame_name,
            "path": str(final_path.relative_to(project_dir)),
            "cleanup": cleanup,
            "render_meta": render_meta,
        })
    write_json(output_dir / "render_manifest.json", {"animation": animation_name, "frames": manifests})
    project["current_stage"] = "production_%s" % animation_name
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "%s animation ready" % animation_name.title(), "Frames saved for review.")
    return {"animation": animation_name, "frames": manifests, "fps": templates["fps"], "frame_count": templates["frame_count"]}


def check_state(status: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if status not in {"pass", "fail", "not_implemented"}:
        raise ValueError("Invalid check state.")
    return {"status": status, "details": details or {}}


def aggregate_check_state(states: List[str]) -> str:
    if any(state == "fail" for state in states):
        return "fail"
    if any(state == "pass" for state in states):
        return "pass"
    return "not_implemented"


def run_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    report = {
        "project_id": project_id,
        "generated_at": now_iso(),
        "per_frame_checks": [],
        "per_animation_checks": {},
        "status": "pass",
        "notes": [
            "QA only evaluates implemented image heuristics.",
            "Semantic checks such as strict side-view correctness remain out of scope for this pass.",
        ],
    }
    source_hashes = {}
    animation_items = list(ANIMATION_SPECS.items())
    for animation_index, (animation_name, spec) in enumerate(animation_items):
        call_progress(
            progress,
            8 + int((animation_index / max(1, len(animation_items))) * 70),
            "Checking %s animation" % animation_name,
            "Validating frame sizes, clipping, pivots, and loop continuity.",
        )
        frames = []
        hashes = []
        animation_dir = project_dir / "animations" / animation_name
        manifest = load_json(animation_dir / "render_manifest.json", {"frames": []})
        by_name = {item["frame_name"]: item for item in manifest.get("frames", [])}

        for index in range(spec["frame_count"]):
            frame_name = "%s_%02d.png" % (animation_name, index)
            path = animation_dir / frame_name
            if not path.exists():
                raise ValueError("Missing frame: %s" % frame_name)
            image = Image.open(path).convert("RGBA")
            alpha = image.getchannel("A")
            alpha_bbox = alpha.getbbox()
            manifest_row = by_name.get(frame_name)
            source_hashes[str(path.relative_to(project_dir))] = image_sha256(path)
            hashes.append(source_hashes[str(path.relative_to(project_dir))])
            pivot_ok = manifest_row is not None and manifest_row.get("cleanup", {}).get("pivot") == list(FRAME_PIVOT)
            transparent = alpha_bbox is not None and any(value < 255 for value in alpha.getdata())
            clipped = border_has_alpha(image)

            checks = {
                "alpha_presence": check_state("pass" if transparent else "fail"),
                "exact_size_256x256": check_state("pass" if list(image.size) == [FRAME_SIZE, FRAME_SIZE] else "fail"),
                "border_clipping": check_state("fail" if clipped else "pass"),
                "pivot_alignment": check_state("pass" if pivot_ok else "fail", {"expected": list(FRAME_PIVOT)}),
                "outline_thickness_stability": check_state("not_implemented"),
                "palette_drift": check_state("not_implemented"),
            }
            frame_status = aggregate_check_state([item["status"] for item in checks.values()])
            if frame_status == "fail":
                report["status"] = "fail"
            report["per_frame_checks"].append({
                "frame_name": frame_name,
                "status": frame_status,
                "checks": checks,
            })
            if alpha_bbox is not None:
                frames.append({"name": frame_name, "bbox": list(alpha_bbox), "hash": hashes[-1], "manifest": manifest_row})

        bbox_jitter_state = "not_implemented"
        duplicate_frame_state = "pass"
        loop_state = "pass"
        if frames:
            xs = [frame["bbox"][0] for frame in frames]
            widths = [frame["bbox"][2] - frame["bbox"][0] for frame in frames]
            if max(xs) - min(xs) <= 18 and max(widths) - min(widths) <= 28:
                bbox_jitter_state = "pass"
            else:
                bbox_jitter_state = "fail"
            duplicate_frame_state = "fail" if len(set(hashes)) != len(hashes) else "pass"
            first_bbox = frames[0]["bbox"]
            last_bbox = frames[-1]["bbox"]
            loop_state = "pass" if first_bbox == last_bbox else "fail"

        animation_checks = {
            "required_frame_count": check_state("pass" if len(frames) == spec["frame_count"] else "fail"),
            "file_naming": check_state(
                "pass" if [item["name"] for item in frames] == ["%s_%02d.png" % (animation_name, idx) for idx in range(spec["frame_count"])] else "fail"
            ),
            "bbox_jitter": check_state(bbox_jitter_state),
            "duplicate_frame_detection": check_state(duplicate_frame_state),
            "loop_seam_continuity": check_state(loop_state),
            "spritesheet_ordering_validation": check_state("not_implemented"),
        }
        animation_status = aggregate_check_state([item["status"] for item in animation_checks.values()])
        if animation_status == "fail":
            report["status"] = "fail"
        report["per_animation_checks"][animation_name] = {
            "status": animation_status,
            "checks": animation_checks,
        }

    report["source_asset_hashes"] = source_hashes
    project["qa_report"] = report
    project["current_stage"] = "qa"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Checks complete", "Review the check results before export.")
    return report


def export_project(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("qa_report") or project["qa_report"]["status"] != "pass":
        raise ValueError("Export blocked: QA must pass first.")

    project_dir = PROJECTS_ROOT / project_id
    export_dir = project_dir / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_dir.mkdir(parents=True, exist_ok=True)
    ordered_frames = []
    call_progress(progress, 8, "Preparing export", "Copying finished frame images into the export folder.")
    for animation_name in ["idle", "walk"]:
        count = ANIMATION_SPECS[animation_name]["frame_count"]
        for index in range(count):
            source = project_dir / "animations" / animation_name / ("%s_%02d.png" % (animation_name, index))
            target_dir = export_dir / "frames"
            target_dir.mkdir(exist_ok=True)
            target = target_dir / source.name
            target.write_bytes(source.read_bytes())
            ordered_frames.append((animation_name, source.name, target))

    call_progress(progress, 45, "Building spritesheet", "Packing all exported frames into a single sheet.")
    spritesheet = Image.new("RGBA", (FRAME_SIZE * len(ordered_frames), FRAME_SIZE), (0, 0, 0, 0))
    atlas_frames = {}
    for index, (_, frame_name, path) in enumerate(ordered_frames):
        frame_image = Image.open(path).convert("RGBA")
        x = index * FRAME_SIZE
        spritesheet.alpha_composite(frame_image, (x, 0))
        atlas_frames[frame_name] = {"x": x, "y": 0, "w": FRAME_SIZE, "h": FRAME_SIZE}
    spritesheet.save(export_dir / "spritesheet.png")

    animations_payload = {
        name: {
            "fps": spec["fps"],
            "loop": spec["loop"],
            "frames": ["%s_%02d.png" % (name, index) for index in range(spec["frame_count"])],
        }
        for name, spec in ANIMATION_SPECS.items()
    }
    export_manifest = {
        "project_id": project_id,
        "approved_concept_id": project["character_spec"]["approved_concept_id"],
        "export_timestamp": now_iso(),
        "tool_version": TOOL_VERSION,
        "source_asset_hashes": project["qa_report"]["source_asset_hashes"],
    }
    write_json(export_dir / "atlas.json", {"image": "spritesheet.png", "frames": atlas_frames})
    write_json(export_dir / "animations.json", animations_payload)
    write_json(export_dir / "qa_report.json", project["qa_report"])
    write_json(export_dir / "export_manifest.json", export_manifest)

    call_progress(progress, 78, "Building preview", "Creating the animated preview file.")
    preview_frames = [Image.open(path).convert("RGBA") for _, _, path in ordered_frames]
    preview_frames[0].save(
        export_dir / "preview.gif",
        save_all=True,
        append_images=preview_frames[1:],
        duration=[int(1000 / ANIMATION_SPECS["idle"]["fps"])] * ANIMATION_SPECS["idle"]["frame_count"]
        + [int(1000 / ANIMATION_SPECS["walk"]["fps"])] * ANIMATION_SPECS["walk"]["frame_count"],
        loop=0,
        disposal=2,
        transparency=0,
    )

    result = {
        "export_dir": str(export_dir.relative_to(project_dir)),
        "files": [
            "spritesheet.png",
            "atlas.json",
            "animations.json",
            "preview.gif",
            "qa_report.json",
            "export_manifest.json",
        ] + ["frames/%s" % name for _, name, _ in ordered_frames],
    }
    project["last_export"] = result
    project["current_stage"] = "export"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Export ready", "Open the export files from the export panel.")
    return result


def multipart_encode(file_field: str, filename: str, content: bytes, content_type: str) -> Tuple[bytes, str]:
    boundary = "----spriteworkbench%s" % uuid.uuid4().hex
    body = (
        "--%s\r\n"
        "Content-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
        "--%s\r\n"
        "Content-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
        "Content-Type: %s\r\n\r\n"
        % (boundary, boundary, file_field, filename, content_type)
    ).encode("utf-8") + content + ("\r\n--%s--\r\n" % boundary).encode("utf-8")
    return body, "multipart/form-data; boundary=%s" % boundary


class HttpRequestError(RuntimeError):
    pass


def http_request(method: str, url: str, body: Optional[bytes], headers: Dict[str, str], timeout: int) -> bytes:
    last_error = None
    for attempt in range(2):
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except HTTPError as exc:
            payload = exc.read()
            if exc.code >= 500 and attempt == 0:
                last_error = HttpRequestError(payload.decode("utf-8", "replace"))
                continue
            raise HttpRequestError(payload.decode("utf-8", "replace") or exc.reason)
        except (URLError, OSError, TimeoutError) as exc:
            if attempt == 0:
                last_error = exc
                continue
            raise HttpRequestError(str(last_error or exc))
    raise HttpRequestError(str(last_error))


def http_json(method: str, url: str, payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = COMFYUI_TIMEOUT_SECONDS) -> Dict[str, Any]:
    body = None
    combined_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        combined_headers.setdefault("Content-Type", "application/json")
    combined_headers.setdefault("Accept", "application/json")
    raw = http_request(method, url, body, combined_headers, timeout)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def upload_image_to_comfyui(base_url: str, image_path: Path) -> str:
    mime = "image/png"
    if image_path.suffix.lower() in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif image_path.suffix.lower() == ".webp":
        mime = "image/webp"
    body, content_type = multipart_encode("image", image_path.name, image_path.read_bytes(), mime)
    raw = http_request(
        "POST",
        "%s/upload/image" % base_url.rstrip("/"),
        body,
        {"Content-Type": content_type, "Accept": "application/json"},
        COMFYUI_TIMEOUT_SECONDS,
    )
    payload = json.loads(raw.decode("utf-8"))
    name = payload.get("name") or payload.get("subfolder") or payload.get("filename")
    if not name:
        raise ValueError("ComfyUI upload response did not include an uploaded filename.")
    return name


def load_workflow_template(template_name: str) -> Dict[str, Any]:
    path = WORKFLOW_DIR / template_name
    payload = load_json(path, None)
    if not isinstance(payload, dict) or "meta" not in payload or "prompt" not in payload:
        raise ValueError("Invalid workflow template: %s" % template_name)
    return payload


def prepare_workflow_prompt(
    template: Dict[str, Any],
    request: ConceptRequest,
    output_prefix: str,
    checkpoint_name: str,
    conditioning_filename: Optional[str],
) -> Dict[str, Any]:
    prompt_graph = copy.deepcopy(template["prompt"])
    meta = template["meta"]

    checkpoint_meta = meta["checkpoint"]
    prompt_graph[checkpoint_meta["node"]]["inputs"][checkpoint_meta["input"]] = checkpoint_name

    positive_meta = meta["positive"]
    negative_meta = meta["negative"]
    prompt_graph[positive_meta["node"]]["inputs"][positive_meta["input"]] = request.positive_prompt
    prompt_graph[negative_meta["node"]]["inputs"][negative_meta["input"]] = request.negative_prompt

    latent_meta = meta["latent"]
    prompt_graph[latent_meta["node"]]["inputs"][latent_meta["width_input"]] = request.width
    prompt_graph[latent_meta["node"]]["inputs"][latent_meta["height_input"]] = request.height

    sampler_meta = meta["sampler"]
    sampler_inputs = prompt_graph[sampler_meta["node"]]["inputs"]
    sampler_inputs[sampler_meta["seed_input"]] = int(request.seed)
    if sampler_meta.get("steps_input"):
        sampler_inputs[sampler_meta["steps_input"]] = meta.get("defaults", {}).get("steps", sampler_inputs.get(sampler_meta["steps_input"], 24))
    if sampler_meta.get("cfg_input"):
        sampler_inputs[sampler_meta["cfg_input"]] = meta.get("defaults", {}).get("cfg", sampler_inputs.get(sampler_meta["cfg_input"], 6.5))

    save_meta = meta["save"]
    prompt_graph[save_meta["node"]]["inputs"][save_meta["input"]] = output_prefix

    conditioning_meta = meta.get("conditioning")
    if conditioning_filename:
        if not conditioning_meta:
            raise ValueError("Workflow template does not define conditioning nodes.")
        prompt_graph[conditioning_meta["load_node"]]["inputs"][conditioning_meta["image_input"]] = conditioning_filename
        sampler_inputs[sampler_meta["latent_input"]] = conditioning_meta["conditioned_source"]
        denoise = request.refine_strength if request.refine_strength is not None else conditioning_meta.get("default_denoise")
        if sampler_meta.get("denoise_input") and denoise is not None:
            sampler_inputs[sampler_meta["denoise_input"]] = denoise
    else:
        if conditioning_meta and conditioning_meta.get("required"):
            raise ValueError("This workflow requires an input image.")
        if conditioning_meta and conditioning_meta.get("empty_source") is not None:
            sampler_inputs[sampler_meta["latent_input"]] = conditioning_meta["empty_source"]
        if sampler_meta.get("denoise_input") and request.refine_strength is not None:
            sampler_inputs[sampler_meta["denoise_input"]] = request.refine_strength

    return prompt_graph


def extract_history_images(history_payload: Dict[str, Any], prompt_id: str) -> List[Dict[str, Any]]:
    entry = history_payload.get(prompt_id) if isinstance(history_payload, dict) else None
    if entry is None and isinstance(history_payload, dict) and "outputs" in history_payload:
        entry = history_payload
    if not isinstance(entry, dict):
        return []
    outputs = entry.get("outputs") or {}
    images = []
    for node_output in outputs.values():
        images.extend(node_output.get("images") or [])
    return images


def fetch_comfyui_history_image(base_url: str, image_meta: Dict[str, Any]) -> bytes:
    query = urlencode({
        "filename": image_meta["filename"],
        "subfolder": image_meta.get("subfolder", ""),
        "type": image_meta.get("type", "output"),
    })
    return http_request("GET", "%s/view?%s" % (base_url.rstrip("/"), query), None, {}, COMFYUI_TIMEOUT_SECONDS)


class DebugProceduralConceptBackend(object):
    name = "debug_procedural"

    def healthcheck(self) -> Dict[str, Any]:
        return {"ok": True, "backend": self.name, "mode": "debug_only"}

    def generate(self, request: ConceptRequest) -> List[GeneratedConcept]:
        if request.output_path is None:
            raise ValueError("Debug backend requires an output path.")
        palette = palette_from_seed(request.seed, 0, request.variation_axes.get("palette_direction", "storm steel"))
        image = Image.new("RGBA", (request.width, request.height), (14, 18, 24, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((56, 40, request.width - 56, request.height - 56), radius=36, fill=(18, 24, 32, 255), outline=(62, 75, 90, 255), width=4)
        draw.ellipse((request.width // 2 - 84, 120, request.width // 2 + 18, 232), fill=hex_to_rgba(palette["skin"]), outline=hex_to_rgba(palette["outline"]), width=4)
        draw.rounded_rectangle((request.width // 2 - 54, 220, request.width // 2 + 104, 530), radius=24, fill=hex_to_rgba(palette["base"]), outline=hex_to_rgba(palette["outline"]), width=5)
        draw.polygon(
            [
                (request.width // 2 - 40, 250),
                (request.width // 2 + 110, 250),
                (request.width // 2 + 130, 360),
                (request.width // 2 - 20, 360),
            ],
            fill=hex_to_rgba(palette["accent"]),
            outline=hex_to_rgba(palette["outline"]),
        )
        draw.rectangle((request.width // 2 + 120, 320, request.width // 2 + 240, 350), fill=hex_to_rgba(palette["prop"]), outline=hex_to_rgba(palette["outline"]), width=4)
        draw.text((80, request.height - 130), request.variation_axes.get("summary", "debug concept"), fill=(235, 235, 235, 255))
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(request.output_path)
        return [
            GeneratedConcept(
                seed=request.seed,
                image_path=request.output_path,
                backend_name=self.name,
                backend_run_id=stable_hash(request.project_id, str(request.seed))[:12],
                positive_prompt=request.positive_prompt,
                negative_prompt=request.negative_prompt,
                variation_axes=request.variation_axes or {},
                references_used=[],
            )
        ]


class ComfyUIConceptBackend(object):
    name = "comfyui"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def healthcheck(self) -> Dict[str, Any]:
        try:
            http_request("GET", self.base_url, None, {}, COMFYUI_TIMEOUT_SECONDS)
            return {"ok": True, "backend": self.name, "base_url": self.base_url}
        except HttpRequestError as exc:
            return {"ok": False, "backend": self.name, "base_url": self.base_url, "error": str(exc)}

    def generate(self, request: ConceptRequest) -> List[GeneratedConcept]:
        if request.output_path is None:
            raise ValueError("Concept generation requires an output path.")
        template_name = "concept_refine_img2img.json" if request.refine_from_image is not None else "concept_txt2img.json"
        template = load_workflow_template(template_name)

        project_dir = PROJECTS_ROOT / request.project_id
        conditioning_board = create_conditioning_board(
            project_dir,
            request.references,
            request.refine_from_image,
            (request.width, request.height),
            "conditioning_%s" % uuid.uuid4().hex[:8],
        )
        conditioning_filename = None
        if conditioning_board is not None:
            conditioning_filename = upload_image_to_comfyui(self.base_url, conditioning_board)

        checkpoint_name = request.checkpoint_name or DEFAULT_COMFYUI_CHECKPOINT
        output_prefix = "sprite-workbench/%s/%s" % (request.project_id, uuid.uuid4().hex[:10])
        prompt_graph = prepare_workflow_prompt(template, request, output_prefix, checkpoint_name, conditioning_filename)
        submit = http_json("POST", "%s/prompt" % self.base_url, {"prompt": prompt_graph}, timeout=COMFYUI_TIMEOUT_SECONDS)
        prompt_id = submit.get("prompt_id")
        if not prompt_id:
            raise ValueError("ComfyUI did not return a prompt_id.")
        if submit.get("node_errors"):
            raise ValueError("ComfyUI reported node errors: %s" % submit["node_errors"])

        deadline = time.monotonic() + COMFYUI_JOB_TIMEOUT_SECONDS
        image_metas = []
        while time.monotonic() < deadline:
            history_payload = http_json("GET", "%s/history/%s" % (self.base_url, quote(str(prompt_id))), timeout=COMFYUI_TIMEOUT_SECONDS)
            image_metas = extract_history_images(history_payload, str(prompt_id))
            if image_metas:
                break
            time.sleep(COMFYUI_POLL_SECONDS)
        if not image_metas:
            raise ValueError(
                "ComfyUI concept job timed out after %s seconds. "
                "Increase SPRITE_WORKBENCH_COMFYUI_JOB_TIMEOUT_SECONDS for slower local runs."
                % COMFYUI_JOB_TIMEOUT_SECONDS
            )

        image_bytes = fetch_comfyui_history_image(self.base_url, image_metas[0])
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(image_bytes)
        return [
            GeneratedConcept(
                seed=request.seed,
                image_path=request.output_path,
                backend_name=self.name,
                backend_run_id=str(prompt_id),
                positive_prompt=request.positive_prompt,
                negative_prompt=request.negative_prompt,
                variation_axes=request.variation_axes or {},
                references_used=[
                    {
                        "role": item.role,
                        "local_path": str(item.local_path.relative_to(project_dir)),
                        "weight": item.weight,
                    }
                    for item in request.references
                ],
            )
        ]


def get_concept_backend(mode: str) -> ConceptBackend:
    if mode == "debug_procedural":
        return DebugProceduralConceptBackend()
    return ComfyUIConceptBackend(DEFAULT_COMFYUI_BASE_URL)


def relative_preview_path(project_dir: Path, image_path: Path) -> str:
    return str(image_path.relative_to(project_dir))


def generate_run(
    project_id: str,
    run_kind: str,
    source_concept_id: Optional[str] = None,
    attribute_group: Optional[str] = None,
    target_value: Optional[str] = None,
    strength_label: Optional[str] = None,
    progress: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    backend_mode = project["brief"]["backend_mode"]
    backend = get_concept_backend(backend_mode)
    call_progress(progress, 5, "Checking the image generator", "Making sure concept generation is available.")
    health = backend.healthcheck()
    if not health.get("ok") and backend_mode != "debug_procedural":
        raise ValueError("ComfyUI backend unavailable: %s" % health.get("error", "unknown backend error"))

    if run_kind == "initial":
        variation_axes_list = build_initial_variation_axes(project["brief"])
    else:
        if source_concept_id is None:
            raise ValueError("Refinement and similar runs require a source concept.")
        base_concept = next((item for item in project["concepts"] if item["concept_id"] == source_concept_id), None)
        if base_concept is None:
            raise ValueError("Source concept not found.")
        if run_kind == "similar":
            variation_axes_list = build_refinement_variation_axes(base_concept, "silhouette", base_concept.get("silhouette"), "subtle", "similar")
            strength_label = "subtle"
        else:
            if attribute_group not in MAJOR_REFINEMENT_LOCKS:
                raise ValueError("Refinement must change exactly one supported major attribute group.")
            if not target_value:
                raise ValueError("Refinement target value is required.")
            if strength_label not in REFINEMENT_STRENGTHS:
                raise ValueError("Refinement strength must be one of: %s." % ", ".join(sorted(REFINEMENT_STRENGTHS)))
            variation_axes_list = build_refinement_variation_axes(base_concept, attribute_group, target_value, strength_label, "refinement")

    run_id = "run-%s" % uuid.uuid4().hex[:10]
    concepts = project["concepts"]
    serial = next_concept_serial(concepts)
    request_references = make_reference_inputs(project_dir, project["brief"])
    generated_records = []
    start_time = time.monotonic()

    if run_kind == "initial":
        base_concept = None
        refine_source = None
        concept_count = INITIAL_CONCEPT_COUNT
    else:
        base_concept = next(item for item in project["concepts"] if item["concept_id"] == source_concept_id)
        refine_source = project_dir / base_concept["preview_image"]
        concept_count = REFINEMENT_CONCEPT_COUNT

    for index, variation_axes in enumerate(variation_axes_list[:concept_count]):
        call_progress(
            progress,
            12 + int((index / max(1, concept_count)) * 72),
            "Generating look %d of %d" % (index + 1, concept_count),
            variation_axes.get("summary"),
        )
        concept_id = "concept-%04d" % serial
        output_path = project_dir / "concepts" / ("%s.png" % concept_id)
        positive_prompt, negative_prompt = build_prompt_bundle(project["brief"], variation_axes, base_concept)
        seed = stable_int(project_id, run_id, concept_id, positive_prompt, mod=4_294_967_295)
        refine_strength = None
        if run_kind in ("refinement", "similar"):
            refine_strength = REFINEMENT_STRENGTHS[strength_label or "subtle"]
        request = ConceptRequest(
            project_id=project_id,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=CONCEPT_CANVAS[0],
            height=CONCEPT_CANVAS[1],
            seed=seed,
            count=1,
            references=request_references,
            mode=run_kind,
            refine_from_image=refine_source,
            refine_strength=refine_strength,
            variation_axes=variation_axes,
            output_path=output_path,
            checkpoint_name=project["brief"].get("comfyui_checkpoint") or DEFAULT_COMFYUI_CHECKPOINT,
        )
        generated = backend.generate(request)[0]
        concept = {
            "concept_id": concept_id,
            "run_id": run_id,
            "run_kind": run_kind,
            "created_at": now_iso(),
            "seed": seed,
            "positive_prompt": generated.positive_prompt,
            "negative_prompt": generated.negative_prompt,
            "prompt": generated.positive_prompt,
            "preview_image": relative_preview_path(project_dir, generated.image_path),
            "backend_name": generated.backend_name,
            "backend_run_id": generated.backend_run_id,
            "variation_axes": variation_axes,
            "difference_summary": variation_axes.get("summary"),
            "silhouette": variation_axes.get("silhouette") or project["brief"]["silhouette_intent"],
            "outfit": variation_axes.get("outfit_complexity") or project["brief"]["outfit_materials"],
            "palette_direction": variation_axes.get("palette_direction") or project["brief"]["palette_mood"],
            "palette": palette_from_seed(seed, index, project["brief"]["palette_mood"]),
            "prop_variant": variation_axes.get("prop_variant") or project["brief"]["prop"],
            "face_head_shape": project["brief"]["shape_language"],
            "references_used": generated.references_used,
            "review_state": {"approved": False, "favorite": False, "rejected": False},
            "approved": False,
            "favorite": False,
            "rejected": False,
            "lineage": {"run_id": run_id, "parent_concept_id": source_concept_id},
        }
        generated_records.append(concept)
        serial += 1

    call_progress(progress, 88, "Reviewing generated looks", "Running lightweight triage and saving concept metadata.")
    annotate_run_triage(project_dir, generated_records)
    for concept in generated_records:
        concepts.append(concept)
        save_concept(project_dir, concept)

    summary = {
        "type": "concept_run",
        "run_id": run_id,
        "run_kind": run_kind,
        "status": "completed",
        "created_at": now_iso(),
        "completed_at": now_iso(),
        "concept_ids": [item["concept_id"] for item in generated_records],
        "concept_count": len(generated_records),
        "backend_name": generated_records[0]["backend_name"] if generated_records else backend_mode,
        "backend_mode": backend_mode,
        "source_concept_id": source_concept_id,
        "attribute_group": attribute_group,
        "target_value": target_value,
        "refinement_strength_label": strength_label,
        "refinement_strength": REFINEMENT_STRENGTHS.get(strength_label) if strength_label else None,
        "references_used": generated_records[0]["references_used"] if generated_records else [],
        "summary": "%s run with %d concepts" % (run_kind, len(generated_records)),
        "duration_ms": int((time.monotonic() - start_time) * 1000),
    }
    history = append_history_event(project_id, summary)
    project["history"] = history
    project["concepts"] = concepts
    project["current_stage"] = "concepts" if run_kind == "initial" else "refine"
    project["status"] = "concepts_generated" if run_kind == "initial" else "concepts_refined"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Looks ready", "The concept board has been updated.")
    return {
        "run_id": run_id,
        "run_kind": run_kind,
        "concept_ids": [item["concept_id"] for item in generated_records],
        "triage": summarize_run_triage(generated_records),
    }


def create_job(project_id: Optional[str], job_type: str, target: Callable[[ProgressCallback], Any]) -> Dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "job_id": job_id,
        "project_id": project_id,
        "job_type": job_type,
        "status": "queued",
        "progress_percent": 0,
        "progress_label": "Queued",
        "progress_detail": "Waiting to start.",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "result": None,
        "error": None,
    }
    with JOB_LOCK:
        JOBS[job_id] = job

    def runner() -> None:
        with JOB_LOCK:
            JOBS[job_id]["status"] = "running"
            JOBS[job_id]["progress_percent"] = 4
            JOBS[job_id]["progress_label"] = "Starting"
            JOBS[job_id]["progress_detail"] = "The server has started the job."
            JOBS[job_id]["updated_at"] = now_iso()

        def report(percent: int, label: Optional[str], detail: Optional[str] = None) -> None:
            with JOB_LOCK:
                if job_id not in JOBS:
                    return
                JOBS[job_id]["progress_percent"] = max(0, min(100, int(percent)))
                if label:
                    JOBS[job_id]["progress_label"] = label
                if detail is not None:
                    JOBS[job_id]["progress_detail"] = detail
                JOBS[job_id]["updated_at"] = now_iso()

        try:
            result = target(report)
            with JOB_LOCK:
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["progress_percent"] = 100
                JOBS[job_id]["progress_label"] = "Completed"
                JOBS[job_id]["progress_detail"] = "The job finished successfully."
                JOBS[job_id]["result"] = result
                JOBS[job_id]["updated_at"] = now_iso()
            if project_id:
                append_history_event(project_id, {
                    "type": "job_summary",
                    "job_id": job_id,
                    "job_type": job_type,
                    "status": "completed",
                    "summary": "Job completed",
                    "completed_at": now_iso(),
                })
        except Exception as exc:
            with JOB_LOCK:
                JOBS[job_id]["status"] = "failed"
                JOBS[job_id]["progress_label"] = "Failed"
                JOBS[job_id]["progress_detail"] = str(exc)
                JOBS[job_id]["error"] = str(exc)
                JOBS[job_id]["updated_at"] = now_iso()
            if project_id:
                append_history_event(project_id, {
                    "type": "job_summary",
                    "job_id": job_id,
                    "job_type": job_type,
                    "status": "failed",
                    "summary": str(exc),
                    "completed_at": now_iso(),
                })

    threading.Thread(target=runner, daemon=True).start()
    return job


class SpriteWorkbenchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if path == "/api/health":
            backend = ComfyUIConceptBackend(DEFAULT_COMFYUI_BASE_URL).healthcheck()
            return self._send_json({
                "ok": True,
                "tool_version": TOOL_VERSION,
                "projects_root": str(PROJECTS_ROOT),
                "stage_maturity": load_stage_maturity(),
                "backend": backend,
                "default_checkpoint": DEFAULT_COMFYUI_CHECKPOINT,
                "comfyui_job_timeout_seconds": COMFYUI_JOB_TIMEOUT_SECONDS,
            })

        if path == "/api/projects":
            include_archived = query.get("include_archived", ["0"])[0] in {"1", "true", "yes"}
            return self._send_json({"projects": [project_summary(item) for item in list_projects(include_archived)]})

        project_match = re.fullmatch(r"/api/projects/([^/]+)", path)
        if project_match:
            try:
                return self._send_json(load_project(project_match.group(1)))
            except FileNotFoundError:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")

        job_match = re.fullmatch(r"/api/projects/([^/]+)/jobs/([^/]+)", path)
        if job_match:
            project_id, job_id = job_match.groups()
            with JOB_LOCK:
                job = JOBS.get(job_id)
            if not job or job.get("project_id") != project_id:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Job not found")
            return self._send_json(job)

        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            if path == "/api/projects":
                return self._send_json(create_project(read_body(self)), status=HTTPStatus.CREATED)

            update_match = re.fullmatch(r"/api/projects/([^/]+)/brief", path)
            if update_match:
                return self._send_json(update_project_brief(update_match.group(1), read_body(self)))

            wizard_match = re.fullmatch(r"/api/projects/([^/]+)/wizard-state", path)
            if wizard_match:
                return self._send_json(update_wizard_state(wizard_match.group(1), read_body(self)))

            duplicate_match = re.fullmatch(r"/api/projects/([^/]+)/duplicate", path)
            if duplicate_match:
                return self._send_json(duplicate_project(duplicate_match.group(1)), status=HTTPStatus.CREATED)

            archive_match = re.fullmatch(r"/api/projects/([^/]+)/archive", path)
            if archive_match:
                return self._send_json(archive_project(archive_match.group(1)))

            generate_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/generate", path)
            if generate_match:
                project_id = generate_match.group(1)
                return self._send_json(
                    create_job(project_id, "concepts.generate", lambda progress: generate_run(project_id, "initial", progress=progress)),
                    status=HTTPStatus.ACCEPTED,
                )

            approve_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/([^/]+)/(approve|favorite|reject)", path)
            if approve_match:
                project_id, concept_id, action = approve_match.groups()
                payload = read_body(self)
                value = payload.get("value")
                return self._send_json(update_concept_review_state(project_id, concept_id, action, value))

            select_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/([^/]+)/select", path)
            if select_match:
                project_id, concept_id = select_match.groups()
                return self._send_json(update_concept_review_state(project_id, concept_id, "approve", True))

            similar_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/([^/]+)/regenerate-similar", path)
            if similar_match:
                project_id, concept_id = similar_match.groups()
                return self._send_json(
                    create_job(project_id, "concepts.regenerate_similar", lambda progress: generate_run(project_id, "similar", source_concept_id=concept_id, progress=progress)),
                    status=HTTPStatus.ACCEPTED,
                )

            refine_match = re.fullmatch(r"/api/projects/([^/]+)/refine", path)
            if refine_match:
                project_id = refine_match.group(1)
                payload = read_body(self)
                source_concept_id = payload.get("concept_id")
                if not source_concept_id:
                    project = load_project(project_id)
                    source_concept_id = project.get("selected_concept_id")
                attribute_group = payload.get("attribute_group") or payload.get("lock") or (payload.get("locks") or [None])[0]
                target_value = (payload.get("target_value") or payload.get("value") or "").strip()
                strength = payload.get("strength") or payload.get("refinement_strength")
                return self._send_json(
                    create_job(
                        project_id,
                        "concepts.refine",
                        lambda progress: generate_run(
                            project_id,
                            "refinement",
                            source_concept_id=source_concept_id,
                            attribute_group=attribute_group,
                            target_value=target_value,
                            strength_label=strength,
                            progress=progress,
                        ),
                    ),
                    status=HTTPStatus.ACCEPTED,
                )

            layers_match = re.fullmatch(r"/api/projects/([^/]+)/layers/build", path)
            if layers_match:
                project_id = layers_match.group(1)
                return self._send_json(create_job(project_id, "layers.build", lambda progress: build_layered_character(project_id, progress=progress)), status=HTTPStatus.ACCEPTED)

            rig_match = re.fullmatch(r"/api/projects/([^/]+)/rig/build", path)
            if rig_match:
                project_id = rig_match.group(1)
                return self._send_json(create_job(project_id, "rig.build", lambda progress: build_rig(project_id, progress=progress)), status=HTTPStatus.ACCEPTED)

            idle_match = re.fullmatch(r"/api/projects/([^/]+)/animations/idle/render", path)
            if idle_match:
                project_id = idle_match.group(1)
                return self._send_json(create_job(project_id, "animations.idle.render", lambda progress: render_animation(project_id, "idle", progress=progress)), status=HTTPStatus.ACCEPTED)

            walk_match = re.fullmatch(r"/api/projects/([^/]+)/animations/walk/render", path)
            if walk_match:
                project_id = walk_match.group(1)
                return self._send_json(create_job(project_id, "animations.walk.render", lambda progress: render_animation(project_id, "walk", progress=progress)), status=HTTPStatus.ACCEPTED)

            qa_match = re.fullmatch(r"/api/projects/([^/]+)/qa/run", path)
            if qa_match:
                project_id = qa_match.group(1)
                return self._send_json(create_job(project_id, "qa.run", lambda progress: run_qa(project_id, progress=progress)), status=HTTPStatus.ACCEPTED)

            export_match = re.fullmatch(r"/api/projects/([^/]+)/export", path)
            if export_match:
                project_id = export_match.group(1)
                return self._send_json(create_job(project_id, "export", lambda progress: export_project(project_id, progress=progress)), status=HTTPStatus.ACCEPTED)

            approve_layer_match = re.fullmatch(r"/api/projects/([^/]+)/layer-review/approve", path)
            if approve_layer_match:
                project_id = approve_layer_match.group(1)
                project = load_project(project_id)
                if not project.get("layered_character") or project["layered_character"]["status"] != "pass":
                    raise ValueError("Layer review cannot be approved before a passing layer build.")
                project["layer_review_approved"] = True
                project["layered_character"]["approved_for_rigging"] = True
                project["updated_at"] = now_iso()
                save_project(project)
                return self._send_json({"ok": True})

            approve_rig_match = re.fullmatch(r"/api/projects/([^/]+)/rig-review/approve", path)
            if approve_rig_match:
                project_id = approve_rig_match.group(1)
                project = load_project(project_id)
                if not project.get("rig"):
                    raise ValueError("Rig review cannot be approved before rig build.")
                if not project.get("layer_review_approved"):
                    raise ValueError("Layer review approval is required before rig review approval.")
                project["rig_review_approved"] = True
                project["rig"]["approved_for_production"] = True
                project["updated_at"] = now_iso()
                save_project(project)
                return self._send_json({"ok": True})

        except FileNotFoundError:
            return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")
        except ValueError as exc:
            return self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except HttpRequestError as exc:
            return self._send_error_json(HTTPStatus.BAD_GATEWAY, str(exc))
        except Exception as exc:
            return self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

        return self._send_error_json(HTTPStatus.NOT_FOUND, "Unknown API route")

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: HTTPStatus, message: str) -> None:
        return self._send_json({"ok": False, "error": message}, status=status)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Solo AI Sprite Workbench server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), SpriteWorkbenchHandler)
    print("Sprite workbench running at http://%s:%s/tools/2d-sprite-and-animation/index.html" % (args.host, args.port))
    print("Projects directory: %s" % PROJECTS_ROOT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
