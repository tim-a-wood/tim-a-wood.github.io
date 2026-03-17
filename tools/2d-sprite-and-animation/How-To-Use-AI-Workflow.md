# How to Use the Sprite Workbench (ai_sideview_v1)

The workbench is an **AI-first** pipeline for one side-view character: **Brief → Character Lock → Key Pose Board → Motion Workflow → Cleanup & QA → Export**.

---

## 1. Start the server and open the tool

- From the project root, run:
  ```bash
  python3 scripts/sprite_workbench_server.py --port 8766
  ```
- In your browser open: **http://127.0.0.1:8766/tools/2d-sprite-and-animation/index.html**

---

## 2. Use a **new** project (required for the new workflow)

- **Old projects** open in **read-only legacy mode**. To use the new AI workflow you must **create a new project**.
- Click **Create Project**, name it, and fill in the character description (e.g. “Humanoid knight in pixel style”). Optionally add reference images, then continue.
- New projects default to **debug mode**: the full pipeline runs without ComfyUI; the server generates variant images from your approved concept. For real PhotoMaker/ToonCrafter you’d switch the project to ComfyUI (see server/docs).

---

## 3. Follow the wizard steps

### Start → Describe Your Character → Add References
- Set the project name and a short character description. References are optional.

### Generate Prompt → Choose A Valid Concept
- Generate a prompt (or paste one from Gemini). Import a **side-view character image** (e.g. from Gemini). Validate it, then **approve one concept** as the chosen look. That image is the source for the rest of the pipeline.

### Character Lock
- Click **Generate 6 Candidates**. The tool produces six identity-locked side-view variants. **Approve one** candidate; that becomes the locked character for key poses.

### Key Pose Board
- Click **Generate 6 Canonical Poses**. You get the six canonical poses (idle_a, idle_b, walk contact/passing front/back). **Approve** the pose set you want to use for motion.

### Motion Workflow
- For **idle** and **walk**:
  1. **Run Motion** (pose-to-pose interpolation).
  2. **Extract Frames** (segment character, align to shared pivot).
  3. **Pixel Cleanup** (cleanup/downscale).
  4. **Approve Cleanup** for that clip.
- Do this for both idle and walk so both show as approved.

### Cleanup & QA
- Click **Run Cleanup & QA**. The tool checks frame count, transparency, pivot alignment, etc. Fix any issues it reports; export is blocked until QA passes.

### Export
- Click **Export**. You get a timestamped folder under the project’s `exports/` with:
  - `spritesheet.png`
  - `atlas.json`
  - `animations.json`
  - `preview.gif`
  - `export_manifest.json` (includes workflow profile and lineage)

---

## 4. Dependencies (for real ComfyUI/PhotoMaker/ToonCrafter runs)

- The **default** backend can run in a **debug/procedural** mode so you can try the flow without ComfyUI.
- For full AI runs (PhotoMaker, ToonCrafter, etc.), you need ComfyUI and the right nodes/models. Set the project’s **backend mode** and configure the required env vars (see server/code for `SPRITE_WORKBENCH_*` and dependency health).
- **GET /api/ai-workflow/health** shows whether the AI stack is ready.

---

## 5. Legacy projects

- Projects created before the pivot (with rig, part manifest, SkelForm, etc.) open in **read-only legacy mode**.
- The stepper shows legacy step names (e.g. “Rig Layout”, “Part Manifest”) and mutating controls are disabled. Create a **new project** to use the full ai_sideview_v1 workflow.
