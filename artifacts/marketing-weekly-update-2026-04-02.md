# Marketing — Tuesday weekly update

**Week of:** 2026-04-02  
**Audience:** Founder / internal (feeds orchestrator digest and `marketing-status.json`)

---

## Goals (this phase)

Grow **trust and recognition** with technically savvy indie devs and metroidvania builders. We are **pre-revenue**; the job is **audience and credibility**, not conversion. Lead with **visible craft** and **human-directed AI** positioning (see `agents/marketing/charter.md`).

---

## What moved in the repo (public / near-public narrative)

Recent `main` history (high level, marketing-relevant):

- **Business brand guide** expanded to **v0.2** (stakeholder-aligned messaging, channel discipline, design-token summary, game-vs-tool boundary). Artifacts: `artifacts/MV-Business-Brand-Guide-v0.2-2026-04-02.pdf` (and v0.1 PDF retained). Source pamphlet: `docs/mv-business-brand-guide-pamphlet.html`.
- **Ashen Hollow art bible v0.2** — markdown + large PDF in `artifacts/`, mood concepts and swatch tests; Design review memo in `docs/reports/` (approve-with-conditions).
- **Agent OS** — continued dashboard UX (product column, filters, workflow affordances); **standing directives** updated (truthfulness / evidence; brainstorm carve-out).
- **Strategy** — assurance-copilot “other income” path closed with a logged decision; `strategy-status.json` repair.

*Game/runtime:* no single headline “player-facing launch” this week; toolchain + brand + creative governance dominated the signal.

---

## Links (verified)

| Asset | Location |
|--------|-----------|
| GitHub remote (authoritative) | https://github.com/tim-a-wood/tim-a-wood.github.io |
| Live PWA (README cache-bust; bump when you deploy) | https://tim-a-wood.github.io/?v=activity6dungeon5 |
| Business brand pamphlet (HTML) | `docs/mv-business-brand-guide-pamphlet.html` |
| Brand guide PDF v0.2 | `artifacts/MV-Business-Brand-Guide-v0.2-2026-04-02.pdf` |
| Art bible v0.2 (PDF) | `artifacts/ashen-hollow-art-bible-v0.2-2026-04-02.pdf` |
| Art bible v0.2 (markdown) | `artifacts/ashen-hollow-art-bible-v0.2.md` |
| Guardrail / agent audit (internal reference) | `docs/reports/agent-guardrail-enforcement-audit-2026-04-02.md` |

**Not in repo:** a dedicated **itch.io project URL** for MV / Ashen Hollow was not found in scanned docs; add when the page exists so future updates can link it.

---

## Engagement (X, devlog, impressions)

**Insufficient evidence for this cycle.** No analytics export, API pull, or founder-supplied screenshot was attached. Next Tuesday’s update should either (a) paste **manual counts** (views, replies, follows) or (b) point to **Analytics** dashboard numbers once that pipeline is wired — without that, we should not infer performance.

---

## Competitor and market signal (light touch)

**Tiled (mapeditor.org)** — active release cadence in March 2026:

- **1.12** (2026-03-13): major workflow upgrade — rewritten Properties view, list-valued custom properties, oblique map orientation, layer blending modes, capsule object shapes, scripting API extensions, and more.  
  https://www.mapeditor.org/2026/03/13/tiled-1-12-released.html  
- **1.12.1** (2026-03-25): patch (notably macOS property-type picker fix, Properties view flicker).  
  https://www.mapeditor.org/2026/03/25/tiled-1-12-1-released.html  
- **Google Summer of Code 2026** participation announced (community pipeline / contributors).  
  https://www.mapeditor.org/2026/02/26/google-summer-of-code-2026.html  

**Implication for MV:** Tiled remains the **default mental model** for 2D level editing; our contrast stays **metroidvania-shaped workflow + integrated sprite/room pipeline + AI suggests / human approves** — not “more tile properties.”

**LDtk** — official release notes hub (not fully reviewed this session): https://ldtk.io/release-notes/  
**Action:** schedule a proper **`competitor-monitor` run** (charter: quarterly or on new entrant) to log LDtk + any **AI level-design** entrants in `marketing-status.json` / research library.

---

## Risks and blockers

- **AI messaging** priority remains **needs-review** / **high risk** in `marketing-status.json` — community skepticism of AI slop; keep “suggests / you decide” language enforced on anything public.
- **No engagement metrics** — cannot validate whether build-in-public is working; risk of flying blind until at least one channel reports numbers.

---

## Next week (proposed focus)

1. **Founder pass on brand guide v0.2** — close or revise per opportunity `marketing-o6` (review matrix, lock external PDF if needed).
2. **One external-facing artifact** — short devlog or X post tying **tool progress + art direction** (even a single screenshot or GIF beats silence), using only **accurate** capability claims.
3. **Competitor-monitor** — capture LDtk + AI level-tool headlines in one structured note (even half a page) so Strategy and Marketing stay aligned.
4. **Tuesday 2026-04-09** — ship the next `artifacts/marketing-weekly-update-2026-04-09.md` with **engagement numbers** if available.

---

*Suppression rule (charter): skip a week only when there is no material change; this week had substantial brand/creative/agent-os movement, so this update is published.*
