# Room Environment Pipeline — Background↔Shell Misalignment & Playtest Color Drift

**Status:** Draft (corrective-action-plan, ready-to-implement)
**Owners:** Sprite Workbench (asset pipeline), Ashen Hollow (runtime composite)
**Schema/version baselines:** Generation plan schema_version 1; bespoke_asset_manifest.schema_version 2.
**Reference project:** `ashen-sentinel-9ea9be55` Room R1.

---

## 1. Plain-English summary

There are two independent bugs in the room environment pipeline. Both look like compositing issues in playtest/preview but they live at different layers.

**Bug 1 — shell never reaches the room border (background leaks at corners and edges).**
The `room_shell_foreground` asset is generated at chamber size (1280×880 for R1 — the playable polygon AABB), not room size (1600×1200). The shell PNG draws a "perimeter band" inside its own canvas (≈106 px on a 1280×880 texture, computed by `_room_shell_band_px_for_size`). The runtime then measures the alpha hole and scales the texture so the hole fits the polygon. With a 1280×880 texture and a 1069×669 hole, the perimeter band scales up to ~21–34 px in room space, but the actual room border is 160 px on every side. The forest background fills the room (0,0)–(1600,1200) and shows through at every gap the shell can't reach. **Fix:** author the shell at room dimensions (1600×1200) with the alpha hole drawn directly at polygon coordinates (160,160)–(1440,1040). The runtime placement math (`computeUnifiedShellWorldPlacement`) then resolves to a clean 1:1 placement at (0,0)–(1600,1200).

**Bug 2 — playtest background looks washed-out / wrong color vs. the source PNG.**
In playtest, the bespoke background sprite is drawn at `alpha=0.4` over a black `<body>`, so 60% of the original color is replaced by black. The runtime-review (workbench preview) uses `alpha=0.72` for the same sprite, which is closer to the on-disk image but still dimmer. The disk asset is full intensity. **Fix:** when a bespoke background is present, render it at `alpha=1.0` in both playtest and runtime-review. The dimming was a hold-over from the procedural-only era, when the background was a stylization layer rather than the dominant biome read.

---

## 2. Evidence and root-cause numbers

### 2.1 Bug 1 — shell dimension mismatch

Shell asset on disk (`projects-data/ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell.png`):
- Size: 1280×880 (matches polygon AABB, not room).
- Largest transparent flood-fill component bbox: `(106, 106, 1174, 774)`, w=1069, h=669.
- Opaque pixels: 36.5%; transparent: 63.5%.

Manifest (`runtime-layout.json` → `rooms[0].environment.runtime.bespoke_asset_manifest.generation_plan` → `R1-room-shell`):
- `target_dimensions`: `{ width: 1280, height: 880 }`
- `placement`: `{ x: 800, y: 1040, display_width: 1280, display_height: 880, origin_x: 0.5, origin_y: 1 }`
- `local_geometry.chamber_*`: `left: 160, top: 160, width: 1280, height: 880`

Plan author (`sprite-workbench/scripts/room_environment_v3.py:411-450`):
- Uses `cw, ch` (chamber dims) for `target_dimensions` and `placement.display_*`. Background and midground correctly use room `width, height` at lines 367-396.

Punch-out math (`sprite-workbench/scripts/room_environment_system.py:5360-5402`):
- `_room_shell_band_px_for_size((1280,880))` → `pad = max(24, min(220, round(min(1280,880)*0.12))) = 106`.
- `_chamber_point_to_output_pixel` insets polygon points by `pad` from the texture edge, so polygon `(160,160)` lands at texture `(106,106)` and `(1440,1040)` lands at `(1174,774)` — exactly matching the measured alpha hole.

Runtime placement (`ashen-hollow/index.html:1779-1834` `computeUnifiedShellWorldPlacement`):
- `dw = sw * chamberW / hole.w = 1280 * 1280 / 1069 = 1532.6`
- `dh = sh * chamberH / hole.h = 880 * 880 / 669 = 1157.5`
- `localX = 160 - 106 * (1532.6/1280) = 33.1`
- `localY = 160 - 106 * (1157.5/880) = 20.6`
- Shell renders at `(33.1, 20.6)`–`(1565.7, 1178.1)`.
- Background sits at `(0,0)`–`(1600,1200)` (full room), so 21–34 px strips of background are visible past the shell on all four sides.

If the shell were authored at 1600×1200 with hole at `(160,160)`–`(1440,1040)` (`hole.x=160, hole.y=160, hole.w=1280, hole.h=880, sw=1600, sh=1200`):
- `dw = 1600 * 1280 / 1280 = 1600`, `dh = 1200 * 880 / 880 = 1200`.
- `localX = 160 - 160 * (1600/1600) = 0`, `localY = 160 - 160 * (1200/1200) = 0`.
- Shell renders at `(0,0)`–`(1600,1200)`. No gaps. **No runtime change needed.**

### 2.2 Bug 2 — playtest background alpha

`ashen-hollow/index.html:3033`:

```js
.setAlpha(RUNTIME_REVIEW_CAPTURE_MODE
    ? (composition.hasBespokeBackground ? 0.72 : 0.58)
    : (composition.hasBespokeBackground ? 0.4 : 0.5));
```

- Playtest path (`RUNTIME_REVIEW_CAPTURE_MODE=false`, bespoke present) → `alpha=0.4`. Composited over `<body style="background:#000">` (line 16) → ≈60% of color is replaced by black.
- Runtime-review path (bespoke present) → `alpha=0.72`. Closer to disk colors but still ≈28% darker.
- Disk asset (`R1-background.png`) is full saturation/intensity.

Feathers at lines 3040-3066 are already suppressed for bespoke shell rooms via `suppressBespokeFeathers = DISABLE_UNIFIED_SHELL_RUNTIME_OVERLAYS && composition.hasBespokeBackground` (line 3011, with `DISABLE_UNIFIED_SHELL_RUNTIME_OVERLAYS=true` at line 50). They are not the cause of the color drift in this room.

> **Note for implementer:** the user's screenshot 2 (playtest) was not provided in the request. The `alpha=0.4` finding above fully explains a darker / washed-out playtest read relative to the disk PNG. If implementing reveals additional drift (hue shift not explained by black-blend), add a line-3033-only experiment with `alpha=1.0` and inspect a fresh playtest before chasing further causes.

---

## 3. Corrective actions

Two independent change-sets. They can land in either order. Bug 1 is multi-file pipeline work; Bug 2 is a one-line runtime change.

### 3.1 Bug 1 — author shell at room size

**Goal:** every `room_shell_foreground` asset is generated at room dimensions (e.g., 1600×1200), with the alpha hole drawn at the polygon's actual room-coordinate location, with no `pad`-inset mapping.

#### 3.1.1 File — `sprite-workbench/scripts/room_environment_v3.py`

Locate `build_generation_plan` (starts at line 306). Find the unified-chamber branch at lines 410-450 (`if unified_chamber:`).

Replace the `append_slot(...)` call for the shell (lines 423-450) with the room-sized variant below. Keep `local_geometry` populated with `chamber_*` so downstream punch-out and contract-mask code can still read polygon-in-room coordinates.

```python
append_slot(
    f"{room_id}-room-shell",
    "room_shell_foreground",
    "walls",
    {"width": width, "height": height},
    {
        "x": int(width / 2),
        "y": height,
        "display_width": width,
        "display_height": height,
        "origin_x": 0.5,
        "origin_y": 1,
    },
    "full",
    "stretch",
    "foreground",
    [shell_lane],
    {
        "room_width": width,
        "room_height": height,
        "chamber_left": cl,
        "chamber_top": ct,
        "chamber_width": cw,
        "chamber_height": ch,
    },
    border_treatment="unified_chamber_shell",
    transparency_mode="alpha",
)
```

No other behavior in this file changes. Background and midground continue to use room `width, height`.

#### 3.1.2 File — `sprite-workbench/scripts/room_environment_system.py`

The polygon-to-texture mapping currently insets by `pad` from the texture edge (line 5277-5278 in `_chamber_point_to_output_pixel`). With a room-sized texture, polygon points must map to their actual room-pixel coordinates so the alpha hole lands at the polygon AABB.

Update `_chamber_point_to_output_pixel` (lines 5262-5281) to support a "room-native" mode driven by geometry. Choose the mode by checking `geometry["room_width"]` / `geometry["room_height"]` against the texture size at the call site, not via a new public flag.

Find every caller of `_geometry_footprint_polygon_output_pixels` (grep for it — lines ~5417, 5511, 5709, 5735, 5762, 5788, 5814, 5933) and apply the rule below at the helper:

- **If** `out_w == int(geometry["room_width"])` **and** `out_h == int(geometry["room_height"])` (room-native texture): map polygon points by identity — `nx = px`, `ny = py`. `pad` is ignored for placement; it is still used by callers that need a band thickness for the surrounding band mask.
- **Else** (legacy chamber-sized texture, kept for back-compat with already-generated assets and procedural fallbacks): keep the current pad-inset mapping.

Concrete edit to `_chamber_point_to_output_pixel`:

```python
def _chamber_point_to_output_pixel(
    x: float,
    y: float,
    left: float,
    top: float,
    chamber_w: float,
    chamber_h: float,
    out_w: int,
    out_h: int,
    pad: int,
    *,
    room_w: Optional[float] = None,
    room_h: Optional[float] = None,
) -> Tuple[float, float]:
    if chamber_w <= 0 or chamber_h <= 0:
        return float(pad), float(pad)
    if (
        room_w is not None
        and room_h is not None
        and abs(out_w - int(room_w)) <= 1
        and abs(out_h - int(room_h)) <= 1
    ):
        return float(x), float(y)
    inner_w = max(1, out_w - (pad * 2))
    inner_h = max(1, out_h - (pad * 2))
    nx = ((float(x) - left) / chamber_w) * inner_w + pad
    ny = ((float(y) - top) / chamber_h) * inner_h + pad
    return nx, ny
```

Update `_geometry_footprint_polygon_output_pixels` (lines 5370-5402) to forward `room_w`/`room_h` from `geometry`:

```python
def _geometry_footprint_polygon_output_pixels(
    geometry: Dict[str, Any],
    out_w: int,
    out_h: int,
    pad: int = 24,
    interior_inset_px: int = 0,
) -> List[Tuple[int, int]]:
    poly_src = geometry.get("polygon") or []
    if not isinstance(poly_src, list) or len(poly_src) < 3:
        return []
    if out_w < 64 or out_h < 64:
        return []
    left = float(geometry.get("left") or 0.0)
    top_g = float(geometry.get("top") or 0.0)
    chamber_w = float(geometry.get("chamber_width") or 0.0)
    chamber_h = float(geometry.get("chamber_height") or 0.0)
    if chamber_w <= 1.0 or chamber_h <= 1.0:
        return []
    room_w = float(geometry.get("room_width") or 0.0) or None
    room_h = float(geometry.get("room_height") or 0.0) or None
    points: List[Tuple[int, int]] = []
    for pt in poly_src:
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            continue
        nx, ny = _chamber_point_to_output_pixel(
            float(pt[0]), float(pt[1]), left, top_g, chamber_w, chamber_h,
            out_w, out_h, pad, room_w=room_w, room_h=room_h,
        )
        points.append((int(round(nx)), int(round(ny))))
    if len(points) < 3:
        return []
    if interior_inset_px > 0:
        points = _inset_polygon_vertices_toward_centroid(points, float(interior_inset_px))
    if len(points) < 3:
        return []
    return points
```

Verify `_room_geometry(room)` (search for its definition; it builds the dict consumed at lines 12116-12117 and 5417) populates `room_width` and `room_height`. If it does not, add them — they must be the room size, not the chamber size. They are also already present in the slot's `local_geometry` per §3.1.1.

`_room_shell_band_px_for_size` (lines 5692-5695) keeps its current "% of min dimension" behavior. For room-size 1600×1200 it produces `pad=144`. The band mask (`_room_shell_silhouette_band_mask` line 5726) already grows the polygon outward with a `MaxFilter` kernel of `(band_px*2)+1`, so the surrounding band naturally fills the room border on a room-sized texture (band overshoots ~144 px past the polygon, which exceeds the 160 px border requirement; clip with the canvas bbox is automatic via `Image.filter`).

If validators report new failures around `pad` semantics on room-sized textures, the most likely fix is to clamp the band to the polygon→room-edge thickness explicitly:

```python
band_px = min(
    int(geometry.get("left") or 0),
    int(geometry.get("top") or 0),
    int((geometry.get("room_width") or out_w) - (geometry.get("left") or 0) - (geometry.get("chamber_width") or 0)),
    int((geometry.get("room_height") or out_h) - (geometry.get("top") or 0) - (geometry.get("chamber_height") or 0)),
)
```

Apply this clamp inside `_room_shell_silhouette_band_mask` only when `out_w == room_w and out_h == room_h`.

#### 3.1.3 File — `sprite-workbench/scripts/room_environment_system.py` (Gemini contract update)

The shell prompt at lines ~4500-4574 currently describes a chamber-perimeter atlas. The wording "1600x1200" is already used for chamber sizing in some prompts. Update the shell prompt header to make the new contract explicit:

- **Canvas size:** "Generate at exactly 1600×1200 pixels (the full room canvas, not the chamber)."
- **Hole position:** "The walkable chamber opening must occupy the rectangle (160,160) to (1440,1040) within the canvas. Pixels inside this rectangle must be transparent (alpha = 0). Stone/masonry shell band must completely cover the rectangle outside the opening, including all four corners and the full room border."
- **Pull the exact polygon coordinates from `geometry["polygon"]`** when generating the prompt for non-rectangular footprints, so the contract image and the prompt language agree.

Mechanically: in the prompt-builder for `room_shell_foreground`, after computing `expected_size` (line 11955), substitute `polygon`, `chamber_*`, and `room_*` from the slot's `local_geometry` into the prompt template.

The reference images (`_room_shell_reference_guide`, `_write_room_shell_contract_map_reference`, `_write_bespoke_room_silhouette_reference`) already use `_geometry_footprint_polygon_output_pixels`, so the §3.1.2 helper change makes them produce the correct hole at room coordinates with no further edit.

#### 3.1.4 File — `sprite-workbench/scripts/room_environment_system.py` (validators)

`_validate_room_shell_before_punchout` (line 5646) and `_validate_room_shell_after_punchout` (line 5501) check `image.size != expected_size`. With the new `target_dimensions = (1600, 1200)`, `expected_size` already becomes `(1600, 1200)` because line 11955 reads `entry["target_dimensions"]`. No code change required, but re-run them mentally against the new size to confirm the corner-box / band coverage thresholds are still passable for room-sized inputs.

Specifically, in `_room_shell_required_corner_boxes` (line 5698), the `corner_boxes` are normalized 0..1 over the texture. They are still meaningful for room-sized output. No change.

#### 3.1.5 File — `ashen-hollow/index.html`

No code change required.

`computeUnifiedShellWorldPlacement` (lines 1779-1834) already supports both modes. With a room-sized texture and a room-coordinate hole, the math resolves to `dw=room_w, dh=room_h, localX=0, localY=0`, which is the desired placement.

`hashRoomFootprintForShellPremask` (line 1585), `getOrCreatePremaskedShellTexture` (line 1610), and `measureShellInteriorHoleBBoxFromTexture` (line 1666) are texture-size-agnostic and continue to work.

#### 3.1.6 File — `sprite-workbench/scripts/room_environment_v3.py` (back-compat & migration)

Existing projects on disk already have `R1-room-shell.png` at 1280×880. After the §3.1.1 change, the schema fingerprint for that slot changes (`target_dimensions` differs from disk). Force regeneration:

1. In the bespoke-asset-manifest staleness check (search for `stale_components` and `component_fingerprints` in `room_environment_system.py`), include `target_dimensions` in the fingerprint input for `room_shell_foreground`. If it is already included via plan-fingerprint hashing, no edit is needed.
2. Add a one-time invalidator: when the manifest is rebuilt and the disk shell PNG dimensions don't match the slot's new `target_dimensions`, mark the slot stale and queue regeneration.

Provide a manual fall-back path for projects already in flight — a CLI step that deletes `room_environment_assets/<room>/bespoke/<room>-room-shell.png` and re-runs the bespoke build. Document this in `docs/plans/room-bespoke-pipeline-void-and-alignment.md` (existing doc, append a "Migration" section).

#### 3.1.7 Tests

In `ashen-hollow/tests/`:

- `room-wizard-overlay-alignment.test.js` — extend with a fixture room whose `room_shell_foreground` asset is room-sized with a polygon-coordinate hole. Assert `computeUnifiedShellWorldPlacement` returns `{dw: roomW, dh: roomH, localX: 0, localY: 0}`.
- `room-wizard-environment.test.js` — assert that for a project with `target_dimensions = roomSize`, the staleness check considers the existing chamber-sized PNG stale.

In `sprite-workbench/`:

- Add a unit test for `_geometry_footprint_polygon_output_pixels` that, given a room-sized output and matching `geometry["room_width"]`/`room_height`, returns the polygon points unchanged.
- Add a unit test for `_apply_walkable_interior_punchout` that, given a 1600×1200 input with full-opaque alpha and a polygon at (160,160)–(1440,1040), produces output where every pixel inside the polygon is `alpha=0` and every pixel outside is `alpha>0`.

#### 3.1.8 Acceptance criteria for Bug 1

- New asset `R1-room-shell.png` for `ashen-sentinel-9ea9be55` is 1600×1200.
- Largest transparent flood-fill component bbox in that asset is `(160,160)`–`(1440,1040)` (within ±2 px tolerance for AA).
- In the workbench room-build preview (capture mode) and in `index.html` playtest, **no background pixels are visible past the shell at any of the four edges**. Inspect by overlaying a 1-px bright magenta border on the shell at runtime (debug-only flag `?shellOutline=1`) and confirming it sits exactly at the room edge.
- `runtime-review.png` for R1 (same project) reproduces the user's expected look (mossy roots/stone frame fully covering room border; brick-portal forest visible only inside the polygon).

---

### 3.2 Bug 2 — playtest background color

#### 3.2.1 File — `ashen-hollow/index.html`

Single-line change at line 3033. Replace:

```js
.setAlpha(RUNTIME_REVIEW_CAPTURE_MODE ? (composition.hasBespokeBackground ? 0.72 : 0.58) : (composition.hasBespokeBackground ? 0.4 : 0.5));
```

with:

```js
.setAlpha(composition.hasBespokeBackground ? 1.0 : (RUNTIME_REVIEW_CAPTURE_MODE ? 0.58 : 0.5));
```

Rationale: bespoke backgrounds are the room's authoritative biome layer at full intensity (this is what the AI generated, the founder approved, and the disk PNG holds). Procedural backgrounds keep their original 0.5/0.58 dimming because they were authored to be a stylization layer over a black canvas.

No other lines change. Feather sprites are already suppressed for bespoke shell rooms via `suppressBespokeFeathers` (line 3011); no edit needed there. Midground is already disabled at runtime via `DISABLE_RUNTIME_MIDGROUND = true` (line 47).

#### 3.2.2 Tests

- `ashen-hollow/tests/room-wizard-environment.test.js` — assert that for a room with `composition.hasBespokeBackground === true`, the background sprite alpha equals `1.0` regardless of `RUNTIME_REVIEW_CAPTURE_MODE`.
- `ashen-hollow/tests/room-wizard-results-contract.test.js` — if it currently snapshots the runtime-review PNG output, regenerate the baseline snapshots after this change. Background pixels in the snapshot should match the disk asset (sample 8 reference points across the central 60% of the room and assert RGB delta < 8 per channel).

#### 3.2.3 Acceptance criteria for Bug 2

- In playtest, sample the central pixel `(800, 600)` of room R1 and compare to the same pixel in `R1-background.png`. RGB channel delta ≤ 4 per channel after the runtime composites the background.
- In runtime-review preview, the same delta holds.
- Visual confirmation: open `?room=R1` in playtest and the workbench room-build preview side-by-side; the central forest scene reads the same color in both.

---

## 4. Implementation order

1. **Bug 2 first** — single-line change, instant visual confirmation, isolates the color question from the geometry question.
   - Edit `ashen-hollow/index.html:3033`.
   - Reload playtest at `R1`; compare central pixel to `R1-background.png`.
   - Update / regenerate snapshot tests.
   - Commit.
2. **Bug 1** — multi-file pipeline change.
   - Edit `room_environment_v3.py` (§3.1.1).
   - Edit `room_environment_system.py` helpers (§3.1.2).
   - Adjust prompt builder (§3.1.3) and add migration/invalidation hooks (§3.1.6).
   - Add tests (§3.1.7).
   - Trigger regeneration of `R1-room-shell.png` for `ashen-sentinel-9ea9be55`. Verify hole bbox.
   - Open the room-build preview; verify no background leaks past shell edges.
   - Commit (one PR per repo: sprite-workbench then ashen-hollow if needed; orchestrator submodule bump after).

Cross-product changes follow the orchestrator rule in `MV/CLAUDE.md`: land submodule changes first, then bump submodule pointers in one orchestrator commit.

---

## 5. Out of scope

- Procedural (non-bespoke) background rendering — Bug 2 only changes the bespoke branch.
- Midground rendering — currently runtime-disabled via `DISABLE_RUNTIME_MIDGROUND`.
- Shell material/tone normalization (`_normalize_room_shell_tone`, `_enhance_room_shell_micro_detail`) — they already operate on whatever canvas the punch-out produced. Verify outputs after §3.1 lands; do not pre-emptively retune.
- The "feather stack" — already suppressed for bespoke rooms by `DISABLE_UNIFIED_SHELL_RUNTIME_OVERLAYS=true`.
- Other rooms in other projects — the same fix applies but verify per-project after rollout (each project's bespoke shell PNG must be regenerated at room size).

---

## 6. Open question for review (not blocking)

The user's reference to "screenshot 2" (playtest color comparison) was not attached to the request. The `alpha=0.4` finding in §2.2 fully explains a darker / desaturated playtest read versus the disk PNG, and the §3.2.1 fix addresses that. If after applying the fix a hue mismatch (not just brightness) remains, capture a fresh playtest screenshot of R1, sample the central pixel, and compare to `R1-background.png` at the same coordinate; report the per-channel deltas before further investigation.
