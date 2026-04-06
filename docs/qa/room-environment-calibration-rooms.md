# Room environment calibration rooms (locked default)

**Status:** Default set chosen by engineering/orchestration on behalf of the founder (2026-04-06). Replace this list only when you intentionally change the calibration scope.

## Canonical room IDs (map layouts)

Use these room ids in the room layout / editor when capturing states, running manual QA, or comparing before/after bundles:

| Priority | Room ID | Role (see `docs/map-graph-v1.md`) |
|----------|---------|-------------------------------------|
| **1 — default** | `R1` | Spawn + final gate chamber; use this whenever a single room is enough (matches most unit tests). |
| **2** | `R2` | Central hub; different topology and connections than `R1`. |
| **3** | `R9` | Final area; distinct purpose from hub/spawn. |

**Minimum bar:** Always support **`R1`**. Run the full three-id set when milestone 6-style calibration calls for multiple room-level reports (`docs/reports/room-environment-mvp-qa-regression-plan.md`).

## Scripted capture fixture (not the same id)

`scripts/capture_room_results_states.js` embeds a synthetic room id **`QA-R1`**. That is intentional: headless capture uses a self-contained fixture. Do not assume `QA-R1` equals the playable map’s `R1` layout; when documenting capture output, name the fixture explicitly.

## Preview inputs (room environment)

Gemini **room preview** images use the layout guide plus **project frozen concept art** (resolved per biome pack `locked_concept_ids` when set). There is **no** client upload path for extra preview references; steer style via art direction and concept board.

## Related

- Map graph: `docs/map-graph-v1.md`
- Regression plan: `docs/reports/room-environment-mvp-qa-regression-plan.md`
