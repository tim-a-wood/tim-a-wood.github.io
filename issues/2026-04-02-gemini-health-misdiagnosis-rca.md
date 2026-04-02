# RCA Task — Gemini Health Misdiagnosis And Overconfidence

**Date:** 2026-04-02
**Owner:** Engineering / agent workflow
**Status:** Open
**Priority:** High

## Problem

During the ruined-gothic calibration pass, the agent initially concluded that repeated Gemini failures were likely a Gemini-side or broad connectivity issue and continued to state that conclusion with too much confidence.

That diagnosis was incomplete. Later isolation showed:

- raw TLS and HTTP access to `generativelanguage.googleapis.com` worked from this machine
- direct REST calls via `curl`, Node `fetch()`, and Python `urllib.request` succeeded
- the failures were specific to the Python Gemini SDK / `httpx` transport path on this local environment

## Why This Needs RCA

This was not just a technical bug. It was also a process failure:

- the agent overfit on one failure mode (`ConnectTimeout` in the SDK)
- the agent did not sufficiently falsify its own hypothesis before repeating it
- the agent stayed too adamant after the evidence base was still weak

That combination risks wasted iteration time, polluted calibration state, and reduced trust in future triage.

## Confirmed Evidence

- `curl` reached `https://generativelanguage.googleapis.com/`
- `openssl s_client` completed TLS and certificate verification
- direct Node `fetch()` to `gemini-2.5-flash:generateContent` returned `200`
- direct Python `urllib.request` to the same endpoint returned `200`
- the Python Gemini SDK path still failed with `httpx.ConnectTimeout` during TLS handshake
- after switching the live room pass to direct REST, a fresh `RG-R2` rerun completed slot generation and produced a real browser-backed runtime screenshot, proving the room pipeline itself was not the failing layer

## Immediate Safeguard To Evaluate

Before labeling any future Gemini failure as a provider outage, require at least one alternate-client falsification step:

- raw HTTP probe (`curl` or `urllib`)
- one non-SDK runtime if available (for example Node `fetch()`)
- explicit distinction between provider outage, network-path issue, and client-library issue in the written diagnosis

## Questions To Answer

1. Why did the agent stop at the SDK failure instead of immediately testing:
   - `curl`
   - raw `urllib`
   - another runtime such as Node
2. What heuristics caused the agent to classify the issue as likely external rather than likely client-stack-specific?
3. Why did the agent continue to state the conclusion with high confidence after external-source checks were inconclusive?
4. What guardrails should require a second transport/runtime check before calling something a provider-side outage?
5. Should the room-environment pipeline prefer direct REST over the Python SDK by default on this machine until the SDK/TLS path is understood?

## Required Deliverables

- a short timeline of the incorrect diagnosis and the evidence available at each step
- the exact point where a falsification check should have been performed
- concrete agent-policy changes to reduce overconfident diagnosis on environment/network issues
- a recommendation on whether to standardize Gemini calls on direct REST for this repo

## Acceptance Criteria

- the team can explain the misdiagnosis without ambiguity
- there is at least one new operational safeguard added to prevent recurrence
- future agents have a documented escalation checklist for SDK/network/provider triage
