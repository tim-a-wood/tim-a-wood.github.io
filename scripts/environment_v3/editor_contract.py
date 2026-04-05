from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from . import stylepack


def build_results_payload(
    env: Dict[str, Any],
    reference_pack_doc: Optional[Dict[str, Any]] = None,
    stylepack_doc: Optional[Dict[str, Any]] = None,
    semantics_doc: Optional[Dict[str, Any]] = None,
    kit_doc: Optional[Dict[str, Any]] = None,
    manifest_doc: Optional[Dict[str, Any]] = None,
    validation_doc: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    reference_pack_doc = reference_pack_doc or {}
    stylepack_doc = stylepack_doc or {}
    semantics_doc = semantics_doc or {}
    kit_doc = kit_doc or {}
    manifest_doc = manifest_doc or {}
    validation_doc = validation_doc or {}
    return {
        "pipeline_version": str(env.get("environment_pipeline_version") or "v2"),
        "reference_pack": {
            "reference_pack_id": reference_pack_doc.get("reference_pack_id"),
            "status": reference_pack_doc.get("status"),
            "upload_count": ((reference_pack_doc.get("summary") or {}).get("upload_count") or 0),
            "canonical_count": ((reference_pack_doc.get("summary") or {}).get("canonical_count") or 0),
        },
        "stylepack": stylepack.summarize_stylepack(stylepack_doc),
        "semantics": {
            "status": "ready" if semantics_doc else "idle",
            "room_id": semantics_doc.get("room_id"),
            "room_name": semantics_doc.get("room_name"),
            "room_role": semantics_doc.get("room_role"),
            "counts": dict(semantics_doc.get("summary") or {}),
            "overlay_geometry": copy.deepcopy(semantics_doc.get("overlay_geometry") or {}),
            "overlay_keys": sorted((semantics_doc.get("overlay_geometry") or {}).keys()),
            "truth_checks": list(semantics_doc.get("truth_checks") or []),
            "source_fields_used": list(semantics_doc.get("source_fields_used") or []),
        },
        "kit": {
            "status": "ready" if kit_doc else "idle",
            "summary": dict(kit_doc.get("summary") or {}),
            "component_count_by_type": dict(kit_doc.get("component_count_by_type") or {}),
            "taxonomy": copy.deepcopy(kit_doc.get("taxonomy") or {}),
            "source": copy.deepcopy(kit_doc.get("source") or {}),
            "validation_errors": list(kit_doc.get("validation_errors") or []),
        },
        "manifest": {
            "status": "ready" if manifest_doc else "idle",
            "room_id": manifest_doc.get("room_id"),
            "stylepack_id": manifest_doc.get("stylepack_id"),
            "seed": manifest_doc.get("seed"),
            "seed_source": manifest_doc.get("seed_source"),
            "pass_order": list(manifest_doc.get("pass_order") or []),
            "layer_order": list(manifest_doc.get("layer_order") or []),
            "passes": copy.deepcopy(manifest_doc.get("passes") or {}),
            "placement_summary": copy.deepcopy(manifest_doc.get("placement_summary") or {}),
            "deterministic_replay": copy.deepcopy(manifest_doc.get("deterministic_replay") or {}),
            "generation_metadata": dict(manifest_doc.get("generation_metadata") or {}),
            "validation_flags": list(manifest_doc.get("validation_flags") or []),
        },
        "validation": {
            "status": "ready" if validation_doc else "idle",
            "blocker_count": int(validation_doc.get("blocker_count") or 0),
            "warning_count": int(validation_doc.get("warning_count") or 0),
            "info_count": int(validation_doc.get("info_count") or 0),
            "findings": copy.deepcopy(((validation_doc.get("findings") or {}).get("all") or [])),
            "blockers": copy.deepcopy(((validation_doc.get("findings") or {}).get("blockers") or [])),
            "warnings": copy.deepcopy(((validation_doc.get("findings") or {}).get("warnings") or [])),
            "info": copy.deepcopy(((validation_doc.get("findings") or {}).get("info") or [])),
            "unresolved_surfaces": list(validation_doc.get("unresolved_surfaces") or []),
            "validation_highlights": copy.deepcopy(validation_doc.get("validation_highlights") or {}),
        },
    }
