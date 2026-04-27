# Room Environment Spec — Per-Room Biome Selection

**Status:** Ready to implement
**Owner:** Sprite Workbench (room editor + room environment pipeline)
**Scope:** Add explicit per-room biome selection driving shell + background generation
**Outcomes:** A biome picker in the room Environment phase; shell prompts use the chosen biome's locked direction + selected shell material; background prompts use the chosen biome's locked direction + frozen concepts; selection changes invalidate cached assets.

---

## 1) Decision Contract (locked answers — do not relitigate)

1. **One biome per room.** Single field `environment.room_intent.selected_biome_id` (already initialized to `null` in the v3 schema). No split shell/background biome.
2. **Default for new rooms = last-used pack** at the project level. Persisted as `art_direction.last_selected_biome_id` (string|null). On project create or first-ever selection, fallback chain is: `last_selected_biome_id` → first ordered pack → `null`.
3. **No new endpoints.** Selection round-trips through the existing room save (`POST /api/projects/<id>/rooms/<rid>/environment/spec`) and the existing `save_room_layout` path. The new project-level `last_selected_biome_id` is updated server-side whenever a room save changes a `selected_biome_id`.
4. **Image references use existing `image_path`.** No thumbnail endpoint, no new caching, no resizing in this work.
5. **Migration is explicit and deterministic.** First time a project loads after this change, every room with `selected_biome_id == null` is filled by snapshotting whatever `_select_biome_pack_for_preview(direction, spec)` resolves to right now. Recorded in the project's history log so it's traceable.

If any implementation detail conflicts with §1, this section wins.

---

## 2) Current State (verified) and Target State

### 2.0 Naming conventions used in this spec

- **"Shell"** in prose means the bespoke room-shell strip. Two key namespaces refer to it:
  - **Plan-entry / prompt-builder side:** `component_type == "room_shell_foreground"` (used in `_build_bespoke_prompt*`).
  - **Asset-pack / staleness side:** `wall_body_strip` (used in `asset_pack["stale_components"]` and in `_build_asset_component_dependency_payloads`).
  - **Schema-key side:** `"walls"` (used inside the prompt as `schema_key`).
  When this spec says "the shell" without qualification, all three refer to the same artifact (`R1-room-shell.png`). When precision matters, the spec uses the exact key.
- **"Background"** maps cleanly: `component_type == "background_far_plate"` ↔ asset key `background` ↔ artifact `R1-background.png`.

### 2.0.1 Line numbers in this spec

All `Lxxxx` references are accurate as of `sprite-workbench` HEAD on the date this spec was written and pin to function definitions or distinctive token sequences. If a reader finds a line number off by more than a few lines (someone edited the file between spec authoring and implementation), re-resolve by **function name** (`_build_bespoke_prompt`, `_build_bespoke_prompt_room_shell_foreground`, `_build_asset_component_dependency_payloads`) or by the literal Python expression quoted alongside the line number. Do not "fix the line number" by editing this spec — open a follow-up spec note instead.

### 2.1 What exists today (reuse — do not duplicate)
- Schema slot: `environment.room_intent.selected_biome_id` initialized in [`sprite-workbench/js/wizard/environment.js:574-576`](sprite-workbench/js/wizard/environment.js#L574).
- Default initializer: `default_room_intent(..., biome_id=...)` at [`sprite-workbench/scripts/room_environment_v3.py:126-144`](sprite-workbench/scripts/room_environment_v3.py#L126).
- Resolution helpers in [`sprite-workbench/scripts/room_environment_system.py`](sprite-workbench/scripts/room_environment_system.py):
  - `_active_preview_biome_id(room, direction)` at L3146 — currently reads only `env.preview.scene_plan.preview_biome_id`, then falls back to `_select_biome_pack_for_preview`.
  - `_find_biome_pack(direction, biome_id)` at L8885.
  - `_select_biome_pack(direction)` at L8880, `_select_biome_pack_for_preview(direction, spec)` at L8915, `_ordered_biome_packs(direction)` at L8871.
  - `_selected_shell_material_path_for_room(room, direction, project_dir)` at L3163 — already routes the shell material reference image off `_active_preview_biome_id` and the biome pack's `shell_material_board.selected_material_id`.
  - `_preview_frozen_concepts_for_pack(project, direction, pack)` at L8928, `_resolve_frozen_concepts(...)` at L1757, `_available_frozen_concepts(...)` at L1734.
- Bespoke prompt builders:
  - `_build_bespoke_prompt_room_shell_foreground(direction, spec, ...)` at L9257 — currently embeds project-level `direction.high_level_direction` / `direction.negative_direction`.
  - `_build_bespoke_prompt(direction, spec, ...)` at L9341 — same; the `background_far_plate` branch flows through this.
- Server entrypoints in [`sprite-workbench/scripts/sprite_workbench_server.py`](sprite-workbench/scripts/sprite_workbench_server.py):
  - `save_room_layout(project_id, payload)` at L2286 (full layout save).
  - `build_project_room_environment_spec(...)` at L1802 → `room_environment_system.build_room_environment_spec(...)` (per-room save path).
  - Other room env entrypoints at L1797, L1807, L1812, L1817, L1822, L1827, L1832 — none currently take a biome selection.

### 2.2 What ships in this change
- A biome picker in the room wizard's Environment tab, writing through both `save_room_layout` and `build_project_room_environment_spec`.
- `_active_preview_biome_id` updated to honor explicit `room_intent.selected_biome_id` first.
- Shell + background prompt builders read from the selected biome's `locked_direction` (and shell prompt also reads `shell_material_description`), not from the project-level direction.
- `last_selected_biome_id` tracked at `art_direction` level; used as the default for new rooms.
- Biome rename / delete reconciliation across all rooms.
- Asset staleness wired so a selection change marks `room_shell_foreground` + `background_far_plate` stale.
- One-time migration of `selected_biome_id == null` rooms.
- Tests, docs, and verification scripts.

---

## 3) Impact Matrix

| Area | Files | Direction |
| --- | --- | --- |
| Schema / data | `js/wizard/environment.js`; `scripts/room_environment_v3.py`; `scripts/room_environment_system.py` (normalize_art_direction) | Add `last_selected_biome_id` to art-direction normalizer; thread `selected_biome_id` end-to-end. |
| Resolution | `scripts/room_environment_system.py` | `_active_preview_biome_id` precedence change; reconciliation helper for biome rename/delete. |
| Prompt builders | `scripts/room_environment_system.py` | Shell + background builders read from selected biome's `locked_direction` (+ shell uses `shell_material_description`). |
| UI | `room-layout-editor.html`; `js/wizard/environment.js`; `js/editor/wizard.js`; `css/room-wizard.css` | New biome-picker block in Environment tab with thumbnails (image_path → `<img>`). |
| Server | `scripts/sprite_workbench_server.py`; `scripts/room_environment_system.py` | Validate `selected_biome_id` on save; update `last_selected_biome_id`; reject IDs not in `art_direction.biome_packs`. |
| Staleness | `scripts/room_environment_system.py` (`_build_asset_component_dependency_payloads` L2759; bespoke manifest write L12377-12388) | Add `biome_context` to `background` + `wall_body_strip` payloads only; add `biome_context` to bespoke manifest immediately after L12380. Update freshness comparator to consider `biome_context`. |
| Migration | `scripts/room_environment_system.py` (helper); call from `scripts/workbench_project_io.py:30` `load_project` | One-time backfill on first load post-change; appends single `room_biome_selection_backfill` history event. |
| Canonical sync | `room-layout-data.json` (via existing `POST /api/layout` editor flow) | No code change beyond §4.5; manual save in editor causes canonical sync. Verified by `git diff` per §4.9. |
| Tests | `tests/test_room_layout_manifest_shell.py`; `tests/test_sprite_workbench.py`; `tests/playwright/*.spec.js` | Coverage per §7. |
| Docs | `docs/qa-evidence/art-direction-biome-wizard/downstream-biome-selection.md` | Update to "explicit, per-room". |

---

## 4) Exact Implementation Steps

Steps are ordered for execution. Each step is independently mergeable behind an existing-data invariant: do not skip the order unless explicitly noted.

### 4.1 — Add `last_selected_biome_id` to art-direction normalizer

**File:** [`sprite-workbench/scripts/room_environment_system.py`](sprite-workbench/scripts/room_environment_system.py) — `normalize_art_direction` (find by name).

- After existing `biome_packs` normalization, add:
  ```python
  raw_last = raw.get("last_selected_biome_id") if isinstance(raw, dict) else None
  trimmed = _trimmed_string(raw_last) if raw_last is not None else None
  valid_ids = {str(p.get("biome_id") or "").strip() for p in (out.get("biome_packs") or []) if isinstance(p, dict)}
  out["last_selected_biome_id"] = trimmed if trimmed in valid_ids else None
  ```
- Persist alphabetically with siblings; no behavior change in this step alone.

**Acceptance:** loading any project (with or without the new field) round-trips cleanly; deleting the referenced biome clears `last_selected_biome_id` on next normalize.

### 4.2 — Make `_active_preview_biome_id` honor explicit selection

**File:** [`sprite-workbench/scripts/room_environment_system.py:3146`](sprite-workbench/scripts/room_environment_system.py#L3146).

Replace the function body with this exact precedence (same signature, same return):
```python
def _active_preview_biome_id(room, direction):
    env = _ensure_room_environment(room)
    intent = env.get("room_intent") if isinstance(env.get("room_intent"), dict) else {}
    explicit = str(intent.get("selected_biome_id") or "").strip()
    if explicit and _find_biome_pack(direction, explicit):
        return explicit
    scene_plan = (env.get("preview") or {}).get("scene_plan")
    if isinstance(scene_plan, dict):
        direct = str(scene_plan.get("preview_biome_id") or "").strip()
        if direct and _find_biome_pack(direction, direct):
            return direct
    spec = env.get("spec") or {}
    preview_pack = _select_biome_pack_for_preview(direction, spec if isinstance(spec, dict) else {})
    if preview_pack:
        return str(preview_pack.get("biome_id") or "").strip() or None
    return None
```

Notes:
- Validating the explicit id against `_find_biome_pack` prevents stale ids (post-delete) from poisoning generation; resolution silently falls through.
- All existing callers (`_selected_shell_material_path_for_room`, the two L11905 / L12379 callers, etc.) require **no changes** — they already consume the return.

**Acceptance:** with `selected_biome_id` set, this is the returned id; clearing it returns the prior behavior; pointing it at a deleted id returns the fallback.

### 4.3 — Reconcile `selected_biome_id` on biome rename / delete / duplicate

**File:** [`sprite-workbench/scripts/room_environment_system.py`](sprite-workbench/scripts/room_environment_system.py).

Add helper:
```python
def _reconcile_room_biome_selection(project: Dict[str, Any], removed_id: Optional[str] = None, renamed_from: Optional[str] = None, renamed_to: Optional[str] = None) -> List[str]:
    affected: List[str] = []
    layout = project.get("room_layout") or {}
    for room in (layout.get("rooms") or []):
        if not isinstance(room, dict):
            continue
        env = room.get("environment") or {}
        intent = env.get("room_intent") or {}
        current = str(intent.get("selected_biome_id") or "").strip()
        if not current:
            continue
        if renamed_from and current == renamed_from and renamed_to:
            intent["selected_biome_id"] = renamed_to
            affected.append(str(room.get("id") or ""))
        elif removed_id and current == removed_id:
            intent["selected_biome_id"] = None
            affected.append(str(room.get("id") or ""))
    direction = project.get("art_direction") or {}
    last = str(direction.get("last_selected_biome_id") or "").strip()
    if removed_id and last == removed_id:
        direction["last_selected_biome_id"] = None
    if renamed_from and last == renamed_from and renamed_to:
        direction["last_selected_biome_id"] = renamed_to
    return affected
```

Call sites (already exist in this file):
- `update_art_direction_biome` (rename handling): if the payload changes `biome_id`, call `_reconcile_room_biome_selection(project, renamed_from=old_id, renamed_to=new_id)`.
- `delete_art_direction_biome`: call `_reconcile_room_biome_selection(project, removed_id=biome_id)`.
- `duplicate_art_direction_biome`: no reconciliation needed (original survives).

After reconciling, mark the affected rooms' shell + background assets stale (see §4.7).

**Acceptance:** deleting a biome that R1 references nulls R1's selection and stales R1's shell+background; renaming preserves the link.

### 4.4 — Shell + background prompts read from selected biome

**File:** [`sprite-workbench/scripts/room_environment_system.py`](sprite-workbench/scripts/room_environment_system.py).

#### 4.4.a — Add the active-pack resolver

Insert immediately above `_build_bespoke_prompt_room_shell_foreground` (currently L9257) — no other location:
```python
def _resolve_active_biome_pack(direction: Dict[str, Any], room: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Returns the biome pack the room currently points to, or None.
    Never falls back to the project-level direction — callers MUST keep
    the `direction.get(...)` fallback at the call site to preserve
    behavior when no biome is selected."""
    if not isinstance(room, dict):
        return None
    biome_id = _active_preview_biome_id(room, direction)
    return _find_biome_pack(direction, biome_id) if biome_id else None
```

#### 4.4.b — Thread `room` to both prompt builders

Two and only two call edits are required. Do not search; do not add `room=` to anywhere else.

1. **`_build_bespoke_prompt_room_shell_foreground`** signature at L9257 — append `room: Optional[Dict[str, Any]] = None` as the final keyword-only parameter (after `shell_rules`). Default `None` keeps any future caller compatible.
2. **`_build_bespoke_prompt`** signature at L9341 — append `room: Optional[Dict[str, Any]] = None` as the final keyword-only parameter (after `room_geometry`).
3. **Single inner call** at L9464 inside `_build_bespoke_prompt` — pass `room=room` through to `_build_bespoke_prompt_room_shell_foreground(...)`.
4. **Single outer call** at L11992 in the bespoke generation loop — change to `_build_bespoke_prompt(direction, spec, entry, template, room_geometry=_room_geometry(room), room=room)`. The local `room` is already in scope at L11992 (the loop iterates `for room in ...` upstream — verify by reading L11960–11992).

There are no other production call sites. If a future test stub calls these with positional args, it must be updated separately; this spec does not own that.

#### 4.4.c — Replace the prompt text in `_build_bespoke_prompt_room_shell_foreground`

Inside the body (currently using `direction.get('high_level_direction')` etc.), replace the two lines:
```python
Art direction (material vocabulary only — ignore if it suggests a full interior scene): {direction.get('high_level_direction') or ''}
Avoid: {direction.get('negative_direction') or ''}
```
with:
```python
_biome_pack = _resolve_active_biome_pack(direction, room)
_locked = (_biome_pack or {}).get("locked_direction") or {}
hl = (_locked.get("high_level_direction") or direction.get("high_level_direction") or "")
nd = (_locked.get("negative_direction") or direction.get("negative_direction") or "")
shell_material_desc = str((_biome_pack or {}).get("shell_material_description") or "").strip()
shell_brief_line = ("\nShell material brief: " + shell_material_desc) if shell_material_desc else ""
# ... and in the f-string body:
Art direction (material vocabulary only — ignore if it suggests a full interior scene): {hl}
Avoid: {nd}{shell_brief_line}
```

`shell_brief_line` MUST be omitted (empty string) when `shell_material_description` is empty/missing — do not emit a bare "Shell material brief:" line. This is required for A.10 (no regression for projects that don't define a description).

**Single source of truth for shell prompts:** at L9463 `_build_bespoke_prompt` performs an early `return _build_bespoke_prompt_room_shell_foreground(...)` for `component_type == "room_shell_foreground"`. Therefore the `Art direction:` / `Avoid:` lines at L9609–L9610 are **unreachable for shell** — the only user-visible `hl`/`nd`/shell-brief text for shell prompts is what §4.4.c emits. The §4.4.d edit below applies to `background_far_plate` (and any other component type that survives the early return); duplication / conflict between the two blocks is impossible.

#### 4.4.d — Replace the prompt text in `_build_bespoke_prompt`

Inside the body, around L9609–L9610, replace:
```python
Art direction: {hl}
Avoid: {nd}
```
with the same `hl`/`nd` derivation, gated on component type. Because `room_shell_foreground` returns early at L9463, the only component this block effectively covers (per §1) is `background_far_plate`. Implement defensively so any future component routed past the early return defaults to today's behavior:

```python
if component_type == "background_far_plate":
    _biome_pack = _resolve_active_biome_pack(direction, room)
    _locked = (_biome_pack or {}).get("locked_direction") or {}
    hl = (_locked.get("high_level_direction") or direction.get("high_level_direction") or "")
    nd = (_locked.get("negative_direction") or direction.get("negative_direction") or "")
else:
    hl = direction.get("high_level_direction") or ""
    nd = direction.get("negative_direction") or ""
```

Do not consolidate this into a single unconditional branch "for simplicity" — the explicit gate is what makes A.10 verifiable. Do not extend the gate to include `room_shell_foreground` "for safety" — that branch is unreachable here per §4.4.c, and adding it would mask a future bug if someone removes the early return.

#### 4.4.e — Pack selection in v3 plan-building (drives background reference templates and frozen concepts)

`background_far_plate` reference templates and frozen-concept image paths are not assembled inside `_build_bespoke_prompt`; they are populated upstream by `envv3.build_generation_plan(room, preview_seed_id, biome_pack, ...)`. The pack passed to that planner determines which `frozen_concepts` and which `background_plate` template get into the plan entry, which then flows into the prompt and reference image set.

`grep -n '_select_biome_pack(direction)' sprite-workbench/scripts/room_environment_system.py` returns exactly **4 hits today**, of which **2 are room-scoped plan-building sites that must change** and **2 are out of scope**:

| Line | Function context | Change? | Reason |
| --- | --- | --- | --- |
| L1737 | `_resolve_frozen_concepts` (helper) | **No** | The caller passes an explicit `biome_id` already; this is the helper's own fallback. |
| L5214 | room-scoped (env build path; `room` in scope) | **Yes** | Drives `_sync_v3_environment_state` biome id for this room. |
| L8824 | room-scoped (preview suggestion path; `room` in scope) | **Yes** | Drives `envv3.build_generation_plan(room, ...)` biome pack for this room. |
| L8888 | inside `_select_biome_pack_for_preview` (the fallback function itself) | **No** | This is the implicit fallback by definition. |

At **L5214** and **L8824**, replace:
```python
biome_pack = _select_biome_pack(direction)
```
with:
```python
biome_pack = _resolve_active_biome_pack(direction, room) or _select_biome_pack(direction)
```
Fallback to `_select_biome_pack(direction)` preserves today's behavior when no biome is selected (A.10).

A third room-scoped plan-building site at **L12386** already uses `biome_pack = _find_biome_pack(direction, _active_preview_biome_id(room, direction))` — no change needed; this site is already explicit-selection-aware via the L12379 line and §4.2's precedence change.

Do NOT change call sites used by: biome wizard endpoints, art-direction admin endpoints (`update_art_direction_biome`, `delete_art_direction_biome`, `duplicate_art_direction_biome`, `generate_project_art_direction_concepts`, `iterate_biome_art_direction_concept`). Those flows are not room-scoped and the L1737 / L8888 helpers are sufficient.

Inside `_build_bespoke_prompt` and `_build_bespoke_prompt_room_shell_foreground`, the literal token `_select_biome_pack(direction)` does not appear (verified by grep) — there is nothing to replace there.

**Acceptance:** prompt strings for shell and background contain the chosen biome's locked direction text and (shell only) `shell_material_description`. Background reference image set is the chosen biome's frozen concepts. Non-shell/non-background prompts are byte-identical when diffed against pre-change output for a project where no room has a `selected_biome_id` yet.

### 4.5 — UI: biome picker in the Environment tab

**Files:**
- [`sprite-workbench/room-layout-editor.html`](sprite-workbench/room-layout-editor.html) — Environment phase markup.
- [`sprite-workbench/js/editor/wizard.js`](sprite-workbench/js/editor/wizard.js) — phase logic.
- [`sprite-workbench/js/wizard/environment.js`](sprite-workbench/js/wizard/environment.js) — schema/normalize.
- [`sprite-workbench/css/room-wizard.css`](sprite-workbench/css/room-wizard.css) — styles.

Markup (insert above the existing Environment phase content, after the layout-complete gate):
```html
<section class="rw-env-biome" id="rwEnvBiomePicker" hidden>
  <h3 class="rw-env-biome-title">Biome</h3>
  <p class="rw-env-biome-sub">Choose which biome's material and concept this room uses.</p>
  <ul class="rw-env-biome-list" id="rwEnvBiomeList" role="radiogroup" aria-label="Biome"></ul>
  <p class="rw-env-biome-empty" id="rwEnvBiomeEmpty" hidden>No biomes yet — create one in <a href="#" data-rw-link="art-direction">Art Direction</a>.</p>
</section>
```

Each list item rendered by JS:
```html
<li class="rw-env-biome-item" data-biome-id="<id>">
  <label>
    <input type="radio" name="rwEnvBiome" value="<id>" />
    <span class="rw-env-biome-thumbs">
      <img src="<concept image_path>" alt="" loading="lazy" />
      <img src="<shell material image_path>" alt="" loading="lazy" />
    </span>
    <span class="rw-env-biome-label"><biome label or biome_id></span>
  </label>
</li>
```

JS responsibilities (in `js/wizard/environment.js` or a new sibling `js/wizard/biome-picker.js`):
- `renderBiomePicker(rootEl, project, room)` — reads `project.art_direction.biome_packs`, the room's current `environment.room_intent.selected_biome_id`, and the project's `art_direction.last_selected_biome_id` (used as the visual "default" hint when the room has no explicit selection — but no implicit write).
- For thumbnails: `concept image` = first entry of `pack.frozen_concepts[0].image_path`, fallback `pack.concept_board.images[0].image_path`. `material image` = the row in `pack.shell_material_board.images` whose `material_id` matches `selected_material_id`, fallback first row. Hide the `<img>` if no path.
- On change, write `room.environment.room_intent.selected_biome_id = id` in the in-memory model and trigger the existing dirty/save flow (whatever the Environment phase currently uses for spec edits — same pattern, no new pathway).
- Show the empty state when `biome_packs.length === 0`.

Gating: Environment phase is already gated behind layout completion ([`room-layout-editor.html:197`](sprite-workbench/room-layout-editor.html#L197)). The picker is the **first** thing inside the Environment phase; downstream Environment actions (preview, generate, approve) remain enabled regardless of picker state — selection is optional, falls back to existing implicit resolution if `null`.

**Acceptance:** opening the Environment tab for a room shows the picker; selecting a biome persists through save and round-trips; switching to another room shows that room's selection independently.

### 4.6 — Server: validate selection, update `last_selected_biome_id`

**File:** [`sprite-workbench/scripts/sprite_workbench_server.py`](sprite-workbench/scripts/sprite_workbench_server.py).

In `save_room_layout` at L2286, after the existing validation block but before persisting, walk every room and:
1. Read each `room.environment.room_intent.selected_biome_id`.
2. If non-empty, ensure `_find_biome_pack(project["art_direction"], id)` returns a pack; if not, raise `ValueError(f"Room {room['id']} references unknown biome {bid}")`. Use that exact f-string format — the test in §7.1 greps for the substring `"references unknown biome"`.
3. **`last_selected_biome_id` write rule (deterministic, no timestamp tiebreak):** the incoming payload represents a single user save. The "most recent" pick is the room *whose `selected_biome_id` differs from the previously-stored value*. Compute as: load the previous `room_layout` from disk; for each room in the new payload, compare `selected_biome_id` against the previous value; collect the diffs in payload order; if the diff list is non-empty, set `project["art_direction"]["last_selected_biome_id"]` to the last diff's new value (or `None` if cleared). If no room's selection changed, leave `last_selected_biome_id` untouched. Do NOT consult `environment.updated_at`.

In `build_project_room_environment_spec` at L1802 (per-room save), apply the same validation against the single `room` being saved. If `selected_biome_id` differs from the previous on-disk value, set `art_direction.last_selected_biome_id` to the new value (or `None` if cleared).

**Acceptance:** a save with an unknown biome id is rejected with `ValueError` whose message contains `"references unknown biome"`. A save that changes R1's selection from `null` to `bx` sets `last_selected_biome_id="bx"`. A save that re-saves the same selection does NOT mutate `last_selected_biome_id` (idempotency).

### 4.7 — Staleness fingerprint includes biome selection

**File:** [`sprite-workbench/scripts/room_environment_system.py`](sprite-workbench/scripts/room_environment_system.py).

#### 4.7.a — Per-component dependency payloads

Inside `_build_asset_component_dependency_payloads` (function at L2759), after the existing `layout_context` is computed but before the per-component dict literal is assembled, derive a single `biome_context` dict:
```python
_biome_id = _active_preview_biome_id(room, direction)
_biome_pack = _find_biome_pack(direction, _biome_id) if _biome_id else None
biome_context = {
    "biome_id": _biome_id or "",
    "locked_direction_revision": str((_biome_pack or {}).get("text_revision") or ""),
    "shell_material_revision": str((_biome_pack or {}).get("shell_material_text_revision") or ""),
    "selected_material_id": str(((_biome_pack or {}).get("shell_material_board") or {}).get("selected_material_id") or ""),
    "frozen_concept_ids": [str(c.get("concept_id") or "") for c in ((_biome_pack or {}).get("frozen_concepts") or []) if isinstance(c, dict)],
}
```

Add `biome_context` as a new key on **exactly these two** component entries returned by the function (no others):
- `background`
- `wall_body_strip`

Do NOT add it to: `door`, `floor_cap_strip`, `platform_ledge_strip`, `midground_arches`. Adding it to those families is an unscoped behavioral change and would fail A.10.

#### 4.7.b — Bespoke manifest fingerprint

The bespoke manifest is finalized at [`sprite-workbench/scripts/room_environment_system.py:12377`](sprite-workbench/scripts/room_environment_system.py#L12377). Today, L12380 already records `bespoke_manifest["biome_id"]`. That field alone is insufficient — material/concept revisions can change without the id changing. Immediately after L12380, add:
```python
bespoke_manifest["biome_context"] = {
    "biome_id": (biome_pack or {}).get("biome_id") or "",
    "locked_direction_revision": str((biome_pack or {}).get("text_revision") or ""),
    "shell_material_revision": str((biome_pack or {}).get("shell_material_text_revision") or ""),
    "selected_material_id": str(((biome_pack or {}).get("shell_material_board") or {}).get("selected_material_id") or ""),
    "frozen_concept_ids": [str(c.get("concept_id") or "") for c in ((biome_pack or {}).get("frozen_concepts") or []) if isinstance(c, dict)],
}
```

Then update every staleness comparator that reads `bespoke_asset_manifest["biome_id"]` (verify by `Grep` for `"biome_id"` within `room_environment_system.py` — list all hits; the only ones to touch are the comparators that produce `stale_components`) so they additionally compare `biome_context`. If the comparison logic lives in a single helper (e.g. `_bespoke_manifest_is_fresh` or similar), patch only that helper. If no such helper exists today, add a freshness check immediately before the next `stale_components` write in the L11960–L12390 region.

**Acceptance:** changing `selected_biome_id` on a room with `status: ready` flips `stale_components` to include `background` and `wall_body_strip` on next refresh. Changing the selected biome's `shell_material_board.selected_material_id` (without changing `selected_biome_id`) ALSO flips both stale, because `biome_context.selected_material_id` differs. The verification script in §6 step 5 covers the first case; the second case is covered by the unit test `test_biome_context_shell_material_change_invalidates_shell` listed in §7.1.

### 4.8 — One-time migration for existing rooms

**File:** [`sprite-workbench/scripts/room_environment_system.py`](sprite-workbench/scripts/room_environment_system.py).

Add a normalize-time backfill (run once per project, idempotent):
```python
def _backfill_room_biome_selection(project: Dict[str, Any]) -> bool:
    direction = project.get("art_direction") or {}
    if not (direction.get("biome_packs") or []):
        return False
    layout = project.get("room_layout") or {}
    changed = False
    for room in (layout.get("rooms") or []):
        if not isinstance(room, dict):
            continue
        env = room.get("environment") or {}
        intent = env.get("room_intent") or {}
        if intent.get("selected_biome_id"):
            continue
        spec = env.get("spec") or {}
        pack = _select_biome_pack_for_preview(direction, spec)
        if not pack:
            continue
        intent["selected_biome_id"] = str(pack.get("biome_id") or "").strip() or None
        env["room_intent"] = intent
        room["environment"] = env
        changed = True
    if changed and not direction.get("last_selected_biome_id"):
        ordered = _ordered_biome_packs(direction)
        if ordered:
            direction["last_selected_biome_id"] = str(ordered[0].get("biome_id") or "").strip() or None
    return changed
```

Insert **exactly one** call:

- **`workbench_project_io.load_project`** at [`sprite-workbench/scripts/workbench_project_io.py:30`](sprite-workbench/scripts/workbench_project_io.py#L30) — invoke `_backfill_room_biome_selection(project)` after the project's `room_layout` has been hydrated and `art_direction` has been normalized, but before the function returns. (Import the helper from `room_environment_system`.) If you cannot identify a single point where both are present, add the call as the last statement before the `return project` line.

Inheritance-only (do not add a second call):

- **`sprite_workbench_server.load_project`** at [`sprite-workbench/scripts/sprite_workbench_server.py:1697`](sprite-workbench/scripts/sprite_workbench_server.py#L1697) is a thin forwarder to `project_io.load_project`. It inherits the backfill automatically. **Adding a second invocation here would double-fire the history event** — verified by reading L1697-L1699: the function is a one-line delegate. Do not edit.

When `_backfill_room_biome_selection` returns `True`, also append a single project-level history event:
```python
history = project.setdefault("history", []) if isinstance(project, dict) else None
if isinstance(history, list):
    history.append({
        "event_type": "room_biome_selection_backfill",
        "occurred_at": now_iso(),
        "affected_room_ids": [...],   # populate from the helper's return value (refactor helper to also return ids)
    })
```
Refactor `_backfill_room_biome_selection` to return `(changed: bool, affected_ids: List[str])` so the loader can populate `affected_room_ids` deterministically. Idempotency requirement: a second `load_project` call MUST return `changed=False` and emit no new history event.

**Acceptance:** loading any pre-change project once auto-fills selections to whatever the implicit logic would have picked; second load is a no-op.

### 4.9 — Canonical sync

The canonical layout file `sprite-workbench/room-layout-data.json` is owned by the room-layout editor and synced via `POST /api/layout` → [`room_layout_canonical.save_canonical_layout`](sprite-workbench/scripts/room_layout_canonical.py). There is no separate "regenerate from project" command.

Required steps, in order:

1. With the workbench server running, open the room editor at `/room-layout-editor.html` and load the project `ashen-sentinel-9ea9be55`.
2. Open R1 → Environment tab → select a biome (e.g. `ruined-gothic-v1`) → save the room.
3. Confirm the canonical sync fired by running `git diff sprite-workbench/room-layout-data.json` from the workspace root. The diff MUST include:
   - The new `last_selected_biome_id` field under `art_direction` (string or null).
   - For R1: `environment.room_intent.selected_biome_id` set to the chosen value.
4. If `room-layout-data.json` is unchanged after a save that touched `selected_biome_id`, the editor's canonical-sync POST is broken — stop and fix the editor (this is a regression the spec covers, not a workflow caveat). Do NOT hand-edit `room-layout-data.json` to make the diff appear.

This step is a workflow step (no code change beyond what §4.5 already lands in the editor); it is listed in §8 and gated by the manual checks in §7.2.

### 4.10 — Docs

**File:** [`sprite-workbench/docs/qa-evidence/art-direction-biome-wizard/downstream-biome-selection.md`](sprite-workbench/docs/qa-evidence/art-direction-biome-wizard/downstream-biome-selection.md).

Replace the "implicit primary pack" framing with: selection is now explicit per room via `environment.room_intent.selected_biome_id`; `_select_biome_pack_for_preview` is the fallback only; project-level `art_direction.last_selected_biome_id` is the default for newly-created rooms.

---

## 5) Acceptance Criteria (must all pass)

- **A.1 Picker present.** Opening the Environment tab for any room with a layout shows the biome picker. With ≥1 biome pack, the list renders one item per pack with both thumbnails (or graceful fallback when an image is missing). With 0 packs, the empty state shows.
- **A.2 Selection round-trips.** Selecting a biome and saving the room writes `environment.room_intent.selected_biome_id` to both `room_layout.json` and the canonical `room-layout-data.json` after canonical sync; reloading the page restores the selection.
- **A.3 Last-used default.** Creating a new room after at least one selection has been made pre-selects `art_direction.last_selected_biome_id` in the picker (visual default; not written until the user confirms or another save fires).
- **A.4 Shell prompt sourced from biome.** For room R1 with biome A selected, the bespoke shell prompt for `room_shell_foreground` includes A's `locked_direction.high_level_direction`, `locked_direction.negative_direction`, and `shell_material_description` (when present), and reference #3 image is A's `shell_material_board.selected_material_id` material image.
- **A.5 Background prompt sourced from biome.** For the same room/biome, the `background_far_plate` prompt includes A's `locked_direction.*` and the bespoke generation iterates A's `frozen_concepts` for reference images.
- **A.6 Switching biomes invalidates assets.** Selecting biome B for R1 (where biome A was selected) MUST: (i) on the next manifest refresh, list `background` and `wall_body_strip` in the asset_pack's `stale_components`; (ii) on the next generate run, produce SHA-256-distinct `R1-room-shell.png` and `R1-background.png` from the previous run. Both signals are required — a stale flag without a regenerated file means generation is short-circuiting; a regenerated file without a stale flag means the staleness fingerprint missed the change.
- **A.7 Rename and delete.** Renaming biome A to A2 updates every room's selection from A to A2 and updates `last_selected_biome_id` if it pointed at A. Deleting A nulls each affected room's selection and clears `last_selected_biome_id` if it pointed at A. In both cases, affected rooms have shell+background marked stale.
- **A.8 Migration deterministic.** A project saved before this change loads with each room's `selected_biome_id` filled to the value `_select_biome_pack_for_preview` would have returned; second load makes no further changes; a `room_biome_selection_backfill` event is logged once.
- **A.9 Validation.** A room save with an unknown biome id is rejected with a clear error; a save with `null` is accepted and falls back to implicit resolution downstream.
- **A.10 No regression in non-shell/non-background pipelines.** Other components (walls, floor, platforms, doors, midground) generate identical prompts pre/post change when no biome is selected (`null`).

---

## 6) Verification Script Pack

Run from the workspace root after implementation. Replace `<PID>` with `ashen-sentinel-9ea9be55`.

```bash
# 1) Schema slot wired
python3 - <<'PY'
import json
p = "sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/project.json"
d = json.load(open(p))
ad = d["art_direction"]
assert "last_selected_biome_id" in ad, "last_selected_biome_id missing on art_direction"
print("art_direction.last_selected_biome_id =", ad.get("last_selected_biome_id"))
PY

# 2) Room selection persisted
python3 - <<'PY'
import json
p = "sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_layout.json"
d = json.load(open(p))
rooms = d.get("rooms") or d["layout"]["rooms"]
r1 = rooms["R1"] if isinstance(rooms, dict) else next(r for r in rooms if r["id"] == "R1")
sel = ((r1.get("environment") or {}).get("room_intent") or {}).get("selected_biome_id")
print("R1.selected_biome_id =", sel)
assert sel is None or isinstance(sel, str)
PY

# 3) Resolution honors explicit selection
python3 - <<'PY'
import sys, importlib
sys.path.insert(0, "sprite-workbench/scripts")
res = importlib.import_module("room_environment_system")
direction = {"biome_packs": [{"biome_id":"A","sort_order":0}, {"biome_id":"B","sort_order":1}]}
room = {"environment": {"room_intent": {"selected_biome_id":"B"}, "preview":{"scene_plan":{"preview_biome_id":"A"}}, "spec":{"theme_id":"forest"}}}
assert res._active_preview_biome_id(room, direction) == "B"
room["environment"]["room_intent"]["selected_biome_id"] = ""
assert res._active_preview_biome_id(room, direction) == "A"
room["environment"]["preview"]["scene_plan"]["preview_biome_id"] = ""
assert res._active_preview_biome_id(room, direction) in ("A","B")
print("resolution OK")
PY

# 4) Shell prompt embeds selected biome's locked direction
python3 - <<'PY'
# Build a synthetic room+direction and call the shell prompt builder directly.
# Assert hl/nd come from biome locked direction, not project direction.
import sys, importlib
sys.path.insert(0, "sprite-workbench/scripts")
res = importlib.import_module("room_environment_system")
direction = {
    "high_level_direction": "PROJECT-HL",
    "negative_direction": "PROJECT-ND",
    "biome_packs": [{
        "biome_id":"A",
        "locked_direction": {"high_level_direction":"BIOME-HL","negative_direction":"BIOME-ND"},
        "shell_material_description":"BIOME-SHELL-DESC",
    }],
}
room = {"id":"R1","polygon":[[160,120],[1240,120],[1240,1080],[160,1080]],
        "environment":{"room_intent":{"selected_biome_id":"A"}, "spec":{}}}
plan_entry = {"target_dimensions":{"width":1600,"height":1200}, "component_type":"room_shell_foreground",
              "schema_key":"walls", "placement":{"x":800,"y":1200,"origin_x":0.5,"origin_y":1}}
template = {"variant_family":"shell"}
# Positional args mirror the signature (L9257-9269): direction, spec, plan_entry,
# template, room_geometry, dims, schema_key, component_schema, protected, placement,
# shell_rules. `room` is the new keyword param added in §4.4.b.
prompt = res._build_bespoke_prompt_room_shell_foreground(
    direction, {}, plan_entry, template, None,
    plan_entry["target_dimensions"], "walls", {}, "none", plan_entry["placement"], "",
    room=room,
)
assert "BIOME-HL" in prompt and "BIOME-ND" in prompt, prompt[:400]
assert "PROJECT-HL" not in prompt
assert "BIOME-SHELL-DESC" in prompt
# A.10 sanity: room=None must fall back to project direction with no shell brief
prompt_none = res._build_bespoke_prompt_room_shell_foreground(
    direction, {}, plan_entry, template, None,
    plan_entry["target_dimensions"], "walls", {}, "none", plan_entry["placement"], "",
    room=None,
)
assert "PROJECT-HL" in prompt_none and "BIOME-HL" not in prompt_none
assert "Shell material brief" not in prompt_none
print("shell prompt OK")
PY

# 5) Staleness fingerprint includes biome
python3 - <<'PY'
import sys, importlib, json
sys.path.insert(0, "sprite-workbench/scripts")
res = importlib.import_module("room_environment_system")
project = json.load(open("sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/project.json"))
direction = project["art_direction"]
layout = json.load(open("sprite-workbench/tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_layout.json"))
rooms = layout.get("rooms") or layout["layout"]["rooms"]
r1 = rooms["R1"] if isinstance(rooms, dict) else next(r for r in rooms if r["id"] == "R1")
deps_a = res._build_asset_component_dependency_payloads(r1, (r1.get("environment") or {}).get("spec") or {}, direction, "")
r1["environment"]["room_intent"]["selected_biome_id"] = "ruined-gothic-v1"
deps_b = res._build_asset_component_dependency_payloads(r1, r1["environment"]["spec"] or {}, direction, "")
assert deps_a["background"] != deps_b["background"], "biome change must alter background fingerprint"
print("fingerprint OK")
PY
```

---

## 7) Test Plan

### 7.1 Required automated tests

1. **`sprite-workbench/tests/test_sprite_workbench.py`** — extend with these named tests:
   - `test_room_layout_save_rejects_unknown_biome`: POST `save_room_layout` with `R1.environment.room_intent.selected_biome_id="ghost"` against a project that has biomes `["ruined-gothic-v1"]`. Assert `ValueError` (or HTTP 400 if going through the handler) with message containing `"unknown biome"`. Assert `room_layout.json` on disk is unchanged (compare mtime).
   - `test_room_layout_save_updates_last_selected_biome`: save R1 with `selected_biome_id="ruined-gothic-v1"`. Assert `project.json["art_direction"]["last_selected_biome_id"] == "ruined-gothic-v1"`.
   - `test_biome_delete_reconciles_rooms`: create biome `bx`, set R1's `selected_biome_id="bx"`, call `delete_art_direction_biome(project_id, "bx")`. Assert R1's `selected_biome_id is None`. Assert `R1.environment.runtime.asset_pack["stale_components"]` contains `"background"` and `"wall_body_strip"`.
   - `test_biome_rename_reconciles_rooms`: create `bx`, set R1 to `bx`, call `update_art_direction_biome(project_id, "bx", {"biome_id": "by"})`. Assert R1's `selected_biome_id == "by"`.

2. **`sprite-workbench/tests/test_room_layout_manifest_shell.py`** — append assertion (do not replace existing assertions):
   - Use the existing `ashen-sentinel-9ea9be55` fixture (project on disk). Pre-set R1's `selected_biome_id` to the project's first biome and pin that biome's `locked_direction.high_level_direction` to the literal string `"BIOME_HL_FIXTURE_TOKEN"` in the test setup.
   - After running the shell-attempt code path, assert: `assert "BIOME_HL_FIXTURE_TOKEN" in latest_attempt["prompt"], latest_attempt["prompt"][:400]`.
   - Also assert: `assert "PROJECT_HL_FIXTURE_TOKEN" not in latest_attempt["prompt"]` (set the project's `art_direction.high_level_direction` to that token in setup, so failure means the swap didn't happen).

3. **`sprite-workbench/tests/test_room_environment_system.py`** (create if absent):
   - `test_active_preview_biome_id_precedence`: parametrize over the 4-cell matrix `(explicit ∈ {set,unset}) × (scene_plan ∈ {set,unset})`. Expected: explicit wins when set; scene_plan wins when explicit unset; `_select_biome_pack_for_preview` fallback otherwise.
   - `test_active_preview_biome_id_falls_back_when_explicit_id_missing_from_packs`: explicit id set to `"deleted"` not in `direction.biome_packs` → returns scene_plan id (or fallback).
   - `test_resolve_active_biome_pack_returns_pack_when_explicit_set`: explicit id matches a pack → returns that pack dict (identity check, not just equality).
   - `test_resolve_active_biome_pack_returns_none_when_room_is_none`: returns `None` (NOT the project default — A.10 depends on this).
   - `test_backfill_fills_then_is_idempotent`: load a project with all rooms `selected_biome_id=null`. Call `_backfill_room_biome_selection` once → assert returns `(True, [...])` with non-empty room ids. Call again → assert returns `(False, [])`.
   - `test_biome_context_shell_material_change_invalidates_shell`: build dependency payloads for R1, change `biome_pack["shell_material_board"]["selected_material_id"]`, rebuild payloads; assert `payloads_a["wall_body_strip"]["biome_context"]["selected_material_id"] != payloads_b["wall_body_strip"]["biome_context"]["selected_material_id"]`.

4. **`sprite-workbench/tests/playwright/room-environment-biome-picker.spec.js`** (new):
   - Setup: a project with two biomes `b1`, `b2`. Open the room editor; navigate to R1 → Environment.
   - Assertions, in order:
     - `await expect(page.locator('#rwEnvBiomeList li')).toHaveCount(2);`
     - Click the radio for `b2`; click Save (or whatever the existing Environment-phase save action is). Reload the page; navigate back to R1. `await expect(page.locator('input[name="rwEnvBiome"][value="b2"]')).toBeChecked();`
     - Open R2; click `b1`; save; reload; navigate to R2: `await expect(page.locator('input[name="rwEnvBiome"][value="b1"]')).toBeChecked();`. Open R1: `await expect(page.locator('input[name="rwEnvBiome"][value="b2"]')).toBeChecked();`
     - From the Art Direction tab delete biome `b2`; reopen R1: `await expect(page.locator('input[name="rwEnvBiome"]:checked')).toHaveCount(0);`

5. **`ashen-hollow/tests/`** — no new tests. Run the existing suite to confirm zero regressions; if any test reads `room.environment.room_intent.selected_biome_id` (it should not, runtime is image-driven) flag it in the PR.

### 7.2 Manual checks (bounded — no other manual steps required)

Project: `ashen-sentinel-9ea9be55`. Run with the workbench server up.

1. **Picker present.** Open R1 → Environment tab. Pass = list shows one `<li>` per biome in `art_direction.biome_packs[]` and the empty-state element `#rwEnvBiomeEmpty` is hidden.
2. **Switch + regenerate produces fresh artifacts.** With biome A selected, click Generate → wait for completion → record SHA-256 of `tools/2d-sprite-and-animation/projects-data/ashen-sentinel-9ea9be55/room_environment_assets/R1/bespoke/R1-room-shell.png` and `…/R1-background.png`. Switch to biome B, regenerate, record the two SHA-256 values again. **Pass = both hashes differ from the biome-A run.** (Identical bytes mean the prompt swap is not effective.) Record both runs' hashes in `tests/test_report.md` under a new H2 `## Per-room biome selection — manual run`.
3. **Visual sanity (informational, not gating).** Compare `R1-room-shell.png` against `pack["shell_material_board"]` selected material image and `R1-background.png` against `pack["frozen_concepts"][0].image_path`. Note any obvious mismatch in the report; do not block on subjective similarity.
4. **Rename roundtrip.** From Art Direction, rename biome A to A-renamed. Reopen R1. Pass = the picker has A-renamed checked (i.e. the radio with `value="A-renamed"`).

Do not perform any other manual checks — the rest is covered by §7.1.

---

## 8) Execution Order

1. **§4.1** add `last_selected_biome_id` normalize.
2. **§4.2** `_active_preview_biome_id` precedence change.
3. **§4.3** rename/delete reconciliation helper + wiring.
4. **§4.7** staleness fingerprint extension.
5. **§4.4** prompt builder swap (shell + background) — this is the behavior-visible step.
6. **§4.5** UI picker + wiring.
7. **§4.6** server-side validation + `last_selected_biome_id` write.
8. **§4.8** migration backfill.
9. Run §6 verification scripts.
10. Run §7 automated tests; capture results in `tests/test_report.md`.
11. Manually verify §7.2 in the workbench against `ashen-sentinel-9ea9be55`, regenerating R1's shell + background.
12. **§4.9** sync canonical `room-layout-data.json` from the project.
13. **§4.10** update `downstream-biome-selection.md`.
14. Commit per repo (sprite-workbench first; orchestrator submodule bump after) per `MV/CLAUDE.md`.

---

## 9) Out of Scope

- Multi-biome per room (separate shell vs background biome).
- Biome thumbnails endpoint or pre-resized cache.
- Cross-room biome propagation (e.g. "set all rooms to biome X" bulk action).
- Biome selection from the Map / world view.
- Changes to non-bespoke procedural background or non-shell components' biome handling beyond what falls out of §4.4 fallbacks.
- Ashen Hollow runtime behavior — biome selection is an authoring concern; runtime remains image-driven and unchanged.

---

## 10) Commit Message

```
feat(room-env): per-room biome selection drives shell + background generation
```
