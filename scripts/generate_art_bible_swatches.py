#!/usr/bin/env python3
"""Emit 64x64 PNG swatches for Ashen Hollow art bible palette tokens."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

# Must match artifacts/ashen-hollow-art-bible-v0.2.md §2.1
TOKENS: dict[str, str] = {
    "AH-INK-0": "#07090B",
    "AH-INK-1": "#0D1115",
    "AH-ASH-2": "#1A2127",
    "AH-ASH-3": "#2B343B",
    "AH-BONE-4": "#4B5A63",
    "AH-FOG-5": "#7E8E95",
    "AH-EMBER-6": "#A85B32",
    "AH-RUST-7": "#7C3D2B",
    "AH-VERDIGRIS-8": "#2D6662",
    "AH-GLINT-9": "#9FD6C7",
    "AH-TOXIC-10": "#6E8F2E",
    "AH-ROYAL-11": "#5A4E87",
}


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out",
        type=Path,
        default=Path("artifacts/art-bible/swatches"),
        help="Output directory for PNG swatches",
    )
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    size = 64
    for name, hx in TOKENS.items():
        img = Image.new("RGB", (size, size), _hex_to_rgb(hx))
        img.save(args.out / f"{name}.png", "PNG")
    print(f"Wrote {len(TOKENS)} swatches to {args.out}")


if __name__ == "__main__":
    main()
