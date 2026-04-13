#!/usr/bin/env python3
"""
Baseline regression for unified shell interior-hole measurement and placement math.

Mirrors index.html:
- measureShellInteriorHoleBBoxFromTexture: alpha < 8, 4-connected components, largest by area
- computeUnifiedShellWorldPlacement (raw path): dw, dh, localX, localY with JS rounding order

CI: synthetic grid always runs. R1 PNG under tools/.../projects-data/ is gitignored; when Pillow
and that file exist locally, golden numbers from tests/fixtures/unified_shell_r1_placement_baseline.json
are asserted.
"""

from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "unified_shell_r1_placement_baseline.json"

THRESHOLD = 8


def largest_low_alpha_component_bbox(
    width: int, height: int, alpha_at) -> tuple[int, int, int, int, int] | None:
    """Return (min_x, min_y, max_x_inclusive, max_y_inclusive, area) or None."""
    visited = [[False] * width for _ in range(height)]
    best: tuple[int, int, int, int, int] | None = None
    for sy in range(height):
        for sx in range(width):
            if visited[sy][sx] or alpha_at(sx, sy) >= THRESHOLD:
                continue
            q = deque([(sx, sy)])
            visited[sy][sx] = True
            mix = miy = 10**9
            mxx = myy = -1
            area = 0
            while q:
                cx, cy = q.popleft()
                area += 1
                mix = min(mix, cx)
                miy = min(miy, cy)
                mxx = max(mxx, cx)
                myy = max(myy, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and not visited[ny][nx]:
                        if alpha_at(nx, ny) < THRESHOLD:
                            visited[ny][nx] = True
                            q.append((nx, ny))
            if area < 64:
                continue
            if best is None or area > best[4]:
                best = (mix, miy, mxx, myy, area)
    if best is None:
        return None
    return best


def placement_rounded(
    chamber_left: int,
    chamber_top: int,
    chamber_right: int,
    chamber_bottom: int,
    hole_x: int,
    hole_y: int,
    hole_w: int,
    hole_h: int,
    sw: int,
    sh: int,
) -> tuple[int, int, int, int]:
    cw = max(1, chamber_right - chamber_left)
    ch = max(1, chamber_bottom - chamber_top)
    dw = sw * cw / hole_w
    dh = sh * ch / hole_h
    lx = chamber_left - hole_x * (dw / sw)
    ly = chamber_top - hole_y * (dh / sh)
    return (
        max(1, round(dw)),
        max(1, round(dh)),
        round(lx),
        round(ly),
    )


def test_synthetic_disconnected_hole() -> None:
    """Two transparent blobs separated by an opaque row; largest must be the main void."""
    w, h = 24, 20
    alpha = [[255] * w for _ in range(h)]
    # Top sliver (disconnected)
    for y in range(3):
        for x in range(7):
            alpha[y][x] = 0
    # Opaque band y=3
    # Main hole x=4..23, y=4..19
    for y in range(4, h):
        for x in range(4, w):
            alpha[y][x] = 0

    def a_at(x: int, y: int) -> int:
        return alpha[y][x]

    got = largest_low_alpha_component_bbox(w, h, a_at)
    assert got is not None
    mix, miy, mxx, myy, area = got
    assert mix == 4 and miy == 4 and mxx == w - 1 and myy == h - 1
    assert area > 200


def test_r1_png_when_present() -> None:
    try:
        from PIL import Image
    except ImportError:
        print("SKIP R1 PNG: Pillow not installed")
        return

    png = (
        ROOT
        / "tools"
        / "2d-sprite-and-animation"
        / "projects-data"
        / "room-ai-helpfulness-qa-67562113"
        / "room_environment_assets"
        / "R1"
        / "bespoke"
        / "R1-room-shell.png"
    )
    if not png.is_file():
        print("SKIP R1 PNG: file not present (projects-data gitignored)")
        return

    with FIXTURE.open(encoding="utf-8") as f:
        baseline = json.load(f)

    im = Image.open(png).convert("RGBA")
    sw, sh = im.size
    px = im.load()

    def a_at(x: int, y: int) -> int:
        return px[x, y][3]

    got = largest_low_alpha_component_bbox(sw, sh, a_at)
    assert got is not None
    mix, miy, mxx, myy, area = got
    hole_w = mxx - mix + 1
    hole_h = myy - miy + 1

    exp = baseline["hole_largest_component_alpha_lt_8"]
    assert (mix, miy, hole_w, hole_h, area) == (
        exp["x"],
        exp["y"],
        exp["w"],
        exp["h"],
        exp["pixel_count"],
    ), f"hole bbox drift: got {(mix,miy,hole_w,hole_h,area)} expected {exp}"

    ch = baseline["layout"]["polygon_chamber_aabb_room_local_px"]
    L, T, R, B = ch["left"], ch["top"], ch["right"], ch["bottom"]
    dw, dh, lx, ly = placement_rounded(L, T, R, B, mix, miy, hole_w, hole_h, sw, sh)
    pexp = baseline["placement_set_origin_0_0_rounded_room_local_px"]
    assert (dw, dh, lx, ly) == (
        pexp["display_width"],
        pexp["display_height"],
        pexp["local_x"],
        pexp["local_y"],
    ), f"placement drift: got {(dw,dh,lx,ly)} expected {pexp}"


def main() -> None:
    test_synthetic_disconnected_hole()
    test_r1_png_when_present()
    print("unified_shell_hole_baseline: OK")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("FAIL:", e, file=sys.stderr)
        sys.exit(1)
