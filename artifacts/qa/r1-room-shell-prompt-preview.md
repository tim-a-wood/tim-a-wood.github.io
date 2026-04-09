# R1 Room Shell Prompt (Uncropped Generation)

Source: latest `R1-room-shell` attempt recorded in `room_layout.json`.

## Prompt Text

Create a single 2D metroidvania environment shell component from the attached references (silhouette geometry guide + approved room preview).

Preserve the same biome family, silhouette role, and composition discipline.
Do not redesign the piece.
Do not invent a new scene.
Only adapt it to the requested fit, dimensions, orientation, and subtle local wear.

Room footprint conditioning: A footprint schematic is included in the reference images (dark field with neutral geometry markers only). It maps this room at the exact output resolution: the boundary marker indicates the walkable chamber contour in side view; fill indicates playable volume. Compose fog, depth, and architecture so the result respects that footprint, including non-rectangular or L-shaped outlines. Do not substitute a generic centered rectangular nave when the outline is irregular. Chamber bounds (room space): width 1280 px, height 880 px.

Reference usage contract for room_shell_foreground: use the silhouette reference to lock border shape and occupied shell geometry. Use the approved room preview reference only for palette, tone, and material family. Do not copy composition objects, camera framing, or scenic focal forms from the preview. Do not add decorative rim lines or UI-like accent strokes along the shell inner boundary; stone cut only.

Component type: room_shell_foreground
Variant family: foreground
Exact output width: 1280 px
Exact output height: 880 px
Orientation: full
Runtime placement: x=800 y=1040 origin=(0.50,1.00)
Runtime display size: width=1280 px height=880 px
Room mood: Sacred decay, damp, low-key, enclosing, calm traversal.
Room lighting: low-key lighting, single focal glow near floor, restrained warm-cool value shifts.
Room description: A damp ruined gothic hall built as enclosing architecture rather than a focal shrine scene. Heavy side arches, recessed wall bays, and fractured pillars define the room shell while the middle lane stays open and calm for traversal. Depth comes from far hall recession, soft fog near the floor, and restrained warm-cool value shifts, with no altar, brazier, center dais, or ritual floor emblem.
Art direction: Broken gothic halls, damp stone, restrained color, readable traversal silhouettes, and sacred decay.
Avoid: clean sci-fi surfaces, cartoon props, glossy plastics, bright cheerful saturation
Protected zones: walkable_shell_interior@(160,160,1280,880)
Tile mode: stretch
Border treatment: unified_chamber_shell
Schema key: walls
Schema contract: design_intent=A damp ruined gothic hall built as enclosing architecture rather than a focal shrine scene. Heavy side arches, recessed wall bays, and fractured pillars define the room shell while the middle lane stays open and calm for traversal. Depth comes from far hall recession, soft fog near the floor, and restrained warm-cool value shifts, with no altar, brazier, center dais, or ritual floor emblem. Broken gothic walls forming an enclosing shell, featuring heavy arches, recessed bays, and fractured pillars. Use damp, dusty carved stone with sacred decay and low-key lighting, keeping the center calm.; material_family=weathered structural stone; detail_density=medium; value_contrast=low_to_medium with darker edges and readable planes; damage_profile=broken masonry, chips, and restrained collapse; silhouette_rules=vertical mass reads as enclosing wall shell, repeat bays instead of scenic one-off shapes; readability_constraints=must read as room enclosure, avoid scenic perspective that flattens gameplay depth; negative_constraints=no altar scene, no brazier focal energy, no giant center architecture; variation_rules=repeat with subtle block shifts, allow local wear without breaking wall rhythm
Gameplay constraints: keep protected readability zones clear, preserve silhouette readability, stay close to the source template family, and protect top-lip / threshold / hazard readability.
Composition contract: this prompt defines a structural shell component only. Do not introduce new scene composition, landmarks, or decorative set-pieces beyond what the template role and technical constraints require.

Component-specific rules: Build one full chamber shell image at the exact output size: ceiling mass, both side walls, and floor/footing as one continuous foreground frame in side view, matching the biome stone family. Ceiling/corner continuity contract: the top cap must read as one monolithic continuous slab with no pasted segment joins, no tiled strip collage, and no repeated patch modules; both top corners must be fused into the side walls as one carved corner mass, not assembled from separate pieces. Edge fill contract: fully populate the perimeter masonry shell with no empty wedges, bite-outs, or unfilled voids in the top ledge and all four corners; the border reads as continuous stone mass around the opening. Corner shading contract: avoid dark vignette pools in corners; corners should remain readable mid-dark stone, not near-black falloff blobs. Detail-scale contract: avoid giant masonry blocks or mega ashlar plates. Use medium-to-fine stone courses and seam cadence so the shell reads at player scale, with multiple visible joints per band rather than a few oversized bricks. The footprint schematic is an authoring guide only: use a neutral outline and filled walkable volume - do not copy that guide as a bright accent line, HUD stroke, or single-pixel hairline frame in the final PNG. Paint deep, heavy masonry with real texture: opaque side shells should each read roughly 16-24% of output width (full stone courses, mortar, chips, wear), the ceiling band roughly 18-28% of output height, the floor footing roughly 14-22% of output height - not a thin neon border. Design-language contract: keep one relatively uniform masonry language across top, sides, and bottom (same stone family, seam scale, and weathering cadence) with only subtle variation, not mixed motif bands. Tone contract: shell bands must visibly separate from the interior field by value so the border remains readable after punchout. The engine will punch the walkable polygon interior to transparent in post; the surviving rim must be substantial carved stone, not a one-pixel edge. Do not add decorative colored rim strokes along the walkable cutout or outer frame; perimeter separation must read as stone/mortar value and texture only. You may paint atmosphere inside the guide polygon for continuity, but the visible perimeter must read as thick structure. Do not replace the footprint with a generic centered rectangle; respect non-rectangular outlines. Avoid a second duplicate floor strip or separate far-background scene; this layer is the structural shell only.

Output a single production-ready component image only at the exact output dimensions above. No text, no characters, no UI.

Iteration note: one reference image is this slot's current production asset. Refine it in place-same role, silhouette, and transparency-using the silhouette and approved preview references for geometry and palette alignment.
