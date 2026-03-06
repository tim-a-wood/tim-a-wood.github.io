/**
 * Unit tests for deterministic game logic mirrored from index.html.
 * Phaser-specific rendering/physics objects are not instantiated here, so we
 * cover the pure decision logic that drives movement, jumping, and layout.
 */

const assert = require('assert');

const CONFIG = {
    H: 400,
    WORLD_WIDTH: 1600,
    PLAYER_SPEED: 280,
    JUMP_FORCE: -690,
    FRICTION: 0.75,
    COLORS: [0x2a3a5a, 0x3a2a5a, 0x2a4a3a, 0x4a3a2a, 0x2a4050]
};

const ROOM_LAYOUT = {
    TILE: 32,
    LEFT_DOORWAY_TOP: 288,
    roomType: 'internal'
};

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
        jumpsRemaining
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
        nextJumpsRemaining = 2;
    }

    if (jumpDown && onGround && nextJumpsRemaining === 2) {
        appliedGroundJump = true;
        nextVelocityY = CONFIG.JUMP_FORCE;
        nextJumpsRemaining--;
        nextJumpBuffer = 0;
    } else if ((jumpJustPressed || nextJumpBuffer > 0) && inAir && nextJumpsRemaining > 0) {
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

function buildFirstZoneLayout(worldWidth = CONFIG.WORLD_WIDTH, tile = ROOM_LAYOUT.TILE, height = CONFIG.H, roomType = ROOM_LAYOUT.roomType) {
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
    }

    const ledges = [
        { x: 0, y: 284, len: 8, tint: 0 },
        { x: 320, y: 280, len: 2, tint: 0 },
        { x: 520, y: 220, len: 3, tint: 1 },
        { x: 800, y: 260, len: 2, tint: 2 },
        { x: 1050, y: 180, len: 4, tint: 3 },
        { x: 1320, y: 240, len: 2, tint: 4 },
        { x: 1450, y: 120, len: 3, tint: 1 }
    ];

    const platformTiles = [];
    ledges.forEach(({ x, y, len, tint }) => {
        for (let i = 0; i < len; i++) {
            platformTiles.push({ x: x + (i * tile) + 16, y, tint: `p${tint}` });
        }
    });

    return { floorCenters, platformTiles, wallTiles };
}

function buildProgressionLayout(height = 400) {
    return {
        exitDoor: { x: 224, y: 326, texture: 'doorLocked' },
        keyPickup: { x: 1498, y: 86, texture: 'key' }
    };
}

function shouldShowInventoryKey(state) {
    return state.hasKey && !state.doorUnlocked;
}

function computeProgressionFrame(state) {
    const next = { ...state };

    if (state.touchingKey && state.keyActive && !state.hasKey) {
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
        jumpsRemaining: 0
    });
    assert.strictEqual(out.nextJumpsRemaining, 2);
    assert.strictEqual(out.appliedGroundJump, false);
    assert.strictEqual(out.appliedAirJump, false);
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
        jumpsRemaining: 2
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
        jumpsRemaining: 1
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
        jumpsRemaining: 1
    });
    assert.strictEqual(out.appliedGroundJump, false);
    assert.strictEqual(out.appliedAirJump, true);
    assert.strictEqual(out.nextVelocityY, CONFIG.JUMP_FORCE);
    assert.strictEqual(out.nextJumpsRemaining, 0);
})();

(function testJumpBufferAllowsSlightlyLateSecondJump() {
    const out = computeJumpFrame({
        onGround: false,
        velocityY: -120,
        jumpDown: false,
        jumpJustPressed: false,
        jumpBuffer: 2,
        jumpsRemaining: 1
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
        jumpsRemaining: 1
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
        jumpsRemaining: 0
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
        jumpsRemaining: 1
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
        jumpsRemaining: 2
    });
    assert.strictEqual(out.appliedGroundJump, true);
    assert.strictEqual(out.nextJumpsRemaining, 1);

    out = computeJumpFrame({
        onGround: false,
        velocityY: -300,
        jumpDown: false,
        jumpJustPressed: false,
        jumpBuffer: out.nextJumpBuffer,
        jumpsRemaining: out.nextJumpsRemaining
    });
    assert.strictEqual(out.appliedAirJump, false, 'No second jump without new press or buffered tap');

    out = computeJumpFrame({
        onGround: false,
        velocityY: -250,
        jumpDown: true,
        jumpJustPressed: true,
        jumpBuffer: out.nextJumpBuffer,
        jumpsRemaining: out.nextJumpsRemaining
    });
    assert.strictEqual(out.appliedAirJump, true);
    assert.strictEqual(out.nextJumpsRemaining, 0);
})();

// ========== Level layout tests ==========
(function testFirstZoneCreatesExpectedFloorTiles() {
    const layout = buildFirstZoneLayout();
    assert.strictEqual(layout.floorCenters.length, 50, '1600px world with 32px tiles should create 50 floor tiles');
    assert.strictEqual(layout.floorCenters[0], 16);
    assert.strictEqual(layout.floorCenters[layout.floorCenters.length - 1], 1584);
})();

(function testFirstZoneCreatesExpectedFloatingPlatforms() {
    const layout = buildFirstZoneLayout();
    assert.strictEqual(layout.platformTiles.length, 24);
    assert.deepStrictEqual(layout.platformTiles[0], { x: 16, y: 284, tint: 'p0' });
    assert.deepStrictEqual(layout.platformTiles[layout.platformTiles.length - 1], { x: 1530, y: 120, tint: 'p1' });
})();

(function testFirstZoneCreatesBoundaryWallsAtClosedEdges() {
    const layout = buildFirstZoneLayout();
    assert.strictEqual(layout.wallTiles.length, 69);
    assert.deepStrictEqual(layout.wallTiles[0], { x: 16, y: 16, texture: 'floor' });
    assert.deepStrictEqual(layout.wallTiles[49], { x: 1584, y: 16, texture: 'floor' });
})();

(function testLeftEdgeStaysOpenOnlyForDoorCorridor() {
    const layout = buildFirstZoneLayout();
    const leftWallTiles = layout.wallTiles.filter((tile) => tile.x === 16 && tile.y > 16);
    assert.deepStrictEqual(leftWallTiles, [
        { x: 16, y: 48, texture: 'floor' },
        { x: 16, y: 80, texture: 'floor' },
        { x: 16, y: 112, texture: 'floor' },
        { x: 16, y: 144, texture: 'floor' },
        { x: 16, y: 176, texture: 'floor' },
        { x: 16, y: 208, texture: 'floor' },
        { x: 16, y: 240, texture: 'floor' },
        { x: 16, y: 272, texture: 'floor' }
    ]);
})();

(function testOutdoorRoomHasNoBoundaryWalls() {
    const layout = buildFirstZoneLayout(CONFIG.WORLD_WIDTH, ROOM_LAYOUT.TILE, CONFIG.H, 'outdoor');
    assert.strictEqual(layout.wallTiles.length, 0, 'Outdoor rooms must not add boundary walls or ceiling');
})();

(function testFirstZoneIncludesLeftCorridorLedge() {
    const layout = buildFirstZoneLayout();
    const corridorTiles = layout.platformTiles.filter((tile) => tile.y === 284);
    assert.deepStrictEqual(corridorTiles, [
        { x: 16, y: 284, tint: 'p0' },
        { x: 48, y: 284, tint: 'p0' },
        { x: 80, y: 284, tint: 'p0' },
        { x: 112, y: 284, tint: 'p0' },
        { x: 144, y: 284, tint: 'p0' },
        { x: 176, y: 284, tint: 'p0' },
        { x: 208, y: 284, tint: 'p0' },
        { x: 240, y: 284, tint: 'p0' }
    ]);
})();

(function testFirstZoneIncludesHighGateLedge() {
    const layout = buildFirstZoneLayout();
    const gateTiles = layout.platformTiles.filter((tile) => tile.y === 120);
    assert.strictEqual(gateTiles.length, 3, 'Expected three tiles for the high gated ledge');
    assert.deepStrictEqual(gateTiles, [
        { x: 1466, y: 120, tint: 'p1' },
        { x: 1498, y: 120, tint: 'p1' },
        { x: 1530, y: 120, tint: 'p1' }
    ]);
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
    assert.deepStrictEqual(layout.exitDoor, { x: 224, y: 326, texture: 'doorLocked' });
    assert.deepStrictEqual(layout.keyPickup, { x: 1498, y: 86, texture: 'key' });
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
