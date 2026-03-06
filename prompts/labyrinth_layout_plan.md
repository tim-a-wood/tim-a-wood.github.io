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

## Metroidvania guide (single room)

**Source:** `prompts/metroidvania_single_room_guide.md` — summary of online metroidvania level design guides applied to this single room. Use it when drafting or revising layouts: timeline first, room as subunits, intentional platforms, ability gate, playable from start, clear return path, landmarks.

---

## Level Design Specification (current source of truth)

The room follows the **Level Design Specification: Labyrinthian Metroidvania Room** (world 1600×1200, 32×32 tiles, 14px platform thickness). Layout is defined by **`LABYRINTH_LEDGES`** in `index.html`: explicit platform list with corridor first, winding path to high key ledge. Door at `(248, 1137)`; key on high ledge; relic on mid platform.

---

## Fixed elements (do not change)

- **World:** 1600×1200. Floor center Y = 1184; ceiling Y = 16. Corridor platform: first ledge `{ x: 0, y: 1100, len: 8 }`.
- **Exit door:** position `(248, 1137)`; top just below corridor bottom (1107), bottom above ground.
- **Boundary:** Left wall to center 1077 (bottom flush 1093); right wall full height (centers to 1168); ceiling full width.

---

## Labyrinth design rules (Step 2)

**Canonical source:** `room-rules.md` → “Internal rooms” → “Indoor / dungeon layout (labyrinth)”. Use those rules when drafting and placing ledges.

---

## Step 3: Layout options (pick one, then iterate)

**Visualize:** Open `level-viewer.html` and use the **Layout** dropdown to switch between options. Pick one; we’ll iterate on that choice.

---

### Option A — Corridor crawl (horizontal layers)

**Idea:** Dungeon as horizontal “floors” — you move along corridors at one height, then step up/down to the next. Mostly left–right movement with short vertical links. Relic in a side alcove; key at the far right on a high shelf.

**Flow:** Start → walk right along lower corridors → branch to relic alcove → continue right → climb to upper corridor → cross to key (double-jump gap) → return along same path to door.

**Feel:** Walking through halls and stairs, not climbing a tower.

---

### Option B — Tower / shaft (vertical spine)

**Idea:** One main vertical run in the centre of the room: narrow stacked platforms with small side alcoves. Strong “climb the tower” feel. Relic mid-climb; key at the top. Compact in x, spread in y.

**Flow:** Start → step into tower base → climb centre spine (with optional alcove detours) → relic on spine → keep climbing → key at top → drop/descend to door.

**Feel:** Vertical ascent, tight and focused.

---

### Option C — Loop (figure-8 / backtrack)

**Idea:** Path goes right and up, then **loops back left** at a different height so you traverse the same horizontal band twice (out and back). Relic on the outward leg; key on the return or after a second climb. Clear backtracking/loop.

**Flow:** Start → go right and up (outward) → relic → continue to right end → loop back left (return leg) → climb left side → cross to key (double jump) → return to corridor → door.

**Feel:** “Go in, loop back, then climb” — metroidvania-style revisit.

---

### Option D — Zigzag ladder (original draft)

**Idea:** Short 1–2 tile platforms in a continuous zigzag from bottom-left to top-right. No strong horizontal “floors” or central tower; just a winding ladder. Relic early; key at top-right.

**Flow:** Corridor → zigzag up through many small steps → relic on ledge 8 → continue zigzag → jump across to key ledge → return same path.

**Feel:** Staircase / ladder climb with many direction changes.

---

**Selection (user ranking, best → worst):** **C → A → B → D.** **Option C (Loop)** was the previous choice; **Option E (Actual labyrinth)** reworks the design as a true maze (see below).

---

## Option E — Actual labyrinth (maze)

**Idea:** A real labyrinth: narrow corridors (len 1–2 only), **junctions** where the path splits, **dead ends** (one holds the relic), and **internal barriers** (vertical stacks of platforms you must go around). The route to the key winds and doubles back; finding the door again is part of the challenge.

**Structure:**
- **Entry:** Corridor → short passage → **first junction** (left = dead end with relic, right = main path).
- **Barrier:** A vertical column of 3 single-tile platforms (same x, different y) so you must go down, left, then under and right to continue.
- **Second dead end:** Short branch off the main path (no pickup).
- **Main path:** Winds right and up in 1-tile steps to the key approach; double-jump to key ledge.
- **Return:** Reverse through the maze to the corridor → door.

**Rules (see `room-rules.md` → “Actual labyrinth (maze)”):** Narrow passages, branches/junctions, dead ends, internal barriers, winding route. **Relic** (304, 953). **Key** (1498, 86). Full ledges in level-viewer layout E.

---

## Option F — Guide-based single room

**Idea:** Layout built from **online metroidvania level design guides** (see `prompts/metroidvania_single_room_guide.md`). Single room with clear timeline (entry → relic → key → door), subunits (entry, relic branch, main path, key approach, return), intentional platform spacing (len 2 for readability, gentle zigzag), one ability gate (key ledge requires double jump), and landmarks (corridor, relic platform, key ledge, door). No maze confusion; every branch leads somewhere. Relic in a short side branch off the first “landing”; main path winds right and up to key approach then key ledge. Return: same path back to corridor. **Relic** (384, 953). **Key** (1498, 86). In viewer as **F — Guide-based single room**.

---

## Implemented layout: F (Guide-based single room), scaled to 1000×600

The game and tests use Layout F: 25 ledges (corridor → landing → relic branch → zigzag → key approach → key ledge). Relic (256, 436), key (954, 86), door (248, 537). Level viewer "Current" matches.

---

## Previous draft: Option C (Loop) — ledges (1600×1200)

| # | x | y | len | tint |
|---|---|---|-----|------|
| 1 | 0 | 1100 | 8 | 0 |
| 2 | 288 | 1060 | 2 | 0 |
| 3 | 368 | 1020 | 2 | 1 |
| 4 | 448 | 980 | 2 | 2 |
| 5 | 528 | 940 | 2 | 0 |
| 6 | 608 | 900 | 2 | 1 |
| 7 | 688 | 860 | 2 | 2 |
| 8 | 656 | 820 | 2 | 0 |
| 9 | 576 | 780 | 2 | 1 |
| 10 | 496 | 740 | 2 | 2 |
| 11 | 416 | 700 | 2 | 0 |
| 12 | 336 | 660 | 2 | 1 |
| 13 | 256 | 620 | 2 | 2 |
| 14 | 288 | 560 | 2 | 0 |
| 15 | 352 | 500 | 2 | 1 |
| 16 | 416 | 440 | 2 | 2 |
| 17 | 480 | 380 | 2 | 0 |
| 18 | 544 | 320 | 2 | 1 |
| 19 | 608 | 260 | 2 | 2 |
| 20 | 672 | 200 | 2 | 0 |
| 21 | 736 | 140 | 2 | 1 |
| 22 | 1100 | 260 | 2 | 4 |
| 23 | 1450 | 120 | 3 | 1 |

Relic (draft): on ledge 11, e.g. (432, 693). Key (draft): on ledge 23, e.g. (1498, 86). Step 4 can refine these.

---

## Iterating on C: three variants (pick or mix)

Use the level viewer **Layout** dropdown: **C** = current, **C1** / **C2** / **C3** = variants below. Pick what you like; we can combine ideas.

| Variant | Change | Why |
|--------|--------|-----|
| **C1 — Relic alcove** | Relic is in a **dead-end branch**: one extra 1-tile platform (336, 720) off the return leg. You step left into the alcove, get relic, step back. | Makes the relic feel like “explore side room, get reward” instead of on the main path. |
| **C2 — Tighter return** | **Two extra platforms** on the deep left (192, 600 and 224, 640) so the return leg runs closer to the left wall. Loop feels more enclosed, more “corridor.” | Stronger sense of a return corridor; less open in the middle. |
| **C3 — Key approach** | **Three extra platforms** (864,200 → 960,220 → 1072,240) leading from the top of the left climb toward the key area. Clear “approach run” before the double-jump to the key. | Key is a visible goal; the double-jump is the final hurdle. |

After you choose (e.g. C1 only, C1+C3, or “current C is fine”), we’ll set that as the final Option C and move to Step 4/5.

---

## Progress

- [x] Step 1 — constraints documented (code comment)
- [x] Step 2 — design rules defined
- [x] Step 3 — layout options drafted; **Option C (Loop) selected**
- [ ] Step 4 — relic/key positions (confirm or refine)
- [ ] Step 5 — implement ledges
- [ ] Step 6 — progression objects
- [ ] Step 7 — tests
- [ ] Step 8 — playthrough + docs
