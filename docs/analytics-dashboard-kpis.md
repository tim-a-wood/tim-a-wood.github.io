# Analytics dashboard KPIs (Agent OS)

**Source of truth:** `tools/2d-sprite-and-animation/projects-data/_usage_ledger.json` (Sprite Workbench server appends on paid API usage). The Agent OS supervisor reads the same path from disk when serving `GET /api/dashboard-data` → `usage_charts` and `usage_summary` (legacy `projects-data/_usage_ledger.json` at repo root is still read if the canonical file is absent).

## v1 internal KPIs (pre-launch)

| KPI | Definition | Denominator / window |
|-----|------------|----------------------|
| **8-wk API calls** | Sum of ledger rows in the rolling 8 ISO weeks (UTC), by week for the area chart | 8 weeks ending current week |
| **Provider mix** | % of window calls by bucket: Pixel Lab (`provider=pixellab`), Gemini (`provider=gemini`), Room AI (endpoint matches room/layout/copilot/environment), Other | Rows in the same 8-week window |
| **Ledger outcomes** | % of window calls with `status=success`, `error`, or other | Rows in the same 8-week window; center label shows **n** |
| **Ledger rows (all-time)** | `entry_count` | All rows in file (subject to server retention limit) |
| **Est. cost (ledger)** | Sum of `usage_cost_usd` on entries | All-time in file; Finance owns vendor ground truth |

## Not inferrable from the ledger alone

- **Copilot accept / revise / discard** — requires product events in the Room editor / Copilot UI.
- **Activation, retention, DAU** — require post-launch telemetry and disclosed consent where applicable.

## Changelog

- **2026-03-29:** Initial v1 rollup in `scripts/workbench_persistence.py` (`build_usage_ledger_charts_from_entries`).
