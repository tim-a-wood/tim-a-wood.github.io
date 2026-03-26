from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)

def check_state(status: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if status not in {"pass", "fail", "not_implemented"}:
        raise ValueError("Invalid check state.")
    return {"status": status, "details": details or {}}

def aggregate_check_state(states: List[str]) -> str:
    if any(state == "fail" for state in states):
        return "fail"
    if any(state == "pass" for state in states):
        return "pass"
    return "not_implemented"

def approved_manual_animation_clips(project: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    store = project.get("manual_animation_clips") or {"clips": {}}
    return {
        clip_id: clip
        for clip_id, clip in (store.get("clips") or {}).items()
        if clip.get("approval_status") == "approved" and not clip.get("is_stale") and clip.get("preview_render_complete")
    }

def run_external_authoring_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = hydrate_external_authoring(project.get("external_authoring"), project_dir)
    bundle = store.get("imported_bundle") if isinstance(store.get("imported_bundle"), dict) else None
    if not store.get("enabled") or not bundle:
        raise ValueError("External authoring bundle is required before QA.")
    call_progress(progress, 12, "Checking SkelForm bundle", "Validating imported spritesheet and metadata files.")
    spritesheet_path = project_dir / str(bundle.get("spritesheet_image_path") or "")
    atlas_path = project_dir / str(bundle.get("atlas_path") or "")
    animations_path = project_dir / str(bundle.get("animations_path") or "")
    preview_gif_path = project_dir / str(bundle.get("preview_gif_path") or "") if bundle.get("preview_gif_path") else None
    atlas = load_json(atlas_path, None) if atlas_path.exists() else None
    animations = load_json(animations_path, None) if animations_path.exists() else None
    atlas_frames = atlas.get("frames") if isinstance(atlas, dict) else None
    animation_names = sorted(animations.keys()) if isinstance(animations, dict) else []
    referenced_frames: List[str] = []
    if isinstance(animations, dict):
        for clip in animations.values():
            if isinstance(clip, dict):
                referenced_frames.extend([str(name) for name in (clip.get("frames") or [])])
    frame_lookup = set((atlas_frames or {}).keys()) if isinstance(atlas_frames, dict) else set()
    missing_frame_refs = sorted(set(referenced_frames).difference(frame_lookup))
    report = {
        "project_id": project_id,
        "generated_at": now_iso(),
        "status": "pass",
        "mode": "external_authoring",
        "per_frame_checks": [],
        "per_animation_checks": {},
        "source_asset_hashes": {},
        "metadata_checks": {
            "external_authoring_enabled": check_state("pass" if store.get("enabled") else "fail"),
            "has_spritesheet": check_state("pass" if spritesheet_path.exists() else "fail"),
            "has_atlas": check_state("pass" if atlas_path.exists() else "fail"),
            "has_animations": check_state("pass" if animations_path.exists() else "fail"),
            "atlas_has_frames": check_state("pass" if isinstance(atlas_frames, dict) and atlas_frames else "fail"),
            "animations_non_empty": check_state("pass" if animation_names else "fail"),
            "animation_frames_resolve_in_atlas": check_state("pass" if not missing_frame_refs else "fail", {"missing_frames": missing_frame_refs}),
            "has_preview_gif": check_state("pass" if preview_gif_path and preview_gif_path.exists() else "warning"),
        },
        "notes": [
            "QA validated the imported external-authoring bundle rather than the legacy deterministic rig pipeline.",
            "Semantic animation quality still requires human review in the workbench.",
        ],
        "sprite_model_build_report": {"status": "pass", "source": "external_authoring"},
    }
    if spritesheet_path.exists():
        report["source_asset_hashes"][str(spritesheet_path.relative_to(project_dir))] = image_sha256(spritesheet_path)
    if atlas_path.exists():
        report["source_asset_hashes"][str(atlas_path.relative_to(project_dir))] = image_sha256(atlas_path)
    if animations_path.exists():
        report["source_asset_hashes"][str(animations_path.relative_to(project_dir))] = image_sha256(animations_path)
    if preview_gif_path and preview_gif_path.exists():
        report["source_asset_hashes"][str(preview_gif_path.relative_to(project_dir))] = image_sha256(preview_gif_path)
    if any(item["status"] == "fail" for item in report["metadata_checks"].values()):
        report["status"] = "fail"
    write_json(canonical_downstream_path(project_dir, "qa_report"), report)
    project["qa_report"] = report
    project["current_stage"] = "qa"
    project["status"] = "qa_%s" % report["status"]
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Checks complete", "Imported SkelForm bundle validation finished.")
    return report

def run_ai_workflow_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    store = ai_workflow_or_error(project)
    cleanup_runs = store.get("cleanup_runs") or {}
    report = {
        "project_id": project_id,
        "generated_at": now_iso(),
        "status": "pass",
        "mode": "ai_workflow",
        "workflow_profile": store.get("profile") or AI_WORKFLOW_PROFILE,
        "per_frame_checks": [],
        "per_animation_checks": {},
        "source_asset_hashes": {},
        "metadata_checks": {},
        "notes": [
            "QA validated AI-produced cleaned frames with deterministic pivot, transparency, and export checks.",
            "Semantic art direction still requires human review in the workbench.",
        ],
        "sprite_model_build_report": {"status": "pass", "source": "ai_workflow"},
    }
    for clip_index, clip_name in enumerate(AI_CLIP_SPECS):
        clip_group = cleanup_runs.get(clip_name) if isinstance(cleanup_runs.get(clip_name), dict) else {}
        approved_run_id = clip_group.get("approved_run_id")
        approved_run = (clip_group.get("runs") or {}).get(approved_run_id) if approved_run_id else None
        if not approved_run:
            raise ValueError("Approve cleaned %s frames before QA." % clip_name)
        animation_dir = project_dir / "animations" / clip_name
        manifest = load_json(animation_dir / "render_manifest.json", {"frames": []})
        frames = manifest.get("frames") or []
        draw_orders = []
        foot_anchors = []
        manifest_names = [item.get("frame_name") for item in frames]
        spec = AI_CLIP_SPECS[clip_name]
        for index in range(spec["frame_count"]):
            call_progress(progress, 8 + int(((clip_index * spec["frame_count"] + index) / max(1, sum(item["frame_count"] for item in AI_CLIP_SPECS.values()))) * 82), "Checking %s frame %d" % (clip_name, index + 1), "Validating cleaned frame dimensions, alpha, clipping, and pivot alignment.")
            frame_name = "%s_%02d.png" % (clip_name, index)
            path = animation_dir / frame_name
            if not path.exists():
                raise ValueError("Missing cleaned frame: %s" % frame_name)
            image = Image.open(path).convert("RGBA")
            alpha = image.getchannel("A")
            alpha_bounds = alpha.getbbox()
            frame_meta = next((item for item in frames if item.get("frame_name") == frame_name), None)
            if frame_meta is None:
                raise ValueError("Missing manifest row: %s" % frame_name)
            draw_orders.append(tuple(frame_meta.get("render_meta", {}).get("draw_sequence") or []))
            foot_anchors.append(frame_meta.get("render_meta", {}).get("foot_anchor") or {"left": [0, 0], "right": [0, 0]})
            report["source_asset_hashes"][str(path.relative_to(project_dir))] = image_sha256(path)
            checks = {
                "exact_frame_size": check_state("pass" if list(image.size) == [FRAME_SIZE, FRAME_SIZE] else "fail"),
                "transparent_background": check_state("pass" if alpha_bounds is not None and any(value < 255 for value in alpha.getdata()) else "fail"),
                "exact_pivot": check_state("pass" if frame_meta.get("cleanup", {}).get("pivot") == list(FRAME_PIVOT) else "fail", {"expected": list(FRAME_PIVOT)}),
                "no_clipping": check_state("fail" if border_has_alpha(image) else "pass"),
            }
            frame_status = aggregate_check_state([item["status"] for item in checks.values()])
            if frame_status == "fail":
                report["status"] = "fail"
            report["per_frame_checks"].append({
                "frame_name": frame_name,
                "status": frame_status,
                "checks": checks,
            })
        foot_y_values = [anchor["left"][1] for anchor in foot_anchors] + [anchor["right"][1] for anchor in foot_anchors]
        foot_anchor_stable = (max(foot_y_values) - min(foot_y_values)) <= 1 if foot_y_values else False
        first_left = (frames[0].get("render_meta", {}).get("foot_anchor", {}) if frames else {}).get("left", [0, 0])
        last_left = (frames[-1].get("render_meta", {}).get("foot_anchor", {}) if frames else {}).get("left", [0, 0])
        animation_checks = {
            "correct_frame_count": check_state("pass" if len(frames) == spec["frame_count"] else "fail"),
            "render_manifest_completeness": check_state("pass" if manifest_names == ["%s_%02d.png" % (clip_name, index) for index in range(spec["frame_count"])] else "fail"),
            "stable_draw_order": check_state("pass" if len(set(draw_orders)) == 1 else "fail"),
            "stable_foot_anchor": check_state("pass" if foot_anchor_stable else "fail"),
            "loop_seam_continuity": check_state("pass" if abs(first_left[1] - last_left[1]) <= 1 else "fail"),
            "metadata_correctness": check_state("pass" if (project.get("animation_clips", {}).get(clip_name, {}).get("frame_count") == spec["frame_count"] and project.get("animation_clips", {}).get(clip_name, {}).get("fps") == spec["fps"]) else "fail"),
        }
        animation_status = aggregate_check_state([item["status"] for item in animation_checks.values()])
        if animation_status == "fail":
            report["status"] = "fail"
        report["per_animation_checks"][clip_name] = {"status": animation_status, "checks": animation_checks}
    report["metadata_checks"] = {
        "ai_workflow_enabled": check_state("pass" if store.get("enabled") else "fail"),
        "workflow_profile_is_active": check_state("pass" if store.get("profile") == AI_WORKFLOW_PROFILE else "fail"),
        "has_approved_character_lock": check_state("pass" if bool((store.get("character_lock") or {}).get("approved_asset_id")) else "fail"),
        "has_approved_key_pose_set": check_state("pass" if bool((store.get("key_pose_set") or {}).get("approved_run_id")) else "fail"),
        "has_clean_idle_and_walk": check_state("pass" if all(bool((cleanup_runs.get(clip_name) or {}).get("approved_run_id")) for clip_name in AI_CLIP_SPECS) else "fail"),
        "dependency_health_snapshot": check_state("pass" if isinstance(store.get("dependency_status"), dict) and bool(store.get("dependency_status")) else "fail"),
    }
    if any(item["status"] == "fail" for item in report["metadata_checks"].values()):
        report["status"] = "fail"
    write_json(canonical_downstream_path(project_dir, "qa_report"), report)
    project["qa_report"] = report
    project["current_stage"] = "qa"
    project["status"] = "qa_%s" % report["status"]
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Checks complete", "AI workflow cleanup outputs passed through deterministic QA.")
    return report

def ai_workflow_ready_for_qa(store: Dict[str, Any]) -> bool:
    if not isinstance(store, dict) or not store.get("enabled") or store.get("legacy_mode"):
        return False
    cleanup_runs = store.get("cleanup_runs") or {}
    return all(bool((cleanup_runs.get(clip_name) or {}).get("approved_run_id")) for clip_name in AI_CLIP_SPECS)

def pixellab_pipeline_ready_for_qa(project: Dict[str, Any], project_dir: Path) -> bool:
    """
    Phase 6: Pixel Lab QA readiness check.

    Canonical inputs:
    - `pixellab_character.json`
    - `pixellab_animations.json`
    - `animation_clips.json` (built in Phase 5.5)
    """
    char_path = _pixellab_character_path(project_dir)
    anim_path = _pixellab_animations_path(project_dir)
    if not char_path.exists() or not anim_path.exists():
        return False
    anim_store = load_json(anim_path, None)
    if not isinstance(anim_store, dict):
        return False
    ab = anim_store.get("animations")
    if not pixellab_animation_store_has_frames(ab if isinstance(ab, dict) else None):
        return False
    clips = project.get("animation_clips") or load_json(canonical_downstream_path(project_dir, "animation_clips"), {})
    return isinstance(clips, dict) and bool(clips)

def run_pixellab_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id

    # Must exist and be non-empty.
    char_path = _pixellab_character_path(project_dir)
    anim_path = _pixellab_animations_path(project_dir)
    if not char_path.exists() or not anim_path.exists():
        raise ValueError("Pixel Lab canonical inputs missing; expected pixellab_character.json and pixellab_animations.json.")
    _pixellab_character_approved_guard(project_dir)  # also enforces approval

    pix_store = load_json(anim_path, None) or {}
    if not isinstance(pix_store, dict):
        pix_store = {}
    anim_block = pix_store.get("animations")
    if not pixellab_animation_store_has_frames(anim_block if isinstance(anim_block, dict) else None):
        raise ValueError(
            "pixellab_animations.json does not contain any generated animation frames yet. "
            "Generate at least one clip on the Animations panel first."
        )

    clips = sync_pixellab_animation_clips(project_id, project=project, project_dir=project_dir)
    if not isinstance(clips, dict) or not clips:
        raise ValueError("animation_clips.json must exist (Phase 5.5) before Pixel Lab QA.")

    # Every clip with raster `frames` in animation_clips.json (idle/walk + custom Pixel Lab clips).
    clip_names = _pixellab_qa_clip_names(clips)
    if not clip_names:
        raise ValueError(
            "animation_clips.json contains no Pixel Lab animations with frame paths. "
            "Generate clips on the Animations panel first."
        )
    total_frame_checks = sum(
        len((clips.get(n) or {}).get("frames") or [])
        for n in clip_names
        if isinstance(clips.get(n), dict)
    )
    frames_done = 0

    report = {
        "project_id": project_id,
        "generated_at": now_iso(),
        "status": "pass",
        "mode": "pixellab",
        "per_frame_checks": [],
        "per_animation_checks": {},
        "source_asset_hashes": {},
        "metadata_checks": {},
        "notes": [
            "QA validates Pixel Lab canonical animation frames for size, transparency, and border clipping.",
            "Semantic art direction still requires human review in the workbench.",
        ],
    }

    for clip_index, clip_name in enumerate(clip_names):
        call_progress(
            progress,
            8 + int((clip_index / max(1, len(clip_names))) * 12),
            "Checking %s clip" % clip_name,
            "Validating Pixel Lab frames (size, transparency, clipping).",
        )
        # Pixel Lab templates may return fewer frames than AI_CLIP_SPECS (deterministic workflow).
        # QA trusts animation_clips.json built from pixellab_animations — not the AI pose-count spec.
        spec = AI_CLIP_SPECS.get(clip_name) or ANIMATION_SPECS.get(clip_name) or {}
        spec_fc = int(spec.get("frame_count") or 0)
        spec_fps = int(spec.get("fps") or 0)

        clip = clips[clip_name]
        meta_fc = int(clip.get("frame_count") or 0)
        fps = int(clip.get("fps") or 0)
        frames = clip.get("frames") if isinstance(clip.get("frames"), list) else []
        path_count = len(frames)

        if not frames:
            raise ValueError("Pixel Lab QA blocked: %s.frames is empty — generate the animation again so the synced clip store has frames." % clip_name)
        if meta_fc and meta_fc != path_count:
            raise ValueError(
                "Pixel Lab QA blocked: %s.frame_count=%s but frames list length=%s. "
                "Re-generate or re-edit the animation so the synced clip metadata is refreshed."
                % (clip_name, meta_fc, path_count)
            )
        frame_count = int(meta_fc or path_count)
        if spec_fc and spec_fc != frame_count:
            report["notes"].append(
                "%s clip has %d frame(s); AI deterministic spec suggests %d — Pixel Lab output is accepted."
                % (clip_name, frame_count, spec_fc)
            )
        if spec_fps and spec_fps != fps:
            report["notes"].append(
                "%s clip fps=%d; AI deterministic spec suggests %d — Pixel Lab timing is accepted."
                % (clip_name, fps, spec_fps)
            )

        per_frame_states: List[str] = []
        for index in range(frame_count):
            frames_done += 1
            call_progress(
                progress,
                8 + int((frames_done / max(1, total_frame_checks)) * 82),
                "Checking %s frame %d" % (clip_name, index + 1),
                "Validating frame image.",
            )
            frame_rel = frames[index] if index < len(frames) else None
            if not frame_rel:
                raise ValueError("Pixel Lab QA blocked: missing frame path for %s index %d." % (clip_name, index))
            path = project_dir / str(frame_rel)
            if not path.exists():
                raise ValueError("Pixel Lab QA blocked: missing frame file %s." % str(path))

            image = Image.open(path).convert("RGBA")
            # Pixel Lab animation frames may be produced at a smaller canvas size
            # (e.g. 64x64). Normalize to the canonical export size so QA checks and
            # atlas packing use the same invariants as deterministic/AI workflows.
            if list(image.size) != [FRAME_SIZE, FRAME_SIZE]:
                image, _ = cleanup_frame(image)
            alpha = image.getchannel("A")
            alpha_bounds = alpha.getbbox()
            checks = {
                "exact_frame_size": check_state("pass" if list(image.size) == [FRAME_SIZE, FRAME_SIZE] else "fail"),
                "transparent_background": check_state("pass" if alpha_bounds is not None and any(value < 255 for value in alpha.getdata()) else "fail"),
                "no_clipping": check_state("fail" if border_has_alpha(image) else "pass"),
            }
            frame_status = aggregate_check_state([item["status"] for item in checks.values()])
            per_frame_states.append(frame_status)
            if frame_status == "fail":
                report["status"] = "fail"
            report["per_frame_checks"].append({
                "frame_name": "%s_%02d.png" % (clip_name, index),
                "status": frame_status,
                "checks": checks,
            })
            report["source_asset_hashes"][str(path.relative_to(project_dir))] = image_sha256(path)

        animation_status = aggregate_check_state(per_frame_states)
        report["per_animation_checks"][clip_name] = {
            "status": animation_status,
            "checks": {
                "correct_frame_count": check_state("pass" if len(frames) == frame_count else "fail"),
                "metadata_correctness": check_state(
                    "pass" if len(frames) == frame_count and (meta_fc == 0 or meta_fc == len(frames)) else "fail"
                ),
            },
        }

    report["metadata_checks"] = {
        "has_pixellab_character": check_state("pass" if char_path.exists() else "fail"),
        "has_pixellab_animations": check_state("pass" if anim_path.exists() and bool(pix_store.get("animations")) else "fail"),
        "has_animation_clips": check_state("pass" if isinstance(clips, dict) and bool(clips) else "fail"),
    }
    if any(item["status"] == "fail" for item in report["metadata_checks"].values()):
        report["status"] = "fail"

    write_json(canonical_downstream_path(project_dir, "qa_report"), report)
    project["qa_report"] = report
    project["current_stage"] = "qa"
    project["status"] = "qa_%s" % report["status"]
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Checks complete", "Pixel Lab QA finished.")
    return report

def run_qa(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    ai_workflow = project.get("ai_workflow") or {}
    if ai_workflow_ready_for_qa(ai_workflow):
        return run_ai_workflow_qa(project_id, progress=progress)
    external_authoring = project.get("external_authoring") or {}
    imported_bundle = external_authoring.get("imported_bundle") if isinstance(external_authoring.get("imported_bundle"), dict) else None
    if external_authoring.get("enabled") and imported_bundle:
        return run_external_authoring_qa(project_id, progress=progress)
    project_dir = PROJECTS_ROOT / project_id
    if pixellab_pipeline_ready_for_qa(project, project_dir):
        return run_pixellab_qa(project_id, progress=progress)
    sprite_model = project.get("sprite_model")
    rig = project.get("rig")
    clips = project.get("animation_clips") or load_json(canonical_downstream_path(project_dir, "animation_clips"), {})
    if not sprite_model or not rig or not clips:
        raise ValueError("Sprite model, rig, and animation clips must exist before QA.")
    build_report = sprite_model.get("build_report") or validate_sprite_model(project_dir, sprite_model)
    sprite_model["build_report"] = build_report
    sprite_model["status"] = build_report["status"]

    report = {
        "project_id": project_id,
        "generated_at": now_iso(),
        "status": "pass",
        "per_frame_checks": [],
        "per_animation_checks": {},
        "source_asset_hashes": {},
        "metadata_checks": {},
        "notes": [
            "QA validates deterministic asset structure and implemented image checks.",
            "Semantic art direction still requires a human review pass in the workbench.",
        ],
        "sprite_model_build_report": build_report,
    }

    rig_layout = sprite_model.get("rig_layout") or project.get("rig_layout") or {}
    required_roles = {item["part_name"] for item in (rig_layout.get("parts") or []) if item.get("required")}
    required_parts = set()
    for part in sprite_model["parts"]:
        role = part.get("part_role", part["part_name"])
        if required_roles and role not in required_roles:
            continue
        image, _ = load_part_asset(project_dir, part)
        if alpha_bbox(image) is not None:
            required_parts.add(role)
    manual_clips = approved_manual_animation_clips(project)
    runtime_animations: List[Tuple[str, Dict[str, Any], Path, str]] = [
        (animation_name, dict(spec), project_dir / "animations" / animation_name, "procedural")
        for animation_name, spec in ANIMATION_SPECS.items()
    ] + [
        (
            clip_id,
            {"frame_count": int(clip.get("frame_count") or 0), "fps": int(clip.get("fps") or 12), "loop": bool(clip.get("loop", True))},
            project_dir / str(clip.get("preview_render", {}).get("frame_dir") or ""),
            "manual",
        )
        for clip_id, clip in manual_clips.items()
    ]
    for animation_index, (animation_name, spec, animation_dir, animation_kind) in enumerate(runtime_animations):
        call_progress(progress, 8 + int((animation_index / max(1, len(runtime_animations))) * 74), "Checking %s clip" % animation_name, "Validating frame dimensions, pivots, parts, draw order, and loop continuity.")
        manifest = load_json((animation_dir.parent if animation_kind == "manual" else animation_dir) / "render_manifest.json", {"frames": []}) if animation_kind == "manual" else load_json(animation_dir / "render_manifest.json", {"frames": []})
        frames = manifest.get("frames", [])
        draw_orders = []
        foot_anchors = []
        frame_hashes = []
        manifest_names = [item.get("frame_name") for item in frames]
        for index in range(spec["frame_count"]):
            frame_name = "%s_%02d.png" % (animation_name, index)
            path = animation_dir / frame_name
            if not path.exists():
                raise ValueError("Missing frame: %s" % frame_name)
            image = Image.open(path).convert("RGBA")
            alpha = image.getchannel("A")
            alpha_bounds = alpha.getbbox()
            frame_meta = next((item for item in frames if item["frame_name"] == frame_name), None)
            if frame_meta is None:
                raise ValueError("Missing manifest row: %s" % frame_name)
            draw_sequence = frame_meta["render_meta"]["draw_sequence"]
            draw_roles = [item.get("part_role", item["part"]) for item in frame_meta["render_meta"]["render_log"]]
            draw_orders.append(tuple(draw_sequence))
            foot_anchors.append(frame_meta["render_meta"]["foot_anchor"])
            frame_hash = image_sha256(path)
            frame_hashes.append(frame_hash)
            report["source_asset_hashes"][str(path.relative_to(project_dir))] = frame_hash
            missing_parts = sorted(required_parts.difference(draw_roles))
            duplicate_prop = draw_roles.count("prop") > 1
            checks = {
                "exact_frame_size": check_state("pass" if list(image.size) == [FRAME_SIZE, FRAME_SIZE] else "fail"),
                "transparent_background": check_state("pass" if alpha_bounds is not None and any(value < 255 for value in alpha.getdata()) else "fail"),
                "exact_pivot": check_state("pass" if frame_meta.get("cleanup", {}).get("pivot") == list(FRAME_PIVOT) else "fail", {"expected": list(FRAME_PIVOT)}),
                "no_clipping": check_state("fail" if border_has_alpha(image) else "pass"),
                "no_missing_parts": check_state("fail" if missing_parts else "pass", {"missing_parts": missing_parts}),
                "no_duplicate_prop": check_state("fail" if duplicate_prop else "pass"),
            }
            frame_status = aggregate_check_state([item["status"] for item in checks.values()])
            if frame_status == "fail":
                report["status"] = "fail"
            report["per_frame_checks"].append({
                "frame_name": frame_name,
                "status": frame_status,
                "checks": checks,
            })

        stable_draw_order = len(set(draw_orders)) == 1
        foot_y_values = [anchor["left"][1] for anchor in foot_anchors] + [anchor["right"][1] for anchor in foot_anchors]
        foot_anchor_stable = (max(foot_y_values) - min(foot_y_values)) <= 30 if foot_y_values else False
        first_meta = frames[0] if frames else {}
        last_meta = frames[-1] if frames else {}
        first_left = first_meta.get("render_meta", {}).get("foot_anchor", {}).get("left", [0, 0])
        last_left = last_meta.get("render_meta", {}).get("foot_anchor", {}).get("left", [999, 999])
        loop_ok = abs(first_left[1] - last_left[1]) <= 6
        animation_checks = {
            "correct_frame_count": check_state("pass" if len(frames) == spec["frame_count"] else "fail"),
            "render_manifest_completeness": check_state(
                "pass" if manifest_names == ["%s_%02d.png" % (animation_name, index) for index in range(spec["frame_count"])] else "fail"
            ),
            "stable_draw_order": check_state("pass" if stable_draw_order else "fail"),
            "stable_foot_anchor": check_state("pass" if foot_anchor_stable else "fail"),
            "loop_seam_continuity": check_state("pass" if loop_ok else "fail"),
            "metadata_correctness": check_state(
                "pass"
                if (
                    (animation_kind == "procedural" and clips.get(animation_name, {}).get("frame_count") == spec["frame_count"] and clips.get(animation_name, {}).get("fps") == spec["fps"])
                    or (animation_kind == "manual" and manual_clips.get(animation_name, {}).get("frame_count") == spec["frame_count"] and manual_clips.get(animation_name, {}).get("fps") == spec["fps"])
                )
                else "fail"
            ),
            "clip_control_persistence": check_state("pass" if animation_kind == "manual" or isinstance(clips.get(animation_name, {}).get("controls"), dict) else "fail"),
        }
        animation_status = aggregate_check_state([item["status"] for item in animation_checks.values()])
        if animation_status == "fail":
            report["status"] = "fail"
        report["per_animation_checks"][animation_name] = {"status": animation_status, "checks": animation_checks}

    report["metadata_checks"] = {
        "has_approved_source_image": check_state(
            "pass"
            if (sprite_model.get("approved_source_image") or project.get("master_pose_approved"))
            else "fail"
        ),
        "has_sprite_model": check_state("pass" if bool(sprite_model.get("parts")) else "fail"),
        "sprite_model_build_report": check_state("pass" if build_report.get("status") != "fail" else "fail", {"status": build_report.get("status")}),
        "has_rig": check_state("pass" if bool(rig.get("rig_joint_map")) else "fail"),
        "has_animation_clips": check_state("pass" if set(clips.keys()) >= {"idle", "walk"} else "fail"),
        "manual_clips_not_stale": check_state("pass" if not any(clip.get("is_stale") for clip in (project.get("manual_animation_clips", {}).get("clips") or {}).values() if clip.get("approval_status") == "approved") else "fail"),
    }
    if any(item["status"] == "fail" for item in report["metadata_checks"].values()):
        report["status"] = "fail"
    write_json(canonical_downstream_path(project_dir, "qa_report"), report)
    project["qa_report"] = report
    project["sprite_model"] = sprite_model
    project["current_stage"] = "qa"
    project["status"] = "qa_%s" % report["status"]
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Checks complete", "QA finished. Export stays blocked until every required check passes.")
    return report

def validate_export_bundle(
    export_dir: Path,
    ordered_frames: List[Tuple[str, str, Path]],
    atlas_frames: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    spritesheet_path = export_dir / "spritesheet.png"
    spritesheet = Image.open(spritesheet_path).convert("RGBA")
    expected_order = [frame_name for _, frame_name, _ in ordered_frames]
    atlas_order = list(atlas_frames.keys())
    crop_checks = []
    for animation_name, frame_name, path in ordered_frames:
        atlas = atlas_frames[frame_name]
        crop = spritesheet.crop((atlas["x"], atlas["y"], atlas["x"] + atlas["w"], atlas["y"] + atlas["h"]))
        source = Image.open(path).convert("RGBA")
        crop_checks.append({
            "frame_name": frame_name,
            "animation": animation_name,
            "matches_source": list(crop.getdata()) == list(source.getdata()),
        })
    status = "pass" if (
        list(spritesheet.size) == [FRAME_SIZE * len(ordered_frames), FRAME_SIZE]
        and atlas_order == expected_order
        and all(item["matches_source"] for item in crop_checks)
    ) else "fail"
    return {
        "status": status,
        "checks": {
            "spritesheet_dimensions": list(spritesheet.size) == [FRAME_SIZE * len(ordered_frames), FRAME_SIZE],
            "atlas_order_matches_frames": atlas_order == expected_order,
            "packed_pixels_match_sources": all(item["matches_source"] for item in crop_checks),
        },
        "atlas_order": atlas_order,
        "expected_order": expected_order,
        "per_frame": crop_checks,
    }

def _pixellab_qa_clip_names(clips: Dict[str, Any]) -> List[str]:
    """Default workflow clips first, then other Pixel Lab clips that have raster frame paths."""
    names = [
        name
        for name, data in clips.items()
        if isinstance(data, dict) and isinstance(data.get("frames"), list) and len(data["frames"]) > 0
    ]
    priority = ["idle", "walk", "run", "jump"]
    ordered = [n for n in priority if n in names]
    ordered.extend(sorted(n for n in names if n not in priority))
    return ordered

def _write_per_animation_preview_gifs(
    export_dir: Path,
    ordered_frames: List[Tuple[str, str, Path]],
    fps_for_animation: Callable[[str], int],
) -> List[str]:
    """
    Write one looping preview GIF per animation (matches spritesheet segment order).
    Returns basenames only, e.g. preview_idle.gif, preview_walk.gif.
    """
    order: List[str] = []
    groups: Dict[str, List[Path]] = {}
    for animation_name, _frame_name, path in ordered_frames:
        if animation_name not in groups:
            order.append(animation_name)
            groups[animation_name] = []
        groups[animation_name].append(path)
    out_names: List[str] = []
    for animation_name in order:
        paths = groups[animation_name]
        fps = max(1, int(fps_for_animation(animation_name)))
        duration = int(1000 / fps)
        imgs = [Image.open(p).convert("RGBA") for p in paths]
        # Compute union bbox of non-transparent pixels across all frames so the
        # crop is stable (no jitter) and the sprite fills the preview.
        union_bbox = None
        for img in imgs:
            bb = img.split()[3].getbbox()  # alpha channel bbox
            if bb is None:
                continue
            if union_bbox is None:
                union_bbox = bb
            else:
                union_bbox = (
                    min(union_bbox[0], bb[0]),
                    min(union_bbox[1], bb[1]),
                    max(union_bbox[2], bb[2]),
                    max(union_bbox[3], bb[3]),
                )
        if union_bbox is not None:
            imgs = [img.crop(union_bbox) for img in imgs]
        out_name = "preview_%s.gif" % animation_name
        out_path = export_dir / out_name
        imgs[0].save(
            out_path,
            save_all=True,
            append_images=imgs[1:],
            duration=duration,
            loop=0,
            disposal=2,
            transparency=0,
        )
        out_names.append(out_name)
    return out_names

def _write_preview_spritesheet(spritesheet: Image.Image, export_dir: Path) -> None:
    """Save a vertically-trimmed copy of the spritesheet as preview_spritesheet.png for workbench display."""
    alpha = spritesheet.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is not None and (bbox[1] > 0 or bbox[3] < spritesheet.height):
        preview = spritesheet.crop((0, bbox[1], spritesheet.width, bbox[3]))
    else:
        preview = spritesheet
    preview.save(export_dir / "preview_spritesheet.png")

def _write_per_animation_spritesheets(
    export_dir: Path,
    ordered_frames: List[Tuple[str, str, Path]],
    animations_payload: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Write one spritesheet + atlas JSON per animation and return relative-path metadata."""
    sheets_dir = export_dir / "animation_sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    groups: Dict[str, List[Tuple[str, Path]]] = {}
    order: List[str] = []
    for animation_name, frame_name, path in ordered_frames:
        if animation_name not in groups:
            groups[animation_name] = []
            order.append(animation_name)
        groups[animation_name].append((frame_name, path))
    manifest: Dict[str, Dict[str, Any]] = {}
    for animation_name in order:
        frames = groups[animation_name]
        spritesheet = Image.new("RGBA", (FRAME_SIZE * len(frames), FRAME_SIZE), (0, 0, 0, 0))
        atlas_frames: Dict[str, Dict[str, Any]] = {}
        frame_names: List[str] = []
        for index, (frame_name, path) in enumerate(frames):
            frame_image = Image.open(path).convert("RGBA")
            x = index * FRAME_SIZE
            spritesheet.alpha_composite(frame_image, (x, 0))
            atlas_frames[frame_name] = {
                "x": x,
                "y": 0,
                "w": FRAME_SIZE,
                "h": FRAME_SIZE,
                "pivot": list(FRAME_PIVOT),
                "animation": animation_name,
            }
            frame_names.append(frame_name)
        image_name = f"{animation_name}.png"
        atlas_name = f"{animation_name}.json"
        image_rel = f"animation_sheets/{image_name}"
        atlas_rel = f"animation_sheets/{atlas_name}"
        spritesheet.save(sheets_dir / image_name)
        meta = animations_payload.get(animation_name) or {}
        write_json(
            sheets_dir / atlas_name,
            {
                "image": image_name,
                "animation": animation_name,
                "fps": int(meta.get("fps") or 12),
                "loop": bool(meta.get("loop", True)),
                "frame_count": len(frames),
                "order": frame_names,
                "frames": atlas_frames,
            },
        )
        manifest[animation_name] = {
            "image": image_rel,
            "atlas": atlas_rel,
            "frame_count": len(frames),
            "fps": int(meta.get("fps") or 12),
            "loop": bool(meta.get("loop", True)),
            "frames": frame_names,
        }
    return manifest

def export_pixellab_project(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    char_path = _pixellab_character_path(project_dir)
    pix_anim_path = _pixellab_animations_path(project_dir)
    if not char_path.exists() or not pix_anim_path.exists():
        raise ValueError("Export blocked: Pixel Lab canonical inputs missing.")

    if not project.get("qa_report") or project["qa_report"].get("status") != "pass":
        raise ValueError("Export blocked: QA must pass first.")

    clips = sync_pixellab_animation_clips(project_id, project=project, project_dir=project_dir)
    if not isinstance(clips, dict) or not clips:
        raise ValueError("Export blocked: animation_clips.json must exist for Pixel Lab export.")

    # Procedural: any animation_clips entry with raster frames.
    procedural_names = [
        name
        for name, c in clips.items()
        if isinstance(c, dict) and isinstance(c.get("frames"), list) and len(c["frames"]) > 0
    ]
    priority = ["idle", "walk", "run", "jump"]
    procedural_names = [n for n in priority if n in procedural_names] + sorted(
        n for n in procedural_names if n not in priority
    )
    if not procedural_names and not bool(approved_manual_animation_clips(project).keys()):
        raise ValueError("Export blocked: no generated animation clips are available.")

    manual_clips = approved_manual_animation_clips(project)

    export_dir = project_dir / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_dir.mkdir(parents=True, exist_ok=True)
    ordered_frames: List[Tuple[str, str, Path]] = []

    target_dir = export_dir / "frames"
    target_dir.mkdir(parents=True, exist_ok=True)

    call_progress(progress, 8, "Preparing Pixel Lab export", "Collecting Pixel Lab frames and runtime metadata.")

    for clip_name in procedural_names:
        clip = clips[clip_name]
        frame_count = int(clip.get("frame_count") or 0)
        fps = int(clip.get("fps") or 12)
        loop = bool(clip.get("loop", True))
        frames = clip.get("frames") if isinstance(clip.get("frames"), list) else []
        if frame_count and len(frames) < frame_count:
            raise ValueError("Export blocked: Pixel Lab %s frames missing (have %d need %d)." % (clip_name, len(frames), frame_count))
        if not frame_count:
            frame_count = len(frames)
        for index in range(frame_count):
            source_rel = frames[index] if index < len(frames) else None
            if not source_rel:
                raise ValueError("Export blocked: missing frame path for %s index %d." % (clip_name, index))
            source = project_dir / str(source_rel)
            if not source.exists():
                raise ValueError("Export blocked: missing frame file %s." % source)
            frame_name = "%s_%02d.png" % (clip_name, index)
            target = target_dir / frame_name
            img = Image.open(source).convert("RGBA")
            if list(img.size) != [FRAME_SIZE, FRAME_SIZE]:
                img, _ = cleanup_frame(img)
            img.save(target)
            ordered_frames.append((clip_name, frame_name, target))

    for clip_id, clip in manual_clips.items():
        frame_count = int(clip.get("frame_count") or 0)
        if not frame_count:
            continue
        source_root = project_dir / str(clip.get("preview_render", {}).get("frame_dir") or "")
        if not source_root.exists():
            raise ValueError("Export blocked: missing manual clip frame_dir for %s." % clip_id)
        for index in range(frame_count):
            source = source_root / ("%s_%02d.png" % (clip_id, index))
            if not source.exists():
                raise ValueError("Export blocked: missing manual frame %s." % source.name)
            frame_name = "%s_%02d.png" % (clip_id, index)
            target = target_dir / frame_name
            target.write_bytes(source.read_bytes())
            ordered_frames.append((clip_id, frame_name, target))

    call_progress(progress, 40, "Packing spritesheet", "Packing frame images into a deterministic atlas.")
    spritesheet = Image.new("RGBA", (FRAME_SIZE * len(ordered_frames), FRAME_SIZE), (0, 0, 0, 0))
    atlas_frames: Dict[str, Dict[str, Any]] = {}
    for index, (animation_name, frame_name, path) in enumerate(ordered_frames):
        frame_image = Image.open(path).convert("RGBA")
        x = index * FRAME_SIZE
        spritesheet.alpha_composite(frame_image, (x, 0))
        atlas_frames[frame_name] = {"x": x, "y": 0, "w": FRAME_SIZE, "h": FRAME_SIZE, "pivot": list(FRAME_PIVOT), "animation": animation_name}
    spritesheet.save(export_dir / "spritesheet.png")
    _write_preview_spritesheet(spritesheet, export_dir)

    animations_payload: Dict[str, Any] = {}
    for name in procedural_names:
        clip = clips[name]
        frame_count = int(clip.get("frame_count") or 0)
        animations_payload[name] = {
            "fps": int(clip.get("fps") or 12),
            "loop": bool(clip.get("loop", True)),
            "frame_count": frame_count,
            "frames": ["%s_%02d.png" % (name, index) for index in range(frame_count)],
            "root_motion_policy": clip.get("root_motion_policy") or clip_root_motion_policy(name),
        }
    for clip_id, clip in manual_clips.items():
        animations_payload[clip_id] = {
            "fps": int(clip.get("fps") or 12),
            "loop": bool(clip.get("loop", True)),
            "frame_count": int(clip.get("frame_count") or 0),
            "frames": ["%s_%02d.png" % (clip_id, index) for index in range(int(clip.get("frame_count") or 0))],
            "root_motion_policy": "manual",
        }

    write_json(export_dir / "atlas.json", {"image": "spritesheet.png", "frames": atlas_frames})
    write_json(export_dir / "animations.json", animations_payload)
    write_json(export_dir / "qa_report.json", project["qa_report"])
    per_animation_sheets = _write_per_animation_spritesheets(export_dir, ordered_frames, animations_payload)

    call_progress(progress, 72, "Building previews", "Creating one preview GIF per animation.")

    def _pl_export_fps(anim_name: str) -> int:
        if anim_name in clips and isinstance(clips.get(anim_name), dict):
            return int(clips[anim_name].get("fps") or 12)
        if anim_name in manual_clips:
            return int(manual_clips[anim_name].get("fps") or 12)
        return 12

    preview_gif_names = _write_per_animation_preview_gifs(export_dir, ordered_frames, _pl_export_fps)

    char_data = load_json(char_path, {}) or {}
    pix_store = load_json(pix_anim_path, None) or {}
    pix_animations = pix_store.get("animations") if isinstance(pix_store, dict) else {}
    pix_job_ids: Dict[str, Any] = {}
    if isinstance(pix_animations, dict):
        for anim_name, anim in pix_animations.items():
            if isinstance(anim, dict):
                pix_job_ids[anim_name] = anim.get("latest_job_id")

    export_manifest: Dict[str, Any] = {
        "project_id": project_id,
        "export_timestamp": now_iso(),
        "tool_version": TOOL_VERSION,
        "export_mode": "pixellab",
        "pixellab_character_id": char_data.get("character_id"),
        "pixellab_latest_job_ids": pix_job_ids,
        "source_asset_hashes": project["qa_report"]["source_asset_hashes"],
        "approved_manual_clips": [
            {"clip_id": clip_id, "clip_name": clip.get("clip_name"), "frame_count": clip.get("frame_count"), "fps": clip.get("fps")}
            for clip_id, clip in manual_clips.items()
        ],
    }

    export_manifest["preview_gifs"] = preview_gif_names
    export_manifest["animation_sheets"] = per_animation_sheets
    bundle_hashes_pl = {
        "atlas.json": image_sha256(export_dir / "atlas.json"),
        "animations.json": image_sha256(export_dir / "animations.json"),
        "qa_report.json": image_sha256(export_dir / "qa_report.json"),
        "spritesheet.png": image_sha256(export_dir / "spritesheet.png"),
    }
    for animation_name, meta in per_animation_sheets.items():
        bundle_hashes_pl[str(meta["image"])] = image_sha256(export_dir / str(meta["image"]))
        bundle_hashes_pl[str(meta["atlas"])] = image_sha256(export_dir / str(meta["atlas"]))
    for pg in preview_gif_names:
        bundle_hashes_pl[pg] = image_sha256(export_dir / pg)
    export_manifest["bundle_hashes"] = bundle_hashes_pl

    call_progress(progress, 76, "Verifying export", "Validating packed spritesheet matches sources.")
    export_manifest["verification"] = validate_export_bundle(export_dir, ordered_frames, atlas_frames)
    write_json(export_dir / "export_manifest.json", export_manifest)

    verification = export_manifest["verification"]
    if verification.get("status") != "pass":
        raise ValueError("Export verification failed: packed spritesheet did not match the frame manifest.")

    result = {
        "export_dir": str(export_dir.relative_to(project_dir)),
        "verification": verification,
        "animation_sheets": per_animation_sheets,
        "preview_gifs": preview_gif_names,
        "preview_gif": None,
        "files": [
            "spritesheet.png",
            "atlas.json",
            "animations.json",
            "qa_report.json",
            "export_manifest.json",
        ]
        + [str(meta["image"]) for meta in per_animation_sheets.values()]
        + [str(meta["atlas"]) for meta in per_animation_sheets.values()]
        + list(preview_gif_names)
        + ["frames/%s" % name for _, name, _ in ordered_frames],
    }
    project["last_export"] = result
    project["current_stage"] = "export"
    project["status"] = "export_ready"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Export ready", "The Pixel Lab sprite package is ready.")
    return result

def export_project(project_id: str, progress: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    project = load_project(project_id)
    if not project.get("qa_report") or project["qa_report"]["status"] != "pass":
        raise ValueError("Export blocked: QA must pass first.")
    ai_workflow = project.get("ai_workflow") or {}
    if project.get("qa_report", {}).get("mode") == "ai_workflow" and ai_workflow_ready_for_qa(ai_workflow):
        project_dir = PROJECTS_ROOT / project_id
        export_dir = project_dir / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        export_dir.mkdir(parents=True, exist_ok=True)
        ordered_frames: List[Tuple[str, str, Path]] = []
        call_progress(progress, 8, "Preparing AI export", "Collecting cleaned AI workflow frames for atlas packing.")
        for clip_name, spec in AI_CLIP_SPECS.items():
            source_root = project_dir / "animations" / clip_name
            for index in range(spec["frame_count"]):
                source = source_root / ("%s_%02d.png" % (clip_name, index))
                if not source.exists():
                    raise ValueError("Export blocked: missing cleaned frame %s." % source.name)
                target_dir = export_dir / "frames"
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / source.name
                target.write_bytes(source.read_bytes())
                ordered_frames.append((clip_name, source.name, target))
        call_progress(progress, 40, "Packing AI spritesheet", "Packing cleaned AI frames into the runtime atlas.")
        spritesheet = Image.new("RGBA", (FRAME_SIZE * len(ordered_frames), FRAME_SIZE), (0, 0, 0, 0))
        atlas_frames = {}
        for index, (animation_name, frame_name, path) in enumerate(ordered_frames):
            frame_image = Image.open(path).convert("RGBA")
            x = index * FRAME_SIZE
            spritesheet.alpha_composite(frame_image, (x, 0))
            atlas_frames[frame_name] = {"x": x, "y": 0, "w": FRAME_SIZE, "h": FRAME_SIZE, "pivot": list(FRAME_PIVOT), "animation": animation_name}
        spritesheet.save(export_dir / "spritesheet.png")
        _write_preview_spritesheet(spritesheet, export_dir)
        animations_payload = {
            clip_name: {
                "fps": spec["fps"],
                "loop": True,
                "frame_count": spec["frame_count"],
                "frames": ["%s_%02d.png" % (clip_name, index) for index in range(spec["frame_count"])],
                "root_motion_policy": AI_WORKFLOW_PROFILE,
            }
            for clip_name, spec in AI_CLIP_SPECS.items()
        }
        write_json(export_dir / "atlas.json", {"image": "spritesheet.png", "frames": atlas_frames})
        write_json(export_dir / "animations.json", animations_payload)
        write_json(export_dir / "qa_report.json", project["qa_report"])
        ai_animation_sheets = _write_per_animation_spritesheets(export_dir, ordered_frames, animations_payload)
        call_progress(progress, 72, "Building AI previews", "Creating one preview GIF per AI workflow clip.")
        ai_preview_names = _write_per_animation_preview_gifs(
            export_dir,
            ordered_frames,
            lambda n: int(AI_CLIP_SPECS[n]["fps"]),
        )
        workflow_manifest = {
            "profile": ai_workflow.get("profile") or AI_WORKFLOW_PROFILE,
            "character_lock_run_id": (ai_workflow.get("character_lock") or {}).get("approved_run_id"),
            "character_lock_asset_id": (ai_workflow.get("character_lock") or {}).get("approved_asset_id"),
            "key_pose_run_id": (ai_workflow.get("key_pose_set") or {}).get("approved_run_id"),
            "motion_run_ids": (ai_workflow.get("selected_assets") or {}).get("motion_run_ids") or {},
            "extract_run_ids": (ai_workflow.get("selected_assets") or {}).get("extract_run_ids") or {},
            "cleanup_run_ids": (ai_workflow.get("selected_assets") or {}).get("cleanup_run_ids") or {},
            "dependency_health_snapshot": ai_workflow.get("dependency_status") or {},
            "model_versions": {
                "comfyui": "removed-phase-8",
                "photomaker": "configured-via-environment",
                "ipadapter_plus": "configured-via-environment",
                "tooncrafter": "configured-via-environment",
                "anime_segmentation": "configured-via-environment",
                "pixelart_cleanup": "configured-via-environment",
            },
        }
        export_manifest = {
            "project_id": project_id,
            "approved_concept_id": (project.get("character_spec") or {}).get("approved_concept_id"),
            "approved_master_pose": None,
            "approved_source_image": (project.get("character_spec") or {}).get("approved_source_image"),
            "export_timestamp": now_iso(),
            "tool_version": TOOL_VERSION,
            "workflow_profile": ai_workflow.get("profile") or AI_WORKFLOW_PROFILE,
            "source_asset_hashes": project["qa_report"]["source_asset_hashes"],
            "workflow": workflow_manifest,
            "preview_gifs": ai_preview_names,
            "animation_sheets": ai_animation_sheets,
        }
        write_json(export_dir / "export_manifest.json", export_manifest)
        verification = validate_export_bundle(export_dir, ordered_frames, atlas_frames)
        project["last_export"] = {
            "export_dir": str(export_dir.relative_to(project_dir)),
            "spritesheet": "spritesheet.png",
            "atlas": "atlas.json",
            "animations": "animations.json",
            "animation_sheets": ai_animation_sheets,
            "preview_gif": None,
            "preview_gifs": ai_preview_names,
            "export_manifest": "export_manifest.json",
            "generated_at": now_iso(),
            "mode": "ai_workflow",
            "verification": verification,
            "files": ["spritesheet.png", "atlas.json", "animations.json", "export_manifest.json", "qa_report.json"]
            + [str(meta["image"]) for meta in ai_animation_sheets.values()]
            + [str(meta["atlas"]) for meta in ai_animation_sheets.values()]
            + list(ai_preview_names),
        }
        project["current_stage"] = "export"
        project["status"] = "export_complete"
        project["updated_at"] = now_iso()
        save_project(project)
        call_progress(progress, 100, "AI export ready", "AI workflow frames were packaged into the runtime atlas/export bundle.")
        return project["last_export"]
    external_authoring = project.get("external_authoring") or {}
    imported_bundle = external_authoring.get("imported_bundle") if isinstance(external_authoring.get("imported_bundle"), dict) else None
    project_dir = PROJECTS_ROOT / project_id
    pix_char_exists = _pixellab_character_path(project_dir).exists()
    pix_anim_exists = _pixellab_animations_path(project_dir).exists()
    if not project.get("sprite_model") and not (external_authoring.get("enabled") and imported_bundle) and not (pix_char_exists and pix_anim_exists):
        raise ValueError("Export blocked: sprite model is missing.")
    if external_authoring.get("enabled") and imported_bundle:
        export_dir = project_dir / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        export_dir.mkdir(parents=True, exist_ok=True)
        call_progress(progress, 12, "Preparing external export", "Copying imported SkelForm assets into the standard export bundle.")
        spritesheet_source = project_dir / str(imported_bundle.get("spritesheet_image_path") or "")
        atlas_source = project_dir / str(imported_bundle.get("atlas_path") or "")
        animations_source = project_dir / str(imported_bundle.get("animations_path") or "")
        preview_source = project_dir / str(imported_bundle.get("preview_gif_path") or "") if imported_bundle.get("preview_gif_path") else None
        for source, target_name in [
            (spritesheet_source, "spritesheet.png"),
            (atlas_source, "atlas.json"),
            (animations_source, "animations.json"),
        ]:
            if not source.exists():
                raise ValueError("Export blocked: missing imported bundle asset %s." % source)
            (export_dir / target_name).write_bytes(source.read_bytes())
        write_json(export_dir / "qa_report.json", project["qa_report"])
        if preview_source and preview_source.exists():
            (export_dir / "preview.gif").write_bytes(preview_source.read_bytes())
        export_manifest = {
            "project_id": project_id,
            "approved_concept_id": (project.get("character_spec") or {}).get("approved_concept_id"),
            "approved_master_pose": None,
            "approved_source_image": (project.get("sprite_model") or {}).get("approved_source_image"),
            "export_timestamp": now_iso(),
            "tool_version": TOOL_VERSION,
            "export_mode": "external_authoring",
            "external_authoring_provider": external_authoring.get("provider"),
            "external_bundle": {
                "bundle_id": imported_bundle.get("bundle_id"),
                "animation_names": imported_bundle.get("animation_names") or [],
                "frame_count": imported_bundle.get("frame_count"),
                "source_label": imported_bundle.get("source_label"),
            },
            "source_asset_hashes": project["qa_report"]["source_asset_hashes"],
        }
        write_json(export_dir / "export_manifest.json", export_manifest)
        project["last_export"] = {
            "export_dir": str(export_dir.relative_to(project_dir)),
            "spritesheet": "spritesheet.png",
            "atlas": "atlas.json",
            "animations": "animations.json",
            "preview_gif": "preview.gif" if preview_source and preview_source.exists() else None,
            "export_manifest": "export_manifest.json",
            "generated_at": now_iso(),
            "mode": "external_authoring",
        }
        project["current_stage"] = "export"
        project["status"] = "export_complete"
        project["updated_at"] = now_iso()
        save_project(project)
        call_progress(progress, 100, "External export ready", "Imported SkelForm assets were packaged into the standard export directory.")
        return {
            "export_dir": str(export_dir.relative_to(project_dir)),
            "spritesheet": "spritesheet.png",
            "atlas": "atlas.json",
            "animations": "animations.json",
            "preview_gif": "preview.gif" if preview_source and preview_source.exists() else None,
            "export_manifest": "export_manifest.json",
            "mode": "external_authoring",
        }
    # Phase 6: Pixel Lab export path (no sprite_model/rig dependency).
    if pix_char_exists and pix_anim_exists:
        return export_pixellab_project(project_id, progress=progress)
    clips = project.get("animation_clips") or load_json(canonical_downstream_path(project_dir, "animation_clips"), {})
    manual_clips = approved_manual_animation_clips(project)
    export_dir = project_dir / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_dir.mkdir(parents=True, exist_ok=True)
    ordered_frames = []
    call_progress(progress, 8, "Preparing export", "Collecting deterministic clip frames and runtime metadata.")
    runtime_exports: List[Tuple[str, int, Path]] = [
        (animation_name, ANIMATION_SPECS[animation_name]["frame_count"], project_dir / "animations" / animation_name)
        for animation_name in ["idle", "walk"]
    ] + [
        (clip_id, int(clip.get("frame_count") or 0), project_dir / str(clip.get("preview_render", {}).get("frame_dir") or ""))
        for clip_id, clip in manual_clips.items()
    ]
    for animation_name, frame_count, source_root in runtime_exports:
        for index in range(frame_count):
            source = source_root / ("%s_%02d.png" % (animation_name, index))
            target_dir = export_dir / "frames"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / source.name
            target.write_bytes(source.read_bytes())
            ordered_frames.append((animation_name, source.name, target))

    call_progress(progress, 40, "Packing spritesheet", "Packing frame images into a deterministic atlas.")
    spritesheet = Image.new("RGBA", (FRAME_SIZE * len(ordered_frames), FRAME_SIZE), (0, 0, 0, 0))
    atlas_frames = {}
    for index, (animation_name, frame_name, path) in enumerate(ordered_frames):
        frame_image = Image.open(path).convert("RGBA")
        x = index * FRAME_SIZE
        spritesheet.alpha_composite(frame_image, (x, 0))
        atlas_frames[frame_name] = {"x": x, "y": 0, "w": FRAME_SIZE, "h": FRAME_SIZE, "pivot": list(FRAME_PIVOT), "animation": animation_name}
    spritesheet.save(export_dir / "spritesheet.png")
    _write_preview_spritesheet(spritesheet, export_dir)

    animations_payload = {
        name: {
            "fps": clips[name]["fps"],
            "loop": clips[name]["loop"],
            "frame_count": clips[name]["frame_count"],
            "frames": ["%s_%02d.png" % (name, index) for index in range(clips[name]["frame_count"])],
            "root_motion_policy": clips[name]["root_motion_policy"],
        }
        for name in ["idle", "walk"]
    }
    for clip_id, clip in manual_clips.items():
        animations_payload[clip_id] = {
            "fps": int(clip.get("fps") or 12),
            "loop": bool(clip.get("loop", True)),
            "frame_count": int(clip.get("frame_count") or 0),
            "frames": ["%s_%02d.png" % (clip_id, index) for index in range(int(clip.get("frame_count") or 0))],
            "root_motion_policy": "manual",
        }
    export_manifest = {
        "project_id": project_id,
        "approved_concept_id": project["character_spec"]["approved_concept_id"],
        "approved_master_pose": project.get("sprite_model", {}).get("approved_master_pose"),
        "approved_source_image": project.get("sprite_model", {}).get("approved_source_image"),
        "export_timestamp": now_iso(),
        "tool_version": TOOL_VERSION,
        "sprite_model_hash": hashlib.sha256(canonical_downstream_path(project_dir, "sprite_model").read_bytes()).hexdigest(),
        "rig_hash": hashlib.sha256(canonical_downstream_path(project_dir, "rig").read_bytes()).hexdigest(),
        "source_asset_hashes": project["qa_report"]["source_asset_hashes"],
        "approved_manual_clips": [
            {"clip_id": clip_id, "clip_name": clip.get("clip_name"), "frame_count": clip.get("frame_count"), "fps": clip.get("fps")}
            for clip_id, clip in manual_clips.items()
        ],
    }
    write_json(export_dir / "atlas.json", {"image": "spritesheet.png", "frames": atlas_frames})
    write_json(export_dir / "animations.json", animations_payload)
    write_json(export_dir / "qa_report.json", project["qa_report"])
    det_animation_sheets = _write_per_animation_spritesheets(export_dir, ordered_frames, animations_payload)

    call_progress(progress, 72, "Building previews", "Creating one preview GIF per animation.")

    def _det_export_fps(anim_name: str) -> int:
        if anim_name in clips:
            return int(clips[anim_name]["fps"])
        if anim_name in manual_clips:
            return int(manual_clips[anim_name].get("fps") or 12)
        return 12

    det_preview_names = _write_per_animation_preview_gifs(export_dir, ordered_frames, _det_export_fps)
    export_manifest["preview_gifs"] = det_preview_names
    export_manifest["animation_sheets"] = det_animation_sheets
    bundle_hashes_det = {
        "atlas.json": image_sha256(export_dir / "atlas.json"),
        "animations.json": image_sha256(export_dir / "animations.json"),
        "qa_report.json": image_sha256(export_dir / "qa_report.json"),
        "spritesheet.png": image_sha256(export_dir / "spritesheet.png"),
    }
    for animation_name, meta in det_animation_sheets.items():
        bundle_hashes_det[str(meta["image"])] = image_sha256(export_dir / str(meta["image"]))
        bundle_hashes_det[str(meta["atlas"])] = image_sha256(export_dir / str(meta["atlas"]))
    for pg in det_preview_names:
        bundle_hashes_det[pg] = image_sha256(export_dir / pg)
    export_manifest["bundle_hashes"] = bundle_hashes_det
    export_manifest["verification"] = validate_export_bundle(export_dir, ordered_frames, atlas_frames)
    if export_manifest["verification"]["status"] != "pass":
        raise ValueError("Export verification failed: packed spritesheet did not match the frame manifest.")
    write_json(export_dir / "export_manifest.json", export_manifest)

    result = {
        "export_dir": str(export_dir.relative_to(project_dir)),
        "verification": export_manifest["verification"],
        "animation_sheets": det_animation_sheets,
        "preview_gifs": det_preview_names,
        "preview_gif": None,
        "files": [
            "spritesheet.png",
            "atlas.json",
            "animations.json",
            "qa_report.json",
            "export_manifest.json",
        ]
        + [str(meta["image"]) for meta in det_animation_sheets.values()]
        + [str(meta["atlas"]) for meta in det_animation_sheets.values()]
        + list(det_preview_names)
        + ["frames/%s" % name for _, name, _ in ordered_frames],
    }
    project["last_export"] = result
    project["current_stage"] = "export"
    project["status"] = "export_ready"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Export ready", "The deterministic sprite package is ready.")
    return result
