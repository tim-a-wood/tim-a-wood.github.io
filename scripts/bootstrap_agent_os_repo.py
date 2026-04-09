#!/usr/bin/env python3
"""Bootstrap a standalone Agent OS repo from the approved phase-1 manifest."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from scripts.agent_os_split_manifest import PHASE1_COPY_PATHS
from scripts.agent_os_standalone_templates import (
    STANDALONE_AGENTS,
    STANDALONE_CLAUDE,
    STANDALONE_GITIGNORE,
    STANDALONE_README,
)


def _copy_path(src_root: Path, dest_root: Path, rel: str, *, force: bool) -> None:
    src = src_root / rel
    dest = dest_root / rel
    if not src.exists():
        raise FileNotFoundError(f"Missing manifest path: {rel}")
    if dest.exists():
        if not force:
            raise FileExistsError(f"Destination exists: {dest}")
        if dest.is_dir() and not dest.is_symlink():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Bootstrap a standalone Agent OS repo from the MV checkout.")
    ap.add_argument("destination", help="Destination directory for the new Agent OS repo")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files in destination")
    args = ap.parse_args()

    dest_root = Path(args.destination).expanduser().resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    for rel in PHASE1_COPY_PATHS:
        _copy_path(APP_ROOT, dest_root, rel, force=args.force)

    _write_text(dest_root / "README.md", STANDALONE_README)
    _write_text(dest_root / "AGENTS.md", STANDALONE_AGENTS)
    _write_text(dest_root / "CLAUDE.md", STANDALONE_CLAUDE)
    _write_text(dest_root / ".gitignore", STANDALONE_GITIGNORE)

    print(f"Bootstrapped Agent OS repo scaffold at {dest_root}")
    print("Next step: run the copied launcher with MV_WORKSPACE_ROOT pointing at the MV workspace.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
