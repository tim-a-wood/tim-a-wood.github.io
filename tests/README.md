# Tests

Unit tests for the metroidvania PWA. Game logic lives in `index.html`; these tests duplicate deterministic algorithms to verify behavior without loading Phaser.

**Current coverage:**
- Seeded RNG helper behavior retained for future procedural terrain work
- Legacy pit-zone helper behavior retained for regression safety
- Current movement rules from `handleMovement()`:
  - horizontal movement and friction
  - jump refill rules
  - first jump / second jump state transitions
  - jump buffer behavior
  - edge cases around upward velocity and exhausted jumps
- Current first-zone layout expectations from `buildFirstZone()`

**Keep in sync:** When changing the movement, jump, or zone-layout logic in `index.html`, update the corresponding helpers in `tests/game-logic.test.js`.

## Run

```bash
node tests/game-logic.test.js
```

Exit code 0 = pass; non-zero or uncaught exception = fail.
