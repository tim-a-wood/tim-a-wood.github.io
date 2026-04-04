# Pixel art quality standards (production gate)

**Owner:** Animation agent  
**Status:** Active as of 2026-04-03  
**Scope:** All raster sprites and sprite sheets intended for the Ashen Hollow game (player, enemies, effects, props), whether hand-drawn or AI-assisted.

---

## Relationship to other documents

| Document | Role |
|----------|------|
| [`artifacts/ashen-hollow-art-bible-v0.2.md`](../artifacts/ashen-hollow-art-bible-v0.2.md) | **Foundational visual contract** — master palette (`AH-*` tokens), silhouette differentiation, lighting, materials, biome grammar, and the bible’s §7 production quality gate. |
| [`agents/animation/charter.md`](../agents/animation/charter.md) | Domain authority for animation theory, export discipline, and AI workflow rules (e.g. no AI sprites in production without human pixel pass). |
| [`STYLE_GUIDE.md`](../STYLE_GUIDE.md) | **Toolchain UI only** — editor chrome, dashboards, workbench panels. In-game pixel art follows the art bible, not product cyan tokens. |

If guidance conflicts: **art bible wins for world-facing pixels**; **STYLE_GUIDE wins for tool UI**.

---

## 1. Palette rules

### 1.1 Token compliance

- Production sprites must use **only** colors that map to approved **`AH-*` tokens** from the art bible §2 (core palette, usage limits, usage matrix).
- The art bible **hard ban** applies: no untracked one-off hexes in production sprites. Every opaque pixel must be attributable to the locked palette (or an explicitly documented extension approved by Creative and logged for the asset).
- **Accent budget** and **pairing rules** from the bible §2.3–2.4 apply per entity and per biome assignment.

### 1.2 Pixel-craft discipline (extends the bible)

- **Material ramps:** Build shading as **3–6 steps per material** (value-ordered), with **hue shift** in shadows (cooler) and highlights (warmer) — avoid straight luminance-only ramps (flat “mud”).
- **No color contamination:** Do not introduce near-duplicate browns/grays; reuse an existing ramp color when in doubt.
- **Character palette cap (recommended default):** **≤16 opaque colors per character** (including outline), unless a spec explicitly approves a higher count for a hero or boss asset. Environment tiles may follow bible percentage rules instead of this cap.
- **Transparency:** Index transparency is allowed where the format supports it; **partial opacity is not** (see §3).

### 1.3 Dithering

- **Characters and hero props:** Prefer **no dithering** when it competes with silhouette or animation clarity.
- **Environment / large surfaces:** Ordered or hand-placed dithering is allowed when consistent with biome grammar and readability.
- **AI-generated sources:** Quantization and cleanup must **not** leave stray intermediate tones outside the approved palette.

---

## 2. Silhouette requirements

### 2.1 Art bible baseline

- Follow art bible **§3 Silhouette differentiation rules** for class identity (player, enemy archetypes, bosses, environment reads) and **§6** separation (player vs hazard vs interactable).
- **Black-fill test:** At target display scale, the entity must remain **class-identifiable** with interior filled black against a mid-gray background (bosses: bible §3.3 minimum read points).

### 2.2 Animation-specific bar

- **Motion clarity over frame count:** Each frame must earn its place at the clip’s target FPS (often **6–12 fps** for gameplay sprites). Silhouette changes between frames must support **weight, anticipation, and contact** — not noise.
- **Limbs and weapons:** No ambiguous merges across frames; use outline weight, separation gaps, or single-pixel offsets as needed so hands, feet, and weapon edges **read at 1×**.
- **Secondary motion:** Capes, cloth, tails may trail the root motion by **1–2 frames**; they must not obscure the primary silhouette read in combat-critical poses.

### 2.3 Scale checks

- Evaluate at **1×**, **0.75×**, and **0.5×** (matches art bible read-check scale). If the silhouette fails at the smallest scale used in-game, revise before ship.

---

## 3. Anti-aliasing policy

### 3.1 Definition of done

- **No soft edges in asset data:** Every pixel is **fully opaque** (palette color) or **fully transparent**. No fractional alpha, no “gray fringe” anti-aliasing baked into the sprite.
- **Lossless delivery:** PNG or lossless WebP for production sheets — **never** JPEG or lossy WebP for sprite pixels.

### 3.2 Rendering

- Any preview or in-game draw path for these assets must use **`image-rendering: pixelated`** (or engine-equivalent nearest-neighbor) so the display does not introduce interpolation artifacts.

### 3.3 AI-assisted and imported sources

- Downscale, trace, or quantize from AI or photo reference **only** through a step that snaps to the indexed palette and **removes** anti-aliased rims.
- A **transparency audit** is required before ship: zoom to **400–800%** and verify edges are crisp palette steps, not rgba blends.

---

## 4. Lighting and shading (short gate)

- **Default key light** and material response must match art bible **§4** unless a biome override is documented for that asset.
- **Pillow shading is a reject:** Highlights must follow a **consistent light direction**, not a radial “blob” from the viewer.

---

## 5. Pass / fail checklist (spritesheet audit)

Use this list for hand-off, review, and `spritesheet-audit` outcomes.

| # | Check | Fail if |
|---|--------|--------|
| P1 | Palette | Any opaque pixel not mapped to approved `AH-*` (or approved logged extension). |
| P2 | Silhouette | Class or action unclear at mandated scales or black-fill test. |
| P3 | Anti-alias / alpha | Partial transparency, gray fringes, or lossy compression artifacts. |
| P4 | Animation | Merge artifacts, unreadable contacts, or clutter that breaks motion read. |
| P5 | Lighting | Conflicting light direction or pillow shading on primary forms. |
| P6 | Bible gate | Any art bible §7 production check failed for this asset type. |

**Any single fail = not production-ready** until corrected.

---

## 6. AI-assisted production reminder

- AI output is **reference or rough** until a human performs **palette snap, edge cleanup, and frame consistency** passes per [`agents/animation/charter.md`](../agents/animation/charter.md).
- Prompting and model choice remain separate from this gate: **this document defines whether finished pixels are allowed in the build.**

---

## Revision

- **v1.0** — 2026-04-03: Initial publication (palette, silhouette, anti-aliasing policy) aligned with art bible v0.2.
