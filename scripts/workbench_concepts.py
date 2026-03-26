from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)

def load_concepts(project_dir: Path) -> List[Dict[str, Any]]:
    concepts = []
    concepts_dir = project_dir / "concepts"
    if not concepts_dir.exists():
        return concepts
    for path in concepts_dir.glob("*.json"):
        payload = load_json(path, None)
        if isinstance(payload, dict):
            concepts.append(payload)
    concepts.sort(key=lambda item: (parse_iso(item.get("created_at")), item.get("concept_id", "")))
    return concepts

def prompt_history_entries(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entries = []
    for concept in concepts:
        if not concept.get("prompt_text"):
            continue
        entries.append({
            "concept_id": concept.get("concept_id"),
            "attempt_group_id": concept.get("attempt_group_id"),
            "attempt_index": concept.get("attempt_index"),
            "prompt_version": concept.get("prompt_version"),
            "prompt_source": concept.get("prompt_source"),
            "prompt_text": concept.get("prompt_text"),
            "prompt_file": concept.get("prompt_file"),
            "created_at": concept.get("created_at"),
            "validation_feedback": concept.get("validation_feedback"),
        })
    entries.sort(key=lambda item: (item.get("prompt_version") or 0, parse_iso(item.get("created_at"))), reverse=True)
    return entries

def hydrate_concept(concept: Dict[str, Any], fallback_created_at: Optional[str] = None) -> Dict[str, Any]:
    record = dict(concept or {})
    record.setdefault("concept_id", "")
    record.setdefault("run_id", record.get("lineage", {}).get("run_id") if isinstance(record.get("lineage"), dict) else "legacy")
    record.setdefault("run_kind", "legacy")
    record.setdefault("created_at", fallback_created_at or now_iso())
    record.setdefault("positive_prompt", record.get("prompt") or "")
    record.setdefault("prompt_text", record.get("prompt") or record.get("positive_prompt") or "")
    record.setdefault("prompt_version", 0)
    record.setdefault("prompt_source", "initial")
    record.setdefault("attempt_group_id", record.get("run_id") or "legacy")
    record.setdefault("attempt_index", 1)
    record.setdefault("import_source", None)
    record.setdefault("validation_status", "valid" if record.get("review_state", {}).get("approved") else "pending")
    record.setdefault("validation_feedback", None)
    validation_source = record.get("validation_source")
    if validation_source == "codex":
        validation_source = "gemini"
    elif validation_source == "codex_overridden":
        validation_source = "gemini_overridden"
    record.setdefault("validation_source", validation_source or "manual")
    record.setdefault("validation_updated_at", record.get("created_at"))
    record.setdefault("validation_error", None)
    record.setdefault("codex_review_summary", None)
    record.setdefault("codex_response_id", None)
    record.setdefault("accepted_for_review", bool(record.get("review_state", {}).get("approved")))
    record.setdefault("prompt_file", None)
    record.setdefault("negative_prompt", DEFAULT_NEGATIVE_PROMPT)
    record.setdefault("preview_image", "")
    record.setdefault("original_preview_image", record.get("preview_image") or "")
    record.setdefault("processed_preview_image", None)
    record.setdefault("postprocess_status", "not_needed")
    record.setdefault("postprocess_notes", None)
    record.setdefault("approved_source_image", record.get("processed_preview_image") or record.get("preview_image") or None)
    record.setdefault("concept_source_mode", "legacy")
    record.setdefault("init_source_image", None)
    record.setdefault("variation_axes", {})
    review_state = record.get("review_state") or {}
    record["review_state"] = {
        "approved": bool(review_state.get("approved", record.get("approved", False))),
        "favorite": bool(review_state.get("favorite", record.get("favorite", False))),
        "rejected": bool(review_state.get("rejected", record.get("rejected", False))),
    }
    record["approved"] = record["review_state"]["approved"]
    record["favorite"] = record["review_state"]["favorite"]
    record["rejected"] = record["review_state"]["rejected"]
    if record["review_state"]["approved"]:
        record["validation_status"] = "valid"
        record["accepted_for_review"] = True
        if not record.get("approved_source_image"):
            record["approved_source_image"] = record.get("processed_preview_image") or record.get("original_preview_image") or record.get("preview_image")
    if "difference_summary" not in record:
        silhouette = record.get("silhouette") or record.get("variation_axes", {}).get("silhouette")
        outfit = record.get("outfit") or record.get("variation_axes", {}).get("outfit_complexity")
        record["difference_summary"] = ", ".join([item for item in [silhouette, outfit] if item]) or "legacy concept"
    record.setdefault("references_used", [])
    record.setdefault("triage", {
        "status": "not_evaluated",
        "flags": [],
        "metrics": {},
    })
    if not record.get("preview_image"):
        record["preview_image"] = (
            record.get("original_preview_image")
            or record.get("processed_preview_image")
            or record.get("approved_source_image")
            or record.get("image_path")
            or ""
        )
    if not record.get("original_preview_image") and record.get("preview_image"):
        record["original_preview_image"] = record["preview_image"]
    if not record.get("approved_source_image"):
        record["approved_source_image"] = record.get("processed_preview_image") or record.get("original_preview_image") or record.get("preview_image")
    return record

def save_concept(project_dir: Path, concept: Dict[str, Any]) -> None:
    path = project_dir / "concepts" / ("%s.json" % concept["concept_id"])
    write_json(path, concept)

def next_concept_serial(concepts: List[Dict[str, Any]]) -> int:
    highest = 0
    for concept in concepts:
        match = re.search(r"(\d+)$", concept.get("concept_id", ""))
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1

def next_prompt_version(concepts: List[Dict[str, Any]]) -> int:
    highest = 0
    for concept in concepts:
        highest = max(highest, int(concept.get("prompt_version") or 0))
    return highest + 1

def save_prompt_artifacts(project_dir: Path, prompt_version: int, prompt_text: str) -> Tuple[str, str]:
    prompts_dir = project_dir / "prompts"
    history_dir = prompts_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    latest_path = prompts_dir / "latest-gemini-prompt.txt"
    history_path = history_dir / ("prompt-v%03d.txt" % prompt_version)
    latest_path.write_text(prompt_text.strip() + "\n", encoding="utf-8")
    history_path.write_text(prompt_text.strip() + "\n", encoding="utf-8")
    return str(latest_path.relative_to(project_dir)), str(history_path.relative_to(project_dir))

def update_concept_validation(project_id: str, concept_id: str, validation_status: str, feedback: Optional[str] = None) -> Dict[str, Any]:
    if validation_status not in {"pending", "valid", "invalid"}:
        raise ValueError("validation_status must be pending, valid, or invalid.")
    project = load_project(project_id)
    concept = next((item for item in project["concepts"] if item["concept_id"] == concept_id), None)
    if concept is None:
        raise ValueError("Concept not found.")
    if not concept.get("preview_image"):
        raise ValueError("Only imported concept attempts can be validated.")
    source = "gemini_overridden" if concept.get("validation_source") == "gemini" else "manual"
    project = apply_validation_state(
        project,
        concept,
        validation_status,
        feedback=feedback,
        summary=concept.get("codex_review_summary"),
        validation_source=source,
        validation_error=None,
        codex_response_id=concept.get("codex_response_id"),
    )
    project["updated_at"] = now_iso()
    save_concept(PROJECTS_ROOT / project_id, concept)
    save_project(project)
    append_history_event(project_id, {
        "type": "concept_validation",
        "concept_id": concept_id,
        "validation_status": validation_status,
        "validation_feedback": concept["validation_feedback"],
        "validation_source": concept["validation_source"],
        "created_at": now_iso(),
    })
    return load_project(project_id)

def update_concept_review_state(project_id: str, concept_id: str, action: str, value: Optional[bool]) -> Dict[str, Any]:
    if action not in {"approve", "favorite", "reject"}:
        raise ValueError("Unsupported review action.")

    project = load_project(project_id)
    concept = next((item for item in project["concepts"] if item["concept_id"] == concept_id), None)
    if concept is None:
        raise ValueError("Concept not found.")

    event_value = True if value is None else bool(value)

    if action == "approve":
        event_value = True
        if concept.get("validation_status") != "valid":
            raise ValueError("Only valid imported concepts can be accepted.")
        if not concept.get("approved_source_image"):
            raise ValueError("Only valid imported concepts with an approved source image can be accepted.")
        reset_downstream_assets(project_id, "concept")
        project = clear_project_downstream_state(project, "concept")
        for item in project["concepts"]:
            item["review_state"]["approved"] = item["concept_id"] == concept_id
            item["approved"] = item["review_state"]["approved"]
            item["accepted_for_review"] = item["concept_id"] == concept_id
            save_concept(PROJECTS_ROOT / project_id, item)
        project["selected_concept_id"] = concept_id
        project["character_spec"] = make_character_spec(project, concept)
        ai_workflow = project.get("ai_workflow") or {}
        if ai_workflow.get("enabled") and not ai_workflow.get("legacy_mode"):
            project["rig_layout"] = None
            project["rig_layout_history"] = default_rig_layout_history(project_id)
            project["rig_layout_approved"] = False
            ai_workflow["selected_assets"] = ai_workflow.get("selected_assets") or {}
            ai_workflow["selected_assets"]["approved_concept_id"] = concept_id
            project["ai_workflow"] = ai_workflow
            if str((project.get("brief") or {}).get("backend_mode") or "") == "pixellab":
                _set_pixellab_east_only_character_source(project, PROJECTS_ROOT / project_id, concept_id, approved=True)
        else:
            rig_layout = resolve_rig_layout(project, concept, rig_profile=project["character_spec"]["rig_profile"], persist=True)
            project["rig_layout"] = rig_layout
            project["rig_layout_history"] = load_json(rig_layout_history_path(PROJECTS_ROOT / project_id), default_rig_layout_history(project_id))
            project["rig_layout_approved"] = False
        project["rig_layout_approved"] = False
        project["current_stage"] = "concepts" if str((project.get("brief") or {}).get("backend_mode") or "") == "pixellab" else "rig_layout"
        project["status"] = "concept_approved"
        project["master_pose_approved"] = False
        project["sprite_model_approved"] = False
        project["layer_review_approved"] = False
        project["rig_review_approved"] = False
        project["qa_report"] = None
        project["last_export"] = None
    else:
        concept["review_state"]["favorite"] = event_value if action == "favorite" else concept["review_state"]["favorite"]
        concept["review_state"]["rejected"] = event_value if action == "reject" else concept["review_state"]["rejected"]
        concept["favorite"] = concept["review_state"]["favorite"]
        concept["rejected"] = concept["review_state"]["rejected"]
        if action == "reject" and project.get("selected_concept_id") == concept_id and event_value:
            reset_downstream_assets(project_id, "concept")
            project = clear_project_downstream_state(project, "concept")
            concept["review_state"]["approved"] = False
            concept["approved"] = False
            project["selected_concept_id"] = None
            project["character_spec"] = None
            project["master_pose_approved"] = False
            project["sprite_model_approved"] = False
            project["layer_review_approved"] = False
            project["rig_review_approved"] = False
            concept["accepted_for_review"] = False
        save_concept(PROJECTS_ROOT / project_id, concept)

    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "review_action",
        "run_id": concept.get("run_id"),
        "concept_id": concept_id,
        "action": action,
        "value": event_value,
    })
    return load_project(project_id)

def _concept_image_rel_paths(concept: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for key in _CONCEPT_ARTIFACT_IMAGE_KEYS:
        rel = concept.get(key)
        if rel and isinstance(rel, str) and rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out

def _delete_concept_disk_artifacts(project_dir: Path, removed: Dict[str, Any], remaining: List[Dict[str, Any]]) -> None:
    still_used: Set[str] = set()
    for c in remaining:
        for rel in _concept_image_rel_paths(c):
            still_used.add(rel)
    for rel in _concept_image_rel_paths(removed):
        if rel in still_used:
            continue
        target = project_dir / rel
        if target.exists() and target.is_file():
            delete_path(target)
    prompt_file = removed.get("prompt_file")
    if prompt_file and isinstance(prompt_file, str):
        if not any((c.get("prompt_file") == prompt_file) for c in remaining):
            pf = project_dir / prompt_file
            if pf.exists() and pf.is_file():
                delete_path(pf)

def delete_concept(project_id: str, concept_id: str) -> Dict[str, Any]:
    project = load_project(project_id)
    concepts = list(project.get("concepts") or [])
    removed = next((c for c in concepts if c.get("concept_id") == concept_id), None)
    if removed is None:
        raise ValueError("Concept not found.")

    project_dir = PROJECTS_ROOT / project_id
    remaining = [c for c in concepts if c.get("concept_id") != concept_id]
    was_selected = project.get("selected_concept_id") == concept_id
    was_approved_look = bool(removed.get("review_state", {}).get("approved"))

    if was_selected or was_approved_look:
        reset_downstream_assets(project_id, "concept")
        project = clear_project_downstream_state(project, "concept")
        project["selected_concept_id"] = None
        project["character_spec"] = None
        delete_path(project_dir / "character_spec.json")
        for item in remaining:
            item.setdefault("review_state", {"approved": False, "favorite": False, "rejected": False})
            item["review_state"]["approved"] = False
            item["review_state"]["favorite"] = item["review_state"].get("favorite") or False
            item["review_state"]["rejected"] = item["review_state"].get("rejected") or False
            item["approved"] = False
            item["accepted_for_review"] = False
        ai_workflow = project.get("ai_workflow") or {}
        if ai_workflow.get("enabled") and not ai_workflow.get("legacy_mode"):
            ai_workflow.setdefault("selected_assets", {})
            ai_workflow["selected_assets"]["approved_concept_id"] = None
        project["ai_workflow"] = ai_workflow
        project["current_stage"] = "concepts"
        project["status"] = "concept_deleted"

    project["concepts"] = remaining
    _delete_concept_disk_artifacts(project_dir, removed, remaining)
    delete_path(project_dir / "concepts" / ("%s.json" % concept_id))

    project["updated_at"] = now_iso()
    save_project(project)
    append_history_event(project_id, {
        "type": "concept_deleted",
        "concept_id": concept_id,
        "was_selected": was_selected,
        "cleared_pipeline": was_selected or was_approved_look,
        "created_at": now_iso(),
    })
    return load_project(project_id)

def selected_concept(project: Dict[str, Any]) -> Dict[str, Any]:
    concept = next((item for item in (project.get("concepts") or []) if item["concept_id"] == project.get("selected_concept_id")), None)
    if concept is None:
        raise ValueError("Concept approval is required before this stage.")
    return concept
