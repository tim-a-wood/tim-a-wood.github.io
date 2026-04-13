#!/usr/bin/env python3
"""Procedural background_far_plate 1600x1200 — gothic hall far-depth, footprint alpha."""
from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image, ImageDraw

W, H = 1600, 1200

# 8-vertex walkable void (CCW) — stepped ceiling/floor per layout guide (locked shape).
VOID_POLY = [
    (144, 276),
    (1016, 276),
    (1016, 144),
    (1456, 144),
    (1456, 1056),
    (992, 1056),
    (992, 992),
    (144, 992),
]


def polygon_area(pts: list[tuple[int, int]]) -> float:
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def fbm(nx: np.ndarray, ny: np.ndarray, octaves: int = 4) -> np.ndarray:
    """Simple value noise stack for stone grain."""
    t = np.zeros_like(nx, dtype=np.float32)
    amp = 0.5
    f = 1.0
    for _ in range(octaves):
        t += amp * np.sin(f * nx * 6.2 + f * ny * 4.1) * np.sin(f * nx * 3.7 - f * ny * 5.3)
        amp *= 0.5
        f *= 2.0
    return t


def main() -> None:
    area = polygon_area(VOID_POLY)
    print(f"void polygon area={area:.0f} px² ({100 * area / (W * H):.1f}% of full canvas)")

    xs = np.arange(W, dtype=np.float32)
    ys = np.arange(H, dtype=np.float32)
    X, Y = np.meshgrid(xs, ys)

    # Normalized "room" coords (1080×960 chamber centered in 1600×1200)
    nx = (X - 800) / 540
    ny = (Y - 600) / 480

    # --- Far / mid value layers (orthographic: no vanishing point) ---
    far_plane = 20.0 + 3.0 * np.sin(nx * 0.8 + ny * 0.2)

    mid = 36.0
    # Continuous side-wall read (outer thirds)
    side_read = np.exp(-((np.abs(nx) - 0.68) ** 2) / 0.045)
    mid += 18.0 * np.clip(side_read, 0, 1)
    # Broken courses / horizontal breaks
    mid += 7.0 * np.sin(nx * 5.0 + np.sin(Y * 0.021) * 2.0)
    mid += 5.0 * np.sin(Y * 0.035 + nx * 2.0)

    # Center lane dim (416–1184 x full height): keep architecturally dark, no bloom
    cx = np.exp(-(nx**2) / 0.48)
    mid -= 22.0 * cx
    # Dark recessed corridor body in center — vertical stone striations, not empty fog
    mid += 8.0 * np.sin(nx * 7.0) * np.exp(-(nx**2) / 0.42) * (0.6 + 0.4 * np.abs(ny))

    # Column / pier rhythm (near-vertical, parallax-style)
    col = (X * 0.0175) % (2 * math.pi)
    pier = 11.0 * (0.55 + 0.45 * np.sin(col)) * np.exp(-((np.abs(ny) - 0.05) ** 2) / 0.55)
    pier *= 0.35 + 0.65 * np.clip(np.abs(nx), 0.15, 1.0)
    mid += pier

    # Multiple modest arch bands — avoid one dominant central gothic arch
    for k, phase in enumerate([-0.35, 0.05, 0.42]):
        ay = phase + 0.11 * np.sin(nx * (2.4 + k * 0.3))
        band = np.exp(-((ny - ay) ** 2) / 0.055) * (16.0 - k * 2.5)
        band *= 1.0 - 0.75 * cx * (1.0 if k != 1 else 0.5)
        mid += band

    # Floor dampness — lower values, structure still visible; no bright floor pool
    floor_t = np.clip((ny - 0.28) / 0.72, 0, 1)
    damp = (1.0 - floor_t) * 22.0
    damp *= 1.0 - 0.55 * cx
    mid += damp

    depth_mix = 0.38 + 0.22 * np.sin(nx * 0.85 + ny * 0.25)
    v = far_plane * (1.0 - depth_mix) + mid * depth_mix
    v = np.clip(v, 16, 92)

    grain = fbm(X * 0.004, Y * 0.004) * 5.5
    v = np.clip(v + grain, 12, 96)

    # Muted warm/cool separation (no cyan/teal accents)
    floor_t2 = np.clip((ny - 0.25) / 0.75, 0, 1)
    r = v + 3.5 * np.sin(nx * 0.45) + 2.5 * (1.0 - floor_t2)
    g = v + 1.8 * np.sin(ny * 0.35 + X * 0.008)
    b = v + 5.5 * (1.0 - 0.35 * depth_mix)

    r = np.clip(r, 8, 98).astype(np.uint8)
    g = np.clip(g, 8, 96).astype(np.uint8)
    b = np.clip(b, 10, 100).astype(np.uint8)

    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[..., 0] = r
    rgba[..., 1] = g
    rgba[..., 2] = b

    mask_img = Image.new("L", (W, H), 0)
    flat = [c for xy in VOID_POLY for c in xy]
    ImageDraw.Draw(mask_img).polygon(flat, fill=255)
    mask = np.array(mask_img) > 127
    rgba[..., 3] = np.where(mask, 255, 0)

    out_path = os.environ.get(
        "OUT", "/opt/cursor/artifacts/background_far_plate_gothic_hall_1600x1200.png"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(out_path, compress_level=6)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
