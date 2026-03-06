/**
 * Unit tests for game logic (RNG, pit-zone helpers, and double-jump).
 * The game currently uses a bounded hand-placed zone with no procedural gen;
 * RNG/pit tests remain for regression if procedural or pit-based terrain is reintroduced.
 * Jump logic below must match index.html handleMovement() so double jump is fully testable.
 */

const assert = require('assert');

// ----- Double-jump state machine (must match index.html: inAir, refill, ground jump, air jump, buffer) -----
function computeJumpFrame(state) {
    const { onGround, velocityY, jump, jumpJustPressed, jumpBuffer, jumpsRemaining } = state;
    const inAir = !onGround || velocityY < 0;
    let buffer = jumpJustPressed ? 5 : jumpBuffer;
    if (buffer > 0) buffer--;
    let jumps = jumpsRemaining;
    if (onGround && velocityY >= 0) jumps = 2;

    let applyGroundJump = false;
    let applyAirJump = false;
    let nextJumps = jumps;
    let nextBuffer = buffer;

    if (jump && onGround && jumps === 2) {
        applyGroundJump = true;
        nextJumps = 1;
        nextBuffer = 0;
    } else if ((jumpJustPressed || buffer > 0) && inAir && jumps > 0) {
        applyAirJump = true;
        nextJumps = jumps - 1;
        nextBuffer = 0;
    }

    return {
        applyGroundJump,
        applyAirJump,
        nextJumpsRemaining: nextJumps,
        nextBuffer,
        nextJumpWasDownLastFrame: jump
    };
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

// ========== Double-jump tests (must match index.html handleMovement) ==========
(function testJumpRefillOnGround() {
    const r = computeJumpFrame({
        onGround: true, velocityY: 0, jump: false, jumpJustPressed: false,
        jumpBuffer: 0, jumpsRemaining: 0
    });
    assert.strictEqual(r.nextJumpsRemaining, 2, 'Refill to 2 when on ground, not moving');
    assert.strictEqual(r.applyGroundJump, false);
    assert.strictEqual(r.applyAirJump, false);
})();

(function testJumpNoRefillWhenMovingUp() {
    const r = computeJumpFrame({
        onGround: true, velocityY: -100, jump: false, jumpJustPressed: false,
        jumpBuffer: 0, jumpsRemaining: 1
    });
    assert.strictEqual(r.nextJumpsRemaining, 1, 'Do not refill while moving up (Arcade one-frame delay)');
})();

(function testGroundJumpWhenEligible() {
    const r = computeJumpFrame({
        onGround: true, velocityY: 0, jump: true, jumpJustPressed: true,
        jumpBuffer: 0, jumpsRemaining: 2
    });
    assert.strictEqual(r.applyGroundJump, true);
    assert.strictEqual(r.applyAirJump, false);
    assert.strictEqual(r.nextJumpsRemaining, 1);
    assert.strictEqual(r.nextBuffer, 0, 'Buffer cleared on ground jump so holding jump does not auto double-jump');
})();

(function testNoGroundJumpWhenOnlyOneJumpLeft() {
    const r = computeJumpFrame({
        onGround: true, velocityY: 0, jump: true, jumpJustPressed: false,
        jumpBuffer: 0, jumpsRemaining: 1
    });
    assert.strictEqual(r.applyGroundJump, false, 'No ground jump when jumpsRemaining is 1 (edge case)');
})();

(function testMidAirHopOnJustPressed() {
    const r = computeJumpFrame({
        onGround: false, velocityY: -200, jump: true, jumpJustPressed: true,
        jumpBuffer: 0, jumpsRemaining: 1
    });
    assert.strictEqual(r.applyGroundJump, false);
    assert.strictEqual(r.applyAirJump, true);
    assert.strictEqual(r.nextJumpsRemaining, 0);
    assert.strictEqual(r.nextBuffer, 0);
})();

(function testMidAirHopViaBuffer() {
    const r = computeJumpFrame({
        onGround: false, velocityY: -200, jump: false, jumpJustPressed: false,
        jumpBuffer: 3, jumpsRemaining: 1
    });
    assert.strictEqual(r.applyAirJump, true, 'Mid-air hop can trigger from buffer without new press');
    assert.strictEqual(r.nextJumpsRemaining, 0);
    assert.strictEqual(r.nextBuffer, 0);
})();

(function testInAirWhenMovingUpButStillReportedOnGround() {
    const r = computeJumpFrame({
        onGround: true, velocityY: -50, jump: false, jumpJustPressed: false,
        jumpBuffer: 4, jumpsRemaining: 1
    });
    assert.strictEqual(r.applyAirJump, true, 'inAir is true when velocityY < 0 so one-frame Arcade delay still allows double jump');
})();

(function testNoAirJumpWhenNoInputAndNoBuffer() {
    const r = computeJumpFrame({
        onGround: false, velocityY: -100, jump: false, jumpJustPressed: false,
        jumpBuffer: 0, jumpsRemaining: 1
    });
    assert.strictEqual(r.applyAirJump, false);
    assert.strictEqual(r.nextJumpsRemaining, 1);
})();

(function testNoAirJumpWhenJumpsExhausted() {
    const r = computeJumpFrame({
        onGround: false, velocityY: -100, jump: true, jumpJustPressed: true,
        jumpBuffer: 0, jumpsRemaining: 0
    });
    assert.strictEqual(r.applyAirJump, false);
    assert.strictEqual(r.nextJumpsRemaining, 0);
})();

(function testBufferDecrementsEachFrame() {
    const r = computeJumpFrame({
        onGround: true, velocityY: 0, jump: false, jumpJustPressed: false,
        jumpBuffer: 2, jumpsRemaining: 2
    });
    assert.strictEqual(r.nextBuffer, 1);
})();

(function testBufferClearedOnGroundJump() {
    const r = computeJumpFrame({
        onGround: true, velocityY: 0, jump: true, jumpJustPressed: true,
        jumpBuffer: 0, jumpsRemaining: 2
    });
    assert.strictEqual(r.nextBuffer, 0, 'Buffer cleared on ground jump so holding jump does not auto double-jump');
})();

(function testBufferDecaysWhenNotConsumed() {
    const r = computeJumpFrame({
        onGround: true, velocityY: 0, jump: false, jumpJustPressed: false,
        jumpBuffer: 5, jumpsRemaining: 2
    });
    assert.strictEqual(r.nextBuffer, 4, 'Buffer decrements each frame when no jump is performed');
})();

(function testFullDoubleJumpSequence() {
    let state = { onGround: true, velocityY: 0, jump: true, jumpJustPressed: true, jumpBuffer: 0, jumpsRemaining: 2 };
    let out = computeJumpFrame(state);
    assert.strictEqual(out.applyGroundJump, true);
    assert.strictEqual(out.nextJumpsRemaining, 1);
    state = { ...state, jumpsRemaining: out.nextJumpsRemaining, jumpBuffer: out.nextBuffer, jumpWasDownLastFrame: out.nextJumpWasDownLastFrame };
    state = { onGround: false, velocityY: -300, jump: false, jumpJustPressed: true, jumpBuffer: state.jumpBuffer, jumpsRemaining: state.jumpsRemaining };
    out = computeJumpFrame(state);
    assert.strictEqual(out.applyAirJump, true, 'Second press in air triggers mid-air hop');
    assert.strictEqual(out.nextJumpsRemaining, 0);
})();

console.log('All game-logic tests passed.');
