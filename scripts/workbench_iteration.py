from __future__ import annotations

import base64
import copy
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)

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

def _element_edit_mask_for_size(element: str, size: Tuple[int, int]) -> Image.Image:
    square_mask, _ = _build_element_inpaint_mask(element, 64)
    if square_mask.size == size:
        return square_mask
    return square_mask.resize(size, resample=Image.Resampling.NEAREST)

def _is_side_view_correction_request(element: str, change_text: str) -> bool:
    if element != "pose":
        return False
    text = str(change_text or "").lower()
    side_terms = (
        "side view",
        "side-view",
        "side profile",
        "side-profile",
        "strict profile",
        "profile view",
        "orthographic side",
        "true side",
    )
    off_view_terms = (
        "3/4",
        "three quarter",
        "three-quarter",
        "front view",
        "frontal",
        "turned toward camera",
        "not side view",
        "wrong view",
    )
    correction_verbs = (
        "change",
        "make",
        "turn",
        "convert",
        "fix",
        "adjust",
        "shift",
    )
    direct_side_requests = (
        "strict side view",
        "strict side-view",
        "strict side profile",
        "strict side-profile",
        "true side view",
        "true side profile",
        "orthographic side view",
        "full side view",
    )
    has_side_term = any(term in text for term in side_terms)
    has_off_view_term = any(term in text for term in off_view_terms)
    has_direct_side_request = any(term in text for term in direct_side_requests)
    has_correction_verb = any(term in text for term in correction_verbs)
    return (has_side_term and has_off_view_term) or (has_direct_side_request and has_correction_verb)

def _protected_source_mask_for_element(element: str, size: Tuple[int, int], change_text: str = "") -> Image.Image:
    if element != "pose" or _is_side_view_correction_request(element, change_text):
        return Image.new("L", size, 0)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    w, h = size
    # Preserve the side-profile read by locking the head and torso core.
    draw.rectangle((int(w * 0.30), int(h * 0.08), int(w * 0.66), int(h * 0.34)), fill=255)
    draw.rectangle((int(w * 0.34), int(h * 0.28), int(w * 0.64), int(h * 0.62)), fill=255)
    return mask

def _iteration_element_contract(element: str) -> Dict[str, Any]:
    contracts = {
        "outfit": {
            "label": "outfit and materials",
            "editable_zone": "clothing, armor surface treatment, cloth shapes, and material accents for the outfit only",
            "allowed": [
                "change garment shape, trim, layering, or material treatment",
                "extend or reduce cloth attached to the outfit",
                "adjust outfit pixels where the requested outfit change physically requires it",
            ],
            "locked": [
                "pose and body stance",
                "head design and facial area unless covered by outfit changes",
                "weapons, shield, and handheld props",
            ],
        },
        "weapon/prop": {
            "label": "weapon or handheld prop",
            "editable_zone": "the held item only, including its silhouette, size, and attached details",
            "allowed": [
                "change the held item's shape, material read, or decoration",
                "adjust the hand contact area only if needed to support the new prop shape",
            ],
            "locked": [
                "body pose and limb placement",
                "armor and clothing outside the hand contact area",
                "head, torso, and leg silhouette",
            ],
        },
        "palette/colors": {
            "label": "palette and color treatment",
            "editable_zone": "color choices only",
            "allowed": [
                "change hue, value, and saturation relationships",
                "re-map existing rendered regions to a new palette",
            ],
            "locked": [
                "silhouette and pose",
                "pixel clusters and line placement",
                "prop shape and costume design",
            ],
        },
        "pose": {
            "label": "pose",
            "editable_zone": "limb placement, arm angles, leg angles, and stance only while preserving the existing side-profile head and torso read",
            "allowed": [
                "reposition limbs and shift stance to create the requested pose",
                "shift prop placement only as a consequence of the new pose",
            ],
            "locked": [
                "character identity, armor design, and prop design",
                "head profile, face direction, and torso side-view read",
                "background and empty space",
            ],
        },
        "silhouette": {
            "label": "overall silhouette",
            "editable_zone": "outer contour of the character only",
            "allowed": [
                "broaden, narrow, lengthen, or simplify the readable outer shape",
                "change contour mass where needed to satisfy the requested silhouette change",
            ],
            "locked": [
                "core costume identity unless contour changes require minimal adjustment",
                "background and empty space",
                "rendering style and palette",
            ],
        },
        "hair/head": {
            "label": "hair or head treatment",
            "editable_zone": "hair, helmet crest, head accessory, and head silhouette only",
            "allowed": [
                "change headgear shape, hair shape, or head accessory read",
                "adjust adjacent neck pixels only if needed for a clean connection",
            ],
            "locked": [
                "body pose and torso design",
                "weapons, shield, and lower body",
                "background and empty space",
            ],
        },
        "accessories": {
            "label": "accessories",
            "editable_zone": "non-primary accessories only",
            "allowed": [
                "add, remove, or modify secondary straps, charms, pouches, or ornaments",
                "adjust nearby attachment pixels only where required",
            ],
            "locked": [
                "pose and anatomy",
                "primary weapon or shield silhouette",
                "base armor and clothing shapes",
            ],
        },
        "expression": {
            "label": "expression",
            "editable_zone": "face or visor read only",
            "allowed": [
                "change eyes, mouth, visor opening, or faceplate read",
                "make minimal head-area pixel edits necessary for the requested expression",
            ],
            "locked": [
                "head silhouette unless expression requires a tiny change",
                "body pose and costume",
                "weapons, shield, and background",
            ],
        },
        "proportions": {
            "label": "proportions",
            "editable_zone": "relative body part size and length relationships only",
            "allowed": [
                "lengthen or shorten limbs, torso, or head size relationships",
                "rebalance mass distribution to satisfy the requested proportion change",
            ],
            "locked": [
                "costume identity and accessory design unless geometry must follow the new proportions",
                "background and empty space",
                "rendering style and palette",
            ],
        },
    }
    return contracts[element]

def _iteration_element_contract_with_request(element: str, change_text: str) -> Dict[str, Any]:
    contract = copy.deepcopy(_iteration_element_contract(element))
    if _is_side_view_correction_request(element, change_text):
        contract["label"] = "pose and view correction"
        contract["editable_zone"] = "the full body pose and orientation, specifically to convert a bad 3/4 or front-turned sprite into a strict side view"
        contract["allowed"] = [
            "rebuild head, torso, limbs, and prop placement as needed to achieve a true side view",
            "remove 3/4-view or front-facing information that conflicts with a side-profile read",
            "reposition the full figure if needed to land on a clean side-view stance",
        ]
        contract["locked"] = [
            "character identity, costume identity, and prop identity",
            "overall design language, palette intent, and pixel-art rendering style",
            "background and empty space",
        ]
    return contract

def _build_iteration_edit_prompt(
    brief: Dict[str, Any],
    element: str,
    change_text: str,
    *,
    canvas_size: Optional[int] = None,
) -> str:
    style = _brief_pixel_lab_style(brief)
    description = str(brief.get("raw_prompt") or "").strip() or str(brief.get("description") or "").strip()
    contract = _iteration_element_contract_with_request(element, change_text)
    correcting_view = _is_side_view_correction_request(element, change_text)

    lines = [
        "ROLE: pixel art revision engine.",
        "JOB: edit the supplied source sprite by changing exactly one user-selected aspect.",
        "The source image is the authority for identity, rendering, layout, and all untouched pixels.",
        "Do not redesign the sprite. Do not perform a general cleanup pass. Do not make a second improvement.",
        "",
        "SOURCE OF TRUTH:",
        f"  Character brief: {description}" if description else "  Character brief: pixel art game character",
        f"  Outfit/materials: {brief.get('outfit_materials', '')}" if brief.get("outfit_materials") else "",
        f"  Palette mood: {brief.get('palette_mood', '')}" if brief.get("palette_mood") else "",
        f"  Silhouette intent: {brief.get('silhouette_intent', '')}" if brief.get("silhouette_intent") else "",
        f"  Primary prop: {brief.get('prop', '')}" if brief.get("prop") else "",
        f"  Rendering style: {style['outline_style_pixel_lab']}, {style['shading_style_pixel_lab']}, {style['detail_level_pixel_lab']}",
        "  View: strict orthographic side view, facing right (east)",
        f"  Canvas: {canvas_size}x{canvas_size} pixels" if canvas_size else "",
        "",
        "EDIT CONTRACT:",
        f"  Editable aspect: {contract['label']}",
        f"  User request: {change_text}",
        f"  Editable zone: {contract['editable_zone']}",
        "  This is the ONLY aspect that may materially change.",
        "",
        "ALLOWED CHANGES FOR THIS EDIT:",
        *[f"  - {item}" for item in contract["allowed"]],
        "",
        "LOCKED ASPECTS FOR THIS EDIT:",
        *[f"  - {item}" for item in contract["locked"]],
        "",
        "PIXEL OWNERSHIP RULES:",
        "  - Source opaque pixels belong to the character or a carried item.",
        "  - Source transparent pixels are empty background space.",
        "  - Never add a backing silhouette, halo, matte, cutout fill, shadow plate, or blocker shape behind the sprite.",
        "  - Never convert empty background into a black fill, white fill, checker pattern, or placeholder mass.",
        "  - New opaque pixels are allowed only where the requested edit physically changes the selected aspect.",
        "",
        "GLOBAL INVARIANTS:",
        "  - Preserve all untouched pixels exactly.",
        "  - Outside the selected edit region, the output should be a verbatim copy of the source sprite.",
        "  - Preserve the rendering style exactly: same pixel-art hardness, same anti-aliasing policy, same level of detail.",
        "  - Preserve the character identity and design language unless the selected aspect directly requires a local change.",
        "  - Preserve canvas size, crop, facing direction, and side-view presentation.",
        "  - The character must remain a strict side-view sprite, not a 3/4 view or front-turned redraw.",
        "  - If the request is specifically to fix a wrong view, prioritize reaching a true side view over preserving an incorrect source pose.",
        "",
        "BACKGROUND RULES:",
        "  - Background pixels stay background pixels.",
        "  - Do not place background-colored mass inside the character silhouette.",
        "  - Do not infer or paint a hidden body chunk, drop shadow, or backdrop shape behind the sprite.",
        "  - If the model is unsure whether a region is background or character, keep the source interpretation unchanged.",
        "",
        "DECISION RULE:",
        "  - When choosing between 'apply the requested edit' and 'preserve the source', preserve the source everywhere outside the selected aspect.",
        "  - If the requested edit can be satisfied with a smaller change, choose the smaller change.",
        "",
        "OUTPUT REQUIREMENT:",
        "  - Return one full sprite image with exactly one intentional revision: the requested change to the selected aspect.",
        "  - If the edit would break the strict side view, prefer a smaller side-view-safe change instead.",
        "  - If the request is to convert a bad 3/4 or front-facing image into side view, perform that correction directly and do not preserve the incorrect viewing angle.",
    ]
    if correcting_view:
        lines.extend([
            "",
            "VIEW CORRECTION MODE:",
            "  - The source is allowed to be wrong about orientation.",
            "  - Replace 3/4-view, front-facing, or camera-turned anatomy with a clean strict side profile.",
            "  - Keep the same character, but fix the view.",
        ])
    return "\n".join(line for line in lines if line)

def _build_gemini_requirements_prompt(
    brief: Dict[str, Any],
    element: str,
    change_text: str,
) -> str:
    contract = _iteration_element_contract_with_request(element, change_text)
    correcting_view = _is_side_view_correction_request(element, change_text)
    description = str(brief.get("raw_prompt") or "").strip() or str(brief.get("description") or "").strip() or "pixel art character"
    style = _brief_pixel_lab_style(brief)

    lines = [
        "Edit the attached sprite image.",
        "This is an image edit, not a redesign and not a fresh generation.",
        "Use the attached image as the visual source of truth.",
        "",
        "Target character:",
        f"- {description}",
        f"- Rendering style: {style['outline_style_pixel_lab']}, {style['shading_style_pixel_lab']}, {style['detail_level_pixel_lab']}",
        "",
        "Requested edit:",
        f"- Aspect to change: {contract['label']}",
        f"- User request: {change_text}",
        f"- Editable zone: {contract['editable_zone']}",
        "",
        "Allowed changes:",
        *[f"- {item}" for item in contract["allowed"]],
        "",
        "Keep unchanged unless required by the requested edit:",
        *[f"- {item}" for item in contract["locked"]],
        "",
        "Output requirements:",
        "- Return one edited full sprite image only.",
        "- Keep the same character identity, costume identity, gear identity, and pixel-art style.",
        "- Keep the same framing, crop, scale, and facing direction unless the request explicitly requires changing them.",
        "- Make only the smallest set of changes needed to satisfy the request.",
        "- Keep the background transparent and empty.",
        "- Do not add a backdrop, matte, glow, cast shadow, extra silhouette, hidden body fill, or any other new background-shaped mass.",
    ]
    if correcting_view:
        lines.extend([
            "- The source view may be wrong.",
            "- Correct the figure to a true strict side view while keeping the same identity, costume, and gear.",
        ])
    else:
        lines.extend([
            "- Keep the current viewing angle and body orientation unless the request explicitly asks to correct them.",
            "- Preserve the side-view presentation.",
        ])
    return "\n".join(lines)

def gemini_iteration_supported_for_element(element: str) -> bool:
    return str(element or "").strip() in ITERATION_ELEMENTS

def _concept_source_image_relpath(concept: Dict[str, Any]) -> Optional[str]:
    return (
        concept.get("original_preview_image")
        or concept.get("preview_image")
        or concept.get("processed_preview_image")
        or concept.get("image_path")
    )

def _count_mask_pixels(mask: Image.Image) -> int:
    normalized = normalize_mask(mask)
    return sum(1 for value in normalized.getdata() if value > 0)

def evaluate_gemini_iteration_result(
    source_image: Image.Image,
    result_image: Image.Image,
    element: str,
    change_text: str,
) -> Dict[str, Any]:
    edit_mask = _element_edit_mask_for_size(element, result_image.size).convert("L")
    edit_pixels = edit_mask.load()
    src_pixels = source_image.convert("RGBA").load()
    out_pixels = result_image.convert("RGBA").load()
    width, height = result_image.size

    changed_inside = 0
    changed_outside = 0
    subject_pixels_inside = 0
    for y in range(height):
        for x in range(width):
            inside = edit_pixels[x, y] > 0
            if src_pixels[x, y][3] > 0 and inside:
                subject_pixels_inside += 1
            if src_pixels[x, y] != out_pixels[x, y]:
                if inside:
                    changed_inside += 1
                else:
                    changed_outside += 1

    source_mask = largest_component_mask(detect_mask(source_image))
    result_mask = largest_component_mask(detect_mask(result_image))
    contamination_pixels = 0
    srcm = source_mask.load()
    outm = result_mask.load()
    for y in range(height):
        for x in range(width):
            if srcm[x, y] <= 0 and outm[x, y] > 0:
                contamination_pixels += 1

    changed_ratio = float(changed_inside) / float(max(1, subject_pixels_inside))
    result = {
        "changed_inside_edit_mask": changed_inside,
        "changed_outside_edit_mask": changed_outside,
        "subject_pixels_inside_edit_mask": subject_pixels_inside,
        "changed_ratio_inside_edit_mask": changed_ratio,
        "background_contamination_pixels": contamination_pixels,
        "view_correction_mode": _is_side_view_correction_request(element, change_text),
    }

    if result["view_correction_mode"]:
        result["status"] = "pass"
        result["reason"] = None
        return result

    min_changed = {
        "expression": 2,
        "accessories": 4,
        "hair/head": 6,
        "weapon/prop": 12,
        "outfit": 16,
        "palette/colors": 40,
        "pose": 24,
        "silhouette": 24,
        "proportions": 24,
    }.get(element, 4)
    max_ratio = {
        "expression": 0.38,
        "accessories": 0.45,
        "hair/head": 0.55,
        "weapon/prop": 0.7,
        "outfit": 0.75,
        "palette/colors": 1.0,
        "pose": 0.9,
        "silhouette": 0.95,
        "proportions": 0.95,
    }.get(element, 0.8)

    if changed_inside < min_changed:
        result["status"] = "fail"
        result["reason"] = "Gemini did not make a meaningful edit in the requested region."
        return result
    if changed_ratio > max_ratio:
        result["status"] = "fail"
        result["reason"] = "Gemini changed too much of the requested region for this edit type."
        return result
    if changed_outside > 0:
        result["status"] = "fail"
        result["reason"] = "Gemini changed pixels outside the requested edit region."
        return result
    if contamination_pixels > 0:
        result["status"] = "fail"
        result["reason"] = "Gemini introduced new foreground pixels outside the original character silhouette."
        return result

    result["status"] = "pass"
    result["reason"] = None
    return result

def build_iteration_prompt(
    brief: Dict[str, Any],
    element: str,
    change_text: str,
    *,
    source_concept_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Scaffold targeted concept iteration using generate-image-pixflux with init_image (img2img).

    init_image_strength (1-999): higher = closer to source. ~750 preserves character identity
    while still applying the targeted change from the description.
    """
    element = (element or "").strip()
    change_text = (change_text or "").strip()
    if not element:
        raise ValueError("Iteration requires 'element'.")
    if not change_text:
        raise ValueError("Iteration requires 'change_text'.")

    allowed_elements = set(ITERATION_ELEMENTS)
    if element not in allowed_elements:
        raise ValueError("Invalid element. Must be one of: %s" % ", ".join(sorted(allowed_elements)))

    style = _brief_pixel_lab_style(brief)
    canvas_size = PIXELLAB_CONCEPT_IMAGE_SIZE
    pixellab_description = _build_iteration_edit_prompt(
        brief,
        element,
        change_text,
        canvas_size=canvas_size,
    )

    if source_concept_path is None:
        raise ValueError("Iteration scaffolding requires source_concept_path.")
    if not isinstance(source_concept_path, Path):
        raise ValueError("source_concept_path must be a Path.")
    if not source_concept_path.exists():
        raise ValueError("source_concept_path does not exist: %s" % str(source_concept_path))

    with Image.open(source_concept_path) as loaded:
        rgba = loaded.convert("RGBA")
        side = min(rgba.size[0], rgba.size[1])
        left = (rgba.size[0] - side) // 2
        top = (rgba.size[1] - side) // 2
        cropped = rgba.crop((left, top, left + side, top + side))
        resized = cropped.resize((canvas_size, canvas_size), resample=Image.Resampling.NEAREST)
        init_image_b64 = _encode_png_base64(resized)
    mask_image, mask_boxes = _build_element_inpaint_mask(element, canvas_size)
    mask_image_b64 = _encode_png_base64(mask_image)

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
        "img2img": {
            "element": element,
            "init_image_strength": 750,
            "pixel_lab_endpoint": "POST /v1/generate-image-pixflux",
        },
        "inpaint": {
            "mask_boxes": mask_boxes,
            "crop_to_mask": True,
        },
    }

    display_prompt = pixellab_description + "\n\n" + "\n".join(
        [
            "DEBUG CONSTRAINTS (tool-enforced):",
            f"- Orientation: view=side, direction=east",
            f"- Canvas: {canvas_size}x{canvas_size}",
            f"- img2img element: {element}",
            f"- init_image_strength: 750",
            f"- Style mapping: outline={style['outline_style_user']} shading={style['shading_style_user']} detail={style['detail_level_user']}",
        ]
    )

    pixellab_params = {
        "description": pixellab_description,
        "init_image_b64": init_image_b64,
        "inpainting_image_b64": init_image_b64,
        "init_image_strength": 750,
        "image_size": {"width": canvas_size, "height": canvas_size},
        "mask_image_b64": mask_image_b64,
        "crop_to_mask": True,
        "view": "side",
        "direction": "east",
        "outline": style["outline_style_pixel_lab"],
        "shading": style["shading_style_pixel_lab"],
        "detail": style["detail_level_pixel_lab"],
        "no_background": True,
        "seed": seed,
    }

    return {
        "display_prompt": display_prompt,
        "pixellab_params": pixellab_params,
        "debug_constraints": debug_constraints,
    }

def get_gemini_client() -> Any:
    if not _GOOGLE_GENAI_AVAILABLE:
        raise ValueError("google-genai package not installed. Run: pip install google-genai")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    return _google_genai.Client(api_key=api_key)

def gemini_iterate_concept(
    source_image_bytes: bytes,
    element: str,
    change_text: str,
    brief: Dict[str, Any],
) -> bytes:
    """
    Use Gemini image editing to apply one targeted change to a sprite.

    Sends the original source image to Gemini and relies on the prompt to constrain the edit.
    Returns the modified image as PNG bytes at the original dimensions.
    """
    src = Image.open(io.BytesIO(source_image_bytes)).convert("RGBA")
    orig_w, orig_h = src.size
    prompt = _build_gemini_requirements_prompt(brief, element, change_text)

    client_factory = globals().get("gemini_client_factory")
    client = client_factory() if callable(client_factory) else get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=[
            _google_genai_types.Part.from_bytes(data=source_image_bytes, mime_type="image/png"),
            prompt,
        ],
        config=_google_genai_types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data:
            result_img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGBA")
            if result_img.size != (orig_w, orig_h):
                result_img = result_img.resize((orig_w, orig_h), resample=Image.Resampling.NEAREST)

            out_buf = io.BytesIO()
            result_img.save(out_buf, format="PNG")
            return out_buf.getvalue()

    raise ValueError("Gemini did not return an image. Response: %s" % str(response.candidates[0].content.parts))
