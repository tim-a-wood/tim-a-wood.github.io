# Gate State Spec v1 (Frozen)

Version: 1.0
Date: 2026-03-08
Status: Frozen
Depends on: `docs/map-mvp-constraints.md` v1.2, `docs/map-graph-v1.md` v1.0, `docs/progression-unlocks-v1.md` v1.0

## Purpose

Define deterministic progression-state behavior for final gate unlock in `R1`, including state variables, transitions, persistence, telemetry, and test coverage contract.

## State Variables (Authoritative)

- `key_item_a` (`boolean`)
- `key_item_b` (`boolean`)
- `key_item_c` (`boolean`)
- `ability_unlock_a` (`boolean`)
- `ability_unlock_b` (`boolean`)
- `ability_unlock_c` (`boolean`)
- `key_items_collected` (`integer`, 0..3)
- `abilities_unlocked` (`integer`, 0..3)
- `final_gate_state` (`enum`: `LOCKED_KEY_ITEMS` | `LOCKED_ABILITIES` | `UNLOCKED`)

Derived invariants:

- `key_items_collected = sum(key_item_a, key_item_b, key_item_c)`
- `abilities_unlocked = sum(ability_unlock_a, ability_unlock_b, ability_unlock_c)`
- Counters are always recomputable from booleans on load/resume.

## Valid Gate States

- `LOCKED_KEY_ITEMS`
  - Meaning: fewer than 3 key items collected.
- `LOCKED_ABILITIES`
  - Meaning: 3 key items collected, fewer than 3 abilities unlocked.
- `UNLOCKED`
  - Meaning: all 3 key items and all 3 abilities unlocked.

State resolver (single source of truth):

1. If `key_items_collected < 3`: `LOCKED_KEY_ITEMS`
2. Else if `abilities_unlocked < 3`: `LOCKED_ABILITIES`
3. Else: `UNLOCKED`

## Transition Rules

### Event Types

- `on_key_item_pickup(item_id)` where `item_id` in `{A, B, C}`
- `on_ability_unlock(unlock_id)` where `unlock_id` in `{A, B, C}`
- `on_run_load(saved_state)`
- `on_new_run_reset()`

### Key Item Pickup Transition

1. If target flag already `true`, no-op (idempotent).
2. Set corresponding `key_item_* = true`.
3. Recompute `key_items_collected` from booleans.
4. Resolve `final_gate_state` using resolver.
5. If gate state changed, emit `gate_state_changed` telemetry.

### Ability Unlock Transition

1. If target flag already `true`, no-op (idempotent).
2. Set corresponding `ability_unlock_* = true`.
3. Recompute `abilities_unlocked` from booleans.
4. Resolve `final_gate_state` using resolver.
5. If gate state changed, emit `gate_state_changed` telemetry.
6. If new state is `UNLOCKED`, emit `gate_unlocked` telemetry once.

### Load/Resume Transition

1. Read saved booleans and counters.
2. Normalize counters from booleans (booleans win if mismatch).
3. Resolve `final_gate_state` with resolver.
4. Persist normalized state back to save store.

### New Run Reset Transition

1. Set all six booleans to `false`.
2. Set counters to `0`.
3. Set `final_gate_state = LOCKED_KEY_ITEMS`.
4. Clear one-shot gate unlock emission guard for new run.

## Visual and Audio Behavior by Gate State (`R1`)

- `LOCKED_KEY_ITEMS`
  - Visual: 0-2 runes lit, chained gate frame, low-intensity red pulse.
  - Audio: muted hum, no unlock tone.
- `LOCKED_ABILITIES`
  - Visual: all 3 key runes lit, central core dim/unstable, amber pulse.
  - Audio: brighter hum layer, short deny chirp on interact.
- `UNLOCKED`
  - Visual: all runes + core fully lit, chains dissolved, gate aperture active.
  - Audio: one-time unlock stinger, stable open resonance loop.

## Interaction Text by Gate State

- `LOCKED_KEY_ITEMS`: `Gate sealed: recover 3 Key Items.`
- `LOCKED_ABILITIES`: `Gate sealed: awaken 3 Abilities.`
- `UNLOCKED`: `Gate attuned. Enter the Final Ascent.`

Optional progress suffix (recommended):

- `Keys: {key_items_collected}/3 | Abilities: {abilities_unlocked}/3`

## Idempotency and Data Integrity Rules

1. Duplicate pickup/unlock events cannot mutate counters if flag already true.
2. Counters are derived from booleans whenever mismatch is detected.
3. Gate unlock event (`gate_unlocked`) may fire at most once per run.
4. Invalid IDs for pickup/unlock are rejected and logged without state change.

## Save/Restore Contract

Persisted keys per run profile:

- `key_item_a`, `key_item_b`, `key_item_c`
- `ability_unlock_a`, `ability_unlock_b`, `ability_unlock_c`
- `key_items_collected`, `abilities_unlocked`
- `final_gate_state`
- `gate_unlocked_emitted` (one-shot telemetry guard)

Restore order:

1. Load booleans.
2. Normalize counters.
3. Resolve and set gate state.
4. Repair persisted record if normalized values differ.

## Reset Contract

`on_new_run_reset()` must:

- Clear all progression booleans.
- Reset counters and gate state.
- Clear one-shot telemetry guard.
- Leave unrelated user settings untouched.

## Telemetry Hooks

### `key_item_collected`

Payload:

- `run_id`
- `item_id` (`A|B|C`)
- `key_items_collected`
- `abilities_unlocked`
- `room_id`
- `timestamp`

### `ability_unlocked`

Payload:

- `run_id`
- `unlock_id` (`A|B|C`)
- `key_items_collected`
- `abilities_unlocked`
- `room_id`
- `timestamp`

### `gate_state_changed`

Payload:

- `run_id`
- `from_state`
- `to_state`
- `key_items_collected`
- `abilities_unlocked`
- `timestamp`

### `gate_unlocked`

Payload:

- `run_id`
- `key_items_collected` (must be `3`)
- `abilities_unlocked` (must be `3`)
- `timestamp`

## Transition Test Matrix

| ID | Scenario | Input/Event | Expected Result |
|---|---|---|---|
| GSM-01 | Fresh run state | `on_new_run_reset()` | All flags false, counts 0, gate `LOCKED_KEY_ITEMS` |
| GSM-02 | First key item | pickup `A` once | `key_item_a=true`, keys `1`, gate still `LOCKED_KEY_ITEMS` |
| GSM-03 | Duplicate key item | pickup `A` twice | Count increments once only |
| GSM-04 | All key items no abilities | pickups `A,B,C` | keys `3`, abilities `<3`, gate `LOCKED_ABILITIES` |
| GSM-05 | First ability unlock | unlock `A` after some keys | `ability_unlock_a=true`, abilities increment once |
| GSM-06 | Duplicate ability unlock | unlock `B` twice | Count increments once only |
| GSM-07 | Full unlock path | all keys + all abilities | gate transitions to `UNLOCKED`, `gate_unlocked` emitted once |
| GSM-08 | Post-unlock duplicate events | duplicate pickup/unlock after unlocked | gate remains `UNLOCKED`, no extra counters/events |
| GSM-09 | Load with stale counters low | booleans true, counters lower | counters normalized upward from booleans |
| GSM-10 | Load with stale counters high | booleans false, counters high | counters normalized downward from booleans |
| GSM-11 | Load mismatched gate state | persisted gate not matching counts | gate recomputed via resolver |
| GSM-12 | Invalid event IDs | pickup/unlock with bad ID | no state change, error log/telemetry for invalid input |
| GSM-13 | State transition ordering | keys hit 3 before abilities hit 3 | state sequence is `LOCKED_KEY_ITEMS -> LOCKED_ABILITIES` |
| GSM-14 | Direct unlock completion | final required ability obtained with keys already 3 | state changes `LOCKED_ABILITIES -> UNLOCKED` |

## Freeze Decision

This state machine is frozen as v1.0 and is the implementation contract for Activity 5+ gate behavior and QA.

Sign-off:

- Project owner: Tim Wood
- Frozen on: 2026-03-08
