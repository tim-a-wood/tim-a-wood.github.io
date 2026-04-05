from __future__ import annotations

import copy
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple


VALIDATION_SCHEMA_VERSION = 2
DIRECT_RUNTIME_FLAG_CODES = {
    "runtime_review_pending",
    "runtime_review_failed",
    "runtime_screenshot_missing",
}


def _finding(severity: str, code: str, message: str, ref: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if ref:
        payload["ref"] = copy.deepcopy(ref)
    return payload


def _status_from_findings(findings: Sequence[Dict[str, Any]], blocker_status: str = "blocked") -> str:
    severities = {str(item.get("severity") or "") for item in findings}
    if "blocker" in severities:
        return blocker_status
    if "warning" in severities:
        return "warning"
    if findings:
        return "pass"
    return "pass"


def _placement_bounds(placement: Dict[str, Any], target_dimensions: Dict[str, Any]) -> Tuple[int, int, int, int]:
    display_width = max(1, int(placement.get("display_width") or target_dimensions.get("width") or 1))
    display_height = max(1, int(placement.get("display_height") or target_dimensions.get("height") or 1))
    origin_x = float(placement.get("origin_x") or 0)
    origin_y = float(placement.get("origin_y") or 0)
    x = int(round(float(placement.get("x") or 0) - (display_width * origin_x)))
    y = int(round(float(placement.get("y") or 0) - (display_height * origin_y)))
    return x, y, display_width, display_height


def _rect_from_bounds(bounds: Tuple[int, int, int, int], **extra: Any) -> Dict[str, Any]:
    x, y, width, height = bounds
    payload: Dict[str, Any] = {
        "x": int(x),
        "y": int(y),
        "width": int(width),
        "height": int(height),
    }
    payload.update(extra)
    return payload


def _rect_intersects(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return not (
        int(a.get("x") or 0) + int(a.get("width") or 0) <= int(b.get("x") or 0)
        or int(b.get("x") or 0) + int(b.get("width") or 0) <= int(a.get("x") or 0)
        or int(a.get("y") or 0) + int(a.get("height") or 0) <= int(b.get("y") or 0)
        or int(b.get("y") or 0) + int(b.get("height") or 0) <= int(a.get("y") or 0)
    )


def _contains_rect(container: Dict[str, Any], rect: Dict[str, Any]) -> bool:
    return (
        int(rect.get("x") or 0) >= int(container.get("x") or 0)
        and int(rect.get("y") or 0) >= int(container.get("y") or 0)
        and int(rect.get("x") or 0) + int(rect.get("width") or 0) <= int(container.get("x") or 0) + int(container.get("width") or 0)
        and int(rect.get("y") or 0) + int(rect.get("height") or 0) <= int(container.get("y") or 0) + int(container.get("height") or 0)
    )


def _room_rect(semantics_doc: Dict[str, Any]) -> Dict[str, Any]:
    size = semantics_doc.get("room_size") if isinstance(semantics_doc.get("room_size"), dict) else {}
    return {"x": 0, "y": 0, "width": int(size.get("width") or 0), "height": int(size.get("height") or 0)}


def _all_layer_items(manifest: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    layers = manifest.get("layers") if isinstance(manifest.get("layers"), dict) else {}
    records: List[Tuple[str, Dict[str, Any]]] = []
    for layer_name in ("structural", "background", "decor"):
        for item in (layers.get(layer_name) or []):
            if isinstance(item, dict):
                records.append((layer_name, item))
    return records


def _dedupe_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for finding in findings:
        key = (
            str(finding.get("severity") or ""),
            str(finding.get("code") or ""),
            repr(finding.get("ref") or {}),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


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

    coverage = assembly_plan.get("planner_coverage_summary") if isinstance(assembly_plan.get("planner_coverage_summary"), dict) else {}
    runtime_review = review_state.get("runtime_review") if isinstance(review_state.get("runtime_review"), dict) else {}
    room_rect = _room_rect(semantics_doc)
    decor_safe_zones = [item for item in (semantics_doc.get("decor_safe_zones") or []) if isinstance(item, dict)]
    gameplay_exclusion_zones = [item for item in (semantics_doc.get("gameplay_exclusion_zones") or []) if isinstance(item, dict)]
    opening_boundaries = [item for item in (semantics_doc.get("opening_boundaries") or []) if isinstance(item, dict)]
    unresolved_surfaces = list(coverage.get("missing_slots") or [])

    geometry_findings: List[Dict[str, Any]] = []
    readability_findings: List[Dict[str, Any]] = []
    system_findings: List[Dict[str, Any]] = []
    visual_findings: List[Dict[str, Any]] = []
    validation_highlights: Dict[str, List[Dict[str, Any]]] = {
        "out_of_bounds": [],
        "opening_obstructions": [],
        "gameplay_intrusions": [],
        "wrong_surface_placements": [],
        "unresolved_surfaces": [{"code": code} for code in unresolved_surfaces],
    }

    for blocker_code in unresolved_surfaces:
        geometry_findings.append(
            _finding(
                "blocker",
                blocker_code,
                "Planner coverage still has unresolved required surfaces.",
                {"artifact": "assembly_plan", "code": blocker_code},
            )
        )

    structural_layer = (manifest.get("layers") or {}).get("structural") or []
    background_layer = (manifest.get("layers") or {}).get("background") or []
    decor_layer = (manifest.get("layers") or {}).get("decor") or []

    if not structural_layer:
        geometry_findings.append(
            _finding(
                "blocker",
                "structural_layer_missing",
                "Structural composition pass produced no placements.",
                {"artifact": "environment_manifest", "layer": "structural"},
            )
        )

    top_count = int(((semantics_doc.get("summary") or {}).get("top_count") or 0))
    structural_top_count = sum(
        1
        for item in structural_layer
        if str(item.get("component_type") or "").endswith("_top")
    )
    if top_count and structural_top_count < top_count:
        readability_findings.append(
            _finding(
                "warning",
                "ledge_clarity_at_risk",
                "Not every traversal top has a structural top placement yet.",
                {
                    "expected_top_surfaces": top_count,
                    "structural_top_placements": structural_top_count,
                },
            )
        )

    if background_layer and len(background_layer) > max(1, len(structural_layer)):
        readability_findings.append(
            _finding(
                "warning",
                "background_dominance_risk",
                "Background composition currently outweighs the structural shell count.",
                {
                    "background_count": len(background_layer),
                    "structural_count": len(structural_layer),
                },
            )
        )

    repeated_types = Counter(str(item.get("component_type") or "") for _, item in _all_layer_items(manifest))
    repeated_types = Counter({component_type: count for component_type, count in repeated_types.items() if component_type and count >= 3})
    if repeated_types:
        readability_findings.append(
            _finding(
                "warning",
                "repetition_suspicion",
                "Several component types repeat enough to warrant a visual repetition check.",
                {"component_types": dict(repeated_types)},
            )
        )

    for layer_name, item in _all_layer_items(manifest):
        placement = item.get("placement") if isinstance(item.get("placement"), dict) else {}
        target_dimensions = item.get("target_dimensions") if isinstance(item.get("target_dimensions"), dict) else {}
        bounds = _placement_bounds(placement, target_dimensions)
        placement_rect = _rect_from_bounds(
            bounds,
            slot_id=str(item.get("slot_id") or ""),
            layer=layer_name,
            component_type=str(item.get("component_type") or ""),
        )

        if room_rect["width"] and room_rect["height"] and not _contains_rect(room_rect, placement_rect):
            geometry_findings.append(
                _finding(
                    "blocker",
                    "placement_out_of_bounds",
                    "A composed placement extends beyond the room bounds.",
                    placement_rect,
                )
            )
            validation_highlights["out_of_bounds"].append(copy.deepcopy(placement_rect))

        if layer_name == "decor":
            in_safe_zone = any(_contains_rect(zone, placement_rect) for zone in decor_safe_zones) if decor_safe_zones else True
            if not in_safe_zone:
                geometry_findings.append(
                    _finding(
                        "blocker",
                        "wrong_surface_placement",
                        "A decor placement falls outside the allowed decor-safe zones.",
                        placement_rect,
                    )
                )
                validation_highlights["wrong_surface_placements"].append(copy.deepcopy(placement_rect))

        blocked_zone = next((zone for zone in gameplay_exclusion_zones if _rect_intersects(placement_rect, zone)), None)
        if blocked_zone and layer_name == "decor":
            geometry_findings.append(
                _finding(
                    "blocker",
                    "gameplay_zone_intrusion",
                    "A decor placement intrudes into a gameplay exclusion zone.",
                    {
                        **placement_rect,
                        "zone_id": blocked_zone.get("zone_id"),
                        "zone_type": blocked_zone.get("zone_type"),
                    },
                )
            )
            validation_highlights["gameplay_intrusions"].append(copy.deepcopy(placement_rect))
            readability_findings.append(
                _finding(
                    "warning",
                    "traversal_space_clutter",
                    "Decor is encroaching on traversal-critical space.",
                    {
                        "slot_id": placement_rect["slot_id"],
                        "zone_id": blocked_zone.get("zone_id"),
                    },
                )
            )

        if str(item.get("component_type") or "") != "door_frame":
            blocked_opening = next((opening for opening in opening_boundaries if _rect_intersects(placement_rect, opening)), None)
            if blocked_opening is not None and layer_name in {"structural", "decor"}:
                geometry_findings.append(
                    _finding(
                        "blocker",
                        "opening_obstruction",
                        "A placement obstructs an opening boundary that should remain readable.",
                        {
                            **placement_rect,
                            "opening": copy.deepcopy(blocked_opening),
                        },
                    )
                )
                validation_highlights["opening_obstructions"].append(copy.deepcopy(placement_rect))

    runtime_status = str(runtime_review.get("status") or "idle")
    screenshot_url = runtime_review.get("screenshot_url")
    if runtime_status in {"idle", "running"}:
        system_findings.append(
            _finding(
                "warning",
                "runtime_review_pending",
                "Runtime review has not completed yet.",
                {"runtime_status": runtime_status},
            )
        )
    elif runtime_status == "fail":
        system_findings.append(
            _finding(
                "blocker",
                "runtime_review_failed",
                "Runtime review reported a failure.",
                {"runtime_status": runtime_status},
            )
        )

    if not screenshot_url:
        system_findings.append(
            _finding(
                "warning",
                "runtime_screenshot_missing",
                "No runtime screenshot is attached to the current review state.",
                {"runtime_status": runtime_status},
            )
        )
        visual_findings.append(
            _finding(
                "info",
                "visual_validation_required",
                "Browser-backed visual validation is still required for final approval.",
                {"review_mode": runtime_review.get("review_mode")},
            )
        )
    else:
        visual_findings.append(
            _finding(
                "info",
                "visual_validation_backed_by_screenshot",
                "A runtime screenshot is available for external visual review.",
                {"screenshot_url": screenshot_url},
            )
        )

    for flag in (manifest.get("validation_flags") or []):
        flag_code = str(flag or "")
        if not flag_code:
            continue
        if flag_code in DIRECT_RUNTIME_FLAG_CODES:
            continue
        severity = "warning"
        message = "Manifest-level validation flag requires review."
        if "failed" in flag_code:
            severity = "blocker"
            message = "Manifest-level validation flag indicates a blocked state."
        elif "drift" in flag_code:
            message = "Manifest carries a style drift flag that needs review."
        system_findings.append(_finding(severity, flag_code, message, {"artifact": "environment_manifest"}))

    geometry_findings = _dedupe_findings(geometry_findings)
    readability_findings = _dedupe_findings(readability_findings)
    system_findings = _dedupe_findings(system_findings)
    visual_findings = _dedupe_findings(visual_findings)

    blockers = [item for item in geometry_findings + readability_findings + system_findings + visual_findings if item["severity"] == "blocker"]
    warnings = [item for item in geometry_findings + readability_findings + system_findings + visual_findings if item["severity"] == "warning"]
    info = [item for item in geometry_findings + readability_findings + system_findings + visual_findings if item["severity"] == "info"]

    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "severity_model": {
            "blocker": "Must be resolved before the environment slice is treated as valid.",
            "warning": "Review needed, but not always a hard stop.",
            "info": "Context only; not a failing condition.",
        },
        "geometry_safety": {
            "status": _status_from_findings(geometry_findings),
            "findings": geometry_findings,
        },
        "readability": {
            "status": _status_from_findings(readability_findings, blocker_status="warning"),
            "findings": readability_findings,
        },
        "system_integrity": {
            "status": _status_from_findings(system_findings),
            "findings": system_findings,
        },
        "visual_consistency": {
            "status": _status_from_findings(visual_findings, blocker_status="warning"),
            "findings": visual_findings,
        },
        "unresolved_surfaces": unresolved_surfaces,
        "validation_highlights": validation_highlights,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "info_count": len(info),
        "findings": {
            "blockers": blockers,
            "warnings": warnings,
            "info": info,
            "all": blockers + warnings + info,
        },
    }
