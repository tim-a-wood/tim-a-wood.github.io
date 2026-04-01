# Ashen Hollow Art Bible Foundation v0.1

Version: v0.1  
Date: 2026-04-01  
Owner: Creative Agent  
Intent: Establish the non-negotiable visual quality gate before production-scale asset creation.

---

## 1) Visual Identity Thesis

Ashen Hollow is a dark-fantasy metroidvania with a restrained, low-saturation base world and selective high-contrast signaling for danger, interactables, and progression landmarks.

- Base world language: ashen stone, oxidized metal, dead wood, cold fog, and ritual remnants.
- Emotional arc: quiet dread -> hostile intrusion -> corrupted intensity -> severe clarity near endgame spaces.
- Visual promise to player: readable traversal first, atmosphere second, decoration third.

Primary references in spirit (not imitation): Hollow Knight value restraint, Blasphemous icon discipline, and Ori-style light hierarchy used sparingly.

---

## 2) Master Palette

### 2.1 Core Palette (global)

| Token | Hex | Role | Allowed Use |
|---|---|---|---|
| `AH-INK-0` | `#07090B` | Near-black foundation | Deep voids, screen edge falloff, silhouette backing |
| `AH-INK-1` | `#0D1115` | Primary shadow mass | Cavities, underside planes, occlusion zones |
| `AH-ASH-2` | `#1A2127` | Dark midtone | Structural rock and masonry midtones |
| `AH-ASH-3` | `#2B343B` | Light midtone | Foreground surface planes, ledge readability |
| `AH-BONE-4` | `#4B5A63` | Edge light neutral | Material edges and light-facing bevels |
| `AH-FOG-5` | `#7E8E95` | Atmospheric lift | Distant planes and fog blend ramps |
| `AH-EMBER-6` | `#A85B32` | Warm danger accent | Fire, fresh hazard edge, active threat states |
| `AH-RUST-7` | `#7C3D2B` | Warm grime | Oxidation, blood-rust traces, old damage |
| `AH-VERDIGRIS-8` | `#2D6662` | Cool relic accent | Ancient machinery, inactive arcane traces |
| `AH-GLINT-9` | `#9FD6C7` | High-value focal accent | Rare pickups, key readability pings, eye guides |
| `AH-TOXIC-10` | `#6E8F2E` | Biological hazard accent | Spores, caustic flora, poison reads |
| `AH-ROYAL-11` | `#5A4E87` | Ability/ritual signal | Ability shrines, progression rituals |

### 2.2 Palette Usage Limits (enforced)

- Environment tiles: 70-80% from `AH-INK-0` to `AH-BONE-4`.
- Atmosphere layers: 15-25% from `AH-FOG-5` and muted variants.
- Accent budget per screen: 5-10% total, never more than two accent families at once.
- Pure highlight usage (`AH-GLINT-9`) capped to micro-areas: icon centers, spark hits, focal edges.
- Hard ban: introducing untracked one-off colors in production sprites.

### 2.3 Usage Matrix

| Visual Need | Primary | Secondary | Never Pair With |
|---|---|---|---|
| Traversable floor readability | `AH-ASH-3` | `AH-BONE-4` | `AH-FOG-5` as main floor value |
| Background depth | `AH-INK-1` | `AH-ASH-2` | `AH-GLINT-9` broad fill |
| Hazard telegraph | `AH-EMBER-6` | `AH-RUST-7` | `AH-VERDIGRIS-8` same asset state |
| Ancient mechanism | `AH-VERDIGRIS-8` | `AH-BONE-4` | `AH-EMBER-6` unless "overheated" variant |
| Ability altar | `AH-ROYAL-11` | `AH-GLINT-9` | `AH-TOXIC-10` |
| Bio-corruption | `AH-TOXIC-10` | `AH-RUST-7` | `AH-ROYAL-11` |

---

## 3) Silhouette Differentiation Rules

Silhouette must identify class before detail and color.

### 3.1 Universal Rules

- Read check scale: evaluate at 1x, 0.75x, and 0.5x capture sizes.
- Unique outer contour priority over interior detail.
- Max one dominant silhouette idea per entity.
- Internal contrast cannot be required to identify entity class.

### 3.2 Player Silhouette Rules

- Form language: tapered vertical body with asymmetric cloak/cloth break.
- Read anchors: distinct head notch, one leading shoulder mass, and clear foot break.
- Motion identity: forward-lean anticipation and cape tail direction must remain readable in idle/run/jump.
- Prohibited overlap: no enemy class may share player head-to-body ratio or cape profile.

### 3.3 Enemy Class Silhouette Rules

#### Grunt Enemies
- Broad lower mass, compressed upper profile.
- Lateral aggression shapes (hooks, spikes, or weapon wings).
- Must contrast player by wider stance and lower center of mass.

#### Agile Enemies
- Long diagonal contour; reduced torso mass.
- Read feature must be limb extension or tail line, not face detail.
- Must never mirror player cloak rhythm in run cycle.

#### Heavy/Elite Enemies
- Top-heavy geometry and stepped armor planes.
- Boxed shoulders, minimal taper.
- At least 1.4x player silhouette area when on same plane.

#### Bosses
- Three read points minimum: crown/mantle, weapon extremity, unique negative-space hole.
- Must remain identifiable in pure black fill against mid-gray background.
- Boss add-ons cannot create player-like profile at any frame.

### 3.4 Environment Silhouette Rules

- Traversable surfaces: long stable horizontals with predictable step cadence.
- Non-traversable decoration: broken contours and interrupted rhythm.
- Hazard silhouettes: sharp repeats (teeth, thorns, hooks), no rounded comfort curves.
- Door/transition silhouette: vertical framing with a distinct top marker to telegraph route logic.

---

## 4) Global Lighting and Material Response

### 4.1 Global Light Direction

- Key light direction default: upper-left at ~35 degrees.
- Fill: low-intensity cool bounce from lower-right.
- Rim light: reserved for interactables, player, bosses, and key path props.
- Exceptions must be biome-authored and documented; no per-asset arbitrary light direction changes.

### 4.2 Value Hierarchy

- Foreground playable plane: highest local contrast.
- Midground atmosphere: compressed contrast.
- Far background: value-clustered with fog lift.
- Rule: player must never be lower contrast than immediate hazard silhouette.

### 4.3 Material Response Rules

| Material | Highlight Behavior | Shadow Behavior | Texture Rule |
|---|---|---|---|
| Ash stone | Short, matte edge kicks | Broad soft pooling | Medium noise, low spec hits |
| Oxidized metal | Narrow directional glints | Hard terminator with grime bands | Controlled streaking, no mirror shine |
| Dead wood | Broken linear catches | Fibrous dark striations | Grain follows form direction |
| Wet surfaces | Thin high-value line + drip dots | Deep cool sink | Use sparingly for tension rooms |
| Bone/chitin | Waxy mids, clipped highlight tip | Purple-gray core shadows | Segment lines must aid form read |
| Corruption growth | Pulsed emissive nodes | Subsurface dark pockets | Edge glow only on active state |

### 4.4 Emissive and FX Rules

- Emissive colors allowed: `AH-GLINT-9`, `AH-EMBER-6`, `AH-ROYAL-11`, `AH-TOXIC-10`.
- Emissive occupies <= 4% of frame unless a scripted set-piece.
- Particle effects may break palette only for one-frame white core in impact flashes.

---

## 5) Biome-by-Biome Visual Grammar (Foundation Set)

This foundation defines initial grammar for five biome families. Final naming can change; grammar should remain.

### 5.1 Cinder Approach (Entry Biome)

- Dominant values: `AH-INK-1`, `AH-ASH-2`, `AH-ASH-3`.
- Accent family: `AH-RUST-7` with sparse `AH-EMBER-6`.
- Shape language: collapsed arches, fractured buttresses, wind-cut flats.
- Lighting mood: low-angle dusk bleed, long shadows, sparse warm brazier pockets.
- Readability mandate: path edges brighter than walls by one value step.

### 5.2 Weeping Vaults (Subterranean Stone)

- Dominant values: `AH-INK-0`, `AH-INK-1`, `AH-BONE-4`.
- Accent family: `AH-VERDIGRIS-8`.
- Shape language: vertical shafts, hanging roots/chains, drip-fed basins.
- Lighting mood: cold directional shafts with low fog bloom.
- Hazard language: waterline shimmer + spike silhouettes below sightline.

### 5.3 Thorn Reliquary (Bio-Corrupted Zone)

- Dominant values: `AH-ASH-2`, `AH-ASH-3`, `AH-TOXIC-10` (controlled).
- Accent family: `AH-TOXIC-10` + limited `AH-RUST-7`.
- Shape language: invasive overgrowth, barbed radial bursts, tendon bridges.
- Lighting mood: underlit toxicity with intermittent breathing glow.
- Hazard language: repeating thorn cadence; poisonous reads pre-contact.

### 5.4 Iron Ossuary (Militant Ruin/Factory Hybrid)

- Dominant values: `AH-INK-1`, `AH-ASH-2`, `AH-BONE-4`.
- Accent family: `AH-VERDIGRIS-8` plus overheated `AH-EMBER-6` states.
- Shape language: riveted beams, pressure doors, bone-stack motifs.
- Lighting mood: directional industrial slashes with furnace punctures.
- Readability mandate: moving machinery contrast must not hide enemy reads.

### 5.5 Hollow Throne (Late-Game Ritual Core)

- Dominant values: `AH-INK-0`, `AH-ASH-2`, `AH-ROYAL-11`.
- Accent family: `AH-ROYAL-11` + focal `AH-GLINT-9`.
- Shape language: severe symmetry broken by ritual damage.
- Lighting mood: stark top light with deep vignette wells.
- Encounter framing: bosses centered by negative space and constrained emissive arcs.

---

## 6) Environment, Enemy, and Player Separation Rules

- Player always occupies a unique value lane against walkable planes.
- Enemy telegraph colors never overlap interactable objective colors in the same room state.
- Background motifs cannot share silhouette rhythm with active hazards.
- Collectible/read-important objects require one of: hue separation, value halo, or motion contrast.

---

## 7) Production Quality Gate (Pass/Fail)

Any asset entering the game must pass all checks:

1. Palette compliance: only approved tokens, with biome rules respected.
2. Silhouette class clarity at game scale (quick black-fill test).
3. Lighting consistency with global or documented biome override.
4. Material response matches assigned material family.
5. Visual grammar fit for assigned biome.
6. Gameplay readability: platform/hazard/interactable hierarchy intact.

Failure on any single check = reject for revision.

---

## 8) Implementation Notes for PDF Export

- This document is markdown-first and copy-paste ready for Google Docs, Notion, or Word export to PDF.
- Suggested export title: `Ashen Hollow Art Bible Foundation v0.1`.
- If a repository PDF artifact is required, generate only after explicit founder approval to add/commit binary output.

---

## 9) Known Open Decisions for v0.2

- Confirm canonical biome names with Narrative and Game Director.
- Lock player fantasy before final player silhouette variants.
- Approve "danger accent hierarchy" against final combat telegraph standards.
- Decide whether any biome gets a sanctioned secondary accent family.
