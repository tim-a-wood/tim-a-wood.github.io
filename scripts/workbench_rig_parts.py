from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


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
        "prop_definition": {
            "type": concept.get("prop_variant") or project["brief"]["prop"],
            "attachment_joint": "wrist_right",
        },
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
    project["rig_layout_history"] = load_json(
        rig_layout_history_path(PROJECTS_ROOT / project_id),
        default_rig_layout_history(project_id),
    )
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
            layout["codex_check"].update(
                {
                    "valid": False,
                    "summary": summary or "Codex did not approve this image for rig layout generation.",
                    "applied_at": now_iso(),
                    "raw_response_excerpt": response_text[:1200],
                }
            )
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
        lines.extend(
            [
                "",
                "Current manifest draft:",
                "- %s"
                % "\n- ".join(
                    "%s (%s)" % (item.get("part_name"), "required" if item.get("required") else "optional")
                    for item in current_parts
                ),
            ]
        )
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
        lines.extend(
            [
                "",
                "Approved manifest parts:",
                "- %s" % "\n- ".join(item["part_name"] for item in manifest["parts"]),
            ]
        )
    if part_shapes and part_shapes.get("parts"):
        lines.extend(
            [
                "",
                "Current shape draft parts:",
                "- %s" % "\n- ".join(item["part_name"] for item in part_shapes["parts"]),
            ]
        )
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
        manifest.setdefault("parts", []).append(
            {
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
            }
        )
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
        manifest["parts"] = [
            item
            for item in manifest.get("parts", [])
            if item.get("part_name") != part_name or item.get("required")
        ]
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
    part_shapes = build_default_part_shapes(
        project,
        project.get("part_manifest") or {},
        source_image,
        approved_rel,
        operation_source="auto_init",
    )
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
            refreshed = build_default_part_shapes(
                project,
                {
                    "parts": [
                        next(
                            item
                            for item in (project.get("part_manifest") or {}).get("parts", [])
                            if item.get("part_name") == part_name
                        )
                    ]
                },
                source_image,
                source_rel,
                operation_source="auto_init",
            )
            if refreshed.get("parts"):
                index = next(
                    (idx for idx, item in enumerate(part_shapes.get("parts", [])) if item.get("part_name") == part_name),
                    None,
                )
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
