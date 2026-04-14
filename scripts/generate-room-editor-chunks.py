#!/usr/bin/env python3
"""Emit js/editor/chunk-*.js string arrays + load-chunks.js from room-layout-editor.html IIFE body."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "room-layout-editor.html"
OUT = ROOT / "js" / "editor"


def main() -> None:
    lines = HTML.read_text(encoding="utf-8").splitlines()
    # Inner body: after `(() => {` through line before closing `})();` (includes bootstrap + window.* exports)
    start = next(i for i, ln in enumerate(lines) if "(() => {" in ln) + 1
    close_i = next(i for i, ln in enumerate(lines) if ln.strip() == "})();")
    body_lines = lines[start:close_i]
    src = "\n".join(body_lines)

    # Namespace transforms (spec §2.3)
    src = re.sub(r"\bconst state = \{", "RoomEditor.State = {", src)
    src = re.sub(r"\bstate\.", "RoomEditor.State.", src)
    src = re.sub(r"\bconst ui = \{", "RoomEditor.Ui.refs = {", src)
    src = re.sub(r"\bui\.", "RoomEditor.Ui.refs.", src)

    # Predeclare namespace roots for load-time rule: only plain assignments (no outer reads at top of slices)
    preamble = (
        "globalThis.RoomEditor = globalThis.RoomEditor || {};\n"
        "globalThis.RoomEditor.Constants = globalThis.RoomEditor.Constants || {};\n"
        "globalThis.RoomEditor.State = globalThis.RoomEditor.State || {};\n"
        "globalThis.RoomEditor.Ui = globalThis.RoomEditor.Ui || { refs: null };\n"
    )

    blines = src.splitlines()
    blanks = [i for i, ln in enumerate(blines) if not ln.strip()]
    target = 2000
    splits = [0]
    pos = 0
    while pos + target < len(blines):
        goal = pos + target
        cand = next((b for b in blanks if b >= goal), len(blines) - 1)
        splits.append(cand + 1)
        pos = cand + 1
    splits.append(len(blines))

    OUT.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    for idx, (a, b) in enumerate(zip(splits, splits[1:])):
        chunk = "\n".join(blines[a:b])
        parts.append(chunk)
        chunk_js = (
            "'use strict';\n"
            "globalThis.__RoomEditorChunks = globalThis.__RoomEditorChunks || [];\n"
            f"globalThis.__RoomEditorChunks.push({json.dumps(chunk)});\n"
        )
        (OUT / f"chunk-{idx}.js").write_text(chunk_js, encoding="utf-8")

    prem_js = "'use strict';\n" + "".join(
        f"{line}\n"
        for line in preamble.strip().split("\n")
    )
    (OUT / "preamble.js").write_text(prem_js, encoding="utf-8")

    load_js = """'use strict';
(function () {
  const chunks = globalThis.__RoomEditorChunks || [];
  const src = "'use strict';\\n" + chunks.join("\\n");
  const run = new Function(src);
  run();
  globalThis.__RoomEditorChunks.length = 0;
})();
"""
    (OUT / "load-chunks.js").write_text(load_js, encoding="utf-8")

    print("Wrote", len(parts), "chunks; total body lines", len(blines))
    for i, p in enumerate(parts):
        print(f"  chunk-{i}.js payload lines: {len(p.splitlines())}")


if __name__ == "__main__":
    main()
