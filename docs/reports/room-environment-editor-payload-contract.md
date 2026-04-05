# Room Environment Results Tab Contract

**Date:** 2026-04-04
**Status:** Corrected implementation contract
**Scope:** Existing room editor Environment `Results` tab only

## Correction

The MVP surface is **not** a separate dashboard. It is an in-place extension of the existing room editor workbench, specifically the current Environment `Results` tab in [`room-layout-editor.html`](/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html).

That means:

- room layout remains the authoritative workspace
- the Results tab remains the delivery surface
- the new room-environment controls are embedded beside previews, assets, and revision flow
- no new dashboard shell, nav, or parallel workspace is introduced

## Authoring Fields

The following room-specific authoring fields live in `room.environment.spec`:

- `theme_name`
- `notes`
- `seed`
- `lock_stylepack`
- `reference_uploads`

These fields must remain visible inside the Results tab while the user reviews previews and assets.

## Results Tab Layout

The tab order does not change:

1. progress / wait state
2. room-level environment workbench strip
3. preview surface
4. staged summary cards
5. preview gallery
6. revision and build actions

## Embedded Workbench Strip

The new strip inside Results contains:

- theme name
- seed
- room notes
- reference upload control
- stylepack lock control
- layer toggles
- debug toggles

This strip is room-scoped metadata, not a global dashboard module.

## Staged Summary Order

The staged summaries remain fixed in this order:

1. Stylepack
2. Semantics
3. Kit
4. Manifest
5. Validation

Each stage is a compact card in the Results tab, not a top-level navigation destination.

## Toggle Rules

Layer and debug toggles are editor-only UI state.

- they do not belong in exported room JSON
- they do not replace the stylepack lock state
- they are secondary diagnostics, not the primary review surface

## Preview / Build Flow

The existing flow stays intact:

1. build environment
2. inspect preview candidates
3. approve a preview
4. build production assets
5. inspect runtime review

The new staged cards and authoring strip support that flow; they do not replace it.

## QA States

QA should validate these states in the embedded Results tab:

1. Empty
2. Draft
3. Locked
4. Generating
5. Partial
6. Ready
7. Blocked

For each state, QA should check:

- authoring strip values
- staged card order
- preview/gallery continuity
- build button copy and disabled state
- toggle visibility and persistence within the editor session

## Recommendation

Implement and review the MVP as an extension of the existing room editor Results tab only.
