from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

from PIL import Image


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


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
    project["room_layout"] = load_json(room_layout_path(project_dir), default_room_layout(project_id, project.get("project_name") or "Untitled Project"))
    project["room_layout_history"] = load_json(room_layout_history_path(project_dir), default_room_layout_history(project_id, project["room_layout"]))
    project["level_validation_report"] = load_json(level_validation_report_path(project_dir), None)
    if not isinstance(project["level_validation_report"], dict):
        project["level_validation_report"] = validate_room_layout(project["room_layout"])
        project["level_validation_report"]["project_id"] = project_id
    project["pixellab_character"] = load_json(_pixellab_character_path(project_dir), None)
    project["pixellab_skeleton"] = load_json(_pixellab_skeleton_path(project_dir), None)
    project["pixellab_animations"] = _load_pixellab_animations_store(project_dir)
    project["concepts"] = [hydrate_concept(item, project["created_at"]) for item in load_concepts(project_dir)]
    project["pixellab_character"] = _normalize_east_only_character_source(project_dir, project["pixellab_character"], project["concepts"])
    project["pixellab_skeleton"] = load_json(_pixellab_skeleton_path(project_dir), None)
    project["pixellab_animations"] = _upscale_legacy_east_only_animation_frames(project_dir, project["pixellab_character"], project["pixellab_animations"])
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
    health_report, bundle_manifest = persist_project_integrity_metadata(project, project_dir)
    project["health_report"] = health_report
    project["health_report_path"] = str(project_health_report_path(project_dir).relative_to(project_dir))
    project["project_bundle_manifest"] = bundle_manifest
    project["project_bundle_manifest_path"] = str(project_bundle_manifest_path(project_dir).relative_to(project_dir))
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
        "room_layout",
        "room_layout_history",
        "level_validation_report",
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
        "health_report",
        "health_report_path",
        "project_bundle_manifest",
        "project_bundle_manifest_path",
    }}
    core["project_schema_version"] = int(project.get("project_schema_version") or PROJECT_SCHEMA_VERSION)
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
    if project.get("room_layout") is not None:
        room_layout_payload = copy.deepcopy(project["room_layout"])
        room_layout_payload.setdefault("meta", {})
        room_layout_payload["meta"]["project_id"] = project["project_id"]
        room_layout_payload["meta"]["project_name"] = project.get("project_name") or project["project_id"]
        room_layout_payload["meta"]["updated_at"] = now_iso()
        write_json(room_layout_path(project_dir), room_layout_payload)
    if project.get("room_layout_history") is not None:
        room_history_payload = copy.deepcopy(project["room_layout_history"])
        room_history_payload["project_id"] = project["project_id"]
        write_json(room_layout_history_path(project_dir), room_history_payload)
    if project.get("level_validation_report") is not None:
        validation_payload = copy.deepcopy(project["level_validation_report"])
        validation_payload["project_id"] = project["project_id"]
        write_json(level_validation_report_path(project_dir), validation_payload)
    for concept in project.get("concepts", []) or []:
        save_concept(project_dir, concept)
    persist_project_integrity_metadata(project, project_dir)
