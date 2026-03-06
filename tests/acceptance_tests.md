# Acceptance Tests

Manual acceptance tests for the current `index.html` prototype. These are the high-level checks that should be reviewed after gameplay or input changes.

## How To Use

1. Run the game locally in a browser or on the target device.
2. Execute each acceptance test below.
3. Record the outcome in `tests/test_report.md`.
4. Do not change this file automatically when a code change suggests new acceptance coverage; propose updates to the user first.

## Test Cases

### AT-01 Fresh Load And Startup

- **Description:** Verify the prototype loads into the playable zone without crashes or blank screens.
- **Steps:**
  1. Open the game URL.
  2. Wait for the first frame to render.
  3. Confirm the player, HUD, and controls are visible.
- **Expected result:** The game starts cleanly, the player is visible, and there are no obvious startup errors.

### AT-02 Movement, Camera, And World Bounds

- **Description:** Verify left/right movement works and the player/camera stay inside the intended bounded world.
- **Steps:**
  1. Move left until reaching the left edge.
  2. Move right across the zone toward the far edge.
  3. Watch the camera while traversing.
- **Expected result:** Movement is responsive, the player never exits the world, and the camera does not scroll past the level bounds.

### AT-03 Ground Jump

- **Description:** Verify the first jump works consistently from solid ground.
- **Steps:**
  1. Stand still on the floor.
  2. Press or tap jump once.
  3. Repeat several times after landing.
- **Expected result:** Each ground jump immediately launches the player upward with consistent force.

### AT-04 Mid-Air Double Jump

- **Description:** Verify the second jump works in mid-air and creates a clear extra hop.
- **Steps:**
  1. Perform a ground jump.
  2. While airborne, release jump and press/tap jump again.
  3. Repeat with both keyboard and touch controls if available.
- **Expected result:** The second press triggers one additional jump in mid-air and does not require a full landing first.

### AT-05 Landing Refills Jump State

- **Description:** Verify landing restores the ability to perform another full jump + double jump sequence.
- **Steps:**
  1. Perform a full jump + double jump sequence.
  2. Land on the floor or a platform.
  3. Attempt the same sequence again.
- **Expected result:** After landing, the player can once again perform a ground jump followed by a double jump.

### AT-06 Touch Controls

- **Description:** Verify on-screen controls behave correctly on touch devices.
- **Steps:**
  1. Press and hold left, then release.
  2. Press and hold right, then release.
  3. Tap jump once, then tap again in mid-air.
- **Expected result:** Direction buttons move the player only while held, and touch jump supports both the first jump and the double jump.

### AT-07 Death, Respawn, And Restart

- **Description:** Verify the life system, respawn behavior, game-over state, and restart control.
- **Steps:**
  1. Fall out of bounds enough times to lose a life.
  2. Repeat until lives reach zero.
  3. Use the restart button.
- **Expected result:** Non-final deaths respawn the player and reduce lives; the final death shows game over; restart returns the game to a clean starting state.

### AT-08 HUD And Feedback

- **Description:** Verify the HUD remains visible and updates during play.
- **Steps:**
  1. Start the game and move through the zone.
  2. Observe the distance text while moving.
  3. Lose a life and observe the life icons.
- **Expected result:** HUD text remains visible, distance updates during movement, and life icons reflect the current life count.

### AT-09 Key Pickup And Door Unlock

- **Description:** Verify the first progression loop works end to end: collect the key on the high ledge, show it in the HUD inventory, then consume it to unlock the left-side door.
- **Steps:**
  1. Reach the high ledge and collect the key.
  2. Confirm a key icon appears in the HUD inventory.
  3. Return to the locked door on the left.
  4. Touch the door with the key in inventory.
- **Expected result:** The key disappears from the world when collected, the HUD shows the key while it is carried, the door unlocks on contact, and the HUD key icon is removed because the key is consumed.
