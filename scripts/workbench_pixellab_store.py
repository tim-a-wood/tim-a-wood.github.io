from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)

def _pixellab_character_path(project_dir: Path) -> Path:
    return project_dir / "pixellab_character.json"

def _normalize_east_only_character_source(
    project_dir: Path,
    char_data: Optional[Dict[str, Any]],
    concepts: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(char_data, dict) or not char_data.get("east_only_source"):
        return char_data

    current_size = char_data.get("image_size")
    target_size = preferred_concept_canvas_size(current_size)
    if (
        isinstance(current_size, dict)
        and int(current_size.get("width") or 0) == target_size
        and int(current_size.get("height") or 0) == target_size
    ):
        return char_data

    east_rel = ((char_data.get("images") or {}) if isinstance(char_data.get("images"), dict) else {}).get("east")
    east_path = (project_dir / str(east_rel)) if east_rel else (project_dir / "character" / "east.png")

    source_path: Optional[Path] = None
    if concepts and char_data.get("source_concept_id"):
        concept = next((item for item in concepts if item.get("concept_id") == char_data.get("source_concept_id")), None)
        if concept is not None:
            source_rel = (
                concept.get("processed_preview_image")
                or concept.get("original_preview_image")
                or concept.get("preview_image")
                or concept.get("image_path")
            )
            if source_rel:
                candidate = Path(str(source_rel))
                source_path = candidate if candidate.is_absolute() else (project_dir / str(source_rel))
                if not source_path.exists():
                    source_path = None

    if source_path is None and east_path.exists():
        source_path = east_path

    if source_path is None:
        return char_data

    with Image.open(source_path) as loaded:
        source_size = {"width": loaded.size[0], "height": loaded.size[1]}
    target_size = preferred_concept_canvas_size(source_size)
    normalized = prepare_pixellab_character_color_source(source_path, target_size)

    east_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.save(east_path)

    char_data = dict(char_data)
    images = dict(char_data.get("images") or {})
    images["east"] = str(east_path.relative_to(project_dir))
    char_data["images"] = images
    char_data["image_size"] = {"width": target_size, "height": target_size}
    char_data["updated_at"] = now_iso()
    _pixellab_character_path(project_dir).write_text(json.dumps(char_data, indent=2), encoding="utf-8")

    skel_path = _pixellab_skeleton_path(project_dir)
    if skel_path.exists():
        skel_data = load_json(skel_path, None) or {}
        skel_size = skel_data.get("image_size") if isinstance(skel_data, dict) else {}
        if (
            not isinstance(skel_size, dict)
            or int(skel_size.get("width") or 0) != target_size
            or int(skel_size.get("height") or 0) != target_size
        ):
            skel_path.unlink(missing_ok=True)

    return char_data

def _set_pixellab_east_only_character_source(
    project: Dict[str, Any],
    project_dir: Path,
    concept_id: str,
    *,
    approved: bool,
) -> Dict[str, Any]:
    concept = next((item for item in (project.get("concepts") or []) if item.get("concept_id") == concept_id), None)
    if concept is None:
        raise ValueError("Concept not found for east-only character source.")

    source_rel = (
        concept.get("processed_preview_image")
        or concept.get("original_preview_image")
        or concept.get("preview_image")
        or concept.get("image_path")
    )
    if not source_rel:
        raise ValueError("Concept does not have a preview image path.")

    source_path = Path(str(source_rel))
    if not source_path.is_absolute():
        source_path = project_dir / str(source_rel)
    if not source_path.exists():
        raise ValueError("Concept preview image is missing on disk.")

    with Image.open(source_path) as loaded:
        source_size = {"width": loaded.size[0], "height": loaded.size[1]}
    canvas_size = preferred_concept_canvas_size(source_size)
    east_image = prepare_pixellab_character_color_source(source_path, canvas_size)

    assets_dir = _pixellab_character_assets_dir(project_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)
    east_path = assets_dir / "east.png"
    east_image.save(east_path)

    _pixellab_skeleton_path(project_dir).unlink(missing_ok=True)

    char_payload = {
        "character_id": None,
        "approved": bool(approved),
        "pixellab_character_approved": bool(approved),
        "created_at": now_iso(),
        "directions": ["east"],
        "image_size": {"width": canvas_size, "height": canvas_size},
        "source_concept_id": concept_id,
        "backend_name": "approved_concept",
        "seed": None,
        "east_only_source": True,
        "images": {"east": str(east_path.relative_to(project_dir))},
    }
    _pixellab_character_path(project_dir).write_text(json.dumps(char_payload, indent=2), encoding="utf-8")
    project["pixellab_character_ready"] = True
    project["pixellab_character_approved"] = bool(approved)
    project["pixellab_skeleton_ready"] = False
    return char_payload

def _upscale_legacy_east_only_animation_frames(
    project_dir: Path,
    char_data: Optional[Dict[str, Any]],
    store: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if (
        not isinstance(char_data, dict)
        or not char_data.get("east_only_source")
        or not isinstance(store, dict)
        or not isinstance(store.get("animations"), dict)
    ):
        return store

    target_size = preferred_concept_canvas_size(char_data.get("image_size"))
    changed = False
    animations = store.get("animations") or {}
    for anim in animations.values():
        if not isinstance(anim, dict):
            continue
        directions = anim.get("directions")
        if not isinstance(directions, dict):
            continue
        for direction_meta in directions.values():
            if not isinstance(direction_meta, dict):
                continue
            for rel_path in direction_meta.get("frames") or []:
                frame_path = project_dir / str(rel_path)
                if not frame_path.exists():
                    continue
                with Image.open(frame_path) as loaded:
                    if loaded.size == (target_size, target_size):
                        continue
                    width, height = loaded.size
                    if width != height or width >= target_size or width not in SUPPORTED_CANVAS_SIZES:
                        continue
                    upscaled = loaded.resize((target_size, target_size), Image.Resampling.NEAREST)
                upscaled.save(frame_path)
                changed = True

    if changed:
        store = dict(store)
        store["updated_at"] = now_iso()
        _save_pixellab_animations_store(project_dir, store)
    return store

def pixellab_character_wizard_complete(project: Dict[str, Any], project_dir: Path) -> bool:
    """True when Pixel Lab character exists and is approved (project flags and/or JSON)."""
    if bool(project.get("pixellab_character_approved")):
        return True
    char_path = _pixellab_character_path(project_dir)
    if not char_path.exists():
        return False
    char_data = load_json(char_path, None) or {}
    if bool(char_data.get("pixellab_character_approved")):
        return True
    return bool(char_data.get("approved"))

def pixellab_animation_store_has_frames(animations: Any) -> bool:
    if not isinstance(animations, dict):
        return False
    for entry in animations.values():
        if not isinstance(entry, dict):
            continue
        dirs = entry.get("directions")
        if not isinstance(dirs, dict):
            continue
        for data in dirs.values():
            frames = data.get("frames") if isinstance(data, dict) else None
            if isinstance(frames, list) and frames:
                return True
    return False

def pixellab_animations_step_complete(project: Dict[str, Any], project_dir: Path) -> bool:
    """At least one Pixel Lab animation clip has generated frame paths."""
    store = project.get("pixellab_animations")
    if not isinstance(store, dict) or not isinstance(store.get("animations"), dict):
        store = _load_pixellab_animations_store(project_dir)
    anims = store.get("animations") if isinstance(store.get("animations"), dict) else {}
    return pixellab_animation_store_has_frames(anims)

def _pixellab_skeleton_path(project_dir: Path) -> Path:
    return project_dir / "pixellab_skeleton.json"

def _pixellab_character_assets_dir(project_dir: Path) -> Path:
    return project_dir / "character"

def _pixellab_animations_path(project_dir: Path) -> Path:
    return project_dir / "pixellab_animations.json"

def _load_pixellab_animations_store(project_dir: Path) -> Dict[str, Any]:
    path = _pixellab_animations_path(project_dir)
    if not path.exists():
        return {"project_id": project_dir.name, "updated_at": now_iso(), "animations": {}}
    store = load_json(path, None) or {}
    if not isinstance(store, dict):
        store = {}
    store.setdefault("project_id", project_dir.name)
    store.setdefault("animations", {})
    store.setdefault("updated_at", now_iso())
    return store

def _save_pixellab_animations_store(project_dir: Path, store: Dict[str, Any]) -> None:
    path = _pixellab_animations_path(project_dir)
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")

def validate_pixellab_animation_name(raw: Any) -> str:
    """Lowercase slug for Pixel Lab clip keys (idle/walk + user-defined)."""
    s = str(raw or "").strip().lower()
    if not _PIXELLAB_ANIMATION_NAME_RE.fullmatch(s):
        raise ValueError(
            "animation_name must start with a letter, use only a-z, 0-9, underscore, max 48 characters."
        )
    return s

def _infer_animation_name_from_template(template_animation_id: str) -> str:
    s = (template_animation_id or "").lower()
    if any(token in s for token in ["idle", "breathing"]):
        return "idle"
    if any(token in s for token in ["walk", "walking"]):
        return "walk"
    if any(token in s for token in ["run", "running", "slide"]):
        return "run"
    if any(token in s for token in ["jump", "jumping", "flip"]):
        return "jump"
    return "idle"

def _upsert_pixellab_animation_frames(
    project_dir: Path,
    store: Dict[str, Any],
    *,
    animation_name: str,
    direction: str,
    fps: int,
    frame_count: int,
    loop: bool,
    frames_paths: List[str],
    template_animation_id: Optional[str],
    backend_name: str,
    seed: Optional[int],
    job_id: Optional[str] = None,
    edited_description: Optional[str] = None,
) -> Dict[str, Any]:
    store.setdefault("animations", {})
    animations = store["animations"]
    anim = animations.get(animation_name) if isinstance(animations, dict) else None
    if not isinstance(anim, dict):
        anim = {}
    anim.update({
        "animation_name": animation_name,
        "fps": int(fps),
        "frame_count": int(frame_count),
        "loop": bool(loop),
        "backend_name": backend_name,
        "seed": seed,
        "template_animation_id": template_animation_id,
        "updated_at": now_iso(),
    })
    if job_id:
        anim["latest_job_id"] = job_id
    if edited_description:
        anim["latest_edited_description"] = edited_description

    anim.setdefault("directions", {})
    if isinstance(anim["directions"], dict):
        anim["directions"][direction] = {
            "frames": list(frames_paths),
            "frame_count": int(frame_count),
            "fps": int(fps),
            "updated_at": now_iso(),
        }
    animations[animation_name] = anim
    store["updated_at"] = now_iso()
    _save_pixellab_animations_store(project_dir, store)
    return anim
