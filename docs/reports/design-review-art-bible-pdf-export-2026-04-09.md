# Design review memorandum — Art Bible PDF export & email delivery

**Agent:** Design  
**Date:** 2026-04-09  
**Input:** `scripts/send_markdown_pdf_email.py`, `scripts/send_weekly_digest.py` (markdown → HTML → PDF → Resend), `artifacts/ashen-hollow-art-bible-v0.3.md` and bundled `artifacts/art-bible/**`  
**Trigger:** Founder cannot reliably open the art bible PDF from email; prior PDF used a light print theme inconsistent with `STYLE_GUIDE.md`.  
**Related:** `docs/reports/design-review-ashen-hollow-art-bible-v0.2.md` §4 (superseded for this pipeline — see §2 below).

**Scope:** Design owns **toolchain-facing documentation chrome** and **`STYLE_GUIDE.md`**. Creative owns art bible **content**. This memo covers **export fidelity to the design system**, **email/PDF deliverability**, and **founder workflow** — not art direction inside the bible.

---

## Verdict: **Approve with conditions** (visual pipeline) · **Open issue** (attachment delivery)

---

## 1. Visual pipeline — STYLE_GUIDE dark export

**Assessment:** As of commit `ed8fc864`, PDFs produced by `send_markdown_pdf_email.py` use a **`styleguide`** theme: `md_to_html(..., theme="styleguide")` and a print wrapper with `STYLE_GUIDE.md` core tokens (`#050709` background, `#cce8e0` primary text, `#5d7870` muted, `#00e8c8` accent for links, `#07090c`–class surfaces for tables, `Plus Jakarta Sans` / `Bebas Neue` / `DM Mono`, 4px accent strip, `print-color-adjust: exact`, `image-rendering: pixelated` on images). This **aligns** with Design charter: **dark-only** for product-aligned artifacts, **no ad-hoc light “report” theme** for this use case.

**Conditions:**

- Keep **`theme=email`** as the default for **general weekly digest** content unless Founder explicitly chooses dark for that channel (many clients still bias light HTML).
- Any new markdown→PDF entry points should **reuse** `_theme_map("styleguide")` — do not fork a third color system.

**Supersedes:** The v0.2 review memo §4 stated that PDF/email used a **light print theme** and was acceptable as outbound documentation. For **art bible and other founder-facing MV artifacts** where the founder expects **toolchain visual identity**, the **styleguide** path is now the **default** in `send_markdown_pdf_email.py`. Light theme remains valid for **generic** digest mail only.

---

## 2. Email PDF — founder cannot open attachment

**Assessment:** The v0.3 art bible PDF generated locally is on the order of **~18 MB**. Full-resolution concept plates and many embedded PNGs inflate the file. **Outlook** (especially web and mobile), **carrier filters**, and **corporate gateways** often block, strip, or fail to preview oversized PDFs; some clients report a generic error instead of “file too large.” This is a **delivery UX** problem, not proof that the PDF bytes are invalid.

**Evidence to collect (Founder / Support):**

- Exact client (Outlook desktop vs web vs iOS/Android).
- Error string if any (download fails vs open fails vs blank preview).
- Whether saving the attachment to disk and opening in **Preview** (macOS) or **Adobe Reader** works — if yes, the issue is **client attachment handling**, not generation.

**Conditions (product):**

| Priority | Mitigation |
|----------|------------|
| P0 | **Founder must be able to read the bible without fighting email.** Email **cannot** be the only distribution path for an ~18 MB PDF. |
| P1 | Provide a **mailbox-safe** variant or alternate channel (see §5). |
| P2 | Log **attachment size** in the send script stdout and warn when above **10 MB** (Outlook-style soft threshold). |

---

## 3. Accessibility & readability (PDF)

**Assessment:** Dark backgrounds with `print-color-adjust: exact` improve **on-screen PDF** fidelity. **Printed** copies may use more toner; contrast of body text (`#cce8e0` on `#050709`) is acceptable for reading PDFs on displays. Tables use visible borders (`rgba(0,232,200,0.10)`).

**Conditions:**

- If a **print-first** export is required later, Design may specify a **separate print stylesheet** (still token-derived) — out of scope unless Founder requests paper workflow.

---

## 4. Risks

| Risk | Mitigation |
|------|------------|
| Large PDFs fail in email | Alternate delivery + optional “lite” PDF build (§5) |
| Duplicate token definitions drift | Single `_theme_map("styleguide")` in `send_weekly_digest.py` |
| Founder assumes email is source of truth | Memo + status: canonical text remains **`artifacts/ashen-hollow-art-bible-v0.3.md`** in repo |

---

## 5. Recommended delivery strategy (pending Founder choice)

**Option A — Primary: canonical repo + local PDF (current)**

- Open `artifacts/ashen-hollow-art-bible-v0.3.md` in the repo or GitHub **markdown view** (images resolve when paths are bundled).
- Generate PDF **without email** (no Resend keys required):  
  `python3 scripts/send_markdown_pdf_email.py --pdf-only --file artifacts/ashen-hollow-art-bible-v0.3.md`  
  Output: `artifacts/ashen-hollow-art-bible-v0.3-YYYY-MM-DD.pdf` — open in **Preview** or Acrobat from disk.
- To email after review: omit `--pdf-only` and set `RESEND_API_KEY` + `DIGEST_EMAIL_TO` in `.env.local` (expect **WARNING** on stderr if PDF ≥ ~10 MB).

**Option B — “Lite” PDF for email (&lt; ~10 MB)**

- Engineering: optional flag (e.g. `--compress-images` or `--max-image-width 1200`) that rewrites image `src` to downscaled temporaries before Chrome PDF. **Design approves** max width that keeps biome plates readable.

**Option C — Hosted link**

- Founder-approved host (e.g. GitHub **Release** asset, private bucket, or GitHub Pages path) with **one** canonical URL; email body links to it and attaches **lite** PDF or no attachment.

**Recommendation:** **A + B** short term: Founder reads from repo or opens local PDF; next sprint add **B** so email attachment reliably opens in Outlook.

---

## 6. Verdict summary

| Dimension | Result |
|-----------|--------|
| STYLE_GUIDE fidelity (PDF HTML) | **Approve with conditions** (reuse styleguide theme; no light fork for this path) |
| Email attachment reliability | **Open** — treat ~18 MB as high risk for Outlook; implement §5 |
| Art bible content | **Out of scope** — Creative / Game Director |

---

## 7. Next actions

| Owner | Action |
|-------|--------|
| Founder | Confirm Outlook behavior (web vs app); try **Save as** then open locally; choose §5 option **A/B/C** for ongoing |
| Engineering | **`--pdf-only`** and size **WARNING** (≥10 MB) on `send_markdown_pdf_email.py`; implement **`--compress-images`** for mailbox-safe sends |
| Design | This memo is the formal record; update `STYLE_GUIDE.md` cross-link only if Founder wants explicit “export themes” subsection |
| Creative | No change to bible **content** from this memo |

---

**Recommendation:** Adopt **§5 Option A** immediately for reading; prioritize **Option B** so the next emailed PDF opens in your mailbox without workarounds.

**Risks:** Continued reliance on large email attachments will repeat “can’t open” reports across devices.

**Confidence:** **High** on root cause being **size + client limits**; **Medium** until we reproduce on your exact Outlook surface.

**Founder approval needed:** **Yes** — pick **B vs C** (lite PDF vs hosted canonical link) for future automated sends.

**Next actions:** Same as §7 table.
