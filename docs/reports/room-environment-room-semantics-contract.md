# Room Environment Room Semantics Contract

**Date:** 2026-04-04  
**Owner:** Level Design  
**Status:** Draft contract for the MVP adaptation  
**Related inputs:**
- [AGENTS.md](/Users/timwood/Desktop/projects/PWA/MV/AGENTS.md)
- [docs/room-environment-pipeline-v3-spec.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-spec.md)
- [docs/room-environment-pipeline-v3-software-requirements.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-software-requirements.md)
- [docs/room-layout-validation.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-layout-validation.md)
- [docs/room-rules.md](/Users/timwood/Desktop/projects/PWA/MV/room-rules.md)
- [decisions/2026-03-31-room-environment-quality-pass.md](/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md)

## Purpose

`room_semantics.json` is a derived, geometry-first sidecar. It does not replace the room JSON authority model. It interprets the room layout so planning, overlay review, and QA can agree on what the room actually contains.

The source of truth remains the current room payload, especially the room polygon and the room-local gameplay objects. The semantics file only describes what can be inferred from that payload.

## Authority Model

The semantics extractor must treat the following as authoritative room inputs:

- `id`
- `name`
- `size`
- `polygon`
- `platforms`
- `doors`
- `movingPlatforms`
- `playerStart`
- `edgeLinks`
- `removedEdges`
- `keys`
- `abilities`
- `pits` when present in a room-authoring fixture

The following are not geometry authority:

- `global`
- `environment`
- any biome or art-direction metadata

Those fields may inform review context, but they must not invent, remove, or reshape room geometry.

## Proposed `room_semantics.json` Shape

```json
{
  "schema_version": "room-semantics-v1",
  "source": {
    "layout_path": "/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json",
    "layout_hash": "sha256:...",
    "generated_at": "2026-04-04T00:00:00Z",
    "authority": "room-layout-data"
  },
  "rooms": [
    {
      "room_id": "R11",
      "room_name": "Branch A Tunnel Shaft",
      "room_index": 10,
      "room_role": "traversal_shaft",
      "room_type": "internal",
      "room_size": { "width": 1600, "height": 1800 },
      "source_fields_used": ["polygon", "edgeLinks", "removedEdges", "size", "platforms", "doors", "playerStart"],
      "semantics": {
        "tops": [],
        "undersides": [],
        "vertical_faces": [],
        "shell_surfaces": [],
        "openings": [],
        "corners": [],
        "cavities": [],
        "decor_safe_zones": [],
        "gameplay_exclusion_zones": [],
        "anchors": []
      },
      "overlay_geometry": {},
      "truth_checks": []
    }
  ]
}
```

## Per-Room Field Contract

- `room_id`, `room_name`, and `room_index` identify the source room exactly as it appears in the canonical room JSON.
- `room_role` is a derived design label such as `threshold`, `corridor_transition`, `hub`, `traversal_shaft`, `reward_room`, or `pit_traversal`.
- `room_type` should preserve the room family (`internal` or `outdoor`) if the source authoring model provides it.
- `source_fields_used` records which room JSON fields contributed to the derived semantics.
- `semantics` is the designer-facing classification layer.
- `overlay_geometry` is the geometry-facing layer used for QA overlays and planner truth checks.
- `truth_checks` records what the extractor believes must be visually verified against the source layout.

## Extraction Expectations

| Category | Derived from | Must include | Must not do |
|---|---|---|---|
| `tops` | Platform top edges, floor-top spans, pit rims, moving-platform top paths, and any walkable roof/top plane implied by the polygon | Every walkable top plane that matters at gameplay scale | Invent a top plane where the source room has no walkable surface |
| `undersides` | Platform bottom faces, overhang bottoms, roof underside edges, underside lips of large floor spans | Any underside visible from the room camera or needed to explain shell depth | Turn the underside into a fake second floor or scenic ledge |
| `vertical_faces` | Polygon side edges, platform risers, door jambs, pit walls, shaft walls | All readable vertical shell faces that define enclosure or traversal shape | Collapse a face into a decorative background wash |
| `shell_surfaces` | The room polygon perimeter plus derived enclosure bands around walls, floor, ceiling, and major ledges | The actual enclosing shell that makes the chamber feel closed | Use scenic depth to stand in for shell structure |
| `openings` | Doors, removed edges, pit mouths, intentional voids, edge-link cutouts | Every threshold, mouth, and boundary break that changes traversal | Hide an opening inside decoration or ignore a removed edge |
| `corners` | Polygon vertices, platform endpoints, door shoulders, cavity turns, pit corners | Convex and concave corners that affect silhouette, lighting, or validation | Treat corners as optional polish only |
| `cavities` | Negative spaces inside polygon concavities, shafts, pits, alcoves, dead-end pockets | All enclosed voids and route-relevant pockets | Flatten negative space into background texture |
| `decor_safe_zones` | Interior regions outside gameplay lanes, door mouths, jump arcs, and platform tops | Regions safe for non-interactive dressing | Allow decoration to drift into route-critical space |
| `gameplay_exclusion_zones` | Platform tops, door mouths, player start landing zone, moving-platform paths, jump envelopes, pit openings, and edge-link corridors | Everything that must stay visually legible for play | Let shell art or props occlude traversal |
| `anchors` | Stable geometry landmarks such as corners, thresholds, platform centers, cavity rims, and shell midlines | Anchor points for planner overlays and review comparison | Invent anchors that are not grounded in the room JSON |
| `overlay_geometry` | The union of the above, rendered back into room space | Renderable shapes that QA can compare directly with the room JSON | Drift into abstract art or biome-only interpretation |

## Extraction Rules By Category

### Tops

- Tops are the first-class read for anything the player can stand on.
- They must be derived from room-local geometry, not from visual impressions.
- A room with no platforms may still have top shell bands, but it must not gain fake traversal tops.

### Undersides

- Undersides are the visible lower faces of geometry that hang over the play space.
- They are critical for tall shafts, wide halls, and any room where the shell needs to read as layered enclosure.
- If a room has no overhangs, the undersides list should be empty instead of speculative.

### Vertical Faces

- Vertical faces carry enclosure and support.
- They should capture walls, platform risers, door jambs, and shaft boundaries.
- Vertical faces are especially important for rooms where the polygon itself is the only readable shell.

### Shell Surfaces

- Shell surfaces are the enclosing mass that surrounds the playable chamber.
- They should be built from the polygon perimeter first and then refined by doors, pits, and platform adjacency.
- They must never be replaced by scenic depth language.

### Openings

- Openings are intentional breaks in the shell: doors, removed edges, pits, and edge-link mouths.
- Each opening must preserve its source edge or source object reference.
- If an opening is not supported by the room JSON, it should not appear in semantics.

### Corners

- Corners are structural turning points, not decorative accents.
- The extractor should preserve both convex and concave corners because they control silhouette and shell rhythm.
- Corner anchors are essential for overlay truth checks in irregular rooms.

### Cavities

- Cavities are the negative spaces that make a room feel like a chamber instead of a flat stage.
- A narrow shaft, a pit, or a dead-end alcove is a cavity only if the source geometry supports that read.
- Do not invent hidden cavities behind the room polygon.

### Decor-Safe Zones

- Decor-safe zones are the places where scenic dressing may live without competing with play.
- They should be derived after gameplay exclusion zones are reserved.
- If a decorative area overlaps traversal, it is not safe.

### Gameplay Exclusion Zones

- Gameplay exclusion zones protect the player-facing path from art drift.
- They should include door mouths, top planes, moving-platform paths, jump arcs, start/landing zones, and pit openings.
- The overlay must make these zones obvious to QA.

### Anchors

- Anchors are stable landmarks used for comparison and prompting.
- Good anchors are tied to geometry: corners, threshold centers, platform centers, rim points, and shell midpoints.
- Bad anchors are subjective visual impressions with no room-JSON source.

### Overlay Geometry

- Overlay geometry is the renderable truth layer.
- It should be directly traceable back to the room payload.
- If the overlay cannot explain itself from the source room JSON, it is too abstract to be trusted.

## QA Hand-off: Fixture And Overlay-Truth Checks

QA should run these checks on any room semantics output:

1. Compare the `overlay_geometry` against the raw room polygon first, not against the rendered art.
2. Verify that every door, removed edge, and edge link is represented as an opening or threshold anchor.
3. Verify that every platform contributes a top surface and, where relevant, an underside face.
4. Verify that no interior region outside the polygon is treated as extra room space.
5. Verify that decor-safe zones never overlap door mouths, platform tops, pit openings, or jump arcs.
6. Verify that the semantics file does not invent a player start, a platform, or a door when the source room does not contain one.
7. Verify that room-role labels are descriptive, but not authoritative enough to override the room JSON.

## Existing Repo Coverage To Reuse

The repo already contains real edge cases that should inform the semantics contract:

- [room-layout-data.json](/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json) room `R11` `Branch A Tunnel Shaft` is the best existing irregular-room path.
  - It has no platforms.
  - It has no doors.
  - It has no `playerStart`.
  - It has a narrow polygon, two edge links, and removed edges only.
- [room-layout-data.json](/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json) room `R2` `Central Hub` covers the opposite end of the spectrum.
  - It has four doors.
  - It has a moving platform.
  - It has a multi-vertex polygon and no `playerStart`.
- [room-layout-data.json](/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json) room `R7` `Branch C South Shaft` is a useful tall-shaft companion case.
  - It has stacked platforms.
  - It has upper and side thresholds.
  - It is useful for testing top and side opening semantics.

If a dedicated micro-fixture pack is added later, it should preserve those same edge classes instead of inventing new ones.

## Recommended Micro-Fixture Requirements

- One zero-platform shaft room with only polygon-boundary openings.
- One multi-door hub room with a moving platform.
- One tall shaft room with upper and side threshold anchors.
- One pit-heavy room that exercises cavities and exclusion zones.
- One room where the overlay must prove that `global` is ignored for geometry extraction.

## Scope Guard

This contract intentionally avoids changing production code.

It is a documentation and fixture scaffolding step so Development can implement the extractor against a stable target and QA can inspect the same truth layer every time.
