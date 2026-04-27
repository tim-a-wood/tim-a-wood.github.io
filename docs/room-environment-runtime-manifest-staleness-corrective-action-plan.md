# Room Environment Pipeline — Runtime Manifest Staleness (Grey Shell in Playtest)

**Status:** Draft (corrective-action-plan, ready-to-implement)
**Owners:** Sprite Workbench (asset pipeline / canonical layout sync)
**Schema/version baselines:** Generation plan schema_version 1; bespoke_asset_manifest.schema_version 2.
**Reference project (regenerated assets live here):** `ashen-sentinel-9ea9be55` Room R1.
**Companion plan:** [`room-environment-misalignment-corrective-action-plan.md`](room-environment-misalignment-corrective-action-plan.md) — this plan addresses the gap that companion left open.

---

## 1. Plain-English summary

The previous corrective-action plan fixed the room environment **pipeline** (planner produces room-sized shells; runtime placement math handles them; playtest no longer dims bespoke backgrounds). The regeneration step produced a correct 1600×1200 shell PNG in the active project on disk.

But the runtime never sees that PNG. Phaser loads bespoke assets by reading the `bespoke_asset_manifest` embedded inside `sprite-workbench/room-layout-data.json` (the canonical layout the game fetches at boot). That manifest is **stale**: it still describes the old 1080×960 shell and points at a different project's `bespoke/` directory. The runtime fetches the URL the manifest gives it. Depending on how the developer is serving the page, that URL either resolves to the **old, misaligned 1080×960 shell** (Bug 1 still visible in playtest) or **404s and triggers the procedural grey-shell fallback**. Either way the user does not see the regenerated 1600×1200 shell.

**Fix:** republish the manifest entry for `R1-room-shell` (and any other regenerated slots) into `sprite-workbench/room-layout-data.json` so its `generation_plan`, `assets[*]`, `final_dimensions`, `placement`, and `url` all match the regenerated 1600×1200 PNG in `projects-data/ashen-sentinel-9ea9be55/`. Two acceptable implementation paths are listed in §5; Path A (re-run the planner end-to-end) is preferred, Path B (surgical JSON patch) is the minimum acceptable.

---

## 2. Evidence and root-cause numbers

### 2.1 What is on disk vs. what the manifest claims

Regenerated shell asset on disk (correct, post-fix from companion plan):

```
/Users/timwood/Desktop/projects/PWA/MV/sprite-workbench/tools/2d-sprite-and-animation/
  projects-data/ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell.png
size:               1600 × 1200 (RGBA)
alpha hole bbox:    (160, 160) – (1440, 1040)   ← exactly the chamber polygon
```

Asset the runtime actually loads (stale, pre-fix):

```
URL in manifest:    /tools/2d-sprite-and-animation/projects-data/
                    room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/R1-room-shell.png
size on disk:       1080 × 960 (RGBA)            ← old shell, never regenerated
```

### 2.2 Stale `bespoke_asset_manifest` for R1 in `sprite-workbench/room-layout-data.json`

`rooms.R1.environment.runtime.bespoke_asset_manifest`:

- `status: "ready"` — passes the `isPlayableRoomEnvironmentBespokeManifest` gate, so the runtime trusts the manifest and skips fallbacks until it tries to use the texture.
- `built_slots: ["R1-background", "R1-midground", "R1-room-shell"]`.
- `generation_plan[*]` entries (relevant slot only):

  ```
  R1-background      target_dimensions={1600,1200}  placement={x:800, y:1200, dw:1600, dh:1200, origin:(0.5,1)}   ← already correct
  R1-midground       target_dimensions={1600,1200}  placement={x:800, y:1200, dw:1600, dh:1200, origin:(0.5,1)}   ← already correct
  R1-room-shell      target_dimensions={1080, 960}  placement={x:700, y:1080, dw:1080, dh: 960, origin:(0.5,1)}   ← STALE
  ```

- `assets["R1-room-shell"]`:

  ```
  slot_id:           "R1-room-shell"
  component_type:    "room_shell_foreground"
  requested_dimensions: {1080, 960}
  final_dimensions:     {1080, 960}
  placement:            {x:700, y:1080, display_width:1080, display_height:960, origin_x:0.5, origin_y:1}
  url:                  "/tools/2d-sprite-and-animation/projects-data/
                         room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/R1-room-shell.png"
  ```

### 2.3 Runtime path that produces the grey shell

`ashen-hollow/index.html`:
- `getRoomEnvironmentBespokeManifest(roomId)` → reads `env.runtime.bespoke_asset_manifest` from layout data (lines ~1440-1444).
- `isPlayableRoomEnvironmentBespokeManifest` → passes because `status === "ready"` (lines ~1446-1451).
- `preloadRoomEnvironmentAssets()` → calls `this.load.image('env-bespoke-R1-room-shell', asset.url)` (line ~2500). When `asset.url` 404s, Phaser logs a load error and the texture is never registered.
- `addRoomBespokeUnifiedShellForegroundDecor(roomId, support)` → checks `this.textures.exists('env-bespoke-R1-room-shell')` (line ~3284). On miss, returns `false` immediately. No bespoke shell is drawn.
- The procedural shell fallback (`buildWorldGeometry` masonry) takes over → flat grey rectangle around the chamber.

If the URL **does** resolve (e.g., served by `sprite_workbench_server.py` whose web root contains both `room-ai-helpfulness-qa-67562113` and `ashen-sentinel-9ea9be55`), the runtime instead loads the **old 1080×960 shell**, applies the `computeUnifiedShellWorldPlacement` math against `final_dimensions={1080,960}` and `placement.display_width=1080`, and draws the original misaligned shell — i.e., Bug 1 from the companion plan, unfixed for runtime users.

### 2.4 Why the previous plan did not catch this

The companion plan changed:
- The pipeline so future planner runs emit `target_dimensions={room_w, room_h}` for `room_shell_foreground` slots.
- The runtime so room-sized shells map identity (no chamber-rescale).
- The Bug 2 alpha line.

It did **not** include a step to (a) re-run the planner against the active project to refresh the manifest, or (b) republish the refreshed manifest into the canonical `sprite-workbench/room-layout-data.json`. The asset on disk was regenerated outside the planner, and the layout file was never resynced with the regenerated outputs.

---

## 3. Root cause (one-line)

`sprite-workbench/room-layout-data.json` `→ rooms.R1.environment.runtime.bespoke_asset_manifest` carries pre-fix `generation_plan` + `assets["R1-room-shell"]` entries that point at a different project's old 1080×960 PNG. The regenerated 1600×1200 PNG in `ashen-sentinel-9ea9be55/...` is never reached by the runtime.

---

## 4. Required updates — exact target state for the manifest

The shell entry in `sprite-workbench/room-layout-data.json` must end up in this exact shape (R1 only — repeat for any other room with regenerated shells). Values are absolute and final; do not parameterize.

### 4.1 `rooms.R1.environment.runtime.bespoke_asset_manifest.generation_plan[<shell entry>]`

```json
{
  "slot_id": "R1-room-shell",
  "component_type": "room_shell_foreground",
  "source_template_id": "ruined-gothic-v1-foreground_frame",
  "target_dimensions": { "width": 1600, "height": 1200 },
  "placement": {
    "x": 800,
    "y": 1200,
    "display_width": 1600,
    "display_height": 1200,
    "origin_x": 0.5,
    "origin_y": 1
  },
  "schema_key": "walls",
  "slot_group": "foreground",
  "transparency_mode": "alpha"
}
```

(Preserve any other keys the planner stamps — `local_geometry`, `protected_zones`, etc. — by re-running the planner; do not invent them.)

### 4.2 `rooms.R1.environment.runtime.bespoke_asset_manifest.assets["R1-room-shell"]`

```json
{
  "slot_id": "R1-room-shell",
  "component_type": "room_shell_foreground",
  "source_template_id": "ruined-gothic-v1-foreground_frame",
  "requested_dimensions": { "width": 1600, "height": 1200 },
  "final_dimensions": { "width": 1600, "height": 1200 },
  "placement": {
    "x": 800,
    "y": 1200,
    "display_width": 1600,
    "display_height": 1200,
    "origin_x": 0.5,
    "origin_y": 1
  },
  "url": "/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell.png",
  "transparency_mode": "alpha",
  "schema_key": "walls",
  "slot_group": "foreground",
  "validation": { "status": "pass", "errors": [] },
  "generation_source": "ai"
}
```

(Keep the existing `attempts[]` history if present — it is provenance, not config.)

### 4.3 Other manifest fields to verify (not change)

- `rooms.R1.environment.runtime.bespoke_asset_manifest.status` — must remain `"ready"`.
- `built_slots` — must contain `"R1-room-shell"`.
- `R1-background` and `R1-midground` `generation_plan` and `assets` entries are already correct at 1600×1200 — leave them.
- `schema_validation.status`, `runtime_review.status`, `review.status` — leave at their current values; this plan does not re-run review.

### 4.4 Files that must NOT be touched by this plan

- `ashen-hollow/index.html` — no runtime change required. The companion plan's runtime fix already handles room-sized shells correctly when the manifest agrees.
- `sprite-workbench/scripts/room_environment_v3.py` — companion-plan changes already correct. No further edits.
- `sprite-workbench/scripts/room_environment_system.py` — same.
- The mirror copy `.git/modules/sprite-workbench/room-layout-data.json` — leave alone; it is a git-internal artefact, not a runtime read path.

---

## 5. Implementation paths

Pick one. Path A is preferred because it round-trips through the canonical pipeline and so cannot diverge from future planner output. Path B is acceptable as a tactical patch when the planner cannot be re-run end-to-end.

### Path A — Re-run the planner against `ashen-sentinel-9ea9be55`, then sync canonical layout

A.1. Start the workbench server in the project context:

```
cd /Users/timwood/Desktop/projects/PWA/MV/sprite-workbench
python3 scripts/sprite_workbench_server.py
```

A.2. In the workbench UI, open project `ashen-sentinel-9ea9be55`, navigate to the room layout editor's R1 tab, and trigger a fresh environment generation for R1 (button label varies by build — same control used for the original generation that produced `R1-background.png` / `R1-midground.png`). The companion-plan changes guarantee that the planner now emits:

- `generation_plan["R1-room-shell"].target_dimensions = {1600, 1200}`
- `generation_plan["R1-room-shell"].placement = {x:800, y:1200, dw:1600, dh:1200, origin:(0.5, 1.0)}`
- `assets["R1-room-shell"].final_dimensions = {1600, 1200}`
- `assets["R1-room-shell"].url` rooted at `projects-data/ashen-sentinel-9ea9be55/...`

A.3. The room layout editor's "Sync to canonical room-layout-data.json" action (see `_merged_editor_body.js:7410`) writes the active project's layout into repo-root `sprite-workbench/room-layout-data.json` via `room_layout_canonical.write_layout` (`scripts/room_layout_canonical.py`). Trigger that sync.

A.4. Verify the on-disk file matches §4. If yes, proceed to §6 acceptance.

### Path B — Surgical JSON patch (use only if Path A is not available)

B.1. Confirm the regenerated PNG exists and is correct:

```
file:  sprite-workbench/tools/2d-sprite-and-animation/projects-data/
       ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell.png
size:  1600 × 1200
hole bbox via flood fill of alpha=0 component reachable from corners: (160, 160) – (1440, 1040)
```

If those do not match, abort and run the regeneration step from the companion plan first.

B.2. Edit `sprite-workbench/room-layout-data.json`. Locate `rooms.R1.environment.runtime.bespoke_asset_manifest`. Within `generation_plan`, find the entry whose `slot_id === "R1-room-shell"` and replace its `target_dimensions` and `placement` to match §4.1. Within `assets`, find the entry whose `slot_id === "R1-room-shell"` (key may itself be `"R1-room-shell"`) and replace `requested_dimensions`, `final_dimensions`, `placement`, and `url` to match §4.2. Preserve `attempts[]` and `validation` from the existing entry.

B.3. Do not edit `built_slots`, `failed_assets`, `schema_validation`, `runtime_review`, `review`, `status`, or `generated_at`. Do not touch the `R1-background` or `R1-midground` entries.

B.4. JSON formatting: keep the file's existing indentation (workbench writes 2-space pretty JSON via `room_layout_canonical.write_layout`). Trailing newline must be preserved.

B.5. Commit message convention: `chore(room-env): republish R1 manifest for room-sized unified shell`. Do not commit the regenerated PNG separately if it has already been committed in the companion plan; if the workbench wrote a new PNG during Path A, commit it inside the same change.

---

## 6. Acceptance criteria

All of the following must hold after the fix lands. Verify in order — earlier failures invalidate later ones.

A.0. `sprite-workbench/room-layout-data.json` parses as valid JSON.

A.1. `rooms.R1.environment.runtime.bespoke_asset_manifest.assets["R1-room-shell"].final_dimensions == {1600, 1200}`.

A.2. `rooms.R1.environment.runtime.bespoke_asset_manifest.assets["R1-room-shell"].placement` deep-equals `{x:800, y:1200, display_width:1600, display_height:1200, origin_x:0.5, origin_y:1}`.

A.3. `rooms.R1.environment.runtime.bespoke_asset_manifest.assets["R1-room-shell"].url` resolves, when prefixed with the workbench server web root, to a file whose size is `1600 × 1200` and whose largest transparent flood-fill component bbox is `(160, 160, 1440, 1040)`.

A.4. The corresponding `generation_plan` entry's `target_dimensions == {1600, 1200}` and `placement` matches §4.1.

A.5. `built_slots` still contains `"R1-room-shell"`. `status` still `"ready"`.

A.6. `R1-background` and `R1-midground` manifest entries are unchanged.

A.7. Loading the playtest (no `#preview=embed`) renders a shell that:
   - Is not the procedural grey rectangle.
   - Reaches all four room edges (no background bleed at corners or sides).
   - Visually matches the on-disk PNG palette (no washed-out background — confirms the companion plan's Bug 2 fix is also in effect).

A.8. Loading the workbench preview (`#preview=embed`) shows the same shell at the same placement.

---

## 7. Verification commands

Run from `/Users/timwood/Desktop/projects/PWA/MV` (paths absolute below for clarity):

```bash
# A.1 – A.5: manifest shape
python3 - <<'PY'
import json
with open('/Users/timwood/Desktop/projects/PWA/MV/sprite-workbench/room-layout-data.json') as f:
    data = json.load(f)
rooms = data.get('rooms') or data.get('layout', {}).get('rooms') or {}
r1 = rooms['R1'] if isinstance(rooms, dict) else next(r for r in rooms if r.get('id') == 'R1')
m = r1['environment']['runtime']['bespoke_asset_manifest']
shell = m['assets']['R1-room-shell'] if 'R1-room-shell' in m['assets'] else next(v for v in m['assets'].values() if v['slot_id'] == 'R1-room-shell')
plan_entry = next(p for p in m['generation_plan'] if p['slot_id'] == 'R1-room-shell')

assert m['status'] == 'ready', m['status']
assert 'R1-room-shell' in m['built_slots']
assert shell['final_dimensions'] == {'width': 1600, 'height': 1200}, shell['final_dimensions']
assert shell['placement'] == {'x': 800, 'y': 1200, 'display_width': 1600, 'display_height': 1200, 'origin_x': 0.5, 'origin_y': 1}, shell['placement']
assert plan_entry['target_dimensions'] == {'width': 1600, 'height': 1200}, plan_entry['target_dimensions']
assert plan_entry['placement'] == shell['placement'], plan_entry['placement']
assert 'ashen-sentinel-9ea9be55' in shell['url'], shell['url']
print('manifest OK')
PY

# A.3: actual PNG referenced by the manifest
python3 - <<'PY'
from PIL import Image
import json
from collections import deque
with open('/Users/timwood/Desktop/projects/PWA/MV/sprite-workbench/room-layout-data.json') as f:
    data = json.load(f)
rooms = data.get('rooms') or data.get('layout', {}).get('rooms') or {}
r1 = rooms['R1'] if isinstance(rooms, dict) else next(r for r in rooms if r.get('id') == 'R1')
m = r1['environment']['runtime']['bespoke_asset_manifest']
shell = m['assets']['R1-room-shell'] if 'R1-room-shell' in m['assets'] else next(v for v in m['assets'].values() if v['slot_id'] == 'R1-room-shell')
url = shell['url']
# Map URL `/tools/...` back to disk under sprite-workbench/
disk = '/Users/timwood/Desktop/projects/PWA/MV/sprite-workbench' + url
im = Image.open(disk).convert('RGBA')
assert im.size == (1600, 1200), im.size
# Largest transparent component bbox via flood from (0,0)
W, H = im.size
alpha = im.split()[-1].load()
seen = [[False]*H for _ in range(W)]
q = deque()
def push(x, y):
    if 0 <= x < W and 0 <= y < H and not seen[x][y] and alpha[x, y] == 0:
        seen[x][y] = True
        q.append((x, y))
push(0, 0); push(W-1, 0); push(0, H-1); push(W-1, H-1)
minx, miny, maxx, maxy = W, H, -1, -1
while q:
    x, y = q.popleft()
    minx = min(minx, x); miny = min(miny, y); maxx = max(maxx, x); maxy = max(maxy, y)
    push(x+1, y); push(x-1, y); push(x, y+1); push(x, y-1)
print('shell hole bbox:', (minx, miny, maxx, maxy))
assert (minx, miny, maxx, maxy) == (160, 160, 1440, 1040), (minx, miny, maxx, maxy)
print('PNG OK')
PY
```

A.7 / A.8 are manual-visual checks against `R1-background.png` and screenshot 1 from the companion plan.

---

## 8. Tests to add (optional but recommended)

If a regression test makes sense in this codebase, add one assertion to a layout-data sanity test (location: `sprite-workbench/scripts/tests/test_room_layout_canonical*.py` or equivalent — pick the existing test that already loads `room-layout-data.json`):

```python
def test_R1_unified_shell_manifest_is_room_sized():
    data = json.loads(CANONICAL_LAYOUT_PATH.read_text())
    rooms = data.get('rooms') or data['layout']['rooms']
    r1 = rooms['R1'] if isinstance(rooms, dict) else next(r for r in rooms if r['id'] == 'R1')
    manifest = r1['environment']['runtime']['bespoke_asset_manifest']
    shell = next(v for v in manifest['assets'].values() if v['component_type'] == 'room_shell_foreground')
    assert shell['final_dimensions'] == {'width': 1600, 'height': 1200}
    assert shell['placement']['display_width'] == 1600
    assert shell['placement']['display_height'] == 1200
    assert shell['placement']['origin_x'] == 0.5 and shell['placement']['origin_y'] == 1
    assert shell['placement']['x'] == 800 and shell['placement']['y'] == 1200
```

This guards against future planner regressions republishing 1080×960 entries.

---

## 9. Implementation order (single agent)

1. Decide Path A vs. Path B (default: A).
2. Execute the chosen path (§5).
3. Run §7 verification commands. Both blocks must print `OK`.
4. Manual visual check (§6 A.7, A.8).
5. Add the regression test from §8.
6. Commit with message from §5 B.5 (or planner-equivalent if Path A regenerates files).

Stop after step 4 if any check fails. Do not proceed to commit without green verification.

---

## 10. Out of scope for this plan

- Other rooms (R2…). If they have their own regenerated shells, repeat §4 and §5 for each, but do not bundle them into this plan unless explicitly requested.
- Re-running the workbench runtime-review pipeline. The manifest's `runtime_review` block can stay stale; the playtest does not gate on it.
- Cleaning up the unused 1080×960 PNG in `room-ai-helpfulness-qa-67562113`. That project is a separate workspace and is not the source of truth for this build.
- Changes to `withPreviewAssetCacheBust`, cross-origin `postMessage` handling, or any other companion-plan bonus code. Those are working as intended.
