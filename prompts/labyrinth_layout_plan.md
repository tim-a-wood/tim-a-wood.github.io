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

## Step 3: Draft ledges array (for G3 approval)

**Visualize:** Open `level-viewer.html` in a browser to see the draft layout (platforms, door, start, relic, key). Same data as the table below; update the viewer if you change the draft.

Data only. First entry is fixed (corridor). Rest zigzag upward with short runs (len 1–2), one relic alcove, then climb to key ledge. Path: start (corridor) → relic (early alcove) → key (high, double-jump only) → return to door.

| # | x | y | len | tint | Notes |
|---|---|---|-----|------|------|
| 1 | 0 | 1100 | 8 | 0 | **FIXED** corridor (start) |
| 2 | 288 | 1060 | 2 | 0 | Step right from corridor |
| 3 | 352 | 1020 | 1 | 1 | Zig right |
| 4 | 304 | 980 | 2 | 2 | Zig left |
| 5 | 400 | 940 | 1 | 0 | Zig right |
| 6 | 336 | 900 | 2 | 3 | Zig left |
| 7 | 432 | 860 | 1 | 1 | Zig right |
| 8 | 368 | 820 | 2 | 2 | Zig left — **relic alcove** (relic platform) |
| 9 | 480 | 780 | 1 | 0 | Zig right |
| 10 | 416 | 740 | 2 | 4 | Zig left |
| 11 | 512 | 700 | 1 | 1 | Zig right |
| 12 | 448 | 660 | 2 | 2 | Zig left |
| 13 | 544 | 620 | 1 | 0 | Zig right |
| 14 | 480 | 580 | 2 | 3 | Zig left |
| 15 | 576 | 540 | 1 | 1 | Zig right |
| 16 | 512 | 500 | 2 | 4 | Zig left |
| 17 | 608 | 460 | 1 | 0 | Zig right |
| 18 | 544 | 420 | 2 | 2 | Zig left |
| 19 | 640 | 380 | 1 | 1 | Zig right |
| 20 | 576 | 340 | 2 | 3 | Zig left |
| 21 | 672 | 300 | 1 | 0 | Zig right |
| 22 | 608 | 260 | 2 | 4 | Zig left |
| 23 | 704 | 220 | 1 | 1 | Zig right |
| 24 | 1100 | 260 | 2 | 4 | Approach to key area (gap forces double jump) |
| 25 | 1450 | 120 | 3 | 1 | **Key ledge** — reachable only via double jump from 24 |

Flow: Corridor (1) → 2 → 3 → … → 8 (relic) → … → 24 → 25 (key). Return: 25 → 24 → … → 2 → 1 → door.

Relic position (Step 4): on platform 8 (centers 384, 416; y=820). Key position (Step 4): on platform 25 (e.g. center tile; y=120).

---

## Progress

- [x] Step 1 — constraints documented (code comment)
- [x] Step 2 — design rules defined
- [x] Step 3 — ledge draft (pending G3 approval)
- [ ] Step 4 — relic/key positions
- [ ] Step 5 — implement ledges
- [ ] Step 6 — progression objects
- [ ] Step 7 — tests
- [ ] Step 8 — playthrough + docs
