# Map MVP Constraints

Version: 1.2
Date: 2026-03-08
Status: Approved

## Terminology (Industry-Standard)

- `Key Item`: progression collectible required for gate logic.
- `Ability Unlock`: player capability or power-state activation used for traversal/combat gating.
- `Gate Flag`: boolean progression state used by doors/locks.

Legacy mapping used in earlier drafts:

- Sigil -> Key Item
- Attunement -> Ability Unlock

## Fixed Goals

1. Deliver one complete run in 10-15 minutes.
2. Place the final unlockable gate visibly beside player spawn in `R1`.
3. Use two progression layers:
   - Layer 1: collect 3 key items.
   - Layer 2: unlock 3 abilities (one per branch).
4. Require completion of both layers to open the final gate.

Player success statement:
Collect 3 key items, unlock 3 branch abilities, return to `R1`, unlock the final gate, clear the final area, and exit.

## Timing Assumptions

- Target first-time completion: 12 minutes.
- Acceptable completion band: 10-15 minutes.
- Layer 2 time budget: 30-60 seconds per branch (included inside branch duration, no extra rooms).

## Content Constraints

- Room count for MVP: `R1-R10`.
- One final area (`R9`).
- One exit room (`R10`) or merged exit trigger if scope compression is required.
- No new rooms added solely for Layer 2 in MVP v1.2.

## Progression Model (Two Layers)

### Layer 1: Key Item Collection (Macro Progress)

- `Key Item A` obtained in `R4`.
- `Key Item B` obtained in `R6`.
- `Key Item C` obtained in `R8`.
- Gate feedback in `R1` must update at 1/3, 2/3, 3/3 key items.

### Layer 2: Ability Unlock Activation (Unlockable Progression)

Each branch includes one ability unlock activation in its return path:

- `Ability Unlock A` (after `R4`) enables one hard-gate utility required once.
- `Ability Unlock B` (after `R6`) grants one soft-power utility used before final.
- `Ability Unlock C` (after `R8`) grants one soft-power utility used before final.

Ability unlock constraints:

- Interaction must be obvious and completed in-place (no hidden backtracking requirement).
- Confirmation must have clear UI/audio response.
- Branch remains completable if player dies and retries before unlock is confirmed.

## Logic Constraints

Final gate unlock condition is:

- `key_items_collected == 3`
- `abilities_unlocked == 3`

No hidden extra conditions for final unlock.

Required tracked state:

- `key_item_a`, `key_item_b`, `key_item_c`
- `ability_unlock_a`, `ability_unlock_b`, `ability_unlock_c`
- `key_items_collected`, `abilities_unlocked`
- `final_gate_state`

Gate state labels:

- `LOCKED_KEY_ITEMS`
- `LOCKED_ABILITIES`
- `UNLOCKED`

## Non-Goals (Out of Scope for MVP)

1. Branching endings.
2. Additional biome branches beyond the `R1-R10` plan.
3. Multi-tier skill trees beyond the 3 defined ability unlocks.
4. Optional side-quests required for completion.
5. Complex multi-stage quest scripting for core progression.

## Quality Guardrails

1. Objective clarity:
   - Players should understand the two-step goal (collect key items, then complete ability unlocks) without external instruction.
2. Progression clarity:
   - `R1` gate must visibly distinguish missing key items vs missing ability unlocks.
3. Sequence safety:
   - Branches may be completed in any order without breaking progression state.
4. State safety:
   - Duplicate interactions cannot increment key item/ability totals more than once.

## Acceptance Criteria for Constraints

1. In first 2 minutes, testers can describe final requirement as "3 key items + 3 ability unlocks".
2. Median test run remains near 12 minutes after Layer 2 is added.
3. 80%+ of internal testers complete the full unlock loop within 10-15 minutes.

## Change Control

Any change to this document requires explicit sign-off from project owner before implementation.

Required approval for changes:

- Scope changes: room count, final gate location, key item count, ability unlock count, timing targets.
- Progression logic changes: unlock condition or required completion order.

## Sign-off

- Project owner: Tim Wood
- Approved on: 2026-03-08
- Next review checkpoint: after Activity 4 (Gate and State Logic freeze)
