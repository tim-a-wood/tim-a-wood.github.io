# Room Environment Spec — Halve Unified Shell Thickness

**Status:** Ready to implement  
**Owner:** Sprite Workbench + Ashen Hollow runtime integration  
**Scope:** Unified bespoke shell (`room_shell_foreground`) only  
**Outcomes:** 50% thinner shell ring, preserved gameplay alignment, preserved manifest/runtime consistency

---

## 1) Decision Contract (No Ambiguity)

This spec defines **"halve shell thickness"** as:

1. **Generation contract thickness** is reduced by exactly **50%** for unified shell guidance and mask construction.
2. **Runtime side-collider lip derived from shell width** is reduced by exactly **50%**.
3. **Gameplay footprint polygon stays unchanged** (no level-geometry rewrite).
4. **No edits to non-shell asset families** (`background_far_plate`, `midground_side_frame`, legacy `foreground_frame` validation for non-shell paths, etc.).

If any implementation detail conflicts with these four points, this section wins.

---

## 2) Current State and Target State

### 2.1 Current shell-thickness drivers

- `sprite-workbench/scripts/room_environment_system.py`
  - `FOREGROUND_FRAME_BORDER_TOP_PX = 720`
  - `FOREGROUND_FRAME_BORDER_BOTTOM_PX = 360`
  - `FOREGROUND_FRAME_BORDER_SIDE_PX = 672`
  - `_room_shell_band_px_for_size(...)` uses `0.12 * min(width, height)` with clamp `24..220`.
  - Room-shell prompt text hardcodes thickness language (`~16-24% side`, `~18-28% top`, `~14-22% bottom`).
- `ashen-hollow/index.html`
  - `SHELL_UNIFIED_SIDE_COLLIDER_SIDE_PX = 672` (runtime collider lip derivation).

### 2.2 Required target values

Introduce dedicated unified-shell constants (do **not** reuse legacy foreground constants for this change):

- `ROOM_SHELL_BORDER_TOP_PX = 360`
- `ROOM_SHELL_BORDER_BOTTOM_PX = 180`
- `ROOM_SHELL_BORDER_SIDE_PX = 336`
- `ROOM_SHELL_BAND_SCALE = 0.06` (from `0.12`)
- `ROOM_SHELL_BAND_MIN_PX = 12` (from `24`)
- `ROOM_SHELL_BAND_MAX_PX = 110` (from `220`)

Runtime collider constant target:

- `SHELL_UNIFIED_SIDE_COLLIDER_SIDE_PX = 336` (from `672`)

---

## 3) Impact Matrix

### 3.1 Generation / Prompting (high impact)

**Files**
- `sprite-workbench/scripts/room_environment_system.py`

**Impacts**
- Shell prompt thickness clauses must be halved and expressed from new shell constants.
- Retry prompts that interpolate border px/% must use the new shell constants (not `FOREGROUND_FRAME_*`).
- Spatial contract/mask references must reflect thinner shell band.

### 3.2 Alpha/punchout and mask geometry (high impact)

**Files**
- `sprite-workbench/scripts/room_environment_system.py`

**Impacts**
- `_room_shell_band_px_for_size(...)` must use `ROOM_SHELL_BAND_*` values.
- `_room_shell_silhouette_band_mask(...)` must consume the new band size.
- `_write_bespoke_room_silhouette_reference(...)` should render thinner occupied shell band.

### 3.3 Runtime placement and collisions (high impact)

**Files**
- `ashen-hollow/index.html`

**Impacts**
- `computeUnifiedShellWorldPlacement(...)` still valid (hole fitting remains required).
- `addRoomBespokeShellInteriorSideColliders(...)` lip width derivation must halve by changing `SHELL_UNIFIED_SIDE_COLLIDER_SIDE_PX`.
- Must verify player cannot clip into masonry after thickness reduction.

### 3.4 Validation gates (medium impact)

**Files**
- `sprite-workbench/scripts/room_environment_system.py`

**Impacts**
- Post-punchout shell validators tuned for thicker bands may over-fail thinner output.
- Any validator thresholds changed in this task must be documented inline with rationale.
- Do not weaken unrelated foreground/border validators unless they block this exact contract.

### 3.5 Manifest and canonical sync (high impact)

**Files**
- Project runtime layout: `sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_layout.json`
- Canonical layout: `sprite-workbench/room-layout-data.json`

**Impacts**
- New regen attempt prompt text must show halved thickness clauses.
- `generation_plan` and `assets` dimensions/placement remain room-sized (`1600x1200`, `(800,1200)`).
- `attempts[-1]` provenance must be current-run.

### 3.6 Tests (required)

**Files**
- `sprite-workbench/tests/test_room_layout_manifest_shell.py`
- `ashen-hollow/tests/room_environment_system.test.py` (only if existing shell prompt/validator expectations break)
- `tests/test_report.md`

---

## 4) Exact Implementation Steps

## 4.1 Add shell-specific thickness constants

In `sprite-workbench/scripts/room_environment_system.py`, add:

- `ROOM_SHELL_BORDER_TOP_PX = 360`
- `ROOM_SHELL_BORDER_BOTTOM_PX = 180`
- `ROOM_SHELL_BORDER_SIDE_PX = 336`
- `ROOM_SHELL_BAND_SCALE = 0.06`
- `ROOM_SHELL_BAND_MIN_PX = 12`
- `ROOM_SHELL_BAND_MAX_PX = 110`

Do **not** overwrite `FOREGROUND_FRAME_BORDER_*` in this spec; keep legacy foreground-frame behaviors stable.

## 4.2 Rewire shell-only code paths to new constants

In `sprite-workbench/scripts/room_environment_system.py`:

1. `_room_shell_band_px_for_size(...)`
   - Replace formula with:
     - `band_px = round(min(out_w, out_h) * ROOM_SHELL_BAND_SCALE)`
     - clamp to `[ROOM_SHELL_BAND_MIN_PX, ROOM_SHELL_BAND_MAX_PX]`
2. Room-shell prompt builder (`_build_bespoke_prompt_room_shell_foreground`)
   - Replace static thickness language with these **exact** ranges (verbatim):
     - `THICKNESS CONTRACT: inside the shell band only, keep a broad structural shell read (not a hairline outline): aim for roughly ~8-12% of image width per side band and ~9-14% top / ~7-11% bottom where the contract allows —`
   - Do not use alternate wording like "about half" or "approximately half" in code.
   - Keep all other contract clauses unchanged.
3. Retry prompt builder (`_retry_prompt_for_validation_errors`, `room_shell_foreground` branch)
   - Replace `FOREGROUND_FRAME_BORDER_*` references with `ROOM_SHELL_BORDER_*`.

## 4.3 Runtime side-collider halving

In `ashen-hollow/index.html`:

- Set `SHELL_UNIFIED_SIDE_COLLIDER_SIDE_PX = 336`.
- Leave `SHELL_UNIFIED_SIDE_COLLIDER_BAND_USE`, min/max clamps unchanged for first pass.

If collision tests fail, adjust `SHELL_UNIFIED_SIDE_COLLIDER_BAND_USE` only in a follow-up patch in the same task, documenting before/after values.

## 4.4 Regenerate and republish shell

1. Restart workbench server.
2. Regenerate `R1-room-shell` for project `ashen-sentinel-9ea9be55`.
3. Sync project layout to canonical `sprite-workbench/room-layout-data.json`.
4. Ensure manifest reflects latest attempt and prompt content.

---

## 5) Acceptance Criteria (Must All Pass)

### A.1 Prompt and provenance

- Latest `R1-room-shell` attempt is from current run and has non-null timestamps.
- Prompt includes the same required canvas/opening contract lines as current staleness plan, plus **halved thickness wording**.

### A.2 Geometry and dimensions

- Raw PNG and final PNG remain `1600x1200`.
- `generation_plan` and `assets` placement/dimensions remain room-sized (`x=800,y=1200,display=1600x1200`).
- `walkable_shell_interior` remains aligned to the room polygon AABB contract.

### A.3 Thickness reduction check (objective)

Define shell-band occupancy metric on the contract band (outside opening, within band mask):

- Baseline artifact is pinned to:
  - `sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell.pre-thin-baseline.png`
- Candidate artifact is:
  - `sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell.png`
- Compute opaque pixel count in band for baseline and candidate using the canonical script in §6.
- Post-change must be within **45%–55%** of baseline occupancy for the same room (`R1`), excluding transparent opening.

### A.4 Runtime collision safety

- Player cannot visually overlap shell masonry on left/right interior boundaries in playtest.
- No new "invisible wall" felt deeper than one tile from visible shell edge.

### A.5 No unintended collateral

- Background/midground manifest entries unchanged.
- Non-shell template validation tests not regressed.

---

## 6) Verification Script Pack

Run from repo root after implementation.

```bash
# 1) Verify shell constants are halved and decoupled
python3 - <<'PY'
from pathlib import Path
p = Path("sprite-workbench/scripts/room_environment_system.py").read_text(encoding="utf-8")
for needle in (
    "ROOM_SHELL_BORDER_TOP_PX = 360",
    "ROOM_SHELL_BORDER_BOTTOM_PX = 180",
    "ROOM_SHELL_BORDER_SIDE_PX = 336",
    "ROOM_SHELL_BAND_SCALE = 0.06",
    "ROOM_SHELL_BAND_MIN_PX = 12",
    "ROOM_SHELL_BAND_MAX_PX = 110",
):
    assert needle in p, f"missing {needle}"
print("constants OK")
PY

# 2) Verify runtime collider constant halved
python3 - <<'PY'
from pathlib import Path
p = Path("ashen-hollow/index.html").read_text(encoding="utf-8")
assert "const SHELL_UNIFIED_SIDE_COLLIDER_SIDE_PX = 336;" in p
print("runtime collider constant OK")
PY

# 3) Manifest + prompt freshness
python3 - <<'PY'
import json
d=json.load(open("sprite-workbench/room-layout-data.json"))
rooms=d.get("rooms") or d["layout"]["rooms"]
r1=rooms["R1"] if isinstance(rooms,dict) else next(r for r in rooms if r["id"]=="R1")
m=r1["environment"]["runtime"]["bespoke_asset_manifest"]
shell=m["assets"]["R1-room-shell"]
a=shell["attempts"][-1]
assert a.get("started_at") and a.get("ended_at")
prompt=a["prompt"]
for s in (
    "Canvas size contract: generate exactly 1600x1200 pixels",
    "Output one image at exactly 1600×1200 px.",
):
    assert s in prompt
print("manifest/prompt OK")
PY

# 4) Thickness occupancy ratio against pinned baseline
python3 - <<'PY'
from PIL import Image
from pathlib import Path

baseline = Path("sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell.pre-thin-baseline.png")
candidate = Path("sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell.png")
assert baseline.exists(), f"missing baseline artifact: {baseline}"
assert candidate.exists(), f"missing candidate artifact: {candidate}"

def band_opaque_count(path: Path) -> int:
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    alpha = im.split()[-1].load()
    # R1 polygon AABB contract for shell opening.
    cl, ct, cw, ch = 160, 120, 1080, 960
    left, right = cl, cl + cw
    top, bottom = ct, ct + ch
    count = 0
    for y in range(h):
        for x in range(w):
            in_opening = (left <= x < right) and (top <= y < bottom)
            if in_opening:
                continue
            if alpha[x, y] > 0:
                count += 1
    return count

b = band_opaque_count(baseline)
c = band_opaque_count(candidate)
ratio = c / max(1, b)
print("baseline_opaque", b, "candidate_opaque", c, "ratio", round(ratio, 4))
assert 0.45 <= ratio <= 0.55, f"expected 0.45..0.55, got {ratio:.4f}"
print("thickness occupancy ratio OK")
PY
```

---

## 7) Test Plan

## 7.1 Required automated tests

1. Run:
   - `python3 -m pytest sprite-workbench/tests/test_room_layout_manifest_shell.py`
2. Extend `sprite-workbench/tests/test_room_layout_manifest_shell.py` with one new assertion:
   - prompt includes exact halved-thickness phrase:
     - `~8-12% of image width per side band and ~9-14% top / ~7-11% bottom`
3. If shell prompt/validator unit tests in `ashen-hollow/tests/room_environment_system.test.py` fail from text/threshold drift, update those assertions in the same change.

## 7.2 Manual tests

1. Workbench preview (`#preview=embed`) in `R1`:
   - shell visibly thinner than baseline.
   - opening alignment still follows polygon.
2. Playtest:
   - no wall clipping regressions.
   - no obvious background bleed that breaks style/readability.

Record results in `tests/test_report.md`.

---

## 8) Execution Order

1. Implement constants + shell-only rewiring in `room_environment_system.py`.
2. Implement runtime collider constant update in `ashen-hollow/index.html`.
3. Restart server, regenerate `R1-room-shell`, sync canonical.
4. Run verification scripts and tests.
5. Run manual visual/runtime checks.
6. Update `tests/test_report.md`.
7. Commit.

---

## 9) Out of Scope

- Changing room polygon geometry for gameplay.
- Retuning unrelated biome/template families.
- Multi-room shell-thickness rollout beyond `R1` in this task.
- Broad validator redesign outside shell-specific paths.

---

## 10) Commit Message

`feat(room-env): halve unified shell thickness contract and runtime collider lip`

