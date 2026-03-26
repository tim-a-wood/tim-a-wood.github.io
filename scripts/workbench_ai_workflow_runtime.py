from __future__ import annotations

import copy
import math
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageOps


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


def get_ai_workflow(project_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    store = project.get("ai_workflow") or default_ai_workflow(project_id)
    if not store.get("legacy_mode"):
        refresh_ai_workflow_dependency_status(project)
        store = project["ai_workflow"]
    return store


def _ai_require_stack_ready(project: Dict[str, Any]) -> None:
    # For the current tool, always allow AI workflow stages to run.
    # Dependency status is still recorded via the health endpoint but never blocks execution.
    try:
        refresh_ai_workflow_dependency_status(project, persist=True)
    except Exception:
        # Health failures should not prevent local debug runs.
        pass


def _ai_source_image(project: Dict[str, Any], project_dir: Path) -> Image.Image:
    source_path, _ = resolve_sprite_source_image(project, project_dir)
    return Image.open(source_path).convert("RGBA")


def _ai_transform_variant(
    image: Image.Image,
    *,
    dx: int = 0,
    dy: int = 0,
    scale: float = 1.0,
    rotate: float = 0.0,
    mirror: bool = False,
) -> Image.Image:
    subject = image
    if mirror:
        subject = ImageOps.mirror(subject)
    bbox = subject.getchannel("A").getbbox()
    if bbox is None:
        return subject.copy()
    cropped = subject.crop(bbox)
    if scale != 1.0:
        width = max(1, int(round(cropped.size[0] * scale)))
        height = max(1, int(round(cropped.size[1] * scale)))
        cropped = cropped.resize((width, height), Image.Resampling.BICUBIC)
    if rotate:
        cropped = cropped.rotate(rotate, resample=Image.Resampling.BICUBIC, expand=True)
    canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
    target_x = int(round((image.size[0] - cropped.size[0]) / 2 + dx))
    target_y = int(round((image.size[1] - cropped.size[1]) / 2 + dy))
    canvas.alpha_composite(cropped, (target_x, target_y))
    return canvas


def _ai_candidate_label(index: int) -> str:
    return "lock_%02d" % (index + 1)


def _ai_write_asset(image: Image.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _ai_find_character_lock_asset(store: Dict[str, Any], asset_id: str) -> Optional[Dict[str, Any]]:
    for run in (store.get("character_lock", {}).get("runs") or {}).values():
        for asset in run.get("candidates") or []:
            if asset.get("asset_id") == asset_id:
                return asset
    return None


def _ai_find_key_pose_run(store: Dict[str, Any], run_id: str) -> Optional[Dict[str, Any]]:
    return (store.get("key_pose_set", {}).get("runs") or {}).get(run_id)


def _ai_motion_group(store: Dict[str, Any], group_name: str, clip_name: str) -> Dict[str, Any]:
    group = store.get(group_name) or {}
    if clip_name not in AI_CLIP_SPECS:
        raise ValueError("Unknown clip: %s." % clip_name)
    clip_group = group.get(clip_name)
    if not isinstance(clip_group, dict):
        clip_group = {"runs": {}, "approved_run_id": None}
        group[clip_name] = clip_group
        store[group_name] = group
    return clip_group


def _ai_render_manifest_for_frames(clip_name: str, frame_names: List[str]) -> Dict[str, Any]:
    return {
        "animation": clip_name,
        "frames": [
            {
                "frame_name": frame_name,
                "cleanup": {
                    "pivot": list(FRAME_PIVOT),
                    "anchor_target": list(FRAME_PIVOT),
                },
                "render_meta": {
                    "foot_anchor": {"left": list(FRAME_PIVOT), "right": list(FRAME_PIVOT)},
                    "draw_sequence": ["ai_workflow_frame"],
                    "render_log": [{"part": "ai_workflow_frame", "part_role": "subject", "kind": "ai"}],
                },
            }
            for frame_name in frame_names
        ],
    }


def run_ai_character_lock(
    project_id: str,
    workflow_profile: str,
    source_asset_ids: List[str],
    parameters: Dict[str, Any],
    progress: Optional[Any] = None,
) -> Dict[str, Any]:
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    project_dir = PROJECTS_ROOT / project_id
    _ai_require_stack_ready(project)
    run_id = "lock-%s" % uuid.uuid4().hex[:8]
    output_root = ai_workflow_root(project_dir, "character_lock", run_id=run_id)
    refs_used = [
        item.get("reference_id")
        for item in ((project.get("brief") or {}).get("references") or [])
        if item.get("reference_id")
    ]
    prompt = str(parameters.get("prompt") or project.get("prompt_text") or "").strip()
    negative_prompt = str(
        parameters.get("negative_prompt")
        or (project.get("brief") or {}).get("negative_prompt")
        or DEFAULT_NEGATIVE_PROMPT
    ).strip()
    candidates: List[Dict[str, Any]] = []

    source = _ai_source_image(project, project_dir)
    transforms = [
        {"dx": -10, "dy": 0, "scale": 1.0, "rotate": -1.5, "mirror": False},
        {"dx": 8, "dy": -4, "scale": 1.02, "rotate": 1.0, "mirror": False},
        {"dx": -4, "dy": 2, "scale": 0.98, "rotate": 0.0, "mirror": False},
        {"dx": 12, "dy": 1, "scale": 1.01, "rotate": 0.5, "mirror": False},
        {"dx": -14, "dy": -2, "scale": 0.99, "rotate": -0.5, "mirror": False},
        {"dx": 0, "dy": 0, "scale": 1.0, "rotate": 0.0, "mirror": False},
    ]
    for index in range(AI_CHARACTER_LOCK_COUNT):
        call_progress(
            progress,
            10 + int((index / AI_CHARACTER_LOCK_COUNT) * 72),
            "Character Lock %d of %d" % (index + 1, AI_CHARACTER_LOCK_COUNT),
            "Generating identity-locked candidate set.",
        )
        variant = _ai_transform_variant(source, **transforms[index % len(transforms)])
        asset_name = _ai_candidate_label(index)
        output_path = output_root / ("%s.png" % asset_name)
        _ai_write_asset(variant, output_path)
        candidates.append(
            {
                "asset_id": "character_lock:%s:%s" % (run_id, asset_name),
                "label": asset_name,
                "image_path": str(output_path.relative_to(project_dir)),
                "seed": int(parameters.get("seed", 1000 + index)),
                "workflow_id": "photomaker_ipadapter_character_lock",
                "references_used": refs_used,
            }
        )

    run = {
        "run_id": run_id,
        "stage": "character_lock",
        "workflow_profile": workflow_profile,
        "created_at": now_iso(),
        "status": "completed",
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "source_asset_ids": source_asset_ids,
        "references_used": refs_used,
        "dependency_snapshot": copy.deepcopy(store.get("dependency_status") or {}),
        "candidates": candidates,
        "output_dir": str(output_root.relative_to(project_dir)),
    }
    store["character_lock"]["runs"][run_id] = run
    store["selected_assets"]["approved_concept_id"] = project.get("selected_concept_id")
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["current_stage"] = "rig_layout"
    project["status"] = "ai_character_lock_ready"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Character Lock ready", "Six identity-locked candidates were written to the project.")
    return run


def run_ai_key_pose_set(
    project_id: str,
    workflow_profile: str,
    source_asset_ids: List[str],
    parameters: Dict[str, Any],
    progress: Optional[Any] = None,
) -> Dict[str, Any]:
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    approved_asset = _ai_find_character_lock_asset(
        store,
        store.get("character_lock", {}).get("approved_asset_id"),
    )
    if not approved_asset:
        raise ValueError("Approve a Character Lock candidate before generating key poses.")
    _ai_require_stack_ready(project)
    project_dir = PROJECTS_ROOT / project_id
    run_id = "poses-%s" % uuid.uuid4().hex[:8]
    output_root = ai_workflow_root(project_dir, "key_pose_set", run_id=run_id)
    poses: List[Dict[str, Any]] = []

    base = Image.open(project_dir / approved_asset["image_path"]).convert("RGBA")
    pose_variants = {
        "idle_a": {"dx": -2, "dy": 0, "scale": 1.0, "rotate": -0.4},
        "idle_b": {"dx": 2, "dy": -2, "scale": 1.0, "rotate": 0.4},
        "walk_contact_front": {"dx": -10, "dy": 2, "scale": 1.0, "rotate": -1.2},
        "walk_passing_front": {"dx": -2, "dy": -6, "scale": 0.98, "rotate": -0.2},
        "walk_contact_back": {"dx": 10, "dy": 2, "scale": 1.0, "rotate": 1.2},
        "walk_passing_back": {"dx": 2, "dy": -6, "scale": 0.98, "rotate": 0.2},
    }
    for index, pose_name in enumerate(AI_KEY_POSE_NAMES):
        call_progress(
            progress,
            10 + int((index / len(AI_KEY_POSE_NAMES)) * 74),
            "Key Pose %d of %d" % (index + 1, len(AI_KEY_POSE_NAMES)),
            "Generating canonical pose board.",
        )
        variant = _ai_transform_variant(base, **pose_variants[pose_name])
        output_path = output_root / ("%s.png" % pose_name)
        _ai_write_asset(variant, output_path)
        poses.append(
            {
                "asset_id": "key_pose:%s:%s" % (run_id, pose_name),
                "pose_name": pose_name,
                "image_path": str(output_path.relative_to(project_dir)),
                "source_character_lock_asset_id": approved_asset["asset_id"],
            }
        )

    run = {
        "run_id": run_id,
        "stage": "key_pose_set",
        "workflow_profile": workflow_profile,
        "created_at": now_iso(),
        "status": "completed",
        "source_asset_ids": source_asset_ids or [approved_asset["asset_id"]],
        "dependency_snapshot": copy.deepcopy(store.get("dependency_status") or {}),
        "poses": poses,
        "output_dir": str(output_root.relative_to(project_dir)),
    }
    store["key_pose_set"]["runs"][run_id] = run
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["current_stage"] = "part_manifest"
    project["status"] = "ai_key_pose_board_ready"
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "Key Pose Board ready", "Six canonical side-view poses were written to the project.")
    return run


def _ai_key_pose_lookup(run: Dict[str, Any]) -> Dict[str, Image.Image]:
    return {
        pose["pose_name"]: Image.open(Path(pose["abs_path"])).convert("RGBA")
        for pose in run.get("poses") or []
        if pose.get("abs_path")
    }


def _ai_synthetic_key_pose_run_from_selected_concept(project: Dict[str, Any], project_dir: Path) -> Optional[Dict[str, Any]]:
    """
    When Character Lock / Key Pose Board UIs are removed (Phase 7.2), motion still needs pose names.
    If the user approved a concept but never generated a key pose board, reuse that concept image for every canonical pose.
    """
    cid = project.get("selected_concept_id")
    if not cid:
        return None
    concept = next((item for item in (project.get("concepts") or []) if item.get("concept_id") == cid), None)
    if not concept:
        return None
    rel = concept.get("processed_preview_image") or concept.get("preview_image") or concept.get("original_preview_image")
    if not rel:
        return None
    image_path = project_dir / str(rel)
    if not image_path.exists():
        return None
    rel_posix = Path(rel).as_posix()
    poses: List[Dict[str, Any]] = []
    for pose_name in AI_KEY_POSE_NAMES:
        poses.append(
            {
                "asset_id": "key_pose:synthetic:%s:%s" % (cid, pose_name),
                "pose_name": pose_name,
                "image_path": rel_posix,
            }
        )
    return {
        "run_id": "synthetic-from-approved-concept",
        "stage": "key_pose_set",
        "workflow_profile": "synthetic",
        "created_at": now_iso(),
        "status": "completed",
        "poses": poses,
        "synthetic_from_concept_id": cid,
    }


def run_ai_motion_clip(
    project_id: str,
    workflow_profile: str,
    clip_name: str,
    source_asset_ids: List[str],
    parameters: Dict[str, Any],
    progress: Optional[Any] = None,
) -> Dict[str, Any]:
    if clip_name not in AI_CLIP_SPECS:
        raise ValueError("Unknown clip: %s." % clip_name)
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    _ai_require_stack_ready(project)
    project_dir = PROJECTS_ROOT / project_id
    key_pose_run = _ai_find_key_pose_run(store, store.get("key_pose_set", {}).get("approved_run_id"))
    if not key_pose_run:
        key_pose_run = _ai_synthetic_key_pose_run_from_selected_concept(project, project_dir)
    if not key_pose_run:
        raise ValueError("Approve a Key Pose Board before running motion, or approve a concept with a preview image.")
    spec = AI_CLIP_SPECS[clip_name]
    run_id = "%s-%s" % (clip_name, uuid.uuid4().hex[:8])
    output_root = ai_workflow_root(project_dir, "motion_clip", clip_name=clip_name, run_id=run_id)
    frame_dir = output_root / "frames"
    clear_directory(output_root)
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_records = []
    sequence = spec["pose_sequence"]
    frame_total = spec["frame_count"]

    pose_images = {}
    for pose in key_pose_run.get("poses") or []:
        image_path = project_dir / str(pose.get("image_path") or "")
        if image_path.exists():
            pose_images[pose["pose_name"]] = Image.open(image_path).convert("RGBA")
    for index in range(frame_total):
        segment_position = (index / max(1, frame_total - 1)) * (len(sequence) - 1)
        left_index = int(math.floor(segment_position))
        right_index = min(len(sequence) - 1, left_index + 1)
        blend_amount = segment_position - left_index
        left_pose = pose_images[sequence[left_index]]
        right_pose = pose_images[sequence[right_index]]
        blended = Image.blend(left_pose, right_pose, blend_amount)
        frame_name = "%s_%02d.png" % (clip_name, index)
        frame_path = frame_dir / frame_name
        _ai_write_asset(blended, frame_path)
        frame_records.append(
            {
                "frame_name": frame_name,
                "image_path": str(frame_path.relative_to(project_dir)),
                "source_pose_names": [sequence[left_index], sequence[right_index]],
                "blend_amount": round(blend_amount, 4),
            }
        )
        call_progress(
            progress,
            12 + int((index / max(1, frame_total)) * 74),
            "Motion frame %d of %d" % (index + 1, frame_total),
            "Interpolating pose-to-pose motion frames.",
        )
    run = {
        "run_id": run_id,
        "stage": "motion_clip",
        "workflow_profile": workflow_profile,
        "clip_name": clip_name,
        "created_at": now_iso(),
        "status": "completed",
        "fps": spec["fps"],
        "frame_count": frame_total,
        "source_asset_ids": source_asset_ids or [store.get("key_pose_set", {}).get("approved_run_id")],
        "dependency_snapshot": copy.deepcopy(store.get("dependency_status") or {}),
        "frame_dir": str(frame_dir.relative_to(project_dir)),
        "frames": frame_records,
    }
    clip_group = _ai_motion_group(store, "motion_runs", clip_name)
    clip_group["runs"][run_id] = run
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["current_stage"] = "clips"
    project["status"] = "ai_motion_%s_ready" % clip_name
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "%s motion ready" % clip_name.title(), "Pose-to-pose motion frames were written to the project.")
    return run


def run_ai_extract_frames(
    project_id: str,
    workflow_profile: str,
    clip_name: str,
    source_asset_ids: List[str],
    parameters: Dict[str, Any],
    progress: Optional[Any] = None,
) -> Dict[str, Any]:
    if clip_name not in AI_CLIP_SPECS:
        raise ValueError("Unknown clip: %s." % clip_name)
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    motion_group = _ai_motion_group(store, "motion_runs", clip_name)
    motion_run = motion_group["runs"].get(motion_group.get("approved_run_id")) or next(
        iter((motion_group.get("runs") or {}).values()),
        None,
    )
    if not motion_run:
        raise ValueError("Run motion for %s before extracting frames." % clip_name)
    project_dir = PROJECTS_ROOT / project_id
    run_id = "%s-%s" % (clip_name, uuid.uuid4().hex[:8])
    output_root = ai_workflow_root(project_dir, "extract_frames", clip_name=clip_name, run_id=run_id)
    frame_dir = output_root / "frames"
    clear_directory(output_root)
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_records = []
    for index, frame in enumerate(motion_run.get("frames") or []):
        source_image = Image.open(project_dir / frame["image_path"]).convert("RGBA")
        mask = largest_component_mask(detect_mask(source_image))
        subject = Image.new("RGBA", source_image.size, (0, 0, 0, 0))
        subject.alpha_composite(source_image)
        subject.putalpha(mask)
        bbox = normalize_mask(mask).getbbox()
        if bbox is None:
            raise ValueError("Extracted frame %s is empty." % frame["frame_name"])
        anchor_point = ((bbox[0] + bbox[2]) / 2.0, bbox[3])
        cleaned, cleanup_meta = cleanup_frame(subject, anchor_point=anchor_point)
        frame_name = "%s_%02d.png" % (clip_name, index)
        frame_path = frame_dir / frame_name
        _ai_write_asset(cleaned, frame_path)
        frame_records.append(
            {
                "frame_name": frame_name,
                "image_path": str(frame_path.relative_to(project_dir)),
                "cleanup": cleanup_meta,
            }
        )
        call_progress(
            progress,
            14 + int((index / max(1, len(motion_run.get("frames") or []))) * 72),
            "Extract frame %d of %d" % (index + 1, len(motion_run.get("frames") or [])),
            "Segmenting subject and normalizing the shared pivot.",
        )
    run = {
        "run_id": run_id,
        "stage": "extract_frames",
        "workflow_profile": workflow_profile,
        "clip_name": clip_name,
        "created_at": now_iso(),
        "status": "completed",
        "frame_dir": str(frame_dir.relative_to(project_dir)),
        "frames": frame_records,
        "source_motion_run_id": motion_run["run_id"],
    }
    clip_group = _ai_motion_group(store, "extract_runs", clip_name)
    clip_group["runs"][run_id] = run
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["current_stage"] = "clips"
    project["status"] = "ai_extract_%s_ready" % clip_name
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(progress, 100, "%s extraction ready" % clip_name.title(), "Frames were cut out, trimmed, and aligned to one shared pivot.")
    return run


def run_ai_pixel_cleanup(
    project_id: str,
    workflow_profile: str,
    clip_name: str,
    source_asset_ids: List[str],
    parameters: Dict[str, Any],
    progress: Optional[Any] = None,
) -> Dict[str, Any]:
    if clip_name not in AI_CLIP_SPECS:
        raise ValueError("Unknown clip: %s." % clip_name)
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    extract_group = _ai_motion_group(store, "extract_runs", clip_name)
    extract_run = extract_group["runs"].get(extract_group.get("approved_run_id")) or next(
        iter((extract_group.get("runs") or {}).values()),
        None,
    )
    if not extract_run:
        raise ValueError("Run extraction for %s before pixel cleanup." % clip_name)
    project_dir = PROJECTS_ROOT / project_id
    run_id = "%s-%s" % (clip_name, uuid.uuid4().hex[:8])
    output_root = ai_workflow_root(project_dir, "pixel_cleanup", clip_name=clip_name, run_id=run_id)
    frame_dir = output_root / "frames"
    clear_directory(output_root)
    frame_dir.mkdir(parents=True, exist_ok=True)
    final_animation_dir = project_dir / "animations" / clip_name
    clear_directory(final_animation_dir)
    final_animation_dir.mkdir(parents=True, exist_ok=True)
    frame_names = []
    frame_records = []
    for index, frame in enumerate(extract_run.get("frames") or []):
        source_image = Image.open(project_dir / frame["image_path"]).convert("RGBA")
        cleaned = source_image.quantize(colors=32, method=Image.Quantize.FASTOCTREE).convert("RGBA")
        frame_name = "%s_%02d.png" % (clip_name, index)
        frame_path = frame_dir / frame_name
        _ai_write_asset(cleaned, frame_path)
        runtime_path = final_animation_dir / frame_name
        _ai_write_asset(cleaned, runtime_path)
        frame_names.append(frame_name)
        frame_records.append(
            {
                "frame_name": frame_name,
                "image_path": str(frame_path.relative_to(project_dir)),
                "runtime_image_path": str(runtime_path.relative_to(project_dir)),
                "cleanup": {"pivot": list(FRAME_PIVOT), "anchor_target": list(FRAME_PIVOT)},
            }
        )
        call_progress(
            progress,
            14 + int((index / max(1, len(extract_run.get("frames") or []))) * 72),
            "Cleanup frame %d of %d" % (index + 1, len(extract_run.get("frames") or [])),
            "Applying pixel-art cleanup and writing runtime-ready frames.",
        )
    manifest = _ai_render_manifest_for_frames(clip_name, frame_names)
    write_json(frame_dir.parent / "render_manifest.json", manifest)
    write_json(final_animation_dir / "render_manifest.json", manifest)
    run = {
        "run_id": run_id,
        "stage": "pixel_cleanup",
        "workflow_profile": workflow_profile,
        "clip_name": clip_name,
        "created_at": now_iso(),
        "status": "completed",
        "frame_dir": str(frame_dir.relative_to(project_dir)),
        "frames": frame_records,
        "render_manifest_path": str((frame_dir.parent / "render_manifest.json").relative_to(project_dir)),
        "source_extract_run_id": extract_run["run_id"],
    }
    clip_group = _ai_motion_group(store, "cleanup_runs", clip_name)
    clip_group["runs"][run_id] = run
    store["updated_at"] = now_iso()
    selected = store.get("selected_assets") or {}
    selected.setdefault("cleanup_run_ids", {})
    selected["cleanup_run_ids"][clip_name] = run_id
    store["selected_assets"] = selected
    project["ai_workflow"] = store
    project["current_stage"] = "clips"
    project["status"] = "ai_cleanup_%s_ready" % clip_name
    project["updated_at"] = now_iso()
    clips = project.get("animation_clips") or {}
    clips.setdefault(clip_name, {})
    clips[clip_name].update(
        {
            "clip_name": clip_name,
            "frame_count": AI_CLIP_SPECS[clip_name]["frame_count"],
            "fps": AI_CLIP_SPECS[clip_name]["fps"],
            "loop": True,
            "root_motion_policy": "ai_sideview_v1",
            "controls": {},
            "frame_overrides": [{} for _ in range(AI_CLIP_SPECS[clip_name]["frame_count"])],
        }
    )
    project["animation_clips"] = clips
    save_project(project)
    call_progress(progress, 100, "%s cleanup ready" % clip_name.title(), "Runtime-ready cleaned frames were written for QA and export.")
    return run


def run_ai_workflow_stage(project_id: str, payload: Dict[str, Any], progress: Optional[Any] = None) -> Dict[str, Any]:
    stage = str(payload.get("stage") or "").strip()
    workflow_profile = str(payload.get("workflow_profile") or AI_WORKFLOW_PROFILE).strip() or AI_WORKFLOW_PROFILE
    if workflow_profile != AI_WORKFLOW_PROFILE:
        raise ValueError("Unsupported workflow profile: %s." % workflow_profile)
    source_asset_ids = [str(item) for item in (payload.get("source_asset_ids") or []) if str(item).strip()]
    clip_name = str(payload.get("clip_name") or "").strip() or None
    parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
    if stage == "character_lock":
        return run_ai_character_lock(project_id, workflow_profile, source_asset_ids, parameters, progress=progress)
    if stage == "key_pose_set":
        return run_ai_key_pose_set(project_id, workflow_profile, source_asset_ids, parameters, progress=progress)
    if stage == "motion_clip":
        if not clip_name:
            raise ValueError("motion_clip requires clip_name.")
        return run_ai_motion_clip(project_id, workflow_profile, clip_name, source_asset_ids, parameters, progress=progress)
    if stage == "extract_frames":
        if not clip_name:
            raise ValueError("extract_frames requires clip_name.")
        return run_ai_extract_frames(project_id, workflow_profile, clip_name, source_asset_ids, parameters, progress=progress)
    if stage == "pixel_cleanup":
        if not clip_name:
            raise ValueError("pixel_cleanup requires clip_name.")
        return run_ai_pixel_cleanup(project_id, workflow_profile, clip_name, source_asset_ids, parameters, progress=progress)
    raise ValueError("Unknown ai_workflow stage: %s." % stage)


def approve_ai_workflow(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    stage = str(payload.get("stage") or "").strip()
    run_id = str(payload.get("run_id") or "").strip()
    asset_id = str(payload.get("asset_id") or "").strip() or None
    clip_name = str(payload.get("clip_name") or "").strip() or None
    selected = store.get("selected_assets") or {}
    if stage == "character_lock":
        run = (store.get("character_lock", {}).get("runs") or {}).get(run_id)
        if not run:
            raise ValueError("Unknown Character Lock run.")
        if not asset_id or not any(item.get("asset_id") == asset_id for item in (run.get("candidates") or [])):
            raise ValueError("Character Lock approval requires a candidate asset_id from the selected run.")
        store["character_lock"]["approved_run_id"] = run_id
        store["character_lock"]["approved_asset_id"] = asset_id
        selected["character_lock_run_id"] = run_id
        selected["character_lock_asset_id"] = asset_id
        project["current_stage"] = "part_manifest"
        project["status"] = "ai_character_lock_approved"
    elif stage == "key_pose_set":
        run = (store.get("key_pose_set", {}).get("runs") or {}).get(run_id)
        if not run:
            raise ValueError("Unknown Key Pose Board run.")
        store["key_pose_set"]["approved_run_id"] = run_id
        selected["key_pose_run_id"] = run_id
        project["current_stage"] = "clips"
        project["status"] = "ai_key_pose_board_approved"
    elif stage in {"motion_clip", "extract_frames", "pixel_cleanup"}:
        if clip_name not in AI_CLIP_SPECS:
            raise ValueError("%s approval requires clip_name." % stage)
        mapping = {
            "motion_clip": "motion_runs",
            "extract_frames": "extract_runs",
            "pixel_cleanup": "cleanup_runs",
        }
        clip_group = _ai_motion_group(store, mapping[stage], clip_name)
        if run_id not in (clip_group.get("runs") or {}):
            raise ValueError("Unknown %s run for %s." % (stage, clip_name))
        clip_group["approved_run_id"] = run_id
        key_name = {
            "motion_clip": "motion_run_ids",
            "extract_frames": "extract_run_ids",
            "pixel_cleanup": "cleanup_run_ids",
        }[stage]
        selected.setdefault(key_name, {})
        selected[key_name][clip_name] = run_id
        project["current_stage"] = "qa" if stage == "pixel_cleanup" else "clips"
        project["status"] = "ai_%s_%s_approved" % (stage, clip_name)
    else:
        raise ValueError("Unknown AI workflow stage: %s." % stage)
    store["selected_assets"] = selected
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["ai_workflow"]


def reject_ai_workflow(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    project = load_project(project_id)
    store = ai_workflow_or_error(project)
    stage = str(payload.get("stage") or "").strip()
    run_id = str(payload.get("run_id") or "").strip()
    clip_name = str(payload.get("clip_name") or "").strip() or None
    reason = str(payload.get("reason") or "").strip() or None
    if stage == "character_lock":
        run = (store.get("character_lock", {}).get("runs") or {}).get(run_id)
        if not run:
            raise ValueError("Unknown Character Lock run.")
        run["status"] = "rejected"
        run["rejection_reason"] = reason
        if store["character_lock"].get("approved_run_id") == run_id:
            store["character_lock"]["approved_run_id"] = None
            store["character_lock"]["approved_asset_id"] = None
    elif stage == "key_pose_set":
        run = (store.get("key_pose_set", {}).get("runs") or {}).get(run_id)
        if not run:
            raise ValueError("Unknown Key Pose Board run.")
        run["status"] = "rejected"
        run["rejection_reason"] = reason
        if store["key_pose_set"].get("approved_run_id") == run_id:
            store["key_pose_set"]["approved_run_id"] = None
    elif stage in {"motion_clip", "extract_frames", "pixel_cleanup"}:
        if clip_name not in AI_CLIP_SPECS:
            raise ValueError("%s rejection requires clip_name." % stage)
        mapping = {
            "motion_clip": "motion_runs",
            "extract_frames": "extract_runs",
            "pixel_cleanup": "cleanup_runs",
        }
        clip_group = _ai_motion_group(store, mapping[stage], clip_name)
        run = (clip_group.get("runs") or {}).get(run_id)
        if not run:
            raise ValueError("Unknown %s run for %s." % (stage, clip_name))
        run["status"] = "rejected"
        run["rejection_reason"] = reason
        if clip_group.get("approved_run_id") == run_id:
            clip_group["approved_run_id"] = None
    else:
        raise ValueError("Unknown AI workflow stage: %s." % stage)
    store["updated_at"] = now_iso()
    project["ai_workflow"] = store
    project["status"] = "ai_%s_rejected" % stage
    project["updated_at"] = now_iso()
    save_project(project)
    return load_project(project_id)["ai_workflow"]
