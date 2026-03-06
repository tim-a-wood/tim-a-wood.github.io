# Room Rules

## Room types

The game supports two room kinds. The active zone’s type is set via config (e.g. `ROOM_LAYOUT.roomType`) so the same build path can render internal or outdoor rooms.

- **Internal rooms** — Enclosed spaces (dungeons, buildings). Use walls and a ceiling; entry/exit only through doors (or other defined transitions).
- **Outdoor rooms** — Open areas (courtyards, overworld). No boundary walls or ceiling; edges are passable unless blocked by another mechanism (e.g. hazard, gate, or locked door).

## Internal rooms

- Add **walls and a ceiling** on every edge that does not have an intentional door (or other transition).
- Rooms are **enterable and exitable by doors only** (or other defined transition objects).
- If a door exists on an edge, keep the rest of that edge closed so the doorway is the only transition.
- Mirror room-boundary logic in layout tests when room geometry or room type changes.

### Indoor / dungeon layout (labyrinth)

When designing internal room platforms to feel labyrinthian (dungeon-style):

- **Corridors** — Prefer short runs of 1–2 tiles for narrow passages and choke points rather than long straight platforms.
- **Zigzags and vertical flow** — Path should wind (alternate left/right) and move vertically with direction changes; use staggered steps instead of a single straight climb.
- **Alcoves and dead ends** — Optional small branches (1–2 tiles) for pickups or variety; main progression path stays clear (e.g. start → relic → key → door).
- **Internal walls (optional)** — Use platforms as walls to form corridors (vertical strips or L-shapes); same ledge/platform API, no new systems.
- **Progression flow** — One clear route; abilities (e.g. double jump) gate later parts; no sequence breaks.
- **Density** — Prefer more, smaller platforms over fewer long ones; reuse existing tints for variety.

### Actual labyrinth (maze)

When the goal is an **actual labyrinth** (maze-like, easy to get lost):

- **Narrow passages** — Use len 1–2 only so the path feels like corridors, not open platforms.
- **Branches and junctions** — At least 2–3 places where the path splits; only some branches lead to progress.
- **Dead ends** — Several branches that end in a single platform (no exit); one dead end holds the relic so exploration is rewarded.
- **Internal barriers** — Vertical stacks of single-tile platforms (same x, different y) so the player must go around; no direct straight line through the room.
- **Winding route** — The path to the key doubles back or loops so orientation is non-obvious; return to the door feels like “finding your way out.”

## Outdoor rooms

- **Do not** add boundary walls or a ceiling for the room shell. The player may leave via any edge unless something else blocks it (e.g. hazard, one-way gate, or locked door).
- Entry and exit are **not** restricted to doors; open passage is allowed unless another mechanism blocks it.
- Optional: use doors or other objects on edges to mark transitions (e.g. into an internal room) without sealing the rest of the edge.

## Future-proofing

- Use `roomType: 'internal' | 'outdoor'` (or equivalent) when building a zone so boundary walls/ceiling are only created for internal rooms.
- When adding multiple zones or scenes, set each zone’s room type so internal zones get walls/ceiling and outdoor zones do not.
