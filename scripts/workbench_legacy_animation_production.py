from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


def update_animation_clip(project_id: str, animation_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if animation_name not in ANIMATION_SPECS:
        raise ValueError("Unknown clip: %s." % animation_name)
    project = load_project(project_id)
    if not project.get("rig"):
        raise ValueError("Build the rig before editing clips.")
    clips = hydrate_animation_clips(project.get("animation_clips"), project.get("animation_templates"), rig_profile=active_rig_profile_name(project, project.get("rig_layout")))
    clip = clips[animation_name]
    merged_controls = dict(clip.get("controls") or {})
    incoming_controls = payload.get("controls") if isinstance(payload.get("controls"), dict) else payload
    if isinstance(incoming_controls, dict):
        merged_controls.update({key: value for key, value in incoming_controls.items() if key in DEFAULT_CLIP_CONTROLS[animation_name]})
    controls = normalize_clip_controls(animation_name, merged_controls)
    overrides = clip_frame_overrides(ANIMATION_SPECS[animation_name]["frame_count"], payload.get("frame_overrides") if "frame_overrides" in payload else clip.get("frame_overrides"))
    clip["controls"] = controls
    clip["frame_overrides"] = overrides
    clip["joint_transforms_per_frame"] = generate_clip_frames(animation_name, controls, overrides, rig_profile=active_rig_profile_name(project, project.get("rig_layout")))
    clips[animation_name] = clip
    reset_downstream_assets(project_id, "clips")
    project = clear_project_downstream_state(project, "clips")
    project["animation_clips"] = clips
    project["animation_templates"] = clips
    project["current_stage"] = "clips"
    project["status"] = "%s_clip_updated" % animation_name
    project["updated_at"] = now_iso()
    save_project(project)
    return clip


def reset_animation_clip(project_id: str, animation_name: str) -> Dict[str, Any]:
    return update_animation_clip(project_id, animation_name, {
        "controls": default_clip_controls(animation_name),
        "frame_overrides": [{} for _ in range(ANIMATION_SPECS[animation_name]["frame_count"])],
    })


def approve_sprite_model_review(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    sprite_model = project.get("sprite_model")
    if not sprite_model:
        raise ValueError("Sprite model cannot be approved before a build.")
    if sprite_model.get("status") == "fail":
        raise ValueError("Sprite model approval is blocked until build failures are resolved.")
    project["sprite_model_approved"] = True
    project["layer_review_approved"] = True
    project["sprite_model"]["approved_for_rigging"] = True
    project["updated_at"] = now_iso()
    save_project(project)
    return {"ok": True}


def approve_rig_review(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("rig"):
        raise ValueError("Rig review cannot be approved before rig build.")
    if not project.get("sprite_model_approved") and not project.get("layer_review_approved"):
        raise ValueError("Sprite-model approval is required before rig review approval.")
    project["rig_review_approved"] = True
    project["rig"]["approved_for_production"] = True
    project["updated_at"] = now_iso()
    save_project(project)
    return {"ok": True}


def render_animation(project_id: str, animation_name: str, progress: Optional[Any] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("rig"):
        raise ValueError("Build the rig before rendering clips.")
    if not project.get("rig_review_approved"):
        raise ValueError("Rig review approval is required before production.")
    clips = project.get("animation_clips") or load_json(canonical_downstream_path(PROJECTS_ROOT / project_id, "animation_clips"))
    if animation_name not in clips:
        raise ValueError("Unknown clip: %s." % animation_name)
    delete_path(canonical_downstream_path(PROJECTS_ROOT / project_id, "qa_report"))
    clear_directory(PROJECTS_ROOT / project_id / "exports")
    project["qa_report"] = None
    project["last_export"] = None

    clip = clips[animation_name]
    project_dir = PROJECTS_ROOT / project_id
    output_dir = project_dir / "animations" / animation_name
    output_dir.mkdir(parents=True, exist_ok=True)
    clear_directory(output_dir)
    manifests = []
    frame_total = len(clip["joint_transforms_per_frame"])
    for frame_index, transforms in enumerate(clip["joint_transforms_per_frame"]):
        call_progress(progress, 12 + int((frame_index / max(1, frame_total)) * 80), "Rendering %s frame %d of %d" % (animation_name, frame_index + 1, frame_total), "Compositing extracted parts with deterministic rig transforms.")
        raw, render_meta = render_pose_from_sprite_model(project, project["rig"], transforms)
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
        frame_name = "%s_%02d.png" % (animation_name, frame_index)
        final_path = output_dir / frame_name
        final_frame.save(final_path)
        manifests.append({
            "frame_name": frame_name,
            "path": str(final_path.relative_to(project_dir)),
            "cleanup": cleanup,
            "render_meta": render_meta,
            "joint_transforms": transforms,
        })
    write_json(output_dir / "render_manifest.json", {"animation": animation_name, "frames": manifests})
    project["current_stage"] = "production_%s" % animation_name
    project["status"] = "%s_rendered" % animation_name
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "%s ready" % animation_name.title(), "The deterministic clip frames are ready for QA.")
    return {"animation": animation_name, "frames": manifests, "fps": clip["fps"], "frame_count": clip["frame_count"]}
