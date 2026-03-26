from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


def apply_project_defaults(project: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(project or {})
    normalized.setdefault("project_id", "")
    normalized.setdefault("project_name", "Untitled Project")
    normalized.setdefault("project_schema_version", PROJECT_SCHEMA_VERSION)
    normalized.setdefault("prompt_text", "")
    normalized.setdefault("created_at", now_iso())
    normalized.setdefault("updated_at", normalized["created_at"])
    normalized.setdefault("current_stage", "intake")
    normalized.setdefault("status", "ready_for_concepts")
    normalized.setdefault("layer_review_approved", False)
    normalized.setdefault("rig_review_approved", False)
    normalized.setdefault("master_pose_approved", False)
    normalized.setdefault("sprite_model_approved", False)
    normalized.setdefault("rig_layout_approved", False)
    normalized.setdefault("part_manifest_approved", False)
    normalized.setdefault("part_shapes_approved", False)
    normalized.setdefault("part_split_approved", False)
    normalized.setdefault("split_review_approved", False)
    normalized.setdefault("selected_concept_id", None)
    normalized.setdefault("archived_at", None)
    normalized.setdefault("last_ui_mode", "wizard")
    normalized.setdefault("wizard_state", None)
    normalized.setdefault("ai_workflow", None)
    normalized.setdefault("external_authoring", None)
    return normalized


def default_wizard_state() -> Dict[str, Any]:
    return {
        "current_step": "project",
        "last_completed_step": None,
        "completed_steps": [],
        "skipped_optional_steps": [],
        "show_advanced": False,
    }


def normalize_wizard_state(payload: Any) -> Dict[str, Any]:
    state = default_wizard_state()
    if isinstance(payload, dict):
        current_step = payload.get("current_step")
        if current_step in WIZARD_STEPS_KNOWN:
            state["current_step"] = current_step
        last_completed = payload.get("last_completed_step")
        if last_completed in WIZARD_STEPS_KNOWN:
            state["last_completed_step"] = last_completed
        completed = [item for item in payload.get("completed_steps", []) if item in WIZARD_STEPS_KNOWN]
        skipped = [item for item in payload.get("skipped_optional_steps", []) if item in WIZARD_STEPS_KNOWN]
        state["completed_steps"] = list(dict.fromkeys(completed))
        state["skipped_optional_steps"] = list(dict.fromkeys(skipped))
        state["show_advanced"] = bool(payload.get("show_advanced", False))
    return state


def migrate_modern_ai_wizard_state(state: Dict[str, Any]) -> Dict[str, Any]:
    ws = normalize_wizard_state(state)
    alias = {
        "project": "describe",
        "brief": "describe",
        "references": "describe",
        "review": "concepts",
        "character": "concepts",
        "clips": "animations",
        "qa": "export",
    }
    cur = ws.get("current_step")
    if cur in alias:
        ws["current_step"] = alias[cur]
    new_completed: List[str] = []
    for item in ws.get("completed_steps", []):
        mapped = alias.get(item, item)
        if mapped not in new_completed:
            new_completed.append(mapped)
    ws["completed_steps"] = new_completed
    return ws


def set_wizard_step_complete(state: Dict[str, Any], step: str) -> Dict[str, Any]:
    wizard_state = normalize_wizard_state(state)
    if step not in wizard_state["completed_steps"]:
        wizard_state["completed_steps"].append(step)
    wizard_state["last_completed_step"] = step
    return wizard_state


def set_wizard_optional_step_skipped(state: Dict[str, Any], step: str) -> Dict[str, Any]:
    wizard_state = normalize_wizard_state(state)
    if step not in wizard_state["skipped_optional_steps"]:
        wizard_state["skipped_optional_steps"].append(step)
    return wizard_state


def animation_render_complete(project_dir: Path, animation_name: str) -> bool:
    manifest = load_json(project_dir / "animations" / animation_name / "render_manifest.json", None)
    if not isinstance(manifest, dict):
        return False
    frames = manifest.get("frames") or []
    return len(frames) == ANIMATION_SPECS[animation_name]["frame_count"]


def canonical_downstream_path(project_dir: Path, key: str) -> Path:
    return project_dir / CANONICAL_DOWNSTREAM_FILES[key]


def legacy_downstream_path(project_dir: Path, key: str) -> Path:
    return project_dir / LEGACY_DOWNSTREAM_FILES[key]


def default_sprite_model_history(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "current_revision_id": None,
        "events": [],
        "revisions": [],
    }


def default_manual_animation_clips(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "clips": {},
        "updated_at": now_iso(),
    }


def default_ai_dependency_status() -> Dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "overall_status": "unknown",
        "dependencies": {},
    }


def default_ai_workflow(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "enabled": True,
        "profile": AI_WORKFLOW_PROFILE,
        "dependency_status": default_ai_dependency_status(),
        "legacy_mode": False,
        "character_lock": {
            "runs": {},
            "approved_run_id": None,
            "approved_asset_id": None,
        },
        "key_pose_set": {
            "runs": {},
            "approved_run_id": None,
        },
        "motion_runs": {clip_name: {"runs": {}, "approved_run_id": None} for clip_name in AI_CLIP_SPECS},
        "extract_runs": {clip_name: {"runs": {}, "approved_run_id": None} for clip_name in AI_CLIP_SPECS},
        "cleanup_runs": {clip_name: {"runs": {}, "approved_run_id": None} for clip_name in AI_CLIP_SPECS},
        "selected_assets": {
            "approved_concept_id": None,
            "character_lock_asset_id": None,
            "character_lock_run_id": None,
            "key_pose_run_id": None,
            "motion_run_ids": {},
            "extract_run_ids": {},
            "cleanup_run_ids": {},
        },
        "updated_at": now_iso(),
    }


def _normalize_run_group(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {"runs": {}, "approved_run_id": None}
    return {
        "runs": copy.deepcopy(value.get("runs") or {}),
        "approved_run_id": value.get("approved_run_id"),
    }


def hydrate_ai_workflow(store: Any, project: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
    hydrated = default_ai_workflow(project_dir.name)
    if isinstance(store, dict):
        hydrated["enabled"] = bool(store.get("enabled", True))
        hydrated["profile"] = str(store.get("profile") or AI_WORKFLOW_PROFILE)
        if isinstance(store.get("dependency_status"), dict):
            hydrated["dependency_status"] = copy.deepcopy(store["dependency_status"])
        hydrated["legacy_mode"] = bool(store.get("legacy_mode", False))
        character_lock = _normalize_run_group(store.get("character_lock"))
        hydrated["character_lock"]["runs"] = character_lock["runs"]
        hydrated["character_lock"]["approved_run_id"] = character_lock["approved_run_id"]
        hydrated["character_lock"]["approved_asset_id"] = (store.get("character_lock") or {}).get("approved_asset_id")
        key_pose_set = _normalize_run_group(store.get("key_pose_set"))
        hydrated["key_pose_set"]["runs"] = key_pose_set["runs"]
        hydrated["key_pose_set"]["approved_run_id"] = key_pose_set["approved_run_id"]
        for group_name in ("motion_runs", "extract_runs", "cleanup_runs"):
            source_group = store.get(group_name) if isinstance(store.get(group_name), dict) else {}
            target_group = hydrated[group_name]
            for clip_name in AI_CLIP_SPECS:
                normalized = _normalize_run_group(source_group.get(clip_name))
                target_group[clip_name] = normalized
        if isinstance(store.get("selected_assets"), dict):
            hydrated["selected_assets"].update(copy.deepcopy(store["selected_assets"]))
        hydrated["updated_at"] = str(store.get("updated_at") or hydrated["updated_at"])
    has_legacy_data = bool(
        project.get("external_authoring")
        or project.get("rig")
        or project.get("sprite_model")
        or project.get("part_split")
        or (project.get("manual_animation_clips", {}).get("clips") if isinstance(project.get("manual_animation_clips"), dict) else None)
    )
    if not isinstance(store, dict) and has_legacy_data:
        hydrated["enabled"] = False
        hydrated["legacy_mode"] = True
    if hydrated["legacy_mode"]:
        hydrated["enabled"] = False
    return hydrated


def serialize_ai_workflow(store: Any, project_id: str) -> Dict[str, Any]:
    serialized = default_ai_workflow(project_id)
    if not isinstance(store, dict):
        return serialized
    serialized["enabled"] = bool(store.get("enabled", True))
    serialized["profile"] = str(store.get("profile") or AI_WORKFLOW_PROFILE)
    if isinstance(store.get("dependency_status"), dict):
        serialized["dependency_status"] = copy.deepcopy(store["dependency_status"])
    serialized["legacy_mode"] = bool(store.get("legacy_mode", False))
    serialized["character_lock"] = copy.deepcopy(store.get("character_lock") or serialized["character_lock"])
    serialized["key_pose_set"] = copy.deepcopy(store.get("key_pose_set") or serialized["key_pose_set"])
    for group_name in ("motion_runs", "extract_runs", "cleanup_runs"):
        source_group = store.get(group_name) if isinstance(store.get(group_name), dict) else {}
        serialized[group_name] = {
            clip_name: copy.deepcopy(source_group.get(clip_name) or serialized[group_name][clip_name])
            for clip_name in AI_CLIP_SPECS
        }
    if isinstance(store.get("selected_assets"), dict):
        serialized["selected_assets"].update(copy.deepcopy(store["selected_assets"]))
    serialized["updated_at"] = str(store.get("updated_at") or serialized["updated_at"])
    return serialized


def ai_workflow_root(project_dir: Path, stage: str, clip_name: Optional[str] = None, run_id: Optional[str] = None) -> Path:
    if stage == "character_lock":
        root = project_dir / "ai_workflow" / "character_lock"
    elif stage == "key_pose_set":
        root = project_dir / "ai_workflow" / "key_poses"
    elif stage in {"motion_clip", "extract_frames", "pixel_cleanup"}:
        if clip_name not in AI_CLIP_SPECS:
            raise ValueError("Unknown clip: %s." % clip_name)
        mapping = {
            "motion_clip": "motion",
            "extract_frames": "extract",
            "pixel_cleanup": "cleanup",
        }
        root = project_dir / "ai_workflow" / mapping[stage] / clip_name
    else:
        raise ValueError("Unknown AI workflow stage: %s." % stage)
    if run_id:
        root = root / run_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_external_authoring(project_id: str) -> Dict[str, Any]:
    return {
        "project_id": project_id,
        "enabled": False,
        "provider": "skelform",
        "provider_profile": skelform_provider_profile(),
        "session": {
            "editor_url": SKELFORM_EDITOR_URL,
            "embed_url": SKELFORM_EDITOR_URL,
            "can_embed": True,
            "source_mode": "hosted",
            "last_opened_at": None,
        },
        "validation": {
            "license": "MIT",
            "docs_url": SKELFORM_DOCS_URL,
            "embed_test": "passed",
            "build_flow": "remote-hosted editor embedded first, local vendoring deferred",
            "runtime_format": ".skf plus exported sheets/metadata",
            "validated_at": now_iso(),
        },
        "imported_bundle": None,
        "updated_at": now_iso(),
    }


def hydrate_external_authoring(store: Any, project_dir: Path) -> Dict[str, Any]:
    hydrated = default_external_authoring(project_dir.name)
    if not isinstance(store, dict):
        return hydrated
    hydrated["enabled"] = bool(store.get("enabled", False))
    hydrated["provider"] = str(store.get("provider") or "skelform")
    if isinstance(store.get("provider_profile"), dict):
        hydrated["provider_profile"].update(store["provider_profile"])
    if isinstance(store.get("session"), dict):
        hydrated["session"].update(store["session"])
    if isinstance(store.get("validation"), dict):
        hydrated["validation"].update(store["validation"])
    bundle = store.get("imported_bundle")
    if isinstance(bundle, dict):
        hydrated["imported_bundle"] = copy.deepcopy(bundle)
    hydrated["updated_at"] = str(store.get("updated_at") or hydrated["updated_at"])
    return hydrated


def serialize_external_authoring(store: Any, project_id: str) -> Dict[str, Any]:
    serialized = default_external_authoring(project_id)
    if not isinstance(store, dict):
        return serialized
    serialized["enabled"] = bool(store.get("enabled", False))
    serialized["provider"] = str(store.get("provider") or "skelform")
    if isinstance(store.get("provider_profile"), dict):
        serialized["provider_profile"].update(copy.deepcopy(store["provider_profile"]))
    if isinstance(store.get("session"), dict):
        serialized["session"].update(copy.deepcopy(store["session"]))
    if isinstance(store.get("validation"), dict):
        serialized["validation"].update(copy.deepcopy(store["validation"]))
    if isinstance(store.get("imported_bundle"), dict):
        serialized["imported_bundle"] = copy.deepcopy(store["imported_bundle"])
    serialized["updated_at"] = str(store.get("updated_at") or serialized["updated_at"])
    return serialized


def external_authoring_import_root(project_dir: Path) -> Path:
    root = project_dir / "external_authoring" / "imports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def manual_clip_render_root(project_dir: Path) -> Path:
    return project_dir / "manual_clips"


def manual_clip_source_hashes(project_dir: Path) -> Dict[str, Optional[str]]:
    rig_path = canonical_downstream_path(project_dir, "rig")
    sprite_model_path = canonical_downstream_path(project_dir, "sprite_model")
    return {
        "rig_hash": image_sha256(rig_path) if rig_path.exists() else None,
        "sprite_model_hash": image_sha256(sprite_model_path) if sprite_model_path.exists() else None,
    }


def manual_clip_frame_count(value: Any, default: int = 8) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(64, parsed))


def normalize_manual_clip_frame(frame: Any) -> Dict[str, Any]:
    base = neutral_pose_transforms()
    normalized = dict(base)
    if isinstance(frame, dict):
        for key, value in frame.items():
            if key == "root_offset" and isinstance(value, list) and len(value) == 2:
                normalized[key] = [round(float(value[0]), 2), round(float(value[1]), 2)]
            elif key in normalized and isinstance(value, (int, float)):
                normalized[key] = round(float(value), 2)
    return normalized


def normalize_manual_frame_repairs(value: Any) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    if not isinstance(value, dict):
        return normalized
    for part_name, payload in value.items():
        if not isinstance(payload, dict):
            continue
        image_path = str(payload.get("image_path") or "").strip()
        if not image_path:
            continue
        normalized[str(part_name)] = {
            "variant_id": str(payload.get("variant_id") or "").strip() or None,
            "image_path": image_path,
            "mask_path": str(payload.get("mask_path") or "").strip() or None,
            "source": str(payload.get("source") or "recover-occlusion").strip() or "recover-occlusion",
            "summary": str(payload.get("summary") or "").strip() or None,
            "applied_at": str(payload.get("applied_at") or now_iso()),
        }
    return normalized


def normalize_manual_frame_patches(value: Any) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    if not isinstance(value, dict):
        return normalized
    for patch_id, payload in value.items():
        if not isinstance(payload, dict):
            continue
        source_part = str(payload.get("source_part_name") or payload.get("part_name") or "").strip()
        image_path = str(payload.get("image_path") or "").strip()
        keep_behind_part = str(payload.get("keep_behind_part_name") or "").strip()
        if not source_part or not image_path or not keep_behind_part:
            continue
        normalized[str(patch_id)] = {
            "patch_id": str(payload.get("patch_id") or patch_id).strip() or str(patch_id),
            "source_part_name": source_part,
            "keep_behind_part_name": keep_behind_part,
            "variant_id": str(payload.get("variant_id") or "").strip() or None,
            "image_path": image_path,
            "mask_path": str(payload.get("mask_path") or "").strip() or None,
            "source": str(payload.get("source") or "recover-occlusion").strip() or "recover-occlusion",
            "summary": str(payload.get("summary") or "").strip() or None,
            "applied_at": str(payload.get("applied_at") or now_iso()),
        }
    return normalized


def normalize_manual_clip_frame_entry(frame: Any) -> Dict[str, Any]:
    if isinstance(frame, dict) and ("transforms" in frame or "part_repairs" in frame or "corrective_patches" in frame):
        transforms = normalize_manual_clip_frame(frame.get("transforms"))
        part_repairs = normalize_manual_frame_repairs(frame.get("part_repairs"))
        corrective_patches = normalize_manual_frame_patches(frame.get("corrective_patches"))
    else:
        transforms = normalize_manual_clip_frame(frame)
        part_repairs = {}
        corrective_patches = {}
    return {
        "transforms": transforms,
        "part_repairs": part_repairs,
        "corrective_patches": corrective_patches,
    }


def manual_clip_frame_transforms(frame: Any) -> Dict[str, Any]:
    return normalize_manual_clip_frame_entry(frame)["transforms"]


def blank_manual_clip_frames(frame_count: int) -> List[Dict[str, Any]]:
    return [normalize_manual_clip_frame_entry({}) for _ in range(frame_count)]


def default_manual_clip(project_dir: Path, clip_id: str, clip_name: str, frame_count: int = 8, fps: int = 12, loop: bool = True) -> Dict[str, Any]:
    render_root = manual_clip_render_root(project_dir) / clip_id
    frame_count = manual_clip_frame_count(frame_count)
    fps_value = max(1, min(60, int(fps)))
    return {
        "clip_id": clip_id,
        "clip_name": clip_name,
        "authoring_mode": "manual",
        "approval_status": "draft",
        "frame_count": frame_count,
        "fps": fps_value,
        "loop": bool(loop),
        "frames": blank_manual_clip_frames(frame_count),
        "source_hashes": manual_clip_source_hashes(project_dir),
        "preview_render": {
            "status": "not_rendered",
            "gif_path": str((render_root / "preview.gif").relative_to(project_dir)),
            "render_manifest_path": str((render_root / "render_manifest.json").relative_to(project_dir)),
            "frame_dir": str((render_root / "frames").relative_to(project_dir)),
            "frames": [],
            "generated_at": None,
        },
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "approved_at": None,
    }


def invalidate_manual_clip_preview(clip: Dict[str, Any]) -> Dict[str, Any]:
    preview = dict(clip.get("preview_render") or {})
    preview["status"] = "outdated"
    preview["frames"] = []
    preview["generated_at"] = None
    clip["preview_render"] = preview
    clip["approval_status"] = "draft"
    clip["approved_at"] = None
    clip["updated_at"] = now_iso()
    return clip


def normalize_manual_clip(project_dir: Path, clip_id: str, payload: Any) -> Dict[str, Any]:
    clip = default_manual_clip(project_dir, clip_id, humanize_identifier(clip_id))
    if isinstance(payload, dict):
        clip["clip_name"] = str(payload.get("clip_name") or clip["clip_name"]).strip() or clip["clip_name"]
        clip["frame_count"] = manual_clip_frame_count(payload.get("frame_count"), clip["frame_count"])
        clip["fps"] = max(1, min(60, int(payload.get("fps") or clip["fps"])))
        clip["loop"] = bool(payload.get("loop", clip["loop"]))
        clip["authoring_mode"] = "manual"
        clip["approval_status"] = str(payload.get("approval_status") or clip["approval_status"])
        clip["source_hashes"] = payload.get("source_hashes") if isinstance(payload.get("source_hashes"), dict) else clip["source_hashes"]
        clip["created_at"] = str(payload.get("created_at") or clip["created_at"])
        clip["updated_at"] = str(payload.get("updated_at") or clip["updated_at"])
        clip["approved_at"] = payload.get("approved_at")
        preview = payload.get("preview_render") if isinstance(payload.get("preview_render"), dict) else {}
        clip["preview_render"] = {
            "status": str(preview.get("status") or "not_rendered"),
            "gif_path": str(preview.get("gif_path") or clip["preview_render"]["gif_path"]),
            "render_manifest_path": str(preview.get("render_manifest_path") or clip["preview_render"]["render_manifest_path"]),
            "frame_dir": str(preview.get("frame_dir") or clip["preview_render"]["frame_dir"]),
            "frames": list(preview.get("frames") or []),
            "generated_at": preview.get("generated_at"),
        }
        raw_frames = payload.get("frames") if isinstance(payload.get("frames"), list) else []
        normalized_frames = [normalize_manual_clip_frame_entry(frame) for frame in raw_frames[:clip["frame_count"]]]
        while len(normalized_frames) < clip["frame_count"]:
            normalized_frames.append(normalize_manual_clip_frame_entry({}))
        clip["frames"] = normalized_frames
    return clip


def hydrate_manual_animation_clips(store: Any, project_dir: Path) -> Dict[str, Any]:
    hydrated = default_manual_animation_clips(project_dir.name)
    raw_clips = store.get("clips") if isinstance(store, dict) else {}
    normalized: Dict[str, Any] = {}
    for clip_id, payload in (raw_clips or {}).items():
        if not isinstance(payload, dict):
            continue
        safe_clip_id = sanitize_filename(str(payload.get("clip_id") or clip_id), "manual-clip")
        clip = normalize_manual_clip(project_dir, safe_clip_id, payload)
        current_hashes = manual_clip_source_hashes(project_dir)
        stale_reasons = []
        if clip["source_hashes"].get("rig_hash") != current_hashes.get("rig_hash"):
            stale_reasons.append("rig changed")
        if clip["source_hashes"].get("sprite_model_hash") != current_hashes.get("sprite_model_hash"):
            stale_reasons.append("sprite model changed")
        preview_gif = project_dir / str(clip["preview_render"].get("gif_path") or "")
        manifest_path = project_dir / str(clip["preview_render"].get("render_manifest_path") or "")
        clip["is_stale"] = bool(stale_reasons)
        clip["stale_reasons"] = stale_reasons
        clip["preview_render_complete"] = bool(preview_gif.exists() and manifest_path.exists())
        normalized[safe_clip_id] = clip
    hydrated["clips"] = normalized
    hydrated["updated_at"] = str(store.get("updated_at") or hydrated["updated_at"]) if isinstance(store, dict) else hydrated["updated_at"]
    return hydrated


def serialize_manual_animation_clips(store: Any, project_id: str) -> Dict[str, Any]:
    serialized = default_manual_animation_clips(project_id)
    raw_clips = store.get("clips") if isinstance(store, dict) else {}
    clips: Dict[str, Any] = {}
    for clip_id, payload in (raw_clips or {}).items():
        if not isinstance(payload, dict):
            continue
        clip = copy.deepcopy(payload)
        clip.pop("is_stale", None)
        clip.pop("stale_reasons", None)
        clip.pop("preview_render_complete", None)
        clips[str(clip_id)] = clip
    serialized["clips"] = clips
    if isinstance(store, dict) and store.get("updated_at"):
        serialized["updated_at"] = str(store["updated_at"])
    return serialized
