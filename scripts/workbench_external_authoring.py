from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


def get_external_authoring(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    return project.get("external_authoring") or default_external_authoring(project_id)


def update_external_authoring(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = hydrate_external_authoring(project.get("external_authoring"), project_dir)
    if "enabled" in payload:
        store["enabled"] = bool(payload.get("enabled"))
    provider = str(payload.get("provider") or store.get("provider") or "skelform")
    if provider != "skelform":
        raise ValueError("Only skelform is currently supported for embedded external authoring.")
    store["provider"] = provider
    store["provider_profile"] = skelform_provider_profile()
    store["updated_at"] = now_iso()
    project["external_authoring"] = store
    project["current_stage"] = "external_authoring" if store["enabled"] else project.get("current_stage", "intake")
    project["status"] = "external_authoring_enabled" if store["enabled"] else project.get("status", "ready")
    project["updated_at"] = now_iso()
    if store["enabled"]:
        project["wizard_state"] = set_wizard_step_complete(project.get("wizard_state"), "review")
        project["wizard_state"]["current_step"] = "character"
    save_project(project)
    return load_project(project_id)["external_authoring"]


def open_external_authoring_session(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = hydrate_external_authoring(project.get("external_authoring"), project_dir)
    if not store.get("enabled"):
        raise ValueError("Enable external authoring before opening a SkelForm session.")
    store["session"] = {
        **store.get("session", {}),
        "editor_url": SKELFORM_EDITOR_URL,
        "embed_url": "%s?utm_source=sprite_workbench&project_id=%s" % (SKELFORM_EDITOR_URL, quote(project_id)),
        "can_embed": True,
        "source_mode": "hosted",
        "last_opened_at": now_iso(),
    }
    store["updated_at"] = now_iso()
    project["external_authoring"] = store
    project["current_stage"] = "external_authoring"
    project["status"] = "external_authoring_session_ready"
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["external_authoring"]


def _store_uploaded_or_local_asset(
    project_dir: Path,
    bundle_dir: Path,
    payload: Dict[str, Any],
    stem: str,
    default_suffix: str,
) -> Optional[str]:
    data_url = payload.get("%s_data_url" % stem)
    local_path = payload.get("%s_local_path" % stem)
    original_name = payload.get("%s_name" % stem) or stem
    if data_url:
        mime_type, raw = parse_data_url(str(data_url))
        suffix = guess_extension(str(original_name), mime_type) or default_suffix
        target = bundle_dir / ("%s%s" % (sanitize_filename(Path(str(original_name)).stem, stem), suffix))
        target.write_bytes(raw)
        return str(target.relative_to(project_dir))
    if local_path:
        source = Path(str(local_path)).expanduser()
        if not source.exists() or not source.is_file():
            raise ValueError("%s path does not exist: %s" % (stem, local_path))
        suffix = source.suffix or default_suffix
        target = bundle_dir / ("%s%s" % (sanitize_filename(source.stem, stem), suffix))
        shutil.copy2(source, target)
        return str(target.relative_to(project_dir))
    return None


def import_external_authoring_bundle(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = hydrate_external_authoring(project.get("external_authoring"), project_dir)
    if not store.get("enabled"):
        raise ValueError("Enable external authoring before importing a bundle.")
    bundle_id = "bundle-%s" % uuid.uuid4().hex[:8]
    bundle_dir = external_authoring_import_root(project_dir) / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    spritesheet_path = _store_uploaded_or_local_asset(project_dir, bundle_dir, payload, "spritesheet", ".png")
    atlas_path = _store_uploaded_or_local_asset(project_dir, bundle_dir, payload, "atlas", ".json")
    animations_path = _store_uploaded_or_local_asset(project_dir, bundle_dir, payload, "animations", ".json")
    preview_gif_path = _store_uploaded_or_local_asset(project_dir, bundle_dir, payload, "preview_gif", ".gif")
    if not spritesheet_path:
        raise ValueError("Import requires a spritesheet upload or local path.")
    if not atlas_path:
        raise ValueError("Import requires an atlas JSON upload or local path.")
    if not animations_path:
        raise ValueError("Import requires an animations JSON upload or local path.")
    atlas = load_json(project_dir / atlas_path, None)
    animations = load_json(project_dir / animations_path, None)
    if not isinstance(atlas, dict) or not isinstance(atlas.get("frames"), dict):
        raise ValueError("Atlas JSON must contain a top-level frames object.")
    if not isinstance(animations, dict) or not animations:
        raise ValueError("Animations JSON must be a non-empty object.")
    store["imported_bundle"] = {
        "bundle_id": bundle_id,
        "provider": "skelform",
        "imported_at": now_iso(),
        "source_label": str(payload.get("source_label") or "SkelForm export").strip() or "SkelForm export",
        "notes": str(payload.get("notes") or "").strip() or None,
        "spritesheet_image_path": spritesheet_path,
        "atlas_path": atlas_path,
        "animations_path": animations_path,
        "preview_gif_path": preview_gif_path,
        "animation_names": sorted(animations.keys()),
        "frame_count": len(atlas.get("frames") or {}),
    }
    store["updated_at"] = now_iso()
    project["external_authoring"] = store
    project["current_stage"] = "external_authoring"
    project["status"] = "external_authoring_bundle_imported"
    project["updated_at"] = now_iso()
    project["wizard_state"] = set_wizard_step_complete(project.get("wizard_state"), "clips")
    project["wizard_state"]["current_step"] = "export"
    save_project(project)
    return load_project(project_id)["external_authoring"]
