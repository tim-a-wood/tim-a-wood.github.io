# Test Report

Update this file after each code change. Record one row for every acceptance test in `tests/acceptance_tests.md` plus the overall unit test suite result.

| ID | Line Item | Description | Result | Notes |
|---|---|---|---|---|
| AT-01 | Fresh Load And Startup | Verifies the game loads into the playable scene with the player, HUD, and controls visible. | Not Run | Only Branch A’s R2↔R3 entry behavior and R3→R2 return trigger (now interact-only at the R3 entrance) were adjusted; startup flow was not manually re-tested. |
| AT-02 | Movement, Camera, And World Bounds | Verifies horizontal movement works and the player/camera stay inside the bounded world. | Not Run | World bounds and camera logic were unchanged; only Branch A’s R2↔R3 and R3→R2 room transition logic and input handling for interact were tweaked. |
| AT-03 | Ground Jump | Verifies the first jump consistently works from the ground. | Not Run | Jump physics were untouched; only the mapping of the interact action (no longer tied to the up/jump input) was changed. |
| AT-04 | Mid-Air Double Jump | Verifies a second press/tap in mid-air triggers exactly one additional jump. | Not Run | Double-jump state handling was unchanged and was not manually re-tested here. |
| AT-05 | Landing Refills Jump State | Verifies landing restores the full jump + double jump sequence. | Not Run | Landing and jump-refill behavior were unchanged and were not manually re-verified. |
| AT-06 | Touch Controls | Verifies on-screen left/right/jump controls behave correctly on touch devices. | Not Run | Touch controls for movement and jump were not modified; only the dedicated interact button behavior was refined. |
| AT-07 | Death, Respawn, And Restart | Verifies life loss, respawn flow, game-over state, and restart behavior. | Not Run | Life and respawn systems were not involved in the Branch A R2↔R3 transition/input adjustments and were not re-tested. |
| AT-08 | HUD And Feedback | Verifies the distance HUD and life icons stay visible and update correctly. | Not Run | HUD code was unchanged; no manual HUD check was performed for this tweak. |
| AT-09 | Key Pickup And Door Unlock | Verifies the key can be collected on the high ledge, appears in the HUD inventory, and is consumed when unlocking the left-side door. | Not Run | Key and ability reward logic were unchanged; only Branch A’s R2↔R3 and R3→R2 room transition path and interact handling were adjusted. |
| UT-01 | Unit Test Suite | Verifies the full automated unit test suite in `tests/game-logic.test.js` passes. | Not Run | `node` is not available in the current execution environment, so the test suite could not be re-run after the latest Branch A R2↔R3 and R3→R2 transition/input refinements. |
