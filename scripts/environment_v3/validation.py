from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_validation_report(
    review_state: Optional[Dict[str, Any]] = None,
    assembly_plan: Optional[Dict[str, Any]] = None,
    manifest: Optional[Dict[str, Any]] = None,
    semantics_doc: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    review_state = review_state or {}
    assembly_plan = assembly_plan or {}
    manifest = manifest or {}
    semantics_doc = semantics_doc or {}
    coverage = assembly_plan.get("planner_coverage_summary") or {}
    blockers = list(coverage.get("blockers") or [])
    warnings: List[str] = []
    runtime_review = review_state.get("runtime_review") or {}
    runtime_status = str(runtime_review.get("status") or "idle")
    if runtime_status in {"idle", "running"}:
        warnings.append("runtime_review_pending")
    elif runtime_status == "fail":
        blockers.append("runtime_review_failed")
    if not (manifest.get("layers") or {}).get("structural"):
        blockers.append("structural_layer_missing")
    if not (semantics_doc.get("opening_boundaries") or []):
        warnings.append("opening_boundaries_missing")
    return {
        "schema_version": 1,
        "geometry_safety": {"status": "pass" if not blockers else "blocked", "findings": blockers},
        "readability": {"status": "pass" if not blockers else "warning", "findings": warnings},
        "system_integrity": {"status": "pass" if not blockers else "warning", "findings": list(dict.fromkeys(blockers + warnings))},
        "visual_consistency": {"status": "pending", "findings": ["visual_validation_required"]},
        "unresolved_surfaces": list(coverage.get("missing_slots") or []),
        "findings": {
            "blockers": list(dict.fromkeys(blockers)),
            "warnings": list(dict.fromkeys(warnings)),
            "info": [],
        },
    }
