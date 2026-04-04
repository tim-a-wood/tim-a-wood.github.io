#!/usr/bin/env python3
"""P0 manifest: sprite workbench browser script order + scoped Python import edges.

Writes deterministic JSON to artifacts/sprite-workbench-arch/manifest.json.
See docs/sprite-workbench-architecture-visualization-plan.md §6.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HTML = REPO_ROOT / "tools" / "2d-sprite-and-animation" / "index.html"
DEFAULT_OUT = REPO_ROOT / "artifacts" / "sprite-workbench-arch" / "manifest.json"
SCRIPT_SRC_RE = re.compile(
    r'<script\s+src="(\./app/[^"?#]+\.js)"\s*>\s*</script>',
    re.IGNORECASE,
)

EXTRACTOR_NAME = "extract_sprite_workbench_arch"
EXTRACTOR_VERSION = "0.1"


def _git_head() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "0000000"


def _parse_browser_scripts(html_path: Path) -> List[str]:
    text = html_path.read_text(encoding="utf-8", errors="replace")
    rels: List[str] = []
    seen: Set[str] = set()
    for m in SCRIPT_SRC_RE.findall(text):
        rel_js = m[2:] if m.startswith("./") else m
        rel_js = rel_js.replace("\\", "/")
        rid = f"tools/2d-sprite-and-animation/{rel_js}"
        if rid in seen:
            continue
        seen.add(rid)
        rels.append(rid)
    return rels


def _infer_js_layer(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if name.endswith("-shell.js") or name == "product-shell.js":
        return "shell"
    if "runtime" in name:
        return "runtime"
    if "-stage.js" in name or name.endswith("stage.js"):
        return "stage"
    if "helper" in name or name in ("core-helpers.js", "editor-helpers.js"):
        return "helper"
    return "app"


def _scoped_python_files() -> List[Path]:
    scripts_dir = REPO_ROOT / "scripts"
    out = [scripts_dir / "sprite_workbench_server.py"]
    out.extend(sorted(scripts_dir.glob("workbench_*.py")))
    return [p for p in out if p.is_file()]


def _py_repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _path_for_scripts_submodule(name: str, py_ids: Set[str]) -> Optional[str]:
    base = name.split(".")[0]
    cand = f"scripts/{base}.py"
    return cand if cand in py_ids else None


def _python_import_edges(py_file: Path, py_ids: Set[str]) -> List[Tuple[str, str]]:
    src = _py_repo_rel(py_file)
    if src not in py_ids:
        return []
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except SyntaxError:
        return []

    edges: List[Tuple[str, str]] = []

    def add_edge(tgt: Optional[str]) -> None:
        if tgt and tgt in py_ids and tgt != src:
            edges.append((src, tgt))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top == "scripts":
                    continue
                if top.startswith("workbench_"):
                    add_edge(f"scripts/{top}.py")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module
            if node.level and node.level > 0:
                continue
            if mod is None:
                continue
            if mod == "scripts":
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    add_edge(_path_for_scripts_submodule(alias.name, py_ids))
            elif mod.startswith("scripts."):
                sub = mod[len("scripts.") :].split(".")[0]
                add_edge(_path_for_scripts_submodule(sub, py_ids))
            elif mod.startswith("workbench_"):
                add_edge(f"scripts/{mod.split('.')[0]}.py")

    return edges


def build_manifest(*, html_path: Path, repo_root: Path) -> Dict[str, Any]:
    js_paths = _parse_browser_scripts(html_path)
    py_files = _scoped_python_files()
    py_ids: Set[str] = {_py_repo_rel(p) for p in py_files}

    nodes: List[Dict[str, Any]] = []
    for p in js_paths:
        nodes.append(
            {
                "id": p,
                "path": p,
                "kind": "browser_js",
                "layer": _infer_js_layer(p),
            }
        )
    for p in sorted(py_files, key=lambda x: _py_repo_rel(x)):
        rel = _py_repo_rel(p)
        layer = "python_server" if p.name == "sprite_workbench_server.py" else "python_lib"
        nodes.append(
            {
                "id": rel,
                "path": rel,
                "kind": "python",
                "layer": layer,
            }
        )

    node_ids = {n["id"] for n in nodes}
    edges: List[Dict[str, Any]] = []
    eid = 0
    for i in range(len(js_paths) - 1):
        a, b = js_paths[i], js_paths[i + 1]
        edges.append(
            {
                "id": f"html_script_order:{eid}",
                "source": a,
                "target": b,
                "kind": "html_script_order",
            }
        )
        eid += 1

    py_edge_set: Set[Tuple[str, str]] = set()
    for pf in py_files:
        for s, t in _python_import_edges(pf, py_ids):
            if s in node_ids and t in node_ids:
                py_edge_set.add((s, t))
    for s, t in sorted(py_edge_set):
        edges.append(
            {
                "id": f"python_import:{s}->{t}",
                "source": s,
                "target": t,
                "kind": "python_import",
            }
        )

    edges.sort(key=lambda e: (e["kind"], e["source"], e["target"]))

    return {
        "schema_version": "0.1",
        "extractor_versions": {EXTRACTOR_NAME: EXTRACTOR_VERSION},
        "git_sha": _git_head(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope_note": "Browser: tools/2d-sprite-and-animation/index.html script tags. Python: scripts/sprite_workbench_server.py + scripts/workbench_*.py; imports to in-scope modules only.",
        "nodes": nodes,
        "edges": edges,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit sprite workbench architecture manifest.json")
    ap.add_argument(
        "--html",
        type=Path,
        default=DEFAULT_HTML,
        help="Path to sprite workbench index.html",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output manifest path",
    )
    ap.add_argument(
        "--check-stdout",
        action="store_true",
        help="Print JSON to stdout only (do not write file)",
    )
    args = ap.parse_args()

    html_path: Path = args.html
    if not html_path.is_file():
        print(f"Missing HTML: {html_path}", file=sys.stderr)
        return 1

    manifest = build_manifest(html_path=html_path, repo_root=REPO_ROOT)
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    if args.check_stdout:
        sys.stdout.write(text)
        return 0

    out_path: Path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path} ({len(manifest['nodes'])} nodes, {len(manifest['edges'])} edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
