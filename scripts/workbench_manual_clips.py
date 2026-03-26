from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


def get_manual_animation_clips(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    return project.get("manual_animation_clips") or default_manual_animation_clips(project_id)


def create_manual_animation_clip(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("rig"):
        raise ValueError("Build the rig before creating manual clips.")
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip_name = str(payload.get("clip_name") or "Manual Clip").strip() or "Manual Clip"
    base_id = sanitize_filename(slugify(clip_name), "manual-clip")
    clip_id = base_id
    counter = 2
    while clip_id in (store.get("clips") or {}):
        clip_id = "%s-%d" % (base_id, counter)
        counter += 1
    clip = default_manual_clip(
        project_dir,
        clip_id,
        clip_name,
        frame_count=manual_clip_frame_count(payload.get("frame_count"), 8),
        fps=max(1, min(60, int(payload.get("fps") or 12))),
        loop=bool(payload.get("loop", True)),
    )
    store.setdefault("clips", {})[clip_id] = clip
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["current_stage"] = "clips"
    project["status"] = "manual_clip_created"
    project["updated_at"] = now_iso()
    save_project(project)
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def manual_clip_or_error(project: Dict[str, Any], clip_id: str) -> Dict[str, Any]:
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project["project_id"])
    clip = (store.get("clips") or {}).get(clip_id)
    if not clip:
        raise ValueError("Unknown manual clip: %s." % clip_id)
    return clip


def update_manual_animation_clip_meta(project_id: str, clip_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    next_frame_count = manual_clip_frame_count(payload.get("frame_count"), clip.get("frame_count") or 8)
    clip["clip_name"] = str(payload.get("clip_name") or clip.get("clip_name") or humanize_identifier(clip_id)).strip() or clip["clip_name"]
    clip["fps"] = max(1, min(60, int(payload.get("fps") or clip.get("fps") or 12)))
    clip["loop"] = bool(payload.get("loop", clip.get("loop", True)))
    current_frames = [normalize_manual_clip_frame_entry(frame) for frame in (clip.get("frames") or [])]
    while len(current_frames) < next_frame_count:
        current_frames.append(normalize_manual_clip_frame_entry({}))
    clip["frame_count"] = next_frame_count
    clip["frames"] = current_frames[:next_frame_count]
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_updated"
    project["updated_at"] = now_iso()
    save_project(project)
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def update_manual_animation_clip_frame(project_id: str, clip_id: str, frame_index: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    current_entry = normalize_manual_clip_frame_entry((clip.get("frames") or [])[frame_index])
    incoming = payload.get("transforms") if isinstance(payload.get("transforms"), dict) else payload
    next_entry = dict(current_entry)
    next_entry["transforms"] = normalize_manual_clip_frame(incoming)
    if isinstance(payload.get("part_repairs"), dict):
        next_entry["part_repairs"] = normalize_manual_frame_repairs(payload.get("part_repairs"))
    if isinstance(payload.get("corrective_patches"), dict):
        next_entry["corrective_patches"] = normalize_manual_frame_patches(payload.get("corrective_patches"))
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(next_entry)
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_updated"
    project["updated_at"] = now_iso()
    save_project(project)
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def copy_manual_animation_clip_frame(project_id: str, clip_id: str, frame_index: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    source_index = int(payload.get("source_index", max(0, frame_index - 1)))
    if source_index < 0 or source_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Source frame index out of range.")
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(clip["frames"][source_index])
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_copied"
    project["updated_at"] = now_iso()
    save_project(project)
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def reset_manual_animation_clip_frame(project_id: str, clip_id: str, frame_index: int) -> Dict[str, Any]:
    return update_manual_animation_clip_frame(project_id, clip_id, frame_index, {"transforms": neutral_pose_transforms(), "part_repairs": {}, "corrective_patches": {}})


def generate_manual_animation_clip_frame_repair(project_id: str, clip_id: str, frame_index: int, part_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    result = recover_sprite_model_occlusion(project_id, {"part_name": part_name})
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "part_name": part_name,
        "variants": result.get("variants") or [],
    }


def apply_manual_animation_clip_frame_repair(project_id: str, clip_id: str, frame_index: int, part_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    image_path = str(payload.get("image_path") or "").strip()
    if not image_path:
        raise ValueError("repair/apply requires image_path.")
    frame_entry = normalize_manual_clip_frame_entry((clip.get("frames") or [])[frame_index])
    repairs = dict(frame_entry.get("part_repairs") or {})
    repairs[part_name] = {
        "variant_id": str(payload.get("variant_id") or "").strip() or None,
        "image_path": image_path,
        "mask_path": str(payload.get("mask_path") or "").strip() or None,
        "source": str(payload.get("source") or "recover-occlusion").strip() or "recover-occlusion",
        "summary": str(payload.get("summary") or "").strip() or None,
        "applied_at": now_iso(),
    }
    frame_entry["part_repairs"] = repairs
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(frame_entry)
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_repair_applied"
    project["updated_at"] = now_iso()
    save_project(project)
    hydrated = hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "part_name": part_name,
        "frame": hydrated["frames"][frame_index],
        "clip": hydrated,
    }


def clear_manual_animation_clip_frame_repair(project_id: str, clip_id: str, frame_index: int, part_name: str) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    frame_entry = normalize_manual_clip_frame_entry((clip.get("frames") or [])[frame_index])
    repairs = dict(frame_entry.get("part_repairs") or {})
    repairs.pop(part_name, None)
    frame_entry["part_repairs"] = repairs
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(frame_entry)
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_repair_cleared"
    project["updated_at"] = now_iso()
    save_project(project)
    hydrated = hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "part_name": part_name,
        "frame": hydrated["frames"][frame_index],
        "clip": hydrated,
    }


def generate_manual_animation_clip_frame_patch(project_id: str, clip_id: str, frame_index: int, source_part_name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    result = recover_sprite_model_occlusion(project_id, {"part_name": source_part_name})
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "source_part_name": source_part_name,
        "variants": result.get("variants") or [],
    }


def apply_manual_animation_clip_frame_patch(project_id: str, clip_id: str, frame_index: int, source_part_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    image_path = str(payload.get("image_path") or "").strip()
    keep_behind_part_name = str(payload.get("keep_behind_part_name") or "").strip()
    if not image_path:
        raise ValueError("patch/apply requires image_path.")
    if not keep_behind_part_name:
        raise ValueError("patch/apply requires keep_behind_part_name.")
    sprite_parts = project.get("sprite_model", {}).get("parts") or []
    part_names = {str(item.get("part_name")) for item in sprite_parts if item.get("part_name")}
    if source_part_name not in part_names:
        raise ValueError("Unknown source part: %s." % source_part_name)
    if keep_behind_part_name not in part_names:
        raise ValueError("Unknown keep_behind_part_name: %s." % keep_behind_part_name)
    patch_id = "patch:%s" % source_part_name
    frame_entry = normalize_manual_clip_frame_entry((clip.get("frames") or [])[frame_index])
    patches = dict(frame_entry.get("corrective_patches") or {})
    patches[patch_id] = {
        "patch_id": patch_id,
        "source_part_name": source_part_name,
        "keep_behind_part_name": keep_behind_part_name,
        "variant_id": str(payload.get("variant_id") or "").strip() or None,
        "image_path": image_path,
        "mask_path": str(payload.get("mask_path") or "").strip() or None,
        "source": str(payload.get("source") or "recover-occlusion").strip() or "recover-occlusion",
        "summary": str(payload.get("summary") or "").strip() or None,
        "applied_at": now_iso(),
    }
    frame_entry["corrective_patches"] = patches
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(frame_entry)
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_patch_applied"
    project["updated_at"] = now_iso()
    save_project(project)
    hydrated = hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "source_part_name": source_part_name,
        "frame": hydrated["frames"][frame_index],
        "clip": hydrated,
    }


def clear_manual_animation_clip_frame_patch(project_id: str, clip_id: str, frame_index: int, source_part_name: str) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    if frame_index < 0 or frame_index >= int(clip.get("frame_count") or 0):
        raise ValueError("Frame index out of range.")
    frame_entry = normalize_manual_clip_frame_entry((clip.get("frames") or [])[frame_index])
    patches = dict(frame_entry.get("corrective_patches") or {})
    patches.pop("patch:%s" % source_part_name, None)
    frame_entry["corrective_patches"] = patches
    clip["frames"][frame_index] = normalize_manual_clip_frame_entry(frame_entry)
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    invalidate_manual_clip_preview(clip)
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_frame_patch_cleared"
    project["updated_at"] = now_iso()
    save_project(project)
    hydrated = hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]
    return {
        "clip_id": clip_id,
        "frame_index": frame_index,
        "source_part_name": source_part_name,
        "frame": hydrated["frames"][frame_index],
        "clip": hydrated,
    }


def render_manual_animation_clip_preview(project_id: str, clip_id: str, progress: Optional[Any] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("rig"):
        raise ValueError("Build the rig before rendering manual clips.")
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    render_root = manual_clip_render_root(project_dir) / clip_id
    frame_dir = render_root / "frames"
    clear_directory(render_root)
    frame_dir.mkdir(parents=True, exist_ok=True)
    manifests = []
    frame_total = int(clip.get("frame_count") or len(clip.get("frames") or []))
    for frame_index, frame_entry in enumerate((clip.get("frames") or [])[:frame_total]):
        normalized_frame = normalize_manual_clip_frame_entry(frame_entry)
        transforms = normalized_frame["transforms"]
        part_repairs = normalized_frame["part_repairs"]
        corrective_patches = normalized_frame["corrective_patches"]
        call_progress(progress, 10 + int((frame_index / max(1, frame_total)) * 78), "Rendering manual frame %d of %d" % (frame_index + 1, frame_total), "Compositing the authored manual pose against the current rig and sprite model.")
        raw, render_meta = render_pose_from_sprite_model(project, project["rig"], transforms, part_asset_overrides=part_repairs, corrective_patches=corrective_patches)
        foot_anchor = render_meta.get("foot_anchor") or {}
        anchor_candidates = [
            tuple(foot_anchor[name])
            for name in ("left", "right")
            if isinstance(foot_anchor.get(name), list) and len(foot_anchor.get(name)) == 2
        ]
        anchor_point = None
        if anchor_candidates:
            anchor_point = (
                sum(point[0] for point in anchor_candidates) / float(len(anchor_candidates)),
                sum(point[1] for point in anchor_candidates) / float(len(anchor_candidates)),
            )
        final_frame, cleanup = cleanup_frame(raw, anchor_point=anchor_point)
        frame_name = "%s_%02d.png" % (clip_id, frame_index)
        final_path = frame_dir / frame_name
        final_frame.save(final_path)
        manifests.append({
            "frame_name": frame_name,
            "path": str(final_path.relative_to(project_dir)),
            "cleanup": cleanup,
            "render_meta": render_meta,
            "joint_transforms": transforms,
            "part_repairs": part_repairs,
            "corrective_patches": corrective_patches,
        })
    manifest_path = render_root / "render_manifest.json"
    gif_path = render_root / "preview.gif"
    write_json(manifest_path, {"animation": clip_id, "clip_name": clip.get("clip_name"), "frames": manifests})
    preview_frames = [Image.open(project_dir / item["path"]).convert("RGBA") for item in manifests]
    if preview_frames:
        preview_frames[0].save(
            gif_path,
            save_all=True,
            append_images=preview_frames[1:],
            duration=[int(1000 / max(1, int(clip.get("fps") or 12)))] * len(preview_frames),
            loop=0 if clip.get("loop", True) else 1,
            disposal=2,
            transparency=0,
        )
    clip["preview_render"] = {
        "status": "complete",
        "gif_path": str(gif_path.relative_to(project_dir)),
        "render_manifest_path": str(manifest_path.relative_to(project_dir)),
        "frame_dir": str(frame_dir.relative_to(project_dir)),
        "frames": [item["path"] for item in manifests],
        "generated_at": now_iso(),
    }
    clip["source_hashes"] = manual_clip_source_hashes(project_dir)
    clip["updated_at"] = now_iso()
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_preview_rendered"
    project["current_stage"] = "clips"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Manual preview ready", "Review the generated GIF before approving this clip.")
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]


def approve_manual_animation_clip(project_id: str, clip_id: str, approved: bool) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = project.get("manual_animation_clips") or default_manual_animation_clips(project_id)
    clip = manual_clip_or_error(project, clip_id)
    hydrated = hydrate_manual_animation_clips(store, project_dir)["clips"][clip_id]
    if approved:
        if hydrated.get("is_stale"):
            raise ValueError("Manual clip approval is blocked until the clip is re-rendered against the current rig and sprite model.")
        if not hydrated.get("preview_render_complete"):
            raise ValueError("Render the manual preview before approving the clip.")
        clip["approval_status"] = "approved"
        clip["approved_at"] = now_iso()
    else:
        clip["approval_status"] = "draft"
        clip["approved_at"] = None
    clip["updated_at"] = now_iso()
    store["updated_at"] = now_iso()
    project["manual_animation_clips"] = store
    project["status"] = "manual_clip_%s" % ("approved" if approved else "unapproved")
    project["updated_at"] = now_iso()
    save_project(project)
    return hydrate_manual_animation_clips(project["manual_animation_clips"], project_dir)["clips"][clip_id]
