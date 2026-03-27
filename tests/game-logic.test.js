/**
 * Unit tests for deterministic game logic mirrored from index.html.
 * Phaser-specific rendering/physics objects are not instantiated here, so we
 * cover the pure decision logic that drives movement, jumping, and layout.
 */

const assert = require('assert');

const CONFIG = {
    H: 400,
    WORLD_WIDTH: 3200,
    WORLD_HEIGHT: 1200,
    PLAYER_SPEED: 280,
    JUMP_FORCE: -690,
    FRICTION: 0.75,
    COLORS: [0x2a3a5a, 0x3a2a5a, 0x2a4a3a, 0x4a3a2a, 0x2a4050]
};

const ROOM_LAYOUT = {
    TILE: 32,
    LEFT_DOORWAY_TOP: 1077,
    roomType: 'internal'
};

// ----- Room 1: Hollow Knight cave (must match index.html LABYRINTH_LEDGES) -----
const LABYRINTH_LEDGES = [
    { x: 0, y: 1100, len: 12, tint: 0 },
    { x: 224, y: 1044, len: 18, tint: 1 },
    { x: 416, y: 964, len: 19, tint: 2 },
    { x: 608, y: 884, len: 18, tint: 3 },
    { x: 768, y: 804, len: 15, tint: 0 },
    { x: 608, y: 724, len: 18, tint: 1 },
    { x: 416, y: 644, len: 20, tint: 2 },
    { x: 224, y: 564, len: 16, tint: 3 },
    { x: 416, y: 484, len: 13, tint: 0 },
    { x: 704, y: 404, len: 10, tint: 1 },
    { x: 928, y: 308, len: 8, tint: 2 },
    { x: 1120, y: 180, len: 4, tint: 4 }
];

const ROOM1_OFFSET = 1600;

// ----- Room 2: path to exit (must match index.html ROOM2_LEDGES) -----
const ROOM2_LEDGES = [
    { x: 1248, y: 1068, len: 11, tint: 0 },
    { x: 992, y: 996, len: 14, tint: 1 },
    { x: 736, y: 924, len: 15, tint: 2 },
    { x: 480, y: 852, len: 14, tint: 3 },
    { x: 256, y: 780, len: 12, tint: 0 },
    { x: 96, y: 700, len: 9, tint: 1 },
    { x: 64, y: 612, len: 7, tint: 2 },
    { x: 64, y: 516, len: 6, tint: 3 },
    { x: 64, y: 420, len: 5, tint: 0 },
    { x: 64, y: 332, len: 4, tint: 1 },
    { x: 64, y: 244, len: 4, tint: 4 }
];

const ROOM2_EXIT = { x: 128, y: 210 };

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
        for (let ty = tile; ty < 1168; ty += tile) {
            wallTiles.push({ x: worldWidth - 16, y: ty + 16, texture: 'floor' });
        }
        const room2GapEnd = 272;
        for (let ty = tile; ty < room2GapEnd - tile * 2; ty += tile) {
            wallTiles.push({ x: 16, y: ty + 16, texture: 'floor' });
        }
        for (let ty = room2GapEnd; ty < 1168; ty += tile) {
            wallTiles.push({ x: 16, y: ty + 16, texture: 'floor' });
        }
        wallTiles.push({ x: 16, y: 1077, texture: 'floor' });
        const room1LeftX = ROOM1_OFFSET + 16;
        for (let ty = tile; ty < ROOM_LAYOUT.LEFT_DOORWAY_TOP; ty += tile) {
            wallTiles.push({ x: room1LeftX, y: ty + 16, texture: 'floor' });
        }
        wallTiles.push({ x: room1LeftX, y: 1077, texture: 'floor' });
    }

    const platformTiles = [];
    LABYRINTH_LEDGES.forEach(({ x, y, len, tint }) => {
        for (let i = 0; i < len; i++) {
            platformTiles.push({ x: ROOM1_OFFSET + x + (i * tile) + 16, y, tint: `p${tint}` });
        }
    });
    ROOM2_LEDGES.forEach(({ x, y, len, tint }) => {
        for (let i = 0; i < len; i++) {
            platformTiles.push({ x: x + (i * tile) + 16, y, tint: `p${tint}` });
        }
    });

    return { floorCenters, platformTiles, wallTiles };
}

function buildProgressionLayout() {
    return {
        exitDoor: { x: 248 + ROOM1_OFFSET, y: 1137, texture: 'doorLocked' },
        keyPickup: { x: 1200 + ROOM1_OFFSET, y: 146, texture: 'key' },
        relicPickup: { x: 304 + ROOM1_OFFSET, y: 902, texture: 'relic' },
        exitTrigger: { x: ROOM2_EXIT.x, y: ROOM2_EXIT.y, texture: 'exit' }
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

function clampNumber(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function normalizeLayoutRoomForRuntime(room, fallbackWidth = 1600) {
    const width = Math.max(320, Number(room?.size?.width || fallbackWidth));
    const sourceHeight = Math.max(320, Number(room?.size?.height || CONFIG.WORLD_HEIGHT));
    const scaleY = CONFIG.WORLD_HEIGHT / sourceHeight;
    const normalizeX = (value, fallback = 0) => {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return fallback;
        return clampNumber(numeric, 0, width);
    };
    const normalizeY = (value, fallback = CONFIG.WORLD_HEIGHT - 64) => {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return fallback;
        const scaled = sourceHeight === CONFIG.WORLD_HEIGHT ? numeric : (numeric * scaleY);
        return clampNumber(Number(scaled.toFixed(2)), 0, CONFIG.WORLD_HEIGHT);
    };

    return {
        size: { width, height: CONFIG.WORLD_HEIGHT },
        doors: (room.doors || []).map((door) => ({
            ...door,
            x: normalizeX(door.x, 0),
            y: normalizeY(door.y, CONFIG.WORLD_HEIGHT - 64)
        })),
        platforms: (room.platforms || []).map((platform) => ({
            ...platform,
            x: normalizeX(platform.x, 0),
            y: normalizeY(platform.y, CONFIG.WORLD_HEIGHT - 64)
        })),
        movingPlatforms: (room.movingPlatforms || []).map((mover) => {
            const startX = normalizeX(mover.x, 0);
            const startY = normalizeY(mover.y, CONFIG.WORLD_HEIGHT - 64);
            return {
                ...mover,
                x: startX,
                y: startY,
                endX: normalizeX(mover.endX, startX),
                endY: normalizeY(mover.endY, startY)
            };
        })
    };
}

function computeDoorStandPosition(roomWidth, door) {
    const leftGap = door.x;
    const rightGap = roomWidth - door.x;
    const topGap = door.y;
    const bottomGap = CONFIG.WORLD_HEIGHT - door.y;
    const minGap = Math.min(leftGap, rightGap, topGap, bottomGap);

    if (minGap === leftGap) {
        return { x: door.x + 96, y: door.y, entrySide: 'left' };
    }
    if (minGap === rightGap) {
        return { x: door.x - 96, y: door.y, entrySide: 'right' };
    }
    if (minGap === topGap) {
        return { x: door.x, y: door.y + 96, entrySide: 'top' };
    }
    return { x: door.x, y: door.y - 96, entrySide: 'bottom' };
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

// ========== Runtime layout normalization tests ==========
(function testTallRoomDoorAndPlatformsScaleIntoPlayableHeight() {
    const out = normalizeLayoutRoomForRuntime({
        id: 'R6',
        size: { width: 5000, height: 2000 },
        doors: [{ id: 'R6-D1', x: 201, y: 1622 }],
        platforms: [{ id: 'R6-P1', x: 1790, y: 1551, len: 7, tint: 0 }],
        movingPlatforms: [{ id: 'R6-M1', x: 1072, y: 1584, endX: 1072, endY: 384, len: 4, tint: 0 }]
    });

    assert.strictEqual(out.size.height, CONFIG.WORLD_HEIGHT);
    assert.strictEqual(out.doors[0].y, 973.2);
    assert.strictEqual(out.platforms[0].y, 930.6);
    assert.strictEqual(out.movingPlatforms[0].y, 950.4);
    assert.strictEqual(out.movingPlatforms[0].endY, 230.4);
})();

(function testScaledDoorSpawnStaysInsidePlayableWorld() {
    const out = normalizeLayoutRoomForRuntime({
        id: 'R6',
        size: { width: 5000, height: 2000 },
        doors: [{ id: 'R6-D1', x: 201, y: 1622 }]
    });
    const stand = computeDoorStandPosition(out.size.width, out.doors[0]);

    assert.deepStrictEqual(stand, { x: 297, y: 973.2, entrySide: 'left' });
})();

(function testInBoundsRoomKeepsExistingDoorHeight() {
    const out = normalizeLayoutRoomForRuntime({
        id: 'R5',
        size: { width: 1600, height: 1200 },
        doors: [{ id: 'R5-D1', x: 1216, y: 848 }]
    });

    assert.strictEqual(out.doors[0].y, 848);
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
    assert.strictEqual(layout.floorCenters.length, 100, '3200px world with 32px tiles should create 100 floor tiles');
    assert.strictEqual(layout.floorCenters[0], 16);
    assert.strictEqual(layout.floorCenters[layout.floorCenters.length - 1], 3184);
})();

(function testFirstZoneCreatesExpectedFloatingPlatforms() {
    const layout = buildFirstZoneLayout();
    const expectedCount = LABYRINTH_LEDGES.reduce((sum, l) => sum + l.len, 0) + ROOM2_LEDGES.reduce((sum, l) => sum + l.len, 0);
    assert.strictEqual(layout.platformTiles.length, expectedCount, 'platform count must match room 1 + room 2 ledges');
    assert.deepStrictEqual(layout.platformTiles[0], { x: ROOM1_OFFSET + 16, y: 1100, tint: 'p0' }, 'first tile is room 1 corridor');
})();

(function testFirstZoneCreatesBoundaryWallsAtClosedEdges() {
    const layout = buildFirstZoneLayout();
    assert.strictEqual(layout.wallTiles.length, 205, 'ceiling 100 + right 36 + room2 left 36 + room1 left 33');
    assert.deepStrictEqual(layout.wallTiles[0], { x: 16, y: 16, texture: 'floor' });
})();

(function testLeftEdgeStaysOpenOnlyForDoorCorridor() {
    const layout = buildFirstZoneLayout();
    const room1LeftTiles = layout.wallTiles.filter((t) => t.x === ROOM1_OFFSET + 16 && t.y > 16);
    assert(room1LeftTiles.length >= 33, 'room 1 left wall from 48 down to 1077');
    assert.deepStrictEqual(room1LeftTiles[0], { x: ROOM1_OFFSET + 16, y: 48, texture: 'floor' });
    assert.deepStrictEqual(room1LeftTiles[room1LeftTiles.length - 1], { x: ROOM1_OFFSET + 16, y: 1077, texture: 'floor' });
})();

(function testOutdoorRoomHasNoBoundaryWalls() {
    const layout = buildFirstZoneLayout(CONFIG.WORLD_WIDTH, ROOM_LAYOUT.TILE, CONFIG.WORLD_HEIGHT, 'outdoor');
    assert.strictEqual(layout.wallTiles.length, 0, 'Outdoor rooms must not add boundary walls or ceiling');
})();

(function testFirstZoneIncludesLeftCorridorLedge() {
    const layout = buildFirstZoneLayout();
    const corridorTiles = layout.platformTiles.filter((tile) => tile.y === 1100 && tile.x >= ROOM1_OFFSET);
    const firstEight = corridorTiles.slice(0, 8);
    const base = ROOM1_OFFSET + 16;
    assert.deepStrictEqual(firstEight, [
        { x: base, y: 1100, tint: 'p0' },
        { x: base + 32, y: 1100, tint: 'p0' },
        { x: base + 64, y: 1100, tint: 'p0' },
        { x: base + 96, y: 1100, tint: 'p0' },
        { x: base + 128, y: 1100, tint: 'p0' },
        { x: base + 160, y: 1100, tint: 'p0' },
        { x: base + 192, y: 1100, tint: 'p0' },
        { x: base + 224, y: 1100, tint: 'p0' }
    ], 'first ledge is room 1 corridor (8 tiles at y=1100)');
})();

(function testFirstZoneIncludesHighGateLedge() {
    const layout = buildFirstZoneLayout();
    const highTiles = layout.platformTiles.filter((tile) => tile.y <= 200);
    assert.strictEqual(highTiles.length, 4, 'high gated perch is four tiles wide at y=180');
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
    assert.deepStrictEqual(layout.exitDoor, { x: 248 + ROOM1_OFFSET, y: 1137, texture: 'doorLocked' });
    assert.deepStrictEqual(layout.keyPickup, { x: 1200 + ROOM1_OFFSET, y: 146, texture: 'key' });
    assert.deepStrictEqual(layout.relicPickup, { x: 304 + ROOM1_OFFSET, y: 902, texture: 'relic' });
    assert.deepStrictEqual(layout.exitTrigger, { x: ROOM2_EXIT.x, y: ROOM2_EXIT.y, texture: 'exit' });
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

(function testRoomLayoutEditorValidateLayoutSmoke() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../room-layout-editor.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(html.includes('function validateLayout'), 'validateLayout should exist in room-layout-editor.html');
    assert.ok(html.includes('L1-001') && html.includes('L2-003'), 'validation rule IDs should be present');
    assert.ok(html.includes('renderValidationResults'), 'renderValidationResults should exist');
    assert.ok(html.includes('VALIDATION_L2'), 'VALIDATION_L2 tunable thresholds should exist');
    assert.ok(html.includes('gamePreviewOverlay') && html.includes('gamePreviewFrame'), 'in-page playtest overlay should exist');
})();

(function testIndexPreviewStartFromHashSmoke() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(html.includes('applyPreviewStartFromHash'), 'applyPreviewStartFromHash should exist');
    assert.ok(html.includes('let TEMP_TEST_START'), 'mutable TEMP_TEST_START for preview spawn');
    assert.ok(html.includes('PREVIEW_START_APPLIED'), 'preview spawn flag for create()');
    assert.ok(html.includes('mergeRoomSequence'), 'mergeRoomSequence for layout rooms beyond R11');
})();

(function testPreviewStartHashParsing() {
    function parsePreviewStartRoomId(hash) {
        const m = hash.match(/[&?]start=([^&]+)/);
        return m ? decodeURIComponent(m[1].trim()) : null;
    }
    assert.strictEqual(parsePreviewStartRoomId('#layout=abc&start=R5'), 'R5');
    assert.strictEqual(parsePreviewStartRoomId('#layout=abc'), null);
    assert.strictEqual(parsePreviewStartRoomId(''), null);
})();

console.log('All game-logic tests passed.');
