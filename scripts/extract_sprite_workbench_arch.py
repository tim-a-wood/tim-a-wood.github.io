#!/usr/bin/env python3
"""Sprite workbench architecture manifest: script order, imports, optional exports, churn, JS refs.

Writes deterministic JSON to artifacts/sprite-workbench-arch/manifest.json.
See docs/sprite-workbench-architecture-visualization-plan.md §4.1 (I1) and §6.
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

# Heuristic top-level JS names (I1 — not ES modules; false positives/negatives possible).
JS_TOP_FUNCTION = re.compile(r"^(?:export\s+)?function\s+(\w+)\s*\(", re.MULTILINE)
JS_TOP_CLASS = re.compile(r"^\s*class\s+(\w+)\b", re.MULTILINE)
JS_TOP_CONST_FN = re.compile(
    r"^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>)",
    re.MULTILINE,
)
# String literals like './foo.js' referencing another workbench script (heuristic edge).
JS_LITERAL_REF = re.compile(r"['\"]\./([\w-]+\.js)['\"]")

EXTRACTOR_NAME = "extract_sprite_workbench_arch"
EXTRACTOR_VERSION = "0.2"
EXPORTS_CAP = 40
CHURN_DAYS_DEFAULT = 30


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


def _python_exports(py_path: Path) -> List[str]:
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    except (OSError, SyntaxError):
        return []
    names: List[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                names.append(node.name)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                names.append(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_"):
                    names.append(t.id)
    out = sorted(set(names))[:EXPORTS_CAP]
    return out


def _js_exports_heuristic(repo_root: Path, rel: str) -> List[str]:
    fpath = repo_root / rel
    if not fpath.is_file():
        return []
    try:
        text = fpath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    found: Set[str] = set()
    for rx in (JS_TOP_FUNCTION, JS_TOP_CLASS, JS_TOP_CONST_FN):
        for m in rx.finditer(text):
            found.add(m.group(1))
    out = sorted(found)[:EXPORTS_CAP]
    return out


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


def _js_literal_ref_edges(js_paths: List[str], repo_root: Path) -> List[Tuple[str, str]]:
    base_to_id: Dict[str, str] = {}
    for jp in js_paths:
        fn = jp.split("/")[-1]
        base_to_id[fn] = jp
    found: Set[Tuple[str, str]] = set()
    for src in js_paths:
        fpath = repo_root / src
        if not fpath.is_file():
            continue
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in JS_LITERAL_REF.finditer(text):
            fn = m.group(1)
            tgt = base_to_id.get(fn)
            if tgt and tgt != src:
                found.add((src, tgt))
    return sorted(found)


def _git_touch_counts(
    repo_root: Path, days: int, paths: Set[str]
) -> Dict[str, int]:
    try:
        r = subprocess.run(
            [
                "git",
                "log",
                "--since",
                f"{days} days ago",
                "--name-only",
                "--pretty=format:",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return {}
    counts: Dict[str, int] = {}
    for line in r.stdout.splitlines():
        line = line.strip().replace("\\", "/")
        if line in paths:
            counts[line] = counts.get(line, 0) + 1
    return counts


def build_manifest(
    *,
    html_path: Path,
    repo_root: Path,
    churn_days: int = CHURN_DAYS_DEFAULT,
) -> Dict[str, Any]:
    js_paths = _parse_browser_scripts(html_path)
    py_files = _scoped_python_files()
    py_ids: Set[str] = {_py_repo_rel(p) for p in py_files}

    churn_scope: Set[str] = set(js_paths) | py_ids
    churn = _git_touch_counts(repo_root, churn_days, churn_scope)

    nodes: List[Dict[str, Any]] = []
    for p in js_paths:
        exp = _js_exports_heuristic(repo_root, p)
        node: Dict[str, Any] = {
            "id": p,
            "path": p,
            "kind": "browser_js",
            "layer": _infer_js_layer(p),
            "exports": exp,
            "exports_kind": "js_heuristic",
            "churn_30d": churn.get(p, 0),
        }
        nodes.append(node)

    for p in sorted(py_files, key=lambda x: _py_repo_rel(x)):
        rel = _py_repo_rel(p)
        layer = "python_server" if p.name == "sprite_workbench_server.py" else "python_lib"
        exp = _python_exports(p)
        nodes.append(
            {
                "id": rel,
                "path": rel,
                "kind": "python",
                "layer": layer,
                "exports": exp,
                "exports_kind": "python_ast",
                "churn_30d": churn.get(rel, 0),
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

    for s, t in _js_literal_ref_edges(js_paths, repo_root):
        edges.append(
            {
                "id": f"js_static_ref:{s}->{t}",
                "source": s,
                "target": t,
                "kind": "js_static_ref",
            }
        )

    edges.sort(key=lambda e: (e["kind"], e["source"], e["target"]))

    max_churn = max((n.get("churn_30d") or 0) for n in nodes) if nodes else 0
    hot_ids = [n["id"] for n in nodes if (n.get("churn_30d") or 0) >= max(3, max_churn // 2) and max_churn > 0]

    return {
        "schema_version": "0.2",
        "extractor_versions": {EXTRACTOR_NAME: EXTRACTOR_VERSION},
        "git_sha": _git_head(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "churn_days": churn_days,
        "churn_max_30d": max_churn,
        "hotspot_ids_30d": sorted(hot_ids)[:12],
        "scope_note": "Browser: index.html script tags. Python: sprite_workbench_server.py + workbench_*.py. "
        "exports: python_ast (stdlib) vs js_heuristic (regex). js_static_ref: string literal ./file.js refs only.",
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
        "--churn-days",
        type=int,
        default=CHURN_DAYS_DEFAULT,
        help="Git touch window for churn_30d fields",
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

    manifest = build_manifest(
        html_path=html_path, repo_root=REPO_ROOT, churn_days=args.churn_days
    )
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    if args.check_stdout:
        sys.stdout.write(text)
        return 0

    out_path: Path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(
        f"Wrote {out_path} ({len(manifest['nodes'])} nodes, {len(manifest['edges'])} edges)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
