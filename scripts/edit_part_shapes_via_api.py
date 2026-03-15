#!/usr/bin/env python3
"""
Edit part shapes via the sprite workbench HTTP API.
Usage:
  python scripts/edit_part_shapes_via_api.py [--base-url URL] [project_id]
Default project: test-player-36b63eaf. Default base URL: http://127.0.0.1:8766
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description="Edit part shapes via sprite workbench API")
    parser.add_argument("project_id", nargs="?", default="test-player-36b63eaf", help="Project ID")
    parser.add_argument("--base-url", default="http://127.0.0.1:8766", help="API base URL")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    project_id = args.project_id

    # 1) GET current part shapes
    url = f"{base}/api/projects/{project_id}/part-shapes"
    req = Request(url, method="GET")
    req.add_header("Accept", "application/json")
    try:
        with urlopen(req, timeout=10) as resp:
            part_shapes = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError) as e:
        print("GET part-shapes failed:", e, file=sys.stderr)
        sys.exit(1)

    parts = part_shapes.get("parts") or []
    if not parts:
        print("No parts in part_shapes.", file=sys.stderr)
        sys.exit(1)

    # 2) Apply edits (non-destructive: round head top, nudge weapon)
    modified = copy.deepcopy(part_shapes)
    modified_parts = modified.get("parts") or []

    for part in modified_parts:
        name = part.get("part_name") or ""
        verts = part.get("vertices") or []
        if name == "head" and len(verts) >= 6:
            # Slightly round the top: move top-left and top-right inward and add a top-center point
            # Original head bbox top: y=60. Vertices 0..5 are left side (x~221), 6..11 right (x~371), last is (358,60).
            # Make a small edit: nudge the top-right vertex (358,60) to (365,55) for a subtle shape change
            for i, v in enumerate(verts):
                if v[0] == 358 and v[1] == 60:
                    verts[i] = [365, 55]
                    break
            part["vertices"] = verts
            part["notes"] = "Edited via API: top-right vertex nudged."
        if name == "weapon" and len(verts) >= 4:
            # Nudge first vertex slightly
            v0 = list(verts[0])
            v0[0] += 3
            v0[1] -= 2
            verts[0] = v0
            part["vertices"] = verts
            if not part.get("notes"):
                part["notes"] = "Edited via API: first vertex nudged."

    # Remove validation so server recomputes it
    modified.pop("validation", None)

    # 3) POST part-shapes/update
    update_url = f"{base}/api/projects/{project_id}/part-shapes/update"
    body = json.dumps({"operation": "replace_shapes", "part_shapes": modified}).encode("utf-8")
    req = Request(update_url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urlopen(req, timeout=30) as resp:
            updated = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        print("POST part-shapes/update failed:", e.code, e.read().decode("utf-8"), file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print("POST part-shapes/update failed:", e, file=sys.stderr)
        sys.exit(1)

    print("Part shapes updated successfully.")
    print("Parts count:", len(updated.get("parts") or []))
    validation = updated.get("validation") or {}
    print("Validation status:", validation.get("status", "unknown"))


if __name__ == "__main__":
    main()
