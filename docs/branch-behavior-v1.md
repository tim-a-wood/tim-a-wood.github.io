# Branch Behavior v1 (Frozen)

Version: 1.0
Date: 2026-03-08
Status: Frozen
Depends on: `docs/map-graph-v1.md`, `docs/progression-unlocks-v1.md`, `docs/gate-state-spec-v1.md`

## Scope

Defines branch implementation behavior for Activity 6 (`R3-R8`) including entry/exit flow, progression flags, gating, sequence handling, and timing validation surfaces.

## Branch Mapping

- Branch A: `R3 -> R4 -> R2`
- Branch B: `R5 -> R6 -> R2`
- Branch C: `R7 -> R8 -> R2`

## Core Rules

1. Branch B entry remains hard-gated by Ability A (`Abyss Dash`) ownership.
2. Each branch reward room contains one key item and one ability unlock.
3. Branch completion flag is set only when both branch key and ability are collected.
4. Return routes exist both at room edge transitions and explicit return doors in reward rooms.
5. Final gate state remains derived from `3 keys + 3 abilities`.

## Branch Completion Flags

- `branchCompleteA`
- `branchCompleteB`
- `branchCompleteC`

Completion trigger:

- Set on successful branch return handling from reward room after key+ability ownership is true.

## Sequence Validation Contract

Attempt orders validated:

- `A-B-C`
- `B-C-A`
- `C-A-B`

Behavior:

- `B` attempted before `A` is treated as blocked/redirected and must not break progression.
- Progression remains completable after redirects.

## Timing Validation Contract

Duration targets per branch run:

- A: 150-210 seconds
- B: 150-210 seconds
- C: 150-210 seconds

Runtime behavior:

- Branch run duration is captured and reported with status (`LOW`, `OK`, `HIGH`) in the R2 board.

## Visual Identity Contract

- Branch A: Crimson / vertical choke emphasis / landmark `FANG SPIRE`
- Branch B: Umber / staggered climb emphasis / landmark `BONE ARCH`
- Branch C: Azure / lane-switch emphasis / landmark `TIDE ALTAR`

## Freeze Decision

Branch behavior is frozen as v1.0 for handoff into Activity 7 readability and Activity 8 tuning.

Sign-off:

- Project owner: Tim Wood
- Frozen on: 2026-03-08
