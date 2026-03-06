# Metroidvania single-room level design guide

Summary of principles from online metroidvania level design guides, applied to a **single-room** layout (e.g. one zone, one door in/out, one key and one ability pickup).

**Sources:** ClassX/GoodGus level design steps, Game Wisdom (foundation / upgrades / environment), PC Gamer metroidvania map design, Hollow Knight terrain design (intentional platforms, solid surfaces, vertical as puzzle), doors/gates and backtracking articles.

---

## 1. Timeline and progression first

- **Draft the sequence:** What must the player do, in order? Example: enter → find relic (unlock double jump) → reach key (requires double jump) → return to door (unlock exit).
- **Abilities as keys:** Each ability should gate at least one meaningful barrier. The room should have a clear “before/after” for that ability (e.g. key ledge unreachable without double jump).
- **Locks and keys:** Use soft gates (ability-gated) rather than only hard locks. The player should see or infer what they need (e.g. “I need to get up there” → later “double jump gets me there”).

---

## 2. Room as a set of subunits

- **Break the room into zones:** e.g. “entry,” “exploration loop,” “ability pickup,” “ability-gated goal,” “return path.” Every opening or branch should lead somewhere intentional (no pointless dead ends unless they reward exploration).
- **One main path, optional discovery:** The critical path (relic → key → door) should be readable. Optional or branching paths can reward exploration (e.g. relic in a side branch that feels like a detour).
- **Landmarks:** Give the player something to orient by (e.g. a distinct platform cluster, the door position, the key ledge visible from below) so backtracking isn’t disorienting.

---

## 3. Platform placement and vertical space

- **Intentional, not arbitrary:** Every platform should have a role (path, rest, gate, landmark). Avoid filler platforms that don’t support flow or progression.
- **Solid, predictable surfaces:** No pass-through or ambiguous terrain in this prototype; platforms are solid. That makes ability gates clear (you can’t skip the key ledge without the ability).
- **Vertical as puzzle:** Use height and gaps so that “going up” or “reaching the key” is a small platforming puzzle, not a straight ramp. The ability (e.g. double jump) should feel like the solution.
- **Spacing matches abilities:** Early platforms (before the ability) should be reachable with base movement. After the ability, one or two spaces can require it so the upgrade feels meaningful.

---

## 4. Foundation and first minute

- **Playable from minute one:** The player should have control and a clear first goal (e.g. “move right, explore”) without needing an ability they don’t have. The room shouldn’t start with a gate that blocks everything.
- **Introduce the ability early in the loop:** Place the ability pickup (relic) so the player can reach it with base movement, then use the rest of the room to make that ability useful (key ledge, optional shortcuts).

---

## 5. Backtracking and return path

- **Return recontextualizes space:** The path back to the door can reuse the same platforms; with the new ability, traversal can feel easier or different (e.g. fewer jumps). That reinforces “I got stronger.”
- **Clear way back:** Avoid maze-for-the-sake-of-maze. The return route can be the same path in reverse or a simple alternate (e.g. drop down) so the player isn’t lost after getting the key.
- **Shortcuts (optional):** In a single room, a “shortcut” might be a path that’s only possible with the new ability (e.g. double jump over a gap on the return). Not required for a first single room.

---

## 6. Applied to our single room

| Principle            | Application in this room                                          |
|----------------------|--------------------------------------------------------------------|
| Timeline             | Entry → relic (double jump) → key (double-jump gate) → door.       |
| Subunits             | Entry (corridor + first platforms), exploration (winding path), relic branch, main path to key approach, key ledge, return. |
| Intentional platforms| Short runs (len 1–2) for corridors; 2–3 tile “landing” where needed; one clear key ledge. |
| Ability gate         | Key ledge only reachable via double jump from a specific approach platform. |
| Playable from start  | No gate at entry; first platforms reachable with single jump.     |
| Return path          | Same path back to corridor/door; optional: drop or double-jump shortcut. |
| Landmarks            | Corridor (start), relic platform, key ledge (visible from below), door. |

Use this guide when drafting or revising the single-room layout (e.g. in the level viewer and in `buildFirstZone()`).
