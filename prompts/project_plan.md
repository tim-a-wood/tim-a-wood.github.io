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

## Current State

- **Codebase:** Single `index.html` with Phaser 3; monolithic layout for simplicity and portability.
- **Gameplay:** **Ashen Hollow** — bounded world (3200×1200): room 1 (right, 1600–3200) is the Hollow Knight–style cave with key/door; room 2 (left, 0–1600) is reached through the unlocked door and has a reachable exit in the top left. Camera/world bounds, lives, restart, double jump (relic-unlock), key-to-door loop, and exit trigger in room 2.
- **Tech:** HTML/JS, Phaser 3 (Arcade Physics), texture generation at runtime. No external art assets. `manifest.json` is present; service-worker caching is intentionally disabled during rapid iteration on GitHub Pages to avoid stale installs.
- **Quality:** Unit tests in `./tests/` cover current movement/jump state logic and first-zone layout; CI via `.github/workflows/test.yml`. Manual acceptance checks live in `tests/acceptance_tests.md`, with per-change outcomes recorded in `tests/test_report.md`.
- **Docs:** `prompts/project_overview.md`, this plan, `README.md`, `tests/README.md`, `tests/acceptance_tests.md`, and `tests/test_report.md`.

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

## Map MVP Execution Plan (10-15 Minute In-Game Run)

This section captures the locked high-level activities and expands each into atomic procedural tasks. Each activity produces explicit downstream inputs that should be used by the next activity.

### Activity 1. Lock MVP Constraints

Scope of work: align product boundaries and prevent scope creep.

- [ ] Create `/Users/timwood/Desktop/projects/PWA/MV/docs/map-mvp-constraints.md`.
- [ ] Document fixed goals: 10-15 minute run, final gate visible beside spawn in `R1`, 3-sigil progression.
- [ ] Document non-goals: no branching endings, no extra biome branches, no large progression tree beyond 3 unlocks.
- [ ] Write player success statement: collect 3 sigils, return to `R1`, unlock gate, clear final area.
- [ ] Define timing assumptions: first-time target 12 minutes, acceptable 10-15.
- [ ] Define content constraints: rooms `R1-R10`, one final area, one exit.
- [ ] Define logic constraint: final unlock condition `sigils_collected == 3`.
- [ ] Review and resolve ambiguous wording with stakeholders.
- [ ] Add change-control rule: changes to constraints require explicit sign-off.
- [ ] Mark the constraints doc approved with date and version.

Downstream input: immutable scope contract for topology, unlocks, scripting, and QA.

### Activity 2. Lock Map Graph and Room Purposes

Scope of work: finalize traversal graph and room intent.

- [ ] Create `/Users/timwood/Desktop/projects/PWA/MV/docs/map-graph-v1.md`.
- [ ] Define canonical room IDs and names for `R1-R10`.
- [ ] Write adjacency list for all valid room transitions.
- [ ] Validate dead ends are only intentional endpoints.
- [ ] Assign one primary purpose per room (orientation, hub, challenge, sigil, final, exit).
- [ ] Assign one secondary purpose per room (teaching, pressure ramp, recovery, payoff).
- [ ] Define required interactables per room (doors, sigil pedestal, checkpoint, switches).
- [ ] Define return paths from each branch to hub/spawn.
- [ ] Define respawn anchors (`R1`, `R2`, pre-`R9`).
- [ ] Paper-simulate ideal player route.
- [ ] Paper-simulate confused player route.
- [ ] Fix topology issues and freeze graph v1.

Downstream input: room topology and purpose matrix for progression and level blockout.

### Activity 3. Define Progression Unlocks (1 Hard-Gate + 2 Soft-Power)

Scope of work: design minimal progression tied to map flow.

- [ ] Create `/Users/timwood/Desktop/projects/PWA/MV/docs/progression-unlocks-v1.md`.
- [ ] Assign sigils to branches: `A -> R4`, `B -> R6`, `C -> R8`.
- [ ] Define hard-gate unlock (recommended `Sigil A`) used in one required branch barrier.
- [ ] Define soft-power unlock 1 (recommended `Sigil B`) with one pre-final usage moment.
- [ ] Define soft-power unlock 2 (recommended `Sigil C`) with one pre-final usage moment.
- [ ] Specify pickup trigger and immediate UI/audio feedback for each unlock.
- [ ] Specify forced/obvious first usage moments before final room.
- [ ] Define behavior if soft-power usage is skipped (run remains completable).
- [ ] Write concise pickup/status copy tied to landmarks or color-coded doors.
- [ ] Validate unlock set does not push run time beyond 15 minutes.
- [ ] Validate unlock set does not permit sequence breaks.
- [ ] Freeze unlock table v1.

Downstream input: progression table for gate-state logic, encounter placement, and UX messaging.

### Activity 4. Define Gate and State Logic

Scope of work: implement deterministic progression state machine.

- [ ] Create `/Users/timwood/Desktop/projects/PWA/MV/docs/gate-state-spec-v1.md`.
- [ ] Define state variables: `sigils_collected`, `sigil_a`, `sigil_b`, `sigil_c`, `final_gate_state`.
- [ ] Define valid gate states: `LOCKED_0`, `LOCKED_1`, `LOCKED_2`, `UNLOCKED_3`.
- [ ] Define transition rules on sigil pickup and on reload/resume.
- [ ] Define visuals for each state (runes, lights, effects, audio cue).
- [ ] Define interact text for each state (`Requires 3 Sigils`, `2/3 Collected`, etc.).
- [ ] Add idempotency rule to prevent duplicate pickup corruption.
- [ ] Define save/restore behavior for in-progress runs.
- [ ] Define reset behavior for new runs.
- [ ] Define telemetry hooks: `sigil_pickup`, `gate_state_changed`, `gate_unlocked`.
- [ ] Write test matrix for all valid and invalid transitions.
- [ ] Freeze logic contract for implementation.

Downstream input: implementation-ready gate state machine and QA transition test cases.

### Activity 5. Greybox Critical Path (`R1`, `R2`, `R9`, `R10`)

Scope of work: prove full-loop viability early using placeholder content.

- [ ] Create greybox scenes/layouts for `R1`, `R2`, `R9`, `R10`.
- [ ] Place spawn in `R1` with immediate line-of-sight to the locked final gate.
- [ ] Add gate interactable and temporary gate-state UI in `R1`.
- [ ] Build `R1 <-> R2` traversal path with low friction.
- [ ] Add temporary debug bypass to access `R9` before full branch completion.
- [ ] Greybox `R9` final encounter shell with placeholder logic.
- [ ] Greybox `R10` exit room with completion trigger.
- [ ] Add temporary objective signage in `R1` and `R2`.
- [ ] Time traversal from spawn to hub and back to gate.
- [ ] Adjust room scale/distances for pacing.
- [ ] Run smoke test: spawn, gate text, unlock path, final completion.
- [ ] Mark critical path playable.

Downstream input: playable backbone for branch integration and pacing calibration.

### Activity 6. Build Branch A/B/C Passes (`R3-R8`)

Scope of work: implement three distinct branches with one sigil reward each.

- [ ] Greybox `R3-R8` based on frozen graph.
- [ ] Implement Branch A (`R3`, `R4`) with hard-gate usage and Sigil A reward.
- [ ] Implement Branch B (`R5`, `R6`) with distinct mechanic profile and Sigil B reward.
- [ ] Implement Branch C (`R7`, `R8`) as highest pre-final pressure branch with Sigil C reward.
- [ ] Add deterministic return route from each branch back to hub/spawn.
- [ ] Add branch completion flags and hook them to gate-state updates.
- [ ] Add distinct visual identity per branch (color, icon, landmark).
- [ ] Validate each branch duration against target.
- [ ] Validate each branch works independently and in any completion order.
- [ ] Run sequence tests: `A-B-C`, `B-C-A`, `C-A-B`.
- [ ] Fix order-dependent bugs and sequence breaks.
- [ ] Freeze branch behavior v1.

Downstream input: complete playable map loop with functional progression.

### Activity 7. Add Navigation Readability

Scope of work: ensure players can self-navigate without external instruction.

- [ ] Define branch color/icon language and apply it to doors, markers, and UI.
- [ ] Add objective sign in `R1`: collect 3 sigils to unlock the final gate.
- [ ] Add progress board in `R2` with live branch completion status.
- [ ] Add directional landmarks visible from decision points.
- [ ] Add door labels/icon repeats at branch entrances.
- [ ] Add gate reaction feedback in `R1` after each sigil acquisition.
- [ ] Add short contextual prompts on return to `R1`.
- [ ] Run no-guidance navigation test with at least one fresh tester.
- [ ] Log stalls greater than 20 seconds and wrong turns.
- [ ] Adjust signage/landmarks based on observed confusion.
- [ ] Re-test navigation comprehension.
- [ ] Freeze readability pass.

Downstream input: low-confusion guidance layer for final tuning and QA.

### Activity 8. Tune Pacing and Difficulty

Scope of work: hit timing target and smooth ramp into final room.

- [ ] Create `/Users/timwood/Desktop/projects/PWA/MV/docs/pacing-tuning-v1.md`.
- [ ] Define target duration and difficulty score per room.
- [ ] Capture baseline completion times across internal runs.
- [ ] Shorten overlong traversal segments.
- [ ] Adjust encounter density where difficulty spikes exceed target.
- [ ] Remove low-engagement downtime.
- [ ] Ensure a short recovery window before `R9`.
- [ ] Balance branch durations to similar completion times.
- [ ] Confirm `R9` final duration remains ~2-3 minutes.
- [ ] Re-test after each major tuning pass.
- [ ] Stop tuning when median run is ~12 minutes.
- [ ] Freeze tuned values for QA.

Downstream input: calibrated timing and difficulty baseline for validation thresholds.

### Activity 9. Instrument and Run Internal Playtests

Scope of work: collect evidence and prioritize high-impact fixes.

- [ ] Implement telemetry for run start/end and per-room enter/exit events.
- [ ] Capture deaths, retries, and stalled time per room.
- [ ] Capture unlock comprehension checkpoints after each sigil pickup.
- [ ] Create playtest observer template for qualitative notes.
- [ ] Recruit 5 fresh internal testers.
- [ ] Run sessions without coaching unless hard-stuck.
- [ ] Collect quantitative and qualitative data for each run.
- [ ] Aggregate results into one findings report.
- [ ] Rank issues by completion risk, clarity risk, and pacing impact.
- [ ] Identify top 3 blockers and top 3 high-value improvements.
- [ ] Map each issue to an owner/component.
- [ ] Publish prioritized fix list for stabilization.

Downstream input: evidence-based backlog for final MVP lock.

### Activity 10. Final MVP Lock and QA

Scope of work: stabilize build and certify MVP readiness.

- [ ] Create final triage board with severities (`blocker`, `major`, `minor`).
- [ ] Fix all blocker progression/completion defects.
- [ ] Fix major navigation and objective-comprehension defects.
- [ ] Re-run gate-state regression across all branch orders.
- [ ] Execute full clean run from new game to `R10` completion.
- [ ] Validate respawn and resume behavior.
- [ ] Validate UI/signage/feedback triggers and consistency.
- [ ] Re-validate timing band (10-15 minutes).
- [ ] Document deferred minor issues and rationale.
- [ ] Freeze map layout and progression parameters.
- [ ] Tag MVP candidate build and archive test evidence.
- [ ] Write go/no-go summary against explicit acceptance criteria.

Downstream output: stable MVP map build ready for external MVP testing.

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

- [x] **Add one gate**
  - **What:** One place in the first zone that is unreachable without the new ability (e.g. high ledge, gap, or blocked path). When the player has the ability, they can reach it.
  - **Scope:** Single gate; no full backtracking loop or save system yet. Proves the "ability-gated progression" idea.
  - **Outcome:** Clear before/after: without ability you cannot reach the spot; with ability you can. Sets up M4 (backtracking & progression) later.
  - **Done:** Added a late-zone high ledge in `index.html` intended to require double jump to reach.

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
