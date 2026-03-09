# Test Report

Update this file after each code change. Record one row for every acceptance test in `tests/acceptance_tests.md` plus the overall unit test suite result.

| ID | Line Item | Description | Result | Notes |
|---|---|---|---|---|
| AT-01 | Fresh Load And Startup | Verifies the game loads into the playable scene with the player, HUD, and controls visible. | Not Run | Branch door positions and R2→R3 transition tweens were adjusted; no manual startup run was executed here. |
| AT-02 | Movement, Camera, And World Bounds | Verifies horizontal movement works and the player/camera stay inside the bounded world. | Not Run | World bounds and camera logic were unchanged; only branch door placement and R2→R3 transition behavior were updated, and movement was not manually re-tested. |
| AT-03 | Ground Jump | Verifies the first jump consistently works from the ground. | Not Run | Platform spacing changed substantially; manual jump checks were not executed here. |
| AT-04 | Mid-Air Double Jump | Verifies a second press/tap in mid-air triggers exactly one additional jump. | Not Run | The new key perch is intentionally gated by double jump, but the route was not manually exercised here. |
| AT-05 | Landing Refills Jump State | Verifies landing restores the full jump + double jump sequence. | Not Run | Gameplay changed; landing/refill behavior was not manually re-tested here. |
| AT-06 | Touch Controls | Verifies on-screen left/right/jump controls behave correctly on touch devices. | Not Run | Touch acceptance testing was not executed in this environment. |
| AT-07 | Death, Respawn, And Restart | Verifies life loss, respawn flow, game-over state, and restart behavior. | Not Run | This change did not target death flow, and no manual run was performed here. |
| AT-08 | HUD And Feedback | Verifies the distance HUD and life icons stay visible and update correctly. | Not Run | HUD logic was unchanged, but no manual verification was run against the new room. |
| AT-09 | Key Pickup And Door Unlock | Verifies the key can be collected on the high ledge, appears in the HUD inventory, and is consumed when unlocking the left-side door. | Not Run | Key and ability reward logic were unchanged; new branch entry positioning for R2→R3 was not exercised end to end here. |
| UT-01 | Unit Test Suite | Verifies the full automated unit test suite in `tests/game-logic.test.js` passes. | Not Run | `node` was not available in the current execution environment, so the suite could not be run after the R2→R3 transition update. |
