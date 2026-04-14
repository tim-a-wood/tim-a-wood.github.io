# Baseline: room environment R1 (scenic + unified shell, no duplicate background rim)

**Status:** Locked after founder confirmation that runtime review looks correct with **`background_far_plate` on guide-only Gemini references** (no footprint silhouette image).

## What is baselined

1. **Pipeline contract:** `background_far_plate` uses **`_structural_slot_reference_guide` only** in `_bespoke_reference_images_for_component` — no prepended `_write_bespoke_room_silhouette_reference` — so the far plate does not inherit a second stone frame cue on top of `room_shell_foreground`.
2. **QA room:** Project **`room-ai-helpfulness-qa-67562113`**, room **R1**, with unified shell assets and regenerated **`R1-background.png`** after the server/code restart.
3. **Visual proof (local):** **`room_environment_assets/R1/review/runtime-review.png`** is the founder-checked composite for this lock (file under `projects-data`, may be gitignored).

## Decisions

- **§226–§227** — anti–double-shell prompts + drop silhouette from `background_far_plate` refs  
- **§214–§216** — unified shell hole measurement and R1 placement golden numbers (`tests/fixtures/unified_shell_r1_placement_baseline.json`)  
- **§217** — runtime review occlusion off when unified shell present (no extra rectangular frame read)

## Machine-readable baseline

- `tests/fixtures/room_environment_r1_scenic_baseline.json` — project/room ids, decision list, artifact paths, `guide_only` contract flag.

## Regression tests

- `tests/room_environment_r1_scenic_baseline.test.py` — validates fixture shape and contract string in CI.

## Optional git tag

To mark the repo at this baseline for bisect and human reference:

```bash
git tag -a baseline/room-environment-r1-scenic-2026-04-14 -m "R1 room env: scenic stack + unified shell; background guide-only refs (§228)"
git push origin baseline/room-environment-r1-scenic-2026-04-14
```
