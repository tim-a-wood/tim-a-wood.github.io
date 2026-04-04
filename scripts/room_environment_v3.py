from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


V2_PIPELINE_VERSION = "v2"
V3_PIPELINE_VERSION = "v3"

FIRST_SLICE_COMPONENT_TYPES: List[str] = [
    "walls",
    "floor",
    "platforms",
    "doors",
    "background",
    "midground",
    "ceiling",
    "backwall_panel",
]

TEMPLATE_COMPONENT_BY_SLOT: Dict[str, str] = {
    "background_far_plate": "background_plate",
    "backwall_panel": "background_plate",
    "midground_side_frame": "midground_frame",
    "wall_module_left": "wall_piece",
    "wall_module_right": "wall_piece",
    "wall_base_trim_left": "wall_piece",
    "wall_base_trim_right": "wall_piece",
    "ceiling_band": "ceiling_piece",
    "main_floor_top": "primary_floor_piece",
    "main_floor_face": "primary_floor_piece",
    "hero_platform_top": "hero_platform_piece",
    "hero_platform_face": "hero_platform_piece",
    "door_frame": "door_piece",
    "pit_rim": "primary_floor_piece",
    "pit_interior": "background_plate",
}


def normalize_pipeline_version(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text == V3_PIPELINE_VERSION:
        return V3_PIPELINE_VERSION
    return V2_PIPELINE_VERSION


def _room_dimensions(room: Optional[Dict[str, Any]]) -> Dict[str, int]:
    size = (room or {}).get("size") or {}
    return {
        "width": int(size.get("width") or 0),
        "height": int(size.get("height") or 0),
    }


def infer_room_role(room: Optional[Dict[str, Any]]) -> str:
    room = room or {}
    dims = _room_dimensions(room)
    width = int(dims.get("width") or 0)
    height = int(dims.get("height") or 0)
    door_count = len(room.get("doors") or [])
    if door_count >= 3:
        return "hub"
    if height and width and height > width * 1.35:
        return "traversal_shaft"
    if door_count >= 2:
        return "corridor_transition"
    return "threshold"


def default_room_intent(room: Optional[Dict[str, Any]] = None, spec: Optional[Dict[str, Any]] = None, biome_id: Optional[str] = None) -> Dict[str, Any]:
    spec = spec or {}
    return {
        "selected_biome_id": biome_id,
        "room_role": infer_room_role(room),
        "progression_context": {
            "world_region": None,
            "progression_beat": None,
            "safety_level": "unknown",
            "return_visit_expectation": "unknown",
            "ability_gate_context": None,
        },
        "mood": str(spec.get("mood") or "").strip(),
        "lighting": str(spec.get("lighting") or "").strip(),
        "fog": str(spec.get("fog") or "").strip(),
        "landmarks": list(spec.get("landmarks") or []),
        "hazards": list(spec.get("hazards") or []),
        "readability_notes": list(spec.get("readability_notes") or []),
    }


def _contract_defaults(component_type: str) -> Dict[str, Any]:
    readability_defaults = {
        "walls": "must read as enclosure architecture",
        "floor": "must read as an immediate gameplay surface",
        "platforms": "must read as a jumpable traversal surface",
        "doors": "must read as a threshold with a clear opening",
        "background": "must provide shell depth without becoming the room shell by itself",
        "midground": "must frame from the sides without occluding the center traversal lane",
        "ceiling": "must help close the shell silhouette without dominating the room",
        "backwall_panel": "must support interior shell depth behind gameplay surfaces",
    }
    return {
        "component_type": component_type,
        "readability_goal": readability_defaults.get(component_type, "must fit its assigned component type"),
        "shape_rules": [],
        "fit_rules": [],
        "value_rules": [],
        "motif_rules": [],
        "validation_rules": {
            "requires_component_fit": True,
            "proposal_first": True,
        },
    }


def default_component_contracts(spec: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    spec = spec or {}
    schemas = spec.get("component_schemas") or {}
    contracts: Dict[str, Dict[str, Any]] = {}
    for component_type in FIRST_SLICE_COMPONENT_TYPES:
        schema = schemas.get(component_type) or {}
        contract = _contract_defaults(component_type)
        contract["shape_rules"] = list(schema.get("silhouette_rules") or [])
        contract["fit_rules"] = list(schema.get("readability_constraints") or [])
        value_contrast = str(schema.get("value_contrast") or "").strip()
        if value_contrast:
            contract["value_rules"] = [value_contrast]
        contract["motif_rules"] = list(schema.get("negative_constraints") or [])
        contracts[component_type] = contract
    return contracts


def default_assembly_plan(room: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    room = room or {}
    dimensions = _room_dimensions(room)
    return {
        "plan_id": None,
        "source_room_id": room.get("id"),
        "generated_at": None,
        "slots": [],
        "overlay_geometry": {
            "room_polygon": copy.deepcopy(room.get("polygon") or []),
            "doors": copy.deepcopy(room.get("doors") or []),
            "platforms": copy.deepcopy(room.get("platforms") or []),
            "size": dimensions,
        },
        "planner_coverage_summary": {
            "status": "idle",
            "major_structures": {
                "door_count": len(room.get("doors") or []),
                "platform_count": len(room.get("platforms") or []),
            },
            "missing_slots": [],
            "blockers": [],
        },
    }


def default_review_state() -> Dict[str, Any]:
    return {
        "automated_validation": {
            "status": "idle",
            "valid": False,
            "errors": [],
            "component_statuses": {},
        },
        "runtime_review": {
            "status": "idle",
            "fail_reasons": [],
            "warning_reasons": [],
            "metrics": {},
            "screenshot_url": None,
            "review_mode": None,
        },
        "approval_status": "draft",
        "validation_status": {
            "status": "pending",
            "issues": ["runtime_review_pending"],
        },
    }


def ensure_v3_metadata(env: Dict[str, Any], room: Optional[Dict[str, Any]] = None, biome_id: Optional[str] = None) -> Dict[str, Any]:
    env["environment_pipeline_version"] = V3_PIPELINE_VERSION
    room_intent = env.get("room_intent")
    if not isinstance(room_intent, dict):
        room_intent = default_room_intent(room, env.get("spec"), biome_id)
        env["room_intent"] = room_intent
    component_contracts = env.get("component_contracts")
    if not isinstance(component_contracts, dict):
        component_contracts = default_component_contracts(env.get("spec"))
        env["component_contracts"] = component_contracts
    assembly_plan = env.get("assembly_plan")
    if not isinstance(assembly_plan, dict):
        assembly_plan = default_assembly_plan(room)
        env["assembly_plan"] = assembly_plan
    review_state = env.get("review_state")
    if not isinstance(review_state, dict):
        review_state = default_review_state()
        env["review_state"] = review_state
    review_state.setdefault("validation_status", {"status": "pending", "issues": []})
    return env


def sync_v3_metadata(
    env: Dict[str, Any],
    room: Optional[Dict[str, Any]] = None,
    biome_id: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_v3_metadata(env, room, biome_id)
    env["room_intent"] = default_room_intent(room, env.get("spec"), biome_id)
    env["component_contracts"] = default_component_contracts(env.get("spec"))
    assembly_plan = env.get("assembly_plan") or default_assembly_plan(room)
    assembly_plan["source_room_id"] = (room or {}).get("id")
    if generated_at is not None:
        assembly_plan["generated_at"] = generated_at
    env["assembly_plan"] = assembly_plan
    review_state = env.get("review_state") or default_review_state()
    review_state["automated_validation"] = copy.deepcopy(
        ((env.get("runtime") or {}).get("bespoke_asset_manifest") or {}).get("schema_validation")
        or review_state.get("automated_validation")
        or default_review_state()["automated_validation"]
    )
    runtime_review = (
        ((env.get("runtime") or {}).get("bespoke_asset_manifest") or {}).get("runtime_review")
        or review_state.get("runtime_review")
        or default_review_state()["runtime_review"]
    )
    review_state["runtime_review"] = {
        "status": str(runtime_review.get("status") or "idle"),
        "fail_reasons": list(runtime_review.get("fail_reasons") or []),
        "warning_reasons": list(runtime_review.get("warning_reasons") or []),
        "metrics": copy.deepcopy(runtime_review.get("metrics") or {}),
        "screenshot_url": runtime_review.get("screenshot_url"),
        "review_mode": runtime_review.get("review_mode"),
    }
    review_state["validation_status"] = _validation_status(review_state)
    review_state["approval_status"] = _approval_status(review_state)
    env["review_state"] = review_state
    return env


def build_generation_plan(room: Dict[str, Any], preview_id: str, biome_pack: Dict[str, Any], generated_at: str) -> Dict[str, Any]:
    template_library = {
        str(item.get("component_type") or "").strip(): copy.deepcopy(item)
        for item in (biome_pack.get("template_library") or [])
        if isinstance(item, dict) and str(item.get("component_type") or "").strip()
    }
    room_id = str(room.get("id") or "room")
    size = _room_dimensions(room)
    width = max(1, int(size.get("width") or 1600))
    height = max(1, int(size.get("height") or 1200))
    platforms = _platform_records(room)
    primary_floor = _select_primary_floor(platforms, width)
    hero_platforms = [item for item in platforms if primary_floor is None or item["platform_id"] != primary_floor["platform_id"]]
    room_role = infer_room_role(room)
    doors = _door_records(room, width, height)
    pits = _pit_records(room, width, height)
    center_lane = {"type": "center_lane", "x": int(width * 0.26), "y": 0, "width": int(width * 0.48), "height": height}
    plan: List[Dict[str, Any]] = []

    def append_slot(
        slot_id: str,
        component_type: str,
        schema_key: str,
        target_dimensions: Dict[str, int],
        placement: Dict[str, Any],
        orientation: str,
        tile_mode: str,
        slot_group: str,
        protected_zones: List[Dict[str, Any]],
        local_geometry: Dict[str, Any],
        border_treatment: str = "standard",
    ) -> None:
        template_component = TEMPLATE_COMPONENT_BY_SLOT.get(component_type)
        template = template_library.get(template_component or "")
        if not template:
            return
        plan.append({
            "slot_id": slot_id,
            "component_type": component_type,
            "schema_key": schema_key,
            "source_template_id": template.get("template_id"),
            "biome_component_template_id": template.get("template_id"),
            "source_template_component_type": template_component,
            "target_dimensions": copy.deepcopy(target_dimensions),
            "placement": copy.deepcopy(placement),
            "orientation": orientation,
            "tile_mode": tile_mode,
            "border_treatment": border_treatment,
            "slot_group": slot_group,
            "protected_zones": copy.deepcopy(protected_zones),
            "local_geometry": copy.deepcopy(local_geometry),
        })

    append_slot(
        f"{room_id}-background",
        "background_far_plate",
        "background",
        {"width": width, "height": height},
        {"x": int(width / 2), "y": height, "display_width": width, "display_height": height, "origin_x": 0.5, "origin_y": 1},
        "full",
        "stretch",
        "background",
        [center_lane],
        {"room_width": width, "room_height": height},
        border_treatment="full_frame",
    )
    for index, panel in enumerate(_backwall_panel_records(width, height, room_role)):
        append_slot(
            f"{room_id}-backwall-panel-{index + 1}",
            "backwall_panel",
            "backwall_panel",
            {"width": panel["width"], "height": panel["height"]},
            {"x": panel["x"], "y": panel["y"], "display_width": panel["width"], "display_height": panel["height"], "origin_x": 0.5, "origin_y": 0},
            "full",
            "stretch",
            "background",
            [center_lane],
            {"room_width": width, "room_height": height, "panel_index": index},
            border_treatment="inner_shell",
        )
    append_slot(
        f"{room_id}-midground",
        "midground_side_frame",
        "midground",
        {"width": width, "height": height},
        {"x": int(width / 2), "y": height, "display_width": width, "display_height": height, "origin_x": 0.5, "origin_y": 1},
        "full",
        "stretch",
        "midground",
        [{"type": "main_route", "x": int(width * 0.3), "y": 0, "width": int(width * 0.4), "height": height}],
        {"room_width": width, "room_height": height},
        border_treatment="side_only",
    )
    append_slot(
        f"{room_id}-ceiling",
        "ceiling_band",
        "ceiling",
        {"width": width, "height": max(128, int(height * 0.18))},
        {"x": int(width / 2), "y": 0, "display_width": width, "display_height": max(128, int(height * 0.18)), "origin_x": 0.5, "origin_y": 0},
        "horizontal",
        "stretch",
        "ceiling",
        [center_lane],
        {"room_width": width, "room_height": height},
        border_treatment="ceiling_cap",
    )
    wall_module_width = max(224, min(384, int(width * 0.18)))
    append_slot(
        f"{room_id}-wall-module-left",
        "wall_module_left",
        "walls",
        {"width": wall_module_width, "height": max(320, height - 180)},
        {"x": 0, "y": 0, "display_width": wall_module_width, "display_height": max(320, height - 180), "origin_x": 0, "origin_y": 0},
        "vertical",
        "stretch",
        "walls",
        [center_lane],
        {"side": "left", "room_width": width, "room_height": height},
        border_treatment="dark_outer_edge",
    )
    append_slot(
        f"{room_id}-wall-module-right",
        "wall_module_right",
        "walls",
        {"width": wall_module_width, "height": max(320, height - 180)},
        {"x": max(0, width - wall_module_width), "y": 0, "display_width": wall_module_width, "display_height": max(320, height - 180), "origin_x": 0, "origin_y": 0},
        "vertical",
        "stretch",
        "walls",
        [center_lane],
        {"side": "right", "room_width": width, "room_height": height},
        border_treatment="dark_outer_edge",
    )
    append_slot(
        f"{room_id}-wall-base-left",
        "wall_base_trim_left",
        "walls",
        {"width": 256, "height": 160},
        {"x": 0, "y": max(0, height - 220), "display_width": 256, "display_height": 160, "origin_x": 0, "origin_y": 0},
        "horizontal",
        "stretch",
        "walls",
        [{"type": "floor_lane", "x": int(width * 0.18), "y": int(height * 0.7), "width": int(width * 0.64), "height": int(height * 0.3)}],
        {"side": "left", "room_width": width, "room_height": height},
        border_treatment="base_trim",
    )
    append_slot(
        f"{room_id}-wall-base-right",
        "wall_base_trim_right",
        "walls",
        {"width": 256, "height": 160},
        {"x": max(0, width - 256), "y": max(0, height - 220), "display_width": 256, "display_height": 160, "origin_x": 0, "origin_y": 0},
        "horizontal",
        "stretch",
        "walls",
        [{"type": "floor_lane", "x": int(width * 0.18), "y": int(height * 0.7), "width": int(width * 0.64), "height": int(height * 0.3)}],
        {"side": "right", "room_width": width, "room_height": height},
        border_treatment="base_trim",
    )

    if primary_floor is not None:
        append_slot(
            f"{room_id}-main-floor-top",
            "main_floor_top",
            "floor",
            {"width": primary_floor["width"], "height": 96},
            {"x": primary_floor["x"], "y": primary_floor["y"], "display_width": primary_floor["width"], "display_height": 96, "origin_x": 0, "origin_y": 0.75},
            "horizontal",
            "tile_x",
            "floor",
            [{"type": "platform_top", "x": primary_floor["x"], "y": primary_floor["y"] - 18, "width": primary_floor["width"], "height": 22}],
            primary_floor,
            border_treatment="top_lip_priority",
        )
        append_slot(
            f"{room_id}-main-floor-face",
            "main_floor_face",
            "floor",
            {"width": primary_floor["width"], "height": max(48, int(primary_floor["height"] * 0.65))},
            {"x": primary_floor["x"], "y": primary_floor["y"] + 12, "display_width": primary_floor["width"], "display_height": max(48, int(primary_floor["height"] * 0.65)), "origin_x": 0, "origin_y": 0},
            "horizontal",
            "tile_x",
            "floor",
            [{"type": "platform_top", "x": primary_floor["x"], "y": primary_floor["y"] - 18, "width": primary_floor["width"], "height": 22}],
            primary_floor,
            border_treatment="face_plane_separation",
        )

    for index, platform in enumerate(hero_platforms):
        append_slot(
            f"{room_id}-hero-platform-top-{index + 1}",
            "hero_platform_top",
            "platforms",
            {"width": platform["width"], "height": 72},
            {"x": platform["x"], "y": platform["y"], "display_width": platform["width"], "display_height": 72, "origin_x": 0, "origin_y": 0.68},
            "horizontal",
            "tile_x",
            "platforms",
            [{"type": "platform_top", "x": platform["x"], "y": platform["y"] - 16, "width": platform["width"], "height": 20}],
            platform,
            border_treatment="top_lip_priority",
        )
        append_slot(
            f"{room_id}-hero-platform-face-{index + 1}",
            "hero_platform_face",
            "platforms",
            {"width": platform["width"], "height": max(40, int(platform["height"] * 0.6))},
            {"x": platform["x"], "y": platform["y"] + 8, "display_width": platform["width"], "display_height": max(40, int(platform["height"] * 0.6)), "origin_x": 0, "origin_y": 0},
            "horizontal",
            "tile_x",
            "platforms",
            [{"type": "platform_top", "x": platform["x"], "y": platform["y"] - 16, "width": platform["width"], "height": 20}],
            platform,
            border_treatment="face_plane_separation",
        )

    for index, door in enumerate(doors):
        door_slot = _door_slot_record(door, width, height)
        append_slot(
            f"{room_id}-door-{index + 1}",
            "door_frame",
            "doors",
            {"width": door_slot["target_width"], "height": door_slot["target_height"]},
            {"x": door_slot["x"], "y": door_slot["y"], "display_width": door_slot["display_width"], "display_height": door_slot["display_height"], "origin_x": door_slot["origin_x"], "origin_y": door_slot["origin_y"]},
            door_slot["orientation"],
            "stretch",
            "doors",
            [door_slot["protected_zone"]],
            {**door, "anchor": door.get("anchor")},
            border_treatment=door_slot["border_treatment"],
        )

    for index, pit in enumerate(pits):
        append_slot(
            f"{room_id}-pit-rim-{index + 1}",
            "pit_rim",
            "pits",
            {"width": pit["width"], "height": 96},
            {"x": pit["x"], "y": pit["y"], "display_width": pit["width"], "display_height": 96, "origin_x": 0, "origin_y": 0},
            "horizontal",
            "tile_x",
            "pits",
            [{"type": "pit_opening", "x": pit["x"], "y": pit["y"], "width": pit["width"], "height": pit["height"]}],
            pit,
            border_treatment="hazard_rim",
        )
        append_slot(
            f"{room_id}-pit-interior-{index + 1}",
            "pit_interior",
            "pits",
            {"width": pit["width"], "height": pit["height"]},
            {"x": pit["x"], "y": pit["y"] + 40, "display_width": pit["width"], "display_height": pit["height"], "origin_x": 0, "origin_y": 0},
            "vertical",
            "stretch",
            "pits",
            [{"type": "pit_opening", "x": pit["x"], "y": pit["y"], "width": pit["width"], "height": pit["height"]}],
            pit,
            border_treatment="void_drop",
        )

    overlay_slots = [
        {
            "slot_id": str(item.get("slot_id") or ""),
            "component_type": str(item.get("component_type") or ""),
            "schema_key": str(item.get("schema_key") or ""),
            "placement": copy.deepcopy(item.get("placement") or {}),
            "protected_zones": copy.deepcopy(item.get("protected_zones") or []),
            "slot_group": str(item.get("slot_group") or ""),
        }
        for item in plan
    ]
    assembly_plan = {
        "plan_id": f"{room_id}-plan-{preview_id}",
        "source_room_id": room_id,
        "generated_at": generated_at,
        "slots": copy.deepcopy(plan),
        "overlay_geometry": {
            "room_polygon": copy.deepcopy(room.get("polygon") or []),
            "doors": copy.deepcopy(doors),
            "platforms": copy.deepcopy(platforms),
            "pits": copy.deepcopy(pits),
            "size": {"width": width, "height": height},
            "slot_overlays": overlay_slots,
        },
        "planner_coverage_summary": _planner_coverage_summary(room, plan),
    }
    return {
        "plan": plan,
        "assembly_plan": assembly_plan,
    }


def _platform_records(room: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in (room.get("platforms") or []):
        if not isinstance(item, dict):
            continue
        length = max(1, int(item.get("len") or 1))
        records.append({
            "platform_id": str(item.get("id") or f"platform-{len(records) + 1}"),
            "x": int(item.get("x") or 0),
            "y": int(item.get("y") or 0),
            "width": length * 32,
            "height": max(64, min(160, int(length * 3))),
            "len": length,
        })
    return sorted(records, key=lambda item: (item["y"], -item["width"], item["x"]))


def _select_primary_floor(platforms: List[Dict[str, Any]], room_width: int) -> Optional[Dict[str, Any]]:
    if not platforms:
        return None
    floor_candidates = sorted(platforms, key=lambda item: (-item["y"], -item["width"], item["x"]))
    wide = next((item for item in floor_candidates if item["width"] >= int(room_width * 0.55)), None)
    return wide or floor_candidates[0]


def _door_records(room: Dict[str, Any], width: int, height: int) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in (room.get("doors") or []):
        if not isinstance(item, dict):
            continue
        x = int(item.get("x") or 0)
        y = int(item.get("y") or 0)
        anchor = "bottom_threshold"
        if y <= max(160, int(height * 0.18)):
            anchor = "top_threshold"
        elif x <= max(160, int(width * 0.18)):
            anchor = "left_threshold"
        elif x >= min(width - 160, int(width * 0.82)):
            anchor = "right_threshold"
        records.append({
            "door_id": str(item.get("id") or f"door-{len(records) + 1}"),
            "x": x,
            "y": y,
            "kind": str(item.get("kind") or "transition"),
            "anchor": anchor,
        })
    return records


def _door_slot_record(door: Dict[str, Any], room_width: int, room_height: int) -> Dict[str, Any]:
    anchor = str(door.get("anchor") or "bottom_threshold")
    x = int(door.get("x") or 0)
    y = int(door.get("y") or 0)
    if anchor == "top_threshold":
        return {
            "target_width": 288,
            "target_height": 192,
            "display_width": 144,
            "display_height": 96,
            "x": x,
            "y": max(0, y),
            "origin_x": 0.5,
            "origin_y": 0,
            "orientation": "horizontal",
            "border_treatment": "threshold_clearance_top",
            "protected_zone": {"type": "door_mouth", "x": x - 72, "y": y, "width": 144, "height": 112},
        }
    if anchor == "left_threshold":
        return {
            "target_width": 192,
            "target_height": 288,
            "display_width": 96,
            "display_height": 144,
            "x": max(0, x),
            "y": y,
            "origin_x": 0,
            "origin_y": 1,
            "orientation": "vertical",
            "border_treatment": "threshold_clearance_side",
            "protected_zone": {"type": "door_mouth", "x": x, "y": y - 144, "width": 112, "height": 160},
        }
    if anchor == "right_threshold":
        return {
            "target_width": 192,
            "target_height": 288,
            "display_width": 96,
            "display_height": 144,
            "x": min(room_width, x),
            "y": y,
            "origin_x": 1,
            "origin_y": 1,
            "orientation": "vertical",
            "border_treatment": "threshold_clearance_side",
            "protected_zone": {"type": "door_mouth", "x": x - 112, "y": y - 144, "width": 112, "height": 160},
        }
    return {
        "target_width": 192,
        "target_height": 288,
        "display_width": 96,
        "display_height": 144,
        "x": x,
        "y": y,
        "origin_x": 0.5,
        "origin_y": 1,
        "orientation": "vertical",
        "border_treatment": "threshold_clearance",
        "protected_zone": {"type": "door_mouth", "x": x - 48, "y": y - 144, "width": 96, "height": 160},
    }


def _backwall_panel_records(width: int, height: int, room_role: str) -> List[Dict[str, int]]:
    panel_count = 1
    if width >= 2400:
        panel_count = 3
    elif width >= 1800 or room_role == "corridor_transition":
        panel_count = 2
    panel_width = max(320, int((width * 0.72) / panel_count))
    panel_height = max(240, int(height * 0.52))
    gap = max(24, int(width * 0.03))
    total_width = panel_count * panel_width + (panel_count - 1) * gap
    start_x = int(width / 2 - total_width / 2 + panel_width / 2)
    records: List[Dict[str, int]] = []
    for index in range(panel_count):
        records.append({
            "x": start_x + index * (panel_width + gap),
            "y": int(height * 0.2),
            "width": panel_width,
            "height": panel_height,
        })
    return records


def _pit_records(room: Dict[str, Any], width: int, height: int) -> List[Dict[str, Any]]:
    raw = room.get("pits") if isinstance(room.get("pits"), list) else room.get("voidSpans")
    pits: List[Dict[str, Any]] = []
    for item in (raw or []):
        if not isinstance(item, dict):
            continue
        pit_width = max(96, int(item.get("width") or item.get("w") or 192))
        pit_height = max(128, int(item.get("height") or item.get("h") or 224))
        pits.append({
            "pit_id": str(item.get("id") or f"pit-{len(pits) + 1}"),
            "x": int(item.get("x") or max(0, int(width * 0.35))),
            "y": int(item.get("y") or max(0, int(height * 0.72))),
            "width": pit_width,
            "height": pit_height,
        })
    return pits


def _planner_coverage_summary(room: Dict[str, Any], plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    dims = _room_dimensions(room)
    doors = _door_records(room, int(dims.get("width") or 0), int(dims.get("height") or 0))
    platforms = _platform_records(room)
    door_slot_count = sum(1 for item in plan if str(item.get("schema_key") or "") == "doors")
    platform_top_count = sum(1 for item in plan if str(item.get("component_type") or "").endswith("_top") and str(item.get("schema_key") or "") in {"floor", "platforms"})
    expected_platform_count = len(platforms)
    if platforms:
        # One platform becomes the primary floor. It still counts as a traversal structure.
        expected_platform_count = len(platforms)
    missing_slots: List[str] = []
    if door_slot_count < len(doors):
        missing_slots.append("door_slots_missing")
    if platform_top_count < expected_platform_count:
        missing_slots.append("platform_slots_missing")
    blockers = list(missing_slots)
    return {
        "status": "pass" if not blockers else "fail",
        "major_structures": {
            "door_count": len(doors),
            "platform_count": len(platforms),
            "planned_door_slots": door_slot_count,
            "planned_platform_slots": platform_top_count,
        },
        "missing_slots": missing_slots,
        "blockers": blockers,
    }


def _validation_status(review_state: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_review = review_state.get("runtime_review") or {}
    runtime_status = str(runtime_review.get("status") or "idle")
    screenshot_url = runtime_review.get("screenshot_url")
    if runtime_status != "pass":
        issues.append("runtime_review_pending" if runtime_status in {"idle", "running"} else "runtime_review_failed")
    if not screenshot_url:
        issues.append("runtime_screenshot_missing")
    status = "blocked" if issues else "complete"
    return {"status": status, "issues": issues}


def _approval_status(review_state: Dict[str, Any]) -> str:
    validation_status = review_state.get("validation_status") or {}
    issues = list(validation_status.get("issues") or [])
    if "runtime_review_failed" in issues:
        return "blocked"
    if "runtime_review_pending" in issues or "runtime_screenshot_missing" in issues:
        return "runtime_review_pending"
    return "approved"
