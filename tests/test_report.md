# Test Report
| ID | Line Item | Description | Result | Notes |
|---|---|---|---|---|
| AT-01 | Fresh Load And Startup | Verify the prototype loads into the playable zone without crashes or blank screens. | Not Run | Browser not exercised in this run; change: dynamic room sequence (R12+), preview spawn flag, playtest hash spawn. |
| AT-02 | Movement, Camera, And World Bounds | Verify left/right movement works and the player/camera stay inside the intended bounded world. | Not Run | Same as AT-01. |
| AT-03 | Ground Jump | Verify the first jump works consistently from solid ground. | Not Run | Same as AT-01. |
| AT-04 | Mid-Air Double Jump | Verify the second jump works in mid-air and creates a clear extra hop. | Not Run | Same as AT-01. |
| AT-05 | Landing Refills Jump State | Verify landing restores the ability to perform another full jump + double jump sequence. | Not Run | Same as AT-01. |
| AT-06 | Touch Controls | Verify on-screen controls behave correctly on touch devices. | Not Run | Same as AT-01. |
| AT-07 | Death, Respawn, And Restart | Verify the life system, respawn behavior, game-over state, and restart control. | Not Run | Same as AT-01. |
| AT-08 | HUD And Feedback | Verify the HUD remains visible and updates during play. | Not Run | Same as AT-01. |
| AT-09 | Key Pickup And Door Unlock | Verify the first progression loop works end to end: collect the key on the high ledge, show it in the HUD inventory, then consume it to unlock the left-side door. | Not Run | Same as AT-01. |
| Unit Test Suite | Overall Unit Tests | General unit test suite status. | Pass | Ran `node tests/game-logic.test.js`, `room-editor-export.test.js`, `room-wizard-footprint.test.js` (2026-03-27); all exited 0; includes embed postMessage / READY handshake smoke strings. |
| RW-1 manual | Room wizard vertical slice | Add Room → Layout → Review → Export JSON (per `docs/room-wizard-implementation-sprints.md`). | Not Run | Automated unit tests only; browser demo not executed in CI. |
