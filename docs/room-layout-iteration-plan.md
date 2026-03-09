# Room Layout Iteration Plan (R3-R8)

Date: 2026-03-08
Status: Active

## Goal

Deliver branch rooms (`R3-R8`) that feel like dungeon crawling while remaining reliably reachable on iPhone touch controls.

## Reachability Constraints (Locked)

1. Main route step-up between consecutive required ledges: <= 120 px.
2. Main route horizontal gap between required ledges: <= 220 px.
3. Required interactions (doors, key items, ability nodes): reachable within <= 140 px from stable standing positions.
4. Branch completion route must always allow returning to `R2` without requiring optional jumps.
5. Critical-path transitions at room edges must be reachable from floor-level fallback.

## Task Breakdown

### Task 1: Main Spine First (per room)

- Build one guaranteed path from room entry to room exit using 5-7 ledges.
- Verify each step obeys vertical/horizontal reach constraints.
- Keep a floor fallback where practical so players can recover from misses.

Output:
- Reachable "main spine" for each of `R3-R8`.

### Task 2: Interaction Anchors

- Place key item and ability node on/next to main spine, not in optional side nooks.
- Place branch doors in `R2` at heights aligned to reachable hub ledges.
- Keep interaction radius target within 140 px.

Output:
- Zero mandatory interactions that require precision-only jumps.

### Task 3: Dungeon Flavor Layer

- Add blocker columns, short detours, and visual choke points around the main spine.
- Do not block recovery routes or room-edge transitions.
- Use branch-specific silhouette language:
  - A: tight rises and vertical choke points
  - B: staggered climbs with short drops
  - C: denser lane changes and pressure pacing

Output:
- Dungeon-like feel without breaking route reliability.

### Task 4: Route Validation Pass

Run for each branch:

1. `R2 -> branch door -> entry room`
2. `entry room -> reward room`
3. `collect key`
4. `unlock ability`
5. `return to R2`

Output:
- Every branch completes in one clean loop with no dead-ends.

### Task 5: Sequence Validation

- Validate completion orders: `A-B-C`, `A-C-B`, `C-A-B`.
- Confirm Branch B hard-gate behavior (locked before A ability, open after A ability).
- Confirm gate counters update after each key/ability pickup.

Output:
- Order-independent progression with deterministic state updates.

### Task 6: iPhone Touch QA

- Run all branch loops using only on-screen controls.
- Verify no required action depends on keyboard-only affordances.
- Log misses where interaction/jump reliability feels low and patch those first.

Output:
- Touch-first playability baseline for branch content.

## Exit Criteria

1. No unreachable mandatory ledges or interactions in `R3-R8`.
2. All three branches completable with touch controls only.
3. Final gate can be unlocked through real branch progression (not debug shortcuts).
4. Player can complete full run and return loop without soft-locks.

## Focused Regression Checklist (Branch A / R3-R4)

Use this checklist after every `R3` or `R4` geometry change:

1. Enter Branch A door from `R2` using only touch controls.
2. Traverse `R3` from entry spawn to right boundary transition without damage boosts or debug teleport.
3. Confirm `R3 -> R4` transition always fires when pushing into right boundary (any reachable ledge height).
4. Reach Key Item A in `R4`.
5. Reach Ability Unlock A in `R4` after key pickup.
6. Exit branch and confirm return to `R2`.
7. In `R2`, confirm Branch B door now opens (hard-gate released).
