# Progression Unlocks v1 (Frozen)

Version: 1.0
Date: 2026-03-08
Status: Frozen
Depends on: `docs/map-mvp-constraints.md` v1.2, `docs/map-graph-v1.md` v1.0

## Purpose

Define the MVP progression table for key items and ability unlocks across `R1-R10`, including hard/soft usage rules, player feedback, and sequence safety.

Final gate contract remains unchanged:

- `key_items_collected == 3`
- `abilities_unlocked == 3`

## Branch Mapping (Locked)

- Branch A reward room: `R4`
  - `Key Item A`
  - `Ability Unlock A` (hard-gate utility)
- Branch B reward room: `R6`
  - `Key Item B`
  - `Ability Unlock B` (soft-power utility)
- Branch C reward room: `R8`
  - `Key Item C`
  - `Ability Unlock C` (soft-power utility)

## Unlock Definitions

### Ability Unlock A (Hard Gate)

- Name: `Abyss Dash`
- Unlock room: `R4`
- Type: required traversal unlock
- Required barrier: one mandatory dash gap in `R5` (entry trial segment to reach `R6` reward)
- Requirement policy: run cannot complete without this unlock because Branch B access is blocked until `Abyss Dash` is active

### Ability Unlock B (Soft Power)

- Name: `Soul Lantern`
- Unlock room: `R6`
- Type: optional power/readability unlock
- Primary value: reveals safe footholds and hazard tell marks in darkened lanes
- Pre-final usage moment: optional dark lane shortcut in `R7` that trims traversal time by ~15-20 seconds
- Requirement policy: skipping usage never blocks completion

### Ability Unlock C (Soft Power)

- Name: `Rift Guard`
- Unlock room: `R8`
- Type: optional survivability unlock
- Primary value: one-hit shield against environmental hazard or projectile in final approach
- Pre-final usage moment: optional mitigation in `R9` opener to reduce first-attempt failure rate
- Requirement policy: skipping usage never blocks completion

## Pickup, Trigger, and Feedback Spec

For each branch reward room (`R4`, `R6`, `R8`):

1. Player acquires key item pedestal pickup.
2. Ability node activates in same room and is interactable immediately.
3. On ability activation:
   - Set `ability_unlock_* = true` (idempotent)
   - Increment `abilities_unlocked` only on first activation
   - Fire one UI toast with icon and branch color
   - Play one short confirm SFX + one stinger layer
   - Pulse gate indicator state in `R1` (remote feedback)

Immediate UI copy format:

- `Key Item A secured (1/3)` / `Key Item B secured (2/3)` / `Key Item C secured (3/3)`
- `Abyss Dash awakened (1/3 Abilities)`
- `Soul Lantern awakened (2/3 Abilities)`
- `Rift Guard awakened (3/3 Abilities)`

## Forced/Obvious First-Usage Moments (Pre-Final)

- `Abyss Dash` (required): first required usage appears at Branch B gate in `R5` and is visually framed by branch color cues.
- `Soul Lantern` (optional): first obvious usage appears in `R7` as a dark passage with visible lantern-marked footholds.
- `Rift Guard` (optional): first obvious usage appears at `R9` threshold with a clearly telegraphed incoming hazard volley.

## Soft-Power Skip Behavior

If player does not use `Soul Lantern` or `Rift Guard` in their intended moments:

- Core route remains fully traversable.
- No fail-state or lockout is introduced.
- Alternate safe path is always available at modest time cost (+15-30 seconds total).
- Final gate checks only unlock ownership state, not optional usage events.

## Landmark and Door Copy (Concise)

Room and gate text should be short and location-bound:

- `R1` final gate locked (keys missing): `Gate sealed: recover 3 Key Items.`
- `R1` final gate locked (abilities missing): `Gate sealed: awaken 3 Abilities.`
- `R1` gate ready: `Gate attuned. Enter the Final Ascent.`
- `R2` branch sign A: `Crimson Route -> Trial of Dash`.
- `R2` branch sign B: `Umber Route -> Trial of Sight`.
- `R2` branch sign C: `Azure Route -> Trial of Guard`.

## Sequence and Runtime Validation

### Runtime Budget Check

Estimated first-time timing with this unlock set:

- Orientation + hub setup (`R1-R2`): 1.0-1.5 min
- Branch A (`R3-R4` with unlock): 2.0-2.5 min
- Branch B (`R5-R6` with unlock): 2.0-2.5 min
- Branch C (`R7-R8` with unlock): 2.0-2.5 min
- Return + gate + final + exit (`R1-R9-R10`): 2.5-3.5 min

Total: ~9.5-12.5 min baseline, leaving buffer for deaths/recovery while staying inside 10-15 min target.

### Sequence-Break Safety Check

- Branches can complete in any order after initial routing from `R2`.
- Required dependency is singular and explicit: `Ability Unlock A` gates Branch B entry challenge.
- No dependency loops (`B` or `C` never required to obtain `A`).
- Gate unlock remains deterministic and order-independent.

Validated sequences:

- `A-B-C` (baseline)
- `A-C-B` (valid)
- `C-A-B` (valid)
- `B-first` and `C-first` attempts: intentionally redirected by `Abyss Dash` hard gate messaging, preventing breakage.

## Freeze Decision

The progression unlock table is frozen as v1.0 for implementation in Activity 4 and Activity 5+.

Sign-off:

- Project owner: Tim Wood
- Frozen on: 2026-03-08
