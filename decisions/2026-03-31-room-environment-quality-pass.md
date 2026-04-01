# Room Environment Quality Pass

**Date:** 2026-03-31
**Feature:** Typed environment component schema overhaul and bespoke room environment quality pass
**Status:** Active
**Owner:** Environment art / runtime pipeline agents

---

## Purpose

This log records decisions for the room environment and bespoke asset quality pass so future agents do not repeat failed composition strategies, misleading build behaviors, or weak validation contracts.

## Working Rules

- Read this file before making another substantive change to the environment-art generation pipeline, runtime composition, or review gate.
- Update this file after meaningful decisions, reversals, or rejected directions.
- Record both accepted and rejected paths.

## Decisions

### 1. Typed component schemas are now the primary production contract
- Status: Accepted
- Why: The older coarse prompt map was not constraining walls, floors, platforms, background, and midground strongly enough.
- Consequence: Production logic should prefer `env.spec.component_schemas` over the legacy prompt bundle.

### 2. Build completion must require runtime review, not just image generation
- Status: Accepted
- Why: Prior versions could report success while still producing unreadable rooms or stale playtest output.
- Consequence: `Build Production Assets` is not complete until schema validation, required slot generation, and runtime screenshot review all pass.

### 3. Template-only “success” for v2 production slots is not acceptable
- Status: Rejected
- Why: It created false-positive builds where assets looked unchanged and no real AI generation occurred.
- Consequence: Structural and scenic v2 slots must use the AI generation path; template fallback may be used only as a guide/reference mechanism, not as the final silent output.

### 4. Reusing approved previews or scene-heavy frozen concept art for structural production slots is not acceptable
- Status: Rejected
- Why: It kept reintroducing scenic focal art into walls, floor language, and shell components.
- Consequence: Structural slots use slot-specific guide references derived from templates, not room preview imagery.

### 5. Scenic production slots must be guided by sanitized slot references, not by raw scene art
- Status: Accepted
- Why: Raw scenic references kept reintroducing center clutter, shrine/altar reads, and floor/background mismatch.
- Consequence: `background_far_plate` and `midground_side_frame` now use sanitized guide images with explicit center suppression / center clearance.

### 6. Runtime review must be honest even if playtest rendering is provisional
- Status: Accepted
- Why: Users need to inspect failed-but-built outputs, but the build state still needs to reflect actual quality failures.
- Consequence: Playtest may show provisional assets for inspection while the manifest remains blocked or failed.

### 7. The current “calm center” suppression can overshoot into a fog slab
- Status: Accepted problem statement
- Why: One passing runtime review still produced a visually weak room where the center became an over-suppressed gray block.
- Consequence: Future work must tighten the review gate to reject collage/composite reads and over-suppressed scenic emptiness, not just altar/clutter failures.

### 8. The room currently needs stronger shell readability inspired by Hollow Knight-like separation
- Status: Accepted direction
- Why: The desired target is clearer structural readability with dark wall masses, sharp platform/floor edges, and distinct foreground/background separation.
- Consequence: Future schema and slot work should emphasize heavy wall masses, crisp traversable edges, stronger value separation, and likely additional structural component types such as ceiling, backwall panel, or wall face.

### 9. Runtime must render the bespoke shell pieces, not just the scenic plate and top strips
- Status: Accepted
- Why: The latest pass still read like a collage because runtime mostly relied on the background/midground plus top lip assets, while bespoke wall modules, wall trims, and floor/platform faces were not carrying the room shell in play.
- Consequence: Runtime now preloads all bespoke slots and uses placed wall modules, wall trims, floor faces, and platform faces as environment decor so the play view more closely matches the authored shell kit.

### 10. Runtime review must fail over-suppressed “fog slab” rooms, not just cluttered ones
- Status: Accepted
- Why: The previous gate could pass rooms with a very calm center even when that calmness flattened into a giant unreadable slab and floor/background separation stayed weak.
- Consequence: Runtime review now records extra center-lane contrast metrics and fails rooms when low floor/background separation combines with an over-suppressed, structurally unreadable center lane.

### 11. Midground side frames must reject bright inner-edge doorway reads
- Status: Accepted
- Why: One recurring artifact in the latest pass was luminous vertical bands near the center lane that read like pasted doorway cutouts instead of side-only framing.
- Consequence: Midground validation and postprocessing now detect and suppress hot inner-edge bands so side framing stays dark and subordinate.

## Rejected Paths To Avoid Repeating

- Repeatedly prompt-tuning the same scenic background concept without changing the source-art contract.
- Treating a “passed” build as good enough without reviewing the runtime screenshot.
- Using one scenic plate to imply walls, ceiling, room shell, floor continuity, and depth simultaneously.
- Assuming a build is “close enough” if the runtime only shows the scenic plate plus traversal top strips while the bespoke shell pieces sit unused in the manifest.
- Interpreting fast build completion as success when the system may still be using silent template paths or stale outputs.

### 12. Solid black background is approved only as temporary QA, not a shipping biome
- Status: Accepted
- Why: Wall/floor/platform bespoke readability passes need a neutral ground; tinted theme backgrounds compete with shell evaluation.
- Consequence: Runtime and editor expose `themeId: contrast-qa` with camera clear color `#000000`. Label and copy state **temporary QA**; shipping rooms should use normal biomes (`cave`, `ruins`, etc.). Starfield tint is subdued (`0x333333`) so parallax does not dominate the pass.

## Open Questions

- Should `ceiling`, `backwall_panel`, or `wall_face` become first-class component schema types?
- Should runtime review add explicit collage/composite heuristics and stronger floor/wall/platform edge separation checks?
- Should scenic slots remain AI-generated, or should some shell/background families move to more deterministic construction?
