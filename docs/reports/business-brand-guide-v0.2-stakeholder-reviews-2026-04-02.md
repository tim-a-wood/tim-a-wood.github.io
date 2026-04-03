# Business Brand Guide v0.2 — specialist stakeholder reviews

**Date:** 2026-04-02  
**Source:** `docs/mv-business-brand-guide-pamphlet.html` (updated to v0.2.1 in repo)  
**Purpose:** Record Strategy, Marketing, Design, Engineering, and Game Director sign-offs for section 1.3 of the matrix. Founder column and §10.1 open questions remain for v0.3 lock.

---

## Marketing

**Result:** Approve (already recorded: no copy edits required).

**Notes:** JTBD, voice guardrails, channel priority, and anti-personas align with charter. Competitive frame matches current positioning. No change to elevator copy requested.

---

## Strategy

**Result:** Approve — strategic foundation, portfolio framing, and messaging architecture.

**Notes:**

- North star, flywheel, and web-first rationale match `prompts/project_plan.md` and competitive window framing.
- “Avoid implying a shipped suite beyond what exists” (§3.2) is the right hedge; keep in decks.
- §5.3 competitive table is directionally accurate; refresh when a funded integrated AI toolchain entrant appears (existing Strategy monitor).

---

## Design

**Result:** Approve with one operational follow-up (not blocking this document).

**Notes:**

- Token summary, typography, spacing/radius/motion rules, and entity colors match `STYLE_GUIDE.md` intent. Hex literals here are acceptable for print/PDF reference; product UI stays `var(--*)`.
- Game vs Workbench boundary matches art-bible vs toolchain split.
- **Follow-up:** `research-status.json` still tracks legacy off-token marketing/splash CSS in the sprite workbench shell; that is implementation debt, not a brand-guide text change.

---

## Engineering

**Result:** Approve — messaging and claims discipline vs shipped behavior.

**Notes:**

- Human-in-the-loop Copilot description matches Environment / layout copilot flows (propose → review → apply).
- “Web-native / shareable” is accurate; PWA ships without service worker during rapid iteration—do not claim offline-first until that changes.
- No public copy in the guide asserts room file versioning or features that are not shipped; keep §7.1 discipline on future export/versioning claims.

---

## Game Director (Game / LD)

**Result:** Approve — strategic foundation row from a game perspective, portfolio naming for *Ashen Hollow*, game IP vs toolchain.

**Notes:**

- Proof-by-production language is directional: the game is in development; public posts should stay honest (“in development,” “dogfooding”) per voice rules.
- Entity-color and art-bible references are editor/game-boundary correct. Level Design may use the same matrix column for operational detail; no conflict found.

---

## Founder (pending)

Complete the Founder column in section 1.3 and resolve **§10.1** open questions (legal/display names, logo, pricing narrative, long-form home) before treating **v0.3** as locked for external PDF.
