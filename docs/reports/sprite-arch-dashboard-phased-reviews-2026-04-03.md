# Sprite-arch dashboard — phased reviews (2026-04-03)

Synthetic **Design / QA / Research** checkpoints between implementation phases (no separate agent run — criteria applied during build).

---

## Phase A — Extractor + manifest schema (v0.2)

| Lens | Notes |
|------|--------|
| **Design** | Manifest remains JSON-first; new fields (`exports`, `churn_30d`, `js_static_ref`) are optional for older consumers; KPI copy matches behavior. |
| **QA** | `tests/extract_sprite_workbench_arch.test.py` asserts schema `0.2` and presence of `exports` / `churn_30d` on sampled nodes; edge kinds unchanged for core HTML/Python. |
| **Research** | CI drift check must ignore **git-derived** churn fields so shallow clones do not false-fail (`verify_sprite_workbench_arch_manifest.py`). |

---

## Phase B — Dashboard graph + tabs

| Lens | Notes |
|------|--------|
| **Design** | Shared graph above tab panels; filters only affect relationship/change views; structure view hides heuristic `js_static_ref` edges; inspector shows I1 exports and churn. |
| **QA** | List ↔ graph selection sync; vis loaded lazily; regen button shows toast (local extractor workflow). |
| **Research** | CDN choice documented in `decisions/2026-04-03-sprite-arch-dashboard-graph-library.md`; workbench mirrors explain POST for same-origin. |

---

## Phase C — Explain API + CI

| Lens | Notes |
|------|--------|
| **Design** | Explain output is non-authoritative (stated in UI); model returns JSON `{ "explanation": string }`. |
| **QA** | Without `OPENAI_API_KEY`, supervisor returns `503` with clear message; path allowlist blocks arbitrary repo reads. |
| **Research** | Workflow adds `verify_sprite_workbench_arch_manifest.py` after extractor test to catch stale committed manifest. |
