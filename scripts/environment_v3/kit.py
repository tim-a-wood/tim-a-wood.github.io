from __future__ import annotations

from collections import Counter
import copy
from typing import Any, Dict, List, Optional


KIT_SCHEMA_VERSION = 2
KIT_CONTRACT_VERSION = "mvp-taxonomy-v1"

CLASS_ORDER = {"structural": 0, "background": 1, "decor": 2}

STRUCTURAL_COMPONENT_TYPES = {
    "backwall_panel",
    "ceiling_band",
    "door_frame",
    "hero_platform_face",
    "hero_platform_top",
    "main_floor_face",
    "main_floor_top",
    "pit_interior",
    "pit_rim",
    "wall_base_trim_left",
    "wall_base_trim_right",
    "wall_module_left",
    "wall_module_right",
}

BACKGROUND_COMPONENT_TYPES = {
    "background_far_plate",
    "midground_side_frame",
}

TAXONOMY = {
    "classes": {
        "structural": {
            "description": "Room-shell and traversal-bearing pieces that define readable play surfaces.",
            "default_readability_impact": "high",
        },
        "background": {
            "description": "Depth and framing pieces that stay subordinate to the playable route.",
            "default_readability_impact": "medium",
        },
        "decor": {
            "description": "Non-blocking accent pieces that support the room without defining it.",
            "default_readability_impact": "low",
        },
    },
    "surfaces": [
        "background",
        "backwall_panel",
        "ceiling",
        "doors",
        "floor",
        "midground",
        "pits",
        "platforms",
        "walls",
    ],
    "zones": [
        "background_cavities",
        "decor_safe_zones",
        "gameplay_exclusion_zones",
        "left_shell",
        "opening_boundaries",
        "platform_faces",
        "platform_tops",
        "right_shell",
        "shell_surfaces",
        "side_shell",
        "top_shell",
    ],
    "anchor_types": [
        "bottom_threshold",
        "corner",
        "door",
        "left_threshold",
        "moving_platform_path_center",
        "platform_center",
        "right_threshold",
        "shell_surface",
        "side_frame",
        "top_threshold",
    ],
}

METADATA_BY_COMPONENT_TYPE = {
    "background_far_plate": {
        "component_class": "background",
        "allowed_surfaces": ["background"],
        "allowed_zones": ["shell_surfaces", "background_cavities", "decor_safe_zones"],
        "anchor_types": ["shell_surface", "corner"],
        "readability_impact": "medium",
    },
    "backwall_panel": {
        "component_class": "structural",
        "allowed_surfaces": ["backwall_panel", "walls"],
        "allowed_zones": ["shell_surfaces", "background_cavities", "decor_safe_zones"],
        "anchor_types": ["shell_surface", "corner"],
        "readability_impact": "medium",
    },
    "midground_side_frame": {
        "component_class": "background",
        "allowed_surfaces": ["midground"],
        "allowed_zones": ["decor_safe_zones", "side_shell"],
        "anchor_types": ["corner", "side_frame"],
        "readability_impact": "medium",
    },
    "ceiling_band": {
        "component_class": "structural",
        "allowed_surfaces": ["ceiling"],
        "allowed_zones": ["shell_surfaces", "top_shell"],
        "anchor_types": ["shell_surface", "corner"],
        "readability_impact": "high",
    },
    "wall_module_left": {
        "component_class": "structural",
        "allowed_surfaces": ["walls"],
        "allowed_zones": ["shell_surfaces", "left_shell"],
        "anchor_types": ["shell_surface", "corner"],
        "readability_impact": "high",
    },
    "wall_module_right": {
        "component_class": "structural",
        "allowed_surfaces": ["walls"],
        "allowed_zones": ["shell_surfaces", "right_shell"],
        "anchor_types": ["shell_surface", "corner"],
        "readability_impact": "high",
    },
    "wall_base_trim_left": {
        "component_class": "structural",
        "allowed_surfaces": ["walls"],
        "allowed_zones": ["shell_surfaces", "left_shell"],
        "anchor_types": ["shell_surface", "corner"],
        "readability_impact": "high",
    },
    "wall_base_trim_right": {
        "component_class": "structural",
        "allowed_surfaces": ["walls"],
        "allowed_zones": ["shell_surfaces", "right_shell"],
        "anchor_types": ["shell_surface", "corner"],
        "readability_impact": "high",
    },
    "main_floor_top": {
        "component_class": "structural",
        "allowed_surfaces": ["floor"],
        "allowed_zones": ["platform_tops", "gameplay_exclusion_zones"],
        "anchor_types": ["platform_center", "corner"],
        "readability_impact": "high",
    },
    "main_floor_face": {
        "component_class": "structural",
        "allowed_surfaces": ["floor"],
        "allowed_zones": ["platform_faces", "gameplay_exclusion_zones"],
        "anchor_types": ["platform_center", "corner"],
        "readability_impact": "high",
    },
    "hero_platform_top": {
        "component_class": "structural",
        "allowed_surfaces": ["platforms"],
        "allowed_zones": ["platform_tops", "gameplay_exclusion_zones"],
        "anchor_types": ["platform_center", "corner"],
        "readability_impact": "high",
    },
    "hero_platform_face": {
        "component_class": "structural",
        "allowed_surfaces": ["platforms"],
        "allowed_zones": ["platform_faces", "gameplay_exclusion_zones"],
        "anchor_types": ["platform_center", "corner"],
        "readability_impact": "high",
    },
    "door_frame": {
        "component_class": "structural",
        "allowed_surfaces": ["doors"],
        "allowed_zones": ["opening_boundaries", "gameplay_exclusion_zones"],
        "anchor_types": ["door", "top_threshold", "bottom_threshold", "left_threshold", "right_threshold"],
        "readability_impact": "high",
    },
    "pit_rim": {
        "component_class": "structural",
        "allowed_surfaces": ["pits"],
        "allowed_zones": ["opening_boundaries", "gameplay_exclusion_zones"],
        "anchor_types": ["shell_surface", "corner"],
        "readability_impact": "high",
    },
    "pit_interior": {
        "component_class": "structural",
        "allowed_surfaces": ["pits"],
        "allowed_zones": ["background_cavities", "gameplay_exclusion_zones"],
        "anchor_types": ["shell_surface"],
        "readability_impact": "medium",
    },
}


def _dedupe(values: List[str]) -> List[str]:
    seen: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.append(text)
    return seen


def _plan_slots(assembly_plan: Optional[Dict[str, Any]], plan: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    slots = list((assembly_plan or {}).get("slots") or plan or [])
    return [slot for slot in slots if isinstance(slot, dict)]


def _component_metadata(component_type: str, slot_group: str, schema_key: str) -> Dict[str, Any]:
    metadata = copy.deepcopy(METADATA_BY_COMPONENT_TYPE.get(component_type) or {})
    component_class = str(metadata.get("component_class") or "")
    if not component_class:
        if component_type in STRUCTURAL_COMPONENT_TYPES:
            component_class = "structural"
        elif component_type in BACKGROUND_COMPONENT_TYPES or slot_group == "background":
            component_class = "background"
        else:
            component_class = "decor"
    allowed_surfaces = list(metadata.get("allowed_surfaces") or [])
    if not allowed_surfaces:
        allowed_surfaces = [schema_key or slot_group or component_type or "decor"]
    allowed_zones = list(metadata.get("allowed_zones") or [])
    if not allowed_zones:
        allowed_zones = [slot_group or "decor_safe_zones"]
    anchor_types = list(metadata.get("anchor_types") or [])
    if not anchor_types:
        anchor_types = ["corner"]
    readability_impact = str(
        metadata.get("readability_impact")
        or ("high" if component_class == "structural" else ("medium" if component_class == "background" else "low"))
    )
    return {
        "component_class": component_class,
        "allowed_surfaces": _dedupe(allowed_surfaces),
        "allowed_zones": _dedupe(allowed_zones),
        "anchor_types": _dedupe(anchor_types),
        "readability_impact": readability_impact,
    }


def _slot_sort_key(slot: Dict[str, Any]) -> tuple:
    component_type = str(slot.get("component_type") or "")
    slot_group = str(slot.get("slot_group") or "")
    schema_key = str(slot.get("schema_key") or "")
    metadata = _component_metadata(component_type, slot_group, schema_key)
    slot_id = str(slot.get("slot_id") or "")
    return (
        CLASS_ORDER.get(metadata["component_class"], len(CLASS_ORDER)),
        component_type,
        slot_group,
        slot_id,
    )


def _semantic_source_summary(semantics_doc: Dict[str, Any]) -> Dict[str, Any]:
    overlay_geometry = semantics_doc.get("overlay_geometry") or {}
    return {
        "schema_version": semantics_doc.get("schema_version"),
        "room_id": semantics_doc.get("room_id"),
        "room_name": semantics_doc.get("room_name"),
        "room_role": semantics_doc.get("room_role"),
        "room_size": copy.deepcopy(semantics_doc.get("room_size") or {}),
        "summary": copy.deepcopy(semantics_doc.get("summary") or {}),
        "source_fields_used": list(semantics_doc.get("source_fields_used") or []),
        "truth_checks": list(semantics_doc.get("truth_checks") or []),
        "overlay_keys": sorted(overlay_geometry.keys()),
    }


def _build_entry(
    index: int,
    slot: Dict[str, Any],
    stylepack_id: Optional[str],
    semantics_doc: Dict[str, Any],
    assembly_plan: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    component_type = str(slot.get("component_type") or "")
    slot_group = str(slot.get("slot_group") or "")
    schema_key = str(slot.get("schema_key") or "")
    metadata = _component_metadata(component_type, slot_group, schema_key)
    semantic_source = _semantic_source_summary(semantics_doc)
    provenance = {
        "source": "assembly_plan+room_semantics",
        "stylepack_id": stylepack_id,
        "assembly_plan_id": (assembly_plan or {}).get("plan_id"),
        "assembly_plan_room_id": (assembly_plan or {}).get("source_room_id"),
        "assembly_plan_generated_at": (assembly_plan or {}).get("generated_at"),
        "plan_slot_id": slot.get("slot_id"),
        "plan_slot_index": index,
        "plan_component_type": component_type,
        "plan_schema_key": schema_key,
        "plan_slot_group": slot_group,
        "plan_template_id": slot.get("source_template_id") or slot.get("biome_component_template_id"),
        "plan_template_component_type": slot.get("source_template_component_type"),
        "semantic_room_id": semantics_doc.get("room_id"),
        "semantic_room_role": semantics_doc.get("room_role"),
        "semantic_source_fields": list(semantics_doc.get("source_fields_used") or []),
        "semantic_truth_checks": list(semantics_doc.get("truth_checks") or []),
    }
    structural_slice = {
        "source_plan_slot_id": slot.get("slot_id"),
        "source_component_type": component_type,
        "source_schema_key": schema_key,
        "source_slot_group": slot_group,
        "source_geometry": copy.deepcopy(slot.get("local_geometry") or {}),
        "semantics_overlay_keys": semantic_source["overlay_keys"],
        "semantics_room_role": semantic_source["room_role"],
        "semantics_summary": copy.deepcopy(semantic_source["summary"]),
    }
    return {
        "component_id": f"kit-{index + 1}",
        "component_type": component_type,
        "component_class": metadata["component_class"],
        "component_family": schema_key or slot_group or component_type,
        "stylepack_id": stylepack_id,
        "dimensions": copy.deepcopy(slot.get("target_dimensions") or {}),
        "anchor_type": metadata["anchor_types"][0] if metadata["anchor_types"] else "corner",
        "anchor_types": list(metadata["anchor_types"]),
        "tiling_mode": str(slot.get("tile_mode") or "stretch"),
        "allowed_surfaces": list(metadata["allowed_surfaces"]),
        "allowed_zones": list(metadata["allowed_zones"]),
        "readability_impact": metadata["readability_impact"],
        "variant_group": component_type,
        "rarity_weight": 1,
        "provenance": provenance,
        "structural_slice": structural_slice,
    }


def validate_environment_kit(doc: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for index, entry in enumerate(doc.get("entries") or []):
        label = str(entry.get("component_id") or f"entry-{index + 1}")
        if str(entry.get("component_class") or "") not in {"structural", "background", "decor"}:
            errors.append(f"{label}:invalid_component_class")
        if not isinstance(entry.get("allowed_surfaces"), list) or not entry.get("allowed_surfaces"):
            errors.append(f"{label}:missing_allowed_surfaces")
        if not isinstance(entry.get("allowed_zones"), list) or not entry.get("allowed_zones"):
            errors.append(f"{label}:missing_allowed_zones")
        if not str(entry.get("component_type") or "").strip():
            errors.append(f"{label}:missing_component_type")
        if not isinstance(entry.get("dimensions"), dict):
            errors.append(f"{label}:invalid_dimensions")
        if not isinstance(entry.get("provenance"), dict):
            errors.append(f"{label}:missing_provenance")
    return errors


def build_environment_kit(
    stylepack_id: Optional[str],
    semantics_doc: Dict[str, Any],
    assembly_plan: Optional[Dict[str, Any]] = None,
    plan: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    semantics_doc = semantics_doc or {}
    slots = _plan_slots(assembly_plan, plan)
    ordered_slots = sorted(slots, key=_slot_sort_key)
    entries = [
        _build_entry(index, slot, stylepack_id, semantics_doc, assembly_plan)
        for index, slot in enumerate(ordered_slots)
    ]
    component_count_by_type = dict(Counter(entry["component_type"] for entry in entries))
    component_count_by_class = {
        class_name: sum(1 for entry in entries if entry["component_class"] == class_name)
        for class_name in ("structural", "background", "decor")
    }
    semantic_source_summary = _semantic_source_summary(semantics_doc)
    allowed_surfaces = _dedupe([surface for entry in entries for surface in entry["allowed_surfaces"]])
    allowed_zones = _dedupe([zone for entry in entries for zone in entry["allowed_zones"]])
    anchor_types = _dedupe([anchor_type for entry in entries for anchor_type in entry["anchor_types"]])
    doc = {
        "schema_version": KIT_SCHEMA_VERSION,
        "kit_contract_version": KIT_CONTRACT_VERSION,
        "stylepack_id": stylepack_id,
        "source": {
            "assembly_plan_id": (assembly_plan or {}).get("plan_id"),
            "assembly_plan_room_id": (assembly_plan or {}).get("source_room_id"),
            "assembly_plan_generated_at": (assembly_plan or {}).get("generated_at"),
            "slot_count": len(ordered_slots),
            "semantic_source": semantic_source_summary,
        },
        "taxonomy": TAXONOMY,
        "entries": entries,
        "component_count_by_type": component_count_by_type,
        "summary": {
            "component_count": len(entries),
            "structural_count": component_count_by_class["structural"],
            "background_count": component_count_by_class["background"],
            "decor_count": component_count_by_class["decor"],
            "anchor_count": len(semantics_doc.get("anchor_positions") or []),
            "surface_count": len(allowed_surfaces),
            "zone_count": len(allowed_zones),
            "anchor_type_count": len(anchor_types),
            "component_count_by_type": component_count_by_type,
            "component_count_by_class": component_count_by_class,
        },
        "validation_errors": [],
    }
    doc["validation_errors"] = validate_environment_kit(doc)
    return doc
