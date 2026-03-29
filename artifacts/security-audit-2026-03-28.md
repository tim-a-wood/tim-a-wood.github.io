# Security Audit Report — MV Toolchain

**Date:** 2026-03-28 | **Auditor:** Cybersecurity Agent | **Classification:** Founder Eyes Only

---

## Executive Summary

Three P1 findings require action before any external user exposure: an XSS vulnerability in the room editor (unescaped user strings in innerHTML), no rate limiting on AI API endpoints (Gemini cost-blowout risk), and no input length limits on Copilot text fields (token-bombing risk). Two P2 findings (missing CSP, unverified CORS) should follow in the next sprint. Credential hygiene is sound — no secrets in git history, .env.local correctly gitignored.

---

## P1 Findings — Action Required

### XSS-01 · Room Editor — Unescaped Strings in innerHTML

Three call sites in `room-layout-editor.html` insert user-controlled strings directly into `innerHTML` without calling the `escapeHtml()` function that exists elsewhere in the file.

**Affected lines:**
- Line 4118 — `roomSelect.innerHTML` template with `${room.id}` and `${room.name}` unescaped
- Line 4271 — `globalLinkSummary.innerHTML` with `${room.id}` unescaped
- Line 4277 — same, plus `${existingLink.targetRoomId}` unescaped

A room named `<img src=x onerror=alert(document.cookie)>` will execute JavaScript in the user's browser on load. Single-user tool today — but this must be remediated before any multi-user or hosted deployment.

**Fix:** wrap `room.id`, `room.name`, and `existingLink.targetRoomId` at those three sites in the existing `escapeHtml()` call. ~15 minutes of work.

---

### RATE-01 · No Rate Limiting on AI Endpoints

The Flask server (`sprite_workbench_server.py`) has no rate limiting on the Gemini API proxy endpoints (`/api/environment`, Copilot routes). No Flask-Limiter or equivalent was found anywhere in the server configuration.

**Risk:** A runaway client loop or a single adversarial caller can generate an unbounded number of Gemini API calls at the product's expense. For a solo founder, a billing spike event is existential. Risk formula: low probability × catastrophic impact = P1.

**Fix:** Add Flask-Limiter with 20 requests/minute per IP, 100 requests/hour per IP on all AI endpoints. ~1 hour of work.

---

### INPUT-01 · No Description Length Limit on Copilot Inputs

The `adapt_room_template` function in `room_environment_system.py` accepts `user_text` and `instruction` from the request payload with no length validation before forwarding to Gemini. No `MAX_DESCRIPTION_LEN` guard was found in the Copilot input path.

**Risk:** A 100,000-character description inflates token count and API cost on every call. This is an OWASP LLM04 (Model Denial of Service) finding — even unintentional misuse (a paste accident) can generate a large bill.

**Fix:** Add a hard length cap of 2,000 characters on all free-text Copilot inputs before they reach the Gemini call. ~30 minutes of work.

---

## P2 Findings — Next Sprint

### CSP-01 · No Content Security Policy

No `Content-Security-Policy` header or `<meta http-equiv>` tag is present in any HTML file. The Flask server does not set CSP headers on responses.

**Risk:** Without CSP, any XSS vulnerability (see XSS-01) is trivially exploitable — inline scripts execute freely and data exfiltration to arbitrary external endpoints is unrestricted. Elevates to P1 if the tool is publicly hosted.

**Recommended policy:** `default-src 'self'; script-src 'self'; style-src 'self' fonts.googleapis.com; font-src fonts.gstatic.com; connect-src 'self' localhost:*`

---

### CORS-01 · CORS Posture Unverified

No explicit CORS configuration was found in the Flask server. Localhost-only deployment limits immediate exploitability, but any future hosting decision could expose the AI proxy endpoints to cross-origin requests from any origin.

**Action:** Explicitly configure Flask-CORS to allow only the expected frontend origin before any hosted deployment. Do not use `Access-Control-Allow-Origin: *` on endpoints that proxy AI API calls.

---

## Credential Hygiene — PASS

| Check | Result |
|---|---|
| `.env.local` in `.gitignore` | PASS |
| No `.env*` files in git history | PASS |
| API keys absent from client-side JS | PASS |
| API keys absent from `jsonify()` responses | PASS |
| Bearer token not returned to clients | PASS |

Three live credentials are stored in `.env.local` (Gemini, Pixel Lab, Resend). The file is correctly gitignored and has never appeared in git history. No credential leakage paths were found in server response bodies or log output.

**Advisory:** Three high-value credentials share one file. If this machine is compromised, all three services are affected simultaneously. Consider rotating to per-service least-privilege keys and using a secrets manager for any future hosted deployment.

---

## AI Integration — OWASP LLM Top 10

| Rank | Threat | Status | Notes |
|---|---|---|---|
| LLM01 | Prompt Injection | Partial | System prompt is structured JSON; output field not schema-validated |
| LLM02 | Insecure Output Handling | Partial | AI-generated description stored without HTML sanitization |
| LLM04 | Model DoS | P1 | No input length limits — see INPUT-01 |
| LLM06 | Sensitive Data Disclosure | Unassessed | Gemini DPA opt-out status unknown |
| LLM08 | Excessive Agency | PASS | Copilot requires explicit user confirmation before applying |

**DPA-01 — Unassessed:** Room description text containing proprietary game design content is being forwarded to Google's Gemini API. If users' content enters Google's training pipeline, this has legal and privacy implications. Legal agent must confirm Gemini Data Processing Addendum opt-out status before any user content flows to Gemini in a production deployment.

---

## Summary — Prioritised Action List

- [ ] **XSS-01** — Wrap `room.id`, `room.name`, `existingLink.targetRoomId` in `escapeHtml()` at lines 4118, 4271, 4277 in `room-layout-editor.html` *(Engineering, ~15 min)*
- [ ] **INPUT-01** — Add 2,000-char length guard on all Copilot string inputs in `room_environment_system.py` *(Engineering, ~30 min)*
- [ ] **RATE-01** — Add Flask-Limiter: 20 req/min per IP on AI endpoints *(Engineering, ~1 hr)*
- [ ] **CSP-01** — Add CSP meta tag to `room-layout-editor.html` and `index.html` *(Engineering, ~1 hr)*
- [ ] **DPA-01** — Confirm Gemini DPA opt-out status *(Legal agent, before next user data sent to Gemini)*
- [ ] **CORS-01** — Explicitly configure allowed CORS origins before any hosted deployment *(Engineering, pre-deploy)*
