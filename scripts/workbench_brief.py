from __future__ import annotations

import base64
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)

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
        if reason == "highly asymmetric multi-view requirements":
            for match in pattern.finditer(lowered):
                prefix = lowered[max(0, match.start() - 40):match.start()]
                if NEGATING_PREFIX_PATTERN.search(prefix):
                    continue
                raise ValueError("Unsupported input: %s." % reason)
            continue
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
        "backend_mode": normalize_brief_backend_mode(source.get("backend_mode") or "pixellab"),
        "comfyui_checkpoint": source.get("comfyui_checkpoint"),
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
    canvas_size = PIXELLAB_CONCEPT_IMAGE_SIZE
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
