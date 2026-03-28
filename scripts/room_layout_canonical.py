"""
Read/write repo-root `room-layout-data.json` for local dev (canonical layout sync in room-layout-editor).

Used by `sprite_workbench_server.py` for `GET`/`POST` `/api/layout` (repo-root `room-layout-data.json`).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL_LAYOUT_PATH = ROOT / "room-layout-data.json"


def read_canonical_layout() -> dict:
    """Load canonical layout JSON. Raises FileNotFoundError or json.JSONDecodeError."""
    return json.loads(CANONICAL_LAYOUT_PATH.read_text(encoding="utf-8"))


def save_canonical_layout(payload: dict) -> dict:
    """
    Validate and write canonical layout. Returns {"ok": True, "path": "..."}.
    Raises ValueError if payload shape is invalid; OSError on write failure.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("rooms"), list):
        raise ValueError("Payload must contain a rooms array")
    CANONICAL_LAYOUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(CANONICAL_LAYOUT_PATH)}
