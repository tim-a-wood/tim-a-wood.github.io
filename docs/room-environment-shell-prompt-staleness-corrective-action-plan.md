# Room Environment Pipeline — Shell Prompt / Manifest Staleness (Re-Run Required)

**Status:** Draft (corrective-action-plan, ready-to-implement)
**Owners:** Sprite Workbench (planner + AI generation)
**Schema/version baselines:** Generation plan schema_version 1; bespoke_asset_manifest.schema_version 2.
**Reference project:** `ashen-sentinel-9ea9be55` Room R1.
**Companion plans:**
- [`room-environment-misalignment-corrective-action-plan.md`](room-environment-misalignment-corrective-action-plan.md) — pipeline + runtime alpha fix.
- [`room-environment-runtime-manifest-staleness-corrective-action-plan.md`](room-environment-runtime-manifest-staleness-corrective-action-plan.md) — manifest republish via Path B (surgical JSON patch).
This plan is the third in the sequence and addresses the gap that Path B left open.

---

## 1. Plain-English summary

The prior two plans fixed the **pipeline source code** and **patched the canonical layout JSON** to point at a 1600×1200 shell asset. But neither plan re-ran the AI generation. The PNG on disk and the manifest entry both look right at the *placement* level (1600×1200, room-bottom centered), but the **art inside the PNG was painted by Gemini back on 2026-04-11 against an old chamber-sized prompt asking for 1080×960 px**. Some out-of-band post-process step then padded the chamber-size art onto a 1600×1200 canvas with a 16 px transparent gutter on all four sides. That gutter is what the user sees as a grey margin around the shell when the workbench renders the PNG over its grey panel background.

Two additional symptoms confirm the staleness:
1. The recorded `bespoke_asset_manifest.assets["R1-room-shell"].attempts[0].prompt` does **not** contain the new prompt lines added by the prior pipeline fix (`Canvas size contract:`, `Opening position contract:`, `Rectangular guardrail:`, `ANTI-COLLAGE`). It still says `Exact output width: 1080 px`, `Exact output height: 960 px`, `Output one image at exactly 1080×960 px`. The pipeline edits are present in the working tree but no AI regeneration has been triggered against them.
2. The transparent hole inside the PNG is a clean axis-aligned rectangle `(160, 160) – (1440, 1040)` (1280×880). R1's actual polygon is an **L/step shape** with vertices `[160,260], [900,260], [900,120], [1240,120], [1240,1080], [980,1080], [980,860], [160,860]`. The polygon's AABB is `(160,120)–(1240,1080)` (1080×960). Neither the rectangular hole nor the "old chamber" assumption matches the actual polygon — meaning the hole was punched through a stale or hardcoded chamber rectangle, not through the room footprint. The runtime will draw the bespoke shell at the (160,160,1440,1040) opening while the actual walkable polygon is at (160,120,1240,1080), so the player can clip into the painted shell and the shell mass will draw inside the walkable area along the L-step indents.

**Fix:** trigger a real AI regeneration of `R1-room-shell` against the active project so the planner runs with the fixed pipeline code, the prompt contains the canvas-size contract lines, the AI receives an L-shape polygon contract reference, and the punchout uses the actual room polygon. Then sync the resulting manifest into `sprite-workbench/room-layout-data.json`.

---

## 2. Evidence and root-cause numbers

### 2.1 Manifest is from before the pipeline fix

`sprite-workbench/room-layout-data.json` `→ rooms.R1.environment.runtime.bespoke_asset_manifest`:

```
manifest.generated_at = "2026-04-11T07:08:15.272311+00:00"   ← 15 days before the pipeline fix
shell.attempts = [<single attempt, started_at=null, ended_at=null>]
shell.attempts[0].reference_images = [
  /Users/.../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/.../_refs/...
]
```

The attempt's `reference_images` paths point at `/Users/.../tools/...` (an absolute path under the **MV root**, not under the `sprite-workbench` submodule), and at the `room-ai-helpfulness-qa-67562113` project — neither of which is the canonical active project (`ashen-sentinel-9ea9be55`). This is residue from before the submodule reorganisation.

### 2.2 The recorded prompt does not contain the pipeline fix

`shell.attempts[0].prompt` excerpt (verbatim):

```
…
Generate ONE uncropped room-shell source image only. …

        Exact output width: 1080 px
        Exact output height: 960 px
        Orientation: full
        Runtime placement: x=700 y=1080 origin=(0.50,1.00)
        Protected zones: walkable_shell_interior@(160,120,1080,960)
        …
        Chamber (keep-clear interior) approximate size for context: 1080×960 px (do not invent interior perspective in the border bands).

Spatial contract (JSON, same geometry as reference #1):
{"output_size_px":[1080,960], …}
        Output one image at exactly 1080×960 px. No text, no characters, no UI.
```

Lines added by the pipeline fix that are **missing**:
- `Canvas size contract: generate exactly 1600x1200 pixels (full room canvas, not chamber crop).`
- `Opening position contract: keep the walkable opening locked to the room polygon coordinates from geometry["polygon"] at this same canvas scale.`
- `Rectangular guardrail (when footprint is rectangular): opening must occupy …`
- `ANTI-COLLAGE / ANTI-VOID-GUTTER: …`

The recorded prompt also still uses chamber-centered placement (`x=700 y=1080`) instead of the room-bottom-centered placement (`x=800 y=1200`) that the fixed planner emits.

### 2.3 The PNG was hand-padded, not AI-regenerated at room size

```
file: sprite-workbench/.../ashen-sentinel-9ea9be55/.../R1-room-shell.png      mtime=2026-04-26 19:15:54
file: sprite-workbench/.../ashen-sentinel-9ea9be55/.../R1-room-shell-raw.png  mtime=2026-04-26 19:15:53
final size:    1600 × 1200 (RGBA)
raw size:      1184 × 864     ← AI returned chamber-aspect, not room-aspect
opaque bbox:   (16, 16) – (1584, 1184)        ← 16 px transparent gutter on every side
hole bbox:     (160, 160) – (1440, 1040)      ← rectangular, 1280×880
```

Cross-check against the reference image:

```
file: .../_refs/room_shell_foreground-contract.png    size = 1600 × 1200    ← reference IS room-sized
```

The contract reference is room-sized but the AI output (raw) is chamber-aspect. That is consistent with the stored prompt asking for 1080×960 — the AI honoured the *prompt text*, not the reference image dims.

### 2.4 The hole geometry does not match the actual polygon

R1 polygon (`rooms.R1.polygon`):

```
[[160, 260], [900, 260], [900, 120], [1240, 120],
 [1240, 1080], [980, 1080], [980, 860], [160, 860]]
```

- 8 vertices, L/step shape.
- AABB: `(160, 120) – (1240, 1080)` → 1080 × 960.
- The shell PNG's transparent hole is `(160, 160) – (1440, 1040)` → 1280 × 880, **rectangular, not L-shaped**, and not even aligned to the polygon AABB.

The 1280×880 hole appears to be a hardcoded chamber rectangle from a previous schema (or from the prior plans' assumption that R1 is rectangular). In any case, with this hole the runtime collision polygon and the painted opening disagree — the player will collide with painted stone inside the walkable area along the L-step on the right side, and there will be unpainted background visible above the indent on the left.

### 2.5 Pipeline source files: present in working tree, not yet exercised

```
sprite-workbench/scripts/room_environment_v3.py        mtime=2026-04-26 17:06:49   ← contains pipeline fix
sprite-workbench/scripts/room_environment_system.py    mtime=2026-04-26 17:06:44   ← contains pipeline fix
sprite-workbench/scripts/environment_v3/kit.py         mtime=2026-04-26 15:28:13   ← contains kit metadata fix
```

`git diff` confirms all three files carry the prior plans' edits in the working tree. No AI regeneration has run since the edits.

`git stash list` shows three stashes, none from today, so the user's hypothesis ("changes are stashed") is not the cause — the edits are already on disk.

### 2.6 Why this slipped past the prior plans' verification

- Companion plan 1 verified the PNG dimensions on disk (1600×1200) and the runtime placement math, both of which pass.
- Companion plan 2 verified the manifest's `final_dimensions`, `placement`, and `url` after my Path B JSON patch, all of which pass.
- Neither plan inspected `attempts[0].prompt`, `manifest.generated_at`, `R1-room-shell-raw.png`, or the hole-vs-polygon geometry. Those four checks would have caught the staleness.

---

## 3. Root cause (one-line)

The R1 shell asset and its `bespoke_asset_manifest` entry have not been regenerated by the AI pipeline since the pipeline-fix commit; the on-disk PNG is a hand-padded chamber-size render and the manifest's prompt history reflects the pre-fix code, so the new shell prompt contracts and the polygon-based punchout have never actually been exercised end-to-end.

---

## 4. Required end state

After this plan lands, all the following must be true for `rooms.R1.environment.runtime.bespoke_asset_manifest`:

### 4.1 Manifest provenance

- `manifest.generated_at` is on or after the date the regeneration runs (NOT 2026-04-11).
- `built_slots` contains `"R1-room-shell"`; manifest `status` is `"ready"`.
- `manifest.assets["R1-room-shell"].attempts` has at least one new attempt whose `started_at` and `ended_at` are non-null timestamps from the current regen run.

### 4.2 Prompt content

The latest attempt's `prompt` must contain **all** of the following substrings (case-sensitive):

- `Canvas size contract: generate exactly 1600x1200 pixels (full room canvas, not chamber crop).`
- `Opening position contract: keep the walkable opening locked to the room polygon coordinates`
- `Rectangular guardrail (when footprint is rectangular):` (the constant text; the `(cl,ct)` and `(opening_right,opening_bottom)` numbers will be polygon-derived — they should be `(160,120)` and `(1240,1080)` respectively for R1)
- `ANTI-COLLAGE / ANTI-VOID-GUTTER:`
- `Exact output width: 1600 px`
- `Exact output height: 1200 px`
- `Output one image at exactly 1600×1200 px.`
- The spatial contract JSON line must contain `"output_size_px":[1600,1200]`.
- `Runtime placement: x=800 y=1200 origin=(0.50,1.00)`.
- `Protected zones: walkable_shell_interior@(160,120,1080,960)` (this is the polygon AABB; the polygon-derived guardrail expresses this rectangle, the AI is meant to match the L-shape via the contract reference image, not via this protected-zone line).

### 4.3 Asset and placement entries

`manifest.assets["R1-room-shell"]` (must end identical to the prior plan's §4.2):

- `requested_dimensions == final_dimensions == {width: 1600, height: 1200}`.
- `placement == {x: 800, y: 1200, display_width: 1600, display_height: 1200, origin_x: 0.5, origin_y: 1}`.
- `url` resolves under the canonical workbench server web root and points at the regenerated PNG (project `ashen-sentinel-9ea9be55`).
- `validation.status == "pass"`.

`manifest.generation_plan[<shell entry>]`:

- `target_dimensions == {width: 1600, height: 1200}`.
- `placement` deep-equals the assets entry's placement.
- `local_geometry.room_width == 1600`, `local_geometry.room_height == 1200`.
- `local_geometry.chamber_width == 1080`, `local_geometry.chamber_height == 960`, `local_geometry.chamber_left == 160`, `local_geometry.chamber_top == 120` (polygon AABB).
- `protected_zones` contains a single entry of type `walkable_shell_interior` with `(x,y,width,height) == (160,120,1080,960)`.

### 4.4 PNG geometry (post-processed final asset)

- Size: exactly `(1600, 1200)`.
- The opaque bbox must extend to all four canvas edges: `min_x == 0`, `min_y == 0`, `max_x == 1599`, `max_y == 1199`. **No transparent gutter.** (Tolerate up to 2 px on each side to allow for AI sub-pixel artefacts; anything more than 2 px is a fail.)
- The largest interior transparent component (i.e., the chamber hole — not the outer-edge transparent ring if any) must be **L-shaped** and follow the R1 polygon. Numerically, after rasterising the polygon at canvas scale, at least 95% of polygon-interior pixels must be transparent (alpha 0) and at least 95% of band pixels (the polygon-exterior region inside the canvas) must be opaque (alpha > 0).

### 4.5 Raw PNG

- `R1-room-shell-raw.png` size must be exactly `(1600, 1200)` (not 1184×864). This proves the AI was actually asked for and returned a room-sized image, rather than the post-processor padding chamber-size art onto a room canvas.

---

## 5. Implementation paths

Pick one. Path A is preferred (round-trips through the canonical pipeline). Path B is acceptable only as an investigation tool — do not declare done after Path B.

### Path A — Re-run the planner + AI generation against `ashen-sentinel-9ea9be55`

A.1. Confirm the working tree contains the pipeline-fix edits before doing anything else:

```
grep -q "Canvas size contract: generate exactly" \
  /Users/timwood/Desktop/projects/PWA/MV/sprite-workbench/scripts/room_environment_system.py \
  || { echo "MISSING PIPELINE FIX — abort"; exit 1; }
grep -q '"target_dimensions": {"width": width, "height": height}' \
  /Users/timwood/Desktop/projects/PWA/MV/sprite-workbench/scripts/room_environment_v3.py \
  || { echo "MISSING PIPELINE FIX — abort"; exit 1; }
```

If either grep fails, stop. Investigate why the working tree lost the prior fix (check `git stash list`, `git reflog`, branch state). Do not regenerate against an unfixed planner — that is what produced this bug in the first place.

A.2. Confirm the workbench server is running with the fixed code. Server PID's start time must be after the file mtimes from §2.5. If the server was started before the file edits, restart it (the prior session already documented this — `kill <pid>` then `python3 scripts/sprite_workbench_server.py --host 127.0.0.1 --port 8766`).

A.3. In the workbench UI:
- Open project `ashen-sentinel-9ea9be55`.
- Navigate to the room layout editor's R1 tab.
- Trigger a fresh environment regeneration for R1 (the same control used to produce R1-background.png and R1-midground.png originally — typically "Generate" or "Re-run AI" on the R1 environment panel).
- Wait for status to return to `ready` (or `failed` — see A.5).

A.4. Sync to canonical: trigger the room-layout editor's "Sync to canonical room-layout-data.json" action so the regenerated manifest is written into `sprite-workbench/room-layout-data.json` via `scripts/room_layout_canonical.write_layout`.

A.5. Failure handling:
- If the AI returns a chamber-sized raw PNG again (raw size != 1600×1200), the prompt is leaking through with the wrong dims. Open the failed attempt's prompt and grep for `Canvas size contract` and `Output one image at exactly 1600×1200 px`. If those substrings are present and the AI still returned the wrong size, the failure is on the model side — increase prompt strength (e.g., add `MUST be exactly 1600 wide and 1200 tall — do NOT crop` immediately before the spatial contract block) and retry. If the substrings are missing, the prompt builder is not being invoked — check that `_build_bespoke_prompt_room_shell_foreground` is being reached for this slot (set a logger.debug or add a temporary `print` at the top of the function and observe the server log).
- If the punchout produces a rectangular hole at (160,160,1440,1040) instead of an L-shape, the punchout is reading a stale chamber rectangle rather than the polygon. Check `_apply_walkable_interior_punchout` (`scripts/room_environment_system.py:5429`) and verify it consumes `geometry["polygon"]` to produce the mask, not `geometry["chamber_*"]`. If it currently uses chamber rectangles, that is a separate bug — file it but unblock this plan by manually punching the polygon at post-process time.

### Path B — Read-only investigation only (do not declare done)

B.1. Use the verification scripts in §6 to print the current manifest state, raw PNG state, and prompt staleness. This is for diagnosing a failed Path A run, not for fixing the bug. You cannot exit this plan green by hand-editing `attempts[0].prompt` — the AI generation must actually run.

---

## 6. Acceptance criteria (ordered)

A.0. The pipeline-fix grep guard from §5.A.1 passes (working tree has the fix).

A.1. `manifest.generated_at` parses as a date on or after the regen run started.

A.2. `manifest.assets["R1-room-shell"].attempts[-1]` (the latest attempt) has non-null `started_at` and `ended_at` from the current run.

A.3. The latest attempt's `prompt` contains every substring listed in §4.2.

A.4. `manifest.generation_plan[<shell>]` matches §4.3.

A.5. `manifest.assets["R1-room-shell"]` matches §4.3.

A.6. `R1-room-shell-raw.png` is exactly 1600×1200 (§4.5).

A.7. `R1-room-shell.png` is exactly 1600×1200 with opaque pixels reaching all four edges (§4.4) and the chamber hole shaped to the R1 polygon, not a rectangle (§4.4).

A.8. `R1-background` and `R1-midground` manifest entries are unchanged.

A.9. Visual: load the workbench preview for R1 and confirm the shell now reads as a continuous masonry ring filling the whole canvas with an L-shaped opening at the polygon. Load playtest (no `#preview=embed`) and confirm the same.

Failures earlier in the list invalidate later checks — stop on the first failure and route to §5.A.5.

---

## 7. Verification commands

Run from `/Users/timwood/Desktop/projects/PWA/MV` after Path A:

```bash
# A.0 — pipeline fix present in working tree
grep -q "Canvas size contract: generate exactly" sprite-workbench/scripts/room_environment_system.py && echo "A.0 OK"

# A.1 – A.5: manifest provenance, prompt freshness, dims
python3 - <<'PY'
import json, datetime
with open('/Users/timwood/Desktop/projects/PWA/MV/sprite-workbench/room-layout-data.json') as f:
    d = json.load(f)
rooms = d.get('rooms') or d.get('layout', {}).get('rooms') or {}
r1 = rooms['R1'] if isinstance(rooms, dict) else next(r for r in rooms if r.get('id') == 'R1')
m = r1['environment']['runtime']['bespoke_asset_manifest']
gen = m.get('generated_at') or ''
assert gen >= '2026-04-26', f'manifest.generated_at is stale: {gen}'
print('A.1 OK   generated_at =', gen)

shell = m['assets']['R1-room-shell'] if 'R1-room-shell' in m['assets'] else next(v for v in m['assets'].values() if v['slot_id'] == 'R1-room-shell')
attempt = shell['attempts'][-1]
assert attempt.get('started_at') and attempt.get('ended_at'), 'attempt timestamps missing'
print('A.2 OK   latest attempt =', attempt.get('attempt'))

required = [
    'Canvas size contract: generate exactly 1600x1200 pixels',
    'Opening position contract: keep the walkable opening',
    'Rectangular guardrail (when footprint is rectangular):',
    'ANTI-COLLAGE / ANTI-VOID-GUTTER:',
    'Exact output width: 1600 px',
    'Exact output height: 1200 px',
    'Output one image at exactly 1600×1200 px.',
    '"output_size_px":[1600,1200]',
    'Runtime placement: x=800 y=1200 origin=(0.50,1.00)',
    'Protected zones: walkable_shell_interior@(160,120,1080,960)',
]
prompt = attempt['prompt']
missing = [s for s in required if s not in prompt]
assert not missing, f'prompt missing substrings: {missing}'
print('A.3 OK   prompt contains all canvas-size contract lines')

plan = next(p for p in m['generation_plan'] if p['slot_id'] == 'R1-room-shell')
assert plan['target_dimensions'] == {'width': 1600, 'height': 1200}
assert plan['placement'] == {'x': 800, 'y': 1200, 'display_width': 1600, 'display_height': 1200, 'origin_x': 0.5, 'origin_y': 1}
lg = plan.get('local_geometry') or {}
assert lg.get('room_width') == 1600 and lg.get('room_height') == 1200
assert lg.get('chamber_width') == 1080 and lg.get('chamber_height') == 960
assert lg.get('chamber_left') == 160 and lg.get('chamber_top') == 120
print('A.4 OK   plan + local_geometry')

assert shell['final_dimensions'] == {'width': 1600, 'height': 1200}
assert shell['placement'] == plan['placement']
assert 'ashen-sentinel-9ea9be55' in shell['url']
assert shell.get('validation', {}).get('status') == 'pass'
print('A.5 OK   asset entry')
PY

# A.6 — raw PNG must be room-sized
python3 - <<'PY'
from PIL import Image
raw = '/Users/timwood/Desktop/projects/PWA/MV/sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell-raw.png'
im = Image.open(raw).convert('RGBA')
assert im.size == (1600, 1200), f'raw PNG is {im.size}, must be (1600, 1200)'
print('A.6 OK   raw PNG is room-sized')
PY

# A.7 — final PNG fills canvas + L-shaped hole
python3 - <<'PY'
from PIL import Image, ImageDraw
final = '/Users/timwood/Desktop/projects/PWA/MV/sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell.png'
im = Image.open(final).convert('RGBA')
W, H = im.size
assert (W, H) == (1600, 1200)
ax = im.split()[-1].load()

# opaque bbox reaches edges (allow 2 px tolerance per side for AI artefacts)
minx, miny, maxx, maxy = W, H, -1, -1
for y in range(H):
    for x in range(W):
        if ax[x, y] > 0:
            if x < minx: minx = x
            if y < miny: miny = y
            if x > maxx: maxx = x
            if y > maxy: maxy = y
assert minx <= 2 and miny <= 2 and maxx >= W - 3 and maxy >= H - 3, \
    f'opaque bbox ({minx},{miny})-({maxx},{maxy}) does not reach canvas edges'
print('A.7a OK  opaque bbox reaches canvas edges')

# polygon hole alignment: rasterise R1 polygon, check transparent fraction inside / opaque fraction outside
polygon = [(160, 260), (900, 260), (900, 120), (1240, 120), (1240, 1080), (980, 1080), (980, 860), (160, 860)]
mask = Image.new('L', (W, H), 0)
ImageDraw.Draw(mask).polygon(polygon, fill=255)
mx = mask.load()
inside_total = inside_clear = outside_total = outside_opaque = 0
for y in range(0, H, 2):
    for x in range(0, W, 2):
        if mx[x, y]:
            inside_total += 1
            if ax[x, y] == 0: inside_clear += 1
        else:
            outside_total += 1
            if ax[x, y] > 0: outside_opaque += 1
inside_pct = 100 * inside_clear / max(1, inside_total)
outside_pct = 100 * outside_opaque / max(1, outside_total)
print(f'A.7b inside-polygon transparent: {inside_pct:.1f}%   outside-polygon opaque: {outside_pct:.1f}%')
assert inside_pct >= 95 and outside_pct >= 95, 'hole geometry does not follow R1 polygon'
print('A.7b OK  hole follows L-shape polygon')
PY
```

A.8 / A.9 are manual: visually compare the workbench preview and playtest against `R1-background.png` and the polygon overlay.

---

## 8. Tests to add

Extend `sprite-workbench/tests/test_room_layout_manifest_shell.py` (or add a sibling test) with three additional assertions:

```python
def test_r1_unified_shell_manifest_has_canvas_size_contract_prompt(self):
    layout_path = Path(__file__).resolve().parents[1] / "room-layout-data.json"
    data = json.loads(layout_path.read_text(encoding="utf-8"))
    rooms = data.get("rooms") or data["layout"]["rooms"]
    r1 = rooms["R1"] if isinstance(rooms, dict) else next(r for r in rooms if r["id"] == "R1")
    m = r1["environment"]["runtime"]["bespoke_asset_manifest"]
    shell = next(v for v in m["assets"].values() if v.get("component_type") == "room_shell_foreground")
    prompt = shell["attempts"][-1]["prompt"]
    for needle in (
        "Canvas size contract: generate exactly 1600x1200 pixels",
        "Output one image at exactly 1600×1200 px.",
        '"output_size_px":[1600,1200]',
        "Runtime placement: x=800 y=1200 origin=(0.50,1.00)",
    ):
        self.assertIn(needle, prompt)

def test_r1_unified_shell_plan_local_geometry_is_polygon_aabb(self):
    # ... reads plan entry, asserts local_geometry chamber_* match polygon AABB (160,120,1080,960)

def test_r1_unified_shell_raw_png_is_room_sized(self):
    # ... opens R1-room-shell-raw.png, asserts size == (1600, 1200)
```

These guard against future regressions where the manifest looks correct at the dimensions level but the actual AI generation reverted.

---

## 9. Implementation order (single agent)

1. Run §5.A.1 grep guard. If it fails, stop and surface the regression to the user before doing anything else.
2. Verify the workbench server is running on the fixed code (§5.A.2). Restart if needed.
3. Trigger the regen via the workbench UI (§5.A.3).
4. Sync to canonical (§5.A.4).
5. Run all §7 verification scripts. They must all print `OK`. On failure, route to §5.A.5.
6. Run the new tests from §8.
7. Manual visual check (§6.A.9).
8. Commit. Suggested message: `chore(room-env): regenerate R1 unified shell with room-sized prompt + polygon punchout`.

Do not commit a green Path A run if A.7b fails — a rectangular hole on an L-shape polygon will misregister the runtime collider and the painted shell.

---

## 10. Known follow-ups (out of scope here, file separately)

- **Pipeline edits not yet committed.** `git status` shows the prior pipeline fix as unstaged modifications in `sprite-workbench/scripts/{room_environment_v3.py, room_environment_system.py, environment_v3/kit.py}`. Once this plan is green, those edits should be committed in their own commit so future regenerations are pinned to the fixed code.
- **Punchout polygon source.** If §5.A.5's "rectangular hole" failure mode actually occurs on regen, that is a separate bug in `_apply_walkable_interior_punchout` that needs its own plan. The current symptom suggests the punchout is reading `geometry["chamber_*"]` (a rectangle) rather than `geometry["polygon"]` (the actual L-shape).
- **Stale reference paths under MV root.** `attempts[0].reference_images` paths point at `/Users/.../MV/tools/...` (pre-submodule layout). After regen these should be relative to the workbench server web root or under `sprite-workbench/.../projects-data/...`. If they continue to leak the pre-reorg absolute path, file a separate plan to update the reference-image writer.
- **`runtime-review.png` and `structural-review-bundle.png` are still chamber-sized** (1280×880 and 976×440 respectively). The runtime-review pipeline likely needs the same fix as the bespoke path. Out of scope here, but worth noting since the workbench may render these as previews and that could be what the user is currently seeing in the screenshot.
