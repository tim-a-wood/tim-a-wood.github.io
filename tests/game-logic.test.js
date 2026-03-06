/**
 * Unit tests for deterministic game logic mirrored from index.html.
 * Phaser-specific rendering/physics objects are not instantiated here, so we
 * cover the pure decision logic that drives movement, jumping, and layout.
 */

const assert = require('assert');

const CONFIG = {
    H: 400,
    WORLD_WIDTH: 1000,
    WORLD_HEIGHT: 600,
    PLAYER_SPEED: 280,
    JUMP_FORCE: -690,
    FRICTION: 0.75,
    COLORS: [0x2a3a5a, 0x3a2a5a, 0x2a4a3a, 0x4a3a2a, 0x2a4050]
};

const ROOM_LAYOUT = {
    TILE: 32,
    LEFT_DOORWAY_TOP: 416,
    roomType: 'internal'
};

// ----- Room spec (must match index.html ROOM_SPEC and parseRoomSpec) -----
const ROOM_SPEC = [
    '##########################################################################################',
    '#........................................................................................#',
    '#..........................................................................[ G ].........#',
    '#.........................................................................#######........#',
    '#..............####################################......................#.......#.......#',
    '#.............#....................................#.....................#.......#.......#',
    '#......#######......................................#####################........#.......#',
    '#.....#..........................................................................#.......#',
    '#.....#.........##################################################################.......#',
    '#.....#........#.........................................................................#',
    '#.....#........#.........##########################......................................#',
    '#.....#........#........#..........................#.........#############################',
    '#.....#........#........#..........................#........#.............................#',
    '#.....#........#........#..........................#........#.............................#',
    '#.....#........#........#..........................#........#.............................#',
    '#_PLAT_........#_FLOOR_2_..........................#_FLOOR_2_............................#',
    '#........................................................................................#',
    '#...........................################################################.............#',
    '#..........................#................................................#............#',
    '#.......###################.................................................#............#',
    '#......#....................................................................#............#',
    '#......#.........###########################################################.............#',
    '#......#........#........................................................................#',
    '#_PLAT_........#........................................................................#',
    '#..............#........................................................................#',
    '#......#........############################################################.............#',
    '#......#....................................................................#............#',
    '# [S] ......................................................................#............#',
    '#  S   #####################################################################.............#',
    '##########################################################################################'
].map((line) => {
    const s = line.replace(/\[ G \]/g, 'G').replace(/\[S\]/g, 'S').replace(/[A-Z_0-9]/g, (c) => (c === 'G' || c === 'S' ? c : '.'));
    if (s.length >= 90) return s.slice(0, 90);
    return s + (s[s.length - 1] === '#' ? '#' : '.').repeat(90 - s.length);
});

function parseRoomSpec() {
    const TILE = 32;
    const W = CONFIG.WORLD_WIDTH;
    const SPEC_W = 90;
    const SPEC_H = ROOM_SPEC.length;
    const nTileCols = Math.floor(W / TILE);
    const grid = ROOM_SPEC.map((line) => {
        const row = [];
        for (let c = 0; c < SPEC_W; c++) {
            const ch = (line[c] || '.');
            row.push(ch === '#' || ch === 'G' || ch === 'S' ? 1 : 0);
        }
        return row;
    });
    function tileSolid(row, tileCol) {
        const c0 = (tileCol * SPEC_W) / nTileCols;
        const c1 = ((tileCol + 1) * SPEC_W) / nTileCols;
        for (let c = Math.floor(c0); c < Math.ceil(c1) && c < SPEC_W; c++) {
            if (grid[row][c] === 1) return true;
        }
        return false;
    }
    let keyCol = null;
    for (let r = 0; r < SPEC_H; r++) {
        for (let c = 0; c < SPEC_W; c++) {
            if (ROOM_SPEC[r][c] === 'G') keyCol = c;
        }
    }
    const ledges = [];
    const CORRIDOR_Y = 500;
    ledges.push({ x: 0, y: CORRIDOR_Y, len: 8, tint: 0 });
    ledges.push({ x: 8 * TILE, y: CORRIDOR_Y, len: nTileCols - 8, tint: 0 });
    for (let specRow = 1; specRow <= 25; specRow++) {
        const y = 100 + Math.floor((specRow - 1) * (380 / 25));
        let runStart = null;
        for (let t = 0; t < nTileCols; t++) {
            const solid = tileSolid(specRow, t);
            if (solid && runStart === null) runStart = t;
            if (!solid && runStart !== null) {
                ledges.push({ x: runStart * TILE, y, len: t - runStart, tint: specRow % 5 });
                runStart = null;
            }
        }
        if (runStart !== null) ledges.push({ x: runStart * TILE, y, len: nTileCols - runStart, tint: specRow % 5 });
    }
    const keyX = keyCol != null ? Math.round((keyCol / SPEC_W) * W) : 820;
    const keyLedgeY = 100 + Math.floor(3 * (380 / 25));
    return {
        ledges,
        keyPos: { x: keyX, y: keyLedgeY - 19 },
        startPos: { x: 128, y: CORRIDOR_Y - 27 }
    };
}

// ----- Movement / jump helpers (must match index.html handleMovement()) -----
function computeHorizontalVelocity({ left, right, currentVelocityX }) {
    if (left) {
        return -CONFIG.PLAYER_SPEED;
    }
    if (right) {
        return CONFIG.PLAYER_SPEED;
    }
    return currentVelocityX * CONFIG.FRICTION;
}

function computeJumpFrame(state) {
    const {
        onGround,
        velocityY,
        jumpDown,
        jumpJustPressed,
        jumpBuffer,
        jumpsRemaining,
        doubleJumpUnlocked = false
    } = state;

    const inAir = !onGround || velocityY < 0;
    let nextJumpBuffer = jumpBuffer;
    let nextJumpsRemaining = jumpsRemaining;
    let appliedGroundJump = false;
    let appliedAirJump = false;
    let nextVelocityY = velocityY;

    if (jumpJustPressed) {
        nextJumpBuffer = 5;
    }

    if (nextJumpBuffer > 0) {
        nextJumpBuffer--;
    }

    if (onGround && velocityY >= 0) {
        nextJumpsRemaining = doubleJumpUnlocked ? 2 : 1;
    }

    if (jumpDown && onGround && nextJumpsRemaining > 0) {
        appliedGroundJump = true;
        nextVelocityY = CONFIG.JUMP_FORCE;
        nextJumpsRemaining--;
        nextJumpBuffer = 0;
    } else if (doubleJumpUnlocked && (jumpJustPressed || nextJumpBuffer > 0) && inAir && nextJumpsRemaining > 0) {
        appliedAirJump = true;
        nextVelocityY = CONFIG.JUMP_FORCE;
        nextJumpsRemaining--;
        nextJumpBuffer = 0;
    }

    return {
        appliedGroundJump,
        appliedAirJump,
        nextVelocityY,
        nextJumpsRemaining,
        nextJumpBuffer,
        nextJumpWasDownLastFrame: jumpDown
    };
}

function buildFirstZoneLayout(worldWidth = CONFIG.WORLD_WIDTH, tile = ROOM_LAYOUT.TILE, height = CONFIG.WORLD_HEIGHT, roomType = ROOM_LAYOUT.roomType) {
    const floorCenters = [];
    for (let tx = 0; tx < worldWidth; tx += tile) {
        floorCenters.push(tx + 16);
    }

    const wallTiles = [];
    if (roomType === 'internal') {
        for (let tx = 0; tx < worldWidth; tx += tile) {
            wallTiles.push({ x: tx + 16, y: 16, texture: 'floor' });
        }
        for (let ty = tile; ty < height - tile; ty += tile) {
            wallTiles.push({ x: worldWidth - 16, y: ty + 16, texture: 'floor' });
        }
        for (let ty = tile; ty < ROOM_LAYOUT.LEFT_DOORWAY_TOP; ty += tile) {
            wallTiles.push({ x: 16, y: ty + 16, texture: 'floor' });
        }
        const corridorPlatformTop = 493;
        wallTiles.push({ x: 16, y: corridorPlatformTop - 41, texture: 'floor' });
        wallTiles.push({ x: 16, y: corridorPlatformTop - 16, texture: 'floor' });
    }

    const parsed = parseRoomSpec();
    const ledges = parsed.ledges;

    const platformTiles = [];
    ledges.forEach(({ x, y, len, tint }) => {
        for (let i = 0; i < len; i++) {
            platformTiles.push({ x: x + (i * tile) + 16, y, tint: `p${tint}` });
        }
    });

    return { floorCenters, platformTiles, wallTiles };
}

function buildProgressionLayout() {
    const parsed = parseRoomSpec();
    const keyPos = parsed.keyPos || { x: 954, y: 86 };
    return {
        exitDoor: { x: 248, y: 537, texture: 'doorLocked' },
        keyPickup: { x: keyPos.x, y: keyPos.y, texture: 'key' },
        relicPickup: { x: 256, y: 436, texture: 'relic' }
    };
}

function shouldShowDoubleJumpSkill(state) {
    return state.doubleJumpUnlocked === true;
}

function shouldShowInventoryKey(state) {
    return state.hasKey && !state.doorUnlocked;
}

function computeProgressionFrame(state) {
    const next = { ...state };

    if (state.touchingRelic && state.relicActive && !state.doubleJumpUnlocked) {
        next.doubleJumpUnlocked = true;
        next.relicActive = false;
        next.statusMessage = 'RELIC ACQUIRED - Double jump unlocked';
    } else if (state.touchingKey && state.keyActive && !state.hasKey) {
        next.hasKey = true;
        next.keyActive = false;
        next.statusMessage = 'KEY ACQUIRED - Return to the left door';
    } else if (state.touchingDoor && !state.doorUnlocked && state.hasKey) {
        next.hasKey = false;
        next.doorUnlocked = true;
        next.doorTexture = 'doorOpen';
        next.doorBodyEnabled = false;
        next.statusMessage = 'DOOR UNLOCKED - Passage opened';
    } else if (state.touchingDoor && !state.doorUnlocked && !state.hasKey) {
        next.statusMessage = 'The door is locked. A key waits on the high ledge.';
    }

    return next;
}

// ----- Seeded RNG (must match index.html: this.seed = (this.seed * 16807) % 2147483647; return (this.seed - 1) / 2147483646) -----
function createRng(initialSeed) {
    let seed = initialSeed;
    return function rng() {
        seed = (seed * 16807) % 2147483647;
        return (seed - 1) / 2147483646;
    };
}

// ----- Pit zone check (must match index.html: this.pitZones.some(p => mid >= p.start && mid <= p.end)) -----
function isInPit(mid, pitZones) {
    return pitZones.some(p => mid >= p.start && mid <= p.end);
}

// ========== RNG tests ==========
(function testRngDeterminism() {
    const rng1 = createRng(42);
    const rng2 = createRng(42);
    for (let i = 0; i < 100; i++) {
        assert.strictEqual(rng1(), rng2(), `RNG divergence at step ${i}`);
    }
})();

(function testRngRange() {
    const rng = createRng(12345);
    for (let i = 0; i < 500; i++) {
        const v = rng();
        assert(v >= 0 && v < 1, `RNG value ${v} out of [0, 1) at step ${i}`);
    }
})();

(function testRngDifferentSeeds() {
    const rngA = createRng(42);
    const rngB = createRng(43);
    assert.notStrictEqual(rngA(), rngB(), 'Different seeds must produce different first value');
})();

// ========== Pit zone tests ==========
(function testPitZoneInside() {
    const pits = [{ start: 100, end: 200 }];
    assert.strictEqual(isInPit(100, pits), true);
    assert.strictEqual(isInPit(150, pits), true);
    assert.strictEqual(isInPit(200, pits), true);
})();

(function testPitZoneOutside() {
    const pits = [{ start: 100, end: 200 }];
    assert.strictEqual(isInPit(99, pits), false);
    assert.strictEqual(isInPit(201, pits), false);
})();

(function testPitZoneMultiple() {
    const pits = [{ start: 50, end: 80 }, { start: 200, end: 250 }];
    assert.strictEqual(isInPit(60, pits), true);
    assert.strictEqual(isInPit(100, pits), false);
    assert.strictEqual(isInPit(220, pits), true);
})();

(function testPitZoneEmpty() {
    assert.strictEqual(isInPit(100, []), false);
})();

// ========== Horizontal movement tests ==========
(function testLeftMovementUsesConfiguredSpeed() {
    assert.strictEqual(
        computeHorizontalVelocity({ left: true, right: false, currentVelocityX: 123 }),
        -CONFIG.PLAYER_SPEED
    );
})();

(function testRightMovementUsesConfiguredSpeed() {
    assert.strictEqual(
        computeHorizontalVelocity({ left: false, right: true, currentVelocityX: -123 }),
        CONFIG.PLAYER_SPEED
    );
})();

(function testLeftInputWinsWhenBothDirectionsHeld() {
    assert.strictEqual(
        computeHorizontalVelocity({ left: true, right: true, currentVelocityX: 0 }),
        -CONFIG.PLAYER_SPEED
    );
})();

(function testNoDirectionalInputAppliesFriction() {
    assert.strictEqual(
        computeHorizontalVelocity({ left: false, right: false, currentVelocityX: 200 }),
        150
    );
})();

// ========== Double-jump tests ==========
(function testJumpRefillsOnGroundWhenNotMovingUp() {
    const out = computeJumpFrame({
        onGround: true,
        velocityY: 0,
        jumpDown: false,
        jumpJustPressed: false,
        jumpBuffer: 0,
        jumpsRemaining: 0,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.nextJumpsRemaining, 2);
    assert.strictEqual(out.appliedGroundJump, false);
    assert.strictEqual(out.appliedAirJump, false);
})();

(function testRefillIsOneWhenDoubleJumpNotUnlocked() {
    const out = computeJumpFrame({
        onGround: true,
        velocityY: 0,
        jumpDown: false,
        jumpJustPressed: false,
        jumpBuffer: 0,
        jumpsRemaining: 0,
        doubleJumpUnlocked: false
    });
    assert.strictEqual(out.nextJumpsRemaining, 1);
})();

(function testJumpDoesNotRefillDuringUpwardArcadeDelay() {
    const out = computeJumpFrame({
        onGround: true,
        velocityY: -100,
        jumpDown: false,
        jumpJustPressed: false,
        jumpBuffer: 0,
        jumpsRemaining: 1
    });
    assert.strictEqual(out.nextJumpsRemaining, 1);
})();

(function testGroundJumpConsumesOneJumpAndClearsBuffer() {
    const out = computeJumpFrame({
        onGround: true,
        velocityY: 0,
        jumpDown: true,
        jumpJustPressed: true,
        jumpBuffer: 3,
        jumpsRemaining: 2,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.appliedGroundJump, true);
    assert.strictEqual(out.appliedAirJump, false);
    assert.strictEqual(out.nextVelocityY, CONFIG.JUMP_FORCE);
    assert.strictEqual(out.nextJumpsRemaining, 1);
    assert.strictEqual(out.nextJumpBuffer, 0);
})();

(function testHoldingJumpDoesNotAutoTriggerDoubleJump() {
    const out = computeJumpFrame({
        onGround: false,
        velocityY: -250,
        jumpDown: true,
        jumpJustPressed: false,
        jumpBuffer: 0,
        jumpsRemaining: 1,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.appliedGroundJump, false);
    assert.strictEqual(out.appliedAirJump, false);
    assert.strictEqual(out.nextJumpsRemaining, 1);
})();

(function testMidAirJumpTriggersOnFreshPress() {
    const out = computeJumpFrame({
        onGround: false,
        velocityY: -200,
        jumpDown: true,
        jumpJustPressed: true,
        jumpBuffer: 0,
        jumpsRemaining: 1,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.appliedGroundJump, false);
    assert.strictEqual(out.appliedAirJump, true);
    assert.strictEqual(out.nextVelocityY, CONFIG.JUMP_FORCE);
    assert.strictEqual(out.nextJumpsRemaining, 0);
})();

(function testMidAirJumpBlockedWhenDoubleJumpNotUnlocked() {
    const out = computeJumpFrame({
        onGround: false,
        velocityY: -200,
        jumpDown: true,
        jumpJustPressed: true,
        jumpBuffer: 0,
        jumpsRemaining: 1,
        doubleJumpUnlocked: false
    });
    assert.strictEqual(out.appliedAirJump, false);
    assert.strictEqual(out.nextJumpsRemaining, 1);
})();

(function testJumpBufferAllowsSlightlyLateSecondJump() {
    const out = computeJumpFrame({
        onGround: false,
        velocityY: -120,
        jumpDown: false,
        jumpJustPressed: false,
        jumpBuffer: 2,
        jumpsRemaining: 1,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.appliedAirJump, true);
    assert.strictEqual(out.nextJumpsRemaining, 0);
    assert.strictEqual(out.nextJumpBuffer, 0);
})();

(function testUpwardVelocityStillCountsAsAirEvenIfBlockedDownLingers() {
    const out = computeJumpFrame({
        onGround: true,
        velocityY: -50,
        jumpDown: false,
        jumpJustPressed: false,
        jumpBuffer: 4,
        jumpsRemaining: 1,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.appliedAirJump, true);
    assert.strictEqual(out.nextJumpsRemaining, 0);
})();

(function testExhaustedJumpsPreventThirdJump() {
    const out = computeJumpFrame({
        onGround: false,
        velocityY: -150,
        jumpDown: true,
        jumpJustPressed: true,
        jumpBuffer: 0,
        jumpsRemaining: 0,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.appliedGroundJump, false);
    assert.strictEqual(out.appliedAirJump, false);
    assert.strictEqual(out.nextJumpsRemaining, 0);
})();

(function testJumpFrameTracksHeldStateForNextInputTransition() {
    const out = computeJumpFrame({
        onGround: false,
        velocityY: -150,
        jumpDown: true,
        jumpJustPressed: false,
        jumpBuffer: 0,
        jumpsRemaining: 1,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.nextJumpWasDownLastFrame, true);
})();

(function testFullDoubleJumpSequenceMatchesCurrentStateMachine() {
    let out = computeJumpFrame({
        onGround: true,
        velocityY: 0,
        jumpDown: true,
        jumpJustPressed: true,
        jumpBuffer: 0,
        jumpsRemaining: 2,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.appliedGroundJump, true);
    assert.strictEqual(out.nextJumpsRemaining, 1);

    out = computeJumpFrame({
        onGround: false,
        velocityY: -300,
        jumpDown: false,
        jumpJustPressed: false,
        jumpBuffer: out.nextJumpBuffer,
        jumpsRemaining: out.nextJumpsRemaining,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.appliedAirJump, false, 'No second jump without new press or buffered tap');

    out = computeJumpFrame({
        onGround: false,
        velocityY: -250,
        jumpDown: true,
        jumpJustPressed: true,
        jumpBuffer: out.nextJumpBuffer,
        jumpsRemaining: out.nextJumpsRemaining,
        doubleJumpUnlocked: true
    });
    assert.strictEqual(out.appliedAirJump, true);
    assert.strictEqual(out.nextJumpsRemaining, 0);
})();

// ========== Level layout tests ==========
(function testFirstZoneCreatesExpectedFloorTiles() {
    const layout = buildFirstZoneLayout();
    assert.strictEqual(layout.floorCenters.length, 31, '1000px world with 32px tiles should create 31 floor tiles');
    assert.strictEqual(layout.floorCenters[0], 16);
    assert.strictEqual(layout.floorCenters[layout.floorCenters.length - 1], 976);
})();

(function testFirstZoneCreatesExpectedFloatingPlatforms() {
    const layout = buildFirstZoneLayout();
    const parsed = parseRoomSpec();
    const expectedCount = parsed.ledges.reduce((sum, l) => sum + l.len, 0);
    assert.strictEqual(layout.platformTiles.length, expectedCount, 'platform count must match spec-derived ledges');
    assert.deepStrictEqual(layout.platformTiles[0], { x: 16, y: 500, tint: 'p0' }, 'first tile is corridor start');
})();

(function testFirstZoneCreatesBoundaryWallsAtClosedEdges() {
    const layout = buildFirstZoneLayout();
    assert.strictEqual(layout.wallTiles.length, 62);
    assert.deepStrictEqual(layout.wallTiles[0], { x: 16, y: 16, texture: 'floor' });
    assert.deepStrictEqual(layout.wallTiles[30], { x: 976, y: 16, texture: 'floor' });
})();

(function testLeftEdgeStaysOpenOnlyForDoorCorridor() {
    const layout = buildFirstZoneLayout();
    const leftWallTiles = layout.wallTiles.filter((t) => t.x === 16 && t.y > 16);
    assert.strictEqual(leftWallTiles.length, 14);
    assert.deepStrictEqual(leftWallTiles[0], { x: 16, y: 48, texture: 'floor' });
    assert.deepStrictEqual(leftWallTiles[leftWallTiles.length - 1], { x: 16, y: 477, texture: 'floor' });
})();

(function testOutdoorRoomHasNoBoundaryWalls() {
    const layout = buildFirstZoneLayout(CONFIG.WORLD_WIDTH, ROOM_LAYOUT.TILE, CONFIG.WORLD_HEIGHT, 'outdoor');
    assert.strictEqual(layout.wallTiles.length, 0, 'Outdoor rooms must not add boundary walls or ceiling');
})();

(function testFirstZoneIncludesLeftCorridorLedge() {
    const layout = buildFirstZoneLayout();
    const corridorTiles = layout.platformTiles.filter((tile) => tile.y === 500);
    const firstEight = corridorTiles.slice(0, 8);
    assert.deepStrictEqual(firstEight, [
        { x: 16, y: 500, tint: 'p0' },
        { x: 48, y: 500, tint: 'p0' },
        { x: 80, y: 500, tint: 'p0' },
        { x: 112, y: 500, tint: 'p0' },
        { x: 144, y: 500, tint: 'p0' },
        { x: 176, y: 500, tint: 'p0' },
        { x: 208, y: 500, tint: 'p0' },
        { x: 240, y: 500, tint: 'p0' }
    ], 'first ledge is corridor (8 tiles at y=500)');
})();

(function testFirstZoneIncludesHighGateLedge() {
    const layout = buildFirstZoneLayout();
    const highTiles = layout.platformTiles.filter((tile) => tile.y <= 150);
    assert(highTiles.length >= 1, 'spec should produce at least one high platform (key area)');
})();

(function testAllPlatformTintsReferenceKnownColors() {
    const layout = buildFirstZoneLayout();
    const validTints = new Set(CONFIG.COLORS.map((_, i) => `p${i}`));
    layout.platformTiles.forEach((tile) => {
        assert(validTints.has(tile.tint), `Unknown platform tint ${tile.tint}`);
    });
})();

// ========== Progression layout and state tests ==========
(function testProgressionObjectsAppearAtExpectedPositions() {
    const layout = buildProgressionLayout();
    assert.deepStrictEqual(layout.exitDoor, { x: 248, y: 537, texture: 'doorLocked' });
    assert.strictEqual(layout.keyPickup.texture, 'key');
    assert(layout.keyPickup.x >= 0 && layout.keyPickup.x <= 1000, 'key x in world');
    assert(layout.keyPickup.y >= 0 && layout.keyPickup.y <= 600, 'key y in world');
    assert.deepStrictEqual(layout.relicPickup, { x: 256, y: 436, texture: 'relic' });
})();

(function testTouchingRelicUnlocksDoubleJump() {
    const out = computeProgressionFrame({
        doubleJumpUnlocked: false,
        relicActive: true,
        touchingRelic: true,
        hasKey: false,
        touchingKey: false,
        touchingDoor: false,
        doorUnlocked: false
    });
    assert.strictEqual(out.doubleJumpUnlocked, true);
    assert.strictEqual(out.relicActive, false);
    assert.strictEqual(out.statusMessage, 'RELIC ACQUIRED - Double jump unlocked');
})();

(function testDoubleJumpSkillIconVisibleWhenUnlocked() {
    assert.strictEqual(shouldShowDoubleJumpSkill({ doubleJumpUnlocked: false }), false);
    assert.strictEqual(shouldShowDoubleJumpSkill({ doubleJumpUnlocked: true }), true);
})();

(function testTouchingKeyCollectsIt() {
    const out = computeProgressionFrame({
        hasKey: false,
        keyActive: true,
        touchingKey: true,
        touchingDoor: false,
        doorUnlocked: false,
        doorTexture: 'doorLocked',
        doorBodyEnabled: true,
        statusMessage: ''
    });
    assert.strictEqual(out.hasKey, true);
    assert.strictEqual(out.keyActive, false);
    assert.strictEqual(out.statusMessage, 'KEY ACQUIRED - Return to the left door');
})();

(function testInventoryKeyIsVisibleOnlyWhileHeld() {
    assert.strictEqual(shouldShowInventoryKey({ hasKey: false, doorUnlocked: false }), false);
    assert.strictEqual(shouldShowInventoryKey({ hasKey: true, doorUnlocked: false }), true);
    assert.strictEqual(shouldShowInventoryKey({ hasKey: false, doorUnlocked: true }), false);
})();

(function testDoorStaysLockedWithoutKey() {
    const out = computeProgressionFrame({
        hasKey: false,
        keyActive: true,
        touchingKey: false,
        touchingDoor: true,
        doorUnlocked: false,
        doorTexture: 'doorLocked',
        doorBodyEnabled: true,
        statusMessage: ''
    });
    assert.strictEqual(out.doorUnlocked, false);
    assert.strictEqual(out.doorTexture, 'doorLocked');
    assert.strictEqual(out.doorBodyEnabled, true);
    assert.strictEqual(out.statusMessage, 'The door is locked. A key waits on the high ledge.');
})();

(function testDoorUnlocksWithKey() {
    const out = computeProgressionFrame({
        hasKey: true,
        keyActive: false,
        touchingKey: false,
        touchingDoor: true,
        doorUnlocked: false,
        doorTexture: 'doorLocked',
        doorBodyEnabled: true,
        statusMessage: ''
    });
    assert.strictEqual(out.hasKey, false);
    assert.strictEqual(out.doorUnlocked, true);
    assert.strictEqual(out.doorTexture, 'doorOpen');
    assert.strictEqual(out.doorBodyEnabled, false);
    assert.strictEqual(out.statusMessage, 'DOOR UNLOCKED - Passage opened');
})();

(function testFullKeyDoorLoop() {
    let state = computeProgressionFrame({
        hasKey: false,
        keyActive: true,
        touchingKey: true,
        touchingDoor: false,
        doorUnlocked: false,
        doorTexture: 'doorLocked',
        doorBodyEnabled: true,
        statusMessage: ''
    });
    assert.strictEqual(state.hasKey, true);
    assert.strictEqual(state.keyActive, false);

    state = computeProgressionFrame({
        hasKey: state.hasKey,
        keyActive: state.keyActive,
        touchingKey: false,
        touchingDoor: true,
        doorUnlocked: false,
        doorTexture: 'doorLocked',
        doorBodyEnabled: true,
        statusMessage: state.statusMessage
    });
    assert.strictEqual(state.hasKey, false);
    assert.strictEqual(state.doorUnlocked, true);
    assert.strictEqual(state.doorTexture, 'doorOpen');
    assert.strictEqual(state.doorBodyEnabled, false);
})();

console.log('All game-logic tests passed.');
