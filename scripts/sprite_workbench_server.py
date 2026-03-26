#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import io
import json
import logging
import math
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Running as `python3 scripts/sprite_workbench_server.py` puts ``scripts/`` on sys.path[0];
# keep repo root first so ``import scripts.*`` resolves.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from typing import Any, Callable, Dict, List, Optional, Protocol, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse, unquote
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageDraw, ImageOps

from scripts.pixellab_client import PixelLabError, PixelLabHTTPError
from scripts import workbench_brief as workbench_brief
from scripts import workbench_concepts as workbench_concepts
from scripts import workbench_ai_workflow_runtime as workbench_ai_workflow_runtime
from scripts import workbench_external_authoring as workbench_external_authoring
from scripts import workbench_export as workbench_export
from scripts import workbench_iteration as workbench_iteration
from scripts import workbench_legacy_concept_runs as workbench_legacy_concept_runs
from scripts import workbench_legacy_animation_production as workbench_legacy_animation_production
from scripts import workbench_manual_clips as workbench_manual_clips
from scripts import workbench_part_split as workbench_part_split
from scripts import workbench_persistence as persistence
from scripts import workbench_pixellab_store as workbench_pixellab_store
from scripts import workbench_project_catalog as project_catalog
from scripts import workbench_project_io as project_io
from scripts import workbench_project_lifecycle as project_lifecycle
from scripts import workbench_rig_parts as workbench_rig_parts
from scripts import workbench_sprite_model_rig as workbench_sprite_model_rig
from scripts import workbench_workflow_state as workbench_workflow_state

try:
    from google import genai as _google_genai
    from google.genai import types as _google_genai_types
    _GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    _GOOGLE_GENAI_AVAILABLE = False


ROOT = _REPO_ROOT
TOOL_DIR = ROOT / "tools" / "2d-sprite-and-animation"
PROJECTS_ROOT = TOOL_DIR / "projects-data"
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
PROJECT_SCHEMA_VERSION = 1
PROJECT_BUNDLE_MANIFEST_VERSION = 1
PROJECT_HEALTH_REPORT_VERSION = 1
PROJECT_BUNDLE_MANIFEST_FILENAME = "project_bundle_manifest.json"
PROJECT_HEALTH_REPORT_FILENAME = "project_health.json"
WORKBENCH_SETTINGS_FILENAME = "_workbench_settings.json"
USAGE_LEDGER_FILENAME = "_usage_ledger.json"
ROOM_LAYOUT_FILENAME = "room_layout.json"
ROOM_LAYOUT_HISTORY_FILENAME = "room_layout_history.json"
LEVEL_VALIDATION_REPORT_FILENAME = "level_validation_report.json"
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
PIXELLAB_API_KEY = os.environ.get("PIXELLAB_API_KEY", "")
DEMO_PROJECT_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "sprite_workbench"
WORKBENCH_SETTINGS_DEFAULTS = {
    "safe_mode": False,
    "confirm_paid_actions": True,
}
USAGE_LEDGER_LIMIT = 2000

logger = logging.getLogger("sprite_workbench")


def _pixellab_api_result_summary(result: Any) -> str:
    """Compact description of a Pixel Lab JSON payload for logs (no large base64 bodies)."""
    if result is None:
        return "None"
    if not isinstance(result, dict):
        return type(result).__name__
    parts: List[str] = ["keys=%r" % list(result.keys())]
    for k in (
        "status",
        "job_id",
        "jobId",
        "background_job_id",
        "backgroundJobId",
        "background_job_ids",
        "backgroundJobIds",
        "directions",
    ):
        if k in result:
            parts.append("%s=%r" % (k, result.get(k)))
    pj = result.get("per_job_last_response") or result.get("merged_last_responses")
    if isinstance(pj, list):
        parts.append("merged_jobs=%d" % len(pj))
        for i, block in enumerate(pj[:16]):
            if isinstance(block, dict):
                parts.append("job[%d]_keys=%r" % (i, list(block.keys())[:32]))
            else:
                parts.append("job[%d]_type=%s" % (i, type(block).__name__))
    return "; ".join(parts)


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

        # Pixel Lab may keep the POST connection open a long time before returning job JSON.
        _http_timeout = env_int("SPRITE_WORKBENCH_PIXELLAB_HTTP_TIMEOUT", 180, minimum=30)
        _pixellab_client = PixelLabClient(api_key=PIXELLAB_API_KEY, timeout_seconds=_http_timeout)
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


# Custom animation (animate-with-text-v2) can stay in "processing" longer than idle/walk; override via env if needed.
PIXELLAB_ANIMATE_CUSTOM_POLL_TIMEOUT_SECONDS = env_int("PIXELLAB_ANIMATE_CUSTOM_POLL_TIMEOUT_SECONDS", 900, minimum=180)

CONCEPT_CANVAS = (640, 768)
INITIAL_CONCEPT_COUNT = 6
REFINEMENT_CONCEPT_COUNT = 4
JOB_HISTORY_LIMIT = 50
WIZARD_STEPS = ["project", "brief", "references", "concepts", "review", "rig_layout", "part_manifest", "part_shape_edit", "split_build", "split_review", "sprite_model", "rig", "clips", "qa", "export"]
# Guided AI workflow (non-legacy): no rig_layout / part_manifest steps in the stepper UI.
WIZARD_STEPS_AI = ["project", "brief", "references", "concepts", "review", "clips", "qa", "export"]
# Phase 8: Pixel Lab guided flow uses four visible steps (describe → concepts → animations → export).
WIZARD_STEPS_PIXEL_LAB_UI = ["describe", "concepts", "animations", "export"]
# Non–Pixel Lab AI (debug_procedural) uses three steps (no separate Character or Animations panel).
WIZARD_STEPS_AI_SIMPLE_UI = ["describe", "concepts", "export"]
# Inserted after "clips" for Pixel Lab guided flow (Phase 7.5).
WIZARD_STEP_ANIMATIONS = "animations"
WIZARD_STEPS_KNOWN = set(WIZARD_STEPS) | {WIZARD_STEP_ANIMATIONS, "describe", "character"}
MASTER_POSE_COUNT = 3

FRAME_SIZE = 256
FRAME_PIVOT = (128, 245)
WORKING_CANVAS = (420, 420)
RENDER_SCALE = 0.84
RENDER_CENTER = (210, 220)

HTTP_JSON_DEFAULT_TIMEOUT_SECONDS = env_int("SPRITE_WORKBENCH_HTTP_JSON_TIMEOUT_SECONDS", 30, minimum=5)

REFINEMENT_STRENGTHS = {
    "subtle": 0.25,
    "medium": 0.45,
    "strong": 0.65,
}

ITERATION_ELEMENTS = (
    "outfit",
    "weapon/prop",
    "palette/colors",
    "pose",
    "silhouette",
    "hair/head",
    "accessories",
    "expression",
    "proportions",
)

REFERENCE_ROLES = ("identity", "costume", "style", "prop")
BACKEND_MODES = ("debug_procedural", "pixellab")


def normalize_brief_backend_mode(raw: Any) -> str:
    """Map legacy ``backend_mode`` values after ComfyUI removal (Phase 8)."""
    s = str(raw or "").strip()
    if s == "comfyui":
        return "debug_procedural"
    if s in BACKEND_MODES:
        return s
    return "debug_procedural"


def brief_backend_mode(brief: Optional[Dict[str, Any]]) -> str:
    return normalize_brief_backend_mode((brief or {}).get("backend_mode"))


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
PIXELLAB_CONCEPT_IMAGE_SIZE = 128
PIXELLAB_CONCEPT_INIT_IMAGE_STRENGTH = 820
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
    "detailed shading": "detailed shading",
    "highly detailed shading": "highly detailed shading",
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


def preferred_supported_canvas_size(image_size: Any, default: int = DEFAULT_CANVAS_SIZE) -> int:
    """Prefer a supported square size from stored image metadata before falling back to the brief default."""
    if isinstance(image_size, dict):
        width = image_size.get("width")
        height = image_size.get("height")
        try:
            width_i = int(width)
            height_i = int(height)
        except (TypeError, ValueError):
            return coerce_canvas_size(None, default)
        if width_i == height_i and width_i in SUPPORTED_CANVAS_SIZES:
            return width_i
    return coerce_canvas_size(default, default)


def preferred_concept_canvas_size(image_size: Any) -> int:
    """Concept-derived Pixel Lab assets should normalize onto the shared concept canvas."""
    return preferred_supported_canvas_size(image_size, PIXELLAB_CONCEPT_IMAGE_SIZE)


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

NEGATING_PREFIX_PATTERN = re.compile(r"(?:^|[\s,;:()/-])(?:no|not|avoid|without|exclude|excluding|except|skip)\b", re.I)

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


persistence.configure(
    PROJECTS_ROOT=PROJECTS_ROOT,
    PROJECT_SCHEMA_VERSION=PROJECT_SCHEMA_VERSION,
    PROJECT_BUNDLE_MANIFEST_VERSION=PROJECT_BUNDLE_MANIFEST_VERSION,
    PROJECT_HEALTH_REPORT_VERSION=PROJECT_HEALTH_REPORT_VERSION,
    PROJECT_BUNDLE_MANIFEST_FILENAME=PROJECT_BUNDLE_MANIFEST_FILENAME,
    PROJECT_HEALTH_REPORT_FILENAME=PROJECT_HEALTH_REPORT_FILENAME,
    WORKBENCH_SETTINGS_FILENAME=WORKBENCH_SETTINGS_FILENAME,
    USAGE_LEDGER_FILENAME=USAGE_LEDGER_FILENAME,
    ROOM_LAYOUT_FILENAME=ROOM_LAYOUT_FILENAME,
    ROOM_LAYOUT_HISTORY_FILENAME=ROOM_LAYOUT_HISTORY_FILENAME,
    LEVEL_VALIDATION_REPORT_FILENAME=LEVEL_VALIDATION_REPORT_FILENAME,
    TOOL_VERSION=TOOL_VERSION,
    WORKBENCH_SETTINGS_DEFAULTS=WORKBENCH_SETTINGS_DEFAULTS,
    USAGE_LEDGER_LIMIT=USAGE_LEDGER_LIMIT,
    now_iso=now_iso,
    slugify=slugify,
)

def _sync_persistence_config() -> None:
    persistence.configure(
        PROJECTS_ROOT=PROJECTS_ROOT,
        PROJECT_SCHEMA_VERSION=PROJECT_SCHEMA_VERSION,
        PROJECT_BUNDLE_MANIFEST_VERSION=PROJECT_BUNDLE_MANIFEST_VERSION,
        PROJECT_HEALTH_REPORT_VERSION=PROJECT_HEALTH_REPORT_VERSION,
        PROJECT_BUNDLE_MANIFEST_FILENAME=PROJECT_BUNDLE_MANIFEST_FILENAME,
        PROJECT_HEALTH_REPORT_FILENAME=PROJECT_HEALTH_REPORT_FILENAME,
        WORKBENCH_SETTINGS_FILENAME=WORKBENCH_SETTINGS_FILENAME,
        USAGE_LEDGER_FILENAME=USAGE_LEDGER_FILENAME,
        ROOM_LAYOUT_FILENAME=ROOM_LAYOUT_FILENAME,
        ROOM_LAYOUT_HISTORY_FILENAME=ROOM_LAYOUT_HISTORY_FILENAME,
        LEVEL_VALIDATION_REPORT_FILENAME=LEVEL_VALIDATION_REPORT_FILENAME,
        TOOL_VERSION=TOOL_VERSION,
        WORKBENCH_SETTINGS_DEFAULTS=WORKBENCH_SETTINGS_DEFAULTS,
        USAGE_LEDGER_LIMIT=USAGE_LEDGER_LIMIT,
        now_iso=now_iso,
        slugify=slugify,
    )


def _sync_project_catalog_config() -> None:
    project_catalog.configure(
        PROJECTS_ROOT=PROJECTS_ROOT,
        PROJECT_SCHEMA_VERSION=PROJECT_SCHEMA_VERSION,
        DEMO_PROJECT_FIXTURE_ROOT=DEMO_PROJECT_FIXTURE_ROOT,
        ROOM_LAYOUT_FILENAME=ROOM_LAYOUT_FILENAME,
        ROOM_LAYOUT_HISTORY_FILENAME=ROOM_LAYOUT_HISTORY_FILENAME,
        LEVEL_VALIDATION_REPORT_FILENAME=LEVEL_VALIDATION_REPORT_FILENAME,
        now_iso=now_iso,
        slugify=slugify,
        stable_hash=stable_hash,
        load_json=load_json,
        load_project=load_project,
        save_project=save_project,
        apply_project_defaults=apply_project_defaults,
        ensure_dirs=ensure_dirs,
        append_history_event=append_history_event,
        parse_data_url=parse_data_url,
        project_backup_filename=project_backup_filename,
        load_project_health_summary=load_project_health_summary,
        normalize_wizard_state=normalize_wizard_state,
    )


def _sync_project_io_config() -> None:
    project_io.configure(
        PROJECTS_ROOT=PROJECTS_ROOT,
        PROJECT_SCHEMA_VERSION=PROJECT_SCHEMA_VERSION,
        apply_project_defaults=apply_project_defaults,
        ensure_dirs=ensure_dirs,
        hydrate_brief=hydrate_brief,
        load_json=load_json,
        write_json=write_json,
        canonical_downstream_path=canonical_downstream_path,
        rig_layout_history_path=rig_layout_history_path,
        default_rig_layout_history=default_rig_layout_history,
        part_manifest_history_path=part_manifest_history_path,
        default_part_manifest_history=default_part_manifest_history,
        validate_part_manifest=validate_part_manifest,
        part_shapes_history_path=part_shapes_history_path,
        default_part_shapes_history=default_part_shapes_history,
        validate_part_shapes=validate_part_shapes,
        part_split_history_path=part_split_history_path,
        default_part_split_history=default_part_split_history,
        normalize_mask=normalize_mask,
        detect_mask=detect_mask,
        validate_part_split=validate_part_split,
        load_master_pose_manifest=load_master_pose_manifest,
        legacy_downstream_path=legacy_downstream_path,
        hydrate_legacy_sprite_model=hydrate_legacy_sprite_model,
        validate_sprite_model=validate_sprite_model,
        active_rig_profile_name=active_rig_profile_name,
        hydrate_animation_clips=hydrate_animation_clips,
        hydrate_manual_animation_clips=hydrate_manual_animation_clips,
        hydrate_ai_workflow=hydrate_ai_workflow,
        hydrate_external_authoring=hydrate_external_authoring,
        load_sprite_model_history=load_sprite_model_history,
        resolve_rig_layout=resolve_rig_layout,
        load_history=load_history,
        room_layout_path=room_layout_path,
        default_room_layout=default_room_layout,
        room_layout_history_path=room_layout_history_path,
        default_room_layout_history=default_room_layout_history,
        validate_room_layout=validate_room_layout,
        level_validation_report_path=level_validation_report_path,
        _pixellab_character_path=_pixellab_character_path,
        _pixellab_skeleton_path=_pixellab_skeleton_path,
        _load_pixellab_animations_store=_load_pixellab_animations_store,
        load_concepts=load_concepts,
        hydrate_concept=hydrate_concept,
        _normalize_east_only_character_source=_normalize_east_only_character_source,
        _upscale_legacy_east_only_animation_frames=_upscale_legacy_east_only_animation_frames,
        prompt_history_entries=prompt_history_entries,
        build_rig_layout_handoff_prompt=build_rig_layout_handoff_prompt,
        build_part_manifest_handoff_prompt=build_part_manifest_handoff_prompt,
        build_part_shapes_handoff_prompt=build_part_shapes_handoff_prompt,
        build_part_split_handoff_prompt=build_part_split_handoff_prompt,
        load_stage_maturity=load_stage_maturity,
        derive_metrics=derive_metrics,
        build_run_summaries=build_run_summaries,
        selected_concept=selected_concept,
        animation_render_complete=animation_render_complete,
        compute_wizard_context=compute_wizard_context,
        persist_project_integrity_metadata=persist_project_integrity_metadata,
        project_health_report_path=project_health_report_path,
        project_bundle_manifest_path=project_bundle_manifest_path,
        analyze_reference_asset=analyze_reference_asset,
        save_master_pose_manifest=save_master_pose_manifest,
        save_sprite_model_history=save_sprite_model_history,
        serialize_manual_animation_clips=serialize_manual_animation_clips,
        serialize_ai_workflow=serialize_ai_workflow,
        serialize_external_authoring=serialize_external_authoring,
        save_concept=save_concept,
        now_iso=now_iso,
    )


def _sync_project_lifecycle_config() -> None:
    project_lifecycle.configure(
        PROJECTS_ROOT=PROJECTS_ROOT,
        ROOM_LAYOUT_FILENAME=ROOM_LAYOUT_FILENAME,
        ROOM_LAYOUT_HISTORY_FILENAME=ROOM_LAYOUT_HISTORY_FILENAME,
        LEVEL_VALIDATION_REPORT_FILENAME=LEVEL_VALIDATION_REPORT_FILENAME,
        CANONICAL_DOWNSTREAM_FILES=CANONICAL_DOWNSTREAM_FILES,
        LEGACY_DOWNSTREAM_FILES=LEGACY_DOWNSTREAM_FILES,
        normalize_prompt_text=normalize_prompt_text,
        build_brief_from_payload=build_brief_from_payload,
        merge_new_references=merge_new_references,
        slugify=slugify,
        stable_hash=stable_hash,
        now_iso=now_iso,
        ensure_dirs=ensure_dirs,
        normalize_wizard_state=normalize_wizard_state,
        set_wizard_step_complete=set_wizard_step_complete,
        default_ai_workflow=default_ai_workflow,
        default_external_authoring=default_external_authoring,
        default_room_layout=default_room_layout,
        default_room_layout_history=default_room_layout_history,
        validate_room_layout=validate_room_layout,
        save_project=save_project,
        load_project=load_project,
        delete_path=delete_path,
        legacy_downstream_path=legacy_downstream_path,
    )


def _sync_workbench_export_config() -> None:
    workbench_export.configure(
        AI_CLIP_SPECS=AI_CLIP_SPECS,
        AI_WORKFLOW_PROFILE=AI_WORKFLOW_PROFILE,
        ANIMATION_SPECS=ANIMATION_SPECS,
        FRAME_PIVOT=FRAME_PIVOT,
        FRAME_SIZE=FRAME_SIZE,
        PROJECTS_ROOT=PROJECTS_ROOT,
        TOOL_VERSION=TOOL_VERSION,
        _pixellab_animations_path=_pixellab_animations_path,
        _pixellab_character_approved_guard=_pixellab_character_approved_guard,
        _pixellab_character_path=_pixellab_character_path,
        ai_workflow_or_error=ai_workflow_or_error,
        alpha_bbox=alpha_bbox,
        border_has_alpha=border_has_alpha,
        call_progress=call_progress,
        canonical_downstream_path=canonical_downstream_path,
        cleanup_frame=cleanup_frame,
        clip_root_motion_policy=clip_root_motion_policy,
        hydrate_external_authoring=hydrate_external_authoring,
        image_sha256=image_sha256,
        load_json=load_json,
        load_part_asset=load_part_asset,
        load_project=load_project,
        now_iso=now_iso,
        pixellab_animation_store_has_frames=pixellab_animation_store_has_frames,
        save_project=save_project,
        sync_pixellab_animation_clips=sync_pixellab_animation_clips,
        validate_sprite_model=validate_sprite_model,
        write_json=write_json,
    )


def _sync_workbench_concepts_config() -> None:
    workbench_concepts.configure(
        DEFAULT_NEGATIVE_PROMPT=DEFAULT_NEGATIVE_PROMPT,
        PROJECTS_ROOT=PROJECTS_ROOT,
        _CONCEPT_ARTIFACT_IMAGE_KEYS=_CONCEPT_ARTIFACT_IMAGE_KEYS,
        _set_pixellab_east_only_character_source=_set_pixellab_east_only_character_source,
        append_history_event=append_history_event,
        apply_validation_state=apply_validation_state,
        clear_project_downstream_state=clear_project_downstream_state,
        default_rig_layout_history=default_rig_layout_history,
        delete_path=delete_path,
        load_json=load_json,
        load_project=load_project,
        make_character_spec=make_character_spec,
        now_iso=now_iso,
        parse_iso=parse_iso,
        reset_downstream_assets=reset_downstream_assets,
        resolve_rig_layout=resolve_rig_layout,
        rig_layout_history_path=rig_layout_history_path,
        save_project=save_project,
        write_json=write_json,
    )


def _sync_workbench_brief_config() -> None:
    workbench_brief.configure(
        CHARACTER_TEMPLATE_MAP=CHARACTER_TEMPLATE_MAP,
        DEFAULT_CANVAS_SIZE=DEFAULT_CANVAS_SIZE,
        DEFAULT_CHARACTER_TEMPLATE=DEFAULT_CHARACTER_TEMPLATE,
        DEFAULT_DETAIL_LEVEL=DEFAULT_DETAIL_LEVEL,
        DEFAULT_NEGATIVE_PROMPT=DEFAULT_NEGATIVE_PROMPT,
        DEFAULT_OUTLINE_STYLE=DEFAULT_OUTLINE_STYLE,
        DEFAULT_SHADING_STYLE=DEFAULT_SHADING_STYLE,
        DETAIL_LEVEL_MAP=DETAIL_LEVEL_MAP,
        HOUSE_STYLE_PROMPT_RULES=HOUSE_STYLE_PROMPT_RULES,
        METROIDVANIA_PROMPT_CONTEXT=METROIDVANIA_PROMPT_CONTEXT,
        NEGATING_PREFIX_PATTERN=NEGATING_PREFIX_PATTERN,
        OUTLINE_STYLE_MAP=OUTLINE_STYLE_MAP,
        PIXELLAB_CONCEPT_IMAGE_SIZE=PIXELLAB_CONCEPT_IMAGE_SIZE,
        REFERENCE_ROLES=REFERENCE_ROLES,
        REFERENCE_SPRITESHEET_HINTS=REFERENCE_SPRITESHEET_HINTS,
        REJECT_PATTERNS=REJECT_PATTERNS,
        SHADING_STYLE_MAP=SHADING_STYLE_MAP,
        clamp=clamp,
        coerce_canvas_size=coerce_canvas_size,
        detect_mask=detect_mask,
        guess_extension=guess_extension,
        mask_connected_components=mask_connected_components,
        normalize_brief_backend_mode=normalize_brief_backend_mode,
        now_iso=now_iso,
        parse_data_url=parse_data_url,
        pick_mapped_style=pick_mapped_style,
        sanitize_filename=sanitize_filename,
        stable_hash=stable_hash,
        stable_int=stable_int,
        summarize_iteration_feedback=summarize_iteration_feedback,
    )


def _sync_workbench_iteration_config() -> None:
    workbench_iteration.configure(
        GEMINI_IMAGE_MODEL=GEMINI_IMAGE_MODEL,
        ITERATION_ELEMENTS=ITERATION_ELEMENTS,
        PIXELLAB_CONCEPT_IMAGE_SIZE=PIXELLAB_CONCEPT_IMAGE_SIZE,
        _GOOGLE_GENAI_AVAILABLE=_GOOGLE_GENAI_AVAILABLE,
        _brief_pixel_lab_style=_brief_pixel_lab_style,
        _google_genai=_google_genai if _GOOGLE_GENAI_AVAILABLE else None,
        _google_genai_types=_google_genai_types if _GOOGLE_GENAI_AVAILABLE else None,
        detect_mask=detect_mask,
        gemini_client_factory=lambda: get_gemini_client(),
        largest_component_mask=largest_component_mask,
        normalize_mask=normalize_mask,
        stable_int=stable_int,
    )


def _sync_workbench_pixellab_store_config() -> None:
    workbench_pixellab_store.configure(
        SUPPORTED_CANVAS_SIZES=SUPPORTED_CANVAS_SIZES,
        _PIXELLAB_ANIMATION_NAME_RE=_PIXELLAB_ANIMATION_NAME_RE,
        load_json=load_json,
        now_iso=now_iso,
        preferred_concept_canvas_size=preferred_concept_canvas_size,
        prepare_pixellab_character_color_source=prepare_pixellab_character_color_source,
    )


def _sync_workbench_workflow_state_config() -> None:
    workbench_workflow_state.configure(
        AI_CLIP_SPECS=AI_CLIP_SPECS,
        AI_WORKFLOW_PROFILE=AI_WORKFLOW_PROFILE,
        ANIMATION_SPECS=ANIMATION_SPECS,
        CANONICAL_DOWNSTREAM_FILES=CANONICAL_DOWNSTREAM_FILES,
        LEGACY_DOWNSTREAM_FILES=LEGACY_DOWNSTREAM_FILES,
        PROJECT_SCHEMA_VERSION=PROJECT_SCHEMA_VERSION,
        SKELFORM_DOCS_URL=SKELFORM_DOCS_URL,
        SKELFORM_EDITOR_URL=SKELFORM_EDITOR_URL,
        WIZARD_STEPS_KNOWN=WIZARD_STEPS_KNOWN,
        humanize_identifier=humanize_identifier,
        image_sha256=image_sha256,
        load_json=load_json,
        neutral_pose_transforms=neutral_pose_transforms,
        now_iso=now_iso,
        sanitize_filename=sanitize_filename,
        skelform_provider_profile=skelform_provider_profile,
    )


def _sync_workbench_manual_clips_config() -> None:
    workbench_manual_clips.configure(
        PROJECTS_ROOT=PROJECTS_ROOT,
        call_progress=call_progress,
        cleanup_frame=cleanup_frame,
        clear_directory=clear_directory,
        default_manual_animation_clips=default_manual_animation_clips,
        default_manual_clip=default_manual_clip,
        hydrate_manual_animation_clips=hydrate_manual_animation_clips,
        humanize_identifier=humanize_identifier,
        invalidate_manual_clip_preview=invalidate_manual_clip_preview,
        load_project=load_project,
        manual_clip_frame_count=manual_clip_frame_count,
        manual_clip_render_root=manual_clip_render_root,
        manual_clip_source_hashes=manual_clip_source_hashes,
        normalize_manual_clip_frame=normalize_manual_clip_frame,
        normalize_manual_clip_frame_entry=normalize_manual_clip_frame_entry,
        normalize_manual_frame_patches=normalize_manual_frame_patches,
        normalize_manual_frame_repairs=normalize_manual_frame_repairs,
        now_iso=now_iso,
        neutral_pose_transforms=neutral_pose_transforms,
        recover_sprite_model_occlusion=recover_sprite_model_occlusion,
        render_pose_from_sprite_model=render_pose_from_sprite_model,
        sanitize_filename=sanitize_filename,
        save_project=save_project,
        slugify=slugify,
        write_json=write_json,
    )


def _sync_workbench_legacy_animation_production_config() -> None:
    workbench_legacy_animation_production.configure(
        ANIMATION_SPECS=ANIMATION_SPECS,
        DEFAULT_CLIP_CONTROLS=DEFAULT_CLIP_CONTROLS,
        PROJECTS_ROOT=PROJECTS_ROOT,
        active_rig_profile_name=active_rig_profile_name,
        call_progress=call_progress,
        canonical_downstream_path=canonical_downstream_path,
        cleanup_frame=cleanup_frame,
        clear_directory=clear_directory,
        clear_project_downstream_state=clear_project_downstream_state,
        clip_frame_overrides=clip_frame_overrides,
        default_clip_controls=default_clip_controls,
        delete_path=delete_path,
        generate_clip_frames=generate_clip_frames,
        hydrate_animation_clips=hydrate_animation_clips,
        load_json=load_json,
        load_project=load_project,
        normalize_clip_controls=normalize_clip_controls,
        now_iso=now_iso,
        render_pose_from_sprite_model=render_pose_from_sprite_model,
        reset_downstream_assets=reset_downstream_assets,
        save_project=save_project,
        write_json=write_json,
    )


def _sync_workbench_legacy_concept_runs_config() -> None:
    workbench_legacy_concept_runs.configure(
        CONCEPT_CANVAS=CONCEPT_CANVAS,
        INITIAL_CONCEPT_COUNT=INITIAL_CONCEPT_COUNT,
        MAJOR_REFINEMENT_LOCKS=MAJOR_REFINEMENT_LOCKS,
        PROJECTS_ROOT=PROJECTS_ROOT,
        REFINEMENT_CONCEPT_COUNT=REFINEMENT_CONCEPT_COUNT,
        REFINEMENT_STRENGTHS=REFINEMENT_STRENGTHS,
        ConceptRequest=ConceptRequest,
        annotate_run_triage=annotate_run_triage,
        append_history_event=append_history_event,
        brief_backend_mode=brief_backend_mode,
        build_initial_variation_axes=build_initial_variation_axes,
        build_prompt_bundle=build_prompt_bundle,
        build_refinement_variation_axes=build_refinement_variation_axes,
        call_progress=call_progress,
        get_concept_backend=get_concept_backend,
        load_project=load_project,
        make_reference_inputs=make_reference_inputs,
        now_iso=now_iso,
        palette_from_seed=palette_from_seed,
        save_concept=save_concept,
        save_project=save_project,
        stable_int=stable_int,
        summarize_run_triage=summarize_run_triage,
        next_concept_serial=next_concept_serial,
    )


def _sync_workbench_ai_workflow_runtime_config() -> None:
    workbench_ai_workflow_runtime.configure(
        AI_CHARACTER_LOCK_COUNT=AI_CHARACTER_LOCK_COUNT,
        AI_CLIP_SPECS=AI_CLIP_SPECS,
        AI_KEY_POSE_NAMES=AI_KEY_POSE_NAMES,
        AI_WORKFLOW_PROFILE=AI_WORKFLOW_PROFILE,
        DEFAULT_NEGATIVE_PROMPT=DEFAULT_NEGATIVE_PROMPT,
        FRAME_PIVOT=FRAME_PIVOT,
        PROJECTS_ROOT=PROJECTS_ROOT,
        ai_workflow_or_error=ai_workflow_or_error,
        ai_workflow_root=ai_workflow_root,
        call_progress=call_progress,
        cleanup_frame=cleanup_frame,
        clear_directory=clear_directory,
        default_ai_workflow=default_ai_workflow,
        detect_mask=detect_mask,
        largest_component_mask=largest_component_mask,
        load_project=load_project,
        normalize_mask=normalize_mask,
        now_iso=now_iso,
        refresh_ai_workflow_dependency_status=refresh_ai_workflow_dependency_status,
        resolve_sprite_source_image=resolve_sprite_source_image,
        save_project=save_project,
        write_json=write_json,
    )


def _sync_workbench_external_authoring_config() -> None:
    workbench_external_authoring.configure(
        PROJECTS_ROOT=PROJECTS_ROOT,
        SKELFORM_EDITOR_URL=SKELFORM_EDITOR_URL,
        default_external_authoring=default_external_authoring,
        external_authoring_import_root=external_authoring_import_root,
        guess_extension=guess_extension,
        hydrate_external_authoring=hydrate_external_authoring,
        load_json=load_json,
        load_project=load_project,
        now_iso=now_iso,
        parse_data_url=parse_data_url,
        quote=quote,
        sanitize_filename=sanitize_filename,
        save_project=save_project,
        set_wizard_step_complete=set_wizard_step_complete,
        skelform_provider_profile=skelform_provider_profile,
    )


def _sync_workbench_part_split_config() -> None:
    workbench_part_split.configure(
        CONCEPT_CANVAS=CONCEPT_CANVAS,
        PROJECTS_ROOT=PROJECTS_ROOT,
        active_rig_profile_name=active_rig_profile_name,
        canonical_downstream_path=canonical_downstream_path,
        canonical_sprite_part_role=canonical_sprite_part_role,
        clear_project_downstream_state=clear_project_downstream_state,
        create_part_split_revision=create_part_split_revision,
        crop_region_from_source=crop_region_from_source,
        detect_mask=detect_mask,
        estimate_facing_direction=estimate_facing_direction,
        extract_json_object_from_text=extract_json_object_from_text,
        image_with_mask=image_with_mask,
        load_project=load_project,
        normalize_mask=normalize_mask,
        now_iso=now_iso,
        part_pivot_from_image=part_pivot_from_image,
        render_part_split_reconstruction=render_part_split_reconstruction,
        render_polygon_mask=render_polygon_mask,
        reset_downstream_assets=reset_downstream_assets,
        resolve_layout_region=resolve_layout_region,
        resolve_rig_layout=resolve_rig_layout,
        resolve_sprite_source_image=resolve_sprite_source_image,
        region_box=region_box,
        save_project=save_project,
        selected_concept=selected_concept,
        validate_part_split=validate_part_split,
        write_json=write_json,
        write_part_split_asset=write_part_split_asset,
    )


def _sync_workbench_rig_parts_config() -> None:
    workbench_rig_parts.configure(
        ANIMATION_SPECS=ANIMATION_SPECS,
        CONCEPT_CANVAS=CONCEPT_CANVAS,
        PROJECTS_ROOT=PROJECTS_ROOT,
        RIG_PROFILES=RIG_PROFILES,
        TOOL_VERSION=TOOL_VERSION,
        active_rig_profile_name=active_rig_profile_name,
        build_default_part_manifest=build_default_part_manifest,
        build_default_part_shapes=build_default_part_shapes,
        canonical_downstream_path=canonical_downstream_path,
        clamp_point_to_image=clamp_point_to_image,
        clear_project_downstream_state=clear_project_downstream_state,
        create_part_manifest_revision=create_part_manifest_revision,
        create_part_shapes_revision=create_part_shapes_revision,
        create_rig_layout_revision=create_rig_layout_revision,
        default_rig_layout_history=default_rig_layout_history,
        detect_mask=detect_mask,
        extract_json_object_from_text=extract_json_object_from_text,
        humanize_identifier=humanize_identifier,
        load_json=load_json,
        load_project=load_project,
        now_iso=now_iso,
        preserve_part_shapes_for_manifest=preserve_part_shapes_for_manifest,
        render_polygon_mask=render_polygon_mask,
        reset_downstream_assets=reset_downstream_assets,
        resolve_rig_layout=resolve_rig_layout,
        resolve_sprite_source_image=resolve_sprite_source_image,
        rig_layout_history_path=rig_layout_history_path,
        save_project=save_project,
        select_rig_profile=select_rig_profile,
        selected_concept=selected_concept,
        validate_part_manifest=validate_part_manifest,
        validate_part_shapes=validate_part_shapes,
        validate_rig_layout=validate_rig_layout,
        write_json=write_json,
        write_part_shape_assets=write_part_shape_assets,
    )


def _sync_workbench_sprite_model_rig_config() -> None:
    workbench_sprite_model_rig.configure(
        ANIMATION_SPECS=ANIMATION_SPECS,
        CANONICAL_DOWNSTREAM_FILES=CANONICAL_DOWNSTREAM_FILES,
        CONCEPT_CANVAS=CONCEPT_CANVAS,
        DEFAULT_CLIP_CONTROLS=DEFAULT_CLIP_CONTROLS,
        FRAME_SIZE=FRAME_SIZE,
        FRAME_PIVOT=FRAME_PIVOT,
        PART_DRAW_ORDERS=PART_DRAW_ORDERS,
        PART_PARENT_JOINTS=PART_PARENT_JOINTS,
        PART_PIVOT_FRACTIONS=PART_PIVOT_FRACTIONS,
        PROJECTS_ROOT=PROJECTS_ROOT,
        RIG_PROFILES=RIG_PROFILES,
        SPRITE_MODEL_FAIL_MIN_MASK_AREA=SPRITE_MODEL_FAIL_MIN_MASK_AREA,
        SPRITE_MODEL_MIN_DIMENSION=SPRITE_MODEL_MIN_DIMENSION,
        SPRITE_MODEL_WARN_COMPONENT_OVERLAP_RATIO=SPRITE_MODEL_WARN_COMPONENT_OVERLAP_RATIO,
        SPRITE_MODEL_WARN_MIN_MASK_AREA=SPRITE_MODEL_WARN_MIN_MASK_AREA,
        SPRITE_MODEL_WARN_PROP_OVERLAP_RATIO=SPRITE_MODEL_WARN_PROP_OVERLAP_RATIO,
        SIDE_KNIGHT_SIMPLE_7=SIDE_KNIGHT_SIMPLE_7,
        SIDE_KNIGHT_DUAL_LEG_8=SIDE_KNIGHT_DUAL_LEG_8,
        WORKING_CANVAS=WORKING_CANVAS,
        active_rig_profile_name=active_rig_profile_name,
        add_outline=add_outline,
        alpha_bbox=alpha_bbox,
        bbox_area=bbox_area,
        bbox_intersection_area=bbox_intersection_area,
        call_progress=call_progress,
        canonical_downstream_path=canonical_downstream_path,
        canonical_sprite_part_role=canonical_sprite_part_role,
        clamp=clamp,
        clamp_int=clamp_int,
        clear_directory=clear_directory,
        clear_project_downstream_state=clear_project_downstream_state,
        create_sprite_model_revision=create_sprite_model_revision,
        crop_to_alpha=crop_to_alpha,
        delete_path=delete_path,
        detect_mask=detect_mask,
        dilate_mask=dilate_mask,
        image_with_mask=image_with_mask,
        legacy_downstream_path=legacy_downstream_path,
        list_to_tuple=list_to_tuple,
        load_json=load_json,
        load_part_split_asset=load_part_split_asset,
        load_project=load_project,
        load_sprite_model_history=load_sprite_model_history,
        mask_pixel_area=mask_pixel_area,
        normalize_manual_frame_patches=normalize_manual_frame_patches,
        normalize_mask=normalize_mask,
        now_iso=now_iso,
        parse_data_url=parse_data_url,
        rgba_to_hex=rgba_to_hex,
        resolve_layout_parent_joint=resolve_layout_parent_joint,
        resolve_layout_region=resolve_layout_region,
        resolve_part_image_path=resolve_part_image_path,
        resolve_rig_layout=resolve_rig_layout,
        resolve_sprite_source_image=resolve_sprite_source_image,
        reset_downstream_assets=reset_downstream_assets,
        sanitize_filename=sanitize_filename,
        save_project=save_project,
        save_sprite_model_history=save_sprite_model_history,
        selected_concept=selected_concept,
        write_json=write_json,
    )


load_json = persistence.load_json
write_json = persistence.write_json
project_bundle_manifest_path = persistence.project_bundle_manifest_path
project_health_report_path = persistence.project_health_report_path
room_layout_path = persistence.room_layout_path
room_layout_history_path = persistence.room_layout_history_path
level_validation_report_path = persistence.level_validation_report_path
iter_project_artifact_paths = persistence.iter_project_artifact_paths
build_project_bundle_manifest = persistence.build_project_bundle_manifest
build_project_health_report = persistence.build_project_health_report
persist_project_integrity_metadata = persistence.persist_project_integrity_metadata
load_project_health_summary = persistence.load_project_health_summary
project_backup_filename = persistence.project_backup_filename
default_room_layout = persistence.default_room_layout
default_room_layout_history = persistence.default_room_layout_history
validate_room_layout = persistence.validate_room_layout
room_layout_wizard_complete = persistence.room_layout_wizard_complete


def workbench_settings_path() -> Path:
    _sync_persistence_config()
    return persistence.workbench_settings_path()


def usage_ledger_path() -> Path:
    _sync_persistence_config()
    return persistence.usage_ledger_path()


def load_workbench_settings() -> Dict[str, Any]:
    _sync_persistence_config()
    return persistence.load_workbench_settings()


def save_workbench_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_persistence_config()
    return persistence.save_workbench_settings(payload)


def load_usage_ledger() -> Dict[str, Any]:
    _sync_persistence_config()
    return persistence.load_usage_ledger()


def append_usage_ledger_entry(**kwargs: Any) -> Dict[str, Any]:
    _sync_persistence_config()
    return persistence.append_usage_ledger_entry(**kwargs)


def summarize_usage_ledger() -> Dict[str, Any]:
    _sync_persistence_config()
    return persistence.summarize_usage_ledger()


def provider_call_allowed() -> None:
    _sync_persistence_config()
    persistence.provider_call_allowed()


def list_demo_projects() -> List[Dict[str, Any]]:
    _sync_project_catalog_config()
    return project_catalog.list_demo_projects()


def import_demo_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_project_catalog_config()
    return project_catalog.import_demo_project(payload)


def build_project_bundle_archive(project_id: str) -> Tuple[str, bytes]:
    _sync_project_catalog_config()
    return project_catalog.build_project_bundle_archive(project_id)


def import_project_bundle(payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_project_catalog_config()
    return project_catalog.import_project_bundle(payload)


def list_projects(include_archived: bool) -> List[Dict[str, Any]]:
    _sync_project_catalog_config()
    return project_catalog.list_projects(include_archived)


def project_summary(project: Dict[str, Any]) -> Dict[str, Any]:
    _sync_project_catalog_config()
    return project_catalog.project_summary(project)


def create_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_project_lifecycle_config()
    return project_lifecycle.create_project(payload)


def update_project_brief(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_project_lifecycle_config()
    return project_lifecycle.update_project_brief(project_id, payload)


def duplicate_project(project_id: str) -> Dict[str, Any]:
    _sync_project_lifecycle_config()
    return project_lifecycle.duplicate_project(project_id)


def enrich_brief_references(project_dir: Path, brief: Dict[str, Any]) -> Dict[str, Any]:
    _sync_project_io_config()
    return project_io.enrich_brief_references(project_dir, brief)


def load_project(project_id: str) -> Dict[str, Any]:
    _sync_project_io_config()
    return project_io.load_project(project_id)


def save_project(project: Dict[str, Any]) -> None:
    _sync_project_io_config()
    project_io.save_project(project)


def legacy_reference_entries(brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    _sync_workbench_brief_config()
    return workbench_brief.legacy_reference_entries(brief)


def normalize_prompt_text(prompt_text: str) -> str:
    _sync_workbench_brief_config()
    return workbench_brief.normalize_prompt_text(prompt_text)


def validate_prompt_constraints(prompt_text: str) -> None:
    _sync_workbench_brief_config()
    workbench_brief.validate_prompt_constraints(prompt_text)


def infer_prop(prompt_text: str) -> str:
    _sync_workbench_brief_config()
    return workbench_brief.infer_prop(prompt_text)


def infer_brief_defaults(prompt_text: str) -> Dict[str, str]:
    _sync_workbench_brief_config()
    return workbench_brief.infer_brief_defaults(prompt_text)


def hydrate_brief(brief: Optional[Dict[str, Any]], prompt_text: str) -> Dict[str, Any]:
    _sync_workbench_brief_config()
    return workbench_brief.hydrate_brief(brief, prompt_text)


def build_positive_prompt_base(brief: Dict[str, Any]) -> str:
    _sync_workbench_brief_config()
    return workbench_brief.build_positive_prompt_base(brief)


def _brief_pixel_lab_style(brief: Dict[str, Any]) -> Dict[str, str]:
    _sync_workbench_brief_config()
    return workbench_brief._brief_pixel_lab_style(brief)


def build_concept_prompt(brief: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_brief_config()
    return workbench_brief.build_concept_prompt(brief)


def _build_element_inpaint_mask(element: str, canvas_size: int) -> Tuple[Image.Image, List[Dict[str, int]]]:
    _sync_workbench_iteration_config()
    return workbench_iteration._build_element_inpaint_mask(element, canvas_size)


def _encode_png_base64(image: Image.Image) -> str:
    _sync_workbench_iteration_config()
    return workbench_iteration._encode_png_base64(image)


def _element_edit_mask_for_size(element: str, size: Tuple[int, int]) -> Image.Image:
    _sync_workbench_iteration_config()
    return workbench_iteration._element_edit_mask_for_size(element, size)


def _is_side_view_correction_request(element: str, change_text: str) -> bool:
    _sync_workbench_iteration_config()
    return workbench_iteration._is_side_view_correction_request(element, change_text)


def _protected_source_mask_for_element(element: str, size: Tuple[int, int], change_text: str = "") -> Image.Image:
    _sync_workbench_iteration_config()
    return workbench_iteration._protected_source_mask_for_element(element, size, change_text)


def _iteration_element_contract(element: str) -> Dict[str, Any]:
    _sync_workbench_iteration_config()
    return workbench_iteration._iteration_element_contract(element)


def _iteration_element_contract_with_request(element: str, change_text: str) -> Dict[str, Any]:
    _sync_workbench_iteration_config()
    return workbench_iteration._iteration_element_contract_with_request(element, change_text)


def _build_iteration_edit_prompt(
    brief: Dict[str, Any],
    element: str,
    change_text: str,
    *,
    canvas_size: Optional[int] = None,
) -> str:
    _sync_workbench_iteration_config()
    return workbench_iteration._build_iteration_edit_prompt(brief, element, change_text, canvas_size=canvas_size)


def _build_gemini_requirements_prompt(
    brief: Dict[str, Any],
    element: str,
    change_text: str,
) -> str:
    _sync_workbench_iteration_config()
    return workbench_iteration._build_gemini_requirements_prompt(brief, element, change_text)


def gemini_iteration_supported_for_element(element: str) -> bool:
    _sync_workbench_iteration_config()
    return workbench_iteration.gemini_iteration_supported_for_element(element)


def _concept_source_image_relpath(concept: Dict[str, Any]) -> Optional[str]:
    _sync_workbench_iteration_config()
    return workbench_iteration._concept_source_image_relpath(concept)


def _count_mask_pixels(mask: Image.Image) -> int:
    _sync_workbench_iteration_config()
    return workbench_iteration._count_mask_pixels(mask)


def evaluate_gemini_iteration_result(
    concept_path: Path,
    element: str,
    change_text: str,
    result_image: Image.Image,
) -> Dict[str, Any]:
    _sync_workbench_iteration_config()
    return workbench_iteration.evaluate_gemini_iteration_result(concept_path, element, change_text, result_image)


def build_iteration_prompt(
    brief: Dict[str, Any],
    element: str,
    change_text: str,
    *,
    source_concept_path: Optional[Path] = None,
) -> Dict[str, Any]:
    _sync_workbench_iteration_config()
    return workbench_iteration.build_iteration_prompt(
        brief,
        element,
        change_text,
        source_concept_path=source_concept_path,
    )


def get_gemini_client() -> Any:
    _sync_workbench_iteration_config()
    return workbench_iteration.get_gemini_client()


def gemini_iterate_concept(
    source_image_bytes: bytes,
    element: str,
    change_text: str,
    brief: Dict[str, Any],
) -> bytes:
    _sync_workbench_iteration_config()
    return workbench_iteration.gemini_iterate_concept(source_image_bytes, element, change_text, brief)


def build_gemini_prompt(
    prompt_text: str,
    previous_prompt: Optional[str],
    validation_feedback: Optional[str],
    imported_attempt: Optional[Dict[str, Any]],
) -> str:
    _sync_workbench_brief_config()
    return workbench_brief.build_gemini_prompt(prompt_text, previous_prompt, validation_feedback, imported_attempt)


def analyze_reference_asset(path: Optional[Path], source_value: Optional[str] = None) -> Dict[str, Any]:
    _sync_workbench_brief_config()
    return workbench_brief.analyze_reference_asset(path, source_value)


def store_reference(project_dir: Path, descriptor: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_brief_config()
    return workbench_brief.store_reference(project_dir, descriptor)


def merge_new_references(project_dir: Path, brief: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_brief_config()
    return workbench_brief.merge_new_references(project_dir, brief, payload)


def load_concepts(project_dir: Path) -> List[Dict[str, Any]]:
    _sync_workbench_concepts_config()
    return workbench_concepts.load_concepts(project_dir)


def prompt_history_entries(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    _sync_workbench_concepts_config()
    return workbench_concepts.prompt_history_entries(concepts)


def hydrate_concept(concept: Dict[str, Any], fallback_created_at: Optional[str] = None) -> Dict[str, Any]:
    _sync_workbench_concepts_config()
    return workbench_concepts.hydrate_concept(concept, fallback_created_at=fallback_created_at)


def save_concept(project_dir: Path, concept: Dict[str, Any]) -> None:
    _sync_workbench_concepts_config()
    workbench_concepts.save_concept(project_dir, concept)


def next_concept_serial(concepts: List[Dict[str, Any]]) -> int:
    _sync_workbench_concepts_config()
    return workbench_concepts.next_concept_serial(concepts)


def next_prompt_version(concepts: List[Dict[str, Any]]) -> int:
    _sync_workbench_concepts_config()
    return workbench_concepts.next_prompt_version(concepts)


def save_prompt_artifacts(project_dir: Path, prompt_version: int, prompt_text: str) -> Tuple[str, str]:
    _sync_workbench_concepts_config()
    return workbench_concepts.save_prompt_artifacts(project_dir, prompt_version, prompt_text)


def update_concept_validation(project_id: str, concept_id: str, validation_status: str, feedback: Optional[str] = None) -> Dict[str, Any]:
    _sync_workbench_concepts_config()
    return workbench_concepts.update_concept_validation(project_id, concept_id, validation_status, feedback=feedback)


def update_concept_review_state(project_id: str, concept_id: str, action: str, value: Optional[bool]) -> Dict[str, Any]:
    _sync_workbench_concepts_config()
    return workbench_concepts.update_concept_review_state(project_id, concept_id, action, value)


def _concept_image_rel_paths(concept: Dict[str, Any]) -> List[str]:
    _sync_workbench_concepts_config()
    return workbench_concepts._concept_image_rel_paths(concept)


def _delete_concept_disk_artifacts(project_dir: Path, removed: Dict[str, Any], remaining: List[Dict[str, Any]]) -> None:
    _sync_workbench_concepts_config()
    workbench_concepts._delete_concept_disk_artifacts(project_dir, removed, remaining)


def delete_concept(project_id: str, concept_id: str) -> Dict[str, Any]:
    _sync_workbench_concepts_config()
    return workbench_concepts.delete_concept(project_id, concept_id)


def selected_concept(project: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_concepts_config()
    return workbench_concepts.selected_concept(project)


def _pixellab_character_path(project_dir: Path) -> Path:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store._pixellab_character_path(project_dir)


def _normalize_east_only_character_source(
    project_dir: Path,
    char_data: Optional[Dict[str, Any]],
    concepts: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store._normalize_east_only_character_source(project_dir, char_data, concepts)


def _set_pixellab_east_only_character_source(
    project: Dict[str, Any],
    project_dir: Path,
    concept_id: str,
    *,
    approved: bool,
) -> Dict[str, Any]:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store._set_pixellab_east_only_character_source(project, project_dir, concept_id, approved=approved)


def _upscale_legacy_east_only_animation_frames(
    project_dir: Path,
    char_data: Optional[Dict[str, Any]],
    store: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store._upscale_legacy_east_only_animation_frames(project_dir, char_data, store)


def pixellab_character_wizard_complete(project: Dict[str, Any], project_dir: Path) -> bool:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store.pixellab_character_wizard_complete(project, project_dir)


def pixellab_animation_store_has_frames(animations: Any) -> bool:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store.pixellab_animation_store_has_frames(animations)


def pixellab_animations_step_complete(project: Dict[str, Any], project_dir: Path) -> bool:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store.pixellab_animations_step_complete(project, project_dir)


def _pixellab_skeleton_path(project_dir: Path) -> Path:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store._pixellab_skeleton_path(project_dir)


def _pixellab_character_assets_dir(project_dir: Path) -> Path:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store._pixellab_character_assets_dir(project_dir)


def _pixellab_animations_path(project_dir: Path) -> Path:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store._pixellab_animations_path(project_dir)


def _load_pixellab_animations_store(project_dir: Path) -> Dict[str, Any]:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store._load_pixellab_animations_store(project_dir)


def _save_pixellab_animations_store(project_dir: Path, store: Dict[str, Any]) -> None:
    _sync_workbench_pixellab_store_config()
    workbench_pixellab_store._save_pixellab_animations_store(project_dir, store)


def validate_pixellab_animation_name(raw: Any) -> str:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store.validate_pixellab_animation_name(raw)


def _infer_animation_name_from_template(template_animation_id: str) -> str:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store._infer_animation_name_from_template(template_animation_id)


def _upsert_pixellab_animation_frames(
    project_dir: Path,
    store: Dict[str, Any],
    *,
    animation_name: str,
    direction: str,
    frames_paths: List[str],
    fps: int,
    loop: bool,
    seed: Optional[int] = None,
    backend_name: str,
    job_id: Optional[str] = None,
    edited_description: Optional[str] = None,
    frame_count: int,
    template_animation_id: Optional[str] = None,
) -> Dict[str, Any]:
    _sync_workbench_pixellab_store_config()
    return workbench_pixellab_store._upsert_pixellab_animation_frames(
        project_dir,
        store,
        animation_name=animation_name,
        direction=direction,
        frames_paths=frames_paths,
        fps=fps,
        loop=loop,
        seed=seed,
        backend_name=backend_name,
        job_id=job_id,
        edited_description=edited_description,
        frame_count=frame_count,
        template_animation_id=template_animation_id,
    )


def get_room_layout(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    return copy.deepcopy(project.get("room_layout") or default_room_layout(project_id, project.get("project_name") or "Untitled Project"))


def save_room_layout(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Room layout payload must be a JSON object.")
    validation = validate_room_layout(payload)
    if validation["status"] == "fail":
        raise ValueError("Room layout is invalid: %s" % "; ".join(validation["errors"][:4]))

    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    room_layout = copy.deepcopy(payload)
    room_layout.setdefault("meta", {})
    room_layout["meta"]["project_id"] = project_id
    room_layout["meta"]["project_name"] = project.get("project_name") or project_id
    room_layout["meta"]["updated_at"] = now_iso()
    room_layout.setdefault("version", 1)

    history_payload = project.get("room_layout_history") or default_room_layout_history(project_id, room_layout)
    revisions = history_payload.setdefault("revisions", [])
    revision_id = "room-layout-%s" % uuid.uuid4().hex[:8]
    revisions.append({
        "revision_id": revision_id,
        "created_at": now_iso(),
        "summary": "Saved room layout",
        "room_count": len(room_layout.get("rooms") or []),
    })
    history_payload["current_revision_id"] = revision_id
    history_payload["project_id"] = project_id

    validation_payload = dict(validation)
    validation_payload["project_id"] = project_id

    project["room_layout"] = room_layout
    project["room_layout_history"] = history_payload
    project["level_validation_report"] = validation_payload
    project["updated_at"] = now_iso()
    project["status"] = "room_layout_saved"
    save_project(project)
    append_history_event(project_id, {
        "type": "room_layout_saved",
        "summary": "Saved room layout",
        "room_count": len(room_layout.get("rooms") or []),
        "revision_id": revision_id,
        "created_at": now_iso(),
    })
    return {
        "ok": True,
        "project_id": project_id,
        "room_layout_path": str(room_layout_path(project_dir).relative_to(project_dir)),
        "validation": validation_payload,
        "history_revision_id": revision_id,
    }


def check_state(status: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _sync_workbench_export_config()
    return workbench_export.check_state(status, details)


def aggregate_check_state(states: List[str]) -> str:
    _sync_workbench_export_config()
    return workbench_export.aggregate_check_state(states)


def approved_manual_animation_clips(project: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    _sync_workbench_export_config()
    return workbench_export.approved_manual_animation_clips(project)


def run_external_authoring_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_export_config()
    return workbench_export.run_external_authoring_qa(project_id, progress=progress)


def run_ai_workflow_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_export_config()
    return workbench_export.run_ai_workflow_qa(project_id, progress=progress)


def ai_workflow_ready_for_qa(store: Dict[str, Any]) -> bool:
    _sync_workbench_export_config()
    return workbench_export.ai_workflow_ready_for_qa(store)


def pixellab_pipeline_ready_for_qa(project: Dict[str, Any], project_dir: Path) -> bool:
    _sync_workbench_export_config()
    return workbench_export.pixellab_pipeline_ready_for_qa(project, project_dir)


def run_pixellab_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_export_config()
    return workbench_export.run_pixellab_qa(project_id, progress=progress)


def run_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_export_config()
    return workbench_export.run_qa(project_id, progress=progress)


def validate_export_bundle(
    export_dir: Path,
    ordered_frames: List[Tuple[str, str, Path]],
    atlas_frames: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    _sync_workbench_export_config()
    return workbench_export.validate_export_bundle(export_dir, ordered_frames, atlas_frames)


def _pixellab_qa_clip_names(clips: Dict[str, Any]) -> List[str]:
    _sync_workbench_export_config()
    return workbench_export._pixellab_qa_clip_names(clips)


def _write_per_animation_preview_gifs(
    export_dir: Path,
    ordered_frames: List[Tuple[str, str, Path]],
    fps_for_animation: Callable[[str], int],
) -> List[str]:
    _sync_workbench_export_config()
    return workbench_export._write_per_animation_preview_gifs(export_dir, ordered_frames, fps_for_animation)


def _write_preview_spritesheet(spritesheet: Image.Image, export_dir: Path) -> None:
    _sync_workbench_export_config()
    workbench_export._write_preview_spritesheet(spritesheet, export_dir)


def _write_per_animation_spritesheets(
    export_dir: Path,
    ordered_frames: List[Tuple[str, str, Path]],
    animations_payload: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    _sync_workbench_export_config()
    return workbench_export._write_per_animation_spritesheets(export_dir, ordered_frames, animations_payload)


def export_pixellab_project(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_export_config()
    return workbench_export.export_pixellab_project(project_id, progress=progress)


def export_project(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_export_config()
    return workbench_export.export_project(project_id, progress=progress)


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


def validate_project_room_layout(project_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    room_layout = payload if isinstance(payload, dict) and payload else (project.get("room_layout") or default_room_layout(project_id, project.get("project_name") or "Untitled Project"))
    validation = validate_room_layout(room_layout)
    validation["project_id"] = project_id
    return validation


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
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.apply_project_defaults(project)


def default_wizard_state() -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.default_wizard_state()


def normalize_wizard_state(payload: Any) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.normalize_wizard_state(payload)


def migrate_modern_ai_wizard_state(state: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.migrate_modern_ai_wizard_state(state)


def set_wizard_step_complete(state: Dict[str, Any], step: str) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.set_wizard_step_complete(state, step)


def set_wizard_optional_step_skipped(state: Dict[str, Any], step: str) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.set_wizard_optional_step_skipped(state, step)


def animation_render_complete(project_dir: Path, animation_name: str) -> bool:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.animation_render_complete(project_dir, animation_name)


def canonical_downstream_path(project_dir: Path, key: str) -> Path:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.canonical_downstream_path(project_dir, key)


def legacy_downstream_path(project_dir: Path, key: str) -> Path:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.legacy_downstream_path(project_dir, key)


def default_sprite_model_history(project_id: str) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.default_sprite_model_history(project_id)


def default_manual_animation_clips(project_id: str) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.default_manual_animation_clips(project_id)


def default_ai_dependency_status() -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.default_ai_dependency_status()


def default_ai_workflow(project_id: str) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.default_ai_workflow(project_id)


def hydrate_ai_workflow(store: Any, project: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.hydrate_ai_workflow(store, project, project_dir)


def serialize_ai_workflow(store: Any, project_id: str) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.serialize_ai_workflow(store, project_id)


def ai_workflow_root(project_dir: Path, stage: str, clip_name: Optional[str] = None, run_id: Optional[str] = None) -> Path:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.ai_workflow_root(project_dir, stage, clip_name=clip_name, run_id=run_id)


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
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.default_external_authoring(project_id)


def hydrate_external_authoring(store: Any, project_dir: Path) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.hydrate_external_authoring(store, project_dir)


def serialize_external_authoring(store: Any, project_id: str) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.serialize_external_authoring(store, project_id)


def external_authoring_import_root(project_dir: Path) -> Path:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.external_authoring_import_root(project_dir)


def manual_clip_render_root(project_dir: Path) -> Path:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.manual_clip_render_root(project_dir)


def manual_clip_source_hashes(project_dir: Path) -> Dict[str, Optional[str]]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.manual_clip_source_hashes(project_dir)


def manual_clip_frame_count(value: Any, default: int = 8) -> int:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.manual_clip_frame_count(value, default=default)


def normalize_manual_clip_frame(frame: Any) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.normalize_manual_clip_frame(frame)


def normalize_manual_frame_repairs(value: Any) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.normalize_manual_frame_repairs(value)


def normalize_manual_frame_patches(value: Any) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.normalize_manual_frame_patches(value)


def normalize_manual_clip_frame_entry(frame: Any) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.normalize_manual_clip_frame_entry(frame)


def manual_clip_frame_transforms(frame: Any) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.manual_clip_frame_transforms(frame)


def blank_manual_clip_frames(frame_count: int) -> List[Dict[str, Any]]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.blank_manual_clip_frames(frame_count)


def default_manual_clip(project_dir: Path, clip_id: str, clip_name: str, frame_count: int = 8, fps: int = 12, loop: bool = True) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.default_manual_clip(project_dir, clip_id, clip_name, frame_count=frame_count, fps=fps, loop=loop)


def invalidate_manual_clip_preview(clip: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.invalidate_manual_clip_preview(clip)


def normalize_manual_clip(project_dir: Path, clip_id: str, payload: Any) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.normalize_manual_clip(project_dir, clip_id, payload)


def hydrate_manual_animation_clips(store: Any, project_dir: Path) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.hydrate_manual_animation_clips(store, project_dir)


def serialize_manual_animation_clips(store: Any, project_id: str) -> Dict[str, Any]:
    _sync_workbench_workflow_state_config()
    return workbench_workflow_state.serialize_manual_animation_clips(store, project_id)

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
        wizard_state = migrate_modern_ai_wizard_state(wizard_state)
        completed = set(wizard_state.get("completed_steps", []))
        skipped = set(wizard_state.get("skipped_optional_steps", []))

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

        pixellab_character_ready = pixellab_character_wizard_complete(project, project_dir) if pixellab_brief else approved_cleanup_ready

        has_brief = "describe" in completed or "brief" in completed or bool((project.get("prompt_text") or "").strip())
        has_references = bool(brief.get("references")) or "references" in skipped or has_brief
        has_concepts = bool(project.get("prompt_history")) or bool(imported_attempts)
        has_review = bool(project.get("selected_concept_id"))
        concept_path_ready = bool(project.get("selected_concept_id"))
        has_character_lock = bool(character_lock.get("approved_asset_id")) or concept_path_ready
        has_key_pose_set = bool(key_pose_set.get("approved_run_id")) or concept_path_ready
        has_export = bool(project.get("last_export"))

        animations_complete = pixellab_animations_step_complete(project, project_dir) if pixellab_brief else True
        describe_complete = has_brief
        concepts_complete = has_review and (pixellab_character_ready if pixellab_brief else True)
        export_complete = has_export

        steps_seq = wizard_steps_active(project)
        complete_map: Dict[str, bool] = {
            "describe": describe_complete,
            "concepts": concepts_complete,
            "export": export_complete,
        }
        if pixellab_brief:
            complete_map["animations"] = animations_complete

        export_prereq_met = concepts_complete and (not pixellab_brief or animations_complete)

        concepts_blocker_msg = (
            "Approve a valid concept to lock it as the animation source."
            if pixellab_brief
            else "Approve a Key Pose Board before running Motion Workflow."
        )
        qa_blocker_msg_non_pl = "Approve cleaned idle and walk outputs before review and export."
        export_blocker_msg_pl = (
            "Generate at least one animation before review and export."
        )
        blocking_reasons: Dict[str, List[str]] = {
            "describe": [],
            "concepts": [] if describe_complete else ["Save the character description before building concepts."],
            "export": (
                []
                if export_prereq_met
                else ([export_blocker_msg_pl] if pixellab_brief else [qa_blocker_msg_non_pl])
            ),
        }
        if pixellab_brief:
            blocking_reasons["animations"] = (
                [] if concepts_complete else [concepts_blocker_msg]
            )

        step_statuses: Dict[str, str] = {}
        active_step = None
        for step in steps_seq:
            blockers = blocking_reasons.get(step, [])
            is_complete = complete_map.get(step, False)
            if is_complete:
                step_statuses[step] = "complete"
                continue
            if blockers:
                step_statuses[step] = "locked"
                continue
            if active_step is None:
                step_statuses[step] = "active"
                active_step = step
            else:
                step_statuses[step] = "ready"

        if project.get("qa_report") and not export_complete:
            if project["qa_report"].get("status") != "pass":
                step_statuses["export"] = "attention"
                active_step = "export"

        recommended_next_step = active_step or "export"
        persisted_step = wizard_state.get("current_step")
        persisted_ok = persisted_step in WIZARD_STEPS_KNOWN and step_statuses.get(persisted_step) in {
            "active",
            "ready",
            "attention",
            "complete",
        }
        if persisted_ok:
            recommended_next_step = persisted_step
        wizard_state["current_step"] = persisted_step if persisted_ok else recommended_next_step
        for step_name in steps_seq:
            if complete_map.get(step_name):
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
        "qa": [] if complete_map["clips"] else ["Render the required clips before running checks, or import a SkelForm bundle."],
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
        if is_complete:
            step_statuses[step] = "complete"
            continue
        if blockers:
            step_statuses[step] = "locked"
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
    persisted_ok = persisted_step in WIZARD_STEPS_KNOWN and step_statuses.get(persisted_step) in {
        "active",
        "ready",
        "attention",
        "complete",
    }
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


















































GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"




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


def _is_pixellab_api_url(url: str) -> bool:
    """True when the URL points to the Pixel Lab API (not a CDN / object-storage host)."""
    try:
        host = url.split("//", 1)[1].split("/", 1)[0].split(":")[0].lower()
    except (IndexError, ValueError):
        return False
    return host == "api.pixellab.ai"


def _download_url_bytes(url: str, *, bearer: Optional[str] = None, timeout: int = 90) -> bytes:
    headers = {
        "User-Agent": "MV-sprite-workbench/1.0 (Pixel Lab asset fetch)",
        "Accept": "image/png,image/webp,image/jpeg,image/*;q=0.9,*/*;q=0.5",
    }
    # Only send the Pixel Lab Bearer token to the Pixel Lab API itself.
    # CDN / object-storage hosts (Backblaze B2, Supabase, etc.) reject foreign
    # Authorization headers with 401, so skip Bearer for those URLs upfront.
    use_bearer = bearer and _is_pixellab_api_url(url)
    if use_bearer:
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


def _pixellab_character_requires_template_generation_guard(char_data: Dict[str, Any]) -> None:
    if char_data.get("character_id"):
        return
    if char_data.get("east_only_source"):
        raise ValueError(
            "This character is using the approved concept as an east-only source image. "
            "Pixel Lab template animations require Create Character (4 dir) or Create Character (8 dir)."
        )
    raise ValueError("Pixel Lab template animations require a generated Pixel Lab character_id.")


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
    """Collect https URLs from nested job payloads (e.g. signed frame CDN links).

    Pixel Lab v2 animation jobs often put frame files in ``storage_urls`` (list of strings or
    nested dicts) rather than ``url`` / inline base64. Also scans common alternate keys.
    """
    urls: List[str] = []

    def append_if_url(s: Any) -> None:
        if isinstance(s, str):
            t = s.strip().split("#")[0]
            if t.startswith("http://") or t.startswith("https://"):
                urls.append(t)

    def walk_url_container(val: Any) -> None:
        """Walk list/dict/string shapes used for URL batches (``storage_urls``, etc.)."""
        if val is None:
            return
        if isinstance(val, str):
            append_if_url(val)
            return
        if isinstance(val, list):
            for item in val:
                walk_url_container(item)
            return
        if isinstance(val, dict):
            for v in val.values():
                walk_url_container(v)

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for key in (
                "url",
                "signed_url",
                "image_url",
                "href",
                "storage_url",
                "public_url",
                "cdn_url",
                "download_url",
                "frame_url",
                "presigned_url",
            ):
                append_if_url(o.get(key))
            for bulk_key in (
                "storage_urls",
                "StorageUrls",
                "frame_urls",
                "download_urls",
                "quantized_storage_urls",
            ):
                if bulk_key in o:
                    walk_url_container(o.get(bulk_key))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            append_if_url(o)

    walk(payload)
    return list(dict.fromkeys(urls))


def _pixellab_frame_source_counts(result: Any) -> Tuple[int, int]:
    """Counts of base64-like image strings and https URLs visible in nested JSON (before decode)."""
    return (
        len(_find_all_base64_png_like(result)),
        len(_collect_pixellab_https_asset_urls(result)),
    )


def _collect_rgba_bytes_frames(payload: Any) -> List[Dict[str, Any]]:
    """Collect all ``{"type": "rgba_bytes", "width": W, "height": H, "base64": "..."}`` dicts."""
    found: List[Dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if str(value.get("type") or "").lower() == "rgba_bytes":
                if isinstance(value.get("base64"), str) and value.get("width") and value.get("height"):
                    found.append(value)
                    return
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return found


def _decode_rgba_bytes_frame(frame_obj: Dict[str, Any], target_size: Tuple[int, int]) -> Image.Image:
    """Decode a ``rgba_bytes`` frame dict to an RGBA PIL Image, resized to ``target_size``."""
    import base64 as _base64
    w = int(frame_obj["width"])
    h = int(frame_obj["height"])
    raw = _base64.b64decode(frame_obj["base64"])
    img = Image.frombytes("RGBA", (w, h), raw)
    if (w, h) != target_size:
        img = img.resize(target_size, Image.NEAREST)
    return img


def _pixellab_decode_single_animation_payload_to_frames(
    result: Any,
    *,
    canvas_size: int,
    client: Any,
) -> List[Image.Image]:
    """Decode frames from one job ``last_response`` blob (base64 and/or downloadable URLs)."""
    rgba: Tuple[int, int] = (int(canvas_size), int(canvas_size))
    # Diagnostic: log the shape of images / quantized_images so we can debug decode failures.
    if isinstance(result, dict):
        _log_pixellab_job_images_shape(result, 0)
        imgs = result.get("images")
        if isinstance(imgs, list) and imgs:
            first = imgs[0]
            logger.info(
                "[pixellab/decode] images[0] raw=%r",
                repr(first)[:300] if not isinstance(first, str) else ("str(len=%d head=%r)" % (len(first), first[:80])),
            )
    decoded: List[Image.Image] = []
    # Handle Pixel Lab v2 rgba_bytes format: prefer canonical ``images`` frames and
    # only fall back to ``quantized_images`` if ``images`` are absent.
    rgba_payloads: List[Tuple[str, Any]] = []
    if isinstance(result, dict):
        rgba_payloads.append(("images", result.get("images")))
        rgba_payloads.append(("quantized_images", result.get("quantized_images")))
    rgba_payloads.append(("payload", result))
    seen_sources: Set[str] = set()
    for label, payload in rgba_payloads:
        if label in seen_sources:
            continue
        seen_sources.add(label)
        rgba_frames = _collect_rgba_bytes_frames(payload)
        if not rgba_frames:
            continue
        logger.info("[pixellab/decode] using %d rgba_bytes frames from %s", len(rgba_frames), label)
        for frame_obj in rgba_frames:
            try:
                decoded.append(_decode_rgba_bytes_frame(frame_obj, rgba))
            except Exception as exc:
                logger.warning("[pixellab/decode] rgba_bytes decode failed: %s", exc)
        if decoded:
            return decoded
    for s in _find_all_base64_png_like(result):
        try:
            decoded.append(_decode_base64_image_to_rgba(s, rgba_size=rgba))
        except Exception as exc:
            logger.debug("[pixellab/decode] base64 decode failed: %s", exc)
            continue
    if decoded:
        return decoded
    bearer = getattr(client, "api_key", None) if client is not None else None
    asset_urls = _collect_pixellab_https_asset_urls(result)[:128]
    if asset_urls:
        logger.info("[pixellab/decode] attempting %d URL downloads (no base64 found)", len(asset_urls))
    for idx, url in enumerate(asset_urls):
        try:
            raw = _download_url_bytes(url, bearer=bearer)
            decoded.append(
                _pixellab_open_image_bytes(
                    raw,
                    where="Pixel Lab animation frame URL",
                    rgba_size=rgba,
                )
            )
        except Exception as exc:
            logger.warning(
                "[pixellab/decode] URL %d/%d download/decode failed url=%s error=%s",
                idx + 1, len(asset_urls), url[:120], exc,
            )
            continue
    return decoded


def _log_pixellab_job_images_shape(part: Dict[str, Any], idx: int) -> None:
    """Log the shape/type of the ``images``, ``storage_urls``, and ``quantized_images`` fields for debugging."""
    for key in ("images", "quantized_images", "storage_urls"):
        val = part.get(key)
        if val is None:
            continue
        if isinstance(val, list):
            samples = []
            for i, item in enumerate(val[:3]):
                if isinstance(item, dict):
                    item_type = item.get("type")
                    b64_head = None
                    for bkey in ("base64", "b64", "data", "url"):
                        bval = item.get(bkey)
                        if isinstance(bval, str) and bval:
                            b64_head = "%s=%r" % (bkey, bval[:60])
                            break
                    samples.append("dict(keys=%s type=%r %s)" % (sorted(item.keys()), item_type, b64_head or ""))
                elif isinstance(item, str):
                    samples.append("str(len=%d, head=%r)" % (len(item), item[:80]))
                else:
                    samples.append(type(item).__name__)
            logger.info(
                "[pixellab/decode] job[%d].%s is list[%d] samples=%s",
                idx, key, len(val), samples,
            )
        elif isinstance(val, dict):
            logger.info(
                "[pixellab/decode] job[%d].%s is dict(keys=%s)",
                idx, key, sorted(val.keys())[:10],
            )
        elif isinstance(val, str):
            logger.info(
                "[pixellab/decode] job[%d].%s is str(len=%d, head=%r)",
                idx, key, len(val), val[:80],
            )
        else:
            logger.info(
                "[pixellab/decode] job[%d].%s is %s",
                idx, key, type(val).__name__,
            )


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
            for part_idx, part in enumerate(merged):
                if isinstance(part, dict):
                    _log_pixellab_job_images_shape(part, part_idx)
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















def wizard_steps_active(project: Dict[str, Any]) -> List[str]:
    """
    Wizard step order. Legacy (non-AI or legacy_mode) uses full WIZARD_STEPS.
    Modern AI uses Phase 7.7 simplified steps (describe → … → export).
    """
    ai_workflow = project.get("ai_workflow") or {}
    ai_enabled = bool(ai_workflow.get("enabled")) and not bool(ai_workflow.get("legacy_mode"))
    brief = project.get("brief") or {}
    pixellab_brief = str(brief.get("backend_mode") or "") == "pixellab"
    if ai_enabled:
        if pixellab_brief:
            return list(WIZARD_STEPS_PIXEL_LAB_UI)
        return list(WIZARD_STEPS_AI_SIMPLE_UI)
    return list(WIZARD_STEPS)












PIXELLAB_CORE_ANIMATION_NAMES = frozenset({"idle", "walk", "run", "jump"})
PIXELLAB_DEFAULT_CLIP_TIMINGS = {
    "idle": {"frame_count": 6, "fps": 8},
    "walk": {"frame_count": 8, "fps": 10},
    "run": {"frame_count": 8, "fps": 14},
    "jump": {"frame_count": 6, "fps": 12},
}
_PIXELLAB_ANIMATION_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")






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
        fps = (PIXELLAB_DEFAULT_CLIP_TIMINGS.get(animation_name) or AI_CLIP_SPECS.get(animation_name) or ANIMATION_SPECS.get(animation_name) or {}).get("fps")
    if frame_count is None:
        frame_count = (PIXELLAB_DEFAULT_CLIP_TIMINGS.get(animation_name) or AI_CLIP_SPECS.get(animation_name) or ANIMATION_SPECS.get(animation_name) or {}).get("frame_count")

    if frame_count is None and template_animation_id:
        frame_count = _infer_frame_count_from_template(template_animation_id)

    fps = int(fps or 12)
    frame_count = int(frame_count or 8)

    return {"fps": fps, "frame_count": frame_count, "loop": loop}


def chunk_frame_indices(frame_count: int, batch_size: int = 4) -> List[List[int]]:
    total = max(0, int(frame_count))
    size = max(1, int(batch_size))
    return [list(range(start, min(total, start + size))) for start in range(0, total, size)]


def _write_png_frames(frames: List[Image.Image], project_dir: Path, animation_name: str, direction: str) -> List[str]:
    frames_dir = _pixellab_animation_frames_dir(project_dir, animation_name, direction)
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_paths: List[str] = []
    for idx, img in enumerate(frames):
        path = frames_dir / ("frame_%02d.png" % int(idx))
        img.save(path)
        frame_paths.append(path.relative_to(project_dir).as_posix())
    return frame_paths




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
        "backend_mode": normalize_brief_backend_mode(
            payload.get("backend_mode")
            if payload.get("backend_mode") is not None and str(payload.get("backend_mode")).strip() != ""
            else (
                source.get("backend_mode")
                if source.get("backend_mode") is not None and str(source.get("backend_mode")).strip() != ""
                else "pixellab"
            )
        ),
        "comfyui_checkpoint": payload.get("comfyui_checkpoint") if "comfyui_checkpoint" in payload else source.get("comfyui_checkpoint"),
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
















def image_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
    return "data:%s;base64,%s" % (mime_type, base64.b64encode(path.read_bytes()).decode("ascii"))


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


def run_gemini_concept_validation(
    _project: Dict[str, Any],
    _concept: Dict[str, Any],
    validation_path: Path,
) -> Dict[str, Any]:
    """
    Local mechanical validation for imported concepts (Phase 8: external Gemini API removed).

    Uses the same heuristics as concept triage (``analyze_concept_image``). Creative judgment
    is left to the author; ``invalid`` means the image failed basic extraction-readiness checks.
    """
    analysis = analyze_concept_image(validation_path)
    status = analysis.get("status")
    flags = analysis.get("flags") or []
    if status in ("ok", "warning"):
        return {
            "decision": "valid",
            "summary": "Passed local mechanical checks (no external validation API).",
            "feedback": "",
            "improved_gemini_prompt": None,
            "master_pose_ready": True,
            "technical_requirements_ok": True,
            "response_id": None,
        }
    feedback_bits = [str(f) for f in flags if f]
    feedback = (
        "Image failed local mechanical readiness checks (%s). "
        "Tighten side profile, simplify background, or increase subject clarity." % ", ".join(feedback_bits or ["see metrics"])
    )
    improved = (
        "strict side-view full-body humanoid, one character, plain removable background, "
        "clean silhouette, readable limbs and held item, sprite extraction source framing"
    )
    return {
        "decision": "invalid",
        "summary": "Failed local mechanical checks for sprite extraction.",
        "feedback": feedback,
        "improved_gemini_prompt": improved,
        "master_pose_ready": False,
        "technical_requirements_ok": False,
        "response_id": None,
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


def prepare_pixellab_concept_init_image(raw: bytes, canvas_size: int) -> Image.Image:
    loaded = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGBA")
    return fit_image(loaded, (canvas_size, canvas_size), (0, 0, 0, 0))


def prepare_pixellab_character_color_source(source_path: Path, canvas_size: int) -> Image.Image:
    source = Image.open(source_path).convert("RGBA")
    cropped, _, _ = clean_source_subject(source)
    return fit_image(cropped, (canvas_size, canvas_size), (0, 0, 0, 0))


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
    _sync_workbench_external_authoring_config()
    return workbench_external_authoring.get_external_authoring(project_id)


def update_external_authoring(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_external_authoring_config()
    return workbench_external_authoring.update_external_authoring(project_id, payload)


def open_external_authoring_session(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_external_authoring_config()
    return workbench_external_authoring.open_external_authoring_session(project_id, payload)


def import_external_authoring_bundle(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_external_authoring_config()
    return workbench_external_authoring.import_external_authoring_bundle(project_id, payload)


def ai_workflow_or_error(project: Dict[str, Any]) -> Dict[str, Any]:
    store = project.get("ai_workflow")
    if not isinstance(store, dict):
        raise ValueError("AI workflow state is missing for this project.")
    if store.get("legacy_mode"):
        raise ValueError("This project is in read-only legacy mode. Create a new project to use ai_sideview_v1.")
    if not store.get("enabled"):
        raise ValueError("AI workflow is not enabled for this project.")
    return store


def ai_workflow_health_snapshot(backend_mode: str = "debug_procedural") -> Dict[str, Any]:
    """Dependency snapshot for the guided AI workflow (ComfyUI integration removed in Phase 8)."""
    mode = normalize_brief_backend_mode(backend_mode)
    detail = (
        "debug_procedural offline path"
        if mode == "debug_procedural"
        else "Pixel Lab pipeline (legacy Comfy stack not used)"
    )
    dependencies = {
        "comfyui": {"status": "pass", "detail": "ComfyUI removed; AI workflow uses offline procedural paths"},
        "photomaker": {"status": "pass", "detail": detail},
        "ipadapter_plus": {"status": "pass", "detail": detail},
        "tooncrafter": {"status": "pass", "detail": detail},
        "anime_segmentation": {"status": "pass", "detail": detail},
        "pixelart_cleanup": {"status": "pass", "detail": detail},
    }
    return {
        "generated_at": now_iso(),
        "workflow_profile": AI_WORKFLOW_PROFILE,
        "overall_status": "pass",
        "dependencies": dependencies,
        "backend_mode": mode,
    }


def refresh_ai_workflow_dependency_status(project: Dict[str, Any], persist: bool = False) -> Dict[str, Any]:
    store = ai_workflow_or_error(project)
    backend_mode = brief_backend_mode(project.get("brief"))
    store["dependency_status"] = ai_workflow_health_snapshot(backend_mode)
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    if persist:
        project["updated_at"] = now_iso()
        save_project(project)
    return store["dependency_status"]


def get_ai_workflow(project_id: str) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime.get_ai_workflow(project_id)


def _ai_find_key_pose_run(store: Dict[str, Any], run_id: str) -> Optional[Dict[str, Any]]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime._ai_find_key_pose_run(store, run_id)


def _ai_motion_group(store: Dict[str, Any], group_name: str, clip_name: str) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime._ai_motion_group(store, group_name, clip_name)


def _ai_render_manifest_for_frames(clip_name: str, frame_names: List[str]) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime._ai_render_manifest_for_frames(clip_name, frame_names)


def run_ai_character_lock(project_id: str, workflow_profile: str, source_asset_ids: List[str], parameters: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime.run_ai_character_lock(project_id, workflow_profile, source_asset_ids, parameters, progress=progress)


def run_ai_key_pose_set(project_id: str, workflow_profile: str, source_asset_ids: List[str], parameters: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime.run_ai_key_pose_set(project_id, workflow_profile, source_asset_ids, parameters, progress=progress)


def _ai_key_pose_lookup(run: Dict[str, Any]) -> Dict[str, Image.Image]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime._ai_key_pose_lookup(run)


def _ai_synthetic_key_pose_run_from_selected_concept(project: Dict[str, Any], project_dir: Path) -> Optional[Dict[str, Any]]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime._ai_synthetic_key_pose_run_from_selected_concept(project, project_dir)


def run_ai_motion_clip(project_id: str, workflow_profile: str, clip_name: str, source_asset_ids: List[str], parameters: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime.run_ai_motion_clip(project_id, workflow_profile, clip_name, source_asset_ids, parameters, progress=progress)


def run_ai_extract_frames(project_id: str, workflow_profile: str, clip_name: str, source_asset_ids: List[str], parameters: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime.run_ai_extract_frames(project_id, workflow_profile, clip_name, source_asset_ids, parameters, progress=progress)


def run_ai_pixel_cleanup(project_id: str, workflow_profile: str, clip_name: str, source_asset_ids: List[str], parameters: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime.run_ai_pixel_cleanup(project_id, workflow_profile, clip_name, source_asset_ids, parameters, progress=progress)


def run_ai_workflow_stage(project_id: str, payload: Dict[str, Any], progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime.run_ai_workflow_stage(project_id, payload, progress=progress)


def approve_ai_workflow(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime.approve_ai_workflow(project_id, payload)


def reject_ai_workflow(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_ai_workflow_runtime_config()
    return workbench_ai_workflow_runtime.reject_ai_workflow(project_id, payload)


def make_character_spec(project: Dict[str, Any], concept: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.make_character_spec(project, concept)


def get_rig_layout(project_id: str) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.get_rig_layout(project_id)


def generate_rig_layout(project_id: str) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.generate_rig_layout(project_id)


def update_rig_layout(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.update_rig_layout(project_id, payload)


def approve_rig_layout(project_id: str) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.approve_rig_layout(project_id)


def build_part_manifest_handoff_prompt(project: Dict[str, Any], part_manifest: Optional[Dict[str, Any]] = None) -> str:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.build_part_manifest_handoff_prompt(project, part_manifest=part_manifest)


def build_part_shapes_handoff_prompt(project: Dict[str, Any], part_shapes: Optional[Dict[str, Any]] = None) -> str:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.build_part_shapes_handoff_prompt(project, part_shapes=part_shapes)


def get_part_manifest(project_id: str) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.get_part_manifest(project_id)


def get_part_shapes(project_id: str) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.get_part_shapes(project_id)


def generate_part_manifest(project_id: str) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.generate_part_manifest(project_id)


def update_part_manifest(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.update_part_manifest(project_id, payload)


def approve_part_manifest(project_id: str) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.approve_part_manifest(project_id)


def initialize_part_shapes(project_id: str) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.initialize_part_shapes(project_id)


def refresh_part_shape_assets(project_id: str, part_shapes: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.refresh_part_shape_assets(project_id, part_shapes)


def update_part_shapes(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.update_part_shapes(project_id, payload)


def approve_part_shapes(project_id: str) -> Dict[str, Any]:
    _sync_workbench_rig_parts_config()
    return workbench_rig_parts.approve_part_shapes(project_id)


def build_split_from_part_shapes(project_id: str) -> Dict[str, Any]:
    _sync_workbench_part_split_config()
    return workbench_part_split.build_split_from_part_shapes(project_id)


def build_part_split_handoff_prompt(project: Dict[str, Any], part_split: Optional[Dict[str, Any]] = None) -> str:
    _sync_workbench_part_split_config()
    return workbench_part_split.build_part_split_handoff_prompt(project, part_split=part_split)


def get_part_split(project_id: str) -> Dict[str, Any]:
    _sync_workbench_part_split_config()
    return workbench_part_split.get_part_split(project_id)


def generate_part_split(project_id: str) -> Dict[str, Any]:
    _sync_workbench_part_split_config()
    return workbench_part_split.generate_part_split(project_id)


def update_part_split(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_part_split_config()
    return workbench_part_split.update_part_split(project_id, payload)


def approve_part_split(project_id: str) -> Dict[str, Any]:
    _sync_workbench_part_split_config()
    return workbench_part_split.approve_part_split(project_id)






_CONCEPT_ARTIFACT_IMAGE_KEYS = (
    "preview_image",
    "processed_preview_image",
    "original_preview_image",
    "approved_source_image",
)








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
        "backend_mode": brief_backend_mode(project.get("brief")),
        "candidates": [],
        "approved_candidate_id": None,
        "approved_image": None,
    }

    prompt_suffixes = [
        "strict side-view master pose, clean silhouette, plain background, neutral stance, extraction-ready sprite source",
        "strict side-view master pose, full-body clean profile, plain removable background, readable silhouette, animation-ready stance",
        "strict side-view master pose, clean silhouette overlap, plain background, stable anatomy, source image for sprite extraction",
    ]

    for index in range(MASTER_POSE_COUNT):
        candidate_id = "master-pose-%02d" % (index + 1)
        output_path = master_pose_dir / ("master_pose_%02d.png" % (index + 1))
        call_progress(progress, 16 + index * 22, "Generating master pose %d of %d" % (index + 1, MASTER_POSE_COUNT), prompt_suffixes[index])
        candidate_meta = local_master_pose_candidate(concept_path, output_path, index, concept["palette"]["outline"])
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


def append_sprite_model_history(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.append_sprite_model_history(*args, **kwargs)


def load_sprite_model(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.load_sprite_model(*args, **kwargs)


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
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.restore_sprite_model_revision(project_id, revision_id)


def undo_last_sprite_model_change(project_id: str) -> Dict[str, Any]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.undo_last_sprite_model_change(project_id)


def write_part_asset(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.write_part_asset(*args, **kwargs)


def load_part_asset(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.load_part_asset(*args, **kwargs)


def color_luminance(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.color_luminance(*args, **kwargs)


def extract_palette(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.extract_palette(*args, **kwargs)


def estimate_facing_direction(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.estimate_facing_direction(*args, **kwargs)


def region_box(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.region_box(*args, **kwargs)


def crop_region_from_source(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.crop_region_from_source(*args, **kwargs)


def fallback_part_entry(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.fallback_part_entry(*args, **kwargs)


def shade_part_image(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.shade_part_image(*args, **kwargs)


def clone_part_entry(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.clone_part_entry(*args, **kwargs)


def part_pivot_from_image(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.part_pivot_from_image(*args, **kwargs)


def validate_sprite_model(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.validate_sprite_model(*args, **kwargs)


def build_sprite_model(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.build_sprite_model(project_id, progress)


def sort_sprite_model_parts(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.sort_sprite_model_parts(*args, **kwargs)


def save_sprite_model_bundle(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.save_sprite_model_bundle(*args, **kwargs)


def replace_part_pixels_with_mask(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.replace_part_pixels_with_mask(*args, **kwargs)


def rotate_part_asset(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.rotate_part_asset(*args, **kwargs)


def scale_part_asset(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.scale_part_asset(*args, **kwargs)


def parse_mask_input(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.parse_mask_input(*args, **kwargs)


def normalize_outline_operation(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.normalize_outline_operation(*args, **kwargs)


def apply_palette_mapping(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.apply_palette_mapping(*args, **kwargs)


def update_sprite_model(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.update_sprite_model(project_id, payload)


def recover_sprite_model_occlusion(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.recover_sprite_model_occlusion(project_id, payload)


def promote_sprite_model_recovery_variant(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.promote_sprite_model_recovery_variant(project_id, payload)


def hex_to_rgba(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.hex_to_rgba(*args, **kwargs)


def base_joint_positions(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.base_joint_positions(*args, **kwargs)


def composite_part(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.composite_part(*args, **kwargs)


def is_pixel_art_rig_profile(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.is_pixel_art_rig_profile(*args, **kwargs)


def quantize_pixel_part_rotation(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.quantize_pixel_part_rotation(*args, **kwargs)


def cleanup_frame(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.cleanup_frame(*args, **kwargs)


def border_has_alpha(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.border_has_alpha(*args, **kwargs)






def world_pivot(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.world_pivot(*args, **kwargs)


def vector_between(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.vector_between(*args, **kwargs)


def rotate_vector(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.rotate_vector(*args, **kwargs)


def add_points(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.add_points(*args, **kwargs)


def build_joint_map_from_sprite_model(sprite_model: Dict[str, Any]) -> Dict[str, List[float]]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.build_joint_map_from_sprite_model(sprite_model)


def build_joint_vectors(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.build_joint_vectors(*args, **kwargs)


def clip_root_motion_policy(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.clip_root_motion_policy(*args, **kwargs)


def default_clip_controls(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.default_clip_controls(*args, **kwargs)


def normalize_clip_controls(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.normalize_clip_controls(*args, **kwargs)


def clip_frame_overrides(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.clip_frame_overrides(*args, **kwargs)


def apply_frame_overrides(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.apply_frame_overrides(*args, **kwargs)


def synthesize_clip_controls(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.synthesize_clip_controls(*args, **kwargs)


def legacy_clip_frame_to_joint_frame(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.legacy_clip_frame_to_joint_frame(*args, **kwargs)


def generate_clip_frames(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.generate_clip_frames(*args, **kwargs)


def _animation_clip_source_has_raster_paths(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig._animation_clip_source_has_raster_paths(*args, **kwargs)


def _hydrate_raster_bridge_animation_clip(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig._hydrate_raster_bridge_animation_clip(*args, **kwargs)


def hydrate_animation_clips(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.hydrate_animation_clips(*args, **kwargs)


def infer_legacy_part_bbox(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.infer_legacy_part_bbox(*args, **kwargs)


def normalize_palette_payload(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.normalize_palette_payload(*args, **kwargs)


def hydrate_legacy_sprite_model(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.hydrate_legacy_sprite_model(*args, **kwargs)


def build_default_animation_clips(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.build_default_animation_clips(*args, **kwargs)


def neutral_pose_transforms(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.neutral_pose_transforms(*args, **kwargs)


def compute_pose_joints(*args, **kwargs):
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.compute_pose_joints(*args, **kwargs)


def source_fit(source_bbox: Tuple[int, int, int, int], canvas_size: Tuple[int, int], bottom_margin: int = 54, side_margin: int = 56) -> Tuple[float, float, float]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.source_fit(source_bbox, canvas_size, bottom_margin, side_margin)


def map_source_point(point: Tuple[float, float], scale: float, offset_x: float, offset_y: float) -> Tuple[float, float]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.map_source_point(point, scale, offset_x, offset_y)


def render_pose_from_sprite_model(
    project: Dict[str, Any],
    rig: Dict[str, Any],
    transforms: Dict[str, Any],
    save_path: Optional[Path] = None,
    part_asset_overrides: Optional[Dict[str, Any]] = None,
    corrective_patches: Optional[Dict[str, Any]] = None,
) -> Tuple[Image.Image, Dict[str, Any]]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.render_pose_from_sprite_model(
        project,
        rig,
        transforms,
        save_path=save_path,
        part_asset_overrides=part_asset_overrides,
        corrective_patches=corrective_patches,
    )


def build_layered_character(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.build_layered_character(project_id, progress)


def build_rig(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_sprite_model_rig_config()
    return workbench_sprite_model_rig.build_rig(project_id, progress)


def get_manual_animation_clips(project_id: str) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.get_manual_animation_clips(project_id)


def create_manual_animation_clip(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.create_manual_animation_clip(project_id, payload)


def manual_clip_or_error(project: Dict[str, Any], clip_id: str) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.manual_clip_or_error(project, clip_id)


def update_manual_animation_clip_meta(project_id: str, clip_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.update_manual_animation_clip_meta(project_id, clip_id, payload)


def update_manual_animation_clip_frame(project_id: str, clip_id: str, frame_index: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.update_manual_animation_clip_frame(project_id, clip_id, frame_index, payload)


def copy_manual_animation_clip_frame(project_id: str, clip_id: str, frame_index: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.copy_manual_animation_clip_frame(project_id, clip_id, frame_index, payload)


def reset_manual_animation_clip_frame(project_id: str, clip_id: str, frame_index: int) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.reset_manual_animation_clip_frame(project_id, clip_id, frame_index)


def generate_manual_animation_clip_frame_repair(project_id: str, clip_id: str, frame_index: int, part_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.generate_manual_animation_clip_frame_repair(project_id, clip_id, frame_index, part_name, payload)


def apply_manual_animation_clip_frame_repair(project_id: str, clip_id: str, frame_index: int, part_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.apply_manual_animation_clip_frame_repair(project_id, clip_id, frame_index, part_name, payload)


def clear_manual_animation_clip_frame_repair(project_id: str, clip_id: str, frame_index: int, part_name: str) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.clear_manual_animation_clip_frame_repair(project_id, clip_id, frame_index, part_name)


def generate_manual_animation_clip_frame_patch(project_id: str, clip_id: str, frame_index: int, source_part_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.generate_manual_animation_clip_frame_patch(project_id, clip_id, frame_index, source_part_name, payload)


def apply_manual_animation_clip_frame_patch(project_id: str, clip_id: str, frame_index: int, source_part_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.apply_manual_animation_clip_frame_patch(project_id, clip_id, frame_index, source_part_name, payload)


def clear_manual_animation_clip_frame_patch(project_id: str, clip_id: str, frame_index: int, source_part_name: str) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.clear_manual_animation_clip_frame_patch(project_id, clip_id, frame_index, source_part_name)


def render_manual_animation_clip_preview(project_id: str, clip_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.render_manual_animation_clip_preview(project_id, clip_id, progress)


def approve_manual_animation_clip(project_id: str, clip_id: str, approved: bool) -> Dict[str, Any]:
    _sync_workbench_manual_clips_config()
    return workbench_manual_clips.approve_manual_animation_clip(project_id, clip_id, approved)


def update_animation_clip(project_id: str, animation_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _sync_workbench_legacy_animation_production_config()
    return workbench_legacy_animation_production.update_animation_clip(project_id, animation_name, payload)


def reset_animation_clip(project_id: str, animation_name: str) -> Dict[str, Any]:
    _sync_workbench_legacy_animation_production_config()
    return workbench_legacy_animation_production.reset_animation_clip(project_id, animation_name)


def approve_sprite_model_review(project_id: str) -> Dict[str, Any]:
    _sync_workbench_legacy_animation_production_config()
    return workbench_legacy_animation_production.approve_sprite_model_review(project_id)


def approve_rig_review(project_id: str) -> Dict[str, Any]:
    _sync_workbench_legacy_animation_production_config()
    return workbench_legacy_animation_production.approve_rig_review(project_id)


def render_animation(project_id: str, animation_name: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    _sync_workbench_legacy_animation_production_config()
    return workbench_legacy_animation_production.render_animation(project_id, animation_name, progress)












def sync_pixellab_animation_clips(
    project_id: str,
    *,
    project: Optional[Dict[str, Any]] = None,
    project_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    if project is None:
        project = load_project(project_id)
    if project_dir is None:
        project_dir = PROJECTS_ROOT / project_id

    _pixellab_character_approved_guard(project_dir)
    pix_store = _load_pixellab_animations_store(project_dir)
    anim_store = pix_store.get("animations") if isinstance(pix_store.get("animations"), dict) else {}
    if not pixellab_animation_store_has_frames(anim_store):
        raise ValueError(
            "Cannot sync animation clips yet — no generated animation frames were found in pixellab_animations.json. "
            "Generate any default or custom animation first."
        )

    animation_clips_path = canonical_downstream_path(project_dir, "animation_clips")
    existing = load_json(animation_clips_path, {}) or {}
    if not isinstance(existing, dict):
        existing = {}

    for animation_name, anim in anim_store.items():
        if not isinstance(anim, dict):
            continue
        try:
            validate_pixellab_animation_name(animation_name)
        except ValueError:
            logger.warning("[pixellab/sync-clips] skip invalid animation key %r", animation_name)
            continue

        fps = anim.get("fps") or (AI_CLIP_SPECS.get(animation_name) or {}).get("fps") or ANIMATION_SPECS.get(animation_name, {}).get("fps") or 12
        meta_frame_count = anim.get("frame_count") or (AI_CLIP_SPECS.get(animation_name) or {}).get("frame_count") or ANIMATION_SPECS.get(animation_name, {}).get("frame_count") or 4
        loop = bool(anim.get("loop", True))

        frames_by_direction = {}
        if isinstance(anim.get("directions"), dict):
            for direction, ddata in anim["directions"].items():
                if isinstance(ddata, dict) and isinstance(ddata.get("frames"), list):
                    frames_by_direction[str(direction)] = ddata["frames"]

        default_dir = "east" if "east" in frames_by_direction else (next(iter(frames_by_direction.keys())) if frames_by_direction else "east")
        frames = frames_by_direction.get(default_dir) or []
        path_count = len(frames) if isinstance(frames, list) else 0
        if path_count == 0:
            continue
        if path_count and int(meta_frame_count) != path_count:
            logger.warning(
                "[pixellab/sync-clips] %s: store frame_count=%s but default-dir %r has %d paths — using path count",
                animation_name,
                meta_frame_count,
                default_dir,
                path_count,
            )
        frame_count = int(path_count or meta_frame_count)

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

    project["animation_clips"] = existing
    project["current_stage"] = "animations"
    project["status"] = "pixellab_animation_clips_synced"
    project["updated_at"] = now_iso()
    save_project(project)
    return existing




















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


def http_json(method: str, url: str, payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = HTTP_JSON_DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
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


def get_concept_backend(mode: str) -> ConceptBackend:
    # ComfyUI removed (Phase 8); legacy concept routes use the offline procedural backend only.
    _ = normalize_brief_backend_mode(mode)
    return DebugProceduralConceptBackend()


def relative_preview_path(project_dir: Path, image_path: Path) -> str:
    _sync_workbench_legacy_concept_runs_config()
    return workbench_legacy_concept_runs.relative_preview_path(project_dir, image_path)


def generate_run(
    project_id: str,
    run_kind: str,
    source_concept_id: Optional[str] = None,
    attribute_group: Optional[str] = None,
    target_value: Optional[str] = None,
    strength_label: Optional[str] = None,
    progress: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    _sync_workbench_legacy_concept_runs_config()
    return workbench_legacy_concept_runs.generate_run(
        project_id,
        run_kind,
        source_concept_id=source_concept_id,
        attribute_group=attribute_group,
        target_value=target_value,
        strength_label=strength_label,
        progress=progress,
    )


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
            concept_backend = DebugProceduralConceptBackend().healthcheck()
            return self._send_json({
                "ok": True,
                "tool_version": TOOL_VERSION,
                "projects_root": str(PROJECTS_ROOT),
                "stage_maturity": load_stage_maturity(),
                "concept_backend": concept_backend,
                "legacy_comfyui": "removed",
                "settings": load_workbench_settings(),
                "usage_summary": summarize_usage_ledger(),
                "demo_projects": list_demo_projects(),
            })

        if path == "/api/demo-projects":
            return self._send_json({"projects": list_demo_projects()})

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

        bundle_export_match = re.fullmatch(r"/api/projects/([^/]+)/bundle-export", path)
        if bundle_export_match:
            try:
                filename, payload = build_project_bundle_archive(bundle_export_match.group(1))
            except FileNotFoundError:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")
            return self._send_bytes(
                payload,
                content_type="application/zip",
                filename=filename,
            )

        project_match = re.fullmatch(r"/api/projects/([^/]+)", path)
        if project_match:
            try:
                return self._send_json(load_project(project_match.group(1)))
            except FileNotFoundError:
                return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")

        room_layout_match = re.fullmatch(r"/api/projects/([^/]+)/room-layout", path)
        if room_layout_match:
            try:
                return self._send_json(get_room_layout(room_layout_match.group(1)))
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

            if path == "/api/projects/import-bundle":
                return self._send_json(import_project_bundle(read_body(self)), status=HTTPStatus.CREATED)

            if path == "/api/projects/import-demo":
                return self._send_json(import_demo_project(read_body(self)), status=HTTPStatus.CREATED)

            if path == "/api/settings":
                settings = save_workbench_settings(read_body(self))
                return self._send_json({
                    "ok": True,
                    "settings": settings,
                    "usage_summary": summarize_usage_ledger(),
                })

            room_layout_match = re.fullmatch(r"/api/projects/([^/]+)/room-layout", path)
            if room_layout_match:
                return self._send_json(save_room_layout(room_layout_match.group(1), read_body(self)))

            room_validate_match = re.fullmatch(r"/api/projects/([^/]+)/room-layout/validate", path)
            if room_validate_match:
                payload = read_body(self)
                return self._send_json(validate_project_room_layout(room_validate_match.group(1), payload))

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

                source_rel = _concept_source_image_relpath(concept)
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
                init_source_rel = None
                init_image_b64 = None
                concept_source_mode = "text_prompt"
                try:
                    requested_init_strength = int(
                        payload.get("init_image_strength")
                        or pixellab_params.get("init_image_strength")
                        or PIXELLAB_CONCEPT_INIT_IMAGE_STRENGTH
                    )
                except (TypeError, ValueError):
                    requested_init_strength = PIXELLAB_CONCEPT_INIT_IMAGE_STRENGTH

                init_image_data_url = payload.get("init_image_data_url")
                if init_image_data_url:
                    _, init_raw = parse_data_url(str(init_image_data_url))
                    prepared_init = prepare_pixellab_concept_init_image(
                        init_raw,
                        int(pixellab_params["image_size"]["width"]),
                    )
                    init_output_path = project_dir / "concepts" / ("%s-init.png" % concept_id)
                    init_output_path.parent.mkdir(parents=True, exist_ok=True)
                    prepared_init.save(init_output_path)
                    init_source_rel = str(init_output_path.relative_to(project_dir))
                    init_image_b64 = _encode_png_base64(prepared_init)
                    concept_source_mode = "custom_init_image"

                backend_mode = brief_backend_mode(project.get("brief"))
                seed = pixellab_params.get("seed")

                used_backend = "debug_procedural" if backend_mode == "debug_procedural" else "pixellab"
                backend_run_id = None

                if backend_mode == "debug_procedural" or not pixellab_configured():
                    if init_image_b64:
                        image = debug_pixellab_iterate_from_inpainting(init_image_b64, seed)
                    else:
                        image = debug_pixellab_concept_image(pixellab_params["image_size"], seed, label="gen")
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(output_path)
                    backend_run_id = "debug"
                else:
                    provider_call_allowed()
                    client = get_pixellab_client()
                    if client is None:
                        raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                    desc = pixellab_params["description"]
                    image_size = pixellab_params["image_size"]
                    no_background = bool(pixellab_params.get("no_background", True))

                    # Init-image post-processing is a Pixflux-only path; direct text generation can still try v2 first.
                    last_exc: Optional[str] = None
                    attempts = ["pixflux"] if init_image_b64 else ([mode] + (["pixflux"] if mode != "pixflux" else []))
                    for attempt in attempts:
                        try:
                            if attempt == "v2":
                                result = client.create_image_v2(
                                    desc,
                                    image_size,
                                    no_background=no_background,
                                    seed=seed,
                                )
                            else:
                                pixflux_kwargs = {
                                    "no_background": no_background,
                                    "outline": pixellab_params.get("outline"),
                                    "shading": pixellab_params.get("shading"),
                                    "detail": pixellab_params.get("detail"),
                                    "view": pixellab_params.get("view"),
                                    "direction": pixellab_params.get("direction"),
                                    "seed": seed,
                                }
                                if init_image_b64:
                                    pixflux_kwargs["init_image"] = {
                                        "type": "base64",
                                        "base64": init_image_b64,
                                        "format": "png",
                                    }
                                    pixflux_kwargs["init_image_strength"] = requested_init_strength
                                result = client.create_image_pixflux(desc, image_size, **pixflux_kwargs)

                            backend_run_id = result.get("job_id") or result.get("id")
                            b64 = _find_first_base64_png_like(result)
                            if not b64:
                                raise ValueError("Pixel Lab result did not contain extractable base64 image.")
                            image = _decode_base64_image_to_rgba(b64)
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            image.save(output_path)
                            used_backend = "pixellab"
                            backend_run_id = backend_run_id or "pixellab"
                            append_usage_ledger_entry(
                                provider="pixellab",
                                endpoint="concepts.generate-pixellab",
                                project_id=project_id,
                                status="success",
                                usage=client.last_usage,
                                job_id=result.get("job_id") or result.get("background_job_id"),
                                generation_id=result.get("generation_id") or result.get("id"),
                                metadata={
                                    "mode": attempt,
                                    "concept_id": concept_id,
                                    "source_mode": concept_source_mode,
                                },
                            )
                            last_exc = None
                            break
                        except Exception as exc:
                            append_usage_ledger_entry(
                                provider="pixellab",
                                endpoint="concepts.generate-pixellab",
                                project_id=project_id,
                                status="error",
                                usage=client.last_usage if client else None,
                                error=str(exc),
                                metadata={
                                    "mode": attempt,
                                    "concept_id": concept_id,
                                    "source_mode": concept_source_mode,
                                },
                            )
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
                    "difference_summary": (
                        "Pixel Lab post-processed uploaded init image (pixflux)"
                        if concept_source_mode == "custom_init_image"
                        else "Pixel Lab generated concept (%s)" % mode
                    ),
                    "concept_source_mode": concept_source_mode,
                    "init_source_image": init_source_rel,
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
                if not pixellab_params.get("init_image_b64"):
                    raise ValueError("pixellab_params.init_image_b64 is required.")

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                serial = next_concept_serial(project["concepts"])
                concept_id = "concept-%04d" % serial
                output_path = project_dir / "concepts" / ("%s.png" % concept_id)

                backend_mode = brief_backend_mode(project.get("brief"))
                seed = pixellab_params.get("seed")
                used_backend = "debug_procedural" if backend_mode == "debug_procedural" else "pixellab"
                backend_run_id = None

                if backend_mode == "debug_procedural" or not pixellab_configured():
                    image = debug_pixellab_iterate_from_inpainting(
                        pixellab_params["init_image_b64"],
                        seed,
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(output_path)
                    backend_run_id = "debug"
                else:
                    provider_call_allowed()
                    client = get_pixellab_client()
                    if client is None:
                        raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                    try:
                        result = client.create_image_pixflux(
                            pixellab_params["description"],
                            pixellab_params["image_size"],
                            init_image={"type": "base64", "base64": pixellab_params["init_image_b64"], "format": "png"},
                            init_image_strength=pixellab_params.get("init_image_strength", 750),
                            view=pixellab_params.get("view", "side"),
                            direction=pixellab_params.get("direction", "east"),
                            outline=pixellab_params.get("outline"),
                            shading=pixellab_params.get("shading"),
                            detail=pixellab_params.get("detail"),
                            no_background=bool(pixellab_params.get("no_background", True)),
                            seed=seed,
                        )
                    except Exception as exc:
                        append_usage_ledger_entry(
                            provider="pixellab",
                            endpoint="concepts.iterate-pixellab",
                            project_id=project_id,
                            status="error",
                            usage=client.last_usage if client else None,
                            error=str(exc),
                            metadata={"concept_id": concept_id, "source_concept_id": source_concept_id},
                        )
                        raise

                    backend_run_id = result.get("job_id") or result.get("id")
                    b64 = _find_first_base64_png_like(result)
                    if not b64:
                        raise ValueError("Pixel Lab result did not contain extractable base64 image.")

                    image = _decode_base64_image_to_rgba(b64)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(output_path)
                    used_backend = "pixellab"
                    backend_run_id = backend_run_id or "pixellab"
                    append_usage_ledger_entry(
                        provider="pixellab",
                        endpoint="concepts.iterate-pixellab",
                        project_id=project_id,
                        status="success",
                        usage=client.last_usage,
                        job_id=result.get("job_id") or result.get("background_job_id"),
                        generation_id=result.get("generation_id") or result.get("id"),
                        metadata={"concept_id": concept_id, "source_concept_id": source_concept_id},
                    )

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

            iterate_gemini_match = re.fullmatch(r"/api/projects/([^/]+)/concepts/iterate-gemini", path)
            if iterate_gemini_match:
                project_id = iterate_gemini_match.group(1)
                payload = read_body(self)
                source_concept_id = payload.get("concept_id")
                element = (payload.get("element") or "").strip()
                change_text = (payload.get("change_text") or "").strip()

                if not source_concept_id:
                    raise ValueError("iterate-gemini requires concept_id.")
                if not element:
                    raise ValueError("iterate-gemini requires element.")
                if not change_text:
                    raise ValueError("iterate-gemini requires change_text.")
                if not gemini_iteration_supported_for_element(element):
                    raise ValueError("Gemini iteration requires a supported element.")

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}

                source_concept = next(
                    (c for c in project.get("concepts", []) if c["concept_id"] == source_concept_id), None
                )
                if source_concept is None:
                    raise ValueError("Source concept not found: %s" % source_concept_id)

                source_rel = _concept_source_image_relpath(source_concept)
                if not source_rel:
                    raise ValueError("Source concept has no image.")
                source_path = project_dir / source_rel
                if not source_path.exists():
                    raise ValueError("Source concept image not found: %s" % source_path)

                serial = next_concept_serial(project["concepts"])
                concept_id = "concept-%04d" % serial
                output_path = project_dir / "concepts" / ("%s.png" % concept_id)

                source_bytes = source_path.read_bytes()
                provider_call_allowed()
                try:
                    image_bytes = gemini_iterate_concept(source_bytes, element, change_text, brief)
                except Exception as exc:
                    append_usage_ledger_entry(
                        provider="gemini",
                        endpoint="concepts.iterate-gemini",
                        project_id=project_id,
                        status="error",
                        error=str(exc),
                        metadata={"source_concept_id": source_concept_id, "element": element},
                    )
                    raise

                image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(output_path)
                append_usage_ledger_entry(
                    provider="gemini",
                    endpoint="concepts.iterate-gemini",
                    project_id=project_id,
                    status="success",
                    metadata={"concept_id": concept_id, "source_concept_id": source_concept_id, "element": element},
                )

                preview_rel = str(output_path.relative_to(project_dir))
                concept = hydrate_concept({
                    "concept_id": concept_id,
                    "run_id": stable_hash("gemini-iterate", project_id, concept_id)[:12],
                    "run_kind": "pixellab_iterate",
                    "created_at": now_iso(),
                    "positive_prompt": "%s: %s" % (element, change_text),
                    "prompt": "%s: %s" % (element, change_text),
                    "prompt_text": "%s: %s" % (element, change_text),
                    "prompt_version": 0,
                    "prompt_source": "gemini",
                    "attempt_group_id": stable_hash("gemini-iterate-group", project_id, source_concept_id)[:12],
                    "attempt_index": 0,
                    "import_source": None,
                    "validation_status": "valid",
                    "validation_source": "gemini",
                    "validation_feedback": None,
                    "accepted_for_review": False,
                    "preview_image": preview_rel,
                    "original_preview_image": preview_rel,
                    "backend_name": "gemini",
                    "backend_run_id": "gemini",
                    "difference_summary": "Gemini iteration from %s: %s — %s" % (source_concept_id, element, change_text),
                    "silhouette": brief.get("silhouette_intent", ""),
                    "outfit": brief.get("outfit_materials", ""),
                    "palette_direction": brief.get("palette_mood", ""),
                    "palette": palette_from_seed(serial, 0, brief.get("palette_mood", "")),
                    "prop_variant": brief.get("prop", ""),
                    "face_head_shape": brief.get("shape_language", ""),
                    "references_used": [],
                    "review_state": {"approved": False, "favorite": False, "rejected": False},
                    "lineage": {"run_id": "gemini", "parent_concept_id": source_concept_id},
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
                    "type": "concept_gemini_iterate",
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

                concept = next((item for item in (project.get("concepts") or []) if item.get("concept_id") == color_concept_id), None)
                if concept is None:
                    raise ValueError("color_concept_id concept not found.")

                source_rel = (
                    concept.get("processed_preview_image")
                    or concept.get("original_preview_image")
                    or concept.get("preview_image")
                    or concept.get("image_path")
                )
                if not source_rel:
                    raise ValueError("Concept does not have a preview image path.")

                source_path = Path(source_rel)
                if not source_path.is_absolute():
                    source_path = project_dir / source_rel
                if not source_path.exists():
                    raise ValueError("Concept preview image is missing on disk.")

                with Image.open(source_path) as source_loaded:
                    source_size = {"width": source_loaded.size[0], "height": source_loaded.size[1]}
                canvas_size = preferred_concept_canvas_size(source_size)

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

                backend_mode = brief_backend_mode(brief)
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

                provider_call_allowed()
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

                    prepared_color_source = prepare_pixellab_character_color_source(source_path, canvas_size)
                    color_image = base64_image_payload(
                        client.encode_image_rgba(prepared_color_source),
                        image_format="rgba",
                    )
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
                except PixelLabHTTPError as exc:
                    append_usage_ledger_entry(
                        provider="pixellab",
                        endpoint="pixellab.create-character",
                        project_id=project_id,
                        status="error",
                        usage=client.last_usage if client else None,
                        error=str(exc),
                        metadata={"concept_id": color_concept_id, "directions": directions},
                    )
                    if exc.status_code >= 500:
                        raise ValueError(
                            "Pixel Lab create-character hit a server-side error after the request was accepted. "
                            "The concept source image is compatible, but the Pixel Lab multi-direction endpoint failed internally. "
                            "Retry later or use 'Use Concept as Character (East Only)' for a stable side-scroller path."
                        )
                    raise ValueError("Pixel Lab create-character failed: %s" % str(exc))
                except Exception as exc:
                    append_usage_ledger_entry(
                        provider="pixellab",
                        endpoint="pixellab.create-character",
                        project_id=project_id,
                        status="error",
                        usage=client.last_usage if client else None,
                        error=str(exc),
                        metadata={"concept_id": color_concept_id, "directions": directions},
                    )
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
                append_usage_ledger_entry(
                    provider="pixellab",
                    endpoint="pixellab.create-character",
                    project_id=project_id,
                    status="success",
                    usage=client.last_usage,
                    job_id=result.get("job_id") or result.get("background_job_id"),
                    generation_id=result.get("generation_id") or result.get("character_id") or result.get("id"),
                    metadata={"concept_id": color_concept_id, "directions": directions},
                )
                return self._send_json(char_payload, status=HTTPStatus.CREATED)

            use_concept_character_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/use-concept-character", path)
            if use_concept_character_pixellab_match:
                project_id = use_concept_character_pixellab_match.group(1)
                payload = read_body(self)

                concept_id = payload.get("concept_id") or payload.get("color_concept_id")
                if not concept_id:
                    raise ValueError("use-concept-character requires concept_id.")

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                concept = next((item for item in (project.get("concepts") or []) if item.get("concept_id") == concept_id), None)
                if concept is None:
                    raise ValueError("Concept not found for east-only character source.")

                source_rel = (
                    concept.get("processed_preview_image")
                    or concept.get("original_preview_image")
                    or concept.get("preview_image")
                    or concept.get("image_path")
                )
                if not source_rel:
                    raise ValueError("Concept does not have a preview image path.")

                source_path = Path(source_rel)
                if not source_path.is_absolute():
                    source_path = project_dir / source_rel
                if not source_path.exists():
                    raise ValueError("Concept preview image is missing on disk.")

                char_payload = _set_pixellab_east_only_character_source(project, project_dir, concept_id, approved=False)
                project["current_stage"] = "concepts"
                project["status"] = "pixellab_character_concept_source_ready"
                project["updated_at"] = now_iso()
                save_project(project)
                append_history_event(project_id, {
                    "type": "pixellab_character_concept_source_ready",
                    "concept_id": concept_id,
                    "created_at": now_iso(),
                })
                return self._send_json(char_payload, status=HTTPStatus.CREATED)

            estimate_skeleton_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/estimate-skeleton", path)
            if estimate_skeleton_pixellab_match:
                project_id = estimate_skeleton_pixellab_match.group(1)
                payload = read_body(self)
                direction = (payload.get("direction") or "east").strip().lower()

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                # Require character assets.
                char_path = _pixellab_character_path(project_dir)
                if not char_path.exists():
                    raise ValueError("pixellab_character.json is missing; run create-character first.")
                char_data = load_json(char_path, None) or {}

                image_size = char_data.get("image_size") if isinstance(char_data, dict) else {}
                canvas_size = coerce_canvas_size((image_size or {}).get("width"), DEFAULT_CANVAS_SIZE)
                source_rel = (char_data.get("images") or {}).get(direction) if isinstance(char_data, dict) else None
                if not source_rel:
                    raise ValueError("Character direction image missing from pixellab_character.json: %s" % direction)
                source_img_path = project_dir / str(source_rel)
                if not source_img_path.exists():
                    raise ValueError("Character direction image missing: %s" % str(source_img_path))

                seed = payload.get("seed")
                try:
                    seed = int(seed) if seed is not None else stable_int(project_id, direction, str(canvas_size), mod=4_294_967_295)
                except (TypeError, ValueError):
                    seed = stable_int(project_id, direction, str(canvas_size), mod=4_294_967_295)

                backend_mode = brief_backend_mode(brief)
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

                provider_call_allowed()
                client = get_pixellab_client()
                if client is None:
                    raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                image_b64 = client.encode_image(source_img_path)
                try:
                    result = client.estimate_skeleton(image_b64)
                except Exception as exc:
                    append_usage_ledger_entry(
                        provider="pixellab",
                        endpoint="pixellab.estimate-skeleton",
                        project_id=project_id,
                        status="error",
                        usage=client.last_usage if client else None,
                        error=str(exc),
                        metadata={"direction": direction},
                    )
                    raise
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
                append_usage_ledger_entry(
                    provider="pixellab",
                    endpoint="pixellab.estimate-skeleton",
                    project_id=project_id,
                    status="success",
                    usage=client.last_usage,
                    generation_id=result.get("generation_id") if isinstance(result, dict) else None,
                    metadata={"direction": direction},
                )
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
                char_data["pixellab_character_approved"] = True
                char_path.write_text(json.dumps(char_data, indent=2), encoding="utf-8")

                project["pixellab_character_approved"] = True
                project["status"] = "pixellab_character_approved"
                save_project(project)
                append_history_event(project_id, {"type": "pixellab_character_approved", "created_at": now_iso()})
                return self._send_json(char_data, status=HTTPStatus.OK)

            # -----------------------------
            # Phase 5: Pixel Lab animations
            # -----------------------------
            define_anim_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/define-animation", path)
            if define_anim_pixellab_match:
                project_id = define_anim_pixellab_match.group(1)
                payload = read_body(self)
                name = validate_pixellab_animation_name(payload.get("animation_name"))
                if name in PIXELLAB_CORE_ANIMATION_NAMES:
                    raise ValueError(
                        "Idle, walk, run, and jump already have panels. Pick another name (e.g. attack, cast, parry)."
                    )
                project_dir = PROJECTS_ROOT / project_id
                _pixellab_character_approved_guard(project_dir)
                store = _load_pixellab_animations_store(project_dir)
                anims = store.setdefault("animations", {})
                existing_entry = anims.get(name) if isinstance(anims.get(name), dict) else None
                if isinstance(existing_entry, dict):
                    has_frames = False
                    dirs = existing_entry.get("directions")
                    if isinstance(dirs, dict):
                        for ddata in dirs.values():
                            if isinstance(ddata, dict) and isinstance(ddata.get("frames"), list) and ddata["frames"]:
                                has_frames = True
                                break
                    if has_frames:
                        return self._send_json({"ok": True, "animation_name": name, "already_existed": True})
                anims[name] = {
                    "animation_name": name,
                    "fps": 12,
                    "frame_count": 0,
                    "loop": True,
                    "backend_name": "pending",
                    "updated_at": now_iso(),
                    "directions": {},
                }
                store["updated_at"] = now_iso()
                _save_pixellab_animations_store(project_dir, store)
                proj_reload = load_project(project_id)
                proj_reload["pixellab_animations"] = store
                save_project(proj_reload)
                return self._send_json({"ok": True, "animation_name": name})

            animate_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/animate", path)
            if animate_pixellab_match:
                project_id = animate_pixellab_match.group(1)
                payload = read_body(self)

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}

                # Phase 5 gating (4.3 carry-forward).
                char_data = _pixellab_character_approved_guard(project_dir)
                _pixellab_character_requires_template_generation_guard(char_data)
                canvas_size = preferred_supported_canvas_size(
                    char_data.get("image_size") if isinstance(char_data, dict) else None,
                    coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE),
                )

                template_animation_id = payload.get("template_animation_id")
                if not template_animation_id:
                    raise ValueError("animate requires template_animation_id.")

                directions = int(payload.get("directions") or 4)
                if directions not in {4, 8}:
                    raise ValueError("directions must be 4 or 8.")

                explicit_anim = str(payload.get("animation_name") or "").strip()
                if explicit_anim:
                    animation_name = validate_pixellab_animation_name(explicit_anim)
                else:
                    animation_name = validate_pixellab_animation_name(
                        _infer_animation_name_from_template(str(template_animation_id))
                    )

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

                backend_mode = brief_backend_mode(brief)
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

                logger.info(
                    "[pixellab/animate] start project=%s animation=%s template=%s dir_count=%d "
                    "use_debug=%s backend_mode=%s pixellab_configured=%s character_id=%s",
                    project_id,
                    animation_name,
                    template_animation_id,
                    len(direction_list),
                    use_debug,
                    backend_mode,
                    pixellab_configured(),
                    char_data.get("character_id"),
                )

                if use_debug:
                    logger.info(
                        "[pixellab/animate] debug_procedural — skipping Pixel Lab API (backend_mode=%s or no API key)",
                        backend_mode,
                    )
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
                    provider_call_allowed()
                    client = get_pixellab_client()
                    if client is None:
                        raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                    logger.info(
                        "[pixellab/animate] calling Pixel Lab POST /v2/characters/animations character_id=%s",
                        char_data.get("character_id"),
                    )
                    # v2 endpoint call (async polling handled inside the client).
                    try:
                        result = client.animate_character(
                            str(char_data.get("character_id") or ""),
                            str(template_animation_id),
                            directions=direction_list,
                            seed=seed,
                            poll_timeout_seconds=480,
                        )
                    except Exception as exc:
                        append_usage_ledger_entry(
                            provider="pixellab",
                            endpoint="pixellab.animate-template",
                            project_id=project_id,
                            status="error",
                            usage=client.last_usage if client else None,
                            error=str(exc),
                            metadata={"animation_name": animation_name, "template_animation_id": str(template_animation_id), "directions": len(direction_list)},
                        )
                        raise

                    b64_n, url_n = _pixellab_frame_source_counts(result)
                    logger.info(
                        "[pixellab/animate] api_returned %s; pre_decode b64_candidates=%d https_urls=%d",
                        _pixellab_api_result_summary(result),
                        b64_n,
                        url_n,
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
                    logger.info(
                        "[pixellab/animate] decoded_rgba_frames=%d (expect up to %d for %d dirs × %d frames)",
                        len(plate_frames),
                        len(direction_list) * frame_count,
                        len(direction_list),
                        frame_count,
                    )
                    if not plate_frames:
                        keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
                        logger.warning(
                            "[pixellab/animate] no decodable frames project=%s keys=%s summary=%s",
                            project_id,
                            keys,
                            _pixellab_api_result_summary(result),
                        )
                        raise ValueError(
                            "Pixel Lab animation returned no decodable frames (PNG/WebP/JPEG base64 or image URLs). "
                            "Response keys: %s" % keys
                        )
                    # Heuristic ordering: direction-major then frame index.
                    last_written_fc: Optional[int] = None
                    for dir_idx, direction in enumerate(direction_list):
                        frames: List[Image.Image] = []
                        for frame_idx in range(frame_count):
                            flat_idx = dir_idx * frame_count + frame_idx
                            if flat_idx >= len(plate_frames):
                                break
                            frames.append(plate_frames[flat_idx])
                        actual_fc = len(frames)
                        if actual_fc == 0:
                            raise ValueError(
                                "Pixel Lab returned no decodable frames for direction %r (resolved expect=%d). "
                                "Try another template or retry — API output may be shorter than requested."
                                % (direction, frame_count)
                            )
                        if actual_fc != frame_count:
                            logger.warning(
                                "[pixellab/animate] frame count mismatch animation=%s direction=%s written=%d resolved_meta=%d",
                                animation_name,
                                direction,
                                actual_fc,
                                frame_count,
                            )
                        frame_paths = _write_png_frames(frames, project_dir, animation_name, direction)
                        written_fc = len(frame_paths)
                        _upsert_pixellab_animation_frames(
                            project_dir,
                            store,
                            animation_name=animation_name,
                            direction=direction,
                            fps=fps,
                            frame_count=written_fc,
                            loop=loop,
                            frames_paths=frame_paths,
                            template_animation_id=str(template_animation_id),
                            backend_name="pixellab",
                            seed=seed,
                            job_id=job_id,
                        )
                        last_written_fc = written_fc
                    frame_count = int(last_written_fc or frame_count)
                    append_usage_ledger_entry(
                        provider="pixellab",
                        endpoint="pixellab.animate-template",
                        project_id=project_id,
                        status="success",
                        usage=client.last_usage,
                        job_id=job_id,
                        generation_id=result.get("generation_id") if isinstance(result, dict) else None,
                        metadata={"animation_name": animation_name, "template_animation_id": str(template_animation_id), "directions": len(direction_list)},
                    )

                logger.info(
                    "[pixellab/animate] ok project=%s animation=%s fps=%s frame_count=%s",
                    project_id,
                    animation_name,
                    fps,
                    frame_count,
                )
                return self._send_json({"ok": True, "animation_name": animation_name, "fps": fps, "frame_count": frame_count})

            animate_custom_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/animate-custom", path)
            if animate_custom_pixellab_match:
                project_id = animate_custom_pixellab_match.group(1)
                payload = read_body(self)

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                char_data = _pixellab_character_approved_guard(project_dir)
                canvas_size = preferred_supported_canvas_size(
                    char_data.get("image_size") if isinstance(char_data, dict) else None,
                    coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE),
                )

                action = str(payload.get("action") or "").strip()
                if not action:
                    raise ValueError("animate-custom requires action.")

                animation_name = validate_pixellab_animation_name(payload.get("animation_name") or "idle")

                backend_mode = brief_backend_mode(brief)
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

                logger.info(
                    "[pixellab/animate-custom] start project=%s animation=%s use_debug=%s backend_mode=%s action_len=%d",
                    project_id,
                    animation_name,
                    use_debug,
                    backend_mode,
                    len(action),
                )

                if use_debug:
                    logger.info("[pixellab/animate-custom] debug_procedural — skipping API")
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
                    provider_call_allowed()
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
                    logger.info("[pixellab/animate-custom] calling POST /v2/animate-with-text-v2")
                    try:
                        result = client.animate_with_text_v2(
                            ref_b64,
                            action,
                            image_size,
                            poll_timeout_seconds=PIXELLAB_ANIMATE_CUSTOM_POLL_TIMEOUT_SECONDS,
                        )
                    except Exception as exc:
                        append_usage_ledger_entry(
                            provider="pixellab",
                            endpoint="pixellab.animate-custom",
                            project_id=project_id,
                            status="error",
                            usage=client.last_usage if client else None,
                            error=str(exc),
                            metadata={"animation_name": animation_name, "action": action[:120]},
                        )
                        raise

                    b64_n, url_n = _pixellab_frame_source_counts(result)
                    logger.info(
                        "[pixellab/animate-custom] api_returned %s; pre_decode b64_candidates=%d https_urls=%d",
                        _pixellab_api_result_summary(result),
                        b64_n,
                        url_n,
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
                    logger.info(
                        "[pixellab/animate-custom] decoded_rgba_frames=%d (want up to %d)",
                        len(plate_frames),
                        frame_count,
                    )
                    if not plate_frames:
                        keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
                        logger.warning(
                            "[pixellab/animate-custom] no decodable frames project=%s keys=%s",
                            project_id,
                            keys,
                        )
                        raise ValueError(
                            "Pixel Lab custom animation returned no decodable frames. Response keys: %s" % keys
                        )
                    frames = plate_frames[:frame_count]
                    written_fc = len(frames)
                    frame_paths = _write_png_frames(frames, project_dir, animation_name, direction)
                    _upsert_pixellab_animation_frames(
                        project_dir,
                        store,
                        animation_name=animation_name,
                        direction=direction,
                        fps=fps,
                        frame_count=written_fc,
                        loop=loop,
                        frames_paths=frame_paths,
                        template_animation_id="custom",
                        backend_name="pixellab",
                        seed=seed,
                        job_id=job_id,
                    )
                    frame_count = written_fc
                    append_usage_ledger_entry(
                        provider="pixellab",
                        endpoint="pixellab.animate-custom",
                        project_id=project_id,
                        status="success",
                        usage=client.last_usage,
                        job_id=job_id,
                        generation_id=result.get("generation_id") if isinstance(result, dict) else None,
                        metadata={"animation_name": animation_name, "action": action[:120]},
                    )

                logger.info(
                    "[pixellab/animate-custom] ok project=%s animation=%s frames_written=%d",
                    project_id,
                    animation_name,
                    len(frames),
                )
                return self._send_json({"ok": True, "animation_name": animation_name, "fps": fps, "frame_count": frame_count})

            animate_skeleton_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/animate-skeleton", path)
            if animate_skeleton_pixellab_match:
                project_id = animate_skeleton_pixellab_match.group(1)
                payload = read_body(self)

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                char_data = _pixellab_character_approved_guard(project_dir)
                canvas_size = preferred_supported_canvas_size(
                    char_data.get("image_size") if isinstance(char_data, dict) else None,
                    coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE),
                )

                keypoint_frames = payload.get("keypoint_frames") if isinstance(payload, dict) else None
                if not isinstance(keypoint_frames, list):
                    raise ValueError("animate-skeleton requires keypoint_frames: list.")

                animation_name = validate_pixellab_animation_name(payload.get("animation_name") or "idle")

                direction = str(payload.get("direction") or "east").strip().lower() or "east"
                if direction not in (char_data.get("directions") or ["east"]):
                    # Keep strict enough to catch wiring mistakes.
                    raise ValueError("Invalid direction for this character: %s." % direction)

                backend_mode = brief_backend_mode(brief)
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

                logger.info(
                    "[pixellab/animate-skeleton] start project=%s animation=%s direction=%s "
                    "keypoint_frames=%d use_debug=%s backend_mode=%s",
                    project_id,
                    animation_name,
                    direction,
                    len(keypoint_frames),
                    use_debug,
                    backend_mode,
                )

                if use_debug:
                    logger.info("[pixellab/animate-skeleton] debug_procedural — skipping API")
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
                    provider_call_allowed()
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
                    logger.info("[pixellab/animate-skeleton] calling POST /v1/animate-with-skeleton")
                    try:
                        result = client.animate_with_skeleton(
                            ref_b64,
                            image_size,
                            keypoint_frames,
                            poll_timeout_seconds=480,
                        )
                    except Exception as exc:
                        append_usage_ledger_entry(
                            provider="pixellab",
                            endpoint="pixellab.animate-skeleton",
                            project_id=project_id,
                            status="error",
                            usage=client.last_usage if client else None,
                            error=str(exc),
                            metadata={"animation_name": animation_name, "direction": direction, "keypoint_frame_count": len(keypoint_frames)},
                        )
                        raise

                    b64_n, url_n = _pixellab_frame_source_counts(result)
                    logger.info(
                        "[pixellab/animate-skeleton] api_returned %s; pre_decode b64_candidates=%d https_urls=%d",
                        _pixellab_api_result_summary(result),
                        b64_n,
                        url_n,
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

                    logger.info(
                        "[pixellab/animate-skeleton] decoded_rgba_frames=%d requested_frame_count=%d",
                        len(plate_frames),
                        frame_count,
                    )
                    if not plate_frames:
                        keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
                        logger.warning(
                            "[pixellab/animate-skeleton] no decodable frames project=%s keys=%s",
                            project_id,
                            keys,
                        )
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
                    append_usage_ledger_entry(
                        provider="pixellab",
                        endpoint="pixellab.animate-skeleton",
                        project_id=project_id,
                        status="success",
                        usage=client.last_usage,
                        job_id=job_id,
                        generation_id=result.get("generation_id") if isinstance(result, dict) else None,
                        metadata={"animation_name": animation_name, "direction": direction, "keypoint_frame_count": len(keypoint_frames)},
                    )

                logger.info(
                    "[pixellab/animate-skeleton] ok project=%s animation=%s direction=%s frame_count=%s",
                    project_id,
                    animation_name,
                    direction,
                    frame_count,
                )
                return self._send_json({"ok": True, "animation_name": animation_name, "direction": direction, "fps": fps, "frame_count": frame_count})

            edit_animation_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/edit-animation", path)
            if edit_animation_pixellab_match:
                project_id = edit_animation_pixellab_match.group(1)
                payload = read_body(self)

                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                brief = project.get("brief") or {}
                char_data = _pixellab_character_approved_guard(project_dir)
                canvas_size = preferred_supported_canvas_size(
                    char_data.get("image_size") if isinstance(char_data, dict) else None,
                    coerce_canvas_size(brief.get("canvas_size"), DEFAULT_CANVAS_SIZE),
                )

                animation_name = str(payload.get("animation_name") or "").strip()
                description = str(payload.get("description") or "").strip()
                if not animation_name:
                    raise ValueError("edit-animation requires animation_name.")
                if not description:
                    raise ValueError("edit-animation requires description.")

                animation_name = validate_pixellab_animation_name(animation_name)

                backend_mode = brief_backend_mode(brief)
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

                logger.info(
                    "[pixellab/edit-animation] start project=%s animation=%s directions=%r use_debug=%s backend_mode=%s",
                    project_id,
                    animation_name,
                    directions,
                    use_debug,
                    backend_mode,
                )

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
                    logger.info("[pixellab/edit-animation] direction=%s index=%d/%d", direction, dir_idx + 1, len(directions))
                    # Infer frame_count from store if present.
                    inferred_fc = None
                    if isinstance(anim, dict) and isinstance(anim.get("directions"), dict):
                        inferred_fc = (anim["directions"].get(direction) or {}).get("frame_count")
                    if not inferred_fc:
                        inferred_fc = len(list((_pixellab_animation_frames_dir(project_dir, animation_name, direction)).glob("frame_*.png"))) if _pixellab_animation_frames_dir(project_dir, animation_name, direction).exists() else fps_frame["frame_count"]
                    frame_count = int(inferred_fc or fps_frame["frame_count"])

                    if use_debug:
                        logger.info("[pixellab/edit-animation] debug_procedural direction=%s frame_count=%d", direction, frame_count)
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
                        provider_call_allowed()
                        client = get_pixellab_client()
                        if client is None:
                            raise ValueError("Pixel Lab client unavailable; missing PIXELLAB_API_KEY.")

                        frames_dir = _pixellab_animation_frames_dir(project_dir, animation_name, direction)
                        source_paths: List[Path] = []
                        for idx in range(frame_count):
                            fp = frames_dir / ("frame_%02d.png" % idx)
                            if not fp.exists():
                                break
                            source_paths.append(fp)

                        image_size = {"width": canvas_size, "height": canvas_size}
                        frames: List[Image.Image] = []
                        batches = chunk_frame_indices(len(source_paths), 4)
                        for batch_idx, frame_indices in enumerate(batches, start=1):
                            frame_b64s = [client.encode_image(str(source_paths[i])) for i in frame_indices]
                            logger.info(
                                "[pixellab/edit-animation] calling POST /v2/edit-animation-v2 direction=%s batch=%d/%d input_png_frames=%d",
                                direction,
                                batch_idx,
                                len(batches),
                                len(frame_b64s),
                            )
                            try:
                                result = client.edit_animation_v2(
                                    description,
                                    frame_b64s,
                                    image_size,
                                    poll_timeout_seconds=480,
                                )
                            except Exception as exc:
                                append_usage_ledger_entry(
                                    provider="pixellab",
                                    endpoint="pixellab.edit-animation",
                                    project_id=project_id,
                                    status="error",
                                    usage=client.last_usage if client else None,
                                    error=str(exc),
                                    metadata={"animation_name": animation_name, "direction": direction, "batch": batch_idx},
                                )
                                raise
                            b64_n, url_n = _pixellab_frame_source_counts(result)
                            logger.info(
                                "[pixellab/edit-animation] api_returned direction=%s batch=%d %s; pre_decode b64_candidates=%d https_urls=%d",
                                direction,
                                batch_idx,
                                _pixellab_api_result_summary(result),
                                b64_n,
                                url_n,
                            )
                            plate_frames = _pixellab_animation_job_to_rgba_frames(
                                result,
                                canvas_size=canvas_size,
                                client=client,
                            )
                            logger.info(
                                "[pixellab/edit-animation] decoded_rgba_frames=%d direction=%s batch=%d",
                                len(plate_frames),
                                direction,
                                batch_idx,
                            )
                            if not plate_frames:
                                keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
                                logger.warning(
                                    "[pixellab/edit-animation] no decodable frames project=%s direction=%s batch=%d keys=%s",
                                    project_id,
                                    direction,
                                    batch_idx,
                                    keys,
                                )
                                raise ValueError(
                                    "Pixel Lab edit-animation returned no decodable frames. Response keys: %s" % keys
                                )
                            frames.extend(plate_frames[: len(frame_indices)])
                            append_usage_ledger_entry(
                                provider="pixellab",
                                endpoint="pixellab.edit-animation",
                                project_id=project_id,
                                status="success",
                                usage=client.last_usage,
                                job_id=result.get("job_id") if isinstance(result, dict) else None,
                                generation_id=result.get("generation_id") if isinstance(result, dict) else None,
                                metadata={"animation_name": animation_name, "direction": direction, "batch": batch_idx},
                            )

                        out_fc = min(frame_count, len(frames))
                        frames = frames[:out_fc]
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

                logger.info("[pixellab/edit-animation] ok project=%s animation=%s", project_id, animation_name)
                return self._send_json({"ok": True, "animation_name": animation_name, "description": description})

            build_clips_pixellab_match = re.fullmatch(r"/api/projects/([^/]+)/pixellab/build-clips", path)
            if build_clips_pixellab_match:
                project_id = build_clips_pixellab_match.group(1)
                logger.info("[pixellab/build-clips] start project=%s", project_id)
                project = load_project(project_id)
                project_dir = PROJECTS_ROOT / project_id
                existing = sync_pixellab_animation_clips(project_id, project=project, project_dir=project_dir)
                core_counts = {
                    name: (len((existing.get(name) or {}).get("frames") or []) if isinstance(existing.get(name), dict) else 0)
                    for name in ("idle", "walk", "run", "jump")
                }
                logger.info(
                    "[pixellab/build-clips] ok project=%s idle=%d walk=%d run=%d jump=%d",
                    project_id,
                    core_counts["idle"],
                    core_counts["walk"],
                    core_counts["run"],
                    core_counts["jump"],
                )
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
            logger.warning("POST %s — project not found", path)
            return self._send_error_json(HTTPStatus.NOT_FOUND, "Project not found")
        except ValueError as exc:
            logger.warning("POST %s — bad request: %s", path, exc)
            return self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except HttpRequestError as exc:
            logger.warning("POST %s — upstream error: %s", path, exc)
            return self._send_error_json(HTTPStatus.BAD_GATEWAY, str(exc))
        except PixelLabError as exc:
            logger.warning("POST %s — Pixel Lab: %s", path, exc)
            return self._send_error_json(HTTPStatus.BAD_GATEWAY, str(exc))
        except Exception as exc:
            logger.exception("POST %s — unhandled error: %s", path, exc)
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

    def _send_bytes(
        self,
        payload: bytes,
        *,
        content_type: str,
        filename: Optional[str] = None,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % filename.replace('"', ""))
        self.end_headers()
        self.wfile.write(payload)

    def _send_error_json(self, status: HTTPStatus, message: str) -> None:
        return self._send_json({"ok": False, "error": message}, status=status)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Solo AI Sprite Workbench server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument(
        "--log-level",
        default=os.environ.get("SPRITE_WORKBENCH_LOG_LEVEL", "INFO"),
        help="Python logging level (DEBUG, INFO, WARNING, …). Env: SPRITE_WORKBENCH_LOG_LEVEL.",
    )
    args = parser.parse_args()
    log_level = getattr(logging, str(args.log_level).upper(), logging.INFO)
    if not isinstance(log_level, int):
        log_level = logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("PIL").setLevel(logging.WARNING)
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
