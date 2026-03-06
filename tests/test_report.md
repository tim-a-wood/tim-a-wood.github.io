# Test Report

Update this file after each code change. Record one row for every acceptance test in `tests/acceptance_tests.md` plus the overall unit test suite result.

| ID | Line Item | Description | Result | Notes |
|---|---|---|---|---|
| AT-01 | Fresh Load And Startup | Verifies the game loads into the playable scene with the player, HUD, and controls visible. | Not Run | Gameplay changed; manual startup check not executed in this environment. |
| AT-02 | Movement, Camera, And World Bounds | Verifies horizontal movement works and the player/camera stay inside the bounded world. | Not Run | Room type (internal/outdoor) gates boundary walls; current zone is internal; traversal and bounds were not manually re-tested here. |
| AT-03 | Ground Jump | Verifies the first jump consistently works from the ground. | Not Run | Gameplay changed; manual jump check not executed in this environment. |
| AT-04 | Mid-Air Double Jump | Verifies a second press/tap in mid-air triggers exactly one additional jump. | Not Run | The new key is placed behind the high ledge gate, but manual double-jump verification was not executed here. |
| AT-05 | Landing Refills Jump State | Verifies landing restores the full jump + double jump sequence. | Not Run | Gameplay changed; manual landing/refill check not executed in this environment. |
| AT-06 | Touch Controls | Verifies on-screen left/right/jump controls behave correctly on touch devices. | Not Run | Touch acceptance testing was not executed in this environment. |
| AT-07 | Death, Respawn, And Restart | Verifies life loss, respawn flow, game-over state, and restart behavior. | Not Run | This change did not target death flow, and no manual run was performed here. |
| AT-08 | HUD And Feedback | Verifies the distance HUD and life icons stay visible and update correctly. | Not Run | The HUD now also includes a carried-key indicator, but HUD feedback was not manually verified in this environment. |
| AT-09 | Key Pickup And Door Unlock | Verifies the key can be collected on the high ledge, appears in the HUD inventory, and is consumed when unlocking the left-side door. | Not Run | The key inventory indicator and the repositioned corridor-side door were not manually exercised in this environment. |
| UT-01 | Unit Test Suite | Verifies the full automated unit test suite in `tests/game-logic.test.js` passes. | Not Run | Added relic, doubleJumpUnlocked gating, and skill icon tests; `node` was not available in the current execution environment. |
