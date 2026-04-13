#!/usr/bin/env python3
"""One-off procedural generator: R1 background_far_plate at 1600x1200 with footprint mask."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

W, H = 1600, 1200

# Footprint from room-layout-data.json geometry_summary.polygon (8 vertices)
VERTS = [
    (160, 260),
    (900, 260),
    (900, 120),
    (1240, 120),
    (1240, 1080),
    (980, 1080),
    (980, 860),
    (160, 860),
]

# center_lane (416, 0, 768, 1200) — calm vertical band
LANE_X0, LANE_X1 = 416, 768
LANE_CX = (LANE_X0 + LANE_X1) / 2


def seg_dist(px: np.ndarray, py: np.ndarray, x1: float, y1: float, x2: float, y2: float) -> np.ndarray:
    """Distance from points to line segment (arrays px, py)."""
    vx, vy = x2 - x1, y2 - y1
    wx = px - x1
    wy = py - y1
    c1 = wx * vx + wy * vy
    c2 = vx * vx + vy * vy + 1e-9
    t = np.clip(c1 / c2, 0.0, 1.0)
    qx = x1 + t * vx
    qy = y1 + t * vy
    return np.sqrt((px - qx) ** 2 + (py - qy) ** 2)


def min_edge_distance(px: np.ndarray, py: np.ndarray) -> np.ndarray:
    d = np.full(px.shape, 1e9, dtype=np.float64)
    n = len(VERTS)
    for i in range(n):
        x1, y1 = VERTS[i]
        x2, y2 = VERTS[(i + 1) % n]
        d = np.minimum(d, seg_dist(px, py, x1, y1, x2, y2))
    return d


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / (edge1 - edge0 + 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def main() -> None:
    mask_img = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(mask_img)
    draw.polygon(VERTS, outline=255, fill=255)
    inside = np.array(mask_img, dtype=np.float64) > 127

    ys, xs = np.mgrid[0:H, 0:W].astype(np.float64)
    px, py = xs, ys

    d_edge = np.zeros((H, W), dtype=np.float64)
    d_edge[inside] = min_edge_distance(px[inside], py[inside])

    # Soft fade near footprint edge — avoid hard "lip"; push readable mass inward
    edge_soft = 1.0 - 0.42 * np.exp(-d_edge / 95.0)
    edge_soft = np.clip(edge_soft, 0.0, 1.0)
    edge_soft[~inside] = 0.0

    # Base stone noise (layered sin — parallax-friendly, no perspective convergence)
    n1 = np.sin(px / 38.0) * np.cos(py / 44.0)
    n2 = np.sin(px / 17.0 + py / 23.0) * 0.65
    n3 = np.sin(px / 91.0) * np.sin(py / 103.0)
    noise = 0.52 + 0.22 * n1 + 0.14 * n2 + 0.1 * n3

    # Side masses: heavier architecture in outer thirds; calmer center lane (darker mid)
    dist_from_lane = np.abs(px - LANE_CX)
    lane_mask = smoothstep(0.0, 190.0, dist_from_lane)  # 0 at lane center → 1 toward sides
    center_dim = 0.62 + 0.38 * lane_mask  # darker in center strip

    # Vertical "pillar / bay" rhythm — near-parallel verticals
    pillar = 0.88 + 0.12 * np.sin(px / 55.0 + np.sin(py / 120.0) * 0.4)
    pillar *= 0.92 + 0.08 * np.sin(py / 31.0)

    # Upper vault / ceiling mass — stays enclosed, no skylight
    vault = 1.0 - 0.18 * smoothstep(120.0, 420.0, py)
    vault *= 0.94 + 0.06 * np.sin(px / 70.0)

    # Floor damp / lower depth — structure still reads (not a bright fog bank)
    floor_grad = 0.78 + 0.22 * smoothstep(650.0, 1080.0, py)
    floor_detail = 0.97 + 0.03 * np.sin(px / 25.0) * np.cos(py / 18.0)

    # Far right recess (stepped region): subtle warm hint — not a centered gate spotlight
    far_gate = np.exp(-((px - 1120.0) ** 2) / (2 * 140.0**2)) * np.exp(-((py - 520.0) ** 2) / (2 * 380.0**2))
    warm_r = 18.0 * far_gate * inside.astype(np.float64)
    warm_g = 10.0 * far_gate * inside.astype(np.float64)

    # Distant arch mouths (side-weighted, not one giant center arch): depth via curved occlusion
    def arch_depth(cx: float, base_y: float, span: float, depth_amt: float) -> np.ndarray:
        # Semicircle above base_y: inside arch is "farther" (darker) — distance to arc
        half = span * 0.5
        rel_x = (px - cx) / (half + 1e-9)
        rel_x = np.clip(rel_x, -1.0, 1.0)
        arc_y = base_y - half * 0.84 * np.sqrt(np.maximum(0.0, 1.0 - rel_x * rel_x))
        inside_arch = py < arc_y
        d_arch = np.abs(py - arc_y)
        return np.where(inside_arch, depth_amt * np.exp(-d_arch / 28.0), 0.0)

    # Weight side arches to outer thirds only (no giant center nave)
    w_left = smoothstep(160.0, 520.0, px) * (1.0 - smoothstep(520.0, 680.0, px))
    w_right = smoothstep(880.0, 1040.0, px)
    arch_l = arch_depth(300.0, 740.0, 360.0, 0.24) * w_left
    arch_r = arch_depth(1160.0, 720.0, 280.0, 0.2) * w_right
    arch_mid = arch_depth(LANE_CX, 620.0, 180.0, 0.06)  # narrow distant recess only — subtle
    arch_depths = np.clip(1.0 - arch_l - arch_r - arch_mid, 0.35, 1.0)

    # Compose value channel (muted)
    lum = noise * pillar * vault * floor_grad * floor_detail * center_dim * edge_soft * arch_depths
    lum *= 0.92 + 0.08 * (0.85 + 0.15 * lane_mask)  # slight extra lift at sides

    # Cool-warm separation without neon accents
    base_b = 46.0 + 38.0 * lum
    base_g = 40.0 + 34.0 * lum
    base_r = 32.0 + 30.0 * lum
    base_r += warm_r
    base_g += warm_g * 0.5

    # Depth gradient: farther (top + right step) slightly cooler/darker
    depth = 0.85 + 0.15 * smoothstep(200.0, 1050.0, px) * 0.35 + 0.1 * smoothstep(100.0, 500.0, py)
    base_r *= depth
    base_g *= depth
    base_b *= depth * 1.04  # slight cool in recess

    base_r = np.clip(base_r, 0, 255)
    base_g = np.clip(base_g, 0, 255)
    base_b = np.clip(base_b, 0, 255)

    r = base_r.astype(np.uint8)
    g = base_g.astype(np.uint8)
    b = base_b.astype(np.uint8)

    alpha = (inside.astype(np.uint8) * 255)

    rgba = np.stack([r, g, b, alpha], axis=-1)
    out = Image.fromarray(rgba, mode="RGBA")

    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "/opt/cursor/artifacts/R1_background_far_plate_1600x1200.png"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, format="PNG", compress_level=6)
    print("Wrote", out_path, out.size)


if __name__ == "__main__":
    main()
