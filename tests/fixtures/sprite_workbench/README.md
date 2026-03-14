## Sprite Workbench Fixture Matrix

This folder holds the three project classes used by the sprite workbench migration and downstream contract tests:

- `legacy-layered-character/`
  Reads only legacy downstream files such as `layered_character.json`, `animation_templates.json`, and `palette.json`.
- `hybrid-mixed-pipeline/`
  Contains both legacy and canonical downstream data so load and duplicate behavior can be tested against mixed-schema projects.
- `canonical-sprite-model/`
  Uses only the canonical downstream files for sprite-model, rig, clip, QA, and export verification coverage.

The regression suite in `tests/test_sprite_workbench.py` uses these fixtures to verify:

- legacy hydration still loads safely
- duplicate and archive flows work across all three project classes
- new writes stay on the canonical downstream contract
- sprite-model validation, revision restore, clip persistence, and export verification remain stable
