from __future__ import annotations

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
            "counts": dict(semantics_doc.get("summary") or {}),
            "overlay_keys": sorted((semantics_doc.get("overlay_geometry") or {}).keys()),
        },
        "kit": {
            "status": "ready" if kit_doc else "idle",
            "summary": dict(kit_doc.get("summary") or {}),
        },
        "manifest": {
            "status": "ready" if manifest_doc else "idle",
            "generation_metadata": dict(manifest_doc.get("generation_metadata") or {}),
            "validation_flags": list(manifest_doc.get("validation_flags") or []),
        },
        "validation": {
            "blockers": list(((validation_doc.get("findings") or {}).get("blockers") or [])),
            "warnings": list(((validation_doc.get("findings") or {}).get("warnings") or [])),
            "unresolved_surfaces": list(validation_doc.get("unresolved_surfaces") or []),
        },
    }
