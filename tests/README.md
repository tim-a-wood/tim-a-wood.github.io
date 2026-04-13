# Tests

Unit tests for the metroidvania PWA. Game logic lives in `index.html`; these tests duplicate deterministic algorithms to verify behavior without loading Phaser.

**Unified shell placement (R1 baseline):** `tests/unified_shell_hole_baseline.test.py` — synthetic disconnected-hole raster plus optional check against local `R1-room-shell.png` when `tools/2d-sprite-and-animation/projects-data/` is present (gitignored). Golden numbers: `tests/fixtures/unified_shell_r1_placement_baseline.json`. Doc: `docs/baselines/unified-shell-placement-r1.md`.

**Current coverage:**
- Room wizard **footprint helper** (`room-layout-wizard-footprint.js`) — see `tests/room-wizard-footprint.test.js`
- Room layout **runtime export package** (`room-layout-export-package.js`): manifest, per-room runtime slice, `movingPlatforms` key — see `tests/room-editor-export.test.js`
- Seeded RNG helper behavior retained for future procedural terrain work
- Legacy pit-zone helper behavior retained for regression safety
- Current movement rules from `handleMovement()`:
  - horizontal movement and friction
  - jump refill rules
  - first jump / second jump state transitions
  - jump buffer behavior
  - edge cases around upward velocity and exhausted jumps
- Current first-zone layout expectations from `buildFirstZone()`

**Acceptance artifacts:**
- `tests/acceptance_tests.md` contains the manual high-level acceptance checklist
- `tests/test_report.md` contains the per-change test report table for acceptance results plus the overall unit-suite result

**Keep in sync:** When changing the movement, jump, or zone-layout logic in `index.html`, update the corresponding helpers in `tests/game-logic.test.js`.

## Run

```bash
node tests/game-logic.test.js && node tests/room-editor-export.test.js && node tests/room-wizard-footprint.test.js
```

Exit code 0 = pass; non-zero or uncaught exception = fail.
