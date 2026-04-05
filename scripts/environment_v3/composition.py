from __future__ import annotations

import copy
import hashlib
from typing import Any, Dict, List, Optional
from collections import Counter

MANIFEST_SCHEMA_VERSION = 2
COMPOSITION_CONTRACT_VERSION = "mvp-composition-v1"

STRUCTURAL_GROUPS = {"floor", "platforms", "doors", "walls", "ceiling", "pits"}
BACKGROUND_GROUPS = {"background", "midground", "backwall"}
DECOR_GROUPS = {"decor"}

PASS_SEQUENCE = ["structural", "background", "decor"]
GROUP_PRECEDENCE = {
    "ceiling": 0,
    "walls": 1,
    "doors": 2,
    "floor": 3,
    "platforms": 4,
    "pits": 5,
    "background": 6,
    "midground": 7,
    "backwall": 8,
    "decor": 9,
}


def _pass_name_for_slot(slot: Dict[str, Any]) -> str:
    slot_group = str(slot.get("slot_group") or "").strip().lower()
    component_class = str(slot.get("component_class") or "").strip().lower()
    if component_class in PASS_SEQUENCE:
        return component_class
    if slot_group in STRUCTURAL_GROUPS:
        return "structural"
    if slot_group in BACKGROUND_GROUPS:
        return "background"
    if slot_group in DECOR_GROUPS:
        return "decor"
    return "decor"


def _placement_sort_key(slot: Dict[str, Any]) -> tuple:
    placement = slot.get("placement") if isinstance(slot.get("placement"), dict) else {}
    slot_group = str(slot.get("slot_group") or "").strip().lower()
    return (
        PASS_SEQUENCE.index(_pass_name_for_slot(slot)),
        GROUP_PRECEDENCE.get(slot_group, 99),
        int(placement.get("y") or 0),
        int(placement.get("x") or 0),
        str(slot.get("component_type") or ""),
        str(slot.get("slot_id") or ""),
    )


def _plan_fingerprint(plan: List[Dict[str, Any]]) -> str:
    normalized = [
        {
            "slot_id": str(slot.get("slot_id") or ""),
            "component_type": str(slot.get("component_type") or ""),
            "slot_group": str(slot.get("slot_group") or ""),
            "component_class": str(slot.get("component_class") or ""),
            "placement": copy.deepcopy(slot.get("placement") or {}),
            "target_dimensions": copy.deepcopy(slot.get("target_dimensions") or {}),
        }
        for slot in sorted(plan, key=_placement_sort_key)
    ]
    digest = hashlib.sha1(repr(normalized).encode("utf-8")).hexdigest()
    return digest[:12]


def _seed_metadata(seed: Optional[str]) -> Dict[str, str]:
    seed_value = str(seed or "").strip()
    if seed_value:
        return {"seed": seed_value, "seed_source": "provided"}
    return {"seed": "default", "seed_source": "default"}


def _pass_summary(slots: List[Dict[str, Any]]) -> Dict[str, Any]:
    slot_groups: Dict[str, int] = {}
    component_types: Dict[str, int] = {}
    for slot in slots:
        slot_group = str(slot.get("slot_group") or "misc")
        component_type = str(slot.get("component_type") or "unknown")
        slot_groups[slot_group] = slot_groups.get(slot_group, 0) + 1
        component_types[component_type] = component_types.get(component_type, 0) + 1
    return {
        "count": len(slots),
        "slot_groups": slot_groups,
        "component_types": component_types,
    }


def _placement_summary(layers: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    layer_order = list(PASS_SEQUENCE)
    return {
        "total_count": sum(len(layers.get(layer_name) or []) for layer_name in layer_order),
        "layer_order": layer_order,
        "layers": {
            layer_name: {
                "count": len(layers.get(layer_name) or []),
                "slot_ids": [str(item.get("slot_id") or "") for item in (layers.get(layer_name) or [])],
                "component_types": dict(
                    sorted(
                        Counter(str(item.get("component_type") or "") for item in (layers.get(layer_name) or [])).items()
                    )
                ),
                "placements": [
                    _placement_record(item, layer_name, placement_index)
                    for placement_index, item in enumerate(layers.get(layer_name) or [])
                ],
            }
            for layer_name in layer_order
        },
    }


def _placement_record(slot: Dict[str, Any], pass_name: str, placement_index: int) -> Dict[str, Any]:
    return {
        "slot_id": slot.get("slot_id"),
        "component_type": slot.get("component_type"),
        "schema_key": slot.get("schema_key"),
        "slot_group": slot.get("slot_group"),
        "pass_name": pass_name,
        "placement_index": placement_index,
        "placement": copy.deepcopy(slot.get("placement") or {}),
        "target_dimensions": copy.deepcopy(slot.get("target_dimensions") or {}),
        "protected_zones": copy.deepcopy(slot.get("protected_zones") or []),
        "local_geometry": copy.deepcopy(slot.get("local_geometry") or {}),
        "tile_mode": slot.get("tile_mode"),
        "border_treatment": slot.get("border_treatment"),
        "kit_component_id": slot.get("component_id"),
        "source_template_id": slot.get("source_template_id"),
    }


def build_environment_manifest(
    room: Optional[Dict[str, Any]],
    stylepack_id: Optional[str],
    seed: Optional[str],
    plan: Optional[List[Dict[str, Any]]] = None,
    validation_flags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    room_id = str((room or {}).get("id") or "room")
    ordered_slots = sorted(list(plan or []), key=_placement_sort_key)
    layers = {
        "structural": [],
        "background": [],
        "decor": [],
    }
    pass_summaries: Dict[str, Dict[str, Any]] = {}
    for pass_name in PASS_SEQUENCE:
        pass_slots = [slot for slot in ordered_slots if _pass_name_for_slot(slot) == pass_name]
        pass_summaries[pass_name] = _pass_summary(pass_slots)
        for placement_index, slot in enumerate(pass_slots):
            layers[pass_name].append(_placement_record(slot, pass_name, placement_index))
    seed_metadata = _seed_metadata(seed)
    seed_value = seed_metadata["seed"]
    seed_source = seed_metadata["seed_source"]
    plan_fingerprint = _plan_fingerprint(ordered_slots)
    layer_counts = {layer_name: len(items) for layer_name, items in layers.items()}
    placement_summary = _placement_summary(layers)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "contract_version": COMPOSITION_CONTRACT_VERSION,
        "room_id": room_id,
        "stylepack_id": stylepack_id,
        "seed": seed_value,
        "seed_source": seed_source,
        "pass_order": list(PASS_SEQUENCE),
        "layer_order": list(PASS_SEQUENCE),
        "passes": {
            "sequence": [
                {
                    "pass_name": pass_name,
                    "precedence": index,
                    **pass_summaries[pass_name],
                }
                for index, pass_name in enumerate(PASS_SEQUENCE)
            ],
            "summaries": copy.deepcopy(pass_summaries),
        },
        "layers": layers,
        "placement_summary": placement_summary,
        "deterministic_replay": {
            "seed": seed_value,
            "seed_source": seed_source,
            "stylepack_id": stylepack_id,
            "room_id": room_id,
            "plan_fingerprint": plan_fingerprint,
            "layer_order": list(PASS_SEQUENCE),
            "layer_counts": dict(layer_counts),
            "placement_count": placement_summary["total_count"],
            "plan_slot_count": len(ordered_slots),
            "replay_key": f"{room_id}:{stylepack_id or 'stylepack'}:{seed_value}:{plan_fingerprint}",
            "ordering_rule": "pass_precedence_then_group_then_position_then_slot_id",
        },
        "generation_metadata": {
            "seed": seed_value,
            "seed_source": seed_source,
            "pass_order": list(PASS_SEQUENCE),
            "layer_order": list(PASS_SEQUENCE),
            "layer_counts": dict(layer_counts),
            "structural_count": layer_counts["structural"],
            "background_count": layer_counts["background"],
            "decor_count": layer_counts["decor"],
            "placement_count": placement_summary["total_count"],
            "plan_slot_count": len(ordered_slots),
            "plan_fingerprint": plan_fingerprint,
        },
        "validation_flags": list(validation_flags or []),
    }
