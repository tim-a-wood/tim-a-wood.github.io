from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


def configure(**kwargs: Any) -> None:
    globals().update(kwargs)


def relative_preview_path(project_dir: Path, image_path: Path) -> str:
    return str(image_path.relative_to(project_dir))


def generate_run(
    project_id: str,
    run_kind: str,
    source_concept_id: Optional[str] = None,
    attribute_group: Optional[str] = None,
    target_value: Optional[str] = None,
    strength_label: Optional[str] = None,
    progress: Optional[Any] = None,
) -> Dict[str, Any]:
    project = load_project(project_id)
    project_dir = PROJECTS_ROOT / project_id
    backend_mode = brief_backend_mode(project.get("brief"))
    if backend_mode == "pixellab":
        raise ValueError(
            "Legacy concept generation (similar/refinement) is not used for Pixel Lab projects; use the Pixel Lab concept endpoints."
        )
    backend = get_concept_backend(backend_mode)
    call_progress(progress, 5, "Checking the image generator", "Making sure concept generation is available.")
    health = backend.healthcheck()
    if not health.get("ok"):
        raise ValueError("Concept backend unavailable: %s" % health.get("error", "unknown backend error"))

    if run_kind == "initial":
        variation_axes_list = build_initial_variation_axes(project["brief"])
    else:
        if source_concept_id is None:
            raise ValueError("Refinement and similar runs require a source concept.")
        base_concept = next((item for item in project["concepts"] if item["concept_id"] == source_concept_id), None)
        if base_concept is None:
            raise ValueError("Source concept not found.")
        if run_kind == "similar":
            variation_axes_list = build_refinement_variation_axes(base_concept, "silhouette", base_concept.get("silhouette"), "subtle", "similar")
            strength_label = "subtle"
        else:
            if attribute_group not in MAJOR_REFINEMENT_LOCKS:
                raise ValueError("Refinement must change exactly one supported major attribute group.")
            if not target_value:
                raise ValueError("Refinement target value is required.")
            if strength_label not in REFINEMENT_STRENGTHS:
                raise ValueError("Refinement strength must be one of: %s." % ", ".join(sorted(REFINEMENT_STRENGTHS)))
            variation_axes_list = build_refinement_variation_axes(base_concept, attribute_group, target_value, strength_label, "refinement")

    run_id = "run-%s" % uuid.uuid4().hex[:10]
    concepts = project["concepts"]
    serial = next_concept_serial(concepts)
    request_references = make_reference_inputs(project_dir, project["brief"])
    start_time = time.monotonic()

    if run_kind == "initial":
        base_concept = None
        refine_source = None
        concept_count = INITIAL_CONCEPT_COUNT
    else:
        base_concept = next(item for item in project["concepts"] if item["concept_id"] == source_concept_id)
        refine_source = project_dir / base_concept["preview_image"]
        concept_count = REFINEMENT_CONCEPT_COUNT

    def generate_records_for_attempt(rescue_mode: bool) -> List[Dict[str, Any]]:
        generated_records: List[Dict[str, Any]] = []
        for index, variation_axes in enumerate(variation_axes_list[:concept_count]):
            call_progress(
                progress,
                12 + int((index / max(1, concept_count)) * 72),
                "Generating look %d of %d" % (index + 1, concept_count),
                variation_axes.get("summary"),
            )
            concept_id = "concept-%04d" % (serial + index)
            output_path = project_dir / "concepts" / ("%s.png" % concept_id)
            positive_prompt, negative_prompt = build_prompt_bundle(project["brief"], variation_axes, base_concept, rescue_mode=rescue_mode)
            seed = stable_int(project_id, run_id, concept_id, positive_prompt, "rescue" if rescue_mode else "base", mod=4_294_967_295)
            refine_strength = None
            if run_kind in ("refinement", "similar"):
                refine_strength = REFINEMENT_STRENGTHS[strength_label or "subtle"]
            request = ConceptRequest(
                project_id=project_id,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                width=CONCEPT_CANVAS[0],
                height=CONCEPT_CANVAS[1],
                seed=seed,
                count=1,
                references=request_references,
                mode=run_kind,
                refine_from_image=refine_source,
                refine_strength=refine_strength,
                variation_axes=variation_axes,
                output_path=output_path,
                checkpoint_name=project["brief"].get("comfyui_checkpoint"),
            )
            generated = backend.generate(request)[0]
            concept = {
                "concept_id": concept_id,
                "run_id": run_id,
                "run_kind": run_kind,
                "created_at": now_iso(),
                "seed": seed,
                "positive_prompt": generated.positive_prompt,
                "negative_prompt": generated.negative_prompt,
                "prompt": generated.positive_prompt,
                "preview_image": relative_preview_path(project_dir, generated.image_path),
                "backend_name": generated.backend_name,
                "backend_run_id": generated.backend_run_id,
                "variation_axes": variation_axes,
                "difference_summary": variation_axes.get("summary"),
                "silhouette": variation_axes.get("silhouette") or project["brief"]["silhouette_intent"],
                "outfit": variation_axes.get("outfit_complexity") or project["brief"]["outfit_materials"],
                "palette_direction": variation_axes.get("palette_direction") or project["brief"]["palette_mood"],
                "palette": palette_from_seed(seed, index, project["brief"]["palette_mood"]),
                "prop_variant": variation_axes.get("prop_variant") or project["brief"]["prop"],
                "face_head_shape": project["brief"]["shape_language"],
                "references_used": generated.references_used,
                "review_state": {"approved": False, "favorite": False, "rejected": False},
                "approved": False,
                "favorite": False,
                "rejected": False,
                "lineage": {"run_id": run_id, "parent_concept_id": source_concept_id},
            }
            generated_records.append(concept)
        return generated_records

    generated_records = generate_records_for_attempt(False)
    call_progress(progress, 88, "Reviewing generated looks", "Running lightweight triage and saving concept metadata.")
    annotate_run_triage(project_dir, generated_records)
    triage_summary = summarize_run_triage(generated_records)
    rescue_attempted = False
    quality_gate_failed = False
    usable_count = triage_summary.get("ok", 0) + triage_summary.get("warning", 0)
    if run_kind == "initial" and usable_count < 2:
        rescue_attempted = True
        call_progress(progress, 90, "Board quality too low", "Retrying with stricter single-character framing rules.")
        generated_records = generate_records_for_attempt(True)
        annotate_run_triage(project_dir, generated_records)
        triage_summary = summarize_run_triage(generated_records)
        usable_count = triage_summary.get("ok", 0) + triage_summary.get("warning", 0)
        quality_gate_failed = usable_count < 2

    for concept in generated_records:
        concepts.append(concept)
        save_concept(project_dir, concept)

    summary = {
        "type": "concept_run",
        "run_id": run_id,
        "run_kind": run_kind,
        "status": "quality_failed" if quality_gate_failed else "completed",
        "created_at": now_iso(),
        "completed_at": now_iso(),
        "concept_ids": [item["concept_id"] for item in generated_records],
        "concept_count": len(generated_records),
        "backend_name": generated_records[0]["backend_name"] if generated_records else backend_mode,
        "backend_mode": backend_mode,
        "source_concept_id": source_concept_id,
        "attribute_group": attribute_group,
        "target_value": target_value,
        "refinement_strength_label": strength_label,
        "refinement_strength": REFINEMENT_STRENGTHS.get(strength_label) if strength_label else None,
        "references_used": generated_records[0]["references_used"] if generated_records else [],
        "summary": "Concept board failed quality gate; generated outputs were kept for inspection only." if quality_gate_failed else "%s run with %d concepts" % (run_kind, len(generated_records)),
        "rescue_attempted": rescue_attempted,
        "quality_gate_failed": quality_gate_failed,
        "duration_ms": int((time.monotonic() - start_time) * 1000),
    }
    history = append_history_event(project_id, summary)
    project["history"] = history
    project["concepts"] = concepts
    project["current_stage"] = "concepts" if run_kind == "initial" else "refine"
    project["status"] = "concepts_quality_failed" if quality_gate_failed else ("concepts_generated" if run_kind == "initial" else "concepts_refined")
    project["updated_at"] = now_iso()
    save_project(project)
    call_progress(
        progress,
        100,
        "Looks ready" if not quality_gate_failed else "Board needs attention",
        "The concept board has been updated." if not quality_gate_failed else "No usable concepts passed triage. Adjust the brief or checkpoint, then regenerate.",
    )
    return {
        "run_id": run_id,
        "run_kind": run_kind,
        "concept_ids": [item["concept_id"] for item in generated_records],
        "triage": triage_summary,
        "rescue_attempted": rescue_attempted,
        "quality_gate_failed": quality_gate_failed,
    }
