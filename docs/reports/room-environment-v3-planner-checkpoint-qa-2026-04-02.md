# External Checkpoint Review

**Feature:** Room environment v3  
**Checkpoint:** `planner`  
**Date:** 2026-04-02  
**Reviewer role:** `QA Agent`  
**Reviewer:** Project QA agent, using [qa/charter.md](/Users/timwood/Desktop/projects/PWA/MV/agents/qa/charter.md)  
**Build / branch / commit:** Current workspace state  

---

## Scope

- Rooms reviewed: `RG-R1`, `RG-R2`, `RG-R3`
- Biome reviewed: `ruined-gothic`
- Pipeline version: `v3`
- Phase objective: Validate planner coverage and regression risk before slot calibration expands

## Evidence Reviewed

- [room-environment-v3-planner-checkpoint-packet-2026-04-02.md](/Users/timwood/Desktop/projects/PWA/MV/docs/reports/room-environment-v3-planner-checkpoint-packet-2026-04-02.md)
- [ruined_gothic_calibration_rooms.json](/Users/timwood/Desktop/projects/PWA/MV/tests/fixtures/room_environment_v3/ruined_gothic_calibration_rooms.json)
- [room_environment_v3.py](/Users/timwood/Desktop/projects/PWA/MV/scripts/room_environment_v3.py)

## Findings

### 1. Upper-door handling is under-specified for shaft-style rooms
- Severity: `major`
- Area: `planner_coverage`
- What was reviewed: `RG-R3` Keep Descent Shaft and the current door-slot planner logic
- What is wrong: The planner covers all doors numerically, but it does not explicitly distinguish top-entry door treatment from side or floor-entry thresholds. That creates a regression risk where a planner can appear complete while still giving the slot generator the wrong shape expectation for upper-entry castle shafts.
- Why it matters: This kind of structural mismatch is exactly the sort of issue that will pass coarse coverage counts and still fail later in runtime readability.
- Recommended change: Infer door anchor class from room position and emit top-entry door slots with different placement assumptions than side or floor-entry doors.

### 2. Wide-hall coverage still risks under-describing shell rhythm
- Severity: `major`
- Area: `planner_coverage`
- What was reviewed: `RG-R2` Broken Hall Passage and the current fixed side-wall / backwall plan shape
- What is wrong: The planner always emits a single broad backwall panel and a single left/right wall span pattern. For a wide ruined hall, that is likely enough to pass basic slot counts but not enough to test whether shell rhythm and modular repetition are actually represented.
- Why it matters: QA’s job is to flag likely regression points before they ship; this is a likely place where the planner can claim coverage while still underfitting the room.
- Recommended change: Split wide-room backwall coverage into multiple planned spans and make side-wall sizing more responsive to room width.

## What Looks Good

- The planner no longer collapses to one floor, a few platforms, and one door.
- The calibration set is narrow enough to support focused iteration.
- `RG-R1`, `RG-R2`, and `RG-R3` cover threshold, hall, and shaft risk profiles well.

## Checkpoint Outcome

- Outcome: `continue with changes`
- Conditions before next phase: Address upper-door treatment and wide-hall shell-span planning before broad slot calibration.
- Owner for follow-up: Development

- Recommendation: Proceed to slot calibration only after the planner is made more truthful for upper-door shafts and wide ruined halls.
- Risks: If slot calibration starts before those planner gaps are corrected, later asset-quality findings will be noisy and harder to attribute.
- Confidence: High because these are structural-risk findings rooted in the QA charter’s regression-readiness lens.
- Founder approval needed: No.
- Next actions: 1. Update planner logic for door anchor classes. 2. Update planner logic for wide-room shell spans. 3. Re-run this checkpoint packet against the same three rooms. 4. Then move to slot calibration.
