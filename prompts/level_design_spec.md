# Level Design Specification: Hollow Knight Cave Room

## Overview

Single-screen (bounded) metroidvania-style room with a Hollow Knight-like cave structure: strong landmarks, overlapping shelves that feel carved out of one mass, layered vertical traversal, and a clear return route to the left-side door. Phaser 3, arcade physics, tile-based geometry, fixed world size.

---

## Tile Specifications

- **Tile Size:** 32×32 px (floor and wall blocks).
- **Platform Thickness:** 14 px (floating ledges).
- **Player Size:** ~28×40 px. Vertical clearance ≥ 48 px for comfortable movement.

---

## World Boundaries

- **World Width:** 1600 px.
- **World Height:** 1200 px.
- Physics world and camera clamped to these bounds; all solid geometry within.

---

## Floor and Ceiling

- **Floor:** Continuous at bottom. Center Y = `WORLD_HEIGHT - 16` = 1184 (bottom edge 1200).
- **Ceiling:** Continuous at top. Center Y = 16 (top edge 0).

---

## Walls

- **Left wall:** From just below ceiling down to corridor opening. Tile centers from y = 48 to y = 1077; bottom of wall flush with corridor platform top (1093).
- **Right wall:** Full height, tile centers from 48 to 1168.

---

## Corridor Platform (Bottom-Left)

- **Purpose:** Low-ceiling corridor to locked door.
- **Position:** X starts at 0 (first tile center 16), Y center 1100, length 8 tiles (256 px). Platform bottom 1107; ground 1184; clearance 77 px.
- **Relationship:** Corridor top (1093) flush with left wall bottom (1093).

---

## Locked Door

- **Position:** x = 248, y = 1137 (center). Height 61 px; top ~1106.5, bottom ~1167.5. Blocks corridor until key is used.

---

## Additional Floating Platforms (LABYRINTH_LEDGES)

Current list (left-edge X in code):

- (0, 1100, 8) – Corridor
- (192, 1068, 10) – Threshold shelf
- (416, 1012, 11) – Lower cave floor
- (256, 936, 3) – Relic alcove branch
- (640, 952, 11) – Mid-room shelf chain
- (864, 892, 10) – East rise
- (1088, 824, 8) – Upper east shelf
- (1184, 748, 6) – Upper lip
- (1024, 664, 8) – Return passage
- (832, 580, 9) – West upper shelf
- (608, 500, 8) – West middle shelf
- (384, 420, 7) – Lower return shelf
- (672, 340, 5) – Shrine step
- (928, 260, 4) – Key approach
- (1120, 180, 4) – High gated key perch

Guidelines: most platforms should read as one connected cave mass rather than isolated pads; use long overlapping shelves, only a few branch ledges, and keep the relic as a small side-branch reward while the key remains double-jump gated.

---

## Best Practices

- All geometry on 32×32 grid (platforms 14 px thick).
- Vertical passages ≥ 48 px; horizontal ≥ 32 px.
- No dead ends; every platform reachable and returnable.
- Gradual difficulty; tints for orientation.
- Refresh static bodies after placement.

---

## Summary

Floor and ceiling stay full width; right wall full height; left wall stops for the corridor. Corridor `(0, 1100, 8)` leads to locked door `(248, 1137)`. The player climbs onto a continuous cave shelf network, detours into the relic alcove `(304, 902)`, pushes up through the east shelves, crosses the upper return passage, then double-jumps to the key perch `(1200, 146)` before returning to the door.
