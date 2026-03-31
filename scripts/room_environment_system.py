from __future__ import annotations

import copy
import base64
import hashlib
import io
import json
import math
import os
import shutil
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter

try:
    from google import genai as _google_genai
    from google.genai import types as _google_genai_types
    _GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    _GOOGLE_GENAI_AVAILABLE = False


PROJECTS_ROOT: Path
ROOT: Path
load_project: Callable[[str], Dict[str, Any]]
save_project: Callable[[Dict[str, Any]], None]
now_iso: Callable[[], str]
stable_hash: Callable[..., str]
append_history_event: Callable[[str, Dict[str, Any]], Dict[str, Any]]


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


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


V1_BESPOKE_COMPONENTS: Tuple[Dict[str, Any], ...] = (
    {"component_type": "background_plate", "variant_family": "background", "size": (1600, 1200), "orientation": "full", "transparency_mode": "opaque", "visual_role": "far_depth"},
    {"component_type": "midground_frame", "variant_family": "midground", "size": (1600, 1200), "orientation": "full", "transparency_mode": "alpha", "visual_role": "side_frame"},
    {"component_type": "primary_floor_piece", "variant_family": "floor", "size": (512, 96), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "main_route"},
    {"component_type": "hero_platform_piece", "variant_family": "platform", "size": (320, 72), "orientation": "horizontal", "transparency_mode": "opaque", "visual_role": "hero_platform"},
    {"component_type": "door_piece", "variant_family": "door", "size": (192, 288), "orientation": "vertical", "transparency_mode": "alpha", "visual_role": "transition"},
)


V1_TEMPLATE_SOURCE_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "background_plate": ("background.png",),
    "midground_frame": ("midground_arches.png",),
    "primary_floor_piece": ("floor_cap_strip.png",),
    "hero_platform_piece": ("platform_ledge_strip.png", "floor_cap_strip.png"),
    "door_piece": ("door.png",),
}


def _default_biome_id(direction: Dict[str, Any]) -> str:
    template_id = str(direction.get("template_id") or "ruined-gothic").strip()
    return f"{_slugify(template_id, 'biome')}-v1"


def _default_biome_label(direction: Dict[str, Any]) -> str:
    return str(direction.get("style_family") or direction.get("template_id") or "Biome").strip().title()


def _component_adaptation_mode(component_type: str) -> str:
    if component_type in {"background_plate", "midground_frame", "door_piece"}:
        return "direct"
    if component_type in {"primary_floor_piece", "hero_platform_piece"}:
        return "stretch"
    return "gemini"


def _find_curated_template_source(project_id: str, component_type: str) -> Optional[Path]:
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
        for template in pack.get("template_library") or []:
            if not isinstance(template, dict):
                continue
            component_type = str(template.get("component_type") or "").strip()
            if not component_type:
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
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip() or "gemini-2.5-flash-image"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "imageConfig": {"aspectRatio": "16:9"},
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
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
    bespoke_manifest.setdefault("schema_version", 1)
    bespoke_manifest.setdefault("status", "idle")
    bespoke_manifest.setdefault("biome_id", None)
    bespoke_manifest.setdefault("source_preview_id", None)
    bespoke_manifest.setdefault("generation_plan", [])
    bespoke_manifest.setdefault("assets", {})
    bespoke_manifest.setdefault("failed_assets", [])
    bespoke_manifest.setdefault("used_ai", False)
    bespoke_manifest.setdefault("generated_at", None)
    bespoke_manifest.setdefault("validation_errors", [])
    return env


def _find_room(project: Dict[str, Any], room_id: str) -> Dict[str, Any]:
    layout = project.get("room_layout") or {}
    rooms = layout.get("rooms") or []
    room = next((item for item in rooms if str(item.get("id") or "") == room_id), None)
    if not isinstance(room, dict):
        raise ValueError("Room not found.")
    env = _ensure_room_environment(room)
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


def _room_geometry(room: Dict[str, Any]) -> Dict[str, Any]:
    polygon = room.get("polygon") or []
    xs = [float(pt[0]) for pt in polygon if isinstance(pt, (list, tuple)) and len(pt) == 2]
    ys = [float(pt[1]) for pt in polygon if isinstance(pt, (list, tuple)) and len(pt) == 2]
    doors = room.get("doors") or []
    platforms = room.get("platforms") or []
    return {
        "room_id": room.get("id"),
        "room_name": room.get("name") or room.get("id") or "Unnamed room",
        "width": float(((room.get("size") or {}).get("width")) or (max(xs) - min(xs) if xs else 1600)),
        "height": float(((room.get("size") or {}).get("height")) or (max(ys) - min(ys) if ys else 1200)),
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
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.35},
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
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
        "scene_schema": scene_schema if isinstance(scene_schema, dict) else {},
    }


COMPONENT_KEYS: Tuple[Tuple[str, str], ...] = (
    ("floor", "Floor"),
    ("platforms", "Platforms"),
    ("walls", "Walls"),
    ("doors", "Doors"),
    ("background", "Background"),
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
            "type": "altar",
            "anchor": "floor",
            "zone": "center",
            "count": 1,
            "priority": "high",
            "avoid": ["door", "main_path"],
        })
        set_dressing.append({
            "type": "brazier",
            "anchor": "platform",
            "zone": "center",
            "count": 1,
            "priority": "medium",
            "avoid": ["door", "main_path"],
        })
        set_dressing.append({
            "type": "banner",
            "anchor": "ceiling",
            "zone": "right",
            "count": 1,
            "priority": "low",
            "avoid": ["door"],
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
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    description = str(payload.get("description") or env["spec"].get("description") or "").strip()
    if not description:
        raise ValueError("Environment description is required.")
    components = _normalize_component_prompts_response(
        payload.get("components") if isinstance(payload.get("components"), dict) else env["spec"].get("components"),
        description,
        direction,
    )
    geometry = _room_geometry(room)
    system_prompt = textwrap.dedent(
        """\
        You produce structured room-environment specs for a game editor.
        Respect the locked art direction strictly.
        Keep results readable for a platforming game.
        Return ONLY valid JSON in this shape:
        {"themeId":"cave|ruins|forest|shrine|sewer|void|custom","tags":["a"],"description":"...","mood":"...","lighting":"...","fog":"...","materials":["..."],"landmarks":["..."],"hazards":["..."],"compositionFocus":"...","readabilityNotes":["..."],"components":{"floor":{"label":"Floor","prompt":"..."},"platforms":{"label":"Platforms","prompt":"..."},"walls":{"label":"Walls","prompt":"..."},"doors":{"label":"Doors","prompt":"..."},"background":{"label":"Background","prompt":"..."}},"sceneSchema":{"backgroundLayers":[{"kind":"architecture|fog_band|roots|void_forms","motif":"...","depth":"far|mid|near","density":"low|medium|high"}],"setDressing":[{"type":"brazier|chains|altar|roots|statue|banner","anchor":"floor|platform|ceiling|wall","zone":"left|center|right|focal","count":1,"priority":"low|medium|high","avoid":["door","main_path"]}],"effects":{"fog_profile":"...","particle_profile":"...","lighting_profile":"..."},"kit":{"shell_family":"gothic_ruin|ritual_shrine|flooded_stone|industrial_underworks|rooted_overgrowth|void_structure|weathered_stone","wall_family":"weathered_stone|broken_gothic_stone|industrial_ribbed","platform_family":"broken_masonry_ledge|carved_ledge|iron_walkway","door_family":"arch_door|ritual_gate|iron_gate","backdrop_family":"ruined_arch_hall|flooded_arch_hall|industrial_depth","prop_density":"low|medium|high"}}}
        """
    )
    user_prompt = json.dumps({
        "art_direction": direction,
        "frozen_concepts": direction.get("frozen_concepts") or [],
        "room_geometry": geometry,
        "template_context": env["template_context"],
        "description": description,
        "components": components,
    }, indent=2)
    ai_payload = _gemini_json(system_prompt, user_prompt)
    spec = _normalize_spec_response(ai_payload or {}, description)
    spec["components"] = _normalize_component_prompts_response(spec.get("components"), description, direction)
    spec["scene_schema"] = spec["scene_schema"] if spec["scene_schema"] else _default_scene_schema(spec, geometry)
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
        poly_draw.polygon(polygon, fill=poly_fill + (190,), outline=accent_rgb + (220,))
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
        draw.rounded_rectangle((sx - 7, sy - h, sx + 7, sy), radius=4, fill=accent_rgb + (220,), outline=(255, 255, 255, 60))
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
    draw.rounded_rectangle((36, 36, canvas_size[0] - 36, canvas_size[1] - 36), radius=28, outline=(0, 232, 200, 110), width=2)
    polygon = _fit_points(geometry.get("polygon") or [], canvas_size, padding=72)
    if polygon:
        poly_fill = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        poly_draw = ImageDraw.Draw(poly_fill)
        poly_draw.polygon(polygon, fill=(28, 38, 48, 220), outline=(0, 232, 200, 230))
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
        draw.rounded_rectangle((sx - 12, sy - h, sx + 12, sy), radius=6, fill=(255, 214, 122, 220), outline=(255, 245, 225, 120))
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


def _gemini_client() -> Any:
    if not _GOOGLE_GENAI_AVAILABLE:
        return None
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        return _google_genai.Client(api_key=api_key)
    except Exception:
        return None


def _build_level3_variant_prompt(direction: Dict[str, Any], geometry: Dict[str, Any], spec: Dict[str, Any], frozen_concepts: List[Dict[str, Any]], variant_index: int) -> str:
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
    return textwrap.dedent(
        f"""\
        Create a high-detail 2D side-view game environment concept for a metroidvania room.
        This is a room environment preview, not a mood board and not abstract color treatment.
        The attached first image is a hard layout guide. Respect its overall room silhouette, door locations, main walkable structures, and framing.
        Additional attached images are frozen art direction anchors. Match their style language and world identity closely.

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
        - geometry summary: width {int(geometry.get('width') or 0)}, height {int(geometry.get('height') or 0)}, {int(geometry.get('platform_count') or 0)} platforms, {int(geometry.get('door_count') or 0)} doors
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
) -> bool:
    client = _gemini_client()
    if client is None or not _GOOGLE_GENAI_AVAILABLE:
        return False
    frozen_concepts = direction.get("frozen_concepts") or []
    contents: List[Any] = []
    try:
        contents.append(_google_genai_types.Part.from_bytes(
            data=_render_room_layout_conditioning_image(geometry, spec, variant_index),
            mime_type="image/png",
        ))
        for item in frozen_concepts[:3]:
            rel_path = str(item.get("image_path") or "").strip()
            if not rel_path:
                continue
            concept_path = project_dir / rel_path
            if not concept_path.exists():
                continue
            contents.append(_google_genai_types.Part.from_bytes(
                data=concept_path.read_bytes(),
                mime_type="image/png",
            ))
        contents.append(_build_level3_variant_prompt(direction, geometry, spec, frozen_concepts, variant_index))
        model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip() or "gemini-2.5-flash-image"
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=_google_genai_types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
    except Exception:
        return False
    try:
        for part in response.candidates[0].content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                image = Image.open(io.BytesIO(inline.data)).convert("RGBA")
                path.parent.mkdir(parents=True, exist_ok=True)
                image.save(path)
                return True
    except Exception:
        return False
    return False


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
    draw.rounded_rectangle((40, 40, 728, 392), radius=24, outline=(0, 232, 200, 120), fill=(18, 24, 26, 255))
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


def _generate_image_from_references(path: Path, prompt: str, reference_paths: List[Path], size_hint: str = "") -> bool:
    client = _gemini_client()
    if client is None or not _GOOGLE_GENAI_AVAILABLE:
        return False
    contents: List[Any] = []
    try:
        for ref_path in reference_paths:
            if not ref_path.exists():
                continue
            contents.append(_google_genai_types.Part.from_bytes(
                data=ref_path.read_bytes(),
                mime_type="image/png",
            ))
        contents.append(f"{prompt}\nSize intent: {size_hint}".strip())
        model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip() or "gemini-2.5-flash-image"
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=_google_genai_types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
        for part in response.candidates[0].content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                image = Image.open(io.BytesIO(inline.data)).convert("RGBA")
                path.parent.mkdir(parents=True, exist_ok=True)
                image.save(path)
                return True
    except Exception:
        return False
    return False


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
        block_w = max(56, size[0] // 3)
        block_h = max(72, size[1] // 3)
        draw.rectangle((0, 0, size[0], size[1]), fill=softened(base, -8) + (255,))
        if flags.get("gothic"):
            bay_w = max(88, size[0] // 2)
            for x in range(-24, size[0] + 24, bay_w):
                draw.rectangle((x + 18, 0, x + 36, size[1]), fill=shadow + (255,))
                draw.rectangle((x + 36, 0, x + bay_w - 24, size[1]), fill=softened(base, 6) + (255,))
                draw.arc((x + 8, 18, x + bay_w - 8, 126), 180, 360, fill=accent + (145,), width=3)
                draw.line((x + 24, size[1] * 0.18, x + bay_w - 24, size[1] * 0.18), fill=accent + (96,), width=2)
        else:
            for y in range(0, size[1], block_h):
                offset = 0 if (y // block_h) % 2 == 0 else block_w // 2
                for x in range(-offset, size[0], block_w):
                    fill = softened(alt, ((x + y) // 37) % 6 - 3)
                    draw.rectangle((x, y, x + block_w - 6, y + block_h - 6), outline=accent + (90,), fill=fill + (255,))
        if flags.get("fractured"):
            cracks = [
                (22, 30, 54, 86),
                (size[0] - 74, 18, size[0] - 40, 78),
                (size[0] // 2 - 12, size[1] - 90, size[0] // 2 + 18, size[1] - 32),
            ]
            for x1, y1, x2, y2 in cracks:
                draw.line((x1, y1, x2, y2), fill=accent + (110,), width=2)
                draw.line((x2, y2, x2 + 12, y2 + 20), fill=accent + (76,), width=1)
        if flags.get("mossy"):
            draw.rectangle((0, size[1] - 18, size[0], size[1]), fill=moss + (52,))
    elif mode == "floor":
        draw.rectangle((0, 0, size[0], size[1]), fill=softened(alt, -8) + (255,))
        slab_h = max(88, size[1] // 2)
        slab_w = max(92, size[0] // 2)
        for y in range(0, size[1], slab_h):
            offset = 0 if (y // slab_h) % 2 == 0 else slab_w // 2
            for x in range(-offset, size[0], slab_w):
                fill = softened(base, ((x + y) // 53) % 8 - 4)
                draw.rectangle((x, y, x + slab_w - 8, y + slab_h - 8), outline=accent + (120,), fill=fill + (255,))
        if flags.get("ritual"):
            center = (size[0] // 2, size[1] // 2)
            for radius in (size[0] // 5, size[0] // 3):
                draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), outline=glow + (104,), width=2)
            draw.line((center[0] - size[0] // 4, center[1], center[0] + size[0] // 4, center[1]), fill=accent + (70,), width=1)
        if flags.get("wet"):
            draw.rectangle((0, size[1] - 22, size[0], size[1]), fill=(80, 96, 102, 42))
        if flags.get("fractured"):
            draw.line((26, size[1] // 2 + 16, size[0] // 2 - 20, size[1] // 2 - 10), fill=accent + (82,), width=2)
            draw.line((size[0] // 2 + 18, size[1] // 2 - 12, size[0] - 22, size[1] // 2 + 8), fill=accent + (82,), width=2)
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


def _seed_biome_template_asset(output_path: Path, component_type: str, palette: Dict[str, Any], flags: Dict[str, bool], shell_family: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if component_type == "background_plate":
        _fallback_background_asset(output_path, palette, flags, shell_family)
        return
    if component_type == "midground_frame":
        _fallback_midground_asset(output_path, palette, shell_family)
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
        "version": 1,
        "locked": True,
        "updated_at": now_iso(),
    }]
    return _refresh_biome_pack_templates(project, direction)


def generate_room_environment_previews(project_id: str, room_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
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
    if geometry.get("polygon"):
        labels = ["Focal landmark", "Atmospheric depth", "Broader ambience"]
        for variant_index in range(3):
            preview_id = f"{room_id}-lvl3-{variant_index + 1}"
            rel_path = Path("room_environment_previews") / room_id / f"{preview_id}.png"
            abs_path = project_dir / rel_path
            generated = _generate_level3_image_with_gemini(abs_path, project_dir, direction, geometry, spec, variant_index)
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
        "used_ai": used_ai,
        "description": spec.get("description"),
        "mood": spec.get("mood"),
        "lighting": spec.get("lighting"),
        "fog": spec.get("fog"),
        "landmarks": spec.get("landmarks"),
    }
    env["runtime"]["status"] = "needs_approval"
    env["runtime"]["source"] = None
    env["runtime"]["applied_preview_id"] = None
    env["runtime"]["surface_palette"] = None
    env["runtime"]["material_keywords"] = list(spec.get("materials") or [])
    env["runtime"]["lighting_mode"] = str(spec.get("lighting") or "")
    env["runtime"]["last_applied_at"] = None
    env["runtime"]["bespoke_asset_manifest"] = {
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
    env["runtime"]["asset_pack"]["status"] = "idle"
    env["runtime"]["asset_pack"]["used_ai"] = False
    env["runtime"]["asset_pack"]["generated_at"] = None
    env["runtime"]["asset_pack"]["source_preview_id"] = None
    env["runtime"]["asset_pack"]["assets"] = {}
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


def _template_by_component(biome_pack: Dict[str, Any], component_type: str) -> Optional[Dict[str, Any]]:
    for item in biome_pack.get("template_library") or []:
        if str(item.get("component_type") or "").strip() == component_type:
            return copy.deepcopy(item)
    return None


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
    plan: List[Dict[str, Any]] = []
    background_template = _template_by_component(biome_pack, "background_plate")
    if background_template:
        plan.append({
            "slot_id": f"{room_id}-background",
            "component_type": "background_plate",
            "source_template_id": background_template["template_id"],
            "target_dimensions": {"width": width, "height": height},
            "placement": {"x": int(width / 2), "y": height, "display_width": width, "display_height": height, "origin_x": 0.5, "origin_y": 1},
            "orientation": "full",
            "protected_zones": [{"type": "center_lane", "x": int(width * 0.25), "y": 0, "width": int(width * 0.5), "height": height}],
            "local_geometry": {"room_width": width, "room_height": height},
        })
    midground_template = _template_by_component(biome_pack, "midground_frame")
    if midground_template:
        plan.append({
            "slot_id": f"{room_id}-midground",
            "component_type": "midground_frame",
            "source_template_id": midground_template["template_id"],
            "target_dimensions": {"width": width, "height": height},
            "placement": {"x": int(width / 2), "y": height, "display_width": width, "display_height": height, "origin_x": 0.5, "origin_y": 1},
            "orientation": "full",
            "protected_zones": [{"type": "main_route", "x": int(width * 0.3), "y": 0, "width": int(width * 0.4), "height": height}],
            "local_geometry": {"room_width": width, "room_height": height},
        })
    floor_template = _template_by_component(biome_pack, "primary_floor_piece")
    if floor_template and primary_floor:
        plan.append({
            "slot_id": f"{room_id}-primary-floor",
            "component_type": "primary_floor_piece",
            "source_template_id": floor_template["template_id"],
            "target_dimensions": {"width": primary_floor["width"], "height": 96},
            "placement": {"x": primary_floor["x"], "y": primary_floor["y"], "display_width": primary_floor["width"], "display_height": 96, "origin_x": 0, "origin_y": 0.75},
            "orientation": "horizontal",
            "protected_zones": [{"type": "platform_top", "x": primary_floor["x"], "y": primary_floor["y"] - 18, "width": primary_floor["width"], "height": 22}],
            "local_geometry": primary_floor,
        })
    platform_template = _template_by_component(biome_pack, "hero_platform_piece")
    for index, platform in enumerate(hero_platforms[:3]):
        if not platform_template:
            break
        plan.append({
            "slot_id": f"{room_id}-hero-platform-{index + 1}",
            "component_type": "hero_platform_piece",
            "source_template_id": platform_template["template_id"],
            "target_dimensions": {"width": platform["width"], "height": 72},
            "placement": {"x": platform["x"], "y": platform["y"], "display_width": platform["width"], "display_height": 72, "origin_x": 0, "origin_y": 0.68},
            "orientation": "horizontal",
            "protected_zones": [{"type": "platform_top", "x": platform["x"], "y": platform["y"] - 16, "width": platform["width"], "height": 20}],
            "local_geometry": platform,
        })
    door_template = _template_by_component(biome_pack, "door_piece")
    if door_template and active_door:
        plan.append({
            "slot_id": f"{room_id}-door-1",
            "component_type": "door_piece",
            "source_template_id": door_template["template_id"],
            "target_dimensions": {"width": 192, "height": 288},
            "placement": {"x": int(active_door.get("x") or 0), "y": int(active_door.get("y") or 0), "display_width": 96, "display_height": 144, "origin_x": 0.5, "origin_y": 1},
            "orientation": "vertical",
            "protected_zones": [{"type": "door_mouth", "x": int(active_door.get("x") or 0) - 48, "y": int(active_door.get("y") or 0) - 144, "width": 96, "height": 160}],
            "local_geometry": {"door_id": str(active_door.get("id") or ""), "x": int(active_door.get("x") or 0), "y": int(active_door.get("y") or 0)},
        })
    return plan


def _build_bespoke_prompt(direction: Dict[str, Any], spec: Dict[str, Any], plan_entry: Dict[str, Any], template: Dict[str, Any]) -> str:
    dims = plan_entry.get("target_dimensions") or {}
    component_type = str(plan_entry.get("component_type") or "")
    protected = ", ".join(
        f"{zone.get('type')}@({int(zone.get('x') or 0)},{int(zone.get('y') or 0)},{int(zone.get('width') or 0)},{int(zone.get('height') or 0)})"
        for zone in (plan_entry.get("protected_zones") or [])
        if isinstance(zone, dict)
    ) or "none"
    component_rules = {
        "background_plate": "Treat the approved room preview as context only. Do not copy its focal landmark, altar, platform staging, or center floor graphic. Preserve a calm far-depth backdrop, soft depth falloff, and an open readable center lane.",
        "midground_frame": "Keep the middle third open. Concentrate architecture on the left and right framing edges. No center object, no floor plane, and no props that cross the playable route.",
        "primary_floor_piece": "Preserve a clean readable top lip, straight side-view silhouette, and shallow underside detail. Do not introduce props, braziers, or deep scenic perspective.",
        "hero_platform_piece": "Preserve a crisp horizontal traversal surface with restrained underside variation. No attached scenic background, no braziers, and no large dangling ornaments.",
        "door_piece": "Preserve a centered door silhouette with clear opening read. No extra scene dressing, no floor plane, no surrounding chamber composition.",
    }
    return textwrap.dedent(
        f"""\
        Create a single 2D metroidvania environment component that is a tightly matched equivalent adaptation of the attached template.
        Preserve the same biome family, silhouette role, and composition discipline.
        Do not redesign the piece. Do not invent a new scene. Only adapt it to the requested fit, dimensions, orientation, and subtle local wear.

        Component type: {component_type}
        Variant family: {template.get('variant_family')}
        Requested width: {int(dims.get('width') or 0)} px
        Requested height: {int(dims.get('height') or 0)} px
        Orientation: {plan_entry.get('orientation') or template.get('orientation') or 'unspecified'}
        Room mood: {spec.get('mood') or ''}
        Room lighting: {spec.get('lighting') or ''}
        Room description: {spec.get('description') or ''}
        Art direction: {direction.get('high_level_direction') or ''}
        Avoid: {direction.get('negative_direction') or ''}
        Protected zones: {protected}
        Gameplay constraints: keep protected readability zones clear, preserve silhouette readability, and stay close to the source template family.
        Component-specific rules: {component_rules.get(component_type, 'Preserve the source template closely and keep gameplay-facing surfaces readable.')}
        Output a single production-ready component image only. No text, no characters, no UI.
        """
    ).strip()


def _render_bespoke_component_from_template(template_path: Path, output_path: Path, size: Tuple[int, int], transparent: bool) -> bool:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template_path, output_path)
        _fit_image_to_size(output_path, size, transparent=transparent)
        return True
    except Exception:
        return False


def _generate_bespoke_component_from_references(output_path: Path, prompt: str, refs: List[Path], size: Tuple[int, int], transparent: bool) -> bool:
    if _generate_image_from_references(output_path, prompt, refs, size_hint=f"{size[0]}x{size[1]}"):
        _fit_image_to_size(output_path, size, transparent=transparent)
        return True
    return False


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
    if component_type in {"background_plate", "midground_frame"} and luminance > 185:
        errors.append("too_bright")
    if component_type in {"primary_floor_piece", "hero_platform_piece"} and luminance > 170:
        errors.append("platform_readability_risk")
    trusted_template_copy = False
    if template_path and template_path.exists():
        delta = _template_delta(path, template_path)
        trusted_template_copy = delta <= 1.5
        if component_type in {"background_plate", "midground_frame"} and delta > 42:
            errors.append("template_family_drift")
        if component_type in {"primary_floor_piece", "hero_platform_piece", "door_piece"} and delta > 54:
            errors.append("template_family_drift")
    if transparency_mode == "opaque" and alpha_ratio > (0.08 if trusted_template_copy else 0.02):
        errors.append("unexpected_transparency")
    if component_type == "background_plate" and not trusted_template_copy:
        center = _region_luminance(path, (0.34, 0.22, 0.66, 0.78))
        edges = (_region_luminance(path, (0.0, 0.18, 0.18, 0.82)) + _region_luminance(path, (0.82, 0.18, 1.0, 0.82))) / 2.0
        if center - edges > 18:
            errors.append("center_lane_too_hot")
    if component_type == "midground_frame" and not trusted_template_copy:
        center = _region_alpha_ratio(path, (0.32, 0.18, 0.68, 0.82))
        side_a = _region_alpha_ratio(path, (0.0, 0.18, 0.2, 0.82))
        side_b = _region_alpha_ratio(path, (0.8, 0.18, 1.0, 0.82))
        if center > max(side_a, side_b) + 0.15:
            errors.append("midground_center_clutter")
    return len(errors) == 0, errors


def generate_room_environment_asset_pack(project_id: str, room_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
    preview = env["preview"]
    spec = env["spec"]
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    direction = _attach_default_biome_pack(project, direction)
    preview_id = str((payload or {}).get("preview_id") or preview.get("approved_image_id") or "").strip()
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
    asset_root = project_dir / "room_environment_assets" / room_id / "bespoke"
    asset_root.mkdir(parents=True, exist_ok=True)
    refs = [preview_path]
    for frozen in (direction.get("frozen_concepts") or [])[:3]:
        rel = str(frozen.get("image_path") or "").strip()
        frozen_path = project_dir / rel if rel else None
        if frozen_path and frozen_path.exists():
            refs.append(frozen_path)
    plan = _room_component_plan(room, preview_id, biome_pack)
    assets: Dict[str, Any] = {}
    failed_assets: List[str] = []
    validation_errors: List[str] = []
    used_ai = False
    template_library = {str(item.get("template_id") or ""): item for item in (biome_pack.get("template_library") or []) if isinstance(item, dict)}
    for entry in plan:
        template = template_library.get(str(entry.get("source_template_id") or ""))
        if not template:
            failed_assets.append(str(entry.get("slot_id") or "unknown"))
            validation_errors.append(f"{entry.get('slot_id')}:missing_template")
            continue
        rel_path = str(template.get("image_path") or "").strip()
        template_path = project_dir / rel_path if rel_path else None
        if not template_path or not template_path.exists():
            failed_assets.append(str(entry.get("slot_id") or "unknown"))
            validation_errors.append(f"{entry.get('slot_id')}:missing_template_image")
            continue
        output_name = f"{entry['slot_id']}.png"
        output_path = asset_root / output_name
        prompt = _build_bespoke_prompt(direction, spec, entry, template)
        expected_size = (int(entry["target_dimensions"]["width"]), int(entry["target_dimensions"]["height"]))
        transparent = str(template.get("transparency_mode") or "opaque") == "alpha"
        adaptation_mode = str(template.get("adaptation_mode") or _component_adaptation_mode(str(entry.get("component_type") or "")))
        generation_source = "template"
        if adaptation_mode in {"direct", "stretch"}:
            generated = _render_bespoke_component_from_template(template_path, output_path, expected_size, transparent)
        else:
            refs_for_job = [template_path] + [path for path in refs if path != template_path]
            generated = _generate_bespoke_component_from_references(output_path, prompt, refs_for_job, expected_size, transparent)
            if generated:
                used_ai = True
                generation_source = "ai"
        if not generated:
            if output_path.exists():
                output_path.unlink()
        valid, errors = _validate_bespoke_component(
            output_path,
            str(entry.get("component_type") or ""),
            expected_size,
            str(template.get("transparency_mode") or "opaque"),
            template_path,
        )
        if not generated:
            errors = ["generation_failed"]
        if not valid or errors:
            if output_path.exists():
                output_path.unlink()
            failed_assets.append(entry["slot_id"])
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
            "transparency_mode": template.get("transparency_mode"),
            "validation": {"status": "pass", "errors": []},
            "generation_source": generation_source,
        }
    status = "ready" if assets and not failed_assets and len(assets) == len(plan) else "failed"
    env["runtime"]["bespoke_asset_manifest"] = {
        "schema_version": 1,
        "status": status,
        "biome_id": biome_pack.get("biome_id"),
        "source_preview_id": preview_id,
        "generation_plan": copy.deepcopy(plan),
        "assets": assets,
        "failed_assets": failed_assets,
        "used_ai": used_ai,
        "generated_at": now_iso(),
        "validation_errors": validation_errors,
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
    env["runtime"]["source"] = "approved_preview" if status == "ready" else "bespoke_generation_failed"
    env["runtime"]["applied_preview_id"] = preview_id if status == "ready" else None
    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "room_environment_bespoke_assets_generated",
        "room_id": room_id,
        "preview_id": preview_id,
        "used_ai": used_ai,
        "created_at": now_iso(),
    })
    return {
        "ok": True,
        "environment": copy.deepcopy(env),
        "asset_pack": copy.deepcopy(env["runtime"]["bespoke_asset_manifest"]),
    }


def approve_room_environment_preview(project_id: str, room_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
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
    bespoke_manifest["biome_id"] = ((_select_biome_pack(normalize_art_direction(project.get("art_direction"), project.get("art_direction"))) or {}).get("biome_id"))
    bespoke_manifest["source_preview_id"] = preview_id
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
