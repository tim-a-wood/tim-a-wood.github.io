# Project Plan

**Purpose:** Keep current goals, milestones, and next steps in one place for human and AI contributors. Update this file as the project evolves.

---

## Game Direction (vision)

- **Theme:** Dark fantasy metroidvania — atmospheric, moody world that supports exploration and combat.
- **Inspirations:** Hollow Knight (atmosphere, world structure, combat, bosses), Prince of Persia: The Lost Crown (movement, platforming, metroidvania structure).
- **Pillars:** Combat, smooth movement & platforming, cool boss fights, maze-like dungeon crawling, and unique loot. See `prompts/project_overview.md` for full design pillars.

---

## Current Goals

1. **Deliver a metroidvania PWA** — Exploration, backtracking, and ability-gated progression, playable in the browser and installable (e.g. via GitHub Pages). Align with dark fantasy theme and design pillars (combat, movement, bosses, maze-like dungeons, unique loot).
2. **Grow the game incrementally** — Add features, areas, and mechanics over time rather than building everything at once.
3. **Support agentic workflows** — Keep structure, naming, and docs (including this plan) clear so AI-assisted coding and refactors stay aligned.

---

## Current State (as of plan creation)

- **Codebase:** Single `index.html` with Phaser 3; monolithic layout for simplicity and portability.
- **Gameplay:** **Ashen Hollow** (placeholder dark-fantasy name) — bounded world with one explorable zone: fixed width (1600px), hand-placed floor and platforms, camera and physics bounds. No infinite scroll; no abilities or gates yet.
- **Tech:** HTML/JS, Phaser 3 (Arcade Physics), texture generation at runtime. No external art assets. `manifest.json` is present; service-worker caching is intentionally disabled during rapid iteration on GitHub Pages to avoid stale installs.
- **Quality:** Unit tests in `./tests/` (RNG/pit helpers retained for possible future procedural terrain); CI via `.github/workflows/test.yml`.
- **Docs:** `prompts/project_overview.md`, this plan, `README.md`, `tests/README.md`.

---

## Milestones

| # | Milestone | Description |
|---|-----------|-------------|
| **M1** | **Playable prototype** | ✅ Current: infinite runner with movement, procedural terrain, lives, restart. |
| **M2** | **Bounded world** | ✅ Replace infinite scroll with a fixed, explorable map (rooms or zones) and camera/world bounds. |
| **M3** | **First ability gate** | One new ability (e.g. double jump or dash) and at least one area/route that requires it. |
| **M4** | **Backtracking & progression** | Clear loop: gain ability → revisit earlier area → open new path. Save/load or persistent progress (e.g. localStorage). |
| **M5** | **PWA polish** | Manifest, installability, and later offline/service-worker behavior once the build is stable on GitHub Pages. |
| **M6** | **Expand content** | Additional abilities, areas, and gates as scope allows. |
| **M7** | **Combat, bosses & loot** | Combat feel and depth; at least one signature boss fight; unique loot/upgrades that support the dark-fantasy metroidvania pillars. |

---

## Next Steps (Atomic)

These steps are small, independent units of work. Each can be done in one or two commits. Order is suggested below; dependencies are noted where relevant.

### 1. Naming / branding (low risk)

- [x] **Decide and apply title**
  - **What:** Choose whether to keep "Neon Drifter Infinite" or rename (e.g. drop "Infinite", or adopt a new dark-fantasy name). Apply the decision everywhere the title appears.
  - **Where:** `index.html` (e.g. `<title>`, any visible heading or splash text), and any docs (README, overview) that reference the game name.
  - **How:** Single find/replace or manual edit so the visible title and comments match the decision. No gameplay or logic changes.
  - **Why:** Avoids confusion as features are added and keeps branding aligned with the shift from infinite runner to bounded metroidvania.

---

### 2. PWA basics (M5 — can be done early and independently)

- [x] **Add `manifest.json`**
  - **What:** Web app manifest so the app can be installed (e.g. "Add to Home Screen").
  - **Fields to include:** `name`, `short_name`, `icons` (or placeholders), `start_url`, `display: "standalone"`. Use paths that work when deployed (e.g. on GitHub Pages).
  - **Where:** One new file at project root (or a dedicated `public/` if you introduce one). Link from `index.html` via `<link rel="manifest" href="manifest.json">`.
  - **Scope:** One file only; no refactor of game code.

- [x] **Defer service worker during prototyping**
  - **What:** Do **not** ship a service worker while gameplay and deployment are changing frequently.
  - **Why:** Avoid stale cached `index.html` revisions and hard-to-debug install/update issues on GitHub Pages and iPhone home-screen installs.
  - **When to revisit:** Reintroduce a service worker later in M5 once the build is stable enough to justify offline support and cache management.

---

### 3. Bounded world (M2) — split into small steps

- [x] **Lock camera to world**
  - **What:** Replace infinite horizontal scroll with a fixed world width. Camera stays within that width; no new rooms or zones yet.
  - **How:** Introduce a world width (constant or from a simple config). Update camera logic so it does not scroll beyond 0 and world width (e.g. `camera.setBounds(0, 0, worldWidth, height)` and clamp camera position). Player movement can still use the same physics; only the "endless" generation or scroll is removed or capped.
  - **Outcome:** Visually and behaviorally, the world has left/right limits; no infinite runner feel.

- [x] **Define "one zone"**
  - **What:** Pick a format for a single explorable area (e.g. one room, or a few hand-placed platforms in a fixed layout). Implement one zone so there is a concrete place to explore.
  - **Format options:** Single room, a small hand-placed layout, or one procedural "chunk" with a fixed seed—whichever fits the codebase and design. No need for multiple rooms or doors yet.
  - **Outcome:** One explorable zone (e.g. one screen or one chunk) that the player can move through, with platforms/terrain defined by that format.

- [x] **Add world bounds in physics**
  - **What:** Set Phaser world bounds (and any body boundaries) to the playable area (the one zone or full map) so the player and camera never leave the intended region.
  - **How:** Use `this.physics.world.setBounds(...)` (and camera bounds if not already set) to match the zone or map size. Ensures no falling into the void or walking past the level edges.
  - **Outcome:** Solid, predictable boundaries for movement and camera; foundation for adding more zones later.

You can combine "camera + one zone + bounds" in one or two small steps if preferred.

---

### 4. First ability gate (M3) — two atoms

- [x] **Implement one ability**
  - **What:** One new movement or utility ability—e.g. double jump or dash. Include input handling, state (e.g. "can double jump" / "has dashed"), and the actual movement effect.
  - **Scope:** No gates yet; the ability just works in the existing space. Prioritize smooth, satisfying feel (see design pillars in `project_overview.md`).
  - **Outcome:** Player can use the ability at will within the current bounds; no save/load or persistence required for this step.
  - **Done:** Double jump added in `index.html`: state `doubleJumpAvailable`, refilled on land, consumed on mid-air jump; same jump force as first jump for consistent feel.

- [ ] **Add one gate**
  - **What:** One place in the first zone that is unreachable without the new ability (e.g. high ledge, gap, or blocked path). When the player has the ability, they can reach it.
  - **Scope:** Single gate; no full backtracking loop or save system yet. Proves the "ability-gated progression" idea.
  - **Outcome:** Clear before/after: without ability you cannot reach the spot; with ability you can. Sets up M4 (backtracking & progression) later.

---

### 5. Tests (recurring)

- [ ] **After any RNG or pit/terrain change**
  - **What:** Add or update tests in `./tests/` for any changed or new deterministic logic (e.g. RNG, pit zones, terrain generation).
  - **How:** Run `node tests/game-logic.test.js` (and ensure CI in `.github/workflows/test.yml` still passes). Add new test cases for new behavior.
  - **When:** Treat this as a recurring atomic step whenever you touch those systems—not necessarily every PR, but before considering the feature "done."

---

## Suggested order of execution

| Order | Step | Why |
|-------|------|-----|
| 1 | Naming decision + apply | Quick, avoids confusion as you add features. |
| 2 | `manifest.json` | One file, no refactor, moves you toward PWA (M5). |
| 3 | Defer service worker | Keeps GitHub Pages and iPhone installs loading the latest build during rapid iteration. |
| 4 | Camera + world bounds + one zone | Core of M2; enables "explorable map" instead of infinite runner. |
| 5 | First ability | Unlocks M3. |
| 6 | First gate | Completes "ability-gated progression" for one place. |

Tests (step 5) are ongoing: run and extend them whenever you change RNG, pit logic, or terrain.

---

## How to Use This Plan

- **Before starting work:** Read this file and `prompts/project_overview.md` to stay aligned with goals and architecture.
- **After completing work:** Update "Current State" and "Next Steps" if the product or priorities changed; tick or add milestones as needed.
- **When in doubt:** Prefer incremental, testable changes and keep `index.html` and tests consistent.
