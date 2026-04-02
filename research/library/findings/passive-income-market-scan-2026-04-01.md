---
date: 2026-04-01
title: "Passive income market scan — itch.io assets, education, platforms"
tags:
  - market
  - competitive
  - passive-income
  - itch.io
  - gumroad
  - educational-content
status: final
---

# Passive income market scan (2026-04-01)

## Executive summary

Pixel art and game assets on [itch.io](https://itch.io/game-assets) show **real, documented demand**: public creator write-ups cite **hundreds to low thousands of US dollars per year** from asset sales on the store, and **individual packs** have reached **roughly $8k gross** in at least one cited case—though itch.io does **not** publish per-product sales ranks or revenue, so “top seller” lists are **browsing/discovery signals**, not verified unit sales. **Educational products around AI and game development exist** (courses, suites, prompt-style packs on itch.io and elsewhere), including **level-design–adjacent** training; a **narrow, metroidvania-specific “AI level design” guide** is **not clearly dominant** in public listings, but **differentiation must be proven** with keyword and competitor review before claiming a “gap.” For **platform economics**, **itch.io** uses **open revenue share (seller-chosen 0–100%, default 10%)** plus **payment processor fees** (~2.9% + $0.30); **Gumroad** advertises **10% + $0.50** on direct sales and **30%** on Discover sales, and acts as **merchant of record** from **2025-01-01**. **Lemon Squeezy** and **Paddle** both publish **5% + $0.50** style all-in checkout pricing for merchant-of-record selling; **Stripe Payment Links** remain viable for **simple one-off** sales but **you** handle **tax compliance** unless you add other tooling. **Recommendation for the Orchestrator:** treat **asset packs on itch.io** as the **fastest testable** path if art is truly export-ready; treat **education** as **high leverage but front-loaded** time; run **Finance unit economics** on **$5–$20** price points with **processor + platform** fees modeled explicitly.

---

## 1. Pixel art asset pack market on itch.io

### What we can verify

- **Discovery / popularity signals:** itch.io exposes category pages such as [Top selling game assets](https://itch.io/game-assets/top-sellers), [Top selling tagged Pixel Art](https://itch.io/game-assets/top-sellers/tag-pixel-art), and [Asset Pack + Pixel Art](https://itch.io/game-assets/top-sellers/tag-asset-pack/tag-pixel-art). These reflect **algorithmic/top lists**, not audited sales volumes.
- **Pricing:** List pages and product pages show **wide bands**—many packs sit roughly **$1–$30** with frequent sales; itch.io’s own pricing guide notes **pay-what-you-want** behavior and that **buyers often pay above minimum** ([Pricing — itch.io creators](https://itch.io/docs/creators/pricing)).
- **Creator-reported economics (anecdotal, not averages):**
  - One creator’s **2025 finances** post reports **$820 from itch.io** for the year, from **6 asset packs**, **2 zines**, and **1 major asset update**—i.e. **material but part of a broader freelance practice** ([2025 Finances — Odds & Ents](https://itch.io/blog/1137874/2025-finances)).
  - Third-party/industry discussion has cited **~$8k gross** for a specific pixel pack (**Pixelwood Valley / Gowl**); treat as **single data point**, not a forecast ([itch.io community thread on selling assets](https://itch.io/t/1425337/advice-on-selling-assets-pixel-art) and related devlog references—verify on the creator’s own pages before quoting externally).
- **Review velocity / social proof:** Product pages show ratings and comment activity; **no aggregate public API** for “reviews per week” was used in this scan—**manual spot-checks** on candidate competitors remain necessary.

### Saturation vs. demand

- **Demand:** Strong **category depth** (many packs, repeat buyers, jam/bundle culture on itch.io) supports **ongoing purchases**.
- **Saturation:** **Generic RPG tilesets and character templates** are crowded; **niche themes** (specific biome + consistent style + clear license) still win when **quality and preview materials** are strong.

### Successful launch patterns (qualitative)

- **Devlogs and follower feeds** on itch.io drive repeat purchases ([Interacting with fans](https://itch.io/docs/creators/interact)).
- **Sales and bundles** are first-class ([Sales](https://itch.io/docs/creators/sales), [Bundles](https://itch.io/docs/creators/bundles)).
- **Jam tie-ins** and **seasonal store sales** increase visibility; exact lift is **not** publicly quantified per creator in aggregate.

### Tool developers selling companion content

- **Aseprite** is sold as a **tool** on itch.io ([Aseprite on itch.io](https://dacap.itch.io/aseprite)); **third-party** Aseprite-adjacent plugins/packs exist (e.g. community tools like [Aseprite Advanced Exports](https://coldfox-co.itch.io/aseprite-advanced-exports)).
- **LDtk** appears in collections and workflows; **no strong public signal** in this scan that **Deepnight** sells large standalone “LDtk template packs” as a primary business line the way asset studios do—**companion monetization** for tools more often shows up as **the tool sale itself** plus **community assets**.

### Data gaps (explicit)

- **Per-product unit sales and revenue** for competitors: **not public** on itch.io.
- **2025 “true top 10 revenue”** for pixel packs: **cannot be verified** without private data or creator disclosures.

---

## 2. Educational content — AI-assisted game development

### Does “AI-assisted metroidvania level design” exist as a product?

- **Broad AI + level design** training exists (e.g. vendors advertising [AI for level design guidance](https://completeaitraining.com/lesson/20c-course-ai-for-level-design-guidance_game-developers)—verify curriculum and freshness before partnership or citation).
- **AI + game dev courses** with practical output exist (e.g. [LevelQuest.AI](https://levelquest.ai/), [GamineAI platformer course](https://www.gamineai.com/courses/2d-platformer-game)).
- **Engine-specific** Gumroad-style curricula are common (e.g. [GDQuest Godot material on Gumroad](https://gdquest.gumroad.com/)).
- **Gap claim:** A **tight positioning** (“metroidvania + your toolchain + approval-first AI room authoring”) may be **differentiated**, but this scan **did not** prove search-volume or conversion for that exact positioning—**Marketing** should run **keyword and audience** checks next.

### Formats that appear in-market

- **Low price digital PDFs / zines** on itch.io (adjacent to asset economy).
- **Video or hybrid courses** on dedicated teaching sites and Gumroad-style storefronts.
- **Tooling + prompts** bundled as **addons** (see section 5).

### Distribution platforms

- **itch.io** — strong for **indie-aligned** buyers; good cross-sell with **assets and tools**.
- **Gumroad** — strong **creator landing pages**, **email**, **Discover** (higher fee).
- **Teachable / course platforms** — useful when **cohorts, video hosting, and quizzes** justify setup; higher **fixed operational** attention.
- **YouTube + storefront link** — common **funnel**; not passive at upload time.

### Price ranges (evidence-based, coarse)

- **Small digital guides / packs** often land **~$1–$15** on itch.io (examples exist across tags; exact medians require scraping beyond this scan).
- **Structured courses** often **$15–$100+** depending on depth; **GDQuest** lists illustrate **tiered** hobby vs. pro pricing on Gumroad listings.

---

## 3. Platform economics comparison

### itch.io

- **Open revenue share:** Seller sets **0–100%** to itch.io; **default 10%** ([Payments — itch.io creators](https://itch.io/docs/creators/payments)).
- **Processor fees:** **~2.9% + $0.30** cited for **PayPal** and **Stripe** checkouts through itch.io ([Payments doc](https://itch.io/docs/creators/payments)).
- **Worked example (doc):** At **10%** platform share on **$10**, net to seller after processor fee is **~$8.41** (same page).
- **Merchant of record:** **Choice**—**direct to you** vs. **collected by itch.io (payouts)** with different **tax and liability** splits ([payments mode table](https://itch.io/docs/creators/payments)).
- **Discovery:** Tags, jams, sales, bundles, followers; **no paid ads layer** comparable to large mobile stores.

### Gumroad

- **Fees (official):** **10% + $0.50** per transaction for sales through **your profile or direct links**; **30%** when **new customers** buy via **Gumroad Discover** ([Gumroad Pricing](https://gumroad.com/pricing)).
- **Tax:** From **2025-01-01**, Gumroad states it is **merchant of record** and handles **tax collection/remittance** ([same page](https://gumroad.com/pricing)).

### Lemon Squeezy vs. Paddle (digital goods, small scale)

| Topic | Lemon Squeezy | Paddle |
|--------|----------------|--------|
| **Published headline fee** | **5% + $0.50** per transaction for ecommerce ([Lemon Squeezy Pricing](https://www.lemonsqueezy.com/pricing)) | **5% + $0.50** per checkout transaction ([Paddle Pricing](https://www.paddle.com/pricing)) |
| **Merchant of record** | Yes — tax, filings described as included ([Lemon Squeezy Pricing](https://www.lemonsqueezy.com/pricing)) | Yes — tax/compliance emphasized ([Paddle Pricing](https://www.paddle.com/pricing)) |
| **Under-$10 products** | Notes possible **additional fees** in edge cases ([fees doc linked from pricing](https://docs.lemonsqueezy.com/help/getting-started/fees)) | Site notes **under $10** may need **custom pricing** ([Paddle Pricing](https://www.paddle.com/pricing)) |
| **Strategic note** | Lemon Squeezy **acquired by Stripe**; long-term product shape may evolve—re-check before committing deep integration. | Strong when **SaaS billing depth** and **support** matter; may be **heavier** than needed for a **single PDF**. |

**Winner at tiny scale:** For **one-off downloads** with **tax handled for you**, **Lemon Squeezy and Paddle’s published take is similar**; choose based on **checkout UX**, **payout timing**, **support**, and **whether you expect subscriptions later**. For **marketplace discovery**, **itch.io** often wins **organic indie game buyer** traffic even though **fee structure is not directly comparable** (platform % + processors).

### Stripe alone

- **Payment Links** support **one-time** products with **no code** ([Stripe Payment Links docs](https://docs.stripe.com/payment-links)).
- **Caveat:** You are typically responsible for **tax registration and filing** unless you pair Stripe with other services—**higher compliance burden** than merchant-of-record platforms for **global** sales.

---

## 4. Passive income precedents (indie tools + adjacent content)

### Patterns observed

- **Tool sale** on itch.io (e.g. **Aseprite**) as the **primary** monetization; **community** builds **peripheral packs**.
- **Asset sellers** monetizing **leftovers from client/game work**—reported **multiple packs per year** and **hundreds of dollars annually** from itch alone in at least one **transparent** 2025 retrospective ([2025 Finances post](https://itch.io/blog/1137874/2025-finances)).
- **Bundles and jams** acting as **spikes**, not smooth annuities—still **compatible** with “low ongoing hours” if you **do not** commit to weekly support.

### Revenue ceiling (indie scale, honest framing)

- **Documented single-creator outcomes** in this scan range from **low hundreds / year** (one line-item channel) toward **low thousands / year** when itch is **one of several** income streams.
- **Outlier packs** may reach **low five figures gross** over a product lifetime per **anecdotes**—**not guaranteed** and **not the median**.

---

## 5. AI-adjacent passive products

### Evidence of sales

- **Prompt-style packs** on itch.io exist (example listing: [32 Fantasy RPG Characters – AI Prompt Pack](https://proassets-ia.itch.io/32-fantasy-rpg-characters-prompt-pack)).
- **Godot-oriented AI tooling** sold as an addon (example: [Godot AI Suite](https://marcengelgamedevelopment.itch.io/godot-ai-suite)).
- **Workflow / agent kits** appear as **apps or repos** (e.g. [DEVFORGE on itch.io](https://conflict-simulations-llc.itch.io/devforge)); revenue **not disclosed** in this scan.

### Takeaway

- Category is **real but noisy**; buyers **overlap** with **engine-specific** communities. **Packaging clarity** (what tool, what model, what license, what deliverables) matters as much as **prompt text**.

---

## Option assessment (Orchestrator brief)

### Option A — Pixel art asset packs (itch.io)

| Field | Assessment |
|--------|------------|
| **Signal strength** | **Moderate → Strong** for “people buy pixel assets here”; **Weak** for “your specific art will sell” without preview/competitive check. |
| **Addressable market** | **Global indie gamedev buyers** on itch.io; realistic **early goal** is **tens to low hundreds** of purchases per pack **if** quality, previews, and tags align—**not** forecastable to tighter bounds without testing. |
| **Key risks** | Style too game-specific; weak thumbnails; license ambiguity; support/refund expectations; **processor fixed fee** pain at **$1** price points ([itch.io recommends ≥$2 minimum](https://itch.io/docs/creators/payments)). |
| **Recommended action** | **Prototype one small pack** (minimal SKU), price **$5–$15**, invest in **preview images + clear license**, run a **time-boxed** launch with **one devlog**; compare views → purchases. |

### Option B — Educational content (AI + metroidvania / level design)

| Field | Assessment |
|--------|------------|
| **Signal strength** | **Moderate** for “AI game dev education sells”; **Moderate (unvalidated)** for “your exact niche is under-served.” |
| **Addressable market** | **Indie devs learning AI workflows**; overlap with **room/level tooling** buyers if positioned carefully; likely **smaller** than generic Godot/Unity course markets. |
| **Key risks** | **High upfront authoring time**; content **dating quickly** as models change; **refund/chargeback** risk if quality disappoints. |
| **Recommended action** | **Marketing**: 2-hour **competitive keyword** pass + outline **3 unique lessons** tied to your real workflow; **then** decide **PDF vs. video**. Ship **smallest paid slice** (e.g. **$12–$25**) before building a **full course**. |

---

## Sources (primary)

- [itch.io — Pricing (creators)](https://itch.io/docs/creators/pricing)
- [itch.io — Accepting Payments and Getting Paid](https://itch.io/docs/creators/payments)
- [itch.io — Top selling game assets](https://itch.io/game-assets/top-sellers)
- [itch.io — Top selling: Asset Pack + Pixel Art](https://itch.io/game-assets/top-sellers/tag-asset-pack/tag-pixel-art)
- [itch.io blog — 2025 Finances (Odds & Ents)](https://itch.io/blog/1137874/2025-finances)
- [Gumroad — Pricing](https://gumroad.com/pricing)
- [Lemon Squeezy — Pricing](https://www.lemonsqueezy.com/pricing)
- [Paddle — Pricing](https://www.paddle.com/pricing)
- [Stripe — Payment Links](https://docs.stripe.com/payment-links)
- [Aseprite on itch.io](https://dacap.itch.io/aseprite)
- Example AI-adjacent listings: [AI Prompt Pack (itch.io)](https://proassets-ia.itch.io/32-fantasy-rpg-characters-prompt-pack), [Godot AI Suite](https://marcengelgamedevelopment.itch.io/godot-ai-suite)

---

**Recommendation:** Proceed to **decision mode** with **Finance**: model **net revenue** after **itch.io cut + processor** for **$5 / $10 / $15 / $25** SKUs, and compare to **Gumroad/Lemon Squeezy** for a **PDF-only** product. Green-light **one** low-scope experiment: **either** a **small asset pack** **or** a **short paid guide**, not both at once, unless the founder explicitly allocates **extra** calendar time.

**Risks:** Public data **cannot** rank competitors by true revenue; **education** can **blow up** in hours; **tax and MOSS** complexity if you pick **Stripe-only** without advice.

**Confidence:** **Medium** — strong on **platform facts** (fees/docs), weaker on **your** **conversion** and **niche uniqueness** without a **small launch test**.

**Founder approval needed:** **Yes** — pick **which experiment ships first**, confirm **minimum hours/week** budget, and confirm **comfort** selling **game-derived art** under a **clear license**.

**Next actions:**  
- **Orchestrator** — schedule **decision mode** with Research + Finance + Marketing.  
- **Finance** — build the **fee model** and **breakeven units** table for the SKUs above.  
- **Marketing** — validate **positioning strings** and **three proof assets** (screenshots, TOC, or pack preview) before listing.  
- **Founder** — approve **first SKU** and **price floor** (recommend **≥$5** on itch.io to reduce **fixed processor drag**).
