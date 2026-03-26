from __future__ import annotations

import copy
import io
import math
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageOps

FRAME_PIVOT = (128, 245)
LEGACY_RIG_PROFILE = "side_humanoid_full_20"


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


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

def _animation_clip_source_has_raster_paths(clip_source: Dict[str, Any]) -> bool:
    fr = clip_source.get("frames")
    if isinstance(fr, list) and fr:
        return True
    fbd = clip_source.get("frames_by_direction")
    if isinstance(fbd, dict):
        for v in fbd.values():
            if isinstance(v, list) and v:
                return True
    return False

def _hydrate_raster_bridge_animation_clip(
    animation_name: str,
    clip_source: Dict[str, Any],
    rig_profile: str,
) -> Dict[str, Any]:
    """
    Hydrate a non-idle/walk animation_clips entry produced by pixellab/build-clips.

    Deterministic rig preview still expects joint_transforms_per_frame; synthesize from the
    walk cycle pattern, trimmed/padded to match exported raster frame count.
    """
    bridge_frames = clip_source.get("frames") if isinstance(clip_source.get("frames"), list) else []
    n = len(bridge_frames) if bridge_frames else int(clip_source.get("frame_count") or 8)
    n = max(1, min(int(n), 48))
    controls = normalize_clip_controls("walk", None)
    walk_fc = ANIMATION_SPECS["walk"]["frame_count"]
    overrides_full = clip_frame_overrides(walk_fc, None)
    base = generate_clip_frames("walk", controls, overrides_full, rig_profile=rig_profile)
    jt: List[Dict[str, Any]] = [copy.deepcopy(base[i % len(base)]) for i in range(n)]
    clip_out: Dict[str, Any] = {
        "frame_count": n,
        "fps": int(clip_source.get("fps") or 12),
        "loop": bool(clip_source.get("loop", True)),
        "root_motion_policy": "in_place",
        "loop_continuity_rules": {"wrap_to_first_frame": True},
        "controls": controls,
        "frame_overrides": clip_frame_overrides(n, None),
        "joint_transforms_per_frame": jt,
        "neutral_pose_frame_index": 0,
        "corrective_assets_per_frame": [[] for _ in jt],
    }
    if isinstance(clip_source.get("frames"), list):
        clip_out["frames"] = clip_source.get("frames")
    if isinstance(clip_source.get("frames_by_direction"), dict):
        clip_out["frames_by_direction"] = clip_source.get("frames_by_direction")
    bf = clip_out.get("frames")
    if isinstance(bf, list) and bf:
        fc = len(bf)
        clip_out["frame_count"] = fc
        if fc != len(clip_out["joint_transforms_per_frame"]):
            clip_out["joint_transforms_per_frame"] = [copy.deepcopy(base[i % len(base)]) for i in range(fc)]
            clip_out["frame_overrides"] = clip_frame_overrides(fc, None)
            clip_out["corrective_assets_per_frame"] = [[] for _ in range(fc)]
        if clip_source.get("fps") is not None:
            try:
                clip_out["fps"] = int(clip_source["fps"])
            except (TypeError, ValueError):
                pass
        if "loop" in clip_source:
            clip_out["loop"] = bool(clip_source["loop"])
    return clip_out

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
            # `clip_out` already merged ANIMATION_SPECS (idle=6, walk=8). On-disk bridge
            # from synced Pixel Lab clips can have fewer raster paths; if we only copy `frames`
            # and not timing/count, load_project leaves frame_count=6 with len(frames)=4 and
            # Pixel Lab QA falsely asks for a re-sync.
            bridge_frames = clip_out.get("frames")
            if isinstance(bridge_frames, list) and bridge_frames:
                clip_out["frame_count"] = len(bridge_frames)
                if clip_source.get("fps") is not None:
                    try:
                        clip_out["fps"] = int(clip_source["fps"])
                    except (TypeError, ValueError):
                        pass
                if "loop" in clip_source:
                    clip_out["loop"] = bool(clip_source["loop"])

        clips[animation_name] = clip_out
    if isinstance(source, dict):
        for animation_name, clip_source in source.items():
            if animation_name in clips or not isinstance(clip_source, dict):
                continue
            if not _animation_clip_source_has_raster_paths(clip_source):
                continue
            clips[str(animation_name)] = _hydrate_raster_bridge_animation_clip(
                str(animation_name), clip_source, rig_profile
            )
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
