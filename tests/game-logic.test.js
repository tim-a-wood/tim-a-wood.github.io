/**
 * Unit tests for game logic. Algorithms below mirror index.html for deterministic checks.
 * Update when changing RNG or pit-zone logic in index.html.
 */

const assert = require('assert');

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

console.log('All game-logic tests passed.');
