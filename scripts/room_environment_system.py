from __future__ import annotations

import copy
import base64
import hashlib
import io
import json
import math
import os
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
    out["updated_at"] = now_iso()
    return out


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
    asset_pack.setdefault("used_ai", False)
    asset_pack.setdefault("generated_at", None)
    asset_pack.setdefault("source_preview_id", None)
    asset_pack.setdefault("assets", {})
    return env


def _find_room(project: Dict[str, Any], room_id: str) -> Dict[str, Any]:
    layout = project.get("room_layout") or {}
    rooms = layout.get("rooms") or []
    room = next((item for item in rooms if str(item.get("id") or "") == room_id), None)
    if not isinstance(room, dict):
        raise ValueError("Room not found.")
    _ensure_room_environment(room)
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
    kit = {
        "wall_family": "broken_gothic_stone" if any(word in text for word in ("gothic", "ruin", "shrine", "ritual")) else "weathered_stone",
        "platform_family": "carved_ledge" if any(word in text for word in ("shrine", "ritual", "altar")) else "broken_masonry_ledge",
        "door_family": "ritual_gate" if any(word in text for word in ("shrine", "ritual", "sacred")) else "arch_door",
        "backdrop_family": "flooded_arch_hall" if any(word in text for word in ("wet", "damp", "flood")) else "ruined_arch_hall",
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
        {"themeId":"cave|ruins|forest|shrine|sewer|void|custom","tags":["a"],"description":"...","mood":"...","lighting":"...","fog":"...","materials":["..."],"landmarks":["..."],"hazards":["..."],"compositionFocus":"...","readabilityNotes":["..."],"components":{"floor":{"label":"Floor","prompt":"..."},"platforms":{"label":"Platforms","prompt":"..."},"walls":{"label":"Walls","prompt":"..."},"doors":{"label":"Doors","prompt":"..."},"background":{"label":"Background","prompt":"..."}},"sceneSchema":{"backgroundLayers":[{"kind":"architecture|fog_band|roots|void_forms","motif":"...","depth":"far|mid|near","density":"low|medium|high"}],"setDressing":[{"type":"brazier|chains|altar|roots|statue|banner","anchor":"floor|platform|ceiling|wall","zone":"left|center|right|focal","count":1,"priority":"low|medium|high","avoid":["door","main_path"]}],"effects":{"fog_profile":"...","particle_profile":"...","lighting_profile":"..."},"kit":{"wall_family":"weathered_stone|broken_gothic_stone|industrial_ribbed","platform_family":"broken_masonry_ledge|carved_ledge|iron_walkway","door_family":"arch_door|ritual_gate|iron_gate","backdrop_family":"ruined_arch_hall|flooded_arch_hall|industrial_depth","prop_density":"low|medium|high"}}}
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


def _fallback_background_asset(output_path: Path, preview_path: Path) -> None:
    source = Image.open(preview_path).convert("RGBA").resize((1600, 1200))
    blurred = source.filter(ImageFilter.GaussianBlur(radius=12))
    overlay = Image.new("RGBA", blurred.size, (8, 10, 14, 84))
    blurred.alpha_composite(overlay)
    blurred.save(output_path)


def _fallback_tile_asset(output_path: Path, palette: Dict[str, Any], size: Tuple[int, int], mode: str) -> None:
    base = _hex_to_rgb(str((palette.get("dominant") or ["#2a2522"])[0]), (42, 37, 34))
    alt = _hex_to_rgb(str((palette.get("dominant") or ["#2a2522", "#4a4038"])[1] if len(palette.get("dominant") or []) > 1 else "#4a4038"), (74, 64, 56))
    accent = _hex_to_rgb(str((palette.get("accent") or ["#8d7a5f"])[0]), (141, 122, 95))
    img = Image.new("RGBA", size, base + (255,))
    draw = ImageDraw.Draw(img)
    if mode == "wall":
        block_w = max(18, size[0] // 4)
        block_h = max(18, size[1] // 4)
        for y in range(0, size[1], block_h):
            offset = 0 if (y // block_h) % 2 == 0 else block_w // 3
            for x in range(-offset, size[0], block_w):
                draw.rectangle((x, y, x + block_w - 2, y + block_h - 2), outline=accent + (110,), fill=alt + (42,))
    elif mode == "floor":
        slab_h = max(24, size[1] // 3)
        for y in range(0, size[1], slab_h):
            draw.line((0, y, size[0], y), fill=accent + (120,), width=2)
        for x in range(0, size[0], max(28, size[0] // 5)):
            draw.line((x, 0, x + 18, size[1]), fill=accent + (90,), width=1)
    elif mode == "platform":
        draw.rectangle((0, 0, size[0], size[1]), fill=alt + (255,))
        draw.rectangle((0, 0, size[0], max(6, size[1] // 6)), fill=accent + (150,))
        for x in range(12, size[0] - 12, 48):
            draw.line((x, size[1] // 2, x + 10, size[1] - 1), fill=accent + (110,), width=2)
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


def _fallback_midground_asset(output_path: Path, palette: Dict[str, Any]) -> None:
    size = (1600, 1200)
    base = _hex_to_rgb(str((palette.get("dominant") or ["#181614"])[0]), (24, 22, 20))
    accent = _hex_to_rgb(str((palette.get("accent") or ["#6f624e"])[0]), (111, 98, 78))
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i in range(4):
        x = 160 + (i * 340)
        draw.rectangle((x, 240, x + 44, 1080), fill=base + (92,))
        draw.rounded_rectangle((x - 84, 160, x + 128, 316), radius=60, fill=base + (74,), outline=accent + (54,))
    img.save(output_path)


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


def generate_room_environment_asset_pack(project_id: str, room_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    room = _find_room(project, room_id)
    env = _ensure_room_environment(room)
    preview = env["preview"]
    spec = env["spec"]
    direction = normalize_art_direction(project.get("art_direction"), project.get("art_direction"))
    preview_id = str((payload or {}).get("preview_id") or preview.get("approved_image_id") or "").strip()
    if not preview_id:
        raise ValueError("Approve a room preview before generating production assets.")
    approved = next((item for item in (preview.get("images") or []) if item.get("preview_id") == preview_id), None)
    if not approved:
        raise ValueError("Approved preview not found.")
    project_dir = PROJECTS_ROOT / project_id
    preview_path = _project_url_to_path(project_dir, str(approved.get("url") or ""))
    if preview_path is None or not preview_path.exists():
        raise ValueError("Approved preview image is missing on disk.")

    asset_root = project_dir / "room_environment_assets" / room_id
    asset_root.mkdir(parents=True, exist_ok=True)
    background_path = asset_root / "background.png"
    wall_tile_path = asset_root / "wall_tile.png"
    floor_tile_path = asset_root / "floor_tile.png"
    platform_tile_path = asset_root / "platform_tile.png"
    door_path = asset_root / "door.png"
    midground_arches_path = asset_root / "midground_arches.png"

    refs = [preview_path]
    for frozen in (direction.get("frozen_concepts") or [])[:3]:
        rel = str(frozen.get("image_path") or "").strip()
        frozen_path = project_dir / rel if rel else None
        if frozen_path and frozen_path.exists():
            refs.append(frozen_path)

    base_context = textwrap.dedent(
        f"""\
        Match the approved room environment closely.
        This is for production-ready 2D metroidvania environment assets.
        Art direction: {direction.get('high_level_direction') or ''}
        Avoid: {direction.get('negative_direction') or ''}
        Theme: {spec.get('theme_id') or env.get('themeId') or 'custom'}
        Materials: {', '.join(spec.get('materials') or []) or 'aged environmental materials'}
        Lighting: {spec.get('lighting') or 'controlled focal light'}
        Mood: {spec.get('mood') or 'moody'}
        Room description: {spec.get('description') or ''}
        """
    ).strip()
    components = spec.get("components") if isinstance(spec.get("components"), dict) else {}
    floor_prompt = str(((components.get("floor") or {}).get("prompt")) or "").strip()
    platforms_prompt = str(((components.get("platforms") or {}).get("prompt")) or "").strip()
    walls_prompt = str(((components.get("walls") or {}).get("prompt")) or "").strip()
    doors_prompt = str(((components.get("doors") or {}).get("prompt")) or "").strip()
    background_prompt = str(((components.get("background") or {}).get("prompt")) or "").strip()
    palette = _extract_preview_runtime_palette(preview_path)

    results = {}
    results["background"] = _generate_image_from_references(
        background_path,
        f"""{base_context}
Create a side-view background matte for this room only.
Show deep background architecture, atmosphere, and environment painting.
Use this direction for the background: {background_prompt or 'Distant ruined architecture, atmospheric depth, and room-specific environment silhouettes.'}
No foreground collision blocks, no UI, no characters, no text.
""",
        refs,
        size_hint="wide room background 1600x1200",
    )
    if not results["background"]:
        _fallback_background_asset(background_path, preview_path)

    results["wall_tile"] = _generate_image_from_references(
        wall_tile_path,
        f"""{base_context}
Create a seamless wall tile texture for a side-view metroidvania room.
Use this direction for the wall tile: {walls_prompt or 'Broken gothic wet stone with carved vertical structure, fractured masonry, and subtle age damage.'}
The result must be modular, tileable, and production-ready for repeated room wall geometry.
No text, no characters, no full scene composition, no perspective room painting.
""",
        refs,
        size_hint="seamless square texture 256x256",
    )
    if not results["wall_tile"]:
        _fallback_tile_asset(wall_tile_path, palette, (256, 256), "wall")

    results["floor_tile"] = _generate_image_from_references(
        floor_tile_path,
        f"""{base_context}
Create a seamless floor tile texture for a side-view metroidvania room.
Use this direction for the floor tile: {floor_prompt or 'Large ritual stone slabs, cracked and damp, with subtle carved structure and readable top-down surface rhythm.'}
The result must be modular, tileable, and production-ready for repeated floor or ceiling bands.
No text, no characters, no full scene composition.
""",
        refs,
        size_hint="seamless square texture 256x256",
    )
    if not results["floor_tile"]:
        _fallback_tile_asset(floor_tile_path, palette, (256, 256), "floor")

    results["platform_tile"] = _generate_image_from_references(
        platform_tile_path,
        f"""{base_context}
Create a modular platform ledge texture for a side-view metroidvania room.
Use this direction for the platform tile: {platforms_prompt or 'Fractured shrine ledges with chipped stone lips, readable collision tops, and subtle support detail.'}
This asset should work as a repeated platform strip with a clear top edge and readable front face.
No text, no characters, no full scene composition.
""",
        refs,
        size_hint="platform strip texture 256x96",
    )
    if not results["platform_tile"]:
        _fallback_tile_asset(platform_tile_path, palette, (256, 96), "platform")

    results["door"] = _generate_image_from_references(
        door_path,
        f"""{base_context}
Create a doorway or gate asset for this room style.
Use this direction for the doorway: {doors_prompt or 'Heavy aged iron shrine gate set inside carved wet stone masonry.'}
Readable in side view, centered, production-ready environment prop.
No characters, no text.
""",
        refs,
        size_hint="door prop 192x288",
    )
    if not results["door"]:
        _fallback_door_asset(door_path, preview_path)

    results["midground_arches"] = _generate_image_from_references(
        midground_arches_path,
        f"""{base_context}
Create a transparent-background midground environment strip for a 2D metroidvania room.
Use this direction for the midground layer: {background_prompt or 'Broken gothic arches, columns, hanging silhouettes, and deep architectural rhythm.'}
The result should contain reusable arch or column silhouettes that can sit in front of the far background but behind gameplay.
Transparent background, no text, no characters, no UI.
""",
        refs,
        size_hint="transparent midground strip 1600x800",
    )
    if not results["midground_arches"]:
        _fallback_midground_asset(midground_arches_path, palette)

    used_ai = any(results.values())
    env["runtime"]["asset_pack"] = {
        "status": "ready",
        "used_ai": used_ai,
        "generated_at": now_iso(),
        "source_preview_id": preview_id,
        "assets": {
            "background": {
                "url": f"/tools/2d-sprite-and-animation/projects-data/{project_id}/room_environment_assets/{room_id}/background.png",
                "kind": "background",
            },
            "wall_tile": {
                "url": f"/tools/2d-sprite-and-animation/projects-data/{project_id}/room_environment_assets/{room_id}/wall_tile.png",
                "kind": "wall_tile",
            },
            "floor_tile": {
                "url": f"/tools/2d-sprite-and-animation/projects-data/{project_id}/room_environment_assets/{room_id}/floor_tile.png",
                "kind": "floor_tile",
            },
            "platform_tile": {
                "url": f"/tools/2d-sprite-and-animation/projects-data/{project_id}/room_environment_assets/{room_id}/platform_tile.png",
                "kind": "platform_tile",
            },
            "door": {
                "url": f"/tools/2d-sprite-and-animation/projects-data/{project_id}/room_environment_assets/{room_id}/door.png",
                "kind": "door",
            },
            "midground_arches": {
                "url": f"/tools/2d-sprite-and-animation/projects-data/{project_id}/room_environment_assets/{room_id}/midground_arches.png",
                "kind": "midground_arches",
            },
        },
    }
    env["runtime"]["status"] = "ready"
    env["runtime"]["source"] = "approved_preview"
    env["runtime"]["applied_preview_id"] = preview_id
    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "room_environment_assets_generated",
        "room_id": room_id,
        "preview_id": preview_id,
        "used_ai": used_ai,
        "created_at": now_iso(),
    })
    return {
        "ok": True,
        "environment": copy.deepcopy(env),
        "asset_pack": copy.deepcopy(env["runtime"]["asset_pack"]),
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
    env["runtime"]["asset_pack"]["status"] = "idle"
    env["runtime"]["asset_pack"]["used_ai"] = False
    env["runtime"]["asset_pack"]["generated_at"] = None
    env["runtime"]["asset_pack"]["source_preview_id"] = preview_id
    env["runtime"]["asset_pack"]["assets"] = {}
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
