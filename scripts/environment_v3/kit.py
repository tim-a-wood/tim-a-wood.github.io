from __future__ import annotations

from typing import Any, Dict, List, Optional


STRUCTURAL_SCHEMA_KEYS = {"walls", "floor", "platforms", "doors", "ceiling", "backwall_panel", "pits"}


def build_environment_kit(
    stylepack_id: Optional[str],
    semantics_doc: Dict[str, Any],
    plan: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    for index, slot in enumerate(plan or []):
        schema_key = str(slot.get("schema_key") or "")
        slot_group = str(slot.get("slot_group") or "")
        component_type = str(slot.get("component_type") or "")
        entries.append(
            {
                "component_id": f"kit-{index + 1}",
                "component_type": component_type,
                "component_class": "structural" if schema_key in STRUCTURAL_SCHEMA_KEYS else ("background" if slot_group == "background" else "decor"),
                "stylepack_id": stylepack_id,
                "dimensions": slot.get("target_dimensions") or {},
                "anchor_type": str((slot.get("local_geometry") or {}).get("anchor") or "surface"),
                "tiling_mode": str(slot.get("tile_mode") or "stretch"),
                "allowed_surfaces": [schema_key] if schema_key else [],
                "allowed_zones": [slot_group] if slot_group else [],
                "readability_impact": "high" if schema_key in {"floor", "platforms", "doors", "walls"} else "medium",
                "variant_group": component_type,
                "rarity_weight": 1,
                "provenance": {"source": "deterministic-plan"},
            }
        )
    return {
        "schema_version": 1,
        "stylepack_id": stylepack_id,
        "entries": entries,
        "summary": {
            "component_count": len(entries),
            "structural_count": sum(1 for item in entries if item["component_class"] == "structural"),
            "background_count": sum(1 for item in entries if item["component_class"] == "background"),
            "decor_count": sum(1 for item in entries if item["component_class"] == "decor"),
            "anchor_count": len(semantics_doc.get("anchor_positions") or []),
        },
    }
