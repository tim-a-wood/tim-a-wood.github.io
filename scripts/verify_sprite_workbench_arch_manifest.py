#!/usr/bin/env python3
"""Fail if committed manifest.json drifts from the extractor (volatile keys ignored).

Run from repo root: python3 scripts/verify_sprite_workbench_arch_manifest.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

REPO = Path(__file__).resolve().parent.parent
COMMITTED = REPO / "artifacts" / "sprite-workbench-arch" / "manifest.json"
EXTRACT = REPO / "scripts" / "extract_sprite_workbench_arch.py"

VOLATILE_KEYS = frozenset({"generated_at", "git_sha"})
# Git history differs per clone/depth; extractor fills these from `git log`.
GIT_DERIVED_ROOT_KEYS = frozenset({"churn_max_30d", "hotspot_ids_30d"})


def _for_manifest_compare(obj: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        k: v
        for k, v in obj.items()
        if k not in VOLATILE_KEYS and k not in GIT_DERIVED_ROOT_KEYS
    }
    nodes = out.get("nodes")
    if isinstance(nodes, list):
        out = dict(out)
        stripped_nodes: list[Any] = []
        for n in nodes:
            if isinstance(n, dict):
                stripped_nodes.append({k: v for k, v in n.items() if k != "churn_30d"})
            else:
                stripped_nodes.append(n)
        out["nodes"] = stripped_nodes
    return out


def _canonical(m: Dict[str, Any]) -> str:
    return json.dumps(_for_manifest_compare(m), sort_keys=True)


def main() -> int:
    if not COMMITTED.is_file():
        print(f"Missing {COMMITTED}", file=sys.stderr)
        return 1
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    r = subprocess.run(
        [sys.executable, str(EXTRACT), "--check-stdout"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout, file=sys.stderr)
        return 1
    fresh = json.loads(r.stdout)
    if _canonical(committed) != _canonical(fresh):
        print(
            "sprite-workbench-arch manifest drift: run\n"
            "  python3 scripts/extract_sprite_workbench_arch.py\n"
            "and commit artifacts/sprite-workbench-arch/manifest.json",
            file=sys.stderr,
        )
        return 1
    print("sprite-workbench-arch manifest: OK (matches extractor, volatile keys ignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
