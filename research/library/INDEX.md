# Research Library — Master Index

> Maintained by the Research Agent. All agents should search this index before starting complex tasks. Use `Ctrl+F` / `grep` on this file to locate relevant prior work.
>
> **Directive for all agents:** Before tackling a complex task, grep this file for relevant keywords. If a finding or report exists, read it first. Do not re-litigate resolved issues — check `/decisions/` as well.

---

## How to Use This Library

1. Search this INDEX for your topic
2. Read the linked document
3. Check the document's `status` — `superseded` docs are archived, use `final` or `draft`
4. If no relevant document exists, ask the Research Agent to investigate

---

## Catalog

### Findings (Codebase Scans)

| Date | Title | File | Summary | Status |
|------|-------|------|---------|--------|
| 2026-04-01 | Initial Codebase Scan — MV Toolchain | [codebase-scan-2026-04-01.md](findings/codebase-scan-2026-04-01.md) | Initial scan of 4 primary source files: 3 P1 issues (undefined CSS var, XSS risk, missing focus-visible), 10 P2 issues (token drift, style violations, tech debt), 6 opportunities | final |

### Technical Assessments

| Date | Title | File | Summary | Status |
|------|-------|------|---------|--------|
| 2026-04-02 | Assurance Copilot — DO-178C / regulated SW market | [assurance-copilot-do178c-market-2026-04-02.md](technical/assurance-copilot-do178c-market-2026-04-02.md) | Market scan: traceability/evidence automation demand, DO-330 tool-qualification context, competitors (e.g. Ketryx, Rapita, VectorCAST), wedges and risks vs MV core strategy | final |
| 2026-04-03 | Sprite Workbench architecture visualization — cross-team plan | [../../docs/sprite-workbench-architecture-visualization-plan.md](../../docs/sprite-workbench-architecture-visualization-plan.md) | Scoped repo slice; **Agent OS `sprite-arch` dashboard** for three views; `STYLE_GUIDE.md` UI rules; deterministic extractors (HTML script order, Python ast, optional Acorn); OSS tool matrix; CI + AI inspector guardrails; phased delivery | draft |
| 2026-04-03 | Sprite Workbench arch viz — master program plan | [../../docs/sprite-workbench-architecture-visualization-master-plan.md](../../docs/sprite-workbench-architecture-visualization-master-plan.md) | End-to-end milestones (M0 design lock … M7 AI), workstreams, SC-1–SC-8 success criteria, user journeys, risk mitigations; links HI-FI mockup | draft |
| 2026-04-03 | Agent OS Workbench architecture dashboard — HI-FI mockup | [../../docs/mockups/agent-os-sprite-arch-dashboard-mockup.html](../../docs/mockups/agent-os-sprite-arch-dashboard-mockup.html) | Static HTML: shell, nav, KPI cards, Structure/Relationship/Change tabs, SVG graph + legend, inspector + AI CTA; tokens `--os-control`, mode-pill pattern, no `transition: all` | draft |
| 2026-04-03 | Pixel art quality standards — production gate | [../../docs/pixel-art-quality-standards.md](../../docs/pixel-art-quality-standards.md) | Animation-owned checklist: `AH-*` palette, silhouette + animation bar, anti-alias/transparency policy, lossless export; art bible v0.2 + charter cross-refs | final |

### Competitive Analysis

| Date | Title | File | Summary | Status |
|------|-------|------|---------|--------|
| — | *No competitive analysis yet* | — | — | — |

### Reports

| Date | Title | File | Summary | Status |
|------|-------|------|---------|--------|
| 2026-04-01 | Passive income market scan (itch.io assets, education, platforms) | [passive-income-market-scan-2026-04-01.md](findings/passive-income-market-scan-2026-04-01.md) | Market + platform economics for first passive-income experiments; option A/B signal strength; cites official fee docs and creator-disclosed itch revenue examples | final |

---

## Tags Reference

Common tags used across library documents:
- `css` `html` `javascript` — language/technology
- `style-guide` `design-system` — design rules
- `room-editor` `sprite-workbench` — tool areas
- `bug` `tech-debt` `opportunity` `risk` — finding types
- `P1` `P2` `P3` — severity
- `accessibility` `performance` `security` — quality dimensions
- `competitive` `market` `ai` — external research

---

*Last updated: 2026-04-03 — Sprite workbench arch viz: master plan + HI-FI mockup indexed*
