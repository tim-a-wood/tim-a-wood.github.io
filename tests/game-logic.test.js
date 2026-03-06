/**
 * Unit tests for game logic (RNG, pit-zone helpers, and double-jump).
 * The game currently uses a bounded hand-placed zone with no procedural gen;
 * RNG/pit tests remain for regression if procedural or pit-based terrain is reintroduced.
 * Jump helpers below must match the cooldown-based double-jump behavior in index.html.
 */

const assert = require('assert');

// ----- Double-jump cooldown helpers (must match index.html) -----
function isGrounded(body) {
    return (body.blockedDown || body.touchingDown) && body.velocityY >= 0;
}

function canTouchJump(state) {
    return (state.now - state.lastTouchJumpAt) >= state.cooldownMs;
}

function applyJumpState(state) {
    const next = { ...state };

    if (isGrounded(state.body)) {
        next.jumpCount = 0;
    }

    if (state.jumpRequested && next.jumpCount < 2) {
        next.jumpCount += 1;
        next.appliedJump = true;
    } else {
        next.appliedJump = false;
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

// ========== Double-jump tests (must match index.html touch cooldown + jumpCount logic) ==========
(function testGroundDetectionBlockedDown() {
    assert.strictEqual(isGrounded({ blockedDown: true, touchingDown: false, velocityY: 0 }), true);
})();

(function testGroundDetectionTouchingDown() {
    assert.strictEqual(isGrounded({ blockedDown: false, touchingDown: true, velocityY: 0 }), true);
})();

(function testGroundDetectionRejectsUpwardMotion() {
    assert.strictEqual(isGrounded({ blockedDown: true, touchingDown: true, velocityY: -1 }), false);
})();

(function testTouchCooldownBlocksRapidRepeat() {
    assert.strictEqual(canTouchJump({ now: 100, lastTouchJumpAt: 0, cooldownMs: 180 }), false);
    assert.strictEqual(canTouchJump({ now: 181, lastTouchJumpAt: 0, cooldownMs: 180 }), true);
})();

(function testGroundJumpApplies() {
    const out = applyJumpState({
        jumpCount: 0,
        jumpRequested: true,
        body: { blockedDown: true, touchingDown: true, velocityY: 0 }
    });
    assert.strictEqual(out.appliedJump, true);
    assert.strictEqual(out.jumpCount, 1);
})();

(function testMidAirSecondJumpApplies() {
    const out = applyJumpState({
        jumpCount: 1,
        jumpRequested: true,
        body: { blockedDown: false, touchingDown: false, velocityY: -200 }
    });
    assert.strictEqual(out.appliedJump, true);
    assert.strictEqual(out.jumpCount, 2);
})();

(function testThirdJumpBlocked() {
    const out = applyJumpState({
        jumpCount: 2,
        jumpRequested: true,
        body: { blockedDown: false, touchingDown: false, velocityY: -150 }
    });
    assert.strictEqual(out.appliedJump, false);
    assert.strictEqual(out.jumpCount, 2);
})();

(function testLandingRefillsJumpCount() {
    const out = applyJumpState({
        jumpCount: 2,
        jumpRequested: false,
        body: { blockedDown: true, touchingDown: true, velocityY: 0 }
    });
    assert.strictEqual(out.appliedJump, false);
    assert.strictEqual(out.jumpCount, 0);
})();

(function testFullDoubleJumpSequence() {
    let state = {
        jumpCount: 0,
        jumpRequested: true,
        body: { blockedDown: true, touchingDown: true, velocityY: 0 }
    };

    state = applyJumpState(state);
    assert.strictEqual(state.jumpCount, 1);
    assert.strictEqual(state.appliedJump, true);

    state = applyJumpState({
        jumpCount: state.jumpCount,
        jumpRequested: true,
        body: { blockedDown: false, touchingDown: false, velocityY: -300 }
    });

    assert.strictEqual(state.jumpCount, 2);
    assert.strictEqual(state.appliedJump, true);
})();

console.log('All game-logic tests passed.');
