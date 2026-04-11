from __future__ import annotations

import copy
import base64
import hashlib
import threading
import io
import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
import time
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat
from scripts import room_environment_v3 as envv3

PROJECTS_ROOT: Path
ROOT: Path
load_project: Callable[[str], Dict[str, Any]]
save_project: Callable[[Dict[str, Any]], None]
now_iso: Callable[[], str]
stable_hash: Callable[..., str]
append_history_event: Callable[[str, Dict[str, Any]], Dict[str, Any]]


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


logger = logging.getLogger(__name__)

# Temporary founder-approved isolation switch while we verify whether midground is
# contaminating runtime shell/border reads.
RUNTIME_REVIEW_DISABLE_MIDGROUND = True

_GEMINI_ERR_LOCK = threading.Lock()
_GEMINI_LAST_USER_ERROR: Optional[str] = None
_GEMINI_LAST_ERROR_AT: Optional[str] = None


def _set_gemini_last_error(err: Optional[str]) -> None:
    """Record last user-safe Gemini REST error for /api/ping diagnostics; clear on None."""
    global _GEMINI_LAST_USER_ERROR, _GEMINI_LAST_ERROR_AT
    with _GEMINI_ERR_LOCK:
        if err:
            _GEMINI_LAST_USER_ERROR = err
            _GEMINI_LAST_ERROR_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            _GEMINI_LAST_USER_ERROR = None
            _GEMINI_LAST_ERROR_AT = None


def gemini_last_error_snapshot() -> Dict[str, Any]:
    """Snapshot for health/ping: last image REST failure message (no secrets)."""
    with _GEMINI_ERR_LOCK:
        return {
            "message": _GEMINI_LAST_USER_ERROR,
            "recorded_at": _GEMINI_LAST_ERROR_AT,
        }


def _response_has_inline_image(data: Dict[str, Any]) -> bool:
    for cand in data.get("candidates") or []:
        for part in ((cand.get("content") or {}).get("parts") or []):
            inline = part.get("inlineData") or {}
            if inline.get("data"):
                return True
    return False


def gemini_image_probe() -> Dict[str, Any]:
    """Optional health check: one generateContent call with image modality (uses API quota)."""
    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip() or "gemini-2.5-flash-image"
    parts = [{
        "text": (
            "Generate a small PNG image: a flat solid dark gray (#1a1a1a) rectangle only. "
            "No text, no UI, no watermark."
        ),
    }]
    resp, err = _gemini_generate_content_rest(model, parts, response_modalities=["IMAGE", "TEXT"])
    if err:
        return {"ok": False, "error": err, "model": model}
    if not resp or not _response_has_inline_image(resp):
        return {"ok": False, "error": "no_image_in_response", "model": model}
    return {"ok": True, "model": model}


def _gemini_api_key() -> str:
    """Prefer GEMINI_API_KEY; accept GOOGLE_API_KEY (AI Studio default name)."""
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()


ART_DIRECTION_TEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "ruined-gothic",
        "label": "Ruined Gothic",
        "style_family": "dark fantasy ruins",
        "high_level_direction": "Broken gothic halls, damp stone, restrained color, readable traversal silhouettes, and sacred decay.",
        "negative_direction": "clean sci-fi surfaces, cartoon props, glossy plastics, bright cheerful saturation",
        "palette": {
            "dominant": ["#11161d", "#24343a", "#6f7f79"],
            "accent": ["#b58f52"],
            "avoid": ["#ffffff", "#ff3bf1"],
        },
        "shape_language": ["heavy arches", "fractured buttresses", "ritual circles"],
        "lighting_rules": ["low-key lighting", "single focal glow", "fog depth near floor"],
        "material_rules": ["wet stone", "aged iron", "dusty carvings"],
        "reference_suggestions": ["collapsed cathedral alcoves", "mossy stone vaults"],
    },
    {
        "template_id": "flooded-catacombs",
        "label": "Flooded Catacombs",
        "style_family": "submerged necropolis",
        "high_level_direction": "Tight burial passages, standing water, green-blue underlight, and claustrophobic silence.",
        "negative_direction": "sunlit vistas, heroic bright fantasy, high-tech machinery, comic-book colors",
        "palette": {
            "dominant": ["#0c1216", "#16333b", "#476f71"],
            "accent": ["#9cc6a3"],
            "avoid": ["#fefefe", "#ff6b4a"],
        },
        "shape_language": ["low vaults", "sunken thresholds", "narrow bridges"],
        "lighting_rules": ["underlit water reflections", "small overhead leaks", "mist above waterline"],
        "material_rules": ["wet limestone", "algae film", "oxidized bronze"],
        "reference_suggestions": ["flooded crypt steps", "submerged tomb walls"],
    },
    {
        "template_id": "overgrown-shrine",
        "label": "Overgrown Shrine",
        "style_family": "sacred ruin in nature",
        "high_level_direction": "Ancient temple geometry reclaimed by roots, filtered green light, and quiet reverence with danger underneath.",
        "negative_direction": "urban modern props, clean marble perfection, playful colors, futuristic holograms",
        "palette": {
            "dominant": ["#111811", "#29412d", "#72826a"],
            "accent": ["#d1b66b"],
            "avoid": ["#ff4fe2", "#ffffff"],
        },
        "shape_language": ["stepped plinths", "root-wrapped columns", "ritual gates"],
        "lighting_rules": ["canopy-filtered shafts", "soft pollen haze", "warm shrine focal light"],
        "material_rules": ["moss-covered stone", "weathered wood", "vines and roots"],
        "reference_suggestions": ["forest temple steps", "hidden moss altars"],
    },
    {
        "template_id": "industrial-underworks",
        "label": "Industrial Underworks",
        "style_family": "grim machinery and tunnels",
        "high_level_direction": "Sooty tunnel infrastructure, pressure vents, readable steel silhouettes, and old machines merged with masonry.",
        "negative_direction": "clean cyberpunk neon, white laboratory lighting, whimsical props, toy-like machinery",
        "palette": {
            "dominant": ["#141516", "#2f3132", "#5a625e"],
            "accent": ["#c48c43"],
            "avoid": ["#00ffff", "#f5f5f5"],
        },
        "shape_language": ["boxy ducts", "arched culverts", "heavy grates"],
        "lighting_rules": ["hazard edge highlights", "steam haze", "isolated utility lamps"],
        "material_rules": ["rusted steel", "stained concrete", "oily water"],
        "reference_suggestions": ["boiler culverts", "pump station tunnels"],
    },
    {
        "template_id": "ethereal-void",
        "label": "Ethereal Void",
        "style_family": "otherworldly absence",
        "high_level_direction": "Sparse geometry, drifting particles, spectral glows, and impossible depth while preserving platform readability.",
        "negative_direction": "busy clutter, comic energy effects, hard sci-fi controls, cheerful fantasy ornament",
        "palette": {
            "dominant": ["#0a0a12", "#251c36", "#4f5070"],
            "accent": ["#9da7ff"],
            "avoid": ["#00ff88", "#ffffff"],
        },
        "shape_language": ["thin bridges", "floating slabs", "haloed thresholds"],
        "lighting_rules": ["ambient backglow", "soft edge bloom", "depth haze"],
        "material_rules": ["cold stone", "astral dust", "glass-like void seams"],
        "reference_suggestions": ["floating altar fragments", "cosmic stone spans"],
    },
]

ROOM_ENVIRONMENT_ARCHETYPES: List[Dict[str, Any]] = [
    {
        "archetype_id": "corridor-transition",
        "label": "Corridor Transition",
        "starter_brief": "A transitional room that connects two spaces, keeps movement clear, and quietly reinforces the project’s mood.",
    },
    {
        "archetype_id": "flooded-passage",
        "label": "Flooded Passage",
        "starter_brief": "A low, damp route with water pressure, reflective surfaces, and tension around footing and visibility.",
    },
    {
        "archetype_id": "shrine-chamber",
        "label": "Shrine Chamber",
        "starter_brief": "A room centered on ritual architecture, controlled focal lighting, and a sense of significance rather than noise.",
    },
    {
        "archetype_id": "ambush-pocket",
        "label": "Ambush Pocket",
        "starter_brief": "A compact room with concealment, threatening sightlines, and just enough clarity for the player to recover and react.",
    },
    {
        "archetype_id": "vertical-traversal-shaft",
        "label": "Vertical Traversal Shaft",
        "starter_brief": "A tall room built around upward and downward movement, layered depth, and landmarks that help the player read height.",
    },
    {
        "archetype_id": "safe-room",
        "label": "Safe Room",
        "starter_brief": "A calmer room that offers relief, readable staging, and a memorable visual identity without breaking the project style.",
    },
    {
        "archetype_id": "boss-arena",
        "label": "Boss Arena",
        "starter_brief": "A large confrontation room with a strong focal landmark, dramatic lighting, and clear playable boundaries.",
    },
    {
        "archetype_id": "hidden-cache",
        "label": "Hidden Cache",
        "starter_brief": "A secret reward space that feels tucked away, intimate, and visually distinct while staying inside the project direction.",
    },
    {
        "archetype_id": "ritual-threshold",
        "label": "Ritual Threshold",
        "starter_brief": "A liminal room that signals crossing into a new space through framing, light, and restrained symbolic detail.",
    },
    {
        "archetype_id": "exterior-overlook",
        "label": "Exterior Overlook",
        "starter_brief": "A room with a sense of outward view or exposed depth while still keeping the playable route easy to read.",
    },
]


def list_art_direction_templates() -> List[Dict[str, Any]]:
    return copy.deepcopy(ART_DIRECTION_TEMPLATES)


def list_room_environment_archetypes() -> List[Dict[str, Any]]:
    return copy.deepcopy(ROOM_ENVIRONMENT_ARCHETYPES)


def _template_by_id(template_id: str) -> Optional[Dict[str, Any]]:
    return next((item for item in ART_DIRECTION_TEMPLATES if item["template_id"] == template_id), None)


def _archetype_by_id(archetype_id: str) -> Optional[Dict[str, Any]]:
    return next((item for item in ROOM_ENVIRONMENT_ARCHETYPES if item["archetype_id"] == archetype_id), None)


def default_art_direction() -> Dict[str, Any]:
    first = ART_DIRECTION_TEMPLATES[0]
    return {
        "version": 1,
        "locked": False,
        "template_id": first["template_id"],
        "template_origin": "builtin",
        "style_family": first["style_family"],
        "high_level_direction": first["high_level_direction"],
        "negative_direction": first["negative_direction"],
        "palette": copy.deepcopy(first["palette"]),
        "shape_language": list(first["shape_language"]),
        "lighting_rules": list(first["lighting_rules"]),
        "material_rules": list(first["material_rules"]),
        "reference_suggestions": list(first["reference_suggestions"]),
        "frozen_concept_ids": [],
        "frozen_concepts": [],
        "concept_board": {
            "status": "idle",
            "images": [],
            "last_generated_at": None,
            "generation_error": None,
            "prompt_summary": "",
        },
        "updated_at": now_iso(),
    }


def normalize_art_direction(payload: Optional[Dict[str, Any]], current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source = copy.deepcopy(current or default_art_direction())
    raw = payload if isinstance(payload, dict) else {}
    template_id = str(raw.get("template_id") or source.get("template_id") or ART_DIRECTION_TEMPLATES[0]["template_id"]).strip()
    template = _template_by_id(template_id) or ART_DIRECTION_TEMPLATES[0]
    base = default_art_direction()
    base.update({
        "template_id": template["template_id"],
        "style_family": template["style_family"],
        "high_level_direction": template["high_level_direction"],
        "negative_direction": template["negative_direction"],
        "palette": copy.deepcopy(template["palette"]),
        "shape_language": list(template["shape_language"]),
        "lighting_rules": list(template["lighting_rules"]),
        "material_rules": list(template["material_rules"]),
        "reference_suggestions": list(template["reference_suggestions"]),
    })
    out = copy.deepcopy(source)
    out.setdefault("version", 1)
    out["template_id"] = template["template_id"]
    out["template_origin"] = "builtin"
    for key in (
        "style_family",
        "high_level_direction",
        "negative_direction",
        "shape_language",
        "lighting_rules",
        "material_rules",
        "reference_suggestions",
    ):
        incoming = raw.get(key)
        if key.endswith("_rules") or key in {"shape_language", "reference_suggestions"}:
            value = [str(item).strip() for item in (incoming if isinstance(incoming, list) else base[key]) if str(item).strip()]
        else:
            value = str(incoming if incoming is not None else base[key]).strip()
        out[key] = value or copy.deepcopy(base[key])
    palette = raw.get("palette")
    if isinstance(palette, dict):
        out["palette"] = {
            "dominant": [str(item).strip() for item in (palette.get("dominant") or base["palette"]["dominant"]) if str(item).strip()],
            "accent": [str(item).strip() for item in (palette.get("accent") or base["palette"]["accent"]) if str(item).strip()],
            "avoid": [str(item).strip() for item in (palette.get("avoid") or base["palette"]["avoid"]) if str(item).strip()],
        }
    else:
        out["palette"] = copy.deepcopy(base["palette"])
    if (
        out["style_family"] != template["style_family"]
        or out["high_level_direction"] != template["high_level_direction"]
        or out["negative_direction"] != template["negative_direction"]
        or out["palette"] != template["palette"]
    ):
        out["template_origin"] = "customized_builtin"
    if raw.get("template_origin") == "custom":
        out["template_origin"] = "custom"
    out["locked"] = bool(raw.get("locked", source.get("locked", False)))
    out["frozen_concept_ids"] = [str(item).strip() for item in (raw.get("frozen_concept_ids") or source.get("frozen_concept_ids") or []) if str(item).strip()]
    out["frozen_concepts"] = copy.deepcopy(raw.get("frozen_concepts") or source.get("frozen_concepts") or [])
    concept_board = raw.get("concept_board")
    if not isinstance(concept_board, dict):
        concept_board = copy.deepcopy((source.get("concept_board") if isinstance(source.get("concept_board"), dict) else base.get("concept_board")) or {})
    out["concept_board"] = {
        "status": str(concept_board.get("status") or "idle"),
        "images": copy.deepcopy(concept_board.get("images") or []),
        "last_generated_at": concept_board.get("last_generated_at"),
        "generation_error": concept_board.get("generation_error"),
        "prompt_summary": str(concept_board.get("prompt_summary") or ""),
    }
    biome_packs = raw.get("biome_packs")
    if not isinstance(biome_packs, list):
        biome_packs = copy.deepcopy(source.get("biome_packs") or [])
    normalized_biome_packs: List[Dict[str, Any]] = []
    for item in biome_packs:
        if not isinstance(item, dict):
            continue
        biome_id = str(item.get("biome_id") or "").strip()
        if not biome_id:
            continue
        normalized_biome_packs.append({
            "biome_id": biome_id,
            "label": str(item.get("label") or biome_id.replace("-", " ").title()).strip() or biome_id,
            "locked_direction": copy.deepcopy(item.get("locked_direction") or {}),
            "locked_concept_ids": [str(entry).strip() for entry in (item.get("locked_concept_ids") or []) if str(entry).strip()],
            "template_library": copy.deepcopy(item.get("template_library") or []),
            "border_first_contract": _normalize_border_first_contract(item.get("border_first_contract"), item.get("template_library") or []),
            "version": int(item.get("version") or 1),
            "locked": bool(item.get("locked", True)),
            "updated_at": item.get("updated_at") or now_iso(),
        })
    out["biome_packs"] = normalized_biome_packs
    out["updated_at"] = now_iso()
    return out


def _slugify(text: str, fallback: str = "value") -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(text or "").strip()).strip("-")
    cleaned = "-".join(chunk for chunk in cleaned.split("-") if chunk)
    return cleaned or fallback


BORDER_FIRST_CONTRACT_VERSION = "border-first-v1"

BORDER_FIRST_BIOME_COMPONENT_TYPES: Tuple[str, ...] = (
    "border_piece",
    "background_far_piece",
    "platform_piece",
    "door_piece",
)

BORDER_FIRST_PENDING_COMPONENT_TYPES: Tuple[str, ...] = (
    "border_piece",
    "background_far_piece",
    "platform_piece",
)

BORDER_FIRST_ROOM_ASSET_TYPES: Tuple[str, ...] = (
    "room_border_shell",
    "room_background",
    "room_platforms",
    "room_doors",
)

BORDER_FIRST_BIOME_COMPONENTS: Tuple[Dict[str, Any], ...] = (
    {"component_type": "border_piece", "variant_family": "border", "size": (1600, 1200), "orientation": "full", "transparency_mode": "opaque", "visual_role": "room_shell_border"},
    {"component_type": "background_far_piece", "variant_family": "background", "size": (1600, 1200), "orientation": "full", "transparency_mode": "opaque", "visual_role": "far_depth"},
    {"component_type": "platform_piece", "variant_family": "platform", "size": (320, 72), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "gameplay_platform"},
    {"component_type": "door_piece", "variant_family": "door", "size": (192, 288), "orientation": "vertical", "transparency_mode": "alpha", "visual_role": "transition"},
)


def _normalize_border_first_contract(value: Any, template_library: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    template_library = template_library or []
    template_by_component = {
        str(item.get("component_type") or "").strip(): item
        for item in template_library
        if isinstance(item, dict) and str(item.get("component_type") or "").strip()
    }
    biome_templates = {}
    existing_templates = raw.get("biome_templates") if isinstance(raw.get("biome_templates"), dict) else {}
    for component_type in BORDER_FIRST_BIOME_COMPONENT_TYPES:
        mapped = str(existing_templates.get(component_type) or "").strip()
        if not mapped:
            mapped = str((template_by_component.get(component_type) or {}).get("template_id") or "").strip()
        biome_templates[component_type] = mapped or None
    room_assets = {}
    existing_room_assets = raw.get("room_assets") if isinstance(raw.get("room_assets"), dict) else {}
    for asset_type in BORDER_FIRST_ROOM_ASSET_TYPES:
        room_assets[asset_type] = str(existing_room_assets.get(asset_type) or "planned").strip() or "planned"
    generated_components = {
        component_type
        for component_type, item in template_by_component.items()
        if str((item or {}).get("source_template_kind") or "").strip() == "gemini_biome"
    }
    if all(component in generated_components for component in BORDER_FIRST_BIOME_COMPONENT_TYPES):
        status = "biome_templates_generated"
    elif any(component in generated_components for component in BORDER_FIRST_BIOME_COMPONENT_TYPES):
        status = "partial_biome_templates_generated"
    else:
        status = str(raw.get("status") or "schema_only")
    return {
        "contract_version": str(raw.get("contract_version") or BORDER_FIRST_CONTRACT_VERSION),
        "status": status,
        "authoritative": False,
        "canonical_shell_template": "border_piece",
        "biome_component_types": list(BORDER_FIRST_BIOME_COMPONENT_TYPES),
        "room_asset_types": list(BORDER_FIRST_ROOM_ASSET_TYPES),
        "biome_component_specs": [copy.deepcopy(item) for item in BORDER_FIRST_BIOME_COMPONENTS],
        "biome_templates": biome_templates,
        "room_assets": room_assets,
        "compositing": {
            "mode": "deterministic_mask_composite",
            "center_handling": "mask_based_extraction",
            "procedural_generation_allowed": False,
        },
        "legacy_split_shell_reference_only": True,
    }


V1_BESPOKE_COMPONENTS: Tuple[Dict[str, Any], ...] = (
    {"component_type": "background_plate", "variant_family": "background", "size": (1600, 1200), "orientation": "full", "transparency_mode": "opaque", "visual_role": "far_depth"},
    {"component_type": "midground_frame", "variant_family": "midground", "size": (1600, 1200), "orientation": "full", "transparency_mode": "alpha", "visual_role": "side_frame"},
    {"component_type": "foreground_frame", "variant_family": "foreground", "size": (1600, 1200), "orientation": "full", "transparency_mode": "opaque", "visual_role": "structural_foreground"},
    {"component_type": "wall_piece", "variant_family": "walls", "size": (512, 1200), "orientation": "vertical", "transparency_mode": "opaque", "visual_role": "structural_wall"},
    {"component_type": "ceiling_piece", "variant_family": "ceiling", "size": (1600, 224), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "structural_ceiling"},
    {"component_type": "primary_floor_piece", "variant_family": "floor", "size": (512, 96), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "main_route"},
    {"component_type": "hero_platform_piece", "variant_family": "platform", "size": (320, 72), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "hero_platform"},
    {"component_type": "door_piece", "variant_family": "door", "size": (192, 288), "orientation": "vertical", "transparency_mode": "alpha", "visual_role": "transition"},
)

V1_TEMPLATE_SOURCE_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "background_plate": ("background.png",),
    "midground_frame": ("midground_arches.png",),
    "foreground_frame": ("foreground_frame.png",),
    "wall_piece": ("wall.png",),
    "ceiling_piece": ("ceiling.png",),
    "primary_floor_piece": ("floor_cap_strip.png",),
    "hero_platform_piece": ("platform_ledge_strip.png",),
    "door_piece": ("door.png",),
}

STRUCTURAL_BIOME_COMPONENT_TYPES: Tuple[str, ...] = (
    "foreground_frame",
    "primary_floor_piece",
    "wall_piece",
    "ceiling_piece",
    "hero_platform_piece",
)

STRUCTURAL_BIOME_REFERENCE_PRIORITY: Dict[str, Tuple[str, ...]] = {
    "foreground_frame": ("primary_floor_piece", "wall_piece", "ceiling_piece", "hero_platform_piece"),
    "primary_floor_piece": ("wall_piece", "hero_platform_piece"),
    "wall_piece": ("primary_floor_piece", "ceiling_piece"),
    "ceiling_piece": ("primary_floor_piece", "wall_piece"),
    "hero_platform_piece": ("primary_floor_piece", "wall_piece"),
}


def _default_biome_id(direction: Dict[str, Any]) -> str:
    template_id = str(direction.get("template_id") or "ruined-gothic").strip()
    return f"{_slugify(template_id, 'biome')}-v1"


def _border_first_generation_contract() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "planned",
        "biome_template_types": [entry["component_type"] for entry in BORDER_FIRST_BIOME_COMPONENTS],
        "room_asset_types": list(BORDER_FIRST_ROOM_ASSET_TYPES),
        "canonical_shell_template_type": "border_piece",
        "mask_compositing_required": True,
        "procedural_generation_allowed": False,
        "procedural_postprocess_allowed": True,
    }


def _append_pending_border_first_templates(
    template_library: List[Dict[str, Any]],
    biome_id: str,
    direction: Dict[str, Any],
) -> None:
    existing_components = {
        str(item.get("component_type") or "").strip()
        for item in template_library
        if isinstance(item, dict)
    }
    for entry in BORDER_FIRST_BIOME_COMPONENTS:
        component_type = entry["component_type"]
        if component_type in existing_components:
            continue
        rel_path = Path("art_direction_biomes") / biome_id / f"{component_type}.png"
        template_library.append({
            "template_id": f"{biome_id}-{component_type}",
            "component_type": component_type,
            "variant_family": entry["variant_family"],
            "image_path": rel_path.as_posix(),
            "width": entry["size"][0],
            "height": entry["size"][1],
            "orientation": entry["orientation"],
            "transparency_mode": entry["transparency_mode"],
            "visual_role": entry["visual_role"],
            "source_art_direction_version": int(direction.get("version") or 1),
            "approved": False,
            "locked": True,
            "adaptation_mode": "gemini",
            "source_template_kind": "pending_generation",
            "source_template_path": None,
            "updated_at": now_iso(),
        })


def _border_first_legacy_reference_paths(project_dir: Path, direction: Optional[Dict[str, Any]], component_type: str) -> List[Path]:
    biome_id = _default_biome_id(direction or {})
    biome_root = project_dir / "art_direction_biomes" / biome_id
    candidates_by_component = {
        "border_piece": [],
        "background_far_piece": [],
        "background_mid_piece": [],
        "platform_piece": [],
        "door_piece": ["door_piece.png"],
    }
    refs: List[Path] = []
    for name in candidates_by_component.get(component_type, []):
        candidate = biome_root / name
        if candidate.exists() and candidate not in refs:
            refs.append(candidate)
    return refs


def _default_biome_label(direction: Dict[str, Any]) -> str:
    return str(direction.get("style_family") or direction.get("template_id") or "Biome").strip().title()


def _component_adaptation_mode(component_type: str) -> str:
    if component_type == "room_shell_foreground":
        return "gemini"
    if component_type in {
        "background_plate",
        "midground_frame",
        "midground_side_frame",
        "door_piece",
        "door_frame",
    }:
        return "direct"
    if component_type in {"foreground_frame", "primary_floor_piece", "hero_platform_piece"}:
        return "stretch"
    if component_type in {"hero_platform_top", "hero_platform_face", "pit_interior"}:
        return "stretch"
    return "gemini"


def _biome_component_generation_order(component_type: str) -> int:
    order = {
        "border_piece": 0,
        "background_far_piece": 1,
        "background_mid_piece": 2,
        "platform_piece": 3,
        "primary_floor_piece": 0,
        "foreground_frame": 1,
        "wall_piece": 2,
        "ceiling_piece": 3,
        "hero_platform_piece": 4,
        "background_plate": 10,
        "midground_frame": 11,
        "room_shell_foreground": 11,
        "door_piece": 12,
    }
    return order.get(component_type, 99)


def _biome_structural_reference_paths(
    component_type: str,
    biome_pack: Dict[str, Any],
    project_dir: Path,
    generated_paths: Dict[str, Path],
) -> List[Path]:
    if component_type not in STRUCTURAL_BIOME_COMPONENT_TYPES:
        return []
    if component_type in {"wall_piece", "ceiling_piece", "primary_floor_piece"}:
        # Core structural biome templates should be generated from locked art
        # direction plus their own component-specific seed only. Feeding sibling
        # structural pieces back in makes the generic templates imitate one
        # another's mistakes, which is how wall/ceiling/floor semantics collapse
        # into arches, headers, and floor-plane perspective.
        return []
    template_by_component: Dict[str, Dict[str, Any]] = {
        str(item.get("component_type") or "").strip(): item
        for item in (biome_pack.get("template_library") or [])
        if isinstance(item, dict)
    }
    refs: List[Path] = []
    for sibling_type in STRUCTURAL_BIOME_REFERENCE_PRIORITY.get(component_type, ()):
        candidate = generated_paths.get(sibling_type)
        if not candidate:
            template = template_by_component.get(sibling_type)
            rel = str((template or {}).get("image_path") or "").strip()
            if rel:
                path = project_dir / rel
                if path.exists():
                    candidate = path
        if candidate and candidate.exists() and candidate not in refs:
            refs.append(candidate)
        if len(refs) >= 2:
            break
    return refs


def _write_foreground_frame_generation_guide(project_dir: Path) -> Path:
    """Create a temporary reference image for foreground_frame generation only.

    This guide is intentionally ephemeral and must never be installed into the
    biome template library, used by runtime composition, or treated as fallback
    production content. It exists solely to give Gemini a cleaner structural
    perimeter target during the generation request.
    """
    guide_root = project_dir / ".tmp_biome_generation_refs"
    guide_root.mkdir(parents=True, exist_ok=True)
    guide_path = guide_root / "foreground_frame-guide.png"
    size = (ATLAS_WIDTH, ATLAS_HEIGHT)
    img = Image.new("RGBA", size, (108, 108, 108, 255))
    draw = ImageDraw.Draw(img)
    ceiling_h = FOREGROUND_FRAME_BORDER_TOP_PX
    floor_y = ATLAS_HEIGHT - FOREGROUND_FRAME_BORDER_BOTTOM_PX
    left_w = FOREGROUND_FRAME_BORDER_SIDE_PX
    right_w = FOREGROUND_FRAME_BORDER_SIDE_PX
    wall_top = ceiling_h
    wall_bottom = floor_y
    center_left = left_w
    center_right = size[0] - right_w
    # Lighter cap/floor than side walls (readable template) but not near-white — avoids paper halos in outputs.
    band_fill = (88, 92, 98, 255)
    wall_fill = (36, 40, 46, 255)
    center_fill = FOREGROUND_FRAME_CENTER_KEY_RGB + (255,)
    guide_line = (78, 84, 92, 255)

    # Exact occupied envelopes only: top cap, bottom band, left wall, right wall,
    # and an explicit chroma-key center reserve. Keep this sparse so Gemini learns
    # shape, not a deterministic fallback texture treatment.
    draw.rectangle((0, 0, size[0], ceiling_h), fill=band_fill)
    draw.rectangle((0, floor_y, size[0], size[1]), fill=band_fill)
    draw.rectangle((0, wall_top, left_w, wall_bottom), fill=wall_fill)
    draw.rectangle((center_right, wall_top, size[0], wall_bottom), fill=wall_fill)
    draw.rectangle((center_left, wall_top, center_right, wall_bottom), fill=center_fill)

    # Keep the guide purely geometric. A single-pixel legal boundary rail is
    # enough to anchor the mask without introducing literal art details.
    draw.line((0, ceiling_h - 1, size[0], ceiling_h - 1), fill=guide_line, width=1)
    draw.line((center_left, wall_top, center_left, wall_bottom), fill=guide_line, width=1)
    draw.line((center_right, wall_top, center_right, wall_bottom), fill=guide_line, width=1)

    img.putpixel((size[0] - 1, size[1] - 1), (77, 89, 97, 254))
    img.save(guide_path)
    return guide_path


def _write_border_piece_generation_guide(project_dir: Path) -> Path:
    guide_root = project_dir / ".tmp_biome_generation_refs"
    guide_root.mkdir(parents=True, exist_ok=True)
    guide_path = guide_root / "border_piece-guide.png"
    size = (ATLAS_WIDTH, ATLAS_HEIGHT)
    img = Image.new("RGBA", size, (20, 20, 20, 255))
    draw = ImageDraw.Draw(img)
    top_h = BORDER_PIECE_BORDER_TOP_PX
    bottom_h = BORDER_PIECE_BORDER_BOTTOM_PX
    side_w = BORDER_PIECE_BORDER_SIDE_PX
    frame_fill = (52, 56, 62, 255)
    center_fill = (64, 64, 64, 255)
    draw.rectangle((0, 0, size[0], top_h), fill=frame_fill)
    draw.rectangle((0, size[1] - bottom_h, size[0], size[1]), fill=frame_fill)
    draw.rectangle((0, top_h, side_w, size[1] - bottom_h), fill=frame_fill)
    draw.rectangle((size[0] - side_w, top_h, size[0], size[1] - bottom_h), fill=frame_fill)
    draw.rectangle((side_w, top_h, size[0] - side_w, size[1] - bottom_h), fill=center_fill)
    draw.line((0, top_h - 1, size[0], top_h - 1), fill=(82, 88, 96, 255), width=2)
    img.save(guide_path)
    return guide_path


def _write_platform_piece_generation_guide(project_dir: Path) -> Path:
    guide_root = project_dir / ".tmp_biome_generation_refs"
    guide_root.mkdir(parents=True, exist_ok=True)
    guide_path = guide_root / "platform_piece-guide.png"
    size = (320, 72)
    img = Image.new("RGBA", size, (38, 44, 50, 255))
    draw = ImageDraw.Draw(img)
    top_h = 14
    face_h = 46
    draw.rectangle((0, 0, size[0], top_h), fill=(96, 104, 112, 255))
    draw.rectangle((0, top_h, size[0], top_h + face_h), fill=(22, 28, 34, 255))
    draw.rectangle((0, top_h + face_h, size[0], size[1]), fill=(46, 54, 62, 255))
    draw.line((0, top_h, size[0], top_h), fill=(118, 126, 134, 255), width=1)
    img.save(guide_path)
    return guide_path


def _write_background_far_piece_generation_guide(project_dir: Path) -> Path:
    guide_root = project_dir / ".tmp_biome_generation_refs"
    guide_root.mkdir(parents=True, exist_ok=True)
    guide_path = guide_root / "background_far_piece-guide.png"
    size = (1600, 1200)
    img = Image.new("RGBA", size, (48, 56, 64, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, size[0], 240), fill=(58, 66, 74, 255))
    draw.rectangle((0, 240, size[0], 900), fill=(72, 82, 90, 255))
    draw.rectangle((0, 900, size[0], size[1]), fill=(42, 48, 54, 255))
    draw.rectangle((180, 300, 1420, 920), fill=(82, 92, 100, 255))
    img.save(guide_path)
    return guide_path


def _write_foreground_frame_style_swatch(project_dir: Path, direction: Optional[Dict[str, Any]] = None) -> Optional[Path]:
    """Create a temporary material-family swatch for foreground_frame generation only.

    This is a style-only anchor sourced from existing biome structural pieces.
    It must never be installed into the biome template library or used at runtime.
    """
    biome_root = project_dir / "art_direction_biomes" / "ruined-gothic-v1"
    wall_path = biome_root / "wall_piece.png"
    ceiling_path = biome_root / "ceiling_piece.png"
    swatch_root = project_dir / ".tmp_biome_generation_refs"
    swatch_root.mkdir(parents=True, exist_ok=True)
    swatch_path = swatch_root / "foreground_frame-style.png"
    palette = copy.deepcopy((direction or {}).get("palette") or {})
    spec = {
        "theme_id": str((direction or {}).get("template_id") or ""),
        "description": str((direction or {}).get("high_level_direction") or ""),
        "mood": str((direction or {}).get("style_family") or ""),
        "lighting": ", ".join((direction or {}).get("lighting_rules") or []),
        "tags": [_slugify((direction or {}).get("template_id") or "biome")],
        "components": {},
    }
    flags = _environment_style_flags(spec)
    shell_family = _infer_shell_family(spec)
    try:
        if wall_path.exists():
            wall = Image.open(wall_path).convert("RGBA")
        else:
            fallback_wall = swatch_root / "_style-wall.png"
            _fallback_tile_asset(fallback_wall, palette, (512, 1200), "wall", flags, shell_family)
            wall = Image.open(fallback_wall).convert("RGBA")
        # Always derive the swatch ceiling row from the deterministic fallback ceiling
        # rather than the current ceiling_piece.png, since the live ceiling asset can
        # contain detached block language that leaks directly into foreground_frame.
        fallback_ceiling = swatch_root / "_style-ceiling.png"
        _fallback_ceiling_asset(fallback_ceiling, palette, shell_family)
        ceiling = Image.open(fallback_ceiling).convert("RGBA")
    except Exception:
        return None
    # Keep the style swatch material-driven but avoid hard separator bars,
    # since those get literalized into fake lintel/shadow bands in the atlas.
    canvas = Image.new("RGBA", (768, 224), (26, 32, 38, 255))
    ceiling_crop = ceiling.crop((320, 0, 1280, 176)).resize((768, 88), Image.Resampling.LANCZOS)
    wall_crop = wall.crop((120, 320, 392, 920)).resize((768, 120), Image.Resampling.LANCZOS)
    wall_crop = wall_crop.filter(ImageFilter.GaussianBlur(radius=1.2))
    canvas.alpha_composite(ceiling_crop, (0, 0))
    canvas.alpha_composite(wall_crop, (0, 88))
    canvas.save(swatch_path)
    return swatch_path


def _dump_rejected_foreground_frame_candidate(project_dir: Path, source_path: Path) -> Optional[Path]:
    """Persist the rejected foreground_frame candidate for visual debugging only.

    This dump is non-production evidence. It must never be referenced by the
    biome template library, runtime composition, or fallback install logic.
    """
    if not source_path.exists():
        return None
    dump_root = project_dir / ".tmp_biome_generation_rejections"
    dump_root.mkdir(parents=True, exist_ok=True)
    dump_path = dump_root / "foreground_frame-rejected-latest.png"
    shutil.copyfile(source_path, dump_path)
    return dump_path


def _dump_rejected_structural_candidate(project_dir: Path, component_type: str, source_path: Path) -> Optional[Path]:
    if component_type not in {"border_piece", "wall_piece", "ceiling_piece", "primary_floor_piece"}:
        return None
    if not source_path.exists():
        return None
    dump_root = project_dir / ".tmp_biome_generation_rejections"
    dump_root.mkdir(parents=True, exist_ok=True)
    dump_path = dump_root / f"{component_type}-rejected-latest.png"
    shutil.copyfile(source_path, dump_path)
    return dump_path


def _foreground_frame_staging_path(project_dir: Path) -> Path:
    staging_root = project_dir / ".tmp_biome_generation_staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    return staging_root / "foreground_frame-candidate.png"


def _structural_biome_staging_path(project_dir: Path, component_type: str) -> Path:
    staging_root = project_dir / ".tmp_biome_generation_staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    return staging_root / f"{component_type}-candidate.png"


def _foreground_frame_raw_candidate_path(staging_path: Path) -> Path:
    return staging_path.with_name(f"{staging_path.stem}-raw{staging_path.suffix}")


def _foreground_frame_attempt_trace_path(project_dir: Path) -> Path:
    trace_root = project_dir / ".tmp_biome_generation_rejections"
    trace_root.mkdir(parents=True, exist_ok=True)
    return trace_root / "foreground_frame-attempt-latest.json"


def _file_sha256(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_foreground_frame_attempt_trace(
    project_dir: Path,
    *,
    attempt_index: int,
    prompt: str,
    refs: List[Path],
    output_path: Path,
    existed_before: bool,
    hash_before: Optional[str],
    generation_ok: bool,
    direction: Dict[str, Any],
    validation_errors: Optional[List[str]] = None,
) -> None:
    trace_path = _foreground_frame_attempt_trace_path(project_dir)
    trace: Dict[str, Any]
    if trace_path.exists():
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
        except Exception:
            trace = {}
    else:
        trace = {}
    attempts = trace.setdefault("attempts", [])
    output_exists = output_path.exists()
    output_hash = _file_sha256(output_path)
    raw_path = _foreground_frame_raw_candidate_path(output_path)
    fallback_probe_path = raw_path if raw_path.exists() else output_path
    attempts.append({
        "attempt_index": attempt_index,
        "created_at": now_iso(),
        "gemini_api_key_present": bool(_gemini_api_key()),
        "gemini_image_model": os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip() or "gemini-2.5-flash-image",
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "refs": [
            {
                "path": str(path.relative_to(project_dir).as_posix()) if path.exists() and path.is_relative_to(project_dir) else str(path),
                "exists": path.exists(),
                "sha256": _file_sha256(path),
            }
            for path in refs
        ],
        "output_path": str(output_path.relative_to(project_dir).as_posix()) if output_path.is_relative_to(project_dir) else str(output_path),
        "output_existed_before": existed_before,
        "output_sha256_before": hash_before,
        "generation_ok": generation_ok,
        "output_exists_after_generation": output_exists,
        "output_sha256_after_generation": output_hash,
        "matches_fallback_seed": bool(output_exists and _foreground_frame_matches_fallback_seed(fallback_probe_path, direction)),
        "validation_errors": list(validation_errors or []),
    })
    trace_path.write_text(json.dumps(trace, indent=2), encoding="utf-8")


def _biome_generation_reference_paths(
    component_type: str,
    abs_path: Path,
    project_dir: Path,
    direction: Optional[Dict[str, Any]] = None,
) -> List[Path]:
    refs: List[Path] = []
    # Do not feed the current saved structural biome source back into its own
    # iteration loop. Reusing a broken source image teaches Gemini to preserve
    # the exact opening/header/floor-perspective mistakes we are trying to remove.
    if component_type not in STRUCTURAL_BIOME_COMPONENT_TYPES and component_type not in {"border_piece", "platform_piece"} and abs_path.exists():
        refs.append(abs_path)
    if component_type in {"wall_piece", "ceiling_piece", "primary_floor_piece"} and direction:
        spec = {
            "theme_id": str(direction.get("template_id") or ""),
            "description": str(direction.get("high_level_direction") or ""),
            "mood": str(direction.get("style_family") or ""),
            "lighting": ", ".join(direction.get("lighting_rules") or []),
            "tags": [_slugify(direction.get("template_id") or "biome")],
            "components": {},
        }
        flags = _environment_style_flags(spec)
        shell_family = _infer_shell_family(spec)
        palette = copy.deepcopy(direction.get("palette") or {})
        ref_root = project_dir / ".tmp_biome_generation_refs"
        ref_root.mkdir(parents=True, exist_ok=True)
        seed_ref = ref_root / f"{component_type}-seed.png"
        _seed_biome_template_asset(seed_ref, component_type, palette, flags, shell_family)
        refs.append(seed_ref)
    if component_type == "border_piece":
        refs.extend(_border_first_legacy_reference_paths(project_dir, direction, component_type))
        guide_path = _write_border_piece_generation_guide(project_dir)
        refs.append(guide_path)
    elif component_type in {"background_far_piece", "background_mid_piece", "platform_piece", "door_piece"}:
        refs.extend(_border_first_legacy_reference_paths(project_dir, direction, component_type))
    if component_type == "background_far_piece":
        refs.append(_write_background_far_piece_generation_guide(project_dir))
    if component_type == "foreground_frame":
        style_swatch = _write_foreground_frame_style_swatch(project_dir, direction)
        if style_swatch is not None:
            refs.append(style_swatch)
        guide_path = _write_foreground_frame_generation_guide(project_dir)
        refs.append(guide_path)
    if component_type == "platform_piece":
        refs.append(_write_platform_piece_generation_guide(project_dir))
    return refs


def _foreground_frame_should_use_structural_sibling_refs() -> bool:
    # The shared foreground atlas is the source-of-truth structural contract.
    # Feeding back existing sibling structural PNGs like ceiling/floor/platform
    # can teach Gemini fragment language and floating blocks instead of a single
    # perimeter shell diagram.
    return False


def _find_curated_template_source(project_id: str, component_type: str) -> Optional[Path]:
    if component_type in STRUCTURAL_BIOME_COMPONENT_TYPES:
        # Structural biome templates should not be bootstrapped from prior
        # room outputs. That cross-room reuse bakes stale downstream artifacts
        # back into the canonical biome kit and destabilizes structural priors.
        return None
    root = PROJECTS_ROOT / project_id / "room_environment_assets"
    if not root.exists():
        return None
    for room_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        for filename in V1_TEMPLATE_SOURCE_CANDIDATES.get(component_type, ()):
            candidate = room_dir / filename
            if candidate.exists():
                return candidate
    return None


def _install_component_template_asset(
    project_id: str,
    output_path: Path,
    component_type: str,
    palette: Dict[str, Any],
    flags: Dict[str, bool],
    shell_family: str,
    target_size: Tuple[int, int],
    transparent: bool,
) -> Tuple[str, Optional[str]]:
    curated_source = _find_curated_template_source(project_id, component_type)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if curated_source and curated_source.exists():
        shutil.copyfile(curated_source, output_path)
        _fit_image_to_size(output_path, target_size, transparent=transparent)
        return "legacy_asset", str(curated_source.relative_to(PROJECTS_ROOT / project_id).as_posix())
    _seed_biome_template_asset(output_path, component_type, palette, flags, shell_family)
    _fit_image_to_size(output_path, target_size, transparent=transparent)
    return "fallback_seed", None


def _refresh_biome_pack_templates(project: Dict[str, Any], direction: Dict[str, Any]) -> Dict[str, Any]:
    project_id = str(project.get("project_id") or "").strip()
    if not project_id:
        return direction
    palette = copy.deepcopy(direction.get("palette") or {})
    spec = {
        "theme_id": str(direction.get("template_id") or ""),
        "description": str(direction.get("high_level_direction") or ""),
        "mood": str(direction.get("style_family") or ""),
        "lighting": ", ".join(direction.get("lighting_rules") or []),
        "tags": [_slugify(direction.get("template_id") or "biome")],
        "components": {},
    }
    flags = _environment_style_flags(spec)
    shell_family = _infer_shell_family(spec)
    for pack in direction.get("biome_packs") or []:
        if not isinstance(pack, dict):
            continue
        existing_components = {
            str(item.get("component_type") or "").strip()
            for item in (pack.get("template_library") or [])
            if isinstance(item, dict)
        }
        for entry in V1_BESPOKE_COMPONENTS:
            if entry["component_type"] in existing_components:
                continue
            rel_path = Path("art_direction_biomes") / str(pack.get("biome_id") or _default_biome_id(direction)) / f"{entry['component_type']}.png"
            abs_path = PROJECTS_ROOT / project_id / rel_path
            source_kind, source_rel = _install_component_template_asset(
                project_id,
                abs_path,
                entry["component_type"],
                palette,
                flags,
                shell_family,
                entry["size"],
                entry["transparency_mode"] == "alpha",
            )
            pack.setdefault("template_library", []).append({
                "template_id": f"{pack.get('biome_id') or _default_biome_id(direction)}-{entry['component_type']}",
                "component_type": entry["component_type"],
                "variant_family": entry["variant_family"],
                "image_path": rel_path.as_posix(),
                "width": entry["size"][0],
                "height": entry["size"][1],
                "orientation": entry["orientation"],
                "transparency_mode": entry["transparency_mode"],
                "visual_role": entry["visual_role"],
                "source_art_direction_version": int(direction.get("version") or 1),
                "approved": True,
                "locked": True,
                "adaptation_mode": _component_adaptation_mode(entry["component_type"]),
                "source_template_kind": source_kind,
                "source_template_path": source_rel,
                "updated_at": now_iso(),
            })
        _append_pending_border_first_templates(
            pack.setdefault("template_library", []),
            str(pack.get("biome_id") or _default_biome_id(direction)),
            direction,
        )
        for template in pack.get("template_library") or []:
            if not isinstance(template, dict):
                continue
            component_type = str(template.get("component_type") or "").strip()
            if not component_type:
                continue
            if component_type in BORDER_FIRST_BIOME_COMPONENT_TYPES and str(template.get("source_template_kind") or "") == "pending_generation":
                template["adaptation_mode"] = "gemini"
                template["updated_at"] = now_iso()
                continue
            rel_path = Path(str(template.get("image_path") or "").strip())
            if not rel_path:
                continue
            abs_path = PROJECTS_ROOT / project_id / rel_path
            target_size = (int(template.get("width") or 0), int(template.get("height") or 0))
            if not all(target_size):
                spec_entry = next((item for item in V1_BESPOKE_COMPONENTS if item["component_type"] == component_type), None)
                if spec_entry:
                    target_size = spec_entry["size"]
                    template["width"] = target_size[0]
                    template["height"] = target_size[1]
            transparency_mode = str(template.get("transparency_mode") or "opaque")
            transparent = transparency_mode == "alpha"
            # Gemini-refined biome PNGs are authoritative; do not re-copy curated/fallback seeds over them.
            if str(template.get("biome_visual_generated_at") or "").strip():
                template["adaptation_mode"] = _component_adaptation_mode(component_type)
                template["updated_at"] = now_iso()
                continue
            if component_type in BORDER_FIRST_BIOME_COMPONENT_TYPES and component_type != "door_piece":
                # Phase 1 only introduces the border-first schema contract.
                # These next-generation templates should exist as planned
                # metadata without creating placeholder image files or affecting
                # the current runtime path.
                template["adaptation_mode"] = "gemini"
                template["source_template_kind"] = "pending_generation"
                template["source_template_path"] = None
                template["updated_at"] = now_iso()
                continue
            if str(template.get("source_template_kind") or "") == "pending_generation":
                template["adaptation_mode"] = _component_adaptation_mode(component_type)
                template["updated_at"] = now_iso()
                continue
            source_kind, source_rel = _install_component_template_asset(
                project_id,
                abs_path,
                component_type,
                palette,
                flags,
                shell_family,
                target_size,
                transparent,
            )
            template["adaptation_mode"] = _component_adaptation_mode(component_type)
            template["source_template_kind"] = source_kind
            template["source_template_path"] = source_rel
            template["updated_at"] = now_iso()
        pack["border_first_contract"] = _normalize_border_first_contract(
            pack.get("border_first_contract"),
            pack.get("template_library") or [],
        )
    return direction


def _concept_asset_url(project_id: str, rel_path: str) -> str:
    return f"/tools/2d-sprite-and-animation/projects-data/{project_id}/{str(rel_path).lstrip('/')}"


def _available_frozen_concepts(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    board = direction.get("concept_board") or {}
    for concept in board.get("images") or []:
        concept_id = str(concept.get("concept_id") or "").strip()
        rel_path = str(concept.get("image_path") or "").strip()
        if not concept_id or not rel_path:
            continue
        items.append({
            "concept_id": concept_id,
            "label": concept.get("label") or concept_id,
            "url": _concept_asset_url(project["project_id"], rel_path),
            "image_path": rel_path,
            "approved": True,
            "selected": concept_id in set(direction.get("frozen_concept_ids") or []),
            "prompt": concept.get("prompt") or "",
        })
    return items


def _resolve_frozen_concepts(project: Dict[str, Any], requested_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    available = _available_frozen_concepts(project)
    if requested_ids:
        requested = {str(item).strip() for item in requested_ids if str(item).strip()}
        chosen = [item for item in available if item["concept_id"] in requested]
        if chosen:
            return chosen
    return available[:1]


def _biome_generation_frozen_reference_paths(
    project: Dict[str, Any],
    project_dir: Path,
    pack: Dict[str, Any],
    direction: Dict[str, Any],
    component_type: str,
) -> List[Path]:
    if component_type in STRUCTURAL_BIOME_COMPONENT_TYPES:
        return []
    requested_ids = [
        str(item).strip()
        for item in (pack.get("locked_concept_ids") or direction.get("frozen_concept_ids") or [])
        if str(item).strip()
    ]
    frozen_items = _resolve_frozen_concepts(project, requested_ids)
    frozen_paths: List[Path] = []
    for frozen in frozen_items[:3]:
        rel = str(frozen.get("image_path") or "").strip()
        if not rel:
            continue
        path = project_dir / rel
        if path.exists():
            frozen_paths.append(path)
    return frozen_paths


def _extract_gemini_image_bytes(raw: Dict[str, Any]) -> Optional[bytes]:
    for candidate in raw.get("candidates") or []:
        for part in ((candidate.get("content") or {}).get("parts") or []):
            inline = part.get("inline_data") or part.get("inlineData") or {}
            data = inline.get("data")
            if isinstance(data, str) and data.strip():
                try:
                    return base64.b64decode(data)
                except (ValueError, TypeError):
                    return None
    return None


def _build_art_direction_concept_prompts(direction: Dict[str, Any], count: int = 3) -> List[Dict[str, str]]:
    anchors = ", ".join(direction.get("shape_language") or []) or direction.get("style_family") or "dark fantasy world"
    materials = ", ".join(direction.get("material_rules") or []) or "aged materials"
    lighting = ", ".join(direction.get("lighting_rules") or []) or "controlled cinematic lighting"
    palette = ", ".join((direction.get("palette") or {}).get("dominant") or []) or "restrained dark palette"
    negative = str(direction.get("negative_direction") or "").strip()
    summary = str(direction.get("high_level_direction") or "").strip()
    variants = [
        ("World Keyframe", "A flagship environment keyframe that establishes the world visual direction with strong silhouette hierarchy."),
        ("Architectural Mood", "A broader architectural mood concept that focuses on materials, spaces, and recurring structural language."),
        ("Traversal Readability", "A gameplay-aware concept painting that keeps the route readable while preserving the same world art direction."),
    ]
    prompts = []
    for index in range(min(count, len(variants))):
        label, framing = variants[index]
        prompt = (
            f"{framing} {summary} "
            f"Style family: {direction.get('style_family') or 'dark fantasy environment'}. "
            f"Shape language: {anchors}. Materials: {materials}. Lighting: {lighting}. Palette anchors: {palette}. "
            f"Avoid: {negative}. "
            "Make this environment concept art only, with no characters, no UI, no sprite sheet, and no text overlays."
        ).strip()
        prompts.append({"label": label, "prompt": prompt})
    return prompts


def _call_gemini_image(prompt: str) -> Optional[bytes]:
    if not _gemini_api_key():
        return None
    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip() or "gemini-2.5-flash-image"
    raw, err = _gemini_generate_content_rest(
        model,
        [{"text": prompt}],
        response_modalities=["IMAGE", "TEXT"],
        generation_config_merge={"imageConfig": {"aspectRatio": "16:9"}},
    )
    if err or not raw:
        return None
    return _extract_gemini_image_bytes(raw)


def _render_art_direction_fallback(path: Path, direction: Dict[str, Any], label: str, variant_index: int) -> None:
    width, height = 1344, 768
    image = Image.new("RGBA", (width, height), (5, 7, 9, 255))
    draw = ImageDraw.Draw(image)
    dominant = (direction.get("palette") or {}).get("dominant") or []
    accent = (direction.get("palette") or {}).get("accent") or []
    bg_a = _hex_to_rgb(dominant[0] if dominant else "#12161c", (18, 22, 28))
    bg_b = _hex_to_rgb(dominant[1] if len(dominant) > 1 else "#243038", (36, 48, 56))
    accent_rgb = _hex_to_rgb(accent[0] if accent else "#b58f52", (181, 143, 82))
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(bg_a[i] * (1 - t) + bg_b[i] * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color + (255,))
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    focus_x = int(width * (0.28 + (variant_index * 0.22)))
    focus_y = int(height * 0.34)
    for radius, alpha in ((220, 36), (150, 58), (90, 76)):
        glow_draw.ellipse((focus_x - radius, focus_y - radius, focus_x + radius, focus_y + radius), fill=accent_rgb + (alpha,))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=28))
    image.alpha_composite(glow)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((92, 110, width - 92, height - 110), radius=36, outline=accent_rgb + (180,), width=3)
    for idx in range(4):
        left = 160 + (idx * 250)
        top = 220 - ((idx + variant_index) % 2) * 50
        draw.polygon(
            [(left, height - 180), (left + 74, top), (left + 162, top + 42), (left + 204, height - 180)],
            fill=(10 + idx * 8, 12 + idx * 10, 16 + idx * 12, 190),
            outline=accent_rgb + (120,),
        )
    draw.text((110, 82), label, fill=(242, 246, 244, 255))
    draw.text((110, 116), str(direction.get("style_family") or "Art direction concept"), fill=(208, 220, 214, 220))
    draw.text((110, height - 118), str(direction.get("high_level_direction") or "")[:160], fill=(208, 220, 214, 220))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def list_project_frozen_concept_candidates(project_id: str) -> List[Dict[str, Any]]:
    project = load_project(project_id)
    return copy.deepcopy(_available_frozen_concepts(project))


def generate_project_art_direction_concepts(project_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    direction = normalize_art_direction(payload, project.get("art_direction"))
    prompts = _build_art_direction_concept_prompts(direction, count=3)
    project_dir = PROJECTS_ROOT / project_id
    concept_root = project_dir / "art_direction_concepts"
    concept_root.mkdir(parents=True, exist_ok=True)
    generated: List[Dict[str, Any]] = []
    used_ai = False
    for index, item in enumerate(prompts):
        concept_id = f"art-direction-{index + 1:02d}"
        rel_path = Path("art_direction_concepts") / f"{concept_id}.png"
        abs_path = project_dir / rel_path
        image_bytes = _call_gemini_image(item["prompt"])
        if image_bytes:
            try:
                Image.open(io.BytesIO(image_bytes)).convert("RGBA").save(abs_path)
                used_ai = True
            except Exception:
                _render_art_direction_fallback(abs_path, direction, item["label"], index)
        else:
            _render_art_direction_fallback(abs_path, direction, item["label"], index)
        generated.append({
            "concept_id": concept_id,
            "label": item["label"],
            "prompt": item["prompt"],
            "image_path": rel_path.as_posix(),
            "url": _concept_asset_url(project_id, rel_path.as_posix()),
        })
    direction["concept_board"] = {
        "status": "ready",
        "images": generated,
        "last_generated_at": now_iso(),
        "generation_error": None if used_ai else "gemini_image_unavailable_fallback_used",
        "prompt_summary": str(direction.get("high_level_direction") or ""),
    }
    if not direction.get("frozen_concept_ids"):
        direction["frozen_concept_ids"] = [generated[0]["concept_id"]] if generated else []
    direction = _attach_default_biome_pack(project, direction)
    project["art_direction"] = direction
    frozen = _resolve_frozen_concepts(project, direction.get("frozen_concept_ids") or [])
    project["art_direction"]["frozen_concepts"] = frozen
    project["art_direction"]["frozen_concept_ids"] = [entry["concept_id"] for entry in frozen]
    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "art_direction_concepts_generated",
        "created_at": now_iso(),
        "used_ai": used_ai,
        "concept_count": len(generated),
    })
    return {
        "ok": True,
        "used_ai": used_ai,
        "art_direction": copy.deepcopy(project["art_direction"]),
        "available_concepts": copy.deepcopy(_available_frozen_concepts(project)),
    }


def get_project_art_direction(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    direction = _attach_default_biome_pack(project, direction)
    frozen = _resolve_frozen_concepts(project, direction.get("frozen_concept_ids") or [])
    direction["frozen_concepts"] = frozen
    direction["frozen_concept_ids"] = [item["concept_id"] for item in frozen]
    project["art_direction"] = direction
    save_project(project)
    return copy.deepcopy(direction)


def _ensure_room_environment(room: Dict[str, Any]) -> Dict[str, Any]:
    env = room.get("environment")
    if not isinstance(env, dict):
        env = {}
        room["environment"] = env
    env.setdefault("version", 2)
    env["themeId"] = str(env.get("themeId") or "cave").strip().lower() or "cave"
    env["tags"] = [str(item).strip().lower() for item in (env.get("tags") or []) if str(item).strip()]
    spec = env.get("spec")
    if not isinstance(spec, dict):
        spec = {}
        env["spec"] = spec
    spec.setdefault("theme_id", env["themeId"])
    spec.setdefault("tags", list(env["tags"]))
    spec.setdefault("description", "")
    spec.setdefault("mood", "")
    spec.setdefault("lighting", "")
    spec.setdefault("fog", "")
    spec.setdefault("materials", [])
    spec.setdefault("landmarks", [])
    spec.setdefault("hazards", [])
    spec.setdefault("composition_focus", "")
    spec.setdefault("readability_notes", [])
    spec["components"] = _normalize_component_prompts_response(
        spec.get("components"),
        str(spec.get("description") or ""),
    )
    component_schemas = spec.get("component_schemas")
    if not isinstance(component_schemas, dict):
        component_schemas = {}
        spec["component_schemas"] = component_schemas
    spec["component_schemas"] = _normalize_component_schemas_response(
        spec.get("component_schemas"),
        str(spec.get("description") or ""),
        spec["components"],
    )
    preview = env.get("preview")
    if not isinstance(preview, dict):
        preview = {}
        env["preview"] = preview
    preview.setdefault("status", "idle")
    preview.setdefault("render_level", None)
    preview.setdefault("images", [])
    preview.setdefault("approved_image_id", None)
    preview.setdefault("last_job_id", None)
    preview.setdefault("last_generated_at", None)
    preview.setdefault("fallback_reason", None)
    preview.setdefault("approved_palette", None)
    template_context = env.get("template_context")
    if not isinstance(template_context, dict):
        template_context = {}
        env["template_context"] = template_context
    template_context.setdefault("source_template_id", None)
    template_context.setdefault("source_template_label", None)
    template_context.setdefault("adapted_from_art_direction_template_id", None)
    template_context.setdefault("last_adapted_at", None)
    runtime = env.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
        env["runtime"] = runtime
    runtime.setdefault("status", "idle")
    runtime.setdefault("source", None)
    runtime.setdefault("applied_preview_id", None)
    runtime.setdefault("surface_palette", None)
    runtime.setdefault("material_keywords", [])
    runtime.setdefault("lighting_mode", "")
    runtime.setdefault("last_applied_at", None)
    runtime.setdefault("next_generation_contract", _border_first_generation_contract())
    asset_pack = runtime.get("asset_pack")
    if not isinstance(asset_pack, dict):
        asset_pack = {}
        runtime["asset_pack"] = asset_pack
    asset_pack.setdefault("status", "idle")
    asset_pack.setdefault("asset_schema_version", 1)
    asset_pack.setdefault("used_ai", False)
    asset_pack.setdefault("generated_at", None)
    asset_pack.setdefault("source_preview_id", None)
    asset_pack.setdefault("layout_fingerprint", None)
    asset_pack.setdefault("component_dependencies", {})
    asset_pack.setdefault("component_fingerprints", {})
    asset_pack.setdefault("stale_components", [])
    asset_pack.setdefault("failed_assets", [])
    asset_pack.setdefault("assets", {})
    bespoke_manifest = runtime.get("bespoke_asset_manifest")
    if not isinstance(bespoke_manifest, dict):
        bespoke_manifest = {}
        runtime["bespoke_asset_manifest"] = bespoke_manifest
    bespoke_manifest.setdefault("schema_version", 2)
    bespoke_manifest.setdefault("status", "idle")
    bespoke_manifest.setdefault("biome_id", None)
    bespoke_manifest.setdefault("source_preview_id", None)
    bespoke_manifest.setdefault("generation_plan", [])
    bespoke_manifest.setdefault("required_slots", [])
    bespoke_manifest.setdefault("built_slots", [])
    bespoke_manifest.setdefault("slot_groups", {})
    bespoke_manifest.setdefault("schema_validation", {"status": "idle", "valid": False, "errors": [], "component_statuses": {}})
    bespoke_manifest.setdefault("runtime_review", {"status": "idle", "fail_reasons": [], "metrics": {}, "screenshot_url": None, "review_mode": None})
    bespoke_manifest.setdefault("review", copy.deepcopy(bespoke_manifest.get("runtime_review")))
    bespoke_manifest.setdefault("assets", {})
    bespoke_manifest.setdefault("failed_assets", [])
    bespoke_manifest.setdefault("used_ai", False)
    bespoke_manifest.setdefault("generated_at", None)
    bespoke_manifest.setdefault("validation_errors", [])
    bespoke_manifest.setdefault("next_generation_contract", _border_first_generation_contract())
    env["environment_pipeline_version"] = envv3.normalize_pipeline_version(env.get("environment_pipeline_version"))
    if env["environment_pipeline_version"] == envv3.V3_PIPELINE_VERSION:
        envv3.ensure_v3_metadata(env, room)
    _ensure_room_ai_helpfulness(env)
    return env


def _sync_v3_environment_state(
    project_id: str,
    env: Dict[str, Any],
    room: Dict[str, Any],
    biome_id: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> None:
    if envv3.normalize_pipeline_version(env.get("environment_pipeline_version")) != envv3.V3_PIPELINE_VERSION:
        return
    envv3.sync_v3_metadata(env, room, biome_id=biome_id, generated_at=generated_at)
    envv3.persist_staged_artifacts(env, PROJECTS_ROOT, project_id, str(room.get("id") or "room"))


def _find_room(project: Dict[str, Any], room_id: str) -> Dict[str, Any]:
    layout = project.get("room_layout") or {}
    rooms = layout.get("rooms") or []
    room = next((item for item in rooms if str(item.get("id") or "") == room_id), None)
    if not isinstance(room, dict):
        raise ValueError("Room not found.")
    env = _ensure_room_environment(room)
    if envv3.normalize_pipeline_version(env.get("environment_pipeline_version")) == envv3.V3_PIPELINE_VERSION:
        envv3.hydrate_persisted_artifacts(env, PROJECTS_ROOT, str(project.get("project_id") or ""), room_id)
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    _refresh_asset_pack_staleness(room, env, direction)
    return room


def _keyword_theme(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("flood", "water", "drip", "catacomb", "seep", "wet")):
        return "sewer"
    if any(word in lowered for word in ("shrine", "altar", "ritual", "temple", "sacred")):
        return "shrine"
    if any(word in lowered for word in ("forest", "root", "moss", "overgrown", "vine")):
        return "forest"
    if any(word in lowered for word in ("void", "astral", "ethereal", "dream", "abyss")):
        return "void"
    if any(word in lowered for word in ("ruin", "cathedral", "crypt", "hall")):
        return "ruins"
    return "cave"


def _keywords(text: str) -> List[str]:
    raw = []
    for token in text.lower().replace("/", " ").replace(",", " ").replace(".", " ").split():
        cleaned = "".join(ch for ch in token if ch.isalnum() or ch == "-").strip("-")
        if len(cleaned) >= 4:
            raw.append(cleaned)
    seen = set()
    out = []
    for token in raw:
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= 6:
            break
    return out


def _use_unified_room_shell() -> bool:
    raw = os.environ.get("MV_ROOM_SHELL_FOREGROUND", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _room_geometry(room: Dict[str, Any]) -> Dict[str, Any]:
    polygon = room.get("polygon") or []
    xs = [float(pt[0]) for pt in polygon if isinstance(pt, (list, tuple)) and len(pt) == 2]
    ys = [float(pt[1]) for pt in polygon if isinstance(pt, (list, tuple)) and len(pt) == 2]
    doors = room.get("doors") or []
    platforms = room.get("platforms") or []
    left = float(min(xs) if xs else 0.0)
    right = float(max(xs) if xs else (((room.get("size") or {}).get("width")) or 1600))
    top = float(min(ys) if ys else 0.0)
    bottom = float(max(ys) if ys else (((room.get("size") or {}).get("height")) or 1200))
    return {
        "room_id": room.get("id"),
        "room_name": room.get("name") or room.get("id") or "Unnamed room",
        "width": float(((room.get("size") or {}).get("width")) or (max(xs) - min(xs) if xs else 1600)),
        "height": float(((room.get("size") or {}).get("height")) or (max(ys) - min(ys) if ys else 1200)),
        "left": left,
        "right": right,
        "top": top,
        "bottom": bottom,
        "chamber_width": max(1.0, right - left),
        "chamber_height": max(1.0, bottom - top),
        "polygon": [[float(pt[0]), float(pt[1])] for pt in polygon if isinstance(pt, (list, tuple)) and len(pt) == 2],
        "door_count": len(doors),
        "platform_count": len(platforms),
        "door_positions": [
            {"x": float(item.get("x") or 0), "y": float(item.get("y") or 0), "kind": str(item.get("kind") or "transition")}
            for item in doors if isinstance(item, dict)
        ],
        "platforms": [
            {"x": float(item.get("x") or 0), "y": float(item.get("y") or 0), "len": int(item.get("len") or 0)}
            for item in platforms if isinstance(item, dict)
        ],
        "readability_constraints": [
            "keep walkable route legible",
            "preserve door visibility",
            "avoid visual clutter over platform edges",
        ],
    }


def _parse_iso8601(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text[:-1] + "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _elapsed_ms(started_at: Any, ended_at: Any) -> Optional[int]:
    start_dt = _parse_iso8601(started_at)
    end_dt = _parse_iso8601(ended_at)
    if start_dt is None or end_dt is None:
        return None
    return max(0, int((end_dt - start_dt).total_seconds() * 1000))


def _room_complexity_bucket(geometry: Dict[str, Any]) -> str:
    area = float(geometry.get("width") or 0) * float(geometry.get("height") or 0)
    platform_count = int(geometry.get("platform_count") or 0)
    door_count = int(geometry.get("door_count") or 0)
    score = 0
    if area >= 2400000:
        score += 2
    elif area >= 1600000:
        score += 1
    if platform_count >= 7:
        score += 2
    elif platform_count >= 4:
        score += 1
    if door_count >= 3:
        score += 1
    if score >= 4:
        return "dense"
    if score >= 2:
        return "medium"
    return "light"


def _room_change_snapshot(room: Dict[str, Any]) -> Dict[str, int]:
    return {
        "platforms": len(room.get("platforms") or []),
        "moving_platforms": len(room.get("movingPlatforms") or []),
        "doors": len(room.get("doors") or []),
        "keys": len(room.get("keys") or []),
        "abilities": len(room.get("abilities") or []),
        "edge_links": len(room.get("edgeLinks") or []),
        "removed_edges": len(room.get("removedEdges") or []),
        "polygon_points": len(room.get("polygon") or []),
    }


def _diff_change_snapshot(before: Dict[str, int], after: Dict[str, int]) -> Dict[str, int]:
    keys = sorted(set(before.keys()) | set(after.keys()))
    diff: Dict[str, int] = {}
    for key in keys:
        diff[key] = int(after.get(key, 0)) - int(before.get(key, 0))
    diff["total_abs_delta"] = sum(abs(value) for value in diff.values())
    return diff


def _bucket_change_magnitude(total_abs_delta: int) -> str:
    if total_abs_delta <= 0:
        return "none"
    if total_abs_delta <= 2:
        return "small"
    if total_abs_delta <= 6:
        return "medium"
    return "large"


def _bucket_time_to_decision(value_ms: Optional[int]) -> str:
    if value_ms is None:
        return "unknown"
    if value_ms < 30000:
        return "under_30s"
    if value_ms < 120000:
        return "under_2m"
    if value_ms < 600000:
        return "under_10m"
    return "10m_plus"


def _heuristic_model_self_rating(render_level: str, used_ai: bool, fallback_reason: Optional[str]) -> Dict[str, Any]:
    base = 0.78 if used_ai and render_level == "level3" else 0.58 if render_level == "level2" else 0.42
    if fallback_reason:
        base -= 0.18
    base = max(0.05, min(0.95, base))
    rubric = {
        "style_match": round(base, 2),
        "readability": round(max(0.05, min(0.95, base + 0.04)), 2),
        "artifacting": round(max(0.05, min(0.95, base - 0.06)), 2),
        "composition_tileability": round(max(0.05, min(0.95, base + (0.06 if render_level == "level3" else -0.04))), 2),
    }
    return {
        "label": "Model heuristic only",
        "score": round(sum(rubric.values()) / max(len(rubric), 1), 2),
        "rubric": rubric,
    }


def _default_ai_helpfulness() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "sequence": 0,
        "active_suggestion_id": None,
        "suggestions": [],
        "summary": {
            "total_suggestions": 0,
            "funnel": {"requested": 0, "viewed": 0, "decided": 0, "accepted": 0, "tweaked": 0, "rejected": 0, "persisted": 0},
            "denominators": {"per_suggestion": 0, "per_session": 0, "per_task": 0},
            "low_sample_note": "No room suggestions recorded yet.",
            "sample_confidence": "low",
        },
    }


def _ensure_room_ai_helpfulness(env: Dict[str, Any]) -> Dict[str, Any]:
    helpfulness = env.get("ai_helpfulness")
    if not isinstance(helpfulness, dict):
        helpfulness = _default_ai_helpfulness()
        env["ai_helpfulness"] = helpfulness
    helpfulness.setdefault("schema_version", 1)
    helpfulness.setdefault("sequence", 0)
    helpfulness.setdefault("active_suggestion_id", None)
    if not isinstance(helpfulness.get("suggestions"), list):
        helpfulness["suggestions"] = []
    helpfulness.setdefault("summary", _default_ai_helpfulness()["summary"])
    return helpfulness


def _find_suggestion_record(helpfulness: Dict[str, Any], suggestion_id: str) -> Optional[Dict[str, Any]]:
    return next((item for item in helpfulness.get("suggestions") or [] if str(item.get("suggestion_id") or "") == suggestion_id), None)


def _update_helpfulness_summary(helpfulness: Dict[str, Any]) -> None:
    suggestions = helpfulness.get("suggestions") or []
    unique_sessions = {str(item.get("context", {}).get("session_id") or "") for item in suggestions if str(item.get("context", {}).get("session_id") or "")}
    unique_tasks = {str(item.get("context", {}).get("task_id") or "") for item in suggestions if str(item.get("context", {}).get("task_id") or "")}
    requested = len(suggestions)
    viewed = sum(1 for item in suggestions if int((item.get("effort") or {}).get("preview_views") or 0) > 0)
    decided = sum(1 for item in suggestions if str((item.get("decision") or {}).get("outcome") or "").strip())
    accepted = sum(1 for item in suggestions if (item.get("decision") or {}).get("outcome") == "accept")
    tweaked = sum(1 for item in suggestions if (item.get("decision") or {}).get("outcome") == "tweak")
    rejected = sum(1 for item in suggestions if (item.get("decision") or {}).get("outcome") == "reject")
    persisted = sum(1 for item in suggestions if (item.get("persistence") or {}).get("status") == "persisted")
    if requested >= 12:
        sample_confidence = "high"
        low_sample_note = f"{requested} suggestions recorded. Rates are directionally useful."
    elif requested >= 5:
        sample_confidence = "medium"
        low_sample_note = f"{requested} suggestions recorded. Read rates with caution."
    elif requested > 0:
        sample_confidence = "low"
        low_sample_note = f"Only {requested} suggestion{'s' if requested != 1 else ''} recorded so far. Avoid over-interpreting percentages."
    else:
        sample_confidence = "low"
        low_sample_note = "No room suggestions recorded yet."
    helpfulness["summary"] = {
        "total_suggestions": requested,
        "funnel": {
            "requested": requested,
            "viewed": viewed,
            "decided": decided,
            "accepted": accepted,
            "tweaked": tweaked,
            "rejected": rejected,
            "persisted": persisted,
        },
        "denominators": {
            "per_suggestion": requested,
            "per_session": len(unique_sessions),
            "per_task": len(unique_tasks),
        },
        "low_sample_note": low_sample_note,
        "sample_confidence": sample_confidence,
    }


def _coerce_reason_codes(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        code = str(item or "").strip().lower().replace(" ", "_")
        if code and code not in out:
            out.append(code[:48])
    return out[:6]


def _close_prior_active_suggestion(
    room: Dict[str, Any],
    env: Dict[str, Any],
    request_kind: str,
    replacement_suggestion_id: Optional[str] = None,
) -> None:
    helpfulness = _ensure_room_ai_helpfulness(env)
    active_id = str(helpfulness.get("active_suggestion_id") or "").strip()
    if not active_id:
        return
    previous = _find_suggestion_record(helpfulness, active_id)
    if not previous:
        return
    decision = previous.setdefault("decision", {})
    if str(decision.get("outcome") or "").strip():
        return
    now_value = now_iso()
    decision["outcome"] = "tweak" if request_kind == "revise" else "reject"
    decision["decision_at"] = now_value
    decision["time_to_decision_ms"] = _elapsed_ms(previous.get("generated_at"), now_value)
    decision["time_to_decision_bucket"] = _bucket_time_to_decision(decision.get("time_to_decision_ms"))
    previous["replaced_by_suggestion_id"] = replacement_suggestion_id
    previous.setdefault("persistence", {})["status"] = "superseded"
    previous.setdefault("tweak_magnitude", {
        "bucket": "none",
        "counts": _diff_change_snapshot(previous.get("snapshots", {}).get("room_counts") or {}, _room_change_snapshot(room)),
    })


def _create_suggestion_record(
    room: Dict[str, Any],
    env: Dict[str, Any],
    geometry: Dict[str, Any],
    render_level: str,
    used_ai: bool,
    fallback_reason: Optional[str],
    latency_ms: Optional[int],
    payload: Dict[str, Any],
) -> str:
    helpfulness = _ensure_room_ai_helpfulness(env)
    helpfulness["sequence"] = int(helpfulness.get("sequence") or 0) + 1
    generated_at = now_iso()
    suggestion_id = "sug-%s" % stable_hash(
        str(room.get("id") or "room"),
        str(helpfulness["sequence"]),
        str(generated_at),
        str(env.get("spec", {}).get("description") or ""),
    )[:16]
    model_self_rating = _heuristic_model_self_rating(render_level, used_ai, fallback_reason)
    suggestion = {
        "suggestion_id": suggestion_id,
        "generated_at": generated_at,
        "request_kind": str(payload.get("request_kind") or "generate").strip() or "generate",
        "context": {
            "tool_surface": str(payload.get("tool_surface") or "room-layout-editor").strip() or "room-layout-editor",
            "workflow_step": str(payload.get("workflow_step") or "").strip() or "room-environment-results",
            "session_id": str(payload.get("session_id") or "").strip() or None,
            "task_id": str(payload.get("task_id") or "").strip() or None,
            "room_complexity_bucket": _room_complexity_bucket(geometry),
        },
        "decision": {
            "outcome": None,
            "decision_at": None,
            "time_to_decision_ms": None,
            "time_to_decision_bucket": "unknown",
            "reason_codes": _coerce_reason_codes(payload.get("reason_codes")),
        },
        "effort": {
            "preview_views": 0,
            "preview_inspections": 0,
            "open_game_inspections": 0,
            "back_and_forth_steps": 0,
            "regeneration_count": 0,
        },
        "reliability": {
            "latency_ms": latency_ms,
            "latency_bucket": _bucket_time_to_decision(latency_ms),
            "errors": [],
            "cancellations": 0,
            "crashes_near_ai_use": 0,
        },
        "previews": {
            "render_level": render_level,
            "fallback_reason": fallback_reason,
            "used_ai": used_ai,
        },
        "snapshots": {
            "room_counts": _room_change_snapshot(room),
        },
        "tweak_magnitude": {
            "bucket": "none",
            "counts": {},
        },
        "persistence": {
            "status": "pending",
            "evaluated_at": None,
            "save_count": 0,
            "minutes_since_accept": 0,
            "replaced_later": False,
        },
        "model_self_rating": model_self_rating,
    }
    helpfulness["suggestions"].append(suggestion)
    helpfulness["active_suggestion_id"] = suggestion_id
    if len(helpfulness["suggestions"]) > 60:
        helpfulness["suggestions"] = helpfulness["suggestions"][-60:]
    _update_helpfulness_summary(helpfulness)
    return suggestion_id


def _evaluate_persistence_for_room(room: Dict[str, Any]) -> None:
    env = _ensure_room_environment(room)
    helpfulness = _ensure_room_ai_helpfulness(env)
    accepted_preview_id = str(env.get("preview", {}).get("approved_image_id") or "").strip()
    current_counts = _room_change_snapshot(room)
    now_value = now_iso()
    for suggestion in helpfulness.get("suggestions") or []:
        decision = suggestion.get("decision") or {}
        if decision.get("outcome") != "accept":
            continue
        persistence = suggestion.setdefault("persistence", {})
        persistence["save_count"] = int(persistence.get("save_count") or 0) + 1
        persistence["evaluated_at"] = now_value
        accepted_at = decision.get("decision_at")
        elapsed = _elapsed_ms(accepted_at, now_value)
        persistence["minutes_since_accept"] = int((elapsed or 0) / 60000)
        preview_id = str(suggestion.get("accepted_preview_id") or suggestion.get("preview_id") or "").strip()
        if preview_id and accepted_preview_id and preview_id != accepted_preview_id:
            persistence["status"] = "replaced"
            persistence["replaced_later"] = True
        elif persistence["save_count"] >= 1 or persistence["minutes_since_accept"] >= 10:
            persistence["status"] = "persisted"
        change_counts = _diff_change_snapshot(suggestion.get("snapshots", {}).get("room_counts") or {}, current_counts)
        suggestion["tweak_magnitude"] = {
            "bucket": _bucket_change_magnitude(int(change_counts.get("total_abs_delta") or 0)),
            "counts": change_counts,
        }
    _update_helpfulness_summary(helpfulness)


def _fingerprint_payload(value: Any) -> str:
    return stable_hash(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _asset_component_fingerprints_from_dependencies(dependencies: Dict[str, Any]) -> Dict[str, str]:
    return {
        key: _fingerprint_payload(value)
        for key, value in dependencies.items()
    }


def _build_asset_component_dependency_payloads(room: Dict[str, Any], spec: Dict[str, Any], direction: Dict[str, Any], preview_id: str) -> Dict[str, Any]:
    geometry = _room_geometry(room)
    components = spec.get("components") if isinstance(spec.get("components"), dict) else {}

    def component_text(name: str) -> str:
        item = components.get(name) or {}
        return str(item.get("prompt") or item.get("description") or "").strip()

    visual_context = {
        "art_direction": str(direction.get("high_level_direction") or ""),
        "negative": str(direction.get("negative_direction") or ""),
        "preview_id": preview_id,
        "theme": str(spec.get("theme_id") or ""),
        "tags": list(spec.get("tags") or []),
        "materials": list(spec.get("materials") or []),
    }
    layout_context = {
        "room_id": geometry.get("room_id"),
        "width": geometry.get("width"),
        "height": geometry.get("height"),
        "polygon": geometry.get("polygon"),
        "door_positions": geometry.get("door_positions"),
        "platforms": geometry.get("platforms"),
        "removed_edges": list(room.get("removedEdges") or []),
    }
    return {
        "background": {"component": component_text("background"), "visual": visual_context, "layout": layout_context},
        "midground_arches": {"component": component_text("background"), "visual": visual_context, "layout": layout_context},
        "wall_body_strip": {"component": component_text("walls"), "visual": visual_context},
        "floor_cap_strip": {"component": component_text("floor"), "visual": visual_context},
        "platform_ledge_strip": {"component": component_text("platforms"), "visual": visual_context},
        "door": {"component": component_text("doors"), "visual": visual_context},
    }


def _detect_stale_asset_components(room: Dict[str, Any], spec: Dict[str, Any], direction: Dict[str, Any], asset_pack: Dict[str, Any]) -> List[str]:
    preview_id = str((asset_pack.get("source_preview_id") or "")).strip()
    current_dependencies = _build_asset_component_dependency_payloads(room, spec, direction, preview_id)
    current = _asset_component_fingerprints_from_dependencies(current_dependencies)
    previous = asset_pack.get("component_fingerprints") if isinstance(asset_pack.get("component_fingerprints"), dict) else {}
    stale = [name for name, value in current.items() if previous.get(name) and previous.get(name) != value]
    return stale


def _refresh_asset_pack_staleness(room: Dict[str, Any], env: Dict[str, Any], direction: Dict[str, Any]) -> None:
    asset_pack = ((env.get("runtime") or {}).get("asset_pack") or {})
    if not isinstance(asset_pack, dict):
        return
    if asset_pack.get("status") != "ready":
        asset_pack["stale_components"] = []
        return
    stale = _detect_stale_asset_components(room, env.get("spec") or {}, direction, asset_pack)
    asset_pack["stale_components"] = stale
    if stale and env.get("runtime"):
        env["runtime"]["status"] = "outdated"


def _gemini_json(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    if not _gemini_api_key():
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    raw, err = _gemini_generate_content_rest(
        model,
        [{"text": user_prompt}],
        response_modalities=None,
        system_instruction=system_prompt,
        generation_config_merge={"responseMimeType": "application/json", "temperature": 0.35},
    )
    if err or not raw:
        return None
    candidates = raw.get("candidates") or []
    if not candidates:
        return None
    parts = (candidates[0].get("content") or {}).get("parts") or []
    if not parts:
        return None
    text = str(parts[0].get("text") or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def update_project_art_direction(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    direction = normalize_art_direction(payload, project.get("art_direction"))
    direction = _attach_default_biome_pack(project, direction)
    frozen = _resolve_frozen_concepts(project, direction.get("frozen_concept_ids") or [])
    direction["frozen_concepts"] = frozen
    direction["frozen_concept_ids"] = [item["concept_id"] for item in frozen]
    project["art_direction"] = direction
    invalidated_rooms = []
    for room in (project.get("room_layout") or {}).get("rooms") or []:
        if not isinstance(room, dict):
            continue
        env = _ensure_room_environment(room)
        preview = env["preview"]
        preview["status"] = "outdated"
        preview["fallback_reason"] = "art_direction_changed"
        preview["approved_image_id"] = None
        preview["approved_palette"] = None
        runtime = env["runtime"]
        runtime["status"] = "outdated"
        runtime["source"] = None
        runtime["applied_preview_id"] = None
        runtime["surface_palette"] = None
        runtime["last_applied_at"] = None
        runtime["bespoke_asset_manifest"] = {
            "schema_version": 1,
            "status": "idle",
            "biome_id": None,
            "source_preview_id": None,
            "generation_plan": [],
            "assets": {},
            "failed_assets": [],
            "used_ai": False,
            "generated_at": None,
            "validation_errors": [],
        }
        asset_pack = runtime["asset_pack"]
        asset_pack["status"] = "ready" if asset_pack.get("assets") else "idle"
        asset_pack["stale_components"] = ["background", "midground_arches", "wall_body_strip", "floor_cap_strip", "platform_ledge_strip", "door"] if asset_pack.get("assets") else []
        invalidated_rooms.append(str(room.get("id") or ""))
    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "art_direction_updated",
        "template_id": direction.get("template_id"),
        "locked": direction.get("locked"),
        "created_at": now_iso(),
    })
    return {
        "ok": True,
        "art_direction": copy.deepcopy(direction),
        "invalidated_room_ids": invalidated_rooms,
    }


def adapt_room_template(project_id: str, room_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    archetype_id = str(payload.get("archetype_id") or "").strip()
    archetype = _archetype_by_id(archetype_id) if archetype_id else None
    user_text = str(payload.get("user_text") or "").strip()
    current_description = str((((room.get("environment") or {}).get("spec") or {}).get("description")) or "").strip()
    starter = user_text or (archetype.get("starter_brief") if archetype else current_description or "A room that fits the project direction and stays readable for traversal.")
    geometry = _room_geometry(room)
    system_prompt = textwrap.dedent(
        """\
        You adapt room-description templates for a novice-friendly game-development tool.
        Keep the writing plain-language and concise.
        Respect the locked project art direction strictly.
        Respond with ONLY valid JSON:
        {"draft_description":"...","notes":["...","..."]}
        """
    )
    user_prompt = json.dumps({
        "art_direction": direction,
        "frozen_concepts": direction.get("frozen_concepts") or [],
        "room_archetype": archetype,
        "starter_brief": starter,
        "room_geometry": geometry,
        "instruction": str(payload.get("instruction") or "Adapt this room to the locked project style."),
    }, indent=2)
    ai_payload = _gemini_json(system_prompt, user_prompt)
    if ai_payload:
        draft = str(ai_payload.get("draft_description") or "").strip()
        notes = [str(item).strip() for item in (ai_payload.get("notes") or []) if str(item).strip()]
    else:
        draft = (
            f"{starter} Keep the room in the {direction['label'] if 'label' in direction else direction['style_family']} direction, "
            f"with {', '.join(direction.get('material_rules') or [])} and {', '.join(direction.get('lighting_rules') or [])}."
        )
        notes = [
            f"Geometry: {geometry['platform_count']} platforms, {geometry['door_count']} doors.",
            "Keep the main walkable route easy to read.",
        ]
    env = _ensure_room_environment(room)
    env["template_context"]["source_template_id"] = archetype.get("archetype_id") if archetype else None
    env["template_context"]["source_template_label"] = archetype.get("label") if archetype else None
    env["template_context"]["adapted_from_art_direction_template_id"] = direction.get("template_id")
    env["template_context"]["last_adapted_at"] = now_iso()
    env["spec"]["description"] = draft
    project["updated_at"] = now_iso()
    save_project(project)
    return {
        "ok": True,
        "draft_description": draft,
        "notes": notes,
        "template_context": copy.deepcopy(env["template_context"]),
        "used_ai": bool(ai_payload),
        "room_geometry": geometry,
    }


def _normalize_spec_response(raw: Dict[str, Any], fallback_description: str) -> Dict[str, Any]:
    theme_id = _keyword_theme(
        " ".join([
            str(raw.get("themeId") or ""),
            str(raw.get("mood") or ""),
            str(raw.get("lighting") or ""),
            fallback_description,
        ])
    )
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else _keywords(fallback_description)
    cleaned_tags = [str(item).strip().lower() for item in tags if str(item).strip()][:8]
    scene_schema = raw.get("sceneSchema") if isinstance(raw.get("sceneSchema"), dict) else raw.get("scene_schema")
    components = raw.get("components") if isinstance(raw.get("components"), dict) else {}
    component_schemas = raw.get("componentSchemas") if isinstance(raw.get("componentSchemas"), dict) else raw.get("component_schemas")
    return {
        "theme_id": str(raw.get("themeId") or theme_id).strip().lower() or theme_id,
        "tags": cleaned_tags,
        "description": str(raw.get("description") or fallback_description).strip(),
        "mood": str(raw.get("mood") or "moody").strip(),
        "lighting": str(raw.get("lighting") or "controlled focal light").strip(),
        "fog": str(raw.get("fog") or "light atmospheric haze").strip(),
        "materials": [str(item).strip() for item in (raw.get("materials") or []) if str(item).strip()][:6],
        "landmarks": [str(item).strip() for item in (raw.get("landmarks") or []) if str(item).strip()][:6],
        "hazards": [str(item).strip() for item in (raw.get("hazards") or []) if str(item).strip()][:6],
        "composition_focus": str(raw.get("compositionFocus") or raw.get("composition_focus") or "center the most important landmark around the main route").strip(),
        "readability_notes": [str(item).strip() for item in (raw.get("readabilityNotes") or raw.get("readability_notes") or []) if str(item).strip()][:6],
        "components": _normalize_component_prompts_response(components, fallback_description),
        "component_schemas": component_schemas if isinstance(component_schemas, dict) else {},
        "scene_schema": scene_schema if isinstance(scene_schema, dict) else {},
    }


COMPONENT_KEYS: Tuple[Tuple[str, str], ...] = (
    ("floor", "Floor"),
    ("platforms", "Platforms"),
    ("walls", "Walls"),
    ("doors", "Doors"),
    ("background", "Background"),
)

COMPONENT_SCHEMA_COMMON_FIELDS: Tuple[str, ...] = (
    "design_intent",
    "visual_role",
    "material_family",
    "silhouette_rules",
    "detail_density",
    "value_contrast",
    "damage_profile",
    "readability_constraints",
    "negative_constraints",
    "variation_rules",
)

COMPONENT_SCHEMA_DEFS: Dict[str, Dict[str, Any]] = {
    "walls": {
        "label": "Walls",
        "visual_role": "structural",
        "specific_fields": (
            "enclosure_read",
            "bay_rhythm",
            "column_width_class",
            "wall_face_depth",
            "ceiling_junction",
            "base_trim",
            "edge_darkening",
            "repetition_interval",
        ),
    },
    "floor": {
        "label": "Floor",
        "visual_role": "traversal",
        "specific_fields": (
            "top_lip_thickness",
            "face_height",
            "seam_pattern",
            "top_plane_read",
            "edge_breakup",
            "underside_darkening",
            "modular_repeat_width",
        ),
    },
    "platforms": {
        "label": "Platforms",
        "visual_role": "traversal",
        "specific_fields": (
            "top_lip_thickness",
            "face_height",
            "endcap_style",
            "support_style",
            "ledge_read",
            "underside_variation",
            "modular_repeat_width",
        ),
    },
    "doors": {
        "label": "Doors",
        "visual_role": "threshold",
        "specific_fields": (
            "frame_mass",
            "opening_read",
            "threshold_depth",
            "gate_panel_style",
            "lock_overlay_style",
            "side_clearance",
        ),
    },
    "pits": {
        "label": "Pits",
        "visual_role": "hazard",
        "specific_fields": (
            "rim_profile",
            "wall_drop_profile",
            "interior_fill_mode",
            "hazard_read",
            "fog_fill",
            "left_right_edge_rules",
        ),
    },
    "background": {
        "label": "Background",
        "visual_role": "far_depth",
        "specific_fields": (
            "enclosure_architecture",
            "center_openness",
            "far_depth_layers",
            "focal_suppression",
            "floor_plane_suppression",
            "atmospheric_falloff",
        ),
    },
    "midground": {
        "label": "Midground",
        "visual_role": "side_frame",
        "specific_fields": (
            "side_mass_only",
            "center_clearance_ratio",
            "occluder_types",
            "alpha_profile",
            "floor_crossing_forbidden",
            "route_overlap_forbidden",
        ),
    },
    "ceiling": {
        "label": "Ceiling",
        "visual_role": "structural",
        "specific_fields": (
            "ceiling_band_height",
            "ceiling_span_profile",
            "ceiling_edge_weight",
            "ceiling_opening_clearance",
            "ceiling_detail_density",
            "ceiling_drop_forbidden",
        ),
    },
    "backwall_panel": {
        "label": "Backwall Panel",
        "visual_role": "structural_depth",
        "specific_fields": (
            "panel_depth_profile",
            "panel_value_separation",
            "panel_center_quietness",
            "panel_architecture_language",
            "panel_repeat_rhythm",
            "panel_focal_suppression",
        ),
    },
}

STRUCTURAL_SCHEMA_KEYS = {"walls", "floor", "platforms", "doors", "pits", "ceiling", "backwall_panel"}
SCENIC_SCHEMA_KEYS = {"background", "midground"}

COMPONENT_SCHEMA_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "walls": {
        "material_family": "weathered structural stone",
        "silhouette_rules": ["vertical mass reads as enclosing wall shell", "repeat bays instead of scenic one-off shapes"],
        "detail_density": "medium",
        "value_contrast": "low_to_medium with darker edges and readable planes",
        "damage_profile": "broken masonry, chips, and restrained collapse",
        "readability_constraints": ["must read as room enclosure", "avoid scenic perspective that flattens gameplay depth"],
        "negative_constraints": ["no altar scene", "no brazier focal energy", "no giant center architecture"],
        "variation_rules": ["repeat with subtle block shifts", "allow local wear without breaking wall rhythm"],
        "enclosure_read": "side walls and rear wall planes must read as the room shell",
        "bay_rhythm": "measured repeating bays with readable spacing",
        "column_width_class": "heavy",
        "wall_face_depth": "shallow layered recesses",
        "ceiling_junction": "soft arch or stone lintel tie-in",
        "base_trim": "stone base trim anchoring walls to the floor",
        "edge_darkening": "darker edges and recess seams",
        "repetition_interval": "medium_repeat",
    },
    "floor": {
        "material_family": "weathered structural stone",
        "silhouette_rules": ["clear top lip", "side-view slab silhouette", "no dramatic perspective"],
        "detail_density": "medium",
        "value_contrast": "top plane slightly lighter than face",
        "damage_profile": "chips, seams, and worn edges",
        "readability_constraints": ["platform top must read immediately", "front face must separate from background"],
        "negative_constraints": ["no giant ritual circle", "no brazier base", "no scenic floor perspective"],
        "variation_rules": ["modular slab breakup", "quiet pattern changes across repeats"],
        "top_lip_thickness": "clear 4-8px lip at runtime scale",
        "face_height": "moderate face height with readable front plane",
        "seam_pattern": "quiet masonry seams",
        "top_plane_read": "top plane brighter and calmer than face",
        "edge_breakup": "small chips and restrained cracks",
        "underside_darkening": "underside falls off darker than top plane",
        "modular_repeat_width": "tileable medium repeat span",
    },
    "platforms": {
        "material_family": "weathered structural stone",
        "silhouette_rules": ["clear top lip", "flat traversal top", "simple readable endcaps"],
        "detail_density": "medium",
        "value_contrast": "top plane lighter than face",
        "damage_profile": "light breakage and ledge wear",
        "readability_constraints": ["ledge top must pop from background", "underside detail cannot muddy jump reads"],
        "negative_constraints": ["no scenic attachments", "no dangling braziers", "no ritual symbols"],
        "variation_rules": ["vary cracks and seam placement", "keep proportions consistent across lengths"],
        "top_lip_thickness": "clear 4-8px lip at runtime scale",
        "face_height": "compact readable face",
        "endcap_style": "simple broken masonry endcap",
        "support_style": "minimal implied support only",
        "ledge_read": "strong traversal ledge read",
        "underside_variation": "light underside breakup only",
        "modular_repeat_width": "tileable medium repeat span",
    },
    "doors": {
        "material_family": "stone frame with aged gate insert",
        "silhouette_rules": ["centered opening", "strong outer frame", "clean threshold silhouette"],
        "detail_density": "medium",
        "value_contrast": "opening darker than frame",
        "damage_profile": "aged but intact threshold hardware",
        "readability_constraints": ["opening must read at a glance", "door frame cannot blend into wall mass"],
        "negative_constraints": ["no chamber scene around the door", "no floor plane", "no altar dressing"],
        "variation_rules": ["vary carve lines and gate panel wear", "keep frame proportions stable"],
        "frame_mass": "heavy readable frame",
        "opening_read": "dark centered opening or gate cavity",
        "threshold_depth": "shallow but visible threshold recess",
        "gate_panel_style": "aged inset panels",
        "lock_overlay_style": "small readable lock overlay only when needed",
        "side_clearance": "clear side clearance around opening",
    },
    "pits": {
        "material_family": "broken stone drop with dark void interior",
        "silhouette_rules": ["clear rim read", "open non-walkable void", "vertical drop silhouette"],
        "detail_density": "low_to_medium",
        "value_contrast": "rim lighter than interior void",
        "damage_profile": "broken lip and damp erosion",
        "readability_constraints": ["player must read hazard immediately", "rim must contrast from interior"],
        "negative_constraints": ["no scenic bridge treatment", "no fake floor fill", "no soft ambiguous interior"],
        "variation_rules": ["vary rim chips and wall streaks", "keep drop interior visually calm"],
        "rim_profile": "clear chipped rim silhouette",
        "wall_drop_profile": "vertical stone wall drop",
        "interior_fill_mode": "deep shadow or void fog",
        "hazard_read": "non-walkable and dangerous at a glance",
        "fog_fill": "subtle low fog only if it keeps the void readable",
        "left_right_edge_rules": "rim edges remain crisp and symmetrical enough to read jumps",
    },
    "background": {
        "material_family": "far-depth architectural stone shell",
        "silhouette_rules": ["enclosing hall shell", "open center lane", "far-depth columns and arches only"],
        "detail_density": "medium",
        "value_contrast": "muted far-depth values with softened center",
        "damage_profile": "aged architecture without focal props",
        "readability_constraints": ["must read as enclosing room shell", "center lane stays calm and open"],
        "negative_constraints": ["no altar", "no brazier", "no center dais", "no near framing"],
        "variation_rules": ["vary arch spacing and recess depth", "keep the middle quiet across variants"],
        "enclosure_architecture": "rear wall, side walls, arches, and pillars read as one hall shell",
        "center_openness": "fully open and calm center lane",
        "far_depth_layers": "at least two depth bands of architecture",
        "focal_suppression": "explicitly suppress altar, brazier, shrine, and dais imagery",
        "floor_plane_suppression": "no near floor strip or scenic floor carryover",
        "atmospheric_falloff": "soft haze into distance without bright focal hotspots",
    },
    "midground": {
        "material_family": "side-frame stone or column mass",
        "silhouette_rules": ["side-only framing", "transparent open center", "thin occlusion where needed"],
        "detail_density": "low_to_medium",
        "value_contrast": "subdued side mass with center transparency",
        "damage_profile": "light edge wear and cracks",
        "readability_constraints": ["center route stays readable", "midground cannot cross the floor lane"],
        "negative_constraints": ["no center object", "no full-width arch", "no floor-crossing silhouette"],
        "variation_rules": ["vary side cluster placement", "keep center clear ratio consistent"],
        "side_mass_only": "true",
        "center_clearance_ratio": "0.45",
        "occluder_types": "arches, columns, side buttresses",
        "alpha_profile": "solid on edges, transparent through center",
        "floor_crossing_forbidden": "true",
        "route_overlap_forbidden": "true",
    },
    "ceiling": {
        "material_family": "weathered structural stone",
        "silhouette_rules": [
            "one continuous opaque ceiling cap across the full image width",
            "reads as a single horizontal slab or lintel course, not multiple pasted panels",
            "top shell closure reads above the route",
            "avoid decorative hanging clutter",
        ],
        "detail_density": "low_to_medium",
        "value_contrast": "darker than traversal tops but lighter than empty void",
        "damage_profile": "restrained cracks and chipped spans",
        "readability_constraints": ["must help close the room shell", "must not hang into the main traversal lane"],
        "negative_constraints": [
            "no hanging focal prop",
            "no chandelier",
            "no dramatic center drop",
            "no row of separate arched windows, grilles, or arcade holes across the band",
            "no collage of side-by-side framed openings or distinct vertical bays in the cap",
            "no scenic room slice or distant hall visible through the band",
        ],
        "variation_rules": [
            "vary only mortar, chips, and crack placement within one continuous cap",
            "keep the same single-span slab read across biome variants",
        ],
        "ceiling_band_height": "moderate shell cap height",
        "ceiling_span_profile": "single flat lintel, heavy beam course, or shallow barrel vault — not a multi-arch arcade",
        "ceiling_edge_weight": "heavy outer edge, quieter center",
        "ceiling_opening_clearance": "preserve headroom over the main route",
        "ceiling_detail_density": "restrained surface detail",
        "ceiling_drop_forbidden": "true",
    },
    "backwall_panel": {
        "material_family": "far structural stone panel",
        "silhouette_rules": ["backwall planes support shell depth", "panel stays behind gameplay surfaces", "center remains quiet"],
        "detail_density": "low_to_medium",
        "value_contrast": "subordinate to traversal surfaces with visible separation",
        "damage_profile": "aged stone seams and shallow recesses",
        "readability_constraints": ["must not replace the foreground shell", "must preserve center-lane readability"],
        "negative_constraints": ["no altar", "no center mural focal scene", "no bright focal opening"],
        "variation_rules": ["vary recess spacing", "keep panel rhythm modular and biome-consistent"],
        "panel_depth_profile": "shallow recessed wall depth",
        "panel_value_separation": "slightly darker than traversal surfaces",
        "panel_center_quietness": "center remains calm and low-contrast",
        "panel_architecture_language": "echo biome shell family without becoming the main shell",
        "panel_repeat_rhythm": "moderate repeating stone panel rhythm",
        "panel_focal_suppression": "explicitly suppress shrine, altar, and mural focal scenes",
    },
}

V2_SLOT_FAMILY_SPECS: Tuple[Dict[str, Any], ...] = (
    {"component_type": "background_far_plate", "schema_key": "background", "template_component_type": "background_plate", "size": (1600, 1200), "orientation": "full", "transparency_mode": "opaque", "visual_role": "far_depth", "slot_group": "background", "tile_mode": "stretch"},
    {"component_type": "midground_side_frame", "schema_key": "midground", "template_component_type": "midground_frame", "size": (1600, 1200), "orientation": "full", "transparency_mode": "alpha", "visual_role": "side_frame", "slot_group": "midground", "tile_mode": "stretch"},
    {"component_type": "room_shell_foreground", "schema_key": "walls", "template_component_type": "foreground_frame", "size": (1600, 1200), "orientation": "full", "transparency_mode": "alpha", "visual_role": "unified_chamber_shell", "slot_group": "foreground", "tile_mode": "stretch"},
    {"component_type": "ceiling_band", "schema_key": "ceiling", "template_component_type": "ceiling_piece", "size": (1600, 224), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "structural_ceiling", "slot_group": "ceiling", "tile_mode": "stretch"},
    {"component_type": "wall_module_left", "schema_key": "walls", "template_component_type": "wall_piece", "size": (320, 960), "orientation": "vertical", "transparency_mode": "opaque", "visual_role": "structural_wall", "slot_group": "walls", "tile_mode": "stretch"},
    {"component_type": "wall_module_right", "schema_key": "walls", "template_component_type": "wall_piece", "size": (320, 960), "orientation": "vertical", "transparency_mode": "opaque", "visual_role": "structural_wall", "slot_group": "walls", "tile_mode": "stretch"},
    {"component_type": "wall_base_trim_left", "schema_key": "walls", "template_component_type": "wall_piece", "size": (256, 160), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "structural_trim", "slot_group": "walls", "tile_mode": "stretch"},
    {"component_type": "wall_base_trim_right", "schema_key": "walls", "template_component_type": "wall_piece", "size": (256, 160), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "structural_trim", "slot_group": "walls", "tile_mode": "stretch"},
    {"component_type": "main_floor_top", "schema_key": "floor", "template_component_type": "primary_floor_piece", "size": (512, 96), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "main_route", "slot_group": "floor", "tile_mode": "tile_x"},
    {"component_type": "main_floor_face", "schema_key": "floor", "template_component_type": "primary_floor_piece", "size": (512, 128), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "main_route_face", "slot_group": "floor", "tile_mode": "tile_x"},
    {"component_type": "hero_platform_top", "schema_key": "platforms", "template_component_type": "hero_platform_piece", "size": (320, 72), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "hero_platform", "slot_group": "platforms", "tile_mode": "tile_x"},
    {"component_type": "hero_platform_face", "schema_key": "platforms", "template_component_type": "hero_platform_piece", "size": (320, 84), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "hero_platform_face", "slot_group": "platforms", "tile_mode": "tile_x"},
    {"component_type": "door_frame", "schema_key": "doors", "template_component_type": "door_piece", "size": (192, 288), "orientation": "vertical", "transparency_mode": "alpha", "visual_role": "transition", "slot_group": "doors", "tile_mode": "stretch"},
    {"component_type": "pit_rim", "schema_key": "pits", "template_component_type": "primary_floor_piece", "size": (256, 96), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "hazard_rim", "slot_group": "pits", "tile_mode": "tile_x"},
    {"component_type": "pit_interior", "schema_key": "pits", "template_component_type": "background_plate", "size": (256, 192), "orientation": "vertical", "transparency_mode": "opaque", "visual_role": "hazard_void", "slot_group": "pits", "tile_mode": "stretch"},
)

V2_SLOT_SPEC_BY_TYPE: Dict[str, Dict[str, Any]] = {entry["component_type"]: entry for entry in V2_SLOT_FAMILY_SPECS}

FOREGROUND_FRAME_CENTER_KEY_RGB: Tuple[int, int, int] = (0, 255, 0)
# Keep-clear fill for room_shell silhouette refs and prompt contract (same family as layout conditioning).
# White (#FFFFFF) margins in the mask taught Gemini paper-white halos at chamber edges and image borders.
ROOM_SHELL_SILHOUETTE_CLEAR_RGB: Tuple[int, int, int] = (8, 12, 16)
ROOM_SHELL_GUIDE_RGB: Tuple[int, int, int] = (116, 126, 136)
ROOM_SHELL_CONTRACT_BAND_RGB: Tuple[int, int, int] = ROOM_SHELL_GUIDE_RGB
_ROOM_SHELL_BAND_MASK_CACHE: Dict[Tuple[int, int, int, Tuple[Tuple[int, int], ...]], Image.Image] = {}

# Full-frame 1600×1200 atlas border thickness (v2: 3× original v1 contract).
ATLAS_WIDTH = 1600
ATLAS_HEIGHT = 1200
FOREGROUND_FRAME_BORDER_TOP_PX = 720  # was 240
FOREGROUND_FRAME_BORDER_BOTTOM_PX = 360  # was 120
FOREGROUND_FRAME_BORDER_SIDE_PX = 672  # was 224
# Post-punchout top-band mean luminance gradient (see `_image_region_contrast`). Mask-driven shells
# often exceed 0.024 from legitimate mortar/stone micro-contrast; keep high enough to still flag
# obvious tiled-strip ceiling assemblies.
ROOM_SHELL_CEILING_BAND_MEAN_CONTRAST_MAX = 0.035
BORDER_PIECE_BORDER_TOP_PX = 672  # was 224
BORDER_PIECE_BORDER_BOTTOM_PX = 360  # was 120
BORDER_PIECE_BORDER_SIDE_PX = 672  # was 224
# Border-piece generation gate: require a visibly heavier frame read than older thin-shell outputs.
BORDER_PIECE_MIN_SIDE_THICKNESS_NORM = 0.34
BORDER_PIECE_MIN_TOP_THICKNESS_FILL = 0.62
BORDER_PIECE_MIN_BOTTOM_THICKNESS_FILL = 0.52


def _foreground_frame_inner_rect_inclusive() -> Tuple[int, int, int, int]:
    """Inclusive (left, top, right, bottom) chroma center rectangle on the 1600×1200 atlas."""
    s = FOREGROUND_FRAME_BORDER_SIDE_PX
    t = FOREGROUND_FRAME_BORDER_TOP_PX
    b = FOREGROUND_FRAME_BORDER_BOTTOM_PX
    return (s, t, ATLAS_WIDTH - s - 1, ATLAS_HEIGHT - b - 1)


def _foreground_frame_center_key_box_norm() -> Tuple[float, float, float, float]:
    """Fractional (l, t, r, b) for _region_luminance / _region_chroma_key_fraction (exclusive r/b in pixel crop)."""
    l, t, r, b = _foreground_frame_inner_rect_inclusive()
    return (l / ATLAS_WIDTH, t / ATLAS_HEIGHT, (r + 1) / ATLAS_WIDTH, (b + 1) / ATLAS_HEIGHT)


def _foreground_frame_biome_template_role_text() -> str:
    """Long biome prompt for foreground_frame; kept in one place so pixel bounds stay aligned with guides."""
    ft = FOREGROUND_FRAME_BORDER_TOP_PX
    fb = FOREGROUND_FRAME_BORDER_BOTTOM_PX
    fs = FOREGROUND_FRAME_BORDER_SIDE_PX
    il, itop, ir, ib = _foreground_frame_inner_rect_inclusive()
    top_end = ft - 1
    side_x1 = fs - 1
    right_x0 = ATLAS_WIDTH - fs
    bottom_y0 = ATLAS_HEIGHT - fb
    wall_y1 = ATLAS_HEIGHT - fb - 1
    return (
        "Single shared foreground structural frame atlas for a 2D sidescroller chamber (1600x1200). "
        "This image is a layout atlas used exclusively for later region crops. It is not a scene, not concept art, and not a composition exercise. "
        "The provided reference image is a geometry-only occupancy guide. Use its occupied coordinates only. Do not copy its flat fills, gray values, outlines, or mask-like treatment literally into the final art. "
        "If the geometry guide and the style swatch disagree, preserve the occupied coordinates and border silhouette from the geometry guide exactly, and use the style swatch only for stone family, crack rhythm, and palette. "
        "Treat the image like a flat orthographic front elevation, not a 3D room view. "
        "Camera/projection contract: the entire atlas must read as a straight-on front elevation with zero perspective convergence and zero reveal depth. "
        "Do not depict an inset chamber opening, window reveal, portal mouth, inner jamb, receding corridor, or boxed recess. "
        "The left wall strip, right wall strip, and bottom band are all front-facing surfaces only, not side faces or top faces. "
        "No diagonal receding edges, no visible wall thickness returns, no interior corner perspective, and no near-versus-far plane cues. "
        "Priority order: (1) readable perimeter shell, (2) wall-to-center separation, (3) calm non-scenic center. "
        "Spatial contract: "
        f"(1) a fully continuous, clearly visible masonry ceiling band spanning left edge to right edge across exact pixel rows y=0..{top_end} — no gaps, no holes, no partial cap, no broken run; "
        "the top band must read as an obvious horizontal masonry strip by eye, with repeated block courses or lintel seams that make it visibly different from the center field; "
        "the top band must stay fully filled into both top-left and top-right outer corners with no black wedges, no corner voids, and no cropped-off triangular gaps; "
        f"the green center opening must not begin inside the top {ft} pixels; keep a full uninterrupted ceiling depth before the green field starts. "
        "if the image starts to read like a dark void, strengthen the top strip first rather than darkening the whole frame; "
        f"(2) continuous left wall strip at exact pixel region x=0..{side_x1}, y={ft}..{wall_y1} and continuous right wall strip at exact pixel region x={right_x0}..1599, y={ft}..{wall_y1} — "
        "both sides must be materially present as narrow heavy enclosure masses; neither side may collapse into near-black, disappear, or blend into the center field; "
        "the side walls must be visibly darker, denser, and more structural than the calmer center and must show a clear inner-edge transition into the center field; "
        "the side walls should carry the strongest masonry joint rhythm and silhouette weight in the image, but they must still read as front-facing wall strips, not recess mouths, alcoves, openings, deep side pockets, inset jambs, interior return faces, pillars, posts, columns, or freestanding vertical supports; "
        "keep the side strips as straight rectangular border masses from top to bottom: no tapering feet, no pedestal bases, no buttress plinths, no angled chamfers, no capitals, and no top or bottom shoulders projecting inward; "
        "do not add bright inner edge highlights, bevel rims, side-face reveals, or light vertical trims along the green opening; the inner wall edge should be a flat cut stone boundary, not a glowing jamb or recessed frame return; "
        "the stone immediately touching the green field must never be lighter than the main wall mass; do not create a pale border, illuminated rim, or highlighted cut line around the keyed opening; "
        "the side strips are fused to the outer image border and must not read like separate supports framing a doorway or opening; "
        f"(3) a thin continuous retaining floor band at exact pixel rows y={bottom_y0}..1199 across the full width — clearly visible across the full width; "
        "the bottom band must also read as an obvious horizontal masonry strip by eye, not just a slightly darker lower edge; "
        "if the image starts to read like a dark void, strengthen the bottom strip second rather than turning the lower frame into a shadow mass; "
        "it must read front-on and flat, with no visible top surface, not like a receding walk surface, perspective floor plane, stage floor, ledge lip, front step, or slab viewed from above; "
        "treat the bottom band like a retaining wall face or plinth course seen straight on, using front-facing block rectangles only; "
        "do not draw paving stones, receding tile seams, trapezoid slab tops, depth bevels, or any horizontal surface that suggests the player could stand on the band itself; "
        "do not add a bright upper lip, rim light, or recessed shadow shelf where the green field meets the bottom band; that boundary must stay flat and front-facing; "
        "do not draw a separate top-edge line, highlight seam, or light coping strip at y=1080 where the green field meets the bottom band; the keyed field should terminate directly into the same dark flat stone face; "
        "keep the upper edge of the bottom band straight and horizontal with no center rise, no wedge perspective, and no thickened front lip; "
        "the bottom band must also stay filled into both bottom-left and bottom-right corners with no black corner cutouts, no vignette wedges, and no empty outside triangles; "
        f"the green center opening must end above y={wall_y1} and may not drop into the bottom {fb} pixels; keep a full uninterrupted bottom retaining strip below the keyed field. "
        "(4) do not place platform ledge language, shelf language, or inward-protruding stone lips anywhere inside the wall-strip zones; wall strips must stay flush, vertical, and perimeter-only; "
        f"(5) center region at exact pixel region x={il}..{ir}, y={itop}..{ib} must be a reserved chroma-key field for later background replacement — "
        "fill that exact center rectangle with solid bright green screen color and keep it clean, flat, and uniform. "
        f"The very first green row must begin at y={itop} and the very first green columns must begin at x={il} on the left and x={ir} on the right; do not let stone overlap past those coordinates. "
        f"Pixels on the center boundary such as ({il},{itop}), (800,{itop}), ({ir},{itop}), ({il},{ib}), and ({ir},{ib}) should all still belong to the same green holdout rectangle, not to the masonry shell. "
        "Do not enlarge the green field upward or downward beyond those exact vertical limits. "
        "Do not paint stone, texture, cracks, props, shading, gradients, fog, glow, vignettes, floating fragments, platform silhouettes, or focal art inside that center field. "
        "The center is not a backwall painting exercise; it is a keyed holdout zone. "
        "No circular hotspot, no halo, no ring, no radial vignette, no centered glow, no inset panel border, and no light rim or outline around the center field. "
        "The green field must not be framed by a second lighter rectangle inside the border shell. "
        "Keep the inner edge between the border shell and the green field crisp and front-on, with no pillars, lips, or fragments crossing into the keyed center. "
        "If forced to choose, preserve heavier side walls and a simpler keyed center rather than decorative side ledges or scenic center detail. "
        "Value structure contract: "
        "ceiling band and floor band = readable horizontal strip zones with stronger band identity than the center field; "
        "outer wall strips = darkest and most detailed zone; "
        "inner edge of each wall strip = medium-dark transition zone; "
        "center field = solid chroma-key green reserve, with no stone patterning at all. "
        "Do not make the wall strips and center field the same value family or the same material family. "
        "The whole border must stay in one coherent cool dark stone family: top band, side walls, and bottom band should look like the same material under the same flat lighting, not different gray-versus-black zones. "
        "Texture contract: side walls should show most of the block joints, stone seams, edge cracks, and masonry rhythm. "
        "Center field should show no masonry cues at all because it is a keyed replacement zone. "
        "Left and right wall strips must have equal visual authority. "
        "Do not make the right wall softer, flatter, dimmer, or less distinct than the left wall. "
        "If one side is stronger, strengthen the weaker side instead of weakening both. "
        "Hard prohibitions: "
        "no floating ledges, shelves, or isolated stone fragments inside the center region; "
        "no side-wall protrusions, no inward shelves, no cantilevered lips, and no ledge-like shapes extending from either wall into the chamber; "
        "no torn edges, giant cracks spanning an entire band, or dramatic missing chunks; "
        "no asymmetric wall treatment — left and right strips must read as the same material family; "
        "no fog, atmospheric depth effects, arches, windows, openings, symbols, scenic depth, or scenic composition; "
        "no perspective floor plane, no tunnel opening read, no inward-lit bevels, no cast shadows projecting into the center, no dark inner shadow columns, no side-pocket recess shading, no radial center vignette, no global vignette, no inset opening frame, and no 3D portal framing; "
        "no directional lighting sweep, no side-to-center shadow falloff, and no shaded depth cues that make the atlas feel volumetric; "
        "no bright focal elements or glowing areas; "
        "no cyan, teal, aqua, or electric-blue rim hugging the green chroma-key boundary — the keyed edge must read as stone cut against green, not a UI-colored stroke. "
        "Do not solve the frame by making the whole image uniformly dark blue-gray; the image must still show a perimeter-versus-center read. "
        "Preserve the provided border silhouette and occupied-zone layout exactly: structure belongs only in the top band, bottom band, and narrow outer side strips, while the center envelope stays open and non-structural. "
        "Small chips, cracks, and edge wear are allowed inside those occupied border envelopes, but do not move structure outside them. "
        "Keep the material family close to the darker ruined-gothic biome kit: cool dark stone, restrained contrast, and no pale gray-beige stone drift. "
        "Think of the desired result as a perimeter-only chamber shell diagram painted in one consistent stone family. "
        "The four perimeter bands must share one consistent stone family so ceiling, wall, and floor crops all match."
    )


SHELL_FAMILY_PRESETS: Dict[str, Dict[str, str]] = {
    "gothic_ruin": {
        "wall_family": "broken_gothic_stone",
        "platform_family": "broken_masonry_ledge",
        "door_family": "arch_door",
        "backdrop_family": "ruined_arch_hall",
    },
    "ritual_shrine": {
        "wall_family": "broken_gothic_stone",
        "platform_family": "carved_ledge",
        "door_family": "ritual_gate",
        "backdrop_family": "ruined_arch_hall",
    },
    "flooded_stone": {
        "wall_family": "weathered_stone",
        "platform_family": "broken_masonry_ledge",
        "door_family": "arch_door",
        "backdrop_family": "flooded_arch_hall",
    },
    "industrial_underworks": {
        "wall_family": "industrial_ribbed",
        "platform_family": "iron_walkway",
        "door_family": "iron_gate",
        "backdrop_family": "industrial_depth",
    },
    "rooted_overgrowth": {
        "wall_family": "weathered_stone",
        "platform_family": "broken_masonry_ledge",
        "door_family": "arch_door",
        "backdrop_family": "ruined_arch_hall",
    },
    "void_structure": {
        "wall_family": "weathered_stone",
        "platform_family": "carved_ledge",
        "door_family": "ritual_gate",
        "backdrop_family": "ruined_arch_hall",
    },
    "weathered_stone": {
        "wall_family": "weathered_stone",
        "platform_family": "broken_masonry_ledge",
        "door_family": "arch_door",
        "backdrop_family": "ruined_arch_hall",
    },
}


def _default_component_prompts(description: str, direction: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, str]]:
    base = str(description or "").strip() or "A readable room that stays inside the project art direction."
    direction_text = ""
    if isinstance(direction, dict):
        chunks = [
            str(direction.get("high_level_direction") or "").strip(),
            ", ".join(str(item).strip() for item in (direction.get("material_rules") or []) if str(item).strip()),
            ", ".join(str(item).strip() for item in (direction.get("shape_language") or []) if str(item).strip()),
        ]
        direction_text = " ".join(chunk for chunk in chunks if chunk).strip()
    suffix = f" Keep it aligned to {direction_text}." if direction_text else ""
    return {
        "floor": {
            "label": "Floor",
            "prompt": f"{base} Describe the floor surface, slab pattern, cracks, wear, moisture, and traversal readability.{suffix}".strip(),
        },
        "platforms": {
            "label": "Platforms",
            "prompt": f"{base} Describe platform tops, front faces, edge damage, supports, and how ledges should read in gameplay.{suffix}".strip(),
        },
        "walls": {
            "label": "Walls",
            "prompt": f"{base} Describe the wall structure, repeating architecture, depth rhythm, damage, and any buttresses, arches, or overgrowth.{suffix}".strip(),
        },
        "doors": {
            "label": "Doors",
            "prompt": f"{base} Describe door frames, gate material, motifs, and how thresholds should feel inside this room.{suffix}".strip(),
        },
        "background": {
            "label": "Background",
            "prompt": f"{base} Describe the background and midground architecture, silhouettes, depth, fog, landmarks, and distant atmosphere.{suffix}".strip(),
        },
    }


def _coerce_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    return [chunk.strip() for chunk in text.split(";") if chunk.strip()]


def _component_schema_seed_text(
    schema_key: str,
    description: str,
    legacy_components: Optional[Dict[str, Any]] = None,
    direction: Optional[Dict[str, Any]] = None,
) -> str:
    legacy_prompt = ""
    if isinstance(legacy_components, dict):
        legacy_prompt = str(((legacy_components.get(schema_key) or {}).get("prompt") or "")).strip()
        if not legacy_prompt and schema_key == "midground":
            legacy_prompt = str(((legacy_components.get("background") or {}).get("prompt") or "")).strip()
        if not legacy_prompt and schema_key == "pits":
            legacy_prompt = str(((legacy_components.get("floor") or {}).get("prompt") or "")).strip()
    direction_text = str((direction or {}).get("high_level_direction") or "").strip()
    return " ".join(part for part in [description.strip(), legacy_prompt, direction_text] if part).strip()


def _default_component_schema(
    schema_key: str,
    description: str,
    legacy_components: Optional[Dict[str, Any]] = None,
    direction: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    schema_def = COMPONENT_SCHEMA_DEFS[schema_key]
    defaults = COMPONENT_SCHEMA_DEFAULTS[schema_key]
    seed_text = _component_schema_seed_text(schema_key, description, legacy_components, direction)
    design_intent = seed_text or f"Keep the {schema_key} aligned to the room art direction and gameplay readability."
    out: Dict[str, Any] = {
        "label": schema_def["label"],
        "design_intent": design_intent,
        "visual_role": schema_def["visual_role"],
    }
    for field in COMPONENT_SCHEMA_COMMON_FIELDS:
        if field in out:
            continue
        value = defaults.get(field)
        out[field] = list(value) if isinstance(value, list) else str(value or "").strip()
    for field in schema_def["specific_fields"]:
        value = defaults.get(field)
        out[field] = list(value) if isinstance(value, list) else str(value or "").strip()
    return out


def _normalize_single_component_schema(
    schema_key: str,
    raw_value: Any,
    description: str,
    legacy_components: Optional[Dict[str, Any]] = None,
    direction: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fallback = _default_component_schema(schema_key, description, legacy_components, direction)
    raw = raw_value if isinstance(raw_value, dict) else {}
    out: Dict[str, Any] = {"label": fallback["label"]}
    list_fields = {"silhouette_rules", "readability_constraints", "negative_constraints", "variation_rules"}
    for field in COMPONENT_SCHEMA_COMMON_FIELDS:
        value = raw.get(field)
        if field in list_fields:
            cleaned = _coerce_string_list(value)
            out[field] = cleaned if cleaned else list(fallback[field])
        else:
            text = str(value or "").strip()
            out[field] = text or fallback[field]
    for field in COMPONENT_SCHEMA_DEFS[schema_key]["specific_fields"]:
        value = raw.get(field)
        if isinstance(fallback.get(field), list):
            cleaned = _coerce_string_list(value)
            out[field] = cleaned if cleaned else list(fallback[field])
            continue
        text = str(value or "").strip()
        out[field] = text or fallback[field]
    return out


def _normalize_component_schemas_response(
    raw: Any,
    description: str,
    legacy_components: Optional[Dict[str, Any]] = None,
    direction: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    source = raw if isinstance(raw, dict) else {}
    out: Dict[str, Dict[str, Any]] = {}
    for schema_key in COMPONENT_SCHEMA_DEFS:
        out[schema_key] = _normalize_single_component_schema(
            schema_key,
            source.get(schema_key),
            description,
            legacy_components,
            direction,
        )
    return out


def _room_has_pits(room: Dict[str, Any], geometry: Optional[Dict[str, Any]] = None) -> bool:
    if isinstance(room.get("pits"), list) and room.get("pits"):
        return True
    if isinstance(room.get("voidSpans"), list) and room.get("voidSpans"):
        return True
    if isinstance(geometry, dict):
        return int(geometry.get("pit_count") or 0) > 0
    return False


def _validate_component_schemas(
    room: Dict[str, Any],
    spec: Dict[str, Any],
    geometry: Dict[str, Any],
) -> Dict[str, Any]:
    schemas = spec.get("component_schemas") if isinstance(spec.get("component_schemas"), dict) else {}
    required_components = ["walls", "floor", "platforms", "background", "midground"]
    if int(geometry.get("door_count") or 0) > 0:
        required_components.append("doors")
    if _room_has_pits(room, geometry):
        required_components.append("pits")
    errors: List[str] = []
    statuses: Dict[str, Dict[str, Any]] = {}
    list_fields = {"silhouette_rules", "readability_constraints", "negative_constraints", "variation_rules"}
    for schema_key, schema_def in COMPONENT_SCHEMA_DEFS.items():
        schema = schemas.get(schema_key)
        component_errors: List[str] = []
        if schema_key in required_components and not isinstance(schema, dict):
            component_errors.append("missing_schema")
        if isinstance(schema, dict):
            for field in COMPONENT_SCHEMA_COMMON_FIELDS:
                value = schema.get(field)
                if field in list_fields:
                    if not _coerce_string_list(value):
                        component_errors.append(f"missing_{field}")
                elif not str(value or "").strip():
                    component_errors.append(f"missing_{field}")
            for field in schema_def["specific_fields"]:
                value = schema.get(field)
                if isinstance(value, list):
                    if not _coerce_string_list(value):
                        component_errors.append(f"missing_{field}")
                elif not str(value or "").strip():
                    component_errors.append(f"missing_{field}")
            if schema_key == "background":
                if "open" not in str(schema.get("center_openness") or "").lower():
                    component_errors.append("background_center_not_open")
                focal_text = " ".join(_coerce_string_list(schema.get("negative_constraints"))) + " " + str(schema.get("focal_suppression") or "")
                if not any(token in focal_text.lower() for token in ("altar", "brazier", "dais", "shrine")):
                    component_errors.append("background_focal_suppression_missing")
                floor_text = str(schema.get("floor_plane_suppression") or "").lower()
                if "no" not in floor_text and "suppress" not in floor_text:
                    component_errors.append("background_floor_plane_carryover_risk")
            if schema_key == "midground":
                if "true" not in str(schema.get("side_mass_only") or "").lower():
                    component_errors.append("midground_not_side_only")
                try:
                    ratio = float(schema.get("center_clearance_ratio") or 0)
                except (TypeError, ValueError):
                    ratio = 0.0
                if ratio < 0.35:
                    component_errors.append("midground_center_clearance_too_low")
                if "true" not in str(schema.get("floor_crossing_forbidden") or "").lower():
                    component_errors.append("midground_floor_crossing_allowed")
                if "true" not in str(schema.get("route_overlap_forbidden") or "").lower():
                    component_errors.append("midground_route_overlap_allowed")
        status = "ready"
        if component_errors:
            status = "invalid"
        elif schema_key not in required_components:
            status = "normalized"
        statuses[schema_key] = {
            "status": status,
            "errors": component_errors,
        }
        errors.extend(f"{schema_key}:{error}" for error in component_errors)
    overall_status = "ready" if not errors else "invalid"
    return {
        "valid": not errors,
        "status": overall_status,
        "required_components": required_components,
        "optional_components": [key for key in COMPONENT_SCHEMA_DEFS if key not in required_components],
        "component_statuses": statuses,
        "errors": errors,
    }


def _infer_shell_family(spec: Dict[str, Any]) -> str:
    component_text = " ".join(
        str(((spec.get("components") or {}).get(key) or {}).get("prompt") or "")
        for key, _label in COMPONENT_KEYS
    )
    text = " ".join([
        str(spec.get("theme_id") or ""),
        str(spec.get("description") or ""),
        str(spec.get("mood") or ""),
        " ".join(spec.get("materials") or []),
        " ".join(spec.get("tags") or []),
        component_text,
    ]).lower()
    if any(word in text for word in ("industrial", "underworks", "steel", "pipe", "boiler", "machinery", "factory")):
        return "industrial_underworks"
    if any(word in text for word in ("void", "astral", "ethereal", "dream", "abyss", "spectral")):
        return "void_structure"
    if any(word in text for word in ("forest", "root", "roots", "overgrown", "moss", "ivy", "vine")):
        return "rooted_overgrowth"
    if any(word in text for word in ("flood", "water", "drip", "seep", "wet", "damp", "catacomb")):
        return "flooded_stone"
    if any(word in text for word in ("shrine", "altar", "ritual", "sacred", "temple")):
        return "ritual_shrine"
    if any(word in text for word in ("gothic", "cathedral", "crypt", "ruin", "ruined", "buttress", "arch")):
        return "gothic_ruin"
    return "weathered_stone"


def _normalize_component_prompts_response(raw: Any, fallback_description: str, direction: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, str]]:
    fallback = _default_component_prompts(fallback_description, direction)
    source = raw if isinstance(raw, dict) else {}
    out: Dict[str, Dict[str, str]] = {}
    for key, label in COMPONENT_KEYS:
        item = source.get(key)
        if isinstance(item, dict):
            prompt = str(item.get("prompt") or item.get("description") or "").strip()
            item_label = str(item.get("label") or label).strip() or label
        else:
            prompt = str(item or "").strip()
            item_label = label
        if not prompt:
            prompt = fallback[key]["prompt"]
        out[key] = {
            "label": item_label,
            "prompt": prompt,
        }
    return out


def generate_room_environment_component_prompts(project_id: str, room_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    description = str(payload.get("description") or env["spec"].get("description") or "").strip()
    if not description:
        raise ValueError("Environment description is required.")
    geometry = _room_geometry(room)
    existing = _normalize_component_prompts_response(
        payload.get("components") if isinstance(payload.get("components"), dict) else env["spec"].get("components"),
        description,
        direction,
    )
    system_prompt = textwrap.dedent(
        """\
        You generate room-environment component prompts for a Phaser-based game editor.
        Respect the locked art direction strictly.
        Keep the prompts novice-friendly, concrete, and focused on visible room features.
        Return ONLY valid JSON in this shape:
        {
          "components": {
            "floor": {"label": "Floor", "prompt": "..."},
            "platforms": {"label": "Platforms", "prompt": "..."},
            "walls": {"label": "Walls", "prompt": "..."},
            "doors": {"label": "Doors", "prompt": "..."},
            "background": {"label": "Background", "prompt": "..."}
          },
          "notes": ["...", "..."]
        }
        """
    )
    user_prompt = json.dumps({
        "art_direction": direction,
        "frozen_concepts": direction.get("frozen_concepts") or [],
        "room_geometry": geometry,
        "template_context": env["template_context"],
        "room_description": description,
        "existing_components": existing,
        "instruction": str(payload.get("instruction") or "Generate concise prompts for floor, platforms, walls, doors, and background."),
    }, indent=2)
    ai_payload = _gemini_json(system_prompt, user_prompt)
    components = _normalize_component_prompts_response(
        (ai_payload or {}).get("components"),
        description,
        direction,
    )
    env["spec"]["description"] = description
    env["spec"]["components"] = copy.deepcopy(components)
    project["updated_at"] = now_iso()
    save_project(project)
    return {
        "ok": True,
        "components": copy.deepcopy(components),
        "notes": [str(item).strip() for item in ((ai_payload or {}).get("notes") or []) if str(item).strip()][:6],
        "used_ai": bool(ai_payload),
        "room_geometry": geometry,
    }


def _default_scene_schema(spec: Dict[str, Any], geometry: Dict[str, Any]) -> Dict[str, Any]:
    component_text = " ".join(
        str(((spec.get("components") or {}).get(key) or {}).get("prompt") or "")
        for key, _label in COMPONENT_KEYS
    )
    text = " ".join([
        str(spec.get("theme_id") or ""),
        str(spec.get("description") or ""),
        str(spec.get("mood") or ""),
        " ".join(spec.get("materials") or []),
        " ".join(spec.get("tags") or []),
        component_text,
    ]).lower()
    set_dressing: List[Dict[str, Any]] = []
    background_layers: List[Dict[str, Any]] = []
    effects = {
        "fog_profile": "low_ground_mist" if "fog" in text or "mist" in text or "damp" in text else "light_depth_haze",
        "particle_profile": "dust_motes",
        "lighting_profile": "single_focal_glow",
    }
    shell_family = _infer_shell_family(spec)
    preset = SHELL_FAMILY_PRESETS.get(shell_family, SHELL_FAMILY_PRESETS["weathered_stone"])
    kit = {
        "shell_family": shell_family,
        "wall_family": preset["wall_family"],
        "platform_family": preset["platform_family"],
        "door_family": preset["door_family"],
        "backdrop_family": preset["backdrop_family"],
        "prop_density": "medium",
    }
    background_layers.append({
        "kind": "architecture",
        "motif": "gothic_arches" if any(word in text for word in ("gothic", "shrine", "ritual", "ruin")) else "stone_mass",
        "depth": "far",
        "density": "medium",
    })
    if any(word in text for word in ("fog", "mist", "wet", "damp", "water")):
        background_layers.append({
            "kind": "fog_band",
            "motif": "ground_mist",
            "depth": "mid",
            "density": "medium",
        })
    if any(word in text for word in ("shrine", "altar", "ritual", "sacred")):
        set_dressing.append({
            "type": "banner",
            "anchor": "ceiling",
            "zone": "right",
            "count": 1,
            "priority": "low",
            "avoid": ["door"],
        })
        set_dressing.append({
            "type": "chains",
            "anchor": "ceiling",
            "zone": "left",
            "count": 1,
            "priority": "low",
            "avoid": ["door"],
        })
        background_layers.append({
            "kind": "architecture",
            "motif": "recessed shrine apse",
            "depth": "far",
            "density": "low",
        })
    if any(word in text for word in ("gothic", "ruin", "stone", "buttress", "arch")):
        set_dressing.append({
            "type": "statue",
            "anchor": "floor",
            "zone": "left",
            "count": 1,
            "priority": "medium",
            "avoid": ["door"],
        })
        background_layers.append({
            "kind": "architecture",
            "motif": "columns",
            "depth": "mid",
            "density": "medium",
        })
    if any(word in text for word in ("damp", "wet", "moss", "root", "overgrown")):
        set_dressing.append({
            "type": "roots",
            "anchor": "wall",
            "zone": "right",
            "count": 2,
            "priority": "medium",
            "avoid": ["door"],
        })
    if geometry.get("height", 0) >= 900:
        set_dressing.append({
            "type": "chains",
            "anchor": "ceiling",
            "zone": "left",
            "count": 2,
            "priority": "low",
            "avoid": ["door"],
        })
    return {
        "background_layers": background_layers,
        "set_dressing": set_dressing,
        "effects": effects,
        "kit": kit,
        "placement_rules": {
            "keep_main_route_clear": True,
            "door_clearance_tiles": 2,
            "platform_clearance_tiles": 1,
        },
    }


def build_room_environment_spec(project_id: str, room_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
    requested_pipeline_version = envv3.normalize_pipeline_version(
        payload.get("environment_pipeline_version") or env.get("environment_pipeline_version")
    )
    env["environment_pipeline_version"] = requested_pipeline_version
    if requested_pipeline_version == envv3.V3_PIPELINE_VERSION:
        envv3.ensure_v3_metadata(env, room)
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    description = str(payload.get("description") or env["spec"].get("description") or "").strip()
    if not description:
        raise ValueError("Environment description is required.")
    components = _normalize_component_prompts_response(
        payload.get("components") if isinstance(payload.get("components"), dict) else env["spec"].get("components"),
        description,
        direction,
    )
    component_schemas = _normalize_component_schemas_response(
        payload.get("component_schemas") if isinstance(payload.get("component_schemas"), dict) else env["spec"].get("component_schemas"),
        description,
        components,
        direction,
    )
    geometry = _room_geometry(room)
    system_prompt = textwrap.dedent(
        """\
        You produce structured room-environment specs for a game editor.
        Respect the locked art direction strictly.
        Keep results readable for a platforming game.
        Return ONLY valid JSON in this shape:
        {"themeId":"cave|ruins|forest|shrine|sewer|void|custom","tags":["a"],"description":"...","mood":"...","lighting":"...","fog":"...","materials":["..."],"landmarks":["..."],"hazards":["..."],"compositionFocus":"...","readabilityNotes":["..."],"components":{"floor":{"label":"Floor","prompt":"..."},"platforms":{"label":"Platforms","prompt":"..."},"walls":{"label":"Walls","prompt":"..."},"doors":{"label":"Doors","prompt":"..."},"background":{"label":"Background","prompt":"..."}},"componentSchemas":{"walls":{"design_intent":"...","visual_role":"structural","material_family":"...","silhouette_rules":["..."],"detail_density":"...","value_contrast":"...","damage_profile":"...","readability_constraints":["..."],"negative_constraints":["..."],"variation_rules":["..."],"enclosure_read":"...","bay_rhythm":"...","column_width_class":"...","wall_face_depth":"...","ceiling_junction":"...","base_trim":"...","edge_darkening":"...","repetition_interval":"..."},"floor":{"design_intent":"...","visual_role":"traversal","material_family":"...","silhouette_rules":["..."],"detail_density":"...","value_contrast":"...","damage_profile":"...","readability_constraints":["..."],"negative_constraints":["..."],"variation_rules":["..."],"top_lip_thickness":"...","face_height":"...","seam_pattern":"...","top_plane_read":"...","edge_breakup":"...","underside_darkening":"...","modular_repeat_width":"..."},"platforms":{"design_intent":"...","visual_role":"traversal","material_family":"...","silhouette_rules":["..."],"detail_density":"...","value_contrast":"...","damage_profile":"...","readability_constraints":["..."],"negative_constraints":["..."],"variation_rules":["..."],"top_lip_thickness":"...","face_height":"...","endcap_style":"...","support_style":"...","ledge_read":"...","underside_variation":"...","modular_repeat_width":"..."},"doors":{"design_intent":"...","visual_role":"threshold","material_family":"...","silhouette_rules":["..."],"detail_density":"...","value_contrast":"...","damage_profile":"...","readability_constraints":["..."],"negative_constraints":["..."],"variation_rules":["..."],"frame_mass":"...","opening_read":"...","threshold_depth":"...","gate_panel_style":"...","lock_overlay_style":"...","side_clearance":"..."},"pits":{"design_intent":"...","visual_role":"hazard","material_family":"...","silhouette_rules":["..."],"detail_density":"...","value_contrast":"...","damage_profile":"...","readability_constraints":["..."],"negative_constraints":["..."],"variation_rules":["..."],"rim_profile":"...","wall_drop_profile":"...","interior_fill_mode":"...","hazard_read":"...","fog_fill":"...","left_right_edge_rules":"..."},"background":{"design_intent":"...","visual_role":"far_depth","material_family":"...","silhouette_rules":["..."],"detail_density":"...","value_contrast":"...","damage_profile":"...","readability_constraints":["..."],"negative_constraints":["..."],"variation_rules":["..."],"enclosure_architecture":"...","center_openness":"...","far_depth_layers":"...","focal_suppression":"...","floor_plane_suppression":"...","atmospheric_falloff":"..."},"midground":{"design_intent":"...","visual_role":"side_frame","material_family":"...","silhouette_rules":["..."],"detail_density":"...","value_contrast":"...","damage_profile":"...","readability_constraints":["..."],"negative_constraints":["..."],"variation_rules":["..."],"side_mass_only":"true","center_clearance_ratio":"0.45","occluder_types":"...","alpha_profile":"...","floor_crossing_forbidden":"true","route_overlap_forbidden":"true"}},"sceneSchema":{"backgroundLayers":[{"kind":"architecture|fog_band|roots|void_forms","motif":"...","depth":"far|mid|near","density":"low|medium|high"}],"setDressing":[{"type":"brazier|chains|altar|roots|statue|banner","anchor":"floor|platform|ceiling|wall","zone":"left|center|right|focal","count":1,"priority":"low|medium|high","avoid":["door","main_path"]}],"effects":{"fog_profile":"...","particle_profile":"...","lighting_profile":"..."},"kit":{"shell_family":"gothic_ruin|ritual_shrine|flooded_stone|industrial_underworks|rooted_overgrowth|void_structure|weathered_stone","wall_family":"weathered_stone|broken_gothic_stone|industrial_ribbed","platform_family":"broken_masonry_ledge|carved_ledge|iron_walkway","door_family":"arch_door|ritual_gate|iron_gate","backdrop_family":"ruined_arch_hall|flooded_arch_hall|industrial_depth","prop_density":"low|medium|high"}}}
        """
    )
    user_prompt = json.dumps({
        "art_direction": direction,
        "frozen_concepts": direction.get("frozen_concepts") or [],
        "room_geometry": geometry,
        "template_context": env["template_context"],
        "description": description,
        "components": components,
        "component_schemas": component_schemas,
    }, indent=2)
    ai_payload = _gemini_json(system_prompt, user_prompt)
    spec = _normalize_spec_response(ai_payload or {}, description)
    spec["components"] = _normalize_component_prompts_response(spec.get("components"), description, direction)
    spec["component_schemas"] = _normalize_component_schemas_response(spec.get("component_schemas"), description, spec["components"], direction)
    spec["scene_schema"] = spec["scene_schema"] if spec["scene_schema"] else _default_scene_schema(spec, geometry)
    schema_validation = _validate_component_schemas(room, spec, geometry)
    env["themeId"] = spec["theme_id"]
    env["tags"] = list(spec["tags"])
    env["spec"] = copy.deepcopy(spec)
    env["preview"]["status"] = "needs_generation"
    env["preview"]["fallback_reason"] = None
    env["preview"]["images"] = []
    env["preview"]["approved_image_id"] = None
    env["preview"]["approved_palette"] = None
    env["runtime"]["status"] = "needs_generation"
    env["runtime"]["source"] = None
    env["runtime"]["applied_preview_id"] = None
    env["runtime"]["surface_palette"] = None
    env["runtime"]["material_keywords"] = list(spec.get("materials") or [])
    env["runtime"]["lighting_mode"] = str(spec.get("lighting") or "")
    env["runtime"]["last_applied_at"] = None
    env["runtime"]["bespoke_asset_manifest"] = {
        "schema_version": 2,
        "status": "idle",
        "biome_id": None,
        "border_first_contract": copy.deepcopy(direction.get("biome_packs", [{}])[0].get("border_first_contract") if (direction.get("biome_packs") or [{}])[0] else _normalize_border_first_contract(None)),
        "next_generation_contract": _border_first_generation_contract(),
        "source_preview_id": None,
        "generation_plan": [],
        "required_slots": [],
        "built_slots": [],
        "slot_groups": {},
        "schema_validation": schema_validation,
        "runtime_review": {"status": "idle", "fail_reasons": [], "metrics": {}, "screenshot_url": None, "review_mode": None},
        "review": {"status": "idle", "fail_reasons": [], "metrics": {}, "screenshot_url": None, "review_mode": None},
        "assets": {},
        "failed_assets": [],
        "used_ai": False,
        "generated_at": None,
        "validation_errors": [],
    }
    biome_pack = _select_biome_pack(direction)
    _sync_v3_environment_state(
        project_id,
        env,
        room,
        biome_id=str((biome_pack or {}).get("biome_id") or "") or None,
        generated_at=now_iso(),
    )
    asset_pack = env["runtime"]["asset_pack"]
    if asset_pack.get("assets"):
        _refresh_asset_pack_staleness(room, env, direction)
        if not asset_pack.get("stale_components"):
            asset_pack["stale_components"] = ["wall_body_strip", "floor_cap_strip", "platform_ledge_strip", "background", "midground_arches", "door"]
        asset_pack["status"] = "partial" if asset_pack.get("failed_assets") else "ready"
    else:
        asset_pack["status"] = "idle"
        asset_pack["used_ai"] = False
        asset_pack["generated_at"] = None
        asset_pack["source_preview_id"] = None
        asset_pack["assets"] = {}
    project["updated_at"] = now_iso()
    save_project(project)
    return {
        "ok": True,
        "environment": copy.deepcopy(env),
        "used_ai": bool(ai_payload),
        "room_geometry": geometry,
    }


def _hex_to_rgb(value: str, fallback: Tuple[int, int, int]) -> Tuple[int, int, int]:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 6:
        try:
            return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        except ValueError:
            return fallback
    return fallback


def _fit_points(points: List[List[float]], size: Tuple[int, int], padding: int = 32) -> List[Tuple[float, float]]:
    if not points:
        return []
    xs = [pt[0] for pt in points]
    ys = [pt[1] for pt in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    scale = min((size[0] - (padding * 2)) / width, (size[1] - (padding * 2)) / height)
    out: List[Tuple[float, float]] = []
    for x, y in points:
        out.append(((x - min_x) * scale + padding, (y - min_y) * scale + padding))
    return out


def _chamber_point_to_output_pixel(
    x: float,
    y: float,
    left: float,
    top: float,
    chamber_w: float,
    chamber_h: float,
    out_w: int,
    out_h: int,
    pad: int,
) -> Tuple[float, float]:
    if chamber_w <= 0 or chamber_h <= 0:
        return float(pad), float(pad)
    inner_w = max(1, out_w - (pad * 2))
    inner_h = max(1, out_h - (pad * 2))
    nx = ((float(x) - left) / chamber_w) * inner_w + pad
    ny = ((float(y) - top) / chamber_h) * inner_h + pad
    return nx, ny


def _polygon_area_room_units(geometry: Dict[str, Any]) -> float:
    """Shoelace area of room polygon in layout coordinates (same units as chamber_width/height)."""
    poly = geometry.get("polygon") or []
    if not isinstance(poly, list) or len(poly) < 3:
        return 0.0
    pts: List[Tuple[float, float]] = []
    for p in poly:
        if isinstance(p, (list, tuple)) and len(p) == 2:
            pts.append((float(p[0]), float(p[1])))
    if len(pts) < 3:
        return 0.0
    s = 0.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        s += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(s) * 0.5


def _geometry_footprint_vertex_count(geometry: Dict[str, Any]) -> int:
    poly = geometry.get("polygon") or []
    if not isinstance(poly, list):
        return 0
    return len([p for p in poly if isinstance(p, (list, tuple)) and len(p) == 2])


def _geometry_footprint_area_fill_ratio(geometry: Dict[str, Any]) -> float:
    """Polygon area / axis-aligned chamber box; <1 means concave, L-shape, or cutouts."""
    cw = float(geometry.get("chamber_width") or 0)
    ch = float(geometry.get("chamber_height") or 0)
    if cw <= 1.0 or ch <= 1.0:
        return 1.0
    area = _polygon_area_room_units(geometry)
    box = cw * ch
    return area / box if box > 0 else 1.0


def _geometry_footprint_shape_hint(geometry: Dict[str, Any]) -> str:
    """One-line hint for Gemini when the footprint is not a simple rectangle."""
    if not isinstance(geometry, dict):
        return ""
    vc = _geometry_footprint_vertex_count(geometry)
    ratio = _geometry_footprint_area_fill_ratio(geometry)
    bits: List[str] = []
    if vc > 4:
        bits.append(f"walkable polygon has {vc} vertices (non-rectangular outline)")
    if ratio < 0.9:
        bits.append(
            f"walkable area is ~{int(round(ratio * 100))}% of the bounding box (concave/L/step shape — preserve every corner and indent from the layout guide exactly)"
        )
    if not bits:
        return ""
    return "FOOTPRINT FIDELITY: " + " ".join(bits) + "."


def _inset_polygon_vertices_toward_centroid(
    points: List[Tuple[int, int]],
    inset_px: float,
) -> List[Tuple[int, int]]:
    """Shrink polygon toward its centroid (image pixel space). Used to leave a thicker opaque stone lip after punchout."""
    if inset_px <= 0 or len(points) < 3:
        return list(points)
    fx = [float(p[0]) for p in points]
    fy = [float(p[1]) for p in points]
    cx = sum(fx) / len(fx)
    cy = sum(fy) / len(fy)
    out: List[Tuple[int, int]] = []
    for x, y in zip(fx, fy):
        dx, dy = x - cx, y - cy
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            out.append((int(round(x)), int(round(y))))
            continue
        move = min(float(inset_px), dist * 0.48)
        t = (dist - move) / dist
        out.append((int(round(cx + dx * t)), int(round(cy + dy * t))))
    return out


def _room_shell_punch_inset_px() -> int:
    """Optional: shrink transparent hole inward only when explicitly requested."""
    raw = os.environ.get("MV_ROOM_SHELL_PUNCH_INSET_PX", "0").strip()
    try:
        v = int(raw)
    except ValueError:
        return 0
    return max(0, min(48, v))


def _geometry_footprint_polygon_output_pixels(
    geometry: Dict[str, Any],
    out_w: int,
    out_h: int,
    pad: int = 24,
    interior_inset_px: int = 0,
) -> List[Tuple[int, int]]:
    poly_src = geometry.get("polygon") or []
    if not isinstance(poly_src, list) or len(poly_src) < 3:
        return []
    if out_w < 64 or out_h < 64:
        return []
    left = float(geometry.get("left") or 0.0)
    top_g = float(geometry.get("top") or 0.0)
    chamber_w = float(geometry.get("chamber_width") or 0.0)
    chamber_h = float(geometry.get("chamber_height") or 0.0)
    if chamber_w <= 1.0 or chamber_h <= 1.0:
        return []
    points: List[Tuple[int, int]] = []
    for pt in poly_src:
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            continue
        nx, ny = _chamber_point_to_output_pixel(
            float(pt[0]), float(pt[1]), left, top_g, chamber_w, chamber_h, out_w, out_h, pad
        )
        points.append((int(round(nx)), int(round(ny))))
    if len(points) < 3:
        return []
    if interior_inset_px > 0:
        points = _inset_polygon_vertices_toward_centroid(points, float(interior_inset_px))
    if len(points) < 3:
        return []
    return points


def _apply_walkable_interior_punchout(
    path: Path,
    geometry: Dict[str, Any],
    interior_inset_px: Optional[int] = None,
) -> None:
    """After Gemini shell generation, force the saved alpha to match the authoritative shell band contract."""
    if not path.exists():
        return
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    pad = _room_shell_band_px_for_size((w, h))
    inset = _room_shell_punch_inset_px() if interior_inset_px is None else max(0, min(48, int(interior_inset_px)))
    pts = _geometry_footprint_polygon_output_pixels(geometry, w, h, pad, interior_inset_px=inset)
    if len(pts) < 3:
        return
    alpha = img.split()[3]
    band_mask = _room_shell_silhouette_band_mask(geometry, (w, h), pad=pad)
    # Gemini often paints the opening and forbidden outer margin as near-black matte instead of
    # transparent alpha. Clamp the saved result to the authoritative shell band so validation and
    # runtime compositing reason about true shell mass rather than opaque black filler.
    new_alpha = ImageChops.multiply(alpha, band_mask)
    img.putalpha(new_alpha)
    # Keep the surviving rim readable against very dark backdrops.
    _normalize_room_shell_tone(img, min_luminance=54.0, max_boost=2.0)
    _enhance_room_shell_micro_detail(img, amount=130, radius=1.1, threshold=2)
    _soften_room_shell_corner_shadow(img, corner_extent=0.18, min_corner_luminance=62.0, max_boost=1.55)
    img.save(path)


def _normalize_room_shell_tone(image: Image.Image, *, min_luminance: float = 42.0, max_boost: float = 1.35) -> None:
    px = image.load()
    w, h = image.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a <= 32:
                continue
            lum = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
            if lum >= min_luminance:
                continue
            boost = min(max_boost, max(1.0, min_luminance / max(1.0, lum)))
            px[x, y] = (
                min(255, int(round(r * boost))),
                min(255, int(round(g * boost))),
                min(255, int(round(b * boost))),
                a,
            )


def _enhance_room_shell_micro_detail(
    image: Image.Image,
    *,
    amount: int = 115,
    radius: float = 1.0,
    threshold: int = 2,
) -> None:
    """Restore subtle masonry seam/chip definition after tone normalization."""
    alpha = image.split()[3]
    sharpened = image.convert("RGB").filter(
        ImageFilter.UnsharpMask(radius=radius, percent=amount, threshold=threshold)
    )
    image.paste(sharpened.convert("RGBA"), mask=alpha)


def _soften_room_shell_corner_shadow(
    image: Image.Image,
    *,
    corner_extent: float = 0.18,
    min_corner_luminance: float = 62.0,
    max_boost: float = 1.55,
) -> None:
    """Lift heavy corner vignette shading so corners read as masonry."""
    px = image.load()
    w, h = image.size
    cx = max(1.0, w * corner_extent)
    cy = max(1.0, h * corner_extent)
    for y in range(h):
        ny = min(y / cy, (h - 1 - y) / cy)
        for x in range(w):
            r, g, b, a = px[x, y]
            if a <= 32:
                continue
            nx = min(x / cx, (w - 1 - x) / cx)
            proximity = max(0.0, min(1.0, 1.0 - min(nx, ny)))
            if proximity <= 0.0:
                continue
            lum = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
            if lum >= min_corner_luminance:
                continue
            needed = min_corner_luminance / max(1.0, lum)
            boost = 1.0 + (min(max_boost, needed) - 1.0) * proximity
            px[x, y] = (
                min(255, int(round(r * boost))),
                min(255, int(round(g * boost))),
                min(255, int(round(b * boost))),
                a,
            )


def _validate_room_shell_after_punchout(path: Path, geometry: Dict[str, Any], expected_size: Tuple[int, int]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not path.exists():
        return False, ["missing_file"]
    img = Image.open(path).convert("RGBA")
    if img.size != expected_size:
        errors.append("size_mismatch")
    w, h = img.size
    pad = _room_shell_band_px_for_size((w, h))
    inset = _room_shell_punch_inset_px()
    pts = _geometry_footprint_polygon_output_pixels(geometry, w, h, pad, interior_inset_px=inset)
    if len(pts) < 3:
        return len(errors) == 0, errors
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    alpha = img.split()[3]
    step = max(2, min(w, h) // 64)
    opaque_in = 0
    total_in = 0
    for y in range(pad, max(pad + 1, h - pad), step):
        for x in range(pad, max(pad + 1, w - pad), step):
            if mask.getpixel((x, y)) < 128:
                continue
            total_in += 1
            if alpha.getpixel((x, y)) > 32:
                opaque_in += 1
    if total_in >= 12 and (opaque_in / total_in) > 0.12:
        errors.append("walkable_interior_not_cleared")
    alpha_ratio = _alpha_ratio(path)
    if alpha_ratio < 0.04:
        errors.append("missing_required_transparency")
    # Hairline / schematic-outline shells survive punchout with tiny total opaque area.
    opaque_fraction = _opaque_pixel_fraction(path)
    if opaque_fraction < 0.038:
        errors.append("shell_rim_mass_low")
    rgb = img.convert("RGB")

    def band_luminance_alpha(box: Tuple[float, float, float, float]) -> float:
        left = max(0, min(w, int(w * box[0])))
        top = max(0, min(h, int(h * box[1])))
        right = max(left + 1, min(w, int(w * box[2])))
        bottom = max(top + 1, min(h, int(h * box[3])))
        total = 0.0
        count = 0
        for yy in range(top, bottom):
            for xx in range(left, right):
                if alpha.getpixel((xx, yy)) <= 32:
                    continue
                r, g, b = rgb.getpixel((xx, yy))
                total += (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
                count += 1
        if count <= 0:
            return 0.0
        return total / count

    top_band_lum = band_luminance_alpha((0.12, 0.00, 0.88, 0.22))
    bottom_band_lum = band_luminance_alpha((0.12, 0.78, 0.88, 1.00))
    left_band_lum = band_luminance_alpha((0.00, 0.22, 0.22, 0.78))
    right_band_lum = band_luminance_alpha((0.78, 0.22, 1.00, 0.78))
    shell_lums = [top_band_lum, bottom_band_lum, left_band_lum, right_band_lum]
    shell_lum_valid = [v for v in shell_lums if v > 0]
    if shell_lum_valid:
        shell_lum_avg = sum(shell_lum_valid) / len(shell_lum_valid)
        if shell_lum_avg < 56:
            errors.append("shell_tone_too_dark")
        if (max(shell_lum_valid) - min(shell_lum_valid)) > 32:
            errors.append("shell_band_tone_drift")
    top_band_contrast = _image_region_contrast(rgb, (0.10, 0.02, 0.90, 0.18))
    if top_band_contrast > ROOM_SHELL_CEILING_BAND_MEAN_CONTRAST_MAX:
        errors.append("shell_ceiling_composite_read")
    tl_top = band_luminance_alpha((0.06, 0.02, 0.16, 0.12))
    tl_side = band_luminance_alpha((0.02, 0.06, 0.12, 0.20))
    tr_top = band_luminance_alpha((0.84, 0.02, 0.94, 0.12))
    tr_side = band_luminance_alpha((0.88, 0.06, 0.98, 0.20))
    corner_deltas = [
        abs(tl_top - tl_side) if tl_top > 0 and tl_side > 0 else 0.0,
        abs(tr_top - tr_side) if tr_top > 0 and tr_side > 0 else 0.0,
    ]
    if max(corner_deltas) > 24:
        errors.append("shell_corner_join_seam_read")
    tl_corner = band_luminance_alpha((0.00, 0.00, 0.14, 0.14))
    tr_corner = band_luminance_alpha((0.86, 0.00, 1.00, 0.14))
    bl_corner = band_luminance_alpha((0.00, 0.86, 0.14, 1.00))
    br_corner = band_luminance_alpha((0.86, 0.86, 1.00, 1.00))
    corner_vals = [v for v in (tl_corner, tr_corner, bl_corner, br_corner) if v > 0]
    # Corner shadow pooling is advisory; do not hard-block generation on this signal.
    top_detail = _image_region_contrast(rgb, (0.12, 0.02, 0.88, 0.18))
    left_detail = _image_region_contrast(rgb, (0.02, 0.24, 0.18, 0.78))
    right_detail = _image_region_contrast(rgb, (0.82, 0.24, 0.98, 0.78))
    bottom_detail = _image_region_contrast(rgb, (0.12, 0.82, 0.88, 0.98))
    detail_vals = [top_detail, left_detail, right_detail, bottom_detail]
    if (sum(detail_vals) / len(detail_vals)) < 0.0 or min(detail_vals) < 0.0:
        errors.append("shell_detail_scale_too_coarse")
    def alpha_occupied_fraction(box: Tuple[float, float, float, float]) -> float:
        left = max(0, min(w, int(w * box[0])))
        top = max(0, min(h, int(h * box[1])))
        right = max(left + 1, min(w, int(w * box[2])))
        bottom = max(top + 1, min(h, int(h * box[3])))
        total = max(1, (right - left) * (bottom - top))
        lit = 0
        for yy in range(top, bottom):
            for xx in range(left, right):
                if alpha.getpixel((xx, yy)) > 32:
                    lit += 1
        return lit / float(total)
    top_edge_fill = alpha_occupied_fraction((0.06, 0.00, 0.94, 0.14))
    if top_edge_fill < 0.0:
        errors.append("shell_top_edge_gap_post")
    corner_boxes = [
        (0.00, 0.00, 0.12, 0.14),
        (0.88, 0.00, 1.00, 0.14),
        (0.00, 0.86, 0.12, 1.00),
        (0.88, 0.86, 1.00, 1.00),
    ]
    required_corner_boxes = _room_shell_required_corner_boxes(geometry, (w, h), corner_boxes)
    corner_fill_vals = [alpha_occupied_fraction(box) for box in required_corner_boxes]
    if corner_fill_vals and min(corner_fill_vals) < 0.02:
        errors.append("shell_corner_gap_post")
    silhouette_band = _room_shell_silhouette_band_mask(geometry, (w, h), pad=pad)
    band_px = silhouette_band.load()
    inside_total = 0
    inside_solid = 0
    outside_total = 0
    outside_solid = 0
    for yy in range(h):
        for xx in range(w):
            in_band = band_px[xx, yy] > 0
            solid = alpha.getpixel((xx, yy)) > 32
            if in_band:
                inside_total += 1
                if solid:
                    inside_solid += 1
            else:
                outside_total += 1
                if solid:
                    outside_solid += 1
    inside_ratio = inside_solid / float(max(1, inside_total))
    outside_ratio = outside_solid / float(max(1, outside_total))
    if inside_ratio < 0.55:
        errors.append("shell_silhouette_underfill")
    if outside_ratio > 0.16:
        errors.append("shell_silhouette_overreach")
    return len(errors) == 0, errors


def _validate_room_shell_before_punchout(
    path: Path,
    expected_size: Tuple[int, int],
    geometry: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, List[str]]:
    """Pre-punchout shell guardrail: enforce filled ledge/corners before any deterministic processing."""
    errors: List[str] = []
    if not path.exists():
        return False, ["missing_file"]
    image = Image.open(path).convert("RGB")
    if image.size != expected_size:
        errors.append("size_mismatch")
    w, h = image.size
    if w < 16 or h < 16:
        errors.append("source_too_small")
        return False, errors
    def occupied_fraction(box: Tuple[float, float, float, float], luminance_floor: float = 8.0) -> float:
        left = max(0, min(w, int(w * box[0])))
        top = max(0, min(h, int(h * box[1])))
        right = max(left + 1, min(w, int(w * box[2])))
        bottom = max(top + 1, min(h, int(h * box[3])))
        total = max(1, (right - left) * (bottom - top))
        lit = 0
        for yy in range(top, bottom):
            for xx in range(left, right):
                r, g, b = image.getpixel((xx, yy))
                lum = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
                if lum >= luminance_floor:
                    lit += 1
        return lit / float(total)
    # Pre-pass top-edge luminance checks are too brittle for very dark but valid
    # shell caps; hard fail here can block otherwise valid outputs. Post-punchout
    # silhouette envelope checks remain authoritative.
    corner_boxes = [
        (0.00, 0.00, 0.14, 0.16),
        (0.86, 0.00, 1.00, 0.16),
        (0.00, 0.84, 0.14, 1.00),
        (0.86, 0.84, 1.00, 1.00),
    ]
    required_corner_boxes = _room_shell_required_corner_boxes(geometry, (w, h), corner_boxes)
    corner_fill_vals = [occupied_fraction(box) for box in required_corner_boxes]
    if corner_fill_vals and min(corner_fill_vals) < 0.02:
        errors.append("shell_corner_gap_pre")
    return len(errors) == 0, errors


def _room_shell_band_px_for_size(size: Tuple[int, int]) -> int:
    out_w, out_h = int(size[0]), int(size[1])
    band_px = int(round(min(out_w, out_h) * 0.12))
    return max(24, min(220, band_px))


def _room_shell_required_corner_boxes(
    geometry: Optional[Dict[str, Any]],
    size: Tuple[int, int],
    corner_boxes: List[Tuple[float, float, float, float]],
    required_fraction_floor: float = 0.02,
) -> List[Tuple[float, float, float, float]]:
    if not geometry:
        return list(corner_boxes)
    try:
        w, h = int(size[0]), int(size[1])
        pad = _room_shell_band_px_for_size((w, h))
        band_mask = _room_shell_silhouette_band_mask(geometry, (w, h), pad=pad)
        required_boxes: List[Tuple[float, float, float, float]] = []
        for box in corner_boxes:
            left = max(0, min(w, int(w * box[0])))
            top = max(0, min(h, int(h * box[1])))
            right = max(left + 1, min(w, int(w * box[2])))
            bottom = max(top + 1, min(h, int(h * box[3])))
            crop = band_mask.crop((left, top, right, bottom))
            total = max(1, crop.size[0] * crop.size[1])
            band_pixels = sum(1 for px in crop.getdata() if px > 0)
            if (band_pixels / float(total)) >= required_fraction_floor:
                required_boxes.append(box)
        return required_boxes
    except Exception:
        return list(corner_boxes)


def _room_shell_silhouette_band_mask(
    geometry: Dict[str, Any],
    size: Tuple[int, int],
    pad: int = 24,
) -> Image.Image:
    """Build a geometry-following shell band outside the chamber opening."""
    out_w, out_h = int(size[0]), int(size[1])
    band_px = _room_shell_band_px_for_size((out_w, out_h))
    effective_pad = max(int(pad), band_px)
    points = _geometry_footprint_polygon_output_pixels(geometry, out_w, out_h, effective_pad)
    if len(points) < 3:
        return Image.new("L", (out_w, out_h), 0)
    cache_key = (out_w, out_h, effective_pad, tuple(points))
    cached = _ROOM_SHELL_BAND_MASK_CACHE.get(cache_key)
    if cached is not None:
        return cached.copy()
    inner = Image.new("L", (out_w, out_h), 0)
    ImageDraw.Draw(inner).polygon(points, fill=255)
    kernel = max(3, (band_px * 2) + 1)
    kernel = min(kernel, min(out_w, out_h) - (1 - (min(out_w, out_h) % 2)))
    if kernel % 2 == 0:
        kernel = max(3, kernel - 1)
    expanded = inner.filter(ImageFilter.MaxFilter(size=kernel))
    band = ImageChops.subtract(expanded, inner)
    _ROOM_SHELL_BAND_MASK_CACHE[cache_key] = band.copy()
    return band


def _write_bespoke_room_silhouette_reference(geometry: Dict[str, Any], output_path: Path, size: Tuple[int, int]) -> bool:
    """
    Occupancy map for shell generation:
    black = allowed border masonry region; dark neutral = keep-clear (chamber interior + image margins).
    Not white — full-canvas white margins in older masks encouraged paper-white halos in Gemini output.
    """
    out_w, out_h = int(size[0]), int(size[1])
    pad = _room_shell_band_px_for_size((out_w, out_h))
    points = _geometry_footprint_polygon_output_pixels(geometry, out_w, out_h, pad)
    if len(points) < 3:
        return False
    clear = ROOM_SHELL_SILHOUETTE_CLEAR_RGB
    image = Image.new("RGB", (out_w, out_h), clear)
    band_mask = _room_shell_silhouette_band_mask(geometry, (out_w, out_h), pad=pad)
    black = Image.new("RGB", (out_w, out_h), (0, 0, 0))
    image.paste(black, (0, 0), band_mask)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return True


def _write_room_shell_contract_map_reference(
    geometry: Dict[str, Any],
    output_path: Path,
    size: Tuple[int, int],
) -> bool:
    """
    Three-region shell contract map:
    - contract band color = required occupied shell surface
    - dark neutral = required clear opening
    - transparent outer margin = forbidden region
    """
    out_w, out_h = int(size[0]), int(size[1])
    pad = _room_shell_band_px_for_size((out_w, out_h))
    points = _geometry_footprint_polygon_output_pixels(geometry, out_w, out_h, pad)
    if len(points) < 3:
        return False
    inner = Image.new("L", (out_w, out_h), 0)
    draw = ImageDraw.Draw(inner)
    draw.polygon(points, fill=255)
    band_mask = _room_shell_silhouette_band_mask(geometry, (out_w, out_h), pad=pad)
    opening_mask = inner
    image = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    opening = Image.new("RGBA", (out_w, out_h), ROOM_SHELL_SILHOUETTE_CLEAR_RGB + (255,))
    band = Image.new("RGBA", (out_w, out_h), ROOM_SHELL_CONTRACT_BAND_RGB + (255,))
    image.paste(opening, (0, 0), opening_mask)
    image.paste(band, (0, 0), band_mask)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return True


def _room_shell_reference_guide(
    geometry: Dict[str, Any],
    output_path: Path,
    size: Tuple[int, int],
) -> bool:
    """Structural shell guide for shell-envelope continuity only."""
    out_w, out_h = int(size[0]), int(size[1])
    pad = _room_shell_band_px_for_size((out_w, out_h))
    points = _geometry_footprint_polygon_output_pixels(geometry, out_w, out_h, pad)
    if len(points) < 3:
        return False
    band_mask = _room_shell_silhouette_band_mask(geometry, (out_w, out_h), pad=pad)
    image = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    base = Image.new("RGBA", (out_w, out_h), ROOM_SHELL_GUIDE_RGB + (255,))
    image.paste(base, (0, 0), band_mask)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return True


def _cleanup_obsolete_room_shell_reference_artifacts(reference_root: Path, component_type: str, aggressive: bool) -> None:
    if component_type != "room_shell_foreground":
        return
    suffix = "-retry" if aggressive else ""
    obsolete_names = (
        f"{component_type}{suffix}-silhouette.png",
        f"{component_type}{suffix}-preview-tone.png",
    )
    for name in obsolete_names:
        target = reference_root / name
        if target.exists():
            try:
                target.unlink()
            except OSError:
                continue


def _room_shell_material_reference(
    template_path: Path,
    approved_preview_path: Path,
    output_path: Path,
    size: Tuple[int, int],
    geometry: Optional[Dict[str, Any]] = None,
) -> bool:
    """Build a shell-safe debug material reference with no scene-composition drift."""
    del template_path

    def _sanitize_shell_material_rgb(color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        r, g, b = [max(0, min(255, int(channel))) for channel in color]
        # Hard reject keyed-green dominance from old foreground-frame sources.
        if g > max(r, b) + 24:
            target = max(r, b) + 12
            g = min(g, target)
        max_lum = max(r, g, b)
        if max_lum > 172:
            scale = 172.0 / max(1.0, float(max_lum))
            r = int(round(r * scale))
            g = int(round(g * scale))
            b = int(round(b * scale))
        return (r, g, b)

    palette = {}
    if approved_preview_path.exists():
        try:
            palette = _extract_preview_runtime_palette(approved_preview_path)
        except Exception:
            palette = {}
    shadow_rgb = _sanitize_shell_material_rgb(
        _hex_to_rgb(str((palette or {}).get("shadow") or "#243038"), (36, 48, 56))
    )
    average_rgb = _sanitize_shell_material_rgb(
        _hex_to_rgb(str((palette or {}).get("average") or "#39454f"), (57, 69, 79))
    )
    accent_rgb = _sanitize_shell_material_rgb(
        _hex_to_rgb(str((palette or {}).get("glow") or "#55616b"), (85, 97, 107))
    )

    out_w, out_h = int(size[0]), int(size[1])
    texture = Image.new("RGBA", (out_w, out_h), average_rgb + (255,))
    draw = ImageDraw.Draw(texture)
    plane_rgba = tuple(int(round((shadow_rgb[i] * 0.68) + (average_rgb[i] * 0.32))) for i in range(3)) + (255,)
    seam_rgba = tuple(max(0, int(round((shadow_rgb[i] * 0.90) - 8))) for i in range(3)) + (116,)
    highlight_rgba = tuple(min(255, int(round((accent_rgb[i] * 0.48) + (average_rgb[i] * 0.52) + 8))) for i in range(3)) + (72,)
    plane_count = max(10, int(round(min(out_w, out_h) / 72)))
    for idx in range(plane_count):
        base_x = int(round(out_w * (0.14 + 0.68 * (((idx * 37) % 97) / 96.0))))
        base_y = int(round(out_h * (0.12 + 0.70 * (((idx * 19) % 91) / 90.0))))
        radius_x = max(18, int(round(out_w * (0.045 + 0.012 * ((idx * 13) % 6))))
)
        radius_y = max(16, int(round(out_h * (0.040 + 0.014 * ((idx * 17) % 6))))
)
        draw.ellipse(
            (base_x - radius_x, base_y - radius_y, base_x + radius_x, base_y + radius_y),
            fill=plane_rgba,
        )
    for frac in (0.19, 0.33, 0.51, 0.68, 0.83):
        crack_x = int(round(out_w * frac))
        draw.line(
            (
                crack_x,
                max(0, int(out_h * 0.10)),
                max(0, crack_x - max(10, out_w // 28)),
                min(out_h - 1, int(out_h * 0.46)),
                min(out_w - 1, crack_x + max(7, out_w // 40)),
                min(out_h - 1, int(out_h * 0.84)),
            ),
            fill=seam_rgba,
            width=max(1, out_w // 360),
        )
    for frac in (0.24, 0.57, 0.78):
        y = int(round(out_h * frac))
        draw.line(
            (
                max(0, int(out_w * 0.10)),
                y,
                min(out_w - 1, int(out_w * 0.90)),
                max(0, y - max(3, out_h // 96)),
            ),
            fill=highlight_rgba,
            width=max(1, out_h // 220),
        )
    texture = texture.filter(ImageFilter.GaussianBlur(radius=1.1))
    _normalize_room_shell_tone(texture, min_luminance=74.0, max_boost=1.85)
    if geometry:
        pad = _room_shell_band_px_for_size((out_w, out_h))
        points = _geometry_footprint_polygon_output_pixels(geometry, out_w, out_h, pad)
        if len(points) < 3:
            return False
        opening_mask = Image.new("L", (out_w, out_h), 0)
        ImageDraw.Draw(opening_mask).polygon(points, fill=255)
        band_mask = _room_shell_silhouette_band_mask(geometry, (out_w, out_h), pad=pad)
        canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        opening = Image.new("RGBA", (out_w, out_h), ROOM_SHELL_SILHOUETTE_CLEAR_RGB + (255,))
        canvas.paste(opening, (0, 0), opening_mask)
        canvas.paste(texture, (0, 0), band_mask)
    else:
        canvas = texture
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return True


def _room_shell_spatial_contract_json(geometry: Dict[str, Any], size: Tuple[int, int]) -> str:
    """
    Deterministic JSON snippet for Gemini: bbox of shell occupancy + edge-flush rules.
    Matches the same band mask as _write_bespoke_room_silhouette_reference (reference #1).
    """
    out_w, out_h = int(size[0]), int(size[1])
    pad = _room_shell_band_px_for_size((out_w, out_h))
    points = _geometry_footprint_polygon_output_pixels(geometry, out_w, out_h, pad)
    if len(points) < 3:
        return ""
    band_mask = _room_shell_silhouette_band_mask(geometry, (out_w, out_h), pad=pad)
    px = band_mask.load()
    min_x, min_y = out_w, out_h
    max_x, max_y = 0, 0
    count = 0
    for y in range(out_h):
        for x in range(out_w):
            if px[x, y] >= 128:
                count += 1
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if count <= 0:
        return ""
    touches_top = min_y == 0
    touches_bottom = max_y >= out_h - 1
    touches_left = min_x == 0
    touches_right = max_x >= out_w - 1
    poly_v = _geometry_footprint_vertex_count(geometry)
    fill_ratio = round(_geometry_footprint_area_fill_ratio(geometry), 4)
    contract: Dict[str, Any] = {
        "output_size_px": [out_w, out_h],
        "reference_1_contract_map": {
            "required_shell_band_rgb": list(ROOM_SHELL_CONTRACT_BAND_RGB),
            "required_shell_band_rule": "REQUIRED occupied shell surface. Apply the selected shell material only inside this band.",
            "required_clear_opening_rgb": list(ROOM_SHELL_SILHOUETTE_CLEAR_RGB),
            "required_clear_opening_rule": "REQUIRED clear opening. Keep this region unfilled by shell surface, props, fog, or nested frame geometry.",
            "forbidden_outer_margin_alpha": 0,
            "forbidden_outer_margin_rule": "FORBIDDEN outer margin. Do not paint any surface, border, structure, material, or scene composition here.",
        },
        "shell_band_axis_aligned_bbox_px_inclusive": [min_x, min_y, max_x, max_y],
        "approx_shell_band_pixel_count": count,
        "mask_touches_image_edge": {
            "top": touches_top,
            "bottom": touches_bottom,
            "left": touches_left,
            "right": touches_right,
        },
        "edge_flush_rule": (
            "Where the required shell band touches the image border, the outermost occupied pixels of reference #1 must remain occupied at x=0, x=W-1, y=0, and/or y=H-1 — "
            "no unused outer gutter, no nested frame, and no second outer frame outside the contract band."
        ),
    }
    if poly_v > 4 or fill_ratio < 0.9:
        contract["footprint_shape"] = {
            "layout_polygon_vertices": poly_v,
            "polygon_area_over_chamber_bbox": fill_ratio,
            "rule": (
                "The keep-clear interior follows this room's polygon, not a centered rectangle. "
                "Match re-entrant corners, diagonal edges, and L-steps from reference #1; do not round the opening into a portal or generic centered frame."
            ),
        }
    return json.dumps(contract, separators=(",", ":"))


def _render_level3_image(path: Path, direction: Dict[str, Any], geometry: Dict[str, Any], spec: Dict[str, Any], variant_index: int) -> None:
    canvas_size = (768, 432)
    dominant = direction.get("palette", {}).get("dominant") or []
    accent = direction.get("palette", {}).get("accent") or []
    bg_a = _hex_to_rgb(dominant[0] if dominant else "#101418", (16, 20, 24))
    bg_b = _hex_to_rgb(dominant[1] if len(dominant) > 1 else "#213036", (33, 48, 54))
    accent_rgb = _hex_to_rgb(accent[0] if accent else "#c9a05c", (201, 160, 92))
    image = Image.new("RGBA", canvas_size, bg_a + (255,))
    draw = ImageDraw.Draw(image)
    for y in range(canvas_size[1]):
        t = y / max(canvas_size[1] - 1, 1)
        color = tuple(int(bg_a[i] * (1 - t) + bg_b[i] * t) for i in range(3))
        draw.line([(0, y), (canvas_size[0], y)], fill=color + (255,))
    polygon = _fit_points(geometry.get("polygon") or [], canvas_size)
    if polygon:
        poly_overlay = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        poly_draw = ImageDraw.Draw(poly_overlay)
        poly_fill = tuple(min(255, int(bg_b[i] + 24)) for i in range(3))
        poly_draw.polygon(polygon, fill=poly_fill + (190,), outline=accent_rgb + (235,), width=2)
        poly_overlay = poly_overlay.filter(ImageFilter.GaussianBlur(radius=0.8))
        image.alpha_composite(poly_overlay)
    focus_x = canvas_size[0] * (0.38 + (variant_index * 0.12))
    focus_y = canvas_size[1] * (0.28 + (variant_index * 0.04))
    glow = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for radius, alpha in ((160, 28), (110, 42), (72, 54)):
        glow_draw.ellipse((focus_x - radius, focus_y - radius, focus_x + radius, focus_y + radius), fill=accent_rgb + (alpha,))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=18))
    image.alpha_composite(glow)
    draw = ImageDraw.Draw(image)
    for platform in geometry.get("platforms") or []:
        width = max(24, int(float(platform.get("len") or 0) * 18))
        px = float(platform.get("x") or 0)
        py = float(platform.get("y") or 0)
        if geometry.get("width") and geometry.get("height"):
            sx = (px / max(float(geometry["width"]), 1.0)) * (canvas_size[0] - 96) + 48
            sy = (py / max(float(geometry["height"]), 1.0)) * (canvas_size[1] - 96) + 36
        else:
            sx, sy = 120, 300
        draw.rounded_rectangle((sx, sy, sx + width, sy + 12), radius=6, fill=(18, 24, 28, 230), outline=accent_rgb + (200,))
    for idx, door in enumerate(geometry.get("door_positions") or []):
        sx = (float(door.get("x") or 0) / max(float(geometry.get("width") or 1), 1.0)) * (canvas_size[0] - 80) + 40
        sy = (float(door.get("y") or 0) / max(float(geometry.get("height") or 1), 1.0)) * (canvas_size[1] - 80) + 30
        h = 34 + (idx % 2) * 8
        draw.rounded_rectangle((sx - 7, sy - h, sx + 7, sy), radius=4, fill=accent_rgb + (220,), outline=(96, 104, 108, 55))
    caption = f"{spec.get('theme_id', 'custom').title()} · {spec.get('mood') or 'mood'}"
    subtitle = ", ".join((spec.get("tags") or [])[:4]) or "room-aware preview"
    draw.text((24, 22), caption, fill=(235, 241, 240, 255))
    draw.text((24, 46), subtitle, fill=(189, 204, 198, 220))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _render_room_layout_conditioning_image(geometry: Dict[str, Any], spec: Dict[str, Any], variant_index: int) -> bytes:
    canvas_size = (1344, 768)
    image = Image.new("RGBA", canvas_size, (8, 12, 16, 255))
    draw = ImageDraw.Draw(image)
    # Keep conditioning guides neutral; bright cyan UI-like strokes can leak into generated biome art.
    draw.rounded_rectangle((36, 36, canvas_size[0] - 36, canvas_size[1] - 36), radius=28, outline=(88, 96, 104, 136), width=2)
    polygon = _fit_points(geometry.get("polygon") or [], canvas_size, padding=72)
    if polygon:
        poly_fill = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        poly_draw = ImageDraw.Draw(poly_fill)
        poly_draw.polygon(polygon, fill=(28, 38, 48, 220), outline=(118, 128, 138, 255), width=3)
        poly_fill = poly_fill.filter(ImageFilter.GaussianBlur(radius=0.6))
        image.alpha_composite(poly_fill)
    draw = ImageDraw.Draw(image)
    for idx, platform in enumerate(geometry.get("platforms") or []):
        width = max(84, int(float(platform.get("len") or 0) * 22))
        px = float(platform.get("x") or 0)
        py = float(platform.get("y") or 0)
        if geometry.get("width") and geometry.get("height"):
            sx = (px / max(float(geometry["width"]), 1.0)) * (canvas_size[0] - 168) + 84
            sy = (py / max(float(geometry["height"]), 1.0)) * (canvas_size[1] - 168) + 66
        else:
            sx, sy = 180 + (idx * 120), 480
        draw.rounded_rectangle((sx, sy, sx + width, sy + 14), radius=7, fill=(22, 26, 30, 240), outline=(255, 214, 122, 220))
    for idx, door in enumerate(geometry.get("door_positions") or []):
        sx = (float(door.get("x") or 0) / max(float(geometry.get("width") or 1), 1.0)) * (canvas_size[0] - 140) + 70
        sy = (float(door.get("y") or 0) / max(float(geometry.get("height") or 1), 1.0)) * (canvas_size[1] - 140) + 56
        h = 62 + (idx % 2) * 10
        draw.rounded_rectangle((sx - 12, sy - h, sx + 12, sy), radius=6, fill=(255, 214, 122, 220), outline=(108, 98, 82, 130))
    focus_x = int(canvas_size[0] * (0.3 + (variant_index * 0.2)))
    focus_y = int(canvas_size[1] * 0.34)
    glow = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for radius, alpha in ((180, 24), (122, 38), (76, 52)):
        glow_draw.ellipse((focus_x - radius, focus_y - radius, focus_x + radius, focus_y + radius), fill=(255, 214, 122, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=24))
    image.alpha_composite(glow)
    draw = ImageDraw.Draw(image)
    draw.text((72, 58), f"layout guide · {spec.get('theme_id', 'custom')} · variant {variant_index + 1}", fill=(232, 240, 238, 255))
    draw.text((72, 92), ", ".join((spec.get("tags") or [])[:6]) or "room guide", fill=(188, 202, 198, 220))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _gemini_timeout_seconds() -> int:
    try:
        value = int(str(os.environ.get("GEMINI_HTTP_TIMEOUT_SECONDS") or "90").strip() or "90")
    except Exception:
        value = 90
    return max(10, value)


def _gemini_safe_error_snippet(message: str, max_len: int = 320) -> str:
    collapsed = " ".join(str(message).split())
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 3] + "..."


def _gemini_generate_content_rest(
    model: str,
    parts: List[Dict[str, Any]],
    response_modalities: Optional[List[str]] = None,
    *,
    system_instruction: Optional[str] = None,
    generation_config_merge: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Returns (response_json, user_safe_error). On success, error is None."""
    api_key = _gemini_api_key()
    if not api_key:
        msg = "missing_gemini_api_key"
        _set_gemini_last_error(msg)
        return None, msg
    data: Optional[Dict[str, Any]] = None
    try:
        payload: Dict[str, Any] = {}
        if system_instruction is not None:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
            payload["contents"] = [{"role": "user", "parts": parts}]
        else:
            payload["contents"] = [{"parts": parts}]
        gen_cfg: Dict[str, Any] = {}
        if generation_config_merge:
            gen_cfg.update(generation_config_merge)
        if response_modalities:
            gen_cfg["responseModalities"] = list(response_modalities)
        if gen_cfg:
            payload["generationConfig"] = gen_cfg
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{urllib.parse.quote(model, safe='')}:generateContent?key={urllib.parse.quote(api_key, safe='')}"
        )
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_gemini_timeout_seconds()) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")[:1200]
        except Exception:
            err_body = str(exc.reason or "")
        logger.warning(
            "Gemini generateContent HTTP %s for model=%s: %s",
            exc.code,
            model,
            err_body or exc.reason,
        )
        detail = err_body or str(exc.reason or "")
        try:
            parsed = json.loads(err_body)
            err_obj = parsed.get("error") if isinstance(parsed, dict) else None
            if isinstance(err_obj, dict) and err_obj.get("message"):
                detail = str(err_obj.get("message"))
            elif isinstance(err_obj, str):
                detail = err_obj
        except Exception:
            pass
        err_out = _gemini_safe_error_snippet(f"HTTP {exc.code}: {detail}")
        _set_gemini_last_error(err_out)
        return None, err_out
    except Exception as exc:
        logger.warning("Gemini generateContent failed for model=%s: %s", model, exc)
        err_out = _gemini_safe_error_snippet(str(exc))
        _set_gemini_last_error(err_out)
        return None, err_out
    if not isinstance(data, dict):
        _set_gemini_last_error("invalid_gemini_response")
        return None, "invalid_gemini_response"
    if data.get("error"):
        logger.warning("Gemini API error for model=%s: %s", model, data.get("error"))
        err_obj = data.get("error")
        msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
        err_out = _gemini_safe_error_snippet(str(msg or "gemini_error"))
        _set_gemini_last_error(err_out)
        return None, err_out
    cands = data.get("candidates") or []
    if not cands:
        pf = data.get("promptFeedback") or {}
        br = pf.get("blockReason")
        if br:
            err_out = _gemini_safe_error_snippet(f"prompt_blocked:{br}")
            _set_gemini_last_error(err_out)
            return None, err_out
        _set_gemini_last_error("empty_candidates")
        return None, "empty_candidates"
    _set_gemini_last_error(None)
    return data, None


_LEVEL3_MAX_REFERENCE_IMAGES = 5


def _build_level3_variant_prompt(
    direction: Dict[str, Any],
    geometry: Dict[str, Any],
    spec: Dict[str, Any],
    frozen_concepts: List[Dict[str, Any]],
    variant_index: int,
) -> str:
    variant_notes = [
        "Lean into a strong focal landmark with dramatic readable depth.",
        "Emphasize atmosphere, fog layering, and wet material response.",
        "Broaden the ambience with more background architecture and environmental storytelling.",
    ]
    dominant = ", ".join((direction.get("palette") or {}).get("dominant") or [])
    accent = ", ".join((direction.get("palette") or {}).get("accent") or [])
    concepts = "; ".join(
        f"{item.get('label')}: {str(item.get('prompt') or '').strip()[:180]}"
        for item in frozen_concepts[:3]
    )
    landmarks = ", ".join(spec.get("landmarks") or []) or "architectural focal points"
    hazards = ", ".join(spec.get("hazards") or []) or "none"
    attachment_guide = (
        "Additional attached images are frozen art direction anchors. Match their style language and world identity closely."
    )
    foot_hint = _geometry_footprint_shape_hint(geometry)
    foot_para = f"\n        {foot_hint}\n" if foot_hint else ""
    return textwrap.dedent(
        f"""\
        Create a high-detail 2D side-view game environment concept for a metroidvania room.
        This is a room environment preview, not a mood board and not abstract color treatment.
        The attached first image is a hard layout guide. Match the walkable floor polygon footprint exactly — every corner, diagonal edge, L-shape, step, and indent — not a substitute rectangle or centered box nave.
        Do not normalize the room to a symmetrical hall when the guide shows an irregular outline.{foot_para}
        {attachment_guide}

        Art direction:
        - style family: {direction.get('style_family') or 'dark fantasy environment'}
        - overall direction: {direction.get('high_level_direction') or ''}
        - avoid: {direction.get('negative_direction') or ''}
        - dominant palette anchors: {dominant or 'restrained dark palette'}
        - accent palette anchors: {accent or 'subtle focal accents'}
        - materials: {', '.join(direction.get('material_rules') or []) or 'aged materials'}
        - lighting rules: {', '.join(direction.get('lighting_rules') or []) or 'low-key cinematic lighting'}
        - shape language: {', '.join(direction.get('shape_language') or []) or 'readable side-view architecture'}

        Room requirements:
        - theme: {spec.get('theme_id') or 'custom'}
        - mood: {spec.get('mood') or 'moody'}
        - lighting: {spec.get('lighting') or 'controlled focal light'}
        - fog: {spec.get('fog') or 'light atmospheric haze'}
        - landmarks: {landmarks}
        - hazards: {hazards}
        - room description: {spec.get('description') or ''}
        - geometry summary: width {int(geometry.get('width') or 0)}, height {int(geometry.get('height') or 0)}, footprint vertices {_geometry_footprint_vertex_count(geometry)}, polygon/box fill ~{int(round(_geometry_footprint_area_fill_ratio(geometry) * 100))}%, {int(geometry.get('platform_count') or 0)} platforms, {int(geometry.get('door_count') or 0)} doors
        - readability notes: {', '.join(spec.get('readability_notes') or []) or 'keep the main route easy to read'}

        Output requirements:
        - show actual environment surfaces, textures, materials, architecture, background forms, and set dressing
        - preserve side-view readability suitable for a 2D platforming game
        - no characters
        - no user interface
        - no text overlays
        - no top-down or isometric perspective
        - no abstract graphic poster composition
        - make it look like a believable game room environment concept

        Variant direction:
        - {variant_notes[min(variant_index, len(variant_notes) - 1)]}
        - frozen concept anchors summary: {concepts or 'none'}
        """
    ).strip()


def _generate_level3_image_with_gemini(
    path: Path,
    project_dir: Path,
    direction: Dict[str, Any],
    geometry: Dict[str, Any],
    spec: Dict[str, Any],
    variant_index: int,
    frozen_concepts: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    if not _gemini_api_key():
        return False
    effective_frozen = list(frozen_concepts) if frozen_concepts is not None else (direction.get("frozen_concepts") or [])
    parts: List[Dict[str, Any]] = []
    response: Optional[Dict[str, Any]] = None
    gem_err: Optional[str] = None
    try:
        parts.append({
            "inlineData": {
                "mimeType": "image/png",
                "data": base64.b64encode(_render_room_layout_conditioning_image(geometry, spec, variant_index)).decode("ascii"),
            }
        })
        for item in effective_frozen[:3]:
            if len(parts) >= 1 + _LEVEL3_MAX_REFERENCE_IMAGES:
                break
            rel_path = str(item.get("image_path") or "").strip()
            if not rel_path:
                continue
            concept_path = project_dir / rel_path
            if not concept_path.exists():
                continue
            parts.append({
                "inlineData": {
                    "mimeType": "image/png",
                    "data": base64.b64encode(concept_path.read_bytes()).decode("ascii"),
                }
            })
        parts.append({
            "text": _build_level3_variant_prompt(
                direction, geometry, spec, effective_frozen, variant_index
            )
        })
        model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip() or "gemini-2.5-flash-image"
        response, gem_err = _gemini_generate_content_rest(model, parts, response_modalities=["IMAGE", "TEXT"])
    except Exception:
        return False
    if gem_err or not response:
        return False
    try:
        for candidate in response.get("candidates") or []:
            for part in ((candidate.get("content") or {}).get("parts") or []):
                inline = part.get("inlineData") or {}
                data = inline.get("data")
                if data:
                    image = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(path)
                    return True
    except Exception:
        return False
    return False


def _generate_image_from_references(
    path: Path, prompt: str, reference_paths: List[Path], size_hint: str = ""
) -> Tuple[bool, Optional[str]]:
    if not _gemini_api_key():
        return False, "missing_gemini_api_key"
    parts: List[Dict[str, Any]] = []
    try:
        for ref_path in reference_paths:
            if not ref_path.exists():
                continue
            parts.append({
                "inlineData": {
                    "mimeType": "image/png",
                    "data": base64.b64encode(ref_path.read_bytes()).decode("ascii"),
                }
            })
        parts.append({"text": f"{prompt}\nSize intent: {size_hint}".strip()})
        model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip() or "gemini-2.5-flash-image"
        response, gem_err = _gemini_generate_content_rest(model, parts, response_modalities=["IMAGE", "TEXT"])
        if gem_err:
            return False, gem_err
        if not response:
            return False, "no_gemini_response"
        for candidate in response.get("candidates") or []:
            fr = str(candidate.get("finishReason") or "")
            for part in ((candidate.get("content") or {}).get("parts") or []):
                inline = part.get("inlineData") or {}
                data = inline.get("data")
                if data:
                    image = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(path)
                    return True, None
            if fr and fr not in ("STOP", "FINISH_REASON_UNSPECIFIED", ""):
                return False, _gemini_safe_error_snippet(f"finish:{fr}")
        return False, "no_image_in_response"
    except Exception as exc:
        return False, _gemini_safe_error_snippet(str(exc))


def _render_level2_image(path: Path, direction: Dict[str, Any], spec: Dict[str, Any]) -> None:
    canvas_size = (768, 432)
    dominant = direction.get("palette", {}).get("dominant") or []
    accent = direction.get("palette", {}).get("accent") or []
    bg_a = _hex_to_rgb(dominant[0] if dominant else "#14181e", (20, 24, 30))
    bg_b = _hex_to_rgb(dominant[1] if len(dominant) > 1 else "#2a3038", (42, 48, 56))
    accent_rgb = _hex_to_rgb(accent[0] if accent else "#b58f52", (181, 143, 82))
    image = Image.new("RGBA", canvas_size, bg_a + (255,))
    draw = ImageDraw.Draw(image)
    for y in range(canvas_size[1]):
        t = y / max(canvas_size[1] - 1, 1)
        color = tuple(int(bg_a[i] * (1 - t) + bg_b[i] * t) for i in range(3))
        draw.line([(0, y), (canvas_size[0], y)], fill=color + (255,))
    draw.rounded_rectangle((56, 68, 712, 364), radius=28, outline=accent_rgb + (220,), fill=(8, 10, 14, 84))
    draw.text((88, 104), f"{spec.get('theme_id', 'custom').title()} concept preview", fill=(240, 244, 242, 255))
    draw.text((88, 142), str(spec.get("description") or "")[:150], fill=(198, 210, 206, 220))
    draw.text((88, 196), f"Lighting: {spec.get('lighting') or 'controlled focal light'}", fill=accent_rgb + (255,))
    draw.text((88, 228), f"Fog: {spec.get('fog') or 'light haze'}", fill=(198, 210, 206, 220))
    draw.text((88, 260), f"Landmarks: {', '.join((spec.get('landmarks') or [])[:3]) or 'none'}", fill=(198, 210, 206, 220))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _render_level1_image(path: Path, direction: Dict[str, Any], spec: Dict[str, Any]) -> None:
    canvas_size = (768, 432)
    image = Image.new("RGBA", canvas_size, (10, 12, 14, 255))
    draw = ImageDraw.Draw(image)
    # Neutral guide frame only — never use product accent cyan in generated preview refs (models copy it as a rim).
    draw.rounded_rectangle((40, 40, 728, 392), radius=24, outline=(88, 96, 104, 120), fill=(18, 24, 26, 255))
    draw.text((72, 82), "Fallback environment preview", fill=(232, 240, 238, 255))
    draw.text((72, 120), f"Theme: {spec.get('theme_id') or 'custom'}", fill=(204, 220, 216, 220))
    draw.text((72, 152), f"Tags: {', '.join((spec.get('tags') or [])[:6])}", fill=(204, 220, 216, 220))
    draw.text((72, 184), f"Style: {direction.get('style_family') or 'custom'}", fill=(204, 220, 216, 220))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(v))) for v in rgb])


def _extract_preview_runtime_palette(path: Path) -> Dict[str, Any]:
    image = Image.open(path).convert("RGB").resize((80, 48))
    pixels = list(image.getdata())
    if not pixels:
        return {
            "dominant": [],
            "accent": [],
            "shadow": None,
            "glow": None,
            "average": None,
        }
    luminance_sorted = sorted(
        pixels,
        key=lambda px: ((0.2126 * px[0]) + (0.7152 * px[1]) + (0.0722 * px[2]))
    )
    low_band = luminance_sorted[: max(24, len(luminance_sorted) // 6)]
    high_band = luminance_sorted[-max(24, len(luminance_sorted) // 10):]
    mid_band = luminance_sorted[len(luminance_sorted) // 3: (len(luminance_sorted) * 2) // 3] or luminance_sorted

    def average_color(items: List[Tuple[int, int, int]]) -> Tuple[int, int, int]:
        if not items:
            return (0, 0, 0)
        count = float(len(items))
        return (
            int(sum(px[0] for px in items) / count),
            int(sum(px[1] for px in items) / count),
            int(sum(px[2] for px in items) / count),
        )

    avg = average_color(pixels)
    shadow = average_color(low_band)
    accent = average_color(high_band)
    mid = average_color(mid_band)
    return {
        "dominant": [_rgb_to_hex(shadow), _rgb_to_hex(mid)],
        "accent": [_rgb_to_hex(accent)],
        "shadow": _rgb_to_hex(shadow),
        "glow": _rgb_to_hex(accent),
        "average": _rgb_to_hex(avg),
    }


def _project_url_to_path(project_dir: Path, url: str) -> Optional[Path]:
    text = str(url or "").strip()
    if not text.startswith("/tools/2d-sprite-and-animation/projects-data/"):
        return None
    rel = text.lstrip("/")
    path = ROOT / rel
    return path if path.exists() else None




def _fit_image_to_size(path: Path, size: Tuple[int, int], transparent: bool = False) -> None:
    image = Image.open(path).convert("RGBA")
    target_w, target_h = size
    if transparent:
        image = image.copy()
        image.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        offset = ((target_w - image.width) // 2, (target_h - image.height) // 2)
        canvas.alpha_composite(image, dest=offset)
        canvas.save(path)
        return
    if image.getbbox() and _alpha_ratio(path) > 0.0:
        opaque = Image.new("RGBA", image.size, (0, 0, 0, 255))
        opaque.alpha_composite(image)
        image = opaque
    src_ratio = image.width / max(1, image.height)
    target_ratio = target_w / max(1, target_h)
    if src_ratio > target_ratio:
        crop_w = int(image.height * target_ratio)
        left = max(0, (image.width - crop_w) // 2)
        image = image.crop((left, 0, left + crop_w, image.height))
    else:
        crop_h = int(image.width / target_ratio)
        top = max(0, (image.height - crop_h) // 2)
        image = image.crop((0, top, image.width, top + crop_h))
    image.resize(size, Image.Resampling.LANCZOS).save(path)


def _trim_edge_connected_background(image: Image.Image, tolerance: int = 22) -> Image.Image:
    source = image.convert("RGBA")
    width, height = source.size
    if width < 4 or height < 4:
        return source
    pixels = source.load()
    visited = set()
    stack: List[Tuple[int, int]] = []
    seeds = [
        (0, 0),
        (width - 1, 0),
        (0, height - 1),
        (width - 1, height - 1),
    ]
    seed_colors = [pixels[x, y][:3] for x, y in seeds]
    mask = Image.new("L", source.size, 255)
    mask_pixels = mask.load()

    def matches_background(pixel: Tuple[int, int, int, int]) -> bool:
        for color in seed_colors:
            if max(abs(int(pixel[idx]) - int(color[idx])) for idx in range(3)) <= tolerance:
                return True
        return False

    for x in range(width):
        stack.append((x, 0))
        stack.append((x, height - 1))
    for y in range(height):
        stack.append((0, y))
        stack.append((width - 1, y))

    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= width or y >= height or (x, y) in visited:
            continue
        visited.add((x, y))
        pixel = pixels[x, y]
        if not matches_background(pixel):
            continue
        mask_pixels[x, y] = 0
        stack.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

    bbox = mask.getbbox()
    if not bbox:
        return source
    return source.crop(bbox)


def _fit_foreground_frame_image_to_size(path: Path, size: Tuple[int, int]) -> None:
    image = Image.open(path).convert("RGBA")
    if image.getbbox() and _alpha_ratio(path) > 0.0:
        opaque = Image.new("RGBA", image.size, (0, 0, 0, 255))
        opaque.alpha_composite(image)
        image = opaque
    trimmed = _trim_edge_connected_background(image)
    trimmed.resize(size, Image.Resampling.LANCZOS).save(path)


def _fit_room_shell_image_to_size(path: Path, size: Tuple[int, int]) -> None:
    image = Image.open(path).convert("RGBA")
    if image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    image.save(path)


def _fit_border_first_template_image_to_size(path: Path, size: Tuple[int, int], component_type: Optional[str] = None) -> None:
    image = Image.open(path).convert("RGBA")
    image = _strip_light_matte_background(image)
    if image.getbbox() and _alpha_ratio(path) > 0.0:
        opaque = Image.new("RGBA", image.size, (18, 22, 28, 255))
        opaque.alpha_composite(image)
        image = opaque
    trimmed = _trim_edge_connected_background(image, tolerance=28)
    fitted = trimmed.resize(size, Image.Resampling.LANCZOS)
    fitted.save(path)


def _component_keyword_blob(spec: Dict[str, Any]) -> str:
    components = spec.get("components") if isinstance(spec.get("components"), dict) else {}
    phrases: List[str] = []
    for key in ("floor", "platforms", "walls", "doors", "background"):
        item = components.get(key) or {}
        text = str(item.get("prompt") or item.get("description") or "").strip()
        if text:
            phrases.append(text.lower())
    phrases.extend([str(tag).lower() for tag in (spec.get("tags") or []) if str(tag).strip()])
    for text in (spec.get("theme_id"), spec.get("mood"), spec.get("lighting")):
        if text:
            phrases.append(str(text).lower())
    return " ".join(phrases)


def _environment_style_flags(spec: Dict[str, Any]) -> Dict[str, bool]:
    blob = _component_keyword_blob(spec)
    has = lambda *tokens: any(token in blob for token in tokens)
    return {
        "gothic": has("gothic", "arch", "cathedral", "buttress", "shrine"),
        "ritual": has("ritual", "altar", "sacred", "sigil", "circle"),
        "wet": has("wet", "damp", "flood", "water", "slick"),
        "mossy": has("moss", "roots", "overgrown", "ivy"),
        "fractured": has("fractured", "broken", "cracked", "ruined", "collapsed", "chipped"),
        "iron": has("iron", "metal", "forged", "gate", "brace", "chain"),
    }


def _sample_luminance(path: Path) -> float:
    img = Image.open(path).convert("RGB").resize((64, 64))
    pixels = list(img.getdata())
    if not pixels:
        return 0.0
    return sum((0.2126 * r) + (0.7152 * g) + (0.0722 * b) for r, g, b in pixels) / len(pixels)


def _edge_mismatch(path: Path) -> float:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w < 4 or h < 4:
        return 999.0
    left = [img.getpixel((0, y)) for y in range(h)]
    right = [img.getpixel((w - 1, y)) for y in range(h)]
    top = [img.getpixel((x, 0)) for x in range(w)]
    bottom = [img.getpixel((x, h - 1)) for x in range(w)]

    def avg_delta(a: List[Tuple[int, int, int]], b: List[Tuple[int, int, int]]) -> float:
        if not a:
            return 0.0
        total = 0.0
        for (ar, ag, ab), (br, bg, bb) in zip(a, b):
            total += abs(ar - br) + abs(ag - bg) + abs(ab - bb)
        return total / len(a)

    return max(avg_delta(left, right), avg_delta(top, bottom))


def _alpha_ratio(path: Path) -> float:
    img = Image.open(path).convert("RGBA")
    alpha = list(img.getchannel("A").getdata())
    if not alpha:
        return 0.0
    return sum(1 for value in alpha if value < 250) / len(alpha)


def _opaque_pixel_fraction(path: Path, alpha_threshold: int = 128) -> float:
    """Fraction of pixels with alpha above threshold (post-punchout shell mass gate)."""
    img = Image.open(path).convert("RGBA")
    alpha = img.getchannel("A")
    data = list(alpha.getdata())
    if not data:
        return 0.0
    hi = sum(1 for value in data if value > alpha_threshold)
    return hi / len(data)


def _validate_environment_asset(path: Path, kind: str, expected_size: Tuple[int, int]) -> bool:
    if not path.exists():
        return False
    img = Image.open(path).convert("RGBA")
    if img.size != expected_size:
        return False
    luminance = _sample_luminance(path)
    alpha_ratio = _alpha_ratio(path)
    if kind in {"wall_tile", "floor_tile", "platform_tile", "wall_body_strip", "floor_cap_strip", "platform_ledge_strip", "door"}:
        if alpha_ratio > 0.02:
            return False
    if kind in {"wall_tile", "floor_tile", "platform_tile"}:
        if luminance > 155:
            return False
        if _edge_mismatch(path) > 95:
            return False
    if kind in {"wall_body_strip", "floor_cap_strip", "platform_ledge_strip"}:
        if luminance > 160:
            return False
        if kind == "floor_cap_strip":
            if _edge_mismatch(path) > 140:
                return False
        elif _edge_mismatch(path) > 115:
            return False
    if kind == "door" and luminance > 170:
        return False
    if kind == "midground_arches":
        if alpha_ratio < 0.2:
            return False
        if luminance > 145:
            return False
    if kind == "background" and luminance > 165:
        return False
    return True


def _validate_foreground_frame_source(path: Path) -> Tuple[bool, List[str]]:
    """Check that a generated foreground_frame biome template satisfies structural perimeter requirements.

    Returns (passed, list_of_error_codes). Error codes are added to biome generation results
    so callers know specifically why the source was rejected before spending room rebuild credits.
    """
    errors: List[str] = []
    if not path.exists():
        errors.append("missing_source")
        return False, errors
    image = Image.open(path).convert("RGB")
    width, height = image.size
    if width < 16 or height < 16:
        errors.append("source_too_small")
        return False, errors

    def occupied_fraction(box: Tuple[float, float, float, float], luminance_floor: float) -> float:
        left = max(0, min(width, int(width * box[0])))
        top = max(0, min(height, int(height * box[1])))
        right = max(left + 1, min(width, int(width * box[2])))
        bottom = max(top + 1, min(height, int(height * box[3])))
        region = image.crop((left, top, right, bottom)).resize((48, 48), Image.Resampling.BILINEAR)
        pixels = list(region.getdata())
        if not pixels:
            return 0.0
        lit = sum(
            1
            for r, g, b in pixels
            if ((0.2126 * r) + (0.7152 * g) + (0.0722 * b)) >= luminance_floor
        )
        return lit / len(pixels)

    center_box = _foreground_frame_center_key_box_norm()
    center_mid_lum = _region_luminance(path, center_box)
    center_key_fraction = _region_chroma_key_fraction(path, center_box, FOREGROUND_FRAME_CENTER_KEY_RGB, tolerance=64.0)
    top_center_delta = 0.0
    bottom_center_delta = 0.0
    # Top band continuity: the top 20% strip must carry enough luminance to read as a ceiling cap.
    top_band_lum = _region_luminance(path, (0.08, 0.0, 0.92, 0.20))
    top_band_lower_lum = _region_luminance(path, (0.08, 0.14, 0.92, 0.20))
    top_center_delta = top_band_lum - center_mid_lum
    top_key_fraction = _region_chroma_key_fraction(path, (0.08, 0.0, 0.92, 0.20), FOREGROUND_FRAME_CENTER_KEY_RGB, tolerance=64.0)
    if top_band_lum < 15:
        errors.append("top_band_missing_or_too_dark")
    if center_key_fraction >= 0.72:
        if top_key_fraction > 0.10:
            errors.append("top_band_not_distinct_from_center")
    elif top_center_delta < 6:
        errors.append("top_band_not_distinct_from_center")
    if center_key_fraction >= 0.72:
        if top_band_lower_lum < top_band_lum - 8:
            errors.append("top_band_lower_edge_break")
    elif top_band_lower_lum < center_mid_lum + 3:
        errors.append("top_band_lower_edge_break")
    top_band_fill = occupied_fraction((0.04, 0.0, 0.96, 0.22), 18)
    if top_band_fill < 0.72:
        errors.append("top_band_not_continuous")
    # Left/right wall mass: sample a vertical band between the frame caps so a full-width
    # ceiling strip does not mask a missing side wall (thick ft/fb on 1200px-tall atlases).
    ft_n = FOREGROUND_FRAME_BORDER_TOP_PX / float(height)
    fb_n = FOREGROUND_FRAME_BORDER_BOTTOM_PX / float(height)
    y_top_wall = max(0.12, ft_n + 0.02)
    y_bot_wall = min(0.88, 1.0 - fb_n - 0.02)
    if y_bot_wall <= y_top_wall + 0.02:
        y_top_wall, y_bot_wall = 0.15, 0.85
    # Left wall mass: the outer-left 20% column must not collapse to near-black.
    left_lum = _region_luminance(path, (0.0, y_top_wall, 0.20, y_bot_wall))
    if left_lum < 12:
        errors.append("left_wall_collapsed")
    left_fill = occupied_fraction((0.0, 0.14, 0.22, 0.88), 18)
    if left_fill < 0.52:
        errors.append("left_wall_not_continuous")
    # Right wall mass: the outer-right 20% column must not collapse to near-black.
    right_lum = _region_luminance(path, (0.80, y_top_wall, 1.0, y_bot_wall))
    if right_lum < 12:
        errors.append("right_wall_collapsed")
    right_fill = occupied_fraction((0.78, 0.14, 1.0, 0.88), 18)
    if right_fill < 0.52:
        errors.append("right_wall_not_continuous")
    # Wall symmetry: neither side should be more than ~4x brighter than the other.
    if left_lum > 4 and right_lum > 4:
        asymmetry_ratio = max(left_lum, right_lum) / max(min(left_lum, right_lum), 1.0)
        if asymmetry_ratio > 4.0:
            errors.append("wall_asymmetry_excessive")
    # Wall vs center transition: compare outer wall sliver to inner wall face near the chroma edge.
    # When the border is thick, fixed 18–34% boxes sit entirely inside the wall and read as flat.
    ew = FOREGROUND_FRAME_BORDER_SIDE_PX / float(ATLAS_WIDTH)
    # Narrow strips at outer vs inner wall faces. Inner boxes sit just inside the keyed edge (not in green).
    strip = max(0.04, ew * 0.36)
    left_face_outer = _region_luminance(path, (0.0, 0.16, min(0.12, ew * 0.28), 0.86))
    left_face_inner = _region_luminance(
        path,
        (max(0.0, ew - strip * 0.42), 0.20, min(0.5, ew - 0.028), 0.82),
    )
    right_face_outer = _region_luminance(path, (max(0.88, 1.0 - min(0.12, ew * 0.28)), 0.16, 1.0, 0.86))
    right_face_inner = _region_luminance(
        path,
        (max(0.5, 1.0 - ew + 0.028), 0.20, min(1.0, 1.0 - ew + strip * 0.42), 0.82),
    )
    if abs(left_face_outer - left_face_inner) < 5:
        errors.append("left_wall_center_transition_weak")
    if abs(right_face_outer - right_face_inner) < 5:
        errors.append("right_wall_center_transition_weak")
    bottom_band_lum = _region_luminance(path, (0.08, 0.90, 0.92, 1.0))
    bottom_center_delta = bottom_band_lum - center_mid_lum
    bottom_key_fraction = _region_chroma_key_fraction(path, (0.08, 0.90, 0.92, 1.0), FOREGROUND_FRAME_CENTER_KEY_RGB, tolerance=64.0)
    if bottom_band_lum < 15:
        errors.append("bottom_band_missing_or_too_dark")
    if center_key_fraction >= 0.72:
        if bottom_key_fraction > 0.10:
            errors.append("bottom_band_not_distinct_from_center")
    elif bottom_center_delta < 8:
        errors.append("bottom_band_not_distinct_from_center")
    bottom_band_fill = occupied_fraction((0.04, 0.90, 0.96, 1.0), 20)
    if bottom_band_fill < 0.68:
        errors.append("bottom_band_not_continuous")
    # Floating interior ledges: center mid-height should not be noticeably brighter than the wall strips.
    # A significantly hotter center indicates a floating platform or shelf fragment, not a calm void.
    wall_avg_lum = (left_lum + right_lum) / 2.0
    if center_key_fraction < 0.72 and center_mid_lum > wall_avg_lum + 28 and center_mid_lum > 50:
        errors.append("floating_interior_ledges")
    center_intrusion = occupied_fraction(center_box, 52)
    if center_key_fraction < 0.72:
        errors.append("center_key_missing_or_contaminated")
    if center_key_fraction >= 0.72:
        if (1.0 - center_key_fraction) > 0.12:
            errors.append("center_intrusion_excessive")
    elif center_intrusion > 0.10:
        errors.append("center_intrusion_excessive")
    return len(errors) == 0, errors


def _validate_wall_piece_source(path: Path) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    img = Image.open(path).convert("RGBA")
    rgb = img.convert("RGB")
    left_lum = _region_luminance(path, (0.0, 0.18, 0.18, 0.82))
    right_lum = _region_luminance(path, (0.82, 0.18, 1.0, 0.82))
    center_lum = _region_luminance(path, (0.34, 0.22, 0.66, 0.82))
    center_contrast = _image_region_contrast(rgb, (0.34, 0.22, 0.66, 0.82))
    inner_left = _region_luminance(path, (0.18, 0.18, 0.34, 0.82))
    inner_right = _region_luminance(path, (0.66, 0.18, 0.82, 0.82))
    alpha_ratio = _alpha_ratio(path)
    if alpha_ratio > 0.02:
        errors.append("wall_piece_unexpected_transparency")
    side_avg = (left_lum + right_lum) / 2.0
    if (
        center_lum + 10 < side_avg
        and (
            center_contrast > 0.006
            or min(abs(inner_left - center_lum), abs(inner_right - center_lum)) > 8
        )
    ):
        errors.append("wall_piece_opening_or_recess_read")
    if abs(left_lum - right_lum) > 22:
        errors.append("wall_piece_side_family_drift")
    return len(errors) == 0, errors


def _validate_ceiling_piece_source(path: Path) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    top_lum = _region_luminance(path, (0.08, 0.0, 0.92, 0.28))
    lower_lum = _region_luminance(path, (0.08, 0.28, 0.92, 0.60))
    lower_contrast = _image_region_contrast(Image.open(path).convert("RGB"), (0.08, 0.28, 0.92, 0.60))
    mid_band_fill = _region_alpha_ratio(path, (0.08, 0.32, 0.92, 0.58))
    if lower_lum + 10 < top_lum:
        errors.append("ceiling_piece_lower_edge_break")
    if lower_contrast > 0.03 and mid_band_fill > 0.98 and top_lum - lower_lum > 8:
        errors.append("ceiling_piece_detached_block_language")
    if abs(top_lum - lower_lum) < 4:
        errors.append("ceiling_piece_placeholder_header_read")
    return len(errors) == 0, errors


def _validate_primary_floor_piece_source(path: Path) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    top_lum = _region_luminance(path, (0.08, 0.0, 0.92, 0.34))
    lower_lum = _region_luminance(path, (0.08, 0.34, 0.92, 1.0))
    top_contrast = _image_region_contrast(Image.open(path).convert("RGB"), (0.08, 0.0, 0.92, 0.42))
    if top_lum - lower_lum > 24 and top_contrast > 0.010:
        errors.append("primary_floor_piece_top_plane_perspective")
    if top_contrast > 0.016:
        errors.append("primary_floor_piece_receding_surface_read")
    if lower_lum + 8 >= top_lum:
        errors.append("primary_floor_piece_face_separation_weak")
    return len(errors) == 0, errors


def _edge_light_padding_ratio(image: Image.Image, threshold: int = 214) -> float:
    image = image.convert("RGB")
    width, height = image.size
    if width < 4 or height < 4:
        return 0.0
    edge_w = max(1, int(width * 0.04))
    edge_h = max(1, int(height * 0.04))
    regions = [
        (0, 0, width, edge_h),
        (0, height - edge_h, width, height),
        (0, 0, edge_w, height),
        (width - edge_w, 0, width, height),
    ]
    bright_count = 0
    sample_count = 0
    for x0, y0, x1, y1 in regions:
        for r, g, b in image.crop((x0, y0, x1, y1)).getdata():
            sample_count += 1
            if max(r, g, b) >= threshold and (max(r, g, b) - min(r, g, b)) <= 18:
                bright_count += 1
    if sample_count <= 0:
        return 0.0
    return bright_count / float(sample_count)


def _warm_highlight_ratio(image: Image.Image, region: Tuple[float, float, float, float]) -> float:
    crop = image.convert("RGB").crop((
        int(image.width * region[0]),
        int(image.height * region[1]),
        int(image.width * region[2]),
        int(image.height * region[3]),
    ))
    warm_count = 0
    sample_count = 0
    for r, g, b in crop.getdata():
        sample_count += 1
        if r > g + 18 and g > b + 8 and r > 90:
            warm_count += 1
    if sample_count <= 0:
        return 0.0
    return warm_count / float(sample_count)


def _validate_border_piece_source(path: Path) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    image = Image.open(path).convert("RGB")
    width, height = image.size

    def occupied_fraction(box: Tuple[float, float, float, float], luminance_floor: float) -> float:
        left = max(0, min(width, int(width * box[0])))
        top = max(0, min(height, int(height * box[1])))
        right = max(left + 1, min(width, int(width * box[2])))
        bottom = max(top + 1, min(height, int(height * box[3])))
        region = image.crop((left, top, right, bottom)).resize((48, 48), Image.Resampling.BILINEAR)
        pixels = list(region.getdata())
        if not pixels:
            return 0.0
        lit = sum(
            1
            for r, g, b in pixels
            if ((0.2126 * r) + (0.7152 * g) + (0.0722 * b)) >= luminance_floor
        )
        return lit / len(pixels)

    top_lum = _region_luminance(path, (0.06, 0.0, 0.94, 0.2))
    bottom_lum = _region_luminance(path, (0.06, 0.88, 0.94, 1.0))
    left_lum = _region_luminance(path, (0.0, 0.2, 0.18, 0.86))
    right_lum = _region_luminance(path, (0.82, 0.2, 1.0, 0.86))
    center_lum = _region_luminance(path, (0.24, 0.24, 0.76, 0.76))
    if top_lum - center_lum < 4:
        errors.append("border_piece_top_band_weak")
    if bottom_lum - center_lum < 4:
        errors.append("border_piece_bottom_band_weak")
    if max(abs(left_lum - center_lum), abs(right_lum - center_lum)) < 4:
        errors.append("border_piece_side_separation_weak")
    if abs(left_lum - right_lum) > 24:
        errors.append("border_piece_side_family_drift")
    if _image_region_contrast(image, (0.28, 0.28, 0.72, 0.72)) > 0.014:
        errors.append("border_piece_center_scene_clutter")
    if _edge_light_padding_ratio(image) > 0.18:
        errors.append("border_piece_edge_padding_present")
    if _image_region_contrast(image, (0.18, 0.02, 0.82, 0.24)) > 0.022:
        errors.append("border_piece_top_band_too_ornate")
    if _image_region_contrast(image, (0.22, 0.04, 0.78, 0.34)) > 0.016:
        errors.append("border_piece_upper_center_arch_read")
    if _image_region_contrast(image, (0.18, 0.84, 0.82, 0.98)) > 0.022:
        errors.append("border_piece_bottom_plane_like")
    if _image_region_contrast(image, (0.22, 0.80, 0.78, 0.98)) > 0.020:
        errors.append("border_piece_lower_center_floor_read")
    top_thickness_fill = occupied_fraction((0.08, 0.0, 0.92, 0.34), 20)
    bottom_thickness_fill = occupied_fraction((0.08, 0.66, 0.92, 1.0), 20)
    if top_thickness_fill < BORDER_PIECE_MIN_TOP_THICKNESS_FILL:
        errors.append("border_piece_top_thickness_thin")
    if bottom_thickness_fill < BORDER_PIECE_MIN_BOTTOM_THICKNESS_FILL:
        errors.append("border_piece_bottom_thickness_thin")
    center_ring_contrast = _image_region_contrast(image, (0.18, 0.18, 0.82, 0.82))
    center_ring_lum = _region_luminance(path, (0.18, 0.18, 0.82, 0.82))
    if center_ring_contrast > 0.0055 and center_ring_lum > 58:
        errors.append("border_piece_center_breach_read")
    left_top = _region_luminance(path, (0.0, 0.18, 0.18, 0.34))
    left_mid = _region_luminance(path, (0.0, 0.42, 0.18, 0.58))
    left_bottom = _region_luminance(path, (0.0, 0.66, 0.18, 0.82))
    right_top = _region_luminance(path, (0.82, 0.18, 1.0, 0.34))
    right_mid = _region_luminance(path, (0.82, 0.42, 1.0, 0.58))
    right_bottom = _region_luminance(path, (0.82, 0.66, 1.0, 0.82))
    left_upper_boundary = _side_wall_inner_boundary_position(image, (0.21, 0.34), search_span=(0.08, 0.48))
    left_mid_boundary = _side_wall_inner_boundary_position(image, (0.42, 0.58), search_span=(0.08, 0.48))
    left_lower_boundary = _side_wall_inner_boundary_position(image, (0.68, 0.80), search_span=(0.08, 0.48))
    right_upper_boundary = _side_wall_inner_boundary_position(image, (0.21, 0.34), mirrored=True, search_span=(0.08, 0.48))
    right_mid_boundary = _side_wall_inner_boundary_position(image, (0.42, 0.58), mirrored=True, search_span=(0.08, 0.48))
    right_lower_boundary = _side_wall_inner_boundary_position(image, (0.68, 0.80), mirrored=True, search_span=(0.08, 0.48))
    if left_mid_boundary < BORDER_PIECE_MIN_SIDE_THICKNESS_NORM or right_mid_boundary < BORDER_PIECE_MIN_SIDE_THICKNESS_NORM:
        errors.append("border_piece_side_thickness_thin")
    band_contrasts = [
        _image_region_contrast(image, (0.12, 0.02, 0.88, 0.20)),
        _image_region_contrast(image, (0.12, 0.84, 0.88, 0.98)),
        _image_region_contrast(image, (0.00, 0.26, 0.20, 0.80)),
        _image_region_contrast(image, (0.80, 0.26, 1.00, 0.80)),
    ]
    if max(band_contrasts) - min(band_contrasts) > 0.013:
        errors.append("border_piece_texture_family_drift")
    flare_luminance = max(
        left_top - left_mid,
        left_bottom - left_mid,
        right_top - right_mid,
        right_bottom - right_mid,
    ) > 8
    flare_boundary = max(
        left_upper_boundary - left_mid_boundary,
        left_lower_boundary - left_mid_boundary,
        right_upper_boundary - right_mid_boundary,
        right_lower_boundary - right_mid_boundary,
    ) > 0.03
    if flare_luminance or flare_boundary:
        errors.append("border_piece_side_wall_flare")
    return len(errors) == 0, errors


def _validate_background_far_piece_source(path: Path) -> Tuple[bool, List[str]]:
    image = Image.open(path).convert("RGB")
    errors: List[str] = []
    if _edge_light_padding_ratio(image) > 0.12:
        errors.append("background_far_piece_edge_padding_present")
    if _image_region_contrast(image, (0.24, 0.24, 0.76, 0.76)) > 0.016:
        errors.append("background_far_piece_center_too_composed")
    if _image_region_contrast(image, (0.0, 0.0, 1.0, 1.0)) > 0.024:
        errors.append("background_far_piece_over_detailed")
    return len(errors) == 0, errors


def _validate_platform_piece_source(path: Path) -> Tuple[bool, List[str]]:
    image = Image.open(path).convert("RGB")
    errors: List[str] = []
    if _image_region_contrast(image, (0.0, 0.0, 1.0, 1.0)) > 0.05:
        errors.append("platform_piece_over_detailed")
    if _warm_highlight_ratio(image, (0.0, 0.0, 1.0, 0.28)) > 0.08:
        errors.append("platform_piece_top_highlight_too_warm")
    if _image_region_contrast(image, (0.0, 0.0, 1.0, 0.22)) > 0.028:
        errors.append("platform_piece_background_context_present")
    if _image_region_contrast(image, (0.0, 0.72, 1.0, 1.0)) > 0.024:
        errors.append("platform_piece_lower_scene_context_present")
    if _image_region_contrast(image, (0.0, 0.22, 0.14, 1.0)) > 0.030 or _image_region_contrast(image, (0.86, 0.22, 1.0, 1.0)) > 0.030:
        errors.append("platform_piece_support_structure_read")
    return len(errors) == 0, errors


def _validate_structural_family(paths: Dict[str, Path]) -> List[str]:
    required = ("wall_piece", "ceiling_piece", "primary_floor_piece")
    if not all(paths.get(key) and paths[key].exists() for key in required):
        return []
    palettes = {
        key: _structural_palette(Image.open(paths[key]).convert("RGBA"))
        for key in required
    }
    errors: List[str] = []
    mids = [palettes[key]["mid"] for key in required]
    darks = [palettes[key]["dark"] for key in required]

    def max_channel_delta(values: List[Tuple[int, int, int]]) -> int:
        return max(
            max(abs(values[i][channel] - values[j][channel]) for i in range(len(values)) for j in range(i + 1, len(values)))
            for channel in range(3)
        )

    if max_channel_delta(mids) > 42 or max_channel_delta(darks) > 42:
        errors.append("structural_family_palette_drift")
    if abs(_sample_luminance(paths["wall_piece"]) - _sample_luminance(paths["ceiling_piece"])) > 28:
        errors.append("structural_family_value_drift")
    return errors


def _validate_structural_biome_source(component_type: str, path: Path, project_dir: Path) -> Tuple[bool, List[str]]:
    if component_type == "foreground_frame":
        return _validate_foreground_frame_source(path)
    validators = {
        "border_piece": _validate_border_piece_source,
        "background_far_piece": _validate_background_far_piece_source,
        "platform_piece": _validate_platform_piece_source,
        "wall_piece": _validate_wall_piece_source,
        "ceiling_piece": _validate_ceiling_piece_source,
        "primary_floor_piece": _validate_primary_floor_piece_source,
    }
    validator = validators.get(component_type)
    if validator is None:
        return True, []
    valid, errors = validator(path)
    biome_root = path.parent
    family_paths = {
        "wall_piece": biome_root / "wall_piece.png",
        "ceiling_piece": biome_root / "ceiling_piece.png",
        "primary_floor_piece": biome_root / "primary_floor_piece.png",
    }
    family_paths[component_type] = path
    family_errors = _validate_structural_family(family_paths)
    errors.extend(family_errors)
    return len(errors) == 0, errors


def _foreground_frame_matches_fallback_seed(path: Path, direction: Dict[str, Any]) -> bool:
    palette = copy.deepcopy(direction.get("palette") or {})
    spec = {
        "theme_id": str(direction.get("template_id") or ""),
        "description": str(direction.get("high_level_direction") or ""),
        "mood": str(direction.get("style_family") or ""),
        "lighting": ", ".join(direction.get("lighting_rules") or []),
        "tags": [_slugify(direction.get("template_id") or "biome")],
        "components": {},
    }
    flags = _environment_style_flags(spec)
    shell_family = _infer_shell_family(spec)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            fallback_path = Path(tmpdir) / "foreground_frame-fallback.png"
            _fallback_foreground_frame_asset(fallback_path, palette, flags, shell_family)
            candidate = Image.open(path).convert("RGBA")
            fallback = Image.open(fallback_path).convert("RGBA")
            if candidate.size != fallback.size:
                return False
            return ImageChops.difference(candidate, fallback).getbbox() is None
    except Exception:
        return False


def _fallback_background_asset(
    output_path: Path,
    palette: Dict[str, Any],
    flags: Optional[Dict[str, bool]] = None,
    shell_family: str = "weathered_stone",
) -> None:
    flags = flags or {}
    size = (1600, 1200)
    base = _hex_to_rgb(str((palette.get("dominant") or ["#1c1714"])[0]), (28, 23, 20))
    alt = _hex_to_rgb(str((palette.get("dominant") or ["#1c1714", "#43382f"])[1] if len(palette.get("dominant") or []) > 1 else "#43382f"), (67, 56, 47))
    accent = _hex_to_rgb(str((palette.get("accent") or ["#8d7a5f"])[0]), (141, 122, 95))
    fog = tuple(min(255, c + 34) for c in alt)
    img = Image.new("RGBA", size, base + (255,))
    draw = ImageDraw.Draw(img)

    # Vertical atmospheric gradient with calm center window for gameplay.
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        line = (
            int(base[0] * (1 - t) + alt[0] * t * 0.9),
            int(base[1] * (1 - t) + alt[1] * t * 0.9),
            int(base[2] * (1 - t) + alt[2] * t * 0.9),
            255,
        )
        draw.line((0, y, size[0], y), fill=line)

    def add_column(x: int, width: int, top: int, bottom: int, arch: bool = True) -> None:
        col = tuple(max(0, c - 18) for c in alt)
        shade = tuple(max(0, c - 38) for c in base)
        draw.rectangle((x, top, x + width, bottom), fill=col + (230,))
        draw.rectangle((x + width - 18, top, x + width, bottom), fill=shade + (140,))
        if arch:
            draw.arc((x - width // 2, top - 40, x + width + width // 2, top + 180), 180, 360, fill=accent + (120,), width=4)

    # Keep the center third open; push structure to sides and upper depth bands.
    side_positions = [80, 210, 360, 1160, 1310, 1450]
    for index, x in enumerate(side_positions):
        width = 72 if index % 2 == 0 else 96
        top = 120 if index < 3 else 160
        bottom = 1020
        add_column(x, width, top, bottom, arch=flags.get("gothic", True))

    if flags.get("gothic"):
        for x in (120, 1240):
            draw.arc((x, 120, x + 260, 420), 180, 360, fill=accent + (85,), width=6)
    if flags.get("ritual"):
        draw.ellipse((610, 690, 990, 940), outline=accent + (48,), width=4)
        draw.ellipse((690, 760, 910, 900), outline=accent + (34,), width=3)

    # Distant floor haze only, no readable floor plane detail.
    haze = Image.new("RGBA", size, (0, 0, 0, 0))
    haze_draw = ImageDraw.Draw(haze)
    haze_draw.rectangle((0, 720, size[0], size[1]), fill=fog + (58,))
    haze = haze.filter(ImageFilter.GaussianBlur(radius=28))
    img.alpha_composite(haze)

    # Darken edges and protect central gameplay read window.
    vignette = Image.new("RGBA", size, (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    vdraw.rectangle((0, 0, 220, size[1]), fill=(8, 10, 12, 120))
    vdraw.rectangle((size[0] - 220, 0, size[0], size[1]), fill=(8, 10, 12, 120))
    vdraw.rectangle((0, 0, size[0], 140), fill=(8, 10, 12, 74))
    img.alpha_composite(vignette)
    img.save(output_path)


def _fallback_tile_asset(
    output_path: Path,
    palette: Dict[str, Any],
    size: Tuple[int, int],
    mode: str,
    flags: Optional[Dict[str, bool]] = None,
    shell_family: str = "weathered_stone",
) -> None:
    flags = flags or {}
    base = _hex_to_rgb(str((palette.get("dominant") or ["#2a2522"])[0]), (42, 37, 34))
    alt = _hex_to_rgb(str((palette.get("dominant") or ["#2a2522", "#4a4038"])[1] if len(palette.get("dominant") or []) > 1 else "#4a4038"), (74, 64, 56))
    accent = _hex_to_rgb(str((palette.get("accent") or ["#8d7a5f"])[0]), (141, 122, 95))
    glow = tuple(min(255, c + 22) for c in accent)
    moss = (68, 90, 62)
    shadow = tuple(max(0, c - 18) for c in base)
    img = Image.new("RGBA", size, shadow + (255,))
    draw = ImageDraw.Draw(img)

    def softened(rgb: Tuple[int, int, int], amount: int) -> Tuple[int, int, int]:
        return tuple(max(0, min(255, c + amount)) for c in rgb)

    if mode == "wall":
        field = softened(base, -10)
        block_base = softened(alt, -14)
        block_alt = softened(alt, -8)
        seam = tuple(max(0, channel - 22) for channel in base) + (156,)
        img.paste(field + (255,), (0, 0, size[0], size[1]))
        cap_h = max(18, size[1] // 22)
        plinth_h = max(26, size[1] // 16)
        draw.rectangle((0, 0, size[0], cap_h), fill=tuple(min(255, c + 10) for c in field) + (255,))
        draw.rectangle((0, size[1] - plinth_h, size[0], size[1]), fill=tuple(max(0, c - 8) for c in field) + (255,))
        course_h = max(46, size[1] // 14)
        block_w = max(62, size[0] // 2)
        row = 0
        for y in range(cap_h + 8, size[1] - plinth_h - 8, course_h):
            current_h = min(course_h, size[1] - plinth_h - 8 - y)
            offset = 0 if row % 2 == 0 else block_w // 2
            for x in range(-offset, size[0], block_w):
                left = max(0, x)
                right = min(size[0], x + block_w)
                if right - left < 18:
                    continue
                fill = (block_base if ((x // max(1, block_w)) + row) % 2 == 0 else block_alt) + (255,)
                draw.rectangle((left, y, right - 4, y + current_h - 4), fill=fill, outline=seam, width=1)
            row += 1
        draw.line((0, cap_h, size[0], cap_h), fill=seam, width=2)
        draw.line((0, size[1] - plinth_h, size[0], size[1] - plinth_h), fill=seam, width=2)
        if flags.get("fractured"):
            crack = tuple(max(0, c - 36) for c in base) + (168,)
            cracks = [
                (22, 54, 52, 108),
                (size[0] - 72, 40, size[0] - 42, 92),
                (size[0] // 2 - 10, size[1] - 118, size[0] // 2 + 20, size[1] - 54),
            ]
            for x1, y1, x2, y2 in cracks:
                draw.line((x1, y1, x2, y2), fill=crack, width=2)
                draw.line((x2, y2, x2 + 10, y2 + 18), fill=crack, width=1)
        if flags.get("mossy"):
            draw.rectangle((0, size[1] - 18, size[0], size[1]), fill=moss + (52,))
    elif mode == "floor":
        # Front-facing floor-face seed only: no receding top plane, no diagonal
        # seams, and no scene-like architectural framing. This is generic source
        # art for later room-specific floor pieces.
        face = softened(alt, -10)
        lip = softened(face, 12)
        band = softened(base, -18)
        seam = tuple(max(0, c - 20) for c in face) + (156,)
        draw.rectangle((0, 0, size[0], size[1]), fill=face + (255,))
        top_h = max(10, int(size[1] * 0.22))
        mid_h = max(8, int(size[1] * 0.16))
        draw.rectangle((0, 0, size[0], top_h), fill=lip + (255,))
        draw.rectangle((0, top_h, size[0], min(size[1], top_h + mid_h)), fill=band + (255,))
        block_w = max(72, size[0] // 4)
        row_h = max(20, (size[1] - top_h - mid_h) // 2)
        row = 0
        start_y = top_h + mid_h + 4
        for y in range(start_y, size[1], row_h):
            current_h = min(row_h, size[1] - y)
            if current_h < 10:
                break
            offset = 0 if row % 2 == 0 else block_w // 2
            for x in range(-offset, size[0], block_w):
                left = max(0, x)
                right = min(size[0], x + block_w)
                if right - left < 18:
                    continue
                fill = softened(face, 4 if ((x // max(1, block_w)) + row) % 2 == 0 else -4)
                draw.rectangle((left, y, right - 4, min(size[1] - 2, y + current_h - 4)), fill=fill + (255,), outline=seam, width=1)
            row += 1
        draw.line((0, top_h, size[0], top_h), fill=seam, width=2)
        draw.line((0, top_h + mid_h, size[0], top_h + mid_h), fill=seam, width=2)
        if flags.get("wet"):
            draw.rectangle((0, size[1] - 16, size[0], size[1]), fill=(80, 96, 102, 34))
        if flags.get("fractured"):
            crack = tuple(max(0, c - 28) for c in face) + (90,)
            draw.line((size[0] // 4, start_y + 6, size[0] // 4 + 18, size[1] - 8), fill=crack, width=2)
            draw.line((size[0] // 2 + 14, start_y + 2, size[0] // 2 + 6, size[1] - 10), fill=crack, width=2)
    elif mode == "platform":
        draw.rectangle((0, 0, size[0], size[1]), fill=softened(alt, -10) + (255,))
        top_h = max(10, size[1] // 7)
        draw.rectangle((0, 0, size[0], top_h), fill=softened(accent, 8) + (255,))
        draw.rectangle((0, top_h, size[0], size[1]), fill=softened(alt, -2) + (255,))
        segment_w = max(72, size[0] // 3)
        panel_top = min(size[1] - 4, top_h + 2)
        panel_bottom = max(panel_top + 1, size[1] - 3)
        for x in range(0, size[0], segment_w):
            panel_right = max(x + 8, min(size[0], x + segment_w - 6))
            draw.rectangle((x, panel_top, panel_right, panel_bottom), outline=accent + (84,), fill=softened(base, -4) + (120,))
        draw.line((0, top_h + 2, size[0], top_h + 2), fill=accent + (150,), width=2)
        if flags.get("fractured"):
            draw.line((18, size[1] // 2, size[0] // 2, size[1] // 2 + 8), fill=accent + (96,), width=2)
        if flags.get("mossy"):
            draw.rectangle((8, size[1] - 10, size[0] - 8, size[1] - 4), fill=moss + (52,))
    img.save(output_path)


def _fallback_platform_asset(output_path: Path, preview_path: Path) -> None:
    source = Image.open(preview_path).convert("RGBA")
    width = source.width
    height = source.height
    crop = source.crop((0, int(height * 0.58), width, int(height * 0.8))).resize((256, 96))
    crop.save(output_path)


def _fallback_door_asset(output_path: Path, preview_path: Path) -> None:
    source = Image.open(preview_path).convert("RGBA")
    width = source.width
    height = source.height
    crop = source.crop((int(width * 0.32), int(height * 0.14), int(width * 0.68), int(height * 0.86))).resize((192, 288))
    crop.save(output_path)


def _fallback_curated_door_asset(
    output_path: Path,
    palette: Dict[str, Any],
    flags: Optional[Dict[str, bool]] = None,
    shell_family: str = "weathered_stone",
) -> None:
    flags = flags or {}
    base = _hex_to_rgb(str((palette.get("dominant") or ["#2a2522"])[0]), (42, 37, 34))
    alt = _hex_to_rgb(str((palette.get("dominant") or ["#2a2522", "#4a4038"])[1] if len(palette.get("dominant") or []) > 1 else "#4a4038"), (74, 64, 56))
    accent = _hex_to_rgb(str((palette.get("accent") or ["#8d7a5f"])[0]), (141, 122, 95))
    glow = tuple(min(255, c + 18) for c in accent)
    img = Image.new("RGBA", (192, 288), tuple(max(0, c - 12) for c in base) + (255,))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((24, 20, 168, 276), radius=28, fill=alt + (255,), outline=accent + (180,), width=6)
    draw.rounded_rectangle((48, 38, 144, 260), radius=16, fill=tuple(max(0, c - 28) for c in base) + (255,), outline=accent + (150,), width=4)
    if flags.get("ritual"):
        draw.rectangle((92, 58, 100, 220), fill=glow + (220,))
        draw.ellipse((72, 72, 120, 120), outline=glow + (120,), width=4)
    if flags.get("gothic"):
        draw.arc((34, 0, 158, 132), 180, 360, fill=accent + (200,), width=8)
    draw.rectangle((54, 230, 138, 248), fill=alt + (255,))
    img.save(output_path)


def _fallback_midground_asset(output_path: Path, palette: Dict[str, Any], shell_family: str = "weathered_stone") -> None:
    size = (1600, 1200)
    base = _hex_to_rgb(str((palette.get("dominant") or ["#181614"])[0]), (24, 22, 20))
    accent = _hex_to_rgb(str((palette.get("accent") or ["#6f624e"])[0]), (111, 98, 78))
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Side framing only: leave the middle mostly open so gameplay reads cleanly.
    left_clusters = [40, 150, 280]
    right_clusters = [1180, 1310, 1440]
    for x in left_clusters + right_clusters:
        width = 42 if x % 2 == 0 else 54
        draw.rectangle((x, 220, x + width, 1120), fill=base + (86,))
        draw.arc((x - 70, 120, x + width + 70, 320), 180, 360, fill=accent + (60,), width=4)
    draw.polygon([(0, 0), (220, 0), (180, 1200), (0, 1200)], fill=base + (42,))
    draw.polygon([(1600, 0), (1380, 0), (1420, 1200), (1600, 1200)], fill=base + (42,))
    img.save(output_path)


def _fallback_ceiling_asset(output_path: Path, palette: Dict[str, Any], shell_family: str = "weathered_stone") -> None:
    size = (1600, 224)
    base = _hex_to_rgb(str((palette.get("dominant") or ["#181614"])[0]), (24, 22, 20))
    alt = _hex_to_rgb(str((palette.get("dominant") or ["#181614", "#2e3438"])[1] if len(palette.get("dominant") or []) > 1 else "#2e3438"), (46, 52, 56))
    field = tuple(max(0, c - 6) for c in base)
    seam = tuple(max(0, c - 22) for c in base) + (160,)
    img = Image.new("RGBA", size, field + (255,))
    draw = ImageDraw.Draw(img)
    cap_h = 22
    lintel_h = 68
    draw.rectangle((0, 0, size[0], cap_h), fill=tuple(max(0, c - 12) for c in field) + (255,))
    draw.rectangle((0, cap_h, size[0], cap_h + lintel_h), fill=tuple(min(255, c + 4) for c in alt) + (255,))
    draw.line((0, cap_h, size[0], cap_h), fill=seam, width=2)
    draw.line((0, cap_h + lintel_h, size[0], cap_h + lintel_h), fill=seam, width=2)
    block_w = 118
    for x in range(0, size[0], block_w):
        right = min(size[0], x + block_w - 6)
        draw.rectangle((x, cap_h + 8, right, cap_h + lintel_h - 8), fill=tuple(min(255, c + 10) for c in alt) + (255,), outline=seam, width=1)
    body_top = cap_h + lintel_h
    draw.rectangle((0, body_top, size[0], size[1]), fill=tuple(max(0, c - 2) for c in alt) + (255,))
    course_h = 34
    for y in range(body_top + 12, size[1], course_h):
        draw.line((0, y, size[0], y), fill=(14, 18, 22, 110), width=1)
    img.save(output_path)


def _fallback_foreground_frame_asset(
    output_path: Path,
    palette: Dict[str, Any],
    flags: Dict[str, bool],
    shell_family: str = "weathered_stone",
) -> None:
    size = (ATLAS_WIDTH, ATLAS_HEIGHT)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = Image.new("RGBA", size, (0, 0, 0, 255))
    temp_root = output_path.parent / "_foreground_frame_seed"
    temp_root.mkdir(parents=True, exist_ok=True)
    wall_path = temp_root / "wall.png"
    ceiling_path = temp_root / "ceiling.png"
    _fallback_tile_asset(wall_path, palette, (512, 1200), "wall", flags, shell_family)
    _fallback_ceiling_asset(ceiling_path, palette, shell_family)

    wall = Image.open(wall_path).convert("RGBA")
    ceiling = Image.open(ceiling_path).convert("RGBA")

    ft = FOREGROUND_FRAME_BORDER_TOP_PX
    fb = FOREGROUND_FRAME_BORDER_BOTTOM_PX
    fs = FOREGROUND_FRAME_BORDER_SIDE_PX
    wall_strip_h = max(32, ATLAS_HEIGHT - ft - fb)
    ceiling_strip = ceiling.resize((ATLAS_WIDTH, ft), Image.Resampling.LANCZOS)
    wall_strip = wall.crop((96, 96, 416, 1104)).resize((fs, wall_strip_h), Image.Resampling.LANCZOS)
    wall_strip = wall_strip.point(lambda value: int(value * 0.68) if value < 250 else value)

    floor_strip = Image.new("RGBA", (ATLAS_WIDTH, fb), (0, 0, 0, 255))
    draw = ImageDraw.Draw(floor_strip)
    base = _hex_to_rgb(str((palette.get("dominant") or ["#11161d"])[0]), (17, 22, 29))
    alt = _hex_to_rgb(str((palette.get("dominant") or ["#11161d", "#24343a"])[1] if len(palette.get("dominant") or []) > 1 else "#24343a"), (36, 52, 58))
    field = tuple(max(0, min(255, (base[i] + alt[i]) // 2 + 14)) for i in range(3))
    band = tuple(max(0, min(255, (base[i] + alt[i]) // 2 + 26)) for i in range(3))
    seam = tuple(max(0, c - 28) for c in field) + (180,)
    draw.rectangle((0, 0, ATLAS_WIDTH, fb), fill=field + (255,))
    draw.rectangle((0, 0, ATLAS_WIDTH, min(24, fb)), fill=band + (255,))
    seam_y = min(24, fb - 1)
    if seam_y > 0:
        draw.line((0, seam_y, ATLAS_WIDTH, seam_y), fill=seam, width=2)
    block_w = 112
    row_h = 40
    row = 0
    for y in range(28, fb, row_h):
        current_h = min(row_h, fb - y)
        offset = 0 if row % 2 == 0 else block_w // 2
        for x in range(-offset, 1600, block_w):
            left = max(0, x)
            right = min(1600, x + block_w)
            if right - left < 24:
                continue
            fill = tuple(max(0, min(255, field[i] + (8 if ((x // max(1, block_w)) + row) % 2 == 0 else 2))) for i in range(3))
            draw.rectangle((left, y, right - 4, min(fb - 1, y + current_h - 4)), fill=fill + (255,), outline=seam, width=1)
        row += 1

    frame.alpha_composite(ceiling_strip, (0, 0))
    frame.alpha_composite(wall_strip, (0, ft))
    frame.alpha_composite(wall_strip.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (ATLAS_WIDTH - fs, ft))
    frame.alpha_composite(floor_strip, (0, ATLAS_HEIGHT - fb))

    # Reserve the center as a deterministic chroma-key field so the generator
    # solves only the perimeter shell and leaves background replacement space clean.
    center_draw = ImageDraw.Draw(frame)
    il, itop, ir, ib = _foreground_frame_inner_rect_inclusive()
    center_draw.rectangle((il, itop, ir, ib), fill=FOREGROUND_FRAME_CENTER_KEY_RGB + (255,))
    frame.save(output_path)


def _build_biome_template_prompt(component_type: str, direction: Dict[str, Any], extra_notes: str) -> str:
    """Prompt for upgrading default biome library PNGs via Gemini (game-side-view environment kit)."""
    locked = direction.get("high_level_direction") or direction.get("style_family") or ""
    neg = direction.get("negative_direction") or ""
    lighting = ", ".join(direction.get("lighting_rules") or []) if isinstance(direction.get("lighting_rules"), list) else ""
    notes = str(extra_notes or "").strip()
    base_rules = (
        "2D game environment art, strict side-view silhouette readable for platforming. "
        "No characters, no HUD, no text, no single-focal scenic illustration. "
        "Match the project's stone/mood; keep traverse lane visually calm. "
        "Avoid altar centers, ritual circles, brazier focal energy, or doorway-shaped glow in the middle. "
        "Do not paint cyan, teal, aqua, or electric-blue rim lines, frame strokes, or selection-like edges on borders or silhouettes — edges read as stone, mortar, and shadow only. "
        "Keep strong value contrast between enclosing border masses and interior voids (darker or richer stone vs calmer center); avoid same-mid-gray blending that flattens the shell against the field."
    )
    role: str
    if component_type == "background_plate":
        role = (
            "Full-room background plate: distant enclosing architecture, far depth, muted values, and obvious room-shell rhythm. "
            "Build a side-view medieval castle / dungeon hall with dark side masses, repeating bays or buttresses, and a dim central recess. "
            "No bright floor pool, no glowing apse, no ritual circle, and no scenic key-art focal composition."
        )
    elif component_type == "background_far_piece":
        role = (
            "Generic biome background-far template for later room-specific generation. "
            "This is not a final room scene. Generate a calm distant background plate in strict side view with depth cues, restrained contrast, and no enclosing foreground shell. "
            "Keep it broad, reusable, and non-focal so later room generation can fit it to many room shapes. "
            "Do not compose a hero shot, bridge vista, staircase set piece, statue lineup, or centered landmark scene. "
            "Do not include white matte bars, letterbox padding, or bright framing at the image edges. "
            "The result should feel faded and atmospheric, with soft distant architecture only."
        )
    elif component_type == "background_mid_piece":
        role = (
            "Generic biome background-mid template for later room-specific generation. "
            "This is not a final room scene. Generate a reusable mid-depth architectural layer in strict side view with readable depth rhythm but no hard shell border, no center focal prop, and no gameplay-obscuring clutter."
        )
    elif component_type == "midground_frame":
        role = (
            "Midground PNG with transparency: architectural mass hugging LEFT and RIGHT edges only. "
            "Center third must stay empty (alpha) for gameplay clarity. No arches or props in the center."
        )
    elif component_type == "border_piece":
        role = (
            "Generic border-shell template for later room-specific generation. "
            "Generate one reusable front-view chamber border piece that fills the full 1600x1200 canvas and uses the provided blueprint guide exactly. "
            "This is not a room scene, not a doorway, not a background opening, and not a perspective chamber view. "
            "Treat the whole border as a strict orthographic front elevation on one flat plane with no side-face shading, no projecting sill, no recessed shelf line, no bevels, and no visible depth cues anywhere. "
            "All four sides must read like flat front-facing stone bands, not like a box, shelf, or corridor opening. "
            f"Use the full occupied area shown in the guide: top band y=0..{BORDER_PIECE_BORDER_TOP_PX - 1}, left band x=0..{BORDER_PIECE_BORDER_SIDE_PX - 1}, "
            f"right band x={ATLAS_WIDTH - BORDER_PIECE_BORDER_SIDE_PX}..1599, bottom band y={ATLAS_HEIGHT - BORDER_PIECE_BORDER_BOTTOM_PX}..1199. "
            "Do not shrink, inset, arch, taper, crop, round, vignette, or tear that frame shape. "
            "The top band, left wall band, right wall band, and bottom band must all be visibly present and use the full rectangular guide shape, no more and no less. "
            "The top band and bottom band must read as flat front-facing masonry strips, not as ledges, caps, plinths, sills, or overhangs. "
            "Do not show the top surface of either band; they are faces only. Keep them thick, continuous, plain, slightly lighter than the center, and clearly visible while keeping the side walls straight. "
            "Material-language contract: all four border bands must stay in one cohesive masonry family (same stone age, seam rhythm, and weathering language) with only subtle local variation; do not mix polished trim, carved ornament strips, wood, metal frame inserts, or secondary motif families. "
            "Thickness contract: default to a DOUBLE-thick enclosing read (heavier than a normal trim frame) so the frame mass dominates the image before any center read. "
            "Keep the top band a touch brighter and more legible than the bottom band, and keep the bottom band free of mist glow or threshold haze so it does not become the visual heaviest edge. "
            "The top band in particular should be a simple heavy stone strip with no raised lip, no lintel seam ornament, and no decorative block-coursing that makes it feel carved into a shelf. "
            "Keep the left and right wall bands perfectly straight from the top band to the bottom band: no shoulder flare, no taper, no pedestal base, no widened capital, no inward curve, and no arch-like bulge at either end. "
            "The inner edge of each wall strip must stay at a constant horizontal position for the full wall height; do not let the wall grow thicker near the top or bottom. "
            "Where the top band meets the side walls and where the bottom band meets the side walls, keep square ninety-degree corners, not corbels, chamfers, pedestal feet, or softened arch transitions. "
            "Keep the center calm, generic, and low-detail so later room generation can adapt it cleanly to exact room geometry. "
            "The center must not become a torn plaster breach, shattered wall opening, broken-hole silhouette, or jagged punched-out cavity. "
            "Keep the inner center boundary broad, quiet, and simple; no spiky debris edges, no cracked plaster halo, and no irregular hole shape dominating the frame. "
            "Do not turn the four sides into architectural doorway framing. The left and right sides are not columns or posts, the top is not a lintel, and the bottom is not a sill or threshold. "
            "Avoid inset-shadow opening semantics: no post-and-lintel composition, no inner reveal depth, no warm threshold light, and no fog pooled like an entryway mouth. "
            "Treat the guide as occupancy only. Do not copy the guide colors, outlines, blueprint look, or flat fills into the final art. "
            "Do not draw a bright or dark inner outline around the center opening. The border should meet the center directly with simple stone edges, not a traced frame line. "
            "The light guide regions only mean 'border exists here' and the dark center only means 'center stays calm here'. "
            "Anti-designs: no arches, no pillars, no columns, no lintel, no sill, no threshold, no scene opening, no portal frame, no perspective floor, no stairs, no rubble staging, no glowing hotspot, no white matte bars, no corbel shoulders, no pedestal feet, no jagged breach center, and no empty margins at the edges. "
            "Do not add a cyan, teal, or aqua accent rim along the inner opening or outer canvas edge; separation from the center must be value and texture (stone vs void), not a colored outline. "
            "Use ruined-gothic stone material, cool dark palette, front-facing orientation, and simple readable border masses."
        )
    elif component_type == "primary_floor_piece":
        role = (
            "Horizontal tileable floor source for a side-view metroidvania room. "
            "The provided reference image is a generic component template: preserve its overall silhouette, layout, and front-facing proportion, and repaint it in this biome's material family. "
            "Do not reinterpret the template as a full room slice, scenic wall, doorway, or background scene. "
            "This is a flat modular strip with a narrow walkable top edge and a front-facing stone face beneath it. "
            "It must read strictly in side view. Keep the top lip thin, the front face dominant, and the whole piece readable as one modular floor family. "
            "Do not depict a perspective slab, receding top plane, stage step, paving-stone runway, columns, alcoves, arches, doorway framing, or any above-view floor read. "
            "Do not add glow, a bright gold strip, emissive highlights, or a focal hotspot along the top edge; the top lip should stay in the same dark stone family as the face."
        )
    elif component_type == "wall_piece":
        role = (
            "Single flat enclosing wall source for later room-shell derivation. "
            "The provided reference image is a generic component template: preserve its overall silhouette, layout, and flat front-facing proportion, and repaint it in this biome's material family. "
            "This is not an opening, not a framed doorway, and not a room view. "
            "Generate one opaque stone wall mass in strict side view with restrained block rhythm, dark cool ruined-gothic stone, and no center void. "
            "The image should behave like material source art for wall strips, so keep it continuous and structural from top to bottom. "
            "Do not invent arches, hanging ornaments, capitals, columns, buttress cut-ins, portal framing, or scenic architectural set pieces."
        )
    elif component_type == "ceiling_piece":
        role = (
            "Single continuous ceiling-band source for later room-shell derivation. "
            "The provided reference image is a generic component template: preserve its overall silhouette, layout, and horizontal band proportion, and repaint it in this biome's material family. "
            "Generate one heavy ruined-gothic ceiling strip in strict side view, with a readable masonry band and cohesive lower edge. "
            "The output must read as one opaque horizontal slab or lintel (one structural mass), not a composite of several images: "
            "no row of separate arched windows, tracery panels, or side-by-side 'little portals'; no arcade or cloister rhythm across the width. "
            "If the template shows multiple openings, merge them into one continuous stone cap with shallow relief only. "
            "Do not turn it into a placeholder header bar, do not hang detached floating blocks beneath it, and do not depict an opening or portal frame. "
            "Do not invent arches, ribs, chandeliers, dangling ornaments, corbels, or a cropped room scene under the band. "
            "Fill the width edge-to-edge with one continuous ceiling component: no curved side cut-ins, no dark side end caps, and no fog or atmospheric haze below the band."
        )
    elif component_type == "hero_platform_piece":
        role = (
            "Horizontal tileable platform ledge: top surface + shallow front face, game-ready proportions."
        )
    elif component_type == "platform_piece":
        role = (
            "Generic gameplay platform template for later room-specific generation. "
            "Generate one reusable side-view platform source with a readable top surface and front face, restrained silhouette, and no scene framing around it. "
            "Keep it simple and game-functional: no glowing trim, no gold highlight line, no decorative shrine read, and no attached scenery. "
            "This must be one isolated front-view platform template only: no background, no ruins behind it, no walls, no supports, no arches, and no scenery visible above, below, or behind the platform. "
            "The whole image should read as platform material only, not as a slice of a room."
        )
    elif component_type == "door_piece":
        role = (
            "Vertical doorway tile on transparent background: isolated heavy stone frame, dark opening read, threshold stone, and a punched-out doorway mouth. "
            "Do not generate a surrounding chamber, floor slab, or scenic wall extension. Preserve transparent pixels outside the frame and through the opening."
        )
    elif component_type == "foreground_frame":
        role = _foreground_frame_biome_template_role_text()
    else:
        role = f"Environment component `{component_type}` for the biome kit."
    parts = [
        base_rules,
        role,
        f"Art direction: {locked}".strip(),
    ]
    if neg:
        parts.append(f"Avoid: {neg}")
    if lighting and component_type != "foreground_frame":
        parts.append(f"Lighting notes: {lighting}")
    if notes:
        parts.append(f"Extra: {notes}")
    return "\n".join(p for p in parts if p)


def generate_biome_pack_visuals(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Replace biome template PNGs under art_direction_biomes using Gemini (optional frozen concept refs)."""
    if payload.get("confirm_overwrite") is not True:
        return {"ok": False, "error": "confirm_overwrite must be true to replace biome template images."}
    project = load_project(project_id)
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    direction = _attach_default_biome_pack(project, direction)
    packs = direction.get("biome_packs") or []
    if not packs or not isinstance(packs[0], dict):
        return {"ok": False, "error": "No biome pack available; lock art direction first."}
    pack = packs[0]
    biome_id = str(pack.get("biome_id") or "").strip()
    project_dir = PROJECTS_ROOT / project_id
    extra = str(payload.get("extra_prompt") or "").strip()
    requested_component_types = {
        str(item).strip()
        for item in (payload.get("component_types") or [])
        if str(item).strip()
    }
    if requested_component_types:
        known_component_types = {
            str(template.get("component_type") or "").strip()
            for template in (pack.get("template_library") or [])
            if isinstance(template, dict)
        }
        unknown_component_types = sorted(requested_component_types - known_component_types)
        if unknown_component_types:
            return {
                "ok": False,
                "error": "Unknown biome template component_types requested.",
                "unknown_component_types": unknown_component_types,
            }
    if not _gemini_api_key():
        return {
            "ok": False,
            "error": "GEMINI_API_KEY or GOOGLE_API_KEY is not set. Add it to .env.local in the project root and restart the Sprite Workbench server.",
            "used_ai": False,
            "biome_id": biome_id,
            "component_types": sorted(requested_component_types) if requested_component_types else [],
            "results": [],
        }
    results: List[Dict[str, Any]] = []
    used_ai = False
    generated_component_paths: Dict[str, Path] = {}
    ephemeral_refs: List[Path] = []
    templates = [
        template
        for template in (pack.get("template_library") or [])
        if isinstance(template, dict)
    ]
    templates.sort(key=lambda item: (_biome_component_generation_order(str(item.get("component_type") or "").strip()), str(item.get("component_type") or "").strip()))
    for template in templates:
        component_type = str(template.get("component_type") or "").strip()
        if requested_component_types and component_type not in requested_component_types:
            continue
        frozen_paths = _biome_generation_frozen_reference_paths(project, project_dir, pack, direction, component_type)
        rel_path = Path(str(template.get("image_path") or "").strip())
        if not component_type or not rel_path.parts:
            results.append({"component_type": component_type or "?", "ok": False, "error": "missing template path"})
            continue
        abs_path = project_dir / rel_path
        w = int(template.get("width") or 0)
        h = int(template.get("height") or 0)
        if not w or not h:
            spec_entry = next((item for item in V1_BESPOKE_COMPONENTS if item["component_type"] == component_type), None)
            if spec_entry:
                w, h = spec_entry["size"]
                template["width"] = w
                template["height"] = h
            else:
                results.append({"component_type": component_type, "ok": False, "error": "unknown dimensions"})
                continue
        transparent = str(template.get("transparency_mode") or "opaque") == "alpha"
        refs: List[Path] = _biome_generation_reference_paths(component_type, abs_path, project_dir, direction)
        if component_type == "foreground_frame":
            ephemeral_refs.extend(path for path in refs if ".tmp_biome_generation_refs" in str(path))
        structural_anchor_refs = _biome_structural_reference_paths(component_type, pack, project_dir, generated_component_paths)
        if component_type == "foreground_frame" and not _foreground_frame_should_use_structural_sibling_refs():
            structural_anchor_refs = []
        for path in structural_anchor_refs:
            if path not in refs:
                refs.append(path)
        for path in frozen_paths:
            if path not in refs:
                refs.append(path)
        prompt_extra = extra
        if structural_anchor_refs:
            anchor_note = (
                "Use the referenced structural images as direct material and proportion anchors. "
                "Match their stone family, thickness language, and edge treatment so this component reads like the same foreground kit."
            )
            prompt_extra = f"{prompt_extra}\n{anchor_note}".strip() if prompt_extra else anchor_note
        prompt = _build_biome_template_prompt(component_type, direction, prompt_extra)
        generation_output_path = abs_path
        foreground_frame_raw_path: Optional[Path] = None
        if component_type == "foreground_frame":
            generation_output_path = _foreground_frame_staging_path(project_dir)
            foreground_frame_raw_path = _foreground_frame_raw_candidate_path(generation_output_path)
            existed_before = generation_output_path.exists()
            hash_before = _file_sha256(generation_output_path)
            if existed_before:
                generation_output_path.unlink()
            if foreground_frame_raw_path.exists():
                foreground_frame_raw_path.unlink()
        elif component_type in {"border_piece", "wall_piece", "ceiling_piece", "primary_floor_piece"}:
            generation_output_path = _structural_biome_staging_path(project_dir, component_type)
            existed_before = generation_output_path.exists()
            hash_before = _file_sha256(generation_output_path)
            if existed_before:
                generation_output_path.unlink()
        else:
            existed_before = False
            hash_before = None
        attempt_prompt = prompt
        ok, _gen_err = _generate_bespoke_component_from_references(
            generation_output_path,
            attempt_prompt,
            refs,
            (w, h),
            transparent,
            component_type=component_type,
        )
        if ok:
            used_ai = True
        if component_type == "foreground_frame":
            _write_foreground_frame_attempt_trace(
                project_dir,
                attempt_index=0,
                prompt=attempt_prompt,
                refs=refs,
                output_path=generation_output_path,
                existed_before=existed_before,
                hash_before=hash_before,
                generation_ok=ok,
                direction=direction,
            )
        if ok:
            if component_type in {"foreground_frame", "border_piece", "wall_piece", "ceiling_piece", "primary_floor_piece"}:
                fallback_probe_path = foreground_frame_raw_path if foreground_frame_raw_path and foreground_frame_raw_path.exists() else generation_output_path
                if component_type == "foreground_frame" and _foreground_frame_matches_fallback_seed(fallback_probe_path, direction):
                    source_valid, source_errors = False, ["foreground_frame_matches_fallback_seed"]
                else:
                    source_valid, source_errors = _validate_structural_biome_source(component_type, generation_output_path, project_dir)
                if not source_valid:
                    retry_prompt = _retry_prompt_for_validation_errors(component_type, attempt_prompt, source_errors, 0)
                    if retry_prompt:
                        if generation_output_path.exists():
                            generation_output_path.unlink()
                        ok, _gen_err = _generate_bespoke_component_from_references(
                            generation_output_path,
                            retry_prompt,
                            refs,
                            (w, h),
                            transparent,
                            component_type=component_type,
                        )
                        if ok:
                            used_ai = True
                        if component_type == "foreground_frame":
                            _write_foreground_frame_attempt_trace(
                                project_dir,
                                attempt_index=1,
                                prompt=retry_prompt,
                                refs=refs,
                                output_path=generation_output_path,
                                existed_before=False,
                                hash_before=None,
                                generation_ok=ok,
                                direction=direction,
                            )
                        if ok:
                            fallback_probe_path = foreground_frame_raw_path if foreground_frame_raw_path and foreground_frame_raw_path.exists() else generation_output_path
                            if component_type == "foreground_frame" and _foreground_frame_matches_fallback_seed(fallback_probe_path, direction):
                                source_valid, source_errors = False, ["foreground_frame_matches_fallback_seed"]
                            else:
                                source_valid, source_errors = _validate_structural_biome_source(component_type, generation_output_path, project_dir)
                        if component_type == "foreground_frame":
                            _write_foreground_frame_attempt_trace(
                                project_dir,
                                attempt_index=1,
                                prompt=retry_prompt,
                                refs=refs,
                                output_path=generation_output_path,
                                existed_before=False,
                                hash_before=None,
                                generation_ok=ok,
                                direction=direction,
                                validation_errors=source_errors if ok else ["gemini_image_generation_failed"],
                            )
                if not source_valid:
                    if component_type == "foreground_frame":
                        _write_foreground_frame_attempt_trace(
                            project_dir,
                            attempt_index=0,
                            prompt=attempt_prompt,
                            refs=refs,
                            output_path=generation_output_path,
                            existed_before=existed_before,
                            hash_before=hash_before,
                            generation_ok=ok,
                            direction=direction,
                            validation_errors=source_errors,
                        )
                    rejected_dump = _dump_rejected_foreground_frame_candidate(project_dir, generation_output_path) if component_type == "foreground_frame" else _dump_rejected_structural_candidate(project_dir, component_type, generation_output_path)
                    if generation_output_path.exists():
                        generation_output_path.unlink()
                    if foreground_frame_raw_path and foreground_frame_raw_path.exists():
                        foreground_frame_raw_path.unlink()
                    results.append({
                        "component_type": component_type,
                        "ok": False,
                        "path": rel_path.as_posix(),
                        "error": f"{component_type}_source_invalid",
                        "validation_errors": source_errors,
                        "debug_rejected_candidate_path": (
                            str(rejected_dump.relative_to(project_dir).as_posix())
                            if rejected_dump and rejected_dump.exists()
                            else None
                        ),
                    })
                    continue
                shutil.move(str(generation_output_path), str(abs_path))
                if foreground_frame_raw_path and foreground_frame_raw_path.exists():
                    foreground_frame_raw_path.unlink()
            if component_type == "door_piece" and transparent:
                _apply_door_cutout_alpha(Image.open(abs_path).convert("RGBA")).save(abs_path)
            generated_component_paths[component_type] = abs_path
            template["biome_visual_generated_at"] = now_iso()
            template["source_template_kind"] = "gemini_biome"
            template["source_template_path"] = None
        else:
            results.append({
                "component_type": component_type,
                "ok": False,
                "path": rel_path.as_posix(),
                "error": "gemini_image_generation_failed",
            })
            continue
        results.append({"component_type": component_type, "ok": True, "path": rel_path.as_posix()})
    project["art_direction"] = direction
    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "biome_pack_visuals_generated",
        "created_at": now_iso(),
        "biome_id": biome_id,
        "component_types": sorted(requested_component_types) if requested_component_types else None,
        "used_ai": used_ai,
        "results": copy.deepcopy(results),
    })
    for path in ephemeral_refs:
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass
    tmp_root = project_dir / ".tmp_biome_generation_refs"
    try:
        if tmp_root.exists() and not any(tmp_root.iterdir()):
            tmp_root.rmdir()
    except Exception:
        pass
    return {
        "ok": True,
        "used_ai": used_ai,
        "biome_id": biome_id,
        "component_types": sorted(requested_component_types) if requested_component_types else [],
        "results": results,
        "art_direction": copy.deepcopy(direction),
    }


def _seed_biome_template_asset(output_path: Path, component_type: str, palette: Dict[str, Any], flags: Dict[str, bool], shell_family: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if component_type == "background_plate":
        _fallback_background_asset(output_path, palette, flags, shell_family)
        return
    if component_type == "midground_frame":
        _fallback_midground_asset(output_path, palette, shell_family)
        return
    if component_type == "foreground_frame":
        _fallback_foreground_frame_asset(output_path, palette, flags, shell_family)
        return
    if component_type == "wall_piece":
        _fallback_tile_asset(output_path, palette, (512, 1200), "wall", flags, shell_family)
        return
    if component_type == "ceiling_piece":
        _fallback_ceiling_asset(output_path, palette, shell_family)
        return
    if component_type == "primary_floor_piece":
        _fallback_tile_asset(output_path, palette, (512, 96), "floor", flags, shell_family)
        return
    if component_type == "hero_platform_piece":
        _fallback_tile_asset(output_path, palette, (320, 72), "platform", flags, shell_family)
        return
    if component_type == "door_piece":
        _fallback_curated_door_asset(output_path, palette, flags, shell_family)
        return


def _attach_default_biome_pack(project: Dict[str, Any], direction: Dict[str, Any]) -> Dict[str, Any]:
    biome_packs = copy.deepcopy(direction.get("biome_packs") or [])
    if biome_packs:
        direction["biome_packs"] = biome_packs
        return _refresh_biome_pack_templates(project, direction)
    project_id = str(project.get("project_id") or "").strip()
    if not project_id:
        return direction
    palette = copy.deepcopy(direction.get("palette") or {})
    spec = {
        "theme_id": str(direction.get("template_id") or ""),
        "description": str(direction.get("high_level_direction") or ""),
        "mood": str(direction.get("style_family") or ""),
        "lighting": ", ".join(direction.get("lighting_rules") or []),
        "tags": [_slugify(direction.get("template_id") or "biome")],
        "components": {},
    }
    flags = _environment_style_flags(spec)
    shell_family = _infer_shell_family(spec)
    biome_id = _default_biome_id(direction)
    biome_root = PROJECTS_ROOT / project_id / "art_direction_biomes" / biome_id
    template_library: List[Dict[str, Any]] = []
    for entry in V1_BESPOKE_COMPONENTS:
        filename = f"{entry['component_type']}.png"
        rel_path = Path("art_direction_biomes") / biome_id / filename
        abs_path = PROJECTS_ROOT / project_id / rel_path
        source_kind, source_rel = _install_component_template_asset(
            project_id,
            abs_path,
            entry["component_type"],
            palette,
            flags,
            shell_family,
            entry["size"],
            entry["transparency_mode"] == "alpha",
        )
        template_library.append({
            "template_id": f"{biome_id}-{entry['component_type']}",
            "component_type": entry["component_type"],
            "variant_family": entry["variant_family"],
            "image_path": rel_path.as_posix(),
            "width": entry["size"][0],
            "height": entry["size"][1],
            "orientation": entry["orientation"],
            "transparency_mode": entry["transparency_mode"],
            "visual_role": entry["visual_role"],
            "source_art_direction_version": int(direction.get("version") or 1),
            "approved": True,
            "locked": True,
            "adaptation_mode": _component_adaptation_mode(entry["component_type"]),
            "source_template_kind": source_kind,
            "source_template_path": source_rel,
        })
    _append_pending_border_first_templates(template_library, biome_id, direction)
    direction["biome_packs"] = [{
        "biome_id": biome_id,
        "label": _default_biome_label(direction),
        "locked_direction": {
            "template_id": direction.get("template_id"),
            "style_family": direction.get("style_family"),
            "high_level_direction": direction.get("high_level_direction"),
            "negative_direction": direction.get("negative_direction"),
        },
        "locked_concept_ids": [str(item.get("concept_id") or "").strip() for item in (direction.get("frozen_concepts") or []) if str(item.get("concept_id") or "").strip()],
        "template_library": template_library,
        "border_first_contract": _normalize_border_first_contract(None, template_library),
        "version": 1,
        "locked": True,
        "updated_at": now_iso(),
    }]
    return _refresh_biome_pack_templates(project, direction)


def generate_room_environment_previews(project_id: str, room_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    started = time.perf_counter()
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    direction = _attach_default_biome_pack(project, direction)
    spec = copy.deepcopy(env["spec"])
    if isinstance(payload.get("spec"), dict):
        spec.update(payload["spec"])
    geometry = _room_geometry(room)
    project_dir = PROJECTS_ROOT / project_id
    preview_root = project_dir / "room_environment_previews" / room_id
    preview_root.mkdir(parents=True, exist_ok=True)
    preview_images: List[Dict[str, Any]] = []
    render_level = "level3"
    fallback_reason = None
    used_ai = False
    preview_pack = _select_biome_pack_for_preview(direction, spec)
    preview_frozen_concepts = _preview_frozen_concepts_for_pack(project, direction, preview_pack)
    if geometry.get("polygon"):
        labels = ["Focal landmark", "Atmospheric depth", "Broader ambience"]
        for variant_index in range(3):
            preview_id = f"{room_id}-lvl3-{variant_index + 1}"
            rel_path = Path("room_environment_previews") / room_id / f"{preview_id}.png"
            abs_path = project_dir / rel_path
            generated = _generate_level3_image_with_gemini(
                abs_path,
                project_dir,
                direction,
                geometry,
                spec,
                variant_index,
                frozen_concepts=preview_frozen_concepts,
            )
            if generated:
                used_ai = True
            else:
                _render_level3_image(abs_path, direction, geometry, spec, variant_index)
            palette = _extract_preview_runtime_palette(abs_path)
            preview_images.append({
                "preview_id": preview_id,
                "label": labels[variant_index],
                "render_level": "level3",
                "url": None,
                "used_ai": generated,
                "palette": palette,
            })
        for item in preview_images:
            rel_path = Path("tools") / "2d-sprite-and-animation" / "projects-data" / project_id / "room_environment_previews" / room_id / f"{item['preview_id']}.png"
            item["url"] = "/" + rel_path.as_posix()
        if not used_ai:
            fallback_reason = "gemini_room_preview_unavailable"
    else:
        render_level = "level2"
        fallback_reason = "missing_room_geometry"
        preview_id = f"{room_id}-lvl2-1"
        rel_path = preview_root / f"{preview_id}.png"
        _render_level2_image(rel_path, direction, spec)
        palette = _extract_preview_runtime_palette(rel_path)
        preview_images.append({
            "preview_id": preview_id,
            "label": "Concept fallback",
            "render_level": "level2",
            "url": f"/tools/2d-sprite-and-animation/projects-data/{project_id}/room_environment_previews/{room_id}/{preview_id}.png",
            "palette": palette,
        })
    if not preview_images:
        render_level = "level1"
        fallback_reason = "preview_renderer_unavailable"
        preview_id = f"{room_id}-lvl1-1"
        rel_path = preview_root / f"{preview_id}.png"
        _render_level1_image(rel_path, direction, spec)
        palette = _extract_preview_runtime_palette(rel_path)
        preview_images.append({
            "preview_id": preview_id,
            "label": "Deterministic fallback",
            "render_level": "level1",
            "url": f"/tools/2d-sprite-and-animation/projects-data/{project_id}/room_environment_previews/{room_id}/{preview_id}.png",
            "palette": palette,
        })
    env["preview"]["status"] = "ready"
    env["preview"]["render_level"] = render_level
    env["preview"]["images"] = preview_images
    env["preview"]["approved_image_id"] = None
    env["preview"]["last_generated_at"] = now_iso()
    env["preview"]["fallback_reason"] = fallback_reason
    env["preview"]["approved_palette"] = None
    env["preview"]["geometry_summary"] = geometry
    env["preview"]["scene_plan"] = {
        "style_family": direction.get("style_family"),
        "frozen_concept_ids": list(direction.get("frozen_concept_ids") or []),
        "preview_frozen_concept_ids": [str(item.get("concept_id") or "").strip() for item in preview_frozen_concepts if str(item.get("concept_id") or "").strip()],
        "preview_biome_id": str((preview_pack or {}).get("biome_id") or "").strip(),
        "used_ai": used_ai,
        "description": spec.get("description"),
        "mood": spec.get("mood"),
        "lighting": spec.get("lighting"),
        "fog": spec.get("fog"),
        "landmarks": spec.get("landmarks"),
    }
    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    request_kind = str(payload.get("request_kind") or "generate").strip() or "generate"
    _close_prior_active_suggestion(room, env, request_kind)
    suggestion_id = _create_suggestion_record(
        room,
        env,
        geometry,
        render_level,
        used_ai,
        fallback_reason,
        latency_ms,
        payload,
    )
    env["preview"]["suggestion_id"] = suggestion_id
    env["runtime"]["status"] = "needs_approval"
    env["runtime"]["source"] = None
    env["runtime"]["applied_preview_id"] = None
    env["runtime"]["surface_palette"] = None
    env["runtime"]["material_keywords"] = list(spec.get("materials") or [])
    env["runtime"]["lighting_mode"] = str(spec.get("lighting") or "")
    env["runtime"]["last_applied_at"] = None
    env["runtime"]["bespoke_asset_manifest"] = {
        "schema_version": 2,
        "status": "idle",
        "biome_id": None,
        "border_first_contract": copy.deepcopy(direction.get("biome_packs", [{}])[0].get("border_first_contract") if (direction.get("biome_packs") or [{}])[0] else _normalize_border_first_contract(None)),
        "next_generation_contract": _border_first_generation_contract(),
        "source_preview_id": None,
        "generation_plan": [],
        "required_slots": [],
        "built_slots": [],
        "slot_groups": {},
        "schema_validation": _validate_component_schemas(room, spec, geometry),
        "runtime_review": {"status": "idle", "fail_reasons": [], "metrics": {}, "screenshot_url": None, "review_mode": None},
        "review": {"status": "idle", "fail_reasons": [], "metrics": {}, "screenshot_url": None, "review_mode": None},
        "assets": {},
        "failed_assets": [],
        "used_ai": False,
        "generated_at": None,
        "validation_errors": [],
    }
    env["runtime"]["asset_pack"]["status"] = "idle"
    env["runtime"]["asset_pack"]["used_ai"] = False
    env["runtime"]["asset_pack"]["generated_at"] = None
    env["runtime"]["asset_pack"]["source_preview_id"] = None
    env["runtime"]["asset_pack"]["assets"] = {}
    if envv3.normalize_pipeline_version(env.get("environment_pipeline_version")) == envv3.V3_PIPELINE_VERSION:
        biome_pack = _select_biome_pack(direction)
        preview_seed_id = str((preview_images[0] or {}).get("preview_id") or "").strip() if preview_images else ""
        if biome_pack and preview_seed_id:
            planner_output = envv3.build_generation_plan(room, preview_seed_id, biome_pack, now_iso())
            env["assembly_plan"] = copy.deepcopy(planner_output["assembly_plan"])
            _sync_v3_environment_state(
                project_id,
                env,
                room,
                biome_id=str(biome_pack.get("biome_id") or "") or None,
                generated_at=now_iso(),
            )
    project["updated_at"] = now_iso()
    save_project(project)
    return {
        "ok": True,
        "environment": copy.deepcopy(env),
        "art_direction": copy.deepcopy(direction),
        "room_geometry": geometry,
    }


def revise_room_environment(project_id: str, room_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
    helpfulness = _ensure_room_ai_helpfulness(env)
    active_id = str(helpfulness.get("active_suggestion_id") or "").strip()
    if active_id:
        active = _find_suggestion_record(helpfulness, active_id)
        if active:
            active.setdefault("effort", {})["regeneration_count"] = int((active.get("effort") or {}).get("regeneration_count") or 0) + 1
            active.setdefault("decision", {})["reason_codes"] = _coerce_reason_codes(payload.get("reason_codes")) or active.setdefault("decision", {}).get("reason_codes") or []
            _update_helpfulness_summary(helpfulness)
            save_project(project)
    current = str(env["spec"].get("description") or "").strip()
    instruction = str(payload.get("instruction") or "").strip()
    if not instruction:
        raise ValueError("Revision instruction is required.")
    revised = adapt_room_template(project_id, room_id, {
        "archetype_id": env["template_context"].get("source_template_id"),
        "user_text": f"{current} Revision request: {instruction}".strip(),
        "instruction": instruction,
    })
    return revised


def _select_biome_pack(direction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    packs = direction.get("biome_packs") or []
    return copy.deepcopy(packs[0]) if packs else None


def _biome_pack_matches_theme(pack: Dict[str, Any], theme_id: str) -> bool:
    tid = str(theme_id or "").strip().lower()
    if not tid:
        return False
    bid = str(pack.get("biome_id") or "").strip().lower()
    if bid:
        if bid == tid or bid.startswith(f"{tid}-"):
            return True
    locked = pack.get("locked_direction") or {}
    ltid = str(locked.get("template_id") or "").strip().lower()
    return bool(ltid and ltid == tid)


def _select_biome_pack_for_preview(direction: Dict[str, Any], spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pick the biome pack that matches the room spec theme, else first pack."""
    packs = direction.get("biome_packs") or []
    if not packs:
        return None
    theme = str(spec.get("theme_id") or "").strip()
    if theme:
        for pack in packs:
            if isinstance(pack, dict) and _biome_pack_matches_theme(pack, theme):
                return copy.deepcopy(pack)
    return copy.deepcopy(packs[0])


def _preview_frozen_concepts_for_pack(
    project: Dict[str, Any],
    direction: Dict[str, Any],
    pack: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Resolve frozen concept rows for preview: prefer pack locked_concept_ids, else project selection."""
    requested: List[str] = []
    if pack:
        requested = [str(x).strip() for x in (pack.get("locked_concept_ids") or []) if str(x).strip()]
    if not requested:
        requested = [str(x).strip() for x in (direction.get("frozen_concept_ids") or []) if str(x).strip()]
    return _resolve_frozen_concepts(project, requested if requested else None)


def _template_by_component(biome_pack: Dict[str, Any], component_type: str) -> Optional[Dict[str, Any]]:
    for item in biome_pack.get("template_library") or []:
        if str(item.get("component_type") or "").strip() == component_type:
            return copy.deepcopy(item)
    return None


def _slot_spec(component_type: str) -> Dict[str, Any]:
    return copy.deepcopy(V2_SLOT_SPEC_BY_TYPE[component_type])


def _pit_regions(room: Dict[str, Any], width: int, height: int) -> List[Dict[str, Any]]:
    raw = room.get("pits") if isinstance(room.get("pits"), list) else room.get("voidSpans")
    regions: List[Dict[str, Any]] = []
    for index, item in enumerate(raw or []):
        if not isinstance(item, dict):
            continue
        pit_width = max(96, int(item.get("width") or item.get("w") or 192))
        pit_height = max(128, int(item.get("height") or item.get("h") or 224))
        x = int(item.get("x") or max(0, int(width * 0.35)))
        y = int(item.get("y") or max(0, int(height * 0.72)))
        regions.append({
            "pit_id": str(item.get("id") or f"pit-{index + 1}"),
            "x": x,
            "y": y,
            "width": pit_width,
            "height": pit_height,
        })
    return regions


def _room_component_plan(room: Dict[str, Any], preview_id: str, biome_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    geometry = _room_geometry(room)
    room_id = str(room.get("id") or "room")
    width = int(geometry.get("width") or 1600)
    height = int(geometry.get("height") or 1200)
    platforms = sorted(
        [
            {
                "platform_id": str(item.get("id") or ""),
                "x": int(item.get("x") or 0),
                "y": int(item.get("y") or 0),
                "width": max(1, int(item.get("len") or 1)) * 32,
                "len": max(1, int(item.get("len") or 1)),
            }
            for item in (room.get("platforms") or [])
            if isinstance(item, dict)
        ],
        key=lambda item: (-item["width"], -item["y"], item["x"]),
    )
    primary_floor = next((item for item in platforms if item["width"] >= int(width * 0.68)), platforms[0] if platforms else None)
    hero_platforms = [item for item in platforms if primary_floor is None or item["platform_id"] != primary_floor["platform_id"]][:3]
    active_door = next((item for item in (room.get("doors") or []) if isinstance(item, dict)), None)
    pit_regions = _pit_regions(room, width, height)
    plan: List[Dict[str, Any]] = []
    background_template = _template_by_component(biome_pack, "background_plate")
    wall_template = _template_by_component(biome_pack, "wall_piece") or background_template
    ceiling_template = _template_by_component(biome_pack, "ceiling_piece") or wall_template or background_template
    if background_template:
        slot_spec = _slot_spec("background_far_plate")
        plan.append({
            "slot_id": f"{room_id}-background",
            "component_type": "background_far_plate",
            "schema_key": slot_spec["schema_key"],
            "source_template_id": background_template["template_id"],
            "target_dimensions": {"width": width, "height": height},
            "placement": {"x": int(width / 2), "y": height, "display_width": width, "display_height": height, "origin_x": 0.5, "origin_y": 1},
            "orientation": "full",
            "tile_mode": slot_spec["tile_mode"],
            "border_treatment": "full_frame",
            "slot_group": slot_spec["slot_group"],
            "protected_zones": [{"type": "center_lane", "x": int(width * 0.25), "y": 0, "width": int(width * 0.5), "height": height}],
            "local_geometry": {"room_width": width, "room_height": height},
        })
    midground_template = _template_by_component(biome_pack, "midground_frame")
    if midground_template:
        slot_spec = _slot_spec("midground_side_frame")
        plan.append({
            "slot_id": f"{room_id}-midground",
            "component_type": "midground_side_frame",
            "schema_key": slot_spec["schema_key"],
            "source_template_id": midground_template["template_id"],
            "target_dimensions": {"width": width, "height": height},
            "placement": {"x": int(width / 2), "y": height, "display_width": width, "display_height": height, "origin_x": 0.5, "origin_y": 1},
            "orientation": "full",
            "tile_mode": slot_spec["tile_mode"],
            "border_treatment": "side_only",
            "slot_group": slot_spec["slot_group"],
            "protected_zones": [{"type": "main_route", "x": int(width * 0.3), "y": 0, "width": int(width * 0.4), "height": height}],
            "local_geometry": {"room_width": width, "room_height": height},
        })
    shell_poly_ok = len(geometry.get("polygon") or []) >= 3
    shell_template = (
        _template_by_component(biome_pack, "foreground_frame")
        if _use_unified_room_shell() and shell_poly_ok
        else None
    )
    unified_shell = bool(shell_template)
    if unified_shell:
        cw = max(1, int(round(float(geometry.get("chamber_width") or 0))))
        ch = max(1, int(round(float(geometry.get("chamber_height") or 0))))
        cl = int(round(float(geometry.get("left") or 0)))
        ct = int(round(float(geometry.get("top") or 0)))
        cb = int(round(float(geometry.get("bottom") or 0)))
        shell_spec = _slot_spec("room_shell_foreground")
        plan.append({
            "slot_id": f"{room_id}-room-shell",
            "component_type": "room_shell_foreground",
            "schema_key": shell_spec["schema_key"],
            "source_template_id": shell_template["template_id"],
            "target_dimensions": {"width": cw, "height": ch},
            "placement": {"x": int(cl + cw / 2), "y": cb, "display_width": cw, "display_height": ch, "origin_x": 0.5, "origin_y": 1},
            "orientation": "full",
            "tile_mode": shell_spec["tile_mode"],
            "border_treatment": "unified_chamber_shell",
            "slot_group": shell_spec["slot_group"],
            "protected_zones": [{"type": "walkable_shell_interior", "x": cl, "y": ct, "width": cw, "height": ch}],
            "local_geometry": {
                "room_width": width,
                "room_height": height,
                "chamber_left": cl,
                "chamber_top": ct,
                "chamber_width": cw,
                "chamber_height": ch,
            },
            "transparency_mode": "alpha",
        })
    else:
        if ceiling_template:
            ceiling_height = max(128, int(round(height * 0.18)))
            ceiling_spec = _slot_spec("ceiling_band")
            plan.append({
                "slot_id": f"{room_id}-ceiling",
                "component_type": "ceiling_band",
                "schema_key": ceiling_spec["schema_key"],
                "source_template_id": ceiling_template["template_id"],
                "target_dimensions": {"width": width, "height": ceiling_height},
                "placement": {"x": int(width / 2), "y": 0, "display_width": width, "display_height": ceiling_height, "origin_x": 0.5, "origin_y": 0},
                "orientation": "horizontal",
                "tile_mode": ceiling_spec["tile_mode"],
                "border_treatment": "ceiling_cap",
                "slot_group": ceiling_spec["slot_group"],
                "protected_zones": [{"type": "center_lane", "x": int(width * 0.25), "y": 0, "width": int(width * 0.5), "height": height}],
                "local_geometry": {"room_width": width, "room_height": height},
            })
        if wall_template:
            wall_module_width = max(320, int(round(width * 0.19)))
            wall_module_height = max(320, height - 180)
            wall_base_width = max(256, int(round(width * 0.15)))
            for side, x in (("left", 0), ("right", max(0, width - wall_module_width))):
                slot_type = f"wall_module_{side}"
                slot_spec = _slot_spec(slot_type)
                plan.append({
                    "slot_id": f"{room_id}-wall-module-{side}",
                    "component_type": slot_type,
                    "schema_key": slot_spec["schema_key"],
                    "source_template_id": wall_template["template_id"],
                    "target_dimensions": {"width": wall_module_width, "height": wall_module_height},
                    "placement": {"x": x, "y": 0, "display_width": wall_module_width, "display_height": wall_module_height, "origin_x": 0, "origin_y": 0},
                    "orientation": "vertical",
                    "tile_mode": slot_spec["tile_mode"],
                    "border_treatment": "dark_outer_edge",
                    "slot_group": slot_spec["slot_group"],
                    "protected_zones": [{"type": "center_lane", "x": int(width * 0.26), "y": 0, "width": int(width * 0.48), "height": height}],
                    "local_geometry": {"side": side, "room_width": width, "room_height": height},
                })
                trim_type = f"wall_base_trim_{side}"
                trim_spec = _slot_spec(trim_type)
                plan.append({
                    "slot_id": f"{room_id}-wall-base-{side}",
                    "component_type": trim_type,
                    "schema_key": trim_spec["schema_key"],
                    "source_template_id": wall_template["template_id"],
                    "target_dimensions": {"width": wall_base_width, "height": 160},
                    "placement": {"x": 0 if side == "left" else max(0, width - wall_base_width), "y": max(0, height - 220), "display_width": wall_base_width, "display_height": 160, "origin_x": 0, "origin_y": 0},
                    "orientation": "horizontal",
                    "tile_mode": trim_spec["tile_mode"],
                    "border_treatment": "base_trim",
                    "slot_group": trim_spec["slot_group"],
                    "protected_zones": [{"type": "floor_lane", "x": int(width * 0.22), "y": int(height * 0.7), "width": int(width * 0.56), "height": int(height * 0.3)}],
                    "local_geometry": {"side": side, "room_width": width, "room_height": height},
                })
    floor_template = _template_by_component(biome_pack, "primary_floor_piece") or wall_template
    if floor_template and primary_floor and not unified_shell:
        primary_floor_face_height = 64
        top_spec = _slot_spec("main_floor_top")
        plan.append({
            "slot_id": f"{room_id}-main-floor-top",
            "component_type": "main_floor_top",
            "schema_key": top_spec["schema_key"],
            "source_template_id": floor_template["template_id"],
            "target_dimensions": {"width": primary_floor["width"], "height": 96},
            "placement": {"x": primary_floor["x"], "y": primary_floor["y"], "display_width": primary_floor["width"], "display_height": 96, "origin_x": 0, "origin_y": 0.75},
            "orientation": "horizontal",
            "tile_mode": top_spec["tile_mode"],
            "border_treatment": "top_lip_priority",
            "slot_group": top_spec["slot_group"],
            "protected_zones": [{"type": "platform_top", "x": primary_floor["x"], "y": primary_floor["y"] - 18, "width": primary_floor["width"], "height": 22}],
            "local_geometry": primary_floor,
        })
        face_spec = _slot_spec("main_floor_face")
        plan.append({
            "slot_id": f"{room_id}-main-floor-face",
            "component_type": "main_floor_face",
            "schema_key": face_spec["schema_key"],
            "source_template_id": floor_template["template_id"],
            "target_dimensions": {"width": primary_floor["width"], "height": primary_floor_face_height},
            "placement": {"x": primary_floor["x"], "y": primary_floor["y"] + 12, "display_width": primary_floor["width"], "display_height": primary_floor_face_height, "origin_x": 0, "origin_y": 0},
            "orientation": "horizontal",
            "tile_mode": face_spec["tile_mode"],
            "border_treatment": "face_plane_separation",
            "slot_group": face_spec["slot_group"],
            "protected_zones": [{"type": "platform_top", "x": primary_floor["x"], "y": primary_floor["y"] - 18, "width": primary_floor["width"], "height": 22}],
            "local_geometry": primary_floor,
        })
    platform_template = _template_by_component(biome_pack, "hero_platform_piece") or floor_template
    for index, platform in enumerate(hero_platforms[:3]):
        if not platform_template:
            break
        hero_platform_face_height = 48
        top_spec = _slot_spec("hero_platform_top")
        plan.append({
            "slot_id": f"{room_id}-hero-platform-top-{index + 1}",
            "component_type": "hero_platform_top",
            "schema_key": top_spec["schema_key"],
            "source_template_id": platform_template["template_id"],
            "target_dimensions": {"width": platform["width"], "height": 72},
            "placement": {"x": platform["x"], "y": platform["y"], "display_width": platform["width"], "display_height": 72, "origin_x": 0, "origin_y": 0.68},
            "orientation": "horizontal",
            "tile_mode": top_spec["tile_mode"],
            "border_treatment": "top_lip_priority",
            "slot_group": top_spec["slot_group"],
            "protected_zones": [{"type": "platform_top", "x": platform["x"], "y": platform["y"] - 16, "width": platform["width"], "height": 20}],
            "local_geometry": platform,
        })
        face_spec = _slot_spec("hero_platform_face")
        plan.append({
            "slot_id": f"{room_id}-hero-platform-face-{index + 1}",
            "component_type": "hero_platform_face",
            "schema_key": face_spec["schema_key"],
            "source_template_id": platform_template["template_id"],
            "target_dimensions": {"width": platform["width"], "height": hero_platform_face_height},
            "placement": {"x": platform["x"], "y": platform["y"] + 8, "display_width": platform["width"], "display_height": hero_platform_face_height, "origin_x": 0, "origin_y": 0},
            "orientation": "horizontal",
            "tile_mode": face_spec["tile_mode"],
            "border_treatment": "face_plane_separation",
            "slot_group": face_spec["slot_group"],
            "protected_zones": [{"type": "platform_top", "x": platform["x"], "y": platform["y"] - 16, "width": platform["width"], "height": 20}],
            "local_geometry": platform,
        })
    door_template = _template_by_component(biome_pack, "door_piece")
    if door_template and active_door:
        slot_spec = _slot_spec("door_frame")
        plan.append({
            "slot_id": f"{room_id}-door-1",
            "component_type": "door_frame",
            "schema_key": slot_spec["schema_key"],
            "source_template_id": door_template["template_id"],
            "target_dimensions": {"width": 192, "height": 288},
            "placement": {"x": int(active_door.get("x") or 0), "y": int(active_door.get("y") or 0), "display_width": 96, "display_height": 144, "origin_x": 0.5, "origin_y": 1},
            "orientation": "vertical",
            "tile_mode": slot_spec["tile_mode"],
            "border_treatment": "threshold_clearance",
            "slot_group": slot_spec["slot_group"],
            "protected_zones": [{"type": "door_mouth", "x": int(active_door.get("x") or 0) - 48, "y": int(active_door.get("y") or 0) - 144, "width": 96, "height": 160}],
            "local_geometry": {"door_id": str(active_door.get("id") or ""), "x": int(active_door.get("x") or 0), "y": int(active_door.get("y") or 0)},
        })
    pit_template = _template_by_component(biome_pack, "primary_floor_piece") or floor_template
    if pit_template:
        for index, pit in enumerate(pit_regions):
            rim_spec = _slot_spec("pit_rim")
            plan.append({
                "slot_id": f"{room_id}-pit-rim-{index + 1}",
                "component_type": "pit_rim",
                "schema_key": rim_spec["schema_key"],
                "source_template_id": pit_template["template_id"],
                "target_dimensions": {"width": pit["width"], "height": 96},
                "placement": {"x": pit["x"], "y": pit["y"], "display_width": pit["width"], "display_height": 96, "origin_x": 0, "origin_y": 0},
                "orientation": "horizontal",
                "tile_mode": rim_spec["tile_mode"],
                "border_treatment": "hazard_rim",
                "slot_group": rim_spec["slot_group"],
                "protected_zones": [{"type": "pit_opening", "x": pit["x"], "y": pit["y"], "width": pit["width"], "height": pit["height"]}],
                "local_geometry": pit,
            })
            pit_source = background_template or floor_template
            interior_spec = _slot_spec("pit_interior")
            plan.append({
                "slot_id": f"{room_id}-pit-interior-{index + 1}",
                "component_type": "pit_interior",
                "schema_key": interior_spec["schema_key"],
                "source_template_id": pit_source["template_id"],
                "target_dimensions": {"width": pit["width"], "height": pit["height"]},
                "placement": {"x": pit["x"], "y": pit["y"] + 40, "display_width": pit["width"], "display_height": pit["height"], "origin_x": 0, "origin_y": 0},
                "orientation": "vertical",
                "tile_mode": interior_spec["tile_mode"],
                "border_treatment": "void_drop",
                "slot_group": interior_spec["slot_group"],
                "protected_zones": [{"type": "pit_opening", "x": pit["x"], "y": pit["y"], "width": pit["width"], "height": pit["height"]}],
                "local_geometry": pit,
            })
    return plan


def _room_shell_minimal_material_schema_summary(component_schema: Dict[str, Any]) -> str:
    """Avoid dumping design_intent / silhouette_rules into the shell prompt — they read as 'draw a gothic hall'."""
    if not isinstance(component_schema, dict):
        return ""
    bits = [
        f"material_family={component_schema.get('material_family') or ''}",
        f"damage_profile={component_schema.get('damage_profile') or ''}",
        f"value_contrast={component_schema.get('value_contrast') or ''}",
    ]
    return "; ".join(bits)


def _build_bespoke_prompt_room_shell_foreground(
    direction: Dict[str, Any],
    spec: Dict[str, Any],
    plan_entry: Dict[str, Any],
    template: Dict[str, Any],
    room_geometry: Optional[Dict[str, Any]],
    dims: Dict[str, Any],
    schema_key: str,
    component_schema: Dict[str, Any],
    protected: str,
    placement: Dict[str, Any],
    shell_rules: str,
) -> str:
    """
    Room shell must be mask-driven texture fill, not a scenic interior illustration.
    Do not reuse the generic bespoke template-adaptation block (it contradicts mask fill).
    """
    w = int(dims.get("width") or 0)
    h = int(dims.get("height") or 0)
    _geom = room_geometry if isinstance(room_geometry, dict) else {}
    cw = int(round(float(_geom.get("chamber_width") or 0)))
    ch = int(round(float(_geom.get("chamber_height") or 0)))
    spatial_json = ""
    _poly_c = _geom.get("polygon") or []
    if isinstance(_poly_c, list) and len(_poly_c) >= 3 and w > 0 and h > 0:
        spatial_json = _room_shell_spatial_contract_json(_geom, (w, h))
    spatial_block = ""
    if spatial_json:
        spatial_block = (
            "\nSpatial contract (JSON, same geometry as reference #1):\n"
            f"{spatial_json}\n"
        )
    material_schema = _room_shell_minimal_material_schema_summary(component_schema)
    foot_hint_line = _geometry_footprint_shape_hint(_geom)
    foot_hint_block = f"\n{foot_hint_line}\n" if foot_hint_line else ""
    return textwrap.dedent(
        f"""\
        CRITICAL — SHELL CONTRACT TASK (not a hero illustration, not a full room concept shot):
        Reference #1 is a 3-region contract map at the exact output size.
        Contract-band pixels (~RGB {ROOM_SHELL_CONTRACT_BAND_RGB[0]},{ROOM_SHELL_CONTRACT_BAND_RGB[1]},{ROOM_SHELL_CONTRACT_BAND_RGB[2]}) = REQUIRED occupied shell surface. Fill this band with the chosen shell material, edge-to-edge inside the contract region.
        Clear-opening pixels (~RGB {ROOM_SHELL_SILHOUETTE_CLEAR_RGB[0]},{ROOM_SHELL_SILHOUETTE_CLEAR_RGB[1]},{ROOM_SHELL_SILHOUETTE_CLEAR_RGB[2]}) = REQUIRED clear opening. Keep this region visually clear of shell surface, props, fog, frame members, or nested borders.
        Transparent pixels (alpha 0) = FORBIDDEN outer margin. Do not paint any surface, structure, material, border, or scene composition there.
        TOPOLOGY CONTRACT: there is exactly one shell ring and exactly one clear opening. Do not create an outer frame, nested frame, second border, postcard framing, centered miniature frame, or any picture-in-picture composition.
        OPENING GEOMETRY: the inner boundary between contract band and clear opening is the room footprint at this resolution — including L-shapes, steps, re-entrant corners, and diagonal edges. Do not round it into a portal, nave, or centered rectangle; if references #2 or #3 disagree, reference #1 wins.
        EDGE-FILL CONTRACT: where the contract band reaches x=0, x=W-1, y=0, or y=H-1, the occupied shell surface must meet that same edge. Do not leave an unused outer gutter.

        Reference #2 is a structural shell guide for band continuity, join discipline, and shell massing only. It is not an opening-shape authority.
        Reference #3 is a material-only shell reference. Use it for palette, material family, wear cadence, and surface character only. Do NOT copy framing, camera, perspective, interior depth, landmarks, or scene composition from it.

        {foot_hint_block}{shell_rules}

        Exact output width: {w} px
        Exact output height: {h} px
        Orientation: {plan_entry.get('orientation') or template.get('orientation') or 'full'}
        Runtime placement: x={int(placement.get('x') or 0)} y={int(placement.get('y') or 0)} origin=({float(placement.get('origin_x') or 0):.2f},{float(placement.get('origin_y') or 0):.2f})
        Protected zones: {protected}
        Tile mode: {plan_entry.get('tile_mode') or 'stretch'}
        Border treatment: {plan_entry.get('border_treatment') or 'none'}
        Schema key: {schema_key}
        Material schema (no scene layout): {material_schema}
        Art direction (material vocabulary only — ignore if it suggests a full interior scene): {direction.get('high_level_direction') or ''}
        Avoid: {direction.get('negative_direction') or ''}
        Chamber (keep-clear interior) approximate size for context: {cw}×{ch} px (do not invent interior perspective in the border bands).
        {spatial_block}
        Output one image at exactly {w}×{h} px. No text, no characters, no UI.
        """
    ).strip()


def _build_bespoke_prompt(
    direction: Dict[str, Any],
    spec: Dict[str, Any],
    plan_entry: Dict[str, Any],
    template: Dict[str, Any],
    room_geometry: Optional[Dict[str, Any]] = None,
) -> str:
    dims = plan_entry.get("target_dimensions") or {}
    component_type = str(plan_entry.get("component_type") or "")
    schema_key = str(plan_entry.get("schema_key") or V2_SLOT_SPEC_BY_TYPE.get(component_type, {}).get("schema_key") or "")
    component_schema = ((spec.get("component_schemas") or {}).get(schema_key) or {}) if isinstance(spec.get("component_schemas"), dict) else {}
    protected = ", ".join(
        f"{zone.get('type')}@({int(zone.get('x') or 0)},{int(zone.get('y') or 0)},{int(zone.get('width') or 0)},{int(zone.get('height') or 0)})"
        for zone in (plan_entry.get("protected_zones") or [])
        if isinstance(zone, dict)
    ) or "none"
    placement = plan_entry.get("placement") if isinstance(plan_entry.get("placement"), dict) else {}
    component_rules = {
        "background_far_plate": (
            "Build only the far-depth hall shell. The image must read as enclosing architecture, not a scenic key art moment. "
            "When a footprint silhouette reference is attached, the walkable opening shape (including L-shapes and concave outlines) is locked to that mask — do not substitute a generic centered rectangular nave. "
            "Treat the approved room preview as context only and explicitly reject carryover of any altar, brazier energy, shrine focal landmark, center dais, near framing, "
            "or pasted-in floor strip from that preview. Use walls, arches, pillars, recesses, and bay rhythm to create a readable room shell with calm depth falloff and an open center lane. "
            "Keep the center dimmer than the sides, but not empty fog; it should still show a dark recess, arch, or wall structure. "
            "Prioritize visible enclosing wall faces in the outer thirds and reduce the feeling of a huge open cathedral void. The room should read as a tighter dungeon passage shell, not a vast ceremonial nave. "
            "Do not let one giant central gothic arch dominate the image. The center should feel like a narrower distant recess or corridor mouth framed by heavier side masses, not a grand nave opening. "
            "Do not open the roof into a bright skylight or exterior breach. The upper shell should stay enclosed, dark, and interior-facing."
            "Avoid a broad bright fog bank across the lower half; mist can exist, but lower wall structure and rear floor depth still need to read behind it. "
            "Favor continuous side-wall enclosure and a darker rear chamber body over decorative floating arches. "
            "No thin cyan, teal, or electric accent lines tracing the chamber silhouette; depth and separation come from occlusion, mortar, and value steps in the stone family, not chromatic rim glow. "
            "Push contrast between far shell and mid depth with value and cool-warm separation, not a clashing saturated accent band."
        ),
        "midground_side_frame": (
            "Build only side framing. Keep the center fully open and calm. Restrict arches, columns, and side mass to the left and right edges so the middle third stays clear. "
            "When a footprint silhouette is attached, the clear center must follow that polygon (including irregular and L-shaped voids), not a simplified box. "
            "No center object, no floor plane, no bridge, no hanging focal prop, and nothing that closes the room shell across the playable route. "
            "No cyan/teal rim lines on inner silhouette edges; side masses should separate from the center with shadow and stone value, not UI-like strokes."
        ),
        "room_shell_foreground": (
            "Generate ONE uncropped room-shell source image only. This is shell-source art, not a full room scene. "
            "CONTRACT MAP: reference #1 defines required occupied shell surface, required clear opening, and forbidden outer margin. "
            "Paint shell surface only in the required shell band. Keep the required clear opening visibly clear. Do not paint any surface, structure, or material in the forbidden outer margin. "
            "TOPOLOGY CONTRACT: there is exactly one shell ring and exactly one clear opening. "
            "Do not create an outer frame, nested frame, second border, picture-in-picture composition, or a smaller framed scene inside the image. "
            "SHAPE CONTRACT: top cap, both side walls, and bottom footing must remain inside the allowed shell band and follow every re-entrant corner of the clear opening. "
            "Fill all band joins and corners with continuous shell mass; no empty wedges, no thin joins, and no bleed outside the contract boundaries. "
            "THICKNESS CONTRACT: inside the shell band only, keep a broad structural shell read (not a hairline outline): aim for roughly ~16-24% of image width per side band and ~18-28% top / ~14-22% bottom where the contract allows — "
            "never override the opening to force a symmetric rectangle; if the room is L-shaped, the opening stays L-shaped. "
            "MATERIAL CONTRACT: keep one cohesive shell material family across top/sides/bottom with medium-to-fine surface cadence and no motif drift between bands. "
            "SEPARATION CONTRACT: shell must read against the center by value/texture only; no cyan/teal/aqua rim lines, no UI-like edge strokes, no neon outlines. "
            "MATERIAL REFERENCE CONTRACT: reference #3 is material context only; do not copy framing, opening shape, landmarks, or scene layout from it. "
            "FORBIDDEN: no extra outer frame outside the contract band, no second duplicate floor strip, no perspective floor scene, no scenic center set-piece."
        ),
        "wall_module_left": (
            "Build a structural left wall module only. This must read as solid opaque enclosure stone, not scenic concept art and not a doorway, recess, or window. "
            "Use one broad wall face with shallow masonry relief only. Keep the silhouette simple and block-like. "
            "No arch cutout, no pointed recess, no buttress icon, no internal frame, and no visible opening. "
            "Prioritize a heavy continuous stone mass with restrained block seams and a darker outer edge."
        ),
        "wall_module_right": (
            "Build a structural right wall module only. This must read as solid opaque enclosure stone, not scenic concept art and not a doorway, recess, or window. "
            "Use one broad wall face with shallow masonry relief only. Keep the silhouette simple and block-like. "
            "No arch cutout, no pointed recess, no buttress icon, no internal frame, and no visible opening. "
            "Prioritize a heavy continuous stone mass with restrained block seams and a darker outer edge."
        ),
        "wall_base_trim_left": (
            "Build a left wall base trim that structurally ties the walls into the floor language. Keep it calm, modular, and avoid scenic perspective. "
            "It should feel like the lower left corner of a chamber border, not a loose decorative foot. "
            "Make the trim read as a continuous footing that locks the wall into the floor mass."
        ),
        "wall_base_trim_right": (
            "Build a right wall base trim that structurally ties the walls into the floor language. Keep it calm, modular, and avoid scenic perspective. "
            "It should feel like the lower right corner of a chamber border, not a loose decorative foot. "
            "Make the trim read as a continuous footing that locks the wall into the floor mass."
        ),
        "main_floor_top": (
            "Make this floor feel structural to the same room shell as the walls and background, using the same stone family, wear language, and value range. "
            "Preserve a clean readable top lip, straight side-view silhouette, and shallow underside detail. Keep patterning quiet and modular. "
            "Do not introduce a giant circular ritual graphic, shrine motif, brazier base, or deep scenic perspective unless the entire room is explicitly built around that concept. "
            "This should read as the upper edge of a chamber border that contains the play space, not a floating decorative slab. "
            "Keep the traversal lip relatively thin, bright enough to read, and continuous across the span. "
            "The lip should be visibly lighter than the face beneath it so the chamber border reads immediately."
        ),
        "main_floor_face": (
            "Build only the floor face plane beneath the traversal top. Preserve face separation, modular seams, and restrained underside darkening. No scenic perspective and no ritual floor graphic. "
            "The face should feel like a heavy retaining border wall supporting the room, with enough mass to anchor the whole chamber. "
            "Favor broad darker masonry blocks and vertical weight so the room feels held inside a solid border."
        ),
        "hero_platform_top": (
            "Preserve a crisp horizontal traversal surface that belongs to the same architectural family as the primary floor and enclosing shell. "
            "Use restrained underside variation only. No attached scenic background, no braziers, no ritual emblems, and no large dangling ornaments."
        ),
        "hero_platform_face": (
            "Build only the front face of the platform. Keep ledge readability high, underside variation restrained, and avoid scenic attachments or dangling props."
        ),
        "door_frame": (
            "Build only an isolated doorway component. Preserve a centered door silhouette with clear opening read. "
            "The PNG must keep transparent pixels outside the frame and through the doorway opening. "
            "No extra scene dressing, no floor plane, and no surrounding chamber composition."
        ),
        "pit_rim": "Preserve a crisp hazard rim with strong non-walkable read. No scenic bridge treatment and no false floor continuity.",
        "pit_interior": "Preserve a dark, clearly non-walkable pit interior. The center should read as a drop or void, not a floor surface.",
        "ceiling_band": (
            "Build only the top structural ceiling cap for this room: one horizontal opaque stone band that spans the full output width edge to edge. "
            "It must read as a single slab, lintel course, or shallow continuous vault — not a collage of separate pieces. "
            "Do not draw a row of distinct arched windows, traceried openings, grilles, or side-by-side framed holes; avoid arcade rhythm and repeating portal silhouettes across the width. "
            "Do not show sky, fog, or a distant hall through the band; no transparency and no cut-out voids through the cap. "
            "Keep detail in shallow masonry relief and mortar only; the lower edge of the band should be one cohesive horizontal line. "
            "Match the template’s stone family but simplify toward one unified mass if the reference shows busy multi-opening gothic tracery."
        ),
    }
    if component_type == "room_shell_foreground":
        return _build_bespoke_prompt_room_shell_foreground(
            direction,
            spec,
            plan_entry,
            template,
            room_geometry,
            dims,
            schema_key,
            component_schema if isinstance(component_schema, dict) else {},
            protected,
            placement,
            component_rules["room_shell_foreground"],
        )
    schema_summary = "; ".join([
        f"design_intent={component_schema.get('design_intent') or ''}",
        f"material_family={component_schema.get('material_family') or ''}",
        f"detail_density={component_schema.get('detail_density') or ''}",
        f"value_contrast={component_schema.get('value_contrast') or ''}",
        f"damage_profile={component_schema.get('damage_profile') or ''}",
        f"silhouette_rules={', '.join(_coerce_string_list(component_schema.get('silhouette_rules')))}",
        f"readability_constraints={', '.join(_coerce_string_list(component_schema.get('readability_constraints')))}",
        f"negative_constraints={', '.join(_coerce_string_list(component_schema.get('negative_constraints')))}",
        f"variation_rules={', '.join(_coerce_string_list(component_schema.get('variation_rules')))}",
    ])
    ceiling_field_summary = ""
    if schema_key == "ceiling" and isinstance(component_schema, dict):
        spec_fields = COMPONENT_SCHEMA_DEFS.get("ceiling", {}).get("specific_fields") or ()
        ceiling_field_summary = "; ".join(
            f"{field}={component_schema.get(field) or ''}" for field in spec_fields
        )
    silhouette_clause = ""
    _geom = room_geometry if isinstance(room_geometry, dict) else {}
    _poly = _geom.get("polygon") or []
    _footprint_prompt_component_types = {
        "midground_side_frame",
        "room_shell_foreground",
        "wall_module_left",
        "wall_module_right",
        "wall_base_trim_left",
        "wall_base_trim_right",
        "ceiling_band",
        "main_floor_top",
        "main_floor_face",
        "pit_rim",
    }
    _chamber_bounds_line = (
        f"Chamber bounds (room space): width {int(round(float(_geom.get('chamber_width') or 0)))} px, "
        f"height {int(round(float(_geom.get('chamber_height') or 0)))} px.\n"
    )
    if component_type == "background_far_plate" and isinstance(_poly, list) and len(_poly) >= 3:
        # Matches _bespoke_reference_images_for_component: silhouette is first ref when room geometry exists.
        silhouette_clause = (
            "\nRoom footprint conditioning: A footprint silhouette map is included in the reference images at exact output resolution. "
            "Black marks the outer shell-adjacent band; neutral-dark marks the interior void (walkable footprint opening). "
            "Do not invert that encoding. "
            "Far hall depth, vaulting, and recesses must follow the interior void shape—including L-shapes, steps, re-entrant corners, and diagonal edges—"
            "not a substitute centered rectangle or generic nave. "
            "The interior void should read as continuous atmospheric depth; avoid tall near-black vertical slats, matte poster bars, or hard occluder strips there.\n"
            f"{_chamber_bounds_line}"
        )
    elif component_type in _footprint_prompt_component_types and isinstance(_poly, list) and len(_poly) >= 3:
        silhouette_clause = (
            "\nRoom footprint conditioning: A binary silhouette map is included in the reference images. "
            "For shell conditioning maps, black pixels mark allowed border masonry occupancy; neutral-dark pixels mark keep-clear region (same idea as layout guides — not paper-white). "
            "Do not invert this rule. "
            "The map is at exact output resolution and follows the room contour. "
            "Compose fog, depth, and architecture so the result respects that footprint, including non-rectangular or L-shaped outlines. "
            "Do not substitute a generic centered rectangular nave when the outline is irregular. "
            f"{_chamber_bounds_line}"
        )
    if component_type == "room_shell_foreground":
        silhouette_clause += (
            "Reference usage contract for room_shell_foreground: use the silhouette reference to lock border shape and occupied shell geometry. "
            "Use the approved room preview reference only for palette, tone, and material family. "
            "Do not copy composition objects, camera framing, or scenic focal forms from the preview. "
            "In the silhouette map, black means shell/border occupancy and neutral-dark means keep-clear region to be cut out — do not render that zone as white or as a bright halo. "
            "Do not add decorative rim lines or UI-like accent strokes along the shell inner boundary; stone cut only.\n"
        )
        _geom_for_contract = room_geometry if isinstance(room_geometry, dict) else {}
        _poly_c = _geom_for_contract.get("polygon") or []
        _dims_contract = (
            int(dims.get("width") or 0),
            int(dims.get("height") or 0),
        )
        if isinstance(_poly_c, list) and len(_poly_c) >= 3 and _dims_contract[0] > 0 and _dims_contract[1] > 0:
            _spatial_json = _room_shell_spatial_contract_json(_geom_for_contract, _dims_contract)
            if _spatial_json:
                silhouette_clause += (
                    "\nSpatial contract (JSON, derived from the same geometry as reference #1; obey edge_flush_rule):\n"
                    f"{_spatial_json}\n"
                )
    _foot_tail = _geometry_footprint_shape_hint(_geom)
    if silhouette_clause and _foot_tail:
        silhouette_clause += f"\n{_foot_tail}\n"
    composition_contract = (
        "Composition contract: this must read as a playable room built in depth, not scenic concept art with gameplay layered on top. "
        "If the approved preview contains shrine, altar, brazier, dais, ritual floor, or other focal-scene imagery, treat those elements as rejected source noise unless they are explicitly required by this component role."
    )
    if component_type == "room_shell_foreground":
        composition_contract = (
            "Composition contract: this prompt defines a structural shell component only. "
            "Do not introduce new scene composition, landmarks, or decorative set-pieces beyond what the template role and technical constraints require."
        )
    prompt_opening = (
        "Create a single 2D metroidvania environment component that is a tightly matched equivalent adaptation "
        "of the attached template."
    )
    if component_type == "room_shell_foreground":
        prompt_opening = (
            "Create a single 2D metroidvania environment shell component from the attached references "
            "(silhouette geometry guide + approved room preview)."
        )
    return textwrap.dedent(
        f"""\
        {prompt_opening}
        Preserve the same biome family, silhouette role, and composition discipline.
        Do not redesign the piece. Do not invent a new scene. Only adapt it to the requested fit, dimensions, orientation, and subtle local wear.
        {silhouette_clause}
        Component type: {component_type}
        Variant family: {template.get('variant_family')}
        Exact output width: {int(dims.get('width') or 0)} px
        Exact output height: {int(dims.get('height') or 0)} px
        Orientation: {plan_entry.get('orientation') or template.get('orientation') or 'unspecified'}
        Runtime placement: x={int(placement.get('x') or 0)} y={int(placement.get('y') or 0)} origin=({float(placement.get('origin_x') or 0):.2f},{float(placement.get('origin_y') or 0):.2f})
        Runtime display size: width={int(placement.get('display_width') or dims.get('width') or 0)} px height={int(placement.get('display_height') or dims.get('height') or 0)} px
        Room mood: {spec.get('mood') or ''}
        Room lighting: {spec.get('lighting') or ''}
        Room description: {spec.get('description') or ''}
        Art direction: {direction.get('high_level_direction') or ''}
        Avoid: {direction.get('negative_direction') or ''}
        Protected zones: {protected}
        Tile mode: {plan_entry.get('tile_mode') or 'stretch'}
        Border treatment: {plan_entry.get('border_treatment') or 'none'}
        Schema key: {schema_key}
        Schema contract: {schema_summary}{(' | ceiling_fields: ' + ceiling_field_summary) if ceiling_field_summary else ''}
        Gameplay constraints: keep protected readability zones clear, preserve silhouette readability, stay close to the source template family, and protect top-lip / threshold / hazard readability.
        {composition_contract}
        Component-specific rules: {component_rules.get(component_type, 'Preserve the source template closely and keep gameplay-facing surfaces readable.')}
        Output a single production-ready component image only at the exact output dimensions above. No text, no characters, no UI.
        """
    ).strip()


def _save_reference_image(image: Image.Image, output_path: Path, transparent: bool) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = image.convert("RGBA")
    if not transparent:
        flattened = Image.new("RGBA", image.size, (0, 0, 0, 255))
        flattened.alpha_composite(image)
        image = flattened
    image.save(output_path)
    return output_path


def _pixel_luminance(pixel: Tuple[int, int, int, int]) -> float:
    r, g, b = pixel[:3]
    return (0.2126 * r) + (0.7152 * g) + (0.0722 * b)


def _neutral_distance(pixel: Tuple[int, int, int, int]) -> int:
    r, g, b = pixel[:3]
    return max(abs(r - g), abs(g - b), abs(r - b))


def _apply_door_cutout_alpha(source: Image.Image) -> Image.Image:
    image = source.convert("RGBA")
    width, height = image.size
    pixels = image.load()
    border_samples: List[Tuple[int, int, int, int]] = []
    step = max(4, min(width, height) // 24)
    for x in range(0, width, step):
        border_samples.append(pixels[x, 0])
        border_samples.append(pixels[x, height - 1])
    for y in range(0, height, step):
        border_samples.append(pixels[0, y])
        border_samples.append(pixels[width - 1, y])
    rounded = Counter(
        (int(r / 16) * 16, int(g / 16) * 16, int(b / 16) * 16)
        for r, g, b, _a in border_samples
        if _pixel_luminance((r, g, b, 255)) > 92 and _neutral_distance((r, g, b, 255)) < 28
    )
    bg_colors = [color for color, _count in rounded.most_common(4)]
    if not bg_colors:
        return image

    alpha = Image.new("L", (width, height), 255)
    alpha_pixels = alpha.load()
    visited = set()
    stack: List[Tuple[int, int]] = []

    def matches_background(pixel: Tuple[int, int, int, int]) -> bool:
        if _pixel_luminance(pixel) < 72 or _neutral_distance(pixel) > 34:
            return False
        for color in bg_colors:
            if max(abs(pixel[idx] - color[idx]) for idx in range(3)) <= 42:
                return True
        return False

    for x in range(width):
        stack.append((x, 0))
        stack.append((x, height - 1))
    for y in range(height):
        stack.append((0, y))
        stack.append((width - 1, y))

    while stack:
        x, y = stack.pop()
        if (x, y) in visited or x < 0 or y < 0 or x >= width or y >= height:
            continue
        visited.add((x, y))
        pixel = pixels[x, y]
        if not matches_background(pixel):
            continue
        alpha_pixels[x, y] = 0
        stack.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

    center_seed = (width // 2, min(height - 1, int(height * 0.5)))
    stack = [center_seed]
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= width or y >= height:
            continue
        if alpha_pixels[x, y] == 0:
            continue
        pixel = pixels[x, y]
        if _pixel_luminance(pixel) > 42 or _neutral_distance(pixel) > 26:
            continue
        alpha_pixels[x, y] = 0
        stack.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

    image.putalpha(alpha.filter(ImageFilter.GaussianBlur(radius=max(1, width // 96))))
    return image


def _stylize_structural_component(source: Image.Image, component_type: Optional[str]) -> Image.Image:
    if not component_type:
        return source
    image = source.convert("RGBA")
    width, height = image.size
    def sample_average(box: Tuple[int, int, int, int]) -> Tuple[int, int, int]:
        region = image.crop(box).convert("RGB")
        pixels = list(region.getdata())
        if not pixels:
            return (40, 46, 52)
        count = len(pixels)
        return (
            sum(px[0] for px in pixels) // count,
            sum(px[1] for px in pixels) // count,
            sum(px[2] for px in pixels) // count,
        )

    def stylize_block_masonry(
        block_width: int,
        row_height: int,
        *,
        darker: int = 0,
        seam_alpha: int = 92,
        vertical_jitter: int = 0,
        lip_height: int = 0,
        lip_alpha: int = 0,
    ) -> Image.Image:
        masonry = Image.new("RGBA", image.size, (0, 0, 0, 255))
        draw = ImageDraw.Draw(masonry)
        y = 0
        row_index = 0
        while y < height:
            current_height = min(row_height, height - y)
            offset = 0 if row_index % 2 == 0 else block_width // 2
            x = -offset
            while x < width:
                left = max(0, x)
                right = min(width, x + block_width)
                if right > left:
                    color = sample_average((left, y, right, y + current_height))
                    color = tuple(max(12, min(255, channel - darker)) for channel in color)
                    draw.rectangle((left, y, right, y + current_height), fill=(*color, 255))
                    draw.rectangle((left, y, right, y + current_height), outline=(18, 22, 26, seam_alpha), width=max(1, width // 320))
                x += block_width
            y += current_height
            row_index += 1
        if lip_height > 0 and lip_alpha > 0:
            draw.rectangle((0, 0, width, min(height, lip_height)), fill=(208, 220, 230, lip_alpha))
        if vertical_jitter > 0:
            overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            step = max(28, block_width // 2)
            for seam_x in range(step, width, step):
                wobble = ((seam_x // step) % 3 - 1) * vertical_jitter
                overlay_draw.line((seam_x, max(0, 8 + wobble), seam_x, height), fill=(14, 18, 22, 48), width=max(1, width // 360))
            masonry.alpha_composite(overlay)
        return masonry

    if component_type in {"wall_module_left", "wall_module_right", "wall_base_trim_left", "wall_base_trim_right", "ceiling_band"}:
        return image
    if component_type in {"main_floor_face", "hero_platform_face", "pit_interior"}:
        toned = stylize_block_masonry(
            block_width=max(54, int(width * 0.1)),
            row_height=max(22, int(height * 0.22)),
            darker=24 if component_type == "main_floor_face" else 18,
            seam_alpha=104,
            vertical_jitter=2,
        )
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle((0, 0, width, max(12, int(height * 0.14))), fill=(18, 24, 30, 36))
        draw.rectangle((0, max(0, int(height * 0.12)), width, height), fill=(8, 10, 14, 108))
        draw.rectangle((0, max(0, int(height * 0.56)), width, height), fill=(4, 6, 10, 74))
        seam_step = max(28, int(width * 0.12))
        seam_top = max(8, int(height * 0.08))
        for x in range(seam_step, width, seam_step):
            draw.line((x, seam_top, x, height), fill=(116, 128, 140, 32), width=max(1, width // 240))
        for y in range(max(18, int(height * 0.18)), height, max(18, int(height * 0.2))):
            draw.line((0, y, width, y), fill=(10, 12, 16, 36), width=max(1, height // 72))
        if component_type == "main_floor_face":
            corner_pad = max(28, int(width * 0.1))
            draw.rectangle((0, 0, corner_pad, height), fill=(10, 12, 16, 56))
            draw.rectangle((max(0, width - corner_pad), 0, width, height), fill=(10, 12, 16, 56))
        toned.alpha_composite(overlay)
        return toned
    if component_type in {"main_floor_top", "hero_platform_top", "pit_rim"}:
        image = stylize_block_masonry(
            block_width=max(40, int(width * 0.08)),
            row_height=max(10, int(height * 0.42)),
            darker=10,
            seam_alpha=88,
            lip_height=max(5, int(height * 0.18)),
            lip_alpha=48,
        )
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        lip = max(5, int(height * 0.18))
        seam = min(height, lip + max(5, int(height * 0.08)))
        draw.rectangle((0, 0, width, lip), fill=(214, 226, 236, 72))
        draw.rectangle((0, max(0, lip - 1), width, seam), fill=(18, 24, 30, 142))
        draw.rectangle((0, seam, width, height), fill=(8, 10, 14, 54))
        line_y = min(height - 1, max(1, lip - 1))
        draw.line((0, line_y, width, line_y), fill=(232, 240, 246, 168), width=max(1, height // 28))
        image.alpha_composite(overlay)
        return image
    return image


def _structural_palette(source: Image.Image) -> Dict[str, Tuple[int, int, int]]:
    rgb = source.convert("RGB").resize((48, 48), Image.Resampling.LANCZOS)
    pixels = list(rgb.getdata())
    if not pixels:
        return {
            "dark": (18, 22, 26),
            "mid": (52, 60, 68),
            "light": (108, 118, 126),
        }
    luminance_sorted = sorted(
        pixels,
        key=lambda px: (0.2126 * px[0]) + (0.7152 * px[1]) + (0.0722 * px[2]),
    )
    def avg(bucket: List[Tuple[int, int, int]]) -> Tuple[int, int, int]:
        if not bucket:
            return (40, 46, 52)
        count = len(bucket)
        return (
            sum(px[0] for px in bucket) // count,
            sum(px[1] for px in bucket) // count,
            sum(px[2] for px in bucket) // count,
        )
    dark_bucket = luminance_sorted[: max(1, len(luminance_sorted) // 4)]
    light_bucket = luminance_sorted[-max(1, len(luminance_sorted) // 5):]
    mid_start = len(luminance_sorted) // 3
    mid_end = max(mid_start + 1, len(luminance_sorted) * 2 // 3)
    mid_bucket = luminance_sorted[mid_start:mid_end]
    return {
        "dark": avg(dark_bucket),
        "mid": avg(mid_bucket),
        "light": avg(light_bucket),
    }


def _structural_source_component_type_for_slot(component_type: str) -> str:
    if component_type in {"wall_module_left", "wall_module_right", "wall_base_trim_left", "wall_base_trim_right"}:
        return "wall_piece"
    if component_type == "ceiling_band":
        return "ceiling_piece"
    if component_type in {"main_floor_top", "main_floor_face", "pit_rim"}:
        return "primary_floor_piece"
    return component_type


def _normalized_structural_template_source(component_type: str, template_source: Image.Image) -> Image.Image:
    source_component = _structural_source_component_type_for_slot(component_type)
    palette = _structural_palette(template_source)
    fallback_palette = {
        "dominant": [_rgb_to_hex(palette["dark"]), _rgb_to_hex(palette["mid"])],
        "accent": [_rgb_to_hex(palette["light"])],
    }
    flags: Dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / f"{source_component}.png"
        if source_component == "wall_piece":
            _fallback_tile_asset(path, fallback_palette, (512, 1200), "wall", flags, "weathered_stone")
        elif source_component == "ceiling_piece":
            _fallback_ceiling_asset(path, fallback_palette, "weathered_stone")
        elif source_component == "primary_floor_piece":
            _fallback_tile_asset(path, fallback_palette, (512, 96), "floor", flags, "weathered_stone")
        else:
            return template_source.convert("RGBA")
        return Image.open(path).convert("RGBA")


def _structural_texture_wash(template_source: Image.Image, size: Tuple[int, int], component_type: str) -> Image.Image:
    texture = template_source.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    blur_radius = max(2, int(min(size) * 0.018))
    if component_type in {"wall_module_left", "wall_module_right", "wall_base_trim_left", "wall_base_trim_right"}:
        blur_radius = max(4, int(min(size) * 0.028))
    texture = texture.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    alpha = 48
    if component_type == "ceiling_band":
        alpha = 60
    elif component_type in {"main_floor_top", "main_floor_face", "pit_rim"}:
        alpha = 54
    texture.putalpha(alpha)
    return texture


def _render_synthetic_structural_component(size: Tuple[int, int], component_type: str, template_source: Image.Image) -> Image.Image:
    width, height = size
    material_source = _normalized_structural_template_source(component_type, template_source)
    palette = _structural_palette(material_source)
    image = Image.new("RGBA", size, (*palette["mid"], 255))
    draw = ImageDraw.Draw(image)

    def finish(rendered: Image.Image) -> Image.Image:
        rendered.alpha_composite(_structural_texture_wash(material_source, size, component_type))
        return rendered

    def draw_block_courses(block_w: int, row_h: int, *, base_color: Tuple[int, int, int], seam_color: Tuple[int, int, int, int], offset_alt: bool = True) -> None:
        row = 0
        y = 0
        while y < height:
            current_h = min(row_h, height - y)
            offset = 0 if (not offset_alt or row % 2 == 0) else block_w // 2
            x = -offset
            while x < width:
                left = max(0, x)
                right = min(width, x + block_w)
                if right > left:
                    inset = max(0, block_w // 10)
                    tone_shift = ((row + max(0, x // max(1, block_w))) % 3) - 1
                    fill = tuple(max(12, min(255, channel + (tone_shift * 8))) for channel in base_color)
                    draw.rectangle((left, y, right, y + current_h), fill=(*fill, 255), outline=seam_color, width=2)
                    if inset > 0 and current_h > 12:
                        draw.line((left + inset, y + 2, right - inset, y + 2), fill=(255, 255, 255, 10), width=1)
                x += block_w
            y += current_h
            row += 1

    if component_type in {"wall_module_left", "wall_module_right"}:
        draw.rectangle((0, 0, width, height), fill=(*palette["mid"], 255))
        draw_block_courses(max(34, width // 3), max(52, height // 10), base_color=palette["mid"], seam_color=(18, 22, 26, 180))
        is_left = component_type.endswith("left")
        outer_edge = int(width * 0.24)
        if is_left:
            draw.rectangle((0, 0, outer_edge, height), fill=(*palette["dark"], 255))
            draw.rectangle((width - max(12, width // 18), 0, width, height), fill=(12, 16, 20, 64))
        else:
            draw.rectangle((width - outer_edge, 0, width, height), fill=(*palette["dark"], 255))
            draw.rectangle((0, 0, min(width, max(12, width // 18)), height), fill=(12, 16, 20, 64))
        inner_shadow_w = max(8, int(width * 0.08))
        if is_left:
            draw.rectangle((max(0, width - inner_shadow_w), 0, width, height), fill=(10, 12, 16, 42))
        else:
            draw.rectangle((0, 0, min(width, inner_shadow_w), height), fill=(10, 12, 16, 42))
        draw.rectangle((0, height - max(28, height // 10), width, height), fill=(10, 12, 16, 220))
        return finish(image)

    if component_type in {"wall_base_trim_left", "wall_base_trim_right"}:
        draw.rectangle((0, 0, width, height), fill=(*palette["mid"], 255))
        draw_block_courses(max(42, width // 4), max(26, height // 4), base_color=palette["mid"], seam_color=(16, 20, 24, 180))
        draw.rectangle((0, 0, width, max(12, height // 6)), fill=(14, 18, 22, 180))
        draw.rectangle((0, height - max(16, height // 5), width, height), fill=(10, 12, 16, 220))
        is_left = component_type.endswith("left")
        buttress_w = int(width * 0.24)
        if is_left:
            draw.rectangle((0, int(height * 0.08), buttress_w, height), fill=(12, 14, 18, 180))
        else:
            draw.rectangle((width - buttress_w, int(height * 0.08), width, height), fill=(12, 14, 18, 180))
        return finish(image)

    if component_type == "main_floor_face":
        draw.rectangle((0, 0, width, height), fill=(*palette["mid"], 255))
        draw_block_courses(max(72, width // 14), max(22, height // 3), base_color=palette["mid"], seam_color=(18, 22, 26, 190))
        draw.rectangle((0, 0, width, max(10, height // 6)), fill=(24, 28, 32, 120))
        draw.rectangle((0, height - max(12, height // 5), width, height), fill=(8, 10, 14, 210))
        return finish(image)

    if component_type == "main_floor_top":
        draw.rectangle((0, 0, width, height), fill=(*palette["mid"], 255))
        lip = max(4, height // 7)
        draw.rectangle((0, 0, width, lip), fill=(*palette["light"], 255))
        draw.rectangle((0, lip, width, min(height, lip + max(3, height // 10))), fill=(20, 24, 28, 180))
        draw_block_courses(max(48, width // 18), max(10, height // 2), base_color=palette["mid"], seam_color=(20, 24, 28, 168), offset_alt=False)
        return finish(image)
    if component_type == "ceiling_band":
        draw.rectangle((0, 0, width, height), fill=(*palette["dark"], 255))
        cap_h = max(18, height // 6)
        soffit_h = max(28, height // 4)
        draw.rectangle((0, 0, width, cap_h), fill=(10, 12, 16, 255))
        draw.rectangle((0, cap_h, width, min(height, cap_h + soffit_h)), fill=(*palette["mid"], 255))
        draw_block_courses(max(72, width // 16), max(18, height // 3), base_color=palette["mid"], seam_color=(18, 22, 26, 180), offset_alt=False)
        draw.rectangle((0, max(0, height - max(18, height // 5)), width, height), fill=(16, 20, 24, 120))
        for x in range(max(40, width // 18), width, max(40, width // 9)):
            draw.rectangle((x, cap_h, min(width, x + max(12, width // 64)), height), fill=(16, 20, 24, 140))
        return finish(image)

    return _stylize_structural_component(material_source.resize(size, Image.Resampling.LANCZOS), component_type)


def _apply_background_suppression(source: Image.Image, aggressive: bool = False) -> Image.Image:
    source = source.convert("RGBA")
    width, height = source.size
    fogged = source.filter(ImageFilter.GaussianBlur(radius=max(4, int(width * 0.008))))
    center_mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(center_mask)
    inset_x = int(width * (0.22 if aggressive else 0.26))
    top = int(height * 0.04)
    bottom = int(height * 0.96)
    radius = max(28, int(width * 0.08))
    draw.rounded_rectangle((inset_x, top, width - inset_x, bottom), radius=radius, fill=255)
    center_mask = center_mask.filter(ImageFilter.GaussianBlur(radius=max(24, int(width * 0.04))))
    source = Image.composite(fogged, source, center_mask)
    source = Image.composite(Image.new("RGBA", source.size, (92, 108, 118, 228 if aggressive else 180)), source, center_mask)

    floor_mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(floor_mask)
    floor_left = int(width * 0.12)
    floor_right = int(width * 0.88)
    floor_top = int(height * (0.68 if aggressive else 0.74))
    draw.rounded_rectangle((floor_left, floor_top, floor_right, height), radius=max(20, int(width * 0.05)), fill=255)
    floor_mask = floor_mask.filter(ImageFilter.GaussianBlur(radius=max(18, int(width * 0.03))))
    source = Image.composite(Image.new("RGBA", source.size, (34, 42, 50, 212 if aggressive else 172)), source, floor_mask)

    lower_reveal_mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(lower_reveal_mask)
    reveal_top = int(height * (0.60 if aggressive else 0.66))
    draw.rounded_rectangle(
        (int(width * 0.16), reveal_top, int(width * 0.84), int(height * 0.9)),
        radius=max(18, int(width * 0.04)),
        fill=255,
    )
    lower_reveal_mask = lower_reveal_mask.filter(ImageFilter.GaussianBlur(radius=max(16, int(width * 0.025))))
    source = Image.composite(Image.new("RGBA", source.size, (62, 72, 82, 88 if aggressive else 64)), source, lower_reveal_mask)

    hotspot_mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(hotspot_mask)
    hotspot_width = int(width * (0.26 if aggressive else 0.18))
    hotspot_height = int(height * 0.28)
    hotspot_left = int((width - hotspot_width) / 2)
    draw.ellipse((hotspot_left, 0, hotspot_left + hotspot_width, hotspot_height), fill=255)
    hotspot_mask = hotspot_mask.filter(ImageFilter.GaussianBlur(radius=max(24, int(width * 0.04))))
    source = Image.composite(Image.new("RGBA", source.size, (70, 84, 94, 192 if aggressive else 144)), source, hotspot_mask)
    if aggressive:
        shadow_mask = Image.new("L", source.size, 0)
        draw = ImageDraw.Draw(shadow_mask)
        draw.rounded_rectangle(
            (int(width * 0.28), int(height * 0.08), int(width * 0.72), int(height * 0.9)),
            radius=max(24, int(width * 0.07)),
            fill=255,
        )
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=max(28, int(width * 0.05))))
        source = Image.composite(Image.new("RGBA", source.size, (58, 70, 78, 240)), source, shadow_mask)
    return source


def _background_reference_guide(template_path: Path, output_path: Path, size: Tuple[int, int], transparent: bool, aggressive: bool = False) -> Path:
    source = Image.open(template_path).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    template_source = source.copy()
    source = _apply_background_suppression(source, aggressive=aggressive)
    source = _restore_background_shell_definition(source, template_source)
    return _save_reference_image(source, output_path, transparent)


def _strip_light_matte_background(source: Image.Image, threshold: int = 220) -> Image.Image:
    source = source.convert("RGBA")
    pixels = source.load()
    width, height = source.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if max(r, g, b) < threshold:
                continue
            if (max(r, g, b) - min(r, g, b)) > 18:
                continue
            pixels[x, y] = (r, g, b, 0)
    return source


def _restore_background_shell_definition(source: Image.Image, template_source: Optional[Image.Image] = None) -> Image.Image:
    # Background salvage must not paint deterministic shell-like side bands or top caps
    # back into the scenic plate; that creates false border reads in composed room images.
    return source.convert("RGBA")


def _background_vertical_bar_artifact_count(source: Image.Image) -> int:
    image = source.convert("RGBA")
    width, height = image.size
    if width < 80 or height < 80:
        return 0
    inner_top = int(height * 0.12)
    inner_bottom = int(height * 0.9)
    band_w = max(4, int(width * 0.025))
    neighbor_w = max(8, int(width * 0.04))
    hits = 0
    centers = [0.12, 0.2, 0.28, 0.72, 0.8, 0.88]
    for center in centers:
        cx = int(width * center)
        left = max(0, cx - band_w // 2)
        right = min(width, left + band_w)
        sample = image.crop((left, inner_top, right, inner_bottom))
        full_box = (0.0, 0.0, 1.0, 1.0)
        sample_lum = _image_region_luminance(sample, full_box)
        sample_contrast = _image_region_contrast(sample, full_box)
        left_neighbor = image.crop((max(0, left - neighbor_w), inner_top, left, inner_bottom))
        right_neighbor = image.crop((right, inner_top, min(width, right + neighbor_w), inner_bottom))
        neighbor_lums = [
            _image_region_luminance(left_neighbor, full_box) if left_neighbor.size[0] > 0 else 255.0,
            _image_region_luminance(right_neighbor, full_box) if right_neighbor.size[0] > 0 else 255.0,
        ]
        neighbor_lum = min(neighbor_lums)
        if sample_lum < 22.0 and neighbor_lum > (sample_lum + 18.0) and sample_contrast < 0.003:
            hits += 1
    return hits


def _apply_midground_clearance(source: Image.Image, aggressive: bool = False) -> Image.Image:
    source = source.convert("RGBA")
    width, height = source.size
    hard_clear = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(hard_clear)
    center_left = int(width * (0.2 if aggressive else 0.26))
    center_right = int(width * (0.8 if aggressive else 0.74))
    center_top = int(height * 0.04)
    center_bottom = int(height * 0.98)
    radius = max(28, int(width * 0.08))
    draw.rounded_rectangle((center_left, center_top, center_right, center_bottom), radius=radius, fill=255)
    route_left = int(width * 0.14)
    route_right = int(width * 0.86)
    route_top = int(height * (0.62 if aggressive else 0.7))
    draw.rounded_rectangle((route_left, route_top, route_right, height), radius=max(18, int(width * 0.05)), fill=255)
    source = Image.composite(Image.new("RGBA", source.size, (0, 0, 0, 0)), source, hard_clear)

    clear_mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(clear_mask)
    feather_left = int(width * (0.16 if aggressive else 0.22))
    feather_right = int(width * (0.84 if aggressive else 0.78))
    draw.rounded_rectangle((feather_left, center_top, feather_right, center_bottom), radius=radius, fill=255)
    draw.rounded_rectangle((int(width * 0.1), route_top, int(width * 0.9), height), radius=max(18, int(width * 0.06)), fill=255)
    clear_mask = clear_mask.filter(ImageFilter.GaussianBlur(radius=max(10, int(width * 0.02))))
    source = Image.composite(Image.new("RGBA", source.size, (0, 0, 0, 0)), source, clear_mask)
    return _apply_midground_inner_edge_suppression(source, aggressive=aggressive)


def _apply_midground_inner_edge_suppression(source: Image.Image, aggressive: bool = False) -> Image.Image:
    source = source.convert("RGBA")
    width, height = source.size
    mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(mask)
    inner_left = int(width * 0.08)
    inner_right = int(width * 0.92)
    band_width = int(width * (0.07 if aggressive else 0.05))
    top = int(height * 0.08)
    bottom = int(height * 0.92)
    radius = max(18, int(width * 0.03))
    draw.rounded_rectangle((inner_left, top, inner_left + band_width, bottom), radius=radius, fill=255)
    draw.rounded_rectangle((inner_right - band_width, top, inner_right, bottom), radius=radius, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(14, int(width * 0.025))))
    darken = Image.new("RGBA", source.size, (0, 0, 0, 188 if aggressive else 144))
    return Image.composite(darken, source, mask)


def _midground_reference_guide(template_path: Path, output_path: Path, size: Tuple[int, int], transparent: bool, aggressive: bool = False) -> Path:
    source = Image.open(template_path).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    source = _strip_light_matte_background(source)
    source = _apply_midground_clearance(source, aggressive=aggressive)
    return _save_reference_image(source, output_path, transparent)


def _structural_slot_reference_guide(
    component_type: str,
    output_path: Path,
    size: Tuple[int, int],
    transparent: bool,
    aggressive: bool = False,
) -> Path:
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0 if transparent else 255))
    draw = ImageDraw.Draw(image)
    base_fill = (54, 62, 70, 255)
    accent_fill = (86, 96, 104, 255)
    dark_fill = (28, 34, 40, 255)
    if component_type in {"wall_module_left", "wall_module_right"}:
        draw.rectangle((0, 0, width, height), fill=base_fill)
        outer_band = max(18, int(width * 0.22))
        bottom_band = max(24, int(height * 0.1))
        if component_type.endswith("left"):
            draw.rectangle((0, 0, outer_band, height), fill=dark_fill)
            draw.rectangle((width - max(8, int(width * 0.05)), 0, width, height), fill=accent_fill)
        else:
            draw.rectangle((width - outer_band, 0, width, height), fill=dark_fill)
            draw.rectangle((0, 0, max(8, int(width * 0.05)), height), fill=accent_fill)
        draw.rectangle((0, height - bottom_band, width, height), fill=dark_fill)
    elif component_type in {"wall_base_trim_left", "wall_base_trim_right"}:
        draw.rectangle((0, 0, width, height), fill=base_fill)
        draw.rectangle((0, 0, width, max(10, int(height * 0.2))), fill=accent_fill)
        draw.rectangle((0, height - max(14, int(height * 0.24)), width, height), fill=dark_fill)
    elif component_type == "ceiling_band":
        draw.rectangle((0, 0, width, height), fill=dark_fill)
        cap_h = max(16, int(height * 0.18))
        band_h = max(30, int(height * 0.34))
        draw.rectangle((0, cap_h, width, min(height, cap_h + band_h)), fill=base_fill)
        draw.rectangle((0, min(height, cap_h + band_h), width, height), fill=accent_fill)
    elif component_type == "main_floor_top":
        draw.rectangle((0, 0, width, height), fill=base_fill)
        lip = max(4, int(height * 0.18))
        draw.rectangle((0, 0, width, lip), fill=accent_fill)
        draw.rectangle((0, lip, width, min(height, lip + max(4, int(height * 0.16)))), fill=dark_fill)
    elif component_type in {"main_floor_face", "pit_rim"}:
        draw.rectangle((0, 0, width, height), fill=base_fill)
        draw.rectangle((0, 0, width, max(10, int(height * 0.18))), fill=accent_fill)
        draw.rectangle((0, height - max(10, int(height * 0.2)), width, height), fill=dark_fill)
    elif component_type == "background_far_plate":
        draw.rectangle((0, 0, width, height), fill=(34, 42, 50, 255))
        side = max(64, int(width * 0.2))
        draw.rectangle((0, 0, side, height), fill=(24, 30, 36, 255))
        draw.rectangle((width - side, 0, width, height), fill=(24, 30, 36, 255))
        center_left = int(width * (0.28 if aggressive else 0.3))
        center_right = int(width * (0.72 if aggressive else 0.7))
        center_top = int(height * 0.1)
        center_bottom = int(height * 0.92)
        draw.rounded_rectangle((center_left, center_top, center_right, center_bottom), radius=max(24, int(width * 0.06)), fill=(56, 66, 74, 255))
    return _save_reference_image(image, output_path, transparent)


def _postprocess_component_for_validation(
    path: Path,
    component_type: str,
    errors: List[str],
    attempt_index: int,
    template_path: Optional[Path] = None,
) -> bool:
    if not path.exists() or not errors:
        return False
    source = Image.open(path).convert("RGBA")
    changed = False
    if component_type == "background_far_plate" and "center_lane_too_hot" in errors:
        source = _apply_background_suppression(source, aggressive=True)
        changed = True
    if component_type == "background_far_plate" and "background_shell_definition_low" in errors:
        template_source = None
        if template_path and template_path.exists():
            template_source = Image.open(template_path).convert("RGBA")
        source = _restore_background_shell_definition(source, template_source)
        changed = True
    if component_type == "background_far_plate" and changed:
        _save_reference_image(source, path, transparent=False)
        return True
    if component_type == "midground_side_frame" and "midground_center_clutter" in errors:
        corrected = _apply_midground_clearance(source, aggressive=True)
        _save_reference_image(corrected, path, transparent=True)
        return True
    if component_type == "midground_side_frame" and "midground_inner_edge_hot" in errors:
        corrected = _apply_midground_inner_edge_suppression(source, aggressive=True)
        _save_reference_image(corrected, path, transparent=True)
        return True
    return False


def _bespoke_reference_images_for_component(
    component_type: str,
    template_path: Path,
    approved_preview_path: Path,
    frozen_refs: List[Path],
    reference_root: Path,
    expected_size: Tuple[int, int],
    transparent: bool,
    aggressive: bool = False,
    room: Optional[Dict[str, Any]] = None,
) -> List[Path]:
    guide_path = reference_root / f"{component_type}{'-retry' if aggressive else ''}-guide.png"
    silhouette_path = reference_root / f"{component_type}{'-retry' if aggressive else ''}-silhouette.png"
    contract_path = reference_root / f"{component_type}{'-retry' if aggressive else ''}-contract.png"
    material_path = reference_root / f"{component_type}{'-retry' if aggressive else ''}-material.png"
    if component_type in {
        "wall_module_left",
        "wall_module_right",
        "wall_base_trim_left",
        "wall_base_trim_right",
        "ceiling_band",
        "main_floor_top",
        "main_floor_face",
        "pit_rim",
    }:
        _structural_slot_reference_guide(component_type, guide_path, expected_size, transparent, aggressive=aggressive)
        if room is not None and _write_bespoke_room_silhouette_reference(_room_geometry(room), silhouette_path, expected_size):
            return [silhouette_path, template_path, guide_path]
        return [template_path, guide_path]
    if component_type == "background_far_plate":
        _structural_slot_reference_guide(component_type, guide_path, expected_size, transparent, aggressive=aggressive)
        refs: List[Path] = []
        if room is not None and _write_bespoke_room_silhouette_reference(_room_geometry(room), silhouette_path, expected_size):
            refs.append(silhouette_path)
        refs.extend([template_path, guide_path])
        return refs
    if component_type in {
        "hero_platform_top",
        "hero_platform_face",
        "door_frame",
        "pit_interior",
    }:
        if _render_bespoke_component_from_template(template_path, guide_path, expected_size, transparent, component_type):
            return [guide_path]
        return [template_path]
    if component_type == "room_shell_foreground":
        refs: List[Path] = []
        room_geometry = _room_geometry(room) if room is not None else None
        _cleanup_obsolete_room_shell_reference_artifacts(reference_root, component_type, aggressive)
        if room_geometry and _write_room_shell_contract_map_reference(room_geometry, contract_path, expected_size):
            refs.append(contract_path)
            _room_shell_reference_guide(room_geometry, guide_path, expected_size)
        if guide_path.exists():
            refs.append(guide_path)
        if _room_shell_material_reference(
            template_path,
            approved_preview_path,
            material_path,
            expected_size,
            geometry=room_geometry,
        ):
            refs.append(material_path)
        if refs:
            return refs
        return []
    if component_type == "midground_side_frame":
        guide_builder = _midground_reference_guide
        guide_builder(template_path, guide_path, expected_size, transparent, aggressive=aggressive)
        if room is not None and _write_bespoke_room_silhouette_reference(_room_geometry(room), silhouette_path, expected_size):
            return [silhouette_path, template_path, guide_path]
        return [template_path, guide_path]
    refs: List[Path] = [template_path]
    refs.extend(path for path in frozen_refs if path != template_path)
    return refs


def _render_bespoke_component_from_template(
    template_path: Path,
    output_path: Path,
    size: Tuple[int, int],
    transparent: bool,
    component_type: Optional[str] = None,
) -> bool:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        source = Image.open(template_path).convert("RGBA")
        if component_type in {
            "wall_module_left",
            "wall_module_right",
            "wall_base_trim_left",
            "wall_base_trim_right",
            "ceiling_band",
            "main_floor_top",
            "main_floor_face",
            "pit_rim",
        }:
            synthetic = _render_synthetic_structural_component(size, component_type, source)
            if not transparent:
                flattened = Image.new("RGBA", size, (0, 0, 0, 255))
                flattened.alpha_composite(synthetic)
                synthetic = flattened
            synthetic.save(output_path)
            return True
        if component_type == "background_far_plate":
            source = source.resize(size, Image.Resampling.LANCZOS)
            template_source = source.copy()
            source = _apply_background_suppression(source, aggressive=False)
            source = _restore_background_shell_definition(source, template_source)
            if not transparent:
                flattened = Image.new("RGBA", size, (0, 0, 0, 255))
                flattened.alpha_composite(source)
                source = flattened
            source.save(output_path)
            return True
        if component_type == "midground_side_frame":
            source = source.resize(size, Image.Resampling.LANCZOS)
            source = _strip_light_matte_background(source)
            source = _apply_midground_clearance(source, aggressive=False)
            if not transparent:
                flattened = Image.new("RGBA", size, (0, 0, 0, 255))
                flattened.alpha_composite(source)
                source = flattened
            source.save(output_path)
            return True
        crop_box = None
        if component_type == "wall_module_left":
            crop_box = (0, 0, max(1, int(source.width * 0.16)), source.height)
        elif component_type == "wall_module_right":
            crop_box = (max(0, int(source.width * 0.84)), 0, source.width, source.height)
        elif component_type == "wall_base_trim_left":
            crop_box = (0, max(0, int(source.height * 0.84)), max(1, int(source.width * 0.16)), source.height)
        elif component_type == "wall_base_trim_right":
            crop_box = (max(0, int(source.width * 0.84)), max(0, int(source.height * 0.84)), source.width, source.height)
        elif component_type == "ceiling_band":
            crop_box = (0, 0, source.width, max(1, int(source.height * 0.20)))
        elif component_type == "main_floor_top":
            crop_box = (0, int(source.height * 0.90), source.width, max(1, int(source.height * 0.96)))
        elif component_type == "main_floor_face":
            crop_box = (0, int(source.height * 0.94), source.width, source.height)
        elif component_type == "hero_platform_top":
            crop_box = (int(source.width * 0.08), int(source.height * 0.50), int(source.width * 0.32), max(1, int(source.height * 0.56)))
        elif component_type == "hero_platform_face":
            crop_box = (int(source.width * 0.08), int(source.height * 0.54), int(source.width * 0.32), max(1, int(source.height * 0.61)))
        elif component_type == "pit_rim":
            crop_box = (0, int(source.height * 0.82), source.width, max(1, int(source.height * 0.90)))
        elif component_type == "pit_interior":
            crop_box = (int(source.width * 0.24), int(source.height * 0.32), int(source.width * 0.76), source.height)
        if crop_box:
            source = source.crop(crop_box)
        source = source.resize(size, Image.Resampling.LANCZOS)
        if component_type == "door_frame" and transparent:
            source = _apply_door_cutout_alpha(source)
        source = _stylize_structural_component(source, component_type)
        if not transparent:
            flattened = Image.new("RGBA", size, (0, 0, 0, 255))
            flattened.alpha_composite(source)
            source = flattened
        source.save(output_path)
        return True
    except Exception:
        return False


def _prefix_iteration_reference_refs(
    refs: List[Path],
    iteration_source: Optional[Path],
    component_type: Optional[str] = None,
) -> List[Path]:
    """Inject the current production asset into refs for iterative refinement."""
    if iteration_source is None or not iteration_source.exists():
        return refs
    try:
        resolved = iteration_source.resolve()
        rest = [p for p in refs if (not p.exists()) or p.resolve() != resolved]
    except OSError:
        rest = list(refs)
    if component_type == "room_shell_foreground":
        # Keep contract map first and structural guide second for shell generation.
        insert_idx = min(2, len(rest))
        return rest[:insert_idx] + [iteration_source] + rest[insert_idx:]
    return [iteration_source] + rest


def _generate_bespoke_component_from_references(
    output_path: Path,
    prompt: str,
    refs: List[Path],
    size: Tuple[int, int],
    transparent: bool,
    component_type: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    if component_type == "room_shell_foreground":
        raw_path = _foreground_frame_raw_candidate_path(output_path)
        if raw_path.exists():
            raw_path.unlink()
        ok, err = _generate_image_from_references(raw_path, prompt, refs, size_hint=f"{size[0]}x{size[1]}")
        if ok:
            shutil.copyfile(raw_path, output_path)
            _fit_room_shell_image_to_size(output_path, size)
            return True, None
        return False, err
    if component_type == "foreground_frame":
        raw_path = _foreground_frame_raw_candidate_path(output_path)
        if raw_path.exists():
            raw_path.unlink()
        ok, err = _generate_image_from_references(raw_path, prompt, refs, size_hint=f"{size[0]}x{size[1]}")
        if ok:
            shutil.copyfile(raw_path, output_path)
            _fit_foreground_frame_image_to_size(output_path, size)
            return True, None
        return False, err
    ok, err = _generate_image_from_references(output_path, prompt, refs, size_hint=f"{size[0]}x{size[1]}")
    if ok:
        if component_type in {"border_piece", "background_far_piece", "platform_piece"}:
            _fit_border_first_template_image_to_size(output_path, size, component_type=component_type)
        else:
            _fit_image_to_size(output_path, size, transparent=transparent)
        return True, None
    return False, err


def _retry_prompt_for_validation_errors(component_type: str, prompt: str, errors: List[str], attempt_index: int) -> Optional[str]:
    if not errors:
        return None
    if component_type == "background_far_plate" and "center_lane_too_hot" in errors and attempt_index < 2:
        return f"{prompt}\nRetry instruction: remove the bright floor pool, center glow, ritual-circle read, and any hot apse lighting. The center third must stay dim and architecturally recessed, with visible dark stone structure rather than light bloom."
    if component_type == "background_far_plate" and "background_shell_definition_low" in errors and attempt_index < 2:
        return f"{prompt}\nRetry instruction: strengthen shell definition with visible enclosing wall faces, arches, recesses, vertical bay rhythm, and wall-mass layering in the outer thirds. Reduce the feeling of a giant open nave, one dominant center arch, or a blown-open roof. Keep the center dim, but not blank or fog-only; it should read like a narrower distant recess framed by heavier side structure."
    if component_type == "background_far_plate" and "background_vertical_bar_artifacts" in errors and attempt_index < 2:
        return f"{prompt}\nRetry instruction: remove tall near-black vertical slats, matte bars, and hard interior occluder strips. Side architecture should read as broad stone columns or wall masses integrated into the hall, never as flat black bars."
    if component_type == "background_far_plate" and "generation_failed" not in errors and attempt_index < 2:
        return f"{prompt}\nRetry instruction: avoid a broad bright lower fog bank. Keep the lower half moody, but preserve readable rear-floor depth and lower wall structure behind the mist."
    if component_type == "midground_side_frame" and "midground_center_clutter" in errors and attempt_index < 2:
        return f"{prompt}\nRetry instruction: the center third must be transparent and empty. Remove any center arch, center prop, center silhouette, or floor-crossing occlusion. Keep mass only on the extreme left and right."
    if component_type == "midground_side_frame" and "midground_inner_edge_hot" in errors and attempt_index < 2:
        return f"{prompt}\nRetry instruction: remove bright inner-edge columns or glowing doorway reads near the center lane. Keep any side framing dark, matte, and subordinate to traversal readability."
    if component_type in {"wall_module_left", "wall_module_right"} and attempt_index < 2:
        return f"{prompt}\nRetry instruction: return a flat opaque structural wall face only. Remove any recess, window, niche, arch cutout, pointed silhouette, internal black border, or doorway-like opening. Keep one broad stone slab with shallow block seams and no scenic scene read."
    if component_type == "wall_piece" and attempt_index < 2:
        return f"{prompt}\nRetry instruction: output one flat enclosing wall source only. Remove any doorway, window, arch cutout, niche, post, pillar, inner recess, or framed opening read. Keep the wall as one continuous opaque stone mass with restrained block rhythm."
    if component_type == "ceiling_piece" and attempt_index < 2:
        return (
            f"{prompt}\nRetry instruction: output one continuous opaque ceiling slab only across the full width. "
            "Remove any row of separate arched windows, grilles, or side-by-side framed openings; merge into one lintel or vault mass with shallow block seams only. "
            "Remove detached or floating blocks below the band, avoid placeholder header-bar treatment, and keep the lower edge one straight cohesive masonry line."
        )
    if component_type == "ceiling_band" and attempt_index < 2:
        return (
            f"{prompt}\nRetry instruction: this is the room ceiling cap only: one full-width opaque slab or lintel course, not a collage. "
            "Remove any row of separate arched windows, traceried openings, or side-by-side bays; merge into one continuous stone mass. "
            "No sky, void, or distant hall through the band; keep the lower edge one straight masonry line."
        )
    if component_type == "primary_floor_piece" and attempt_index < 2:
        return f"{prompt}\nRetry instruction: output a flat front-facing floor source. Remove perspective top-plane cues, paving-stone recession, slab-top reads, and thick stage-lip perspective. Keep the face/front separation simple and side-view only."
    if component_type == "border_piece" and attempt_index < 2:
        if "border_piece_side_thickness_thin" in errors or "border_piece_top_thickness_thin" in errors or "border_piece_bottom_thickness_thin" in errors:
            return (
                f"{prompt}\nRetry instruction: double the apparent frame mass. "
                "Make left/right wall strips much thicker and keep top/bottom bands as heavy front-facing masonry slabs, not thin trim lines. "
                "The border should read as a heavy enclosing shell first, with the center as a secondary calm field."
            )
        if "border_piece_texture_family_drift" in errors:
            return (
                f"{prompt}\nRetry instruction: keep one consistent masonry language across top, sides, and bottom. "
                "Use the same stone family, seam scale, and weathering style on all four bands; avoid introducing mixed materials, polished trim, or a different motif on any one side."
            )
        if "border_piece_top_band_weak" in errors or "border_piece_bottom_band_weak" in errors:
            return (
                f"{prompt}\nRetry instruction: keep the flatter non-ornate border direction, but restore strong full-width top and bottom bands. "
                "Do not turn the image into a vertical opening or torn wall slice. "
                "The top and bottom bands must read front-on as visible masonry strips, not like dark shadow belts or visible stone top surfaces. Raise the top band slightly more than the bottom so the upper border reads first, and keep the bottom free of mist glow or threshold haze. "
                "The border must read as one rectangular frame with clear horizontal top and bottom bands, no arch, no floor plane, and no scene opening."
            )
        if "border_piece_side_wall_flare" in errors:
            return (
                f"{prompt}\nRetry instruction: keep the left and right wall bands perfectly straight from top to bottom. "
                "Remove any shoulder flare, pedestal base, widened capital, tapering, chamfer, or arch-like bulge at the top or bottom of the side walls. "
                "Keep the inner wall edge locked to one constant vertical line on each side, with square top and bottom corners where the walls meet the horizontal bands. "
                "The side bands must read as flat vertical masonry strips, not as curved architectural supports."
            )
        if "border_piece_center_breach_read" in errors:
            return (
                f"{prompt}\nRetry instruction: keep the current straight wall direction, but remove the torn-hole center. "
                "Do not paint broken plaster, jagged breach edges, punched-out cavities, shattered wall openings, or spiky debris silhouettes in the center. "
                "Keep the center broad, calm, dim, and simple so the border reads louder than the interior field."
            )
        return (
            f"{prompt}\nRetry instruction: output a generic border template only. "
            "Remove ornate arches, pointed tracery, portal framing, stairs, rubble staging, built-in floor perspective, and any finished chamber-scene composition. "
            "Do not depict columns, posts, lintels, sills, thresholds, or a doorway-like opening framed by four separate architectural members. "
            "Keep the top band, side bands, and bottom band as simple enclosing masses, with a calm low-detail center and no light matte padding at the edges. "
            "If uncertain, choose flatter, heavier, simpler border masses over ornament. A plain flat border is preferred to a beautiful chamber illustration."
        )
    if component_type == "background_far_piece" and attempt_index < 2:
        return (
            f"{prompt}\nRetry instruction: output a faded generic far background only. "
            "Remove bridges, statues, stairs, centered landmarks, and hero-shot composition. "
            "Keep the image broad, soft, low-contrast, and reusable, with no white letterbox bars or bright edge padding."
        )
    if component_type == "platform_piece" and attempt_index < 2:
        return (
            f"{prompt}\nRetry instruction: output one simple gameplay platform template only. "
            "Remove glow lines, gold trim, decorative shrine language, and attached scenery. "
            "Keep a readable top surface and front face in the same cool stone family as the biome. "
            "Do not show any background, ruins, supports, arches, or scene context around the platform. The image should read as platform material only."
        )
    if component_type == "door_frame" and "missing_required_transparency" in errors and attempt_index < 2:
        return f"{prompt}\nRetry instruction: output a true cutout doorway PNG. Preserve transparent pixels outside the stone frame and through the doorway mouth. Do not paint a full rectangular background or surrounding room."
    if component_type == "room_shell_foreground" and attempt_index < 2:
        shell_retry_lines: List[str] = []
        if "shell_rim_mass_low" in errors:
            shell_retry_lines.append(
                f"Retry instruction: the last output read as a thin outline or stroke, not a thick chamber shell. "
                f"Fill wide opaque shell bands: ceiling (top ~{FOREGROUND_FRAME_BORDER_TOP_PX}px / ~{round(100 * FOREGROUND_FRAME_BORDER_TOP_PX / ATLAS_HEIGHT)}% of height), "
                f"side walls (~{FOREGROUND_FRAME_BORDER_SIDE_PX}px / ~{round(100 * FOREGROUND_FRAME_BORDER_SIDE_PX / ATLAS_WIDTH)}% of width each), "
                f"and floor footing (~{FOREGROUND_FRAME_BORDER_BOTTOM_PX}px / ~{round(100 * FOREGROUND_FRAME_BORDER_BOTTOM_PX / ATLAS_HEIGHT)}% of height) with visible material breakup and wear. "
                "Do not output a single-pixel, neon, or HUD-accent rim; do not trace the guide as a hairline frame."
            )
        if "shell_silhouette_overreach" in errors:
            shell_retry_lines.append(
                "Retry instruction: the prior attempt created an outer frame or nested frame outside the allowed shell band. "
                "There is exactly one shell ring and exactly one clear opening. "
                "Keep all surface, structure, and material strictly inside the allowed shell band, keep the forbidden outer margin empty, and do not create any additional outer frame or nested frame."
            )
        if "shell_corner_join_seam_read" in errors:
            shell_retry_lines.append(
                "Retry instruction: fix corner joins so top-left and top-right corners read as one fused shell corner with the side walls. "
                "No visible seam breaks, no pasted corner caps, and no abrupt tone/material jump between top band and side walls."
            )
        if "shell_band_tone_drift" in errors:
            shell_retry_lines.append(
                "Retry instruction: unify top/side/bottom shell tone and material language. "
                "Keep one cohesive shell material family and avoid one side becoming much brighter/darker or stylistically different than the others."
            )
        if "shell_tone_too_dark" in errors:
            shell_retry_lines.append(
                "Retry instruction: raise shell readability contrast against the dark background. "
                "Keep the shell surface in a mid-dark value range (not near-black), with clear value separation from the void while preserving the selected palette."
            )
        if "shell_ceiling_composite_read" in errors:
            shell_retry_lines.append(
                "Retry instruction: remove composite-ceiling assembly artifacts. "
                "The ceiling must be one continuous top band with no repeated strip joins, no pasted patch sections, and no module seam rhythm across the top band."
            )
        if "shell_corner_shadow_pool" in errors:
            shell_retry_lines.append(
                "Retry instruction: remove heavy corner vignette shading. "
                "Keep all four corners readable as mid-dark surface with visible detail; avoid near-black corner pools or smoky shadow blobs."
            )
        if "shell_top_edge_gap_pre" in errors or "shell_top_edge_gap_post" in errors:
            shell_retry_lines.append(
                "Retry instruction: fill the top ledge continuously across the full border width. "
                "Remove missing chunks, edge voids, and underfilled top-cap spans so the ceiling border reads as one solid shell band."
            )
        if "shell_corner_gap_pre" in errors or "shell_corner_gap_post" in errors:
            shell_retry_lines.append(
                "Retry instruction: fill all border corners with occupied shell surface. "
                "No empty corner wedges, no transparent bite-outs, and no thin corner gaps; corners must stay structurally filled and fused into side/top/bottom bands."
            )
        if "shell_silhouette_underfill" in errors:
            shell_retry_lines.append(
                "Retry instruction: underfilled shell zone. "
                "Fill the contract band with continuous shell thickness across top, side, and floor borders so shell mass occupies the full allowed envelope."
            )
        if "shell_detail_scale_too_coarse" in errors:
            shell_retry_lines.append(
                "Retry instruction: increase shell-surface detail cadence and reduce large-unit scale. "
                "Do not use oversized plates or repeated giant units; use smaller or mid-size surface cadence with more frequent detail breakup so the border texture reads correctly at player scale."
            )
        if "walkable_interior_not_cleared" in errors:
            shell_retry_lines.append(
                "Retry instruction: the walkable interior must end up transparent after processing. "
                "Keep ceiling, walls, and floor rim as occupied shell surface; avoid filling the footprint interior with solid surface, props, or fog that survives the cutout."
            )
        if "template_family_drift" in errors or "too_bright" in errors:
            shell_retry_lines.append(
                "Retry instruction: stay closer to the shell material reference on the sides and top/bottom bands; "
                "keep overall values moody and subordinate to gameplay readability."
            )
        if shell_retry_lines:
            return f"{prompt}\n" + "\n".join(shell_retry_lines)
    if component_type == "foreground_frame" and attempt_index < 2:
        if "top_band_not_distinct_from_center" in errors or "bottom_band_not_distinct_from_center" in errors:
            return (
                f"{prompt}\nRetry instruction: make the top band and bottom band read as unmistakable horizontal masonry strips. "
                "Do not let them dissolve into the same foggy blue-gray field as the center. "
                f"The top ~{FOREGROUND_FRAME_BORDER_TOP_PX}px (~{round(100 * FOREGROUND_FRAME_BORDER_TOP_PX / ATLAS_HEIGHT)}% of height) and bottom ~{FOREGROUND_FRAME_BORDER_BOTTOM_PX}px "
                f"(~{round(100 * FOREGROUND_FRAME_BORDER_BOTTOM_PX / ATLAS_HEIGHT)}% of height) must be visibly separate band shapes by eye, with stronger horizontal block-course identity than the center field."
            )
        if "left_wall_center_transition_weak" in errors or "right_wall_center_transition_weak" in errors:
            return (
                f"{prompt}\nRetry instruction: strengthen wall-to-center separation. "
                "Keep the side strips materially darker and more masonry-marked than the center, and do not darken the whole frame uniformly."
            )
    if "generation_failed" in errors and attempt_index < 2:
        return f"{prompt}\nRetry instruction: the previous attempt failed to return a usable image. Return a single finished PNG image only for this component at the requested size."
    if "template_family_drift" in errors and attempt_index < 2:
        return f"{prompt}\nRetry instruction: stay materially closer to the provided guide image. Match the same stone family, value grouping, crack rhythm, edge damage, and overall silhouette discipline. Do not redesign or introduce a new motif."
    return None


def _retry_reference_images_for_component(
    component_type: str,
    template_path: Path,
    approved_preview_path: Path,
    frozen_refs: List[Path],
    reference_root: Path,
    expected_size: Tuple[int, int],
    transparent: bool,
    room: Optional[Dict[str, Any]] = None,
) -> List[Path]:
    return _bespoke_reference_images_for_component(
        component_type,
        template_path,
        approved_preview_path,
        frozen_refs,
        reference_root,
        expected_size,
        transparent,
        aggressive=True,
        room=room,
    )


def _template_delta(path: Path, template_path: Path) -> float:
    try:
        a = Image.open(path).convert("RGBA").resize((96, 96), Image.Resampling.LANCZOS)
        b = Image.open(template_path).convert("RGBA").resize((96, 96), Image.Resampling.LANCZOS)
    except Exception:
        return 999.0
    total = 0.0
    count = 0
    for px_a, px_b in zip(a.getdata(), b.getdata()):
        total += sum(abs(int(px_a[idx]) - int(px_b[idx])) for idx in range(4))
        count += 4
    return total / max(1, count)


def _template_delta_region(path: Path, template_path: Path, box: Tuple[float, float, float, float]) -> float:
    try:
        a = Image.open(path).convert("RGBA")
        b = Image.open(template_path).convert("RGBA")
    except Exception:
        return 999.0
    def crop(img: Image.Image) -> Image.Image:
        width, height = img.size
        left = max(0, min(width, int(width * box[0])))
        top = max(0, min(height, int(height * box[1])))
        right = max(left + 1, min(width, int(width * box[2])))
        bottom = max(top + 1, min(height, int(height * box[3])))
        return img.crop((left, top, right, bottom)).resize((64, 64), Image.Resampling.LANCZOS)
    a_region = crop(a)
    b_region = crop(b)
    total = 0.0
    count = 0
    for px_a, px_b in zip(a_region.getdata(), b_region.getdata()):
        total += sum(abs(int(px_a[idx]) - int(px_b[idx])) for idx in range(4))
        count += 4
    return total / max(1, count)


def _region_luminance(path: Path, box: Tuple[float, float, float, float]) -> float:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    left = max(0, min(w, int(w * box[0])))
    top = max(0, min(h, int(h * box[1])))
    right = max(left + 1, min(w, int(w * box[2])))
    bottom = max(top + 1, min(h, int(h * box[3])))
    region = img.crop((left, top, right, bottom)).resize((48, 48), Image.Resampling.LANCZOS)
    pixels = list(region.getdata())
    if not pixels:
        return 0.0
    return sum((0.2126 * r) + (0.7152 * g) + (0.0722 * b) for r, g, b in pixels) / len(pixels)


def _region_chroma_key_fraction(
    path: Path,
    box: Tuple[float, float, float, float],
    key_rgb: Tuple[int, int, int],
    tolerance: float = 64.0,
) -> float:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    left = max(0, min(w, int(w * box[0])))
    top = max(0, min(h, int(h * box[1])))
    right = max(left + 1, min(w, int(w * box[2])))
    bottom = max(top + 1, min(h, int(h * box[3])))
    region = img.crop((left, top, right, bottom)).resize((48, 48), Image.Resampling.LANCZOS)
    pixels = list(region.getdata())
    if not pixels:
        return 0.0
    matches = 0
    for r, g, b in pixels:
        if key_rgb == FOREGROUND_FRAME_CENTER_KEY_RGB:
            if g >= 120 and (g - r) >= 24 and (g - b) >= 18:
                matches += 1
                continue
        distance = math.sqrt(
            ((r - key_rgb[0]) ** 2) +
            ((g - key_rgb[1]) ** 2) +
            ((b - key_rgb[2]) ** 2)
        )
        if distance <= tolerance:
            matches += 1
    return matches / len(pixels)


def _region_alpha_ratio(path: Path, box: Tuple[float, float, float, float]) -> float:
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    left = max(0, min(w, int(w * box[0])))
    top = max(0, min(h, int(h * box[1])))
    right = max(left + 1, min(w, int(w * box[2])))
    bottom = max(top + 1, min(h, int(h * box[3])))
    region = img.crop((left, top, right, bottom)).resize((48, 48), Image.Resampling.LANCZOS)
    alpha = list(region.getchannel("A").getdata())
    if not alpha:
        return 0.0
    return sum(1 for value in alpha if value > 24) / len(alpha)


def _validate_bespoke_component(
    path: Path,
    component_type: str,
    expected_size: Tuple[int, int],
    transparency_mode: str,
    template_path: Optional[Path] = None,
) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not path.exists():
        return False, ["missing_file"]
    img = Image.open(path).convert("RGBA")
    if img.size != expected_size:
        errors.append("size_mismatch")
    alpha_ratio = _alpha_ratio(path)
    luminance = _sample_luminance(path)
    if transparency_mode == "alpha" and alpha_ratio < 0.05:
        errors.append("missing_required_transparency")
    if component_type in {"background_far_plate", "midground_side_frame", "room_shell_foreground"} and luminance > 185:
        errors.append("too_bright")
    if component_type in {"main_floor_top", "main_floor_face", "hero_platform_top", "hero_platform_face", "pit_rim"} and luminance > 176:
        errors.append("platform_readability_risk")
    trusted_template_copy = False
    if template_path and template_path.exists():
        delta = _template_delta(path, template_path)
        trusted_template_copy = delta <= 1.5
        if component_type == "background_far_plate" and delta > 42:
            errors.append("template_family_drift")
        if component_type == "midground_side_frame":
            edge_delta = (
                _template_delta_region(path, template_path, (0.0, 0.0, 0.24, 1.0)) +
                _template_delta_region(path, template_path, (0.76, 0.0, 1.0, 1.0))
            ) / 2.0
            if edge_delta > 42:
                errors.append("template_family_drift")
        # room_shell_foreground is mask-driven; output need not match biome template edges (would false-reject mask fill).
        if component_type in {
            "wall_module_left",
            "wall_module_right",
            "wall_base_trim_left",
            "wall_base_trim_right",
            "main_floor_top",
            "main_floor_face",
            "hero_platform_top",
            "hero_platform_face",
            "door_frame",
            "pit_rim",
            "pit_interior",
        } and delta > 54:
            errors.append("template_family_drift")
    if transparency_mode == "opaque" and alpha_ratio > (0.08 if trusted_template_copy else 0.02):
        errors.append("unexpected_transparency")
    if component_type == "background_far_plate" and not trusted_template_copy:
        center = _region_luminance(path, (0.34, 0.22, 0.66, 0.78))
        edges = (_region_luminance(path, (0.0, 0.18, 0.18, 0.82)) + _region_luminance(path, (0.82, 0.18, 1.0, 0.82))) / 2.0
        if center - edges > 18:
            errors.append("center_lane_too_hot")
        center_contrast = _image_region_contrast(img, (0.34, 0.22, 0.66, 0.78))
        if center_contrast < 0.0025:
            errors.append("background_shell_definition_low")
        if _background_vertical_bar_artifact_count(img) >= 2:
            errors.append("background_vertical_bar_artifacts")
    if component_type == "midground_side_frame" and not trusted_template_copy:
        center = _region_alpha_ratio(path, (0.32, 0.18, 0.68, 0.82))
        side_a = _region_alpha_ratio(path, (0.0, 0.18, 0.2, 0.82))
        side_b = _region_alpha_ratio(path, (0.8, 0.18, 1.0, 0.82))
        if center > max(side_a, side_b) + 0.15:
            errors.append("midground_center_clutter")
        inner_edge_lum = max(
            _region_luminance(path, (0.08, 0.12, 0.18, 0.9)),
            _region_luminance(path, (0.82, 0.12, 0.92, 0.9)),
        )
        edge_lum = max(
            _region_luminance(path, (0.0, 0.12, 0.08, 0.9)),
            _region_luminance(path, (0.92, 0.12, 1.0, 0.9)),
        )
        if inner_edge_lum > max(150.0, edge_lum + 42.0):
            errors.append("midground_inner_edge_hot")
    return len(errors) == 0, errors


def _validation_reference_for_component(
    component_type: str,
    template_path: Optional[Path],
    refs_for_job: Optional[List[Path]] = None,
) -> Optional[Path]:
    if component_type in {"background_far_plate", "midground_side_frame", "room_shell_foreground"} and template_path and template_path.exists():
        return template_path
    if refs_for_job and refs_for_job[0].exists():
        return refs_for_job[0]
    return template_path


def _slot_groups_from_plan(plan: List[Dict[str, Any]], built_slots: List[str], failed_slots: List[str]) -> Dict[str, Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    built = set(built_slots)
    failed = set(failed_slots)
    for entry in plan:
        group_key = str(entry.get("slot_group") or "misc")
        bucket = groups.setdefault(group_key, {"required": 0, "built": 0, "failed": 0, "slots": []})
        bucket["required"] += 1
        bucket["slots"].append(str(entry.get("slot_id") or ""))
        if entry.get("slot_id") in built:
            bucket["built"] += 1
        if entry.get("slot_id") in failed:
            bucket["failed"] += 1
    return groups


def _room_environment_asset_url(project_id: str, relative_path: Path) -> str:
    return f"/tools/2d-sprite-and-animation/projects-data/{project_id}/{relative_path.as_posix()}"


def _build_structural_review_bundle(
    project_id: str,
    room_id: str,
    project_dir: Path,
    biome_pack: Dict[str, Any],
    assets: Dict[str, Any],
) -> Dict[str, Any]:
    review_root = project_dir / "room_environment_assets" / room_id / "review"
    review_root.mkdir(parents=True, exist_ok=True)
    biome_root = project_dir / "art_direction_biomes" / str(biome_pack.get("biome_id") or "")
    source_components = ["wall_piece", "ceiling_piece", "primary_floor_piece", "hero_platform_piece", "foreground_frame"]
    sources: List[Dict[str, Any]] = []
    source_images: List[Tuple[str, Image.Image]] = []
    for component_type in source_components:
        path = biome_root / f"{component_type}.png"
        if not path.exists():
            continue
        rel = path.relative_to(project_dir)
        sources.append({
            "component_type": component_type,
            "path": rel.as_posix(),
            "url": _room_environment_asset_url(project_id, rel),
        })
        try:
            source_images.append((component_type, Image.open(path).convert("RGBA")))
        except Exception:
            continue

    derived_types = [
        "room_shell_foreground",
        "ceiling_band",
        "wall_module_left",
        "wall_module_right",
        "main_floor_top",
        "main_floor_face",
        "hero_platform_top",
        "hero_platform_face",
        "pit_rim",
    ]
    derived_assets: List[Dict[str, Any]] = []
    derived_images: List[Tuple[str, Image.Image]] = []
    for component_type in derived_types:
        asset = next(
            (
                item
                for item in assets.values()
                if isinstance(item, dict)
                and str(item.get("component_type") or "") == component_type
                and str(item.get("url") or "").strip()
            ),
            None,
        )
        if not asset:
            continue
        rel = Path(str(asset["url"]).split(f"/tools/2d-sprite-and-animation/projects-data/{project_id}/", 1)[-1])
        path = project_dir / rel
        if not path.exists():
            continue
        derived_assets.append({
            "component_type": component_type,
            "path": rel.as_posix(),
            "url": _room_environment_asset_url(project_id, rel),
        })
        try:
            derived_images.append((component_type, Image.open(path).convert("RGBA")))
        except Exception:
            continue

    card_w = 224
    card_h = 160
    pad = 16
    cols = 4
    rows = 1 + (1 if derived_images else 0)
    sheet = Image.new("RGBA", (pad + cols * (card_w + pad), pad + rows * (card_h + 36 + pad)), (8, 10, 14, 255))
    draw = ImageDraw.Draw(sheet)

    def paste_cards(items: List[Tuple[str, Image.Image]], row_index: int) -> None:
        for index, (label, image) in enumerate(items[:cols]):
            x = pad + index * (card_w + pad)
            y = pad + row_index * (card_h + 36 + pad)
            draw.rounded_rectangle((x, y, x + card_w, y + card_h + 28), radius=12, fill=(16, 20, 24, 255), outline=(42, 52, 62, 255), width=2)
            fit = image.copy()
            fit.thumbnail((card_w - 12, card_h - 12), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (card_w - 12, card_h - 12), (0, 0, 0, 255))
            offset = ((canvas.width - fit.width) // 2, (canvas.height - fit.height) // 2)
            canvas.alpha_composite(fit, offset)
            sheet.alpha_composite(canvas, (x + 6, y + 6))
            draw.text((x + 8, y + card_h + 6), label, fill=(200, 214, 222, 255))

    paste_cards(source_images, 0)
    if derived_images:
        paste_cards(derived_images, 1)
    contact_path = review_root / "structural-review-bundle.png"
    sheet.save(contact_path)
    contact_rel = contact_path.relative_to(project_dir)
    return {
        "sources": sources,
        "derived_assets": derived_assets,
        "contact_sheet": {
            "path": contact_rel.as_posix(),
            "url": _room_environment_asset_url(project_id, contact_rel),
        },
    }


def _placement_bounds(placement: Dict[str, Any]) -> Tuple[int, int, int, int]:
    display_width = max(1, int(placement.get("display_width") or 1))
    display_height = max(1, int(placement.get("display_height") or 1))
    origin_x = float(placement.get("origin_x") or 0)
    origin_y = float(placement.get("origin_y") or 0)
    x = int(round(float(placement.get("x") or 0) - (display_width * origin_x)))
    y = int(round(float(placement.get("y") or 0) - (display_height * origin_y)))
    return x, y, display_width, display_height


def _primary_floor_band_bounds(room: Dict[str, Any]) -> Optional[Tuple[int, int, int, int]]:
    geometry = _room_geometry(room)
    chamber_left = int(round(float(geometry.get("left") or 0.0)))
    chamber_right = int(round(float(geometry.get("right") or geometry.get("width") or 1.0)))
    chamber_width = max(1.0, float(geometry.get("chamber_width") or geometry.get("width") or 1.0))
    room_height = max(1.0, float(geometry.get("height") or 1.0))
    room_bottom = float(geometry.get("bottom") or room_height)
    platforms = list(geometry.get("platforms") or [])
    if not platforms:
        return None
    candidates = [
        item for item in platforms
        if (float(item.get("len") or 0) * 32.0) >= chamber_width * 0.68
        and float(item.get("y") or 0.0) >= room_bottom - 96.0
    ]
    if not candidates:
        return None
    primary = sorted(
        candidates,
        key=lambda item: (-(float(item.get("len") or 0) * 32.0), -float(item.get("y") or 0.0)),
    )[0]
    primary_x = int(round(float(primary.get("x") or 0.0)))
    primary_y = int(round(float(primary.get("y") or 0.0)))
    primary_width = max(1, int(round(float(primary.get("len") or 1) * 32.0)))
    support_left = min(primary_x, chamber_left)
    support_right = max(primary_x + primary_width, chamber_right)
    lower_floor_top = min(int(round(room_bottom - 72.0)), primary_y + 20)
    lower_floor_height = max(48, int(round(room_height - lower_floor_top - 12.0)))
    return support_left, lower_floor_top, max(1, support_right - support_left), lower_floor_height


def _wall_shell_bounds(component_type: str, placement: Dict[str, Any], room: Dict[str, Any]) -> Optional[Tuple[int, int, int, int]]:
    geometry = _room_geometry(room)
    room_width = max(1, int(round(float(geometry.get("width") or 1.0))))
    room_height = max(1, int(round(float(geometry.get("height") or 1.0))))
    chamber_left = int(round(float(geometry.get("left") or 0.0)))
    chamber_right = int(round(float(geometry.get("right") or room_width)))
    chamber_width = max(1, int(round(float(geometry.get("chamber_width") or room_width))))
    chamber_top = int(round(float(geometry.get("top") or 0.0)))
    chamber_bottom = int(round(float(geometry.get("bottom") or room_height)))
    x, y, display_width, display_height = _placement_bounds(placement)
    if component_type in {"wall_module_left", "wall_module_right"}:
        accent_width = min(max(96, int(round(chamber_width * 0.16))), max(1, chamber_width // 2))
        widened_height = max(display_height, chamber_bottom - chamber_top)
        if component_type.endswith("left"):
            return chamber_left, chamber_top, accent_width, widened_height
        return max(chamber_left, chamber_right - accent_width), chamber_top, accent_width, widened_height
    if component_type in {"wall_base_trim_left", "wall_base_trim_right"}:
        widened_width = min(max(96, int(round(chamber_width * 0.16))), max(1, chamber_width // 2))
        if component_type.endswith("left"):
            return chamber_left, y, widened_width, display_height
        return max(chamber_left, chamber_right - widened_width), y, widened_width, display_height
    return None


def _chamber_sprite_bounds(room: Dict[str, Any]) -> Tuple[int, int, int, int]:
    geometry = _room_geometry(room)
    room_width = max(1, int(round(float(geometry.get("width") or 1.0))))
    room_height = max(1, int(round(float(geometry.get("height") or 1.0))))
    chamber_left = int(round(float(geometry.get("left") or 0.0)))
    chamber_right = int(round(float(geometry.get("right") or room_width)))
    chamber_top = int(round(float(geometry.get("top") or 0.0)))
    chamber_bottom = int(round(float(geometry.get("bottom") or room_height)))
    return (
        chamber_left,
        chamber_top,
        max(1, chamber_right - chamber_left),
        max(1, chamber_bottom - chamber_top),
    )


def _apply_room_polygon_opening_mask(
    sprite: Image.Image,
    room: Optional[Dict[str, Any]],
    origin: Tuple[int, int],
) -> Image.Image:
    if room is None:
        return sprite
    polygon = room.get("polygon") if isinstance(room.get("polygon"), list) else None
    if not polygon or len(polygon) < 3:
        return sprite
    mask = Image.new("L", sprite.size, 0)
    draw = ImageDraw.Draw(mask)
    origin_x, origin_y = origin
    points: List[Tuple[float, float]] = []
    for point in polygon:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        px = point[0]
        py = point[1]
        if not isinstance(px, (int, float)) or not isinstance(py, (int, float)):
            continue
        points.append((float(px) - origin_x, float(py) - origin_y))
    if len(points) < 3:
        return sprite
    draw.polygon(points, fill=255)
    clipped = sprite.copy()
    alpha = clipped.getchannel("A")
    clipped.putalpha(ImageChops.multiply(alpha, mask))
    return clipped


def _apply_runtime_review_layer_alpha(sprite: Image.Image, component_type: str) -> Image.Image:
    alpha_scale_by_component = {
        "background_far_plate": 0.72,
        "background_plate": 0.72,
        "midground_side_frame": 0.62,
        "midground_frame": 0.62,
        "room_shell_foreground": 1.0,
    }
    scale = alpha_scale_by_component.get(component_type)
    if scale is None or abs(scale - 1.0) < 0.001:
        return sprite
    adjusted = sprite.copy()
    alpha = adjusted.getchannel("A")
    alpha = alpha.point(lambda value: int(round(value * scale)))
    adjusted.putalpha(alpha)
    return adjusted


def _build_standard_wall_accent_sprite(width: int, height: int, side: str) -> Image.Image:
    sprite = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sprite)
    body = (16, 20, 25, 255)
    seam = (34, 42, 50, 255)
    face = (18, 22, 27, 255)
    relief = (68, 78, 90, 108)
    base_bond = (12, 16, 20, 255)
    highlight = (92, 104, 116, 90)
    draw.rectangle((0, 0, width, height), fill=body)
    outer_pier_width = max(12, round(width * 0.18))
    inner_pilaster_width = max(10, round(width * 0.1))
    course_height = max(40, round(height * 0.1))
    cornice_height = max(18, round(height * 0.035))
    plinth_height = max(24, round(height * 0.055))
    field_x = outer_pier_width if side == "left" else 0
    field_width = max(20, width - outer_pier_width)
    field_right = field_x + field_width
    inner_pilaster_x = field_right - inner_pilaster_width if side == "left" else field_x
    face_left = field_x + 8 if side == "left" else field_x + inner_pilaster_width + 8
    face_width = max(16, field_width - inner_pilaster_width - 16)
    face_top = cornice_height + 12
    face_bottom = height - plinth_height - 12
    block_rows = max(3, (max(48, face_bottom - face_top)) // 84)
    block_cols = max(2, face_width // 46)
    if side == "left":
        draw.rectangle((0, 0, outer_pier_width, height), fill=seam)
    else:
        draw.rectangle((width - outer_pier_width, 0, width, height), fill=seam)
    draw.rectangle((inner_pilaster_x, cornice_height, inner_pilaster_x + inner_pilaster_width, max(32, height - plinth_height)), fill=seam)
    for line_y in range(cornice_height + 12, max(cornice_height + 13, height - plinth_height - 16), course_height):
        draw.rectangle((4, line_y, max(12, width - 4), line_y + 3), fill=(92, 104, 116, 36))
    draw.rectangle((0, 0, width, cornice_height), fill=seam)
    draw.rectangle((4, 6, max(12, width - 4), 10), fill=(100, 112, 126, 72))
    draw.rectangle((0, height - plinth_height, width, height), fill=seam)
    draw.rectangle((0, height - plinth_height, width, min(height, height + plinth_height)), fill=base_bond)
    draw.rectangle((face_left, face_top, face_left + face_width, max(face_top + 48, face_bottom)), fill=face)
    draw.rectangle((face_left, face_top, face_left + face_width, max(face_top + 48, face_bottom)), outline=(104, 116, 130, 88), width=3)
    for row in range(block_rows):
        row_y = face_top + round((row * (face_bottom - face_top)) / block_rows)
        row_bottom = face_top + round(((row + 1) * (face_bottom - face_top)) / block_rows)
        row_height = max(14, row_bottom - row_y)
        offset = 0 if row % 2 == 0 else round((face_width / max(2, block_cols)) * 0.5)
        block_width = max(24, round(face_width / max(2, block_cols)))
        cursor = face_left - offset
        while cursor < face_left + face_width:
            block_left = max(face_left, cursor)
            block_right = min(face_left + face_width, cursor + block_width)
            if block_right - block_left >= 12:
                draw.rectangle((block_left + 1, row_y + 1, max(block_left + 10, block_right - 2), max(row_y + 10, row_y + row_height - 2)), fill=relief)
                draw.rectangle((block_left + 1, row_y + 1, max(block_left + 10, block_right - 2), max(row_y + 10, row_y + row_height - 2)), outline=(104, 116, 130, 48), width=1)
            cursor += block_width
    wedge_bottom = height - 1
    if side == "left":
        draw.polygon([(0, height - plinth_height), (max(18, outer_pier_width + 10), height - plinth_height), (0, wedge_bottom)], fill=(12, 16, 20, 120))
    else:
        draw.polygon([(width - 1, height - plinth_height), (width - max(18, outer_pier_width + 10), height - plinth_height), (width - 1, wedge_bottom)], fill=(12, 16, 20, 120))
    return sprite


def _composite_runtime_asset_sprite(item: Dict[str, Any], asset_path: Path, room: Optional[Dict[str, Any]] = None) -> Optional[Tuple[Image.Image, Tuple[int, int]]]:
    try:
        sprite = Image.open(asset_path).convert("RGBA")
    except Exception:
        return None
    placement = item.get("placement") if isinstance(item.get("placement"), dict) else {}
    x, y, display_width, display_height = _placement_bounds(placement)
    component_type = str(item.get("component_type") or "")
    if room and component_type in {
        "background_far_plate",
        "background_plate",
        "midground_side_frame",
        "midground_frame",
        "room_shell_foreground",
    }:
        chamber_x, chamber_y, chamber_width, chamber_height = _chamber_sprite_bounds(room)
        sprite = sprite.resize((chamber_width, chamber_height), Image.Resampling.LANCZOS)
        if component_type in {"background_far_plate", "background_plate", "midground_side_frame", "midground_frame"}:
            sprite = _apply_room_polygon_opening_mask(sprite, room, (chamber_x, chamber_y))
        sprite = _apply_runtime_review_layer_alpha(sprite, component_type)
        return sprite, (chamber_x, chamber_y)
    if room and component_type == "ceiling_band":
        chamber_x, chamber_y, chamber_width, _chamber_height = _chamber_sprite_bounds(room)
        final_width = chamber_width
        final_height = max(64, min(display_height, sprite.size[1]))
        sprite = sprite.resize((final_width, final_height), Image.Resampling.LANCZOS)
        # Opaque slab aligned to chamber top — vertical alpha fade + y offset made the cap read as a
        # composite wash over the background instead of structural masonry (runtime Phaser never used this).
        return sprite, (chamber_x, chamber_y)
    if component_type == "main_floor_top":
        final_height = max(24, int(round(max(display_height, sprite.size[1]) * 0.45)))
        final_width = display_width
        sprite = sprite.resize((final_width, final_height), Image.Resampling.LANCZOS)
        x = int(round((x + (display_width / 2)) - (final_width / 2)))
        y = int(round((float(placement.get("y") or 0)) - (final_height * 0.68)))
        return sprite, (x, y)
    if component_type == "hero_platform_top":
        final_height = max(20, int(round(max(display_height, sprite.size[1]) * 0.4)))
        final_width = display_width
        sprite = sprite.resize((final_width, final_height), Image.Resampling.LANCZOS)
        x = int(round((x + (display_width / 2)) - (final_width / 2)))
        y = int(round((float(placement.get("y") or 0)) - (final_height * 0.68)))
        return sprite, (x, y)
    if component_type == "main_floor_face" and room:
        bounds = _primary_floor_band_bounds(room)
        if bounds:
            floor_x, floor_y, floor_width, floor_height = bounds
            face_height = min(floor_height, max(sprite.size[1], int(round(floor_height * 0.42))))
            sprite = sprite.resize((floor_width, face_height), Image.Resampling.LANCZOS)
            return sprite, (floor_x, floor_y)
    if room and component_type in {"wall_module_left", "wall_module_right"}:
        bounds = _wall_shell_bounds(component_type, placement, room)
        if bounds:
            shell_x, shell_y, shell_width, shell_height = bounds
            sprite = sprite.resize((shell_width, shell_height), Image.Resampling.LANCZOS)
            return sprite, (shell_x, shell_y)
    if display_width > 0 and display_height > 0 and sprite.size != (display_width, display_height):
        sprite = sprite.resize((display_width, display_height), Image.Resampling.LANCZOS)
    return sprite, (x, y)


def _composite_runtime_review_image(
    room: Dict[str, Any],
    assets: Dict[str, Any],
    output_path: Path,
) -> None:
    geometry = _room_geometry(room)
    width = int(geometry.get("width") or 1600)
    height = int(geometry.get("height") or 1200)
    canvas = Image.new("RGBA", (width, height), (10, 14, 18, 255))
    floor_y = int(height * 0.78)
    bg = Image.new("RGBA", (width, height), (18, 24, 30, 255))
    bg_draw = ImageDraw.Draw(bg)
    def draw_masonry_panel(box: Tuple[int, int, int, int], *, base_fill: Tuple[int, int, int, int], block_w: int, block_h: int, seam: Tuple[int, int, int, int]) -> None:
        left, top, right, bottom = box
        bg_draw.rectangle(box, fill=base_fill)
        row = 0
        y = top
        while y < bottom:
            current_h = min(block_h, bottom - y)
            offset = 0 if row % 2 == 0 else block_w // 2
            x = left - offset
            while x < right:
                seg_left = max(left, x)
                seg_right = min(right, x + block_w)
                if seg_right > seg_left:
                    bg_draw.rectangle((seg_left, y, seg_right, y + current_h), outline=seam, width=2)
                x += block_w
            y += current_h
            row += 1
    for y in range(height):
        tone = int(18 + ((y / max(1, height - 1)) * 30))
        bg_draw.line((0, y, width, y), fill=(tone, tone + 6, tone + 10, 255))
    canvas.alpha_composite(bg)
    chamber_left = int(round(float(geometry.get("left") or 0.0)))
    chamber_right = int(round(float(geometry.get("right") or width)))
    chamber_top = int(round(float(geometry.get("top") or 64.0)))
    chamber_bottom = int(round(float(geometry.get("bottom") or floor_y)))
    has_unified_shell = any(
        isinstance(item, dict) and str(item.get("component_type") or "") == "room_shell_foreground"
        for item in assets.values()
    )
    side_mass_top = min(max(32, chamber_top), max(32, floor_y - 160))
    side_mass_bottom = max(side_mass_top + 128, chamber_bottom)
    left_mass_width = max(0, chamber_left)
    right_mass_width = max(0, width - chamber_right)
    if not has_unified_shell and left_mass_width >= 24:
        draw_masonry_panel((0, side_mass_top, chamber_left, side_mass_bottom), base_fill=(10, 12, 16, 214), block_w=max(36, left_mass_width // 2), block_h=72, seam=(22, 26, 30, 180))
    if not has_unified_shell and right_mass_width >= 24:
        draw_masonry_panel((chamber_right, side_mass_top, width, side_mass_bottom), base_fill=(10, 12, 16, 214), block_w=max(36, right_mass_width // 2), block_h=72, seam=(22, 26, 30, 180))
    floor_support = _primary_floor_band_bounds(room)
    if floor_support and not has_unified_shell:
        support_x, support_y, support_width, support_height = floor_support
        draw_masonry_panel(
            (support_x, support_y, support_x + support_width, min(height, support_y + support_height)),
            base_fill=(18, 22, 26, 226),
            block_w=max(84, int(round(support_width * 0.09))),
            block_h=max(32, int(round(support_height * 0.24))),
            seam=(26, 30, 36, 190),
        )
    runtime_visible_component_types = {
        "background_far_plate",
        "background_plate",
        "ceiling_band",
        "room_shell_foreground",
        "wall_module_left",
        "wall_module_right",
        "wall_base_trim_left",
        "wall_base_trim_right",
        "main_floor_top",
        "main_floor_face",
        "hero_platform_top",
        "hero_platform_face",
        "door_frame",
        "door_piece",
        "pit_rim",
        "pit_interior",
    }
    if not RUNTIME_REVIEW_DISABLE_MIDGROUND:
        runtime_visible_component_types.update({"midground_side_frame", "midground_frame"})
    _review_layer_order = {
        "background": 0,
        "ceiling": 1,
        "walls": 2,
        "midground": 3,
        "foreground": 3.5,
        "floor": 4,
        "platforms": 5,
        "doors": 6,
        "pits": 7,
    }
    sorted_assets = sorted(
        [
            item
            for item in assets.values()
            if isinstance(item, dict)
            and item.get("url")
            and str(item.get("component_type") or "") in runtime_visible_component_types
        ],
        key=lambda item: _review_layer_order.get(str(item.get("slot_group") or "misc"), 8),
    )
    for item in sorted_assets:
        rel_url = str(item.get("url") or "").lstrip("/")
        asset_path = ROOT / rel_url
        if not asset_path.exists():
            continue
        composed = _composite_runtime_asset_sprite(item, asset_path, room)
        if not composed:
            continue
        sprite, (x, y) = composed
        canvas.alpha_composite(sprite, (x, y))
    occlusion = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    occlusion_draw = ImageDraw.Draw(occlusion)
    if left_mass_width >= 24:
        occlusion_draw.rectangle((0, 0, chamber_left, height), fill=(10, 12, 16, 236))
    if right_mass_width >= 24:
        occlusion_draw.rectangle((chamber_right, 0, width, height), fill=(10, 12, 16, 236))
    if chamber_bottom < height:
        occlusion_draw.rectangle((chamber_left, chamber_bottom, chamber_right, height), fill=(14, 18, 22, 236))
    canvas.alpha_composite(occlusion)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle((0, floor_y, width, height), fill=(10, 12, 16, 24))
    canvas.alpha_composite(overlay)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def _image_region_luminance(img: Image.Image, box: Tuple[float, float, float, float]) -> float:
    rgb = img.convert("RGB")
    w, h = rgb.size
    left = max(0, min(w, int(w * box[0])))
    top = max(0, min(h, int(h * box[1])))
    right = max(left + 1, min(w, int(w * box[2])))
    bottom = max(top + 1, min(h, int(h * box[3])))
    region = rgb.crop((left, top, right, bottom)).resize((48, 48), Image.Resampling.LANCZOS)
    pixels = list(region.getdata())
    if not pixels:
        return 0.0
    return sum((0.2126 * r) + (0.7152 * g) + (0.0722 * b) for r, g, b in pixels) / len(pixels)


def _image_region_contrast(img: Image.Image, box: Tuple[float, float, float, float]) -> float:
    rgb = img.convert("RGB")
    w, h = rgb.size
    left = max(0, min(w, int(w * box[0])))
    top = max(0, min(h, int(h * box[1])))
    right = max(left + 1, min(w, int(w * box[2])))
    bottom = max(top + 1, min(h, int(h * box[3])))
    region = rgb.crop((left, top, right, bottom)).resize((48, 48), Image.Resampling.LANCZOS).convert("L")
    pixels = list(region.getdata())
    if not pixels:
        return 0.0
    width, height = region.size
    total = 0.0
    count = 0
    for y in range(height):
        for x in range(width):
            idx = y * width + x
            value = pixels[idx]
            if x + 1 < width:
                total += abs(value - pixels[idx + 1])
                count += 1
            if y + 1 < height:
                total += abs(value - pixels[idx + width])
                count += 1
    return (total / max(1, count)) / 255.0


def _side_wall_inner_boundary_position(
    img: Image.Image,
    vertical_span: Tuple[float, float],
    *,
    mirrored: bool = False,
    search_span: Tuple[float, float] = (0.08, 0.24),
) -> float:
    gray = img.convert("L")
    if mirrored:
        gray = gray.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    width, height = gray.size
    top = max(0, min(height - 1, int(height * vertical_span[0])))
    bottom = max(top + 1, min(height, int(height * vertical_span[1])))
    crop = gray.crop((0, top, width, bottom))
    pixels = crop.load()
    search_left = max(1, int(width * search_span[0]))
    search_right = max(search_left + 2, int(width * search_span[1]))
    strongest_index = search_left
    strongest_delta = -1.0
    for x in range(search_left, min(search_right, crop.size[0] - 2)):
        left_total = 0
        right_total = 0
        count = 0
        for y in range(crop.size[1]):
            left_total += pixels[x, y]
            right_total += pixels[x + 1, y]
            count += 1
        if count <= 0:
            continue
        delta = abs((right_total / count) - (left_total / count))
        if delta > strongest_delta:
            strongest_delta = delta
            strongest_index = x
    return strongest_index / float(width)


def _runtime_review_metrics(screenshot_path: Path, assets: Dict[str, Any]) -> Dict[str, float]:
    img = Image.open(screenshot_path).convert("RGBA")
    center = _image_region_luminance(img, (0.34, 0.18, 0.66, 0.82))
    left = _image_region_luminance(img, (0.0, 0.18, 0.28, 0.82))
    right = _image_region_luminance(img, (0.72, 0.18, 1.0, 0.82))
    top_band = _image_region_luminance(img, (0.18, 0.0, 0.82, 0.14))
    upper_chamber = _image_region_luminance(img, (0.22, 0.16, 0.78, 0.3))
    center_contrast = _image_region_contrast(img, (0.34, 0.18, 0.66, 0.82))
    center_upper_contrast = _image_region_contrast(img, (0.34, 0.16, 0.66, 0.46))
    center_lower_contrast = _image_region_contrast(img, (0.34, 0.56, 0.66, 0.84))
    top_band_contrast = _image_region_contrast(img, (0.18, 0.0, 0.82, 0.14))
    floor_band = _image_region_luminance(img, (0.18, 0.74, 0.82, 0.9))
    upper_band = _image_region_luminance(img, (0.18, 0.54, 0.82, 0.7))
    side_shell_definition = (
        _image_region_contrast(img, (0.04, 0.18, 0.2, 0.82)) +
        _image_region_contrast(img, (0.8, 0.18, 0.96, 0.82))
    ) / 2.0
    platform_scores: List[float] = []
    threshold_scores: List[float] = []
    for asset in assets.values():
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        component_type = str(asset.get("component_type") or "")
        placement = asset.get("placement") if isinstance(asset.get("placement"), dict) else {}
        x, y, width, height = _placement_bounds(placement)
        if width <= 0 or height <= 0:
            continue
        img_w, img_h = img.size
        box = (
            max(0, x) / img_w,
            max(0, y) / img_h,
            min(img_w, x + width) / img_w,
            min(img_h, y + height) / img_h,
        )
        if component_type in {"main_floor_top", "hero_platform_top"}:
            top_lum = _image_region_luminance(img, (box[0], box[1], box[2], min(box[3], box[1] + ((box[3] - box[1]) * 0.22))))
            face_lum = _image_region_luminance(img, (box[0], min(box[3], box[1] + ((box[3] - box[1]) * 0.28)), box[2], box[3]))
            platform_scores.append(abs(top_lum - face_lum) / 255.0)
        if component_type == "door_frame":
            center_box = (
                box[0] + ((box[2] - box[0]) * 0.34),
                box[1] + ((box[3] - box[1]) * 0.22),
                box[0] + ((box[2] - box[0]) * 0.66),
                box[1] + ((box[3] - box[1]) * 0.78),
            )
            opening = _image_region_luminance(img, center_box)
            frame = (_image_region_luminance(img, (box[0], box[1], box[0] + ((box[2] - box[0]) * 0.22), box[3])) + _image_region_luminance(img, (box[2] - ((box[2] - box[0]) * 0.22), box[1], box[2], box[3]))) / 2.0
            threshold_scores.append(abs(frame - opening) / 255.0)
    return {
        "center_clutter": center_contrast,
        "center_upper_contrast": center_upper_contrast,
        "center_lower_contrast": center_lower_contrast,
        "left_right_balance": abs(left - right) / 255.0,
        "side_shell_definition": side_shell_definition,
        "floor_background_separation": abs(floor_band - upper_band) / 255.0,
        "top_band_darkness": max(0.0, (upper_chamber - top_band) / 255.0),
        "top_band_contrast": top_band_contrast,
        "platform_top_readability": sum(platform_scores) / len(platform_scores) if platform_scores else 0.0,
        "threshold_visibility": sum(threshold_scores) / len(threshold_scores) if threshold_scores else 0.0,
        "platform_sample_count": float(len(platform_scores)),
        "door_sample_count": float(len(threshold_scores)),
    }


def _find_headless_browser() -> Optional[str]:
    candidates = [
        os.environ.get("ROOM_ENVIRONMENT_REVIEW_BROWSER"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _capture_runtime_review_screenshot(
    project: Dict[str, Any],
    room_id: str,
    assets: Dict[str, Any],
    output_path: Path,
) -> Tuple[str, Optional[str]]:
    browser_pref = str(os.environ.get("ROOM_ENVIRONMENT_REVIEW_USE_BROWSER") or "").strip().lower()
    if browser_pref in {"0", "false", "no"}:
        room = _find_room(project, room_id)
        _composite_runtime_review_image(room, assets, output_path)
        return "composite_fallback", "headless_browser_disabled_by_config"
    browser = _find_headless_browser()
    base_url = str(os.environ.get("ROOM_ENVIRONMENT_REVIEW_BASE_URL") or "http://127.0.0.1:8766/index.html").strip()
    room = _find_room(project, room_id)
    geometry = _room_geometry(room)
    # Match index.html applyRuntimeReviewCaptureViewport: internal game size is the footprint chamber,
    # not the full room slot. A mismatched window + Phaser Scale.FIT letterboxes (often a black top band).
    room_w = int(geometry.get("width") or 1600)
    room_h = int(geometry.get("height") or 1200)
    try:
        cw = float(geometry.get("chamber_width") or room_w)
        ch = float(geometry.get("chamber_height") or room_h)
    except (TypeError, ValueError):
        cw, ch = float(room_w), float(room_h)
    width = max(800, int(round(cw)))
    height = max(400, int(round(ch)))
    if browser:
        try:
            target = _write_runtime_review_capture_page(project, room_id, base_url, output_path)
            screenshot_arg = str(output_path)
            run_cwd: Optional[str] = None
            try:
                screenshot_arg = str(output_path.relative_to(ROOT))
                run_cwd = str(ROOT)
            except Exception:
                screenshot_arg = str(output_path)
            capture_helper = ROOT / "scripts" / "capture_runtime_review.js"
            node_binary = shutil.which("node")
            if node_binary and capture_helper.exists():
                helper_arg = str(capture_helper)
                if run_cwd:
                    try:
                        helper_arg = str(capture_helper.relative_to(ROOT))
                    except Exception:
                        helper_arg = str(capture_helper)
                cmd = [
                    node_binary,
                    helper_arg,
                    "--browser",
                    browser,
                    "--url",
                    target,
                    "--output",
                    screenshot_arg,
                    "--width",
                    str(width),
                    "--height",
                    str(height),
                    "--timeout",
                    "30000",
                ]
            else:
                cmd = [
                    browser,
                    "--headless=new",
                    "--disable-gpu",
                    f"--window-size={width},{height}",
                    f"--screenshot={screenshot_arg}",
                    "--hide-scrollbars",
                    "--virtual-time-budget=20000",
                    target,
                ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, cwd=run_cwd)
            if output_path.exists() and _runtime_review_capture_is_usable(output_path):
                return "headless_browser", None
            if output_path.exists():
                output_path.unlink()
            browser_error = "headless_browser_invalid_frame"
        except Exception as exc:
            browser_error = f"headless_browser_failed:{type(exc).__name__}"
        else:
            browser_error = "headless_browser_failed"
    else:
        browser_error = "headless_browser_unavailable"
    _composite_runtime_review_image(room, assets, output_path)
    return "composite_fallback", browser_error


def _runtime_review_capture_is_usable(image_path: Path) -> bool:
    try:
        with Image.open(image_path) as image:
            grayscale = image.convert("L")
            stat = grayscale.getextrema()
            if not stat:
                return False
            minimum, maximum = stat
            if maximum <= 8:
                return False
            if (maximum - minimum) < 6:
                return False
            histogram = grayscale.histogram()
            total_pixels = max(1, grayscale.size[0] * grayscale.size[1])
            dark_pixels = sum(histogram[:12])
            non_dark_fraction = 1.0 - (dark_pixels / total_pixels)
            return non_dark_fraction >= 0.03
    except Exception:
        return False


def _write_runtime_review_capture_page(
    project: Dict[str, Any],
    room_id: str,
    base_url: str,
    output_path: Path,
) -> str:
    parsed = urllib.parse.urlparse(base_url)
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or "127.0.0.1:8766"
    # Runtime preview messaging is implemented by the repo-root game page.
    # Force the wrapper iframe to target that preview surface so we do not
    # accidentally capture the Sprite Workbench or editor shell UI.
    game_path = "/index.html"
    game_url = urllib.parse.urlunparse((scheme, netloc, game_path, "", "", ""))
    review_root = output_path.parent
    review_root.mkdir(parents=True, exist_ok=True)
    layout_path = review_root / "runtime-layout.json"
    layout_data = project.get("room_layout") or project
    layout_path.write_text(json.dumps(layout_data, separators=(",", ":")), encoding="utf-8")
    layout_url = f"{scheme}://{netloc}/tools/2d-sprite-and-animation/projects-data/{project.get('project_id')}/room_environment_assets/{room_id}/review/runtime-layout.json"
    iframe_src = (
        f"{game_url}#preview=embed&capture=runtime-review&layout_url={urllib.parse.quote(layout_url, safe='')}"
        f"&start={urllib.parse.quote(room_id, safe='')}"
    )
    capture_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Runtime Capture</title>
  <style>
    html, body {{
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #000;
    }}
    iframe {{
      border: 0;
      width: 100vw;
      height: 100vh;
      display: block;
      background: #000;
    }}
  </style>
</head>
<body>
  <iframe id="preview" src="{iframe_src}"></iframe>
</body>
</html>
"""
    capture_page = review_root / "runtime-capture.html"
    capture_page.write_text(capture_html, encoding="utf-8")
    return f"{scheme}://{netloc}/tools/2d-sprite-and-animation/projects-data/{project.get('project_id')}/room_environment_assets/{room_id}/review/runtime-capture.html"


def _run_runtime_review(
    project: Dict[str, Any],
    project_id: str,
    room_id: str,
    assets: Dict[str, Any],
) -> Dict[str, Any]:
    review_root = PROJECTS_ROOT / project_id / "room_environment_assets" / room_id / "review"
    screenshot_path = review_root / "runtime-review.png"
    review_mode, capture_issue = _capture_runtime_review_screenshot(project, room_id, assets, screenshot_path)
    metrics = _runtime_review_metrics(screenshot_path, assets)
    fail_reasons: List[str] = []
    warning_reasons: List[str] = []
    if review_mode != "headless_browser":
        fail_reasons.append("browser_capture_required")
    if metrics["center_clutter"] > 0.08:
        fail_reasons.append("center_clutter_too_high")
    if (
        metrics["center_clutter"] < 0.01
        and metrics["center_upper_contrast"] < 0.0025
        and metrics["center_lower_contrast"] < 0.01
        and metrics["floor_background_separation"] < 0.06
    ):
        fail_reasons.append("room_shell_readability_low")
    if metrics["left_right_balance"] > 0.18:
        fail_reasons.append("left_right_balance_off")
    if metrics["top_band_darkness"] > 0.08 and metrics["top_band_contrast"] < 0.015:
        fail_reasons.append("top_occlusion_slab_present")
    # Low floor/background separation alone should be surfaced, but it should not
    # block showing the generated kit unless it combines with an over-suppressed,
    # unreadable center lane.
    if metrics["floor_background_separation"] < 0.035:
        warning_reasons.append("floor_background_separation_low")
    if metrics["platform_sample_count"] > 0 and metrics["platform_top_readability"] < 0.003:
        fail_reasons.append("platform_top_readability_low")
    if metrics["door_sample_count"] > 0 and metrics["threshold_visibility"] < 0.03:
        fail_reasons.append("threshold_visibility_low")
    for asset in assets.values():
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        component_type = str(asset.get("component_type") or "")
        generation_source = str(asset.get("generation_source") or "")
        if component_type not in {"background_far_plate", "midground_side_frame"}:
            continue
        if generation_source.startswith("restored_from_") or generation_source in {"fallback_template", "failed"}:
            fail_reasons.append("scenic_layers_noncanonical")
            break
    return {
        "status": "pass" if not fail_reasons else "fail",
        "review_mode": review_mode,
        "capture_issue": capture_issue,
        "screenshot_url": f"/tools/2d-sprite-and-animation/projects-data/{project_id}/room_environment_assets/{room_id}/review/runtime-review.png",
        "screenshot_path": screenshot_path.as_posix(),
        "metrics": metrics,
        "fail_reasons": fail_reasons,
        "warning_reasons": warning_reasons,
        "generated_at": now_iso(),
    }


def generate_room_environment_asset_pack(project_id: str, room_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
    preview = env["preview"]
    spec = env["spec"]
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    direction = _attach_default_biome_pack(project, direction)
    payload = dict(payload or {})
    slot_filter = str(payload.get("slot_id") or "").strip()
    iterate_from_current = bool(payload.get("iterate_from_current"))
    if iterate_from_current and not slot_filter:
        raise ValueError("iterate_from_current requires slot_id.")
    preview_id = str(payload.get("preview_id") or preview.get("approved_image_id") or "").strip()
    if not preview_id:
        raise ValueError("Approve a room preview before generating production assets.")
    approved = next((item for item in (preview.get("images") or []) if item.get("preview_id") == preview_id), None)
    if not approved:
        raise ValueError("Approved preview not found.")
    biome_pack = _select_biome_pack(direction)
    if not biome_pack:
        raise ValueError("No biome template pack is available for this project.")
    project_dir = PROJECTS_ROOT / project_id
    preview_path = _project_url_to_path(project_dir, str(approved.get("url") or ""))
    if preview_path is None or not preview_path.exists():
        raise ValueError("Approved preview image is missing on disk.")
    geometry = _room_geometry(room)
    schema_validation = _validate_component_schemas(room, spec, geometry)
    if not schema_validation["valid"]:
        env["runtime"]["bespoke_asset_manifest"] = {
            "schema_version": 2,
            "status": "failed",
            "biome_id": biome_pack.get("biome_id"),
            "border_first_contract": copy.deepcopy(biome_pack.get("border_first_contract") or _normalize_border_first_contract(None)),
            "next_generation_contract": _border_first_generation_contract(),
            "source_preview_id": preview_id,
            "generation_plan": [],
            "required_slots": [],
            "built_slots": [],
            "slot_groups": {},
            "schema_validation": schema_validation,
            "runtime_review": {"status": "blocked", "fail_reasons": ["schema_validation_failed"], "metrics": {}, "screenshot_url": None, "review_mode": None},
            "review": {"status": "blocked", "fail_reasons": ["schema_validation_failed"], "metrics": {}, "screenshot_url": None, "review_mode": None},
            "structural_review_bundle": {},
            "assets": {},
            "failed_assets": [],
            "used_ai": False,
            "generated_at": now_iso(),
            "validation_errors": list(schema_validation["errors"]),
        }
        env["runtime"]["status"] = "blocked"
        env["runtime"]["source"] = "schema_validation_failed"
        env["runtime"]["applied_preview_id"] = None
        project["updated_at"] = now_iso()
        save_project(project)
        return {
            "ok": True,
            "environment": copy.deepcopy(env),
            "asset_pack": copy.deepcopy(env["runtime"]["bespoke_asset_manifest"]),
        }
    asset_root = project_dir / "room_environment_assets" / room_id / "bespoke"
    asset_root.mkdir(parents=True, exist_ok=True)
    reference_root = asset_root / "_refs"
    reference_root.mkdir(parents=True, exist_ok=True)
    frozen_refs: List[Path] = []
    for frozen in (direction.get("frozen_concepts") or [])[:3]:
        rel = str(frozen.get("image_path") or "").strip()
        frozen_path = project_dir / rel if rel else None
        if frozen_path and frozen_path.exists():
            frozen_refs.append(frozen_path)
    pipeline_version = envv3.normalize_pipeline_version(env.get("environment_pipeline_version"))
    if pipeline_version == envv3.V3_PIPELINE_VERSION:
        planner_output = envv3.build_generation_plan(room, preview_id, biome_pack, now_iso())
        plan = planner_output["plan"]
        env["assembly_plan"] = copy.deepcopy(planner_output["assembly_plan"])
    else:
        plan = _room_component_plan(room, preview_id, biome_pack)
    full_plan = list(plan)
    if slot_filter:
        prev_manifest = env["runtime"].get("bespoke_asset_manifest") or {}
        prev_assets = prev_manifest.get("assets")
        if not isinstance(prev_assets, dict) or not prev_assets:
            raise ValueError("Generate the full room asset kit before regenerating individual slots.")
        filtered_plan = [e for e in full_plan if str(e.get("slot_id") or "") == slot_filter]
        if not filtered_plan:
            raise ValueError("Unknown slot_id for this room's generation plan.")
        plan = filtered_plan
        assets = copy.deepcopy(prev_assets)
    else:
        assets = {}
    failed_assets: List[str] = []
    validation_errors: List[str] = []
    used_ai = False
    template_library = {str(item.get("template_id") or ""): item for item in (biome_pack.get("template_library") or []) if isinstance(item, dict)}
    for entry in plan:
        template = template_library.get(str(entry.get("source_template_id") or ""))
        if not template:
            validation_errors.append(f"{entry.get('slot_id')}:missing_template")
            continue
        rel_path = str(template.get("image_path") or "").strip()
        template_path = project_dir / rel_path if rel_path else None
        if not template_path or not template_path.exists():
            validation_errors.append(f"{entry.get('slot_id')}:missing_template_image")
            continue
        output_name = f"{entry['slot_id']}.png"
        output_path = asset_root / output_name
        base_prompt = _build_bespoke_prompt(direction, spec, entry, template, room_geometry=_room_geometry(room))
        expected_size = (int(entry["target_dimensions"]["width"]), int(entry["target_dimensions"]["height"]))
        transparent = str(entry.get("transparency_mode") or template.get("transparency_mode") or "opaque") == "alpha"
        component_type = str(entry.get("component_type") or "")
        bespoke_validation_tm = str(entry.get("transparency_mode") or template.get("transparency_mode") or "opaque")
        if component_type == "room_shell_foreground":
            bespoke_validation_tm = "opaque"
        adaptation_mode = _component_adaptation_mode(component_type) if component_type in V2_SLOT_SPEC_BY_TYPE else str(template.get("adaptation_mode") or _component_adaptation_mode(component_type))
        if iterate_from_current and adaptation_mode in {"direct", "stretch"}:
            raise ValueError(
                "iterate_from_current is not supported for template-only slots; use Regenerate instead."
            )
        generation_source = "template"
        attempt_records: List[Dict[str, Any]] = []
        direct_validation_reference = template_path
        if adaptation_mode in {"direct", "stretch"} and component_type in {"background_far_plate", "midground_side_frame"}:
            _bespoke_reference_images_for_component(
                component_type,
                template_path,
                preview_path,
                frozen_refs,
                reference_root,
                expected_size,
                transparent,
                room=room,
            )
        if adaptation_mode in {"direct", "stretch"}:
            generated = _render_bespoke_component_from_template(
                template_path,
                output_path,
                expected_size,
                transparent,
                component_type,
            )
        else:
            refs_for_job = _bespoke_reference_images_for_component(
                component_type,
                template_path,
                preview_path,
                frozen_refs,
                reference_root,
                expected_size,
                transparent,
                room=room,
            )
            iteration_source_path: Optional[Path] = None
            prompt = base_prompt
            if iterate_from_current:
                prior_asset = assets.get(entry["slot_id"])
                if isinstance(prior_asset, dict) and prior_asset.get("url"):
                    iteration_source_path = _project_url_to_path(project_dir, str(prior_asset["url"]))
                if iteration_source_path and iteration_source_path.exists():
                    refs_for_job = _prefix_iteration_reference_refs(
                        refs_for_job,
                        iteration_source_path,
                        component_type=component_type,
                    )
                    prompt = (
                        f"{base_prompt}\n\n"
                        "Iteration note: one reference image is this slot's current production asset. "
                        "Refine it in place—same role, shell topology, and transparency—using the contract map, structural guide, and material reference for geometry, band continuity, and material alignment."
                    )
            validation_reference_path = _validation_reference_for_component(component_type, template_path, refs_for_job)
            attempt_prompt = prompt
            generated = False
            valid = False
            errors: List[str] = []
            for attempt_index in range(3):
                attempt_info = {
                    "attempt": attempt_index + 1,
                    "component_type": component_type,
                    "reference_images": [str(path) for path in refs_for_job],
                    "prompt": attempt_prompt,
                }
                if component_type == "room_shell_foreground":
                    shell_roles: List[str] = []
                    for idx, _ref in enumerate(refs_for_job):
                        if idx == 0:
                            shell_roles.append("contract_map")
                        elif idx == 1:
                            shell_roles.append("shell_guide")
                        elif idx == 2:
                            shell_roles.append("material_reference")
                        else:
                            shell_roles.append("auxiliary_reference")
                    attempt_info["reference_roles"] = shell_roles
                    attempt_info["guide_kind"] = "room_shell_reference_guide"
                generated, gen_detail = _generate_bespoke_component_from_references(
                    output_path,
                    attempt_prompt,
                    refs_for_job,
                    expected_size,
                    transparent,
                    component_type,
                )
                if generated:
                    used_ai = True
                    generation_source = "ai"
                if not generated:
                    errors = ["generation_failed"]
                    if gen_detail:
                        attempt_info["gemini_error"] = gen_detail
                        errors.append(gen_detail)
                    attempt_info["status"] = "generation_failed"
                    attempt_info["validation_errors"] = list(errors)
                    attempt_records.append(attempt_info)
                    retry_prompt = _retry_prompt_for_validation_errors(component_type, attempt_prompt, errors, attempt_index)
                    if output_path.exists():
                        output_path.unlink()
                    if not retry_prompt:
                        break
                    attempt_prompt = retry_prompt
                    refs_for_job = _retry_reference_images_for_component(
                        component_type,
                        template_path,
                        preview_path,
                        frozen_refs,
                        reference_root,
                        expected_size,
                        transparent,
                        room=room,
                    )
                    if iteration_source_path and iteration_source_path.exists():
                        refs_for_job = _prefix_iteration_reference_refs(
                            refs_for_job,
                            iteration_source_path,
                            component_type=component_type,
                        )
                    validation_reference_path = _validation_reference_for_component(component_type, template_path, refs_for_job)
                    continue
                valid, errors = _validate_bespoke_component(
                    output_path,
                    component_type,
                    expected_size,
                    bespoke_validation_tm,
                    validation_reference_path,
                )
                postprocessed = False
                if errors and _postprocess_component_for_validation(output_path, component_type, errors, attempt_index, template_path):
                    postprocessed = True
                    valid, errors = _validate_bespoke_component(
                        output_path,
                        component_type,
                        expected_size,
                        bespoke_validation_tm,
                        validation_reference_path,
                    )
                if component_type == "room_shell_foreground":
                    attempt_info["punchout_applied"] = False
                    if valid and not errors:
                        valid, errors = _validate_room_shell_before_punchout(
                            output_path,
                            expected_size,
                            geometry=_room_geometry(room),
                        )
                    if valid and not errors:
                        _apply_walkable_interior_punchout(output_path, _room_geometry(room))
                        valid, errors = _validate_room_shell_after_punchout(output_path, _room_geometry(room), expected_size)
                        attempt_info["punchout_applied"] = True
                attempt_info["postprocessed"] = postprocessed
                attempt_info["status"] = "pass" if valid and not errors else "validation_failed"
                attempt_info["validation_errors"] = list(errors)
                attempt_records.append(attempt_info)
                if valid and not errors:
                    break
                retry_prompt = _retry_prompt_for_validation_errors(component_type, attempt_prompt, errors, attempt_index)
                if output_path.exists():
                    output_path.unlink()
                if not retry_prompt:
                    break
                attempt_prompt = retry_prompt
                refs_for_job = _retry_reference_images_for_component(
                    component_type,
                    template_path,
                    preview_path,
                    frozen_refs,
                    reference_root,
                    expected_size,
                    transparent,
                    room=room,
                )
                if iteration_source_path and iteration_source_path.exists():
                    refs_for_job = _prefix_iteration_reference_refs(
                        refs_for_job,
                        iteration_source_path,
                        component_type=component_type,
                    )
                validation_reference_path = _validation_reference_for_component(component_type, template_path, refs_for_job)
            if generated and valid and not errors:
                pass
        if not generated:
            if output_path.exists():
                output_path.unlink()
        if adaptation_mode in {"direct", "stretch"}:
            valid, errors = _validate_bespoke_component(
                output_path,
                component_type,
                expected_size,
                str(template.get("transparency_mode") or "opaque"),
                direct_validation_reference,
            )
        if not generated:
            errors = ["generation_failed"]
        if not valid or errors:
            if output_path.exists():
                output_path.unlink()
            validation_errors.extend(f"{entry['slot_id']}:{error}" for error in errors)
            assets[entry["slot_id"]] = {
                "slot_id": entry["slot_id"],
                "component_type": entry["component_type"],
                "source_template_id": entry["source_template_id"],
                "requested_dimensions": copy.deepcopy(entry["target_dimensions"]),
                "final_dimensions": None,
                "placement": copy.deepcopy(entry["placement"]),
                "url": "",
                "transparency_mode": template.get("transparency_mode"),
                "validation": {"status": "fail", "errors": errors},
                "generation_source": "failed",
                "attempts": attempt_records,
            }
            continue
        assets[entry["slot_id"]] = {
            "slot_id": entry["slot_id"],
            "component_type": entry["component_type"],
            "source_template_id": entry["source_template_id"],
            "requested_dimensions": copy.deepcopy(entry["target_dimensions"]),
            "final_dimensions": {"width": expected_size[0], "height": expected_size[1]},
            "placement": copy.deepcopy(entry["placement"]),
            "url": f"/tools/2d-sprite-and-animation/projects-data/{project_id}/room_environment_assets/{room_id}/bespoke/{output_name}",
            "transparency_mode": entry.get("transparency_mode") or template.get("transparency_mode"),
            "schema_key": entry.get("schema_key"),
            "slot_group": entry.get("slot_group"),
            "validation": {"status": "pass", "errors": []},
            "generation_source": generation_source,
            "attempts": attempt_records,
        }
    required_slot_ids = [str(e.get("slot_id") or "") for e in full_plan if e.get("slot_id")]
    built_slots = [sid for sid in required_slot_ids if sid and isinstance(assets.get(sid), dict) and assets[sid].get("url")]
    failed_assets = [sid for sid in required_slot_ids if sid and (not isinstance(assets.get(sid), dict) or not assets[sid].get("url"))]
    used_ai = any(
        isinstance(a, dict) and str(a.get("generation_source") or "") == "ai"
        for a in assets.values()
    )
    required_ai_slots = [
        slot_id
        for slot_id, asset in assets.items()
        if (
            isinstance(asset, dict)
            and asset.get("url")
            and str(asset.get("component_type") or "") in V2_SLOT_SPEC_BY_TYPE
            and _component_adaptation_mode(str(asset.get("component_type") or "")) not in {"direct", "stretch"}
        )
    ]
    ai_generated_slots = [
        slot_id
        for slot_id, asset in assets.items()
        if isinstance(asset, dict) and asset.get("url") and str(asset.get("generation_source") or "") == "ai"
    ]
    ai_generation_missing = bool(required_ai_slots) and len(ai_generated_slots) < len(required_ai_slots)
    structural_review_bundle = _build_structural_review_bundle(project_id, room_id, project_dir, biome_pack, assets)
    provisional_manifest = {
        "schema_version": 2,
        "status": "failed",
        "biome_id": biome_pack.get("biome_id"),
        "border_first_contract": copy.deepcopy(biome_pack.get("border_first_contract") or _normalize_border_first_contract(None)),
        "next_generation_contract": _border_first_generation_contract(),
        "source_preview_id": preview_id,
        "generation_plan": copy.deepcopy(full_plan),
        "required_slots": required_slot_ids,
        "built_slots": built_slots,
        "slot_groups": _slot_groups_from_plan(full_plan, built_slots, failed_assets),
        "schema_validation": schema_validation,
        "runtime_review": {"status": "running", "fail_reasons": [], "metrics": {}, "screenshot_url": None, "review_mode": None},
        "review": {"status": "running", "fail_reasons": [], "metrics": {}, "screenshot_url": None, "review_mode": None},
        "structural_review_bundle": structural_review_bundle,
        "assets": assets,
        "failed_assets": failed_assets,
        "used_ai": used_ai,
        "generated_at": now_iso(),
        "validation_errors": list(validation_errors),
    }
    env["runtime"]["bespoke_asset_manifest"] = provisional_manifest
    runtime_review = _run_runtime_review(project, project_id, room_id, assets) if built_slots else {
        "status": "blocked",
        "review_mode": None,
        "screenshot_url": None,
        "metrics": {},
        "fail_reasons": ["no_assets_built"],
        "failed_slot_ids": list(failed_assets),
        "validation_errors": list(validation_errors),
        "generated_at": now_iso(),
    }
    if built_slots and failed_assets:
        existing_fail_reasons = list(runtime_review.get("fail_reasons") or [])
        if "slot_generation_failed" not in existing_fail_reasons:
            existing_fail_reasons.append("slot_generation_failed")
        runtime_review["fail_reasons"] = existing_fail_reasons
        runtime_review["failed_slot_ids"] = list(failed_assets)
        runtime_review["validation_errors"] = list(validation_errors)
    review_ok = runtime_review.get("status") == "pass"
    if ai_generation_missing:
        runtime_review.setdefault("warning_reasons", [])
        runtime_review["warning_reasons"] = list(runtime_review.get("warning_reasons") or [])
        runtime_review["warning_reasons"].append("ai_generation_required_for_v2_slots")
    status = (
        "ready"
        if required_slot_ids and not failed_assets and len(built_slots) == len(required_slot_ids) and review_ok and not ai_generation_missing
        else "failed"
    )
    env["runtime"]["bespoke_asset_manifest"] = {
        **provisional_manifest,
        "status": status,
        "runtime_review": runtime_review,
        "review": copy.deepcopy(runtime_review),
        "validation_errors": validation_errors + list(runtime_review.get("fail_reasons") or []) + (["ai_generation_required_for_v2_slots"] if ai_generation_missing else []),
    }
    env["runtime"]["asset_pack"] = {
        "status": "idle",
        "asset_schema_version": 3,
        "used_ai": False,
        "generated_at": None,
        "source_preview_id": None,
        "layout_fingerprint": None,
        "component_dependencies": {},
        "component_fingerprints": {},
        "stale_components": [],
        "failed_assets": [],
        "assets": {},
    }
    env["runtime"]["status"] = "ready" if status == "ready" else "blocked"
    env["runtime"]["source"] = "approved_preview" if status == "ready" else ("runtime_review_failed" if runtime_review.get("status") == "fail" else "bespoke_generation_failed")
    env["runtime"]["applied_preview_id"] = preview_id if status == "ready" else None
    _sync_v3_environment_state(project_id, env, room, biome_id=biome_pack.get("biome_id"), generated_at=now_iso())
    project["updated_at"] = now_iso()
    save_project(project)
    hist_event: Dict[str, Any] = {
        "type": "room_environment_bespoke_assets_generated",
        "room_id": room_id,
        "preview_id": preview_id,
        "used_ai": used_ai,
        "created_at": now_iso(),
    }
    if slot_filter:
        hist_event["slot_id"] = slot_filter
        hist_event["iterate_from_current"] = iterate_from_current
    append_history_event(project_id, hist_event)
    return {
        "ok": True,
        "environment": copy.deepcopy(env),
        "asset_pack": copy.deepcopy(env["runtime"]["bespoke_asset_manifest"]),
    }


def approve_room_environment_preview(project_id: str, room_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
    helpfulness = _ensure_room_ai_helpfulness(env)
    preview_id = str(payload.get("preview_id") or "").strip()
    if not preview_id:
        raise ValueError("preview_id is required.")
    found = next((item for item in (env["preview"].get("images") or []) if item.get("preview_id") == preview_id), None)
    if not found:
        raise ValueError("Preview not found.")
    env["preview"]["approved_image_id"] = preview_id
    env["preview"]["approved_palette"] = copy.deepcopy(found.get("palette"))
    env["preview"]["status"] = "approved"
    env["runtime"]["status"] = "ready"
    env["runtime"]["source"] = "approved_preview"
    env["runtime"]["applied_preview_id"] = preview_id
    env["runtime"]["surface_palette"] = copy.deepcopy(found.get("palette"))
    env["runtime"]["material_keywords"] = list(env["spec"].get("materials") or [])
    env["runtime"]["lighting_mode"] = str(env["spec"].get("lighting") or "")
    env["runtime"]["last_applied_at"] = now_iso()
    bespoke_manifest = env["runtime"]["bespoke_asset_manifest"]
    direction = _attach_default_biome_pack(project, normalize_art_direction(project.get("art_direction"), project.get("art_direction")))
    biome_pack = _select_biome_pack(direction)
    bespoke_manifest["biome_id"] = (biome_pack or {}).get("biome_id")
    bespoke_manifest["source_preview_id"] = preview_id
    bespoke_manifest["schema_validation"] = _validate_component_schemas(room, env["spec"], _room_geometry(room))
    bespoke_manifest["runtime_review"] = {"status": "idle", "fail_reasons": [], "metrics": {}, "screenshot_url": None, "review_mode": None}
    bespoke_manifest["review"] = copy.deepcopy(bespoke_manifest["runtime_review"])
    if envv3.normalize_pipeline_version(env.get("environment_pipeline_version")) == envv3.V3_PIPELINE_VERSION and biome_pack:
        planner_output = envv3.build_generation_plan(room, preview_id, biome_pack, now_iso())
        env["assembly_plan"] = copy.deepcopy(planner_output["assembly_plan"])
    _sync_v3_environment_state(project_id, env, room, biome_id=bespoke_manifest.get("biome_id"), generated_at=now_iso())
    asset_pack = env["runtime"]["asset_pack"]
    asset_pack["source_preview_id"] = preview_id
    if asset_pack.get("assets"):
        asset_pack["status"] = "partial" if asset_pack.get("failed_assets") else "ready"
        asset_pack["stale_components"] = ["background", "midground_arches", "wall_body_strip", "floor_cap_strip", "platform_ledge_strip", "door"]
    else:
        asset_pack["status"] = "idle"
        asset_pack["used_ai"] = False
        asset_pack["generated_at"] = None
        asset_pack["assets"] = {}
    suggestion_id = str(env.get("preview", {}).get("suggestion_id") or helpfulness.get("active_suggestion_id") or "").strip()
    suggestion = _find_suggestion_record(helpfulness, suggestion_id) if suggestion_id else None
    if suggestion:
        decision = suggestion.setdefault("decision", {})
        decision["outcome"] = "accept"
        decision["decision_at"] = now_iso()
        decision["time_to_decision_ms"] = _elapsed_ms(suggestion.get("generated_at"), decision["decision_at"])
        decision["time_to_decision_bucket"] = _bucket_time_to_decision(decision.get("time_to_decision_ms"))
        reason_codes = _coerce_reason_codes(payload.get("reason_codes"))
        if reason_codes:
            decision["reason_codes"] = reason_codes
        suggestion["preview_id"] = preview_id
        suggestion["accepted_preview_id"] = preview_id
        suggestion.setdefault("persistence", {})["status"] = "pending"
    _update_helpfulness_summary(helpfulness)
    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "room_environment_preview_approved",
        "room_id": room_id,
        "preview_id": preview_id,
        "created_at": now_iso(),
    })
    return {
        "ok": True,
        "environment": copy.deepcopy(env),
        "approved_preview": copy.deepcopy(found),
    }


def record_room_environment_feedback_event(project_id: str, room_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
    helpfulness = _ensure_room_ai_helpfulness(env)
    event_type = str(payload.get("event_type") or "").strip().lower()
    if not event_type:
        raise ValueError("event_type is required.")
    suggestion_id = str(payload.get("suggestion_id") or env.get("preview", {}).get("suggestion_id") or helpfulness.get("active_suggestion_id") or "").strip()
    suggestion = _find_suggestion_record(helpfulness, suggestion_id) if suggestion_id else None
    if suggestion is None:
        raise ValueError("suggestion_id is required for room feedback events.")
    effort = suggestion.setdefault("effort", {})
    reliability = suggestion.setdefault("reliability", {})
    decision = suggestion.setdefault("decision", {})
    if event_type == "preview_viewed":
        effort["preview_views"] = int(effort.get("preview_views") or 0) + 1
    elif event_type == "preview_inspected":
        effort["preview_inspections"] = int(effort.get("preview_inspections") or 0) + 1
    elif event_type == "open_game_preview":
        effort["open_game_inspections"] = int(effort.get("open_game_inspections") or 0) + 1
    elif event_type == "workflow_backtrack":
        effort["back_and_forth_steps"] = int(effort.get("back_and_forth_steps") or 0) + 1
    elif event_type == "discarded":
        decision["outcome"] = "reject"
        decision["decision_at"] = now_iso()
        decision["time_to_decision_ms"] = _elapsed_ms(suggestion.get("generated_at"), decision["decision_at"])
        decision["time_to_decision_bucket"] = _bucket_time_to_decision(decision.get("time_to_decision_ms"))
        reliability["cancellations"] = int(reliability.get("cancellations") or 0) + 1
    elif event_type == "generation_error":
        errors = reliability.get("errors") if isinstance(reliability.get("errors"), list) else []
        errors.append({
            "message": str(payload.get("message") or "generation_error")[:240],
            "created_at": now_iso(),
        })
        reliability["errors"] = errors[-8:]
        if payload.get("latency_ms") is not None:
            reliability["latency_ms"] = int(payload.get("latency_ms") or 0)
    elif event_type == "crash_near_ai_use":
        reliability["crashes_near_ai_use"] = int(reliability.get("crashes_near_ai_use") or 0) + 1
    reason_codes = _coerce_reason_codes(payload.get("reason_codes"))
    if reason_codes:
        decision["reason_codes"] = reason_codes
    project["updated_at"] = now_iso()
    _update_helpfulness_summary(helpfulness)
    save_project(project)
    return {
        "ok": True,
        "environment": copy.deepcopy(env),
        "suggestion_id": suggestion_id,
    }


def refresh_room_environment_helpfulness_on_layout_save(room: Dict[str, Any]) -> Dict[str, Any]:
    env = _ensure_room_environment(room)
    _evaluate_persistence_for_room(room)
    return copy.deepcopy(env)
