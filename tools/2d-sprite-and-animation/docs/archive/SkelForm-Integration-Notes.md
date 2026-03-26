## SkelForm Integration Notes

This file captures the validation spike behind the browser-embedded external authoring path.

Status: retired as the active workflow. The current production path is `ai_sideview_v1`, and SkelForm remains documented here only for historical context and legacy project hydration.

### Validated Findings

- Candidate selected: `SkelForm`
- Editor URL: `https://skelform.org/editor/`
- Docs URL: `https://skelform.org/user-docs/`
- License: `MIT`
- Browser embedding: the hosted editor currently responds without `X-Frame-Options`, so iframe embedding is viable for the current workbench prototype.
- Initial build strategy: use the hosted editor first, keep local vendoring/self-hosting as a later hardening step.
- Expected import contract for the workbench adapter:
  - spritesheet image
  - atlas JSON
  - animations JSON
  - optional preview GIF

### Current Implementation

- Projects can enable `SkelForm` external authoring from the wizard shell.
- When enabled, the workbench hides the legacy middle authoring stages for that project:
  - `rig_layout`
  - `part_manifest`
  - `part_shape_edit`
  - `split_build`
  - `split_review`
  - `sprite_model`
  - `rig`
- The `Build Animations` stage becomes the integration surface:
  - embedded SkelForm iframe
  - import form for exported assets
  - imported bundle review
- QA and export now support an `external_authoring` mode that validates and packages the imported bundle without requiring the legacy rig pipeline.

### Deferred Follow-Up

- Validate a fully self-hosted SkelForm build and pin the exact source revision before vendoring.
- Expand the adapter if SkelForm exposes a richer export/runtime format that can remove the current atlas/animations import assumptions.
- Add browser-level acceptance coverage for the embedded editor flow once the project has a stable local test route for it.
