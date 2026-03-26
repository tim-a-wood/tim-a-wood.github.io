from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageChops


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


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
        key=lambda entry: int(
            next(
                (
                    item.get("draw_order", 0)
                    for item in (manifest.get("parts") or [])
                    if item.get("part_name") == entry.get("part_name")
                ),
                0,
            )
        ),
        reverse=True,
    )
    for shape_entry in ordered_shape_entries:
        part_name = str(shape_entry.get("part_name") or "").strip()
        if not part_name:
            continue
        shape_mask = (
            normalize_mask(Image.open(project_dir / shape_entry["mask_path"]).convert("L"))
            if shape_entry.get("mask_path")
            else render_polygon_mask(source_image.size, shape_entry.get("vertices") or [])
        )
        isolated_mask = normalize_mask(ImageChops.multiply(shape_mask, source_mask))
        isolated_mask = normalize_mask(ImageChops.subtract(isolated_mask, assigned_mask))
        bbox = list(isolated_mask.getbbox() or tuple(shape_entry.get("bbox") or (0, 0, 1, 1)))
        cropped_image = image_with_mask(source_image, isolated_mask).crop(tuple(bbox))
        cropped_mask = isolated_mask.crop(tuple(bbox))
        image_path, mask_path = write_part_split_asset(project_dir, part_name, cropped_image, cropped_mask)
        manifest_entry = next((item for item in (manifest.get("parts") or []) if item.get("part_name") == part_name), {})
        parts.append(
            {
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
            }
        )
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
        lines.extend(
            [
                "",
                "Context:",
                f"- selected concept id: {concept.get('concept_id')}",
                f"- source image: {concept.get('approved_source_image')}",
            ]
        )
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
        parts.append(
            {
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
            }
        )

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
