# Brainstorming Summary — Game engine fit (dashboard / runtime)

**Date:** 2026-03-29  
**Topic:** Whether Phaser remains the best runtime fit for a metroidvania in the dashboard versus Unity, Godot, or other stacks—aligned with an AI-enabled product that lowers technical barriers for solo, non-technical creators.  
**Specialists involved:** Chief Engineer (architecture / runtime), Marketing + Product (ICP), QA (testability)—simulated perspectives  
**Mode:** brainstorm  

---

## Vision anchor

- **Product:** Browser toolchain (sprite workbench, room editor, world flow) with plain-language UX and AI that **proposes** structured data users **approve**—no silent mutation.  
- **Game:** Dark-fantasy metroidvania pillars (combat, movement, bosses, maze-like maps, meaningful loot); **PWA / web** in the plan.  
- **Today:** Game in **index.html + Phaser 3**; editors export **deterministic JSON** for the runtime.

**Two questions:** (1) authoring surface (already web), (2) playable runtime (in-browser preview vs download vs store).

---

## Options generated

### Option 1: Stay on Phaser (web-first runtime)

- **Source:** Chief Engineer + Product  
- **Core idea:** Web runtime with Phaser 3; same JS ecosystem as tools; GitHub Pages–style deploy.  
- **Best case:** Fast iteration, agent-friendly repo, no separate engine install for browser-only creators; thin JSON → runtime.  
- **Weak assumption:** Browser performance and long-term combat/boss/polish complexity stay manageable.

### Option 2: Unity (WebGL + desktop)

- **Source:** Chief Engineer + Marketing  
- **Core idea:** Unity as primary runtime; web via WebGL for preview.  
- **Best case:** Strong desktop/console path; huge ecosystem; visual tooling.  
- **Weak assumption:** WebGL + C# + editor complexity still fits non-technical solo + AI story.

### Option 3: Godot (2D-first, multi-export)

- **Source:** Chief Engineer  
- **Core idea:** Godot 4 for 2D; evaluate HTML5 export for browser.  
- **Best case:** Strong 2D workflow; license clarity; approachable GDScript.  
- **Weak assumption:** Web export + deploy rhythm matches PWA cadence; JSON pipeline maps cleanly.

### Option 4: Hybrid — web shell + engine build

- **Source:** Product + QA  
- **Core idea:** Dashboard stays web; Play opens WebGL or desktop wrapper.  
- **Best case:** Browser UX + heavier engine where it wins.  
- **Weak assumption:** Two pipelines stay in sync without confusing users.

### Option 5: Lighter web (PixiJS, Kaboom, custom canvas)

- **Source:** Chief Engineer  
- **Core idea:** Thinner 2D if Phaser abstractions limit you.  
- **Best case:** Control and smaller surface.  
- **Weak assumption:** Rewrite is worth schedule/risk vs Phaser.

---

## Cross-specialist stress test

| Option | Weakest assumption | Raised by |
|--------|-------------------|-----------|
| Phaser | Browser + Arcade physics scale to combat/boss polish. | Chief Engineer |
| Unity | Solo non-dev + AI not blocked by editor/C#/build; WebGL good enough for preview. | Product |
| Godot | Web export + CI matches workbench product feel. | Chief Engineer |
| Hybrid | One clear “Play” story for users with two runtimes. | Product |
| Lighter web | Benefit justifies rewrite. | QA |

---

## Synthesis

- **Aligned with vision today:** Option 1 (Phaser), then Option 5 if Phaser limits you—not a default jump to Unity/Godot.  
- **Explore 2/3 if north star shifts** to store-first or maximum artist tooling—prefer Option 4 so workbench stays web.

Open product question: must **Play** stay **instant in-tab**, or can it be heavier WebGL / download as content grows?

---

## Next step

- [ ] Take to **decision mode** for a single recommended path.  
- [ ] **Spike** same JSON slice in Godot vs WebGL Unity vs Phaser.  
- [x] Founder weighs **browser-first preview** vs **ship anywhere**.

---

**Recommendation:** Keep **Phaser as default** for in-dashboard / PWA runtime until a short **Chief Engineer spike** proves a gap Unity/Godot closes better—or founder locks preview vs ship target.  

**Risks:** Early engine switch fragments the AI-friendly monolith; “Unity = standard” can hurt the non-technical story; ignoring native engines may cap later console/desktop polish.  

**Confidence:** Medium on product alignment; Low–Medium on WebGL/Godot-web without measured spikes.  

**Founder approval needed:** Yes before Unity/Godot as **primary** runtime or dual-pipeline hybrid.  

**Next actions:** (1) Founder/PO: lock browser-first vs multi-platform promise. (2) Chief Engineer: one-page evaluation matrix. (3) Optional time-boxed spike on one vertical slice.

---

*Orchestrator brainstorm — use decision brief for a binding engine choice.*
