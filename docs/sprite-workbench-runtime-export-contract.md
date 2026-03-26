# Sprite Workbench Runtime Export Contract

The runtime export is the game-facing output of Sprite Workbench. It is separate from **Export Project**, which preserves the editable project for backup or transfer.

## Package layout

Every runtime export writes a timestamped folder under the project export root. The package currently includes:

- `spritesheet.png`
- `atlas.json`
- `animations.json`
- `qa_report.json`
- `export_manifest.json`
- `animation_sheets/<clip>.png`
- `animation_sheets/<clip>.json`
- `frames/<clip>_<nn>.png`
- `preview_<clip>.gif`

The package may include additional provider lineage data in `export_manifest.json`, but consumers should treat the files above as the stable runtime boundary.

## Required top-level files

### `spritesheet.png`
Combined packed atlas for compatibility with simple runtimes that still want one packed texture.

### `atlas.json`
Frame map for `spritesheet.png`. The `frames` object must match the file names referenced by `animations.json`.

### `animations.json`
Runtime animation definition document keyed by clip name.

Each animation entry must include:

- `fps`
- `loop`
- `frame_count`
- `frames`
- `root_motion_policy`

Example:

```json
{
  "idle": {
    "fps": 8,
    "loop": true,
    "frame_count": 4,
    "frames": ["idle_00.png", "idle_01.png", "idle_02.png", "idle_03.png"],
    "root_motion_policy": "locked"
  }
}
```

### `qa_report.json`
The last successful QA output bundled alongside the runtime package.

### `export_manifest.json`
Top-level package lineage and verification record.

Required keys:

- `project_id`
- `export_timestamp`
- `tool_version`
- `export_mode`
- `preview_gifs`
- `animation_sheets`
- `bundle_hashes`
- `verification`

Provider-specific keys such as Pixel Lab lineage are allowed, but the keys above are the stable contract.

## Per-animation sheets

Each clip also ships with its own sheet and sheet metadata:

- `animation_sheets/<clip>.png`
- `animation_sheets/<clip>.json`

The sheet metadata file must include:

- `image`
- `animation`
- `fps`
- `loop`
- `frame_count`
- `order`
- `frames`

Example:

```json
{
  "image": "idle.png",
  "animation": "idle",
  "fps": 8,
  "loop": true,
  "frame_count": 4,
  "order": ["idle_00.png", "idle_01.png", "idle_02.png", "idle_03.png"],
  "frames": {
    "idle_00.png": {
      "x": 0,
      "y": 0,
      "w": 256,
      "h": 256,
      "pivot": [128, 245],
      "animation": "idle"
    }
  }
}
```

## Contract rules

- `animations.json` and each per-animation sheet metadata file must agree on `fps`, `loop`, and `frame_count`.
- Every file named in `animations.json` must exist under `frames/`.
- Every file named in a sheet metadata `order` list must exist in the corresponding `frames` map.
- `export_manifest.json` must include hashes for the atlas, `animations.json`, `qa_report.json`, and every per-animation sheet image/metadata file.
- `verification.status` must be `pass` for a successful runtime export.

## Consumer guidance

Use the per-animation sheets as the first-class runtime source when integrating into a game. Keep the combined atlas as a compatibility artifact unless the engine specifically prefers the single packed sheet.
