# Art Bible v0.3 — Change Specification for Handover

**Document type:** Change specification — not a draft  
**From:** Creative Agent  
**Date:** 2026-04-09  
**Input:** Art Bible v0.2 (`artifacts/ashen-hollow-art-bible-v0.2.md`)  
**Output target:** `artifacts/ashen-hollow-art-bible-v0.3.md`  
**Trigger:** Founder interview session — full creative direction pass  

---

## How to use this document

This spec defines every change required to produce v0.3 from v0.2. It is structured as a section-by-section diff with explicit instructions. Where v0.2 content is being replaced entirely, the old content is noted and the new content is specified in full. Where v0.2 content is being extended, the addition is marked clearly.

All placeholder names are marked **[PLACEHOLDER]** and must be clearly flagged in the final document.

---

## Global changes (apply throughout)

- Replace all instances of **"Ashen Hollow"** (as game title) with **"[GAME TITLE TBD]"** with a footnote: *"Ashen Hollow" is a confirmed AI-generated placeholder. A dedicated naming session with Narrative and Game Director is required before any public-facing material is produced.*
- Replace all instances of **"the player"** (where referring to player fantasy) with **"the knight"** or **"the Order knight"** where contextually appropriate.
- Add a document-level note at the top: *v0.3 supersedes v0.2. Biomes, player identity, world lore, and palette have all changed materially.*

---

## Section 1 — Visual Identity Thesis

### 1.1 Replace the thesis paragraph

**Remove:** The existing thesis paragraph.

**Replace with:**

> [GAME TITLE TBD] is a dark-fantasy metroidvania about a knight of the Order of the Sun — a survivor of a catastrophic plague of darkness — whose goal is to ascend from the deepest darkness back to the light. The world was built by an order devoted to the sun, slowly rotted, and then broke catastrophically. What remains is a ruined civilization whose architecture still carries the memory of light.
>
> The game's central visual contract is a **dark-to-light progression axis**. The player begins at the lowest, darkest point of the world and ascends toward the sun. As the world grows brighter and more beautiful, enemies grow darker and more grotesque. Three simultaneous arcs reinforce this at all times: the world brightening, the player's own sun iconography revealing, and the enemies intensifying.
>
> Visual promise to player: readable traversal first, atmosphere second, decoration third.

### 1.2 Replace the primary references line

**Remove:** Hollow Knight / Blasphemous / Ori reference line.

**Replace with:**

> Primary references in spirit (not imitation): Hollow Knight's interconnected world structure and tonal restraint. Blasphemous's icon discipline and religious iconography. Dark Souls' environmental storytelling and tragic lore — specifically Solaire of Astora as the player archetype. The game departs from Dark Souls in tone and does not copy it directly.

### 1.3 Replace the mood spread table (§1.1)

**Remove:** The five-biome mood plate table referencing old concept images.

**Replace with:** New five-biome table using canonical concept plates:

| Flooded Prison | Bone Warrens | Castle Nave | Ruined Belfry | The Solarium |
|---|---|---|---|---|
| ![Flooded Prison](art-bible/concepts/biome-01-flooded-prison.png) | ![Bone Warrens](art-bible/concepts/biome-02-bone-warrens.png) | ![Castle Nave](art-bible/concepts/biome-03-castle-nave.png) | ![Ruined Belfry](art-bible/concepts/biome-04-ruined-belfry.png) | ![The Solarium](art-bible/concepts/biome-05-solarium.png) |

*Biome order = vertical world axis. Flooded Prison is the lowest point. The Solarium is the apex.*

---

## Section 2 — Master Palette

### 2.1 Add three new tokens to the core palette table

Insert the following three rows into the palette table after `AH-ROYAL-11`:

| Sample | Token | Hex | Role | Allowed Use |
|---|---|---|---|---|
| — | `AH-SOLAR` | `#C4962A` | Player sun iconography + endgame world light | Player tabard sun emblem (all reveal states), Ruined Belfry sun accent, The Solarium dominant. **Never used for hazards or enemies.** |
| — | `AH-ARCANE` | `#3A7BD5` | Mystical/rune accent | Bone Warrens rune glow, magical interactive elements. Never used for sky or water. |
| — | `AH-SKY` | `#7EB8D4` | Open sky atmosphere | Ruined Belfry sky. Never used underground. |

*Swatch PNGs to be generated via `scripts/generate_art_bible_swatches.py` after hex values are confirmed by founder.*

### 2.2 Update palette usage limits

Add the following line to §2.3:

> - `AH-SOLAR` is **reserved** for the player's sun iconography and the endgame world palette. It must not appear on enemies, hazards, or non-Order architecture except as a faded/worn trace indicating pre-fall Order presence.

### 2.3 Update the usage matrix (§2.4)

Add the following rows:

| Visual Need | Primary | Secondary | Never Pair With |
|---|---|---|---|
| Player sun iconography | `AH-SOLAR` | `AH-GLINT-9` | Any enemy or hazard token |
| Open sky (Ruined Belfry) | `AH-SKY` | `AH-SOLAR` | `AH-ARCANE` |
| Mystical rune glow | `AH-ARCANE` | `AH-BONE-4` | `AH-TOXIC-10`, `AH-EMBER-6` |
| Castle Nave stained glass | Spectrum exception — see §5.3 note | — | Must be contained to windows and book spines only |

---

## Section 3 — Silhouette differentiation rules

### 3.1 Replace player silhouette rules (§3.2) entirely

**Remove:** All existing player silhouette rules.

**Replace with:**

#### Player — Order of the Sun Knight

The player is a knight of the Order of the Sun. Their identity is defined by:

- **Armour form:** Structured knightly plate armour. Broader shoulder plates, disciplined geometry. Not a flowing wraith — a trained warrior. Presence and weight communicated through proportion.
- **Tabard:** A cloth tabard worn over the armour, bearing the Order's sun emblem. This is the primary canvas for the visual progression arc (see §3.2.1).
- **Sun iconography:** Eight-pointed sun wheel, radiating rays. Present on the tabard, optionally echoed on shoulder plates and helmet.
- **Movement identity:** Fast and precise — the armour does not slow them. Quick acceleration, sharp stops. Weight lives in combat actions (attacks, landings after falls), not traversal.
- **Silhouette anchors:** Distinct helmet profile, structured shoulder mass, tabard break at the hip, clear foot plant.
- **Prohibited overlap:** No enemy class may share the structured shoulder-to-hip ratio or the tabard cloth break.

#### 3.2.1 Player visual progression arc — THREE STATES

This is a core art bible rule. The player has three distinct visual states that must be designed, documented, and respected across all art.

**State 1 — Hidden (game start, Flooded Prison and Bone Warrens)**
- Sun iconography on tabard is concealed or illegible — covered in grime, darkness, or deliberate obscurement.
- Tabard is dark, worn, heavily weathered. The Order's colours are not visible.
- The player reads as an anonymous armoured figure. The sun is a secret they carry.
- AH-SOLAR: not present on player.

**State 2 — Emerging (mid-game, Castle Nave and Ruined Belfry)**
- Tabard begins showing its original colour. Sun emblem partially visible — the grime and damage clearing.
- The sun iconography is there if you look, but not yet blazing.
- AH-SOLAR: appears at low opacity on tabard emblem only.

**State 3 — Revealed (endgame, The Solarium)**
- Tabard fully restored. Sun emblem clear, vivid, blazing.
- The knight is visibly a figure of light. The iconography reads instantly.
- AH-SOLAR: full strength on tabard and optionally armour edge details.

**Crosswalk requirement:** The specific narrative/progression triggers for each state transition must be defined by the Game Director before player sprite production begins. See `game-director-status.json` priority #3.

---

## Section 4 — Global lighting and material response

### 4.1 Add a light progression rule (new subsection after §4.1)

**New §4.1.1 — World light progression:**

> The game's light temperature and intensity follow the vertical world axis:
>
> - **Flooded Prison:** Amber lantern only. No golden-white present. The only warmth is the single hanging lantern. The rest of the space is cold and dark.
> - **Bone Warrens:** Multiple warm torch sources. First traces of golden-white beginning to appear. AH-ARCANE blue from mystical elements provides cool contrast.
> - **Castle Nave:** Golden-white sunlight dominant, entering through stained glass windows in dramatic shafts. The most colourful biome in the game — stained glass spectrum permitted on windows and book spines only.
> - **Ruined Belfry:** Full outdoor golden-white, sky blue present. The sun is physically present and dominant. AH-SOLAR and AH-SKY are the primary accent family here.
> - **The Solarium:** Monotone golden-white. The only colour family is the solar spectrum. No accent diversity — the simplicity is intentional and earned.
>
> Rule: each biome must read as lighter than the one below it on the vertical axis.

---

## Section 5 — Biome-by-biome visual grammar

### 5.0 Replace the section header note

**Remove:** *"Grammar is canonical; display names may change with Narrative / Game Director."*

**Replace with:**

> Biome names are working production names. The game title is **[PLACEHOLDER]** — see global note. Biome names are not confirmed for public use until the game title is locked.
>
> Biome order follows the **vertical world axis** — Flooded Prison is the lowest, darkest point. The Solarium is the apex. The player generally ascends through this order in a Hollow Knight-style interconnected structure (non-linear with backtracking, but with a clear upward direction of progression).

### 5.1 Replace all five biome entries entirely

---

#### Biome 1 — Flooded Prison *(start / lowest point)*

![Flooded Prison](art-bible/concepts/biome-01-flooded-prison.png)

- **Dominant values:** `AH-INK-0`, `AH-INK-1`, `AH-ASH-2`
- **Light source:** Single amber lantern only. No sunlight. No golden-white.
- **Accent family:** Mossy green — `AH-TOXIC-10` at low opacity on stone surfaces, waterline, and cell walls. Reads as organic decay, not hazard.
- **Shape language:** Stone arched corridors, rusted iron bar cells, hanging chains, flooded floor with water reflection, icicle drips from ceiling.
- **Lighting mood:** Near-total darkness punctuated by one amber lantern. The lantern reflection on the water is the primary light read.
- **Environmental storytelling:** This is the Order's old prison — cells still locked, some open. Evidence of the slow rot: moss, water ingress, structural failure over decades before the catastrophic break.
- **Hazard language:** Water depth unknown, cell bars blocking path, chain obstacles.
- **Readability mandate:** The lantern must be the visual anchor of every room. Player silhouette reads against the lantern glow.

---

#### Biome 2 — Bone Warrens *(low-mid)*

![Bone Warrens](art-bible/concepts/biome-02-bone-warrens.png)

- **Dominant values:** `AH-INK-1`, `AH-ASH-2`, `AH-ASH-3`
- **Light sources:** Wall-mounted torches (warm amber), floor lanterns. Multiple sources — more light than Flooded Prison.
- **Accent family:** `AH-ARCANE` (mystical blue) for rune glyphs, magical interactive elements, and arcane residue on stone. Subtle — never dominant.
- **Secondary accent:** Torch warm (`AH-EMBER-6` for active flame only).
- **Shape language:** Natural cave rock carved into burial niches stacked floor to ceiling, filled with bones and skulls. Stone sarcophagi on the ground. Stalactites. Water traces on the floor (connects visually to Flooded Prison below).
- **Lighting mood:** Warmer and more present than Flooded Prison but still largely dark. The AH-ARCANE blue provides cool contrast against the torch warmth.
- **Environmental storytelling:** The Order's burial warrens. Their dead are here. The arcane rune glyphs are Order funerary markings, not enemy markings. The Deep's influence is present but the Order's identity is still legible.
- **Rune/glyph rule:** Arcane glyphs are geometric symbols only — no legible text or letters. AH-ARCANE glow, never AH-ROYAL-11.
- **Hazard language:** Bone-collapse platforms, confined cave passages, ceiling stalactite drops.

---

#### Biome 3 — Castle Nave *(mid / major transition)*

![Castle Nave](art-bible/concepts/biome-03-castle-nave.png)

- **Dominant values:** `AH-ASH-2`, `AH-ASH-3`, `AH-BONE-4` (significantly lighter than biomes 1–2)
- **Light sources:** Golden-white sunlight through stained glass windows — the first real sunlight in the game. Dramatic shaft lighting across stone floors.
- **Accent family — stained glass exception:** This is the only biome permitted a spectrum of colours beyond the palette. Stained glass windows and book spines on shelves may use a controlled range of muted jewel tones. These colours are **contained to windows and book spines only** — never on structural surfaces, enemies, or props.
- **Secondary accent:** Bright green ivy/vines (`AH-TOXIC-10` at higher saturation than Flooded Prison — here it reads as life, not decay). Climbing pillars and walls.
- **Shape language:** Gothic cathedral nave, massive pointed arch windows, tall stone pillars, winding castle corridors leading up to the nave, bookshelves lining lower corridor walls, stone floors with golden light pools.
- **Lighting mood:** The most visually complex biome. Golden-white shafts are the dominant light, coloured by stained glass as they pass through. The space is warm and grand despite its ruin.
- **Environmental storytelling:** The Order's great library and cathedral. Bookshelves with varied spines tell of a civilization of knowledge. The cathedral nave is the Order's primary worship space — the sun wheel altar is here. This is the major boss arena.
- **Boss arena note:** The cathedral nave at the end of this biome is a designed boss encounter space. The golden-white light and sun wheel altar are the visual frame for that encounter.
- **Readability mandate:** Boss must remain readable against the complex stained glass backdrop. Enemy silhouette value must contrast the lit floor plane.

---

#### Biome 4 — Ruined Belfry *(high-mid / first outdoor)*

![Ruined Belfry](art-bible/concepts/biome-04-ruined-belfry.png)

- **Dominant values:** `AH-ASH-3`, `AH-BONE-4`, `AH-FOG-5` (significantly lighter — first outdoor biome)
- **Light source:** Direct golden-white sunlight from above. Outdoor, no ceiling. The sun is physically present for the first time.
- **Primary accent family:** `AH-SOLAR` (sun gold) dominant. `AH-SKY` (open sky blue) for sky atmosphere and background.
- **Shape language:** Two massive gothic stone towers with catastrophically shattered tops, broken open to the sky. Rose window carvings on tower faces — one intact, one shattered. Fallen arches and rubble below. Ivy and green growth on stone. Debris floating in golden light.
- **Lighting mood:** Overwhelming after the darkness below. Ethereal — light rays visible, dust particles in sunlight. The golden-white is at its strongest outdoor intensity here.
- **Environmental storytelling:** The Order's belfry — its towers were the highest point of the complex. The catastrophic break shattered the tops and opened them to the sky. The sun wheel carvings on the towers are the Order's identity made architectural. One intact, one shattered = the state of the Order itself.
- **Player state:** The knight's tabard should be in State 2 (Emerging) by this biome — the sun emblem partially visible. The visual echo between the player's emerging iconography and the carved sun wheels on the towers is intentional.
- **Hazard language:** Exposed high platforms, wind-pushed traversal, falling debris from broken stonework.

---

#### Biome 5 — The Solarium *(apex / endgame)*

![The Solarium](art-bible/concepts/biome-05-solarium.png)

- **Dominant values:** `AH-BONE-4`, `AH-FOG-5`, and `AH-SOLAR` — the lightest value range in the game.
- **Light source:** Single central oculus in the dome ceiling, pouring a column of golden-white light directly onto the altar. The most intense and pure light in the game.
- **Accent family:** Monotone solar. `AH-SOLAR` only. No secondary accent family — the restraint is deliberate and earned. This biome has one colour and it is the sun.
- **Shape language:** Circular solar temple. Grand stone columns in a ring around a central altar. Dome ceiling with oculus. Sun wheel altar at center, directly under the light shaft. Stone floor catching the light warmly.
- **Lighting mood:** Sacred stillness. Triumphant. After five biomes of darkness and ascent, the light is total and unchallenged here. The edges of the space fade to shadow but the centre is brilliantly lit.
- **Environmental storytelling:** The Order's highest sanctuary — the room built to be closest to the sun. It was never destroyed, never corrupted. The Deep never reached here. This is what the Order was building toward.
- **Player state:** The knight's tabard must be in State 3 (Revealed) here — the sun emblem blazing. The player is visually completing the same arc as the world.
- **No enemies in concept art:** The Solarium concept plate shows no enemies deliberately. Enemy design for this biome will be specified separately.
- **Boss note:** The final boss encounter with the being behind The Deep **[PLACEHOLDER]** occurs here. Their design must be specified separately and must earn the tragedy established in the world lore. See §7 open decisions.

---

## Section 6 — Enemy faction structure (new section — absent from v0.2)

### Add new §6.2 — Enemy factions

> The world's enemies belong to two distinct visual tiers:
>
> #### Tier 1 — [The Sunken] **[PLACEHOLDER NAME]**
> Former inhabitants of the world, claimed by The Deep **[PLACEHOLDER NAME]**. These were people, creatures, or constructs before the darkness took them.
>
> - **Visual identity:** Corrupted versions of what they were. Biome-specific — each biome's Sunken look different because they were different things before.
> - **Design rule:** Their original identity must still be legible beneath the corruption. You should be able to read what they were.
> - **Color:** The Deep's darkness has drained their colour. Low saturation, heavy `AH-INK` values, corruption traces in `AH-TOXIC-10` or `AH-RUST-7`.
> - **Animation:** Low-frame expressionist (4–8 frames). Movement feels wrong — snappy, unpredictable, broken. The corruption shows in how they move.
> - **Distribution:** Biome-specific. They do not cross biomes except where the narrative requires it.
>
> #### Tier 2 — [The Servants] **[PLACEHOLDER NAME]**
> Rare, powerful entities deliberately shaped by the being behind The Deep. Almost mythical — encountered as side bosses, not common enemies.
>
> - **Visual identity:** Grander than the Sunken. They carry the being's visual language more directly — ancient, sorrowful, intentional. Traces of what they were before the being's influence should be buried in their design.
> - **Design rule:** They must read as tragic, not purely evil. They were something else before.
> - **Color:** Deeper darkness than the Sunken. `AH-INK-0` dominant with selective `AH-ROYAL-11` traces — they carry something of the ritual/arcane.
> - **Animation:** Grand held frames with explosive transitions. Slow and still, then sudden. Makes them feel mythical.
> - **Distribution:** Cross-biome. Their appearance in a biome is an event, not a standard encounter.
>
> #### Boss tier — The Final Form
> The being behind The Deep **[PLACEHOLDER]** appears in physical form only in The Solarium. Design deferred — must be specified separately and must synthesise all presence language established across the five biomes. The tragedy must be visible in the form.

### Update §6 enemy/environment separation rules

Add to existing separation rules:

> - Tier 1 enemies (Sunken) get progressively darker and more grotesque as the player ascends — in direct visual contrast to the brightening world.
> - Tier 2 enemies (Servants) carry a consistent visual language regardless of biome.
> - Neither tier may use `AH-SOLAR` in any state.

---

## Section 7 — Animation and motion language (new section — absent from v0.2)

**Add new §7 — Animation and motion language** (insert before current §7 Quality Gate, which becomes §8):

### 7.1 Frame count philosophy

| Entity type | Frame count | Rationale |
|---|---|---|
| Player | 8–12 frames | Premium treatment. The tabard and sun iconography must read clearly at speed. Cloth animation must remain legible during fast movement. |
| Tier 1 enemies (Sunken) | 4–8 frames | Corruption reads in the wrongness of movement. Low-frame achieves this naturally. |
| Late-game powerful enemies | Lowest frame count deliberately | The most powerful enemies feel the most unsettling in motion — jerky, too-still between bursts. |
| Tier 2 enemies (Servants) | Grand held frames + explosive transitions | Slow and still, then sudden. Mythical and dangerous. |

### 7.2 Physics and movement feel

**Player movement:** Fast and responsive base. Quick acceleration, sharp stops, responsive jumps. The armour does not slow them — they are a trained warrior.

**Weight lives in combat only:**
- Attack actions carry commitment frames.
- Heavy hits have recovery.
- Landings after normal jumps: quick, single impact frame.
- Landings after long falls: weighted recovery.

**Dodge/evade:** Fast and crisp. The contrast between weighted combat and sharp evasion makes both feel better.

**Cloth/tabard animation rule:** The tabard must remain readable at full movement speed. Cloth animation cannot obscure the sun iconography in State 2 or State 3.

### 7.3 Easing and timing conventions

- Base movement transitions: snappy easing (ease-out, short duration)
- Combat attacks: ease-in to commitment frame, hard stop at impact
- Enemy Sunken movement: irregular timing, no smooth easing — the wrongness is the point
- Servant movement: extremely slow ease-in to held pose, instantaneous explosive release

---

## Section 8 — Production quality gate

### Add two new checks to the quality gate

After existing check 6, add:

> 7. Player visual state consistency: player art must match the correct progression state (Hidden / Emerging / Revealed) for the biome it depicts.
> 8. Enemy darkness gradient: enemies in later biomes must read darker and more grotesque than equivalent enemies in earlier biomes.

---

## Section 9 — Open decisions for v0.4

**Replace** the current §9 open decisions list entirely:

> ### Placeholder names requiring founder decision:
> - **Game title** — "Ashen Hollow" is confirmed placeholder. Dedicated naming session required.
> - **The Deep** — working name for the antagonist darkness force. Placeholder.
> - **The Sunken** — working name for Tier 1 enemies. Placeholder.
> - **The Servants** — working name for Tier 2 enemies. Placeholder.
> - **The being behind The Deep** — no name yet. Requires narrative development.
>
> ### Design decisions pending Game Director:
> - Player visual state transition triggers — which narrative/progression event activates each state (Hidden → Emerging → Revealed). See `game-director-status.json` priority #3.
> - Final boss visual design — deferred until lore and narrative are further developed.
>
> ### Art decisions deferred to v0.4:
> - Confirm `AH-SOLAR`, `AH-ARCANE`, `AH-SKY` hex values with swatch review.
> - Specify enemy design per biome for Tier 1 (Sunken).
> - Specify Tier 2 (Servant) encounter design — visual language and encounter framing rules.
> - Castle Nave stained glass spectrum — define the permitted jewel tone range explicitly.
> - Room graph crosswalk — map biomes to room layout editor once level design locks.
> - Biome names confirmed for public use pending game title lock.

---

## Assets to update

| Asset | Action |
|---|---|
| `artifacts/art-bible/concepts/biome-01-flooded-prison.png` | In place — founder approved |
| `artifacts/art-bible/concepts/biome-02-bone-warrens.png` | In place — founder approved |
| `artifacts/art-bible/concepts/biome-03-castle-nave.png` | In place — founder approved |
| `artifacts/art-bible/concepts/biome-04-ruined-belfry.png` | In place — founder approved |
| `artifacts/art-bible/concepts/biome-05-solarium.png` | In place — founder approved |
| `artifacts/art-bible/swatches/AH-SOLAR.png` | Generate via swatch script after hex confirmed |
| `artifacts/art-bible/swatches/AH-ARCANE.png` | Generate via swatch script after hex confirmed |
| `artifacts/art-bible/swatches/AH-SKY.png` | Generate via swatch script after hex confirmed |
| Old placeholder concept PNGs (`ashen-hollow-concept-*.png`) | Archive — do not delete, they are v0.2 references |

---

## Minor creative decisions made autonomously

*These were made by Creative without founder input. Review and override as needed — see companion document `docs/creative-minor-decisions-v0.3.md`.*

- Proposed `AH-SOLAR` hex as `#C4962A` — warm gold distinct from `AH-EMBER-6` danger orange.
- Proposed `AH-ARCANE` hex as `#3A7BD5` — mid-range blue, mystical not icy.
- Proposed `AH-SKY` hex as `#7EB8D4` — pale open sky, distinct from `AH-ARCANE`.
- Recommended the Bone Warrens water floor trace as a visual bridge to Flooded Prison.
- Recommended Castle Nave as the major boss arena biome (stained glass light + sun altar = natural encounter frame).
- Recommended that the Ruined Belfry sun wheel carvings (one intact, one shattered) visually represent the state of the Order — creative shorthand not explicitly requested by founder.
