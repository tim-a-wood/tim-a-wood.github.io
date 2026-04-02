#!/usr/bin/env python3
"""Verify art bible swatch generator produces 12 PNGs with expected colors."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from PIL import Image
except ImportError:
    print("SKIP: Pillow not installed")
    sys.exit(0)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        r = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_art_bible_swatches.py"),
                "--out",
                str(out),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stderr
        pngs = sorted(out.glob("AH-*.png"))
        assert len(pngs) == 12, f"expected 12 swatches, got {len(pngs)}"
        ink0 = out / "AH-INK-0.png"
        im = Image.open(ink0).convert("RGB")
        assert im.size == (64, 64)
        assert im.getpixel((32, 32)) == (7, 9, 11), "AH-INK-0 should be #07090B"
    print("art_bible_swatches: ok")


if __name__ == "__main__":
    main()
