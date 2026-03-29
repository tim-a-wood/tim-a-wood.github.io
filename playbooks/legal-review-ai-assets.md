# Playbook: Legal Review — AI-Generated Assets

**Invoke:** Before any public release that includes AI-generated content
**Specialists involved:** Legal, QA (for validation pipeline)
**Owner:** Legal (reviews), Founder (approves)

## Scope
This playbook covers review of:
- AI-generated sprite suggestions
- AI-generated room layouts
- AI-generated tileset compositions
- Any AI feature that produces content users might commercialize

## Review Checklist

### Provenance
- [ ] Which AI model/API generated the content?
- [ ] What is the model provider's ToS regarding commercial use of outputs?
- [ ] Is the output trained on any data with conflicting IP claims?

### Disclosure
- [ ] Does the product disclose when content is AI-generated?
- [ ] Does the ToS/EULA address AI-generated content ownership?
- [ ] Are users informed that they should verify commercial rights before publishing AI-assisted work?

### Validation
- [ ] Is there a deterministic validation step before AI content reaches the user?
- [ ] Can AI suggestions be traced back to a specific model version for audit?

## Outputs
- Legal review memo (Legal agent drafts, Founder reviews)
- Updated ToS/EULA if needed (requires real attorney for anything material)
- Disclosure copy for UI and docs

## When to Escalate to Real Attorney
- Any material commercial release
- EU deployment (AI Act compliance)
- User-generated AI content with commercial licensing questions
