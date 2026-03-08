# Map Graph v1 (Frozen)

Version: 1.0
Date: 2026-03-08
Status: Frozen
Depends on: `docs/map-mvp-constraints.md` v1.2

## Purpose

Define canonical room graph and room purposes for the MVP map loop with two-layer progression:

- Layer 1: 3 Key Items
- Layer 2: 3 Ability Unlocks

Final gate in `R1` opens only when:

- `key_items_collected == 3`
- `abilities_unlocked == 3`

Graph was visualized and reviewed in `/Users/timwood/Desktop/projects/PWA/MV/map-graph-viewer.html` before freeze.

## Canonical Room IDs and Names

- `R1` Spawn + Final Gate Chamber
- `R2` Central Hub
- `R3` Branch A Entry Trial
- `R4` Branch A Reward + Ability Node
- `R5` Branch B Entry Trial
- `R6` Branch B Reward + Ability Node
- `R7` Branch C Entry Trial
- `R8` Branch C Reward + Ability Node
- `R9` Final Area
- `R10` Exit / Completion Room

## Adjacency List (Directed Traversal)

- `R1 -> R2` (main progression path)
- `R2 -> R1` (return to final gate)
- `R2 -> R3`, `R3 -> R4`, `R4 -> R2`
- `R2 -> R5`, `R5 -> R6`, `R6 -> R2`
- `R2 -> R7`, `R7 -> R8`, `R8 -> R2`
- `R1 -> R9` (only when final gate unlocked)
- `R9 -> R10`

Dead-end validation:

- Intentional endpoint only: `R10`.
- All other rooms have at least one outbound transition.

## Room Purpose Matrix

| Room | Primary Purpose | Secondary Purpose | Target Time |
|---|---|---|---|
| `R1` | Orientation + final gate objective | Progress recap / payoff anticipation | 45-60s initial, 20-30s revisit |
| `R2` | Hub routing | Progress readability | 30-45s/visit |
| `R3` | Branch A challenge entry | Teach A branch rhythm | 60-90s |
| `R4` | Key Item A reward | Ability Unlock A activation | 90-120s |
| `R5` | Branch B challenge entry | Mechanical variation | 60-90s |
| `R6` | Key Item B reward | Ability Unlock B activation | 90-120s |
| `R7` | Branch C challenge entry | Pre-final pressure ramp | 60-90s |
| `R8` | Key Item C reward | Ability Unlock C activation | 90-120s |
| `R9` | Final encounter/objective | Run climax | 120-180s |
| `R10` | Exit and completion trigger | Reward/summary | 30-60s |

## Required Interactables by Room

- `R1`: spawn point, final gate terminal, gate-state UI marker, path sign to `R2`
- `R2`: branch doors A/B/C, branch completion board, shortcut marker back to `R1`
- `R3`: challenge trigger A, one branch landmark
- `R4`: Key Item A pickup, Ability Unlock A node, return door to `R2`
- `R5`: challenge trigger B, one branch landmark
- `R6`: Key Item B pickup, Ability Unlock B node, return door to `R2`
- `R7`: challenge trigger C, one branch landmark
- `R8`: Key Item C pickup, Ability Unlock C node, return door to `R2`
- `R9`: final objective trigger, pre-exit unlock trigger
- `R10`: exit trigger, run completion marker

## Branch Return Paths

- Branch A loop: `R2 -> R3 -> R4 -> R2`
- Branch B loop: `R2 -> R5 -> R6 -> R2`
- Branch C loop: `R2 -> R7 -> R8 -> R2`

All branch loops support any completion order:

- `A-B-C`, `B-C-A`, `C-A-B`

## Respawn Anchors

- Primary spawn/checkpoint: `R1`
- Mid-run checkpoint: `R2`
- Pre-final checkpoint: `R1` (after gate unlock) or gate-threshold checkpoint just before `R9`

## Paper Simulation Results

### Ideal Route Simulation

1. Start in `R1`, observe final gate requirements.
2. Move to `R2`, choose branch A.
3. Complete `R3 -> R4`, obtain Key Item A + Ability Unlock A, return to `R2`.
4. Complete branches B and C similarly.
5. Return to `R1`, unlock final gate.
6. Complete `R9 -> R10`.

Result:

- No topology blockers.
- Clear loop closure through `R1`.

### Confused Route Simulation

1. Player loops `R1 <-> R2` without branch commitment.
2. Enters wrong branch, returns early, tries another branch.
3. Completes branches in non-linear order.
4. Returns to `R1` early before full requirements met.

Result:

- Progress still robust due to branch independence.
- Requires strong signage in `R1` and `R2` to reduce indecision.

## Freeze Decisions

1. Pre-final checkpoint location:
   - Decision: use an explicit gate-threshold checkpoint immediately before `R9` (not in a new room).
2. Optional branch shortcuts:
   - Decision: no optional shortcuts in v1.0 to keep branch readability and scope stable.
3. Branch C timing risk:
   - Decision: keep target at 60-90s in `R7` + 90-120s in `R8`, with tuning guardrail to cap branch C median at <= 3.5 minutes during Activity 8.

## Freeze Criteria

This graph can be frozen as v1.0 once:

1. Visual review of graph/rooms is accepted.
2. Topology and interactables are signed off.
3. Open items above are resolved.

Freeze confirmation:

- Visual review accepted by project owner on 2026-03-08.
- Topology and interactables signed off.
- Freeze decisions recorded above.
