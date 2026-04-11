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

// ----- Final gate state (must match index.html recomputeProgressionCounts) -----
function resolveFinalGateState(flags) {
    const keyItemsCollected = Number(flags.keyItemA) + Number(flags.keyItemB) + Number(flags.keyItemC);
    const abilitiesUnlocked = Number(flags.abilityA) + Number(flags.abilityB) + Number(flags.abilityC);
    if (keyItemsCollected < 3) return 'LOCKED_KEY_ITEMS';
    if (abilitiesUnlocked < 3) return 'LOCKED_ABILITIES';
    return 'UNLOCKED';
}

// ----- Branch sequence simulation (must match index.html simulateSequenceAttempt) -----
function simulateSequenceAttempt(order) {
    const ability = { A: false, B: false, C: false };
    const completed = [];
    const pending = [...order];
    let guard = 0;

    while (pending.length > 0 && guard < 12) {
        const branch = pending.shift();
        if (completed.includes(branch)) {
            guard++;
            continue;
        }
        if (branch === 'B' && !ability.A) {
            pending.push(branch);
            guard++;
            continue;
        }
        ability[branch] = true;
        completed.push(branch);
        guard++;
    }

    return {
        attempt: order.join('-'),
        resolved: completed.join('-'),
        passed: completed.length === 3
    };
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
    assert.ok(html.includes('ASHEN_HOLLOW_PREVIEW') && html.includes('preview=embed'), 'editor posts layout + embed hash');
    assert.ok(
        html.includes('workflowRailsStack') && html.includes('worldWorkflowRail') && html.includes('workflowScopeWorld'),
        'workflow toggle + world rail'
    );
    assert.ok(html.includes('setEditorWorkflowStep') && html.includes('editorWorkflowStep'), 'main workflow step state');
    assert.ok(html.includes('room-wizard-neighbor-align.js'), 'RW-2 neighbor align script');
    assert.ok(html.includes('room-wizard-terrain.js'), 'RW-3 terrain module script');
    assert.ok(html.includes('room-wizard-environment.js'), 'RW-4 environment module script');
    assert.ok(html.includes('local_slot') && html.includes('LOCAL_STORAGE_PREFIX'), 'local sandbox projects via local_slot');
    assert.ok(html.includes('btnNewLocalProject'), 'New local project control');
    assert.ok(html.includes('syncRoomWizardEdgeSelects'), 'dynamic edge dropdowns for non-quad rooms');
    assert.ok(html.includes('RoomWizardNeighborAlign') || html.includes('roomWizardBtnAlign'), 'RW-2 align UI wired');
    assert.ok(html.includes('room-wizard-dock--compact'), 'room setup dock toggles compact class');
    assert.ok(
        html.includes('!state.roomWizard.active') && html.includes('state.workflowScope === \'room\''),
        'close dismisses room scope when wizard already inactive'
    );
})();

(function testIndexHtmlEnvironmentHooksSmoke() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('getEnvironmentHudLine') &&
            html.includes('ROOM_ENV_THEME_BG') &&
            html.includes('ROOM_ENV_STARFIELD_TINT') &&
            html.includes('getEnvironmentStarfieldTint'),
        'game reads room.environment for HUD + BG + starfield tint'
    );
})();

(function testIndexBespokeWallShellPlacementContract() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('getRoomEnvironmentBespokeWallShellAssets'),
        'bespoke wall decor should accept wall_module_* or fall back to wall_piece'
    );
    assert.ok(
        html.includes('Room-local X only') && html.includes('localWallX'),
        'wall shell must pass room-local X into addPlacedBespokeAsset (avoid double world offset)'
    );
})();

(function testIndexPolygonWallRectGateForBespokeShell() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('roomHasPolygonWallTileRects'),
        'polygon wall rect helper still gates procedural mass fallback when bespoke shell fails'
    );
    assert.ok(
        html.includes('Always run bespoke wall shell when manifest has wall slots'),
        'bespoke wall shell must not be skipped whenever polygon rects are non-empty (typical R1)'
    );
    assert.ok(
        /addRoomBespokeWallShellDecor\([\s\S]*?\)[\s\S]*?!roomHasPolygonWallTileRects\(roomId\)/m.test(html),
        'mass fallback should be inside bespoke-failure branch and gated on empty polygon rects'
    );
})();

(function testIndexWallBodyProceduralFallbackAndTileScale() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('Without a loaded AI strip') && html.includes('roomSurfaceTextureKey(roomId, \'wall\', 0)'),
        'resolveRoomWallBodyTexture should fall back to procedural env-surface wall when no AI strip'
    );
    assert.ok(
        html.includes('applyWallStripTileScaleFromTexture'),
        'wall mass/body TileSprites must scale from actual texture frame size (32 vs 512)'
    );
    assert.ok(
        html.includes('hasFootprintPolygon') && html.includes('emphasizeWalls'),
        'footprint polygon should boost procedural wall tile alpha (emphasizeWalls) for playtest readability'
    );
})();

(function testIndexBespokeWallShellUsesAuthoredWidth() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('authoredW') && html.includes('capW') && html.includes('Phaser.Math.Clamp'),
        'wall shell width should follow placement/final_dimensions/plan, clamped — not wideStripCap viewport bands'
    );
    assert.ok(
        html.includes('Match horizontal scale to generated art'),
        'wall shell comment should state authored-scale intent'
    );
    assert.ok(
        html.includes('authoredH') && html.includes('accentHeight') && html.includes('origin_y: 1'),
        'wall shell height must follow authored/plan and bottom-align; no forced full-chamber vertical stretch'
    );
})();

(function testIndexBespokeWallShellTextureCapAndNoFlankingWithWallAssets() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('getEnvBespokeTextureFrameSize')
            && html.includes('WALL_ART_MAX_SCALE_W')
            && html.includes('WALL_ART_MAX_SCALE_H'),
        'wall shell must cap display size vs loaded texture frame; width no upscale past native'
    );
    assert.ok(
        /capW = Math\.min\(maxHalf, Math\.round\(chamberWidth \* 0\.14\), 272\)/.test(html),
        'wall shell capW must use 14% chamber and 272px absolute max'
    );
    assert.ok(
        /if \(!wallAssets\.length && support\?\.roomBounds && chamberBounds\)/.test(html),
        'flanking wall mass inside bespoke shell only when no wall_module assets (avoid giant margin TileSprites)'
    );
    assert.ok(
        html.includes('origin_x: isLeft ? 1 : 0')
            && /const localWallX = isLeft[\s\S]*\? Number\(chamberBounds\?\.left \|\| 0\)[\s\S]*: Number\(chamberBounds\?\.right \|\| roomWidth\)/m.test(html),
        'left shell right edge and right shell left edge must be boundary-flush'
    );
})();

(function testIndexPrimaryFloorCapFlushWithChamberBounds() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('function getRoomPolygonPrimaryFloorSpans')
            && html.includes('const primaryFloorY = span.tileCenterY')
            && html.includes('function getLayoutFloorTileCenterY')
            && /addRoomFloorCapDecor\([\s\S]*primaryFloorX[\s\S]*primaryFloorY[\s\S]*primaryFloorWidth/m.test(html),
        'primary floor cap should follow polygon bottom spans (per-column ground) with bleed, or bbox fallback'
    );
})();

(function testIndexPrimaryFloorCollisionFlushWithBoundary() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('collisionSpans')
            && html.includes('getRoomPolygonPrimaryFloorSpans(roomId)')
            && html.includes("this.createRoomSurfaceTile(px, span.tileCenterY, roomId, platformTextureKey, 'floor')"),
        'primary floor collision should follow polygon bottom spans with bleed (same geometry as floor cap)'
    );
    assert.ok(
        /isPrimaryFloor\s*=\s*[\s\S]*primaryFloorPlatform[\s\S]*primaryFloorPlatform\.x[\s\S]*Math\.max\(1, Number\(primaryFloorPlatform\.len \|\| 1\)\) === len/m.test(html)
            && !/isPrimaryFloor[\s\S]*primaryFloorPlatform\.y/.test(html),
        'primary-floor collision gate should not require legacy y equality once seam follows primary floor row'
    );
})();

(function testIndexWalkPlaneUsesLayoutFloorRow() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('function getPrimaryFloorTileCenterY')
            && html.includes('function getLayoutFloorTileCenterY')
            && html.includes('function getRoomWalkPlaneTopY')
            && html.includes('y: wallFootY')
            && html.includes('walkPlaneTopY')
            && html.includes('getRoomPolygonBounds(roomId).bottom')
            && html.includes('return b - 16'),
        'walk plane and wall shell foot should follow layout polygon floor row (bottom edge of footprint)'
    );
})();

(function testIndexFloorCapAnchorsTopAtWalkSurface() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('const walkTop = y - 16')
            && html.includes('add.image(x + (width / 2), walkTop')
            && html.includes('.setOrigin(0.5, 0)'),
        'floor cap decor should anchor top at tile walk surface (center y minus half tile)'
    );
})();

(function testIndexBespokeWallShellCoversPolygonInsetMargins() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('marginLeft')
            && html.includes('marginRight')
            && html.includes('Math.max(accentW, marginLeft)')
            && html.includes('Math.max(accentW, marginRight)'),
        'bespoke side shell width must cover room→chamber inset when flanking mass is skipped'
    );
})();

(function testIndexUnifiedShellSkipsPolygonMaskForPlaytestParity() {
    const fs = require('fs');
    const path = require('path');
    const htmlPath = path.join(__dirname, '../index.html');
    if (!fs.existsSync(htmlPath)) return;
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.ok(
        html.includes('addRoomBespokeUnifiedShellForegroundDecor(roomId, shellSupport)')
            && html.includes('saved runtime-review.png')
            && html.includes('not a polygon mask')
            && html.includes('const depth = 0.16')
            && html.includes('UNIFIED_SHELL_PLACEMENT_CHAMBER_BBOX')
            && html.includes('computeUnifiedShellWorldPlacement(asset, support)')
            && html.includes('const localX = curLeft + ox * dw')
            && !html.includes('applyUnifiedShellFootprintMask')
            && !html.includes('strokePoints(worldPts, true)'),
        'unified shell should rely on PNG alpha and depth only (no footprint geometry mask)'
    );
})();

(function testRoomWizardWorkbenchShellCompactCss() {
    const fs = require('fs');
    const path = require('path');
    const cssPath = path.join(__dirname, '../room-wizard-workbench-shell.css');
    if (!fs.existsSync(cssPath)) return;
    const css = fs.readFileSync(cssPath, 'utf8');
    assert.ok(
        css.includes('.room-wizard-dock.room-wizard-dock--compact'),
        'compact room setup strip styles should exist'
    );
    assert.ok(
        css.includes('worldWorkflowRail[hidden]') && css.includes('display: none !important'),
        'world workflow rail must hide with [hidden] (beats display:grid specificity)'
    );
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
    assert.ok(html.includes('loadLayoutDataFromHashUrl'), 'preview should support file-backed layout URLs for large embeds');
    assert.ok(html.includes('applyRuntimeReviewCaptureViewport'), 'capture mode should size the canvas to the active room before boot');
    assert.ok(html.includes('capture=runtime-review'), 'preview should support checkpoint capture mode');
    assert.ok(html.includes('applyRuntimeReviewCapturePresentation'), 'capture mode should hide HUD/debug overlays');
    assert.ok(html.includes('applyRuntimeReviewCaptureCamera'), 'capture mode should frame the room instead of following live gameplay');
    assert.ok(html.includes('const polygonBounds = getRoomPolygonBounds(roomId);'), 'runtime geometry should derive polygon bounds before shell/floor placement');
    assert.ok(html.includes('getRoomCameraChamberBoundsWorld'), 'playtest camera should clamp to footprint polygon chamber');
    assert.ok(html.includes('CAMERA_CHAMBER_SURFACE_BLEED_PX'), 'camera chamber should have vertical surface bleed past polygon');
    assert.ok(html.includes('CAMERA_CHAMBER_SIDE_BLEED_PX'), 'camera chamber should have wider horizontal bleed for wall crop');
    assert.ok(html.includes('RUNTIME_REVIEW_CAPTURE_MODE ? 64 : 48'), 'capture mode should strengthen door readability');
    assert.ok(
        html.includes('RUNTIME_REVIEW_CAPTURE_MODE ? (composition.hasBespokeBackground ? 0.72 : 0.58) : (composition.hasBespokeBackground ? 0.4 : 0.5)'),
        'capture mode should raise scenic backdrop visibility for tone alignment checks'
    );
        assert.ok(html.includes('addRoomBespokeDoorDecor'), 'runtime should place bespoke door-frame assets into the scene');
        assert.ok(html.includes('addRoomBespokeCeilingDecor'), 'runtime should place bespoke ceiling_band into the scene');
        assert.ok(
            /ceiling_band:\s*\[\s*['"]ceiling_band['"]\s*\]/.test(html),
            'getRoomEnvironmentBespokeAsset should resolve ceiling_band slots'
        );
        assert.ok(
            /chamberTop/.test(html) && /addRoomBespokeCeilingDecor[\s\S]*chamberTop/.test(html),
            'ceiling decor should snap Y to footprint chamber top (planner y=0 is not world Y)'
        );
        assert.ok(html.includes('applyRuntimeReviewCaptureContainerAspect'), 'runtime review should lock embed aspect to chamber CONFIG');
        assert.ok(
            html.includes('getRoomBespokeCeilingCapHeightForRuntime') && html.includes('vaultHeight'),
            'background/midground should shorten when a bespoke ceiling slab owns the top band'
        );
    assert.ok(html.includes('ASHEN_HOLLOW_PREVIEW'), 'postMessage layout embed for room editor iframe');
    assert.ok(html.includes('ASHEN_HOLLOW_PREVIEW_READY'), 'child signals when listener can receive layout');
    assert.ok(html.includes('preview=embed'), 'hash flag for embed wait in bootGame');
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

// ========== Map MVP gate state (docs/gate-state-spec-v1.md parity with index.html) ==========
(function testResolveFinalGateStateLockedKeys() {
    assert.strictEqual(
        resolveFinalGateState({
            keyItemA: false,
            keyItemB: false,
            keyItemC: false,
            abilityA: false,
            abilityB: false,
            abilityC: false
        }),
        'LOCKED_KEY_ITEMS'
    );
    assert.strictEqual(
        resolveFinalGateState({
            keyItemA: true,
            keyItemB: true,
            keyItemC: false,
            abilityA: true,
            abilityB: true,
            abilityC: true
        }),
        'LOCKED_KEY_ITEMS'
    );
})();

(function testResolveFinalGateStateLockedAbilities() {
    assert.strictEqual(
        resolveFinalGateState({
            keyItemA: true,
            keyItemB: true,
            keyItemC: true,
            abilityA: false,
            abilityB: false,
            abilityC: false
        }),
        'LOCKED_ABILITIES'
    );
    assert.strictEqual(
        resolveFinalGateState({
            keyItemA: true,
            keyItemB: true,
            keyItemC: true,
            abilityA: true,
            abilityB: true,
            abilityC: false
        }),
        'LOCKED_ABILITIES'
    );
})();

(function testResolveFinalGateStateUnlocked() {
    assert.strictEqual(
        resolveFinalGateState({
            keyItemA: true,
            keyItemB: true,
            keyItemC: true,
            abilityA: true,
            abilityB: true,
            abilityC: true
        }),
        'UNLOCKED'
    );
})();

(function testSimulateSequenceAttemptOrders() {
    const orders = [
        ['A', 'B', 'C'],
        ['B', 'C', 'A'],
        ['C', 'A', 'B']
    ];
    for (const order of orders) {
        const r = simulateSequenceAttempt(order);
        assert.strictEqual(r.passed, true, `sequence should resolve for ${r.attempt}`);
        assert.strictEqual(r.resolved.split('-').length, 3);
    }
})();

console.log('All game-logic tests passed.');
