# Paid Tier Margin Template — MV Toolchain
**Version:** 1.0 | **Date:** 2026-04-07 | **Author:** Finance Agent

> **Purpose:** One-page contribution margin view for the first paid SKU. Shows whether the product makes money on each paying user before overhead. All assumptions are labeled — none are facts until measured data replaces them.

---

## What this is

A contribution margin model answers: for every dollar a paying user sends us, how much is left after we pay for the direct cost of serving them? If that number is negative, the business loses money on every user at scale. This model makes that visible before a price is published.

---

## Cost Structure: Variable Costs Per Paying User Per Month

These are the costs that scale with every paying user.

| Cost Line | Bear Case | Base Case | Bull Case | Assumption Basis |
|---|---|---|---|---|
| **AI API (Gemini)** | $0.40 | $0.18 | $0.06 | ASSUMPTION: Charter estimate of $0.02/invocation. Bear=20 inv/mo (power user), Base=9 inv/mo, Bull=3 inv/mo. Not yet measured — replace with actual logged data when available. |
| **Hosting** | $0.03 | $0.02 | $0.01 | ASSUMPTION: Cloudflare Pages free tier for static assets; estimated marginal compute at scale. Sub-$0.05/user/month is realistic for edge-served static tools. |
| **Payment processing (Stripe)** | varies | varies | varies | FACT: Stripe charges 2.9% + $0.30 per transaction. Applied below per price point. |
| **Total variable (before Stripe)** | **$0.43** | **$0.20** | **$0.07** | |

> **Priority update needed:** AI API cost is the dominant variable. Once per-session token logging is instrumented (Priority #1), replace the charter estimates above with measured p50/p90 actuals.

---

## Contribution Margin by Price Point

Stripe fee is applied per subscription price: `fee = price × 0.029 + 0.30`

### At $6/month

| Scenario | Revenue | Stripe Fee | AI + Hosting | Contribution Margin | Margin % |
|---|---|---|---|---|---|
| Bear | $6.00 | $0.47 | $0.43 | **$5.10** | **85%** |
| Base | $6.00 | $0.47 | $0.20 | **$5.33** | **89%** |
| Bull | $6.00 | $0.47 | $0.07 | **$5.46** | **91%** |

### At $9/month

| Scenario | Revenue | Stripe Fee | AI + Hosting | Contribution Margin | Margin % |
|---|---|---|---|---|---|
| Bear | $9.00 | $0.56 | $0.43 | **$8.01** | **89%** |
| Base | $9.00 | $0.56 | $0.20 | **$8.24** | **92%** |
| Bull | $9.00 | $0.56 | $0.07 | **$8.37** | **93%** |

### At $14/month

| Scenario | Revenue | Stripe Fee | AI + Hosting | Contribution Margin | Margin % |
|---|---|---|---|---|---|
| Bear | $14.00 | $0.71 | $0.43 | **$12.86** | **92%** |
| Base | $14.00 | $0.71 | $0.20 | **$13.09** | **94%** |
| Bull | $14.00 | $0.71 | $0.07 | **$13.22** | **94%** |

> **Reading this table:** Every price point shows positive contribution margin in all three scenarios. The business does not lose money on paying users at current Gemini pricing. The margin floor is ~85% (bear case at $6), which is strong for an AI-native tool. The risk is a Gemini price increase or significantly higher-than-modeled usage — see sensitivity section below.

---

## MRR Scenarios (Contribution Margin × Paying Users)

Using base case AI costs, $9/month price point:

| Paying Users | MRR | Total Variable Cost | Contribution Margin |
|---|---|---|---|
| 10 | $90 | $7.60 | $82.40 |
| 50 | $450 | $38 | $412 |
| 100 | $900 | $76 | $824 |
| 500 | $4,500 | $380 | $4,120 |
| 1,000 | $9,000 | $760 | $8,240 |

> **Note:** These figures are contribution margin — not profit. Fixed costs (tooling subscriptions, founder time, any infrastructure minimums) are not deducted here. Contribution margin must exceed fixed costs for the business to be net profitable.

---

## Sensitivity: What Breaks the Model

The contribution margin looks healthy now. These are the scenarios that could change that:

| Scenario | Impact | Trigger |
|---|---|---|
| Gemini raises prices 2× | AI cost doubles; bear case margin drops from 85% to ~80% | Google pricing change (happened 2023-24 for OpenAI) |
| Gemini raises prices 5× | AI cost at $2/user/month in bear case; margin drops to ~71% at $6/mo | Extreme pricing change; still positive but uncomfortably thin |
| Power user at 50 inv/month | AI cost = $1.00/user/month; margin = 79% at $6/mo | No usage cap in place |
| No usage cap + viral spike | 100× usage in a 48-hour window; potential $X00s bill before rate limit | Pre-revenue viral moment before billing goes live |

**Key threshold:** At current Gemini pricing (~$0.02/invocation), the model stays cash-positive at $6/month even if a user runs 20 sessions/month. The critical cap to set before launch is: how many Copilot invocations does the paid tier include? Unlimited is fine economically today; it becomes a risk only if Gemini prices increase 5× or usage is dramatically higher than modeled.

---

## What This Model Needs to Be Reliable

These assumptions must be replaced with measured data before a final price is committed:

| Item | What's Needed | Who | Status |
|---|---|---|---|
| AI API cost per session | Instrument token logging in the assistant stack | Engineering | Priority #1 in finance backlog — not yet done |
| Invocations per user per month | Usage analytics on how many times a typical user triggers AI features | Engineering/Analytics | Unknown — no measurement in place |
| Hosting cost at 100/1,000 paying users | Actual Cloudflare/hosting bill as traffic grows | Founder | Estimate only |
| Stripe rate confirmation | Confirm current Stripe tier and fee schedule | Founder | FACT: Standard Stripe rate is 2.9% + $0.30 |

---

## Recommendation on Pricing

**This model does not recommend a price — that is a founder decision.** What it shows:

1. **$6/month is financially viable** today given current Gemini pricing and usage estimates. Contribution margin is positive in all three scenarios.
2. **$9/month is the safer floor** — provides more buffer against cost spikes and delivers ~$8/user/month in contribution margin to cover fixed costs and investment.
3. **Usage caps are optional but prudent** — without them, power users are still cash-positive at current pricing. Set a cap (e.g., 20 Copilot invocations/month on the paid tier) before a viral event creates uncontrolled API cost.
4. **Measure before committing** — replace the AI API cost assumption with real data before setting a public price. The p90 usage cost matters more than the average.

---

## Glossary (plain language)

- **Contribution margin:** revenue minus the direct variable costs of serving one paying user. Does not include fixed costs like tooling or founder salary.
- **Bear/Base/Bull:** pessimistic / expected / optimistic scenarios. Bear assumes high usage and costs; bull assumes low usage and costs.
- **Stripe fee:** what the payment processor charges per transaction. 2.9% of the subscription price + $0.30 flat. At $9/month, this is $0.56.
- **ARPU:** average revenue per user per month. For a flat subscription, this equals the subscription price.
- **MRR:** monthly recurring revenue. Paying users × subscription price.

---

*This template is a living document. Update AI API costs when measured data is available. Review quarterly or after any Gemini pricing announcement.*
