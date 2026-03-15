# Test Report
| ID | Line Item | Description | Result | Notes |
|---|---|---|---|---|
| AT-01 | Fresh Load And Startup | Verify the prototype loads into the playable zone without crashes or blank screens. | Not Run | This request changed sprite workbench manifest/shape persistence, not the gameplay prototype. |
| AT-02 | Movement, Camera, And World Bounds | Verify left/right movement works and the player/camera stay inside the intended bounded world. | Not Run | This request changed sprite workbench manifest/shape persistence, not the gameplay prototype. |
| AT-03 | Ground Jump | Verify the first jump works consistently from solid ground. | Not Run | This request changed sprite workbench manifest/shape persistence, not the gameplay prototype. |
| AT-04 | Mid-Air Double Jump | Verify the second jump works in mid-air and creates a clear extra hop. | Not Run | This request changed sprite workbench manifest/shape persistence, not the gameplay prototype. |
| AT-05 | Landing Refills Jump State | Verify landing restores the ability to perform another full jump + double jump sequence. | Not Run | This request changed sprite workbench manifest/shape persistence, not the gameplay prototype. |
| AT-06 | Touch Controls | Verify on-screen controls behave correctly on touch devices. | Not Run | This request changed sprite workbench manifest/shape persistence, not the gameplay prototype. |
| AT-07 | Death, Respawn, And Restart | Verify the life system, respawn behavior, game-over state, and restart control. | Not Run | This request changed sprite workbench manifest/shape persistence, not the gameplay prototype. |
| AT-08 | HUD And Feedback | Verify the HUD remains visible and updates during play. | Not Run | This request changed sprite workbench manifest/shape persistence, not the gameplay prototype. |
| AT-09 | Key Pickup And Door Unlock | Verify the first progression loop works end to end: collect the key on the high ledge, show it in the HUD inventory, then consume it to unlock the left-side door. | Not Run | This request changed sprite workbench manifest/shape persistence, not the gameplay prototype. |
| Unit Test Suite | Overall Unit Tests | General unit test suite status. | Pass | Sprite workbench tests pass. Added `scripts/edit_part_shapes_via_api.py`; ran successfully against local API to edit part shapes (head + weapon vertices). |
