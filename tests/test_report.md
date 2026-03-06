# Test Report

Update this file after each code change. Record one row for every acceptance test in `tests/acceptance_tests.md` plus the overall unit test suite result.

| ID | Line Item | Description | Result | Notes |
|---|---|---|---|---|
| AT-01 | Fresh Load And Startup | Verifies the game loads into the playable scene with the player, HUD, and controls visible. | Not Run | Docs/metadata tidy-up only; gameplay not re-tested in this change. |
| AT-02 | Movement, Camera, And World Bounds | Verifies horizontal movement works and the player/camera stay inside the bounded world. | Not Run | Docs/metadata tidy-up only; gameplay not re-tested in this change. |
| AT-03 | Ground Jump | Verifies the first jump consistently works from the ground. | Not Run | Docs/metadata tidy-up only; gameplay not re-tested in this change. |
| AT-04 | Mid-Air Double Jump | Verifies a second press/tap in mid-air triggers exactly one additional jump. | Not Run | Docs/metadata tidy-up only; gameplay not re-tested in this change. |
| AT-05 | Landing Refills Jump State | Verifies landing restores the full jump + double jump sequence. | Not Run | Docs/metadata tidy-up only; gameplay not re-tested in this change. |
| AT-06 | Touch Controls | Verifies on-screen left/right/jump controls behave correctly on touch devices. | Not Run | Docs/metadata tidy-up only; gameplay not re-tested in this change. |
| AT-07 | Death, Respawn, And Restart | Verifies life loss, respawn flow, game-over state, and restart behavior. | Not Run | Docs/metadata tidy-up only; gameplay not re-tested in this change. |
| AT-08 | HUD And Feedback | Verifies the distance HUD and life icons stay visible and update correctly. | Not Run | Docs/metadata tidy-up only; gameplay not re-tested in this change. |
| UT-01 | Unit Test Suite | Verifies the full automated unit test suite in `tests/game-logic.test.js` passes. | Not Run | Docs/metadata-only change; `node` was not available in the current execution environment. |
