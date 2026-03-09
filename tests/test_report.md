# Test Report

Update this file after each code change. Record one row for every acceptance test in `tests/acceptance_tests.md` plus the overall unit test suite result.

| ID | Line Item | Description | Result | Notes |
|---|---|---|---|---|
| AT-01 | Fresh Load And Startup | Verifies the game loads into the playable scene with the player, HUD, and controls visible. | Not Run | Only Branch A’s R3↔R4 linkage and R3 door interactions were adjusted; startup flow was not manually re-tested. |
| AT-02 | Movement, Camera, And World Bounds | Verifies horizontal movement works and the player/camera stay inside the bounded world. | Not Run | World bounds were unchanged; only local room-transition triggers and door positions in Branch A were updated, and this was not manually re-verified. |
| AT-03 | Ground Jump | Verifies the first jump consistently works from the ground. | Not Run | Jump physics were untouched; only interact-driven room transitions around R3/R4 were changed. |
| AT-04 | Mid-Air Double Jump | Verifies a second press/tap in mid-air triggers exactly one additional jump. | Not Run | Double-jump state handling was unchanged and was not manually re-tested here. |
| AT-05 | Landing Refills Jump State | Verifies landing restores the full jump + double jump sequence. | Not Run | Landing and jump-refill behavior were unchanged and were not manually re-verified. |
| AT-06 | Touch Controls | Verifies on-screen left/right/jump controls behave correctly on touch devices. | Not Run | Touch controls for movement and jump were not modified; only the dedicated interact doors for R3↔R4 and the existing R3→R2 return door were refined. |
| AT-07 | Death, Respawn, And Restart | Verifies life loss, respawn flow, game-over state, and restart behavior. | Not Run | Life and respawn systems were not involved in the Branch A R3↔R4 changes and were not re-tested. |
| AT-08 | HUD And Feedback | Verifies the distance HUD and life icons stay visible and update correctly. | Not Run | HUD code was unchanged; no manual HUD check was performed for this tweak. |
| AT-09 | Key Pickup And Door Unlock | Verifies the key can be collected on the high ledge, appears in the HUD inventory, and is consumed when unlocking the left-side door. | Not Run | Key and ability reward logic were unchanged; only Branch A’s R3 top door to R4, the R4→R3 return door, and interaction checks were adjusted. |
| UT-01 | Unit Test Suite | Verifies the full automated unit test suite in `tests/game-logic.test.js` passes. | Not Run | `node` is not available in the current execution environment, so the test suite could not be re-run after the latest Branch A R3↔R4 door and interaction changes. |
