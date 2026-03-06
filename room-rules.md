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

## Outdoor rooms

- **Do not** add boundary walls or a ceiling for the room shell. The player may leave via any edge unless something else blocks it (e.g. hazard, one-way gate, or locked door).
- Entry and exit are **not** restricted to doors; open passage is allowed unless another mechanism blocks it.
- Optional: use doors or other objects on edges to mark transitions (e.g. into an internal room) without sealing the rest of the edge.

## Future-proofing

- Use `roomType: 'internal' | 'outdoor'` (or equivalent) when building a zone so boundary walls/ceiling are only created for internal rooms.
- When adding multiple zones or scenes, set each zone’s room type so internal zones get walls/ceiling and outdoor zones do not.
