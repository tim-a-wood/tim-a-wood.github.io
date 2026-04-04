from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


def build_environment_manifest(
    room: Optional[Dict[str, Any]],
    stylepack_id: Optional[str],
    seed: Optional[str],
    plan: Optional[List[Dict[str, Any]]] = None,
    validation_flags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    room_id = str((room or {}).get("id") or "room")
    structural = []
    background = []
    decor = []
    for slot in plan or []:
        slot_group = str(slot.get("slot_group") or "")
        placement = {
            "slot_id": slot.get("slot_id"),
            "component_type": slot.get("component_type"),
            "placement": copy.deepcopy(slot.get("placement") or {}),
            "target_dimensions": copy.deepcopy(slot.get("target_dimensions") or {}),
        }
        if slot_group in {"floor", "platforms", "doors", "walls", "ceiling", "pits"}:
            structural.append(placement)
        elif slot_group == "background":
            background.append(placement)
        else:
            decor.append(placement)
    return {
        "schema_version": 1,
        "room_id": room_id,
        "stylepack_id": stylepack_id,
        "seed": seed or "default",
        "layers": {
            "structural": structural,
            "background": background,
            "decor": decor,
        },
        "generation_metadata": {
            "structural_count": len(structural),
            "background_count": len(background),
            "decor_count": len(decor),
        },
        "validation_flags": list(validation_flags or []),
    }
