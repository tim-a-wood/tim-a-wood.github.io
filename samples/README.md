# Layout samples

## `room-environment-hooks-sample.json`

Three **intentionally contrasting** `room.environment` rows for hook QA in `index.html`:

| Room | `themeId` | Look (camera BG + starfield tint) | Tags (all different vocabulary) |
|------|-----------|-----------------------------------|--------------------------------|
| **R1** | `cave` | Cold blue void | underground, limestone, dripping, … |
| **R2** | `void` | Wine / magenta cast | zero-g, whisper, purple-haze, … |
| **R3** | `shrine` | Deep violet | incense, gong, ritual, … |

**In-game:** top HUD shows `ENV: {themeId} · …` and changes sharply when you change rooms. **Canonical** `room-layout-data.json` uses **cave / void / sewer** on **R1–R3** with equally distinct tag sets so the main play path doubles as a hook test.
