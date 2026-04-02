# Room Environment Pipeline V3 — Creative Review

**Date:** 2026-04-01
**Reviewer:** Creative
**Package reviewed:**
- [docs/room-environment-pipeline-v3-spec.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-spec.md)
- [docs/reports/room-environment-v3-stakeholder-review-kickoff-2026-04-01.md](/Users/timwood/Desktop/projects/PWA/MV/docs/reports/room-environment-v3-stakeholder-review-kickoff-2026-04-01.md)
- [decisions/2026-03-31-room-environment-quality-pass.md](/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md)

## Position

Accept with changes.

Creative agrees with the diagnosis that the current pipeline fails because it does not protect visual identity, shell coherence, or component role strongly enough. The v3 direction is substantially better. The spec should be strengthened in a few areas before implementation begins.

## Top Findings

### 1. Biome distinctness needs stronger visual language than palette and material labels alone

The proposed biome-definition model is much better than the current single-pack approach, but Creative wants stronger emphasis on:

- silhouette families
- trim weight
- edge wear language
- architectural rhythm
- accent placement rules

If these are weak, the system will still drift into “same room, different tint.”

Recommendation: each biome definition should include a concise visual identity checklist used during review.

### 2. Component-fit rules are correct, but visual rejection criteria need to be harsher

Creative strongly supports making component-fit a top-level gate. This is the most important quality improvement in the spec.

Recommended visual rejection conditions:

- wall reads as backdrop instead of enclosure
- floor reads as illustration or mural instead of a playable surface
- platform reads as decorative prop
- door reads as niche or ornament rather than threshold
- background becomes the focal scene
- midground competes with gameplay

### 3. Structural vs scenic separation is the right direction

Creative agrees that structural surfaces must carry shell readability and that scenic layers must support mood instead of replacing structure.

This is especially important for:

- shrine-like rooms
- fog-heavy rooms
- vertical shafts
- rooms with strong focal landmarks

Recommendation: the first calibration slice should visually compare structural-only, scenic-only, and combined views during review so the team can see what each layer is actually doing.

### 4. Screenshot review evidence is sufficient if annotated review is required

The proposed screenshot package is good. Creative wants annotations required for:

- shell silhouette problems
- motif violations
- foreground/background confusion
- palette or value hierarchy issues

Without annotations, the review history will be harder to use in later rounds.

### 5. Gemini remains acceptable under the proposed constraints

Creative does not object to keeping Gemini if:

- biome and component contracts are explicit
- slot prompts are narrow
- forbidden motifs are enforced
- all outputs remain human-reviewed

Creative does object to using Gemini with broad scenic prompts as a primary strategy for structural outputs.

## Required Additions

### 1. Biome Identity Checklist

Every biome should define:

- shell silhouette identity
- dominant trim language
- allowed accent usage
- wear/damage language
- atmospheric density
- motif exclusions

### 2. Creative Round Rejection Codes

Recommended rejection codes:

- `shell_not_coherent`
- `component_role_unclear`
- `biome_identity_weak`
- `motif_violation`
- `focal_scene_drift`
- `value_hierarchy_broken`

### 3. Review Views

Creative recommends preserving these review views for first-slice calibration:

- assembly-plan overlay
- generated slot gallery
- combined bespoke kit
- runtime standard view
- runtime contrast-QA view

## Verdict

Pass with flags.

Creative supports the v3 direction. The strongest requirement is that the team must treat visual role clarity as a rejection-level issue, not a minor polish concern.

