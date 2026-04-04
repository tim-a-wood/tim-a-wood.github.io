from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_stylepack(
    stylepack_id: Optional[str] = None,
    summary: Optional[str] = None,
    palette_profile: Optional[Dict[str, Any]] = None,
    material_vocabulary: Optional[List[str]] = None,
    shape_language: Optional[List[str]] = None,
    motif_vocabulary: Optional[List[str]] = None,
    forbidden_drift_traits: Optional[List[str]] = None,
    prompt_pack: Optional[Dict[str, Any]] = None,
    review_checklist: Optional[List[str]] = None,
    locked: bool = False,
    status: str = "proposal",
) -> Dict[str, Any]:
    return {
        "stylepack_id": stylepack_id or "stylepack-draft",
        "status": "locked" if locked else status,
        "locked": bool(locked),
        "summary": str(summary or "").strip(),
        "palette_profile": palette_profile or {},
        "material_vocabulary": list(material_vocabulary or []),
        "shape_language": list(shape_language or []),
        "motif_vocabulary": list(motif_vocabulary or []),
        "value_hierarchy": {},
        "forbidden_drift_traits": list(forbidden_drift_traits or []),
        "component_generation_hints": {},
        "prompt_pack": prompt_pack or {},
        "review_checklist": list(review_checklist or []),
    }


def summarize_stylepack(stylepack_doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "stylepack_id": stylepack_doc.get("stylepack_id"),
        "status": stylepack_doc.get("status"),
        "locked": bool(stylepack_doc.get("locked")),
        "material_count": len(stylepack_doc.get("material_vocabulary") or []),
        "shape_count": len(stylepack_doc.get("shape_language") or []),
        "motif_count": len(stylepack_doc.get("motif_vocabulary") or []),
        "forbidden_trait_count": len(stylepack_doc.get("forbidden_drift_traits") or []),
    }
