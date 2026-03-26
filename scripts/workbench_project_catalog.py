from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


PROJECTS_ROOT: Path
PROJECT_SCHEMA_VERSION: int
DEMO_PROJECT_FIXTURE_ROOT: Path

now_iso: Callable[[], str]
slugify: Callable[[str], str]
stable_hash: Callable[..., str]
load_json: Callable[[Path, Any], Any]
load_project: Callable[[str], Dict[str, Any]]
save_project: Callable[[Dict[str, Any]], None]
apply_project_defaults: Callable[[Dict[str, Any]], Dict[str, Any]]
ensure_dirs: Callable[[Path], None]
append_history_event: Callable[[str, Dict[str, Any]], Dict[str, Any]]
parse_data_url: Callable[[str], Any]
project_backup_filename: Callable[[Dict[str, Any]], str]
load_project_health_summary: Callable[[Path], Dict[str, Any]]
normalize_wizard_state: Callable[[Any], Dict[str, Any]]


ROOM_LAYOUT_FILENAME: str
ROOM_LAYOUT_HISTORY_FILENAME: str
LEVEL_VALIDATION_REPORT_FILENAME: str


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


def _humanize_key(value: str) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").strip().title() or "Sample Project"


def list_demo_projects() -> List[Dict[str, Any]]:
    if not DEMO_PROJECT_FIXTURE_ROOT.exists():
        return []
    descriptions = {
        "canonical-sprite-model": "Canonical downstream contract with approved sprite-model, rig, clips, QA, and export data.",
        "hybrid-mixed-pipeline": "Mixed legacy/canonical project for compatibility and migration testing.",
        "legacy-layered-character": "Legacy layered-character project for older downstream contract coverage.",
    }
    demos: List[Dict[str, Any]] = []
    for path in sorted(DEMO_PROJECT_FIXTURE_ROOT.iterdir()):
        if not path.is_dir() or not (path / "project.json").exists():
            continue
        project = apply_project_defaults(load_json(path / "project.json", {}))
        demos.append({
            "fixture_name": path.name,
            "project_id": project.get("project_id") or path.name,
            "project_name": project.get("project_name") or _humanize_key(path.name),
            "description": descriptions.get(path.name, "Sprite Workbench sample project."),
        })
    return demos


def import_demo_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    fixture_name = str(payload.get("fixture_name") or "").strip()
    if not fixture_name:
        raise ValueError("Demo import requires fixture_name.")
    source_dir = DEMO_PROJECT_FIXTURE_ROOT / fixture_name
    if not source_dir.exists() or not (source_dir / "project.json").exists():
        raise ValueError("Unknown demo project: %s." % fixture_name)

    imported_project_data = apply_project_defaults(load_json(source_dir / "project.json", {}))
    imported_project_id = str(imported_project_data.get("project_id") or "").strip() or fixture_name
    target_project_id = imported_project_id
    if (PROJECTS_ROOT / target_project_id).exists():
        target_project_id = "%s-%s" % (
            slugify(imported_project_data.get("project_name") or imported_project_id) or imported_project_id,
            stable_hash(imported_project_id, now_iso())[:8],
        )

    project_dir = PROJECTS_ROOT / target_project_id
    ensure_dirs(project_dir)
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or path.name == ".DS_Store":
            continue
        rel = path.relative_to(source_dir)
        target = project_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    imported = load_project(target_project_id)
    imported["project_id"] = target_project_id
    imported["project_schema_version"] = int(imported.get("project_schema_version") or PROJECT_SCHEMA_VERSION)
    imported["archived_at"] = None
    imported["updated_at"] = now_iso()
    imported["status"] = "demo_imported"
    history = imported.get("history") if isinstance(imported.get("history"), dict) else {}
    if isinstance(history, dict):
        history["project_id"] = target_project_id
        imported["history"] = history
    if isinstance(imported.get("room_layout"), dict):
        imported["room_layout"].setdefault("meta", {})
        imported["room_layout"]["meta"]["project_id"] = target_project_id
        imported["room_layout"]["meta"]["project_name"] = imported.get("project_name") or target_project_id
    for key in (
        "room_layout_history",
        "level_validation_report",
        "rig_layout_history",
        "part_manifest_history",
        "part_shapes_history",
        "part_split_history",
        "sprite_model_history",
        "manual_animation_clips",
        "ai_workflow",
        "external_authoring",
        "pixellab_animations",
    ):
        value = imported.get(key)
        if isinstance(value, dict):
            value["project_id"] = target_project_id
    for concept in imported.get("concepts", []) or []:
        concept["project_id"] = target_project_id
    save_project(imported)
    append_history_event(target_project_id, {
        "type": "demo_project_imported",
        "fixture_name": fixture_name,
        "created_at": now_iso(),
    })
    return load_project(target_project_id)


def build_project_bundle_archive(project_id: str) -> tuple[str, bytes]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(project_dir.rglob("*")):
            if not path.is_file() or path.name == ".DS_Store":
                continue
            arcname = "%s/%s" % (project_id, path.relative_to(project_dir).as_posix())
            zf.write(path, arcname)
    return project_backup_filename(project), buffer.getvalue()


def _normalize_import_bundle_members(names: List[str]) -> Dict[str, str]:
    files = [name for name in names if name and not name.endswith("/") and Path(name).name != ".DS_Store"]
    if not files:
        raise ValueError("Project bundle is empty.")
    top_levels = {Path(name).parts[0] for name in files if Path(name).parts}
    strip_prefix = None
    if len(top_levels) == 1:
        candidate = next(iter(top_levels))
        if all(len(Path(name).parts) >= 2 for name in files):
            strip_prefix = candidate
    normalized: Dict[str, str] = {}
    for name in files:
        path = Path(name)
        rel = Path(*path.parts[1:]) if strip_prefix and path.parts and path.parts[0] == strip_prefix else path
        if not rel.parts:
            continue
        rel_text = rel.as_posix()
        if rel_text.startswith("../") or rel_text.startswith("/"):
            raise ValueError("Project bundle contains unsafe paths.")
        normalized[name] = rel_text
    return normalized


def import_project_bundle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data_url = payload.get("data_url")
    if not data_url:
        raise ValueError("Import bundle requires data_url.")
    mime_type, raw = parse_data_url(str(data_url))
    if mime_type not in {"application/zip", "application/x-zip-compressed", "application/octet-stream"}:
        if ".zip" not in str(payload.get("name") or "").lower():
            raise ValueError("Import bundle must be a .zip file.")

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_root = Path(tmpdir)
        try:
            with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
                member_map = _normalize_import_bundle_members(zf.namelist())
                if "project.json" not in member_map.values():
                    raise ValueError("Project bundle is missing project.json.")
                for member_name, rel_text in member_map.items():
                    target = temp_root / rel_text
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member_name, "r") as source, target.open("wb") as dest:
                        shutil.copyfileobj(source, dest)
        except zipfile.BadZipFile as exc:
            raise ValueError("Import bundle is not a valid zip archive.") from exc

        imported_project_data = apply_project_defaults(load_json(temp_root / "project.json", {}))
        imported_project_id = str(imported_project_data.get("project_id") or "").strip() or slugify(
            str(imported_project_data.get("project_name") or Path(str(payload.get("name") or "imported-project")).stem)
        )
        if not imported_project_id:
            imported_project_id = "imported-project"
        target_project_id = imported_project_id
        if (PROJECTS_ROOT / target_project_id).exists():
            target_project_id = "%s-%s" % (
                slugify(imported_project_data.get("project_name") or imported_project_id) or imported_project_id,
                stable_hash(imported_project_id, now_iso())[:8],
            )

        project_dir = PROJECTS_ROOT / target_project_id
        ensure_dirs(project_dir)
        for path in sorted(temp_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(temp_root)
            target = project_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

    imported = load_project(target_project_id)
    imported["project_id"] = target_project_id
    imported["project_schema_version"] = int(imported.get("project_schema_version") or PROJECT_SCHEMA_VERSION)
    imported["archived_at"] = None
    imported["updated_at"] = now_iso()
    if imported.get("history"):
        imported["history"]["project_id"] = target_project_id
    if isinstance(imported.get("room_layout"), dict):
        imported["room_layout"].setdefault("meta", {})
        imported["room_layout"]["meta"]["project_id"] = target_project_id
        imported["room_layout"]["meta"]["project_name"] = imported.get("project_name") or target_project_id
    for key in (
        "room_layout_history",
        "level_validation_report",
        "rig_layout_history",
        "part_manifest_history",
        "part_shapes_history",
        "part_split_history",
        "sprite_model_history",
        "manual_animation_clips",
        "ai_workflow",
        "external_authoring",
        "pixellab_animations",
    ):
        value = imported.get(key)
        if isinstance(value, dict):
            value["project_id"] = target_project_id
    for concept in imported.get("concepts", []) or []:
        concept["project_id"] = target_project_id
    save_project(imported)
    append_history_event(target_project_id, {
        "type": "project_bundle_imported",
        "source_name": payload.get("name") or project_backup_filename(imported),
        "created_at": now_iso(),
    })
    return load_project(target_project_id)


def list_projects(include_archived: bool) -> List[Dict[str, Any]]:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(PROJECTS_ROOT.iterdir()):
        if not path.is_dir():
            continue
        project = apply_project_defaults(load_json(path / "project.json", {}))
        if not project.get("project_id"):
            continue
        if project.get("archived_at") and not include_archived:
            continue
        project["project_health_summary"] = load_project_health_summary(path)
        items.append(project)
    return items


def project_summary(project: Dict[str, Any]) -> Dict[str, Any]:
    wizard_state = normalize_wizard_state(project.get("wizard_state"))
    sprite_model_approved = bool(project.get("sprite_model_approved") or project.get("layer_review_approved"))
    health_summary = project.get("project_health_summary") or {}
    return {
        "project_id": project["project_id"],
        "project_name": project["project_name"],
        "project_schema_version": int(project.get("project_schema_version") or PROJECT_SCHEMA_VERSION),
        "created_at": project["created_at"],
        "updated_at": project["updated_at"],
        "current_stage": project["current_stage"],
        "status": project["status"],
        "selected_concept_id": project.get("selected_concept_id"),
        "master_pose_approved": project.get("master_pose_approved", False),
        "rig_layout_approved": project.get("rig_layout_approved", False),
        "part_split_approved": project.get("part_split_approved", False),
        "split_review_approved": project.get("split_review_approved", False),
        "sprite_model_approved": sprite_model_approved,
        "layer_review_approved": sprite_model_approved,
        "rig_review_approved": project.get("rig_review_approved", False),
        "archived_at": project.get("archived_at"),
        "last_export": project.get("last_export"),
        "last_ui_mode": project.get("last_ui_mode", "wizard"),
        "ai_workflow_enabled": bool((project.get("ai_workflow") or {}).get("enabled")),
        "ai_workflow_legacy_mode": bool((project.get("ai_workflow") or {}).get("legacy_mode")),
        "external_authoring_enabled": bool((project.get("external_authoring") or {}).get("enabled")),
        "project_health_status": health_summary.get("status", "unknown"),
        "project_health_warning_count": int(health_summary.get("warning_count") or 0),
        "project_health_missing_file_count": int(health_summary.get("missing_file_count") or 0),
        "wizard_state": wizard_state,
        "can_resume_wizard": wizard_state.get("current_step") not in {None, "project", "export"},
    }
