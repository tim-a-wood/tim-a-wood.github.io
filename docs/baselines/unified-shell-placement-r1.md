# Baseline: unified shell placement (R1 golden room)

**Status:** Locked after founder confirmation that runtime placement matches the footprint grid.

## What is baselined

1. **Hole geometry:** Largest 4-connected region of pixels with alpha &lt; 8 in the unified shell PNG (not the axis-aligned envelope of all transparent pixels).
2. **Chamber box:** Axis-aligned bounds from the layout polygon (`getRoomPolygonBounds` / `room-layout-data.json` R1).
3. **Placement:** Scale the full texture so that hole `(x,y,w,h)` maps linearly to the chamber AABB; `setOrigin(0,0)`; rounded `displayWidth`, `displayHeight`, room-local `localX`, `localY` before adding `roomBounds.start`.

## Machine-readable baseline

- `tests/fixtures/unified_shell_r1_placement_baseline.json` — expected hole bbox, chamber rect, and rounded placement for R1.

## Regression tests

- `tests/unified_shell_hole_baseline.test.py` — synthetic flood-fill smoke test (always runs in CI); optional check against the local R1 PNG when the file exists.

## Decisions

- §214 — hole-driven scale/offset vs full-frame stretch  
- §215 — largest connected transparent component (disconnected top sliver + opaque band on R1)

## Optional git tag

To mark the repo at this baseline for humans and bisect:

```bash
git tag -a baseline/unified-shell-r1-2026-04-12 -m "Unified shell: connected-component hole placement verified on R1"
git push origin baseline/unified-shell-r1-2026-04-12
```
