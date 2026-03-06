# Ashen Hollow

Dark-fantasy metroidvania prototype built as a single-file Phaser game in `index.html`.

## Project Shape

- Monolithic prototype: gameplay, UI, and styles currently live in `index.html`
- Hosted on GitHub Pages
- `manifest.json` is present for install metadata
- No service worker is shipped during rapid iteration, to avoid stale cached builds on devices

## Local Run

Use a simple local HTTP server instead of opening the file directly.

### Option 1: VS Code / Cursor

- Install `Live Server`
- Open `index.html`
- Run `Open with Live Server`

### Option 2: Python

```bash
python3 -m http.server 8765
```

Then open `http://127.0.0.1:8765/`.

To test on an iPhone on the same Wi-Fi, use your computer's LAN IP instead of `127.0.0.1`.

## Controls

- Keyboard: arrow keys for movement, `Up` or `Space` to jump
- Touch: on-screen left, right, and jump buttons

## Tests

- Unit tests: `tests/game-logic.test.js`
- Acceptance checklist: `tests/acceptance_tests.md`
- Per-change test report: `tests/test_report.md`

See `tests/README.md` for the current automated coverage scope.

## Project Docs

- `prompts/project_overview.md` - scope, architecture, conventions
- `prompts/project_plan.md` - milestones, current state, next steps
- `tests/README.md` - automated test notes

## Current Focus

- Stabilize movement and double-jump behavior
- Keep deployment simple and fresh on GitHub Pages
- Expand toward the first real ability gate and progression loop