# Layout samples

## `room-environment-hooks-sample.json`

Minimal two-room layout used to **manually verify** that `room.environment` is read by the game:

1. Open `index.html` with this file as the active layout (e.g. import via editor **Advanced JSON**, or replace `room-layout-data.json` temporarily, or pass a hash payload if you use that flow).
2. **HUD** — Top center should show a line like `ENV: cave · sample, hook-test` in **R1**, changing when you move to **R2** (e.g. `ENV: ruins · …`).
3. **Background** — `cameras.main` tint shifts slightly per `themeId` (`cave`, `ruins`, `forest`, …).

Canonical data for day-to-day work also includes `environment` on **R1–R3** in `room-layout-data.json` so the hooks are visible without swapping files.
