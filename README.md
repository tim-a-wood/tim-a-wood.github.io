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
   - Example: `https://your-username.github.io/your-repo/?v=activity6dungeon5`
2. **Current cache-bust value:** `activity6dungeon5` (update this when you deploy and want clients to refresh).

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

## Local Room Editor

Do not open `room-layout-editor.html` as a raw file — run a local HTTP server so **Sync Canonical JSON** and **Environment Copilot** work.

**Recommended: Sprite Workbench** (one process for sprites + room layout + Copilot). The workbench server exposes:

- **`GET` / `POST` `/api/layout`** — read/write repo-root **`room-layout-data.json`** (canonical sync when not using `?project_id=…`)
- **`GET` `/api/ping`**, **`POST` `/api/copilot`** — Environment Copilot (Gemini)
- **`/api/projects/…/room-layout`** — per-project layout when the editor URL includes **`project_id`**

```bash
./scripts/start_sprite_workbench_with_env.sh
```

Then open **`/room-layout-editor.html`** on the same host/port (defaults are documented in the launcher; often port **8766**).

Local editor workflow:

1. Edit the layout in the browser.
2. Click **Sync Canonical JSON** to overwrite `room-layout-data.json` (or use project sync when linked to a workbench project).
3. Open the game from the editor to test against that file.
4. Run `git add room-layout-data.json && git commit && git push`.

If you open the editor outside a server that implements those routes, canonical sync is unavailable — use **Export JSON** instead.

**Environment Copilot (Gemini):** In **Room wizard → Environment**, describe a room’s mood; the server calls Gemini using **`GEMINI_API_KEY`** from **`.env.local`**. Restart after env changes. Optional **`GEMINI_MODEL`** (default `gemini-2.5-flash`). Nothing is applied until you click **Apply**; the game never calls Gemini at runtime.

**Validation (Level 1–3):** Canonical definitions, check IDs (`L1-001`, `L2-001`, …), and the **user-docs placeholder** (`DOC-ROOM-VALIDATION-001`) live in [`docs/room-layout-validation.md`](docs/room-layout-validation.md). Level 2 thresholds are project conventions, not an external industry standard; tune via `VALIDATION_L2` in the editor script.

## Solo AI Sprite Workbench

The sprite workbench lives at `tools/2d-sprite-and-animation/index.html` and uses a local filesystem-backed API server.

Install the tool-local Python dependency first:

```bash
python3 -m pip install -r tools/2d-sprite-and-animation/requirements.txt
```

The default concept backend is local `ComfyUI` at `http://127.0.0.1:8188`.
Optional environment overrides:

```bash
export SPRITE_WORKBENCH_COMFYUI_URL=http://127.0.0.1:8188
export SPRITE_WORKBENCH_COMFYUI_CHECKPOINT=sd15.safetensors
export SPRITE_WORKBENCH_COMFYUI_JOB_TIMEOUT_SECONDS=600
```

`SPRITE_WORKBENCH_COMFYUI_JOB_TIMEOUT_SECONDS` is the per-image generation timeout used by the workbench server.

Create a local env file once, then paste your Gemini API key into it:

```bash
cp .env.local.example .env.local
```

Expected variable in `.env.local`:

```bash
export GEMINI_API_KEY="paste_key_here"
```

Canonical launch flow:

```bash
./scripts/start_sprite_workbench_with_env.sh
```

Then open:

```text
http://127.0.0.1:8766/tools/2d-sprite-and-animation/index.html
```

Advanced fallback, if you want to bypass the launcher and manage env loading yourself:

```bash
source .env.local
python3 scripts/sprite_workbench_server.py --host 127.0.0.1 --port 8766
```

### Agent OS dashboard (local supervisor)

To use **Agent OS** (`os-dashboard.html`) with live **Engineering** data and **Start / Restart / Stop** for the workbench from the dashboard:

1. Add `OS_DASHBOARD_SUPERVISOR_TOKEN` to `.env.local` (see `.env.local.example`).
2. Start the supervisor and open the browser in one step:

```bash
bash scripts/start_agent_os_dashboard.sh
```

Or double-click **`Agent-OS-Dashboard.command`** in the repo root (opens a brief Terminal session).

**Dock / one-click (no Terminal window):** run once:

```bash
bash macos/install_agent_os_launcher_app.sh
```

That installs **`Agent OS Dashboard.app`** into `~/Applications`. Drag it to the **Dock** (or keep it in Applications). Each launch starts the supervisor if needed and opens the dashboard.

**Menu bar (Shortcuts):** Shortcuts → **+** → add **Run Shell Script** (shell: `/bin/bash`), paste (fix the path to your clone):

```bash
cd "/Users/timwood/Desktop/projects/PWA/MV" && bash scripts/start_agent_os_dashboard.sh
```

Turn on **Pin in Menu Bar** for the shortcut (shortcut settings).

3. Default URL: `http://127.0.0.1:8769/os-dashboard.html` (supervisor port `8769`).
4. In **Engineering → Workbench Server**, paste the **same** value as `OS_DASHBOARD_SUPERVISOR_TOKEN` from `.env.local` and click **Save token** (stored in the browser tab only).

The supervisor binds **127.0.0.1** only, serves the dashboard and `/api/dashboard-data`, and controls the workbench on **8766** by default (`--workbench-port` to override). Override ports with `OS_DASHBOARD_SUPERVISOR_PORT` / `OS_DASHBOARD_WORKBENCH_PORT` if needed.

The server writes local-first project data and exports under `tools/2d-sprite-and-animation/projects-data/`.

Current workbench notes:

- Concept generation and refinement are ComfyUI-backed by default.
- A debug procedural backend still exists, but only when explicitly selected in the UI.
- New downstream writes use the canonical files only: `sprite_model.json`, `sprite_model_history.json`, `rig.json`, `animation_clips.json`, and `qa_report.json`.
- Legacy `layered_character.json`, `animation_templates.json`, and `palette.json` are hydration-only inputs for older projects and fixtures.
- Sprite-model builds now emit a `build_report` with pass, warning, and fail states. Failures block approval in the UI.
- The sprite-model editor supports direct bbox and pivot manipulation, mask rectangle edits, recovery promotion, undo, and revision restore.
- Idle and walk clips are per-project deterministic clips stored in `animation_clips.json`, with editable high-level controls in the workbench.
- Export verification now checks the packed spritesheet pixels and atlas order after packing, not just the pre-pack frame manifest.
- References are copied into each project under `references/` and recorded in `history.json`.

Canonical route and file contract notes live in `tools/2d-sprite-and-animation/docs/CANONICAL-DOWNSTREAM-CONTRACT.md`.

Sprite workbench regression tests:

```bash
python3 -m unittest tests.test_sprite_workbench
```

Fixture matrix for migration and canonical downstream coverage lives under `tests/fixtures/sprite_workbench/`.

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
