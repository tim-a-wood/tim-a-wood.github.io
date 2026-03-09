# Test Report

Update this file after each code change. Record one row for every acceptance test in `tests/acceptance_tests.md` plus the overall unit test suite result.

| ID | Line Item | Description | Result | Notes |
|---|---|---|---|---|
| AT-01 | Fresh Load And Startup | Verifies the game loads into the playable scene with the player, HUD, and controls visible. | Not Run | Tunnel + secret door added; startup flow not re-tested. |
| AT-02 | Movement, Camera, And World Bounds | Verifies horizontal movement works and the player/camera stay inside the bounded world. | Not Run | R4 tunnel floor/walls made solid (DUNGEON_WALL_RECTS); R11 tunnel floor gap bridged (len 31); world bounds unchanged. |
| AT-03 | Ground Jump | Verifies the first jump consistently works from the ground. | Not Run | Jump physics untouched. |
| AT-04 | Mid-Air Double Jump | Verifies a second press/tap in mid-air triggers exactly one additional jump. | Not Run | Double-jump unchanged; not re-tested. |
| AT-05 | Landing Refills Jump State | Verifies landing restores the full jump + double jump sequence. | Not Run | Landing/jump-refill unchanged; not re-verified. |
| AT-06 | Touch Controls | Verifies on-screen left/right/jump controls behave correctly on touch devices. | Not Run | Touch controls not modified. |
| AT-07 | Death, Respawn, And Restart | Verifies life loss, respawn flow, game-over state, and restart behavior. | Not Run | Life/respawn not involved. |
| AT-08 | HUD And Feedback | Verifies the distance HUD and life icons stay visible and update correctly. | Not Run | HUD unchanged. |
| AT-09 | Key Pickup And Door Unlock | Verifies the key can be collected on the high ledge, appears in the HUD inventory, and is consumed when unlocking the left-side door. | Not Run | Branch A: R4 ability node moved to x=1560 so it no longer overlaps tunnel east wall (was 1520, wall right edge ~1512). |
| UT-01 | Unit Test Suite | Verifies the full automated unit test suite in `tests/game-logic.test.js` passes. | Not Run | Unit tests not re-run; tunnel geometry fix (no fall-through in R4/R11). |
