# Brainstorming summary — picking the right “play” technology for the toolchain

**Date:** 2026-03-29 · **Rewritten:** plain-language reporting directive (goals, milestones, risks, issues, blockers first)

---

## At a glance (read this first)

**Goals we’re protecting**

- Solo and non-technical creators can build a metroidvania-style game with AI help, without getting lost in expert tooling.
- The workbench stays in the browser; “Play” should feel like part of one product, not a separate universe.
- We ship a playable dark-fantasy exploration game that matches our pillars: good movement, combat, bosses, maze-like maps, meaningful rewards.

**Milestones this ties to**

- **Now:** Prove the loop — editors → export → playable preview — without forcing users to install a heavy game studio.
- **Later:** If we promise “ship on PC/console/store,” the answer may change; this brainstorm separates “browser-first” from “ship anywhere.”

**Risks if we choose wrong**

- **Switch too early:** We split attention across two products (browser tools + a big external engine) and slow everyone down, including AI-assisted workflows tied to our current stack.
- **Stay too long on the wrong stack:** We hit a ceiling on polish, performance, or content scale and pay for a painful migration later.
- **Confusing “Play”:** Users don’t know whether the game opens in the tab, downloads, or launches something else — trust drops.

**Issues on the table**

- We’re already running the prototype in the browser with one technology; the question is whether that remains the right default as scope grows.
- “Best engine” depends on whether our promise is **instant play in the browser** or **ship a standalone/desktop/console build** as the main story.

**Blockers to a final call**

- We haven’t locked **browser-first preview** vs **multi-platform ship** as the primary customer promise.
- We haven’t run a small, timed comparison (same slice of game) on the serious alternatives — evidence beats debate.

**Decisions needed soon**

- Founder / product: one clear line on **where “Play” must work first** (browser only vs browser + download vs store-first).
- Whether to run a **short spike** before decision mode, and who owns it.

---

## Why this topic matters (vision, in plain terms)

We’re building an **AI-enabled** toolchain so people without a engineering background can **author** games: guided flows, plain language, AI suggests and the human **approves** — no silent changes.

The **game** is a dark-fantasy metroidvania: exploration, backtracking, abilities that open new paths, strong movement and combat, memorable bosses, and loot that matters.

Today the **tools** live on the web, and the **playable game** also runs in the browser using tech we already chose. Exported layout data feeds that game. The open question is: **keep that path**, or **move (or split)** where the “real” game runs — for example a mainstream game editor with a web preview — without breaking the solo-creator story.

---

## Choices we brainstormed (five paths)

### A — Stay browser-first with what we use today

**Idea:** Keep one family of technology for tools and runtime; ship updates like a normal web app.

**Upside:** Fast iteration; fits “everything in the browser”; keeps AI and contributors working in one familiar codebase.

**What we’re betting on:** The browser can carry the game as fights, bosses, and polish ramp up — or we’re willing to invest in custom work if we hit limits.

### B — Use a major studio-style engine (example: Unity), web only as a preview

**Idea:** The “real” game lives in a full game editor; browser shows a preview build when needed.

**Upside:** Well-worn path to desktop/console, huge learning material, strong artist tooling.

**What we’re betting on:** Preview-in-browser stays good enough for our users, and we don’t drown non-technical creators in installs, accounts, and build steps.

### C — Use a strong 2D-first engine (example: Godot)

**Idea:** Favor an engine built for 2D; still consider web output for preview.

**Upside:** Friendly for 2D metroidvania work; clear licensing story; approachable scripting.

**What we’re betting on:** Web export and our release rhythm still feel like **one product** with the workbench, and our exported data plugs in cleanly.

### D — Hybrid

**Idea:** Tools stay in the browser; “Play” sometimes opens a heavier build (web preview or a small desktop launcher).

**Upside:** Match each piece to its strength.

**What we’re betting on:** We can keep **one simple story** for users (“press Play and you know what happens”) while operating two pipelines behind the scenes.

### E — Lighter browser tech (replace our current runtime layer only)

**Idea:** If our current stack feels heavy or limiting, swap for a slimmer browser graphics layer — not necessarily jump to Unity/Godot.

**Upside:** More control, possibly smaller surface area.

**What we’re betting on:** A rewrite pays for itself in schedule and risk — otherwise we’re churning.

---

## Stress test — where each path is weakest

| Path | Main weak bet | Who flagged it |
|------|----------------|----------------|
| A (stay browser + current stack) | Browser and our current physics style may feel tight as combat and boss polish grow. | Engineering |
| B (big studio engine) | Non-technical solo flow + AI story may clash with editor/install/build friction; preview quality varies. | Product |
| C (2D-first engine) | Web export + “always fresh deploy” may not match how fast we ship the workbench today. | Engineering |
| D (hybrid) | Two pipelines can confuse users and operations unless “Play” is crystal clear. | Product |
| E (lighter browser layer) | Easy to underestimate cost of rebuilding what we already have. | QA |

---

## Synthesis (brainstorm — not a binding decision)

- **Best match for today’s vision** (browser workbench, web game, AI-friendly single repo): **stay on A**, and only consider **E** if we hit a concrete wall — not an automatic jump to B or C.
- **Worth exploring B or C** if we **change the north star** toward store-first or maximum artist-studio depth — ideally under **D** so the workbench **stays web** and non-technical creators aren’t forced into expert workflows day one.

The product question to settle: **Must “Play” be instant in the tab forever, or can it become a heavier preview or download as the game grows?**

---

## Next steps

- [ ] Move to **decision mode** when you want one recommended path and explicit “what would change our mind.”
- [ ] **Time-box a spike:** same small vertical slice through one alternative preview path vs current — only if we want data before deciding.
- [x] Founder direction: **browser-first preview** vs **ship anywhere** — partial input; lock when ready.

---

**Recommendation (orchestrator):** Treat **stay browser-first (A)** as the default until a **short, owned spike** shows a specific gap that B or C fixes better — or until the founder **locks** the customer promise on preview vs ship.

**Risks:** Switching engines too soon fragments how we build; “everyone uses Unity” can **hurt** non-technical solo positioning; ignoring B/C entirely may **cap** later if we pivot to console/desktop as revenue.

**Confidence:** **Medium** on direction; **lower** on web-preview quality for B/C until we try a slice.

**Founder approval needed:** **Yes** before adopting B or C as the **primary** runtime, or before committing to a **hybrid (D)** that users will feel.

**Next actions:** (1) One-line product lock: browser-first vs multi-platform promise. (2) One-page comparison: deploy, ease of solo use, AI workflow fit, cost/licensing — minimal jargon, decision-oriented. (3) Optional spike: same slice, timed.

---

*Brainstorm only — use a decision brief when you want a binding engine choice.*
