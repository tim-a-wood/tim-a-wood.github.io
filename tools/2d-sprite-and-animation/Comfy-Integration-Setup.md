## ComfyUI Integration Setup

This workbench can drive the `ai_sideview_v1` pipeline directly against a local ComfyUI instance. The goal is that day‑to‑day sprite production runs from the workbench UI only; Comfy stays in the background as an image/motion engine.

### 1. Run ComfyUI

- **Clone / install ComfyUI** in your preferred location.
- Start it with a fixed listen address and port the workbench expects:

```bash
python main.py --listen 127.0.0.1 --port 8188
```

- If you change the host or port, set:

```bash
export SPRITE_WORKBENCH_COMFYUI_URL="http://127.0.0.1:8188"
```

before starting `sprite_workbench_server.py`.

### 2. Required models and custom nodes

The side‑view pipeline assumes the following capabilities are installed into ComfyUI. Exact download locations may vary by distribution; use these as **suggested defaults** and adjust to your environment.

- **PhotoMaker checkpoint / adapter**
  - Install the PhotoMaker checkpoint and loader node into ComfyUI.
  - Recommended location: `ComfyUI/models/checkpoints/photomaker.safetensors`.
  - Configure the checkpoint name in the Character Lock / Key Pose workflows if it differs.
  - Signal readiness to the workbench:

    ```bash
    export SPRITE_WORKBENCH_PHOTOMAKER_READY=1
    ```

- **IPAdapter+ weights**
  - Install the IPAdapter+ model files (usually under `ComfyUI/models/ipadapter/`).
  - Ensure the Comfy graph nodes in `character_lock_photomaker.json` and `key_pose_photomaker.json` point at the correct model name.
  - Signal readiness:

    ```bash
    export SPRITE_WORKBENCH_IPADAPTER_PLUS_READY=1
    ```

- **ToonCrafter (video / motion model)**
  - Install the ToonCrafter model and related nodes (often distributed as a custom ComfyUI node pack).
  - Place model weights under something like `ComfyUI/models/tooncrafter/`.
  - Update `motion_tooncrafter.json` if your node names differ.
  - Signal readiness:

    ```bash
    export SPRITE_WORKBENCH_TOONCRAFTER_READY=1
    ```

- **Anime / person segmentation model**
  - Install an anime‑oriented foreground segmentation model (e.g. AnimeSeg) for optional masking inside Comfy.
  - Typical placement: `ComfyUI/models/unet/anime_segmentation_<variant>.safetensors`.
  - Signal readiness:

    ```bash
    export SPRITE_WORKBENCH_ANIME_SEGMENTATION_READY=1
    ```

- **Pixel‑art cleanup / detector**
  - Install a compact pixel‑art cleanup or style‑transfer node if you plan to move `pixel_cleanup` into Comfy.
  - Place the model under `ComfyUI/models/pixelart/` (or similar).
  - Signal readiness:

    ```bash
    export SPRITE_WORKBENCH_PIXELART_CLEANUP_READY=1
    ```

None of these flags **block** the pipeline; they are surfaced in `/api/ai-workflow/health` and the UI as **warnings** only.

### 3. Workflow templates used by the workbench

The workbench expects the following workflow templates in `tools/2d-sprite-and-animation/workflows/`:

- `character_lock_photomaker.json`
- `key_pose_photomaker.json`
- `motion_tooncrafter.json`
- `pixel_cleanup_pixelart.json` (optional, future use)

Each template contains:

- A **`meta`** section describing:
  - Which node loads the checkpoint.
  - Which nodes accept positive / negative prompt text.
  - The latent size (width / height).
  - The sampler seed / cfg / steps / denoise inputs.
  - Optional conditioning image inputs (PhotoMaker / IPAdapter+ / ToonCrafter).
  - The `SaveImage` node and its `filename_prefix`.
- A **`prompt`** section which is the raw ComfyUI graph.

The Python backend patches the `meta` inputs at runtime (prompts, seed, conditioning image, frame count, etc.) and then:

1. Sends the graph to ComfyUI via `POST /prompt`.
2. Polls `/history/<prompt_id>` until outputs are available.
3. Downloads the resulting images into the current project’s `ai_workflow` folders.

You can edit the graphs visually in ComfyUI and re‑export, as long as the `meta` mappings stay consistent.

### 4. Backend mode selection

Each sprite workbench project has a `brief.backend_mode` field:

- `"comfyui"` — run Character Lock / Key Pose / Motion through ComfyUI.
- `"debug_procedural"` — use deterministic Pillow‑based placeholders and **never** talk to ComfyUI.

The UI exposes the active backend in the AI boards. If Comfy is down or misconfigured, you can switch a project back to `debug_procedural` and continue working.

