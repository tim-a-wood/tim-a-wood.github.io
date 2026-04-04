from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_reference_pack(
    reference_pack_id: Optional[str] = None,
    uploads: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
    canonical_selection: Optional[List[str]] = None,
    status: str = "idle",
) -> Dict[str, Any]:
    uploads = list(uploads or [])
    canonical_selection = list(canonical_selection or [])
    return {
        "reference_pack_id": reference_pack_id or "reference-pack-draft",
        "status": status,
        "notes": str(notes or "").strip(),
        "uploads": uploads,
        "provenance": provenance or {"source_mode": "uploads-first", "project_art_direction_fallback": True},
        "canonical_selection": canonical_selection,
        "supported_file_types": ["image/png", "image/jpeg", "image/webp"],
        "summary": {
            "upload_count": len(uploads),
            "canonical_count": len(canonical_selection),
        },
    }
