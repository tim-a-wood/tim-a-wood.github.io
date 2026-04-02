# Design review memo — Ashen Hollow Art Bible v0.2

**Agent:** Design  
**Date:** 2026-04-02  
**Input:** `artifacts/ashen-hollow-art-bible-v0.2.md` (and bundled `artifacts/art-bible/` samples)  
**Trigger:** Founder request — Design review of art bible  
**Scope note:** Design **does not own** in-game art direction (Creative owns the art bible). This review covers **jurisdictional clarity**, **consistency with `STYLE_GUIDE.md` governance**, and **risks when the same humans implement both toolchain UI and game-facing UI**.

---

## Verdict: **Approve with conditions**

---

## 1. Token compliance (toolchain lens)

**Assessment:** The art bible uses **named game tokens** (`AH-*`) and raw hex for **world art**. That is correct for sprites, backgrounds, and in-game HUD as specified.

**Conditions:**

- **Do not** map `AH-*` hex values into **editor chrome**, **sprite workbench shell**, **OS dashboard**, or other **product UI** CSS. Toolchain surfaces stay on **`STYLE_GUIDE.md`** variables (`--accent`, `--bg`, etc.). The bible already states this in **§6.1**; treat that as a hard gate for code review.
- If a **room editor** (or similar) shows a **live preview** of the game world on canvas, the **canvas content** may follow the art bible for fidelity; **panels, rails, and inspectors** around it still follow the design system. If preview and chrome ever share one stylesheet, split by scope (e.g. prefixed game-preview root) so tokens do not leak.

**N/A:** Pixel art on canvas remains subject to `image-rendering: pixelated` per existing tooling rules; the bible does not contradict that.

---

## 2. Accessibility compliance (game UI implications)

**Assessment:** Readability rules (value hierarchy, separation, “never rely on color alone” for interactables) **align** with Design’s principle that **state must not be color-only** (WCAG 1.4.1).

**Conditions:**

- When **in-game HUD / map / menus** are implemented from this bible, **pair** accent colors (`AH-GLINT-9`, `AH-ROYAL-11`, etc.) with **shape, icon, label, motion, or layout** — same discipline as toolchain UI, even though the palette differs.
- Run **contrast checks** on any **UI text** rendered over game palettes (not just sprites). WCAG 2.x (and eventually APCA) apply to **readable UI copy**; atmospheric darkness in the world does not exempt HUD strings.

---

## 3. Interaction & component spec (toolchain)

**Assessment:** **No change** to `STYLE_GUIDE.md` component specs is **required** solely because of v0.2.

**Optional follow-up (not blocking):** Add a **short “Related documents”** pointer in `STYLE_GUIDE.md` (one paragraph) to the art bible for **in-game / diegetic UI** only — reduces “which doc wins?” questions for new contributors.

---

## 4. PDF / export pipeline

**Assessment:** Markdown → HTML → PDF paths used for **email delivery** use a **light print theme**. That is **outbound documentation**, not product UI. **No conflict** with dark-theme-only toolchain governance.

---

## 5. Risks

| Risk | Mitigation |
|------|------------|
| Contributors paste `AH-*` hex into tool CSS for “consistency” | PR review + lint mindset; §6.1 cited in review checklist |
| In-game UI ships with color-only states | Apply §7 gate + explicit HUD spec from Creative/Design pairing |
| Room editor preview vs chrome confusion | Document preview root vs shell tokens when that UI ships |

---

## 6. Recommendation summary

| Dimension | Result |
|-----------|--------|
| Token compliance (toolchain) | **Approve with conditions** (§6.1 enforced in implementation) |
| Accessibility (game-facing UI) | **Approve with conditions** (paired cues + text contrast) |
| Interaction / STYLE_GUIDE | **Approve** (no mandatory token changes) |
| Overall | **Approve with conditions** |

**Escalation:** If a feature requires **one shared component** to appear **both** in toolchain and in-game with identical styling, that is a **design system governance** decision — escalate to Founder + Creative + Design before shipping.

---

## 7. Next actions

| Owner | Action |
|-------|--------|
| Engineering | Enforce §6.1 in any HUD/map UI PRs; scope room preview CSS if needed |
| Creative | Keep art bible as source of truth for `AH-*`; update if HUD patterns add new UI tokens |
| Design | Optional: `STYLE_GUIDE.md` cross-link to art bible for in-game UI |
| Founder | Explicit lock when v0.2 (or successor) is production-frozen |
