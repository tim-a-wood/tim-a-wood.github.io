# Playbook: Release Readiness

**Invoke:** orchestrator mode=launch
**Specialists involved:** QA, Legal, Cybersecurity, Marketing
**Owner:** QA agent (coordinates), Founder (approves)

## Pre-Launch Checklist

### QA Gate
- [ ] All P0 and P1 bugs resolved or explicitly deferred with founder sign-off
- [ ] Canvas rendering tested in Chrome, Firefox, Safari
- [ ] Export output validated against current JSON schema
- [ ] AI Copilot round-trip tested (suggestion → accept/reject → state correct)
- [ ] Undo/redo stack validated across all entity types
- [ ] Room layout loads correctly from saved JSON
- [ ] No console errors on baseline workflows

### Security Gate
- [ ] No API keys in client-side JS
- [ ] Python server endpoints have input validation
- [ ] No new XSS vectors introduced
- [ ] CSP headers present on served pages

### Legal Gate
- [ ] Any new AI features disclosed in changelog
- [ ] No marketing claims that constitute warranties
- [ ] New dependencies checked for license compatibility

### Marketing Gate
- [ ] Changelog drafted and reviewed
- [ ] Announcement copy ready (if public release)
- [ ] Screenshots/video updated if UI changed significantly

## Go / No-Go Decision
Founder reviews gate status. Any unresolved P0 = No-Go by default.
