# Workbench wait bars & toasts — root cause (design governance)

## Why `STYLE_GUIDE.md` drifted from the apps

1. **Incomplete spec** — Section 8.8 documented a **single** bottom-corner toast only. It never described **toast stacks**, **wait bars**, or the **activity dock**. Features (room wizard AI, sprite Pixel Lab flows) shipped **without** a guide update, so implementations were the de facto spec.

2. **Evolution without consolidation** — The room sprint UI (`room-wizard-workbench-shell.css`) matured first; the sprite workbench kept **older local CSS** (hex fills, rem sizes, `gap: 10px`). No cross-tool audit tied them back to the guide.

3. **Scoped CSS oversight** — Progress rules were written under `.room-wizard-dock` only. The **activity dock** reused class names but lived **outside** that scope, so styling never applied. This was a **selector bug**, not intentional design.

4. **Agent / human process** — Cursor and repo rules reference the style guide, but **nothing required** updating the guide when adding new feedback components. Drift is expected without an explicit “UI PR updates §8” check.

## Corrective actions (done or ongoing)

- Document **wait bars** and **toast stack** in `STYLE_GUIDE.md` using the room wizard / sprint patterns as canonical.
- Share **progress-track / progress-fill** rules for `.activity-dock` in `room-wizard-workbench-shell.css`.
- Align sprite workbench CSS to the same tokens and motion rules.
- Drop redundant **info toasts** when a wait bar + activity dock already show the same “working” state.

## Ongoing governance

- When adding a new global feedback pattern (banner, blocking loader, etc.), update `STYLE_GUIDE.md` in the same PR or immediately after.
