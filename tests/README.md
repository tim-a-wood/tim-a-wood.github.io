# Tests

Unit tests for the metroidvania PWA. Game logic lives in `index.html`; these tests duplicate deterministic algorithms to verify behavior without loading Phaser.

**Keep in sync:** When changing the RNG or pit-zone logic in `index.html`, update the corresponding logic in `tests/game-logic.test.js`.

## Run

```bash
node tests/game-logic.test.js
```

Exit code 0 = pass; non-zero or uncaught exception = fail.
