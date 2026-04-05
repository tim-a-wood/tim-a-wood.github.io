from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple


Point = Dict[str, int]
Rect = Dict[str, int]

AUTHORITATIVE_FIELDS = [
    "id",
    "name",
    "size",
    "polygon",
    "platforms",
    "doors",
    "movingPlatforms",
    "playerStart",
    "edgeLinks",
    "removedEdges",
    "keys",
    "abilities",
    "pits",
]


def _room_bounds(room: Optional[Dict[str, Any]]) -> Tuple[int, int]:
    size = (room or {}).get("size") or {}
    return int(size.get("width") or 0), int(size.get("height") or 0)


def _polygon_points(room: Optional[Dict[str, Any]]) -> List[Point]:
    points: List[Point] = []
    for point in ((room or {}).get("polygon") or []):
        if not isinstance(point, Sequence) or len(point) < 2:
            continue
        points.append({"x": int(round(float(point[0]))), "y": int(round(float(point[1])))})
    return points


def _rect(x: int, y: int, width: int, height: int, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "x": int(x),
        "y": int(y),
        "width": max(0, int(width)),
        "height": max(0, int(height)),
    }
    payload.update(extra)
    return payload


def _midpoint(start: Point, end: Point) -> Point:
    return {"x": int(round((start["x"] + end["x"]) / 2)), "y": int(round((start["y"] + end["y"]) / 2))}


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def _edge_rect(start: Point, end: Point, thickness: int = 24) -> Rect:
    pad = max(8, thickness // 2)
    x = min(start["x"], end["x"]) - pad
    y = min(start["y"], end["y"]) - pad
    width = abs(end["x"] - start["x"]) + pad * 2
    height = abs(end["y"] - start["y"]) + pad * 2
    return _rect(x, y, width, height)


def _platform_records(room: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in ((room or {}).get("platforms") or []):
        if not isinstance(item, dict):
            continue
        length = max(1, int(item.get("len") or 1))
        width = length * 32
        x = int(item.get("x") or 0)
        y = int(item.get("y") or 0)
        face_height = max(32, min(160, int(length * 4)))
        platform_id = str(item.get("id") or f"platform-{len(records) + 1}")
        left = {"x": x, "y": y, "width": 16, "height": face_height}
        right = {"x": x + max(0, width - 16), "y": y, "width": 16, "height": face_height}
        top = {"x": x, "y": y, "width": width, "height": 16}
        underside = {"x": x, "y": y + 16, "width": width, "height": 12}
        records.append(
            {
                "platform_id": platform_id,
                "top": top,
                "underside": underside,
                "left_face": left,
                "right_face": right,
                "corners": [
                    {"corner_id": f"{platform_id}-left-top", "x": x, "y": y, "source": "platform"},
                    {"corner_id": f"{platform_id}-right-top", "x": x + width, "y": y, "source": "platform"},
                ],
                "anchor": {
                    "anchor_id": f"{platform_id}-center",
                    "x": x + int(width / 2),
                    "y": y,
                    "anchor_type": "platform_center",
                    "source": "platform",
                },
            }
        )
    return records


def _moving_platform_records(room: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in ((room or {}).get("movingPlatforms") or []):
        if not isinstance(item, dict):
            continue
        mover_id = str(item.get("id") or f"moving-platform-{len(records) + 1}")
        length = max(1, int(item.get("len") or 1))
        width = length * 32
        x = int(item.get("x") or 0)
        y = int(item.get("y") or 0)
        end_x = int(item.get("endX") or x)
        end_y = int(item.get("endY") or y)
        top = {"x": min(x, end_x), "y": min(y, end_y), "width": max(width, abs(end_x - x) + width), "height": 16}
        underside = {"x": top["x"], "y": top["y"] + 16, "width": top["width"], "height": 12}
        records.append(
            {
                "moving_platform_id": mover_id,
                "top": top,
                "underside": underside,
                "left_face": {"x": top["x"], "y": top["y"], "width": 16, "height": max(32, min(160, int(length * 4)))},
                "right_face": {"x": top["x"] + max(0, top["width"] - 16), "y": top["y"], "width": 16, "height": max(32, min(160, int(length * 4)))},
                "path_zone": _rect(min(x, end_x), min(y, end_y) - 24, abs(end_x - x) + width, abs(end_y - y) + 48, zone_id=f"{mover_id}-path", zone_type="moving_platform_path"),
                "anchor": {
                    "anchor_id": f"{mover_id}-path-center",
                    "x": int(round((x + end_x + width) / 2)),
                    "y": int(round((y + end_y) / 2)),
                    "anchor_type": "moving_platform_path_center",
                    "source": "movingPlatform",
                },
                "corners": [
                    {"corner_id": f"{mover_id}-left-top", "x": top["x"], "y": top["y"], "source": "movingPlatform"},
                    {"corner_id": f"{mover_id}-right-top", "x": top["x"] + top["width"], "y": top["y"], "source": "movingPlatform"},
                ],
            }
        )
    return records


def _classify_threshold(x: int, y: int, width: int, height: int) -> str:
    if y <= max(160, int(height * 0.18)):
        return "top_threshold"
    if y >= max(0, height - max(180, int(height * 0.2))):
        return "bottom_threshold"
    if x <= max(160, int(width * 0.18)):
        return "left_threshold"
    if x >= max(0, width - max(180, int(width * 0.18))):
        return "right_threshold"
    return "interior_threshold"


def _door_records(room: Optional[Dict[str, Any]], width: int, height: int) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in ((room or {}).get("doors") or []):
        if not isinstance(item, dict):
            continue
        x = int(item.get("x") or 0)
        y = int(item.get("y") or 0)
        anchor_type = _classify_threshold(x, y, width, height)
        if anchor_type in ("top_threshold", "bottom_threshold"):
            boundary = _rect(x - 72, y - 24, 144, 96)
            shoulder_a = {"corner_id": f"{item.get('id')}-shoulder-left", "x": x - 72, "y": y, "source": "door"}
            shoulder_b = {"corner_id": f"{item.get('id')}-shoulder-right", "x": x + 72, "y": y, "source": "door"}
        else:
            boundary = _rect(x - 48, y - 88, 96, 176)
            shoulder_a = {"corner_id": f"{item.get('id')}-shoulder-top", "x": x, "y": y - 88, "source": "door"}
            shoulder_b = {"corner_id": f"{item.get('id')}-shoulder-bottom", "x": x, "y": y + 88, "source": "door"}
        door_id = str(item.get("id") or f"door-{len(records) + 1}")
        records.append(
            {
                "opening_id": door_id,
                "opening_type": "door",
                "opening_boundary": boundary,
                "source": "door",
                "anchor": {"anchor_id": f"{door_id}-anchor", "x": x, "y": y, "anchor_type": anchor_type, "source": "door"},
                "corners": [shoulder_a, shoulder_b],
            }
        )
    return records


def _polygon_edges(points: List[Point]) -> List[Tuple[Point, Point]]:
    if len(points) < 2:
        return []
    return [(points[index], points[(index + 1) % len(points)]) for index in range(len(points))]


def _edge_opening_records(room: Dict[str, Any], points: List[Point]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    edges = _polygon_edges(points)
    edge_links = {(int(link.get("edgeIndex")), str(link.get("targetRoomId") or ""), int(link.get("targetEdgeIndex") or 0)) for link in (room.get("edgeLinks") or []) if isinstance(link, dict)}
    removed_edges = {int(index) for index in (room.get("removedEdges") or []) if isinstance(index, int)}
    for index, (start, end) in enumerate(edges):
        link = next((link for link in edge_links if link[0] == index), None)
        if index not in removed_edges and link is None:
            continue
        opening_id = f"{room.get('id') or 'room'}-edge-opening-{index}"
        opening_type = "edge_link" if link is not None else "removed_edge"
        mid = _midpoint(start, end)
        records.append(
            {
                "opening_id": opening_id,
                "opening_type": opening_type,
                "opening_boundary": _edge_rect(start, end, 40),
                "edge_index": index,
                "source": "edge_link" if link is not None else "removed_edge",
                "anchor": {
                    "anchor_id": f"{opening_id}-anchor",
                    "x": mid["x"],
                    "y": mid["y"],
                    "anchor_type": opening_type,
                    "source": "edge",
                },
                "corners": [
                    {"corner_id": f"{opening_id}-start", "x": start["x"], "y": start["y"], "source": "edge"},
                    {"corner_id": f"{opening_id}-end", "x": end["x"], "y": end["y"], "source": "edge"},
                ],
                "target_room_id": link[1] if link is not None else "",
                "target_edge_index": link[2] if link is not None else None,
            }
        )
    return records


def _polygon_orientation(points: List[Point]) -> int:
    total = 0
    for current, next_point in _polygon_edges(points):
        total += current["x"] * next_point["y"] - next_point["x"] * current["y"]
    return 1 if total >= 0 else -1


def _concave_cavity_records(points: List[Point]) -> List[Dict[str, Any]]:
    if len(points) < 4:
        return []
    orientation = _polygon_orientation(points)
    cavities: List[Dict[str, Any]] = []
    for index in range(len(points)):
        prev_point = points[index - 1]
        point = points[index]
        next_point = points[(index + 1) % len(points)]
        ax = point["x"] - prev_point["x"]
        ay = point["y"] - prev_point["y"]
        bx = next_point["x"] - point["x"]
        by = next_point["y"] - point["y"]
        cross = ax * by - ay * bx
        if cross == 0 or (1 if cross > 0 else -1) == orientation:
            continue
        size = 56
        cavities.append(
            {
                "cavity_id": f"cavity-{index + 1}",
                "x": point["x"] - size // 2,
                "y": point["y"] - size // 2,
                "width": size,
                "height": size,
                "source_corner_id": f"corner-{index + 1}",
            }
        )
    return cavities


def _keys_and_abilities_exclusion(room: Dict[str, Any]) -> List[Dict[str, Any]]:
    zones: List[Dict[str, Any]] = []
    for field_name, zone_type in (("keys", "key_pickup"), ("abilities", "ability_pickup")):
        for item in (room.get(field_name) or []):
            if not isinstance(item, dict):
                continue
            x = int(item.get("x") or 0)
            y = int(item.get("y") or 0)
            item_id = str(item.get("id") or f"{field_name[:-1]}-{len(zones) + 1}")
            zones.append(_rect(x - 24, y - 24, 48, 48, zone_id=f"{item_id}-pickup-zone", zone_type=zone_type))
    return zones


def _player_start_zone(room: Dict[str, Any]) -> List[Dict[str, Any]]:
    item = room.get("playerStart")
    if not isinstance(item, dict):
        return []
    x = int(item.get("x") or 0)
    y = int(item.get("y") or 0)
    return [_rect(x - 32, y - 32, 64, 64, zone_id="player-start-zone", zone_type="player_start")]


def _derive_room_role(room: Dict[str, Any], width: int, height: int) -> str:
    name = str(room.get("name") or "").strip().lower()
    if "hub" in name:
        return "hub"
    if "shaft" in name:
        return "traversal_shaft"
    if "corridor" in name or "passage" in name or "threshold" in name:
        return "corridor_transition"
    if "reward" in name or "treasure" in name:
        return "reward_room"
    if "boss" in name:
        return "pre_boss"
    if "shrine" in name:
        return "shrine_chamber"
    polygon = room.get("polygon") or []
    if polygon:
        xs = [float(point[0]) for point in polygon if isinstance(point, Sequence) and len(point) >= 2]
        ys = [float(point[1]) for point in polygon if isinstance(point, Sequence) and len(point) >= 2]
        if xs and ys:
            poly_width = max(xs) - min(xs)
            poly_height = max(ys) - min(ys)
            if poly_height > max(poly_width * 2.4, 480) and not (room.get("platforms") or []):
                return "traversal_shaft"
    if height > max(width * 1.15, width + 240) and not (room.get("platforms") or []):
        return "traversal_shaft"
    if len(room.get("doors") or []) >= 3:
        return "hub"
    if len(polygon) > 8 and len(room.get("platforms") or []) >= 5:
        return "chamber"
    if len(room.get("doors") or []) >= 1:
        return "threshold"
    return "room"


def derive_room_semantics(room: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    room = room or {}
    width, height = _room_bounds(room)
    polygon_points = _polygon_points(room)
    polygon = [[point["x"], point["y"]] for point in polygon_points]
    platform_records = _platform_records(room)
    moving_platform_records = _moving_platform_records(room)
    door_records = _door_records(room, width, height)
    edge_openings = _edge_opening_records(room, polygon_points)
    opening_records = door_records + edge_openings

    exposed_tops = [item["top"] for item in platform_records] + [item["top"] for item in moving_platform_records]
    undersides = [item["underside"] for item in platform_records] + [item["underside"] for item in moving_platform_records]
    vertical_faces = (
        [item["left_face"] for item in platform_records]
        + [item["right_face"] for item in platform_records]
        + [item["left_face"] for item in moving_platform_records]
        + [item["right_face"] for item in moving_platform_records]
    )
    shell_surfaces: List[Dict[str, Any]] = []
    corner_records: List[Dict[str, Any]] = []

    for index, point in enumerate(polygon_points):
        next_point = polygon_points[(index + 1) % len(polygon_points)] if polygon_points else point
        shell_surfaces.append(
            {
                "surface_id": f"shell-{index + 1}",
                "start": {"x": point["x"], "y": point["y"]},
                "end": {"x": next_point["x"], "y": next_point["y"]},
                "surface_type": "boundary_edge",
            }
        )
        corner_records.append({"corner_id": f"corner-{index + 1}", "x": point["x"], "y": point["y"], "source": "polygon"})

    for record in platform_records:
        corner_records.extend(record["corners"])
    for record in opening_records:
        corner_records.extend(record["corners"])

    background_cavities = _concave_cavity_records(polygon_points)
    anchors = [item["anchor"] for item in platform_records] + [item["anchor"] for item in moving_platform_records] + [item["anchor"] for item in opening_records]
    anchors.extend({"anchor_id": corner["corner_id"], "x": corner["x"], "y": corner["y"], "anchor_type": "corner", "source": corner.get("source", "polygon")} for corner in corner_records if corner.get("source") in ("polygon", "platform"))

    gameplay_exclusion_zones: List[Dict[str, Any]] = []
    gameplay_exclusion_zones.extend(
        _rect(record["top"]["x"], record["top"]["y"] - 8, record["top"]["width"], record["top"]["height"] + 16, zone_id=f"{record['platform_id']}-top-buffer", zone_type="platform_top")
        for record in platform_records
    )
    gameplay_exclusion_zones.extend(
        _rect(record["opening_boundary"]["x"], record["opening_boundary"]["y"], record["opening_boundary"]["width"], record["opening_boundary"]["height"], zone_id=f"{record['opening_id']}-opening-zone", zone_type=record["opening_type"])
        for record in opening_records
    )
    gameplay_exclusion_zones.extend(record["path_zone"] for record in moving_platform_records)
    gameplay_exclusion_zones.extend(_player_start_zone(room))
    gameplay_exclusion_zones.extend(_keys_and_abilities_exclusion(room))

    decor_safe_zones: List[Dict[str, Any]] = []
    if width and height:
        candidate_zones = [
            _rect(24, 24, max(0, int(width * 0.22) - 24), max(0, int(height * 0.22) - 24), zone_id="upper-left-safe", zone_type="decor_safe"),
            _rect(max(24, int(width * 0.78)), 24, max(0, width - int(width * 0.78) - 24), max(0, int(height * 0.22) - 24), zone_id="upper-right-safe", zone_type="decor_safe"),
        ]
        for zone in candidate_zones:
            if zone["width"] <= 0 or zone["height"] <= 0:
                continue
            overlaps = False
            for blocked in gameplay_exclusion_zones:
                if not (
                    zone["x"] + zone["width"] <= blocked["x"]
                    or blocked["x"] + blocked["width"] <= zone["x"]
                    or zone["y"] + zone["height"] <= blocked["y"]
                    or blocked["y"] + blocked["height"] <= zone["y"]
                ):
                    overlaps = True
                    break
            if not overlaps:
                decor_safe_zones.append(zone)

    source_fields_used = [field for field in AUTHORITATIVE_FIELDS if room.get(field) not in (None, [], {}, "")]
    truth_checks = [
        "overlay_matches_room_polygon",
        "door_and_edge_openings_preserved",
        "platform_top_and_underside_truth",
        "non_authority_fields_ignored",
    ]
    if moving_platform_records:
        truth_checks.append("moving_platform_path_reserved")

    summary = {
        "top_count": len(exposed_tops),
        "underside_count": len(undersides),
        "vertical_face_count": len(vertical_faces),
        "opening_count": len(opening_records),
        "corner_count": len(corner_records),
        "anchor_count": len(anchors),
        "cavity_count": len(background_cavities),
        "decor_safe_zone_count": len(decor_safe_zones),
        "gameplay_exclusion_zone_count": len(gameplay_exclusion_zones),
        "shell_surface_count": len(shell_surfaces),
    }

    return {
        "schema_version": "room-semantics-v1",
        "room_id": room.get("id"),
        "room_name": room.get("name"),
        "room_role": _derive_room_role(room, width, height),
        "room_type": str(room.get("roomType") or room.get("room_type") or room.get("type") or "unknown"),
        "room_size": {"width": width, "height": height},
        "source_fields_used": source_fields_used,
        "truth_checks": truth_checks,
        "exposed_tops": exposed_tops,
        "moving_platform_tops": [item["top"] for item in moving_platform_records],
        "undersides": undersides,
        "moving_platform_undersides": [item["underside"] for item in moving_platform_records],
        "vertical_faces": vertical_faces,
        "shell_surfaces": shell_surfaces,
        "corner_records": corner_records,
        "opening_boundaries": [item["opening_boundary"] for item in opening_records],
        "opening_records": opening_records,
        "background_cavities": background_cavities,
        "decor_safe_zones": decor_safe_zones,
        "gameplay_exclusion_zones": gameplay_exclusion_zones,
        "anchor_positions": anchors,
        "overlay_geometry": {
            "room_polygon": polygon,
            "shell_surfaces": shell_surfaces,
            "openings": [copy.deepcopy(item) for item in opening_records],
            "doors": [item["opening_boundary"] for item in door_records],
            "platform_tops": exposed_tops,
            "moving_platform_tops": [item["top"] for item in moving_platform_records],
            "platform_undersides": undersides,
            "moving_platform_undersides": [item["underside"] for item in moving_platform_records],
            "vertical_faces": vertical_faces,
            "platform_faces": [item["left_face"] for item in platform_records] + [item["right_face"] for item in platform_records],
            "moving_platform_faces": [item["left_face"] for item in moving_platform_records] + [item["right_face"] for item in moving_platform_records],
            "corners": corner_records,
            "anchors": anchors,
            "background_cavities": background_cavities,
            "decor_safe_zones": decor_safe_zones,
            "gameplay_exclusion_zones": gameplay_exclusion_zones,
        },
        "summary": summary,
    }
