# Labyrinth layout plan (dungeon-style level)

Redesign interior platforms to feel labyrinthian. Corridor platform and exit door are **fixed** and must not change.

---

## Steps and gates

| Step | Action | Gate (review before next step) |
|------|--------|--------------------------------|
| **1** | Lock constraints: document fixed elements (corridor, door, boundaries) in code. | **G1** — Confirm constraints are correctly documented and no layout code was changed. |
| **2** | Define labyrinth design rules (corridors, zigzags, alcoves; optional internal walls). | **G2** — Approve design rules before drafting ledge data. |
| **3** | Draft new `ledges` array (data only): first entry = corridor; path start → relic → key → door. | **G3** — Approve ledge list (coordinates, flow). |
| **4** | Choose relic and key positions on the new layout (relic without double jump; key gated by double jump). | **G4** — Approve progression object positions. |
| **5** | Replace `ledges` in `buildFirstZone()` with new list; no other changes. | **G5** — Verify in-game: platforms only, corridor/door unchanged. |
| **6** | Update key/relic in `buildProgressionObjects()` if positions changed; door unchanged. | **G6** — Verify progression flow (relic → key → door). |
| **7** | Update unit tests to match new ledges and progression positions. | **G7** — All tests pass; coverage preserved. |
| **8** | Manual playthrough + optional doc note (project_plan, room-rules). | **G8** — Sign-off on full labyrinth layout. |

---

## Fixed elements (do not change)

- **Corridor platform:** first ledge `{ x: 0, y: 1100, len: 8, tint: 0 }`.
- **Exit door:** position `(248, 1137)`; right flush with corridor (256); top/bottom flush with corridor bottom (1107) and ground (1168).
- **Boundary:** `buildBoundaryWalls()`, `ROOM_LAYOUT` (ceiling, right wall, left wall + doorway).

---

## Labyrinth design rules (Step 2)

**Canonical source:** `room-rules.md` → “Internal rooms” → “Indoor / dungeon layout (labyrinth)”. Use those rules when drafting and placing ledges.

---

## Progress

- [x] Step 1 — constraints documented (code comment)
- [x] Step 2 — design rules defined
- [ ] Step 3 — ledge draft (use rules above)
- [ ] Step 4 — relic/key positions
- [ ] Step 5 — implement ledges
- [ ] Step 6 — progression objects
- [ ] Step 7 — tests
- [ ] Step 8 — playthrough + docs
