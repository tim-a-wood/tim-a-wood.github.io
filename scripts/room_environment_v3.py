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

REVIEW_SURFACE_ORDER: List[str] = [
    "room_intent",
    "biome_selection",
    "component_contracts",
    "assembly_plan_overlay",
    "slot_gallery",
    "combined_kit",
    "runtime_view",
    "contrast_qa_view",
]

REQUIRED_SCREENSHOT_STAGES: List[str] = [
    "room_intent",
    "biome_selection",
    "component_contracts",
    "assembly_plan_overlay",
    "slot_gallery",
    "combined_kit",
    "runtime_view",
    "contrast_qa_view",
    "structural_only_runtime",
    "scenic_only_runtime",
]

QA_BLOCKER_CATEGORIES: List[str] = [
    "component_fit",
    "planner_coverage",
    "shell_readability",
    "traversal_readability",
    "biome_identity",
    "motif_violation",
    "runtime_composition",
    "workflow_usability",
]

CREATIVE_REJECTION_CODES: List[str] = [
    "shell_not_coherent",
    "component_role_unclear",
    "biome_identity_weak",
    "motif_violation",
    "focal_scene_drift",
    "value_hierarchy_broken",
]

TEMPLATE_COMPONENT_BY_SLOT: Dict[str, str] = {
    "background_far_plate": "background_plate",
    "backwall_panel": "background_plate",
    "midground_side_frame": "midground_frame",
    "wall_module_left": "background_plate",
    "wall_module_right": "background_plate",
    "wall_base_trim_left": "background_plate",
    "wall_base_trim_right": "background_plate",
    "ceiling_band": "background_plate",
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
        "qa_review_rounds": [],
        "creative_review_rounds": [],
        "approval_status": "draft",
        "review_bundle_id": None,
        "validation_plan": {
            "review_surface_order": list(REVIEW_SURFACE_ORDER),
            "required_screenshot_stages": list(REQUIRED_SCREENSHOT_STAGES),
            "required_round_counts": {"qa": 3, "creative": 3},
            "qa_blocker_categories": list(QA_BLOCKER_CATEGORIES),
            "creative_rejection_codes": list(CREATIVE_REJECTION_CODES),
            "runtime_is_approval_artifact": True,
            "proposal_first_required": True,
        },
        "validation_status": {
            "status": "pending",
            "issues": ["runtime_review_pending", "qa_review_pending", "creative_review_pending"],
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
    review_state.setdefault("validation_plan", copy.deepcopy(default_review_state()["validation_plan"]))
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


def append_manual_review_round(env: Dict[str, Any], payload: Dict[str, Any], created_at: str) -> Dict[str, Any]:
    ensure_v3_metadata(env)
    review_state = env["review_state"]
    reviewer_role = str(payload.get("reviewer_role") or "").strip().lower()
    if reviewer_role not in {"qa", "creative", "design"}:
        raise ValueError("reviewer_role must be qa, creative, or design.")
    key = "qa_review_rounds" if reviewer_role == "qa" else "creative_review_rounds" if reviewer_role == "creative" else "design_review_rounds"
    rounds = review_state.get(key)
    if not isinstance(rounds, list):
        rounds = []
        review_state[key] = rounds
    round_number = len(rounds) + 1
    screenshots = [copy.deepcopy(item) for item in (payload.get("screenshots") or []) if isinstance(item, dict)]
    findings = [copy.deepcopy(item) for item in (payload.get("findings") or []) if isinstance(item, dict)]
    record = {
        "round_number": round_number,
        "reviewer_role": reviewer_role,
        "reviewer_name": str(payload.get("reviewer_name") or "").strip() or reviewer_role,
        "date": created_at,
        "screenshots": screenshots,
        "findings": findings,
        "finding_codes": [str(item).strip() for item in (payload.get("finding_codes") or []) if str(item).strip()],
        "blockers": [str(item).strip() for item in (payload.get("blockers") or []) if str(item).strip()],
        "decision": str(payload.get("decision") or "needs_changes").strip(),
        "required_changes": [str(item).strip() for item in (payload.get("required_changes") or []) if str(item).strip()],
    }
    rounds.append(record)
    review_state["validation_status"] = _validation_status(review_state)
    review_state["approval_status"] = _approval_status(review_state)
    return record


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
    doors = _door_records(room)
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
    append_slot(
        f"{room_id}-backwall-panel",
        "backwall_panel",
        "backwall_panel",
        {"width": int(width * 0.64), "height": max(240, int(height * 0.52))},
        {"x": int(width / 2), "y": int(height * 0.2), "display_width": int(width * 0.64), "display_height": max(240, int(height * 0.52)), "origin_x": 0.5, "origin_y": 0},
        "full",
        "stretch",
        "background",
        [center_lane],
        {"room_width": width, "room_height": height},
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
    append_slot(
        f"{room_id}-wall-module-left",
        "wall_module_left",
        "walls",
        {"width": 320, "height": max(320, height - 180)},
        {"x": 0, "y": 0, "display_width": 320, "display_height": max(320, height - 180), "origin_x": 0, "origin_y": 0},
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
        {"width": 320, "height": max(320, height - 180)},
        {"x": max(0, width - 320), "y": 0, "display_width": 320, "display_height": max(320, height - 180), "origin_x": 0, "origin_y": 0},
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
        append_slot(
            f"{room_id}-door-{index + 1}",
            "door_frame",
            "doors",
            {"width": 192, "height": 288},
            {"x": door["x"], "y": door["y"], "display_width": 96, "display_height": 144, "origin_x": 0.5, "origin_y": 1},
            "vertical",
            "stretch",
            "doors",
            [{"type": "door_mouth", "x": door["x"] - 48, "y": door["y"] - 144, "width": 96, "height": 160}],
            door,
            border_treatment="threshold_clearance",
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


def _door_records(room: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in (room.get("doors") or []):
        if not isinstance(item, dict):
            continue
        records.append({
            "door_id": str(item.get("id") or f"door-{len(records) + 1}"),
            "x": int(item.get("x") or 0),
            "y": int(item.get("y") or 0),
            "kind": str(item.get("kind") or "transition"),
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
    doors = _door_records(room)
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
    validation_plan = review_state.get("validation_plan") or {}
    required_round_counts = validation_plan.get("required_round_counts") or {}
    runtime_review = review_state.get("runtime_review") or {}
    runtime_status = str(runtime_review.get("status") or "idle")
    screenshot_url = runtime_review.get("screenshot_url")
    if runtime_status != "pass":
        issues.append("runtime_review_pending" if runtime_status in {"idle", "running"} else "runtime_review_failed")
    if not screenshot_url:
        issues.append("runtime_screenshot_missing")
    qa_rounds = review_state.get("qa_review_rounds") or []
    creative_rounds = review_state.get("creative_review_rounds") or []
    required_qa_rounds = int(required_round_counts.get("qa") or 0)
    required_creative_rounds = int(required_round_counts.get("creative") or 0)
    if not qa_rounds:
        issues.append("qa_review_pending")
    elif required_qa_rounds and len(qa_rounds) < required_qa_rounds:
        issues.append("qa_round_count_incomplete")
    if not creative_rounds:
        issues.append("creative_review_pending")
    elif required_creative_rounds and len(creative_rounds) < required_creative_rounds:
        issues.append("creative_round_count_incomplete")
    manual_only_issues = {
        "qa_review_pending",
        "creative_review_pending",
        "qa_round_count_incomplete",
        "creative_round_count_incomplete",
    }
    status = "ready_for_manual_review" if issues and set(issues).issubset(manual_only_issues) else "blocked" if issues else "complete"
    return {"status": status, "issues": issues}


def _approval_status(review_state: Dict[str, Any]) -> str:
    validation_status = review_state.get("validation_status") or {}
    issues = list(validation_status.get("issues") or [])
    if "runtime_review_failed" in issues:
        return "blocked"
    if "runtime_review_pending" in issues or "runtime_screenshot_missing" in issues:
        return "runtime_review_pending"
    if (
        "qa_review_pending" in issues
        or "creative_review_pending" in issues
        or "qa_round_count_incomplete" in issues
        or "creative_round_count_incomplete" in issues
    ):
        return "manual_review_pending"
    for key in ("qa_review_rounds", "creative_review_rounds"):
        rounds = review_state.get(key) or []
        if rounds and any((item.get("blockers") or []) for item in rounds if isinstance(item, dict)):
            return "needs_revision"
        if rounds and any(str(item.get("decision") or "").strip().lower() not in {"pass", "approved"} for item in rounds if isinstance(item, dict)):
            return "needs_revision"
    return "approved"
