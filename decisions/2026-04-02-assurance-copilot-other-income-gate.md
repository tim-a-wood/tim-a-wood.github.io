# Decision log — Assurance-by-process / “Assurance Copilot” other-income track

**Date:** 2026-04-02  
**Owner:** Strategy (with Research filing)  
**Status:** Active gate (default: parked)

## Context

Some regulated software teams need **traceability**, **CI evidence**, and **provenance** around AI-assisted coding. That demand is real (avionics, automotive, medtech contexts). It is **not** the same business as the Workbench + Ashen Hollow flywheel: long **B2B sales cycles**, **legal/commercial** posture, and **tool-qualification** conversations (e.g. DO-330-style) are normal for buyers.

Full market and risk synthesis: `research/library/technical/assurance-copilot-do178c-market-2026-04-02.md`.

## Decisions (locked until founder revisits)

1. **Do not market** a product as “DO-178C compliant” or as granting certification. Frame as **process automation** and **human-in-the-loop** evidence helpers; the **customer** owns compliance and any tool qualification.
2. **Default:** **No standalone product** commitment. Treat this as an **optional** other-income track **after** explicit founder priority.
3. **Allowed next step:** A **time-boxed spike only**, with **Legal** and **Finance** gates (positioning/disclaimers/contracts; CAC, cycle length, services mix vs. Workbench path).
4. **Go / no-go for a spike** (from research §6, reiterated here):
   - Founder can allocate attention **or** a separate resource decision for roughly **6–12 months** *after* core Workbench milestones **or** explicitly deprioritizes those for this experiment.
   - A **first customer** is **reachable** (network, subcontract, or LOI) for **one** vertical — pick **one**: avionics **or** medtech **or** automotive.
   - **Legal/commercial** templates exist or are budgeted for regulated B2B (MSA, DPA, AI addendum).
5. If those gates are **not** met: **remain parked**; the research library entry remains the decision record.

## Explicitly rejected / deferred (for now)

- Implying the coding agent itself is “qualified” under a customer’s program without a scoped legal and engineering plan.
- Building a broad SaaS before **one** paid or LOI-backed learning cycle (services-first or narrow pilot is the lower-risk path per research).

## Internal reuse (MV repo)

Lightweight assurance patterns already in use (charters, directives, `decisions/`, agent dashboards) **transfer** to thinking about agentic discipline; they do **not** replace enterprise evidence packs. Optional: tighten **internal** completion hygiene (e.g. non-null `output_location` before “done”) without productizing.

## Next trigger

Founder states: spike **yes/no**, **week budget**, **one vertical**, and **first-customer path** — or confirms **stay parked**.
