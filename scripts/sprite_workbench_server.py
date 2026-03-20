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
from typing import Any, Callable, Dict, List, Optional, Protocol, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse, unquote
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parent.parent
TOOL_DIR = ROOT / "tools" / "2d-sprite-and-animation"
PROJECTS_ROOT = TOOL_DIR / "projects-data"
WORKFLOW_DIR = TOOL_DIR / "workflows"
STAGE_MATURITY_PATH = TOOL_DIR / "stage-maturity.json"

# Canonical downstream contract for new work:
# - sprite_model.json
# - sprite_model_history.json
# - rig.json
# - animation_clips.json
# - manual_animation_clips.json
# - qa_report.json
CANONICAL_DOWNSTREAM_FILES = {
    "rig_layout": "rig_layout.json",
    "rig_layout_history": "rig_layout_history.json",
    "part_manifest": "part_manifest.json",
    "part_manifest_history": "part_manifest_history.json",
    "part_shapes": "part_shapes.json",
    "part_shapes_history": "part_shapes_history.json",
    "part_split": "part_split.json",
    "part_split_history": "part_split_history.json",
    "sprite_model": "sprite_model.json",
    "sprite_model_history": "sprite_model_history.json",
    "rig": "rig.json",
    "animation_clips": "animation_clips.json",
    "manual_animation_clips": "manual_animation_clips.json",
    "ai_workflow": "ai_workflow.json",
    "external_authoring": "external_authoring.json",
    "qa_report": "qa_report.json",
}
LEGACY_DOWNSTREAM_FILES = {
    "layered_character": "layered_character.json",
    "animation_templates": "animation_templates.json",
    "palette": "palette.json",
}
SPRITE_MODEL_REVISIONS_DIRNAME = "sprite_model_revisions"

TOOL_VERSION = "solo-ai-sprite-workbench-v4"
SKELFORM_EDITOR_URL = "https://skelform.org/editor/"
SKELFORM_DOCS_URL = "https://skelform.org/user-docs/"
AI_WORKFLOW_PROFILE = "ai_sideview_v1"
AI_CHARACTER_LOCK_COUNT = 6
AI_KEY_POSE_NAMES = [
    "idle_a",
    "idle_b",
    "walk_contact_front",
    "walk_passing_front",
    "walk_contact_back",
    "walk_passing_back",
]
AI_CLIP_SPECS = {
    "idle": {
        "fps": 8,
        "frame_count": 6,
        "pose_sequence": ["idle_a", "idle_b", "idle_a"],
    },
    "walk": {
        "fps": 10,
        "frame_count": 8,
        "pose_sequence": [
            "walk_contact_front",
            "walk_passing_front",
            "walk_contact_back",
            "walk_passing_back",
            "walk_contact_front",
        ],
    },
}
DEFAULT_COMFYUI_BASE_URL = os.environ.get("SPRITE_WORKBENCH_COMFYUI_URL", "http://127.0.0.1:8188")
DEFAULT_COMFYUI_CHECKPOINT = os.environ.get("SPRITE_WORKBENCH_COMFYUI_CHECKPOINT", "sd15.safetensors")
GEMINI_API_BASE_URL = os.environ.get("GEMINI_API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
DEFAULT_GEMINI_VALIDATION_MODEL = os.environ.get("SPRITE_WORKBENCH_GEMINI_VALIDATION_MODEL", "gemini-2.5-flash")

PIXELLAB_API_KEY = os.environ.get("PIXELLAB_API_KEY", "")


def pixellab_configured() -> bool:
    """Return True if a Pixel Lab API key is set in the environment."""
    return bool(PIXELLAB_API_KEY)


_pixellab_client = None


def get_pixellab_client():
    """Lazy Pixel Lab client initializer (keeps server import fast)."""
    global _pixellab_client
    if not pixellab_configured():
        return None
    if _pixellab_client is None:
        # Lazy import to avoid importing PIL/client machinery unless needed.
        import sys as _sys, pathlib as _pl
        _project_root = str(_pl.Path(__file__).resolve().parent.parent)
        if _project_root not in _sys.path:
            _sys.path.insert(0, _project_root)
        from scripts.pixellab_client import PixelLabClient

        _pixellab_client = PixelLabClient(api_key=PIXELLAB_API_KEY)
    return _pixellab_client


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
WIZARD_STEPS = ["project", "brief", "references", "concepts", "review", "rig_layout", "part_manifest", "part_shape_edit", "split_build", "split_review", "sprite_model", "rig", "clips", "qa", "export"]
# Guided AI workflow (non-legacy): no rig_layout / part_manifest steps in the stepper UI.
WIZARD_STEPS_AI = ["project", "brief", "references", "concepts", "review", "clips", "qa", "export"]
# Inserted after "clips" for Pixel Lab guided flow (Phase 7.5).
WIZARD_STEP_ANIMATIONS = "animations"
WIZARD_STEPS_KNOWN = set(WIZARD_STEPS) | {WIZARD_STEP_ANIMATIONS}
MASTER_POSE_COUNT = 3

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
BACKEND_MODES = ("comfyui", "debug_procedural", "pixellab")
MAJOR_REFINEMENT_LOCKS = {"silhouette", "face_head_shape", "outfit", "palette", "prop"}
REFERENCE_SPRITESHEET_HINTS = ("sprite", "spritesheet", "spritelist", "sheet", "idle", "walk", "run", "attack", "anim")

DEFAULT_NEGATIVE_PROMPT = (
    "front view, rear view, top-down, isometric, multiple characters, crowd, group shot, "
    "full environment scene, busy background, extra limbs, extra arms, extra weapons, "
    "wings, huge cape, non-humanoid anatomy, mount, vehicle, text, watermark, logo, "
    "character sheet, model sheet, turnaround sheet, sprite sheet, animation sheet, silhouette sheet, "
    "contact sheet, collage, mood board, sketch page, comic page, split panel layout, multiple poses, "
    "pose lineup, small figure, distant figure, tiny subject, cropped body, cut off feet, cut off head"
)

# Pixel Lab scaffold defaults (kept server-side for deterministic prompt generation).
SUPPORTED_CANVAS_SIZES = (32, 64, 128, 256)
DEFAULT_CANVAS_SIZE = 64
DEFAULT_OUTLINE_STYLE = "single color black outline"
DEFAULT_SHADING_STYLE = "medium shading"
DEFAULT_DETAIL_LEVEL = "medium detail"
DEFAULT_CHARACTER_TEMPLATE = "mannequin"

OUTLINE_STYLE_MAP = {
    # User-friendly values (what we store in brief) -> Pixel Lab values.
    # Pixel Lab accepts these as strings for weak/guide conditioning.
    "single color black outline": "single color black outline",
    "selective outline": "selective outline",
    "lineless": "lineless",
}

SHADING_STYLE_MAP = {
    "flat shading": "flat shading",
    "basic shading": "basic shading",
    "medium shading": "medium shading",
    "soft shading": "soft shading",
    "hard shading": "hard shading",
}

DETAIL_LEVEL_MAP = {
    "low detail": "low detail",
    "medium detail": "medium detail",
    "highly detailed": "highly detailed",
}

CHARACTER_TEMPLATE_MAP = {
    "mannequin": "mannequin",
    "bear": "bear",
    "cat": "cat",
    "dog": "dog",
    "horse": "horse",
    "lion": "lion",
}


def coerce_canvas_size(value: Any, default: int = DEFAULT_CANVAS_SIZE) -> int:
    """Coerce `canvas_size` into a Pixel Lab supported integer size."""
    try:
        if value is None:
            return default
        size = int(value)
    except (TypeError, ValueError):
        return default
    return size if size in SUPPORTED_CANVAS_SIZES else default


def pick_mapped_style(mapping: Dict[str, str], user_value: Optional[str], default_user_value: str) -> Tuple[str, str]:
    """
    Returns (user_value_normalized, pixel_lab_value).
    Keeps the "user-friendly" vocabulary in the brief, while mapping to Pixel Lab strings.
    """
    normalized = (user_value or "").strip()
    if not normalized:
        normalized = default_user_value
    if normalized not in mapping:
        normalized = default_user_value
    return normalized, mapping[normalized]

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

CONCEPT_RESCUE_POSITIVE_RULES = (
    "exactly one full-body character only, large centered figure occupying most of the canvas, "
    "plain studio backdrop, no concept page layout, no pose lineup, no thumbnail sheet, "
    "head and feet both fully visible, single readable side-view silhouette"
)

CONCEPT_RESCUE_NEGATIVE_RULES = (
    "multiple silhouettes, silhouette lineup, design sheet, turnarounds, concept sheet, contact sheet, "
    "sprite page, reference page, white margin blocks, page annotations, tiny character, distant figure, "
    "cropped framing, duplicate character, multi-pose board"
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

LEGACY_RIG_PROFILE = "side_humanoid_full_20"
SIDE_KNIGHT_SIMPLE_7 = "side_knight_simple_7"
SIDE_KNIGHT_DUAL_LEG_8 = "side_knight_dual_leg_8"

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

DEFAULT_CLIP_CONTROLS = {
    "idle": {
        "body_bob": 2.0,
        "torso_lean": 2.5,
        "arm_swing": 6.0,
        "leg_swing": 4.0,
        "foot_lift": 4.0,
        "prop_lag": 1.5,
    },
    "walk": {
        "body_bob": 6.0,
        "torso_lean": 3.5,
        "arm_swing": 18.0,
        "leg_swing": 20.0,
        "foot_lift": 16.0,
        "prop_lag": 4.0,
    },
}

SPRITE_MODEL_FAIL_MIN_MASK_AREA = 18
SPRITE_MODEL_WARN_MIN_MASK_AREA = 36
SPRITE_MODEL_MIN_DIMENSION = 2
SPRITE_MODEL_WARN_COMPONENT_OVERLAP_RATIO = 0.62
SPRITE_MODEL_WARN_PROP_OVERLAP_RATIO = 0.48

PART_PARENT_JOINTS = {
    "head": "head",
    "hair_front": "head",
    "hair_back": "head",
    "torso": "torso",
    "pelvis": "pelvis",
    "upper_arm_left": "shoulder_left",
    "lower_arm_left": "elbow_left",
    "hand_left": "wrist_left",
    "upper_arm_right": "shoulder_right",
    "lower_arm_right": "elbow_right",
    "hand_right": "wrist_right",
    "upper_leg_left": "hip_left",
    "lower_leg_left": "knee_left",
    "foot_left": "ankle_left",
    "upper_leg_right": "hip_right",
    "lower_leg_right": "knee_right",
    "foot_right": "ankle_right",
    "prop": "wrist_right",
    "accessory_front": "torso",
    "accessory_back": "torso",
}

PART_DRAW_ORDERS = {
    "hair_back": 5,
    "accessory_back": 6,
    "upper_leg_left": 10,
    "lower_leg_left": 11,
    "foot_left": 12,
    "pelvis": 14,
    "torso": 16,
    "upper_arm_left": 18,
    "lower_arm_left": 19,
    "hand_left": 20,
    "head": 22,
    "hair_front": 23,
    "upper_leg_right": 24,
    "lower_leg_right": 25,
    "foot_right": 26,
    "upper_arm_right": 28,
    "lower_arm_right": 29,
    "hand_right": 30,
    "prop": 32,
    "accessory_front": 34,
}

PART_REGION_FRACTIONS = {
    "head": (0.28, 0.02, 0.72, 0.20),
    "hair_front": (0.34, 0.02, 0.76, 0.16),
    "hair_back": (0.18, 0.02, 0.64, 0.18),
    "torso": (0.26, 0.18, 0.76, 0.50),
    "pelvis": (0.28, 0.48, 0.70, 0.62),
    "upper_arm_left": (0.12, 0.20, 0.56, 0.40),
    "lower_arm_left": (0.08, 0.34, 0.52, 0.56),
    "hand_left": (0.06, 0.44, 0.40, 0.62),
    "upper_arm_right": (0.46, 0.20, 0.88, 0.40),
    "lower_arm_right": (0.52, 0.34, 0.92, 0.56),
    "hand_right": (0.60, 0.44, 0.96, 0.64),
    "upper_leg_left": (0.26, 0.56, 0.52, 0.78),
    "lower_leg_left": (0.22, 0.72, 0.52, 0.95),
    "foot_left": (0.18, 0.90, 0.60, 1.00),
    "upper_leg_right": (0.46, 0.56, 0.72, 0.78),
    "lower_leg_right": (0.46, 0.72, 0.76, 0.95),
    "foot_right": (0.42, 0.90, 0.86, 1.00),
    "prop": (0.58, 0.28, 1.00, 0.76),
    "accessory_front": (0.42, 0.18, 0.78, 0.66),
    "accessory_back": (0.16, 0.18, 0.52, 0.66),
}

PART_PIVOT_FRACTIONS = {
    "head": (0.5, 0.86),
    "hair_front": (0.5, 0.14),
    "hair_back": (0.5, 0.14),
    "torso": (0.5, 0.10),
    "pelvis": (0.5, 0.10),
    "upper_arm_left": (0.5, 0.10),
    "lower_arm_left": (0.5, 0.10),
    "hand_left": (0.5, 0.18),
    "upper_arm_right": (0.5, 0.10),
    "lower_arm_right": (0.5, 0.10),
    "hand_right": (0.5, 0.18),
    "upper_leg_left": (0.5, 0.08),
    "lower_leg_left": (0.5, 0.08),
    "foot_left": (0.28, 0.35),
    "upper_leg_right": (0.5, 0.08),
    "lower_leg_right": (0.5, 0.08),
    "foot_right": (0.28, 0.35),
    "prop": (0.18, 0.22),
    "accessory_front": (0.5, 0.10),
    "accessory_back": (0.5, 0.10),
}

LEGACY_RIG_LAYOUT_FLAGS = {
    "has_weapon": True,
    "has_cape_back": True,
    "has_front_cloth": True,
    "back_leg_mode": "full",
    "back_arm_mode": "full",
    "helmet_has_hair_layers": True,
}

SIMPLE_RIG_LAYOUT_FLAGS = {
    "has_weapon": True,
    "has_cape_back": True,
    "has_front_cloth": True,
    "back_leg_mode": "none",
    "back_arm_mode": "none",
    "helmet_has_hair_layers": False,
}

DUAL_LEG_RIG_LAYOUT_FLAGS = {
    "has_weapon": True,
    "has_cape_back": True,
    "has_front_cloth": True,
    "back_leg_mode": "single",
    "back_arm_mode": "none",
    "helmet_has_hair_layers": False,
}

SIMPLE_RIG_PARTS = [
    {
        "part_name": "head",
        "part_role": "head",
        "required": True,
        "parent_joint": "head",
        "draw_order": 22,
        "pivot_strategy": {"mode": "fractional", "fraction": [0.5, 0.86]},
        "extraction_region": [0.28, 0.02, 0.72, 0.20],
        "fallback_mode": "empty_fail",
        "overlay_only": False,
        "label": "Head / Helmet",
        "coverage": "The whole head mass, including helmet and neck silhouette. Exclude shoulder, cape, and torso armor.",
    },
    {
        "part_name": "torso_pelvis",
        "part_role": "torso_pelvis",
        "required": True,
        "parent_joint": "torso",
        "draw_order": 16,
        "pivot_strategy": {"mode": "fractional", "fraction": [0.5, 0.14]},
        "extraction_region": [0.26, 0.18, 0.76, 0.62],
        "fallback_mode": "empty_fail",
        "overlay_only": False,
        "label": "Torso / Pelvis",
        "coverage": "Chest, waist, belt, and pelvis as one stable body mass. Exclude the readable front leg, weapon, and cape.",
    },
    {
        "part_name": "front_arm",
        "part_role": "front_arm",
        "required": True,
        "parent_joint": "shoulder_front",
        "draw_order": 28,
        "pivot_strategy": {"mode": "fractional", "fraction": [0.52, 0.10]},
        "extraction_region": {
            "left": [0.12, 0.20, 0.56, 0.62],
            "right": [0.46, 0.20, 0.88, 0.62],
        },
        "fallback_mode": "empty_fail",
        "overlay_only": False,
        "label": "Front Arm",
        "coverage": "Visible-side arm as one piece, including hand if needed. Keep it tight to the readable arm silhouette.",
    },
    {
        "part_name": "front_leg",
        "part_role": "front_leg",
        "required": True,
        "parent_joint": "hip_front",
        "draw_order": 24,
        "pivot_strategy": {"mode": "fractional", "fraction": [0.5, 0.08]},
        "extraction_region": {
            "left": [0.26, 0.56, 0.60, 1.00],
            "right": [0.42, 0.56, 0.86, 1.00],
        },
        "fallback_mode": "empty_fail",
        "overlay_only": False,
        "label": "Front Leg",
        "coverage": "Visible-side leg as one stable piece from thigh through foot. Do not try to split hidden-side limb details.",
    },
    {
        "part_name": "weapon",
        "part_role": "weapon",
        "required": False,
        "parent_joint": "wrist_front",
        "draw_order": 32,
        "pivot_strategy": {"mode": "fractional", "fraction": [0.18, 0.22]},
        "extraction_region": {
            "left": [0.00, 0.24, 0.58, 0.72],
            "right": [0.42, 0.24, 1.00, 0.72],
        },
        "fallback_mode": "allow_missing",
        "overlay_only": False,
        "label": "Weapon",
        "coverage": "Only the clearly visible handheld weapon. Keep it separate from torso, cape, and front cloth.",
    },
    {
        "part_name": "cape_back",
        "part_role": "cape_back",
        "required": False,
        "parent_joint": "torso",
        "draw_order": 6,
        "pivot_strategy": {"mode": "fractional", "fraction": [0.5, 0.10]},
        "extraction_region": {
            "left": [0.46, 0.18, 0.96, 1.00],
            "right": [0.04, 0.18, 0.54, 1.00],
        },
        "fallback_mode": "allow_missing",
        "overlay_only": True,
        "label": "Back Cape",
        "coverage": "Rear-hanging cape or back cloth behind the body. Exclude torso armor and visible limbs.",
    },
    {
        "part_name": "front_cloth",
        "part_role": "front_cloth",
        "required": False,
        "parent_joint": "torso",
        "draw_order": 34,
        "pivot_strategy": {"mode": "fractional", "fraction": [0.5, 0.10]},
        "extraction_region": [0.42, 0.20, 0.78, 0.96],
        "fallback_mode": "allow_missing",
        "overlay_only": True,
        "label": "Front Cloth",
        "coverage": "Front cloth flap, sash, or tabard over the body. Exclude the readable front leg where possible.",
    },
]

DUAL_LEG_RIG_PARTS = [
    copy.deepcopy(SIMPLE_RIG_PARTS[0]),
    copy.deepcopy(SIMPLE_RIG_PARTS[1]),
    copy.deepcopy(SIMPLE_RIG_PARTS[2]),
    copy.deepcopy(SIMPLE_RIG_PARTS[3]),
    {
        "part_name": "back_leg",
        "part_role": "back_leg",
        "required": True,
        "parent_joint": "hip_back",
        "draw_order": 10,
        "pivot_strategy": {"mode": "fractional", "fraction": [0.5, 0.08]},
        "extraction_region": [0.68, 0.67, 0.92, 1.00],
        "fallback_mode": "clone_from:front_leg",
        "overlay_only": False,
        "label": "Back Leg",
        "coverage": "Rear leg mass for locomotion support. Prefer a clean visible rear-leg read; otherwise derive deterministically from the front leg.",
    },
    copy.deepcopy(SIMPLE_RIG_PARTS[4]),
    copy.deepcopy(SIMPLE_RIG_PARTS[5]),
    copy.deepcopy(SIMPLE_RIG_PARTS[6]),
]

RIG_PROFILES: Dict[str, Dict[str, Any]] = {
    LEGACY_RIG_PROFILE: {
        "rig_profile": LEGACY_RIG_PROFILE,
        "joint_schema": {
            "joints": list(RIG_JOINTS),
            "transform_channels": [
                "root_offset",
                "pelvis_rotation",
                "torso_rotation",
                "head_rotation",
                "shoulder_left_rotation",
                "elbow_left_rotation",
                "shoulder_right_rotation",
                "elbow_right_rotation",
                "hip_left_rotation",
                "knee_left_rotation",
                "ankle_left_rotation",
                "hip_right_rotation",
                "knee_right_rotation",
                "ankle_right_rotation",
                "prop_rotation",
            ],
        },
        "flags": dict(LEGACY_RIG_LAYOUT_FLAGS),
        "parts": [
            {
                "part_name": part_name,
                "part_role": part_name,
                "required": True,
                "parent_joint": PART_PARENT_JOINTS[part_name],
                "draw_order": PART_DRAW_ORDERS[part_name],
                "pivot_strategy": {"mode": "fractional", "fraction": list(PART_PIVOT_FRACTIONS.get(part_name, (0.5, 0.5)))},
                "extraction_region": list(PART_REGION_FRACTIONS[part_name]),
                "fallback_mode": "mirror_counterpart" if part_name.endswith("_left") or part_name.endswith("_right") else "empty_fail",
                "overlay_only": part_name in {"hair_front", "hair_back", "accessory_front", "accessory_back"},
                "label": part_name.replace("_", " ").title(),
                "coverage": "Keep the box tight to this isolated body part and avoid neighboring pixels.",
            }
            for part_name in REQUIRED_PARTS
        ],
        "joint_driving_parts": [
            "head",
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
        ],
        "overlay_parts": ["hair_front", "hair_back", "accessory_front", "accessory_back"],
    },
    SIDE_KNIGHT_SIMPLE_7: {
        "rig_profile": SIDE_KNIGHT_SIMPLE_7,
        "joint_schema": {
            "joints": ["root", "torso", "neck", "head", "shoulder_front", "wrist_front", "hip_front", "ankle_front"],
            "transform_channels": [
                "root_offset",
                "torso_rotation",
                "head_rotation",
                "shoulder_front_rotation",
                "hip_front_rotation",
                "weapon_rotation",
                "cape_back_rotation_bias",
                "front_cloth_rotation_bias",
            ],
        },
        "flags": dict(SIMPLE_RIG_LAYOUT_FLAGS),
        "parts": copy.deepcopy(SIMPLE_RIG_PARTS),
        "joint_driving_parts": ["head", "torso_pelvis", "front_arm", "front_leg", "weapon"],
        "overlay_parts": ["cape_back", "front_cloth"],
    },
    SIDE_KNIGHT_DUAL_LEG_8: {
        "rig_profile": SIDE_KNIGHT_DUAL_LEG_8,
        "joint_schema": {
            "joints": ["root", "torso", "neck", "head", "shoulder_front", "wrist_front", "hip_front", "ankle_front", "hip_back", "ankle_back"],
            "transform_channels": [
                "root_offset",
                "torso_rotation",
                "head_rotation",
                "shoulder_front_rotation",
                "hip_front_rotation",
                "hip_back_rotation",
                "weapon_rotation",
                "cape_back_rotation_bias",
                "front_cloth_rotation_bias",
            ],
        },
        "flags": dict(DUAL_LEG_RIG_LAYOUT_FLAGS),
        "parts": copy.deepcopy(DUAL_LEG_RIG_PARTS),
        "joint_driving_parts": ["head", "torso_pelvis", "front_arm", "front_leg", "back_leg", "weapon"],
        "overlay_parts": ["cape_back", "front_cloth"],
    },
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
        "prompts/history",
        "layers",
        "master_pose",
        "part_manifest",
        "part_shapes",
        "part_shapes/masks",
        "part_shapes/previews",
        "part_split",
        "part_split/parts",
        "part_split/masks",
        "parts",
        "parts/masks",
        "parts/recovery",
        "rig",
        "animations/idle",
        "animations/walk",
        "manual_clips",
        "ai_workflow",
        "ai_workflow/character_lock",
        "ai_workflow/key_poses",
        "ai_workflow/motion",
        "ai_workflow/extract",
        "ai_workflow/cleanup",
        "external_authoring",
        "external_authoring/imports",
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


def rgba_to_hex(value: Tuple[int, int, int, int]) -> str:
    return "#%02x%02x%02x" % value[:3]


def delete_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def clear_directory(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        delete_path(child)


def reset_downstream_assets(project_id: str, from_stage: str) -> None:
    project_dir = PROJECTS_ROOT / project_id
    if from_stage == "concept":
        clear_directory(project_dir / "master_pose")
        delete_path(canonical_downstream_path(project_dir, "rig_layout"))
        delete_path(canonical_downstream_path(project_dir, "rig_layout_history"))
    if from_stage in {"concept", "master_pose", "rig_layout"}:
        delete_path(canonical_downstream_path(project_dir, "part_manifest"))
        delete_path(canonical_downstream_path(project_dir, "part_manifest_history"))
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest"}:
        delete_path(canonical_downstream_path(project_dir, "part_shapes"))
        delete_path(canonical_downstream_path(project_dir, "part_shapes_history"))
        clear_directory(project_dir / "part_shapes")
        (project_dir / "part_shapes" / "masks").mkdir(parents=True, exist_ok=True)
        (project_dir / "part_shapes" / "previews").mkdir(parents=True, exist_ok=True)
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes"}:
        delete_path(canonical_downstream_path(project_dir, "part_split"))
        delete_path(canonical_downstream_path(project_dir, "part_split_history"))
        clear_directory(project_dir / "part_split")
        (project_dir / "part_split" / "parts").mkdir(parents=True, exist_ok=True)
        (project_dir / "part_split" / "masks").mkdir(parents=True, exist_ok=True)
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes", "part_split"}:
        delete_path(canonical_downstream_path(project_dir, "sprite_model"))
        delete_path(canonical_downstream_path(project_dir, "sprite_model_history"))
        delete_path(legacy_downstream_path(project_dir, "palette"))
        clear_directory(project_dir / "parts")
        clear_directory(sprite_model_revisions_path(project_dir))
        (project_dir / "parts" / "masks").mkdir(parents=True, exist_ok=True)
        (project_dir / "parts" / "recovery").mkdir(parents=True, exist_ok=True)
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes", "part_split", "sprite_model"}:
        clear_directory(project_dir / "rig")
        delete_path(canonical_downstream_path(project_dir, "rig"))
        delete_path(canonical_downstream_path(project_dir, "animation_clips"))
        delete_path(legacy_downstream_path(project_dir, "animation_templates"))
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes", "part_split", "sprite_model", "rig", "clips"}:
        clear_directory(project_dir / "animations" / "idle")
        clear_directory(project_dir / "animations" / "walk")
        (project_dir / "animations" / "idle").mkdir(parents=True, exist_ok=True)
        (project_dir / "animations" / "walk").mkdir(parents=True, exist_ok=True)
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes", "part_split", "sprite_model", "rig"}:
        clear_directory(manual_clip_render_root(project_dir))
        manual_clip_render_root(project_dir).mkdir(parents=True, exist_ok=True)
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes", "part_split", "sprite_model", "rig", "clips", "qa"}:
        delete_path(canonical_downstream_path(project_dir, "qa_report"))
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes", "part_split", "sprite_model", "rig", "clips", "qa", "export"}:
        clear_directory(project_dir / "exports")


def clear_project_downstream_state(project: Dict[str, Any], from_stage: str) -> Dict[str, Any]:
    if from_stage == "concept":
        project["master_pose_manifest"] = {"candidates": []}
        project["master_pose_approved"] = False
        project["rig_layout"] = None
        project["rig_layout_history"] = default_rig_layout_history(project["project_id"])
        project["rig_layout_approved"] = False
    if from_stage in {"concept", "master_pose", "rig_layout"}:
        project["part_manifest"] = None
        project["part_manifest_history"] = default_part_manifest_history(project["project_id"])
        project["part_manifest_approved"] = False
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest"}:
        project["part_shapes"] = None
        project["part_shapes_history"] = default_part_shapes_history(project["project_id"])
        project["part_shapes_approved"] = False
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes"}:
        project["part_split"] = None
        project["part_split_history"] = default_part_split_history(project["project_id"])
        project["part_split_approved"] = False
        project["split_review_approved"] = False
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes", "part_split"}:
        project["sprite_model"] = None
        project["palette"] = None
        project["sprite_model_history"] = default_sprite_model_history(project["project_id"])
        project["sprite_model_approved"] = False
        project["layer_review_approved"] = False
        project["layered_character"] = None
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes", "part_split", "sprite_model"}:
        project["rig"] = None
        project["animation_clips"] = None
        project["animation_templates"] = None
        project["rig_review_approved"] = False
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes", "part_split", "sprite_model", "rig", "clips"}:
        project["qa_report"] = None
    if from_stage in {"concept", "master_pose", "rig_layout", "part_manifest", "part_shapes", "part_split", "sprite_model", "rig", "clips", "qa", "export"}:
        project["last_export"] = None
    return project


def list_to_tuple(values: List[int]) -> Tuple[int, int]:
    return int(values[0]), int(values[1])


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


def clamp_int(value: float, minimum: int, maximum: int) -> int:
    return int(max(minimum, min(maximum, round(value))))


def normalize_mask(mask: Image.Image, threshold: int = 16) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value > threshold else 0)


def dilate_mask(mask: Image.Image, radius: int = 1) -> Image.Image:
    source = normalize_mask(mask)
    expanded = Image.new("L", source.size, 0)
    width, height = source.size
    src = source.load()
    dst = expanded.load()
    for y in range(height):
        for x in range(width):
            if src[x, y] <= 0:
                continue
            for oy in range(-radius, radius + 1):
                for ox in range(-radius, radius + 1):
                    nx = x + ox
                    ny = y + oy
                    if 0 <= nx < width and 0 <= ny < height:
                        dst[nx, ny] = 255
    return expanded


def erode_mask(mask: Image.Image, radius: int = 1) -> Image.Image:
    source = normalize_mask(mask)
    eroded = Image.new("L", source.size, 0)
    width, height = source.size
    src = source.load()
    dst = eroded.load()
    for y in range(height):
        for x in range(width):
            keep = True
            for oy in range(-radius, radius + 1):
                for ox in range(-radius, radius + 1):
                    nx = x + ox
                    ny = y + oy
                    if nx < 0 or ny < 0 or nx >= width or ny >= height or src[nx, ny] <= 0:
                        keep = False
                        break
                if not keep:
                    break
            if keep:
                dst[x, y] = 255
    return eroded


def largest_component_mask(mask: Image.Image, min_area_ratio: float = 0.035) -> Image.Image:
    source = normalize_mask(mask)
    width, height = source.size
    pixels = source.load()
    visited = set()
    components: List[List[Tuple[int, int]]] = []
    for y in range(height):
        for x in range(width):
            if pixels[x, y] <= 0 or (x, y) in visited:
                continue
            queue = [(x, y)]
            visited.add((x, y))
            component: List[Tuple[int, int]] = []
            while queue:
                cx, cy = queue.pop()
                component.append((cx, cy))
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx = cx + dx
                    ny = cy + dy
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if pixels[nx, ny] <= 0 or (nx, ny) in visited:
                        continue
                    visited.add((nx, ny))
                    queue.append((nx, ny))
            components.append(component)
    if not components:
        return source
    largest = max(components, key=len)
    minimum_area = max(24, int(len(largest) * min_area_ratio))
    filtered = Image.new("L", source.size, 0)
    dst = filtered.load()
    for component in components:
        if len(component) < minimum_area:
            continue
        for x, y in component:
            dst[x, y] = 255
    if filtered.getbbox() is None:
        for x, y in largest:
            dst[x, y] = 255
    return filtered


def strip_light_edge_matte(image: Image.Image, mask: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = normalize_mask(mask)
    interior = erode_mask(alpha, 1)
    inner_pixels = interior.load()
    alpha_pixels = alpha.load()
    rgba_pixels = rgba.load()
    width, height = rgba.size
    cleaned = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    cleaned_pixels = cleaned.load()
    for y in range(height):
        for x in range(width):
            if alpha_pixels[x, y] <= 0:
                continue
            r, g, b, a = rgba_pixels[x, y]
            if inner_pixels[x, y] <= 0 and a > 0:
                neighbor_samples = []
                for oy in (-1, 0, 1):
                    for ox in (-1, 0, 1):
                        if ox == 0 and oy == 0:
                            continue
                        nx = x + ox
                        ny = y + oy
                        if nx < 0 or ny < 0 or nx >= width or ny >= height:
                            continue
                        if inner_pixels[nx, ny] <= 0:
                            continue
                        neighbor_samples.append(rgba_pixels[nx, ny][:3])
                luminance = (r + g + b) / 3.0
                neutral_range = max(r, g, b) - min(r, g, b)
                neighbor_luminance = None
                if neighbor_samples:
                    neighbor_luminance = sum((sample[0] + sample[1] + sample[2]) / 3.0 for sample in neighbor_samples) / float(len(neighbor_samples))
                if min(r, g, b) >= 208 and neutral_range <= 42:
                    cleaned_pixels[x, y] = (r, g, b, 0)
                    continue
                if neighbor_luminance is not None and neutral_range <= 48 and luminance >= neighbor_luminance + 34:
                    cleaned_pixels[x, y] = (r, g, b, 0)
                    continue
                if min(r, g, b) >= 232:
                    cleaned_pixels[x, y] = (r, g, b, 0)
                    continue
            cleaned_pixels[x, y] = (r, g, b, 255)
    return cleaned


def alpha_bbox(image: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    return image.getchannel("A").getbbox()


def crop_to_alpha(image: Image.Image, mask: Optional[Image.Image] = None) -> Tuple[Image.Image, Image.Image, Tuple[int, int, int, int]]:
    image = image.convert("RGBA")
    alpha = image.getchannel("A") if mask is None else normalize_mask(mask)
    bbox = alpha.getbbox()
    if bbox is None:
        empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        return empty, Image.new("L", (1, 1), 0), (0, 0, 1, 1)
    cropped_image = image.crop(bbox)
    cropped_mask = alpha.crop(bbox)
    return cropped_image, cropped_mask, bbox


def image_with_mask(image: Image.Image, mask: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    result = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    result.alpha_composite(rgba)
    result.putalpha(normalize_mask(mask))
    return result


def fit_source_point(
    point: Tuple[float, float],
    source_bbox: Tuple[int, int, int, int],
    canvas_size: Tuple[int, int],
    bottom_margin: int = 54,
    side_margin: int = 56,
) -> Tuple[float, float]:
    width = max(1, source_bbox[2] - source_bbox[0])
    height = max(1, source_bbox[3] - source_bbox[1])
    scale = min((canvas_size[0] - side_margin * 2) / float(width), (canvas_size[1] - bottom_margin - 40) / float(height))
    offset_x = (canvas_size[0] / 2.0) - ((source_bbox[0] + width / 2.0) * scale)
    offset_y = (canvas_size[1] - bottom_margin) - (source_bbox[3] * scale)
    return point[0] * scale + offset_x, point[1] * scale + offset_y


def call_progress(progress: Optional[ProgressCallback], percent: int, label: Optional[str], detail: Optional[str] = None) -> None:
    if progress is None:
        return
    progress(percent, label, detail)


def rig_layout_history_path(project_dir: Path) -> Path:
    return canonical_downstream_path(project_dir, "rig_layout_history")


def default_rig_layout_history(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "current_revision_id": None,
        "events": [],
        "revisions": [],
    }


def part_manifest_history_path(project_dir: Path) -> Path:
    return canonical_downstream_path(project_dir, "part_manifest_history")


def default_part_manifest_history(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "current_revision_id": None,
        "events": [],
        "revisions": [],
    }


def part_shapes_history_path(project_dir: Path) -> Path:
    return canonical_downstream_path(project_dir, "part_shapes_history")


def default_part_shapes_history(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "current_revision_id": None,
        "events": [],
        "revisions": [],
    }


def part_split_history_path(project_dir: Path) -> Path:
    return canonical_downstream_path(project_dir, "part_split_history")


def default_part_split_history(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "current_revision_id": None,
        "events": [],
        "revisions": [],
    }


def part_split_parts_dir(project_dir: Path) -> Path:
    return project_dir / "part_split" / "parts"


def part_split_masks_dir(project_dir: Path) -> Path:
    return project_dir / "part_split" / "masks"


def write_part_split_asset(project_dir: Path, part_name: str, image: Image.Image, mask: Image.Image) -> Tuple[str, str]:
    safe = sanitize_filename(part_name, "part")
    image_path = part_split_parts_dir(project_dir) / f"{safe}.png"
    mask_path = part_split_masks_dir(project_dir) / f"{safe}.png"
    image.convert("RGBA").save(image_path)
    normalize_mask(mask).save(mask_path)
    return str(image_path.relative_to(project_dir)), str(mask_path.relative_to(project_dir))


def load_part_split_asset(project_dir: Path, part: Dict[str, Any]) -> Tuple[Image.Image, Image.Image]:
    image = Image.open(project_dir / str(part.get("image_path") or "")).convert("RGBA")
    mask = normalize_mask(Image.open(project_dir / str(part.get("mask_path") or "")).convert("L"))
    return image, mask


def part_shapes_masks_dir(project_dir: Path) -> Path:
    return project_dir / "part_shapes" / "masks"


def part_shapes_previews_dir(project_dir: Path) -> Path:
    return project_dir / "part_shapes" / "previews"


def create_part_manifest_revision(project_dir: Path, part_manifest: Dict[str, Any], reason: str, operation: Optional[str] = None) -> Dict[str, Any]:
    history = load_json(part_manifest_history_path(project_dir), default_part_manifest_history(project_dir.name))
    revision = {
        "revision_id": "rev-%s" % uuid.uuid4().hex[:10],
        "created_at": now_iso(),
        "reason": reason,
        "operation": operation,
        "part_manifest_hash": hashlib.sha256(json.dumps(part_manifest, sort_keys=True).encode("utf-8")).hexdigest(),
    }
    history.setdefault("revisions", []).append(revision)
    history["current_revision_id"] = revision["revision_id"]
    history.setdefault("events", []).append({
        "type": "part_manifest_%s" % reason,
        "operation": operation,
        "created_at": revision["created_at"],
    })
    write_json(part_manifest_history_path(project_dir), history)
    return history


def create_part_shapes_revision(project_dir: Path, part_shapes: Dict[str, Any], reason: str, operation: Optional[str] = None) -> Dict[str, Any]:
    history = load_json(part_shapes_history_path(project_dir), default_part_shapes_history(project_dir.name))
    revision = {
        "revision_id": "rev-%s" % uuid.uuid4().hex[:10],
        "created_at": now_iso(),
        "reason": reason,
        "operation": operation,
        "part_shapes_hash": hashlib.sha256(json.dumps(part_shapes, sort_keys=True).encode("utf-8")).hexdigest(),
    }
    history.setdefault("revisions", []).append(revision)
    history["current_revision_id"] = revision["revision_id"]
    history.setdefault("events", []).append({
        "type": "part_shapes_%s" % reason,
        "operation": operation,
        "created_at": revision["created_at"],
    })
    write_json(part_shapes_history_path(project_dir), history)
    return history


def create_part_split_revision(project_dir: Path, part_split: Dict[str, Any], reason: str, operation: Optional[str] = None) -> Dict[str, Any]:
    history = load_json(part_split_history_path(project_dir), default_part_split_history(project_dir.name))
    revision = {
        "revision_id": "rev-%s" % uuid.uuid4().hex[:10],
        "created_at": now_iso(),
        "reason": reason,
        "operation": operation,
        "part_split_hash": hashlib.sha256(json.dumps(part_split, sort_keys=True).encode("utf-8")).hexdigest(),
    }
    history.setdefault("revisions", []).append(revision)
    history["current_revision_id"] = revision["revision_id"]
    history.setdefault("events", []).append({
        "type": "part_split_%s" % reason,
        "operation": operation,
        "created_at": revision["created_at"],
    })
    write_json(part_split_history_path(project_dir), history)
    return history


def normalize_fraction_region(value: Any) -> Any:
    if isinstance(value, dict):
        normalized = {}
        for key, region in value.items():
            if isinstance(region, (list, tuple)) and len(region) == 4:
                normalized[str(key)] = [float(item) for item in region]
        return normalized
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [float(item) for item in value]
    return None


def active_rig_profile_name(project: Dict[str, Any], rig_layout: Optional[Dict[str, Any]] = None) -> str:
    if isinstance(rig_layout, dict) and rig_layout.get("rig_profile") in RIG_PROFILES:
        return str(rig_layout["rig_profile"])
    character_spec = project.get("character_spec") if isinstance(project, dict) else None
    if isinstance(character_spec, dict) and character_spec.get("rig_profile") in RIG_PROFILES:
        return str(character_spec["rig_profile"])
    return LEGACY_RIG_PROFILE


def profile_definition(profile_name: Optional[str]) -> Dict[str, Any]:
    return copy.deepcopy(RIG_PROFILES.get(profile_name or "", RIG_PROFILES[LEGACY_RIG_PROFILE]))


def brief_text_blob(project: Dict[str, Any], concept: Optional[Dict[str, Any]] = None) -> str:
    brief = project.get("brief") or {}
    fields = [
        project.get("prompt_text", ""),
        brief.get("role", ""),
        brief.get("silhouette", ""),
        brief.get("outfit_materials", ""),
        brief.get("prop", ""),
        brief.get("palette_mood", ""),
        brief.get("shape_language", ""),
        brief.get("mood_tone", ""),
        concept.get("positive_prompt", "") if isinstance(concept, dict) else "",
        concept.get("validation_feedback", "") if isinstance(concept, dict) else "",
        concept.get("outfit", "") if isinstance(concept, dict) else "",
        concept.get("prop_variant", "") if isinstance(concept, dict) else "",
    ]
    return " ".join(str(item or "") for item in fields).lower()


def select_rig_profile(project: Dict[str, Any], concept: Dict[str, Any]) -> str:
    blob = brief_text_blob(project, concept)
    side_view = "side" in blob and "view" in blob
    armored = any(token in blob for token in ("armor", "armour", "knight", "helmet", "chainmail", "plate"))
    has_sword = any(token in blob for token in ("sword", "blade", "arming sword", "weapon"))
    has_cloth = any(token in blob for token in ("cape", "tabard", "cloth", "sash", "traveler"))
    humanoid = not any(token in blob for token in ("beast", "quadruped", "wolf", "dog", "mount"))
    if side_view and armored and has_sword and has_cloth and humanoid:
        return SIDE_KNIGHT_SIMPLE_7
    return LEGACY_RIG_PROFILE


def resolve_layout_parent_joint(part_name: str, profile_name: str, source_facing: str) -> str:
    if profile_name == LEGACY_RIG_PROFILE and part_name == "prop":
        return "wrist_left" if source_facing == "left" else "wrist_right"
    return {
        "front_arm": "shoulder_front",
        "front_leg": "hip_front",
        "back_leg": "hip_back",
        "weapon": "wrist_front",
    }.get(part_name, "")


def resolve_layout_region(part_definition: Dict[str, Any], source_facing: str) -> Optional[List[float]]:
    region = normalize_fraction_region(part_definition.get("extraction_region"))
    if isinstance(region, dict):
        return region.get(source_facing) or region.get("right") or region.get("left")
    return region


def canonical_sprite_part_role(part: Dict[str, Any], rig_profile: Optional[str]) -> str:
    part_name = str(part.get("part_name") or "")
    part_role = str(part.get("part_role") or part_name)
    if rig_profile in {SIDE_KNIGHT_SIMPLE_7, SIDE_KNIGHT_DUAL_LEG_8}:
        return part_name or part_role
    return part_role or part_name


def validate_rig_layout(layout: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(layout, dict):
        raise ValueError("Invalid rig layout payload.")
    profile_name = str(layout.get("rig_profile") or "")
    if profile_name not in RIG_PROFILES:
        raise ValueError("Unknown rig profile.")
    profile = RIG_PROFILES[profile_name]
    joint_names = set(profile["joint_schema"]["joints"])
    profile_parts = {item["part_name"]: item for item in profile["parts"]}
    seen: Set[str] = set()
    errors: List[str] = []
    parts = layout.get("parts") or []
    if not isinstance(parts, list) or not parts:
        errors.append("layout must include one or more parts")
    for entry in parts:
        if not isinstance(entry, dict):
            errors.append("each layout part must be an object")
            continue
        name = str(entry.get("part_name") or "")
        if not name or name not in profile_parts:
            errors.append("unknown part role: %s" % (name or "missing"))
            continue
        if name in seen:
            errors.append("duplicate part name: %s" % name)
        seen.add(name)
        if str(entry.get("parent_joint") or "") not in joint_names:
            errors.append("unknown parent joint for %s" % name)
        region = resolve_layout_region(entry, "right")
        if not region or len(region) != 4:
            errors.append("invalid extraction region for %s" % name)
        if not isinstance(entry.get("draw_order"), int):
            errors.append("invalid draw order for %s" % name)
        if bool(entry.get("overlay_only")) and name in set(layout.get("joint_driving_parts") or []):
            errors.append("overlay part cannot be joint-driving: %s" % name)
    status = "pass" if not errors else "fail"
    return {"status": status, "errors": errors}


def build_default_part_manifest(project: Dict[str, Any], rig_layout: Dict[str, Any], concept: Dict[str, Any]) -> Dict[str, Any]:
    parts: List[Dict[str, Any]] = []
    for entry in list(rig_layout.get("parts") or []):
        if not isinstance(entry, dict):
            continue
        part_name = str(entry.get("part_name") or "").strip()
        if not part_name:
            continue
        parts.append({
            "part_name": part_name,
            "part_label": humanize_identifier(part_name),
            "part_role": canonical_sprite_part_role(entry, rig_layout.get("rig_profile")),
            "required": bool(entry.get("required", True)),
            "overlay_only": bool(entry.get("overlay_only")),
            "parent_joint": str(entry.get("parent_joint") or ""),
            "draw_order": int(entry.get("draw_order", 0)),
            "source": "rig_profile",
            "editable": True,
            "notes": "",
        })
    manifest = {
        "project_id": project["project_id"],
        "approved_concept_id": concept.get("concept_id"),
        "rig_profile": rig_layout.get("rig_profile"),
        "source_rig_layout_revision": (project.get("rig_layout_history") or {}).get("current_revision_id"),
        "parts": sorted(parts, key=lambda item: (int(item.get("draw_order", 0)), item["part_name"])),
        "approved": False,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    manifest["validation"] = validate_part_manifest(manifest)
    return manifest


def validate_part_manifest(part_manifest: Dict[str, Any]) -> Dict[str, Any]:
    parts = part_manifest.get("parts") or []
    failures: List[str] = []
    warnings: List[str] = []
    seen: Set[str] = set()
    required_count = 0
    overlay_count = 0
    for entry in parts:
        if not isinstance(entry, dict):
            failures.append("each manifest part must be an object")
            continue
        name = str(entry.get("part_name") or "").strip()
        if not name:
            failures.append("manifest part is missing part_name")
            continue
        if name in seen:
            failures.append("duplicate part name: %s" % name)
        seen.add(name)
        if bool(entry.get("required")):
            required_count += 1
        if bool(entry.get("overlay_only")):
            overlay_count += 1
        if not str(entry.get("parent_joint") or "").strip():
            warnings.append("%s: missing parent_joint" % name)
        if not isinstance(entry.get("draw_order"), int):
            failures.append("%s: draw_order must be an integer" % name)
        if not str(entry.get("part_label") or "").strip():
            warnings.append("%s: missing part_label" % name)
    if not parts:
        failures.append("manifest must contain at least one part")
    if required_count == 0:
        failures.append("manifest must contain at least one required part")
    if len(parts) >= 10:
        warnings.append("part list may be over-split for the current concept")
    status = "pass"
    if failures:
        status = "fail"
    elif warnings:
        status = "warning"
    return {
        "status": status,
        "failures": failures,
        "warnings": warnings,
        "required_count": required_count,
        "optional_count": max(0, len(parts) - required_count),
        "overlay_count": overlay_count,
    }


def humanize_identifier(value: str) -> str:
    return str(value or "").replace("_", " ").strip().title()


def polygon_bbox(vertices: List[List[float]]) -> List[int]:
    if not vertices:
        return [0, 0, 1, 1]
    xs = [float(point[0]) for point in vertices]
    ys = [float(point[1]) for point in vertices]
    return [
        int(math.floor(min(xs))),
        int(math.floor(min(ys))),
        int(math.ceil(max(xs))),
        int(math.ceil(max(ys))),
    ]


def clamp_point_to_image(point: Tuple[float, float], size: Tuple[int, int]) -> List[int]:
    return [
        int(max(0, min(size[0] - 1, round(point[0])))),
        int(max(0, min(size[1] - 1, round(point[1])))),
    ]


def contour_polygon_from_mask(mask: Image.Image, target_points: int = 10) -> List[List[int]]:
    normalized = normalize_mask(mask)
    bbox = normalized.getbbox()
    if bbox is None:
        return []
    x0, y0, x1, y1 = bbox
    if x1 - x0 <= 1 or y1 - y0 <= 1:
        return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    slices = max(3, target_points // 2)
    left_points: List[List[int]] = []
    right_points: List[List[int]] = []
    pixels = normalized.load()
    for index in range(slices + 1):
        sample_y = min(y1 - 1, max(y0, y0 + int(round((index / float(slices)) * max(0, (y1 - y0 - 1))))))
        xs = [x for x in range(x0, x1) if pixels[x, sample_y] > 0]
        if not xs:
            continue
        left_points.append([min(xs), sample_y])
        right_points.append([max(xs), sample_y])
    points = left_points + list(reversed(right_points))
    deduped: List[List[int]] = []
    for point in points:
        if not deduped or deduped[-1] != point:
            deduped.append(point)
    return deduped if len(deduped) >= 3 else [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def render_polygon_mask(size: Tuple[int, int], vertices: List[List[float]], closed: bool = True) -> Image.Image:
    mask = Image.new("L", size, 0)
    if len(vertices) < 3:
        return mask
    draw = ImageDraw.Draw(mask)
    points = [(int(round(point[0])), int(round(point[1]))) for point in vertices]
    if closed:
        draw.polygon(points, fill=255)
    else:
        draw.line(points, fill=255, width=1)
    return normalize_mask(mask)


def extraction_box_from_manifest_entry(source_size: Tuple[int, int], subject_bbox: Tuple[int, int, int, int], rig_layout: Dict[str, Any], part_name: str, facing: str) -> Tuple[int, int, int, int]:
    layout_entry = next((item for item in (rig_layout.get("parts") or []) if item.get("part_name") == part_name), None) or {}
    extraction_region = resolve_layout_region(layout_entry, facing) or layout_entry.get("extraction_region")
    if extraction_region:
        return region_box(subject_bbox, extraction_region)
    return subject_bbox


def write_part_shape_assets(project_dir: Path, part_name: str, source_image: Image.Image, mask: Image.Image) -> Tuple[Optional[str], Optional[str], List[int]]:
    safe = sanitize_filename(part_name, "part")
    mask_path = part_shapes_masks_dir(project_dir) / f"{safe}.png"
    preview_path = part_shapes_previews_dir(project_dir) / f"{safe}.png"
    normalize_mask(mask).save(mask_path)
    bbox = list(normalize_mask(mask).getbbox() or (0, 0, 1, 1))
    if bbox_area(bbox) > 0 and mask_pixel_area(mask) > 0:
        preview = image_with_mask(source_image, mask).crop(tuple(bbox))
        preview.save(preview_path)
        preview_rel = str(preview_path.relative_to(project_dir))
    else:
        preview_rel = None
        if preview_path.exists():
            delete_path(preview_path)
    return str(mask_path.relative_to(project_dir)), preview_rel, bbox


def build_default_part_shapes(project: Dict[str, Any], part_manifest: Dict[str, Any], source_image: Image.Image, source_rel: str, operation_source: str = "auto_init") -> Dict[str, Any]:
    source_mask = normalize_mask(detect_mask(source_image))
    subject_bbox = source_mask.getbbox()
    if subject_bbox is None:
        raise ValueError("Could not detect a character silhouette in the approved source image.")
    project_dir = PROJECTS_ROOT / project["project_id"]
    rig_layout = project.get("rig_layout") or {}
    facing = estimate_facing_direction(source_mask)
    parts: List[Dict[str, Any]] = []
    for manifest_entry in list(part_manifest.get("parts") or []):
        part_name = str(manifest_entry.get("part_name") or "").strip()
        if not part_name:
            continue
        extraction_box = extraction_box_from_manifest_entry(source_image.size, subject_bbox, rig_layout, part_name, facing)
        regional_mask = Image.new("L", source_image.size, 0)
        regional_mask.paste(source_mask.crop(extraction_box), extraction_box[:2])
        polygon = contour_polygon_from_mask(regional_mask)
        if len(polygon) < 3:
            x0, y0, x1, y1 = extraction_box
            polygon = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        polygon = [clamp_point_to_image((point[0], point[1]), source_image.size) for point in polygon]
        mask = render_polygon_mask(source_image.size, polygon, closed=True)
        mask_path, preview_path, bbox = write_part_shape_assets(project_dir, part_name, source_image, mask)
        parts.append({
            "part_name": part_name,
            "part_label": manifest_entry.get("part_label") or humanize_identifier(part_name),
            "shape_type": "polygon",
            "vertices": polygon,
            "closed": True,
            "bbox": bbox,
            "mask_path": mask_path,
            "preview_path": preview_path,
            "source_method": operation_source,
            "status": "candidate",
            "locked": False,
            "visible": True,
            "color": stable_part_shape_color(project["project_id"], part_name),
            "notes": "",
        })
    part_shapes = {
        "project_id": project["project_id"],
        "approved_concept_id": part_manifest.get("approved_concept_id"),
        "source_image": source_rel,
        "manifest_revision_id": (project.get("part_manifest_history") or {}).get("current_revision_id"),
        "parts": parts,
        "approved": False,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    part_shapes["validation"] = validate_part_shapes(project_dir, part_shapes, part_manifest)
    return part_shapes


def stable_part_shape_color(project_id: str, part_name: str) -> str:
    return "#%06x" % (stable_int(project_id, part_name, mod=0xFFFFFF) or 0x66CCFF)


def preserve_part_shapes_for_manifest(
    project: Dict[str, Any],
    part_manifest: Dict[str, Any],
    existing_part_shapes: Optional[Dict[str, Any]],
    rename_map: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(existing_part_shapes, dict) or not existing_part_shapes.get("parts"):
        return None
    project_dir = PROJECTS_ROOT / project["project_id"]
    approved_path, approved_rel = resolve_sprite_source_image(project, project_dir)
    source_image = Image.open(approved_path).convert("RGBA")
    rename_lookup = dict(rename_map or {})
    existing_lookup: Dict[str, Dict[str, Any]] = {}
    for entry in list(existing_part_shapes.get("parts") or []):
        if not isinstance(entry, dict):
            continue
        original_name = str(entry.get("part_name") or "").strip()
        if not original_name:
            continue
        current_name = rename_lookup.get(original_name, original_name)
        existing_lookup[current_name] = copy.deepcopy(entry)
    missing_manifest = {
        "parts": [
            copy.deepcopy(item)
            for item in (part_manifest.get("parts") or [])
            if str(item.get("part_name") or "").strip() not in existing_lookup
        ]
    }
    default_shapes = build_default_part_shapes(project, missing_manifest, source_image, approved_rel, operation_source="auto_init") if missing_manifest["parts"] else {"parts": []}
    default_lookup = {
        str(entry.get("part_name") or ""): copy.deepcopy(entry)
        for entry in (default_shapes.get("parts") or [])
        if isinstance(entry, dict) and entry.get("part_name")
    }
    parts: List[Dict[str, Any]] = []
    for manifest_entry in list(part_manifest.get("parts") or []):
        part_name = str(manifest_entry.get("part_name") or "").strip()
        if not part_name:
            continue
        if part_name in existing_lookup:
            part_shape = existing_lookup[part_name]
            part_shape["part_name"] = part_name
            part_shape["part_label"] = manifest_entry.get("part_label") or part_shape.get("part_label") or humanize_identifier(part_name)
            part_shape.setdefault("shape_type", "polygon")
            part_shape.setdefault("closed", True)
            part_shape.setdefault("source_method", "manual_edit")
            part_shape.setdefault("status", "candidate")
            part_shape.setdefault("locked", False)
            part_shape.setdefault("visible", True)
            part_shape.setdefault("notes", "")
            part_shape["color"] = str(part_shape.get("color") or stable_part_shape_color(project["project_id"], part_name))
            parts.append(part_shape)
            continue
        fallback = default_lookup.get(part_name)
        if fallback:
            parts.append(fallback)
    part_shapes = {
        "project_id": project["project_id"],
        "approved_concept_id": part_manifest.get("approved_concept_id"),
        "source_image": approved_rel,
        "manifest_revision_id": None,
        "parts": parts,
        "approved": False,
        "created_at": existing_part_shapes.get("created_at") or now_iso(),
        "updated_at": now_iso(),
    }
    part_shapes["validation"] = validate_part_shapes(project_dir, part_shapes, part_manifest)
    return part_shapes


def validate_part_shapes(project_dir: Path, part_shapes: Dict[str, Any], part_manifest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    manifest = part_manifest or {}
    manifest_parts = {item["part_name"]: item for item in (manifest.get("parts") or []) if isinstance(item, dict) and item.get("part_name")}
    failures: List[str] = []
    warnings: List[str] = []
    seen: Set[str] = set()
    per_part: List[Dict[str, Any]] = []
    for entry in list(part_shapes.get("parts") or []):
        if not isinstance(entry, dict):
            failures.append("each part shape must be an object")
            continue
        name = str(entry.get("part_name") or "").strip()
        vertices = entry.get("vertices") or []
        if not name:
            failures.append("shape entry is missing part_name")
            continue
        if name in seen:
            failures.append("duplicate part shape: %s" % name)
        seen.add(name)
        entry_failures: List[str] = []
        entry_warnings: List[str] = []
        if len(vertices) < 3:
            entry_failures.append("polygon needs at least 3 vertices")
        bbox = entry.get("bbox") or polygon_bbox(vertices)
        if bbox_area(bbox) <= 0:
            entry_failures.append("shape bbox is empty")
        mask_rel = str(entry.get("mask_path") or "")
        mask_area = 0
        if mask_rel and (project_dir / mask_rel).exists():
            mask_area = mask_pixel_area(Image.open(project_dir / mask_rel).convert("L"))
            if mask_area < SPRITE_MODEL_FAIL_MIN_MASK_AREA and manifest_parts.get(name, {}).get("required"):
                entry_failures.append("required part mask is empty")
            elif mask_area < SPRITE_MODEL_WARN_MIN_MASK_AREA:
                entry_warnings.append("mask area is very small")
        elif manifest_parts.get(name, {}).get("required"):
            entry_failures.append("mask asset is missing")
        if name not in manifest_parts:
            entry_warnings.append("shape does not exist in the approved manifest")
        status = "pass"
        if entry_failures:
            status = "fail"
        elif entry_warnings:
            status = "warning"
        per_part.append({
            "part_name": name,
            "status": status,
            "bbox": [int(value) for value in bbox],
            "mask_area": mask_area,
            "warnings": entry_warnings,
            "failures": entry_failures,
        })
        warnings.extend("%s: %s" % (name, item) for item in entry_warnings)
        failures.extend("%s: %s" % (name, item) for item in entry_failures)
    missing_required = sorted(name for name, entry in manifest_parts.items() if entry.get("required") and name not in seen)
    for name in missing_required:
        failures.append("missing required shape: %s" % name)
    status = "pass"
    if failures:
        status = "fail"
    elif warnings:
        status = "warning"
    return {
        "generated_at": now_iso(),
        "status": status,
        "warnings": warnings,
        "failures": failures,
        "missing_required_parts": missing_required,
        "per_part": per_part,
    }


def render_part_split_reconstruction(project_dir: Path, source_size: Tuple[int, int], parts: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    canvas = Image.new("RGBA", source_size, (0, 0, 0, 0))
    for part in sorted(parts, key=lambda item: int(item.get("draw_order", 0))):
        image_path = part.get("image_path")
        if not image_path:
            continue
        image = Image.open(project_dir / str(image_path)).convert("RGBA")
        bbox = part.get("bbox") or [0, 0, image.size[0], image.size[1]]
        canvas.alpha_composite(image, (int(bbox[0]), int(bbox[1])))
    preview_path = project_dir / "part_split" / "reconstruction_preview.png"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(preview_path)
    mask = normalize_mask(canvas.getchannel("A"))
    return str(preview_path.relative_to(project_dir)), {
        "bbox": list(mask.getbbox() or (0, 0, 1, 1)),
        "mask_area": mask_pixel_area(mask),
    }


def validate_part_split(project_dir: Path, part_split: Dict[str, Any], source_mask: Optional[Image.Image] = None) -> Dict[str, Any]:
    manifest = part_split.get("part_manifest") or {}
    rig_layout = part_split.get("rig_layout") or {}
    expected_source = manifest.get("parts") or rig_layout.get("parts") or []
    expected_parts = {item["part_name"]: item for item in expected_source if isinstance(item, dict) and item.get("part_name")}
    parts = part_split.get("parts") or []
    seen: Set[str] = set()
    warnings: List[str] = []
    failures: List[str] = []
    per_part: List[Dict[str, Any]] = []
    overlap_masks: List[Tuple[str, Image.Image]] = []
    if isinstance(source_mask, Image.Image):
        overlap_canvas_size = source_mask.size
    else:
        max_x = 1
        max_y = 1
        for entry in parts:
            if not isinstance(entry, dict):
                continue
            bbox = entry.get("bbox") or [0, 0, 1, 1]
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                max_x = max(max_x, int(bbox[2]))
                max_y = max(max_y, int(bbox[3]))
        overlap_canvas_size = (max_x, max_y)
    for entry in parts:
        if not isinstance(entry, dict):
            failures.append("each split part must be an object")
            continue
        name = str(entry.get("part_name") or "")
        if not name:
            failures.append("split part is missing part_name")
            continue
        if name in seen:
            failures.append("duplicate part: %s" % name)
        seen.add(name)
        try:
            image, mask = load_part_split_asset(project_dir, entry)
            bbox = entry.get("bbox") or [0, 0, image.size[0], image.size[1]]
            x0, y0, x1, y1 = [int(value) for value in bbox]
            area = mask_pixel_area(mask)
            status = "pass"
            entry_warnings: List[str] = []
            entry_failures: List[str] = []
            if area < SPRITE_MODEL_FAIL_MIN_MASK_AREA or bbox_area(bbox) <= 0:
                entry_failures.append("part is missing usable opaque pixels")
                status = "fail"
            elif area < SPRITE_MODEL_WARN_MIN_MASK_AREA:
                entry_warnings.append("mask area is unusually small")
                status = "warning"
            per_part.append({
                "part_name": name,
                "status": status,
                "mask_area": area,
                "bbox": [int(value) for value in bbox],
                "warnings": entry_warnings,
                "failures": entry_failures,
            })
            positioned_mask = Image.new("L", overlap_canvas_size, 0)
            positioned_mask.paste(mask, (x0, y0))
            overlap_masks.append((name, normalize_mask(positioned_mask)))
            warnings.extend("%s: %s" % (name, message) for message in entry_warnings)
            failures.extend("%s: %s" % (name, message) for message in entry_failures)
        except FileNotFoundError:
            failures.append("missing asset files for %s" % name)
    missing_required = sorted(
        name for name, definition in expected_parts.items()
        if definition.get("required") and name not in seen
    )
    for name in missing_required:
        failures.append("missing required part: %s" % name)
    enforce_overlap_checks = any(str(entry.get("source_method") or "") != "legacy_box_fallback" for entry in parts)
    if enforce_overlap_checks:
        for left_index, (left_name, left_mask) in enumerate(overlap_masks):
            left_area = float(max(1, mask_pixel_area(left_mask)))
            for right_name, right_mask in overlap_masks[left_index + 1:]:
                overlap = mask_pixel_area(ImageChops.multiply(left_mask, right_mask))
                if overlap <= 0:
                    continue
                overlap_ratio = overlap / left_area
                if overlap_ratio > 0.45:
                    failures.append("severe overlap contamination: %s vs %s" % (left_name, right_name))
                elif overlap_ratio > 0.22:
                    warnings.append("overlap contamination needs review: %s vs %s" % (left_name, right_name))
    reconstruction = part_split.get("reconstruction_preview") or {}
    if isinstance(source_mask, Image.Image) and reconstruction.get("path"):
        preview_mask = normalize_mask(Image.open(project_dir / reconstruction["path"]).convert("RGBA").getchannel("A"))
        union = mask_pixel_area(ImageChops.lighter(source_mask, preview_mask))
        overlap = mask_pixel_area(ImageChops.multiply(source_mask, preview_mask))
        coverage = overlap / float(max(1, union))
        reconstruction["coverage_ratio"] = round(coverage, 4)
        if coverage < 0.55:
            failures.append("reconstruction drift is too large")
        elif coverage < 0.72:
            warnings.append("reconstruction drift needs review")
    status = "pass"
    if failures:
        status = "fail"
    elif warnings:
        status = "warning"
    return {
        "generated_at": now_iso(),
        "status": status,
        "warnings": warnings,
        "failures": failures,
        "missing_required_parts": missing_required,
        "per_part": per_part,
        "reconstruction": reconstruction,
    }


def extract_json_object_from_text(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Codex response is empty.")
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    candidates = fenced + [raw]
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = candidate[start:end + 1]
            try:
                parsed = json.loads(snippet)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    raise ValueError("Could not find a valid JSON object in the Codex response.")


def create_rig_layout_revision(project_dir: Path, rig_layout: Dict[str, Any], reason: str, operation: Optional[str] = None) -> Dict[str, Any]:
    history = load_json(rig_layout_history_path(project_dir), default_rig_layout_history(project_dir.name))
    revision = {
        "revision_id": "rev-%s" % uuid.uuid4().hex[:10],
        "created_at": now_iso(),
        "reason": reason,
        "operation": operation,
        "rig_layout_hash": hashlib.sha256(json.dumps(rig_layout, sort_keys=True).encode("utf-8")).hexdigest(),
    }
    history.setdefault("revisions", []).append(revision)
    history["current_revision_id"] = revision["revision_id"]
    history.setdefault("events", []).append({
        "type": "rig_layout_%s" % reason,
        "operation": operation,
        "created_at": revision["created_at"],
    })
    write_json(rig_layout_history_path(project_dir), history)
    return history


def resolve_rig_layout(project: Dict[str, Any], concept: Optional[Dict[str, Any]] = None, rig_profile: Optional[str] = None, persist: bool = False) -> Dict[str, Any]:
    project_dir = PROJECTS_ROOT / project["project_id"]
    if concept is None:
        concepts = project.get("concepts") or []
        concept = next((item for item in concepts if item.get("concept_id") == project.get("selected_concept_id")), {}) if concepts else {}
    profile_name = rig_profile or active_rig_profile_name(project)
    if profile_name not in RIG_PROFILES:
        profile_name = LEGACY_RIG_PROFILE
    profile = profile_definition(profile_name)
    source_facing = "right"
    if isinstance(project.get("sprite_model"), dict) and project["sprite_model"].get("source_facing") in {"left", "right"}:
        source_facing = project["sprite_model"]["source_facing"]
    parts: List[Dict[str, Any]] = []
    for entry in profile["parts"]:
        part = copy.deepcopy(entry)
        parent_joint = resolve_layout_parent_joint(part["part_name"], profile_name, source_facing)
        if parent_joint:
            part["parent_joint"] = parent_joint
        part["extraction_region"] = resolve_layout_region(part, source_facing)
        parts.append(part)
    layout = {
        "layout_version": 1,
        "project_id": project["project_id"],
        "approved_concept_id": concept.get("concept_id") if isinstance(concept, dict) else None,
        "rig_profile": profile_name,
        "parts": parts,
        "joint_schema": profile["joint_schema"],
        "draw_order": [item["part_name"] for item in sorted(parts, key=lambda item: item["draw_order"])],
        "extraction_rules": {item["part_name"]: item["extraction_region"] for item in parts},
        "pivot_rules": {item["part_name"]: item.get("pivot_strategy") for item in parts},
        "joint_driving_parts": list(profile["joint_driving_parts"]),
        "overlay_parts": list(profile["overlay_parts"]),
        "flags": copy.deepcopy(profile["flags"]),
        "source_assumptions": {
            "strict_side_view": True,
            "source_facing": source_facing,
        },
        "validation": validate_rig_layout({
            "rig_profile": profile_name,
            "parts": parts,
            "joint_driving_parts": profile["joint_driving_parts"],
        }),
        "approved": profile_name == LEGACY_RIG_PROFILE and not persist,
        "auto_generated_legacy": profile_name == LEGACY_RIG_PROFILE and not persist,
        "created_at": now_iso(),
    }
    if persist:
        write_json(canonical_downstream_path(project_dir, "rig_layout"), layout)
        create_rig_layout_revision(project_dir, layout, "generate")
    return layout


def build_rig_layout_handoff_prompt(project: Dict[str, Any], rig_layout: Optional[Dict[str, Any]] = None) -> str:
    layout = rig_layout or project.get("rig_layout") or resolve_rig_layout(project, persist=False)
    concept = None
    try:
        concept = selected_concept(project)
    except Exception:
        concept = None
    prompt_profile = active_rig_profile_name(project, layout)
    if isinstance(concept, dict) and concept:
        prompt_profile = select_rig_profile(project, concept)
    layout = resolve_rig_layout(project, concept, rig_profile=prompt_profile, persist=False)
    brief = project.get("brief") or {}
    allowed_parts = [item["part_name"] for item in (layout.get("parts") or [])]
    allowed_joints = list((layout.get("joint_schema") or {}).get("joints") or [])
    lines = [
        "You are validating a side-view character concept for a deterministic 2D sprite pipeline.",
        "This step does two things at once:",
        "1. decide whether the concept is suitable for deterministic sprite extraction and rigging",
        "2. if it is suitable, define the internal rig_layout JSON that downstream sprite extraction, rig build, and animation rendering will use",
        "",
        "The rig_layout is not a generic anatomy rig.",
        "It should be optimized to the actual visible shapes in this concept image so the bind pose reconstructs cleanly and animation remains stable.",
        "Fit the rig to the concept. Do not force the concept into unnecessary articulated pieces.",
        "",
        "Rig simplicity is a hard requirement.",
        "For armored side-view knight concepts, default to the minimum viable rig that reconstructs the concept cleanly.",
        "For this pipeline, a stable merged-mass layout is preferred over a detailed anatomy rig.",
        "A result that mechanically expands into the legacy full-part decomposition is usually wrong for this task.",
        "",
        "Primary design goals:",
        "- preserve the concept's readable silhouette and shape language",
        "- maximize clean neutral-pose reconstruction from extracted parts",
        "- minimize seams, duplicated pixels, and unstable hidden-side anatomy",
        "- prefer fewer, larger, more reliable masses when separation is ambiguous",
        "- keep overlays like cape or front cloth as overlays when that is more stable than making them primary joint-driving pieces",
        "- keep weapon, arm, leg, torso, and head separations only where the concept clearly supports them",
        "",
        "Decision rule:",
        "- If the concept is not suitable for this pipeline, return valid=false and explain why briefly.",
        "- If the concept is suitable, return valid=true and produce a rig_layout object that matches the required schema exactly.",
        "- If the only way to make the layout work is to invent hidden-side anatomy or speculative articulation, return valid=false.",
        "- If the concept would require the legacy many-part rig to function, return valid=false instead of emitting an over-split layout.",
        "",
        "Context:",
        f"- project: {project.get('project_name') or project.get('project_id')}",
        f"- rig_profile: {layout.get('rig_profile')}",
        f"- character brief: role={brief.get('role_archetype') or brief.get('role', '')}; silhouette={brief.get('silhouette_intent') or brief.get('silhouette', '')}; outfit={brief.get('outfit_materials') or brief.get('outfit', '')}; prop={brief.get('prop', '')}; palette={brief.get('palette_mood') or brief.get('palette_direction', '')}; mood={brief.get('mood_tone') or brief.get('mood_tone', '')}",
    ]
    if concept:
        lines.extend([
            f"- selected concept id: {concept.get('concept_id')}",
            f"- concept prompt summary: {(concept.get('positive_prompt') or '').strip()}",
        ])
    lines.extend([
        "",
        "Response requirements:",
        "- Return exactly one JSON object.",
        "- You may wrap it in a ```json code fence, but do not include any extra prose outside the JSON.",
        "- The JSON object must contain: valid, summary, rig_layout.",
        "- If valid is false, still return a rig_layout field using null.",
        '- The summary should explain the rigging judgment in human terms, for example why the image is stable or unstable for deterministic extraction.',
        "",
        "Required top-level JSON shape:",
        "{",
        '  "valid": true,',
        '  "summary": "short human-readable validation summary",',
        '  "rig_layout": {',
        '    "layout_version": 1,',
        f'    "rig_profile": "{layout.get("rig_profile")}",',
        '    "parts": [...],',
        '    "joint_schema": {"joints": [...], "transform_channels": [...]},',
        '    "draw_order": [...],',
        '    "extraction_rules": {...},',
        '    "pivot_rules": {...},',
        '    "joint_driving_parts": [...],',
        '    "overlay_parts": [...],',
        '    "flags": {...},',
        '    "source_assumptions": {...}',
        "  }",
        "}",
        "",
        "Schema constraints:",
        f"- allowed part names: {', '.join(allowed_parts)}",
        f"- allowed joints: {', '.join(allowed_joints)}",
        "- Every part object must contain: part_name, part_role, required, parent_joint, draw_order, pivot_strategy, extraction_region, fallback_mode, overlay_only.",
        "- extraction_region must be either [x0, y0, x1, y1] or a facing map like {\"left\": [...], \"right\": [...]} using normalized 0..1 coordinates.",
        "- pivot_strategy must use mode=fractional and fraction=[x, y].",
        "- joint_driving_parts must not include overlay-only parts.",
        "- draw_order must match the intended visual stacking for the image.",
        "- Keep the layout conservative. Merge ambiguous anatomy into larger stable masses instead of inventing fragile articulated splits.",
        "- Use as few parts as possible while preserving neutral-pose reconstruction and stable animation.",
        "- Omitted allowed parts are expected and preferred over speculative parts.",
        "- The allowed part list is a superset, not a target checklist. Do not try to use every allowed part.",
        "- Do not return more than 8 total parts. If more than 8 parts seem necessary, return valid=false.",
        "- Do not include a limb split unless the split is clearly visible in the concept and materially improves deformation stability.",
        "- Do not create hidden-side limbs, hidden-side joints, or duplicated anatomy from inference.",
        "- Prefer one-piece armor masses over anatomical segmentation when armor reads as a single stable shape.",
        "- Cape, tabard, front cloth, loin cloth, and similar hanging materials should default to overlay parts rather than primary joint-driving parts.",
        "- If an arm or leg can be reconstructed more reliably as one visible mass, prefer the merged limb over elbow or knee sub-parts.",
        "- The output rig_layout should be the best practical structure for this specific concept image, not a theoretical perfect rig.",
        "- Avoid legacy anatomy-style decomposition such as separate upper/lower arm, hand, upper/lower leg, and foot splits unless the image truly cannot be stabilized without them.",
        "",
        "Complexity target:",
        "- For knight-like side-view concepts, target the minimum viable part count.",
        "- Expected primary driven parts: 4 to 8.",
        "- Expected overlay parts: 0 to 2.",
        "- A typical good result for this kind of character is about 7 to 8 total parts, not 20.",
        "- 8 total parts is a hard ceiling for this response.",
        "- If more than 8 primary driven parts are used, the summary must briefly justify why the extra splits are necessary for stability.",
        "- If the layout reaches anything close to the legacy full-part count, treat that as a likely failure to simplify and reconsider from scratch.",
        "",
        "Preferred simplification pattern for armored side-view characters:",
        "- Merge torso and pelvis if the separation is weak or mostly hidden by armor or cloth.",
        "- Use one front arm mass instead of upper arm, forearm, and hand unless the elbow break is unusually clear and necessary.",
        "- Use one front leg mass instead of thigh, shin, and foot unless ankle articulation is clearly needed for ground contact.",
        "- Keep the rear-side anatomy omitted unless it is cleanly visible and materially necessary.",
        "- Treat weapon, cape, and front cloth as optional extra masses only when they are visually distinct and stable.",
        "",
        "Updated output contract:",
        "- Before producing JSON, internally test whether the neutral pose can be reconstructed with fewer parts.",
        "- Before producing JSON, internally test whether any obscured limb, hidden-side anatomy, or speculative joint was invented.",
        "- Before producing JSON, internally test whether any armor mass was split where a merged mass would be more stable.",
        "- Before producing JSON, internally test whether any cape, tabard, or front cloth was incorrectly promoted to a primary joint-driving part.",
        "- Before producing JSON, internally test whether you accidentally drifted toward the legacy 20-part anatomy breakdown. If so, simplify again.",
        "- If any of those checks fail, simplify the layout before returning JSON.",
        "- If the simplified profile still cannot represent the concept within 8 total parts, return valid=false.",
        "- If the concept still requires speculative anatomy or unnecessary articulation after simplification, return valid=false.",
        "",
        "Profile-specific expectation:",
        "- For knight-like side-view concepts, use the simplified merged-mass layout rather than the legacy full 20-part layout unless the image clearly demands more structure.",
        "- For side_knight_simple_7, the default expected joint_driving_parts are: head, torso_pelvis, front_arm, front_leg, weapon.",
        "- For side_knight_simple_7, do not rename or expand the simple profile into legacy-style equivalents.",
    ])
    return "\n".join(lines)


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
    normalized.setdefault("master_pose_approved", False)
    normalized.setdefault("sprite_model_approved", False)
    normalized.setdefault("rig_layout_approved", False)
    normalized.setdefault("part_manifest_approved", False)
    normalized.setdefault("part_shapes_approved", False)
    normalized.setdefault("part_split_approved", False)
    normalized.setdefault("split_review_approved", False)
    normalized.setdefault("selected_concept_id", None)
    normalized.setdefault("archived_at", None)
    normalized.setdefault("last_ui_mode", "wizard")
    normalized.setdefault("wizard_state", None)
    normalized.setdefault("ai_workflow", None)
    normalized.setdefault("external_authoring", None)
    return normalized


def default_wizard_state() -> Dict[str, Any]:
    return {
        "current_step": "project",
        "last_completed_step": None,
        "completed_steps": [],
        "skipped_optional_steps": [],
        "show_advanced": False,
    }


def normalize_wizard_state(payload: Any) -> Dict[str, Any]:
    state = default_wizard_state()
    if isinstance(payload, dict):
        current_step = payload.get("current_step")
        if current_step in WIZARD_STEPS_KNOWN:
            state["current_step"] = current_step
        last_completed = payload.get("last_completed_step")
        if last_completed in WIZARD_STEPS_KNOWN:
            state["last_completed_step"] = last_completed
        completed = [item for item in payload.get("completed_steps", []) if item in WIZARD_STEPS_KNOWN]
        skipped = [item for item in payload.get("skipped_optional_steps", []) if item in WIZARD_STEPS_KNOWN]
        state["completed_steps"] = list(dict.fromkeys(completed))
        state["skipped_optional_steps"] = list(dict.fromkeys(skipped))
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


def canonical_downstream_path(project_dir: Path, key: str) -> Path:
    return project_dir / CANONICAL_DOWNSTREAM_FILES[key]


def legacy_downstream_path(project_dir: Path, key: str) -> Path:
    return project_dir / LEGACY_DOWNSTREAM_FILES[key]


def default_sprite_model_history(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "current_revision_id": None,
        "events": [],
        "revisions": [],
    }


def default_manual_animation_clips(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "clips": {},
        "updated_at": now_iso(),
    }


def default_ai_dependency_status() -> Dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "overall_status": "unknown",
        "dependencies": {},
    }


def default_ai_workflow(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "enabled": True,
        "profile": AI_WORKFLOW_PROFILE,
        "dependency_status": default_ai_dependency_status(),
        "legacy_mode": False,
        "character_lock": {
            "runs": {},
            "approved_run_id": None,
            "approved_asset_id": None,
        },
        "key_pose_set": {
            "runs": {},
            "approved_run_id": None,
        },
        "motion_runs": {clip_name: {"runs": {}, "approved_run_id": None} for clip_name in AI_CLIP_SPECS},
        "extract_runs": {clip_name: {"runs": {}, "approved_run_id": None} for clip_name in AI_CLIP_SPECS},
        "cleanup_runs": {clip_name: {"runs": {}, "approved_run_id": None} for clip_name in AI_CLIP_SPECS},
        "selected_assets": {
            "approved_concept_id": None,
            "character_lock_asset_id": None,
            "character_lock_run_id": None,
            "key_pose_run_id": None,
            "motion_run_ids": {},
            "extract_run_ids": {},
            "cleanup_run_ids": {},
        },
        "updated_at": now_iso(),
    }


def _normalize_run_group(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {"runs": {}, "approved_run_id": None}
    return {
        "runs": copy.deepcopy(value.get("runs") or {}),
        "approved_run_id": value.get("approved_run_id"),
    }


def hydrate_ai_workflow(store: Any, project: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
    hydrated = default_ai_workflow(project_dir.name)
    if isinstance(store, dict):
        hydrated["enabled"] = bool(store.get("enabled", True))
        hydrated["profile"] = str(store.get("profile") or AI_WORKFLOW_PROFILE)
        if isinstance(store.get("dependency_status"), dict):
            hydrated["dependency_status"] = copy.deepcopy(store["dependency_status"])
        hydrated["legacy_mode"] = bool(store.get("legacy_mode", False))
        character_lock = _normalize_run_group(store.get("character_lock"))
        hydrated["character_lock"]["runs"] = character_lock["runs"]
        hydrated["character_lock"]["approved_run_id"] = character_lock["approved_run_id"]
        hydrated["character_lock"]["approved_asset_id"] = (store.get("character_lock") or {}).get("approved_asset_id")
        key_pose_set = _normalize_run_group(store.get("key_pose_set"))
        hydrated["key_pose_set"]["runs"] = key_pose_set["runs"]
        hydrated["key_pose_set"]["approved_run_id"] = key_pose_set["approved_run_id"]
        for group_name in ("motion_runs", "extract_runs", "cleanup_runs"):
            source_group = store.get(group_name) if isinstance(store.get(group_name), dict) else {}
            target_group = hydrated[group_name]
            for clip_name in AI_CLIP_SPECS:
                normalized = _normalize_run_group(source_group.get(clip_name))
                target_group[clip_name] = normalized
        if isinstance(store.get("selected_assets"), dict):
            hydrated["selected_assets"].update(copy.deepcopy(store["selected_assets"]))
        hydrated["updated_at"] = str(store.get("updated_at") or hydrated["updated_at"])
    has_legacy_data = bool(
        project.get("external_authoring")
        or project.get("rig")
        or project.get("sprite_model")
        or project.get("part_split")
        or (project.get("manual_animation_clips", {}).get("clips") if isinstance(project.get("manual_animation_clips"), dict) else None)
    )
    if not isinstance(store, dict) and has_legacy_data:
        hydrated["enabled"] = False
        hydrated["legacy_mode"] = True
    if hydrated["legacy_mode"]:
        hydrated["enabled"] = False
    return hydrated


def serialize_ai_workflow(store: Any, project_id: str) -> Dict[str, Any]:
    serialized = default_ai_workflow(project_id)
    if not isinstance(store, dict):
        return serialized
    serialized["enabled"] = bool(store.get("enabled", True))
    serialized["profile"] = str(store.get("profile") or AI_WORKFLOW_PROFILE)
    if isinstance(store.get("dependency_status"), dict):
        serialized["dependency_status"] = copy.deepcopy(store["dependency_status"])
    serialized["legacy_mode"] = bool(store.get("legacy_mode", False))
    serialized["character_lock"] = copy.deepcopy(store.get("character_lock") or serialized["character_lock"])
    serialized["key_pose_set"] = copy.deepcopy(store.get("key_pose_set") or serialized["key_pose_set"])
    for group_name in ("motion_runs", "extract_runs", "cleanup_runs"):
        source_group = store.get(group_name) if isinstance(store.get(group_name), dict) else {}
        serialized[group_name] = {
            clip_name: copy.deepcopy(source_group.get(clip_name) or serialized[group_name][clip_name])
            for clip_name in AI_CLIP_SPECS
        }
    if isinstance(store.get("selected_assets"), dict):
        serialized["selected_assets"].update(copy.deepcopy(store["selected_assets"]))
    serialized["updated_at"] = str(store.get("updated_at") or serialized["updated_at"])
    return serialized


def ai_workflow_root(project_dir: Path, stage: str, clip_name: Optional[str] = None, run_id: Optional[str] = None) -> Path:
    if stage == "character_lock":
        root = project_dir / "ai_workflow" / "character_lock"
    elif stage == "key_pose_set":
        root = project_dir / "ai_workflow" / "key_poses"
    elif stage in {"motion_clip", "extract_frames", "pixel_cleanup"}:
        if clip_name not in AI_CLIP_SPECS:
            raise ValueError("Unknown clip: %s." % clip_name)
        mapping = {
            "motion_clip": "motion",
            "extract_frames": "extract",
            "pixel_cleanup": "cleanup",
        }
        root = project_dir / "ai_workflow" / mapping[stage] / clip_name
    else:
        raise ValueError("Unknown AI workflow stage: %s." % stage)
    if run_id:
        root = root / run_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def skelform_provider_profile() -> Dict[str, Any]:
    return {
        "provider": "skelform",
        "label": "SkelForm",
        "editor_url": SKELFORM_EDITOR_URL,
        "docs_url": SKELFORM_DOCS_URL,
        "license": "MIT",
        "embed_strategy": "iframe-hosted-editor",
        "self_hosting_status": "validated_remote_editor_first",
        "x_frameable": True,
        "export_expectations": [
            "spritesheet image",
            "atlas json",
            "animations json",
            "optional preview gif",
        ],
        "validated_at": now_iso(),
    }


def default_external_authoring(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "enabled": False,
        "provider": "skelform",
        "provider_profile": skelform_provider_profile(),
        "session": {
            "editor_url": SKELFORM_EDITOR_URL,
            "embed_url": SKELFORM_EDITOR_URL,
            "can_embed": True,
            "source_mode": "hosted",
            "last_opened_at": None,
        },
        "validation": {
            "license": "MIT",
            "docs_url": SKELFORM_DOCS_URL,
            "embed_test": "passed",
            "build_flow": "remote-hosted editor embedded first, local vendoring deferred",
            "runtime_format": ".skf plus exported sheets/metadata",
            "validated_at": now_iso(),
        },
        "imported_bundle": None,
        "updated_at": now_iso(),
    }


def hydrate_external_authoring(store: Any, project_dir: Path) -> Dict[str, Any]:
    hydrated = default_external_authoring(project_dir.name)
    if not isinstance(store, dict):
        return hydrated
    hydrated["enabled"] = bool(store.get("enabled", False))
    hydrated["provider"] = str(store.get("provider") or "skelform")
    if isinstance(store.get("provider_profile"), dict):
        hydrated["provider_profile"].update(store["provider_profile"])
    if isinstance(store.get("session"), dict):
        hydrated["session"].update(store["session"])
    if isinstance(store.get("validation"), dict):
        hydrated["validation"].update(store["validation"])
    bundle = store.get("imported_bundle")
    if isinstance(bundle, dict):
        hydrated["imported_bundle"] = copy.deepcopy(bundle)
    hydrated["updated_at"] = str(store.get("updated_at") or hydrated["updated_at"])
    return hydrated


def serialize_external_authoring(store: Any, project_id: str) -> Dict[str, Any]:
    serialized = default_external_authoring(project_id)
    if not isinstance(store, dict):
        return serialized
    serialized["enabled"] = bool(store.get("enabled", False))
    serialized["provider"] = str(store.get("provider") or "skelform")
    if isinstance(store.get("provider_profile"), dict):
        serialized["provider_profile"].update(copy.deepcopy(store["provider_profile"]))
    if isinstance(store.get("session"), dict):
        serialized["session"].update(copy.deepcopy(store["session"]))
    if isinstance(store.get("validation"), dict):
        serialized["validation"].update(copy.deepcopy(store["validation"]))
    if isinstance(store.get("imported_bundle"), dict):
        serialized["imported_bundle"] = copy.deepcopy(store["imported_bundle"])
    serialized["updated_at"] = str(store.get("updated_at") or serialized["updated_at"])
    return serialized


def external_authoring_import_root(project_dir: Path) -> Path:
    root = project_dir / "external_authoring" / "imports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def manual_clip_render_root(project_dir: Path) -> Path:
    return project_dir / "manual_clips"


def manual_clip_source_hashes(project_dir: Path) -> Dict[str, Optional[str]]:
    rig_path = canonical_downstream_path(project_dir, "rig")
    sprite_model_path = canonical_downstream_path(project_dir, "sprite_model")
    return {
        "rig_hash": image_sha256(rig_path) if rig_path.exists() else None,
        "sprite_model_hash": image_sha256(sprite_model_path) if sprite_model_path.exists() else None,
    }


def manual_clip_frame_count(value: Any, default: int = 8) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(64, parsed))


def normalize_manual_clip_frame(frame: Any) -> Dict[str, Any]:
    base = neutral_pose_transforms()
    normalized = dict(base)
    if isinstance(frame, dict):
        for key, value in frame.items():
            if key == "root_offset" and isinstance(value, list) and len(value) == 2:
                normalized[key] = [round(float(value[0]), 2), round(float(value[1]), 2)]
            elif key in normalized and isinstance(value, (int, float)):
                normalized[key] = round(float(value), 2)
    return normalized


def normalize_manual_frame_repairs(value: Any) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    if not isinstance(value, dict):
        return normalized
    for part_name, payload in value.items():
        if not isinstance(payload, dict):
            continue
        image_path = str(payload.get("image_path") or "").strip()
        if not image_path:
            continue
        normalized[str(part_name)] = {
            "variant_id": str(payload.get("variant_id") or "").strip() or None,
            "image_path": image_path,
            "mask_path": str(payload.get("mask_path") or "").strip() or None,
            "source": str(payload.get("source") or "recover-occlusion").strip() or "recover-occlusion",
            "summary": str(payload.get("summary") or "").strip() or None,
            "applied_at": str(payload.get("applied_at") or now_iso()),
        }
    return normalized


def normalize_manual_frame_patches(value: Any) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    if not isinstance(value, dict):
        return normalized
    for patch_id, payload in value.items():
        if not isinstance(payload, dict):
            continue
        source_part = str(payload.get("source_part_name") or payload.get("part_name") or "").strip()
        image_path = str(payload.get("image_path") or "").strip()
        keep_behind_part = str(payload.get("keep_behind_part_name") or "").strip()
        if not source_part or not image_path or not keep_behind_part:
            continue
        normalized[str(patch_id)] = {
            "patch_id": str(payload.get("patch_id") or patch_id).strip() or str(patch_id),
            "source_part_name": source_part,
            "keep_behind_part_name": keep_behind_part,
            "variant_id": str(payload.get("variant_id") or "").strip() or None,
            "image_path": image_path,
            "mask_path": str(payload.get("mask_path") or "").strip() or None,
            "source": str(payload.get("source") or "recover-occlusion").strip() or "recover-occlusion",
            "summary": str(payload.get("summary") or "").strip() or None,
            "applied_at": str(payload.get("applied_at") or now_iso()),
        }
    return normalized


def normalize_manual_clip_frame_entry(frame: Any) -> Dict[str, Any]:
    if isinstance(frame, dict) and ("transforms" in frame or "part_repairs" in frame or "corrective_patches" in frame):
        transforms = normalize_manual_clip_frame(frame.get("transforms"))
        part_repairs = normalize_manual_frame_repairs(frame.get("part_repairs"))
        corrective_patches = normalize_manual_frame_patches(frame.get("corrective_patches"))
    else:
        transforms = normalize_manual_clip_frame(frame)
        part_repairs = {}
        corrective_patches = {}
    return {
        "transforms": transforms,
        "part_repairs": part_repairs,
        "corrective_patches": corrective_patches,
    }


def manual_clip_frame_transforms(frame: Any) -> Dict[str, Any]:
    return normalize_manual_clip_frame_entry(frame)["transforms"]


def blank_manual_clip_frames(frame_count: int) -> List[Dict[str, Any]]:
    return [normalize_manual_clip_frame_entry({}) for _ in range(frame_count)]


def default_manual_clip(project_dir: Path, clip_id: str, clip_name: str, frame_count: int = 8, fps: int = 12, loop: bool = True) -> Dict[str, Any]:
    render_root = manual_clip_render_root(project_dir) / clip_id
    frame_count = manual_clip_frame_count(frame_count)
    fps_value = max(1, min(60, int(fps)))
    return {
        "clip_id": clip_id,
        "clip_name": clip_name,
        "authoring_mode": "manual",
        "approval_status": "draft",
        "frame_count": frame_count,
        "fps": fps_value,
        "loop": bool(loop),
        "frames": blank_manual_clip_frames(frame_count),
        "source_hashes": manual_clip_source_hashes(project_dir),
        "preview_render": {
            "status": "not_rendered",
            "gif_path": str((render_root / "preview.gif").relative_to(project_dir)),
            "render_manifest_path": str((render_root / "render_manifest.json").relative_to(project_dir)),
            "frame_dir": str((render_root / "frames").relative_to(project_dir)),
            "frames": [],
            "generated_at": None,
        },
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "approved_at": None,
    }


def invalidate_manual_clip_preview(clip: Dict[str, Any]) -> Dict[str, Any]:
    preview = dict(clip.get("preview_render") or {})
    preview["status"] = "outdated"
    preview["frames"] = []
    preview["generated_at"] = None
    clip["preview_render"] = preview
    clip["approval_status"] = "draft"
    clip["approved_at"] = None
    clip["updated_at"] = now_iso()
    return clip


def normalize_manual_clip(project_dir: Path, clip_id: str, payload: Any) -> Dict[str, Any]:
    clip = default_manual_clip(project_dir, clip_id, humanize_identifier(clip_id))
    if isinstance(payload, dict):
        clip["clip_name"] = str(payload.get("clip_name") or clip["clip_name"]).strip() or clip["clip_name"]
        clip["frame_count"] = manual_clip_frame_count(payload.get("frame_count"), clip["frame_count"])
        clip["fps"] = max(1, min(60, int(payload.get("fps") or clip["fps"])))
        clip["loop"] = bool(payload.get("loop", clip["loop"]))
        clip["authoring_mode"] = "manual"
        clip["approval_status"] = str(payload.get("approval_status") or clip["approval_status"])
        clip["source_hashes"] = payload.get("source_hashes") if isinstance(payload.get("source_hashes"), dict) else clip["source_hashes"]
        clip["created_at"] = str(payload.get("created_at") or clip["created_at"])
        clip["updated_at"] = str(payload.get("updated_at") or clip["updated_at"])
        clip["approved_at"] = payload.get("approved_at")
        preview = payload.get("preview_render") if isinstance(payload.get("preview_render"), dict) else {}
        clip["preview_render"] = {
            "status": str(preview.get("status") or "not_rendered"),
            "gif_path": str(preview.get("gif_path") or clip["preview_render"]["gif_path"]),
            "render_manifest_path": str(preview.get("render_manifest_path") or clip["preview_render"]["render_manifest_path"]),
            "frame_dir": str(preview.get("frame_dir") or clip["preview_render"]["frame_dir"]),
            "frames": list(preview.get("frames") or []),
            "generated_at": preview.get("generated_at"),
        }
        raw_frames = payload.get("frames") if isinstance(payload.get("frames"), list) else []
        normalized_frames = [normalize_manual_clip_frame_entry(frame) for frame in raw_frames[:clip["frame_count"]]]
        while len(normalized_frames) < clip["frame_count"]:
            normalized_frames.append(normalize_manual_clip_frame_entry({}))
        clip["frames"] = normalized_frames
    return clip


def hydrate_manual_animation_clips(store: Any, project_dir: Path) -> Dict[str, Any]:
    hydrated = default_manual_animation_clips(project_dir.name)
    raw_clips = store.get("clips") if isinstance(store, dict) else {}
    normalized: Dict[str, Any] = {}
    for clip_id, payload in (raw_clips or {}).items():
        if not isinstance(payload, dict):
            continue
        safe_clip_id = sanitize_filename(str(payload.get("clip_id") or clip_id), "manual-clip")
        clip = normalize_manual_clip(project_dir, safe_clip_id, payload)
        current_hashes = manual_clip_source_hashes(project_dir)
        stale_reasons = []
        if clip["source_hashes"].get("rig_hash") != current_hashes.get("rig_hash"):
            stale_reasons.append("rig changed")
        if clip["source_hashes"].get("sprite_model_hash") != current_hashes.get("sprite_model_hash"):
            stale_reasons.append("sprite model changed")
        preview_gif = project_dir / str(clip["preview_render"].get("gif_path") or "")
        manifest_path = project_dir / str(clip["preview_render"].get("render_manifest_path") or "")
        clip["is_stale"] = bool(stale_reasons)
        clip["stale_reasons"] = stale_reasons
        clip["preview_render_complete"] = bool(preview_gif.exists() and manifest_path.exists())
        normalized[safe_clip_id] = clip
    hydrated["clips"] = normalized
    hydrated["updated_at"] = str(store.get("updated_at") or hydrated["updated_at"]) if isinstance(store, dict) else hydrated["updated_at"]
    return hydrated


def serialize_manual_animation_clips(store: Any, project_id: str) -> Dict[str, Any]:
    serialized = default_manual_animation_clips(project_id)
    raw_clips = store.get("clips") if isinstance(store, dict) else {}
    clips: Dict[str, Any] = {}
    for clip_id, payload in (raw_clips or {}).items():
        if not isinstance(payload, dict):
            continue
        clip = copy.deepcopy(payload)
        clip.pop("is_stale", None)
        clip.pop("stale_reasons", None)
        clip.pop("preview_render_complete", None)
        clips[str(clip_id)] = clip
    serialized["clips"] = clips
    if isinstance(store, dict) and store.get("updated_at"):
        serialized["updated_at"] = str(store["updated_at"])
    return serialized

def sprite_model_revisions_path(project_dir: Path) -> Path:
    return project_dir / SPRITE_MODEL_REVISIONS_DIRNAME


def bbox_area(box: Optional[List[int]]) -> int:
    if not isinstance(box, list) or len(box) != 4:
        return 0
    return max(0, int(box[2]) - int(box[0])) * max(0, int(box[3]) - int(box[1]))


def bbox_intersection_area(a: Optional[List[int]], b: Optional[List[int]]) -> int:
    if not isinstance(a, list) or len(a) != 4 or not isinstance(b, list) or len(b) != 4:
        return 0
    left = max(int(a[0]), int(b[0]))
    top = max(int(a[1]), int(b[1]))
    right = min(int(a[2]), int(b[2]))
    bottom = min(int(a[3]), int(b[3]))
    if right <= left or bottom <= top:
        return 0
    return (right - left) * (bottom - top)


def mask_pixel_area(mask: Image.Image) -> int:
    normalized = normalize_mask(mask)
    return sum(1 for value in normalized.getdata() if value > 0)


def compute_wizard_context(project: Dict[str, Any]) -> Dict[str, Any]:
    project_dir = PROJECTS_ROOT / project["project_id"]
    wizard_state = normalize_wizard_state(project.get("wizard_state"))
    brief = project.get("brief") or {}
    ai_workflow = project.get("ai_workflow") or {}
    ai_enabled = bool(ai_workflow.get("enabled")) and not bool(ai_workflow.get("legacy_mode"))
    external_authoring = project.get("external_authoring") or {}
    external_enabled = bool(external_authoring.get("enabled"))
    external_bundle = external_authoring.get("imported_bundle") if isinstance(external_authoring.get("imported_bundle"), dict) else None
    has_external_bundle = bool(
        external_bundle
        and external_bundle.get("spritesheet_image_path")
        and external_bundle.get("atlas_path")
        and external_bundle.get("animations_path")
    )
    completed = set(wizard_state.get("completed_steps", []))
    skipped = set(wizard_state.get("skipped_optional_steps", []))
    attempts = project.get("concepts") or []
    imported_attempts = [item for item in attempts if item.get("preview_image")]
    valid_attempts = [item for item in imported_attempts if item.get("validation_status") == "valid"]

    if ai_enabled:
        character_lock = ai_workflow.get("character_lock") or {}
        key_pose_set = ai_workflow.get("key_pose_set") or {}
        cleanup_runs = ai_workflow.get("cleanup_runs") or {}
        pixellab_brief = str(brief.get("backend_mode") or "") == "pixellab"
        approved_cleanup_ready = True
        for clip_name in AI_CLIP_SPECS:
            clip_group = cleanup_runs.get(clip_name) if isinstance(cleanup_runs.get(clip_name), dict) else {}
            approved_run_id = clip_group.get("approved_run_id")
            approved_run = (clip_group.get("runs") or {}).get(approved_run_id) if approved_run_id else None
            if not approved_run or not approved_run.get("frame_dir"):
                approved_cleanup_ready = False
                break

        pixellab_clips_complete = pixellab_character_wizard_complete(project, project_dir) if pixellab_brief else approved_cleanup_ready

        has_brief = "brief" in completed or bool((project.get("prompt_text") or "").strip())
        has_references = bool(brief.get("references")) or "references" in completed or "references" in skipped or has_brief
        has_concepts = bool(project.get("prompt_history")) or bool(imported_attempts)
        has_review = bool(project.get("selected_concept_id"))
        # Phase 7.2: Character Lock / Key Pose panels removed; approved concept unlocks the same gates.
        concept_path_ready = bool(project.get("selected_concept_id"))
        has_character_lock = bool(character_lock.get("approved_asset_id")) or concept_path_ready
        has_key_pose_set = bool(key_pose_set.get("approved_run_id")) or concept_path_ready
        has_qa = bool(project.get("qa_report"))
        has_export = bool(project.get("last_export"))

        complete_map = {
            "project": True,
            "brief": has_brief,
            "references": has_references,
            "concepts": has_concepts,
            "review": has_review,
            "rig_layout": has_character_lock,
            "part_manifest": has_key_pose_set,
            "part_shape_edit": has_key_pose_set,
            "split_build": has_key_pose_set,
            "split_review": has_key_pose_set,
            "sprite_model": has_key_pose_set,
            "rig": has_key_pose_set,
            "clips": pixellab_clips_complete,
            "qa": has_qa,
            "export": has_export,
        }
        if pixellab_brief:
            complete_map["animations"] = pixellab_animations_step_complete(project, project_dir)
        clips_blocker_msg = (
            "Approve a chosen concept before creating a Pixel Lab character."
            if pixellab_brief
            else "Approve a Key Pose Board before running Motion Workflow."
        )
        qa_blocker_msg = (
            "Complete the Animations step (idle + walk) before running checks."
            if pixellab_brief
            else "Approve cleaned idle and walk outputs before running Cleanup & QA."
        )
        blocking_reasons = {
            "brief": [] if complete_map["project"] else ["Create or open a project first."],
            "references": [] if complete_map["brief"] else ["Save the character description before adding or skipping references."],
            "concepts": [] if complete_map["brief"] else ["Save the character description before building a concept prompt."],
            "review": [] if valid_attempts else ["Generate or import at least one valid concept before approving a look."],
            "rig_layout": [] if complete_map["review"] else (
                ["Approve a source concept before the Character step."]
                if pixellab_brief
                else ["Approve a source concept before Motion Workflow."]
            ),
            "part_manifest": [] if complete_map["rig_layout"] else (
                ["Complete the prior step before creating a Pixel Lab character."]
                if pixellab_brief
                else ["Complete the prior step before running motion."]
            ),
            "part_shape_edit": [],
            "split_build": [],
            "split_review": [],
            "sprite_model": [],
            "rig": [],
            "clips": [] if complete_map["part_manifest"] else [clips_blocker_msg],
            "qa": (
                []
                if (complete_map["clips"] and (not pixellab_brief or complete_map.get("animations")))
                else [qa_blocker_msg]
            ),
            "export": [] if complete_map["qa"] and project.get("qa_report", {}).get("status") == "pass" else ["Checks must pass before export."],
        }
        if pixellab_brief:
            blocking_reasons["animations"] = (
                [] if complete_map["clips"] else ["Approve the Pixel Lab character before generating animations."]
            )
        step_statuses: Dict[str, str] = {}
        active_step = None
        for step in wizard_steps_active(project):
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
                step_statuses["export"] = "locked"
                blocking_reasons["export"] = ["QA must pass before export."]
        recommended_next_step = active_step or "export"
        persisted_step = wizard_state.get("current_step")
        persisted_ok = persisted_step in WIZARD_STEPS_KNOWN and step_statuses.get(persisted_step) in {"active", "ready", "attention"}
        if persisted_ok:
            recommended_next_step = persisted_step
        wizard_state["current_step"] = persisted_step if persisted_ok else recommended_next_step
        for step_name, completed_flag in complete_map.items():
            if completed_flag:
                wizard_state = set_wizard_step_complete(wizard_state, step_name)
        can_resume_wizard = recommended_next_step != "export" or step_statuses.get("export") != "complete"
        return {
            "wizard_state": wizard_state,
            "recommended_next_step": recommended_next_step,
            "step_statuses": step_statuses,
            "blocking_reasons": blocking_reasons,
            "can_resume_wizard": can_resume_wizard,
        }

    has_brief = "brief" in completed or bool((project.get("prompt_text") or "").strip())
    # References are optional in the guided flow. Once the brief exists, the
    # step should not remain the "active" blocker forever just because the
    # user chose not to add any.
    has_references = bool(brief.get("references")) or "references" in completed or "references" in skipped or has_brief
    has_concepts = bool(project.get("prompt_history")) or bool(imported_attempts)
    has_review = bool(project.get("selected_concept_id"))
    has_rig_layout = (bool(project.get("rig_layout")) and bool(project.get("rig_layout_approved"))) or external_enabled
    has_part_manifest = (bool(project.get("part_manifest")) and bool(project.get("part_manifest_approved"))) or external_enabled
    has_part_shapes = (bool(project.get("part_shapes")) and bool(project.get("part_shapes_approved"))) or external_enabled
    has_part_split = bool(project.get("part_split")) or external_enabled
    has_split_build = bool(project.get("part_split")) or external_enabled
    has_split_review = bool(project.get("part_split_approved")) or external_enabled
    has_sprite_model = bool(project.get("sprite_model")) or external_enabled
    has_rig = bool(project.get("rig_review_approved")) or external_enabled
    has_clips = (animation_render_complete(project_dir, "idle") and animation_render_complete(project_dir, "walk")) or has_external_bundle
    has_qa = bool(project.get("qa_report"))
    has_export = bool(project.get("last_export"))

    complete_map = {
        "project": True,
        "brief": has_brief,
        "references": has_references,
        "concepts": has_concepts,
        "review": has_review,
        "rig_layout": has_rig_layout,
        "part_manifest": has_part_manifest or has_part_split,
        "part_shape_edit": has_part_shapes or has_part_split,
        "split_build": has_split_build,
        "split_review": has_split_review,
        "sprite_model": has_sprite_model,
        "rig": has_rig,
        "clips": has_clips,
        "qa": has_qa,
        "export": has_export,
    }

    blocking_reasons = {
        "brief": [] if complete_map["project"] else ["Create or open a project first."],
        "references": [] if complete_map["brief"] else ["Save the character description before adding or skipping references."],
        "concepts": [] if complete_map["brief"] else ["Save the character description before building a concept prompt."],
        "review": [] if valid_attempts else ["Generate or import at least one valid concept before choosing one to approve."],
        "rig_layout": [] if complete_map["review"] else ["Approve a source concept before defining the rig layout."],
        "part_manifest": [] if complete_map["rig_layout"] else ["Generate and approve the rig layout before configuring the part manifest."],
        "part_shape_edit": [] if complete_map["part_manifest"] else ["Approve the part manifest before editing part shapes."],
        "split_build": [] if complete_map["part_shape_edit"] else ["Approve the part shapes before building split assets."],
        "split_review": [] if complete_map["split_build"] else ["Build split assets before reviewing them."],
        "sprite_model": [] if complete_map["split_review"] else ["Approve the part split before building the sprite model."],
        "rig": [] if complete_map["sprite_model"] else ["Build and review the sprite model before rigging."],
        "clips": [] if complete_map["rig"] else ["Approve the rig before building clips."],
        "qa": [] if complete_map["clips"] else ["Render idle and walk before running checks, or import a SkelForm bundle."],
        "export": [] if complete_map["qa"] and project.get("qa_report", {}).get("status") == "pass" else ["Checks must pass before export."],
    }
    if external_enabled:
        blocking_reasons["clips"] = [] if complete_map["review"] else ["Accept a Codex-valid concept before opening SkelForm authoring."]
        blocking_reasons["qa"] = [] if complete_map["clips"] else ["Import a SkelForm export bundle before running checks."]

    step_statuses: Dict[str, str] = {}
    active_step = None
    for step in wizard_steps_active(project):
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
    persisted_ok = persisted_step in WIZARD_STEPS_KNOWN and step_statuses.get(persisted_step) in {"active", "ready", "attention"}
    if persisted_ok:
        recommended_next_step = persisted_step

    wizard_state["current_step"] = persisted_step if persisted_ok else recommended_next_step
    if has_brief:
        wizard_state = set_wizard_step_complete(wizard_state, "brief")
    if has_references and "references" not in skipped:
        wizard_state = set_wizard_step_complete(wizard_state, "references")
    if has_concepts:
        wizard_state = set_wizard_step_complete(wizard_state, "concepts")
    if has_review:
        wizard_state = set_wizard_step_complete(wizard_state, "review")
    if has_rig_layout:
        wizard_state = set_wizard_step_complete(wizard_state, "rig_layout")
    if has_part_manifest or has_part_split:
        wizard_state = set_wizard_step_complete(wizard_state, "part_manifest")
    if has_part_shapes or has_part_split:
        wizard_state = set_wizard_step_complete(wizard_state, "part_shape_edit")
    if has_part_split:
        wizard_state = set_wizard_step_complete(wizard_state, "split_build")
    if has_split_review:
        wizard_state = set_wizard_step_complete(wizard_state, "split_review")
    if has_sprite_model:
        wizard_state = set_wizard_step_complete(wizard_state, "sprite_model")
    if has_rig:
        wizard_state = set_wizard_step_complete(wizard_state, "rig")
    if has_clips:
        wizard_state = set_wizard_step_complete(wizard_state, "clips")
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
            "description": "Concept work is now a Gemini import loop with server-side normalization and Gemini validation on every imported image.",
        },
        "sprite_model": {
            "label": "Sprite Model",
            "maturity": "experimental",
            "description": "The tool extracts canonical layered parts directly from the accepted concept source image and stores deterministic edit history.",
        },
        "rig_review": {
            "label": "Set Up Motion",
            "maturity": "experimental",
            "description": "Rigging now binds extracted sprite-model parts instead of procedural placeholders.",
        },
        "production": {
            "label": "Build Animations",
            "maturity": "real",
            "description": "Idle and walk clips are rendered deterministically from the rigged sprite model with no AI frame generation.",
        },
        "qa": {
            "label": "Checks",
            "maturity": "experimental",
            "description": "QA enforces implemented structural checks for deterministic assets and blocks export on failure.",
        },
        "export": {
            "label": "Export",
            "maturity": "experimental",
            "description": "Exports package the deterministic sprite sheet, frames, metadata, and preview from the real sprite-model path.",
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
            # Pixel Lab scaffold parameters.
            "outline_style": DEFAULT_OUTLINE_STYLE,
            "shading_style": DEFAULT_SHADING_STYLE,
            "detail_level": DEFAULT_DETAIL_LEVEL,
            "canvas_size": DEFAULT_CANVAS_SIZE,
            "character_template": DEFAULT_CHARACTER_TEMPLATE,
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
        # Pixel Lab scaffold parameters.
        "outline_style": DEFAULT_OUTLINE_STYLE,
        "shading_style": DEFAULT_SHADING_STYLE,
        "detail_level": DEFAULT_DETAIL_LEVEL,
        "canvas_size": DEFAULT_CANVAS_SIZE,
        "character_template": DEFAULT_CHARACTER_TEMPLATE,
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
        # Prompt scaffold style parameters.
        "outline_style": source.get("outline_style") or defaults.get("outline_style") or DEFAULT_OUTLINE_STYLE,
        "shading_style": source.get("shading_style") or defaults.get("shading_style") or DEFAULT_SHADING_STYLE,
        "detail_level": source.get("detail_level") or defaults.get("detail_level") or DEFAULT_DETAIL_LEVEL,
        "canvas_size": coerce_canvas_size(source.get("canvas_size") if "canvas_size" in source else None, DEFAULT_CANVAS_SIZE),
        "character_template": source.get("character_template") or defaults.get("character_template") or DEFAULT_CHARACTER_TEMPLATE,
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
            "reference_kind": item.get("reference_kind"),
            "reference_warning": item.get("reference_warning"),
            "usable_for_concepts": item.get("usable_for_concepts"),
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


def _brief_pixel_lab_style(brief: Dict[str, Any]) -> Dict[str, str]:
    """Maps user-friendly brief style choices into Pixel Lab string values."""
    user_outline, pixel_outline = pick_mapped_style(
        OUTLINE_STYLE_MAP,
        brief.get("outline_style"),
        DEFAULT_OUTLINE_STYLE,
    )
    user_shading, pixel_shading = pick_mapped_style(
        SHADING_STYLE_MAP,
        brief.get("shading_style"),
        DEFAULT_SHADING_STYLE,
    )
    user_detail, pixel_detail = pick_mapped_style(
        DETAIL_LEVEL_MAP,
        brief.get("detail_level"),
        DEFAULT_DETAIL_LEVEL,
    )
    user_template, pixel_template = pick_mapped_style(
        CHARACTER_TEMPLATE_MAP,
        brief.get("character_template"),
        DEFAULT_CHARACTER_TEMPLATE,
    )

    return {
        "outline_style_user": user_outline,
        "shading_style_user": user_shading,
        "detail_level_user": user_detail,
        "character_template_user": user_template,
        "outline_style_pixel_lab": pixel_outline,
        "shading_style_pixel_lab": pixel_shading,
        "detail_level_pixel_lab": pixel_detail,
        "character_template_pixel_lab": pixel_template,
    }


def build_concept_prompt(brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministically scaffold the prompt + Pixel Lab params for *concept generation*.

    Output shape includes:
    - display_prompt: copyable prompt (includes DEBUG CONSTRAINTS section)
    - pixellab_params: params suitable for `PixelLabClient.create_image_pixflux(...)`
    - debug_constraints: machine-readable summary (also injected into display_prompt)
    """
    style = _brief_pixel_lab_style(brief)
    canvas_size = coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE)
    description = str(brief.get("raw_prompt") or "").strip() or str(brief.get("description") or "").strip() or str(brief.get("prompt_text") or "").strip()

    # Keep Pixel Lab description free of debug text; the UI can show debug separately.
    pixellab_description = "\n".join(
        [
            "Create exactly one full-body 2D side-view pixel art character concept.",
            "Facing: right (east), strict orthographic side profile.",
            "Background: plain single flat color background only; no environment and no ground.",
            "Framing: full body visible, centered, animation-friendly proportions.",
            "",
            "CHARACTER:",
            f"- Role: {brief.get('role_archetype','')}",
            f"- Description: {description}",
            f"- Silhouette: {brief.get('silhouette_intent','')}",
            f"- Outfit/Materials: {brief.get('outfit_materials','')}",
            f"- Held Item: {brief.get('prop','')}",
            f"- Shape Language: {brief.get('shape_language','')}",
            f"- Mood/Tone: {brief.get('mood_tone','')}",
            f"- Palette: {brief.get('palette_mood','')}",
            "",
            "STYLE (pixel art):",
            f"- Outline: {style['outline_style_pixel_lab']}",
            f"- Shading: {style['shading_style_pixel_lab']}",
            f"- Detail: {style['detail_level_pixel_lab']}",
            f"- Template: {style['character_template_pixel_lab']}",
            "",
            "TECHNICAL REQUIREMENTS (tool-enforced):",
            f"- Output size: {canvas_size}x{canvas_size} pixels",
            "- Single character only, no text, no watermark, no UI elements.",
            "- No front view / 3/4 view / top-down view.",
        ]
    )

    debug_constraints = {
        "orientation": {"view": "side", "direction": "east", "facing": "right"},
        "canvas_size": {"width": canvas_size, "height": canvas_size},
        "background_rule": "plain flat color only; no environment; output must be transparent-ready via Pixel Lab no_background",
        "style_mapping": {
            "outline_style_user": style["outline_style_user"],
            "outline_style_pixel_lab": style["outline_style_pixel_lab"],
            "shading_style_user": style["shading_style_user"],
            "shading_style_pixel_lab": style["shading_style_pixel_lab"],
            "detail_level_user": style["detail_level_user"],
            "detail_level_pixel_lab": style["detail_level_pixel_lab"],
            "character_template_user": style["character_template_user"],
            "character_template_pixel_lab": style["character_template_pixel_lab"],
        },
        "pixel_lab_endpoint": "POST /v1/generate-image-pixflux",
    }

    display_prompt = pixellab_description + "\n\n" + "\n".join(
        [
            "DEBUG CONSTRAINTS (tool-enforced):",
            f"- Orientation: view={debug_constraints['orientation']['view']}, direction={debug_constraints['orientation']['direction']}",
            f"- Canvas: {debug_constraints['canvas_size']['width']}x{debug_constraints['canvas_size']['height']}",
            f"- Background rule: {debug_constraints['background_rule']}",
            "- Style mapping:",
            f"  - outline: {style['outline_style_user']} -> {style['outline_style_pixel_lab']}",
            f"  - shading: {style['shading_style_user']} -> {style['shading_style_pixel_lab']}",
            f"  - detail: {style['detail_level_user']} -> {style['detail_level_pixel_lab']}",
            f"  - template: {style['character_template_user']} -> {style['character_template_pixel_lab']}",
        ]
    )

    seed = stable_int(
        "concept",
        str(brief.get("project_hint") or ""),
        str(brief.get("role_archetype") or ""),
        str(brief.get("silhouette_intent") or ""),
        str(brief.get("outfit_materials") or ""),
        str(brief.get("prop") or ""),
        str(brief.get("palette_mood") or ""),
        str(brief.get("shape_language") or ""),
        str(brief.get("mood_tone") or ""),
        str(brief.get("outline_style") or ""),
        str(brief.get("shading_style") or ""),
        str(brief.get("detail_level") or ""),
        str(canvas_size),
        mod=4_294_967_295,
    )

    pixellab_params = {
        "description": pixellab_description,
        "image_size": {"width": canvas_size, "height": canvas_size},
        "view": "side",
        "direction": "east",
        "no_background": True,
        "outline": style["outline_style_pixel_lab"],
        "shading": style["shading_style_pixel_lab"],
        "detail": style["detail_level_pixel_lab"],
        "seed": seed,
    }

    return {
        "display_prompt": display_prompt,
        "pixellab_params": pixellab_params,
        "debug_constraints": debug_constraints,
    }


def _build_element_inpaint_mask(element: str, canvas_size: int) -> Tuple[Image.Image, List[Dict[str, int]]]:
    """
    Returns (mask_image, debug_boxes) for inpaint-v3.
    mask: 'L' mode with 255 in the region to edit.
    """
    from PIL import ImageDraw

    w = canvas_size
    h = canvas_size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    # Boxes are heuristic pixel-aligned regions in the 64x64 canvas.
    # The goal is determinism + "good enough" targeting before more advanced segmentation exists.
    boxes: List[Dict[str, int]] = []

    def rect(x0: int, y0: int, x1: int, y1: int):
        draw.rectangle((x0, y0, x1, y1), fill=255)
        boxes.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1})

    element = element.strip().lower()
    if element in {"outfit", "outfit/materials", "costume"}:
        rect(int(w * 0.22), int(h * 0.28), int(w * 0.78), int(h * 0.82))  # torso + legs
        rect(int(w * 0.14), int(h * 0.28), int(w * 0.36), int(h * 0.55))  # left arm area
        rect(int(w * 0.64), int(h * 0.28), int(w * 0.86), int(h * 0.55))  # right arm area
    elif element in {"weapon/prop", "prop", "weapon", "held item"}:
        rect(int(w * 0.48), int(h * 0.38), int(w * 0.96), int(h * 0.78))
    elif element in {"palette/colors", "palette", "colors"}:
        rect(int(w * 0.16), int(h * 0.10), int(w * 0.84), int(h * 0.88))  # whole character
    elif element in {"pose"}:
        rect(int(w * 0.18), int(h * 0.14), int(w * 0.82), int(h * 0.88))  # character body area
    elif element in {"silhouette"}:
        rect(int(w * 0.14), int(h * 0.08), int(w * 0.86), int(h * 0.92))  # full silhouette area
    elif element in {"hair/head", "hair", "head"}:
        rect(int(w * 0.20), int(h * 0.04), int(w * 0.80), int(h * 0.42))
    elif element in {"accessories"}:
        rect(int(w * 0.20), int(h * 0.18), int(w * 0.80), int(h * 0.62))  # mid accessory band
        rect(int(w * 0.26), int(h * 0.00), int(w * 0.74), int(h * 0.28))  # crown area
    elif element in {"expression"}:
        rect(int(w * 0.30), int(h * 0.14), int(w * 0.70), int(h * 0.26))  # face / eyes region
    elif element in {"proportions"}:
        rect(int(w * 0.14), int(h * 0.10), int(w * 0.86), int(h * 0.90))
    else:
        # Fallback: edit whole character.
        rect(int(w * 0.16), int(h * 0.08), int(w * 0.84), int(h * 0.92))

    return mask, boxes


def _encode_png_base64(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def build_iteration_prompt(
    brief: Dict[str, Any],
    element: str,
    change_text: str,
    *,
    source_concept_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Deterministically scaffold *targeted concept iteration* using inpaint-v3.
    """
    element = (element or "").strip()
    change_text = (change_text or "").strip()
    if not element:
        raise ValueError("Iteration requires 'element'.")
    if not change_text:
        raise ValueError("Iteration requires 'change_text'.")

    allowed_elements = {
        "outfit",
        "weapon/prop",
        "palette/colors",
        "pose",
        "silhouette",
        "hair/head",
        "accessories",
        "expression",
        "proportions",
    }
    if element not in allowed_elements:
        raise ValueError("Invalid element. Must be one of: %s" % ", ".join(sorted(allowed_elements)))

    style = _brief_pixel_lab_style(brief)
    canvas_size = coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE)
    description = str(brief.get("raw_prompt") or "").strip() or str(brief.get("description") or "").strip()

    pixellab_description = "\n".join(
        [
            "Inpaint-edit a single 2D side-view pixel art character concept.",
            "Facing: right (east), strict orthographic side profile.",
            "Background: plain flat color only; no environment; preserve transparency-ready look.",
            "",
            "CURRENT CHARACTER (must remain recognizable):",
            f"- Role: {brief.get('role_archetype','')}",
            f"- Description: {description}",
            f"- Silhouette: {brief.get('silhouette_intent','')}",
            f"- Outfit/Materials: {brief.get('outfit_materials','')}",
            f"- Held Item: {brief.get('prop','')}",
            f"- Shape Language: {brief.get('shape_language','')}",
            f"- Mood/Tone: {brief.get('mood_tone','')}",
            f"- Palette: {brief.get('palette_mood','')}",
            "",
            "STYLE (pixel art):",
            f"- Outline: {style['outline_style_pixel_lab']}",
            f"- Shading: {style['shading_style_pixel_lab']}",
            f"- Detail: {style['detail_level_pixel_lab']}",
            f"- Template: {style['character_template_pixel_lab']}",
            "",
            "ITERATION:",
            f"- Element to change: {element}",
            f"- Specific change: {change_text}",
            "- Constraints: Keep ALL other visual elements unchanged except where the edit naturally affects continuity.",
            "- Maintain the same style, palette, and proportions unless explicitly changed by the request.",
        ]
    )

    # Mask + base64 are required for inpaint.
    if source_concept_path is None:
        raise ValueError("Iteration scaffolding requires source_concept_path for inpaint-v3.")
    if not isinstance(source_concept_path, Path):
        raise ValueError("source_concept_path must be a Path.")
    if not source_concept_path.exists():
        raise ValueError("source_concept_path does not exist: %s" % str(source_concept_path))

    with Image.open(source_concept_path) as loaded:
        rgba = loaded.convert("RGBA")
        # Deterministic center-square crop so mask and inpainting align.
        side = min(rgba.size[0], rgba.size[1])
        left = (rgba.size[0] - side) // 2
        top = (rgba.size[1] - side) // 2
        cropped = rgba.crop((left, top, left + side, top + side))
        resized = cropped.resize((canvas_size, canvas_size), resample=Image.Resampling.NEAREST)
        inpainting_image_b64 = _encode_png_base64(resized)

    mask_img, boxes = _build_element_inpaint_mask(element, canvas_size)
    mask_image_b64 = _encode_png_base64(mask_img)

    seed = stable_int(
        "iteration",
        str(brief.get("role_archetype") or ""),
        str(brief.get("silhouette_intent") or ""),
        str(brief.get("outfit_materials") or ""),
        str(brief.get("prop") or ""),
        str(brief.get("palette_mood") or ""),
        str(brief.get("shape_language") or ""),
        str(brief.get("mood_tone") or ""),
        str(style.get("outline_style_user") or ""),
        str(style.get("shading_style_user") or ""),
        str(style.get("detail_level_user") or ""),
        str(canvas_size),
        element,
        change_text,
        mod=4_294_967_295,
    )

    debug_constraints = {
        "orientation": {"view": "side", "direction": "east", "facing": "right"},
        "canvas_size": {"width": canvas_size, "height": canvas_size},
        "style_mapping": {
            "outline_style_user": style["outline_style_user"],
            "outline_style_pixel_lab": style["outline_style_pixel_lab"],
            "shading_style_user": style["shading_style_user"],
            "shading_style_pixel_lab": style["shading_style_pixel_lab"],
            "detail_level_user": style["detail_level_user"],
            "detail_level_pixel_lab": style["detail_level_pixel_lab"],
        },
        "inpaint": {
            "element": element,
            "mask_boxes": boxes,
            "strategy": "heuristic deterministic rectangles in canvas space",
            "pixel_lab_endpoint": "POST /v2/inpaint-v3",
        },
    }

    display_prompt = pixellab_description + "\n\n" + "\n".join(
        [
            "DEBUG CONSTRAINTS (tool-enforced):",
            f"- Orientation: view=side, direction=east",
            f"- Canvas: {canvas_size}x{canvas_size}",
            f"- Inpaint element: {element}",
            f"- Mask boxes: {boxes}",
            f"- Style mapping: outline={style['outline_style_user']} shading={style['shading_style_user']} detail={style['detail_level_user']}",
        ]
    )

    pixellab_params = {
        "description": pixellab_description,
        "inpainting_image_b64": inpainting_image_b64,
        "mask_image_b64": mask_image_b64,
        "image_size": {"width": canvas_size, "height": canvas_size},
        "no_background": True,
        "crop_to_mask": True,
        "seed": seed,
    }

    return {
        "display_prompt": display_prompt,
        "pixellab_params": pixellab_params,
        "debug_constraints": debug_constraints,
    }


def _find_first_base64_png_like(payload: Any) -> Optional[str]:
    """
    Heuristically extracts a base64-encoded PNG image from a nested JSON payload.

    Pixel Lab can return different shapes; for Phase 3 we primarily need a stable
    way to support their image outputs without hard-coding one exact schema.
    """
    # Fast path for common fields.
    if isinstance(payload, dict):
        for key in ("image_base64", "image", "image_b64", "imageB64", "b64", "base64"):
            if key in payload:
                candidate = payload.get(key)
                if isinstance(candidate, str):
                    return candidate
                if isinstance(candidate, dict):
                    for subkey in ("base64", "b64", "data"):
                        v = candidate.get(subkey)
                        if isinstance(v, str):
                            return v

    # Recursive walk.
    if isinstance(payload, dict):
        for value in payload.values():
            found = _find_first_base64_png_like(value)
            if found:
                return found
        return None
    if isinstance(payload, list):
        for value in payload:
            found = _find_first_base64_png_like(value)
            if found:
                return found
        return None
    if isinstance(payload, str):
        s = payload.strip()
        # Accept data URIs.
        if "base64," in s:
            s = s.split("base64,", 1)[1].strip()
        # PNG base64 usually starts with iVBORw0...
        if s.startswith("iVBORw0") and len(s) > 2000:
            return payload
    return None


def _decode_base64_to_bytes_loose(value: str) -> bytes:
    """Decode base64 with whitespace stripped and padding fixed (Pixel Lab / browsers vary)."""
    t = str(value).strip()
    if "base64," in t:
        t = t.split("base64,", 1)[1].strip()
    t = re.sub(r"\s+", "", t)
    pad = (-len(t)) % 4
    if pad:
        t += "=" * pad
    return base64.b64decode(t, validate=False)


def _try_pixellab_raw_packed_pixels(
    raw: bytes,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Optional[Image.Image]:
    """
    Pixel Lab sometimes returns raw packed pixels (no PNG/WebP header), e.g. 64×64×4 = 16384 bytes RGBA.
    """
    n = len(raw)
    if width is not None and height is not None:
        w, h = int(width), int(height)
        if w > 0 and h > 0:
            if n == w * h * 4:
                try:
                    return Image.frombytes("RGBA", (w, h), raw)
                except Exception:
                    return None
            if n == w * h * 3:
                try:
                    return Image.frombytes("RGB", (w, h), raw).convert("RGBA")
                except Exception:
                    return None
        return None
    if n % 4 != 0:
        return None
    px = n // 4
    side = math.isqrt(px)
    if side * side != px or side < 8 or side > 4096:
        return None
    try:
        return Image.frombytes("RGBA", (side, side), raw)
    except Exception:
        return None


def _pixellab_open_image_bytes(
    raw: bytes,
    *,
    where: str,
    rgba_size: Optional[Tuple[int, int]] = None,
) -> Image.Image:
    """
    Open image bytes from Pixel Lab (PNG/WebP/JPEG, or raw packed RGB/RGBA matching the canvas).
    ``rgba_size`` is (width, height) when the API may return raw pixels for that canvas.
    """
    if not raw:
        raise ValueError("Empty image payload %s" % where)
    head = raw[: min(24, len(raw))]
    if raw[:1] in (b"{", b"["):
        snippet = raw[:400].decode("utf-8", "replace")
        raise ValueError("Expected image %s but received JSON/text: %s" % (where, snippet))
    lower = raw[:32].lower()
    if lower.startswith(b"<!doctype") or lower.startswith(b"<html"):
        snippet = raw[:400].decode("utf-8", "replace")
        raise ValueError("Expected image %s but received HTML (wrong URL or auth?): %s" % (where, snippet))
    try:
        with Image.open(io.BytesIO(raw)) as loaded:
            return loaded.convert("RGBA")
    except Exception:
        pass
    if rgba_size:
        unpacked = _try_pixellab_raw_packed_pixels(raw, width=rgba_size[0], height=rgba_size[1])
        if unpacked is not None:
            return unpacked
    unpacked = _try_pixellab_raw_packed_pixels(raw)
    if unpacked is not None:
        return unpacked
    try:
        with Image.open(io.BytesIO(raw)) as loaded:
            return loaded.convert("RGBA")
    except Exception as exc:
        raise ValueError(
            "Cannot identify image file %s (%d bytes, starts with %r). "
            "Not a known image container and not raw RGBA/RGB for the expected canvas %s: %s"
            % (where, len(raw), head, rgba_size or "(try square infer)", exc)
        ) from exc


def _decode_base64_image_to_rgba(
    image_b64: str,
    *,
    rgba_size: Optional[Tuple[int, int]] = None,
) -> Image.Image:
    """
    Decode base64 image into RGBA PIL image.
    ``rgba_size`` matches the workbench canvas when Pixel Lab returns raw packed RGBA (no PNG header).
    """
    raw = _decode_base64_to_bytes_loose(image_b64)
    return _pixellab_open_image_bytes(raw, where="(base64 image)", rgba_size=rgba_size)


def _normalize_pixellab_image_base64(value: Any) -> Optional[str]:
    """Normalize Pixel Lab Base64Image objects or data-URI strings to raw base64 text."""
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if "base64," in s:
            s = s.split("base64,", 1)[1].strip()
        s = re.sub(r"\s+", "", s)
        return s if len(s) > 12 else None
    if isinstance(value, dict):
        inner = value.get("base64") or value.get("b64") or value.get("data")
        if isinstance(inner, str):
            return _normalize_pixellab_image_base64(inner)
    return None


def _collect_nested_images_dict(payload: Any) -> Optional[Dict[str, Any]]:
    """Find a direction-keyed ``images`` map on the payload or nested job/result blobs."""
    if not isinstance(payload, dict):
        return None
    imgs = payload.get("images")
    if isinstance(imgs, dict) and imgs:
        return imgs
    for key in ("last_response", "result", "output", "data"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            found = _collect_nested_images_dict(nested)
            if found:
                return found
    return None


def _download_url_bytes(url: str, *, bearer: Optional[str] = None, timeout: int = 90) -> bytes:
    headers = {
        "User-Agent": "MV-sprite-workbench/1.0 (Pixel Lab asset fetch)",
        "Accept": "image/png,image/webp,image/jpeg,image/*;q=0.9,*/*;q=0.5",
    }
    if bearer:
        headers["Authorization"] = "Bearer %s" % bearer
    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _extract_pixellab_character_direction_image_bytes(
    result: Any,
    direction_list: List[str],
    *,
    client: Any,
) -> List[bytes]:
    """
    After async create-character completes, Pixel Lab returns either:
    - ``images``: {direction: Base64Image | data-URI str, ...}
    - or metadata (often ``character_id``) — then ``GET /v2/characters/{id}`` exposes ``rotation_urls``.

    Completed v2 jobs may still be wrapped as ``{last_response: {...}}`` if an older client returned
    the raw BackgroundJobResponse; unwrap here defensively.
    """
    if isinstance(result, dict) and isinstance(result.get("last_response"), dict) and result.get("last_response"):
        result = result["last_response"]

    images_block = _collect_nested_images_dict(result)
    if images_block:
        out: List[bytes] = []
        bearer = getattr(client, "api_key", None) if client is not None else None
        for d in direction_list:
            cell = images_block.get(d)
            raw_dir: Optional[bytes] = None
            if isinstance(cell, dict):
                u = cell.get("url") or cell.get("image_url") or cell.get("href") or cell.get("signed_url")
                if isinstance(u, str) and u.strip():
                    try:
                        raw_dir = _download_url_bytes(u.strip(), bearer=bearer)
                    except Exception:
                        raw_dir = None
            if raw_dir is None:
                b64s = _normalize_pixellab_image_base64(cell)
                if not b64s:
                    return []
                try:
                    raw_dir = _decode_base64_to_bytes_loose(b64s)
                except Exception:
                    return []
            out.append(raw_dir)
        if len(out) == len(direction_list):
            return out

    cid: Optional[str] = None
    if isinstance(result, dict):
        cid = result.get("character_id") or result.get("id")
        nested = result.get("result")
        if not cid and isinstance(nested, dict):
            cid = nested.get("character_id") or nested.get("id")
        lr = result.get("last_response")
        if not cid and isinstance(lr, dict):
            cid = lr.get("character_id") or lr.get("id")

    if cid and client is not None:
        try:
            detail = client.get_character(str(cid))
        except Exception:
            detail = {}
        urls = None
        if isinstance(detail, dict):
            urls = detail.get("rotation_urls") or detail.get("rotationUrls")
        if isinstance(urls, dict):
            bearer = getattr(client, "api_key", None)
            out2: List[bytes] = []
            for d in direction_list:
                u = urls.get(d)
                if not isinstance(u, str) or not u.strip():
                    return []
                try:
                    raw = _download_url_bytes(u.strip(), bearer=bearer)
                except Exception:
                    return []
                out2.append(raw)
            if len(out2) == len(direction_list):
                return out2

    return []


def debug_pixellab_concept_image(image_size: Dict[str, int], seed: Optional[int], label: str = "pixellab-debug") -> Image.Image:
    """
    Offline fallback that produces a stable transparent concept image.
    """
    width = int(image_size.get("width") or image_size.get("w") or 64)
    height = int(image_size.get("height") or image_size.get("h") or width)
    base = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)

    # Deterministic color selection from seed (or constant).
    s = int(seed or 0)
    r = (120 + (s % 120)) % 255
    g = (60 + ((s // 3) % 160)) % 255
    b = (80 + ((s // 7) % 140)) % 255
    accent = (r, g, b, 210)
    outline = (max(0, r - 40), max(0, g - 30), max(0, b - 30), 255)

    # Main silhouette-ish blob.
    pad = max(4, int(width * 0.12))
    draw.rounded_rectangle((pad, pad, width - pad, height - pad), radius=int(width * 0.25), fill=accent, outline=outline, width=max(2, width // 24))
    # Held-item hint.
    item_w = max(8, width // 5)
    item_h = max(10, height // 6)
    draw.rectangle((width - pad - item_w, height // 2 - item_h // 2, width - pad, height // 2 + item_h // 2), fill=(outline[0], outline[1], outline[2], 200))

    # Tiny label for human debugging (still within deterministic canvas).
    draw.text((pad, height - pad - 10), label[:6], fill=(235, 235, 235, 255))
    return base


def debug_pixellab_iterate_from_inpainting(inpainting_image_b64: str, seed: Optional[int]) -> Image.Image:
    """
    Offline fallback for inpaint iterations.
    """
    try:
        image = _decode_base64_image_to_rgba(inpainting_image_b64)
    except Exception:
        image = debug_pixellab_concept_image({"width": 64, "height": 64}, seed, label="iter")
    s = int(seed or 0)
    draw = ImageDraw.Draw(image)
    w, h = image.size
    # Add a deterministic “change marker” in a small corner.
    c = (
        (150 + (s % 105)) % 255,
        (70 + ((s // 4) % 140)) % 255,
        (90 + ((s // 11) % 120)) % 255,
        220,
    )
    draw.rectangle((w - w // 4, h - h // 4, w - 1, h - 1), fill=c)
    return image


def debug_pixellab_character_images(directions: List[str], canvas_size: int, seed: Optional[int]) -> Dict[str, Image.Image]:
    """
    Offline fallback producing one transparent-direction image per requested direction.
    """
    s = int(seed or 0)
    images: Dict[str, Image.Image] = {}
    for idx, direction in enumerate(directions):
        img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Deterministic per-direction colors.
        r = (80 + ((s + idx * 17) % 150)) % 255
        g = (50 + ((s + idx * 29) % 180)) % 255
        b = (70 + ((s + idx * 37) % 160)) % 255
        fill = (r, g, b, 215)
        outline = (max(0, r - 45), max(0, g - 35), max(0, b - 35), 255)

        pad = max(4, int(canvas_size * 0.10))
        draw.rounded_rectangle(
            (pad, pad, canvas_size - pad, canvas_size - pad),
            radius=max(4, int(canvas_size * 0.18)),
            fill=fill,
            outline=outline,
            width=max(2, canvas_size // 20),
        )

        # Direction marker helps humans confirm wiring.
        draw.text((pad + 2, pad + 2), direction[:3].upper(), fill=(235, 235, 235, 255))
        images[direction] = img

    return images


def debug_pixellab_skeleton_keypoints(canvas_size: int) -> List[List[float]]:
    """
    Offline fallback that returns 18 humanoid keypoints.

    Pixel Lab’s exact keypoint coordinate system is not documented in our repo yet,
    so for now we return deterministic pixel-space points (for tests and UI scaffolding).
    """
    w = float(canvas_size)
    h = float(canvas_size)

    # Create a simple, symmetric humanoid-ish layout.
    # Order corresponds to our `SkeletonLabel` enum in llms.txt (NOSE, NECK, ...).
    # This is a best-effort placeholder for offline pipeline testing.
    points: List[List[float]] = [
        [w * 0.50, h * 0.18],  # NOSE
        [w * 0.50, h * 0.28],  # NECK
        [w * 0.60, h * 0.28],  # RIGHT SHOULDER
        [w * 0.66, h * 0.38],  # RIGHT ELBOW
        [w * 0.70, h * 0.52],  # RIGHT ARM
        [w * 0.40, h * 0.28],  # LEFT SHOULDER
        [w * 0.34, h * 0.38],  # LEFT ELBOW
        [w * 0.30, h * 0.52],  # LEFT ARM
        [w * 0.54, h * 0.56],  # RIGHT HIP
        [w * 0.56, h * 0.70],  # RIGHT KNEE
        [w * 0.58, h * 0.86],  # RIGHT LEG
        [w * 0.46, h * 0.56],  # LEFT HIP
        [w * 0.44, h * 0.70],  # LEFT KNEE
        [w * 0.42, h * 0.86],  # LEFT LEG
        [w * 0.47, h * 0.20],  # RIGHT EYE (approx)
        [w * 0.53, h * 0.20],  # LEFT EYE (approx)
        [w * 0.44, h * 0.24],  # RIGHT EAR
        [w * 0.56, h * 0.24],  # LEFT EAR
    ]
    return points


def debug_pixellab_animation_frames(
    animation_name: str,
    direction: str,
    canvas_size: int,
    frame_count: int,
    seed: Optional[int],
    *,
    description_hint: Optional[str] = None,
) -> List[Image.Image]:
    """
    Offline fallback that produces stable synthetic animation frames.

    Frames are saved as transparent-background PNGs with deterministic colored
    rectangles and a small text label that includes the frame index.
    """
    s = int(seed or 0)
    safe_anim = (animation_name or "anim")[:10]
    safe_dir = (direction or "dir")[:10]
    hint = (description_hint or "").strip()[:10]

    frames: List[Image.Image] = []
    for i in range(int(frame_count)):
        img = Image.new("RGBA", (int(canvas_size), int(canvas_size)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        r = (90 + ((s + i * 17 + len(safe_dir)) % 150)) % 255
        g = (50 + ((s // 3 + i * 29) % 180)) % 255
        b = (70 + ((s // 7 + i * 37) % 160)) % 255
        fill = (r, g, b, 215)
        outline = (max(0, r - 45), max(0, g - 35), max(0, b - 35), 255)

        pad = max(4, int(canvas_size * 0.10))
        draw.rounded_rectangle(
            (pad, pad, canvas_size - pad, canvas_size - pad),
            radius=max(4, int(canvas_size * 0.18)),
            fill=fill,
            outline=outline,
            width=max(2, canvas_size // 20),
        )

        draw.text(
            (pad + 2, pad + 2),
            "%s %s %02d" % (safe_anim[:3], safe_dir[:3], i),
            fill=(235, 235, 235, 255),
        )
        if hint:
            draw.text((pad + 2, canvas_size - pad - 10), hint[:6], fill=(235, 235, 235, 255))

        frames.append(img)
    return frames


def _pixellab_character_approved_guard(project_dir: Path) -> Dict[str, Any]:
    """
    Phase 5 gating (carry-forward from 4.3):
    Require `pixellab_character_approved` (or legacy `approved`) to be true.
    """
    char_path = _pixellab_character_path(project_dir)
    if not char_path.exists():
        raise ValueError("pixellab_character.json is missing; create-character first.")
    char_data = load_json(char_path, None) or {}

    if isinstance(char_data, dict) and (char_data.get("pixellab_character_approved") is not None):
        approved = bool(char_data.get("pixellab_character_approved"))
    else:
        approved = bool((char_data or {}).get("approved"))

    if not approved:
        raise ValueError("Pixel Lab character approval is required (pixellab_character_approved=false).")
    return char_data if isinstance(char_data, dict) else {}


def _pixellab_animation_frames_dir(project_dir: Path, animation_name: str, direction: str) -> Path:
    # Phase 5: animations/<animation_name>/<direction>/frame_NN.png
    return project_dir / "animations" / animation_name / direction


def _pixellab_animation_frame_path(
    project_dir: Path,
    animation_name: str,
    direction: str,
    frame_index: int,
) -> Path:
    return _pixellab_animation_frames_dir(project_dir, animation_name, direction) / ("frame_%02d.png" % int(frame_index))


def _looks_like_base64_image_string(value: str) -> bool:
    """True if string looks like base64-encoded raster image (PNG / WebP / JPEG / GIF)."""
    s = str(value).strip()
    if "base64," in s:
        s = s.split("base64,", 1)[1].strip()
    s = re.sub(r"\s+", "", s)
    if len(s) < 40:
        return False
    return (
        s.startswith("iVBORw0")
        or s.startswith("UklGR")
        or s.startswith("/9j/")
        or s.startswith("R0lGOD")
    )


def _find_all_base64_png_like(payload: Any) -> List[str]:
    """
    Extract base64-encoded image strings from a nested Pixel Lab response.
    Accepts PNG, WebP, JPEG, GIF prefixes and v2 ``Base64Image`` objects (type=base64).
    """
    found: List[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            t = str(value.get("type") or "").lower()
            if t == "base64":
                inner = value.get("base64") or value.get("b64") or value.get("data")
                if isinstance(inner, str) and _looks_like_base64_image_string(inner):
                    found.append(inner.strip())
                return
            for v in value.values():
                walk(v)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if isinstance(value, str) and _looks_like_base64_image_string(value):
            found.append(value.strip())

    walk(payload)
    return list(dict.fromkeys(found))


def _collect_pixellab_https_asset_urls(payload: Any) -> List[str]:
    """Collect https URLs from nested job payloads (e.g. signed frame CDN links)."""
    urls: List[str] = []

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for key in ("url", "signed_url", "image_url", "href"):
                u = o.get(key)
                if isinstance(u, str) and (u.startswith("http://") or u.startswith("https://")):
                    urls.append(u.strip().split("#")[0])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(payload)
    return list(dict.fromkeys(urls))


def _pixellab_decode_single_animation_payload_to_frames(
    result: Any,
    *,
    canvas_size: int,
    client: Any,
) -> List[Image.Image]:
    """Decode frames from one job ``last_response`` blob (base64 and/or downloadable URLs)."""
    rgba: Tuple[int, int] = (int(canvas_size), int(canvas_size))
    decoded: List[Image.Image] = []
    for s in _find_all_base64_png_like(result):
        try:
            decoded.append(_decode_base64_image_to_rgba(s, rgba_size=rgba))
        except Exception:
            continue
    if decoded:
        return decoded
    bearer = getattr(client, "api_key", None) if client is not None else None
    for url in _collect_pixellab_https_asset_urls(result)[:128]:
        try:
            raw = _download_url_bytes(url, bearer=bearer)
            decoded.append(
                _pixellab_open_image_bytes(
                    raw,
                    where="Pixel Lab animation frame URL",
                    rgba_size=rgba,
                )
            )
        except Exception:
            continue
    return decoded


def _pixellab_animation_job_to_rgba_frames(
    result: Any,
    *,
    canvas_size: int,
    client: Any,
) -> List[Image.Image]:
    """
    Decode frames from a Pixel Lab animation result.

    Template ``/v2/characters/animations`` may return multiple background jobs; the client merges
    those into ``per_job_last_response`` in order (direction-major when aligned with API ``directions``).
    """
    if isinstance(result, dict):
        merged = result.get("per_job_last_response") or result.get("merged_last_responses")
        if isinstance(merged, list) and merged:
            out: List[Image.Image] = []
            for part in merged:
                out.extend(
                    _pixellab_decode_single_animation_payload_to_frames(
                        part,
                        canvas_size=canvas_size,
                        client=client,
                    )
                )
            if out:
                return out
    return _pixellab_decode_single_animation_payload_to_frames(
        result,
        canvas_size=canvas_size,
        client=client,
    )


def _pixellab_character_path(project_dir: Path) -> Path:
    return project_dir / "pixellab_character.json"


def pixellab_character_wizard_complete(project: Dict[str, Any], project_dir: Path) -> bool:
    """True when Pixel Lab character exists and is approved (project flags and/or JSON)."""
    if bool(project.get("pixellab_character_approved")):
        return True
    char_path = _pixellab_character_path(project_dir)
    if not char_path.exists():
        return False
    char_data = load_json(char_path, None) or {}
    if bool(char_data.get("pixellab_character_approved")):
        return True
    return bool(char_data.get("approved"))


def pixellab_missing_canonical_animation_clips(animations: Any) -> List[str]:
    """
    Canonical export/QA expects **idle** and **walk** in ``pixellab_animations.animations``,
    each with at least one direction listing non-empty ``frames``.
    Returns clip names still missing (empty list = ready for build-clips / wizard step).
    """
    required = ("idle", "walk")
    if not isinstance(animations, dict):
        return list(required)
    missing: List[str] = []
    for name in required:
        entry = animations.get(name)
        if not isinstance(entry, dict):
            missing.append(name)
            continue
        dirs = entry.get("directions")
        if not isinstance(dirs, dict) or not dirs:
            missing.append(name)
            continue
        has_frames = False
        for _d, data in dirs.items():
            if isinstance(data, dict):
                frames = data.get("frames")
                if isinstance(frames, list) and len(frames) > 0:
                    has_frames = True
                    break
        if not has_frames:
            missing.append(name)
    return missing


def pixellab_animations_step_complete(project: Dict[str, Any], project_dir: Path) -> bool:
    """Idle + walk each have at least one direction with frame paths in pixellab_animations."""
    store = project.get("pixellab_animations")
    if not isinstance(store, dict) or not isinstance(store.get("animations"), dict):
        store = _load_pixellab_animations_store(project_dir)
    anims = store.get("animations") if isinstance(store.get("animations"), dict) else {}
    return not pixellab_missing_canonical_animation_clips(anims)


def wizard_steps_active(project: Dict[str, Any]) -> List[str]:
    """
    Wizard step order. Legacy (non-AI or legacy_mode) uses full WIZARD_STEPS.
    Modern AI uses WIZARD_STEPS_AI (no rig_layout / part_manifest in UI).
    Pixel Lab AI projects insert `animations` after Character (`clips`).
    """
    ai_workflow = project.get("ai_workflow") or {}
    ai_enabled = bool(ai_workflow.get("enabled")) and not bool(ai_workflow.get("legacy_mode"))
    brief = project.get("brief") or {}
    pixellab_brief = str(brief.get("backend_mode") or "") == "pixellab"
    if ai_enabled:
        seq = list(WIZARD_STEPS_AI)
        if pixellab_brief:
            i = seq.index("clips") + 1
            seq = seq[:i] + [WIZARD_STEP_ANIMATIONS] + seq[i:]
        return seq
    return list(WIZARD_STEPS)


def _pixellab_skeleton_path(project_dir: Path) -> Path:
    return project_dir / "pixellab_skeleton.json"


def _pixellab_character_assets_dir(project_dir: Path) -> Path:
    return project_dir / "character"


def _pixellab_animations_path(project_dir: Path) -> Path:
    return project_dir / "pixellab_animations.json"


def _load_pixellab_animations_store(project_dir: Path) -> Dict[str, Any]:
    path = _pixellab_animations_path(project_dir)
    if not path.exists():
        return {"project_id": project_dir.name, "updated_at": now_iso(), "animations": {}}
    store = load_json(path, None) or {}
    if not isinstance(store, dict):
        store = {}
    store.setdefault("project_id", project_dir.name)
    store.setdefault("animations", {})
    store.setdefault("updated_at", now_iso())
    return store


def _save_pixellab_animations_store(project_dir: Path, store: Dict[str, Any]) -> None:
    path = _pixellab_animations_path(project_dir)
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")


def _infer_animation_name_from_template(template_animation_id: str) -> str:
    s = (template_animation_id or "").lower()
    if any(token in s for token in ["idle", "breathing"]):
        return "idle"
    if any(token in s for token in ["walk", "walking"]):
        return "walk"
    return "idle"


def _infer_frame_count_from_template(template_animation_id: str) -> Optional[int]:
    s = (template_animation_id or "").lower()
    for count in (8, 6, 4, 2, 1):
        # Matches patterns like "walking-8-frames" and "jumping-1".
        if ("-%d-frames" % count) in s or ("jumping-%d" % count) in s or ("-frames-%d" % count) in s:
            return count
    return None


def _resolve_animation_timing(
    animation_name: str,
    *,
    template_animation_id: Optional[str] = None,
    pixel_lab_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Decide fps/frame_count/loop for a generated animation.

    Design choice (from your earlier note):
    - Prefer values returned by Pixel Lab (if present),
    - Fall back to deterministic mapping from animation_name/template id.
    """
    loop = True
    fps = None
    frame_count = None

    if isinstance(pixel_lab_result, dict):
        raw_fps = pixel_lab_result.get("fps") or pixel_lab_result.get("frame_rate") or pixel_lab_result.get("frameRate")
        raw_fc = pixel_lab_result.get("frame_count") or pixel_lab_result.get("frameCount") or pixel_lab_result.get("frames_count")
        if raw_fps is not None:
            try:
                fps = int(raw_fps)
            except (TypeError, ValueError):
                fps = None
        if raw_fc is not None:
            try:
                frame_count = int(raw_fc)
            except (TypeError, ValueError):
                frame_count = None

    if fps is None:
        fps = (AI_CLIP_SPECS.get(animation_name) or ANIMATION_SPECS.get(animation_name) or {}).get("fps")
    if frame_count is None:
        frame_count = (AI_CLIP_SPECS.get(animation_name) or ANIMATION_SPECS.get(animation_name) or {}).get("frame_count")

    if frame_count is None and template_animation_id:
        frame_count = _infer_frame_count_from_template(template_animation_id)

    fps = int(fps or 12)
    frame_count = int(frame_count or 4)

    return {"fps": fps, "frame_count": frame_count, "loop": loop}


def _write_png_frames(frames: List[Image.Image], project_dir: Path, animation_name: str, direction: str) -> List[str]:
    frames_dir = _pixellab_animation_frames_dir(project_dir, animation_name, direction)
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_paths: List[str] = []
    for idx, img in enumerate(frames):
        path = frames_dir / ("frame_%02d.png" % int(idx))
        img.save(path)
        frame_paths.append(str(path.relative_to(project_dir)))
    return frame_paths


def _upsert_pixellab_animation_frames(
    project_dir: Path,
    store: Dict[str, Any],
    *,
    animation_name: str,
    direction: str,
    fps: int,
    frame_count: int,
    loop: bool,
    frames_paths: List[str],
    template_animation_id: Optional[str],
    backend_name: str,
    seed: Optional[int],
    job_id: Optional[str] = None,
    edited_description: Optional[str] = None,
) -> Dict[str, Any]:
    store.setdefault("animations", {})
    animations = store["animations"]
    anim = animations.get(animation_name) if isinstance(animations, dict) else None
    if not isinstance(anim, dict):
        anim = {}
    anim.update({
        "animation_name": animation_name,
        "fps": int(fps),
        "frame_count": int(frame_count),
        "loop": bool(loop),
        "backend_name": backend_name,
        "seed": seed,
        "template_animation_id": template_animation_id,
        "updated_at": now_iso(),
    })
    if job_id:
        anim["latest_job_id"] = job_id
    if edited_description:
        anim["latest_edited_description"] = edited_description

    anim.setdefault("directions", {})
    if isinstance(anim["directions"], dict):
        anim["directions"][direction] = {
            "frames": list(frames_paths),
            "frame_count": int(frame_count),
            "fps": int(fps),
            "updated_at": now_iso(),
        }
    animations[animation_name] = anim
    store["updated_at"] = now_iso()
    _save_pixellab_animations_store(project_dir, store)
    return anim


def build_identity_lock_lines(brief: Dict[str, Any]) -> List[str]:
    return [
        "Continuity lock: this must remain the same character between iterations, not a redesign.",
        "Keep these identity anchors fixed unless feedback explicitly asks to change them:",
        "- role/archetype: %s" % brief["role_archetype"],
        "- silhouette family: %s" % brief["silhouette_intent"],
        "- outfit/materials: %s" % brief["outfit_materials"],
        "- prop policy: %s" % brief["prop"],
        "- palette direction: %s" % brief["palette_mood"],
        "- shape language: %s" % brief["shape_language"],
        "- mood/tone: %s" % brief["mood_tone"],
        "Only change the minimum necessary details requested by the feedback. Preserve the same character identity, proportions, costume logic, silhouette family, and rendering intent.",
    ]


def summarize_iteration_feedback(brief: Dict[str, Any], feedback: Optional[str]) -> List[str]:
    text = (feedback or "").strip()
    if not text:
        return ["Make only minor polish-level improvements. Keep the same character, pose logic, costume, and silhouette."]
    lowered = text.lower()
    prop = str(brief.get("prop") or "").strip()
    instructions: List[str] = []
    if prop and any(token in lowered for token in ["missing", "absence", "absent", "not visible"]) and any(token in lowered for token in ["sword", "prop", "held item", "weapon"]):
        instructions.append("Add the required %s." % prop)
        instructions.append("Keep the %s clearly visible in the front/reading hand." % prop)
        instructions.append("Maintain strong negative space between the %s, hand, torso, and cape." % prop)
        instructions.append("Do not redesign the helmet, armor, body proportions, palette, or silhouette.")
        return instructions
    instructions.append(text)
    instructions.append("Keep all other character design decisions unchanged.")
    return instructions


def build_gemini_prompt(
    brief: Dict[str, Any],
    previous_prompt: Optional[str] = None,
    validation_feedback: Optional[str] = None,
    imported_attempt: Optional[Dict[str, Any]] = None,
) -> str:
    iteration_mode = bool(previous_prompt or imported_attempt)
    if iteration_mode:
        lines = [
            "Use the attached previous image as the direct reference.",
            "Edit or regenerate the same character, not a redesign.",
            "Keep the same side-view composition, same character identity, same costume logic, same proportions, same palette direction, and same silhouette family.",
            "Exactly one full-body humanoid character on a plain removable background.",
            "Strict orthographic side profile only.",
            "Do not change the character into a different knight or different costume interpretation.",
            "",
            "Keep these identity anchors fixed:",
            "- role/archetype: %s" % brief["role_archetype"],
            "- silhouette family: %s" % brief["silhouette_intent"],
            "- outfit/materials: %s" % brief["outfit_materials"],
            "- held item intent: %s" % brief["prop"],
            "- palette direction: %s" % brief["palette_mood"],
            "- shape language: %s" % brief["shape_language"],
            "- mood/tone: %s" % brief["mood_tone"],
            "",
            "Make only these corrections:",
            *["- %s" % item for item in summarize_iteration_feedback(brief, validation_feedback)],
            "",
            "Hard constraints:",
            "- one character only",
            "- full body visible",
            "- no front view, 3/4 view, top-down view, or dramatic camera angle",
            "- no background scene, no collage, no concept page, no turnaround, no sprite sheet, no multiple poses",
            "- do not crop head or feet",
            "- preserve low-resolution readability",
        ]
        return "\n".join(lines)
    lines = [
        "Create exactly one full-body side-view humanoid character concept for a 2D metroidvania sprite pipeline.",
        "Plain removable background only.",
        "Strict orthographic side profile only.",
        "Full body visible, centered, readable, and animation-friendly.",
        "",
        "Character brief:",
        "- role/archetype: %s" % brief["role_archetype"],
        "- silhouette family: %s" % brief["silhouette_intent"],
        "- outfit/materials: %s" % brief["outfit_materials"],
        "- held item: %s" % brief["prop"],
        "- palette direction: %s" % brief["palette_mood"],
        "- shape language: %s" % brief["shape_language"],
        "- mood/tone: %s" % brief["mood_tone"],
        "- readability constraints: %s" % brief["side_view_constraints"],
        "",
        "Composition requirements:",
        "- one character only",
        "- no background scene or environment storytelling",
        "- no front view, 3/4 view, top-down view, or dramatic camera angle",
        "- no action montage, no multiple poses, no turnaround, no sprite sheet, no collage, no concept page",
        "- do not crop head or feet",
        "- maintain clear negative space between head, torso, limbs, and held item",
        "- held item must read as a separate silhouette from the torso when present",
    ]
    return "\n".join(lines)


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
        "outline_style": payload.get("outline_style") or source.get("outline_style") or defaults["outline_style"],
        "shading_style": payload.get("shading_style") or source.get("shading_style") or defaults["shading_style"],
        "detail_level": payload.get("detail_level") or source.get("detail_level") or defaults["detail_level"],
        "canvas_size": coerce_canvas_size(payload.get("canvas_size") if "canvas_size" in payload else source.get("canvas_size") if "canvas_size" in source else None, DEFAULT_CANVAS_SIZE),
        "character_template": payload.get("character_template") or source.get("character_template") or defaults["character_template"],
        "backend_mode": payload.get("backend_mode") if payload.get("backend_mode") in BACKEND_MODES else (source.get("backend_mode") if source.get("backend_mode") in BACKEND_MODES and source.get("backend_mode") != "debug_procedural" else "pixellab"),
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


def analyze_reference_asset(path: Optional[Path], source_value: Optional[str] = None) -> Dict[str, Any]:
    name_bits = [str(source_value or "")]
    if path:
        name_bits.append(path.name)
        name_bits.append(path.stem)
    lowered_name = " ".join(name_bits).lower()
    if any(hint in lowered_name for hint in REFERENCE_SPRITESHEET_HINTS):
        return {
            "reference_kind": "sprite_sheet",
            "reference_warning": "Looks like a sprite or animation sheet. The concept generator will ignore it because it tends to produce layout-copy artifacts instead of usable concept art.",
            "usable_for_concepts": False,
        }

    if path and path.exists():
        try:
            with Image.open(path) as loaded:
                image = loaded.convert("RGBA")
            mask = detect_mask(image)
            component_count = mask_connected_components(mask)
            width, height = image.size
            aspect_ratio = width / max(height, 1)
            if width >= 384 and aspect_ratio >= 1.2 and component_count >= 8:
                return {
                    "reference_kind": "sprite_sheet",
                    "reference_warning": "This reference reads like a multi-frame sprite sheet. The concept generator will ignore it to avoid copying sheet structure into the concept board.",
                    "usable_for_concepts": False,
                }
        except Exception:
            pass

    return {
        "reference_kind": "illustration",
        "reference_warning": None,
        "usable_for_concepts": True,
    }


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

    analysis = analyze_reference_asset(output_path, source_value)

    return {
        "reference_id": reference_id,
        "role": role,
        "weight": weight,
        "source_type": source_type,
        "source_value": source_value,
        "local_path": str(output_path.relative_to(project_dir)),
        "added_at": now_iso(),
        "reference_kind": analysis["reference_kind"],
        "reference_warning": analysis["reference_warning"],
        "usable_for_concepts": analysis["usable_for_concepts"],
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


def prompt_history_entries(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entries = []
    for concept in concepts:
        if not concept.get("prompt_text"):
            continue
        entries.append({
            "concept_id": concept.get("concept_id"),
            "attempt_group_id": concept.get("attempt_group_id"),
            "attempt_index": concept.get("attempt_index"),
            "prompt_version": concept.get("prompt_version"),
            "prompt_source": concept.get("prompt_source"),
            "prompt_text": concept.get("prompt_text"),
            "prompt_file": concept.get("prompt_file"),
            "created_at": concept.get("created_at"),
            "validation_feedback": concept.get("validation_feedback"),
        })
    entries.sort(key=lambda item: (item.get("prompt_version") or 0, parse_iso(item.get("created_at"))), reverse=True)
    return entries


def hydrate_concept(concept: Dict[str, Any], fallback_created_at: Optional[str] = None) -> Dict[str, Any]:
    record = dict(concept or {})
    record.setdefault("concept_id", "")
    record.setdefault("run_id", record.get("lineage", {}).get("run_id") if isinstance(record.get("lineage"), dict) else "legacy")
    record.setdefault("run_kind", "legacy")
    record.setdefault("created_at", fallback_created_at or now_iso())
    record.setdefault("positive_prompt", record.get("prompt") or "")
    record.setdefault("prompt_text", record.get("prompt") or record.get("positive_prompt") or "")
    record.setdefault("prompt_version", 0)
    record.setdefault("prompt_source", "initial")
    record.setdefault("attempt_group_id", record.get("run_id") or "legacy")
    record.setdefault("attempt_index", 1)
    record.setdefault("import_source", None)
    record.setdefault("validation_status", "valid" if record.get("review_state", {}).get("approved") else "pending")
    record.setdefault("validation_feedback", None)
    validation_source = record.get("validation_source")
    if validation_source == "codex":
        validation_source = "gemini"
    elif validation_source == "codex_overridden":
        validation_source = "gemini_overridden"
    record.setdefault("validation_source", validation_source or "manual")
    record.setdefault("validation_updated_at", record.get("created_at"))
    record.setdefault("validation_error", None)
    record.setdefault("codex_review_summary", None)
    record.setdefault("codex_response_id", None)
    record.setdefault("accepted_for_review", bool(record.get("review_state", {}).get("approved")))
    record.setdefault("prompt_file", None)
    record.setdefault("negative_prompt", DEFAULT_NEGATIVE_PROMPT)
    record.setdefault("preview_image", "")
    record.setdefault("original_preview_image", record.get("preview_image") or "")
    record.setdefault("processed_preview_image", None)
    record.setdefault("postprocess_status", "not_needed")
    record.setdefault("postprocess_notes", None)
    record.setdefault("approved_source_image", record.get("processed_preview_image") or record.get("preview_image") or None)
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
    if record["review_state"]["approved"]:
        record["validation_status"] = "valid"
        record["accepted_for_review"] = True
        if not record.get("approved_source_image"):
            record["approved_source_image"] = record.get("processed_preview_image") or record.get("original_preview_image") or record.get("preview_image")
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
    if not record.get("original_preview_image") and record.get("preview_image"):
        record["original_preview_image"] = record["preview_image"]
    if not record.get("approved_source_image"):
        record["approved_source_image"] = record.get("processed_preview_image") or record.get("original_preview_image") or record.get("preview_image")
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


def next_prompt_version(concepts: List[Dict[str, Any]]) -> int:
    highest = 0
    for concept in concepts:
        highest = max(highest, int(concept.get("prompt_version") or 0))
    return highest + 1


def save_prompt_artifacts(project_dir: Path, prompt_version: int, prompt_text: str) -> Tuple[str, str]:
    prompts_dir = project_dir / "prompts"
    history_dir = prompts_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    latest_path = prompts_dir / "latest-gemini-prompt.txt"
    history_path = history_dir / ("prompt-v%03d.txt" % prompt_version)
    latest_path.write_text(prompt_text.strip() + "\n", encoding="utf-8")
    history_path.write_text(prompt_text.strip() + "\n", encoding="utf-8")
    return str(latest_path.relative_to(project_dir)), str(history_path.relative_to(project_dir))


def image_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
    return "data:%s;base64,%s" % (mime_type, base64.b64encode(path.read_bytes()).decode("ascii"))


def concept_validation_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "decision": {"type": "string", "enum": ["valid", "invalid"]},
            "summary": {"type": "string"},
            "feedback": {"type": "string"},
            "improved_gemini_prompt": {"type": ["string", "null"]},
            "master_pose_ready": {"type": "boolean"},
            "technical_requirements_ok": {"type": "boolean"},
        },
        "required": [
            "decision",
            "summary",
            "feedback",
            "improved_gemini_prompt",
            "master_pose_ready",
            "technical_requirements_ok",
        ],
    }


def safe_normalize_concept_image(source_path: Path, output_path: Path) -> Dict[str, Any]:
    source_image = ImageOps.exif_transpose(Image.open(source_path)).convert("RGBA")
    source_mask = largest_component_mask(detect_mask(source_image))
    bbox = source_mask.getbbox()
    if bbox is None:
        return {
            "status": "failed",
            "image_path": None,
            "notes": "Could not isolate a full-body subject from the imported image.",
        }

    canvas_matches = source_image.size == CONCEPT_CANVAS
    width = max(1, bbox[2] - bbox[0])
    height = max(1, bbox[3] - bbox[1])
    centered_x = abs(((bbox[0] + bbox[2]) / 2.0) - (source_image.size[0] / 2.0)) <= max(18, source_image.size[0] * 0.05)
    full_body_visible = bbox[1] > 8 and bbox[3] < source_image.size[1] - 8 and bbox[0] > 4 and bbox[2] < source_image.size[0] - 4
    target_scale = min((CONCEPT_CANVAS[0] - 112) / float(width), (CONCEPT_CANVAS[1] - 94) / float(height))
    current_scale = min(source_image.size[0] / float(width), source_image.size[1] / float(height))
    close_to_target = abs(current_scale - target_scale) <= 0.12
    clean = analyze_concept_image(source_path)
    if canvas_matches and centered_x and full_body_visible and close_to_target and clean.get("status") == "ok":
        return {
            "status": "not_needed",
            "image_path": None,
            "notes": "Imported image already fits extraction framing.",
        }

    subject = strip_light_edge_matte(source_image, source_mask)
    cleaned_mask = largest_component_mask(subject.getchannel("A"))
    subject = image_with_mask(subject, cleaned_mask)
    cropped, cropped_mask, _ = crop_to_alpha(subject, cleaned_mask)
    if cropped_mask.getbbox() is None or mask_pixel_area(cropped_mask) < 1500:
        return {
            "status": "failed",
            "image_path": None,
            "notes": "Subject area was too small or fragmented for safe normalization.",
        }

    contained = ImageOps.contain(cropped, (CONCEPT_CANVAS[0] - 112, CONCEPT_CANVAS[1] - 94))
    canvas = Image.new("RGBA", CONCEPT_CANVAS, (0, 0, 0, 0))
    offset_x = (CONCEPT_CANVAS[0] - contained.size[0]) // 2
    offset_y = CONCEPT_CANVAS[1] - 54 - contained.size[1]
    offset_y = max(20, offset_y)
    canvas.alpha_composite(contained, (offset_x, offset_y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return {
        "status": "applied",
        "image_path": str(output_path),
        "notes": "Normalized canvas, centering, and padding for extraction without repainting the artwork.",
    }


def parse_gemini_response_text(payload: Dict[str, Any]) -> str:
    for candidate in payload.get("candidates", []) or []:
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            text_value = part.get("text")
            if isinstance(text_value, str) and text_value.strip():
                return text_value
    raise ValueError("Gemini response did not include structured text output.")


def run_gemini_concept_validation(
    project: Dict[str, Any],
    concept: Dict[str, Any],
    validation_path: Path,
) -> Dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    brief = project.get("brief") or {}
    prompt_text = concept.get("prompt_text") or concept.get("positive_prompt") or ""
    instructions = (
        "You validate imported Gemini concept art for a 2d side-view sprite pipeline. "
        "Judge both creative quality and direct extraction readiness. "
        "Accept only if the image is artistically acceptable for the brief and can serve as the direct sprite extraction source after only safe mechanical normalization. "
        "Reject if side profile is weak, the background is not safely removable, the body is cropped, there are multiple characters, the silhouette is unclear, or the image would still need a separate master pose step. "
        "If rejected, describe only the targeted corrections needed to fix the specific issues while preserving the same character identity. "
        "Do not suggest a redesign, different costume, different silhouette family, or different character unless the brief itself is inconsistent. "
        "If you provide an improved Gemini prompt, it must explicitly preserve the same character and change only the minimum required details. "
        "The required technical standard is: strict side profile, one full-body humanoid, plain removable background, clean silhouette, readable limbs and prop, direct sprite-source readiness, consistency with the brief and latest Gemini prompt. "
        "Set decision=valid only when both master_pose_ready and technical_requirements_ok are true."
    )
    user_prompt = (
        "Brief summary:\n"
        "Role: %s\n"
        "Silhouette: %s\n"
        "Outfit: %s\n"
        "Prop: %s\n"
        "Palette: %s\n"
        "Tone: %s\n\n"
        "Latest Gemini prompt:\n%s\n"
    ) % (
        brief.get("role_archetype", ""),
        brief.get("silhouette_intent", ""),
        brief.get("outfit_materials", ""),
        brief.get("prop", ""),
        brief.get("palette_mood", ""),
        brief.get("mood_tone", ""),
        prompt_text,
    )
    image_bytes = base64.b64decode(image_data_url(validation_path).split(",", 1)[1])
    endpoint = "%s/models/%s:generateContent" % (
        GEMINI_API_BASE_URL,
        DEFAULT_GEMINI_VALIDATION_MODEL,
    )
    body = {
        "system_instruction": {
            "parts": [{"text": instructions}],
        },
        "contents": [{
            "role": "user",
            "parts": [
                {"text": user_prompt},
                {
                    "inline_data": {
                        "mime_type": {
                            ".png": "image/png",
                            ".jpg": "image/jpeg",
                            ".jpeg": "image/jpeg",
                            ".webp": "image/webp",
                        }.get(validation_path.suffix.lower(), "image/png"),
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    }
                },
            ],
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": concept_validation_schema(),
        },
    }
    request = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError(
                "Gemini validation model '%s' was not found for this API/version. "
                "Set SPRITE_WORKBENCH_GEMINI_VALIDATION_MODEL to an available model."
                % DEFAULT_GEMINI_VALIDATION_MODEL
            ) from exc
        if exc.code == 429:
            raise ValueError("Gemini rate limit hit. Validation left pending; retry later.") from exc
        raise
    parsed = json.loads(parse_gemini_response_text(payload))
    decision = parsed.get("decision")
    if decision not in {"valid", "invalid"}:
        raise ValueError("Gemini validation decision was missing or invalid.")
    return {
        "decision": decision,
        "summary": str(parsed.get("summary") or "").strip(),
        "feedback": str(parsed.get("feedback") or "").strip(),
        "improved_gemini_prompt": (str(parsed.get("improved_gemini_prompt")).strip() if parsed.get("improved_gemini_prompt") else None),
        "master_pose_ready": bool(parsed.get("master_pose_ready")),
        "technical_requirements_ok": bool(parsed.get("technical_requirements_ok")),
        "response_id": payload.get("responseId"),
    }


def apply_validation_state(
    project: Dict[str, Any],
    concept: Dict[str, Any],
    validation_status: str,
    *,
    feedback: Optional[str] = None,
    summary: Optional[str] = None,
    validation_source: str = "manual",
    validation_error: Optional[str] = None,
    codex_response_id: Optional[str] = None,
) -> Dict[str, Any]:
    concept["validation_status"] = validation_status
    concept["validation_feedback"] = (feedback or "").strip() or None
    concept["validation_source"] = validation_source
    concept["validation_updated_at"] = now_iso()
    concept["validation_error"] = (validation_error or "").strip() or None
    concept["codex_review_summary"] = (summary or "").strip() or None
    concept["codex_response_id"] = codex_response_id
    concept["review_state"]["rejected"] = validation_status == "invalid"
    concept["approved"] = concept["review_state"]["approved"]
    concept["favorite"] = concept["review_state"]["favorite"]
    concept["rejected"] = concept["review_state"]["rejected"]
    if validation_status != "valid" and project.get("selected_concept_id") == concept["concept_id"]:
        reset_downstream_assets(project["project_id"], "concept")
        project = clear_project_downstream_state(project, "concept")
        concept["review_state"]["approved"] = False
        concept["approved"] = False
        concept["accepted_for_review"] = False
        project["selected_concept_id"] = None
        project["character_spec"] = None
    concept["accepted_for_review"] = bool(project.get("selected_concept_id") == concept["concept_id"] and validation_status == "valid")
    return project


def persist_gemini_retry_prompt(project: Dict[str, Any], concept: Dict[str, Any], prompt_text: str) -> Dict[str, Any]:
    prompt_text = (prompt_text or "").strip()
    if not prompt_text:
        raise ValueError("Improved Gemini prompt was empty.")
    latest_prompt = project.get("latest_prompt") or {}
    if latest_prompt.get("prompt_text", "").strip() == prompt_text:
        return latest_prompt
    return create_prompt_attempt(
        project,
        prompt_text,
        "gemini_retry",
        attempt_group_id=concept.get("attempt_group_id"),
        validation_feedback=concept.get("validation_feedback"),
    )


def build_retry_prompt_from_validation(project: Dict[str, Any], concept: Dict[str, Any], fallback_prompt_text: Optional[str] = None) -> str:
    feedback = (concept.get("validation_feedback") or "").strip()
    prior_prompt = (
        concept.get("prompt_text")
        or concept.get("positive_prompt")
        or (project.get("latest_prompt") or {}).get("prompt_text")
        or fallback_prompt_text
        or ""
    )
    return build_gemini_prompt(
        project["brief"],
        previous_prompt=prior_prompt,
        validation_feedback=feedback,
        imported_attempt=concept if concept.get("preview_image") else None,
    )


def validate_imported_concept(project_id: str, concept_id: str, *, allow_prompt_create: bool = True) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    concept = next((item for item in project["concepts"] if item["concept_id"] == concept_id), None)
    if concept is None:
        raise ValueError("Concept not found.")
    original_rel = concept.get("original_preview_image") or concept.get("preview_image")
    if not original_rel:
        raise ValueError("Only imported concept attempts can be revalidated.")
    original_path = project_dir / original_rel
    if not original_path.exists():
        raise ValueError("Imported concept image is missing on disk.")

    processed_path = project_dir / "concepts" / ("%s-processed.png" % concept_id)
    postprocess = safe_normalize_concept_image(original_path, processed_path)
    concept["postprocess_status"] = postprocess["status"]
    concept["postprocess_notes"] = postprocess["notes"]
    concept["processed_preview_image"] = (
        str(processed_path.relative_to(project_dir))
        if postprocess.get("image_path") and processed_path.exists()
        else None
    )
    concept["approved_source_image"] = concept.get("processed_preview_image") or original_rel
    validation_path = project_dir / (concept["processed_preview_image"] or original_rel)

    try:
        review = run_gemini_concept_validation(project, concept, validation_path)
    except Exception as exc:
        project = apply_validation_state(
            project,
            concept,
            "pending",
            feedback=concept.get("validation_feedback"),
            summary=None,
            validation_source="gemini",
            validation_error=str(exc),
            codex_response_id=None,
        )
        concept["review_state"]["approved"] = False
        concept["approved"] = False
        concept["accepted_for_review"] = False
        concept["favorite"] = concept["review_state"]["favorite"]
        save_concept(project_dir, concept)
        project["updated_at"] = now_iso()
        project["current_stage"] = "concepts"
        project["status"] = "concept_validation_pending"
        save_project(project)
        append_history_event(project_id, {
            "type": "concept_gemini_validation_pending",
            "concept_id": concept_id,
            "validation_error": concept.get("validation_error"),
            "created_at": now_iso(),
        })
        return load_project(project_id)

    if review["decision"] == "valid" and not (review["master_pose_ready"] and review["technical_requirements_ok"]):
        review["decision"] = "invalid"
        if not review.get("feedback"):
            review["feedback"] = "Image was not extraction-ready under the technical rubric."

    project = apply_validation_state(
        project,
        concept,
        review["decision"],
        feedback=review["feedback"],
        summary=review["summary"],
        validation_source="gemini",
        validation_error=None,
        codex_response_id=review.get("response_id"),
    )
    save_concept(project_dir, concept)
    retry_prompt = None
    if review["decision"] == "invalid" and allow_prompt_create:
        synthesized_retry_prompt = build_retry_prompt_from_validation(project, concept, review.get("improved_gemini_prompt"))
        retry_prompt = persist_gemini_retry_prompt(project, concept, synthesized_retry_prompt)
    project["updated_at"] = now_iso()
    project["current_stage"] = "concepts"
    project["status"] = "concept_%s" % review["decision"]
    save_project(project)
    append_history_event(project_id, {
        "type": "concept_gemini_validation",
        "concept_id": concept_id,
        "validation_status": review["decision"],
        "summary": review["summary"],
        "response_id": review.get("response_id"),
        "created_at": now_iso(),
    })
    if retry_prompt is not None:
        append_history_event(project_id, {
            "type": "concept_gemini_retry_prompt",
            "concept_id": concept_id,
            "prompt_version": retry_prompt.get("prompt_version"),
            "created_at": now_iso(),
        })
    return load_project(project_id)


def create_prompt_attempt(
    project: Dict[str, Any],
    prompt_text: str,
    prompt_source: str,
    attempt_group_id: Optional[str] = None,
    validation_feedback: Optional[str] = None,
) -> Dict[str, Any]:
    project_dir = PROJECTS_ROOT / project["project_id"]
    project["concepts"] = project.get("concepts") or []
    serial = next_concept_serial(project["concepts"])
    prompt_version = next_prompt_version(project["concepts"])
    concept_id = "concept-%04d" % serial
    attempt_group = attempt_group_id or ("attempt-%s" % uuid.uuid4().hex[:10])
    _, history_prompt_path = save_prompt_artifacts(project_dir, prompt_version, prompt_text)
    concept = hydrate_concept({
        "concept_id": concept_id,
        "run_id": "prompt-%s" % prompt_version,
        "run_kind": "prompt_request",
        "created_at": now_iso(),
        "positive_prompt": prompt_text,
        "prompt": prompt_text,
        "prompt_text": prompt_text,
        "prompt_version": prompt_version,
        "prompt_source": prompt_source,
        "prompt_file": history_prompt_path,
        "attempt_group_id": attempt_group,
        "attempt_index": prompt_version,
        "import_source": None,
        "validation_status": "pending",
        "validation_feedback": validation_feedback,
        "accepted_for_review": False,
        "difference_summary": "Gemini prompt v%d" % prompt_version,
        "silhouette": project["brief"]["silhouette_intent"],
        "outfit": project["brief"]["outfit_materials"],
        "palette_direction": project["brief"]["palette_mood"],
        "palette": palette_from_seed(prompt_version, 0, project["brief"]["palette_mood"]),
        "prop_variant": project["brief"]["prop"],
        "face_head_shape": project["brief"]["shape_language"],
        "references_used": [],
        "review_state": {"approved": False, "favorite": False, "rejected": False},
        "lineage": {"run_id": "prompt-%s" % prompt_version, "parent_concept_id": None},
    })
    project["concepts"].append(concept)
    save_concept(project_dir, concept)
    project["updated_at"] = now_iso()
    project["current_stage"] = "concepts"
    project["status"] = "prompt_ready"
    save_project(project)
    append_history_event(project["project_id"], {
        "type": "prompt_generation",
        "concept_id": concept_id,
        "attempt_group_id": attempt_group,
        "prompt_version": prompt_version,
        "prompt_source": prompt_source,
        "created_at": now_iso(),
    })
    return concept


def import_concept_attempt(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    source_prompt_id = payload.get("source_prompt_id")
    if not source_prompt_id:
        raise ValueError("source_prompt_id is required.")
    source_prompt = next((item for item in project["concepts"] if item["concept_id"] == source_prompt_id), None)
    if source_prompt is None:
        raise ValueError("Prompt attempt not found.")

    imports_dir = project_dir / "concepts"
    imports_dir.mkdir(parents=True, exist_ok=True)
    data_url = payload.get("data_url")
    local_path = payload.get("local_path")
    original_name = payload.get("name") or payload.get("filename") or "gemini-concept"
    if data_url:
        mime_type, raw = parse_data_url(data_url)
        extension = guess_extension(original_name, mime_type)
        import_source = "upload"
        source_value = original_name
    elif local_path:
        source = Path(str(local_path)).expanduser()
        if not source.exists() or not source.is_file():
            raise ValueError("Local image path does not exist: %s" % local_path)
        raw = source.read_bytes()
        extension = source.suffix or ".png"
        import_source = "local_path"
        source_value = str(source)
    else:
        raise ValueError("Provide an upload or local_path.")

    serial = next_concept_serial(project["concepts"])
    concept_id = "concept-%04d" % serial
    filename = "%s%s" % (concept_id, extension)
    output_path = imports_dir / filename
    output_path.write_bytes(raw)

    prompt_version = int(source_prompt.get("prompt_version") or next_prompt_version(project["concepts"]))
    concept = hydrate_concept({
        "concept_id": concept_id,
        "run_id": source_prompt.get("run_id") or ("import-%s" % prompt_version),
        "run_kind": "manual_import",
        "created_at": now_iso(),
        "positive_prompt": source_prompt.get("prompt_text") or source_prompt.get("positive_prompt") or "",
        "prompt": source_prompt.get("prompt_text") or source_prompt.get("positive_prompt") or "",
        "prompt_text": source_prompt.get("prompt_text") or source_prompt.get("positive_prompt") or "",
        "prompt_version": prompt_version,
        "prompt_source": source_prompt.get("prompt_source") or "initial",
        "prompt_file": source_prompt.get("prompt_file"),
        "preview_image": str(output_path.relative_to(project_dir)),
        "original_preview_image": str(output_path.relative_to(project_dir)),
        "backend_name": "manual_import",
        "backend_run_id": source_value,
        "attempt_group_id": source_prompt.get("attempt_group_id") or source_prompt_id,
        "attempt_index": source_prompt.get("attempt_index") or prompt_version,
        "import_source": import_source,
        "validation_status": "pending",
        "validation_feedback": None,
        "accepted_for_review": False,
        "difference_summary": "Imported Gemini concept for prompt v%d" % prompt_version,
        "silhouette": project["brief"]["silhouette_intent"],
        "outfit": project["brief"]["outfit_materials"],
        "palette_direction": project["brief"]["palette_mood"],
        "palette": palette_from_seed(prompt_version, 0, project["brief"]["palette_mood"]),
        "prop_variant": project["brief"]["prop"],
        "face_head_shape": project["brief"]["shape_language"],
        "references_used": [],
        "review_state": {"approved": False, "favorite": False, "rejected": False},
        "lineage": {"run_id": source_prompt.get("run_id"), "parent_concept_id": source_prompt_id},
    })
    try:
        concept["triage"] = analyze_concept_image(output_path)
    except Exception:
        concept["triage"] = {"status": "not_evaluated", "flags": [], "metrics": {}}
    project["concepts"].append(concept)
    project["updated_at"] = now_iso()
    project["current_stage"] = "concepts"
    project["status"] = "concept_imported"
    save_project(project)
    save_concept(project_dir, concept)
    append_history_event(project_id, {
        "type": "concept_import",
        "concept_id": concept_id,
        "source_prompt_id": source_prompt_id,
        "import_source": import_source,
        "created_at": now_iso(),
    })
    return validate_imported_concept(project_id, concept_id)


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


def build_prompt_bundle(
    brief: Dict[str, Any],
    variation_axes: Dict[str, Any],
    source_concept: Optional[Dict[str, Any]] = None,
    rescue_mode: bool = False,
) -> Tuple[str, str]:
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
    negative_prompt = brief["negative_prompt"]
    if rescue_mode:
        positive_parts.append(CONCEPT_RESCUE_POSITIVE_RULES)
        negative_prompt = "%s, %s" % (negative_prompt, CONCEPT_RESCUE_NEGATIVE_RULES)
    if source_concept is not None:
        positive_parts.append("preserve the same character identity core as the source concept")
        preserve = variation_axes.get("preserve") or {}
        locked_bits = []
        for key in ["silhouette", "outfit", "palette_direction", "prop_variant"]:
            if preserve.get(key):
                locked_bits.append("%s=%s" % (key, preserve[key]))
        if locked_bits:
            positive_parts.append("locked attributes: %s" % ", ".join(locked_bits))
    return ", ".join(positive_parts), negative_prompt


def make_reference_inputs(project_dir: Path, brief: Dict[str, Any]) -> List[ReferenceInput]:
    inputs = []
    for item in brief.get("references") or []:
        local_rel = item.get("local_path")
        if not local_rel:
            continue
        path = project_dir / local_rel
        analysis = analyze_reference_asset(path, item.get("source_value"))
        if path.exists() and analysis.get("usable_for_concepts", True):
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
            "quality_gate_failed": bool(event.get("quality_gate_failed")),
            "rescue_attempted": bool(event.get("rescue_attempted")),
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


def enrich_brief_references(project_dir: Path, brief: Dict[str, Any]) -> Dict[str, Any]:
    references = []
    for item in brief.get("references") or []:
        if not isinstance(item, dict):
            continue
        local_path = project_dir / item["local_path"] if item.get("local_path") else None
        analysis = analyze_reference_asset(local_path if local_path and local_path.exists() else None, item.get("source_value"))
        enriched = dict(item)
        enriched["reference_kind"] = analysis["reference_kind"]
        enriched["reference_warning"] = analysis["reference_warning"]
        enriched["usable_for_concepts"] = analysis["usable_for_concepts"]
        references.append(enriched)
    brief["references"] = references
    return brief


def load_project(project_id: str) -> Dict[str, Any]:
    project_dir = PROJECTS_ROOT / project_id
    project_path = project_dir / "project.json"
    if not project_path.exists():
        raise FileNotFoundError(project_id)

    project = apply_project_defaults(load_json(project_path, {}))
    ensure_dirs(project_dir)
    project["brief"] = enrich_brief_references(project_dir, hydrate_brief(load_json(project_dir / "brief.json", {}), project.get("prompt_text", "")))
    project["character_spec"] = load_json(project_dir / "character_spec.json")
    project["rig_layout"] = load_json(canonical_downstream_path(project_dir, "rig_layout"))
    project["rig_layout_history"] = load_json(rig_layout_history_path(project_dir), default_rig_layout_history(project_id))
    project["part_manifest"] = load_json(canonical_downstream_path(project_dir, "part_manifest"))
    project["part_manifest_history"] = load_json(part_manifest_history_path(project_dir), default_part_manifest_history(project_id))
    if project["part_manifest"] is not None and not project["part_manifest"].get("validation"):
        project["part_manifest"]["validation"] = validate_part_manifest(project["part_manifest"])
    project["part_shapes"] = load_json(canonical_downstream_path(project_dir, "part_shapes"))
    project["part_shapes_history"] = load_json(part_shapes_history_path(project_dir), default_part_shapes_history(project_id))
    if project["part_shapes"] is not None and not project["part_shapes"].get("validation"):
        project["part_shapes"]["validation"] = validate_part_shapes(project_dir, project["part_shapes"], project.get("part_manifest"))
    project["part_split"] = load_json(canonical_downstream_path(project_dir, "part_split"))
    project["part_split_history"] = load_json(part_split_history_path(project_dir), default_part_split_history(project_id))
    if project["part_split"] is not None and not project["part_split"].get("validation"):
        source_rel = str(project["part_split"].get("source_image") or "")
        source_mask = None
        if source_rel and (project_dir / source_rel).exists():
            source_mask = normalize_mask(detect_mask(Image.open(project_dir / source_rel).convert("RGBA")))
        project["part_split"]["validation"] = validate_part_split(project_dir, project["part_split"], source_mask)
    project["master_pose_manifest"] = load_master_pose_manifest(project_dir)
    legacy_layered_character = load_json(legacy_downstream_path(project_dir, "layered_character"))
    project["rig"] = load_json(canonical_downstream_path(project_dir, "rig"))
    sprite_model = load_json(canonical_downstream_path(project_dir, "sprite_model"))
    legacy_palette = load_json(legacy_downstream_path(project_dir, "palette"))
    if sprite_model is None and legacy_layered_character:
        sprite_model = hydrate_legacy_sprite_model(project_dir, legacy_layered_character, project.get("rig"), legacy_palette, project.get("character_spec"))
    if sprite_model is not None and not sprite_model.get("build_report"):
        sprite_model["build_report"] = validate_sprite_model(project_dir, sprite_model)
        sprite_model["status"] = sprite_model["build_report"]["status"]
    project["sprite_model"] = sprite_model
    project["palette"] = (sprite_model or {}).get("palette") or legacy_palette
    project["layered_character"] = sprite_model or legacy_layered_character
    legacy_animation_templates = load_json(legacy_downstream_path(project_dir, "animation_templates"))
    project["animation_clips"] = hydrate_animation_clips(
        load_json(canonical_downstream_path(project_dir, "animation_clips")),
        legacy_animation_templates,
        rig_profile=active_rig_profile_name(project, project.get("rig_layout")),
    )
    project["manual_animation_clips"] = hydrate_manual_animation_clips(
        load_json(canonical_downstream_path(project_dir, "manual_animation_clips")),
        project_dir,
    )
    project["ai_workflow"] = hydrate_ai_workflow(
        load_json(canonical_downstream_path(project_dir, "ai_workflow")),
        project,
        project_dir,
    )
    project["external_authoring"] = hydrate_external_authoring(
        load_json(canonical_downstream_path(project_dir, "external_authoring")),
        project_dir,
    )
    project["animation_templates"] = project["animation_clips"] or legacy_animation_templates
    project["qa_report"] = load_json(canonical_downstream_path(project_dir, "qa_report"))
    project["sprite_model_history"] = load_sprite_model_history(project_dir)
    if project["rig_layout"] is None and project.get("selected_concept_id"):
        project["rig_layout"] = resolve_rig_layout(project, persist=False)
        project["rig_layout_approved"] = True
    elif project["rig_layout"] is not None:
        project["rig_layout_approved"] = bool(project.get("rig_layout_approved") or project["rig_layout"].get("approved"))
    if project["part_manifest"] is not None:
        project["part_manifest_approved"] = bool(project.get("part_manifest_approved") or project["part_manifest"].get("approved"))
    if project["part_shapes"] is not None:
        project["part_shapes_approved"] = bool(project.get("part_shapes_approved") or project["part_shapes"].get("approved"))
    if project["part_split"] is not None:
        project["part_split_approved"] = bool(project.get("part_split_approved") or project["part_split"].get("approved"))
        project["split_review_approved"] = bool(project.get("split_review_approved") or project.get("part_split_approved") or project["part_split"].get("approved"))
    project["history"] = load_history(project_id)
    project["pixellab_character"] = load_json(_pixellab_character_path(project_dir), None)
    project["pixellab_skeleton"] = load_json(_pixellab_skeleton_path(project_dir), None)
    project["pixellab_animations"] = _load_pixellab_animations_store(project_dir)
    project["concepts"] = [hydrate_concept(item, project["created_at"]) for item in load_concepts(project_dir)]
    project["prompt_history"] = prompt_history_entries(project["concepts"])
    project["latest_prompt"] = project["prompt_history"][0] if project["prompt_history"] else None
    project["sprite_model_approved"] = bool(project.get("sprite_model_approved") or (not project.get("sprite_model_approved") and project.get("layer_review_approved")))
    project["layer_review_approved"] = bool(project.get("layer_review_approved") or project.get("sprite_model_approved"))
    if project.get("selected_concept_id") is None:
        for concept in project["concepts"]:
            if concept["review_state"]["approved"]:
                project["selected_concept_id"] = concept["concept_id"]
                break
    project["rig_layout_handoff_prompt"] = build_rig_layout_handoff_prompt(project, project.get("rig_layout")) if project.get("selected_concept_id") else None
    project["part_manifest_handoff_prompt"] = build_part_manifest_handoff_prompt(project, project.get("part_manifest")) if project.get("selected_concept_id") and project.get("rig_layout_approved") else None
    project["part_shapes_handoff_prompt"] = build_part_shapes_handoff_prompt(project, project.get("part_shapes")) if project.get("selected_concept_id") and project.get("part_manifest_approved") else None
    project["part_split_handoff_prompt"] = build_part_split_handoff_prompt(project, project.get("part_split")) if project.get("selected_concept_id") and project.get("rig_layout_approved") else None
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
        "master_pose_ready": bool(project["master_pose_manifest"].get("candidates")),
        "master_pose_approved": bool(project.get("master_pose_approved") and project["master_pose_manifest"].get("approved_image")),
        "concept_source_ready": bool(selected_concept(project).get("approved_source_image")) if project.get("selected_concept_id") else False,
        "rig_layout_ready": bool(project.get("rig_layout")) and bool(project.get("rig_layout_approved")),
        "part_manifest_ready": bool(project.get("part_manifest")) and bool(project.get("part_manifest_approved")),
        "part_shapes_ready": bool(project.get("part_shapes")) and bool(project.get("part_shapes_approved")),
        "part_split_ready": bool(project.get("part_split")) and bool(project.get("part_split_approved")),
        "sprite_model_ready": bool(project["sprite_model"]),
        "idle_render_complete": animation_render_complete(project_dir, "idle"),
        "walk_render_complete": animation_render_complete(project_dir, "walk"),
        "manual_clip_count": len(project["manual_animation_clips"]["clips"]),
        "approved_manual_clip_count": sum(
            1
            for clip in project["manual_animation_clips"]["clips"].values()
            if clip.get("approval_status") == "approved" and not clip.get("is_stale")
        ),
        "stale_manual_clip_count": sum(1 for clip in project["manual_animation_clips"]["clips"].values() if clip.get("is_stale")),
    }
    project["production_warnings"] = [
        "Final frames are deterministic and built from persisted extracted parts.",
        "Use sprite-model edits for corrections instead of rerunning downstream AI generation.",
        "QA covers implemented structural/image checks; final style judgment still needs human review.",
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
        "pixellab_character",
        "pixellab_skeleton",
        "pixellab_animations",
        "rig_layout",
        "rig_layout_history",
        "part_manifest",
        "part_manifest_history",
        "part_shapes",
        "part_shapes_history",
        "part_split",
        "part_split_history",
        "master_pose_manifest",
        "sprite_model",
        "palette",
        "sprite_model_history",
        "layered_character",
        "rig",
        "animation_clips",
        "manual_animation_clips",
        "ai_workflow",
        "external_authoring",
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
        "layer_review_approved",
    }}
    core["sprite_model_approved"] = bool(project.get("sprite_model_approved") or project.get("layer_review_approved"))
    write_json(project_dir / "project.json", core)
    write_json(project_dir / "brief.json", project["brief"])
    if project.get("character_spec") is not None:
        write_json(project_dir / "character_spec.json", project["character_spec"])
    if project.get("rig_layout") is not None:
        write_json(canonical_downstream_path(project_dir, "rig_layout"), project["rig_layout"])
    if project.get("rig_layout_history") is not None:
        write_json(rig_layout_history_path(project_dir), project["rig_layout_history"])
    if project.get("part_manifest") is not None:
        write_json(canonical_downstream_path(project_dir, "part_manifest"), project["part_manifest"])
    if project.get("part_manifest_history") is not None:
        write_json(part_manifest_history_path(project_dir), project["part_manifest_history"])
    if project.get("part_shapes") is not None:
        write_json(canonical_downstream_path(project_dir, "part_shapes"), project["part_shapes"])
    if project.get("part_shapes_history") is not None:
        write_json(part_shapes_history_path(project_dir), project["part_shapes_history"])
    if project.get("part_split") is not None:
        write_json(canonical_downstream_path(project_dir, "part_split"), project["part_split"])
    if project.get("part_split_history") is not None:
        write_json(part_split_history_path(project_dir), project["part_split_history"])
    if project.get("master_pose_manifest") is not None:
        save_master_pose_manifest(project_dir, project["master_pose_manifest"])
    if project.get("sprite_model") is not None:
        write_json(canonical_downstream_path(project_dir, "sprite_model"), project["sprite_model"])
    if project.get("sprite_model_history") is not None:
        save_sprite_model_history(project_dir, project["sprite_model_history"])
    if project.get("rig") is not None:
        write_json(canonical_downstream_path(project_dir, "rig"), project["rig"])
    if project.get("animation_clips") is not None:
        write_json(canonical_downstream_path(project_dir, "animation_clips"), project["animation_clips"])
    if project.get("manual_animation_clips") is not None:
        write_json(canonical_downstream_path(project_dir, "manual_animation_clips"), serialize_manual_animation_clips(project["manual_animation_clips"], project["project_id"]))
    if project.get("ai_workflow") is not None:
        write_json(canonical_downstream_path(project_dir, "ai_workflow"), serialize_ai_workflow(project["ai_workflow"], project["project_id"]))
    if project.get("external_authoring") is not None:
        write_json(canonical_downstream_path(project_dir, "external_authoring"), serialize_external_authoring(project["external_authoring"], project["project_id"]))
    if project.get("qa_report") is not None:
        write_json(canonical_downstream_path(project_dir, "qa_report"), project["qa_report"])
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
    sprite_model_approved = bool(project.get("sprite_model_approved") or project.get("layer_review_approved"))
    return {
        "project_id": project["project_id"],
        "project_name": project["project_name"],
        "created_at": project["created_at"],
        "updated_at": project["updated_at"],
        "current_stage": project["current_stage"],
        "status": project["status"],
        "selected_concept_id": project.get("selected_concept_id"),
        "master_pose_approved": project.get("master_pose_approved", False),
        "rig_layout_approved": project.get("rig_layout_approved", False),
        "part_split_approved": project.get("part_split_approved", False),
        "split_review_approved": project.get("split_review_approved", False),
        "sprite_model_approved": sprite_model_approved,
        "layer_review_approved": sprite_model_approved,
        "rig_review_approved": project.get("rig_review_approved", False),
        "archived_at": project.get("archived_at"),
        "last_export": project.get("last_export"),
        "last_ui_mode": project.get("last_ui_mode", "wizard"),
        "ai_workflow_enabled": bool((project.get("ai_workflow") or {}).get("enabled")),
        "ai_workflow_legacy_mode": bool((project.get("ai_workflow") or {}).get("legacy_mode")),
        "external_authoring_enabled": bool((project.get("external_authoring") or {}).get("enabled")),
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
    if payload.get("backend_mode") not in BACKEND_MODES:
        brief["backend_mode"] = "pixellab"
    project_id = "%s-%s" % (
        slugify(project_name or brief["role_archetype"]),
        stable_hash(project_name, prompt, now_iso())[:8],
    )
    project_dir = PROJECTS_ROOT / project_id
    ensure_dirs(project_dir)
    brief = merge_new_references(project_dir, brief, payload)

    now = now_iso()
    initial_mode = "wizard"
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
        "ai_workflow": default_ai_workflow(project_id),
        "external_authoring": default_external_authoring(project_id),
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

    for filename in [
        "project.json",
        "brief.json",
        "character_spec.json",
        "history.json",
        CANONICAL_DOWNSTREAM_FILES["part_manifest"],
        CANONICAL_DOWNSTREAM_FILES["part_manifest_history"],
        CANONICAL_DOWNSTREAM_FILES["part_shapes"],
        CANONICAL_DOWNSTREAM_FILES["part_shapes_history"],
        CANONICAL_DOWNSTREAM_FILES["part_split"],
        CANONICAL_DOWNSTREAM_FILES["part_split_history"],
        CANONICAL_DOWNSTREAM_FILES["sprite_model"],
        CANONICAL_DOWNSTREAM_FILES["sprite_model_history"],
        CANONICAL_DOWNSTREAM_FILES["rig"],
        CANONICAL_DOWNSTREAM_FILES["animation_clips"],
        CANONICAL_DOWNSTREAM_FILES["manual_animation_clips"],
        CANONICAL_DOWNSTREAM_FILES["ai_workflow"],
        CANONICAL_DOWNSTREAM_FILES["external_authoring"],
        CANONICAL_DOWNSTREAM_FILES["qa_report"],
        LEGACY_DOWNSTREAM_FILES["layered_character"],
        LEGACY_DOWNSTREAM_FILES["animation_templates"],
        LEGACY_DOWNSTREAM_FILES["palette"],
    ]:
        src = PROJECTS_ROOT / project_id / filename
        if src.exists():
            shutil.copy2(src, new_dir / filename)

    for folder in ["concepts", "prompts", "references", "master_pose", "part_shapes", "part_split", "parts", "rig", "animations", "manual_clips", "ai_workflow", "external_authoring", "layers", "logs"]:
        src_folder = PROJECTS_ROOT / project_id / folder
        dst_folder = new_dir / folder
        dst_folder.mkdir(parents=True, exist_ok=True)
        if src_folder.exists():
            for path in src_folder.rglob("*"):
                target = dst_folder / path.relative_to(src_folder)
                if path.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif path.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)

    duplicated = load_project(new_id)
    duplicated["project_id"] = new_id
    duplicated["project_name"] = "%s Copy" % source["project_name"]
    duplicated["created_at"] = now_iso()
    duplicated["updated_at"] = now_iso()
    duplicated["current_stage"] = "concept_lock" if source.get("character_spec") else "concepts"
    duplicated["status"] = "branched_from_%s" % source["project_id"]
    duplicated["sprite_model_approved"] = False
    duplicated["layer_review_approved"] = False
    duplicated["rig_review_approved"] = False
    duplicated["last_export"] = None
    duplicated["archived_at"] = None
    duplicated["last_ui_mode"] = "wizard"
    duplicated["wizard_state"] = normalize_wizard_state(source.get("wizard_state"))
    if duplicated.get("history"):
        duplicated["history"]["project_id"] = new_id
    for concept in duplicated.get("concepts", []) or []:
        concept["project_id"] = new_id
    save_project(duplicated)
    delete_path(legacy_downstream_path(new_dir, "layered_character"))
    delete_path(legacy_downstream_path(new_dir, "animation_templates"))
    delete_path(legacy_downstream_path(new_dir, "palette"))
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
    if requested_step in WIZARD_STEPS_KNOWN:
        wizard_state["current_step"] = requested_step

    if isinstance(payload.get("show_advanced"), bool):
        wizard_state["show_advanced"] = payload["show_advanced"]

    for step in payload.get("completed_steps", []) or []:
        if step in WIZARD_STEPS_KNOWN:
            wizard_state = set_wizard_step_complete(wizard_state, step)

    for step in payload.get("skipped_optional_steps", []) or []:
        if step in {"references"}:
            wizard_state = set_wizard_optional_step_skipped(wizard_state, step)

    project["last_ui_mode"] = "wizard"

    project["wizard_state"] = wizard_state
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)


def get_external_authoring(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    return project.get("external_authoring") or default_external_authoring(project_id)


def update_external_authoring(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = hydrate_external_authoring(project.get("external_authoring"), project_dir)
    if "enabled" in payload:
        store["enabled"] = bool(payload.get("enabled"))
    provider = str(payload.get("provider") or store.get("provider") or "skelform")
    if provider != "skelform":
        raise ValueError("Only skelform is currently supported for embedded external authoring.")
    store["provider"] = provider
    store["provider_profile"] = skelform_provider_profile()
    store["updated_at"] = now_iso()
    project["external_authoring"] = store
    project["current_stage"] = "external_authoring" if store["enabled"] else project.get("current_stage", "intake")
    project["status"] = "external_authoring_enabled" if store["enabled"] else project.get("status", "ready")
    project["updated_at"] = now_iso()
    if store["enabled"]:
        project["wizard_state"] = set_wizard_step_complete(project.get("wizard_state"), "review")
        project["wizard_state"]["current_step"] = "clips"
    save_project(project)
    return load_project(project_id)["external_authoring"]


def open_external_authoring_session(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = hydrate_external_authoring(project.get("external_authoring"), project_dir)
    if not store.get("enabled"):
        raise ValueError("Enable external authoring before opening a SkelForm session.")
    store["session"] = {
        **store.get("session", {}),
        "editor_url": SKELFORM_EDITOR_URL,
        "embed_url": "%s?utm_source=sprite_workbench&project_id=%s" % (SKELFORM_EDITOR_URL, quote(project_id)),
        "can_embed": True,
        "source_mode": "hosted",
        "last_opened_at": now_iso(),
    }
    store["updated_at"] = now_iso()
    project["external_authoring"] = store
    project["current_stage"] = "external_authoring"
    project["status"] = "external_authoring_session_ready"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["external_authoring"]


def _store_uploaded_or_local_asset(project_dir: Path, bundle_dir: Path, payload: Dict[str, Any], stem: str, default_suffix: str) -> Optional[str]:
    data_url = payload.get("%s_data_url" % stem)
    local_path = payload.get("%s_local_path" % stem)
    original_name = payload.get("%s_name" % stem) or stem
    if data_url:
        mime_type, raw = parse_data_url(str(data_url))
        suffix = guess_extension(str(original_name), mime_type) or default_suffix
        target = bundle_dir / ("%s%s" % (sanitize_filename(Path(str(original_name)).stem, stem), suffix))
        target.write_bytes(raw)
        return str(target.relative_to(project_dir))
    if local_path:
        source = Path(str(local_path)).expanduser()
        if not source.exists() or not source.is_file():
            raise ValueError("%s path does not exist: %s" % (stem, local_path))
        suffix = source.suffix or default_suffix
        target = bundle_dir / ("%s%s" % (sanitize_filename(source.stem, stem), suffix))
        shutil.copy2(source, target)
        return str(target.relative_to(project_dir))
    return None


def import_external_authoring_bundle(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = hydrate_external_authoring(project.get("external_authoring"), project_dir)
    if not store.get("enabled"):
        raise ValueError("Enable external authoring before importing a bundle.")
    bundle_id = "bundle-%s" % uuid.uuid4().hex[:8]
    bundle_dir = external_authoring_import_root(project_dir) / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    spritesheet_path = _store_uploaded_or_local_asset(project_dir, bundle_dir, payload, "spritesheet", ".png")
    atlas_path = _store_uploaded_or_local_asset(project_dir, bundle_dir, payload, "atlas", ".json")
    animations_path = _store_uploaded_or_local_asset(project_dir, bundle_dir, payload, "animations", ".json")
    preview_gif_path = _store_uploaded_or_local_asset(project_dir, bundle_dir, payload, "preview_gif", ".gif")
    if not spritesheet_path:
        raise ValueError("Import requires a spritesheet upload or local path.")
    if not atlas_path:
        raise ValueError("Import requires an atlas JSON upload or local path.")
    if not animations_path:
        raise ValueError("Import requires an animations JSON upload or local path.")
    atlas = load_json(project_dir / atlas_path, None)
    animations = load_json(project_dir / animations_path, None)
    if not isinstance(atlas, dict) or not isinstance(atlas.get("frames"), dict):
        raise ValueError("Atlas JSON must contain a top-level frames object.")
    if not isinstance(animations, dict) or not animations:
        raise ValueError("Animations JSON must be a non-empty object.")
    store["imported_bundle"] = {
        "bundle_id": bundle_id,
        "provider": "skelform",
        "imported_at": now_iso(),
        "source_label": str(payload.get("source_label") or "SkelForm export").strip() or "SkelForm export",
        "notes": str(payload.get("notes") or "").strip() or None,
        "spritesheet_image_path": spritesheet_path,
        "atlas_path": atlas_path,
        "animations_path": animations_path,
        "preview_gif_path": preview_gif_path,
        "animation_names": sorted(animations.keys()),
        "frame_count": len(atlas.get("frames") or {}),
    }
    store["updated_at"] = now_iso()
    project["external_authoring"] = store
    project["current_stage"] = "external_authoring"
    project["status"] = "external_authoring_bundle_imported"
    project["updated_at"] = now_iso()
    project["wizard_state"] = set_wizard_step_complete(project.get("wizard_state"), "clips")
    project["wizard_state"]["current_step"] = "qa"
    save_project(project)
    return load_project(project_id)["external_authoring"]


def ai_workflow_or_error(project: Dict[str, Any]) -> Dict[str, Any]:
    store = project.get("ai_workflow")
    if not isinstance(store, dict):
        raise ValueError("AI workflow state is missing for this project.")
    if store.get("legacy_mode"):
        raise ValueError("This project is in read-only legacy mode. Create a new project to use ai_sideview_v1.")
    if not store.get("enabled"):
        raise ValueError("AI workflow is not enabled for this project.")
    return store


def ai_workflow_health_snapshot(backend_mode: str = "comfyui") -> Dict[str, Any]:
    if backend_mode == "debug_procedural":
        dependencies = {
            "comfyui": {"status": "pass", "detail": "debug_procedural bypass enabled for local tests"},
            "photomaker": {"status": "pass", "detail": "debug fallback satisfied"},
            "ipadapter_plus": {"status": "pass", "detail": "debug fallback satisfied"},
            "tooncrafter": {"status": "pass", "detail": "debug fallback satisfied"},
            "anime_segmentation": {"status": "pass", "detail": "debug fallback satisfied"},
            "pixelart_cleanup": {"status": "pass", "detail": "debug fallback satisfied"},
        }
        return {
            "generated_at": now_iso(),
            "workflow_profile": AI_WORKFLOW_PROFILE,
            "overall_status": "pass",
            "dependencies": dependencies,
            "backend_mode": backend_mode,
        }

    comfy = ComfyUIConceptBackend(DEFAULT_COMFYUI_BASE_URL).healthcheck()
    comfy_status = "pass" if comfy.get("ok") else "fail"
    def configured(name: str) -> Dict[str, Any]:
        env_name = "SPRITE_WORKBENCH_%s_READY" % name.upper()
        ready = str(os.environ.get(env_name, "")).lower() in {"1", "true", "yes", "ready"}
        return {
            "status": "pass" if ready else "fail",
            "detail": "ready via %s" % env_name if ready else "missing; set %s after installing the required node/model" % env_name,
        }
    dependencies = {
        "comfyui": {
            "status": comfy_status,
            "detail": comfy.get("error") or ("reachable at %s" % comfy.get("base_url", DEFAULT_COMFYUI_BASE_URL)),
        },
        "photomaker": configured("photomaker"),
        "ipadapter_plus": configured("ipadapter_plus"),
        "tooncrafter": configured("tooncrafter"),
        "anime_segmentation": configured("anime_segmentation"),
        "pixelart_cleanup": configured("pixelart_cleanup"),
    }
    overall_status = "pass" if all(item["status"] == "pass" for item in dependencies.values()) else "fail"
    return {
        "generated_at": now_iso(),
        "workflow_profile": AI_WORKFLOW_PROFILE,
        "overall_status": overall_status,
        "dependencies": dependencies,
        "backend_mode": backend_mode,
    }


def refresh_ai_workflow_dependency_status(project: Dict[str, Any], persist: bool = False) -> Dict[str, Any]:
    store = ai_workflow_or_error(project)
    backend_mode = str((project.get("brief") or {}).get("backend_mode") or "comfyui")
    store["dependency_status"] = ai_workflow_health_snapshot(backend_mode)
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    if persist:
        project["updated_at"] = now_iso()
        save_project(project)
    return store["dependency_status"]


def get_ai_workflow(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    store = project.get("ai_workflow") or default_ai_workflow(project_id)
    if not store.get("legacy_mode"):
        refresh_ai_workflow_dependency_status(project)
        store = project["ai_workflow"]
    return store


def _ai_require_stack_ready(project: Dict[str, Any]) -> None:
    # For the current tool, always allow AI workflow stages to run.
    # Dependency status is still recorded via the health endpoint but never blocks execution.
    try:
        refresh_ai_workflow_dependency_status(project, persist=True)
    except Exception:
        # Health failures should not prevent local debug runs.
        pass


def _ai_source_image(project: Dict[str, Any], project_dir: Path) -> Image.Image:
    source_path, _ = resolve_sprite_source_image(project, project_dir)
    return Image.open(source_path).convert("RGBA")


def _ai_backend_mode(project: Dict[str, Any]) -> str:
    return str((project.get("brief") or {}).get("backend_mode") or "comfyui")


def _ai_transform_variant(image: Image.Image, *, dx: int = 0, dy: int = 0, scale: float = 1.0, rotate: float = 0.0, mirror: bool = False) -> Image.Image:
    subject = image
    if mirror:
        subject = ImageOps.mirror(subject)
    bbox = subject.getchannel("A").getbbox()
    if bbox is None:
        return subject.copy()
    cropped = subject.crop(bbox)
    if scale != 1.0:
        width = max(1, int(round(cropped.size[0] * scale)))
        height = max(1, int(round(cropped.size[1] * scale)))
        cropped = cropped.resize((width, height), Image.Resampling.BICUBIC)
    if rotate:
        cropped = cropped.rotate(rotate, resample=Image.Resampling.BICUBIC, expand=True)
    canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
    target_x = int(round((image.size[0] - cropped.size[0]) / 2 + dx))
    target_y = int(round((image.size[1] - cropped.size[1]) / 2 + dy))
    canvas.alpha_composite(cropped, (target_x, target_y))
    return canvas


def _ai_candidate_label(index: int) -> str:
    return "lock_%02d" % (index + 1)


def _ai_write_asset(image: Image.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _ai_find_character_lock_asset(store: Dict[str, Any], asset_id: str) -> Optional[Dict[str, Any]]:
    for run in (store.get("character_lock", {}).get("runs") or {}).values():
        for asset in run.get("candidates") or []:
            if asset.get("asset_id") == asset_id:
                return asset
    return None


def _ai_find_key_pose_run(store: Dict[str, Any], run_id: str) -> Optional[Dict[str, Any]]:
    return (store.get("key_pose_set", {}).get("runs") or {}).get(run_id)


def _ai_motion_group(store: Dict[str, Any], group_name: str, clip_name: str) -> Dict[str, Any]:
    group = store.get(group_name) or {}
    if clip_name not in AI_CLIP_SPECS:
        raise ValueError("Unknown clip: %s." % clip_name)
    clip_group = group.get(clip_name)
    if not isinstance(clip_group, dict):
        clip_group = {"runs": {}, "approved_run_id": None}
        group[clip_name] = clip_group
        store[group_name] = group
    return clip_group


def _ai_render_manifest_for_frames(clip_name: str, frame_names: List[str]) -> Dict[str, Any]:
    return {
        "animation": clip_name,
        "frames": [
            {
                "frame_name": frame_name,
                "cleanup": {
                    "pivot": list(FRAME_PIVOT),
                    "anchor_target": list(FRAME_PIVOT),
                },
                "render_meta": {
                    "foot_anchor": {"left": list(FRAME_PIVOT), "right": list(FRAME_PIVOT)},
                    "draw_sequence": ["ai_workflow_frame"],
                    "render_log": [{"part": "ai_workflow_frame", "part_role": "subject", "kind": "ai"}],
                },
            }
            for frame_name in frame_names
        ],
    }


def run_comfy_prompt_graph(prompt_graph: Dict[str, Any], output_dir: Path) -> List[Path]:
    base_url = DEFAULT_COMFYUI_BASE_URL.rstrip("/")
    output_dir.mkdir(parents=True, exist_ok=True)
    submit = http_json("POST", "%s/prompt" % base_url, {"prompt": prompt_graph}, timeout=COMFYUI_TIMEOUT_SECONDS)
    prompt_id = submit.get("prompt_id")
    if not prompt_id:
        raise ValueError("ComfyUI did not return a prompt_id.")
    if submit.get("node_errors"):
        raise ValueError("ComfyUI reported node errors: %s" % submit["node_errors"])

    deadline = time.monotonic() + COMFYUI_JOB_TIMEOUT_SECONDS
    image_metas: List[Dict[str, Any]] = []
    while time.monotonic() < deadline:
        history_payload = http_json("GET", "%s/history/%s" % (base_url, quote(str(prompt_id))), timeout=COMFYUI_TIMEOUT_SECONDS)
        image_metas = extract_history_images(history_payload, str(prompt_id))
        if image_metas:
            break
        time.sleep(COMFYUI_POLL_SECONDS)
    if not image_metas:
        raise ValueError(
            "ComfyUI workflow job timed out after %s seconds. "
            "Increase SPRITE_WORKBENCH_COMFYUI_JOB_TIMEOUT_SECONDS for slower local runs."
            % COMFYUI_JOB_TIMEOUT_SECONDS
        )

    result_paths: List[Path] = []
    for index, image_meta in enumerate(image_metas):
        image_bytes = fetch_comfyui_history_image(base_url, image_meta)
        filename = image_meta.get("filename") or "frame_%02d.png" % index
        path = output_dir / filename
        path.write_bytes(image_bytes)
        result_paths.append(path)
    return result_paths


def run_ai_character_lock(project_id: str, workflow_profile: str, source_asset_ids: List[str], parameters: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    project_dir = PROJECTS_ROOT / project_id
    backend_mode = _ai_backend_mode(project)
    _ai_require_stack_ready(project)
    run_id = "lock-%s" % uuid.uuid4().hex[:8]
    output_root = ai_workflow_root(project_dir, "character_lock", run_id=run_id)
    refs_used = [item.get("reference_id") for item in ((project.get("brief") or {}).get("references") or []) if item.get("reference_id")]
    prompt = str(parameters.get("prompt") or project.get("prompt_text") or "").strip()
    negative_prompt = str(parameters.get("negative_prompt") or (project.get("brief") or {}).get("negative_prompt") or DEFAULT_NEGATIVE_PROMPT).strip()
    candidates: List[Dict[str, Any]] = []

    if backend_mode == "debug_procedural":
        source = _ai_source_image(project, project_dir)
        transforms = [
            {"dx": -10, "dy": 0, "scale": 1.0, "rotate": -1.5, "mirror": False},
            {"dx": 8, "dy": -4, "scale": 1.02, "rotate": 1.0, "mirror": False},
            {"dx": -4, "dy": 2, "scale": 0.98, "rotate": 0.0, "mirror": False},
            {"dx": 12, "dy": 1, "scale": 1.01, "rotate": 0.5, "mirror": False},
            {"dx": -14, "dy": -2, "scale": 0.99, "rotate": -0.5, "mirror": False},
            {"dx": 0, "dy": 0, "scale": 1.0, "rotate": 0.0, "mirror": False},
        ]
        for index in range(AI_CHARACTER_LOCK_COUNT):
            call_progress(progress, 10 + int((index / AI_CHARACTER_LOCK_COUNT) * 72), "Character Lock %d of %d" % (index + 1, AI_CHARACTER_LOCK_COUNT), "Generating identity-locked candidate set.")
            variant = _ai_transform_variant(source, **transforms[index % len(transforms)])
            asset_name = _ai_candidate_label(index)
            output_path = output_root / ("%s.png" % asset_name)
            _ai_write_asset(variant, output_path)
            candidates.append({
                "asset_id": "character_lock:%s:%s" % (run_id, asset_name),
                "label": asset_name,
                "image_path": str(output_path.relative_to(project_dir)),
                "seed": int(parameters.get("seed", 1000 + index)),
                "workflow_id": "photomaker_ipadapter_character_lock",
                "references_used": refs_used,
            })
    else:
        template = load_workflow_template("character_lock_photomaker.json")
        source_path, _ = resolve_sprite_source_image(project, project_dir)
        conditioning_filename = upload_image_to_comfyui(DEFAULT_COMFYUI_BASE_URL, source_path)
        checkpoint_name = DEFAULT_COMFYUI_CHECKPOINT
        brief = project.get("brief") or {}
        base_positive = prompt or build_positive_prompt_base(brief)
        for index in range(AI_CHARACTER_LOCK_COUNT):
            seed = int(parameters.get("seed", 1000 + index))
            call_progress(progress, 10 + int((index / AI_CHARACTER_LOCK_COUNT) * 72), "Character Lock %d of %d" % (index + 1, AI_CHARACTER_LOCK_COUNT), "Generating identity-locked candidate set.")
            request = ConceptRequest(
                project_id=project_id,
                positive_prompt=base_positive,
                negative_prompt=negative_prompt,
                width=CONCEPT_CANVAS[0],
                height=CONCEPT_CANVAS[1],
                seed=seed,
                count=1,
                references=[],
                mode="character_lock",
                refine_from_image=None,
                refine_strength=None,
                variation_axes={"summary": "character lock seed %d" % seed},
                output_path=None,
                checkpoint_name=checkpoint_name,
            )
            output_prefix = "sprite-workbench/%s/ai_sideview_v1/character_lock/%s_%02d" % (project_id, run_id, index)
            prompt_graph = prepare_workflow_prompt(template, request, output_prefix, checkpoint_name, conditioning_filename)
            result_paths = run_comfy_prompt_graph(prompt_graph, output_root)
            if not result_paths:
                raise ValueError("ComfyUI Character Lock run did not return any images.")
            asset_name = _ai_candidate_label(index)
            target_path = output_root / ("%s.png" % asset_name)
            # Copy the first result into a stable per-candidate filename.
            target_path.write_bytes(result_paths[0].read_bytes())
            candidates.append({
                "asset_id": "character_lock:%s:%s" % (run_id, asset_name),
                "label": asset_name,
                "image_path": str(target_path.relative_to(project_dir)),
                "seed": seed,
                "workflow_id": "photomaker_ipadapter_character_lock",
                "references_used": refs_used,
            })

    run = {
        "run_id": run_id,
        "stage": "character_lock",
        "workflow_profile": workflow_profile,
        "created_at": now_iso(),
        "status": "completed",
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "source_asset_ids": source_asset_ids,
        "references_used": refs_used,
        "dependency_snapshot": copy.deepcopy(store.get("dependency_status") or {}),
        "candidates": candidates,
        "output_dir": str(output_root.relative_to(project_dir)),
    }
    store["character_lock"]["runs"][run_id] = run
    store["selected_assets"]["approved_concept_id"] = project.get("selected_concept_id")
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["current_stage"] = "rig_layout"
    project["status"] = "ai_character_lock_ready"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Character Lock ready", "Six identity-locked candidates were written to the project.")
    return run


def run_ai_key_pose_set(project_id: str, workflow_profile: str, source_asset_ids: List[str], parameters: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    approved_asset = _ai_find_character_lock_asset(store, store.get("character_lock", {}).get("approved_asset_id"))
    if not approved_asset:
        raise ValueError("Approve a Character Lock candidate before generating key poses.")
    _ai_require_stack_ready(project)
    project_dir = PROJECTS_ROOT / project_id
    backend_mode = _ai_backend_mode(project)
    run_id = "poses-%s" % uuid.uuid4().hex[:8]
    output_root = ai_workflow_root(project_dir, "key_pose_set", run_id=run_id)
    poses: List[Dict[str, Any]] = []

    if backend_mode == "debug_procedural":
        base = Image.open(project_dir / approved_asset["image_path"]).convert("RGBA")
        pose_variants = {
            "idle_a": {"dx": -2, "dy": 0, "scale": 1.0, "rotate": -0.4},
            "idle_b": {"dx": 2, "dy": -2, "scale": 1.0, "rotate": 0.4},
            "walk_contact_front": {"dx": -10, "dy": 2, "scale": 1.0, "rotate": -1.2},
            "walk_passing_front": {"dx": -2, "dy": -6, "scale": 0.98, "rotate": -0.2},
            "walk_contact_back": {"dx": 10, "dy": 2, "scale": 1.0, "rotate": 1.2},
            "walk_passing_back": {"dx": 2, "dy": -6, "scale": 0.98, "rotate": 0.2},
        }
        for index, pose_name in enumerate(AI_KEY_POSE_NAMES):
            call_progress(progress, 10 + int((index / len(AI_KEY_POSE_NAMES)) * 74), "Key Pose %d of %d" % (index + 1, len(AI_KEY_POSE_NAMES)), "Generating canonical pose board.")
            variant = _ai_transform_variant(base, **pose_variants[pose_name])
            output_path = output_root / ("%s.png" % pose_name)
            _ai_write_asset(variant, output_path)
            poses.append({
                "asset_id": "key_pose:%s:%s" % (run_id, pose_name),
                "pose_name": pose_name,
                "image_path": str(output_path.relative_to(project_dir)),
                "source_character_lock_asset_id": approved_asset["asset_id"],
            })
    else:
        template = load_workflow_template("key_pose_photomaker.json")
        checkpoint_name = DEFAULT_COMFYUI_CHECKPOINT
        conditioning_filename = upload_image_to_comfyui(DEFAULT_COMFYUI_BASE_URL, project_dir / approved_asset["image_path"])
        brief = project.get("brief") or {}
        base_positive = build_positive_prompt_base(brief)
        negative_prompt = (project.get("brief") or {}).get("negative_prompt") or DEFAULT_NEGATIVE_PROMPT
        pose_prompts = {
            "idle_a": "idle pose, relaxed stance, minimal motion blur",
            "idle_b": "idle pose, subtle weight shift, minimal motion blur",
            "walk_contact_front": "walk cycle contact pose, front leg contacting ground",
            "walk_passing_front": "walk cycle passing pose, front leg passing under body",
            "walk_contact_back": "walk cycle contact pose, rear leg contacting ground",
            "walk_passing_back": "walk cycle passing pose, rear leg passing under body",
        }
        for index, pose_name in enumerate(AI_KEY_POSE_NAMES):
            call_progress(progress, 10 + int((index / len(AI_KEY_POSE_NAMES)) * 74), "Key Pose %d of %d" % (index + 1, len(AI_KEY_POSE_NAMES)), "Generating canonical pose board.")
            seed = stable_int(project_id, run_id, pose_name, base_positive, pose_prompts.get(pose_name, pose_name))
            positive_prompt = "%s, %s" % (base_positive, pose_prompts.get(pose_name, pose_name))
            request = ConceptRequest(
                project_id=project_id,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                width=CONCEPT_CANVAS[0],
                height=CONCEPT_CANVAS[1],
                seed=seed,
                count=1,
                references=[],
                mode="key_pose_set",
                refine_from_image=None,
                refine_strength=None,
                variation_axes={"summary": "key pose %s" % pose_name},
                output_path=None,
                checkpoint_name=checkpoint_name,
            )
            output_prefix = "sprite-workbench/%s/ai_sideview_v1/key_pose/%s_%s" % (project_id, run_id, pose_name)
            prompt_graph = prepare_workflow_prompt(template, request, output_prefix, checkpoint_name, conditioning_filename)
            result_paths = run_comfy_prompt_graph(prompt_graph, output_root)
            if not result_paths:
                raise ValueError("ComfyUI Key Pose run did not return any images for %s." % pose_name)
            output_path = output_root / ("%s.png" % pose_name)
            output_path.write_bytes(result_paths[0].read_bytes())
            poses.append({
                "asset_id": "key_pose:%s:%s" % (run_id, pose_name),
                "pose_name": pose_name,
                "image_path": str(output_path.relative_to(project_dir)),
                "source_character_lock_asset_id": approved_asset["asset_id"],
            })

    run = {
        "run_id": run_id,
        "stage": "key_pose_set",
        "workflow_profile": workflow_profile,
        "created_at": now_iso(),
        "status": "completed",
        "source_asset_ids": source_asset_ids or [approved_asset["asset_id"]],
        "dependency_snapshot": copy.deepcopy(store.get("dependency_status") or {}),
        "poses": poses,
        "output_dir": str(output_root.relative_to(project_dir)),
    }
    store["key_pose_set"]["runs"][run_id] = run
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["current_stage"] = "part_manifest"
    project["status"] = "ai_key_pose_board_ready"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Key Pose Board ready", "Six canonical side-view poses were written to the project.")
    return run


def _ai_key_pose_lookup(run: Dict[str, Any]) -> Dict[str, Image.Image]:
    return {pose["pose_name"]: Image.open(Path(pose["abs_path"])).convert("RGBA") for pose in run.get("poses") or [] if pose.get("abs_path")}


def _ai_synthetic_key_pose_run_from_selected_concept(project: Dict[str, Any], project_dir: Path) -> Optional[Dict[str, Any]]:
    """
    When Character Lock / Key Pose Board UIs are removed (Phase 7.2), motion still needs pose names.
    If the user approved a concept but never generated a key pose board, reuse that concept image for every canonical pose.
    """
    cid = project.get("selected_concept_id")
    if not cid:
        return None
    concept = next((item for item in (project.get("concepts") or []) if item.get("concept_id") == cid), None)
    if not concept:
        return None
    rel = concept.get("processed_preview_image") or concept.get("preview_image") or concept.get("original_preview_image")
    if not rel:
        return None
    image_path = project_dir / str(rel)
    if not image_path.exists():
        return None
    rel_posix = Path(rel).as_posix()
    poses: List[Dict[str, Any]] = []
    for pose_name in AI_KEY_POSE_NAMES:
        poses.append({
            "asset_id": "key_pose:synthetic:%s:%s" % (cid, pose_name),
            "pose_name": pose_name,
            "image_path": rel_posix,
        })
    return {
        "run_id": "synthetic-from-approved-concept",
        "stage": "key_pose_set",
        "workflow_profile": "synthetic",
        "created_at": now_iso(),
        "status": "completed",
        "poses": poses,
        "synthetic_from_concept_id": cid,
    }


def run_ai_motion_clip(project_id: str, workflow_profile: str, clip_name: str, source_asset_ids: List[str], parameters: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    if clip_name not in AI_CLIP_SPECS:
        raise ValueError("Unknown clip: %s." % clip_name)
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    _ai_require_stack_ready(project)
    backend_mode = _ai_backend_mode(project)
    project_dir = PROJECTS_ROOT / project_id
    key_pose_run = _ai_find_key_pose_run(store, store.get("key_pose_set", {}).get("approved_run_id"))
    if not key_pose_run:
        key_pose_run = _ai_synthetic_key_pose_run_from_selected_concept(project, project_dir)
    if not key_pose_run:
        raise ValueError("Approve a Key Pose Board before running motion, or approve a concept with a preview image.")
    spec = AI_CLIP_SPECS[clip_name]
    run_id = "%s-%s" % (clip_name, uuid.uuid4().hex[:8])
    output_root = ai_workflow_root(project_dir, "motion_clip", clip_name=clip_name, run_id=run_id)
    frame_dir = output_root / "frames"
    clear_directory(output_root)
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_records = []
    sequence = spec["pose_sequence"]
    frame_total = spec["frame_count"]

    if backend_mode == "debug_procedural":
        pose_images = {}
        for pose in key_pose_run.get("poses") or []:
            image_path = project_dir / str(pose.get("image_path") or "")
            if image_path.exists():
                pose_images[pose["pose_name"]] = Image.open(image_path).convert("RGBA")
        for index in range(frame_total):
            segment_position = (index / max(1, frame_total - 1)) * (len(sequence) - 1)
            left_index = int(math.floor(segment_position))
            right_index = min(len(sequence) - 1, left_index + 1)
            blend_amount = segment_position - left_index
            left_pose = pose_images[sequence[left_index]]
            right_pose = pose_images[sequence[right_index]]
            blended = Image.blend(left_pose, right_pose, blend_amount)
            frame_name = "%s_%02d.png" % (clip_name, index)
            frame_path = frame_dir / frame_name
            _ai_write_asset(blended, frame_path)
            frame_records.append({
                "frame_name": frame_name,
                "image_path": str(frame_path.relative_to(project_dir)),
                "source_pose_names": [sequence[left_index], sequence[right_index]],
                "blend_amount": round(blend_amount, 4),
            })
            call_progress(progress, 12 + int((index / max(1, frame_total)) * 74), "Motion frame %d of %d" % (index + 1, frame_total), "Interpolating pose-to-pose motion frames.")
    else:
        template = load_workflow_template("motion_tooncrafter.json")
        prompt_graph = copy.deepcopy(template["prompt"])
        meta = template.get("meta") or {}
        motion_meta = meta.get("motion") or {}
        motion_node = motion_meta.get("node")
        if motion_node and motion_node in prompt_graph:
            node_inputs = prompt_graph[motion_node]["inputs"]
            if motion_meta.get("frames_input"):
                node_inputs[motion_meta["frames_input"]] = frame_total
            if motion_meta.get("fps_input"):
                node_inputs[motion_meta["fps_input"]] = spec["fps"]
        poses_meta = (meta.get("poses") or {}).get("load_nodes") or []
        # Map up to four unique poses from the sequence into the ToonCrafter template.
        pose_by_name = {pose["pose_name"]: pose for pose in (key_pose_run.get("poses") or [])}
        unique_sequence = []
        for name in sequence:
            if name not in unique_sequence:
                unique_sequence.append(name)
        for mapped, pose_name in zip(poses_meta, unique_sequence):
            pose = pose_by_name.get(pose_name)
            if not pose:
                continue
            image_path = project_dir / str(pose.get("image_path") or "")
            if not image_path.exists():
                continue
            uploaded = upload_image_to_comfyui(DEFAULT_COMFYUI_BASE_URL, image_path)
            node_id = mapped.get("node")
            input_name = mapped.get("input") or "image"
            if node_id and node_id in prompt_graph:
                prompt_graph[node_id]["inputs"][input_name] = uploaded
        call_progress(progress, 16, "%s motion" % clip_name.title(), "Generating motion frames via ToonCrafter.")
        result_paths = run_comfy_prompt_graph(prompt_graph, frame_dir)
        if len(result_paths) < frame_total:
            raise ValueError("ComfyUI ToonCrafter run returned %d frames, expected %d." % (len(result_paths), frame_total))
        # Truncate or use first frame_total outputs to keep invariants stable.
        for index in range(frame_total):
            path = result_paths[index]
            frame_name = "%s_%02d.png" % (clip_name, index)
            frame_path = frame_dir / frame_name
            frame_path.write_bytes(path.read_bytes())
            segment_position = (index / max(1, frame_total - 1)) * (len(sequence) - 1)
            left_index = int(math.floor(segment_position))
            right_index = min(len(sequence) - 1, left_index + 1)
            blend_amount = segment_position - left_index
            frame_records.append({
                "frame_name": frame_name,
                "image_path": str(frame_path.relative_to(project_dir)),
                "source_pose_names": [sequence[left_index], sequence[right_index]],
                "blend_amount": round(blend_amount, 4),
            })
            call_progress(progress, 12 + int((index / max(1, frame_total)) * 74), "Motion frame %d of %d" % (index + 1, frame_total), "Mapping ToonCrafter frames into the motion clip.")
    run = {
        "run_id": run_id,
        "stage": "motion_clip",
        "workflow_profile": workflow_profile,
        "clip_name": clip_name,
        "created_at": now_iso(),
        "status": "completed",
        "fps": spec["fps"],
        "frame_count": frame_total,
        "source_asset_ids": source_asset_ids or [store.get("key_pose_set", {}).get("approved_run_id")],
        "dependency_snapshot": copy.deepcopy(store.get("dependency_status") or {}),
        "frame_dir": str(frame_dir.relative_to(project_dir)),
        "frames": frame_records,
    }
    clip_group = _ai_motion_group(store, "motion_runs", clip_name)
    clip_group["runs"][run_id] = run
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["current_stage"] = "clips"
    project["status"] = "ai_motion_%s_ready" % clip_name
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "%s motion ready" % clip_name.title(), "Pose-to-pose motion frames were written to the project.")
    return run


def run_ai_extract_frames(project_id: str, workflow_profile: str, clip_name: str, source_asset_ids: List[str], parameters: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    if clip_name not in AI_CLIP_SPECS:
        raise ValueError("Unknown clip: %s." % clip_name)
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    motion_group = _ai_motion_group(store, "motion_runs", clip_name)
    motion_run = motion_group["runs"].get(motion_group.get("approved_run_id")) or next(iter((motion_group.get("runs") or {}).values()), None)
    if not motion_run:
        raise ValueError("Run motion for %s before extracting frames." % clip_name)
    project_dir = PROJECTS_ROOT / project_id
    run_id = "%s-%s" % (clip_name, uuid.uuid4().hex[:8])
    output_root = ai_workflow_root(project_dir, "extract_frames", clip_name=clip_name, run_id=run_id)
    frame_dir = output_root / "frames"
    clear_directory(output_root)
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_records = []
    for index, frame in enumerate(motion_run.get("frames") or []):
        source_image = Image.open(project_dir / frame["image_path"]).convert("RGBA")
        mask = largest_component_mask(detect_mask(source_image))
        subject = Image.new("RGBA", source_image.size, (0, 0, 0, 0))
        subject.alpha_composite(source_image)
        subject.putalpha(mask)
        bbox = normalize_mask(mask).getbbox()
        if bbox is None:
            raise ValueError("Extracted frame %s is empty." % frame["frame_name"])
        anchor_point = ((bbox[0] + bbox[2]) / 2.0, bbox[3])
        cleaned, cleanup_meta = cleanup_frame(subject, anchor_point=anchor_point)
        frame_name = "%s_%02d.png" % (clip_name, index)
        frame_path = frame_dir / frame_name
        _ai_write_asset(cleaned, frame_path)
        frame_records.append({
            "frame_name": frame_name,
            "image_path": str(frame_path.relative_to(project_dir)),
            "cleanup": cleanup_meta,
        })
        call_progress(progress, 14 + int((index / max(1, len(motion_run.get("frames") or []))) * 72), "Extract frame %d of %d" % (index + 1, len(motion_run.get("frames") or [])), "Segmenting subject and normalizing the shared pivot.")
    run = {
        "run_id": run_id,
        "stage": "extract_frames",
        "workflow_profile": workflow_profile,
        "clip_name": clip_name,
        "created_at": now_iso(),
        "status": "completed",
        "frame_dir": str(frame_dir.relative_to(project_dir)),
        "frames": frame_records,
        "source_motion_run_id": motion_run["run_id"],
    }
    clip_group = _ai_motion_group(store, "extract_runs", clip_name)
    clip_group["runs"][run_id] = run
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["current_stage"] = "clips"
    project["status"] = "ai_extract_%s_ready" % clip_name
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "%s extraction ready" % clip_name.title(), "Frames were cut out, trimmed, and aligned to one shared pivot.") 
    return run


def run_ai_pixel_cleanup(project_id: str, workflow_profile: str, clip_name: str, source_asset_ids: List[str], parameters: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    if clip_name not in AI_CLIP_SPECS:
        raise ValueError("Unknown clip: %s." % clip_name)
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    extract_group = _ai_motion_group(store, "extract_runs", clip_name)
    extract_run = extract_group["runs"].get(extract_group.get("approved_run_id")) or next(iter((extract_group.get("runs") or {}).values()), None)
    if not extract_run:
        raise ValueError("Run extraction for %s before pixel cleanup." % clip_name)
    project_dir = PROJECTS_ROOT / project_id
    run_id = "%s-%s" % (clip_name, uuid.uuid4().hex[:8])
    output_root = ai_workflow_root(project_dir, "pixel_cleanup", clip_name=clip_name, run_id=run_id)
    frame_dir = output_root / "frames"
    clear_directory(output_root)
    frame_dir.mkdir(parents=True, exist_ok=True)
    final_animation_dir = project_dir / "animations" / clip_name
    clear_directory(final_animation_dir)
    final_animation_dir.mkdir(parents=True, exist_ok=True)
    frame_names = []
    frame_records = []
    for index, frame in enumerate(extract_run.get("frames") or []):
        source_image = Image.open(project_dir / frame["image_path"]).convert("RGBA")
        cleaned = source_image.quantize(colors=32, method=Image.Quantize.FASTOCTREE).convert("RGBA")
        frame_name = "%s_%02d.png" % (clip_name, index)
        frame_path = frame_dir / frame_name
        _ai_write_asset(cleaned, frame_path)
        runtime_path = final_animation_dir / frame_name
        _ai_write_asset(cleaned, runtime_path)
        frame_names.append(frame_name)
        frame_records.append({
            "frame_name": frame_name,
            "image_path": str(frame_path.relative_to(project_dir)),
            "runtime_image_path": str(runtime_path.relative_to(project_dir)),
            "cleanup": {"pivot": list(FRAME_PIVOT), "anchor_target": list(FRAME_PIVOT)},
        })
        call_progress(progress, 14 + int((index / max(1, len(extract_run.get("frames") or []))) * 72), "Cleanup frame %d of %d" % (index + 1, len(extract_run.get("frames") or [])), "Applying pixel-art cleanup and writing runtime-ready frames.")
    manifest = _ai_render_manifest_for_frames(clip_name, frame_names)
    write_json(frame_dir.parent / "render_manifest.json", manifest)
    write_json(final_animation_dir / "render_manifest.json", manifest)
    run = {
        "run_id": run_id,
        "stage": "pixel_cleanup",
        "workflow_profile": workflow_profile,
        "clip_name": clip_name,
        "created_at": now_iso(),
        "status": "completed",
        "frame_dir": str(frame_dir.relative_to(project_dir)),
        "frames": frame_records,
        "render_manifest_path": str((frame_dir.parent / "render_manifest.json").relative_to(project_dir)),
        "source_extract_run_id": extract_run["run_id"],
    }
    clip_group = _ai_motion_group(store, "cleanup_runs", clip_name)
    clip_group["runs"][run_id] = run
    store["updated_at"] = now_iso()
    selected = store.get("selected_assets") or {}
    selected.setdefault("cleanup_run_ids", {})
    selected["cleanup_run_ids"][clip_name] = run_id
    store["selected_assets"] = selected
    project["ai_workflow"] = store
    project["current_stage"] = "clips"
    project["status"] = "ai_cleanup_%s_ready" % clip_name
    project["updated_at"] = now_iso()
    clips = project.get("animation_clips") or {}
    clips.setdefault(clip_name, {})
    clips[clip_name].update({
        "clip_name": clip_name,
        "frame_count": AI_CLIP_SPECS[clip_name]["frame_count"],
        "fps": AI_CLIP_SPECS[clip_name]["fps"],
        "loop": True,
        "root_motion_policy": "ai_sideview_v1",
        "controls": {},
        "frame_overrides": [{} for _ in range(AI_CLIP_SPECS[clip_name]["frame_count"])],
    })
    project["animation_clips"] = clips
    save_project(project)
    call_progress(progress, 100, "%s cleanup ready" % clip_name.title(), "Runtime-ready cleaned frames were written for QA and export.")
    return run


def run_ai_workflow_stage(project_id: str, payload: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    stage = str(payload.get("stage") or "").strip()
    workflow_profile = str(payload.get("workflow_profile") or AI_WORKFLOW_PROFILE).strip() or AI_WORKFLOW_PROFILE
    if workflow_profile != AI_WORKFLOW_PROFILE:
        raise ValueError("Unsupported workflow profile: %s." % workflow_profile)
    source_asset_ids = [str(item) for item in (payload.get("source_asset_ids") or []) if str(item).strip()]
    clip_name = str(payload.get("clip_name") or "").strip() or None
    parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
    if stage == "character_lock":
        return run_ai_character_lock(project_id, workflow_profile, source_asset_ids, parameters, progress=progress)
    if stage == "key_pose_set":
        return run_ai_key_pose_set(project_id, workflow_profile, source_asset_ids, parameters, progress=progress)
    if stage == "motion_clip":
        if not clip_name:
            raise ValueError("motion_clip requires clip_name.")
        return run_ai_motion_clip(project_id, workflow_profile, clip_name, source_asset_ids, parameters, progress=progress)
    if stage == "extract_frames":
        if not clip_name:
            raise ValueError("extract_frames requires clip_name.")
        return run_ai_extract_frames(project_id, workflow_profile, clip_name, source_asset_ids, parameters, progress=progress)
    if stage == "pixel_cleanup":
        if not clip_name:
            raise ValueError("pixel_cleanup requires clip_name.")
        return run_ai_pixel_cleanup(project_id, workflow_profile, clip_name, source_asset_ids, parameters, progress=progress)
    raise ValueError("Unknown ai_workflow stage: %s." % stage)


def approve_ai_workflow(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    stage = str(payload.get("stage") or "").strip()
    run_id = str(payload.get("run_id") or "").strip()
    asset_id = str(payload.get("asset_id") or "").strip() or None
    clip_name = str(payload.get("clip_name") or "").strip() or None
    selected = store.get("selected_assets") or {}
    if stage == "character_lock":
        run = (store.get("character_lock", {}).get("runs") or {}).get(run_id)
        if not run:
            raise ValueError("Unknown Character Lock run.")
        if not asset_id or not any(item.get("asset_id") == asset_id for item in (run.get("candidates") or [])):
            raise ValueError("Character Lock approval requires a candidate asset_id from the selected run.")
        store["character_lock"]["approved_run_id"] = run_id
        store["character_lock"]["approved_asset_id"] = asset_id
        selected["character_lock_run_id"] = run_id
        selected["character_lock_asset_id"] = asset_id
        project["current_stage"] = "part_manifest"
        project["status"] = "ai_character_lock_approved"
    elif stage == "key_pose_set":
        run = (store.get("key_pose_set", {}).get("runs") or {}).get(run_id)
        if not run:
            raise ValueError("Unknown Key Pose Board run.")
        store["key_pose_set"]["approved_run_id"] = run_id
        selected["key_pose_run_id"] = run_id
        project["current_stage"] = "clips"
        project["status"] = "ai_key_pose_board_approved"
    elif stage in {"motion_clip", "extract_frames", "pixel_cleanup"}:
        if clip_name not in AI_CLIP_SPECS:
            raise ValueError("%s approval requires clip_name." % stage)
        mapping = {
            "motion_clip": "motion_runs",
            "extract_frames": "extract_runs",
            "pixel_cleanup": "cleanup_runs",
        }
        clip_group = _ai_motion_group(store, mapping[stage], clip_name)
        if run_id not in (clip_group.get("runs") or {}):
            raise ValueError("Unknown %s run for %s." % (stage, clip_name))
        clip_group["approved_run_id"] = run_id
        selected.setdefault("%s_run_ids" % stage.split("_")[0], {})
        key_name = {
            "motion_clip": "motion_run_ids",
            "extract_frames": "extract_run_ids",
            "pixel_cleanup": "cleanup_run_ids",
        }[stage]
        selected.setdefault(key_name, {})
        selected[key_name][clip_name] = run_id
        project["current_stage"] = "qa" if stage == "pixel_cleanup" else "clips"
        project["status"] = "ai_%s_%s_approved" % (stage, clip_name)
    else:
        raise ValueError("Unknown AI workflow stage: %s." % stage)
    store["selected_assets"] = selected
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["ai_workflow"]


def reject_ai_workflow(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    stage = str(payload.get("stage") or "").strip()
    run_id = str(payload.get("run_id") or "").strip()
    clip_name = str(payload.get("clip_name") or "").strip() or None
    reason = str(payload.get("reason") or "").strip() or None
    if stage == "character_lock":
        run = (store.get("character_lock", {}).get("runs") or {}).get(run_id)
        if not run:
            raise ValueError("Unknown Character Lock run.")
        run["status"] = "rejected"
        run["rejection_reason"] = reason
        if store["character_lock"].get("approved_run_id") == run_id:
            store["character_lock"]["approved_run_id"] = None
            store["character_lock"]["approved_asset_id"] = None
    elif stage == "key_pose_set":
        run = (store.get("key_pose_set", {}).get("runs") or {}).get(run_id)
        if not run:
            raise ValueError("Unknown Key Pose Board run.")
        run["status"] = "rejected"
        run["rejection_reason"] = reason
        if store["key_pose_set"].get("approved_run_id") == run_id:
            store["key_pose_set"]["approved_run_id"] = None
    elif stage in {"motion_clip", "extract_frames", "pixel_cleanup"}:
        if clip_name not in AI_CLIP_SPECS:
            raise ValueError("%s rejection requires clip_name." % stage)
        mapping = {
            "motion_clip": "motion_runs",
            "extract_frames": "extract_runs",
            "pixel_cleanup": "cleanup_runs",
        }
        clip_group = _ai_motion_group(store, mapping[stage], clip_name)
        run = (clip_group.get("runs") or {}).get(run_id)
        if not run:
            raise ValueError("Unknown %s run for %s." % (stage, clip_name))
        run["status"] = "rejected"
        run["rejection_reason"] = reason
        if clip_group.get("approved_run_id") == run_id:
            clip_group["approved_run_id"] = None
    else:
        raise ValueError("Unknown AI workflow stage: %s." % stage)
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["status"] = "ai_%s_rejected" % stage
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["ai_workflow"]


def make_character_spec(project: Dict[str, Any], concept: Dict[str, Any]) -> Dict[str, Any]:
    seed_history = [item["seed"] for item in project["concepts"] if item.get("seed") is not None]
    rig_profile = select_rig_profile(project, concept)
    return {
        "approved_concept_id": concept["concept_id"],
        "canonical_prompt": concept["positive_prompt"],
        "negative_prompt": concept["negative_prompt"],
        "prompt_lineage": {
            "run_id": concept.get("run_id"),
            "parent_concept_id": concept.get("lineage", {}).get("parent_concept_id"),
            "backend_name": concept.get("backend_name"),
            "backend_run_id": concept.get("backend_run_id"),
        },
        "palette_direction": concept.get("palette_direction"),
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
        "rig_profile": rig_profile,
        "rig_profile_flags": copy.deepcopy(RIG_PROFILES[rig_profile]["flags"]),
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


def get_rig_layout(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    layout = project.get("rig_layout")
    if not layout:
        raise ValueError("No rig layout is available for this project.")
    return layout


def generate_rig_layout(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("selected_concept_id"):
        raise ValueError("Accept a concept before generating the rig layout.")
    concept = selected_concept(project)
    rig_profile = active_rig_profile_name(project)
    if isinstance(project.get("character_spec"), dict):
        rig_profile = project["character_spec"].get("rig_profile") or rig_profile
    reset_downstream_assets(project_id, "rig_layout")
    project = clear_project_downstream_state(project, "rig_layout")
    layout = resolve_rig_layout(project, concept, rig_profile=rig_profile, persist=True)
    project["rig_layout"] = layout
    project["rig_layout_history"] = load_json(rig_layout_history_path(PROJECTS_ROOT / project_id), default_rig_layout_history(project_id))
    project["rig_layout_approved"] = False
    project["current_stage"] = "rig_layout"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["rig_layout"]


def update_rig_layout(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    layout = copy.deepcopy(project.get("rig_layout"))
    if not isinstance(layout, dict):
        raise ValueError("Generate the rig layout before editing it.")
    operation = str(payload.get("operation") or "").strip() or "replace_layout"
    if operation == "replace_layout":
        incoming = payload.get("rig_layout")
        if not isinstance(incoming, dict):
            raise ValueError("replace_layout requires a rig_layout object.")
        layout = copy.deepcopy(incoming)
    elif operation == "update_part":
        part_name = str(payload.get("part_name") or "").strip()
        part = next((item for item in layout.get("parts", []) if item.get("part_name") == part_name), None)
        if part is None:
            raise ValueError("Part not found: %s" % part_name)
        for field in ["parent_joint", "draw_order", "pivot_strategy", "extraction_region", "overlay_only", "required"]:
            if field in payload:
                part[field] = copy.deepcopy(payload[field])
    elif operation == "update_flags":
        flags = payload.get("flags")
        if not isinstance(flags, dict):
            raise ValueError("update_flags requires flags.")
        layout.setdefault("flags", {}).update(copy.deepcopy(flags))
    elif operation == "apply_codex_response":
        response_text = str(payload.get("response_text") or "").strip()
        parsed = extract_json_object_from_text(response_text)
        codex_valid = parsed.get("valid")
        if codex_valid is None:
            decision = str(parsed.get("decision") or "").strip().lower()
            codex_valid = decision == "valid"
        summary = str(parsed.get("summary") or parsed.get("feedback") or "").strip()
        layout_payload = parsed.get("rig_layout") if isinstance(parsed.get("rig_layout"), dict) else parsed.get("layout")
        if codex_valid:
            if not isinstance(layout_payload, dict):
                raise ValueError("Codex marked the image valid but did not include a rig_layout object.")
            layout = copy.deepcopy(layout_payload)
            layout["codex_check"] = {
                "valid": True,
                "summary": summary or "Codex marked this concept valid for the current rig layout step.",
                "applied_at": now_iso(),
                "raw_response_excerpt": response_text[:1200],
            }
        else:
            layout.setdefault("codex_check", {})
            layout["codex_check"].update({
                "valid": False,
                "summary": summary or "Codex did not approve this image for rig layout generation.",
                "applied_at": now_iso(),
                "raw_response_excerpt": response_text[:1200],
            })
    else:
        raise ValueError("Unsupported rig-layout operation.")

    profile_name = active_rig_profile_name(project, layout)
    layout["rig_profile"] = profile_name
    layout["draw_order"] = [item["part_name"] for item in sorted(layout.get("parts", []), key=lambda item: item.get("draw_order", 0))]
    layout["extraction_rules"] = {item["part_name"]: item.get("extraction_region") for item in layout.get("parts", [])}
    layout["pivot_rules"] = {item["part_name"]: item.get("pivot_strategy") for item in layout.get("parts", [])}
    layout["validation"] = validate_rig_layout(layout)
    if layout["validation"]["status"] != "pass":
        raise ValueError("; ".join(layout["validation"]["errors"]))
    layout["approved"] = False
    reset_downstream_assets(project_id, "rig_layout")
    project = clear_project_downstream_state(project, "rig_layout")
    write_json(canonical_downstream_path(project_dir, "rig_layout"), layout)
    project["rig_layout"] = layout
    project["rig_layout_history"] = create_rig_layout_revision(project_dir, layout, "update", operation=operation)
    project["rig_layout_approved"] = False
    project["current_stage"] = "rig_layout"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["rig_layout"]


def approve_rig_layout(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    layout = copy.deepcopy(project.get("rig_layout"))
    if not isinstance(layout, dict):
        raise ValueError("Generate the rig layout before approving it.")
    validation = validate_rig_layout(layout)
    if validation["status"] != "pass":
        raise ValueError("Rig layout approval is blocked: %s" % "; ".join(validation["errors"]))
    layout["approved"] = True
    project["rig_layout"] = layout
    project["rig_layout_approved"] = True
    project["current_stage"] = "rig_layout"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)


def build_part_manifest_handoff_prompt(project: Dict[str, Any], part_manifest: Optional[Dict[str, Any]] = None) -> str:
    layout = project.get("rig_layout") or {}
    concept = None
    try:
        concept = selected_concept(project)
    except Exception:
        concept = None
    parts = list(layout.get("parts") or [])
    current_parts = list((part_manifest or {}).get("parts") or [])
    lines = [
        "You are proposing a configurable part manifest for a deterministic 2D sprite pipeline.",
        "Use the approved source image and approved rig layout as context, but return the practical authored part list rather than a theoretical anatomy split.",
        "",
        "Goals:",
        "- keep the part list conservative and production-friendly",
        "- mark clearly optional parts as optional",
        "- keep ambiguous hanging cloth or cape masses as overlays where appropriate",
        "- do not invent hidden-side anatomy",
        "- prefer merged masses when separation is visually ambiguous",
        "",
        "Return exactly one JSON object with:",
        '{ "valid": true, "summary": "short summary", "part_manifest": { "parts": [...] } }',
        "",
        "Each part entry must include:",
        "- part_name",
        "- part_label",
        "- part_role",
        "- required",
        "- overlay_only",
        "- parent_joint",
        "- draw_order",
        "- source",
        "- editable",
        "- notes",
        "",
        "Allowed base part names from rig layout:",
        "- %s" % "\n- ".join(item["part_name"] for item in parts),
    ]
    if current_parts:
        lines.extend([
            "",
            "Current manifest draft:",
            "- %s" % "\n- ".join("%s (%s)" % (item.get("part_name"), "required" if item.get("required") else "optional") for item in current_parts),
        ])
    if concept:
        lines.extend([
            "",
            "Context:",
            f"- selected concept id: {concept.get('concept_id')}",
            f"- source image: {concept.get('approved_source_image')}",
        ])
    return "\n".join(lines)


def build_part_shapes_handoff_prompt(project: Dict[str, Any], part_shapes: Optional[Dict[str, Any]] = None) -> str:
    manifest = project.get("part_manifest") or {}
    lines = [
        "You are proposing candidate part polygons or masks for a deterministic 2D sprite pipeline.",
        "Use the approved source image and approved part manifest.",
        "",
        "Rules:",
        "- return candidate polygons or masks only for manifest parts",
        "- no speculative hidden anatomy",
        "- merge masses where separation is ambiguous",
        "- prioritize reconstruction fidelity over anatomical completeness",
        "- all outputs remain editable drafts",
        "",
        "Return exactly one JSON object with:",
        '{ "valid": true, "summary": "short summary", "part_shapes": { "parts": [...] } }',
    ]
    if manifest.get("parts"):
        lines.extend([
            "",
            "Approved manifest parts:",
            "- %s" % "\n- ".join(item["part_name"] for item in manifest["parts"]),
        ])
    if part_shapes and part_shapes.get("parts"):
        lines.extend([
            "",
            "Current shape draft parts:",
            "- %s" % "\n- ".join(item["part_name"] for item in part_shapes["parts"]),
        ])
    return "\n".join(lines)


def get_part_manifest(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    payload = project.get("part_manifest")
    if not payload:
        raise ValueError("No part manifest is available for this project.")
    return payload


def get_part_shapes(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    payload = project.get("part_shapes")
    if not payload:
        raise ValueError("No part shapes are available for this project.")
    return payload


def generate_part_manifest(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("selected_concept_id"):
        raise ValueError("Accept a concept before generating the part manifest.")
    if not project.get("rig_layout_approved"):
        raise ValueError("Approve the rig layout before generating the part manifest.")
    project_dir = PROJECTS_ROOT / project_id
    concept = selected_concept(project)
    rig_layout = project.get("rig_layout") or resolve_rig_layout(project, concept, persist=False)
    existing_part_shapes = copy.deepcopy(project.get("part_shapes"))
    manifest = build_default_part_manifest(project, rig_layout, concept)
    preserved_part_shapes = preserve_part_shapes_for_manifest(project, manifest, existing_part_shapes)
    reset_downstream_assets(project_id, "part_manifest")
    project = clear_project_downstream_state(project, "part_manifest")
    write_json(canonical_downstream_path(project_dir, "part_manifest"), manifest)
    project["part_manifest"] = manifest
    project["part_manifest_history"] = create_part_manifest_revision(project_dir, manifest, "generate")
    if isinstance(preserved_part_shapes, dict):
        preserved_part_shapes["manifest_revision_id"] = project["part_manifest_history"]["current_revision_id"]
        preserved_part_shapes = refresh_part_shape_assets(project_id, preserved_part_shapes)
        write_json(canonical_downstream_path(project_dir, "part_shapes"), preserved_part_shapes)
        project["part_shapes"] = preserved_part_shapes
        project["part_shapes_history"] = create_part_shapes_revision(project_dir, preserved_part_shapes, "update", operation="manifest_refresh")
        project["part_shapes_approved"] = False
    project["part_manifest_approved"] = False
    project["current_stage"] = "part_manifest"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["part_manifest"]


def update_part_manifest(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    manifest = copy.deepcopy(project.get("part_manifest"))
    existing_part_shapes = copy.deepcopy(project.get("part_shapes"))
    rename_map: Dict[str, str] = {}
    if not isinstance(manifest, dict):
        raise ValueError("Generate the part manifest before editing it.")
    operation = str(payload.get("operation") or "").strip() or "replace_manifest"
    if operation == "replace_manifest":
        incoming = payload.get("part_manifest")
        if not isinstance(incoming, dict):
            raise ValueError("replace_manifest requires a part_manifest object.")
        manifest = copy.deepcopy(incoming)
    elif operation == "apply_codex_response":
        parsed = extract_json_object_from_text(str(payload.get("response_text") or ""))
        manifest_payload = parsed.get("part_manifest")
        if not isinstance(manifest_payload, dict):
            raise ValueError("Codex response did not include a part_manifest object.")
        manifest = copy.deepcopy(manifest_payload)
    elif operation == "add_optional_part":
        part_name = str(payload.get("part_name") or "").strip()
        if not part_name:
            raise ValueError("add_optional_part requires part_name.")
        manifest.setdefault("parts", []).append({
            "part_name": part_name,
            "part_label": str(payload.get("part_label") or humanize_identifier(part_name)),
            "part_role": str(payload.get("part_role") or part_name),
            "required": False,
            "overlay_only": bool(payload.get("overlay_only")),
            "parent_joint": str(payload.get("parent_joint") or "torso"),
            "draw_order": int(payload.get("draw_order", len(manifest.get("parts") or []) + 1)),
            "source": str(payload.get("source") or "manual"),
            "editable": True,
            "notes": str(payload.get("notes") or ""),
        })
    elif operation in {"update_part", "rename_part"}:
        part_name = str(payload.get("part_name") or "").strip()
        part = next((item for item in manifest.get("parts", []) if item.get("part_name") == part_name), None)
        if part is None:
            raise ValueError("Part not found: %s" % part_name)
        if operation == "rename_part":
            new_name = str(payload.get("new_part_name") or "").strip()
            if not new_name:
                raise ValueError("rename_part requires new_part_name.")
            rename_map[part_name] = new_name
            part["part_name"] = new_name
        for field in ["part_label", "part_role", "required", "overlay_only", "parent_joint", "draw_order", "editable", "notes", "source"]:
            if field in payload:
                part[field] = copy.deepcopy(payload[field])
    elif operation == "delete_optional_part":
        part_name = str(payload.get("part_name") or "").strip()
        before = len(manifest.get("parts") or [])
        manifest["parts"] = [item for item in manifest.get("parts", []) if item.get("part_name") != part_name or item.get("required")]
        if len(manifest["parts"]) == before:
            raise ValueError("Optional part not found or cannot delete required part.")
    elif operation == "merge_parts":
        target_name = str(payload.get("target_name") or "").strip()
        source_names = [str(item).strip() for item in (payload.get("source_names") or []) if str(item).strip()]
        if not target_name or len(source_names) < 1:
            raise ValueError("merge_parts requires target_name and one or more source_names.")
        target = next((item for item in manifest.get("parts", []) if item.get("part_name") == target_name), None)
        if target is None:
            raise ValueError("Target part not found.")
        manifest["parts"] = [item for item in manifest.get("parts", []) if item.get("part_name") not in set(source_names)]
        target["source"] = "manual"
        target["notes"] = ("Merged from: %s" % ", ".join(source_names)).strip()
    elif operation == "reset_to_rig_profile_default":
        concept = selected_concept(project)
        manifest = build_default_part_manifest(project, project.get("rig_layout") or {}, concept)
    else:
        raise ValueError("Unsupported part-manifest operation.")
    manifest["project_id"] = project_id
    manifest["approved_concept_id"] = project.get("selected_concept_id")
    manifest["rig_profile"] = active_rig_profile_name(project, project.get("rig_layout"))
    manifest["source_rig_layout_revision"] = (project.get("rig_layout_history") or {}).get("current_revision_id")
    manifest["updated_at"] = now_iso()
    manifest["validation"] = validate_part_manifest(manifest)
    manifest["approved"] = False
    preserved_part_shapes = preserve_part_shapes_for_manifest(project, manifest, existing_part_shapes, rename_map=rename_map)
    reset_downstream_assets(project_id, "part_manifest")
    project = clear_project_downstream_state(project, "part_manifest")
    write_json(canonical_downstream_path(project_dir, "part_manifest"), manifest)
    project["part_manifest"] = manifest
    project["part_manifest_history"] = create_part_manifest_revision(project_dir, manifest, "update", operation=operation)
    if isinstance(preserved_part_shapes, dict):
        preserved_part_shapes["manifest_revision_id"] = project["part_manifest_history"]["current_revision_id"]
        preserved_part_shapes = refresh_part_shape_assets(project_id, preserved_part_shapes)
        write_json(canonical_downstream_path(project_dir, "part_shapes"), preserved_part_shapes)
        project["part_shapes"] = preserved_part_shapes
        project["part_shapes_history"] = create_part_shapes_revision(project_dir, preserved_part_shapes, "update", operation="manifest_refresh")
        project["part_shapes_approved"] = False
    project["part_manifest_approved"] = False
    project["current_stage"] = "part_manifest"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["part_manifest"]


def approve_part_manifest(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    manifest = copy.deepcopy(project.get("part_manifest"))
    if not isinstance(manifest, dict):
        raise ValueError("Generate the part manifest before approving it.")
    validation = validate_part_manifest(manifest)
    if validation["status"] == "fail":
        raise ValueError("Part manifest approval is blocked: %s" % "; ".join(validation["failures"]))
    manifest["approved"] = True
    manifest["updated_at"] = now_iso()
    project["part_manifest"] = manifest
    project["part_manifest_approved"] = True
    project["current_stage"] = "part_manifest"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)


def initialize_part_shapes(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("selected_concept_id"):
        raise ValueError("Accept a concept before initializing part shapes.")
    if not project.get("part_manifest_approved"):
        raise ValueError("Approve the part manifest before initializing part shapes.")
    project_dir = PROJECTS_ROOT / project_id
    approved_path, approved_rel = resolve_sprite_source_image(project, project_dir)
    source_image = Image.open(approved_path).convert("RGBA")
    reset_downstream_assets(project_id, "part_shapes")
    project = clear_project_downstream_state(project, "part_shapes")
    part_shapes = build_default_part_shapes(project, project.get("part_manifest") or {}, source_image, approved_rel, operation_source="auto_init")
    write_json(canonical_downstream_path(project_dir, "part_shapes"), part_shapes)
    project["part_shapes"] = part_shapes
    project["part_shapes_history"] = create_part_shapes_revision(project_dir, part_shapes, "generate")
    project["part_shapes_approved"] = False
    project["current_stage"] = "part_shape_edit"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["part_shapes"]


def refresh_part_shape_assets(project_id: str, part_shapes: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    source_rel = str(part_shapes.get("source_image") or "")
    source_path = project_dir / source_rel
    if not source_rel or not source_path.exists():
        approved_path, approved_rel = resolve_sprite_source_image(project, project_dir)
        source_path = approved_path
        source_rel = approved_rel
        part_shapes["source_image"] = approved_rel
    source_image = Image.open(source_path).convert("RGBA")
    for entry in list(part_shapes.get("parts") or []):
        vertices = [clamp_point_to_image((point[0], point[1]), source_image.size) for point in (entry.get("vertices") or [])]
        entry["vertices"] = vertices
        mask = render_polygon_mask(source_image.size, vertices, closed=bool(entry.get("closed", True)))
        mask_path, preview_path, bbox = write_part_shape_assets(project_dir, str(entry.get("part_name") or ""), source_image, mask)
        entry["mask_path"] = mask_path
        entry["preview_path"] = preview_path
        entry["bbox"] = bbox
    part_shapes["updated_at"] = now_iso()
    part_shapes["validation"] = validate_part_shapes(project_dir, part_shapes, project.get("part_manifest"))
    return part_shapes


def update_part_shapes(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    part_shapes = copy.deepcopy(project.get("part_shapes"))
    if not isinstance(part_shapes, dict):
        raise ValueError("Initialize part shapes before editing them.")
    operation = str(payload.get("operation") or "").strip() or "replace_shapes"
    if operation == "replace_shapes":
        incoming = payload.get("part_shapes")
        if not isinstance(incoming, dict):
            raise ValueError("replace_shapes requires a part_shapes object.")
        part_shapes = copy.deepcopy(incoming)
    elif operation == "apply_codex_response":
        parsed = extract_json_object_from_text(str(payload.get("response_text") or ""))
        shape_payload = parsed.get("part_shapes")
        if not isinstance(shape_payload, dict):
            raise ValueError("Codex response did not include a part_shapes object.")
        part_shapes = copy.deepcopy(shape_payload)
    elif operation in {"update_part", "reset_part_shape"}:
        part_name = str(payload.get("part_name") or "").strip()
        part = next((item for item in part_shapes.get("parts", []) if item.get("part_name") == part_name), None)
        if part is None:
            raise ValueError("Part shape not found: %s" % part_name)
        if operation == "reset_part_shape":
            source_rel = str(part_shapes.get("source_image") or "")
            source_path = project_dir / source_rel
            if not source_rel or not source_path.exists():
                source_path, source_rel = resolve_sprite_source_image(project, project_dir)
            source_image = Image.open(source_path).convert("RGBA")
            refreshed = build_default_part_shapes(project, {"parts": [next(item for item in (project.get("part_manifest") or {}).get("parts", []) if item.get("part_name") == part_name)]}, source_image, source_rel, operation_source="auto_init")
            if refreshed.get("parts"):
                index = next((idx for idx, item in enumerate(part_shapes.get("parts", [])) if item.get("part_name") == part_name), None)
                if index is not None:
                    part_shapes["parts"][index] = refreshed["parts"][0]
        else:
            for field in ["shape_type", "vertices", "closed", "source_method", "status", "notes", "locked", "visible", "color", "part_label"]:
                if field in payload:
                    part[field] = copy.deepcopy(payload[field])
    else:
        raise ValueError("Unsupported part-shapes operation.")
    part_shapes["project_id"] = project_id
    part_shapes["approved_concept_id"] = project.get("selected_concept_id")
    part_shapes["manifest_revision_id"] = (project.get("part_manifest_history") or {}).get("current_revision_id")
    part_shapes["approved"] = False
    reset_downstream_assets(project_id, "part_shapes")
    project = clear_project_downstream_state(project, "part_shapes")
    part_shapes = refresh_part_shape_assets(project_id, part_shapes)
    write_json(canonical_downstream_path(project_dir, "part_shapes"), part_shapes)
    project["part_shapes"] = part_shapes
    project["part_shapes_history"] = create_part_shapes_revision(project_dir, part_shapes, "update", operation=operation)
    project["part_shapes_approved"] = False
    project["current_stage"] = "part_shape_edit"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["part_shapes"]


def approve_part_shapes(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    part_shapes = copy.deepcopy(project.get("part_shapes"))
    if not isinstance(part_shapes, dict):
        raise ValueError("Initialize part shapes before approving them.")
    validation = validate_part_shapes(PROJECTS_ROOT / project_id, part_shapes, project.get("part_manifest"))
    if validation["status"] == "fail":
        raise ValueError("Part shapes approval is blocked: %s" % "; ".join(validation["failures"]))
    part_shapes["approved"] = True
    part_shapes["updated_at"] = now_iso()
    part_shapes["validation"] = validation
    project["part_shapes"] = part_shapes
    project["part_shapes_approved"] = True
    project["current_stage"] = "part_shape_edit"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)


def build_split_from_part_shapes(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("selected_concept_id"):
        raise ValueError("Accept a concept before building split assets.")
    if not project.get("part_shapes_approved"):
        raise ValueError("Approve the part shapes before building split assets.")
    project_dir = PROJECTS_ROOT / project_id
    approved_path, approved_rel = resolve_sprite_source_image(project, project_dir)
    source_image = Image.open(approved_path).convert("RGBA")
    source_mask = normalize_mask(detect_mask(source_image))
    part_shapes = project.get("part_shapes") or {}
    manifest = project.get("part_manifest") or {}
    reset_downstream_assets(project_id, "part_split")
    project = clear_project_downstream_state(project, "part_split")
    parts: List[Dict[str, Any]] = []
    assigned_mask = Image.new("L", source_image.size, 0)
    ordered_shape_entries = sorted(
        list(part_shapes.get("parts") or []),
        key=lambda entry: int(next((item.get("draw_order", 0) for item in (manifest.get("parts") or []) if item.get("part_name") == entry.get("part_name")), 0)),
        reverse=True,
    )
    for shape_entry in ordered_shape_entries:
        part_name = str(shape_entry.get("part_name") or "").strip()
        if not part_name:
            continue
        shape_mask = normalize_mask(Image.open(project_dir / shape_entry["mask_path"]).convert("L")) if shape_entry.get("mask_path") else render_polygon_mask(source_image.size, shape_entry.get("vertices") or [])
        isolated_mask = normalize_mask(ImageChops.multiply(shape_mask, source_mask))
        isolated_mask = normalize_mask(ImageChops.subtract(isolated_mask, assigned_mask))
        bbox = list(isolated_mask.getbbox() or tuple(shape_entry.get("bbox") or (0, 0, 1, 1)))
        cropped_image = image_with_mask(source_image, isolated_mask).crop(tuple(bbox))
        cropped_mask = isolated_mask.crop(tuple(bbox))
        image_path, mask_path = write_part_split_asset(project_dir, part_name, cropped_image, cropped_mask)
        manifest_entry = next((item for item in (manifest.get("parts") or []) if item.get("part_name") == part_name), {})
        parts.append({
            "part_name": part_name,
            "part_role": manifest_entry.get("part_role") or part_name,
            "required": bool(manifest_entry.get("required")),
            "image_path": image_path,
            "mask_path": mask_path,
            "bbox": bbox,
            "overlay_only": bool(manifest_entry.get("overlay_only")),
            "source_method": shape_entry.get("source_method") or "manual_edit",
            "status": "candidate",
            "notes": str(shape_entry.get("notes") or ""),
            "pivot_hint": part_pivot_from_image(part_name, cropped_image, manifest_entry),
            "parent_joint": manifest_entry.get("parent_joint"),
            "draw_order": int(manifest_entry.get("draw_order", 0)),
        })
        assigned_mask = normalize_mask(ImageChops.lighter(assigned_mask, isolated_mask))
    preview_path, reconstruction_meta = render_part_split_reconstruction(project_dir, source_image.size, parts)
    payload = {
        "layout_version": 2,
        "project_id": project_id,
        "approved_concept_id": project.get("selected_concept_id"),
        "manifest_revision_id": (project.get("part_manifest_history") or {}).get("current_revision_id"),
        "shape_revision_id": (project.get("part_shapes_history") or {}).get("current_revision_id"),
        "rig_profile": active_rig_profile_name(project, project.get("rig_layout")),
        "rig_layout": project.get("rig_layout") or {},
        "part_manifest": manifest,
        "source_image": approved_rel,
        "source_facing": estimate_facing_direction(source_mask),
        "parts": sorted(parts, key=lambda item: (int(item.get("draw_order", 0)), item["part_name"])),
        "reconstruction_preview": {"path": preview_path, **reconstruction_meta},
        "approved": False,
        "created_at": now_iso(),
    }
    payload["validation"] = validate_part_split(project_dir, payload, source_mask)
    write_json(canonical_downstream_path(project_dir, "part_split"), payload)
    project["part_split"] = payload
    project["part_split_history"] = create_part_split_revision(project_dir, payload, "generate", operation="split_build")
    project["part_split_approved"] = False
    project["split_review_approved"] = False
    project["current_stage"] = "split_build"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["part_split"]


def build_part_split_handoff_prompt(project: Dict[str, Any], part_split: Optional[Dict[str, Any]] = None) -> str:
    layout = project.get("rig_layout") or {}
    manifest = project.get("part_manifest") or {}
    concept = None
    try:
        concept = selected_concept(project)
    except Exception:
        concept = None
    lines = [
        "You are preparing separated sprite parts for a deterministic 2D sprite pipeline.",
        "Use the approved side-view concept and approved rig layout to produce candidate split parts.",
        "",
        "Rules:",
        "- return candidate part assets only for the approved manifest parts",
        "- do not invent hidden-side anatomy",
        "- preserve merged armor masses when the layout keeps them merged",
        "- overlays stay overlays; do not promote them into anatomy splits",
        "- optimize for clean neutral-pose reconstruction, not anatomy completeness",
        "- output candidates only; the user will review and approve them",
        "",
        "Expected part names:",
        "- %s" % "\n- ".join(item["part_name"] for item in ((manifest.get("parts") or []) or (layout.get("parts") or []))),
        "",
        "Required output:",
        "- one isolated transparent PNG per part when visible",
        "- one mask per part",
        "- no prose redesign",
        "- preserve source silhouette and palette",
    ]
    if concept:
        lines.extend([
            "",
            "Context:",
            f"- selected concept id: {concept.get('concept_id')}",
            f"- source image: {concept.get('approved_source_image')}",
        ])
    return "\n".join(lines)


def get_part_split(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    payload = project.get("part_split")
    if not payload:
        raise ValueError("No part split is available for this project.")
    return payload


def generate_part_split(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    if project.get("part_shapes_approved"):
        return build_split_from_part_shapes(project_id)
    if not project.get("selected_concept_id"):
        raise ValueError("Accept a concept before generating split parts.")
    if not project.get("rig_layout_approved"):
        raise ValueError("Approve the rig layout before generating split parts.")
    project_dir = PROJECTS_ROOT / project_id
    concept = selected_concept(project)
    rig_layout = project.get("rig_layout") or resolve_rig_layout(project, concept, persist=False)
    approved_path, approved_rel = resolve_sprite_source_image(project, project_dir)
    source_image = Image.open(approved_path).convert("RGBA")
    source_mask = normalize_mask(detect_mask(source_image))
    subject_bbox = source_mask.getbbox()
    if subject_bbox is None:
        raise ValueError("Could not detect a character silhouette in the approved source image.")

    reset_downstream_assets(project_id, "part_split")
    project = clear_project_downstream_state(project, "part_split")

    facing = estimate_facing_direction(source_mask)
    parts: List[Dict[str, Any]] = []
    for entry in list(rig_layout.get("parts") or []):
        extraction_region = resolve_layout_region(entry, facing) or entry.get("extraction_region")
        if not extraction_region:
            continue
        box = region_box(subject_bbox, extraction_region)
        part_image, part_mask, absolute_bbox = crop_region_from_source(source_image, source_mask, box)
        image_path, mask_path = write_part_split_asset(project_dir, entry["part_name"], part_image, part_mask)
        parts.append({
            "part_name": entry["part_name"],
            "part_role": canonical_sprite_part_role(entry, rig_layout.get("rig_profile")),
            "required": bool(entry.get("required")),
            "image_path": image_path,
            "mask_path": mask_path,
            "bbox": [int(value) for value in absolute_bbox],
            "overlay_only": bool(entry.get("overlay_only")),
            "source_method": "legacy_box_fallback",
            "status": "candidate",
            "notes": "",
            "pivot_hint": part_pivot_from_image(entry["part_name"], part_image, entry),
            "parent_joint": entry.get("parent_joint"),
            "draw_order": int(entry.get("draw_order", 0)),
        })

    preview_path, reconstruction_meta = render_part_split_reconstruction(project_dir, source_image.size, parts)
    payload = {
        "layout_version": 1,
        "project_id": project_id,
        "approved_concept_id": concept.get("concept_id"),
        "rig_profile": rig_layout.get("rig_profile"),
        "rig_layout": rig_layout,
        "source_image": approved_rel,
        "source_facing": facing,
        "parts": parts,
        "reconstruction_preview": {"path": preview_path, **reconstruction_meta},
        "approved": False,
        "created_at": now_iso(),
    }
    payload["validation"] = validate_part_split(project_dir, payload, source_mask)
    write_json(canonical_downstream_path(project_dir, "part_split"), payload)
    project["part_split"] = payload
    project["part_split_history"] = create_part_split_revision(project_dir, payload, "generate")
    project["part_split_approved"] = False
    project["split_review_approved"] = False
    project["current_stage"] = "part_split"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["part_split"]


def update_part_split(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    part_split = copy.deepcopy(project.get("part_split"))
    if not isinstance(part_split, dict):
        raise ValueError("Generate split parts before editing them.")
    operation = str(payload.get("operation") or "").strip() or "replace_split"
    if operation == "replace_split":
        incoming = payload.get("part_split")
        if not isinstance(incoming, dict):
            raise ValueError("replace_split requires a part_split object.")
        part_split = copy.deepcopy(incoming)
    elif operation == "update_part":
        part_name = str(payload.get("part_name") or "").strip()
        part = next((item for item in part_split.get("parts", []) if item.get("part_name") == part_name), None)
        if part is None:
            raise ValueError("Part not found: %s" % part_name)
        for field in ["required", "overlay_only", "notes", "pivot_hint", "parent_joint", "draw_order", "status", "source_method", "bbox"]:
            if field in payload:
                part[field] = copy.deepcopy(payload[field])
    elif operation == "apply_codex_response":
        parsed = extract_json_object_from_text(str(payload.get("response_text") or ""))
        split_payload = parsed.get("part_split") if isinstance(parsed.get("part_split"), dict) else parsed.get("split")
        if not isinstance(split_payload, dict):
            raise ValueError("Codex response did not include a part_split object.")
        part_split = copy.deepcopy(split_payload)
    else:
        raise ValueError("Unsupported part-split operation.")

    source_rel = str(part_split.get("source_image") or "")
    source_mask = None
    if source_rel:
        source_path = project_dir / source_rel
        if source_path.exists():
            source_mask = normalize_mask(detect_mask(Image.open(source_path).convert("RGBA")))
    preview_path, reconstruction_meta = render_part_split_reconstruction(
        project_dir,
        Image.open(project_dir / source_rel).convert("RGBA").size if source_rel and (project_dir / source_rel).exists() else CONCEPT_CANVAS,
        list(part_split.get("parts") or []),
    )
    part_split["reconstruction_preview"] = {"path": preview_path, **reconstruction_meta}
    part_split["rig_layout"] = project.get("rig_layout") or part_split.get("rig_layout")
    part_split["rig_profile"] = active_rig_profile_name(project, project.get("rig_layout"))
    part_split["validation"] = validate_part_split(project_dir, part_split, source_mask)
    part_split["approved"] = False
    write_json(canonical_downstream_path(project_dir, "part_split"), part_split)
    project = clear_project_downstream_state(project, "part_split")
    project["part_split"] = part_split
    project["part_split_history"] = create_part_split_revision(project_dir, part_split, "update", operation=operation)
    project["part_split_approved"] = False
    project["split_review_approved"] = False
    project["current_stage"] = "part_split"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["part_split"]


def approve_part_split(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    part_split = copy.deepcopy(project.get("part_split"))
    if not isinstance(part_split, dict):
        raise ValueError("Generate split parts before approving them.")
    validation = part_split.get("validation") or {}
    if validation.get("status") == "fail":
        raise ValueError("Part split approval is blocked: %s" % "; ".join(validation.get("failures") or ["validation failed"]))
    part_split["approved"] = True
    project["part_split"] = part_split
    project["part_split_approved"] = True
    project["split_review_approved"] = True
    project["current_stage"] = "split_review"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)


def update_concept_validation(project_id: str, concept_id: str, validation_status: str, feedback: Optional[str] = None) -> Dict[str, Any]:
    if validation_status not in {"pending", "valid", "invalid"}:
        raise ValueError("validation_status must be pending, valid, or invalid.")
    project = load_project(project_id)
    concept = next((item for item in project["concepts"] if item["concept_id"] == concept_id), None)
    if concept is None:
        raise ValueError("Concept not found.")
    if not concept.get("preview_image"):
        raise ValueError("Only imported concept attempts can be validated.")
    source = "gemini_overridden" if concept.get("validation_source") == "gemini" else "manual"
    project = apply_validation_state(
        project,
        concept,
        validation_status,
        feedback=feedback,
        summary=concept.get("codex_review_summary"),
        validation_source=source,
        validation_error=None,
        codex_response_id=concept.get("codex_response_id"),
    )
    project["updated_at"] = now_iso()
    save_concept(PROJECTS_ROOT / project_id, concept)
    save_project(project)
    append_history_event(project_id, {
        "type": "concept_validation",
        "concept_id": concept_id,
        "validation_status": validation_status,
        "validation_feedback": concept["validation_feedback"],
        "validation_source": concept["validation_source"],
        "created_at": now_iso(),
    })
    return load_project(project_id)


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
        if concept.get("validation_status") != "valid":
            raise ValueError("Only valid imported concepts can be accepted.")
        if not concept.get("approved_source_image"):
            raise ValueError("Only valid imported concepts with an approved source image can be accepted.")
        reset_downstream_assets(project_id, "concept")
        project = clear_project_downstream_state(project, "concept")
        for item in project["concepts"]:
            item["review_state"]["approved"] = item["concept_id"] == concept_id
            item["approved"] = item["review_state"]["approved"]
            item["accepted_for_review"] = item["concept_id"] == concept_id
            save_concept(PROJECTS_ROOT / project_id, item)
        project["selected_concept_id"] = concept_id
        project["character_spec"] = make_character_spec(project, concept)
        ai_workflow = project.get("ai_workflow") or {}
        if ai_workflow.get("enabled") and not ai_workflow.get("legacy_mode"):
            project["rig_layout"] = None
            project["rig_layout_history"] = default_rig_layout_history(project_id)
            project["rig_layout_approved"] = False
            ai_workflow["selected_assets"] = ai_workflow.get("selected_assets") or {}
            ai_workflow["selected_assets"]["approved_concept_id"] = concept_id
            project["ai_workflow"] = ai_workflow
        else:
            rig_layout = resolve_rig_layout(project, concept, rig_profile=project["character_spec"]["rig_profile"], persist=True)
            project["rig_layout"] = rig_layout
            project["rig_layout_history"] = load_json(rig_layout_history_path(PROJECTS_ROOT / project_id), default_rig_layout_history(project_id))
            project["rig_layout_approved"] = False
        project["rig_layout_approved"] = False
        project["current_stage"] = "rig_layout"
        project["status"] = "concept_approved"
        project["master_pose_approved"] = False
        project["sprite_model_approved"] = False
        project["layer_review_approved"] = False
        project["rig_review_approved"] = False
        project["qa_report"] = None
        project["last_export"] = None
    else:
        concept["review_state"]["favorite"] = event_value if action == "favorite" else concept["review_state"]["favorite"]
        concept["review_state"]["rejected"] = event_value if action == "reject" else concept["review_state"]["rejected"]
        concept["favorite"] = concept["review_state"]["favorite"]
        concept["rejected"] = concept["review_state"]["rejected"]
        if action == "reject" and project.get("selected_concept_id") == concept_id and event_value:
            reset_downstream_assets(project_id, "concept")
            project = clear_project_downstream_state(project, "concept")
            concept["review_state"]["approved"] = False
            concept["approved"] = False
            project["selected_concept_id"] = None
            project["character_spec"] = None
            project["master_pose_approved"] = False
            project["sprite_model_approved"] = False
            project["layer_review_approved"] = False
            project["rig_review_approved"] = False
            concept["accepted_for_review"] = False
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


_CONCEPT_ARTIFACT_IMAGE_KEYS = (
    "preview_image",
    "processed_preview_image",
    "original_preview_image",
    "approved_source_image",
)


def _concept_image_rel_paths(concept: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for key in _CONCEPT_ARTIFACT_IMAGE_KEYS:
        rel = concept.get(key)
        if rel and isinstance(rel, str) and rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


def _delete_concept_disk_artifacts(project_dir: Path, removed: Dict[str, Any], remaining: List[Dict[str, Any]]) -> None:
    still_used: Set[str] = set()
    for c in remaining:
        for rel in _concept_image_rel_paths(c):
            still_used.add(rel)
    for rel in _concept_image_rel_paths(removed):
        if rel in still_used:
            continue
        target = project_dir / rel
        if target.exists() and target.is_file():
            delete_path(target)
    prompt_file = removed.get("prompt_file")
    if prompt_file and isinstance(prompt_file, str):
        if not any((c.get("prompt_file") == prompt_file) for c in remaining):
            pf = project_dir / prompt_file
            if pf.exists() and pf.is_file():
                delete_path(pf)


def delete_concept(project_id: str, concept_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    concepts = list(project.get("concepts") or [])
    removed = next((c for c in concepts if c.get("concept_id") == concept_id), None)
    if removed is None:
        raise ValueError("Concept not found.")

    project_dir = PROJECTS_ROOT / project_id
    remaining = [c for c in concepts if c.get("concept_id") != concept_id]
    was_selected = project.get("selected_concept_id") == concept_id
    was_approved_look = bool(removed.get("review_state", {}).get("approved"))

    if was_selected or was_approved_look:
        reset_downstream_assets(project_id, "concept")
        project = clear_project_downstream_state(project, "concept")
        project["selected_concept_id"] = None
        project["character_spec"] = None
        delete_path(project_dir / "character_spec.json")
        for item in remaining:
            item.setdefault("review_state", {"approved": False, "favorite": False, "rejected": False})
            item["review_state"]["approved"] = False
            item["review_state"]["favorite"] = item["review_state"].get("favorite") or False
            item["review_state"]["rejected"] = item["review_state"].get("rejected") or False
            item["approved"] = False
            item["accepted_for_review"] = False
        ai_workflow = project.get("ai_workflow") or {}
        if ai_workflow.get("enabled") and not ai_workflow.get("legacy_mode"):
            ai_workflow.setdefault("selected_assets", {})
            ai_workflow["selected_assets"]["approved_concept_id"] = None
        project["ai_workflow"] = ai_workflow
        project["current_stage"] = "concepts"
        project["status"] = "concept_deleted"

    project["concepts"] = remaining
    _delete_concept_disk_artifacts(project_dir, removed, remaining)
    delete_path(project_dir / "concepts" / ("%s.json" % concept_id))

    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "concept_deleted",
        "concept_id": concept_id,
        "was_selected": was_selected,
        "cleared_pipeline": was_selected or was_approved_look,
        "created_at": now_iso(),
    })
    return load_project(project_id)


def generate_initial_prompt(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    concepts = list(project.get("concepts") or [])
    prior = None
    if concepts:
        concepts.sort(key=lambda item: parse_iso(item.get("created_at")), reverse=True)
        prior = next((item for item in concepts if item.get("preview_image")), concepts[0])
    prompt_text = build_gemini_prompt(
        project["brief"],
        previous_prompt=(prior.get("prompt_text") or prior.get("positive_prompt")) if prior else None,
        validation_feedback=(prior.get("validation_feedback") or None) if prior and prior.get("validation_status") == "invalid" else None,
        imported_attempt=prior if prior and prior.get("preview_image") else None,
    )
    concept = create_prompt_attempt(project, prompt_text, "iteration" if prior else "initial", attempt_group_id=prior.get("attempt_group_id") if prior else None)
    return {
        "concept_id": concept["concept_id"],
        "attempt_group_id": concept["attempt_group_id"],
        "prompt_version": concept["prompt_version"],
        "prompt_source": concept["prompt_source"],
        "prompt_text": concept["prompt_text"],
        "prompt_file": concept["prompt_file"],
    }


def generate_improved_prompt(project_id: str, concept_id: str, feedback: Optional[str] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    prior = next((item for item in project["concepts"] if item["concept_id"] == concept_id), None)
    if prior is None:
        raise ValueError("Concept attempt not found.")
    prompt_text = build_gemini_prompt(
        project["brief"],
        previous_prompt=prior.get("prompt_text") or prior.get("positive_prompt"),
        validation_feedback=feedback or prior.get("validation_feedback"),
        imported_attempt=prior if prior.get("preview_image") else None,
    )
    concept = create_prompt_attempt(
        project,
        prompt_text,
        "improved",
        attempt_group_id=prior.get("attempt_group_id"),
        validation_feedback=(feedback or prior.get("validation_feedback") or "").strip() or None,
    )
    return {
        "concept_id": concept["concept_id"],
        "attempt_group_id": concept["attempt_group_id"],
        "prompt_version": concept["prompt_version"],
        "prompt_source": concept["prompt_source"],
        "prompt_text": concept["prompt_text"],
        "prompt_file": concept["prompt_file"],
    }


def promote_reference_as_concept(project_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    payload = payload or {}

    requested_reference_id = payload.get("reference_id")
    references = [
        item for item in project["brief"].get("references") or []
        if isinstance(item, dict) and item.get("local_path")
    ]
    if requested_reference_id:
        reference = next((item for item in references if item.get("reference_id") == requested_reference_id), None)
    else:
        reference = next((item for item in references if item.get("role") == "identity"), None)
        if reference is None:
            reference = references[0] if references else None
    if reference is None:
        raise ValueError("Attach at least one usable reference before promoting it as the approved concept.")

    source_path = project_dir / reference["local_path"]
    if not source_path.exists():
        raise ValueError("Reference image is missing on disk.")

    reset_downstream_assets(project_id, "concept")
    project = clear_project_downstream_state(project, "concept")

    serial = next_concept_serial(project["concepts"])
    concept_id = "concept-%04d" % serial
    concept_filename = "%s%s" % (concept_id, source_path.suffix or ".png")
    concept_output_path = project_dir / "concepts" / concept_filename
    concept_output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, concept_output_path)

    run_id = "manual-reference-%s" % stable_hash(project_id, concept_id, reference.get("reference_id", ""))[:10]
    seed = stable_int(project_id, concept_id, reference.get("reference_id", ""), mod=4_294_967_295)
    concept = hydrate_concept({
        "concept_id": concept_id,
        "run_id": run_id,
        "run_kind": "manual_reference",
        "created_at": now_iso(),
        "seed": seed,
        "positive_prompt": "%s, approved directly from attached reference image, preserve character identity and style direction"
        % project["brief"]["positive_prompt_base"],
        "negative_prompt": project["brief"]["negative_prompt"],
        "prompt": "%s, approved directly from attached reference image, preserve character identity and style direction"
        % project["brief"]["positive_prompt_base"],
        "preview_image": str(concept_output_path.relative_to(project_dir)),
        "original_preview_image": str(concept_output_path.relative_to(project_dir)),
        "approved_source_image": str(concept_output_path.relative_to(project_dir)),
        "backend_name": "manual_reference",
        "backend_run_id": reference.get("reference_id"),
        "variation_axes": {
            "summary": "approved directly from attached reference image",
        },
        "difference_summary": "Using the attached reference as the approved concept direction.",
        "silhouette": project["brief"]["silhouette_intent"],
        "outfit": project["brief"]["outfit_materials"],
        "palette_direction": project["brief"]["palette_mood"],
        "palette": palette_from_seed(seed, 0, project["brief"]["palette_mood"]),
        "prop_variant": project["brief"]["prop"],
        "face_head_shape": project["brief"]["shape_language"],
        "references_used": [{
            "role": reference.get("role"),
            "local_path": reference.get("local_path"),
            "weight": float(reference.get("weight", 1.0)),
            "reference_id": reference.get("reference_id"),
        }],
        "review_state": {
            "approved": True,
            "favorite": True,
            "rejected": False,
        },
        "approved": True,
        "favorite": True,
        "rejected": False,
        "validation_status": "valid",
        "validation_source": "manual",
        "validation_updated_at": now_iso(),
        "codex_review_summary": "Reference promoted directly as the approved extraction source.",
        "lineage": {
            "run_id": run_id,
            "parent_concept_id": None,
            "source_reference_id": reference.get("reference_id"),
        },
        "triage": analyze_concept_image(concept_output_path),
    })

    for item in project["concepts"]:
        item["review_state"]["approved"] = False
        item["approved"] = False
        save_concept(project_dir, item)
    project["concepts"].append(concept)
    save_concept(project_dir, concept)

    project["selected_concept_id"] = concept_id
    project["character_spec"] = make_character_spec(project, concept)
    rig_layout = resolve_rig_layout(project, concept, rig_profile=project["character_spec"]["rig_profile"], persist=True)
    project["rig_layout"] = rig_layout
    project["rig_layout_history"] = load_json(rig_layout_history_path(project_dir), default_rig_layout_history(project_id))
    project["rig_layout_approved"] = False
    project["current_stage"] = "rig_layout"
    project["status"] = "concept_approved"
    project["master_pose_approved"] = False
    project["sprite_model_approved"] = False
    project["layer_review_approved"] = False
    project["rig_review_approved"] = False
    project["qa_report"] = None
    project["last_export"] = None
    project["wizard_state"] = set_wizard_step_complete(project.get("wizard_state"), "references")
    project["wizard_state"] = set_wizard_step_complete(project["wizard_state"], "concepts")
    project["wizard_state"] = set_wizard_step_complete(project["wizard_state"], "review")
    if project["last_ui_mode"] == "wizard":
        project["wizard_state"]["current_step"] = "rig_layout"
    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "manual_reference_concept",
        "concept_id": concept_id,
        "reference_id": reference.get("reference_id"),
        "summary": "Attached reference promoted to approved concept.",
        "created_at": now_iso(),
    })
    return load_project(project_id)


def master_pose_manifest_path(project_dir: Path) -> Path:
    return project_dir / "master_pose" / "master_pose_manifest.json"


def load_master_pose_manifest(project_dir: Path) -> Dict[str, Any]:
    return load_json(master_pose_manifest_path(project_dir), {"candidates": []})


def save_master_pose_manifest(project_dir: Path, manifest: Dict[str, Any]) -> None:
    write_json(master_pose_manifest_path(project_dir), manifest)


def selected_concept(project: Dict[str, Any]) -> Dict[str, Any]:
    concept = next((item for item in (project.get("concepts") or []) if item["concept_id"] == project.get("selected_concept_id")), None)
    if concept is None:
        raise ValueError("Concept approval is required before this stage.")
    return concept


def resolve_sprite_source_image(project: Dict[str, Any], project_dir: Path) -> Tuple[Path, str]:
    concept = selected_concept(project)
    approved_source = concept.get("approved_source_image")
    if approved_source:
        source_path = project_dir / approved_source
        if source_path.exists():
            return source_path, approved_source
    legacy_master_pose = project.get("master_pose_manifest", {}).get("approved_image") or "master_pose/approved_master_pose.png"
    legacy_path = project_dir / legacy_master_pose
    if legacy_path.exists():
        return legacy_path, legacy_master_pose
    raise ValueError("Approved concept source image is missing.")


def clean_source_subject(image: Image.Image) -> Tuple[Image.Image, Image.Image, Tuple[int, int, int, int]]:
    mask = normalize_mask(detect_mask(image))
    cleaned = image_with_mask(image, mask)
    cropped, cropped_mask, bbox = crop_to_alpha(cleaned, mask)
    return cropped, cropped_mask, bbox


def add_outline(image: Image.Image, outline_color: Tuple[int, int, int, int]) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = normalize_mask(rgba.getchannel("A"))
    expanded = dilate_mask(alpha, 1)
    border = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    border.putalpha(ImageChops.subtract(expanded, alpha))
    tint = Image.new("RGBA", rgba.size, outline_color)
    outlined = Image.composite(tint, border, border.getchannel("A"))
    outlined.alpha_composite(rgba)
    return outlined


def local_master_pose_candidate(source_path: Path, output_path: Path, variant_index: int, outline_hex: str) -> Dict[str, Any]:
    source = Image.open(source_path).convert("RGBA")
    cropped, _, _ = clean_source_subject(source)
    canvas = Image.new("RGBA", CONCEPT_CANVAS, (0, 0, 0, 0))
    target_width = int(CONCEPT_CANVAS[0] * [0.58, 0.62, 0.56][variant_index])
    target_height = int(CONCEPT_CANVAS[1] * [0.78, 0.82, 0.80][variant_index])
    contained = ImageOps.contain(cropped, (target_width, target_height))
    if variant_index == 1:
        contained = add_outline(contained, hex_to_rgba(outline_hex))
    x = (CONCEPT_CANVAS[0] - contained.size[0]) // 2 + [-10, 0, 8][variant_index]
    y = CONCEPT_CANVAS[1] - contained.size[1] - [28, 22, 26][variant_index]
    canvas.alpha_composite(contained, (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    candidate_mask = normalize_mask(detect_mask(canvas))
    bbox = candidate_mask.getbbox() or (0, 0, CONCEPT_CANVAS[0], CONCEPT_CANVAS[1])
    return {
        "bbox": list(bbox),
        "silhouette_components": mask_connected_components(candidate_mask),
        "background_clean": True,
    }


def generate_master_pose_candidates(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    concept = selected_concept(project)
    concept_path = project_dir / concept["preview_image"]
    if not concept_path.exists():
        raise ValueError("Approved concept image is missing.")

    call_progress(progress, 8, "Preparing master pose", "Using the approved concept as the source for extraction-ready candidates.")
    reset_downstream_assets(project_id, "master_pose")
    project = clear_project_downstream_state(project, "master_pose")
    master_pose_dir = project_dir / "master_pose"
    clear_directory(master_pose_dir)
    master_pose_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "project_id": project_id,
        "approved_concept_id": concept["concept_id"],
        "generated_at": now_iso(),
        "backend_mode": project["brief"]["backend_mode"],
        "candidates": [],
        "approved_candidate_id": None,
        "approved_image": None,
    }

    backend_mode = project["brief"]["backend_mode"]
    backend = get_concept_backend(backend_mode)
    request_references = make_reference_inputs(project_dir, project["brief"])
    use_local_reference_candidates = concept.get("backend_name") == "manual_reference"
    prompt_suffixes = [
        "strict side-view master pose, clean silhouette, plain background, neutral stance, extraction-ready sprite source",
        "strict side-view master pose, full-body clean profile, plain removable background, readable silhouette, animation-ready stance",
        "strict side-view master pose, clean silhouette overlap, plain background, stable anatomy, source image for sprite extraction",
    ]

    if backend_mode != "debug_procedural" and not use_local_reference_candidates:
        health = backend.healthcheck()
        if not health.get("ok"):
            raise ValueError("ComfyUI backend unavailable: %s" % health.get("error", "unknown backend error"))

    for index in range(MASTER_POSE_COUNT):
        candidate_id = "master-pose-%02d" % (index + 1)
        output_path = master_pose_dir / ("master_pose_%02d.png" % (index + 1))
        call_progress(progress, 16 + index * 22, "Generating master pose %d of %d" % (index + 1, MASTER_POSE_COUNT), prompt_suffixes[index])
        candidate_meta = None
        if backend_mode == "debug_procedural" or use_local_reference_candidates:
            candidate_meta = local_master_pose_candidate(concept_path, output_path, index, concept["palette"]["outline"])
        else:
            request = ConceptRequest(
                project_id=project_id,
                positive_prompt="%s, %s" % (concept["positive_prompt"], prompt_suffixes[index]),
                negative_prompt="%s, dramatic perspective, scene background, cropped limbs, motion blur" % concept["negative_prompt"],
                width=CONCEPT_CANVAS[0],
                height=CONCEPT_CANVAS[1],
                seed=stable_int(project_id, concept["concept_id"], candidate_id, mod=4_294_967_295),
                count=1,
                references=request_references,
                mode="master_pose",
                refine_from_image=concept_path,
                refine_strength=0.28 + (index * 0.03),
                variation_axes={"summary": prompt_suffixes[index]},
                output_path=output_path,
                checkpoint_name=project["brief"].get("comfyui_checkpoint") or DEFAULT_COMFYUI_CHECKPOINT,
            )
            backend.generate(request)
            candidate_meta = local_master_pose_candidate(output_path, output_path, 1, concept["palette"]["outline"])
        manifest["candidates"].append({
            "candidate_id": candidate_id,
            "image_path": str(output_path.relative_to(project_dir)),
            "summary": prompt_suffixes[index],
            "created_at": now_iso(),
            "background_clean": candidate_meta["background_clean"],
            "bbox": candidate_meta["bbox"],
            "silhouette_components": candidate_meta["silhouette_components"],
            "approved": False,
        })

    save_master_pose_manifest(project_dir, manifest)
    project["master_pose_manifest"] = manifest
    project["current_stage"] = "master_pose"
    project["status"] = "master_pose_candidates_ready"
    project["master_pose_approved"] = False
    project["sprite_model_approved"] = False
    project["layer_review_approved"] = False
    project["rig_review_approved"] = False
    project["qa_report"] = None
    project["last_export"] = None
    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "master_pose_generation",
        "approved_concept_id": concept["concept_id"],
        "candidate_count": MASTER_POSE_COUNT,
        "created_at": now_iso(),
    })
    call_progress(progress, 100, "Master poses ready", "Choose the cleanest source image before sprite model extraction.")
    return manifest


def select_master_pose(project_id: str, candidate_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    manifest = load_master_pose_manifest(project_dir)
    candidate = next((item for item in manifest.get("candidates", []) if item["candidate_id"] == candidate_id), None)
    if candidate is None:
        raise ValueError("Master pose candidate not found.")

    approved_source = project_dir / candidate["image_path"]
    if not approved_source.exists():
        raise ValueError("Master pose candidate image is missing.")

    approved_target = project_dir / "master_pose" / "approved_master_pose.png"
    approved_target.write_bytes(approved_source.read_bytes())
    reset_downstream_assets(project_id, "master_pose")
    project = clear_project_downstream_state(project, "master_pose")
    for item in manifest.get("candidates", []):
        item["approved"] = item["candidate_id"] == candidate_id
    manifest["approved_candidate_id"] = candidate_id
    manifest["approved_image"] = str(approved_target.relative_to(project_dir))
    manifest["approved_at"] = now_iso()
    save_master_pose_manifest(project_dir, manifest)
    project["master_pose_manifest"] = manifest

    project["master_pose_approved"] = True
    project["sprite_model_approved"] = False
    project["layer_review_approved"] = False
    project["rig_review_approved"] = False
    project["current_stage"] = "master_pose"
    project["status"] = "master_pose_approved"
    project["updated_at"] = now_iso()
    project["qa_report"] = None
    project["last_export"] = None
    save_project(project)
    append_history_event(project_id, {
        "type": "master_pose_selected",
        "candidate_id": candidate_id,
        "created_at": now_iso(),
    })
    return manifest


def sprite_model_history_path(project_dir: Path) -> Path:
    return canonical_downstream_path(project_dir, "sprite_model_history")


def load_sprite_model_history(project_dir: Path) -> Dict[str, Any]:
    history = load_json(sprite_model_history_path(project_dir), default_sprite_model_history(project_dir.name))
    history.setdefault("project_id", project_dir.name)
    history.setdefault("current_revision_id", None)
    history.setdefault("events", [])
    history.setdefault("revisions", [])
    return history


def save_sprite_model_history(project_dir: Path, history: Dict[str, Any]) -> None:
    write_json(sprite_model_history_path(project_dir), history)


def append_sprite_model_history(project_dir: Path, event: Dict[str, Any]) -> Dict[str, Any]:
    history = load_sprite_model_history(project_dir)
    history["events"].append({"created_at": now_iso(), **event})
    save_sprite_model_history(project_dir, history)
    return history


def load_sprite_model(project_dir: Path) -> Optional[Dict[str, Any]]:
    sprite_model = load_json(canonical_downstream_path(project_dir, "sprite_model"))
    if sprite_model is not None:
        return sprite_model
    legacy_layered_character = load_json(legacy_downstream_path(project_dir, "layered_character"))
    if legacy_layered_character:
        rig = load_json(canonical_downstream_path(project_dir, "rig"))
        legacy_palette = load_json(legacy_downstream_path(project_dir, "palette"))
        character_spec = load_json(project_dir / "character_spec.json")
        return hydrate_legacy_sprite_model(project_dir, legacy_layered_character, rig, legacy_palette, character_spec)
    return None


def resolve_part_image_path(part: Dict[str, Any]) -> Optional[str]:
    return part.get("image_path") or part.get("source_image_path")


def sprite_model_hash(sprite_model: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(sprite_model, sort_keys=True).encode("utf-8")).hexdigest()


def create_sprite_model_revision(
    project_dir: Path,
    sprite_model: Dict[str, Any],
    reason: str,
    operation: Optional[str] = None,
    part_name: Optional[str] = None,
) -> Dict[str, Any]:
    revisions_root = sprite_model_revisions_path(project_dir)
    revisions_root.mkdir(parents=True, exist_ok=True)
    revision_id = "rev-%s" % uuid.uuid4().hex[:10]
    revision_dir = revisions_root / revision_id
    revision_dir.mkdir(parents=True, exist_ok=True)
    write_json(revision_dir / CANONICAL_DOWNSTREAM_FILES["sprite_model"], sprite_model)
    parts_dir = project_dir / "parts"
    if parts_dir.exists():
        shutil.copytree(parts_dir, revision_dir / "parts", dirs_exist_ok=True)

    history = load_sprite_model_history(project_dir)
    revision = {
        "revision_id": revision_id,
        "created_at": now_iso(),
        "reason": reason,
        "operation": operation,
        "part_name": part_name,
        "sprite_model_hash": sprite_model_hash(sprite_model),
        "snapshot_dir": str(revision_dir.relative_to(project_dir)),
    }
    history["revisions"].append(revision)
    history["current_revision_id"] = revision_id
    history["events"].append({
        "created_at": revision["created_at"],
        "type": reason,
        "operation": operation,
        "part_name": part_name,
        "revision_id": revision_id,
        "sprite_model_hash": revision["sprite_model_hash"],
    })
    save_sprite_model_history(project_dir, history)
    return history


def restore_sprite_model_revision(project_id: str, revision_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    history = load_sprite_model_history(project_dir)
    revision = next((item for item in history["revisions"] if item["revision_id"] == revision_id), None)
    if revision is None:
        raise ValueError("Revision not found.")
    revision_dir = project_dir / revision["snapshot_dir"]
    sprite_model = load_json(revision_dir / CANONICAL_DOWNSTREAM_FILES["sprite_model"], None)
    if not isinstance(sprite_model, dict):
        raise ValueError("Revision snapshot is missing sprite_model.json.")
    revision_parts_dir = revision_dir / "parts"
    if not revision_parts_dir.exists():
        raise ValueError("Revision snapshot is missing part assets.")

    clear_directory(project_dir / "parts")
    shutil.copytree(revision_parts_dir, project_dir / "parts", dirs_exist_ok=True)
    write_json(canonical_downstream_path(project_dir, "sprite_model"), sprite_model)
    reset_downstream_assets(project_id, "sprite_model")
    project = clear_project_downstream_state(project, "sprite_model")
    history["current_revision_id"] = revision_id
    history["events"].append({
        "created_at": now_iso(),
        "type": "restore",
        "revision_id": revision_id,
        "part_name": revision.get("part_name"),
        "operation": revision.get("operation"),
        "sprite_model_hash": revision["sprite_model_hash"],
    })
    save_sprite_model_history(project_dir, history)
    project["sprite_model"] = sprite_model
    project["palette"] = sprite_model.get("palette")
    project["layered_character"] = sprite_model
    project["sprite_model_history"] = history
    project["sprite_model_approved"] = False
    project["layer_review_approved"] = False
    project["rig_review_approved"] = False
    project["current_stage"] = "sprite_model"
    project["status"] = "sprite_model_restored"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)


def undo_last_sprite_model_change(project_id: str) -> Dict[str, Any]:
    project_dir = PROJECTS_ROOT / project_id
    history = load_sprite_model_history(project_dir)
    revisions = history.get("revisions") or []
    current_revision_id = history.get("current_revision_id")
    if len(revisions) < 2 or current_revision_id is None:
        raise ValueError("No earlier revision is available.")
    current_index = next((index for index, item in enumerate(revisions) if item["revision_id"] == current_revision_id), None)
    if current_index is None or current_index <= 0:
        raise ValueError("No earlier revision is available.")
    return restore_sprite_model_revision(project_id, revisions[current_index - 1]["revision_id"])


def write_part_asset(project_dir: Path, part_name: str, image: Image.Image, mask: Image.Image) -> Tuple[str, str]:
    image_path = project_dir / "parts" / ("%s.png" % part_name)
    mask_path = project_dir / "parts" / "masks" / ("%s.png" % part_name)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGBA").save(image_path)
    normalize_mask(mask).save(mask_path)
    return str(image_path.relative_to(project_dir)), str(mask_path.relative_to(project_dir))


def load_part_asset(project_dir: Path, part: Dict[str, Any], asset_override: Optional[Dict[str, Any]] = None) -> Tuple[Image.Image, Image.Image]:
    image_rel = str((asset_override or {}).get("image_path") or resolve_part_image_path(part) or "")
    if not image_rel:
        raise ValueError("Part is missing an image path.")
    image = Image.open(project_dir / image_rel).convert("RGBA")
    mask_rel = (asset_override or {}).get("mask_path") or part.get("mask_path")
    if mask_rel and (project_dir / mask_rel).exists():
        mask = normalize_mask(Image.open(project_dir / mask_rel))
    else:
        mask = normalize_mask(detect_mask(image))
    return image, mask


def color_luminance(hex_value: str) -> float:
    rgb = tuple(int(hex_value.lstrip("#")[index:index + 2], 16) for index in (0, 2, 4))
    return (0.2126 * rgb[0]) + (0.7152 * rgb[1]) + (0.0722 * rgb[2])


def extract_palette(image: Image.Image, color_count: int = 8) -> Dict[str, Any]:
    rgba = image.convert("RGBA")
    alpha = normalize_mask(rgba.getchannel("A"))
    sample = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    sample.alpha_composite(rgba)
    sample.putalpha(alpha)
    quantized = sample.convert("P", palette=Image.Palette.ADAPTIVE, colors=color_count).convert("RGBA")
    colors = []
    for count, value in quantized.getcolors(maxcolors=color_count * 8) or []:
        if value[3] == 0:
            continue
        hex_value = rgba_to_hex(value)
        if hex_value not in colors:
            colors.append(hex_value)
    if not colors:
        colors = ["#101820", "#3d4a5c", "#7e8ca0", "#d7dde4"]
    ordered = sorted(colors, key=color_luminance)
    outline = ordered[0]
    return {
        "swatches": ordered,
        "outline": outline,
        "shadow": ordered[min(1, len(ordered) - 1)],
        "base": ordered[min(2, len(ordered) - 1)],
        "accent": ordered[min(3, len(ordered) - 1)],
        "highlight": ordered[-1],
        "palette_size": len(ordered),
    }


def estimate_facing_direction(mask: Image.Image) -> str:
    bbox = mask.getbbox()
    if bbox is None:
        return "right"
    sample = normalize_mask(mask.crop(bbox))
    width, height = sample.size
    pixels = sample.load()
    weighted = 0.0
    total = 0.0
    top_limit = max(1, int(height * 0.55))
    for y in range(top_limit):
        for x in range(width):
            if pixels[x, y] > 0:
                weighted += x
                total += 1
    if total == 0:
        return "right"
    return "right" if (weighted / total) >= (width / 2.0) else "left"


def region_box(subject_bbox: Tuple[int, int, int, int], fractions: Tuple[float, float, float, float]) -> Tuple[int, int, int, int]:
    width = subject_bbox[2] - subject_bbox[0]
    height = subject_bbox[3] - subject_bbox[1]
    return (
        subject_bbox[0] + clamp_int(width * fractions[0], 0, width),
        subject_bbox[1] + clamp_int(height * fractions[1], 0, height),
        subject_bbox[0] + clamp_int(width * fractions[2], 0, width),
        subject_bbox[1] + clamp_int(height * fractions[3], 0, height),
    )


def crop_region_from_source(image: Image.Image, mask: Image.Image, box: Tuple[int, int, int, int]) -> Tuple[Image.Image, Image.Image, Tuple[int, int, int, int]]:
    cropped_image = image.crop(box)
    cropped_mask = normalize_mask(mask.crop(box))
    subject = image_with_mask(cropped_image, cropped_mask)
    part_image, part_mask, local_bbox = crop_to_alpha(subject, cropped_mask)
    return part_image, part_mask, (
        box[0] + local_bbox[0],
        box[1] + local_bbox[1],
        box[0] + local_bbox[2],
        box[1] + local_bbox[3],
    )


def fallback_part_entry(
    part_name: str,
    source_part: Optional[Dict[str, Any]],
    source_image: Optional[Image.Image],
    source_mask: Optional[Image.Image],
    target_bbox: Tuple[int, int, int, int],
) -> Tuple[Image.Image, Image.Image, Dict[str, Any]]:
    if source_part and source_image and source_mask:
        image = ImageOps.mirror(source_image)
        mask = ImageOps.mirror(source_mask)
        bbox = (
            target_bbox[0],
            target_bbox[1],
            target_bbox[0] + image.size[0],
            target_bbox[1] + image.size[1],
        )
        return image, mask, {
            "mirror_of": source_part["part_name"],
            "bbox": list(bbox),
        }
    empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return empty, Image.new("L", (1, 1), 0), {"mirror_of": None, "bbox": list(target_bbox)}


def shade_part_image(image: Image.Image, factor: float) -> Image.Image:
    rgba = image.convert("RGBA")
    factor = max(0.0, float(factor))
    r, g, b, a = rgba.split()
    return Image.merge("RGBA", (
        r.point(lambda value: int(round(value * factor))),
        g.point(lambda value: int(round(value * factor))),
        b.point(lambda value: int(round(value * factor))),
        a,
    ))


def clone_part_entry(
    source_part: Optional[Dict[str, Any]],
    source_image: Optional[Image.Image],
    source_mask: Optional[Image.Image],
    target_bbox: Tuple[int, int, int, int],
    *,
    shade_factor: float = 1.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    align: str = "top_left",
) -> Tuple[Image.Image, Image.Image, Dict[str, Any]]:
    if source_part and source_image and source_mask:
        image = shade_part_image(source_image, shade_factor)
        mask = source_mask.copy()
        if scale_x != 1.0 or scale_y != 1.0:
            scaled_size = (
                max(1, int(round(image.size[0] * max(0.05, float(scale_x))))),
                max(1, int(round(image.size[1] * max(0.05, float(scale_y))))),
            )
            image = image.resize(scaled_size, Image.Resampling.NEAREST)
            mask = mask.resize(scaled_size, Image.Resampling.NEAREST)
        left = target_bbox[0]
        top = target_bbox[1]
        if align == "bottom_right":
            left = target_bbox[2] - image.size[0]
            top = target_bbox[3] - image.size[1]
        elif align == "bottom_left":
            top = target_bbox[3] - image.size[1]
        elif align == "top_right":
            left = target_bbox[2] - image.size[0]
        bbox = (
            int(left),
            int(top),
            int(left + image.size[0]),
            int(top + image.size[1]),
        )
        return image, mask, {
            "mirror_of": source_part["part_name"],
            "bbox": list(bbox),
        }
    empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return empty, Image.new("L", (1, 1), 0), {"mirror_of": None, "bbox": list(target_bbox)}


def part_pivot_from_image(part_name: str, image: Image.Image, part_definition: Optional[Dict[str, Any]] = None) -> List[int]:
    strategy = (part_definition or {}).get("pivot_strategy") or {}
    if strategy.get("mode") == "fractional" and isinstance(strategy.get("fraction"), (list, tuple)) and len(strategy.get("fraction")) == 2:
        fx, fy = float(strategy["fraction"][0]), float(strategy["fraction"][1])
    else:
        fx, fy = PART_PIVOT_FRACTIONS.get(part_name, (0.5, 0.5))
    return [
        clamp_int(image.size[0] * fx, 0, max(0, image.size[0] - 1)),
        clamp_int(image.size[1] * fy, 0, max(0, image.size[1] - 1)),
    ]


def validate_sprite_model(project_dir: Path, sprite_model: Dict[str, Any]) -> Dict[str, Any]:
    parts = sprite_model.get("parts") or []
    rig_layout = sprite_model.get("rig_layout") or load_json(canonical_downstream_path(project_dir, "rig_layout"))
    profile_name = active_rig_profile_name({"character_spec": None}, rig_layout)
    layout_parts = {item["part_name"]: item for item in (rig_layout or {}).get("parts", []) if isinstance(item, dict)}
    required_roles: Set[str] = {item["part_name"] for item in layout_parts.values() if item.get("required")}
    optional_roles: Set[str] = {item["part_name"] for item in layout_parts.values() if not item.get("required")}
    overlay_roles: Set[str] = set((rig_layout or {}).get("overlay_parts") or [])
    role_counts: Dict[str, int] = {}
    part_reports: List[Dict[str, Any]] = []
    warnings: List[str] = []
    failures: List[str] = []
    overlap_warnings: List[Dict[str, Any]] = []
    prop_separation_warnings: List[Dict[str, Any]] = []

    for part in parts:
        role = canonical_sprite_part_role(part, profile_name)
        role_counts[role] = role_counts.get(role, 0) + 1
        image, mask = load_part_asset(project_dir, part)
        bbox = part.get("bbox") or [0, 0, image.size[0], image.size[1]]
        bbox_size = [max(0, int(bbox[2]) - int(bbox[0])), max(0, int(bbox[3]) - int(bbox[1]))]
        area = mask_pixel_area(mask)
        part_warnings: List[str] = []
        part_failures: List[str] = []
        status = "pass"

        if area < SPRITE_MODEL_FAIL_MIN_MASK_AREA or min(bbox_size) < SPRITE_MODEL_MIN_DIMENSION or bbox_area(bbox) <= 0:
            part_failures.append("part is missing usable opaque pixels")
            status = "fail"
        elif area < SPRITE_MODEL_WARN_MIN_MASK_AREA:
            part_warnings.append("mask area is unusually small")
            status = "warning"
        if part.get("mirror_of"):
            part_warnings.append("used mirrored fallback")
        if bbox_area(bbox) > 0 and area / float(max(1, bbox_area(bbox))) < 0.08:
            part_warnings.append("mask coverage is sparse inside the bbox")

        part_reports.append({
            "part_name": part["part_name"],
            "part_role": role,
            "status": status,
            "mask_area": area,
            "bbox": [int(value) for value in bbox],
            "bbox_size": bbox_size,
            "used_mirrored_fallback": bool(part.get("mirror_of")),
            "mirror_of": part.get("mirror_of"),
            "warnings": part_warnings,
            "failures": part_failures,
        })
        for message in part_warnings:
            warnings.append("%s: %s" % (part["part_name"], message))
        for message in part_failures:
            failures.append("%s: %s" % (part["part_name"], message))

    missing_roles = sorted(required_roles.difference(set(role_counts)))
    for role in missing_roles:
        failures.append("missing required part: %s" % role)
    missing_optional_roles = sorted(optional_roles.difference(set(role_counts)))
    for role in missing_optional_roles:
        warnings.append("missing optional part: %s" % role)

    usable_part_reports = [item for item in part_reports if item["status"] != "fail"]
    for index, left in enumerate(usable_part_reports):
        for right in usable_part_reports[index + 1:]:
            interesting_roles = {"prop", "weapon", "accessory_front", "accessory_back", "front_cloth", "cape_back"}
            if left["part_role"] not in interesting_roles and right["part_role"] not in interesting_roles and left["part_role"] not in overlay_roles and right["part_role"] not in overlay_roles:
                continue
            shared = bbox_intersection_area(left["bbox"], right["bbox"])
            if shared <= 0:
                continue
            ratio = shared / float(max(1, min(bbox_area(left["bbox"]), bbox_area(right["bbox"]))))
            threshold = 0.8 if left["part_role"] in overlay_roles or right["part_role"] in overlay_roles else SPRITE_MODEL_WARN_COMPONENT_OVERLAP_RATIO
            if ratio >= threshold:
                overlap_warnings.append({
                    "parts": [left["part_name"], right["part_name"]],
                    "ratio": round(ratio, 4),
                })

    prop_report = next((item for item in usable_part_reports if item["part_role"] in {"prop", "weapon"}), None)
    if prop_report is not None:
        candidate_roles = ["torso", "torso_pelvis", "hand_left", "hand_right", "front_arm"]
        for role in candidate_roles:
            other = next((item for item in usable_part_reports if item["part_role"] == role), None)
            if other is None:
                continue
            overlap = bbox_intersection_area(prop_report["bbox"], other["bbox"])
            ratio = overlap / float(max(1, min(bbox_area(prop_report["bbox"]), bbox_area(other["bbox"]))))
            if ratio >= SPRITE_MODEL_WARN_PROP_OVERLAP_RATIO:
                prop_separation_warnings.append({
                    "parts": [prop_report["part_name"], other["part_name"]],
                    "ratio": round(ratio, 4),
                })

    warnings.extend(
        "overlap warning: %s vs %s" % (item["parts"][0], item["parts"][1])
        for item in overlap_warnings
    )
    warnings.extend(
        "prop separation warning: %s vs %s" % (item["parts"][0], item["parts"][1])
        for item in prop_separation_warnings
    )

    status = "pass"
    if failures:
        status = "fail"
    elif any(item["status"] == "warning" for item in part_reports):
        status = "warning"
    return {
        "generated_at": now_iso(),
        "status": status,
        "warnings": warnings,
        "failures": failures,
        "required_parts_missing": missing_roles,
        "optional_parts_missing": missing_optional_roles,
        "overlap_warnings": overlap_warnings,
        "prop_separation_warnings": prop_separation_warnings,
        "per_part": part_reports,
        "summary": {
            "part_count": len(parts),
            "required_part_count": len(required_roles) if required_roles else len(parts),
            "optional_part_count": len(optional_roles),
            "rig_profile": profile_name,
            "overlay_part_count": len(overlay_roles),
            "joint_driving_part_count": len(set((rig_layout or {}).get("joint_driving_parts") or [])),
            "mirrored_fallback_count": sum(1 for item in part_reports if item["used_mirrored_fallback"]),
            "warning_count": len(warnings),
            "fail_count": len(failures),
        },
    }


def build_sprite_model(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    concept = selected_concept(project)
    if concept.get("validation_status") != "valid":
        raise ValueError("A valid accepted concept is required before sprite model build.")
    rig_layout = project.get("rig_layout") or resolve_rig_layout(project, concept, persist=False)
    if rig_layout.get("validation", {}).get("status") == "fail":
        raise ValueError("Approve a valid rig layout before sprite model build.")
    if project.get("selected_concept_id") and not (project.get("rig_layout_approved") or rig_layout.get("auto_generated_legacy")):
        raise ValueError("Approve the rig layout before building the sprite model.")

    part_split = project.get("part_split")
    if part_split and project.get("part_split_approved"):
        call_progress(progress, 8, "Preparing sprite model", "Building from approved split parts instead of recropping the source image.")
        reset_downstream_assets(project_id, "sprite_model")
        project = clear_project_downstream_state(project, "sprite_model")
        clear_directory(project_dir / "parts")
        (project_dir / "parts" / "masks").mkdir(parents=True, exist_ok=True)
        (project_dir / "parts" / "recovery").mkdir(parents=True, exist_ok=True)
        delete_path(canonical_downstream_path(project_dir, "sprite_model"))
        delete_path(legacy_downstream_path(project_dir, "palette"))

        approved_rel = str(part_split.get("source_image") or "")
        approved_path = project_dir / approved_rel if approved_rel else None
        source_image = Image.open(approved_path).convert("RGBA") if approved_path and approved_path.exists() else None
        palette_source = source_image if source_image is not None else Image.new("RGBA", CONCEPT_CANVAS, (0, 0, 0, 0))
        palette = extract_palette(palette_source)
        facing = str(part_split.get("source_facing") or "left")
        built_parts: List[Dict[str, Any]] = []
        for index, part_definition in enumerate(list(part_split.get("parts") or [])):
            call_progress(progress, 12 + int((index / max(1, len(part_split.get("parts") or []))) * 72), "Copying split part %d of %d" % (index + 1, len(part_split.get("parts") or [])), part_definition["part_name"])
            image, mask = load_part_split_asset(project_dir, part_definition)
            image_path, mask_path = write_part_asset(project_dir, part_definition["part_name"], image, mask)
            built_parts.append({
                "part_name": part_definition["part_name"],
                "part_role": canonical_sprite_part_role(part_definition, rig_layout["rig_profile"]),
                "image_path": image_path,
                "mask_path": mask_path,
                "pivot_point": list(part_definition.get("pivot_hint") or part_pivot_from_image(part_definition["part_name"], image, part_definition)),
                "parent_joint": str(part_definition.get("parent_joint") or resolve_layout_parent_joint(part_definition["part_name"], rig_layout["rig_profile"], facing) or "torso"),
                "draw_order": int(part_definition.get("draw_order", 0)),
                "bbox": [int(value) for value in (part_definition.get("bbox") or [0, 0, image.size[0], image.size[1]])],
                "mirror_of": None,
                "approved": True,
                "overlay_only": bool(part_definition.get("overlay_only")),
            })
        ordered_parts = sorted(built_parts, key=lambda item: item["draw_order"])
        source_bounds = normalize_mask(source_image.getchannel("A")).getbbox() if source_image is not None else None
        sprite_model = {
            "project_id": project_id,
            "approved_master_pose": part_split.get("approved_master_pose"),
            "approved_source_image": approved_rel,
            "parts": ordered_parts,
            "palette": palette,
            "outline_rules": {
                "outline_color": palette["outline"],
                "mode": "single_pixel_detected",
            },
            "draw_order": [item["part_name"] for item in ordered_parts],
            "source_facing": facing,
            "source_bounds": list(source_bounds or (0, 0, palette_source.size[0], palette_source.size[1])),
            "rig_layout": rig_layout,
            "status": "pass",
            "approved_for_rigging": False,
            "source_mode": "approved_part_split",
        }
        sprite_model["build_report"] = validate_sprite_model(project_dir, sprite_model)
        sprite_model["status"] = sprite_model["build_report"]["status"]
        write_json(canonical_downstream_path(project_dir, "sprite_model"), sprite_model)
        create_sprite_model_revision(project_dir, sprite_model, "build")
        project["sprite_model"] = sprite_model
        project["palette"] = palette
        project["layered_character"] = sprite_model
        project["sprite_model_history"] = load_sprite_model_history(project_dir)
        project["current_stage"] = "sprite_model"
        project["status"] = "sprite_model_%s" % sprite_model["status"]
        project["updated_at"] = now_iso()
        save_project(project)
        return load_project(project_id)["sprite_model"]

    if not part_split:
        call_progress(progress, 5, "Legacy fallback", "Using legacy extraction because no approved part split exists.")
    else:
        raise ValueError("Approve the part split before building the sprite model.")

    approved_path, approved_rel = resolve_sprite_source_image(project, project_dir)
    call_progress(progress, 8, "Preparing sprite model", "Loading the accepted concept source image and extracting the subject silhouette.")
    source_image = Image.open(approved_path).convert("RGBA")
    source_mask = normalize_mask(detect_mask(source_image))
    subject_bbox = source_mask.getbbox()
    if subject_bbox is None:
        raise ValueError("Could not detect a character silhouette in the approved master pose.")
    reset_downstream_assets(project_id, "sprite_model")
    project = clear_project_downstream_state(project, "sprite_model")

    clear_directory(project_dir / "parts")
    (project_dir / "parts" / "masks").mkdir(parents=True, exist_ok=True)
    (project_dir / "parts" / "recovery").mkdir(parents=True, exist_ok=True)
    delete_path(canonical_downstream_path(project_dir, "sprite_model"))
    delete_path(legacy_downstream_path(project_dir, "palette"))

    palette = extract_palette(image_with_mask(source_image, source_mask))
    facing = estimate_facing_direction(source_mask)
    left_in_front = facing == "left"
    rig_layout["source_assumptions"] = {
        **(rig_layout.get("source_assumptions") or {}),
        "source_facing": facing,
    }
    built_parts: Dict[str, Dict[str, Any]] = {}
    built_images: Dict[str, Image.Image] = {}
    built_masks: Dict[str, Image.Image] = {}
    layout_parts = list(rig_layout.get("parts") or [])
    total_parts = len(layout_parts)

    for index, part_definition in enumerate(layout_parts):
        part_name = part_definition["part_name"]
        call_progress(progress, 12 + int((index / max(1, total_parts)) * 72), "Extracting part %d of %d" % (index + 1, total_parts), part_name)
        extraction_region = resolve_layout_region(part_definition, facing) or part_definition.get("extraction_region")
        if not extraction_region:
            continue
        box = region_box(subject_bbox, extraction_region)
        part_image, part_mask, absolute_bbox = crop_region_from_source(source_image, source_mask, box)
        fallback_mode = str(part_definition.get("fallback_mode") or "")
        if fallback_mode.startswith("clone_from:"):
            source_name = fallback_mode.split(":", 1)[1].strip()
            source_part = built_parts.get(source_name)
            source_image_clone = built_images.get(source_name)
            source_mask_clone = built_masks.get(source_name)
            part_image, part_mask, fallback_meta = clone_part_entry(
                source_part,
                source_image_clone,
                source_mask_clone,
                box,
                shade_factor=0.7 if part_name == "back_leg" else 1.0,
                scale_x=0.88 if part_name == "back_leg" else 1.0,
                scale_y=0.95 if part_name == "back_leg" else 1.0,
                align="bottom_right" if part_name == "back_leg" else "top_left",
            )
            absolute_bbox = tuple(fallback_meta["bbox"])
            mirror_of = fallback_meta["mirror_of"]
        elif alpha_bbox(part_image) is None:
            counterpart = None
            counterpart_name = None
            if fallback_mode == "mirror_counterpart" and part_name.endswith("_left"):
                counterpart_name = part_name.replace("_left", "_right")
                counterpart = built_parts.get(counterpart_name)
            elif fallback_mode == "mirror_counterpart" and part_name.endswith("_right"):
                counterpart_name = part_name.replace("_right", "_left")
                counterpart = built_parts.get(counterpart_name)
            counterpart_image = built_images.get(counterpart["part_name"]) if counterpart else None
            counterpart_mask = built_masks.get(counterpart["part_name"]) if counterpart else None
            if counterpart is None and counterpart_name:
                counterpart_definition = next((item for item in layout_parts if item["part_name"] == counterpart_name), None)
                counterpart_region = resolve_layout_region(counterpart_definition or {}, facing)
                counterpart_box = region_box(subject_bbox, counterpart_region or extraction_region)
                counterpart_image, counterpart_mask, _ = crop_region_from_source(source_image, source_mask, counterpart_box)
                if alpha_bbox(counterpart_image) is not None:
                    counterpart = {"part_name": counterpart_name}
            if fallback_mode == "allow_missing":
                part_image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
                part_mask = Image.new("L", (1, 1), 0)
                absolute_bbox = (int(box[0]), int(box[1]), int(box[0]) + 1, int(box[1]) + 1)
                mirror_of = None
            else:
                part_image, part_mask, fallback_meta = fallback_part_entry(part_name, counterpart, counterpart_image, counterpart_mask, box)
                absolute_bbox = tuple(fallback_meta["bbox"])
                mirror_of = fallback_meta["mirror_of"]
        else:
            mirror_of = None

        draw_order = int(part_definition.get("draw_order", 0))
        if part_name.endswith("_left") and left_in_front:
            draw_order += 10
        if part_name.endswith("_right") and not left_in_front:
            draw_order += 10
        parent_joint = resolve_layout_parent_joint(part_name, rig_layout["rig_profile"], facing) or str(part_definition.get("parent_joint") or "torso")

        image_path, mask_path = write_part_asset(project_dir, part_name, part_image, part_mask)
        part_entry = {
            "part_name": part_name,
            "part_role": canonical_sprite_part_role(part_definition, rig_layout["rig_profile"]),
            "image_path": image_path,
            "mask_path": mask_path,
            "pivot_point": part_pivot_from_image(part_name, part_image, part_definition),
            "parent_joint": parent_joint,
            "draw_order": draw_order,
            "bbox": list(absolute_bbox),
            "mirror_of": mirror_of,
            "approved": True,
            "overlay_only": bool(part_definition.get("overlay_only")),
        }
        built_parts[part_name] = part_entry
        built_images[part_name] = part_image
        built_masks[part_name] = part_mask

    ordered_parts = sorted(built_parts.values(), key=lambda item: item["draw_order"])
    sprite_model = {
        "project_id": project_id,
        "approved_master_pose": approved_rel if approved_rel.startswith("master_pose/") else None,
        "approved_source_image": approved_rel,
        "parts": ordered_parts,
        "palette": palette,
        "outline_rules": {
            "outline_color": palette["outline"],
            "mode": "single_pixel_detected",
        },
        "draw_order": [item["part_name"] for item in ordered_parts],
        "source_facing": facing,
        "source_bounds": list(subject_bbox),
        "rig_layout": rig_layout,
        "status": "pass",
        "approved_for_rigging": False,
    }
    sprite_model["build_report"] = validate_sprite_model(project_dir, sprite_model)
    sprite_model["status"] = sprite_model["build_report"]["status"]
    write_json(canonical_downstream_path(project_dir, "sprite_model"), sprite_model)
    create_sprite_model_revision(project_dir, sprite_model, "build")
    project["sprite_model"] = sprite_model
    project["palette"] = palette
    project["layered_character"] = sprite_model
    project["sprite_model_history"] = load_sprite_model_history(project_dir)
    project["current_stage"] = "sprite_model"
    project["status"] = "sprite_model_%s" % sprite_model["status"]
    project["sprite_model_approved"] = False
    project["layer_review_approved"] = False
    project["rig_review_approved"] = False
    project["updated_at"] = now_iso()
    project["qa_report"] = None
    project["last_export"] = None
    save_project(project)
    call_progress(progress, 100, "Sprite model ready", "Inspect the extracted parts, pivots, and draw order before rigging.")
    return sprite_model


def sort_sprite_model_parts(sprite_model: Dict[str, Any]) -> None:
    sprite_model["parts"] = sorted(sprite_model.get("parts", []), key=lambda item: (item.get("draw_order", 0), item["part_name"]))
    sprite_model["draw_order"] = [item["part_name"] for item in sprite_model["parts"]]


def save_sprite_model_bundle(project_dir: Path, sprite_model: Dict[str, Any], palette: Optional[Dict[str, Any]] = None) -> None:
    sort_sprite_model_parts(sprite_model)
    if palette is not None:
        sprite_model["palette"] = palette
    write_json(canonical_downstream_path(project_dir, "sprite_model"), sprite_model)


def replace_part_pixels_with_mask(image: Image.Image, mask: Image.Image) -> Image.Image:
    result = image.convert("RGBA")
    result.putalpha(normalize_mask(mask))
    return result


def rotate_part_asset(image: Image.Image, mask: Image.Image, pivot: Tuple[int, int], degrees: float) -> Tuple[Image.Image, Image.Image, List[int]]:
    width, height = image.size
    canvas_size = max(width, height) * 4
    center = (canvas_size // 2, canvas_size // 2)
    image_canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    mask_canvas = Image.new("L", (canvas_size, canvas_size), 0)
    offset = (center[0] - pivot[0], center[1] - pivot[1])
    image_canvas.alpha_composite(image, offset)
    mask_canvas.paste(mask, offset)
    rotated_image = image_canvas.rotate(degrees, resample=Image.Resampling.BICUBIC, center=center)
    rotated_mask = normalize_mask(mask_canvas.rotate(degrees, resample=Image.Resampling.BICUBIC, center=center))
    part_image, part_mask, bbox = crop_to_alpha(rotated_image, rotated_mask)
    return part_image, part_mask, [center[0] - bbox[0], center[1] - bbox[1]]


def scale_part_asset(image: Image.Image, mask: Image.Image, pivot: Tuple[int, int], factor: float) -> Tuple[Image.Image, Image.Image, List[int]]:
    factor = max(0.1, factor)
    new_size = (
        max(1, int(round(image.size[0] * factor))),
        max(1, int(round(image.size[1] * factor))),
    )
    scaled_image = image.resize(new_size, resample=Image.Resampling.BICUBIC)
    scaled_mask = normalize_mask(mask.resize(new_size, resample=Image.Resampling.NEAREST))
    return scaled_image, scaled_mask, [clamp_int(pivot[0] * factor, 0, max(0, new_size[0] - 1)), clamp_int(pivot[1] * factor, 0, max(0, new_size[1] - 1))]


def parse_mask_input(payload: Dict[str, Any]) -> Image.Image:
    if payload.get("mask_data_url"):
        _, raw = parse_data_url(payload["mask_data_url"])
        return normalize_mask(Image.open(io.BytesIO(raw)))
    if payload.get("mask_path"):
        return normalize_mask(Image.open(Path(payload["mask_path"])))
    raise ValueError("replace_mask requires mask_data_url or mask_path.")


def normalize_outline_operation(image: Image.Image, mask: Image.Image, outline_color: str) -> Image.Image:
    return add_outline(replace_part_pixels_with_mask(image, mask), hex_to_rgba(outline_color))


def apply_palette_mapping(image: Image.Image, replacements: Dict[str, str]) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    parsed = {
        source.lower(): tuple(int(source.lstrip("#")[index:index + 2], 16) for index in (0, 2, 4))
        for source in replacements
    }
    targets = {
        source.lower(): tuple(int(target.lstrip("#")[index:index + 2], 16) for index in (0, 2, 4))
        for source, target in replacements.items()
    }
    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y]
            if pixel[3] == 0:
                continue
            current = "#%02x%02x%02x" % pixel[:3]
            if current.lower() in targets:
                target = targets[current.lower()]
                pixels[x, y] = target + (pixel[3],)
    return rgba


def update_sprite_model(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    operation = payload.get("operation")
    if not operation:
        raise ValueError("sprite-model/update requires an operation.")

    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    sprite_model = load_sprite_model(project_dir)
    if not sprite_model:
        raise ValueError("Build the sprite model before applying deterministic edits.")
    palette = sprite_model.get("palette", {})

    part_name = payload.get("part_name")
    parts_by_name = {item["part_name"]: item for item in sprite_model.get("parts", [])}
    part = parts_by_name.get(part_name) if part_name else None
    if operation not in {"merge_parts", "split_part"} and part_name and part is None:
        raise ValueError("Part not found: %s" % part_name)

    if operation == "set_pivot":
        part["pivot_point"] = [int(payload["pivot_point"][0]), int(payload["pivot_point"][1])]
    elif operation == "set_bbox":
        bbox = payload.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("set_bbox requires a four-value bbox.")
        part["bbox"] = [int(value) for value in bbox]
    elif operation == "set_draw_order":
        part["draw_order"] = int(payload["draw_order"])
    elif operation == "set_parent_joint":
        parent_joint = str(payload.get("parent_joint") or "").strip()
        valid_joints = set(((sprite_model.get("rig_layout") or project.get("rig_layout") or {}).get("joint_schema") or {}).get("joints") or RIG_JOINTS)
        if parent_joint not in valid_joints:
            raise ValueError("Invalid parent joint.")
        part["parent_joint"] = parent_joint
    elif operation == "rename_part":
        new_name = sanitize_filename(str(payload.get("new_part_name") or ""), "part")
        if not new_name:
            raise ValueError("rename_part requires new_part_name.")
        image, mask = load_part_asset(project_dir, part)
        if resolve_part_image_path(part):
            delete_path(project_dir / resolve_part_image_path(part))
        if part.get("mask_path"):
            delete_path(project_dir / part["mask_path"])
        image_path, mask_path = write_part_asset(project_dir, new_name, image, mask)
        part["part_name"] = new_name
        part["image_path"] = image_path
        part["mask_path"] = mask_path
    elif operation == "merge_parts":
        names = payload.get("part_names") or ([part_name] if part_name else [])
        if len(names) < 2:
            raise ValueError("merge_parts requires at least two part_names.")
        merge_parts = [parts_by_name[name] for name in names if name in parts_by_name]
        if len(merge_parts) != len(names):
            raise ValueError("merge_parts references an unknown part.")
        boxes = [entry["bbox"] for entry in merge_parts]
        union = (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
        merged_image = Image.new("RGBA", (union[2] - union[0], union[3] - union[1]), (0, 0, 0, 0))
        merged_mask = Image.new("L", merged_image.size, 0)
        for entry in merge_parts:
            image, mask = load_part_asset(project_dir, entry)
            merged_image.alpha_composite(image, (entry["bbox"][0] - union[0], entry["bbox"][1] - union[1]))
            merged_mask.paste(mask, (entry["bbox"][0] - union[0], entry["bbox"][1] - union[1]), mask)
        target_name = sanitize_filename(str(payload.get("target_part_name") or merge_parts[0]["part_name"]), merge_parts[0]["part_name"])
        for entry in merge_parts:
            if resolve_part_image_path(entry):
                delete_path(project_dir / resolve_part_image_path(entry))
            if entry.get("mask_path"):
                delete_path(project_dir / entry["mask_path"])
        sprite_model["parts"] = [item for item in sprite_model["parts"] if item["part_name"] not in names]
        image_path, mask_path = write_part_asset(project_dir, target_name, merged_image, merged_mask)
        sprite_model["parts"].append({
            "part_name": target_name,
            "part_role": merge_parts[0].get("part_role", merge_parts[0]["part_name"]),
            "image_path": image_path,
            "mask_path": mask_path,
            "pivot_point": part_pivot_from_image(target_name, merged_image),
            "parent_joint": merge_parts[0]["parent_joint"],
            "draw_order": merge_parts[0]["draw_order"],
            "bbox": list(union),
            "mirror_of": None,
            "approved": True,
        })
    elif operation == "split_part":
        image, mask = load_part_asset(project_dir, part)
        regions = payload.get("regions")
        if not regions:
            axis = payload.get("axis") or "vertical"
            ratio = clamp(float(payload.get("ratio", 0.5)), 0.1, 0.9)
            if axis == "horizontal":
                split_at = int(round(image.size[1] * ratio))
                regions = [
                    {"part_name": "%s_a" % part["part_name"], "bbox": [0, 0, image.size[0], split_at]},
                    {"part_name": "%s_b" % part["part_name"], "bbox": [0, split_at, image.size[0], image.size[1]]},
                ]
            else:
                split_at = int(round(image.size[0] * ratio))
                regions = [
                    {"part_name": "%s_a" % part["part_name"], "bbox": [0, 0, split_at, image.size[1]]},
                    {"part_name": "%s_b" % part["part_name"], "bbox": [split_at, 0, image.size[0], image.size[1]]},
                ]
        sprite_model["parts"] = [item for item in sprite_model["parts"] if item["part_name"] != part["part_name"]]
        if resolve_part_image_path(part):
            delete_path(project_dir / resolve_part_image_path(part))
        if part.get("mask_path"):
            delete_path(project_dir / part["mask_path"])
        for region in regions:
            box = tuple(int(value) for value in region["bbox"])
            child_image = image.crop(box)
            child_mask = normalize_mask(mask.crop(box))
            child_name = sanitize_filename(region["part_name"], "part")
            image_path, mask_path = write_part_asset(project_dir, child_name, child_image, child_mask)
            sprite_model["parts"].append({
                "part_name": child_name,
                "part_role": region.get("part_role") or part.get("part_role", part["part_name"]),
                "image_path": image_path,
                "mask_path": mask_path,
                "pivot_point": part_pivot_from_image(child_name, child_image),
                "parent_joint": part["parent_joint"],
                "draw_order": part["draw_order"],
                "bbox": [part["bbox"][0] + box[0], part["bbox"][1] + box[1], part["bbox"][0] + box[2], part["bbox"][1] + box[3]],
                "mirror_of": None,
                "approved": True,
            })
    else:
        image, mask = load_part_asset(project_dir, part)
        if operation == "translate_part":
            dx = int(payload.get("dx", 0))
            dy = int(payload.get("dy", 0))
            part["bbox"] = [part["bbox"][0] + dx, part["bbox"][1] + dy, part["bbox"][2] + dx, part["bbox"][3] + dy]
        elif operation == "rotate_part":
            image, mask, new_pivot = rotate_part_asset(image, mask, list_to_tuple(part["pivot_point"]), float(payload.get("degrees", 0)))
            part["pivot_point"] = new_pivot
            center_x = (part["bbox"][0] + part["bbox"][2]) / 2.0
            center_y = (part["bbox"][1] + part["bbox"][3]) / 2.0
            part["bbox"] = [
                int(round(center_x - image.size[0] / 2.0)),
                int(round(center_y - image.size[1] / 2.0)),
                int(round(center_x + image.size[0] / 2.0)),
                int(round(center_y + image.size[1] / 2.0)),
            ]
            part["image_path"], part["mask_path"] = write_part_asset(project_dir, part["part_name"], image, mask)
        elif operation == "scale_part":
            factor = float(payload.get("scale", payload.get("factor", 1.0)))
            image, mask, new_pivot = scale_part_asset(image, mask, list_to_tuple(part["pivot_point"]), factor)
            part["pivot_point"] = new_pivot
            center_x = (part["bbox"][0] + part["bbox"][2]) / 2.0
            center_y = (part["bbox"][1] + part["bbox"][3]) / 2.0
            part["bbox"] = [
                int(round(center_x - image.size[0] / 2.0)),
                int(round(center_y - image.size[1] / 2.0)),
                int(round(center_x + image.size[0] / 2.0)),
                int(round(center_y + image.size[1] / 2.0)),
            ]
            part["image_path"], part["mask_path"] = write_part_asset(project_dir, part["part_name"], image, mask)
        elif operation == "replace_mask":
            new_mask = parse_mask_input(payload)
            if new_mask.size != image.size:
                new_mask = normalize_mask(new_mask.resize(image.size, resample=Image.Resampling.NEAREST))
            image = replace_part_pixels_with_mask(image, new_mask)
            mask = new_mask
            part["image_path"], part["mask_path"] = write_part_asset(project_dir, part["part_name"], image, mask)
        elif operation == "cleanup_alpha":
            mask = normalize_mask(mask)
            image = replace_part_pixels_with_mask(image, mask)
            part["image_path"], part["mask_path"] = write_part_asset(project_dir, part["part_name"], image, mask)
        elif operation == "normalize_outline":
            image = normalize_outline_operation(image, mask, str(payload.get("outline_color") or palette.get("outline") or "#0d1117"))
            mask = normalize_mask(image.getchannel("A"))
            part["image_path"], part["mask_path"] = write_part_asset(project_dir, part["part_name"], image, mask)
        elif operation == "apply_palette_change":
            replacements = payload.get("replacements") or {}
            if not isinstance(replacements, dict) or not replacements:
                raise ValueError("apply_palette_change requires a replacements object.")
            image = apply_palette_mapping(image, replacements)
            part["image_path"], part["mask_path"] = write_part_asset(project_dir, part["part_name"], image, mask)
            for source, target in replacements.items():
                palette["swatches"] = [target if item.lower() == source.lower() else item for item in palette.get("swatches", [])]
                for key in ["outline", "shadow", "base", "accent", "highlight"]:
                    if str(palette.get(key, "")).lower() == source.lower():
                        palette[key] = target
        elif operation == "add_to_mask":
            region = payload.get("region")
            if not region:
                raise ValueError("add_to_mask requires region.")
            draw = ImageDraw.Draw(mask)
            draw.rectangle(tuple(int(value) for value in region), fill=255)
            image = replace_part_pixels_with_mask(image, mask)
            part["image_path"], part["mask_path"] = write_part_asset(project_dir, part["part_name"], image, mask)
        elif operation == "remove_from_mask":
            region = payload.get("region")
            if not region:
                raise ValueError("remove_from_mask requires region.")
            draw = ImageDraw.Draw(mask)
            draw.rectangle(tuple(int(value) for value in region), fill=0)
            image = replace_part_pixels_with_mask(image, mask)
            part["image_path"], part["mask_path"] = write_part_asset(project_dir, part["part_name"], image, mask)
        elif operation == "mirror_part":
            image = ImageOps.mirror(image)
            mask = ImageOps.mirror(mask)
            part["pivot_point"] = [max(0, image.size[0] - 1 - part["pivot_point"][0]), part["pivot_point"][1]]
            part["image_path"], part["mask_path"] = write_part_asset(project_dir, part["part_name"], image, mask)
        elif operation == "duplicate_part":
            new_name = sanitize_filename(str(payload.get("new_part_name") or ""), "part")
            if not new_name:
                raise ValueError("duplicate_part requires new_part_name.")
            image_path, mask_path = write_part_asset(project_dir, new_name, image, mask)
            sprite_model["parts"].append({
                **copy.deepcopy(part),
                "part_name": new_name,
                "image_path": image_path,
                "mask_path": mask_path,
            })
        elif operation == "crop_pad_part":
            padding = payload.get("padding") or [0, 0, 0, 0]
            if len(padding) != 4:
                raise ValueError("crop_pad_part requires four padding values.")
            padded = Image.new("RGBA", (image.size[0] + padding[0] + padding[2], image.size[1] + padding[1] + padding[3]), (0, 0, 0, 0))
            padded_mask = Image.new("L", padded.size, 0)
            padded.alpha_composite(image, (padding[0], padding[1]))
            padded_mask.paste(mask, (padding[0], padding[1]), mask)
            part["pivot_point"] = [part["pivot_point"][0] + padding[0], part["pivot_point"][1] + padding[1]]
            part["bbox"] = [part["bbox"][0] - padding[0], part["bbox"][1] - padding[1], part["bbox"][2] + padding[2], part["bbox"][3] + padding[3]]
            part["image_path"], part["mask_path"] = write_part_asset(project_dir, part["part_name"], padded, padded_mask)
        else:
            raise ValueError("Unsupported sprite-model operation.")

    sprite_model["palette"] = palette
    sprite_model["build_report"] = validate_sprite_model(project_dir, sprite_model)
    sprite_model["status"] = sprite_model["build_report"]["status"]
    sprite_model["approved_for_rigging"] = False
    save_sprite_model_bundle(project_dir, sprite_model, palette)
    create_sprite_model_revision(project_dir, sprite_model, "update", operation=operation, part_name=part_name)
    reset_downstream_assets(project_id, "sprite_model")
    project = clear_project_downstream_state(project, "sprite_model")
    project["sprite_model"] = sprite_model
    project["palette"] = palette
    project["layered_character"] = sprite_model
    project["sprite_model_history"] = load_sprite_model_history(project_dir)
    project["sprite_model_approved"] = False
    project["layer_review_approved"] = False
    project["rig_review_approved"] = False
    project["current_stage"] = "sprite_model"
    project["status"] = "sprite_model_%s" % sprite_model["status"]
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["sprite_model"]


def recover_sprite_model_occlusion(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project_dir = PROJECTS_ROOT / project_id
    sprite_model = load_sprite_model(project_dir)
    if not sprite_model:
        raise ValueError("Build the sprite model before recovering occlusion.")
    part_name = str(payload.get("part_name") or "").strip()
    if not part_name:
        raise ValueError("recover-occlusion requires part_name.")
    part = next((item for item in sprite_model["parts"] if item["part_name"] == part_name), None)
    if part is None:
        raise ValueError("Part not found.")
    image, mask = load_part_asset(project_dir, part)
    variants = []

    counterpart = None
    if part_name.endswith("_left"):
        counterpart = next((item for item in sprite_model["parts"] if item["part_name"] == part_name.replace("_left", "_right")), None)
    elif part_name.endswith("_right"):
        counterpart = next((item for item in sprite_model["parts"] if item["part_name"] == part_name.replace("_right", "_left")), None)

    candidates: List[Tuple[Image.Image, Image.Image, str]] = [
        (add_outline(image, hex_to_rgba(sprite_model["palette"]["outline"])), normalize_mask(mask), "outlined current part"),
        (replace_part_pixels_with_mask(image, dilate_mask(mask, 1)), dilate_mask(mask, 1), "expanded alpha fill"),
    ]
    if counterpart is not None:
        other_image, other_mask = load_part_asset(project_dir, counterpart)
        candidates.append((ImageOps.mirror(other_image), ImageOps.mirror(other_mask), "mirrored counterpart"))

    for index, (candidate_image, candidate_mask, summary) in enumerate(candidates[:3], start=1):
        path = project_dir / "parts" / "recovery" / ("%s_variant_%02d.png" % (part_name, index))
        mask_path = project_dir / "parts" / "recovery" / ("%s_variant_%02d_mask.png" % (part_name, index))
        candidate_image.save(path)
        normalize_mask(candidate_mask).save(mask_path)
        variants.append({
            "variant_id": "%s-variant-%02d" % (part_name, index),
            "image_path": str(path.relative_to(project_dir)),
            "mask_path": str(mask_path.relative_to(project_dir)),
            "summary": summary,
        })

    append_sprite_model_history(project_dir, {"type": "recover_occlusion", "part_name": part_name, "variant_count": len(variants)})
    return {"part_name": part_name, "variants": variants}


def promote_sprite_model_recovery_variant(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    sprite_model = load_sprite_model(project_dir)
    if not sprite_model:
        raise ValueError("Build the sprite model before promoting recovery variants.")
    part_name = str(payload.get("part_name") or "").strip()
    if not part_name:
        raise ValueError("promote-recovery requires part_name.")
    image_path = str(payload.get("image_path") or "").strip()
    mask_path = str(payload.get("mask_path") or "").strip()
    if not image_path or not mask_path:
        raise ValueError("promote-recovery requires image_path and mask_path.")

    part = next((item for item in sprite_model["parts"] if item["part_name"] == part_name), None)
    if part is None:
        raise ValueError("Part not found.")

    recovery_image = Image.open(project_dir / image_path).convert("RGBA")
    recovery_mask = normalize_mask(Image.open(project_dir / mask_path))
    part["image_path"], part["mask_path"] = write_part_asset(project_dir, part_name, recovery_image, recovery_mask)
    part["bbox"] = [
        int(part["bbox"][0]),
        int(part["bbox"][1]),
        int(part["bbox"][0]) + recovery_image.size[0],
        int(part["bbox"][1]) + recovery_image.size[1],
    ]
    sprite_model["build_report"] = validate_sprite_model(project_dir, sprite_model)
    sprite_model["status"] = sprite_model["build_report"]["status"]
    sprite_model["approved_for_rigging"] = False
    save_sprite_model_bundle(project_dir, sprite_model)
    create_sprite_model_revision(project_dir, sprite_model, "promote_recovery", operation="promote_recovery", part_name=part_name)
    reset_downstream_assets(project_id, "sprite_model")
    project = clear_project_downstream_state(project, "sprite_model")
    project["sprite_model"] = sprite_model
    project["palette"] = sprite_model.get("palette")
    project["layered_character"] = sprite_model
    project["sprite_model_history"] = load_sprite_model_history(project_dir)
    project["sprite_model_approved"] = False
    project["layer_review_approved"] = False
    project["rig_review_approved"] = False
    project["current_stage"] = "sprite_model"
    project["status"] = "sprite_model_%s" % sprite_model["status"]
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)


def hex_to_rgba(value: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4)) + (alpha,)


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


def composite_part(
    canvas: Image.Image,
    part_image: Image.Image,
    pivot_world: Tuple[float, float],
    pivot_local: Tuple[int, int],
    rotation_deg: float,
    *,
    resample: int = Image.Resampling.BICUBIC,
) -> None:
    rotated = part_image.rotate(rotation_deg, resample=resample, center=pivot_local, expand=True)
    bbox = rotated.getbbox()
    if bbox is None:
        return
    offset_x = pivot_world[0] - pivot_local[0]
    offset_y = pivot_world[1] - pivot_local[1]
    canvas.alpha_composite(rotated, (int(round(offset_x)), int(round(offset_y))))


def is_pixel_art_rig_profile(profile_name: Optional[str]) -> bool:
    return profile_name in {SIDE_KNIGHT_SIMPLE_7, SIDE_KNIGHT_DUAL_LEG_8}


def quantize_pixel_part_rotation(part_role: str, rotation_deg: float) -> float:
    limits = {
        "head": 0.75,
        "torso_pelvis": 0.75,
        "front_arm": 2.0,
        "front_leg": 6.0,
        "back_leg": 5.5,
        "weapon": 0.75,
        "cape_back": 0.75,
        "front_cloth": 0.75,
    }
    limit = limits.get(part_role, 1.0)
    clamped = max(-limit, min(limit, float(rotation_deg)))
    return round(clamped * 2.0) / 2.0


def cleanup_frame(
    image: Image.Image,
    anchor_point: Optional[Tuple[float, float]] = None,
    anchor_target: Tuple[int, int] = FRAME_PIVOT,
) -> Tuple[Image.Image, Dict[str, Any]]:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("Rendered frame is empty.")
    cropped = image.crop(bbox)
    anchor_relative = None
    if anchor_point is not None:
        anchor_relative = (
            float(anchor_point[0]) - float(bbox[0]),
            float(anchor_point[1]) - float(bbox[1]),
        )
    original_size = cropped.size
    if cropped.size[0] > FRAME_SIZE - 4 or cropped.size[1] > FRAME_SIZE - 4:
        cropped = ImageOps.contain(cropped, (FRAME_SIZE - 4, FRAME_SIZE - 4))
    if anchor_relative is not None and original_size != cropped.size:
        scale_x = cropped.size[0] / float(max(1, original_size[0]))
        scale_y = cropped.size[1] / float(max(1, original_size[1]))
        anchor_relative = (
            anchor_relative[0] * scale_x,
            anchor_relative[1] * scale_y,
        )
    padded = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
    if anchor_relative is not None:
        target_x = int(round(anchor_target[0] - anchor_relative[0]))
        target_y = int(round(anchor_target[1] - anchor_relative[1]))
    else:
        target_x = FRAME_PIVOT[0] - cropped.size[0] // 2
        target_y = FRAME_PIVOT[1] - cropped.size[1]
    target_x = max(2, min(FRAME_SIZE - cropped.size[0] - 2, target_x))
    target_y = max(2, min(FRAME_SIZE - cropped.size[1] - 2, target_y))
    padded.alpha_composite(cropped, (target_x, target_y))
    return padded, {
        "crop_box": list(bbox),
        "output_box": [target_x, target_y, target_x + cropped.size[0], target_y + cropped.size[1]],
        "pivot": list(FRAME_PIVOT),
        "anchor_target": list(anchor_target),
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


def world_pivot(part: Dict[str, Any]) -> Tuple[float, float]:
    return part["bbox"][0] + part["pivot_point"][0], part["bbox"][1] + part["pivot_point"][1]


def vector_between(start: Tuple[float, float], end: Tuple[float, float]) -> Tuple[float, float]:
    return end[0] - start[0], end[1] - start[1]


def rotate_vector(vector: Tuple[float, float], degrees: float) -> Tuple[float, float]:
    radians = math.radians(degrees)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    return (
        (vector[0] * cosine) - (vector[1] * sine),
        (vector[0] * sine) + (vector[1] * cosine),
    )


def add_points(a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
    return a[0] + b[0], a[1] + b[1]


def build_joint_map_from_sprite_model(sprite_model: Dict[str, Any]) -> Dict[str, List[float]]:
    rig_layout = sprite_model.get("rig_layout") or {}
    rig_profile = active_rig_profile_name({}, rig_layout)
    if rig_profile in {SIDE_KNIGHT_SIMPLE_7, SIDE_KNIGHT_DUAL_LEG_8}:
        parts = {canonical_sprite_part_role(item, rig_profile): item for item in sprite_model["parts"]}
        body = parts["torso_pelvis"]
        head_part = parts["head"]
        front_arm = parts["front_arm"]
        front_leg = parts["front_leg"]
        torso = list(world_pivot(body))
        head = list(world_pivot(head_part))
        shoulder_front = list(world_pivot(front_arm))
        hip_front = list(world_pivot(front_leg))
        neck_y = max(body["bbox"][1] + 6, head_part["bbox"][3] - 8)
        neck = [head[0], float(neck_y)]
        ankle_front = [
            float(front_leg["bbox"][0] + front_leg["pivot_point"][0]),
            float(front_leg["bbox"][3] - max(2, front_leg["pivot_point"][1] * 0.15)),
        ]
        root = [ankle_front[0], float(max(front_leg["bbox"][3], body["bbox"][3]) + 10)]
        wrist_front = [
            float(front_arm["bbox"][0] + front_arm["pivot_point"][0]),
            float(front_arm["bbox"][3] - max(2, front_arm["pivot_point"][1] * 0.2)),
        ]
        joint_map = {
            "root": root,
            "torso": torso,
            "neck": neck,
            "head": head,
            "shoulder_front": shoulder_front,
            "wrist_front": wrist_front,
            "hip_front": hip_front,
            "ankle_front": ankle_front,
        }
        if rig_profile == SIDE_KNIGHT_DUAL_LEG_8 and "back_leg" in parts:
            back_leg = parts["back_leg"]
            hip_back = list(world_pivot(back_leg))
            ankle_back = [
                float(back_leg["bbox"][0] + back_leg["pivot_point"][0]),
                float(back_leg["bbox"][3] - max(2, back_leg["pivot_point"][1] * 0.15)),
            ]
            joint_map["hip_back"] = hip_back
            joint_map["ankle_back"] = ankle_back
            joint_map["root"] = [
                round((ankle_front[0] + ankle_back[0]) / 2.0, 2),
                float(max(front_leg["bbox"][3], back_leg["bbox"][3], body["bbox"][3]) + 10),
            ]
        return joint_map
    parts = {canonical_sprite_part_role(item, rig_profile): item for item in sprite_model["parts"]}
    joint_map = {
        "head": list(world_pivot(parts["head"])),
        "torso": list(world_pivot(parts["torso"])),
        "pelvis": list(world_pivot(parts["pelvis"])),
        "shoulder_left": list(world_pivot(parts["upper_arm_left"])),
        "elbow_left": list(world_pivot(parts["lower_arm_left"])),
        "wrist_left": list(world_pivot(parts["hand_left"])),
        "shoulder_right": list(world_pivot(parts["upper_arm_right"])),
        "elbow_right": list(world_pivot(parts["lower_arm_right"])),
        "wrist_right": list(world_pivot(parts["hand_right"])),
        "hip_left": list(world_pivot(parts["upper_leg_left"])),
        "knee_left": list(world_pivot(parts["lower_leg_left"])),
        "ankle_left": list(world_pivot(parts["foot_left"])),
        "hip_right": list(world_pivot(parts["upper_leg_right"])),
        "knee_right": list(world_pivot(parts["lower_leg_right"])),
        "ankle_right": list(world_pivot(parts["foot_right"])),
    }
    head_part = parts["head"]
    torso_part = parts["torso"]
    neck_y = max(torso_part["bbox"][1] + 6, head_part["bbox"][3] - 8)
    joint_map["neck"] = [joint_map["head"][0], float(neck_y)]
    feet_bottom = max(parts["foot_left"]["bbox"][3], parts["foot_right"]["bbox"][3]) + 10
    joint_map["root"] = [
        round((joint_map["ankle_left"][0] + joint_map["ankle_right"][0]) / 2.0, 2),
        float(feet_bottom),
    ]
    return joint_map


def build_joint_vectors(joint_map: Dict[str, List[float]]) -> Dict[str, List[float]]:
    if "shoulder_front" in joint_map:
        as_tuple = {key: list_to_tuple([int(round(value[0])), int(round(value[1]))]) for key, value in joint_map.items()}
        vectors = {
            "torso_from_root": list(vector_between(as_tuple["root"], as_tuple["torso"])),
            "neck_from_torso": list(vector_between(as_tuple["torso"], as_tuple["neck"])),
            "head_from_neck": list(vector_between(as_tuple["neck"], as_tuple["head"])),
            "shoulder_front_from_torso": list(vector_between(as_tuple["torso"], as_tuple["shoulder_front"])),
            "wrist_front_from_shoulder": list(vector_between(as_tuple["shoulder_front"], as_tuple["wrist_front"])),
            "hip_front_from_root": list(vector_between(as_tuple["root"], as_tuple["hip_front"])),
            "ankle_front_from_hip": list(vector_between(as_tuple["hip_front"], as_tuple["ankle_front"])),
        }
        if "hip_back" in as_tuple and "ankle_back" in as_tuple:
            vectors["hip_back_from_root"] = list(vector_between(as_tuple["root"], as_tuple["hip_back"]))
            vectors["ankle_back_from_hip"] = list(vector_between(as_tuple["hip_back"], as_tuple["ankle_back"]))
        return vectors
    as_tuple = {key: list_to_tuple([int(round(value[0])), int(round(value[1]))]) for key, value in joint_map.items()}
    return {
        "pelvis_from_root": list(vector_between(as_tuple["root"], as_tuple["pelvis"])),
        "torso_from_pelvis": list(vector_between(as_tuple["pelvis"], as_tuple["torso"])),
        "neck_from_torso": list(vector_between(as_tuple["torso"], as_tuple["neck"])),
        "head_from_neck": list(vector_between(as_tuple["neck"], as_tuple["head"])),
        "shoulder_left_from_torso": list(vector_between(as_tuple["torso"], as_tuple["shoulder_left"])),
        "elbow_left_from_shoulder": list(vector_between(as_tuple["shoulder_left"], as_tuple["elbow_left"])),
        "wrist_left_from_elbow": list(vector_between(as_tuple["elbow_left"], as_tuple["wrist_left"])),
        "shoulder_right_from_torso": list(vector_between(as_tuple["torso"], as_tuple["shoulder_right"])),
        "elbow_right_from_shoulder": list(vector_between(as_tuple["shoulder_right"], as_tuple["elbow_right"])),
        "wrist_right_from_elbow": list(vector_between(as_tuple["elbow_right"], as_tuple["wrist_right"])),
        "hip_left_from_pelvis": list(vector_between(as_tuple["pelvis"], as_tuple["hip_left"])),
        "knee_left_from_hip": list(vector_between(as_tuple["hip_left"], as_tuple["knee_left"])),
        "ankle_left_from_knee": list(vector_between(as_tuple["knee_left"], as_tuple["ankle_left"])),
        "hip_right_from_pelvis": list(vector_between(as_tuple["pelvis"], as_tuple["hip_right"])),
        "knee_right_from_hip": list(vector_between(as_tuple["hip_right"], as_tuple["knee_right"])),
        "ankle_right_from_knee": list(vector_between(as_tuple["knee_right"], as_tuple["ankle_right"])),
    }


def clip_root_motion_policy(animation_name: str) -> str:
    return "locked" if animation_name == "idle" else "in_place"


def default_clip_controls(animation_name: str) -> Dict[str, float]:
    return copy.deepcopy(DEFAULT_CLIP_CONTROLS[animation_name])


def normalize_clip_controls(animation_name: str, controls: Optional[Dict[str, Any]]) -> Dict[str, float]:
    normalized = default_clip_controls(animation_name)
    if isinstance(controls, dict):
        for key in normalized:
            value = controls.get(key)
            if isinstance(value, (int, float)):
                normalized[key] = round(float(value), 2)
    return normalized


def clip_frame_overrides(frame_count: int, overrides: Optional[List[Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for index in range(frame_count):
        override = overrides[index] if isinstance(overrides, list) and index < len(overrides) and isinstance(overrides[index], dict) else {}
        rows.append(dict(override))
    return rows


def apply_frame_overrides(frames: List[Dict[str, Any]], overrides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for index, frame in enumerate(frames):
        updated = dict(frame)
        for key, value in (overrides[index] if index < len(overrides) else {}).items():
            if key == "root_offset" and isinstance(value, list) and len(value) == 2:
                updated[key] = [round(float(value[0]), 2), round(float(value[1]), 2)]
            elif isinstance(value, (int, float)):
                updated[key] = round(float(value), 2)
        merged.append(updated)
    return merged


def synthesize_clip_controls(animation_name: str, clip_source: Optional[Dict[str, Any]]) -> Dict[str, float]:
    controls = default_clip_controls(animation_name)
    if not isinstance(clip_source, dict):
        return controls
    frames = clip_source.get("joint_transforms_per_frame") or []
    if not isinstance(frames, list) or not frames:
        return controls

    def amplitude(*keys: str) -> float:
        values = []
        for frame in frames:
            for key in keys:
                value = frame.get(key)
                if isinstance(value, list) and len(value) == 2:
                    values.extend(abs(float(item)) for item in value)
                elif isinstance(value, (int, float)):
                    values.append(abs(float(value)))
        return round(max(values), 2) if values else 0.0

    controls["body_bob"] = max(controls["body_bob"], amplitude("root_offset"))
    controls["torso_lean"] = max(controls["torso_lean"], amplitude("torso_rotation"))
    controls["arm_swing"] = max(controls["arm_swing"], amplitude("arm_swing", "shoulder_left_rotation", "shoulder_right_rotation"))
    controls["leg_swing"] = max(controls["leg_swing"], amplitude("leg_swing", "hip_left_rotation", "hip_right_rotation"))
    controls["foot_lift"] = max(controls["foot_lift"], amplitude("knee_left_rotation", "knee_right_rotation"))
    controls["prop_lag"] = max(controls["prop_lag"], round(controls["arm_swing"] * 0.2, 2))
    return controls


def legacy_clip_frame_to_joint_frame(animation_name: str, frame: Dict[str, Any]) -> Dict[str, Any]:
    if any(key in frame for key in ("shoulder_left_rotation", "shoulder_right_rotation", "hip_left_rotation", "hip_right_rotation")):
        upgraded = dict(frame)
        root = upgraded.get("root_offset") or [0, 0]
        upgraded["root_offset"] = [round(float(root[0]), 2), round(float(root[1]), 2)]
        return upgraded

    arm_swing = float(frame.get("arm_swing", 0.0))
    leg_swing = float(frame.get("leg_swing", 0.0))
    torso_rotation = float(frame.get("torso_rotation", 0.0))
    head_rotation = float(frame.get("head_rotation", 0.0))
    root_offset = frame.get("root_offset") or [0, 0]
    return {
        "root_offset": [round(float(root_offset[0]), 2), round(float(root_offset[1]), 2)],
        "torso_rotation": round(torso_rotation, 2),
        "head_rotation": round(head_rotation, 2),
        "shoulder_left_rotation": round(-arm_swing, 2),
        "elbow_left_rotation": round(8 + max(0.0, arm_swing * 0.3), 2),
        "shoulder_right_rotation": round(arm_swing, 2),
        "elbow_right_rotation": round(10 + max(0.0, -arm_swing * 0.3), 2),
        "hip_left_rotation": round(leg_swing, 2),
        "knee_left_rotation": round(max(0.0, -leg_swing) * (1.2 if animation_name == "walk" else 1.0), 2),
        "ankle_left_rotation": round(max(0.0, leg_swing) * -0.5, 2),
        "hip_right_rotation": round(-leg_swing, 2),
        "knee_right_rotation": round(max(0.0, leg_swing) * (1.2 if animation_name == "walk" else 1.0), 2),
        "ankle_right_rotation": round(max(0.0, -leg_swing) * -0.5, 2),
        "prop_rotation": round(arm_swing * 0.2, 2),
    }


def generate_clip_frames(animation_name: str, controls: Dict[str, float], overrides: Optional[List[Dict[str, Any]]] = None, rig_profile: str = LEGACY_RIG_PROFILE) -> List[Dict[str, Any]]:
    frame_total = ANIMATION_SPECS[animation_name]["frame_count"]
    frames: List[Dict[str, Any]] = []
    for index in range(frame_total):
        phase = index / float(frame_total)
        swing = math.sin(phase * math.tau)
        lift = max(0.0, -swing)
        push = max(0.0, swing)
        if rig_profile == SIDE_KNIGHT_DUAL_LEG_8:
            if animation_name == "idle":
                frames.append({
                    "root_offset": [0.0, round(swing * controls["body_bob"] * 0.18, 2)],
                    "torso_rotation": round(swing * controls["torso_lean"] * 0.14, 2),
                    "head_rotation": round(math.sin(phase * math.tau + 0.45) * max(0.2, controls["torso_lean"] * 0.08), 2),
                    "shoulder_front_rotation": round(-1.0 + (swing * controls["arm_swing"] * 0.05), 2),
                    "hip_front_rotation": round(swing * controls["leg_swing"] * 0.08, 2),
                    "hip_back_rotation": round(-swing * controls["leg_swing"] * 0.06, 2),
                    "weapon_rotation": round(-swing * controls["prop_lag"] * 0.1, 2),
                    "cape_back_rotation_bias": round(math.sin((phase - 0.12) * math.tau) * 0.4, 2),
                    "front_cloth_rotation_bias": round(math.sin((phase + 0.08) * math.tau) * 0.18, 2),
                })
            else:
                body_bob = controls["body_bob"] * 0.28
                torso_lean = controls["torso_lean"] * 0.14
                head_sway = max(0.2, controls["torso_lean"] * 0.12)
                arm_swing = min(1.6, controls["arm_swing"] * 0.08)
                front_leg_swing = min(6.4, controls["leg_swing"] * 0.32)
                back_leg_swing = min(5.8, controls["leg_swing"] * 0.29)
                weapon_lag = min(0.65, controls["prop_lag"] * 0.16)
                cape_bias = min(0.6, 0.35 + (controls["torso_lean"] * 0.04))
                front_cloth_bias = min(0.9, 0.35 + (controls["leg_swing"] * 0.018))
                frames.append({
                    "root_offset": [0.0, round(abs(swing) * -body_bob, 2)],
                    "torso_rotation": round(swing * torso_lean, 2),
                    "head_rotation": round(math.sin(phase * math.tau + 0.35) * head_sway, 2),
                    "shoulder_front_rotation": round(-swing * arm_swing, 2),
                    "hip_front_rotation": round(swing * front_leg_swing, 2),
                    "hip_back_rotation": round(-swing * back_leg_swing, 2),
                    "weapon_rotation": round(math.sin((phase - 0.08) * math.tau) * weapon_lag, 2),
                    "cape_back_rotation_bias": round(math.sin((phase - 0.16) * math.tau) * cape_bias, 2),
                    "front_cloth_rotation_bias": round(-swing * front_cloth_bias, 2),
                })
            continue
        if rig_profile == SIDE_KNIGHT_SIMPLE_7:
            if animation_name == "idle":
                frames.append({
                    "root_offset": [0.0, round(swing * controls["body_bob"], 2)],
                    "torso_rotation": round(swing * controls["torso_lean"], 2),
                    "head_rotation": round(math.sin(phase * math.tau + 0.5) * max(1.2, controls["torso_lean"] * 0.7), 2),
                    "shoulder_front_rotation": round(-4 + (swing * controls["arm_swing"] * 0.6), 2),
                    "hip_front_rotation": round(swing * controls["leg_swing"] * 0.8, 2),
                    "weapon_rotation": round(-swing * controls["prop_lag"], 2),
                    "cape_back_rotation_bias": round(math.sin((phase - 0.12) * math.tau) * 1.6, 2),
                })
            else:
                # Walk: phase offset so frame 0 is near contact (leg under); stronger scaling for readable motion
                walk_phase = (index + 0.5) / float(frame_total)
                walk_swing = math.sin(walk_phase * math.tau)
                body_bob = controls["body_bob"] * 0.52
                torso_lean = controls["torso_lean"] * 0.44
                head_sway = max(1.0, controls["torso_lean"] * 0.36)
                arm_swing = min(7.2, controls["arm_swing"] * 0.32)
                leg_swing = min(9.2, controls["leg_swing"] * 0.38)
                weapon_lag = min(2.6, controls["prop_lag"] * 0.6)
                cape_bias = min(1.8, 1.0 + (controls["torso_lean"] * 0.16))
                frames.append({
                    "root_offset": [0.0, round(abs(walk_swing) * -body_bob, 2)],
                    "torso_rotation": round(walk_swing * torso_lean, 2),
                    "head_rotation": round(math.sin(walk_phase * math.tau + 0.35) * head_sway, 2),
                    "shoulder_front_rotation": round(-walk_swing * arm_swing, 2),
                    "hip_front_rotation": round(walk_swing * leg_swing, 2),
                    "weapon_rotation": round(math.sin((walk_phase - 0.08) * math.tau) * weapon_lag, 2),
                    "cape_back_rotation_bias": round(math.sin((walk_phase - 0.18) * math.tau) * cape_bias, 2),
                })
            continue
        if animation_name == "idle":
            frames.append({
                "root_offset": [0.0, round(swing * controls["body_bob"], 2)],
                "torso_rotation": round(swing * controls["torso_lean"], 2),
                "head_rotation": round(math.sin(phase * math.tau + 0.5) * max(1.2, controls["torso_lean"] * 0.7), 2),
                "shoulder_left_rotation": round(-4 + (swing * controls["arm_swing"] * 0.6), 2),
                "elbow_left_rotation": round(8 + (push * controls["arm_swing"] * 0.18), 2),
                "shoulder_right_rotation": round(8 - (swing * controls["arm_swing"] * 0.75), 2),
                "elbow_right_rotation": round(10 + (lift * controls["arm_swing"] * 0.18), 2),
                "hip_left_rotation": round(swing * controls["leg_swing"] * 0.8, 2),
                "knee_left_rotation": round(lift * controls["foot_lift"] * 0.7, 2),
                "ankle_left_rotation": round(push * controls["foot_lift"] * -0.24, 2),
                "hip_right_rotation": round(-swing * controls["leg_swing"] * 0.8, 2),
                "knee_right_rotation": round(push * controls["foot_lift"] * 0.7, 2),
                "ankle_right_rotation": round(lift * controls["foot_lift"] * -0.24, 2),
                "prop_rotation": round(-swing * controls["prop_lag"], 2),
            })
        else:
            frames.append({
                "root_offset": [0.0, round(abs(swing) * -controls["body_bob"], 2)],
                "torso_rotation": round(swing * controls["torso_lean"], 2),
                "head_rotation": round(math.sin(phase * math.tau + 0.35) * max(1.4, controls["torso_lean"] * 0.8), 2),
                "shoulder_left_rotation": round(-swing * controls["arm_swing"], 2),
                "elbow_left_rotation": round(8 + (push * controls["arm_swing"] * 0.4), 2),
                "shoulder_right_rotation": round(swing * controls["arm_swing"], 2),
                "elbow_right_rotation": round(10 + (lift * controls["arm_swing"] * 0.4), 2),
                "hip_left_rotation": round(swing * controls["leg_swing"], 2),
                "knee_left_rotation": round(lift * controls["foot_lift"] * 1.35, 2),
                "ankle_left_rotation": round(push * controls["foot_lift"] * -0.58, 2),
                "hip_right_rotation": round(-swing * controls["leg_swing"], 2),
                "knee_right_rotation": round(push * controls["foot_lift"] * 1.35, 2),
                "ankle_right_rotation": round(lift * controls["foot_lift"] * -0.58, 2),
                "prop_rotation": round(math.sin((phase - 0.08) * math.tau) * controls["prop_lag"], 2),
            })
    return apply_frame_overrides(frames, overrides or [])


def hydrate_animation_clips(animation_clips: Optional[Dict[str, Any]], legacy_animation_templates: Optional[Dict[str, Any]], rig_profile: str = LEGACY_RIG_PROFILE) -> Dict[str, Any]:
    if not ((isinstance(animation_clips, dict) and animation_clips) or (isinstance(legacy_animation_templates, dict) and legacy_animation_templates)):
        return {}
    source = animation_clips if isinstance(animation_clips, dict) and animation_clips else legacy_animation_templates if isinstance(legacy_animation_templates, dict) else {}
    clips: Dict[str, Any] = {}
    for animation_name in ["idle", "walk"]:
        clip_source = source.get(animation_name) if isinstance(source, dict) else None
        controls = normalize_clip_controls(animation_name, clip_source.get("controls") if isinstance(clip_source, dict) else None)
        if isinstance(clip_source, dict) and "controls" not in clip_source:
            controls = synthesize_clip_controls(animation_name, clip_source)
        overrides = clip_frame_overrides(ANIMATION_SPECS[animation_name]["frame_count"], clip_source.get("frame_overrides") if isinstance(clip_source, dict) else None)
        if isinstance(clip_source, dict) and clip_source.get("joint_transforms_per_frame") and "controls" not in clip_source:
            frames = [
                legacy_clip_frame_to_joint_frame(animation_name, frame)
                for frame in clip_source.get("joint_transforms_per_frame", [])
            ]
            if len(frames) != ANIMATION_SPECS[animation_name]["frame_count"]:
                frames = generate_clip_frames(animation_name, controls, overrides, rig_profile=rig_profile)
            else:
                frames = apply_frame_overrides(frames, overrides)
        else:
            frames = generate_clip_frames(animation_name, controls, overrides, rig_profile=rig_profile)
        clip_out = {
            **ANIMATION_SPECS[animation_name],
            "root_motion_policy": clip_root_motion_policy(animation_name),
            "loop_continuity_rules": {"wrap_to_first_frame": True},
            "controls": controls,
            "frame_overrides": overrides,
            "joint_transforms_per_frame": frames,
            "neutral_pose_frame_index": 0,
            "corrective_assets_per_frame": [[] for _ in frames],
        }

        # Preserve Pixel Lab frame metadata for Phase 5/6 flows without breaking
        # the existing deterministic rig-based renderer.
        if isinstance(clip_source, dict):
            if isinstance(clip_source.get("frames"), list):
                clip_out["frames"] = clip_source.get("frames")
            if isinstance(clip_source.get("frames_by_direction"), dict):
                clip_out["frames_by_direction"] = clip_source.get("frames_by_direction")

        clips[animation_name] = clip_out
    return clips


def infer_legacy_part_bbox(part: Dict[str, Any], joint_map: Dict[str, List[float]], image_size: Tuple[int, int]) -> List[int]:
    parent_joint = part.get("parent_joint") or PART_PARENT_JOINTS.get(part.get("part_name", ""), "torso")
    pivot = part.get("pivot_point") or [image_size[0] // 2, image_size[1] // 2]
    anchor = joint_map.get(parent_joint) or list(base_joint_positions()[parent_joint])
    left = int(round(float(anchor[0]) - float(pivot[0])))
    top = int(round(float(anchor[1]) - float(pivot[1])))
    return [left, top, left + image_size[0], top + image_size[1]]


def normalize_palette_payload(palette: Optional[Dict[str, Any]], fallback_image: Optional[Image.Image] = None) -> Dict[str, Any]:
    if isinstance(palette, dict) and palette.get("swatches"):
        result = dict(palette)
        result.setdefault("outline", palette.get("outline") or "#0d1117")
        result.setdefault("shadow", palette.get("shadow") or palette.get("outline") or "#111922")
        result.setdefault("base", palette.get("base") or palette["swatches"][0])
        result.setdefault("accent", palette.get("accent") or palette["swatches"][min(1, len(palette["swatches"]) - 1)])
        result.setdefault("highlight", palette.get("highlight") or palette["swatches"][-1])
        return result
    if isinstance(palette, dict) and {"outline", "base", "accent"}.issubset(set(palette.keys())):
        swatches = [palette["outline"], palette["base"], palette["accent"], palette.get("highlight") or palette["base"]]
        return {
            "outline": palette["outline"],
            "shadow": palette.get("shadow") or palette["outline"],
            "base": palette["base"],
            "accent": palette["accent"],
            "highlight": palette.get("highlight") or palette["base"],
            "swatches": list(dict.fromkeys(swatches)),
        }
    if fallback_image is not None:
        return extract_palette(fallback_image)
    return {
        "outline": "#0d1117",
        "shadow": "#111922",
        "base": "#7c8b98",
        "accent": "#d4a752",
        "highlight": "#edf2f8",
        "swatches": ["#0d1117", "#111922", "#7c8b98", "#d4a752", "#edf2f8"],
    }


def hydrate_legacy_sprite_model(
    project_dir: Path,
    layered_character: Dict[str, Any],
    rig: Optional[Dict[str, Any]],
    legacy_palette: Optional[Dict[str, Any]],
    character_spec: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(layered_character, dict) or not isinstance(layered_character.get("parts"), list):
        return None
    joint_map = None
    if isinstance(rig, dict):
        joint_map = rig.get("rig_joint_map") or rig.get("default_neutral_pose")
    if not isinstance(joint_map, dict):
        joint_map = {key: list(value) for key, value in base_joint_positions().items()}

    parts: List[Dict[str, Any]] = []
    palette_source_image = None
    for entry in layered_character.get("parts", []):
        image_rel = entry.get("source_image_path") or entry.get("image_path")
        if not image_rel or not (project_dir / image_rel).exists():
            continue
        image = Image.open(project_dir / image_rel).convert("RGBA")
        if palette_source_image is None:
            palette_source_image = image
        pivot = entry.get("pivot_point") or part_pivot_from_image(entry.get("part_name") or "part", image)
        bbox = entry.get("bbox") or infer_legacy_part_bbox(entry, joint_map, image.size)
        parts.append({
            "part_name": entry["part_name"],
            "part_role": entry.get("part_role") or entry["part_name"],
            "image_path": image_rel,
            "mask_path": entry.get("mask_path"),
            "pivot_point": [int(pivot[0]), int(pivot[1])],
            "parent_joint": entry.get("parent_joint") or PART_PARENT_JOINTS.get(entry["part_name"], "torso"),
            "draw_order": int(entry.get("draw_order", PART_DRAW_ORDERS.get(entry["part_name"], 0))),
            "bbox": [int(value) for value in bbox],
            "mirror_of": entry.get("mirror_of"),
            "approved": True,
        })
    if not parts:
        return None
    palette = normalize_palette_payload(
        legacy_palette or ((character_spec or {}).get("palette_definition") if isinstance(character_spec, dict) else None),
        palette_source_image,
    )
    source_bounds = [
        min(part["bbox"][0] for part in parts),
        min(part["bbox"][1] for part in parts),
        max(part["bbox"][2] for part in parts),
        max(part["bbox"][3] for part in parts),
    ]
    sprite_model = {
        "project_id": project_dir.name,
        "approved_master_pose": None,
        "approved_source_image": None,
        "parts": sorted(parts, key=lambda item: (item["draw_order"], item["part_name"])),
        "palette": palette,
        "outline_rules": {
            "outline_color": palette["outline"],
            "mode": "legacy_hydrated",
        },
        "draw_order": [item["part_name"] for item in sorted(parts, key=lambda item: (item["draw_order"], item["part_name"]))],
        "source_facing": "right",
        "source_bounds": source_bounds,
        "status": "warning",
        "approved_for_rigging": False,
    }
    report = validate_sprite_model(project_dir, sprite_model)
    sprite_model["build_report"] = report
    sprite_model["status"] = report["status"]
    return sprite_model


def build_default_animation_clips(joint_map: Dict[str, List[float]], existing_clips: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ = joint_map
    if "hip_back" in joint_map:
        rig_profile = SIDE_KNIGHT_DUAL_LEG_8
    elif "shoulder_front" in joint_map:
        rig_profile = SIDE_KNIGHT_SIMPLE_7
    else:
        rig_profile = LEGACY_RIG_PROFILE
    if not isinstance(existing_clips, dict) or not existing_clips:
        existing_clips = {
            name: {
                "controls": default_clip_controls(name),
                "frame_overrides": [{} for _ in range(ANIMATION_SPECS[name]["frame_count"])],
            }
            for name in ANIMATION_SPECS
        }
    return hydrate_animation_clips(existing_clips, None, rig_profile=rig_profile)


def neutral_pose_transforms() -> Dict[str, Any]:
    return {
        "root_offset": [0.0, 0.0],
        "pelvis_rotation": 0.0,
        "torso_rotation": 0.0,
        "head_rotation": 0.0,
        "shoulder_front_rotation": 0.0,
        "hip_front_rotation": 0.0,
        "hip_back_rotation": 0.0,
        "weapon_rotation": 0.0,
        "cape_back_rotation_bias": 0.0,
        "front_cloth_rotation_bias": 0.0,
        "shoulder_left_rotation": 0.0,
        "elbow_left_rotation": 0.0,
        "shoulder_right_rotation": 0.0,
        "elbow_right_rotation": 0.0,
        "hip_left_rotation": 0.0,
        "knee_left_rotation": 0.0,
        "ankle_left_rotation": 0.0,
        "hip_right_rotation": 0.0,
        "knee_right_rotation": 0.0,
        "ankle_right_rotation": 0.0,
        "prop_rotation": 0.0,
    }


def compute_pose_joints(rig: Dict[str, Any], transforms: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    if rig.get("rig_profile") in {SIDE_KNIGHT_SIMPLE_7, SIDE_KNIGHT_DUAL_LEG_8}:
        base = {key: tuple(value) for key, value in rig["rig_joint_map"].items()}
        vectors = {key: tuple(value) for key, value in rig["joint_vectors"].items()}
        root_offset = tuple(transforms.get("root_offset", [0, 0]))
        root = add_points(base["root"], root_offset)
        torso_rotation = float(transforms.get("torso_rotation", 0.0))
        head_rotation = float(transforms.get("head_rotation", 0.0))
        shoulder_front_rotation = float(transforms.get("shoulder_front_rotation", 0.0))
        hip_front_rotation = float(transforms.get("hip_front_rotation", 0.0))
        torso = add_points(root, rotate_vector(vectors["torso_from_root"], torso_rotation * 0.1))
        neck = add_points(torso, rotate_vector(vectors["neck_from_torso"], torso_rotation))
        head = add_points(neck, rotate_vector(vectors["head_from_neck"], torso_rotation + head_rotation))
        shoulder_front = add_points(torso, rotate_vector(vectors["shoulder_front_from_torso"], torso_rotation))
        wrist_front = add_points(shoulder_front, rotate_vector(vectors["wrist_front_from_shoulder"], shoulder_front_rotation + (torso_rotation * 0.2)))
        hip_front = add_points(root, rotate_vector(vectors["hip_front_from_root"], torso_rotation * 0.1))
        ankle_front = add_points(hip_front, rotate_vector(vectors["ankle_front_from_hip"], hip_front_rotation))
        joints = {
            "root": root,
            "torso": torso,
            "neck": neck,
            "head": head,
            "shoulder_front": shoulder_front,
            "wrist_front": wrist_front,
            "hip_front": hip_front,
            "ankle_front": ankle_front,
        }
        if rig.get("rig_profile") == SIDE_KNIGHT_DUAL_LEG_8 and "hip_back_from_root" in vectors and "ankle_back_from_hip" in vectors:
            hip_back_rotation = float(transforms.get("hip_back_rotation", 0.0))
            hip_back = add_points(root, rotate_vector(vectors["hip_back_from_root"], torso_rotation * 0.1))
            ankle_back = add_points(hip_back, rotate_vector(vectors["ankle_back_from_hip"], hip_back_rotation))
            joints["hip_back"] = hip_back
            joints["ankle_back"] = ankle_back
        return joints
    base = {key: tuple(value) for key, value in rig["rig_joint_map"].items()}
    vectors = {key: tuple(value) for key, value in rig["joint_vectors"].items()}
    root_offset = tuple(transforms.get("root_offset", [0, 0]))
    root = add_points(base["root"], root_offset)
    pelvis_rotation = float(transforms.get("pelvis_rotation", 0.0))
    torso_rotation = float(transforms.get("torso_rotation", 0.0))
    head_rotation = float(transforms.get("head_rotation", 0.0))
    shoulder_left_rotation = float(transforms.get("shoulder_left_rotation", 0.0))
    elbow_left_rotation = float(transforms.get("elbow_left_rotation", 0.0))
    shoulder_right_rotation = float(transforms.get("shoulder_right_rotation", 0.0))
    elbow_right_rotation = float(transforms.get("elbow_right_rotation", 0.0))
    hip_left_rotation = float(transforms.get("hip_left_rotation", 0.0))
    knee_left_rotation = float(transforms.get("knee_left_rotation", 0.0))
    ankle_left_rotation = float(transforms.get("ankle_left_rotation", 0.0))
    hip_right_rotation = float(transforms.get("hip_right_rotation", 0.0))
    knee_right_rotation = float(transforms.get("knee_right_rotation", 0.0))
    ankle_right_rotation = float(transforms.get("ankle_right_rotation", 0.0))

    pelvis = add_points(root, rotate_vector(vectors["pelvis_from_root"], pelvis_rotation))
    torso = add_points(pelvis, rotate_vector(vectors["torso_from_pelvis"], torso_rotation))
    neck = add_points(torso, rotate_vector(vectors["neck_from_torso"], torso_rotation * 0.6))
    head = add_points(neck, rotate_vector(vectors["head_from_neck"], head_rotation + (torso_rotation * 0.15)))
    shoulder_left = add_points(torso, rotate_vector(vectors["shoulder_left_from_torso"], torso_rotation))
    elbow_left = add_points(shoulder_left, rotate_vector(vectors["elbow_left_from_shoulder"], shoulder_left_rotation + (torso_rotation * 0.2)))
    wrist_left = add_points(elbow_left, rotate_vector(vectors["wrist_left_from_elbow"], shoulder_left_rotation + elbow_left_rotation + (torso_rotation * 0.2)))
    shoulder_right = add_points(torso, rotate_vector(vectors["shoulder_right_from_torso"], torso_rotation))
    elbow_right = add_points(shoulder_right, rotate_vector(vectors["elbow_right_from_shoulder"], shoulder_right_rotation + (torso_rotation * 0.2)))
    wrist_right = add_points(elbow_right, rotate_vector(vectors["wrist_right_from_elbow"], shoulder_right_rotation + elbow_right_rotation + (torso_rotation * 0.2)))
    hip_left = add_points(pelvis, rotate_vector(vectors["hip_left_from_pelvis"], pelvis_rotation * 0.25))
    knee_left = add_points(hip_left, rotate_vector(vectors["knee_left_from_hip"], hip_left_rotation))
    ankle_left = add_points(knee_left, rotate_vector(vectors["ankle_left_from_knee"], hip_left_rotation + knee_left_rotation))
    hip_right = add_points(pelvis, rotate_vector(vectors["hip_right_from_pelvis"], pelvis_rotation * 0.25))
    knee_right = add_points(hip_right, rotate_vector(vectors["knee_right_from_hip"], hip_right_rotation))
    ankle_right = add_points(knee_right, rotate_vector(vectors["ankle_right_from_knee"], hip_right_rotation + knee_right_rotation))
    return {
        "root": root,
        "pelvis": pelvis,
        "torso": torso,
        "neck": neck,
        "head": head,
        "shoulder_left": shoulder_left,
        "elbow_left": elbow_left,
        "wrist_left": wrist_left,
        "shoulder_right": shoulder_right,
        "elbow_right": elbow_right,
        "wrist_right": wrist_right,
        "hip_left": hip_left,
        "knee_left": knee_left,
        "ankle_left": ankle_left,
        "hip_right": hip_right,
        "knee_right": knee_right,
        "ankle_right": ankle_right,
    }


def source_fit(source_bbox: Tuple[int, int, int, int], canvas_size: Tuple[int, int], bottom_margin: int = 54, side_margin: int = 56) -> Tuple[float, float, float]:
    width = max(1, source_bbox[2] - source_bbox[0])
    height = max(1, source_bbox[3] - source_bbox[1])
    scale = min((canvas_size[0] - side_margin * 2) / float(width), (canvas_size[1] - bottom_margin - 40) / float(height))
    offset_x = (canvas_size[0] / 2.0) - ((source_bbox[0] + width / 2.0) * scale)
    offset_y = (canvas_size[1] - bottom_margin) - (source_bbox[3] * scale)
    return scale, offset_x, offset_y


def map_source_point(point: Tuple[float, float], scale: float, offset_x: float, offset_y: float) -> Tuple[float, float]:
    return point[0] * scale + offset_x, point[1] * scale + offset_y


def render_pose_from_sprite_model(
    project: Dict[str, Any],
    rig: Dict[str, Any],
    transforms: Dict[str, Any],
    save_path: Optional[Path] = None,
    part_asset_overrides: Optional[Dict[str, Any]] = None,
    corrective_patches: Optional[Dict[str, Any]] = None,
) -> Tuple[Image.Image, Dict[str, Any]]:
    project_dir = PROJECTS_ROOT / project["project_id"]
    sprite_model = project["sprite_model"]
    parts = sorted(sprite_model["parts"], key=lambda item: item["draw_order"])
    joints = compute_pose_joints(rig, transforms)
    neutral_joints = {key: tuple(value) for key, value in (rig.get("rig_joint_map") or {}).items()}
    scale, offset_x, offset_y = source_fit(tuple(rig["source_bounds"]), WORKING_CANVAS)
    pixel_art_mode = is_pixel_art_rig_profile(rig.get("rig_profile"))
    prop_attachment_joint = rig.get("prop_attachment_joint") or "wrist_right"
    if rig.get("rig_profile") in {SIDE_KNIGHT_SIMPLE_7, SIDE_KNIGHT_DUAL_LEG_8}:
        prop_chain_rotation = float(transforms.get("shoulder_front_rotation", 0.0)) + float(transforms.get("weapon_rotation", 0.0))
        if rig.get("rig_profile") == SIDE_KNIGHT_DUAL_LEG_8 and "ankle_back" in joints:
            foot_anchor = {
                "left": [round(value, 2) for value in map_source_point(joints["ankle_front"], scale, offset_x, offset_y)],
                "right": [round(value, 2) for value in map_source_point(joints["ankle_back"], scale, offset_x, offset_y)],
            }
        else:
            foot_anchor = [round(value, 2) for value in map_source_point(joints["ankle_front"], scale, offset_x, offset_y)]
        rotations = {
            "head": float(transforms.get("head_rotation", 0.0)),
            "torso_pelvis": float(transforms.get("torso_rotation", 0.0)),
            "front_arm": float(transforms.get("shoulder_front_rotation", 0.0)),
            "front_leg": float(transforms.get("hip_front_rotation", 0.0)),
            "weapon": prop_chain_rotation,
            "cape_back": float(transforms.get("torso_rotation", 0.0)) + float(transforms.get("cape_back_rotation_bias", 0.0)),
            "front_cloth": (float(transforms.get("torso_rotation", 0.0)) * 0.45) + float(transforms.get("front_cloth_rotation_bias", 0.0)),
        }
        if rig.get("rig_profile") == SIDE_KNIGHT_DUAL_LEG_8:
            rotations["back_leg"] = float(transforms.get("hip_back_rotation", 0.0))
    else:
        prop_rotation = float(transforms.get("prop_rotation", 0.0))
        if prop_attachment_joint == "wrist_left":
            prop_chain_rotation = float(transforms.get("shoulder_left_rotation", 0.0)) + float(transforms.get("elbow_left_rotation", 0.0)) + prop_rotation
        else:
            prop_chain_rotation = float(transforms.get("shoulder_right_rotation", 0.0)) + float(transforms.get("elbow_right_rotation", 0.0)) + prop_rotation
        foot_anchor = None

    canvas = Image.new("RGBA", WORKING_CANVAS, (0, 0, 0, 0))
    render_log = []
    draw_sequence = []
    overrides = part_asset_overrides if isinstance(part_asset_overrides, dict) else {}
    patches = normalize_manual_frame_patches(corrective_patches)
    parts_by_name = {part["part_name"]: part for part in parts}
    patches_before: Dict[str, List[Dict[str, Any]]] = {}
    for patch in patches.values():
        patches_before.setdefault(str(patch["keep_behind_part_name"]), []).append(patch)
    if rig.get("rig_profile") not in {SIDE_KNIGHT_SIMPLE_7, SIDE_KNIGHT_DUAL_LEG_8}:
        rotations = {
            "hair_back": float(transforms.get("head_rotation", 0.0)),
            "head": float(transforms.get("head_rotation", 0.0)),
            "hair_front": float(transforms.get("head_rotation", 0.0)),
            "torso": float(transforms.get("torso_rotation", 0.0)),
            "pelvis": float(transforms.get("pelvis_rotation", 0.0)),
            "upper_arm_left": float(transforms.get("shoulder_left_rotation", 0.0)),
            "lower_arm_left": float(transforms.get("shoulder_left_rotation", 0.0)) + float(transforms.get("elbow_left_rotation", 0.0)),
            "hand_left": float(transforms.get("shoulder_left_rotation", 0.0)) + float(transforms.get("elbow_left_rotation", 0.0)),
            "upper_arm_right": float(transforms.get("shoulder_right_rotation", 0.0)),
            "lower_arm_right": float(transforms.get("shoulder_right_rotation", 0.0)) + float(transforms.get("elbow_right_rotation", 0.0)),
            "hand_right": float(transforms.get("shoulder_right_rotation", 0.0)) + float(transforms.get("elbow_right_rotation", 0.0)),
            "upper_leg_left": float(transforms.get("hip_left_rotation", 0.0)),
            "lower_leg_left": float(transforms.get("hip_left_rotation", 0.0)) + float(transforms.get("knee_left_rotation", 0.0)),
            "foot_left": float(transforms.get("hip_left_rotation", 0.0)) + float(transforms.get("knee_left_rotation", 0.0)) + float(transforms.get("ankle_left_rotation", 0.0)),
            "upper_leg_right": float(transforms.get("hip_right_rotation", 0.0)),
            "lower_leg_right": float(transforms.get("hip_right_rotation", 0.0)) + float(transforms.get("knee_right_rotation", 0.0)),
            "foot_right": float(transforms.get("hip_right_rotation", 0.0)) + float(transforms.get("knee_right_rotation", 0.0)) + float(transforms.get("ankle_right_rotation", 0.0)),
            "prop": prop_chain_rotation,
            "accessory_front": float(transforms.get("torso_rotation", 0.0)),
            "accessory_back": float(transforms.get("torso_rotation", 0.0)),
        }
    if pixel_art_mode:
        rotations = {role: quantize_pixel_part_rotation(role, rotation) for role, rotation in rotations.items()}

    def composite_bound_asset(bound_part: Dict[str, Any], asset_override: Optional[Dict[str, Any]] = None, logical_name: Optional[str] = None, kind: str = "part") -> None:
        image, _ = load_part_asset(project_dir, bound_part, asset_override=asset_override)
        if image.size == (1, 1) and image.getchannel("A").getbbox() is None:
            return
        scaled_image = image.resize(
            (
                max(1, int(round(image.size[0] * scale))),
                max(1, int(round(image.size[1] * scale))),
            ),
            resample=Image.Resampling.NEAREST if pixel_art_mode else Image.Resampling.BICUBIC,
        )
        pivot = (
            max(0, int(round(bound_part["pivot_point"][0] * scale))),
            max(0, int(round(bound_part["pivot_point"][1] * scale))),
        )
        parent_joint = bound_part["parent_joint"]
        current_joint_world = map_source_point(joints[parent_joint], scale, offset_x, offset_y)
        role = bound_part.get("part_role", bound_part["part_name"])
        rotation = rotations.get(role, 0.0)
        neutral_joint = neutral_joints.get(parent_joint, joints[parent_joint])
        neutral_pivot = world_pivot(bound_part)
        neutral_offset = vector_between(neutral_joint, neutral_pivot)
        scaled_offset = (neutral_offset[0] * scale, neutral_offset[1] * scale)
        rotated_offset = rotate_vector(scaled_offset, rotation)
        pivot_world = (
            current_joint_world[0] + rotated_offset[0],
            current_joint_world[1] + rotated_offset[1],
        )
        composite_part(
            canvas,
            scaled_image,
            pivot_world,
            pivot,
            rotation,
            resample=Image.Resampling.NEAREST if pixel_art_mode else Image.Resampling.BICUBIC,
        )
        draw_sequence.append(logical_name or bound_part["part_name"])
        render_log.append({
            "part": logical_name or bound_part["part_name"],
            "base_part_name": bound_part["part_name"],
            "kind": kind,
            "part_role": role,
            "joint": parent_joint,
            "rotation": round(rotation, 2),
            "pivot_world": [round(pivot_world[0], 2), round(pivot_world[1], 2)],
            "asset_override": asset_override,
        })

    for part in parts:
        for patch in patches_before.get(part["part_name"], []):
            source_part = parts_by_name.get(str(patch["source_part_name"]))
            if source_part is None:
                continue
            composite_bound_asset(source_part, asset_override=patch, logical_name=patch["patch_id"], kind="corrective_patch")
        asset_override = overrides.get(part["part_name"]) if isinstance(overrides.get(part["part_name"]), dict) else None
        composite_bound_asset(part, asset_override=asset_override, logical_name=part["part_name"], kind="part")

    if save_path is not None:
        canvas.save(save_path)
    if foot_anchor is None:
        foot_anchor = {
            "left": [round(value, 2) for value in map_source_point(joints["ankle_left"], scale, offset_x, offset_y)],
            "right": [round(value, 2) for value in map_source_point(joints["ankle_right"], scale, offset_x, offset_y)],
        }
    elif isinstance(foot_anchor, list):
        foot_anchor = {"left": foot_anchor, "right": foot_anchor}
    return canvas, {
        "draw_sequence": draw_sequence,
        "render_log": render_log,
        "foot_anchor": foot_anchor,
        "joints": {key: [round(value[0], 2), round(value[1], 2)] for key, value in joints.items()},
        "part_asset_overrides": overrides,
        "corrective_patches": patches,
    }


def build_layered_character(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    return build_sprite_model(project_id, progress=progress)


def build_rig(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    sprite_model = project.get("sprite_model")
    if not sprite_model:
        raise ValueError("Sprite model build is required before rig build.")
    rig_profile = active_rig_profile_name(project, sprite_model.get("rig_layout") or project.get("rig_layout"))
    prop_part = next((part for part in sprite_model["parts"] if canonical_sprite_part_role(part, rig_profile) in {"prop", "weapon"}), None)
    if rig_profile in {SIDE_KNIGHT_SIMPLE_7, SIDE_KNIGHT_DUAL_LEG_8}:
        prop_attachment_joint = "wrist_front"
    else:
        prop_attachment_joint = prop_part.get("parent_joint") if prop_part and prop_part.get("parent_joint") else ("wrist_left" if sprite_model.get("source_facing") == "left" else "wrist_right")
    existing_clips = copy.deepcopy(project.get("animation_clips") or {})
    reset_downstream_assets(project_id, "rig")
    project = clear_project_downstream_state(project, "rig")

    call_progress(progress, 10, "Preparing rig", "Building a deterministic rig from the extracted sprite model.")
    joint_map = build_joint_map_from_sprite_model(sprite_model)
    joint_vectors = build_joint_vectors(joint_map)
    clips = build_default_animation_clips(joint_map, existing_clips)
    rig = {
        "source_mode": "sprite_model",
        "source_summary": "Rig is built from the extracted canonical sprite model.",
        "rig_profile": rig_profile,
        "rig_layout": sprite_model.get("rig_layout") or project.get("rig_layout"),
        "joints": sprite_model.get("rig_layout", {}).get("joint_schema", {}).get("joints") or (RIG_PROFILES[rig_profile]["joint_schema"]["joints"]),
        "rig_joint_map": joint_map,
        "joint_vectors": joint_vectors,
        "per_joint_rotation_limits": ({
            "torso": {"min": -12, "max": 12},
            "head": {"min": -18, "max": 18},
            "shoulder_front": {"min": -40, "max": 40},
            "hip_front": {"min": -22, "max": 22},
            **({"hip_back": {"min": -18, "max": 18}} if rig_profile == SIDE_KNIGHT_DUAL_LEG_8 else {}),
        } if rig_profile in {SIDE_KNIGHT_SIMPLE_7, SIDE_KNIGHT_DUAL_LEG_8} else {
            "torso": {"min": -12, "max": 12},
            "head": {"min": -18, "max": 18},
            "shoulder_left": {"min": -40, "max": 40},
            "elbow_left": {"min": -5, "max": 55},
            "shoulder_right": {"min": -40, "max": 40},
            "elbow_right": {"min": -5, "max": 55},
            "hip_left": {"min": -28, "max": 28},
            "knee_left": {"min": -4, "max": 45},
            "hip_right": {"min": -28, "max": 28},
            "knee_right": {"min": -4, "max": 45},
        }),
        "draw_order_rules_for_overlap": sprite_model["draw_order"],
        "foot_anchor_reference": {
            "left": joint_map["ankle_front"] if rig_profile in {SIDE_KNIGHT_SIMPLE_7, SIDE_KNIGHT_DUAL_LEG_8} else joint_map["ankle_left"],
            "right": joint_map["ankle_back"] if rig_profile == SIDE_KNIGHT_DUAL_LEG_8 else joint_map["ankle_front"] if rig_profile == SIDE_KNIGHT_SIMPLE_7 else joint_map["ankle_right"],
            "pivot": list(FRAME_PIVOT),
        },
        "prop_attachment_joint": prop_attachment_joint,
        "pivot_map": {part["part_name"]: part["pivot_point"] for part in sprite_model["parts"]},
        "source_bounds": sprite_model["source_bounds"],
        "neutral_pose_render": "rig/neutral_pose.png",
        "approved_for_production": False,
        "created_at": now_iso(),
    }
    call_progress(progress, 48, "Rendering neutral pose", "Capturing the deterministic neutral pose from the extracted parts.")
    _, neutral_meta = render_pose_from_sprite_model(project, rig, neutral_pose_transforms(), project_dir / "rig" / "neutral_pose.png")
    rig["occlusion_order_map"] = neutral_meta["draw_sequence"]
    write_json(canonical_downstream_path(project_dir, "rig"), rig)
    write_json(project_dir / "rig" / "joint_map.json", joint_map)
    write_json(project_dir / "rig" / "pivot_map.json", rig["pivot_map"])
    write_json(canonical_downstream_path(project_dir, "animation_clips"), clips)
    project["rig"] = rig
    project["animation_clips"] = clips
    project["animation_templates"] = clips
    project["current_stage"] = "rig_review"
    project["status"] = "rig_ready"
    project["rig_review_approved"] = False
    project["qa_report"] = None
    project["last_export"] = None
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Rig ready", "Review the skeleton and neutral pose before rendering clips.")
    return rig


def get_manual_animation_clips(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    return project.get("manual_animation_clips") or default_manual_animation_clips(project_id)


def create_manual_animation_clip(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("rig"):
        raise ValueError("Build the rig before creating manual clips.")
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip_name = str(payload.get("clip_name") or "Manual Clip").strip() or "Manual Clip"
    base_id = sanitize_filename(slugify(clip_name), "manual-clip")
    clip_id = base_id
    counter = 2
    while clip_id in (store.get("clips") or {}):
        clip_id = "%s-%d" % (base_id, counter)
        counter += 1
    clip = default_manual_clip(
        project_dir,
        clip_id,
        clip_name,
        frame_count=manual_clip_frame_count(payload.get("frame_count"), 8),
        fps=max(1, min(60, int(payload.get("fps") or 12))),
        loop=bool(payload.get("loop", True)),
    )
    store.setdefault("clips", {})[clip_id] = clip
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["current_stage"] = "clips"
    project["status"] = "manual_clip_created"
    project["updated_at"] = now_iso()
    save_project(project)
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def manual_clip_or_error(project: Dict[str, Any], clip_id: str) -> Dict[str, Any]:
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project["project_id"])
    clip = (store.get("clips") or {}).get(clip_id)
    if not clip:
        raise ValueError("Unknown manual clip: %s." % clip_id)
    return clip


def update_manual_animation_clip_meta(project_id: str, clip_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    next_frame_count = manual_clip_frame_count(payload.get("frame_count"), clip.get("frame_count") or 8)
    clip["clip_name"] = str(payload.get("clip_name") or clip.get("clip_name") or humanize_identifier(clip_id)).strip() or clip["clip_name"]
    clip["fps"] = max(1, min(60, int(payload.get("fps") or clip.get("fps") or 12)))
    clip["loop"] = bool(payload.get("loop", clip.get("loop", True)))
    current_frames = [normalize_manual_clip_frame_entry(frame) for frame in (clip.get("frames") or [])]
    while len(current_frames) < next_frame_count:
        current_frames.append(normalize_manual_clip_frame_entry({}))
    clip["frame_count"] = next_frame_count
    clip["frames"] = current_frames[:next_frame_count]
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_updated"
    project["updated_at"] = now_iso()
    save_project(project)
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def update_manual_animation_clip_frame(project_id: str, clip_id: str, frame_index: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    current_entry = normalize_manual_clip_frame_entry((clip.get("frames") or [])[frame_index])
    incoming = payload.get("transforms") if isinstance(payload.get("transforms"), dict) else payload
    next_entry = dict(current_entry)
    next_entry["transforms"] = normalize_manual_clip_frame(incoming)
    if isinstance(payload.get("part_repairs"), dict):
        next_entry["part_repairs"] = normalize_manual_frame_repairs(payload.get("part_repairs"))
    if isinstance(payload.get("corrective_patches"), dict):
        next_entry["corrective_patches"] = normalize_manual_frame_patches(payload.get("corrective_patches"))
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(next_entry)
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_updated"
    project["updated_at"] = now_iso()
    save_project(project)
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def copy_manual_animation_clip_frame(project_id: str, clip_id: str, frame_index: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    source_index = int(payload.get("source_index", max(0, frame_index - 1)))
    if source_index < 0 or source_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Source frame index out of range.")
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(clip["frames"][source_index])
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_copied"
    project["updated_at"] = now_iso()
    save_project(project)
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def reset_manual_animation_clip_frame(project_id: str, clip_id: str, frame_index: int) -> Dict[str, Any]:
    return update_manual_animation_clip_frame(project_id, clip_id, frame_index, {"transforms": neutral_pose_transforms(), "part_repairs": {}, "corrective_patches": {}})


def generate_manual_animation_clip_frame_repair(project_id: str, clip_id: str, frame_index: int, part_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    result = recover_sprite_model_occlusion(project_id, {"part_name": part_name})
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "part_name": part_name,
        "variants": result.get("variants") or [],
    }


def apply_manual_animation_clip_frame_repair(project_id: str, clip_id: str, frame_index: int, part_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    image_path = str(payload.get("image_path") or "").strip()
    if not image_path:
        raise ValueError("repair/apply requires image_path.")
    frame_entry = normalize_manual_clip_frame_entry((clip.get("frames") or [])[frame_index])
    repairs = dict(frame_entry.get("part_repairs") or {})
    repairs[part_name] = {
        "variant_id": str(payload.get("variant_id") or "").strip() or None,
        "image_path": image_path,
        "mask_path": str(payload.get("mask_path") or "").strip() or None,
        "source": str(payload.get("source") or "recover-occlusion").strip() or "recover-occlusion",
        "summary": str(payload.get("summary") or "").strip() or None,
        "applied_at": now_iso(),
    }
    frame_entry["part_repairs"] = repairs
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(frame_entry)
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_repair_applied"
    project["updated_at"] = now_iso()
    save_project(project)
    hydrated = hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "part_name": part_name,
        "frame": hydrated["frames"][frame_index],
        "clip": hydrated,
    }


def clear_manual_animation_clip_frame_repair(project_id: str, clip_id: str, frame_index: int, part_name: str) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    frame_entry = normalize_manual_clip_frame_entry((clip.get("frames") or [])[frame_index])
    repairs = dict(frame_entry.get("part_repairs") or {})
    repairs.pop(part_name, None)
    frame_entry["part_repairs"] = repairs
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(frame_entry)
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_repair_cleared"
    project["updated_at"] = now_iso()
    save_project(project)
    hydrated = hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "part_name": part_name,
        "frame": hydrated["frames"][frame_index],
        "clip": hydrated,
    }


def generate_manual_animation_clip_frame_patch(project_id: str, clip_id: str, frame_index: int, source_part_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    result = recover_sprite_model_occlusion(project_id, {"part_name": source_part_name})
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "source_part_name": source_part_name,
        "variants": result.get("variants") or [],
    }


def apply_manual_animation_clip_frame_patch(project_id: str, clip_id: str, frame_index: int, source_part_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    image_path = str(payload.get("image_path") or "").strip()
    keep_behind_part_name = str(payload.get("keep_behind_part_name") or "").strip()
    if not image_path:
        raise ValueError("patch/apply requires image_path.")
    if not keep_behind_part_name:
        raise ValueError("patch/apply requires keep_behind_part_name.")
    sprite_parts = project.get("sprite_model", {}).get("parts") or []
    part_names = {str(item.get("part_name")) for item in sprite_parts if item.get("part_name")}
    if source_part_name not in part_names:
        raise ValueError("Unknown source part: %s." % source_part_name)
    if keep_behind_part_name not in part_names:
        raise ValueError("Unknown keep_behind_part_name: %s." % keep_behind_part_name)
    patch_id = "patch:%s" % source_part_name
    frame_entry = normalize_manual_clip_frame_entry((clip.get("frames") or [])[frame_index])
    patches = dict(frame_entry.get("corrective_patches") or {})
    patches[patch_id] = {
        "patch_id": patch_id,
        "source_part_name": source_part_name,
        "keep_behind_part_name": keep_behind_part_name,
        "variant_id": str(payload.get("variant_id") or "").strip() or None,
        "image_path": image_path,
        "mask_path": str(payload.get("mask_path") or "").strip() or None,
        "source": str(payload.get("source") or "recover-occlusion").strip() or "recover-occlusion",
        "summary": str(payload.get("summary") or "").strip() or None,
        "applied_at": now_iso(),
    }
    frame_entry["corrective_patches"] = patches
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(frame_entry)
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_patch_applied"
    project["updated_at"] = now_iso()
    save_project(project)
    hydrated = hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "source_part_name": source_part_name,
        "frame": hydrated["frames"][frame_index],
        "clip": hydrated,
    }


def clear_manual_animation_clip_frame_patch(project_id: str, clip_id: str, frame_index: int, source_part_name: str) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    frame_entry = normalize_manual_clip_frame_entry((clip.get("frames") or [])[frame_index])
    patches = dict(frame_entry.get("corrective_patches") or {})
    patches.pop("patch:%s" % source_part_name, None)
    frame_entry["corrective_patches"] = patches
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(frame_entry)
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_patch_cleared"
    project["updated_at"] = now_iso()
    save_project(project)
    hydrated = hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "source_part_name": source_part_name,
        "frame": hydrated["frames"][frame_index],
        "clip": hydrated,
    }


def render_manual_animation_clip_preview(project_id: str, clip_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("rig"):
        raise ValueError("Build the rig before rendering manual clips.")
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    render_root = manual_clip_render_root(project_dir) / clip_id
    frame_dir = render_root / "frames"
    clear_directory(render_root)
    frame_dir.mkdir(parents=True, exist_ok=True)
    manifests = []
    frame_total = int(clip.get("frame_count") or len(clip.get("frames") or []))
    for frame_index, frame_entry in enumerate((clip.get("frames") or [])[:frame_total]):
        normalized_frame = normalize_manual_clip_frame_entry(frame_entry)
        transforms = normalized_frame["transforms"]
        part_repairs = normalized_frame["part_repairs"]
        corrective_patches = normalized_frame["corrective_patches"]
        call_progress(progress, 10 + int((frame_index / max(1, frame_total)) * 78), "Rendering manual frame %d of %d" % (frame_index + 1, frame_total), "Compositing the authored manual pose against the current rig and sprite model.")
        raw, render_meta = render_pose_from_sprite_model(project, project["rig"], transforms, part_asset_overrides=part_repairs, corrective_patches=corrective_patches)
        foot_anchor = render_meta.get("foot_anchor") or {}
        anchor_candidates = [
            tuple(foot_anchor[name])
            for name in ("left", "right")
            if isinstance(foot_anchor.get(name), list) and len(foot_anchor.get(name)) == 2
        ]
        anchor_point = None
        if anchor_candidates:
            anchor_point = (
                sum(point[0] for point in anchor_candidates) / float(len(anchor_candidates)),
                sum(point[1] for point in anchor_candidates) / float(len(anchor_candidates)),
            )
        final_frame, cleanup = cleanup_frame(raw, anchor_point=anchor_point)
        frame_name = "%s_%02d.png" % (clip_id, frame_index)
        final_path = frame_dir / frame_name
        final_frame.save(final_path)
        manifests.append({
            "frame_name": frame_name,
            "path": str(final_path.relative_to(project_dir)),
            "cleanup": cleanup,
            "render_meta": render_meta,
            "joint_transforms": transforms,
            "part_repairs": part_repairs,
            "corrective_patches": corrective_patches,
        })
    manifest_path = render_root / "render_manifest.json"
    gif_path = render_root / "preview.gif"
    write_json(manifest_path, {"animation": clip_id, "clip_name": clip.get("clip_name"), "frames": manifests})
    preview_frames = [Image.open(project_dir / item["path"]).convert("RGBA") for item in manifests]
    if preview_frames:
        preview_frames[0].save(
            gif_path,
            save_all=True,
            append_images=preview_frames[1:],
            duration=[int(1000 / max(1, int(clip.get("fps") or 12)))] * len(preview_frames),
            loop=0 if clip.get("loop", True) else 1,
            disposal=2,
            transparency=0,
        )
    clip["preview_render"] = {
        "status": "complete",
        "gif_path": str(gif_path.relative_to(project_dir)),
        "render_manifest_path": str(manifest_path.relative_to(project_dir)),
        "frame_dir": str(frame_dir.relative_to(project_dir)),
        "frames": [item["path"] for item in manifests],
        "generated_at": now_iso(),
    }
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    clip["updated_at"] = now_iso()
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_preview_rendered"
    project["current_stage"] = "clips"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Manual preview ready", "Review the generated GIF before approving this clip.")
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def approve_manual_animation_clip(project_id: str, clip_id: str, approved: bool) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    hydrated = hydrate_manual_animation_clips(store, project_dir)["clips"][clip_id]
    if approved:
        if hydrated.get("is_stale"):
            raise ValueError("Manual clip approval is blocked until the clip is re-rendered against the current rig and sprite model.")
        if not hydrated.get("preview_render_complete"):
            raise ValueError("Render the manual preview before approving the clip.")
        clip["approval_status"] = "approved"
        clip["approved_at"] = now_iso()
    else:
        clip["approval_status"] = "draft"
        clip["approved_at"] = None
    clip["updated_at"] = now_iso()
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_%s" % ("approved" if approved else "unapproved")
    project["updated_at"] = now_iso()
    save_project(project)
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def update_animation_clip(project_id: str, animation_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if animation_name not in ANIMATION_SPECS:
        raise ValueError("Unknown clip: %s." % animation_name)
    project = load_project(project_id)
    if not project.get("rig"):
        raise ValueError("Build the rig before editing clips.")
    clips = hydrate_animation_clips(project.get("animation_clips"), project.get("animation_templates"), rig_profile=active_rig_profile_name(project, project.get("rig_layout")))
    clip = clips[animation_name]
    merged_controls = dict(clip.get("controls") or {})
    incoming_controls = payload.get("controls") if isinstance(payload.get("controls"), dict) else payload
    if isinstance(incoming_controls, dict):
        merged_controls.update({key: value for key, value in incoming_controls.items() if key in DEFAULT_CLIP_CONTROLS[animation_name]})
    controls = normalize_clip_controls(animation_name, merged_controls)
    overrides = clip_frame_overrides(ANIMATION_SPECS[animation_name]["frame_count"], payload.get("frame_overrides") if "frame_overrides" in payload else clip.get("frame_overrides"))
    clip["controls"] = controls
    clip["frame_overrides"] = overrides
    clip["joint_transforms_per_frame"] = generate_clip_frames(animation_name, controls, overrides, rig_profile=active_rig_profile_name(project, project.get("rig_layout")))
    clips[animation_name] = clip
    reset_downstream_assets(project_id, "clips")
    project = clear_project_downstream_state(project, "clips")
    project["animation_clips"] = clips
    project["animation_templates"] = clips
    project["current_stage"] = "clips"
    project["status"] = "%s_clip_updated" % animation_name
    project["updated_at"] = now_iso()
    save_project(project)
    return clip


def reset_animation_clip(project_id: str, animation_name: str) -> Dict[str, Any]:
    return update_animation_clip(project_id, animation_name, {
        "controls": default_clip_controls(animation_name),
        "frame_overrides": [{} for _ in range(ANIMATION_SPECS[animation_name]["frame_count"])],
    })


def approve_sprite_model_review(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    sprite_model = project.get("sprite_model")
    if not sprite_model:
        raise ValueError("Sprite model cannot be approved before a build.")
    if sprite_model.get("status") == "fail":
        raise ValueError("Sprite model approval is blocked until build failures are resolved.")
    project["sprite_model_approved"] = True
    project["layer_review_approved"] = True
    project["sprite_model"]["approved_for_rigging"] = True
    project["updated_at"] = now_iso()
    save_project(project)
    return {"ok": True}


def approve_rig_review(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("rig"):
        raise ValueError("Rig review cannot be approved before rig build.")
    if not project.get("sprite_model_approved") and not project.get("layer_review_approved"):
        raise ValueError("Sprite-model approval is required before rig review approval.")
    project["rig_review_approved"] = True
    project["rig"]["approved_for_production"] = True
    project["updated_at"] = now_iso()
    save_project(project)
    return {"ok": True}


def render_animation(project_id: str, animation_name: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("rig"):
        raise ValueError("Build the rig before rendering clips.")
    if not project.get("rig_review_approved"):
        raise ValueError("Rig review approval is required before production.")
    clips = project.get("animation_clips") or load_json(canonical_downstream_path(PROJECTS_ROOT / project_id, "animation_clips"))
    if animation_name not in clips:
        raise ValueError("Unknown clip: %s." % animation_name)
    delete_path(canonical_downstream_path(PROJECTS_ROOT / project_id, "qa_report"))
    clear_directory(PROJECTS_ROOT / project_id / "exports")
    project["qa_report"] = None
    project["last_export"] = None

    clip = clips[animation_name]
    project_dir = PROJECTS_ROOT / project_id
    output_dir = project_dir / "animations" / animation_name
    output_dir.mkdir(parents=True, exist_ok=True)
    clear_directory(output_dir)
    manifests = []
    frame_total = len(clip["joint_transforms_per_frame"])
    for frame_index, transforms in enumerate(clip["joint_transforms_per_frame"]):
        call_progress(progress, 12 + int((frame_index / max(1, frame_total)) * 80), "Rendering %s frame %d of %d" % (animation_name, frame_index + 1, frame_total), "Compositing extracted parts with deterministic rig transforms.")
        raw, render_meta = render_pose_from_sprite_model(project, project["rig"], transforms)
        foot_anchor = render_meta.get("foot_anchor") or {}
        anchor_candidates = [
            tuple(foot_anchor[name])
            for name in ("left", "right")
            if isinstance(foot_anchor.get(name), list) and len(foot_anchor.get(name)) == 2
        ]
        anchor_point = None
        if anchor_candidates:
            anchor_point = (
                sum(point[0] for point in anchor_candidates) / float(len(anchor_candidates)),
                sum(point[1] for point in anchor_candidates) / float(len(anchor_candidates)),
            )
        final_frame, cleanup = cleanup_frame(raw, anchor_point=anchor_point)
        frame_name = "%s_%02d.png" % (animation_name, frame_index)
        final_path = output_dir / frame_name
        final_frame.save(final_path)
        manifests.append({
            "frame_name": frame_name,
            "path": str(final_path.relative_to(project_dir)),
            "cleanup": cleanup,
            "render_meta": render_meta,
            "joint_transforms": transforms,
        })
    write_json(output_dir / "render_manifest.json", {"animation": animation_name, "frames": manifests})
    project["current_stage"] = "production_%s" % animation_name
    project["status"] = "%s_rendered" % animation_name
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "%s ready" % animation_name.title(), "The deterministic clip frames are ready for QA.")
    return {"animation": animation_name, "frames": manifests, "fps": clip["fps"], "frame_count": clip["frame_count"]}


def approved_manual_animation_clips(project: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    store = project.get("manual_animation_clips") or {"clips": {}}
    return {
        clip_id: clip
        for clip_id, clip in (store.get("clips") or {}).items()
        if clip.get("approval_status") == "approved" and not clip.get("is_stale") and clip.get("preview_render_complete")
    }


def run_external_authoring_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = hydrate_external_authoring(project.get("external_authoring"), project_dir)
    bundle = store.get("imported_bundle") if isinstance(store.get("imported_bundle"), dict) else None
    if not store.get("enabled") or not bundle:
        raise ValueError("External authoring bundle is required before QA.")
    call_progress(progress, 12, "Checking SkelForm bundle", "Validating imported spritesheet and metadata files.")
    spritesheet_path = project_dir / str(bundle.get("spritesheet_image_path") or "")
    atlas_path = project_dir / str(bundle.get("atlas_path") or "")
    animations_path = project_dir / str(bundle.get("animations_path") or "")
    preview_gif_path = project_dir / str(bundle.get("preview_gif_path") or "") if bundle.get("preview_gif_path") else None
    atlas = load_json(atlas_path, None) if atlas_path.exists() else None
    animations = load_json(animations_path, None) if animations_path.exists() else None
    atlas_frames = atlas.get("frames") if isinstance(atlas, dict) else None
    animation_names = sorted(animations.keys()) if isinstance(animations, dict) else []
    referenced_frames: List[str] = []
    if isinstance(animations, dict):
        for clip in animations.values():
            if isinstance(clip, dict):
                referenced_frames.extend([str(name) for name in (clip.get("frames") or [])])
    frame_lookup = set((atlas_frames or {}).keys()) if isinstance(atlas_frames, dict) else set()
    missing_frame_refs = sorted(set(referenced_frames).difference(frame_lookup))
    report = {
        "project_id": project_id,
        "generated_at": now_iso(),
        "status": "pass",
        "mode": "external_authoring",
        "per_frame_checks": [],
        "per_animation_checks": {},
        "source_asset_hashes": {},
        "metadata_checks": {
            "external_authoring_enabled": check_state("pass" if store.get("enabled") else "fail"),
            "has_spritesheet": check_state("pass" if spritesheet_path.exists() else "fail"),
            "has_atlas": check_state("pass" if atlas_path.exists() else "fail"),
            "has_animations": check_state("pass" if animations_path.exists() else "fail"),
            "atlas_has_frames": check_state("pass" if isinstance(atlas_frames, dict) and atlas_frames else "fail"),
            "animations_non_empty": check_state("pass" if animation_names else "fail"),
            "animation_frames_resolve_in_atlas": check_state("pass" if not missing_frame_refs else "fail", {"missing_frames": missing_frame_refs}),
            "has_preview_gif": check_state("pass" if preview_gif_path and preview_gif_path.exists() else "warning"),
        },
        "notes": [
            "QA validated the imported external-authoring bundle rather than the legacy deterministic rig pipeline.",
            "Semantic animation quality still requires human review in the workbench.",
        ],
        "sprite_model_build_report": {"status": "pass", "source": "external_authoring"},
    }
    if spritesheet_path.exists():
        report["source_asset_hashes"][str(spritesheet_path.relative_to(project_dir))] = image_sha256(spritesheet_path)
    if atlas_path.exists():
        report["source_asset_hashes"][str(atlas_path.relative_to(project_dir))] = image_sha256(atlas_path)
    if animations_path.exists():
        report["source_asset_hashes"][str(animations_path.relative_to(project_dir))] = image_sha256(animations_path)
    if preview_gif_path and preview_gif_path.exists():
        report["source_asset_hashes"][str(preview_gif_path.relative_to(project_dir))] = image_sha256(preview_gif_path)
    if any(item["status"] == "fail" for item in report["metadata_checks"].values()):
        report["status"] = "fail"
    write_json(canonical_downstream_path(project_dir, "qa_report"), report)
    project["qa_report"] = report
    project["current_stage"] = "qa"
    project["status"] = "qa_%s" % report["status"]
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Checks complete", "Imported SkelForm bundle validation finished.")
    return report


def run_ai_workflow_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = ai_workflow_or_error(project)
    cleanup_runs = store.get("cleanup_runs") or {}
    report = {
        "project_id": project_id,
        "generated_at": now_iso(),
        "status": "pass",
        "mode": "ai_workflow",
        "workflow_profile": store.get("profile") or AI_WORKFLOW_PROFILE,
        "per_frame_checks": [],
        "per_animation_checks": {},
        "source_asset_hashes": {},
        "metadata_checks": {},
        "notes": [
            "QA validated AI-produced cleaned frames with deterministic pivot, transparency, and export checks.",
            "Semantic art direction still requires human review in the workbench.",
        ],
        "sprite_model_build_report": {"status": "pass", "source": "ai_workflow"},
    }
    for clip_index, clip_name in enumerate(AI_CLIP_SPECS):
        clip_group = cleanup_runs.get(clip_name) if isinstance(cleanup_runs.get(clip_name), dict) else {}
        approved_run_id = clip_group.get("approved_run_id")
        approved_run = (clip_group.get("runs") or {}).get(approved_run_id) if approved_run_id else None
        if not approved_run:
            raise ValueError("Approve cleaned %s frames before QA." % clip_name)
        animation_dir = project_dir / "animations" / clip_name
        manifest = load_json(animation_dir / "render_manifest.json", {"frames": []})
        frames = manifest.get("frames") or []
        draw_orders = []
        foot_anchors = []
        manifest_names = [item.get("frame_name") for item in frames]
        spec = AI_CLIP_SPECS[clip_name]
        for index in range(spec["frame_count"]):
            call_progress(progress, 8 + int(((clip_index * spec["frame_count"] + index) / max(1, sum(item["frame_count"] for item in AI_CLIP_SPECS.values()))) * 82), "Checking %s frame %d" % (clip_name, index + 1), "Validating cleaned frame dimensions, alpha, clipping, and pivot alignment.")
            frame_name = "%s_%02d.png" % (clip_name, index)
            path = animation_dir / frame_name
            if not path.exists():
                raise ValueError("Missing cleaned frame: %s" % frame_name)
            image = Image.open(path).convert("RGBA")
            alpha = image.getchannel("A")
            alpha_bounds = alpha.getbbox()
            frame_meta = next((item for item in frames if item.get("frame_name") == frame_name), None)
            if frame_meta is None:
                raise ValueError("Missing manifest row: %s" % frame_name)
            draw_orders.append(tuple(frame_meta.get("render_meta", {}).get("draw_sequence") or []))
            foot_anchors.append(frame_meta.get("render_meta", {}).get("foot_anchor") or {"left": [0, 0], "right": [0, 0]})
            report["source_asset_hashes"][str(path.relative_to(project_dir))] = image_sha256(path)
            checks = {
                "exact_frame_size": check_state("pass" if list(image.size) == [FRAME_SIZE, FRAME_SIZE] else "fail"),
                "transparent_background": check_state("pass" if alpha_bounds is not None and any(value < 255 for value in alpha.getdata()) else "fail"),
                "exact_pivot": check_state("pass" if frame_meta.get("cleanup", {}).get("pivot") == list(FRAME_PIVOT) else "fail", {"expected": list(FRAME_PIVOT)}),
                "no_clipping": check_state("fail" if border_has_alpha(image) else "pass"),
            }
            frame_status = aggregate_check_state([item["status"] for item in checks.values()])
            if frame_status == "fail":
                report["status"] = "fail"
            report["per_frame_checks"].append({
                "frame_name": frame_name,
                "status": frame_status,
                "checks": checks,
            })
        foot_y_values = [anchor["left"][1] for anchor in foot_anchors] + [anchor["right"][1] for anchor in foot_anchors]
        foot_anchor_stable = (max(foot_y_values) - min(foot_y_values)) <= 1 if foot_y_values else False
        first_left = (frames[0].get("render_meta", {}).get("foot_anchor", {}) if frames else {}).get("left", [0, 0])
        last_left = (frames[-1].get("render_meta", {}).get("foot_anchor", {}) if frames else {}).get("left", [0, 0])
        animation_checks = {
            "correct_frame_count": check_state("pass" if len(frames) == spec["frame_count"] else "fail"),
            "render_manifest_completeness": check_state("pass" if manifest_names == ["%s_%02d.png" % (clip_name, index) for index in range(spec["frame_count"])] else "fail"),
            "stable_draw_order": check_state("pass" if len(set(draw_orders)) == 1 else "fail"),
            "stable_foot_anchor": check_state("pass" if foot_anchor_stable else "fail"),
            "loop_seam_continuity": check_state("pass" if abs(first_left[1] - last_left[1]) <= 1 else "fail"),
            "metadata_correctness": check_state("pass" if (project.get("animation_clips", {}).get(clip_name, {}).get("frame_count") == spec["frame_count"] and project.get("animation_clips", {}).get(clip_name, {}).get("fps") == spec["fps"]) else "fail"),
        }
        animation_status = aggregate_check_state([item["status"] for item in animation_checks.values()])
        if animation_status == "fail":
            report["status"] = "fail"
        report["per_animation_checks"][clip_name] = {"status": animation_status, "checks": animation_checks}
    report["metadata_checks"] = {
        "ai_workflow_enabled": check_state("pass" if store.get("enabled") else "fail"),
        "workflow_profile_is_active": check_state("pass" if store.get("profile") == AI_WORKFLOW_PROFILE else "fail"),
        "has_approved_character_lock": check_state("pass" if bool((store.get("character_lock") or {}).get("approved_asset_id")) else "fail"),
        "has_approved_key_pose_set": check_state("pass" if bool((store.get("key_pose_set") or {}).get("approved_run_id")) else "fail"),
        "has_clean_idle_and_walk": check_state("pass" if all(bool((cleanup_runs.get(clip_name) or {}).get("approved_run_id")) for clip_name in AI_CLIP_SPECS) else "fail"),
        "dependency_health_snapshot": check_state("pass" if isinstance(store.get("dependency_status"), dict) and bool(store.get("dependency_status")) else "fail"),
    }
    if any(item["status"] == "fail" for item in report["metadata_checks"].values()):
        report["status"] = "fail"
    write_json(canonical_downstream_path(project_dir, "qa_report"), report)
    project["qa_report"] = report
    project["current_stage"] = "qa"
    project["status"] = "qa_%s" % report["status"]
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Checks complete", "AI workflow cleanup outputs passed through deterministic QA.")
    return report


def ai_workflow_ready_for_qa(store: Dict[str, Any]) -> bool:
    if not isinstance(store, dict) or not store.get("enabled") or store.get("legacy_mode"):
        return False
    cleanup_runs = store.get("cleanup_runs") or {}
    return all(bool((cleanup_runs.get(clip_name) or {}).get("approved_run_id")) for clip_name in AI_CLIP_SPECS)


def pixellab_pipeline_ready_for_qa(project: Dict[str, Any], project_dir: Path) -> bool:
    """
    Phase 6: Pixel Lab QA readiness check.

    Canonical inputs:
    - `pixellab_character.json`
    - `pixellab_animations.json`
    - `animation_clips.json` (built in Phase 5.5)
    """
    char_path = _pixellab_character_path(project_dir)
    anim_path = _pixellab_animations_path(project_dir)
    if not char_path.exists() or not anim_path.exists():
        return False
    anim_store = load_json(anim_path, None)
    if not isinstance(anim_store, dict):
        return False
    ab = anim_store.get("animations")
    if pixellab_missing_canonical_animation_clips(ab if isinstance(ab, dict) else None):
        return False
    clips = project.get("animation_clips") or load_json(canonical_downstream_path(project_dir, "animation_clips"), {})
    return isinstance(clips, dict) and bool(clips)


def run_pixellab_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id

    # Must exist and be non-empty.
    char_path = _pixellab_character_path(project_dir)
    anim_path = _pixellab_animations_path(project_dir)
    if not char_path.exists() or not anim_path.exists():
        raise ValueError("Pixel Lab canonical inputs missing; expected pixellab_character.json and pixellab_animations.json.")
    _pixellab_character_approved_guard(project_dir)  # also enforces approval

    pix_store = load_json(anim_path, None) or {}
    if not isinstance(pix_store, dict):
        pix_store = {}
    anim_block = pix_store.get("animations")
    miss_qa = pixellab_missing_canonical_animation_clips(anim_block if isinstance(anim_block, dict) else None)
    if miss_qa:
        raise ValueError(
            "pixellab_animations.json is missing generated clips: %s. "
            "Generate **idle** and **walk** on the Animations panel (template or custom), then run Build canonical clips."
            % ", ".join(miss_qa)
        )

    clips = project.get("animation_clips") or load_json(canonical_downstream_path(project_dir, "animation_clips"), {})
    if not isinstance(clips, dict) or not clips:
        raise ValueError("animation_clips.json must exist (Phase 5.5) before Pixel Lab QA.")

    # Only validate canonical idle/walk clips that actually contain Pixel Lab frame metadata
    # (i.e. Phase 5.5 copied `frames` into `animation_clips.json`).
    clip_names = [
        name
        for name in ["idle", "walk"]
        if name in clips
        and isinstance(clips.get(name), dict)
        and isinstance(clips.get(name).get("frames"), list)
    ]
    if not clip_names:
        raise ValueError("animation_clips.json contains no supported Pixel Lab animations (idle/walk).")

    report = {
        "project_id": project_id,
        "generated_at": now_iso(),
        "status": "pass",
        "mode": "pixellab",
        "per_frame_checks": [],
        "per_animation_checks": {},
        "source_asset_hashes": {},
        "metadata_checks": {},
        "notes": [
            "QA validates Pixel Lab canonical animation frames for size, transparency, and border clipping.",
            "Semantic art direction still requires human review in the workbench.",
        ],
    }

    for clip_index, clip_name in enumerate(clip_names):
        call_progress(
            progress,
            8 + int((clip_index / max(1, len(clip_names))) * 74),
            "Checking %s clip" % clip_name,
            "Validating Pixel Lab frames (size, transparency, clipping).",
        )
        spec = AI_CLIP_SPECS.get(clip_name) or ANIMATION_SPECS.get(clip_name) or {}
        expected_fc = int(spec.get("frame_count") or 0)
        expected_fps = int(spec.get("fps") or 0)

        clip = clips[clip_name]
        frame_count = int(clip.get("frame_count") or 0)
        fps = int(clip.get("fps") or 0)
        frames = clip.get("frames") if isinstance(clip.get("frames"), list) else []

        if expected_fc and frame_count != expected_fc:
            raise ValueError("Pixel Lab QA blocked: %s.frame_count=%s but expected %s." % (clip_name, frame_count, expected_fc))
        if expected_fps and fps != expected_fps:
            raise ValueError("Pixel Lab QA blocked: %s.fps=%s but expected %s." % (clip_name, fps, expected_fps))
        if expected_fc and len(frames) != expected_fc:
            raise ValueError("Pixel Lab QA blocked: %s.frames length=%s but expected %s." % (clip_name, len(frames), expected_fc))

        per_frame_states: List[str] = []
        for index in range(frame_count):
            call_progress(
                progress,
                8 + int(((clip_index * frame_count + index) / max(1, len(clip_names) * frame_count)) * 82),
                "Checking %s frame %d" % (clip_name, index + 1),
                "Validating frame image.",
            )
            frame_rel = frames[index] if index < len(frames) else None
            if not frame_rel:
                raise ValueError("Pixel Lab QA blocked: missing frame path for %s index %d." % (clip_name, index))
            path = project_dir / str(frame_rel)
            if not path.exists():
                raise ValueError("Pixel Lab QA blocked: missing frame file %s." % str(path))

            image = Image.open(path).convert("RGBA")
            # Pixel Lab animation frames may be produced at a smaller canvas size
            # (e.g. 64x64). Normalize to the canonical export size so QA checks and
            # atlas packing use the same invariants as deterministic/AI workflows.
            if list(image.size) != [FRAME_SIZE, FRAME_SIZE]:
                image, _ = cleanup_frame(image)
            alpha = image.getchannel("A")
            alpha_bounds = alpha.getbbox()
            checks = {
                "exact_frame_size": check_state("pass" if list(image.size) == [FRAME_SIZE, FRAME_SIZE] else "fail"),
                "transparent_background": check_state("pass" if alpha_bounds is not None and any(value < 255 for value in alpha.getdata()) else "fail"),
                "no_clipping": check_state("fail" if border_has_alpha(image) else "pass"),
            }
            frame_status = aggregate_check_state([item["status"] for item in checks.values()])
            per_frame_states.append(frame_status)
            if frame_status == "fail":
                report["status"] = "fail"
            report["per_frame_checks"].append({
                "frame_name": "%s_%02d.png" % (clip_name, index),
                "status": frame_status,
                "checks": checks,
            })
            report["source_asset_hashes"][str(path.relative_to(project_dir))] = image_sha256(path)

        animation_status = aggregate_check_state(per_frame_states)
        report["per_animation_checks"][clip_name] = {
            "status": animation_status,
            "checks": {
                "correct_frame_count": check_state("pass" if len(frames) == frame_count else "fail"),
                "metadata_correctness": check_state("pass" if frame_count == expected_fc and fps == expected_fps else "fail"),
            },
        }

    report["metadata_checks"] = {
        "has_pixellab_character": check_state("pass" if char_path.exists() else "fail"),
        "has_pixellab_animations": check_state("pass" if anim_path.exists() and bool(pix_store.get("animations")) else "fail"),
        "has_animation_clips": check_state("pass" if isinstance(clips, dict) and bool(clips) else "fail"),
    }
    if any(item["status"] == "fail" for item in report["metadata_checks"].values()):
        report["status"] = "fail"

    write_json(canonical_downstream_path(project_dir, "qa_report"), report)
    project["qa_report"] = report
    project["current_stage"] = "qa"
    project["status"] = "qa_%s" % report["status"]
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Checks complete", "Pixel Lab QA finished.")
    return report


def run_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    ai_workflow = project.get("ai_workflow") or {}
    if ai_workflow_ready_for_qa(ai_workflow):
        return run_ai_workflow_qa(project_id, progress=progress)
    external_authoring = project.get("external_authoring") or {}
    imported_bundle = external_authoring.get("imported_bundle") if isinstance(external_authoring.get("imported_bundle"), dict) else None
    if external_authoring.get("enabled") and imported_bundle:
        return run_external_authoring_qa(project_id, progress=progress)
    project_dir = PROJECTS_ROOT / project_id
    if pixellab_pipeline_ready_for_qa(project, project_dir):
        return run_pixellab_qa(project_id, progress=progress)
    sprite_model = project.get("sprite_model")
    rig = project.get("rig")
    clips = project.get("animation_clips") or load_json(canonical_downstream_path(project_dir, "animation_clips"), {})
    if not sprite_model or not rig or not clips:
        raise ValueError("Sprite model, rig, and animation clips must exist before QA.")
    build_report = sprite_model.get("build_report") or validate_sprite_model(project_dir, sprite_model)
    sprite_model["build_report"] = build_report
    sprite_model["status"] = build_report["status"]

    report = {
        "project_id": project_id,
        "generated_at": now_iso(),
        "status": "pass",
        "per_frame_checks": [],
        "per_animation_checks": {},
        "source_asset_hashes": {},
        "metadata_checks": {},
        "notes": [
            "QA validates deterministic asset structure and implemented image checks.",
            "Semantic art direction still requires a human review pass in the workbench.",
        ],
        "sprite_model_build_report": build_report,
    }

    rig_layout = sprite_model.get("rig_layout") or project.get("rig_layout") or {}
    required_roles = {item["part_name"] for item in (rig_layout.get("parts") or []) if item.get("required")}
    required_parts = set()
    for part in sprite_model["parts"]:
        role = part.get("part_role", part["part_name"])
        if required_roles and role not in required_roles:
            continue
        image, _ = load_part_asset(project_dir, part)
        if alpha_bbox(image) is not None:
            required_parts.add(role)
    manual_clips = approved_manual_animation_clips(project)
    runtime_animations: List[Tuple[str, Dict[str, Any], Path, str]] = [
        (animation_name, dict(spec), project_dir / "animations" / animation_name, "procedural")
        for animation_name, spec in ANIMATION_SPECS.items()
    ] + [
        (
            clip_id,
            {"frame_count": int(clip.get("frame_count") or 0), "fps": int(clip.get("fps") or 12), "loop": bool(clip.get("loop", True))},
            project_dir / str(clip.get("preview_render", {}).get("frame_dir") or ""),
            "manual",
        )
        for clip_id, clip in manual_clips.items()
    ]
    for animation_index, (animation_name, spec, animation_dir, animation_kind) in enumerate(runtime_animations):
        call_progress(progress, 8 + int((animation_index / max(1, len(runtime_animations))) * 74), "Checking %s clip" % animation_name, "Validating frame dimensions, pivots, parts, draw order, and loop continuity.")
        manifest = load_json((animation_dir.parent if animation_kind == "manual" else animation_dir) / "render_manifest.json", {"frames": []}) if animation_kind == "manual" else load_json(animation_dir / "render_manifest.json", {"frames": []})
        frames = manifest.get("frames", [])
        draw_orders = []
        foot_anchors = []
        frame_hashes = []
        manifest_names = [item.get("frame_name") for item in frames]
        for index in range(spec["frame_count"]):
            frame_name = "%s_%02d.png" % (animation_name, index)
            path = animation_dir / frame_name
            if not path.exists():
                raise ValueError("Missing frame: %s" % frame_name)
            image = Image.open(path).convert("RGBA")
            alpha = image.getchannel("A")
            alpha_bounds = alpha.getbbox()
            frame_meta = next((item for item in frames if item["frame_name"] == frame_name), None)
            if frame_meta is None:
                raise ValueError("Missing manifest row: %s" % frame_name)
            draw_sequence = frame_meta["render_meta"]["draw_sequence"]
            draw_roles = [item.get("part_role", item["part"]) for item in frame_meta["render_meta"]["render_log"]]
            draw_orders.append(tuple(draw_sequence))
            foot_anchors.append(frame_meta["render_meta"]["foot_anchor"])
            frame_hash = image_sha256(path)
            frame_hashes.append(frame_hash)
            report["source_asset_hashes"][str(path.relative_to(project_dir))] = frame_hash
            missing_parts = sorted(required_parts.difference(draw_roles))
            duplicate_prop = draw_roles.count("prop") > 1
            checks = {
                "exact_frame_size": check_state("pass" if list(image.size) == [FRAME_SIZE, FRAME_SIZE] else "fail"),
                "transparent_background": check_state("pass" if alpha_bounds is not None and any(value < 255 for value in alpha.getdata()) else "fail"),
                "exact_pivot": check_state("pass" if frame_meta.get("cleanup", {}).get("pivot") == list(FRAME_PIVOT) else "fail", {"expected": list(FRAME_PIVOT)}),
                "no_clipping": check_state("fail" if border_has_alpha(image) else "pass"),
                "no_missing_parts": check_state("fail" if missing_parts else "pass", {"missing_parts": missing_parts}),
                "no_duplicate_prop": check_state("fail" if duplicate_prop else "pass"),
            }
            frame_status = aggregate_check_state([item["status"] for item in checks.values()])
            if frame_status == "fail":
                report["status"] = "fail"
            report["per_frame_checks"].append({
                "frame_name": frame_name,
                "status": frame_status,
                "checks": checks,
            })

        stable_draw_order = len(set(draw_orders)) == 1
        foot_y_values = [anchor["left"][1] for anchor in foot_anchors] + [anchor["right"][1] for anchor in foot_anchors]
        foot_anchor_stable = (max(foot_y_values) - min(foot_y_values)) <= 30 if foot_y_values else False
        first_meta = frames[0] if frames else {}
        last_meta = frames[-1] if frames else {}
        first_left = first_meta.get("render_meta", {}).get("foot_anchor", {}).get("left", [0, 0])
        last_left = last_meta.get("render_meta", {}).get("foot_anchor", {}).get("left", [999, 999])
        loop_ok = abs(first_left[1] - last_left[1]) <= 6
        animation_checks = {
            "correct_frame_count": check_state("pass" if len(frames) == spec["frame_count"] else "fail"),
            "render_manifest_completeness": check_state(
                "pass" if manifest_names == ["%s_%02d.png" % (animation_name, index) for index in range(spec["frame_count"])] else "fail"
            ),
            "stable_draw_order": check_state("pass" if stable_draw_order else "fail"),
            "stable_foot_anchor": check_state("pass" if foot_anchor_stable else "fail"),
            "loop_seam_continuity": check_state("pass" if loop_ok else "fail"),
            "metadata_correctness": check_state(
                "pass"
                if (
                    (animation_kind == "procedural" and clips.get(animation_name, {}).get("frame_count") == spec["frame_count"] and clips.get(animation_name, {}).get("fps") == spec["fps"])
                    or (animation_kind == "manual" and manual_clips.get(animation_name, {}).get("frame_count") == spec["frame_count"] and manual_clips.get(animation_name, {}).get("fps") == spec["fps"])
                )
                else "fail"
            ),
            "clip_control_persistence": check_state("pass" if animation_kind == "manual" or isinstance(clips.get(animation_name, {}).get("controls"), dict) else "fail"),
        }
        animation_status = aggregate_check_state([item["status"] for item in animation_checks.values()])
        if animation_status == "fail":
            report["status"] = "fail"
        report["per_animation_checks"][animation_name] = {"status": animation_status, "checks": animation_checks}

    report["metadata_checks"] = {
        "has_approved_source_image": check_state(
            "pass"
            if (sprite_model.get("approved_source_image") or project.get("master_pose_approved"))
            else "fail"
        ),
        "has_sprite_model": check_state("pass" if bool(sprite_model.get("parts")) else "fail"),
        "sprite_model_build_report": check_state("pass" if build_report.get("status") != "fail" else "fail", {"status": build_report.get("status")}),
        "has_rig": check_state("pass" if bool(rig.get("rig_joint_map")) else "fail"),
        "has_animation_clips": check_state("pass" if set(clips.keys()) >= {"idle", "walk"} else "fail"),
        "manual_clips_not_stale": check_state("pass" if not any(clip.get("is_stale") for clip in (project.get("manual_animation_clips", {}).get("clips") or {}).values() if clip.get("approval_status") == "approved") else "fail"),
    }
    if any(item["status"] == "fail" for item in report["metadata_checks"].values()):
        report["status"] = "fail"
    write_json(canonical_downstream_path(project_dir, "qa_report"), report)
    project["qa_report"] = report
    project["sprite_model"] = sprite_model
    project["current_stage"] = "qa"
    project["status"] = "qa_%s" % report["status"]
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Checks complete", "QA finished. Export stays blocked until every required check passes.")
    return report


def validate_export_bundle(
    export_dir: Path,
    ordered_frames: List[Tuple[str, str, Path]],
    atlas_frames: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    spritesheet_path = export_dir / "spritesheet.png"
    spritesheet = Image.open(spritesheet_path).convert("RGBA")
    expected_order = [frame_name for _, frame_name, _ in ordered_frames]
    atlas_order = list(atlas_frames.keys())
    crop_checks = []
    for animation_name, frame_name, path in ordered_frames:
        atlas = atlas_frames[frame_name]
        crop = spritesheet.crop((atlas["x"], atlas["y"], atlas["x"] + atlas["w"], atlas["y"] + atlas["h"]))
        source = Image.open(path).convert("RGBA")
        crop_checks.append({
            "frame_name": frame_name,
            "animation": animation_name,
            "matches_source": list(crop.getdata()) == list(source.getdata()),
        })
    status = "pass" if (
        list(spritesheet.size) == [FRAME_SIZE * len(ordered_frames), FRAME_SIZE]
        and atlas_order == expected_order
        and all(item["matches_source"] for item in crop_checks)
    ) else "fail"
    return {
        "status": status,
        "checks": {
            "spritesheet_dimensions": list(spritesheet.size) == [FRAME_SIZE * len(ordered_frames), FRAME_SIZE],
            "atlas_order_matches_frames": atlas_order == expected_order,
            "packed_pixels_match_sources": all(item["matches_source"] for item in crop_checks),
        },
        "atlas_order": atlas_order,
        "expected_order": expected_order,
        "per_frame": crop_checks,
    }


def export_pixellab_project(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    char_path = _pixellab_character_path(project_dir)
    pix_anim_path = _pixellab_animations_path(project_dir)
    if not char_path.exists() or not pix_anim_path.exists():
        raise ValueError("Export blocked: Pixel Lab canonical inputs missing.")

    if not project.get("qa_report") or project["qa_report"].get("status") != "pass":
        raise ValueError("Export blocked: QA must pass first.")

    clips = project.get("animation_clips") or load_json(canonical_downstream_path(project_dir, "animation_clips"), {})
    if not isinstance(clips, dict) or not clips:
        raise ValueError("Export blocked: animation_clips.json must exist for Pixel Lab export.")

    # Only procedural idle/walk for runtime export right now; manual clips still use deterministic render outputs.
    procedural_names = [
        name
        for name in ["idle", "walk"]
        if name in clips and isinstance(clips.get(name), dict) and isinstance(clips[name].get("frames"), list)
    ]
    if not procedural_names and not bool(approved_manual_animation_clips(project).keys()):
        raise ValueError("Export blocked: no Pixel Lab/procedural frames available.")

    manual_clips = approved_manual_animation_clips(project)

    export_dir = project_dir / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_dir.mkdir(parents=True, exist_ok=True)
    ordered_frames: List[Tuple[str, str, Path]] = []

    target_dir = export_dir / "frames"
    target_dir.mkdir(parents=True, exist_ok=True)

    call_progress(progress, 8, "Preparing Pixel Lab export", "Collecting Pixel Lab frames and runtime metadata.")

    for clip_name in procedural_names:
        clip = clips[clip_name]
        frame_count = int(clip.get("frame_count") or 0)
        fps = int(clip.get("fps") or 12)
        loop = bool(clip.get("loop", True))
        frames = clip.get("frames") if isinstance(clip.get("frames"), list) else []
        if frame_count and len(frames) < frame_count:
            raise ValueError("Export blocked: Pixel Lab %s frames missing (have %d need %d)." % (clip_name, len(frames), frame_count))
        if not frame_count:
            frame_count = len(frames)
        for index in range(frame_count):
            source_rel = frames[index] if index < len(frames) else None
            if not source_rel:
                raise ValueError("Export blocked: missing frame path for %s index %d." % (clip_name, index))
            source = project_dir / str(source_rel)
            if not source.exists():
                raise ValueError("Export blocked: missing frame file %s." % source)
            frame_name = "%s_%02d.png" % (clip_name, index)
            target = target_dir / frame_name
            img = Image.open(source).convert("RGBA")
            if list(img.size) != [FRAME_SIZE, FRAME_SIZE]:
                img, _ = cleanup_frame(img)
            img.save(target)
            ordered_frames.append((clip_name, frame_name, target))

    for clip_id, clip in manual_clips.items():
        frame_count = int(clip.get("frame_count") or 0)
        if not frame_count:
            continue
        source_root = project_dir / str(clip.get("preview_render", {}).get("frame_dir") or "")
        if not source_root.exists():
            raise ValueError("Export blocked: missing manual clip frame_dir for %s." % clip_id)
        for index in range(frame_count):
            source = source_root / ("%s_%02d.png" % (clip_id, index))
            if not source.exists():
                raise ValueError("Export blocked: missing manual frame %s." % source.name)
            frame_name = "%s_%02d.png" % (clip_id, index)
            target = target_dir / frame_name
            target.write_bytes(source.read_bytes())
            ordered_frames.append((clip_id, frame_name, target))

    call_progress(progress, 40, "Packing spritesheet", "Packing frame images into a deterministic atlas.")
    spritesheet = Image.new("RGBA", (FRAME_SIZE * len(ordered_frames), FRAME_SIZE), (0, 0, 0, 0))
    atlas_frames: Dict[str, Dict[str, Any]] = {}
    for index, (animation_name, frame_name, path) in enumerate(ordered_frames):
        frame_image = Image.open(path).convert("RGBA")
        x = index * FRAME_SIZE
        spritesheet.alpha_composite(frame_image, (x, 0))
        atlas_frames[frame_name] = {"x": x, "y": 0, "w": FRAME_SIZE, "h": FRAME_SIZE, "pivot": list(FRAME_PIVOT), "animation": animation_name}
    spritesheet.save(export_dir / "spritesheet.png")

    animations_payload: Dict[str, Any] = {}
    for name in procedural_names:
        clip = clips[name]
        frame_count = int(clip.get("frame_count") or 0)
        animations_payload[name] = {
            "fps": int(clip.get("fps") or 12),
            "loop": bool(clip.get("loop", True)),
            "frame_count": frame_count,
            "frames": ["%s_%02d.png" % (name, index) for index in range(frame_count)],
            "root_motion_policy": clip.get("root_motion_policy") or clip_root_motion_policy(name),
        }
    for clip_id, clip in manual_clips.items():
        animations_payload[clip_id] = {
            "fps": int(clip.get("fps") or 12),
            "loop": bool(clip.get("loop", True)),
            "frame_count": int(clip.get("frame_count") or 0),
            "frames": ["%s_%02d.png" % (clip_id, index) for index in range(int(clip.get("frame_count") or 0))],
            "root_motion_policy": "manual",
        }

    write_json(export_dir / "atlas.json", {"image": "spritesheet.png", "frames": atlas_frames})
    write_json(export_dir / "animations.json", animations_payload)
    write_json(export_dir / "qa_report.json", project["qa_report"])

    call_progress(progress, 72, "Building preview", "Creating an animated preview from the exported Pixel Lab frames.")
    preview_frames = [Image.open(path).convert("RGBA") for _, _, path in ordered_frames]
    durations: List[int] = []
    for animation_name, _, _ in ordered_frames:
        if animation_name in clips:
            durations.append(int(1000 / int(clips[animation_name].get("fps") or 12)))
        elif animation_name in manual_clips:
            durations.append(int(1000 / max(1, int(manual_clips[animation_name].get("fps") or 12))))
        else:
            durations.append(100)

    preview_frames[0].save(
        export_dir / "preview.gif",
        save_all=True,
        append_images=preview_frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        transparency=0,
    )

    char_data = load_json(char_path, {}) or {}
    pix_store = load_json(pix_anim_path, None) or {}
    pix_animations = pix_store.get("animations") if isinstance(pix_store, dict) else {}
    pix_job_ids: Dict[str, Any] = {}
    if isinstance(pix_animations, dict):
        for anim_name, anim in pix_animations.items():
            if isinstance(anim, dict):
                pix_job_ids[anim_name] = anim.get("latest_job_id")

    export_manifest: Dict[str, Any] = {
        "project_id": project_id,
        "export_timestamp": now_iso(),
        "tool_version": TOOL_VERSION,
        "export_mode": "pixellab",
        "pixellab_character_id": char_data.get("character_id"),
        "pixellab_latest_job_ids": pix_job_ids,
        "source_asset_hashes": project["qa_report"]["source_asset_hashes"],
        "approved_manual_clips": [
            {"clip_id": clip_id, "clip_name": clip.get("clip_name"), "frame_count": clip.get("frame_count"), "fps": clip.get("fps")}
            for clip_id, clip in manual_clips.items()
        ],
    }

    export_manifest["bundle_hashes"] = {
        "atlas.json": image_sha256(export_dir / "atlas.json"),
        "animations.json": image_sha256(export_dir / "animations.json"),
        "qa_report.json": image_sha256(export_dir / "qa_report.json"),
        "spritesheet.png": image_sha256(export_dir / "spritesheet.png"),
        "preview.gif": image_sha256(export_dir / "preview.gif"),
    }

    call_progress(progress, 76, "Verifying export", "Validating packed spritesheet matches sources.")
    export_manifest["verification"] = validate_export_bundle(export_dir, ordered_frames, atlas_frames)
    write_json(export_dir / "export_manifest.json", export_manifest)

    verification = export_manifest["verification"]
    if verification.get("status") != "pass":
        raise ValueError("Export verification failed: packed spritesheet did not match the frame manifest.")

    result = {
        "export_dir": str(export_dir.relative_to(project_dir)),
        "verification": verification,
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
    project["status"] = "export_ready"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Export ready", "The Pixel Lab sprite package is ready.")
    return result


def export_project(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("qa_report") or project["qa_report"]["status"] != "pass":
        raise ValueError("Export blocked: QA must pass first.")
    ai_workflow = project.get("ai_workflow") or {}
    if project.get("qa_report", {}).get("mode") == "ai_workflow" and ai_workflow_ready_for_qa(ai_workflow):
        project_dir = PROJECTS_ROOT / project_id
        export_dir = project_dir / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        export_dir.mkdir(parents=True, exist_ok=True)
        ordered_frames: List[Tuple[str, str, Path]] = []
        call_progress(progress, 8, "Preparing AI export", "Collecting cleaned AI workflow frames for atlas packing.")
        for clip_name, spec in AI_CLIP_SPECS.items():
            source_root = project_dir / "animations" / clip_name
            for index in range(spec["frame_count"]):
                source = source_root / ("%s_%02d.png" % (clip_name, index))
                if not source.exists():
                    raise ValueError("Export blocked: missing cleaned frame %s." % source.name)
                target_dir = export_dir / "frames"
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / source.name
                target.write_bytes(source.read_bytes())
                ordered_frames.append((clip_name, source.name, target))
        call_progress(progress, 40, "Packing AI spritesheet", "Packing cleaned AI frames into the runtime atlas.")
        spritesheet = Image.new("RGBA", (FRAME_SIZE * len(ordered_frames), FRAME_SIZE), (0, 0, 0, 0))
        atlas_frames = {}
        for index, (animation_name, frame_name, path) in enumerate(ordered_frames):
            frame_image = Image.open(path).convert("RGBA")
            x = index * FRAME_SIZE
            spritesheet.alpha_composite(frame_image, (x, 0))
            atlas_frames[frame_name] = {"x": x, "y": 0, "w": FRAME_SIZE, "h": FRAME_SIZE, "pivot": list(FRAME_PIVOT), "animation": animation_name}
        spritesheet.save(export_dir / "spritesheet.png")
        animations_payload = {
            clip_name: {
                "fps": spec["fps"],
                "loop": True,
                "frame_count": spec["frame_count"],
                "frames": ["%s_%02d.png" % (clip_name, index) for index in range(spec["frame_count"])],
                "root_motion_policy": AI_WORKFLOW_PROFILE,
            }
            for clip_name, spec in AI_CLIP_SPECS.items()
        }
        write_json(export_dir / "atlas.json", {"image": "spritesheet.png", "frames": atlas_frames})
        write_json(export_dir / "animations.json", animations_payload)
        write_json(export_dir / "qa_report.json", project["qa_report"])
        call_progress(progress, 72, "Building AI preview", "Creating a preview GIF from the cleaned AI workflow frames.")
        preview_frames = [Image.open(path).convert("RGBA") for _, _, path in ordered_frames]
        durations = [int(1000 / AI_CLIP_SPECS[name]["fps"]) for name, _, _ in ordered_frames]
        preview_frames[0].save(
            export_dir / "preview.gif",
            save_all=True,
            append_images=preview_frames[1:],
            duration=durations,
            loop=0,
            disposal=2,
            transparency=0,
        )
        workflow_manifest = {
            "profile": ai_workflow.get("profile") or AI_WORKFLOW_PROFILE,
            "character_lock_run_id": (ai_workflow.get("character_lock") or {}).get("approved_run_id"),
            "character_lock_asset_id": (ai_workflow.get("character_lock") or {}).get("approved_asset_id"),
            "key_pose_run_id": (ai_workflow.get("key_pose_set") or {}).get("approved_run_id"),
            "motion_run_ids": (ai_workflow.get("selected_assets") or {}).get("motion_run_ids") or {},
            "extract_run_ids": (ai_workflow.get("selected_assets") or {}).get("extract_run_ids") or {},
            "cleanup_run_ids": (ai_workflow.get("selected_assets") or {}).get("cleanup_run_ids") or {},
            "dependency_health_snapshot": ai_workflow.get("dependency_status") or {},
            "model_versions": {
                "comfyui": "runtime-health-only",
                "photomaker": "configured-via-environment",
                "ipadapter_plus": "configured-via-environment",
                "tooncrafter": "configured-via-environment",
                "anime_segmentation": "configured-via-environment",
                "pixelart_cleanup": "configured-via-environment",
            },
        }
        export_manifest = {
            "project_id": project_id,
            "approved_concept_id": (project.get("character_spec") or {}).get("approved_concept_id"),
            "approved_master_pose": None,
            "approved_source_image": (project.get("character_spec") or {}).get("approved_source_image"),
            "export_timestamp": now_iso(),
            "tool_version": TOOL_VERSION,
            "workflow_profile": ai_workflow.get("profile") or AI_WORKFLOW_PROFILE,
            "source_asset_hashes": project["qa_report"]["source_asset_hashes"],
            "workflow": workflow_manifest,
        }
        write_json(export_dir / "export_manifest.json", export_manifest)
        verification = validate_export_bundle(export_dir, ordered_frames, atlas_frames)
        project["last_export"] = {
            "export_dir": str(export_dir.relative_to(project_dir)),
            "spritesheet": "spritesheet.png",
            "atlas": "atlas.json",
            "animations": "animations.json",
            "preview_gif": "preview.gif",
            "export_manifest": "export_manifest.json",
            "generated_at": now_iso(),
            "mode": "ai_workflow",
            "verification": verification,
            "files": ["spritesheet.png", "atlas.json", "animations.json", "preview.gif", "export_manifest.json", "qa_report.json"],
        }
        project["current_stage"] = "export"
        project["status"] = "export_complete"
        project["updated_at"] = now_iso()
        save_project(project)
        call_progress(progress, 100, "AI export ready", "AI workflow frames were packaged into the runtime atlas/export bundle.")
        return project["last_export"]
    external_authoring = project.get("external_authoring") or {}
    imported_bundle = external_authoring.get("imported_bundle") if isinstance(external_authoring.get("imported_bundle"), dict) else None
    project_dir = PROJECTS_ROOT / project_id
    pix_char_exists = _pixellab_character_path(project_dir).exists()
    pix_anim_exists = _pixellab_animations_path(project_dir).exists()
    if not project.get("sprite_model") and not (external_authoring.get("enabled") and imported_bundle) and not (pix_char_exists and pix_anim_exists):
        raise ValueError("Export blocked: sprite model is missing.")
    if external_authoring.get("enabled") and imported_bundle:
        export_dir = project_dir / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        export_dir.mkdir(parents=True, exist_ok=True)
        call_progress(progress, 12, "Preparing external export", "Copying imported SkelForm assets into the standard export bundle.")
        spritesheet_source = project_dir / str(imported_bundle.get("spritesheet_image_path") or "")
        atlas_source = project_dir / str(imported_bundle.get("atlas_path") or "")
        animations_source = project_dir / str(imported_bundle.get("animations_path") or "")
        preview_source = project_dir / str(imported_bundle.get("preview_gif_path") or "") if imported_bundle.get("preview_gif_path") else None
        for source, target_name in [
            (spritesheet_source, "spritesheet.png"),
            (atlas_source, "atlas.json"),
            (animations_source, "animations.json"),
        ]:
            if not source.exists():
                raise ValueError("Export blocked: missing imported bundle asset %s." % source)
            (export_dir / target_name).write_bytes(source.read_bytes())
        write_json(export_dir / "qa_report.json", project["qa_report"])
        if preview_source and preview_source.exists():
            (export_dir / "preview.gif").write_bytes(preview_source.read_bytes())
        export_manifest = {
            "project_id": project_id,
            "approved_concept_id": (project.get("character_spec") or {}).get("approved_concept_id"),
            "approved_master_pose": None,
            "approved_source_image": (project.get("sprite_model") or {}).get("approved_source_image"),
            "export_timestamp": now_iso(),
            "tool_version": TOOL_VERSION,
            "export_mode": "external_authoring",
            "external_authoring_provider": external_authoring.get("provider"),
            "external_bundle": {
                "bundle_id": imported_bundle.get("bundle_id"),
                "animation_names": imported_bundle.get("animation_names") or [],
                "frame_count": imported_bundle.get("frame_count"),
                "source_label": imported_bundle.get("source_label"),
            },
            "source_asset_hashes": project["qa_report"]["source_asset_hashes"],
        }
        write_json(export_dir / "export_manifest.json", export_manifest)
        project["last_export"] = {
            "export_dir": str(export_dir.relative_to(project_dir)),
            "spritesheet": "spritesheet.png",
            "atlas": "atlas.json",
            "animations": "animations.json",
            "preview_gif": "preview.gif" if preview_source and preview_source.exists() else None,
            "export_manifest": "export_manifest.json",
            "generated_at": now_iso(),
            "mode": "external_authoring",
        }
        project["current_stage"] = "export"
        project["status"] = "export_complete"
        project["updated_at"] = now_iso()
        save_project(project)
        call_progress(progress, 100, "External export ready", "Imported SkelForm assets were packaged into the standard export directory.")
        return {
            "export_dir": str(export_dir.relative_to(project_dir)),
            "spritesheet": "spritesheet.png",
            "atlas": "atlas.json",
            "animations": "animations.json",
            "preview_gif": "preview.gif" if preview_source and preview_source.exists() else None,
            "export_manifest": "export_manifest.json",
            "mode": "external_authoring",
        }
    # Phase 6: Pixel Lab export path (no sprite_model/rig dependency).
    if pix_char_exists and pix_anim_exists:
        return export_pixellab_project(project_id, progress=progress)
    clips = project.get("animation_clips") or load_json(canonical_downstream_path(project_dir, "animation_clips"), {})
    manual_clips = approved_manual_animation_clips(project)
    export_dir = project_dir / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_dir.mkdir(parents=True, exist_ok=True)
    ordered_frames = []
    call_progress(progress, 8, "Preparing export", "Collecting deterministic clip frames and runtime metadata.")
    runtime_exports: List[Tuple[str, int, Path]] = [
        (animation_name, ANIMATION_SPECS[animation_name]["frame_count"], project_dir / "animations" / animation_name)
        for animation_name in ["idle", "walk"]
    ] + [
        (clip_id, int(clip.get("frame_count") or 0), project_dir / str(clip.get("preview_render", {}).get("frame_dir") or ""))
        for clip_id, clip in manual_clips.items()
    ]
    for animation_name, frame_count, source_root in runtime_exports:
        for index in range(frame_count):
            source = source_root / ("%s_%02d.png" % (animation_name, index))
            target_dir = export_dir / "frames"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / source.name
            target.write_bytes(source.read_bytes())
            ordered_frames.append((animation_name, source.name, target))

    call_progress(progress, 40, "Packing spritesheet", "Packing frame images into a deterministic atlas.")
    spritesheet = Image.new("RGBA", (FRAME_SIZE * len(ordered_frames), FRAME_SIZE), (0, 0, 0, 0))
    atlas_frames = {}
    for index, (animation_name, frame_name, path) in enumerate(ordered_frames):
        frame_image = Image.open(path).convert("RGBA")
        x = index * FRAME_SIZE
        spritesheet.alpha_composite(frame_image, (x, 0))
        atlas_frames[frame_name] = {"x": x, "y": 0, "w": FRAME_SIZE, "h": FRAME_SIZE, "pivot": list(FRAME_PIVOT), "animation": animation_name}
    spritesheet.save(export_dir / "spritesheet.png")

    animations_payload = {
        name: {
            "fps": clips[name]["fps"],
            "loop": clips[name]["loop"],
            "frame_count": clips[name]["frame_count"],
            "frames": ["%s_%02d.png" % (name, index) for index in range(clips[name]["frame_count"])],
            "root_motion_policy": clips[name]["root_motion_policy"],
        }
        for name in ["idle", "walk"]
    }
    for clip_id, clip in manual_clips.items():
        animations_payload[clip_id] = {
            "fps": int(clip.get("fps") or 12),
            "loop": bool(clip.get("loop", True)),
            "frame_count": int(clip.get("frame_count") or 0),
            "frames": ["%s_%02d.png" % (clip_id, index) for index in range(int(clip.get("frame_count") or 0))],
            "root_motion_policy": "manual",
        }
    export_manifest = {
        "project_id": project_id,
        "approved_concept_id": project["character_spec"]["approved_concept_id"],
        "approved_master_pose": project.get("sprite_model", {}).get("approved_master_pose"),
        "approved_source_image": project.get("sprite_model", {}).get("approved_source_image"),
        "export_timestamp": now_iso(),
        "tool_version": TOOL_VERSION,
        "sprite_model_hash": hashlib.sha256(canonical_downstream_path(project_dir, "sprite_model").read_bytes()).hexdigest(),
        "rig_hash": hashlib.sha256(canonical_downstream_path(project_dir, "rig").read_bytes()).hexdigest(),
        "source_asset_hashes": project["qa_report"]["source_asset_hashes"],
        "approved_manual_clips": [
            {"clip_id": clip_id, "clip_name": clip.get("clip_name"), "frame_count": clip.get("frame_count"), "fps": clip.get("fps")}
            for clip_id, clip in manual_clips.items()
        ],
    }
    write_json(export_dir / "atlas.json", {"image": "spritesheet.png", "frames": atlas_frames})
    write_json(export_dir / "animations.json", animations_payload)
    write_json(export_dir / "qa_report.json", project["qa_report"])

    call_progress(progress, 72, "Building preview", "Creating an animated preview from the exported frames.")
    preview_frames = [Image.open(path).convert("RGBA") for _, _, path in ordered_frames]
    durations = []
    for animation_name, _, _ in ordered_frames:
        if animation_name in clips:
            durations.append(int(1000 / clips[animation_name]["fps"]))
        elif animation_name in manual_clips:
            durations.append(int(1000 / max(1, int(manual_clips[animation_name].get("fps") or 12))))
        else:
            durations.append(100)
    preview_frames[0].save(
        export_dir / "preview.gif",
        save_all=True,
        append_images=preview_frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        transparency=0,
    )
    export_manifest["bundle_hashes"] = {
        "atlas.json": image_sha256(export_dir / "atlas.json"),
        "animations.json": image_sha256(export_dir / "animations.json"),
        "qa_report.json": image_sha256(export_dir / "qa_report.json"),
        "spritesheet.png": image_sha256(export_dir / "spritesheet.png"),
        "preview.gif": image_sha256(export_dir / "preview.gif"),
    }
    export_manifest["verification"] = validate_export_bundle(export_dir, ordered_frames, atlas_frames)
    if export_manifest["verification"]["status"] != "pass":
        raise ValueError("Export verification failed: packed spritesheet did not match the frame manifest.")
    write_json(export_dir / "export_manifest.json", export_manifest)

    result = {
        "export_dir": str(export_dir.relative_to(project_dir)),
        "verification": export_manifest["verification"],
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
    project["status"] = "export_ready"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Export ready", "The deterministic sprite package is ready.")
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
    start_time = time.monotonic()

    if run_kind == "initial":
        base_concept = None
        refine_source = None
        concept_count = INITIAL_CONCEPT_COUNT
    else:
        base_concept = next(item for item in project["concepts"] if item["concept_id"] == source_concept_id)
        refine_source = project_dir / base_concept["preview_image"]
        concept_count = REFINEMENT_CONCEPT_COUNT

    def generate_records_for_attempt(rescue_mode: bool) -> List[Dict[str, Any]]:
        generated_records: List[Dict[str, Any]] = []
        for index, variation_axes in enumerate(variation_axes_list[:concept_count]):
            call_progress(
                progress,
                12 + int((index / max(1, concept_count)) * 72),
                "Generating look %d of %d" % (index + 1, concept_count),
                variation_axes.get("summary"),
            )
            concept_id = "concept-%04d" % (serial + index)
            output_path = project_dir / "concepts" / ("%s.png" % concept_id)
            positive_prompt, negative_prompt = build_prompt_bundle(project["brief"], variation_axes, base_concept, rescue_mode=rescue_mode)
            seed = stable_int(project_id, run_id, concept_id, positive_prompt, "rescue" if rescue_mode else "base", mod=4_294_967_295)
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
        return generated_records

    generated_records = generate_records_for_attempt(False)
    call_progress(progress, 88, "Reviewing generated looks", "Running lightweight triage and saving concept metadata.")
    annotate_run_triage(project_dir, generated_records)
    triage_summary = summarize_run_triage(generated_records)
    rescue_attempted = False
    quality_gate_failed = False
    usable_count = triage_summary.get("ok", 0) + triage_summary.get("warning", 0)
    if run_kind == "initial" and usable_count < 2:
        rescue_attempted = True
        call_progress(progress, 90, "Board quality too low", "Retrying with stricter single-character framing rules.")
        generated_records = generate_records_for_attempt(True)
        annotate_run_triage(project_dir, generated_records)
        triage_summary = summarize_run_triage(generated_records)
        usable_count = triage_summary.get("ok", 0) + triage_summary.get("warning", 0)
        quality_gate_failed = usable_count < 2

    for concept in generated_records:
        concepts.append(concept)
        save_concept(project_dir, concept)

    summary = {
        "type": "concept_run",
        "run_id": run_id,
        "run_kind": run_kind,
        "status": "quality_failed" if quality_gate_failed else "completed",
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
        "summary": "Concept board failed quality gate; generated outputs were kept for inspection only." if quality_gate_failed else "%s run with %d concepts" % (run_kind, len(generated_records)),
        "rescue_attempted": rescue_attempted,
        "quality_gate_failed": quality_gate_failed,
        "duration_ms": int((time.monotonic() - start_time) * 1000),
    }
    history = append_history_event(project_id, summary)
    project["history"] = history
    project["concepts"] = concepts
    project["current_stage"] = "concepts" if run_kind == "initial" else "refine"
    project["status"] = "concepts_quality_failed" if quality_gate_failed else ("concepts_generated" if run_kind == "initial" else "concepts_refined")
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(
        progress,
        100,
        "Looks ready" if not quality_gate_failed else "Board needs attention",
        "The concept board has been updated." if not quality_gate_failed else "No usable concepts passed triage. Adjust the brief or checkpoint, then regenerate.",
    )
    return {
        "run_id": run_id,
        "run_kind": run_kind,
        "concept_ids": [item["concept_id"] for item in generated_records],
        "triage": triage_summary,
        "rescue_attempted": rescue_attempted,
        "quality_gate_failed": quality_gate_failed,
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


API_PATH_PREFIX = "/tools/2d-sprite-and-animation"


def _normalize_api_path(path: str) -> str:
    """Strip tool path prefix so /tools/2d-sprite-and-animation/api/... matches API routes."""
    if path.startswith(API_PATH_PREFIX):
        path = path[len(API_PATH_PREFIX) :] or "/"
    return path


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
        path = _normalize_api_path(unquote(parsed.path))
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

        if path == "/api/pixellab/health":
            configured = pixellab_configured()
            client = get_pixellab_client()
            balance = None
            credits_remaining = None
            usage = None
            error = None

            if client:
                try:
                    balance = client.get_balance()
                    usage = client.last_usage
                    if isinstance(balance, dict):
                        # The API has historically returned USD balance.
                        credits_remaining = (
                            balance.get("remaining_credits")
                            or balance.get("credits_remaining")
                            or balance.get("usd")
                            or balance.get("credits")
                        )
                except Exception as exc:
                    error = str(exc)
                    usage = client.last_usage

            return self._send_json({
                "ok": True,
                "configured": configured,
                "balance": balance,
                "credits_remaining": credits_remaining,
                "usage": usage,
                "error": error,
            })

        if path == "/api/ai-workflow/health":
            return self._send_json(ai_workflow_health_snapshot())

        if path == "/api/projects":
            include_archived = query.get("include_archived", ["0"])[0] in {"1", "true", "yes"}
            return self._send_json({"projects": [project_summary(item) for item in list_projects(include_archived)]})

        project_match = re.fullmatch(r"/api/projects/([^/]+)", path)
        if project_match:
            try:
                return self._send_json(load_project(project_match.group(1)))
            except FileNotFoundError:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")

        rig_layout_match = re.fullmatch(r"/api/projects/([^/]+)/rig-layout", path)
        if rig_layout_match:
            try:
                return self._send_json(get_rig_layout(rig_layout_match.group(1)))
            except FileNotFoundError:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")

        part_manifest_match = re.fullmatch(r"/api/projects/([^/]+)/part-manifest", path)
        if part_manifest_match:
            try:
                return self._send_json(get_part_manifest(part_manifest_match.group(1)))
            except FileNotFoundError:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")

        part_shapes_match = re.fullmatch(r"/api/projects/([^/]+)/part-shapes", path)
        if part_shapes_match:
            try:
                return self._send_json(get_part_shapes(part_shapes_match.group(1)))
            except FileNotFoundError:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")

        part_split_match = re.fullmatch(r"/api/projects/([^/]+)/part-split", path)
        if part_split_match:
            try:
                return self._send_json(get_part_split(part_split_match.group(1)))
            except FileNotFoundError:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")

        manual_clips_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips", path)
        if manual_clips_match:
            try:
                return self._send_json(get_manual_animation_clips(manual_clips_match.group(1)))
            except FileNotFoundError:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")

        external_authoring_match = re.fullmatch(r"/api/projects/([^/]+)/external-authoring", path)
        if external_authoring_match:
            try:
                return self._send_json(get_external_authoring(external_authoring_match.group(1)))
            except FileNotFoundError:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")

        ai_workflow_match = re.fullmatch(r"/api/projects/([^/]+)/ai-workflow", path)
        if ai_workflow_match:
            try:
                return self._send_json(get_ai_workflow(ai_workflow_match.group(1)))
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

        if path.startswith("/api/"):
            return self._send_error_json(HTTPStatus.NOT_FOUND, "Unknown API route (GET): %s" % path)
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = _normalize_api_path(unquote(parsed.path))
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
                return self._send_json(generate_initial_prompt(project_id), status=HTTPStatus.CREATED)

            build_prompt_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/build-prompt", path)
            if build_prompt_match:
                project_id = build_prompt_match.group(1)
                project = load_project(project_id)
                scaffold = build_concept_prompt(project.get("brief") or {})
                return self._send_json(scaffold, status=HTTPStatus.OK)

            persist_scaffold_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/persist-scaffold-prompt", path)
            if persist_scaffold_match:
                project_id = persist_scaffold_match.group(1)
                project = load_project(project_id)
                scaffold = build_concept_prompt(project.get("brief") or {})
                row = create_prompt_attempt(project, scaffold["display_prompt"], "pixel_lab_scaffold")
                out = dict(scaffold)
                out["anchor_concept_id"] = row["concept_id"]
                return self._send_json(out, status=HTTPStatus.CREATED)

            build_iteration_prompt_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/build-iteration-prompt", path)
            if build_iteration_prompt_match:
                project_id = build_iteration_prompt_match.group(1)
                payload = read_body(self)
                concept_id = payload.get("concept_id")
                element = payload.get("element")
                change_text = payload.get("change_text")
                if not concept_id:
                    raise ValueError("build-iteration-prompt requires concept_id.")
                if not element:
                    raise ValueError("build-iteration-prompt requires element.")
                if not change_text:
                    raise ValueError("build-iteration-prompt requires change_text.")

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                concept = next((item for item in (project.get("concepts") or []) if item.get("concept_id") == concept_id), None)
                if concept is None:
                    raise ValueError("Concept not found: %s" % str(concept_id))

                source_rel = concept.get("original_preview_image") or concept.get("preview_image") or concept.get("image_path")
                if not source_rel:
                    raise ValueError("Concept does not have a preview image path (expected preview_image/original_preview_image/image_path).")

                source_path = Path(source_rel)
                if not source_path.is_absolute():
                    source_path = project_dir / source_rel

                scaffold = build_iteration_prompt(
                    project.get("brief") or {},
                    element,
                    change_text,
                    source_concept_path=source_path,
                )
                return self._send_json(scaffold, status=HTTPStatus.OK)

            generate_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/generate-pixellab", path)
            if generate_pixellab_match:
                project_id = generate_pixellab_match.group(1)
                payload = read_body(self)
                pixellab_params = payload.get("pixellab_params") or {}
                mode = (payload.get("mode") or "v2").strip().lower()

                if not isinstance(pixellab_params, dict):
                    raise ValueError("generate-pixellab requires pixellab_params object.")
                if not pixellab_params.get("description"):
                    raise ValueError("pixellab_params.description is required.")
                if not pixellab_params.get("image_size"):
                    raise ValueError("pixellab_params.image_size is required.")

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                serial = next_concept_serial(project["concepts"])
                concept_id = "concept-%04d" % serial
                output_path = project_dir / "concepts" / ("%s.png" % concept_id)

                backend_mode = str((project.get("brief") or {}).get("backend_mode") or "comfyui")
                seed = pixellab_params.get("seed")

                used_backend = "debug_procedural" if backend_mode == "debug_procedural" else "pixellab"
                backend_run_id = None

                if backend_mode == "debug_procedural" or not pixellab_configured():
                    image = debug_pixellab_concept_image(pixellab_params["image_size"], seed, label="gen")
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(output_path)
                    backend_run_id = "debug"
                else:
                    client = get_pixellab_client()
                    if client is None:
                        raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                    desc = pixellab_params["description"]
                    image_size = pixellab_params["image_size"]
                    no_background = bool(pixellab_params.get("no_background", True))

                    # Prefer v2 for best quality, but keep pixflux as a fallback.
                    last_exc: Optional[str] = None
                    for attempt in ([mode] + (["pixflux"] if mode != "pixflux" else [])):
                        try:
                            if attempt == "v2":
                                result = client.create_image_v2(
                                    desc,
                                    image_size,
                                    no_background=no_background,
                                    seed=seed,
                                )
                            else:
                                result = client.create_image_pixflux(
                                    desc,
                                    image_size,
                                    no_background=no_background,
                                    outline=pixellab_params.get("outline"),
                                    shading=pixellab_params.get("shading"),
                                    detail=pixellab_params.get("detail"),
                                    view=pixellab_params.get("view"),
                                    direction=pixellab_params.get("direction"),
                                    seed=seed,
                                )

                            backend_run_id = result.get("job_id") or result.get("id")
                            b64 = _find_first_base64_png_like(result)
                            if not b64:
                                raise ValueError("Pixel Lab result did not contain extractable base64 image.")
                            image = _decode_base64_image_to_rgba(b64)
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            image.save(output_path)
                            used_backend = "pixellab"
                            backend_run_id = backend_run_id or "pixellab"
                            last_exc = None
                            break
                        except Exception as exc:
                            last_exc = str(exc)
                            continue

                    if last_exc is not None:
                        raise ValueError("generate-pixellab failed: %s" % last_exc)

                concept = hydrate_concept({
                    "concept_id": concept_id,
                    "run_id": stable_hash("pixellab-generate", project_id, concept_id, str(seed or ""))[:12],
                    "run_kind": "pixellab_generate",
                    "created_at": now_iso(),
                    "positive_prompt": pixellab_params["description"],
                    "prompt": pixellab_params["description"],
                    "prompt_text": pixellab_params["description"],
                    "prompt_version": 0,
                    "prompt_source": "scaffold",
                    "attempt_group_id": stable_hash("pixellab-group", project_id, str(seed or ""))[:12],
                    "attempt_index": 0,
                    "import_source": None,
                    "validation_status": "valid",
                    "validation_source": "pixel_lab_scaffold",
                    "validation_feedback": None,
                    "accepted_for_review": False,
                    "preview_image": str(output_path.relative_to(project_dir)),
                    "original_preview_image": str(output_path.relative_to(project_dir)),
                    "backend_name": used_backend,
                    "backend_run_id": backend_run_id,
                    "difference_summary": "Pixel Lab generated concept (%s)" % mode,
                    "silhouette": project["brief"]["silhouette_intent"],
                    "outfit": project["brief"]["outfit_materials"],
                    "palette_direction": project["brief"]["palette_mood"],
                    "palette": palette_from_seed(serial, 0, project["brief"]["palette_mood"]),
                    "prop_variant": project["brief"]["prop"],
                    "face_head_shape": project["brief"]["shape_language"],
                    "references_used": [],
                    "review_state": {"approved": False, "favorite": False, "rejected": False},
                    "lineage": {"run_id": backend_run_id or "pixellab", "parent_concept_id": None},
                })

                # Optional triage (best-effort). Keeps UI triage metrics coherent.
                try:
                    concept["triage"] = analyze_concept_image(output_path)
                except Exception:
                    concept["triage"] = {"status": "not_evaluated", "flags": [], "metrics": {}}

                project["concepts"].append(concept)
                project["updated_at"] = now_iso()
                project["current_stage"] = "concepts"
                project["status"] = "concept_pixellab_generated"
                save_project(project)
                save_concept(project_dir, concept)
                append_history_event(project_id, {
                    "type": "concept_pixellab_generate",
                    "concept_id": concept_id,
                    "mode": mode,
                    "created_at": now_iso(),
                })

                return self._send_json(concept, status=HTTPStatus.CREATED)

            iterate_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/iterate-pixellab", path)
            if iterate_pixellab_match:
                project_id = iterate_pixellab_match.group(1)
                payload = read_body(self)
                source_concept_id = payload.get("concept_id")
                pixellab_params = payload.get("pixellab_params") or {}

                if not source_concept_id:
                    raise ValueError("iterate-pixellab requires concept_id.")
                if not isinstance(pixellab_params, dict):
                    raise ValueError("iterate-pixellab requires pixellab_params object.")
                if not pixellab_params.get("description"):
                    raise ValueError("pixellab_params.description is required.")
                if not pixellab_params.get("image_size"):
                    raise ValueError("pixellab_params.image_size is required.")
                if not pixellab_params.get("inpainting_image_b64"):
                    raise ValueError("pixellab_params.inpainting_image_b64 is required.")
                if not pixellab_params.get("mask_image_b64"):
                    raise ValueError("pixellab_params.mask_image_b64 is required.")

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                serial = next_concept_serial(project["concepts"])
                concept_id = "concept-%04d" % serial
                output_path = project_dir / "concepts" / ("%s.png" % concept_id)

                backend_mode = str((project.get("brief") or {}).get("backend_mode") or "comfyui")
                seed = pixellab_params.get("seed")
                used_backend = "debug_procedural" if backend_mode == "debug_procedural" else "pixellab"
                backend_run_id = None

                if backend_mode == "debug_procedural" or not pixellab_configured():
                    image = debug_pixellab_iterate_from_inpainting(
                        pixellab_params["inpainting_image_b64"],
                        seed,
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(output_path)
                    backend_run_id = "debug"
                else:
                    client = get_pixellab_client()
                    if client is None:
                        raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                    result = client.inpaint_v3(
                        pixellab_params["description"],
                        pixellab_params["inpainting_image_b64"],
                        pixellab_params["mask_image_b64"],
                        pixellab_params["image_size"],
                        no_background=bool(pixellab_params.get("no_background", True)),
                        crop_to_mask=bool(pixellab_params.get("crop_to_mask", True)),
                        seed=seed,
                    )

                    backend_run_id = result.get("job_id") or result.get("id")
                    b64 = _find_first_base64_png_like(result)
                    if not b64:
                        raise ValueError("Pixel Lab result did not contain extractable base64 image.")

                    image = _decode_base64_image_to_rgba(b64)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(output_path)
                    used_backend = "pixellab"
                    backend_run_id = backend_run_id or "pixellab"

                concept = hydrate_concept({
                    "concept_id": concept_id,
                    "run_id": stable_hash("pixellab-iterate", project_id, concept_id, str(seed or ""))[:12],
                    "run_kind": "pixellab_iterate",
                    "created_at": now_iso(),
                    "positive_prompt": pixellab_params["description"],
                    "prompt": pixellab_params["description"],
                    "prompt_text": pixellab_params["description"],
                    "prompt_version": 0,
                    "prompt_source": "scaffold",
                    "attempt_group_id": stable_hash("pixellab-iterate-group", project_id, source_concept_id)[:12],
                    "attempt_index": 0,
                    "import_source": None,
                    "validation_status": "valid",
                    "validation_source": "pixel_lab_scaffold",
                    "validation_feedback": None,
                    "accepted_for_review": False,
                    "preview_image": str(output_path.relative_to(project_dir)),
                    "original_preview_image": str(output_path.relative_to(project_dir)),
                    "backend_name": used_backend,
                    "backend_run_id": backend_run_id,
                    "difference_summary": "Pixel Lab inpaint iteration from %s" % source_concept_id,
                    "silhouette": project["brief"]["silhouette_intent"],
                    "outfit": project["brief"]["outfit_materials"],
                    "palette_direction": project["brief"]["palette_mood"],
                    "palette": palette_from_seed(serial, 0, project["brief"]["palette_mood"]),
                    "prop_variant": project["brief"]["prop"],
                    "face_head_shape": project["brief"]["shape_language"],
                    "references_used": [],
                    "review_state": {"approved": False, "favorite": False, "rejected": False},
                    "lineage": {"run_id": backend_run_id or "pixellab", "parent_concept_id": source_concept_id},
                })

                try:
                    concept["triage"] = analyze_concept_image(output_path)
                except Exception:
                    concept["triage"] = {"status": "not_evaluated", "flags": [], "metrics": {}}

                project["concepts"].append(concept)
                project["updated_at"] = now_iso()
                project["current_stage"] = "concepts"
                project["status"] = "concept_pixellab_iterated"
                save_project(project)
                save_concept(project_dir, concept)
                append_history_event(project_id, {
                    "type": "concept_pixellab_iterate",
                    "concept_id": concept_id,
                    "source_concept_id": source_concept_id,
                    "created_at": now_iso(),
                })

                return self._send_json(concept, status=HTTPStatus.CREATED)

            create_character_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/create-character", path)
            if create_character_pixellab_match:
                project_id = create_character_pixellab_match.group(1)
                payload = read_body(self)

                directions = int(payload.get("directions") or 4)
                if directions not in {4, 8}:
                    raise ValueError("directions must be 4 or 8.")

                color_concept_id = payload.get("color_concept_id") or payload.get("concept_id")
                if not color_concept_id:
                    raise ValueError("create-character requires color_concept_id/concept_id to find the reference image.")

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                canvas_size = coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE)

                concept = next((item for item in (project.get("concepts") or []) if item.get("concept_id") == color_concept_id), None)
                if concept is None:
                    raise ValueError("color_concept_id concept not found.")

                source_rel = concept.get("original_preview_image") or concept.get("preview_image") or concept.get("image_path")
                if not source_rel:
                    raise ValueError("Concept does not have a preview image path.")

                source_path = Path(source_rel)
                if not source_path.is_absolute():
                    source_path = project_dir / source_rel
                if not source_path.exists():
                    raise ValueError("Concept preview image is missing on disk.")

                seed = payload.get("seed")
                try:
                    seed = int(seed) if seed is not None else stable_int(project_id, color_concept_id, str(directions), mod=4_294_967_295)
                except (TypeError, ValueError):
                    seed = stable_int(project_id, color_concept_id, str(directions), mod=4_294_967_295)

                if directions == 4:
                    direction_list = ["south", "west", "east", "north"]
                else:
                    direction_list = [
                        "south",
                        "south-east",
                        "east",
                        "north-east",
                        "north",
                        "north-west",
                        "west",
                        "south-west",
                    ]

                backend_mode = str(brief.get("backend_mode") or "comfyui")
                use_debug = backend_mode == "debug_procedural" or not pixellab_configured()

                if use_debug:
                    images = debug_pixellab_character_images(direction_list, canvas_size, seed)
                    char_id = "debug-char-%s" % stable_hash(project_id, color_concept_id, str(directions))[:10]
                    for d, img in images.items():
                        asset_path = _pixellab_character_assets_dir(project_dir) / ("%s.png" % d)
                        asset_path.parent.mkdir(parents=True, exist_ok=True)
                        img.save(asset_path)

                    char_payload = {
                        "character_id": char_id,
                        "approved": False,
                        "created_at": now_iso(),
                        "directions": direction_list,
                        "image_size": {"width": canvas_size, "height": canvas_size},
                        "source_concept_id": color_concept_id,
                        "backend_name": "debug_procedural",
                        "seed": seed,
                        "images": {d: str((_pixellab_character_assets_dir(project_dir) / ("%s.png" % d)).relative_to(project_dir)) for d in direction_list},
                    }
                    _pixellab_character_path(project_dir).write_text(json.dumps(char_payload, indent=2), encoding="utf-8")
                    project["pixellab_character_approved"] = False
                    project["pixellab_character_ready"] = True
                    project["current_stage"] = "concepts"
                    project["status"] = "pixellab_character_debug_ready"
                    project["updated_at"] = now_iso()
                    save_project(project)
                    append_history_event(project_id, {
                        "type": "pixellab_character_created",
                        "character_id": char_id,
                        "directions": directions,
                        "created_at": now_iso(),
                    })
                    return self._send_json(char_payload, status=HTTPStatus.CREATED)

                client = get_pixellab_client()
                if client is None:
                    raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                # Build a deterministic description for the Pixel Lab character template call.
                style = _brief_pixel_lab_style(brief)
                character_description = "\n".join(
                    [
                        "Create a 2D side-view pixel art character from the supplied concept.",
                        f"Role: {brief.get('role_archetype','')}",
                        f"Silhouette: {brief.get('silhouette_intent','')}",
                        f"Outfit: {brief.get('outfit_materials','')}",
                        f"Held item: {brief.get('prop','')}",
                        f"Palette mood: {brief.get('palette_mood','')}",
                        f"Shape language: {brief.get('shape_language','')}",
                        f"Mood/tone: {brief.get('mood_tone','')}",
                        f"Style outline={style['outline_style_pixel_lab']} shading={style['shading_style_pixel_lab']} detail={style['detail_level_pixel_lab']}.",
                    ]
                )

                try:
                    from scripts.pixellab_client import base64_image_payload

                    color_image = base64_image_payload(client.encode_image(source_path))
                    if directions == 4:
                        result = client.create_character_4dir(
                            character_description,
                            {"width": canvas_size, "height": canvas_size},
                            template_id=style["character_template_pixel_lab"],
                            view="side",
                            color_image=color_image,
                            force_colors=True,
                            seed=seed,
                            poll_timeout_seconds=300,
                        )
                    else:
                        result = client.create_character_8dir(
                            character_description,
                            {"width": canvas_size, "height": canvas_size},
                            template_id=style["character_template_pixel_lab"],
                            view="side",
                            color_image=color_image,
                            force_colors=True,
                            seed=seed,
                            poll_timeout_seconds=420,
                        )
                except Exception as exc:
                    raise ValueError("Pixel Lab create-character failed: %s" % str(exc))

                images_bytes = _extract_pixellab_character_direction_image_bytes(
                    result,
                    direction_list,
                    client=client,
                )
                if len(images_bytes) < len(direction_list):
                    raise ValueError(
                        "Pixel Lab create-character response did not contain enough direction images to map into %s "
                        "(expected per-direction ``images`` or fetchable ``rotation_urls`` via ``character_id``)."
                        % str(direction_list)
                    )

                char_id = result.get("character_id") or result.get("id") or ("pixellab-char-%s" % stable_hash(project_id, seed)[:10])
                assets_dir = _pixellab_character_assets_dir(project_dir)
                assets_dir.mkdir(parents=True, exist_ok=True)
                images_map: Dict[str, str] = {}
                for idx, d in enumerate(direction_list):
                    img = _pixellab_open_image_bytes(
                        images_bytes[idx],
                        where="Pixel Lab direction %s" % d,
                        rgba_size=(canvas_size, canvas_size),
                    )
                    asset_path = assets_dir / ("%s.png" % d)
                    img.save(asset_path)
                    images_map[d] = str(asset_path.relative_to(project_dir))

                char_payload = {
                    "character_id": char_id,
                    "approved": False,
                    "created_at": now_iso(),
                    "directions": direction_list,
                    "image_size": {"width": canvas_size, "height": canvas_size},
                    "source_concept_id": color_concept_id,
                    "backend_name": "pixellab",
                    "seed": seed,
                    "images": images_map,
                }
                _pixellab_character_path(project_dir).write_text(json.dumps(char_payload, indent=2), encoding="utf-8")
                project["pixellab_character_approved"] = False
                project["pixellab_character_ready"] = True
                project["status"] = "pixellab_character_ready"
                project["updated_at"] = now_iso()
                save_project(project)
                return self._send_json(char_payload, status=HTTPStatus.CREATED)

            estimate_skeleton_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/estimate-skeleton", path)
            if estimate_skeleton_pixellab_match:
                project_id = estimate_skeleton_pixellab_match.group(1)
                payload = read_body(self)
                direction = (payload.get("direction") or "east").strip().lower()

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                canvas_size = coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE)

                # Require character assets.
                char_path = _pixellab_character_path(project_dir)
                if not char_path.exists():
                    raise ValueError("pixellab_character.json is missing; run create-character first.")
                char_data = load_json(char_path, None) or {}

                assets_dir = _pixellab_character_assets_dir(project_dir)
                source_img_path = assets_dir / ("%s.png" % direction)
                if not source_img_path.exists():
                    raise ValueError("Character direction image missing: %s" % str(source_img_path))

                seed = payload.get("seed")
                try:
                    seed = int(seed) if seed is not None else stable_int(project_id, direction, str(canvas_size), mod=4_294_967_295)
                except (TypeError, ValueError):
                    seed = stable_int(project_id, direction, str(canvas_size), mod=4_294_967_295)

                backend_mode = str(brief.get("backend_mode") or "comfyui")
                use_debug = backend_mode == "debug_procedural" or not pixellab_configured()

                if use_debug:
                    keypoints = debug_pixellab_skeleton_keypoints(canvas_size)
                    skel_payload = {
                        "approved": False,
                        "created_at": now_iso(),
                        "character_id": char_data.get("character_id"),
                        "direction": direction,
                        "image_size": {"width": canvas_size, "height": canvas_size},
                        "seed": seed,
                        "skeleton_keypoints": keypoints,
                    }
                    _pixellab_skeleton_path(project_dir).write_text(json.dumps(skel_payload, indent=2), encoding="utf-8")
                    project["pixellab_skeleton_ready"] = True
                    save_project(project)
                    append_history_event(project_id, {"type": "pixellab_skeleton_estimated", "direction": direction, "created_at": now_iso()})
                    return self._send_json(skel_payload, status=HTTPStatus.CREATED)

                client = get_pixellab_client()
                if client is None:
                    raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                image_b64 = client.encode_image(source_img_path)
                result = client.estimate_skeleton(image_b64)
                # Heuristic: locate keypoints array.
                keypoints = result.get("skeleton_keypoints") or result.get("keypoints") or result.get("result", {}).get("skeleton_keypoints")
                if not isinstance(keypoints, list) or len(keypoints) != 18:
                    raise ValueError("Pixel Lab skeleton response did not contain expected 18 keypoints.")

                skel_payload = {
                    "approved": False,
                    "created_at": now_iso(),
                    "character_id": char_data.get("character_id"),
                    "direction": direction,
                    "image_size": {"width": canvas_size, "height": canvas_size},
                    "seed": seed,
                    "skeleton_keypoints": keypoints,
                }
                _pixellab_skeleton_path(project_dir).write_text(json.dumps(skel_payload, indent=2), encoding="utf-8")
                project["pixellab_skeleton_ready"] = True
                save_project(project)
                return self._send_json(skel_payload, status=HTTPStatus.CREATED)

            approve_character_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/approve-character", path)
            if approve_character_pixellab_match:
                project_id = approve_character_pixellab_match.group(1)
                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                char_path = _pixellab_character_path(project_dir)
                if not char_path.exists():
                    raise ValueError("pixellab_character.json is missing; run create-character first.")

                char_data = load_json(char_path, None) or {}
                char_data["approved"] = True
                char_path.write_text(json.dumps(char_data, indent=2), encoding="utf-8")

                project["pixellab_character_approved"] = True
                project["status"] = "pixellab_character_approved"
                save_project(project)
                append_history_event(project_id, {"type": "pixellab_character_approved", "created_at": now_iso()})
                return self._send_json(char_data, status=HTTPStatus.OK)

            # -----------------------------
            # Phase 5: Pixel Lab animations
            # -----------------------------
            animate_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/animate", path)
            if animate_pixellab_match:
                project_id = animate_pixellab_match.group(1)
                payload = read_body(self)

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                canvas_size = coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE)

                # Phase 5 gating (4.3 carry-forward).
                char_data = _pixellab_character_approved_guard(project_dir)

                template_animation_id = payload.get("template_animation_id")
                if not template_animation_id:
                    raise ValueError("animate requires template_animation_id.")

                directions = int(payload.get("directions") or 4)
                if directions not in {4, 8}:
                    raise ValueError("directions must be 4 or 8.")

                animation_name = str(payload.get("animation_name") or "") or _infer_animation_name_from_template(template_animation_id)
                if animation_name not in {"idle", "walk"}:
                    # Current deterministic canonical pipeline only supports idle/walk.
                    raise ValueError("Unsupported animation_name (expected idle or walk).")

                if directions == 4:
                    direction_list = ["south", "west", "east", "north"]
                else:
                    direction_list = [
                        "south",
                        "south-east",
                        "east",
                        "north-east",
                        "north",
                        "north-west",
                        "west",
                        "south-west",
                    ]

                backend_mode = str(brief.get("backend_mode") or "comfyui")
                use_debug = backend_mode == "debug_procedural" or not pixellab_configured()

                seed = payload.get("seed")
                if seed is None:
                    seed = stable_int(project_id, str(template_animation_id), animation_name, str(directions), mod=4_294_967_295)
                try:
                    seed = int(seed)
                except (TypeError, ValueError):
                    seed = stable_int(project_id, str(template_animation_id), animation_name, str(directions), mod=4_294_967_295)

                fps_frame = _resolve_animation_timing(animation_name, template_animation_id=str(template_animation_id), pixel_lab_result=None)
                fps = fps_frame["fps"]
                frame_count = fps_frame["frame_count"]
                loop = fps_frame["loop"]

                store = _load_pixellab_animations_store(project_dir)

                if use_debug:
                    for dir_idx, direction in enumerate(direction_list):
                        frames = debug_pixellab_animation_frames(
                            animation_name,
                            direction,
                            canvas_size,
                            frame_count,
                            seed + dir_idx * 1000,
                            description_hint=str(template_animation_id)[:8],
                        )
                        frame_paths = _write_png_frames(frames, project_dir, animation_name, direction)
                        _upsert_pixellab_animation_frames(
                            project_dir,
                            store,
                            animation_name=animation_name,
                            direction=direction,
                            fps=fps,
                            frame_count=frame_count,
                            loop=loop,
                            frames_paths=frame_paths,
                            template_animation_id=str(template_animation_id),
                            backend_name="debug_procedural",
                            seed=seed,
                        )
                else:
                    client = get_pixellab_client()
                    if client is None:
                        raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                    # v2 endpoint call (async polling handled inside the client).
                    result = client.animate_character(
                        str(char_data.get("character_id") or ""),
                        str(template_animation_id),
                        directions=direction_list,
                        seed=seed,
                        poll_timeout_seconds=480,
                    )

                    fps_frame = _resolve_animation_timing(
                        animation_name,
                        template_animation_id=str(template_animation_id),
                        pixel_lab_result=result,
                    )
                    fps = fps_frame["fps"]
                    frame_count = fps_frame["frame_count"]
                    loop = fps_frame["loop"]

                    job_id = None
                    if isinstance(result, dict):
                        bj = result.get("background_job_ids") or result.get("backgroundJobIds")
                        if isinstance(bj, list) and bj:
                            job_id = ",".join(str(x) for x in bj if x)[:500] or None
                        if job_id is None:
                            job_id = (
                                result.get("job_id")
                                or result.get("jobId")
                                or result.get("background_job_id")
                                or result.get("backgroundJobId")
                            )

                    plate_frames = _pixellab_animation_job_to_rgba_frames(
                        result,
                        canvas_size=canvas_size,
                        client=client,
                    )
                    if not plate_frames:
                        keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
                        raise ValueError(
                            "Pixel Lab animation returned no decodable frames (PNG/WebP/JPEG base64 or image URLs). "
                            "Response keys: %s" % keys
                        )
                    # Heuristic ordering: direction-major then frame index.
                    for dir_idx, direction in enumerate(direction_list):
                        frames: List[Image.Image] = []
                        for frame_idx in range(frame_count):
                            flat_idx = dir_idx * frame_count + frame_idx
                            if flat_idx >= len(plate_frames):
                                break
                            frames.append(plate_frames[flat_idx])
                        frame_paths = _write_png_frames(frames[:frame_count], project_dir, animation_name, direction)
                        _upsert_pixellab_animation_frames(
                            project_dir,
                            store,
                            animation_name=animation_name,
                            direction=direction,
                            fps=fps,
                            frame_count=frame_count,
                            loop=loop,
                            frames_paths=frame_paths,
                            template_animation_id=str(template_animation_id),
                            backend_name="pixellab",
                            seed=seed,
                            job_id=job_id,
                        )

                return self._send_json({"ok": True, "animation_name": animation_name, "fps": fps, "frame_count": frame_count})

            animate_custom_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/animate-custom", path)
            if animate_custom_pixellab_match:
                project_id = animate_custom_pixellab_match.group(1)
                payload = read_body(self)

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                canvas_size = coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE)
                char_data = _pixellab_character_approved_guard(project_dir)

                action = str(payload.get("action") or "").strip()
                if not action:
                    raise ValueError("animate-custom requires action.")

                animation_name = str(payload.get("animation_name") or "idle").strip()
                if animation_name not in {"idle", "walk"}:
                    raise ValueError("Unsupported animation_name (expected idle or walk).")

                backend_mode = str(brief.get("backend_mode") or "comfyui")
                use_debug = backend_mode == "debug_procedural" or not pixellab_configured()

                seed = payload.get("seed")
                if seed is None:
                    seed = stable_int(project_id, action, animation_name, "custom", mod=4_294_967_295)
                try:
                    seed = int(seed)
                except (TypeError, ValueError):
                    seed = stable_int(project_id, action, animation_name, "custom", mod=4_294_967_295)

                fps_frame = _resolve_animation_timing(animation_name, pixel_lab_result=None)
                fps = fps_frame["fps"]
                frame_count = fps_frame["frame_count"]
                loop = fps_frame["loop"]

                direction = "east"
                store = _load_pixellab_animations_store(project_dir)

                if use_debug:
                    frames = debug_pixellab_animation_frames(animation_name, direction, canvas_size, frame_count, seed, description_hint=action)
                    frame_paths = _write_png_frames(frames, project_dir, animation_name, direction)
                    _upsert_pixellab_animation_frames(
                        project_dir,
                        store,
                        animation_name=animation_name,
                        direction=direction,
                        fps=fps,
                        frame_count=frame_count,
                        loop=loop,
                        frames_paths=frame_paths,
                        template_animation_id=None,
                        backend_name="debug_procedural",
                        seed=seed,
                    )
                else:
                    client = get_pixellab_client()
                    if client is None:
                        raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                    ref_rel = (char_data.get("images") or {}).get(direction)
                    if not ref_rel:
                        raise ValueError("pixellab_character.json is missing east reference image.")
                    ref_path = project_dir / str(ref_rel)
                    if not ref_path.exists():
                        raise ValueError("East reference image missing on disk.")

                    ref_b64 = client.encode_image(str(ref_path))
                    image_size = {"width": canvas_size, "height": canvas_size}
                    result = client.animate_with_text_v2(
                        ref_b64,
                        action,
                        image_size,
                        poll_timeout_seconds=480,
                    )

                    fps_frame = _resolve_animation_timing(animation_name, pixel_lab_result=result)
                    fps = fps_frame["fps"]
                    frame_count = fps_frame["frame_count"]
                    loop = fps_frame["loop"]

                    job_id = None
                    if isinstance(result, dict):
                        job_id = result.get("job_id") or result.get("jobId") or result.get("background_job_id") or result.get("backgroundJobId")

                    plate_frames = _pixellab_animation_job_to_rgba_frames(
                        result,
                        canvas_size=canvas_size,
                        client=client,
                    )
                    if not plate_frames:
                        keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
                        raise ValueError(
                            "Pixel Lab custom animation returned no decodable frames. Response keys: %s" % keys
                        )
                    frames = plate_frames[:frame_count]
                    frame_paths = _write_png_frames(frames[:frame_count], project_dir, animation_name, direction)
                    _upsert_pixellab_animation_frames(
                        project_dir,
                        store,
                        animation_name=animation_name,
                        direction=direction,
                        fps=fps,
                        frame_count=frame_count,
                        loop=loop,
                        frames_paths=frame_paths,
                        template_animation_id="custom",
                        backend_name="pixellab",
                        seed=seed,
                        job_id=job_id,
                    )

                return self._send_json({"ok": True, "animation_name": animation_name, "fps": fps, "frame_count": frame_count})

            animate_skeleton_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/animate-skeleton", path)
            if animate_skeleton_pixellab_match:
                project_id = animate_skeleton_pixellab_match.group(1)
                payload = read_body(self)

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                canvas_size = coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE)
                char_data = _pixellab_character_approved_guard(project_dir)

                keypoint_frames = payload.get("keypoint_frames") if isinstance(payload, dict) else None
                if not isinstance(keypoint_frames, list):
                    raise ValueError("animate-skeleton requires keypoint_frames: list.")

                animation_name = str(payload.get("animation_name") or "idle").strip()
                if animation_name not in {"idle", "walk"}:
                    raise ValueError("Unsupported animation_name (expected idle or walk).")

                direction = str(payload.get("direction") or "east").strip().lower() or "east"
                if direction not in (char_data.get("directions") or ["east"]):
                    # Keep strict enough to catch wiring mistakes.
                    raise ValueError("Invalid direction for this character: %s." % direction)

                backend_mode = str(brief.get("backend_mode") or "comfyui")
                use_debug = backend_mode == "debug_procedural" or not pixellab_configured()

                seed = payload.get("seed")
                if seed is None:
                    seed = stable_int(project_id, animation_name, direction, "skeleton", mod=4_294_967_295)
                try:
                    seed = int(seed)
                except (TypeError, ValueError):
                    seed = stable_int(project_id, animation_name, direction, "skeleton", mod=4_294_967_295)

                # Phase 5 debug mode mimics the plan: 4 frames per call.
                req_frame_count = len(keypoint_frames)
                fps_frame = _resolve_animation_timing(animation_name, pixel_lab_result=None)
                fps = fps_frame["fps"]
                frame_count = int(req_frame_count or 4)
                loop = fps_frame["loop"]

                # Require stored skeleton as base (Phase 5.3).
                skel_path = _pixellab_skeleton_path(project_dir)
                if not skel_path.exists():
                    raise ValueError("pixellab_skeleton.json is missing; estimate-skeleton first.")

                store = _load_pixellab_animations_store(project_dir)

                if use_debug:
                    frames = debug_pixellab_animation_frames(animation_name, direction, canvas_size, frame_count, seed, description_hint="skel")
                    frame_paths = _write_png_frames(frames, project_dir, animation_name, direction)
                    _upsert_pixellab_animation_frames(
                        project_dir,
                        store,
                        animation_name=animation_name,
                        direction=direction,
                        fps=fps,
                        frame_count=frame_count,
                        loop=loop,
                        frames_paths=frame_paths,
                        template_animation_id="skeleton",
                        backend_name="debug_procedural",
                        seed=seed,
                    )
                else:
                    client = get_pixellab_client()
                    if client is None:
                        raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                    ref_rel = (char_data.get("images") or {}).get(direction)
                    if not ref_rel:
                        raise ValueError("pixellab_character.json is missing reference image for direction=%s." % direction)
                    ref_path = project_dir / str(ref_rel)
                    if not ref_path.exists():
                        raise ValueError("Reference image missing on disk.")

                    ref_b64 = client.encode_image(str(ref_path))
                    image_size = {"width": canvas_size, "height": canvas_size}
                    result = client.animate_with_skeleton(
                        ref_b64,
                        image_size,
                        keypoint_frames,
                        poll_timeout_seconds=480,
                    )

                    fps_frame = _resolve_animation_timing(animation_name, pixel_lab_result=result)
                    fps = fps_frame["fps"]
                    loop = fps_frame["loop"]
                    # If Pixel Lab returns frames for a different count, trust the returned extraction.
                    plate_frames = _pixellab_animation_job_to_rgba_frames(
                        result,
                        canvas_size=canvas_size,
                        client=client,
                    )

                    job_id = None
                    if isinstance(result, dict):
                        job_id = result.get("job_id") or result.get("jobId") or result.get("background_job_id") or result.get("backgroundJobId")

                    if not plate_frames:
                        keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
                        raise ValueError(
                            "Pixel Lab skeleton animation returned no decodable frames. Response keys: %s" % keys
                        )
                    frame_count = min(int(frame_count), len(plate_frames))
                    frames = [plate_frames[i] for i in range(frame_count)]
                    frame_paths = _write_png_frames(frames[:frame_count], project_dir, animation_name, direction)
                    _upsert_pixellab_animation_frames(
                        project_dir,
                        store,
                        animation_name=animation_name,
                        direction=direction,
                        fps=fps,
                        frame_count=frame_count,
                        loop=loop,
                        frames_paths=frame_paths,
                        template_animation_id="skeleton",
                        backend_name="pixellab",
                        seed=seed,
                        job_id=job_id,
                    )

                return self._send_json({"ok": True, "animation_name": animation_name, "direction": direction, "fps": fps, "frame_count": frame_count})

            edit_animation_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/edit-animation", path)
            if edit_animation_pixellab_match:
                project_id = edit_animation_pixellab_match.group(1)
                payload = read_body(self)

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                canvas_size = coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE)
                char_data = _pixellab_character_approved_guard(project_dir)

                animation_name = str(payload.get("animation_name") or "").strip()
                description = str(payload.get("description") or "").strip()
                if not animation_name:
                    raise ValueError("edit-animation requires animation_name.")
                if not description:
                    raise ValueError("edit-animation requires description.")

                if animation_name not in {"idle", "walk"}:
                    raise ValueError("Unsupported animation_name (expected idle or walk).")

                backend_mode = str(brief.get("backend_mode") or "comfyui")
                use_debug = backend_mode == "debug_procedural" or not pixellab_configured()

                store = _load_pixellab_animations_store(project_dir)
                anim = (store.get("animations") or {}).get(animation_name) if isinstance(store.get("animations"), dict) else None
                directions = []
                if isinstance(anim, dict) and isinstance(anim.get("directions"), dict):
                    directions = list(anim["directions"].keys())
                if not directions:
                    # Fallback: infer from disk folders.
                    maybe_dir = project_dir / "animations" / animation_name
                    if maybe_dir.exists():
                        directions = [p.name for p in maybe_dir.iterdir() if p.is_dir()]
                if not directions:
                    raise ValueError("No existing animation frames found to edit.")

                # Use deterministic frame_count from AI specs when possible, otherwise infer from files.
                fps_frame = _resolve_animation_timing(animation_name, pixel_lab_result=None)
                fps = fps_frame["fps"]
                loop = fps_frame["loop"]

                seed = payload.get("seed")
                if seed is None:
                    seed = stable_int(project_id, animation_name, description, "edit", mod=4_294_967_295)
                try:
                    seed = int(seed)
                except (TypeError, ValueError):
                    seed = stable_int(project_id, animation_name, description, "edit", mod=4_294_967_295)

                for dir_idx, direction in enumerate(directions):
                    direction = str(direction).strip().lower()
                    # Infer frame_count from store if present.
                    inferred_fc = None
                    if isinstance(anim, dict) and isinstance(anim.get("directions"), dict):
                        inferred_fc = (anim["directions"].get(direction) or {}).get("frame_count")
                    if not inferred_fc:
                        inferred_fc = len(list((_pixellab_animation_frames_dir(project_dir, animation_name, direction)).glob("frame_*.png"))) if _pixellab_animation_frames_dir(project_dir, animation_name, direction).exists() else fps_frame["frame_count"]
                    frame_count = int(inferred_fc or fps_frame["frame_count"])

                    if use_debug:
                        frames = debug_pixellab_animation_frames(
                            animation_name,
                            direction,
                            canvas_size,
                            frame_count,
                            seed + dir_idx * 1000,
                            description_hint=description,
                        )
                        frame_paths = _write_png_frames(frames, project_dir, animation_name, direction)
                        _upsert_pixellab_animation_frames(
                            project_dir,
                            store,
                            animation_name=animation_name,
                            direction=direction,
                            fps=fps,
                            frame_count=frame_count,
                            loop=loop,
                            frames_paths=frame_paths,
                            template_animation_id="edited",
                            backend_name="debug_procedural",
                            seed=seed,
                            edited_description=description,
                        )
                    else:
                        client = get_pixellab_client()
                        if client is None:
                            raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                        frames_dir = _pixellab_animation_frames_dir(project_dir, animation_name, direction)
                        frame_b64s: List[str] = []
                        for idx in range(frame_count):
                            fp = frames_dir / ("frame_%02d.png" % idx)
                            if not fp.exists():
                                break
                            frame_b64s.append(client.encode_image(str(fp)))

                        image_size = {"width": canvas_size, "height": canvas_size}
                        result = client.edit_animation_v2(
                            description,
                            frame_b64s,
                            image_size,
                            poll_timeout_seconds=480,
                        )
                        plate_frames = _pixellab_animation_job_to_rgba_frames(
                            result,
                            canvas_size=canvas_size,
                            client=client,
                        )
                        if not plate_frames:
                            keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
                            raise ValueError(
                                "Pixel Lab edit-animation returned no decodable frames. Response keys: %s" % keys
                            )
                        out_fc = min(frame_count, len(plate_frames))
                        frames = [plate_frames[i] for i in range(out_fc)]
                        frame_paths = _write_png_frames(frames, project_dir, animation_name, direction)
                        _upsert_pixellab_animation_frames(
                            project_dir,
                            store,
                            animation_name=animation_name,
                            direction=direction,
                            fps=fps,
                            frame_count=out_fc,
                            loop=loop,
                            frames_paths=frame_paths,
                            template_animation_id="edited",
                            backend_name="pixellab",
                            seed=seed,
                            edited_description=description,
                        )

                return self._send_json({"ok": True, "animation_name": animation_name, "description": description})

            build_clips_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/build-clips", path)
            if build_clips_pixellab_match:
                project_id = build_clips_pixellab_match.group(1)
                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                _pixellab_character_approved_guard(project_dir)

                pix_store = _load_pixellab_animations_store(project_dir)
                anim_store = pix_store.get("animations") if isinstance(pix_store.get("animations"), dict) else {}
                miss = pixellab_missing_canonical_animation_clips(anim_store)
                if miss:
                    raise ValueError(
                        "Cannot build canonical clips yet — no frame data in pixellab_animations.json for: %s. "
                        "Use **Generate via template** or **Generate custom** on the Animations panel for each listed clip (character must be approved), then try again."
                        % ", ".join(miss)
                    )

                animation_clips_path = canonical_downstream_path(project_dir, "animation_clips")
                existing = load_json(animation_clips_path, {}) or {}
                if not isinstance(existing, dict):
                    existing = {}

                for animation_name, anim in anim_store.items():
                    if not isinstance(anim, dict):
                        continue
                    if animation_name not in {"idle", "walk"}:
                        continue

                    fps = anim.get("fps") or (AI_CLIP_SPECS.get(animation_name) or {}).get("fps") or ANIMATION_SPECS.get(animation_name, {}).get("fps") or 12
                    frame_count = anim.get("frame_count") or (AI_CLIP_SPECS.get(animation_name) or {}).get("frame_count") or ANIMATION_SPECS.get(animation_name, {}).get("frame_count") or 4
                    loop = bool(anim.get("loop", True))

                    frames_by_direction = {}
                    if isinstance(anim.get("directions"), dict):
                        for direction, ddata in anim["directions"].items():
                            if isinstance(ddata, dict) and isinstance(ddata.get("frames"), list):
                                frames_by_direction[str(direction)] = ddata["frames"]

                    default_dir = "east" if "east" in frames_by_direction else (next(iter(frames_by_direction.keys())) if frames_by_direction else "east")
                    frames = frames_by_direction.get(default_dir) or []

                    clip = existing.get(animation_name) if isinstance(existing.get(animation_name), dict) else {}
                    if not isinstance(clip, dict):
                        clip = {}
                    clip.update({
                        "fps": int(fps),
                        "loop": loop,
                        "frame_count": int(frame_count),
                        "frames": frames,
                        "frames_by_direction": frames_by_direction,
                    })
                    existing[animation_name] = clip

                # Persist via save_project() so we don't get overwritten by the
                # hydrated `project["animation_clips"]` value.
                project["animation_clips"] = existing
                project["current_stage"] = "animations"
                project["status"] = "pixellab_build_clips_complete"
                project["updated_at"] = now_iso()
                save_project(project)
                return self._send_json({"ok": True, "animation_clips_updated": True})

            improved_prompt_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/([^/]+)/improve-prompt", path)
            if improved_prompt_match:
                project_id, concept_id = improved_prompt_match.groups()
                payload = read_body(self)
                return self._send_json(generate_improved_prompt(project_id, concept_id, payload.get("feedback")), status=HTTPStatus.CREATED)

            import_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/import", path)
            if import_match:
                import_project_id = import_match.group(1)
                import_body = read_body(self)
                import_result = import_concept_attempt(import_project_id, import_body)

                # Phase 3.3: optional convert_to_pixelart post-processing
                if import_body.get("convert_to_pixelart") and pixellab_configured():
                    try:
                        _client = get_pixellab_client()
                        if _client:
                            # The most recently added concept is last in the list.
                            _import_project = load_project(import_project_id)
                            _import_project_dir = PROJECTS_ROOT / import_project_id
                            _new_concept = next(
                                (c for c in reversed(_import_project.get("concepts") or []) if c.get("preview_image")),
                                None,
                            )
                            if _new_concept:
                                _preview_rel = _new_concept.get("preview_image") or ""
                                _preview_path = _import_project_dir / _preview_rel
                                if _preview_path.exists():
                                    _img_b64 = _client.encode_image(str(_preview_path))
                                    _brief = _import_project.get("brief") or {}
                                    _canvas = coerce_canvas_size(_brief.get("canvas_size"), DEFAULT_CANVAS_SIZE)
                                    _converted = _client.image_to_pixelart(
                                        _img_b64,
                                        input_size={"width": _canvas, "height": _canvas},
                                        output_size={"width": _canvas, "height": _canvas},
                                    )
                                    _converted_b64 = (
                                        _converted.get("image", {}).get("base64")
                                        or _converted.get("base64")
                                        or _converted.get("result", {}).get("base64")
                                    )
                                    if _converted_b64:
                                        import base64 as _b64mod
                                        _preview_path.write_bytes(_b64mod.b64decode(_converted_b64))
                    except Exception:
                        pass  # Conversion failure is non-fatal; the original import is preserved.

                return self._send_json(import_result, status=HTTPStatus.CREATED)

            validate_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/([^/]+)/validate", path)
            if validate_match:
                project_id, concept_id = validate_match.groups()
                payload = read_body(self)
                return self._send_json(update_concept_validation(project_id, concept_id, payload.get("validation_status"), payload.get("feedback")))

            revalidate_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/([^/]+)/revalidate", path)
            if revalidate_match:
                project_id, concept_id = revalidate_match.groups()
                return self._send_json(validate_imported_concept(project_id, concept_id))

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

            delete_concept_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/([^/]+)/delete", path)
            if delete_concept_match:
                project_id, concept_id = delete_concept_match.groups()
                return self._send_json(delete_concept(project_id, concept_id))

            promote_reference_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/use-reference", path)
            if promote_reference_match:
                project_id = promote_reference_match.group(1)
                payload = read_body(self)
                return self._send_json(promote_reference_as_concept(project_id, payload))

            similar_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/([^/]+)/regenerate-similar", path)
            if similar_match:
                project_id, concept_id = similar_match.groups()
                return self._send_json(
                    create_job(project_id, "concepts.regenerate_similar", lambda progress: generate_run(project_id, "similar", source_concept_id=concept_id, progress=progress)),
                    status=HTTPStatus.ACCEPTED,
                )

            refine_match = re.fullmatch(r"/api/projects/([^/]+)/refine", path)
            if refine_match:
                return self._send_error_json(HTTPStatus.GONE, "The refine stage has been removed. Generate an improved Gemini prompt instead.")

            master_pose_generate_match = re.fullmatch(r"/api/projects/([^/]+)/master-pose/generate", path)
            if master_pose_generate_match:
                project_id = master_pose_generate_match.group(1)
                return self._send_json(
                    create_job(project_id, "master_pose.generate", lambda progress: generate_master_pose_candidates(project_id, progress=progress)),
                    status=HTTPStatus.ACCEPTED,
                )

            master_pose_select_match = re.fullmatch(r"/api/projects/([^/]+)/master-pose/select", path)
            if master_pose_select_match:
                project_id = master_pose_select_match.group(1)
                payload = read_body(self)
                candidate_id = payload.get("candidate_id")
                if not candidate_id:
                    raise ValueError("master-pose/select requires candidate_id.")
                return self._send_json(select_master_pose(project_id, candidate_id))

            rig_layout_generate_match = re.fullmatch(r"/api/projects/([^/]+)/rig-layout/generate", path)
            if rig_layout_generate_match:
                return self._send_json(generate_rig_layout(rig_layout_generate_match.group(1)), status=HTTPStatus.CREATED)

            rig_layout_update_match = re.fullmatch(r"/api/projects/([^/]+)/rig-layout/update", path)
            if rig_layout_update_match:
                return self._send_json(update_rig_layout(rig_layout_update_match.group(1), read_body(self)))

            rig_layout_approve_match = re.fullmatch(r"/api/projects/([^/]+)/rig-layout/approve", path)
            if rig_layout_approve_match:
                return self._send_json(approve_rig_layout(rig_layout_approve_match.group(1)))

            part_manifest_generate_match = re.fullmatch(r"/api/projects/([^/]+)/part-manifest/generate", path)
            if part_manifest_generate_match:
                return self._send_json(generate_part_manifest(part_manifest_generate_match.group(1)), status=HTTPStatus.CREATED)

            part_manifest_update_match = re.fullmatch(r"/api/projects/([^/]+)/part-manifest/update", path)
            if part_manifest_update_match:
                return self._send_json(update_part_manifest(part_manifest_update_match.group(1), read_body(self)))

            part_manifest_approve_match = re.fullmatch(r"/api/projects/([^/]+)/part-manifest/approve", path)
            if part_manifest_approve_match:
                return self._send_json(approve_part_manifest(part_manifest_approve_match.group(1)))

            part_shapes_initialize_match = re.fullmatch(r"/api/projects/([^/]+)/part-shapes/initialize", path)
            if part_shapes_initialize_match:
                return self._send_json(initialize_part_shapes(part_shapes_initialize_match.group(1)), status=HTTPStatus.CREATED)

            part_shapes_update_match = re.fullmatch(r"/api/projects/([^/]+)/part-shapes/update", path)
            if part_shapes_update_match:
                return self._send_json(update_part_shapes(part_shapes_update_match.group(1), read_body(self)))

            part_shapes_approve_match = re.fullmatch(r"/api/projects/([^/]+)/part-shapes/approve", path)
            if part_shapes_approve_match:
                return self._send_json(approve_part_shapes(part_shapes_approve_match.group(1)))

            split_build_match = re.fullmatch(r"/api/projects/([^/]+)/split-build", path)
            if split_build_match:
                return self._send_json(build_split_from_part_shapes(split_build_match.group(1)), status=HTTPStatus.CREATED)

            part_split_generate_match = re.fullmatch(r"/api/projects/([^/]+)/part-split/generate", path)
            if part_split_generate_match:
                return self._send_json(generate_part_split(part_split_generate_match.group(1)), status=HTTPStatus.CREATED)

            part_split_update_match = re.fullmatch(r"/api/projects/([^/]+)/part-split/update", path)
            if part_split_update_match:
                return self._send_json(update_part_split(part_split_update_match.group(1), read_body(self)))

            part_split_approve_match = re.fullmatch(r"/api/projects/([^/]+)/part-split/approve", path)
            if part_split_approve_match:
                return self._send_json(approve_part_split(part_split_approve_match.group(1)))

            sprite_model_build_match = re.fullmatch(r"/api/projects/([^/]+)/sprite-model/build", path)
            if sprite_model_build_match:
                project_id = sprite_model_build_match.group(1)
                return self._send_json(
                    create_job(project_id, "sprite_model.build", lambda progress: build_sprite_model(project_id, progress=progress)),
                    status=HTTPStatus.ACCEPTED,
                )

            sprite_model_update_match = re.fullmatch(r"/api/projects/([^/]+)/sprite-model/update", path)
            if sprite_model_update_match:
                project_id = sprite_model_update_match.group(1)
                return self._send_json(update_sprite_model(project_id, read_body(self)))

            sprite_model_recover_match = re.fullmatch(r"/api/projects/([^/]+)/sprite-model/recover-occlusion", path)
            if sprite_model_recover_match:
                project_id = sprite_model_recover_match.group(1)
                return self._send_json(recover_sprite_model_occlusion(project_id, read_body(self)))

            sprite_model_promote_match = re.fullmatch(r"/api/projects/([^/]+)/sprite-model/promote-recovery", path)
            if sprite_model_promote_match:
                project_id = sprite_model_promote_match.group(1)
                return self._send_json(promote_sprite_model_recovery_variant(project_id, read_body(self)))

            sprite_model_undo_match = re.fullmatch(r"/api/projects/([^/]+)/sprite-model/undo", path)
            if sprite_model_undo_match:
                return self._send_json(undo_last_sprite_model_change(sprite_model_undo_match.group(1)))

            sprite_model_restore_match = re.fullmatch(r"/api/projects/([^/]+)/sprite-model/restore", path)
            if sprite_model_restore_match:
                project_id = sprite_model_restore_match.group(1)
                payload = read_body(self)
                revision_id = payload.get("revision_id")
                if not revision_id:
                    raise ValueError("sprite-model/restore requires revision_id.")
                return self._send_json(restore_sprite_model_revision(project_id, revision_id))

            rig_match = re.fullmatch(r"/api/projects/([^/]+)/rig/build", path)
            if rig_match:
                project_id = rig_match.group(1)
                return self._send_json(create_job(project_id, "rig.build", lambda progress: build_rig(project_id, progress=progress)), status=HTTPStatus.ACCEPTED)

            manual_clip_create_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/create", path)
            if manual_clip_create_match:
                project_id = manual_clip_create_match.group(1)
                return self._send_json(create_manual_animation_clip(project_id, read_body(self)))

            external_authoring_update_match = re.fullmatch(r"/api/projects/([^/]+)/external-authoring/update", path)
            if external_authoring_update_match:
                return self._send_error_json(HTTPStatus.GONE, "SkelForm external authoring has been retired. Use /api/projects/<id>/ai-workflow instead.")

            external_authoring_session_match = re.fullmatch(r"/api/projects/([^/]+)/external-authoring/session", path)
            if external_authoring_session_match:
                return self._send_error_json(HTTPStatus.GONE, "SkelForm external authoring has been retired. Use /api/projects/<id>/ai-workflow instead.")

            external_authoring_import_match = re.fullmatch(r"/api/projects/([^/]+)/external-authoring/import-bundle", path)
            if external_authoring_import_match:
                return self._send_error_json(HTTPStatus.GONE, "SkelForm external authoring has been retired. Use /api/projects/<id>/ai-workflow instead.")

            ai_workflow_run_match = re.fullmatch(r"/api/projects/([^/]+)/ai-workflow/run", path)
            if ai_workflow_run_match:
                project_id = ai_workflow_run_match.group(1)
                payload = read_body(self)
                return self._send_json(
                    create_job(project_id, "ai_workflow.%s" % str(payload.get("stage") or "run"), lambda progress: run_ai_workflow_stage(project_id, payload, progress=progress)),
                    status=HTTPStatus.ACCEPTED,
                )

            ai_workflow_approve_match = re.fullmatch(r"/api/projects/([^/]+)/ai-workflow/approve", path)
            if ai_workflow_approve_match:
                project_id = ai_workflow_approve_match.group(1)
                return self._send_json(approve_ai_workflow(project_id, read_body(self)))

            ai_workflow_reject_match = re.fullmatch(r"/api/projects/([^/]+)/ai-workflow/reject", path)
            if ai_workflow_reject_match:
                project_id = ai_workflow_reject_match.group(1)
                return self._send_json(reject_ai_workflow(project_id, read_body(self)))

            manual_clip_update_meta_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/update-meta", path)
            if manual_clip_update_meta_match:
                project_id, clip_id = manual_clip_update_meta_match.groups()
                return self._send_json(update_manual_animation_clip_meta(project_id, clip_id, read_body(self)))

            manual_clip_frame_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/frame/([0-9]+)", path)
            if manual_clip_frame_match:
                project_id, clip_id, frame_index = manual_clip_frame_match.groups()
                return self._send_json(update_manual_animation_clip_frame(project_id, clip_id, int(frame_index), read_body(self)))

            manual_clip_copy_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/frame/([0-9]+)/copy", path)
            if manual_clip_copy_match:
                project_id, clip_id, frame_index = manual_clip_copy_match.groups()
                return self._send_json(copy_manual_animation_clip_frame(project_id, clip_id, int(frame_index), read_body(self)))

            manual_clip_reset_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/frame/([0-9]+)/reset", path)
            if manual_clip_reset_match:
                project_id, clip_id, frame_index = manual_clip_reset_match.groups()
                return self._send_json(reset_manual_animation_clip_frame(project_id, clip_id, int(frame_index)))

            manual_clip_repair_generate_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/frame/([0-9]+)/repair/([^/]+)/generate", path)
            if manual_clip_repair_generate_match:
                project_id, clip_id, frame_index, part_name = manual_clip_repair_generate_match.groups()
                return self._send_json(generate_manual_animation_clip_frame_repair(project_id, clip_id, int(frame_index), part_name, read_body(self)))

            manual_clip_repair_apply_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/frame/([0-9]+)/repair/([^/]+)/apply", path)
            if manual_clip_repair_apply_match:
                project_id, clip_id, frame_index, part_name = manual_clip_repair_apply_match.groups()
                return self._send_json(apply_manual_animation_clip_frame_repair(project_id, clip_id, int(frame_index), part_name, read_body(self)))

            manual_clip_repair_clear_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/frame/([0-9]+)/repair/([^/]+)/clear", path)
            if manual_clip_repair_clear_match:
                project_id, clip_id, frame_index, part_name = manual_clip_repair_clear_match.groups()
                return self._send_json(clear_manual_animation_clip_frame_repair(project_id, clip_id, int(frame_index), part_name))

            manual_clip_patch_generate_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/frame/([0-9]+)/patch/([^/]+)/generate", path)
            if manual_clip_patch_generate_match:
                project_id, clip_id, frame_index, source_part_name = manual_clip_patch_generate_match.groups()
                return self._send_json(generate_manual_animation_clip_frame_patch(project_id, clip_id, int(frame_index), source_part_name, read_body(self)))

            manual_clip_patch_apply_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/frame/([0-9]+)/patch/([^/]+)/apply", path)
            if manual_clip_patch_apply_match:
                project_id, clip_id, frame_index, source_part_name = manual_clip_patch_apply_match.groups()
                return self._send_json(apply_manual_animation_clip_frame_patch(project_id, clip_id, int(frame_index), source_part_name, read_body(self)))

            manual_clip_patch_clear_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/frame/([0-9]+)/patch/([^/]+)/clear", path)
            if manual_clip_patch_clear_match:
                project_id, clip_id, frame_index, source_part_name = manual_clip_patch_clear_match.groups()
                return self._send_json(clear_manual_animation_clip_frame_patch(project_id, clip_id, int(frame_index), source_part_name))

            manual_clip_render_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/render-preview", path)
            if manual_clip_render_match:
                project_id, clip_id = manual_clip_render_match.groups()
                return self._send_json(
                    create_job(project_id, "manual_clips.%s.render_preview" % clip_id, lambda progress: render_manual_animation_clip_preview(project_id, clip_id, progress=progress)),
                    status=HTTPStatus.ACCEPTED,
                )

            manual_clip_approve_match = re.fullmatch(r"/api/projects/([^/]+)/manual-clips/([^/]+)/(approve|unapprove)", path)
            if manual_clip_approve_match:
                project_id, clip_id, action = manual_clip_approve_match.groups()
                return self._send_json(approve_manual_animation_clip(project_id, clip_id, action == "approve"))

            clip_update_match = re.fullmatch(r"/api/projects/([^/]+)/clips/([^/]+)/update", path)
            if clip_update_match:
                project_id, clip_name = clip_update_match.groups()
                return self._send_json(update_animation_clip(project_id, clip_name, read_body(self)))

            clip_reset_match = re.fullmatch(r"/api/projects/([^/]+)/clips/([^/]+)/reset", path)
            if clip_reset_match:
                project_id, clip_name = clip_reset_match.groups()
                return self._send_json(reset_animation_clip(project_id, clip_name))

            clip_match = re.fullmatch(r"/api/projects/([^/]+)/clips/([^/]+)/render", path)
            if clip_match:
                project_id, clip_name = clip_match.groups()
                if clip_name not in ANIMATION_SPECS:
                    raise ValueError("Unknown clip: %s." % clip_name)
                return self._send_json(create_job(project_id, "clips.%s.render" % clip_name, lambda progress: render_animation(project_id, clip_name, progress=progress)), status=HTTPStatus.ACCEPTED)

            qa_match = re.fullmatch(r"/api/projects/([^/]+)/qa/run", path)
            if qa_match:
                project_id = qa_match.group(1)
                return self._send_json(create_job(project_id, "qa.run", lambda progress: run_qa(project_id, progress=progress)), status=HTTPStatus.ACCEPTED)

            export_match = re.fullmatch(r"/api/projects/([^/]+)/export", path)
            if export_match:
                project_id = export_match.group(1)
                return self._send_json(create_job(project_id, "export", lambda progress: export_project(project_id, progress=progress)), status=HTTPStatus.ACCEPTED)

            approve_sprite_model_match = re.fullmatch(r"/api/projects/([^/]+)/sprite-model/approve", path)
            if approve_sprite_model_match:
                return self._send_json(approve_sprite_model_review(approve_sprite_model_match.group(1)))

            approve_rig_direct_match = re.fullmatch(r"/api/projects/([^/]+)/rig/approve", path)
            if approve_rig_direct_match:
                return self._send_json(approve_rig_review(approve_rig_direct_match.group(1)))

        except FileNotFoundError:
            return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")
        except ValueError as exc:
            return self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except HttpRequestError as exc:
            return self._send_error_json(HTTPStatus.BAD_GATEWAY, str(exc))
        except Exception as exc:
            return self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

        return self._send_error_json(HTTPStatus.NOT_FOUND, "Unknown API route: %s" % path)

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
