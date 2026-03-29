# QA Assessment — Sprite Workbench
**Date:** 2026-03-28 | **Agent:** QA | **Scope:** Full toolchain quality assessment

---

## Overall Rating: YELLOW

The Sprite Workbench production pipeline has strong output-level gates and a well-defined production contract, but the automated test layer has a critical gap: there are zero automated tests for the workbench modules themselves. Known P1 security findings from the cybersecurity audit are unresolved and affect the same server process that runs the workbench. Not shippable to external users as-is.

---

## What's Working Well

**Production contract enforcement is real.** The spec hard-blocks export unless all per-frame and per-animation checks pass. The QA report for the live project (ashen-sentinel-9ea9be55, export 20260313T114452Z) confirms 14/14 frames and 2/2 animations at full pass across all 9 checks: transparent background, 256×256 dimensions, pivot tolerance, no clipping, no anatomy defects, no palette drift, loop continuity. This is a functional gate, not theater.

**Export determinism infrastructure exists.** Source asset SHA-256 hashes are recorded in `qa_report.json` at export time. The mechanism to detect whether source assets have changed is in place. The next step — comparing hashes between runs to verify byte-for-byte determinism — is not automated but the data exists to do it.

**Fixture data is present.** `tests/fixtures/sprite_workbench/` contains two named fixture sets (`legacy-layered-character`, `hybrid-mixed-pipeline`) with full layer PNGs, `project.json`, `rig.json`, `palette.json`, and animation template files. This is the right raw material for unit and integration testing. The fixtures are not currently wired to any test runner.

**Module decomposition supports testability.** The ~10,200-line server is decomposed into ~18 named modules (`workbench_export.py`, `workbench_sprite_model_rig.py`, `workbench_rig_parts.py`, etc.). The export module (`workbench_export.py`, 1,224 lines) has pure functions (`check_state`, `aggregate_check_state`, `approved_manual_animation_clips`) that are directly unit-testable with no server dependency.

---

## Deficiencies

### TD-01 — No Automated Tests for Workbench Modules (P1)

**Zero** of the 18 workbench Python modules have a corresponding test file. The `tests/` directory contains unit tests for the room editor and game logic only. The charter's required test pyramid for the sprite workbench — unit tests for palette ops, frame ops, export schema serialization, and canvas accuracy — does not exist.

| Module | Lines | Test file |
|---|---|---|
| `workbench_export.py` | 1,224 | None |
| `workbench_sprite_model_rig.py` | — | None |
| `workbench_rig_parts.py` | — | None |
| `workbench_part_split.py` | — | None |
| `workbench_project_io.py` | — | None |
| …13 more | — | None |

**Severity:** P1. Export schema validation, frame check logic, and palette operations are untested. A regression in `workbench_export.py`'s per-frame check logic could silently pass defective frames. The production contract depends entirely on the correctness of this module.

**Fix:** Write Python `unittest` tests for `workbench_export.py` first (highest risk), using the existing fixture data in `tests/fixtures/sprite_workbench/`. Target: `check_state`, `aggregate_check_state`, `run_external_authoring_qa`, and the per-frame pixel checks against known-good and known-bad fixture frames.

---

### TD-02 — No Playwright E2E Tests for Sprite Workbench Workflows (P1)

The acceptance tests (`tests/acceptance_tests.md`) cover `index.html` (the game runtime), not the workbench tool. There are no E2E tests for:
- Full workflow: intake → concept → concept lock → part split → rig → animate → export
- Frame operations: add frame, duplicate, delete, reorder
- Export → spritesheet pixel data matches fixture
- QA gate: a known-bad frame blocks export (negative case)

**Severity:** P1. No automated regression protection for any workbench user workflow. Any refactor of the ~20 app-layer JS files could silently break end-to-end behavior.

---

### TD-03 — Export Determinism Not Verified by Test (P2)

The charter classifies export determinism as a P0 concern. SHA-256 hashes are written into `qa_report.json` at export time, but no test runner loads a fixture, exports, rehashes, and compares. The hashes are records of what happened, not assertions that it will happen identically again.

**Fix:** One pytest function — load fixture state, call export, hash the output JSON, compare to stored hash. This is the charter's exact protocol.

---

### TD-04 — Visual Regression Baseline Missing (P2)

No Playwright snapshot baseline images exist. Canvas rendering accuracy (pixel colors match palette, no bleed) cannot be regression-tested without a fixed viewport + `image-rendering: pixelated` baseline. The fixture data exists; the test infrastructure does not.

---

### SEC-01 — Open P1 Security Findings on Shared Server (Elevated Risk)

The cybersecurity audit (2026-03-28) found three unresolved P1 findings that affect the same Flask server process running the sprite workbench:

- **XSS-01**: Unescaped user strings in `innerHTML` in room-layout-editor.html (3 call sites)
- **RATE-01**: No rate limiting on Gemini API endpoints — billing blowout risk
- **INPUT-01**: No input length cap on Copilot text fields — OWASP LLM04

These do not directly affect the sprite workbench core pipeline today (single-user, local-only), but they block any external user exposure. The QA gate on releasing this server to any audience beyond the founder must remain closed until these are fixed.

---

## Test Coverage Summary

| Area | Coverage | Assessment |
|---|---|---|
| Export gate (per-frame QA checks) | Runtime-enforced, manually validated | Pass — gate works, no automated test |
| Export schema validation | Not tested | Gap |
| Frame operations (add/dup/delete) | Not tested | Gap |
| Palette operations | Not tested | Gap |
| Canvas pixel accuracy | Not tested | Gap |
| Animation preview updates | Not tested | Gap |
| Export determinism | Hash captured, not compared | Gap |
| Rig fitting logic | Not tested | Gap |
| Negative case: bad frame blocks export | Not tested | Gap — highest risk |
| Visual regression baseline | None | Gap |

---

## P0/P1 Bug List

| ID | Severity | Area | Description | Status |
|---|---|---|---|---|
| TD-01 | P1 | Test gap | Zero unit tests for workbench modules | Open |
| TD-02 | P1 | Test gap | No E2E tests for any workbench workflow | Open |
| SEC-RATE-01 | P1 | Security | No rate limiting on AI endpoints | Open |
| SEC-XSS-01 | P1 | Security | XSS in room editor (shared server) | Open |
| SEC-INPUT-01 | P1 | Security | No Copilot input length limit | Open |

No P0 blockers identified. No data loss paths, no corrupted export paths, no API key exposure.

---

## Go / No-Go

**For internal use (solo founder): GREEN** — The workbench produces correct outputs and the export gate is enforced. Active use is safe.

**For any external user exposure: RED** — Three P1 security findings are open on the shared server. The absence of automated tests means regressions in future changes have no safety net.

---

## Recommended Next Sprint

1. Write unit tests for `workbench_export.py` using existing fixtures — highest leverage, ~2 hours
2. Remediate XSS-01, INPUT-01, RATE-01 per cybersecurity agent action list — ~2.5 hours combined
3. Wire `tests/fixtures/sprite_workbench/` to a pytest runner — these fixtures are valuable and currently dormant
4. Add one negative test case: load a fixture with a known defective frame, assert export is blocked
5. Add export determinism test: export → hash → re-export → compare hashes

**Total remediation estimate:** 1–2 focused engineering sessions.
