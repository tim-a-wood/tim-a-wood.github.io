# Test Report
| ID | Line Item | Description | Result | Notes |
|---|---|---|---|---|
| AT-01 | Fresh Load And Startup | Verify the prototype loads into the playable zone without crashes or blank screens. | Not Run | Sprite workbench Animations UI (collapsible panels + custom clips); root game `index.html` not exercised. |
| AT-02 | Movement, Camera, And World Bounds | Verify left/right movement works and the player/camera stay inside the intended bounded world. | Not Run | Workbench-only change; game prototype not exercised. |
| AT-03 | Ground Jump | Verify the first jump works consistently from solid ground. | Not Run | Workbench-only change; game prototype not exercised. |
| AT-04 | Mid-Air Double Jump | Verify the second jump works in mid-air and creates a clear extra hop. | Not Run | Workbench-only change; game prototype not exercised. |
| AT-05 | Landing Refills Jump State | Verify landing restores the ability to perform another full jump + double jump sequence. | Not Run | Workbench-only change; game prototype not exercised. |
| AT-06 | Touch Controls | Verify on-screen controls behave correctly on touch devices. | Not Run | Workbench-only change; game prototype not exercised. |
| AT-07 | Death, Respawn, And Restart | Verify the life system, respawn behavior, game-over state, and restart control. | Not Run | Workbench-only change; game prototype not exercised. |
| AT-08 | HUD And Feedback | Verify the HUD remains visible and updates during play. | Not Run | Workbench-only change; game prototype not exercised. |
| AT-09 | Key Pickup And Door Unlock | Verify the first progression loop works end to end: collect the key on the high ledge, show it in the HUD inventory, then consume it to unlock the left-side door. | Not Run | Workbench-only change; game prototype not exercised. |
| Unit Test Suite | Overall Unit Tests | General unit test suite status. | Pass | Ran `python3 -m unittest discover -s tests -p "test_*.py"` (113 tests, OK). Includes `test_validate_pixellab_animation_name_slug`. Pixel Lab Animations: collapsible panels, `define-animation`, extra clips in build/export; template POST sends `animation_name`. |
