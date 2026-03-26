# Sprite Workbench Phaser Handoff

This is the reference handoff for using a Sprite Workbench runtime export in the existing Ashen Hollow Phaser game.

## Current integration model

Ashen Hollow loads exported frame PNGs directly and builds Phaser animations from them.

Current implementation references:

- [game loader](/Users/timwood/Desktop/projects/PWA/MV/index.html#L937)
- [Workbench hero preload](/Users/timwood/Desktop/projects/PWA/MV/index.html#L999)
- [Workbench animation creation](/Users/timwood/Desktop/projects/PWA/MV/index.html#L1027)
- [jump pose handling](/Users/timwood/Desktop/projects/PWA/MV/index.html#L2659)

The game currently treats these clips as the practical handoff set:

- `idle`
- `run`
- `jump`
- `attack`
- `parry`

`walk` is still exported, but the current gameplay loop uses `run` as the default grounded movement clip.

## What Phaser expects

For each clip the game needs:

- an ordered frame sequence
- `fps`
- whether the clip loops

The current workbench export already provides this through:

- `animations.json`
- `frames/<clip>_<nn>.png`

## Recommended runtime loading path

### 1. Load frame PNGs

Load each exported frame as an image texture:

```js
this.load.image('wb-run_00', `${basePath}/frames/run_00.png`);
```

### 2. Build Phaser animations

Create the clip from the ordered frame names in `animations.json`:

```js
this.anims.create({
  key: 'hero-run',
  frames: ['run_00.png', 'run_01.png', 'run_02.png', 'run_03.png'].map((name) => ({
    key: `wb-${name.replace('.png', '')}`
  })),
  frameRate: animation.fps,
  repeat: animation.loop ? -1 : 0
});
```

### 3. Map gameplay states to clips

Current Ashen Hollow mapping:

- grounded + no input → `idle`
- grounded + movement → `run`
- airborne → `jump`
- debug action preview → `attack` or `parry`

## Integration notes

### Scale and origin

The exported sprites are much larger than the old placeholder hero. Expect to tune:

- render scale
- origin
- collision box

Ashen Hollow currently does that in its Workbench player setup rather than assuming the default Phaser sprite box is correct.

### Jump handling

The current game does not loop the whole jump clip. It manually drives jump frames to distinguish rise and fall. That means a consuming game does not need to treat every exported clip as a simple looping animation.

### Action clips

`attack` and `parry` are currently wired as deliberate runtime triggers rather than passive locomotion.

## Preferred contract for future consumers

For Phaser, the recommended order of trust is:

1. `animations.json`
2. `frames/`
3. `animation_sheets/<clip>.json`
4. `atlas.json`

That keeps the handoff simple:

- `animations.json` defines clip timing and order
- `frames/` provides the actual images
- per-animation sheet metadata is available if a runtime wants sheet-based loading later

## Success criteria

A runtime integration should be considered complete when:

- `idle`, `run`, and `jump` play cleanly in-engine
- `attack` and `parry` can be triggered intentionally
- sprite feet feel planted against the floor
- scale and origin are tuned without hand-editing exported assets
