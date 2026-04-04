from __future__ import annotations

import copy
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


def merge_reference_pack(
    existing: Optional[Dict[str, Any]],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Shallow merge editor/API updates into the reference pack (proposal-first)."""
    base = copy.deepcopy(existing) if isinstance(existing, dict) else build_reference_pack()
    if not isinstance(payload, dict):
        return base
    if "reference_pack_id" in payload and payload["reference_pack_id"] is not None:
        base["reference_pack_id"] = str(payload["reference_pack_id"]).strip() or base.get("reference_pack_id")
    if "notes" in payload:
        base["notes"] = str(payload.get("notes") or "").strip()
    if "status" in payload and payload["status"] is not None:
        base["status"] = str(payload["status"]).strip() or base.get("status", "idle")
    if "uploads" in payload and isinstance(payload["uploads"], list):
        base["uploads"] = copy.deepcopy(payload["uploads"])
    if "provenance" in payload and isinstance(payload["provenance"], dict):
        base["provenance"] = {**dict(base.get("provenance") or {}), **payload["provenance"]}
    if "canonical_selection" in payload and isinstance(payload["canonical_selection"], list):
        base["canonical_selection"] = [str(x).strip() for x in payload["canonical_selection"] if str(x).strip()]
    uploads = base.get("uploads") if isinstance(base.get("uploads"), list) else []
    canonical = base.get("canonical_selection") if isinstance(base.get("canonical_selection"), list) else []
    base["summary"] = {
        "upload_count": len(uploads),
        "canonical_count": len(canonical),
    }
    return base
