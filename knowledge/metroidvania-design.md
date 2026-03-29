# Metroidvania Design Principles

This knowledge file gives specialist agents enough domain context to reason about the product correctly.

## Core Loop
1. Player explores interconnected rooms
2. Locked paths gate progression (doors, ability checks)
3. New abilities unlock previously inaccessible areas (backtracking)
4. World graph must be carefully designed to prevent sequence-breaking or softlocks

## Room Design
- Rooms have clear entry/exit doors with defined connections
- Entity types: Platform, Door, Vertex (path points), Key (collectible), Ability (power-up), Mover (moving platform), Start Point
- Room dimensions and spawn points are fixed at creation
- Doors must be paired — each door in one room connects to a door in another room

## World Graph Design
- The world is a directed graph of rooms connected by doors
- Gating logic: some doors require keys or abilities to open
- Reachability analysis: every room should be reachable from start (no orphaned rooms)
- Sequence break risk: unintended paths that bypass gating logic

## Common Design Failures
- **Softlock:** Player reaches a state where they cannot progress (trapped room, key inaccessible)
- **Orphaned room:** Room that cannot be reached from any path from start
- **Unbalanced gating:** Too many locked doors early, or gating that doesn't match ability acquisition order
- **Inconsistent entity density:** Some rooms are over-cluttered, others feel empty

## AI Assistance Opportunities
- AI can suggest entity placements based on room geometry and design brief
- AI can validate room graph for softlock risk and orphaned rooms
- AI can generate room variants for A/B testing
- AI cannot reliably maintain long-range consistency across the full world graph without schema validation
