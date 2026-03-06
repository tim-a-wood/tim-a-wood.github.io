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
- **Gameplay:** "Neon Drifter Infinite" — procedural infinite runner (forward scroll, pits, platforms, jump/run). Not yet metroidvania (no bounded world, abilities, or gates).
- **Tech:** HTML/JS, Phaser 3 (Arcade Physics), deterministic seeded RNG, texture generation at runtime. No external art assets.
- **Quality:** Unit tests in `./tests/` for RNG and pit-zone logic; CI via `.github/workflows/test.yml`.
- **Docs:** `prompts/project_overview.md`, this plan, `README.md`, `tests/README.md`.

---

## Milestones

| # | Milestone | Description |
|---|-----------|-------------|
| **M1** | **Playable prototype** | ✅ Current: infinite runner with movement, procedural terrain, lives, restart. |
| **M2** | **Bounded world** | Replace infinite scroll with a fixed, explorable map (rooms or zones) and camera/world bounds. |
| **M3** | **First ability gate** | One new ability (e.g. double jump or dash) and at least one area/route that requires it. |
| **M4** | **Backtracking & progression** | Clear loop: gain ability → revisit earlier area → open new path. Save/load or persistent progress (e.g. localStorage). |
| **M5** | **PWA polish** | Manifest, service worker, installability, and reliable offline/refresh behavior on GitHub Pages. |
| **M6** | **Expand content** | Additional abilities, areas, and gates as scope allows. |
| **M7** | **Combat, bosses & loot** | Combat feel and depth; at least one signature boss fight; unique loot/upgrades that support the dark-fantasy metroidvania pillars. |

---

## Next Steps

- [ ] **Align naming with plan** — If keeping "Neon Drifter" as the title, consider whether "Infinite" stays or is renamed as the game shifts to a bounded, dark-fantasy metroidvania.
- [ ] **PWA basics** — Add `manifest.json` and a minimal service worker so the app is installable and cacheable.
- [ ] **Design first bounded map** — Decide format (tilemap, procedural chunks with fixed seed, or hand-placed rooms) and implement world bounds + one explorable zone. Aim for maze-like, interconnected feel where appropriate.
- [ ] **Introduce first ability** — Implement one movement or utility ability and one gate (e.g. high ledge or gap that requires it); prioritize smooth, satisfying feel (see design pillars).
- [ ] **Keep tests in sync** — When changing RNG, pit logic, or new deterministic systems, add or update tests in `./tests/` and run `node tests/game-logic.test.js` (and CI) before committing.

---

## How to Use This Plan

- **Before starting work:** Read this file and `prompts/project_overview.md` to stay aligned with goals and architecture.
- **After completing work:** Update "Current State" and "Next Steps" if the product or priorities changed; tick or add milestones as needed.
- **When in doubt:** Prefer incremental, testable changes and keep `index.html` and tests consistent.
