# Room Environment V3 Planner Checkpoint Packet

**Date:** 2026-04-02  
**Checkpoint:** Planner  
**Status:** Ready for external QA and Creative review  

---

## Purpose

This packet is the first external checkpoint for the v3 room-environment implementation. It is intended for QA and Creative to validate whether the current planner direction is structurally sound before broader slot-generation work continues.

This is not a workbench feature review. It is an implementation review packet.

## Current Implementation State

Implemented:
- versioned `v3` environment contract
- `room_intent`
- `component_contracts`
- `assembly_plan`
- geometry-first planner path for v3
- planner coverage summary in the environment results surface
- runtime-focused validation state

Explicitly not in product scope:
- in-tool QA workflow
- in-tool Creative workflow
- review-bundle persistence
- manual-review approval gating

## Locked First Slice

- Biome: `ruined-gothic`
- Visual direction: medieval dungeon / castle
- Calibration fixture: [ruined_gothic_calibration_rooms.json](/Users/timwood/Desktop/projects/PWA/MV/tests/fixtures/room_environment_v3/ruined_gothic_calibration_rooms.json)

Selected rooms:
- `RG-R1` Gatehouse Threshold
Small threshold room for floor, doorway, and clear shell-readability checks.
- `RG-R2` Broken Hall Passage
Wide castle hall for side-wall rhythm, pit handling, and multi-door horizontal traversal coverage.
- `RG-R3` Keep Descent Shaft
Tall vertical room for shaft readability, upper-door handling, and stacked traversal coverage.

## What QA Should Validate At This Checkpoint

- planner coverage matches actual room structure
- all meaningful doors are represented
- major traversal platforms are represented
- pits, ceiling, and shell-supporting regions appear when needed
- no major structural coverage gap exists that would make later generation misleading

## What Creative Should Validate At This Checkpoint

- selected biome direction fits the intended room role
- planned component breakdown supports a readable shell hierarchy
- component categories are likely to produce role-fitting art
- the planner is not already pushing the room toward scene drift or motif confusion

## Evidence To Review

Use these implementation surfaces:
- v3 results summary in the room editor
- assembly-plan coverage summary
- assembly slot list
- overlay geometry summary
- relevant room JSON if coverage needs verification against raw structure

Primary code references:
- [room_environment_v3.py](/Users/timwood/Desktop/projects/PWA/MV/scripts/room_environment_v3.py)
- [room_environment_system.py](/Users/timwood/Desktop/projects/PWA/MV/scripts/room_environment_system.py)
- [room-layout-editor.html](/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html)

## Recommended Review Questions

### QA

1. Does the planner cover the room’s actual gameplay-critical geometry?
2. Are any doors, platforms, or pits omitted or reduced incorrectly?
3. Would later slot generation be misleading because the planner already simplified the room too aggressively?

### Creative

1. Does this component breakdown support strong shell readability?
2. Are the planned component types appropriate for the desired room feel?
3. Is the biome-direction setup likely to create distinct, role-fitting outputs?

## Exit Criteria

This checkpoint passes when:
- QA reports no blocker-level planner coverage issue
- Creative reports no blocker-level shell or biome-direction issue
- any major findings are converted into concrete implementation tasks before slot-calibration continues

## Deliverables Expected From Reviewers

Reviewers should return:
- one short memo each using [external-checkpoint-review.md](/Users/timwood/Desktop/projects/PWA/MV/templates/external-checkpoint-review.md)
- explicit outcome: `continue`, `continue with changes`, or `stop and revise`

## Known Open Items Before Review Starts

- reviewer names and owners are not assigned in this packet
- exported overlay screenshots are still lightweight; reviewer may need to cross-check the room JSON for edge cases

- Recommendation: Use this packet for the first external planner checkpoint before moving deeper into slot-output calibration.
- Risks: If the calibration rooms are not chosen carefully, the checkpoint can miss planner failures that only appear in more vertical or multi-door rooms.
- Confidence: High because the current v3 implementation is far enough along for meaningful early structural review.
- Founder approval needed: No.
- Next actions: 1. Lock the first checkpoint room set. 2. Assign QA and Creative reviewers. 3. Gather the planner evidence for those rooms. 4. Collect memos and fold findings into the next implementation slice.
