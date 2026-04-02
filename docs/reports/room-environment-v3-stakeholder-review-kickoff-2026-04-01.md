# Room Environment Pipeline V3 — Stakeholder Review Kickoff

**Date:** 2026-04-01
**Owner:** Level Design
**Review package:** [docs/room-environment-pipeline-v3-spec.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-spec.md)
**Decision log:** [decisions/2026-03-31-room-environment-quality-pass.md](/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md)
**Review mode:** decision
**Status:** Open for stakeholder review

---

## Purpose

This kickoff starts the structured stakeholder review for the proposed room environment pipeline v3 rewrite.

The current pipeline has been reviewed end-to-end and found to be structurally insufficient in three critical areas:

- prompt/spec architecture
- biome setup and selection
- room-to-component fit

This review is intended to align Development, QA, Creative, and Founder before implementation begins.

---

## What Is Being Reviewed

Stakeholders are reviewing the proposal to replace the current room environment generation block with a staged v3 pipeline:

1. Art direction lock
2. Biome kit definition
3. Room assembly planning
4. Slot generation
5. Runtime and manual review

The most important changes under review are:

- component-fit becoming a top-level quality gate
- biomes becoming explicit production data rather than one implicit shared pack
- room assembly being generated from actual room geometry
- QA and Creative manual screenshot review becoming mandatory before signoff

---

## Stakeholders and Required Input

## Development

Development is asked to review:

- data model feasibility
- schema changes required for `biome_definition`, `assembly_plan`, and `review_state`
- planner rewrite scope
- prompt scaffold rewrite scope
- runtime capture and review tooling implications

Development must respond with:

- feasibility assessment
- major architecture risks
- recommended implementation sequence
- any blocking schema/versioning concerns

## QA

QA is asked to review:

- automated validation coverage
- screenshot capture checkpoints
- manual validation workflow
- review round exit criteria
- fixture strategy for repeated regression checks

QA must respond with:

- missing validation gates
- testability concerns
- recommended fixture room set
- whether the proposed review loop is realistic and sufficient

## Creative

Creative is asked to review:

- biome definition quality requirements
- component-fit review criteria
- structural vs scenic separation
- manual screenshot review checkpoints
- visual acceptance criteria for coherence and motif control

Creative must respond with:

- missing art-direction controls
- any component types that need stronger definition
- whether biome distinctness and shell coherence are adequately protected
- any concerns about Gemini remaining in the pipeline

## Founder

Founder is asked to review:

- whether to approve a pipeline rewrite instead of another iteration pass
- whether the proposed review loop and implementation cost are justified
- whether the first build slice and rollout scope are acceptable

Founder decision needed:

- approve v3 rewrite direction
- approve first build slice
- approve manual stakeholder review loop as a formal gate

---

## Review Questions by Stakeholder

## Development Review Questions

1. Does the proposed v3 data model create any unacceptable architectural risk?
2. What should be implemented first: schema, planner, prompt scaffold, or review tooling?
3. Which parts of the current pipeline can be safely reused, and which should be replaced outright?
4. What runtime or export versioning decisions are required before implementation starts?

## QA Review Questions

1. Are the proposed screenshot checkpoints sufficient to catch the current known failure modes?
2. Does the proposed manual validation loop cover both workflow correctness and final room readability?
3. What additional fixture coverage is required before the pipeline can be judged stable?
4. Which failures should block a round versus be tracked as follow-up defects?

## Creative Review Questions

1. Are the proposed biome definitions strong enough to create distinct visual identities?
2. Are the component-fit rules precise enough for visual approval?
3. Do the screenshot review checkpoints provide enough evidence to judge shell coherence and motif drift?
4. Which component types need stronger artistic constraints before implementation begins?

## Founder Review Questions

1. Is the quality problem severe enough to justify a staged rewrite?
2. Is the proposed first slice narrow enough to de-risk the rewrite?
3. Are the review loops with QA and Creative sufficient to avoid another failed iteration cycle?
4. Should any scope be reduced before approval?

---

## Proposed Review Sequence

## Step 1: Individual Review

Each stakeholder reads:

- [docs/room-environment-pipeline-v3-spec.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-spec.md)
- relevant sections of [decisions/2026-03-31-room-environment-quality-pass.md](/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md)

Each stakeholder returns:

- accept
- accept with changes
- reject

and written notes against the questions above.

## Step 2: Consolidation Pass

Level Design and Development synthesize:

- points of agreement
- open risks
- disagreements
- requested changes to the spec

## Step 3: Founder Decision Brief

Founder reviews:

- the updated spec
- stakeholder comments
- implementation recommendation

Founder then approves:

- proceed
- proceed with changes
- hold

## Step 4: Validation Planning

If approved, QA and Creative define:

- the first-round room set
- screenshot naming and storage convention
- review annotations format
- round exit criteria in operational form

---

## Required Manual Validation Commitment

The review package assumes that QA and Creative will jointly participate in repeated validation rounds.

Minimum required rounds after implementation begins:

- Round A: baseline
- Round B: post-fix regression
- Round C: biome stress pass
- Round D: final signoff pass

No pipeline signoff should happen before these rounds complete.

---

## Feedback Recording Format

Each stakeholder should record feedback in this format:

### Reviewer

- Name:
- Role:
- Date:
- Decision: accept / accept with changes / reject

### Findings

- Finding 1:
- Finding 2:
- Finding 3:

### Requested Changes

- Change 1:
- Change 2:

### Risks

- Risk 1:
- Risk 2:

### Approval Position

- I support proceeding as written
- I support proceeding after requested changes
- I do not support proceeding

---

## Proposed First Slice for Review Alignment

The initial implementation slice remains:

- biome: ruined gothic
- rooms:
  - corridor transition
  - shrine chamber
  - vertical shaft

This slice is proposed because it is large enough to test:

- component-fit
- shell readability
- biome coherence
- manual review workflow

without forcing the team to solve every biome at once.

---

## Immediate Next Step

Stakeholders should review the v3 spec and respond in writing against their role-specific questions before implementation begins.

