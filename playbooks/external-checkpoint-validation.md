# External Checkpoint Validation

Use this playbook when QA and Creative need to validate the room-environment v3 implementation as part of delivery, without adding workflow features to the workbench.

---

## Purpose

Bring QA and Creative in early enough to catch directional mistakes before implementation hardens, while keeping their validation process outside the product itself.

## Required Checkpoints

### 1. Planner Checkpoint

Run after:
- v3 schema/versioning is working
- room intent is visible
- assembly-plan coverage is visible
- planner output exists for at least one biome and one to three calibration rooms

Review goals:
- Does the plan reflect the actual traversal structure?
- Are doors, pits, platforms, and shell regions represented correctly?
- Does the intended biome direction fit the room role?

Required evidence:
- room summary
- selected biome summary
- planner coverage summary
- assembly-plan overlay or equivalent exported artifact

### 2. Slot Checkpoint

Run after:
- first structural slot outputs exist
- component contracts are stable enough to review
- one biome family has first-pass outputs for the calibration rooms

Review goals:
- Do walls, floors, platforms, doors, ceiling, and backwall art fit their roles?
- Is the shell language coherent?
- Is the biome identity materially distinct from other biomes?

Required evidence:
- slot sheet or exported slot gallery
- component contract summary
- side-by-side room examples across the calibration set

### 3. Runtime Checkpoint

Run after:
- runtime composition is using the generated kit
- runtime screenshots are stable enough for comparison

Review goals:
- Is traversal readability preserved?
- Does the shell hierarchy read clearly?
- Does scenic treatment support rather than obscure the room?

Required evidence:
- runtime screenshot per room
- contrast-QA screenshot if used
- note of any runtime validator warnings or failures

## Working Rules

- Keep checkpoints external to the workbench product.
- Use short written memos based on `/templates/external-checkpoint-review.md`.
- Do not move to the next phase if a checkpoint returns `stop and revise`.
- Fold findings into the implementation plan before proceeding.
- Keep the first slice narrow: one biome, one to three rooms.

## Deliverables

- one memo per reviewer role per checkpoint when possible
- one implementation synthesis after each checkpoint
- decision-log update when a checkpoint changes scope, gates, or accepted direction

- Recommendation: Use this playbook for QA and Creative involvement during v3 implementation so review happens early without expanding product scope.
- Risks: If checkpoints are too broad, they can create churn; if too narrow, they can miss structural quality issues.
- Confidence: High because this keeps the founder-requested early involvement while preserving the no-in-tool-workflow boundary.
- Founder approval needed: No.
- Next actions: 1. Choose the first checkpoint room set. 2. Prepare evidence artifacts. 3. Run QA and Creative review memos. 4. Fold findings into the next implementation phase.
