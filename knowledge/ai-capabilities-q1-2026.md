# AI Capabilities — Q1 2026 Relevance Brief

This knowledge file provides every specialist agent with a shared baseline on the AI capabilities most relevant to this business.

## Coding Agents
- **Claude Code (Anthropic):** Long-horizon coding agent, strong at understanding large codebases. Best for feature implementation, refactoring, and debugging.
- **Codex (OpenAI):** Strong at code generation from spec, integrates with GitHub Copilot Workspace.
- **Cursor:** IDE-native agent with strong inline editing and multi-file refactoring.
- **Key implication:** All three tools can be orchestrated from this repo via AGENTS.md / CLAUDE.md / .cursor/rules. One shared instruction set → consistent behavior across tools.

## Image Generation and Editing
- **State as of Q1 2026:** Image generation is high quality for environment concepts but unreliable for pixel art consistency. Pixel art specifically requires fine-tuned or specialized models.
- **Practical use:** AI can generate environment mood/concept references. Production pixel sprites still need manual cleanup.
- **Tools:** Midjourney, DALL-E 3, Stable Diffusion (ControlNet for consistency), Magnific for upscaling.
- **Key implication:** AI-generated assets are useful for ideation, not production. The toolchain's value is in the workflow, not in replacing artists.

## LLM-Assisted Design (Room Copilot pattern)
- **State:** Gemini 2.0 Flash and Claude 3.5 Haiku can generate structured room layouts from natural language descriptions when given a schema.
- **Practical use:** Room Copilot in this product uses Gemini to suggest entity placements. Output must be schema-validated before application.
- **Key risk:** LLMs hallucinate schema violations. Always run deterministic validation after AI output.

## Agentic Workflows
- **State:** Multi-agent systems with clear role definitions and structured handoffs are now reliable enough for production use.
- **Practical use:** This OS itself is an agentic workflow system. Orchestrator + specialist pattern is proven.
- **Key implication:** The value of this operating system is in the structured prompting and role definition, not in custom infrastructure.

## Cost Landscape (Q1 2026)
- Gemini 2.0 Flash: very low cost-per-token, good quality for structured generation
- Claude Haiku 4.5: cost-efficient for high-frequency agent operations
- Claude Sonnet 4.6: best quality for complex analysis; use for high-stakes decisions
- Batch APIs: 50% cost reduction for async workloads

## What AI Cannot Reliably Do (Yet)
- Produce pixel-perfect, consistent pixel art sprites without manual correction
- Maintain long-range progression/gating logic consistency across a large room graph
- Replace QA for visual regression testing
- Make legally reliable IP ownership determinations for AI-generated content
