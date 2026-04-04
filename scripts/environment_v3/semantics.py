from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple


def _room_bounds(room: Optional[Dict[str, Any]]) -> Tuple[int, int]:
    size = (room or {}).get("size") or {}
    return int(size.get("width") or 0), int(size.get("height") or 0)


def _platform_records(room: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in ((room or {}).get("platforms") or []):
        if not isinstance(item, dict):
            continue
        length = max(1, int(item.get("len") or 1))
        width = length * 32
        x = int(item.get("x") or 0)
        y = int(item.get("y") or 0)
        face_height = max(40, min(160, int(length * 3)))
        platform_id = str(item.get("id") or f"platform-{len(records) + 1}")
        records.append(
            {
                "platform_id": platform_id,
                "top": {"x": x, "y": y, "width": width, "height": 16},
                "underside": {"x": x, "y": y + 16, "width": width, "height": 16},
                "left_face": {"x": x, "y": y, "width": 16, "height": face_height},
                "right_face": {"x": x + max(0, width - 16), "y": y, "width": 16, "height": face_height},
                "anchor": {"anchor_id": f"{platform_id}-center", "x": x + int(width / 2), "y": y, "anchor_type": "platform_center"},
            }
        )
    return records


def _door_records(room: Optional[Dict[str, Any]], width: int, height: int) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for item in ((room or {}).get("doors") or []):
        if not isinstance(item, dict):
            continue
        x = int(item.get("x") or 0)
        y = int(item.get("y") or 0)
        if y <= max(160, int(height * 0.18)):
            boundary = {"x": x - 72, "y": y, "width": 144, "height": 112}
            anchor_type = "top_threshold"
        elif x <= max(160, int(width * 0.18)):
            boundary = {"x": x, "y": y - 144, "width": 112, "height": 160}
            anchor_type = "left_threshold"
        elif x >= min(width - 160, int(width * 0.82)):
            boundary = {"x": x - 112, "y": y - 144, "width": 112, "height": 160}
            anchor_type = "right_threshold"
        else:
            boundary = {"x": x - 48, "y": y - 144, "width": 96, "height": 160}
            anchor_type = "bottom_threshold"
        door_id = str(item.get("id") or f"door-{len(records) + 1}")
        records.append(
            {
                "door_id": door_id,
                "opening_boundary": boundary,
                "anchor": {"anchor_id": f"{door_id}-anchor", "x": x, "y": y, "anchor_type": anchor_type},
            }
        )
    return records


def derive_room_semantics(room: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    room = room or {}
    width, height = _room_bounds(room)
    polygon = copy.deepcopy(room.get("polygon") or [])
    platform_records = _platform_records(room)
    door_records = _door_records(room, width, height)
    exposed_tops = [item["top"] for item in platform_records]
    undersides = [item["underside"] for item in platform_records]
    vertical_faces = [item["left_face"] for item in platform_records] + [item["right_face"] for item in platform_records]
    shell_surfaces = []
    corner_records = []
    if polygon:
        for index, point in enumerate(polygon):
            next_point = polygon[(index + 1) % len(polygon)]
            shell_surfaces.append(
                {
                    "surface_id": f"shell-{index + 1}",
                    "start": {"x": int(point[0]), "y": int(point[1])},
                    "end": {"x": int(next_point[0]), "y": int(next_point[1])},
                }
            )
            corner_records.append({"corner_id": f"corner-{index + 1}", "x": int(point[0]), "y": int(point[1])})
    opening_boundaries = [item["opening_boundary"] for item in door_records]
    anchors = [item["anchor"] for item in door_records] + [item["anchor"] for item in platform_records]
    decor_safe_zones = []
    if width and height:
        decor_safe_zones.append({"zone_id": "upper-side-left", "x": 0, "y": 0, "width": int(width * 0.22), "height": int(height * 0.42)})
        decor_safe_zones.append({"zone_id": "upper-side-right", "x": int(width * 0.78), "y": 0, "width": max(0, width - int(width * 0.78)), "height": int(height * 0.42)})
    gameplay_exclusion_zones = opening_boundaries + [{"zone_id": "platform-top-buffer", **record["top"]} for record in platform_records]
    background_cavities = [{"cavity_id": "main-cavity", "x": int(width * 0.14), "y": int(height * 0.14), "width": int(width * 0.72), "height": int(height * 0.52)}] if width and height else []
    return {
        "schema_version": 1,
        "room_id": room.get("id"),
        "exposed_tops": exposed_tops,
        "undersides": undersides,
        "vertical_faces": vertical_faces,
        "shell_surfaces": shell_surfaces,
        "corner_records": corner_records,
        "opening_boundaries": opening_boundaries,
        "background_cavities": background_cavities,
        "decor_safe_zones": decor_safe_zones,
        "gameplay_exclusion_zones": gameplay_exclusion_zones,
        "anchor_positions": anchors,
        "overlay_geometry": {
            "room_polygon": polygon,
            "doors": [item["opening_boundary"] for item in door_records],
            "platform_tops": exposed_tops,
            "decor_safe_zones": decor_safe_zones,
            "gameplay_exclusion_zones": gameplay_exclusion_zones,
        },
        "summary": {
            "top_count": len(exposed_tops),
            "underside_count": len(undersides),
            "vertical_face_count": len(vertical_faces),
            "opening_count": len(opening_boundaries),
            "corner_count": len(corner_records),
            "anchor_count": len(anchors),
        },
    }
