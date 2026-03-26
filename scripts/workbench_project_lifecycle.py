from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable, Dict


PROJECTS_ROOT: Path
ROOM_LAYOUT_FILENAME: str
ROOM_LAYOUT_HISTORY_FILENAME: str
LEVEL_VALIDATION_REPORT_FILENAME: str
CANONICAL_DOWNSTREAM_FILES: Dict[str, str]
LEGACY_DOWNSTREAM_FILES: Dict[str, str]

normalize_prompt_text: Callable[[str], str]
build_brief_from_payload: Callable[[Dict[str, Any], Any], Dict[str, Any]]
merge_new_references: Callable[[Path, Dict[str, Any], Dict[str, Any]], Dict[str, Any]]
slugify: Callable[[str], str]
stable_hash: Callable[..., str]
now_iso: Callable[[], str]
ensure_dirs: Callable[[Path], None]
normalize_wizard_state: Callable[[Any], Dict[str, Any]]
set_wizard_step_complete: Callable[[Dict[str, Any], str], Dict[str, Any]]
default_ai_workflow: Callable[[str], Dict[str, Any]]
default_external_authoring: Callable[[str], Dict[str, Any]]
default_room_layout: Callable[[str, str], Dict[str, Any]]
default_room_layout_history: Callable[[str, Any], Dict[str, Any]]
validate_room_layout: Callable[[Any], Dict[str, Any]]
save_project: Callable[[Dict[str, Any]], None]
load_project: Callable[[str], Dict[str, Any]]
delete_path: Callable[[Path], None]
legacy_downstream_path: Callable[[Path, str], Path]


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


def create_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_name = (payload.get("project_name") or "").strip()
    prompt = normalize_prompt_text(payload.get("prompt_text") or "")
    if not project_name and not prompt:
        raise ValueError("Project name or prompt is required.")

    brief = build_brief_from_payload(payload)
    project_id = "%s-%s" % (
        slugify(project_name or brief["role_archetype"]),
        stable_hash(project_name, prompt, now_iso())[:8],
    )
    project_dir = PROJECTS_ROOT / project_id
    ensure_dirs(project_dir)
    brief = merge_new_references(project_dir, brief, payload)

    now = now_iso()
    initial_mode = "wizard"
    wizard_state = normalize_wizard_state(payload.get("wizard_state"))
    wizard_state = set_wizard_step_complete(wizard_state, "project")
    if prompt or any(payload.get(key) for key in [
        "role_archetype",
        "silhouette_intent",
        "outfit_materials",
        "prop",
        "palette_mood",
        "shape_language",
        "mood_tone",
        "side_view_constraints",
        "negative_prompt",
    ]):
        wizard_state = set_wizard_step_complete(wizard_state, "brief")
        wizard_state["current_step"] = "concepts"

    project = {
        "project_id": project_id,
        "project_name": project_name or brief["role_archetype"].title(),
        "prompt_text": prompt,
        "created_at": now,
        "updated_at": now,
        "current_stage": "intake",
        "status": "ready_for_concepts",
        "layer_review_approved": False,
        "rig_review_approved": False,
        "selected_concept_id": None,
        "archived_at": None,
        "last_ui_mode": initial_mode,
        "wizard_state": wizard_state,
        "brief": brief,
        "character_spec": None,
        "layered_character": None,
        "rig": None,
        "animation_templates": None,
        "ai_workflow": default_ai_workflow(project_id),
        "external_authoring": default_external_authoring(project_id),
        "qa_report": None,
        "history": {"project_id": project_id, "events": []},
        "concepts": [],
        "room_layout": default_room_layout(project_id, project_name or brief["role_archetype"].title()),
        "room_layout_history": None,
        "level_validation_report": None,
    }
    project["room_layout_history"] = default_room_layout_history(project_id, project["room_layout"])
    project["level_validation_report"] = validate_room_layout(project["room_layout"])
    project["level_validation_report"]["project_id"] = project_id
    save_project(project)
    return load_project(project_id)


def update_project_brief(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    brief = build_brief_from_payload(payload, project["brief"])
    project_dir = PROJECTS_ROOT / project_id
    brief = merge_new_references(project_dir, brief, payload)
    project["brief"] = brief
    project["prompt_text"] = brief["raw_prompt"]
    project["updated_at"] = now_iso()
    project["status"] = "ready_for_concepts"
    project["wizard_state"] = set_wizard_step_complete(project.get("wizard_state"), "brief")
    if project["last_ui_mode"] == "wizard" and project["wizard_state"]["current_step"] in {"project", "brief", "describe"}:
        project["wizard_state"]["current_step"] = "concepts"
    save_project(project)
    return load_project(project_id)


def duplicate_project(project_id: str) -> Dict[str, Any]:
    source = load_project(project_id)
    new_id = "%s-%s" % (
        slugify("%s copy" % source["project_name"]),
        stable_hash(source["project_id"], now_iso())[:8],
    )
    new_dir = PROJECTS_ROOT / new_id
    ensure_dirs(new_dir)

    for filename in [
        "project.json",
        "brief.json",
        "character_spec.json",
        "history.json",
        ROOM_LAYOUT_FILENAME,
        ROOM_LAYOUT_HISTORY_FILENAME,
        LEVEL_VALIDATION_REPORT_FILENAME,
        CANONICAL_DOWNSTREAM_FILES["part_manifest"],
        CANONICAL_DOWNSTREAM_FILES["part_manifest_history"],
        CANONICAL_DOWNSTREAM_FILES["part_shapes"],
        CANONICAL_DOWNSTREAM_FILES["part_shapes_history"],
        CANONICAL_DOWNSTREAM_FILES["part_split"],
        CANONICAL_DOWNSTREAM_FILES["part_split_history"],
        CANONICAL_DOWNSTREAM_FILES["sprite_model"],
        CANONICAL_DOWNSTREAM_FILES["sprite_model_history"],
        CANONICAL_DOWNSTREAM_FILES["rig"],
        CANONICAL_DOWNSTREAM_FILES["animation_clips"],
        CANONICAL_DOWNSTREAM_FILES["manual_animation_clips"],
        CANONICAL_DOWNSTREAM_FILES["ai_workflow"],
        CANONICAL_DOWNSTREAM_FILES["external_authoring"],
        CANONICAL_DOWNSTREAM_FILES["qa_report"],
        LEGACY_DOWNSTREAM_FILES["layered_character"],
        LEGACY_DOWNSTREAM_FILES["animation_templates"],
        LEGACY_DOWNSTREAM_FILES["palette"],
    ]:
        src = PROJECTS_ROOT / project_id / filename
        if src.exists():
            shutil.copy2(src, new_dir / filename)

    for folder in ["concepts", "prompts", "references", "master_pose", "part_shapes", "part_split", "parts", "rig", "animations", "manual_clips", "ai_workflow", "external_authoring", "layers", "logs"]:
        src_folder = PROJECTS_ROOT / project_id / folder
        dst_folder = new_dir / folder
        dst_folder.mkdir(parents=True, exist_ok=True)
        if src_folder.exists():
            for path in src_folder.rglob("*"):
                target = dst_folder / path.relative_to(src_folder)
                if path.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif path.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)

    duplicated = load_project(new_id)
    duplicated["project_id"] = new_id
    duplicated["project_name"] = "%s Copy" % source["project_name"]
    duplicated["created_at"] = now_iso()
    duplicated["updated_at"] = now_iso()
    duplicated["current_stage"] = "concept_lock" if source.get("character_spec") else "concepts"
    duplicated["status"] = "branched_from_%s" % source["project_id"]
    duplicated["sprite_model_approved"] = False
    duplicated["layer_review_approved"] = False
    duplicated["rig_review_approved"] = False
    duplicated["last_export"] = None
    duplicated["archived_at"] = None
    duplicated["last_ui_mode"] = "wizard"
    duplicated["wizard_state"] = normalize_wizard_state(source.get("wizard_state"))
    if duplicated.get("history"):
        duplicated["history"]["project_id"] = new_id
    if isinstance(duplicated.get("room_layout"), dict):
        duplicated["room_layout"].setdefault("meta", {})
        duplicated["room_layout"]["meta"]["project_id"] = new_id
        duplicated["room_layout"]["meta"]["project_name"] = duplicated["project_name"]
    if isinstance(duplicated.get("room_layout_history"), dict):
        duplicated["room_layout_history"]["project_id"] = new_id
    if isinstance(duplicated.get("level_validation_report"), dict):
        duplicated["level_validation_report"]["project_id"] = new_id
    for concept in duplicated.get("concepts", []) or []:
        concept["project_id"] = new_id
    save_project(duplicated)
    delete_path(legacy_downstream_path(new_dir, "layered_character"))
    delete_path(legacy_downstream_path(new_dir, "animation_templates"))
    delete_path(legacy_downstream_path(new_dir, "palette"))
    return load_project(new_id)
