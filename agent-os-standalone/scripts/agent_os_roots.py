#!/usr/bin/env python3
"""Shared Agent OS app-root and workspace-root resolution."""
from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent


def _resolve_root(raw: str | None, fallback: Path) -> Path:
    value = (raw or "").strip()
    if not value:
        return fallback
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (fallback / path).resolve()
    else:
        path = path.resolve()
    return path


def get_workspace_root() -> Path:
    """Return the MV workspace root Agent OS should read/write."""
    return _resolve_root(os.environ.get("MV_WORKSPACE_ROOT"), APP_ROOT)


WORKSPACE_ROOT = get_workspace_root()
AGENT_OS_ENV_FILE = APP_ROOT / "agent_os.env"
WORKSPACE_ENV_FILE = WORKSPACE_ROOT / ".env.local"
