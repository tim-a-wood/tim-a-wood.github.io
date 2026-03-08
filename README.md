# Ashen Hollow

Dark-fantasy metroidvania prototype built as a single-file Phaser game in `index.html`.

## Project Shape

- Monolithic prototype: gameplay, UI, and styles currently live in `index.html`
- Hosted on GitHub Pages
- `manifest.json` is present for install metadata
- No service worker is shipped during rapid iteration, to avoid stale cached builds on devices

## Always see the latest build (GitHub Pages / cache)

Browsers and CDNs often cache `index.html`. To force the latest version:

1. **Use a versioned URL** — Add `?v=XXXX` to the game URL. The current value is in the page source (search for `CACHE_BUST`) or below. We bump it when we deploy, so this URL always bypasses cache.
   - Example: `https://your-username.github.io/your-repo/?v=fa5d8ac`
2. **Current cache-bust value:** `fa5d8ac` (update this when you deploy and want clients to refresh).

The page also sends `Cache-Control: no-cache` via meta tags so some clients may revalidate without the query param.

## Level layout viewer

Open `level-viewer.html` in a browser (or via your local server) to visualize draft platform layouts without running the full game. Use the **Layout** dropdown to compare options (e.g. **F — Guide-based single room**, from `prompts/metroidvania_single_room_guide.md`). Plan: `prompts/labyrinth_layout_plan.md`.

## MVP planning dashboard

Open `plan-dashboard.html` to track the full Map MVP activity/task plan, progress totals, and burndown chart.

- Uses browser `localStorage` for task completion state and completion dates
- Includes schedule controls (start/target date) that drive the ideal burndown line
- Includes actual burndown from task completion timestamps

## Map graph viewer

Open `map-graph-viewer.html` to visualize the MVP room graph and inspect each room's role before freezing topology.

- Click any room node to see purpose, interactables, timing target, respawn behavior, and connections
- Shows critical flow and final-gate dependency (`key_items_collected == 3` and `abilities_unlocked == 3`)
- Draft source spec lives in `docs/map-graph-v1.md`

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
