# Test Report
| ID | Line Item | Description | Result | Notes |
|---|---|---|---|---|
| AT-01 | Fresh Load And Startup | Verify the prototype loads into the playable zone without crashes or blank screens. | Not Run | Browser not exercised for this update; change scope is Creative documentation/status only. |
| AT-02 | Movement, Camera, And World Bounds | Verify left/right movement works and the player/camera stay inside the intended bounded world. | Not Run | Same as AT-01. |
| AT-03 | Ground Jump | Verify the first jump works consistently from solid ground. | Not Run | Same as AT-01. |
| AT-04 | Mid-Air Double Jump | Verify the second jump works in mid-air and creates a clear extra hop. | Not Run | Same as AT-01. |
| AT-05 | Landing Refills Jump State | Verify landing restores the ability to perform another full jump + double jump sequence. | Not Run | Same as AT-01. |
| AT-06 | Touch Controls | Verify on-screen controls behave correctly on touch devices. | Not Run | Same as AT-01. |
| AT-07 | Death, Respawn, And Restart | Verify the life system, respawn behavior, game-over state, and restart control. | Not Run | Same as AT-01. |
| AT-08 | HUD And Feedback | Verify the HUD remains visible and updates during play. | Not Run | Same as AT-01. |
| AT-09 | Key Pickup And Door Unlock | Verify the first progression loop works end to end: collect the key on the high ledge, show it in the HUD inventory, then consume it to unlock the left-side door. | Not Run | Same as AT-01. |
| Unit Test Suite | Overall Unit Tests | `python3 tests/room_environment_system.test.py`, `python3 tests/room_ai_helpfulness_dashboard.test.py`, `node tests/room-wizard-environment-copilot.test.js` | Pass | Room helpfulness lifecycle tests, dashboard aggregation test, and copilot JS regression check all passed on 2026-04-01. After `scripts/update_dashboards.sh` + README hardening (2026-04-01), re-ran `node --test tests/game-logic.test.js` only as a quick sanity check; full Python suite not re-run for that doc/shell-only diff. |
| RW-1 manual | Room wizard vertical slice | Add Room → Layout → Review → Export JSON (per `docs/room-wizard-implementation-sprints.md`). | Not Run | Automated unit tests only; browser demo not executed in CI. |
| RW-2 manual | Neighbors & alignment | Adjoining room → Align → Match opening height; global map shows link (per `docs/room-wizard-implementation-sprints.md` §RW-2). | Not Run | Automated unit tests only; browser not exercised in CI. |
| RW-AI-01 manual | Room AI helpfulness smoke | Project-backed room flow: build environment preview, record preview view, approve suggestion, save later edit, then confirm `/api/dashboard-data` exposes helpfulness rollups. | Pass | Live HTTP smoke pass against `sprite_workbench_server.py` on 2026-04-01 succeeded after fixing two regressions found during QA: `suggestion_id` hashing needed string coercion, and dashboard scanning needed `room_layout.json` rather than `room-layout.json`. |
