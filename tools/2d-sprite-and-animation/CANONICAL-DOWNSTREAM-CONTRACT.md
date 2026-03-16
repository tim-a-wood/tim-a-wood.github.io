## Canonical Downstream Contract

New downstream writes use these canonical files only:

- `sprite_model.json`
- `sprite_model_history.json`
- `rig.json`
- `animation_clips.json`
- `manual_animation_clips.json`
- `qa_report.json`

Legacy files are read for hydration only:

- `layered_character.json`
- `animation_templates.json`
- `palette.json`

Canonical sprite workbench routes:

- `POST /api/projects/<project_id>/sprite-model/build`
- `POST /api/projects/<project_id>/sprite-model/update`
- `POST /api/projects/<project_id>/sprite-model/recover-occlusion`
- `POST /api/projects/<project_id>/sprite-model/promote-recovery`
- `POST /api/projects/<project_id>/sprite-model/undo`
- `POST /api/projects/<project_id>/sprite-model/restore`
- `POST /api/projects/<project_id>/sprite-model/approve`
- `POST /api/projects/<project_id>/rig/build`
- `POST /api/projects/<project_id>/rig/approve`
- `POST /api/projects/<project_id>/clips/<clip_name>/update`
- `POST /api/projects/<project_id>/clips/<clip_name>/reset`
- `POST /api/projects/<project_id>/clips/<clip_name>/render`
- `GET /api/projects/<project_id>/manual-clips`
- `POST /api/projects/<project_id>/manual-clips/create`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/update-meta`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/frame/<frame_index>`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/frame/<frame_index>/copy`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/frame/<frame_index>/reset`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/frame/<frame_index>/repair/<part_name>/generate`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/frame/<frame_index>/repair/<part_name>/apply`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/frame/<frame_index>/repair/<part_name>/clear`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/frame/<frame_index>/patch/<part_name>/generate`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/frame/<frame_index>/patch/<part_name>/apply`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/frame/<frame_index>/patch/<part_name>/clear`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/render-preview`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/approve`
- `POST /api/projects/<project_id>/manual-clips/<clip_id>/unapprove`
- `POST /api/projects/<project_id>/qa/run`
- `POST /api/projects/<project_id>/export`

Notes:

- `sprite_model.json` carries the palette and the latest `build_report`.
- `sprite_model_history.json` stores both the event log and revision snapshots.
- `animation_clips.json` is the only canonical clip source for idle and walk.
- `manual_animation_clips.json` stores optional named manual clips and their approval state separately from procedural idle/walk generation.
- manual clip frames now persist pose `transforms` plus optional per-frame `part_repairs` overrides and `corrective_patches` for gap-filling patches rendered behind a chosen front part.
