# Level Design Specification: Labyrinthian Metroidvania Room

## Overview

Single-screen (bounded) metroidvania-style room: walls, floors, ceilings, and a corridor platform behind a locked door. Consistent spacing, no player stuck, 2D platformer best practices. Phaser 3, arcade physics, tile-based geometry, fixed world size.

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

Example list (left-edge X in code; spec gives center X so stored as center−16):

- (0, 1100, 8) – Corridor
- (320, 1120, 2), (500, 1080, 3), (750, 1100, 2), (1000, 1060, 2), (400, 1000, 2), (650, 980, 3), (950, 1020, 2), (300, 920, 3), (600, 900, 2), (900, 940, 3), (450, 820, 2), (750, 840, 3), (1050, 800, 2), (350, 720, 3), (700, 700, 2), (500, 600, 2), (850, 620, 3), (400, 520, 2), (700, 500, 3), (1000, 540, 2), (550, 400, 2), (900, 420, 3), (1050, 350, 4), (800, 380, 2), (1100, 240, 2), (1450, 120, 3)

Guidelines: platforms 2–4 tiles; vertical gaps 80–150 px; horizontal gaps &lt; 200–300 px; double-jump required for highest ledges.

---

## Best Practices

- All geometry on 32×32 grid (platforms 14 px thick).
- Vertical passages ≥ 48 px; horizontal ≥ 32 px.
- No dead ends; every platform reachable and returnable.
- Gradual difficulty; tints for orientation.
- Refresh static bodies after placement.

---

## Summary

Floor and ceiling full width; right wall full height; left wall stops for corridor. Corridor (8 tiles, y=1100) leads to locked door (248, 1137). Key on high ledge (1450, 120, 3); relic on path. Labyrinth of floating platforms for vertical exploration.
