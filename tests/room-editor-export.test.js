/**
 * Unit tests for room-layout-export-package.js (Sprint 4 runtime bundle).
 */

const assert = require('assert');
const {
  generateExportPackage,
  buildRuntimeRoom,
  normalizeRuntimeEnvironment
} = require('../room-layout-export-package.js');

const minimalLayout = {
  version: 1,
  meta: { worldWidth: 3200, worldHeight: 1200, grid: 32 },
  rooms: [
    {
      id: 'R1',
      name: 'Test',
      global: { x: 0, y: 0 },
      polygon: [
        [0, 0],
        [100, 0],
        [100, 100]
      ],
      size: { width: 800, height: 1200 },
      platforms: [{ id: 'p1', x: 0, y: 100, len: 4, tint: 0 }],
      doors: [],
      keys: [],
      abilities: [],
      movingPlatforms: [{ id: 'm1', x: 10, y: 200, endX: 100, endY: 200, len: 2, tint: 0 }],
      playerStart: { x: 50, y: 50 },
      edgeLinks: [],
      environment: {
        version: 2,
        themeId: 'ruins',
        tags: ['stone'],
        spec: {},
        preview: {},
        runtime: {
          bespoke_asset_manifest: {
            schema_version: 1,
            status: 'ready',
            biome_id: 'ruined-gothic-v1',
            source_preview_id: 'R1-lvl3-1',
            generation_plan: [],
            assets: {
              'R1-background': {
                slot_id: 'R1-background',
                component_type: 'background_plate',
                url: '/tools/2d-sprite-and-animation/projects-data/project-alpha/room_environment_assets/R1/bespoke/R1-background.png'
              }
            },
            failed_assets: [],
            used_ai: true,
            generated_at: '2026-01-01T00:00:00.000Z',
            validation_errors: []
          }
        }
      }
    }
  ]
};

const validationReport = {
  run_at: '2026-01-01T00:00:00.000Z',
  level_1: { passed: true, checks: [] },
  level_2: { passed: true, checks: [] },
  summary: { errors: 0, warnings: 0 }
};

const pkg = generateExportPackage(minimalLayout, validationReport);

assert.strictEqual(pkg.manifest.room_count, 1);
assert.strictEqual(pkg.manifest.validation_l1_passed, true);
assert.strictEqual(pkg.manifest.validation_l2_passed, true);
assert.strictEqual(pkg.manifest.validation_highest_passing_level, 2);
assert.strictEqual(pkg.manifest.engine_hints.grid_size, 32);
assert.ok(pkg.manifest.sha_simple && pkg.manifest.sha_simple.length >= 8);
assert.ok(Array.isArray(pkg.worldGraph.rooms));
assert.strictEqual(pkg.worldGraph.rooms[0].connections.length, 0);

const roomFile = pkg.roomFiles['R1.json'];
assert.ok(roomFile, 'per-room file uses safe id as filename');
assert.deepStrictEqual(roomFile.movingPlatforms, minimalLayout.rooms[0].movingPlatforms);
assert.strictEqual(roomFile.movers, undefined);
assert.deepStrictEqual(roomFile.environment, normalizeRuntimeEnvironment(minimalLayout.rooms[0]));
assert.ok(pkg.worldGraph.rooms[0].environment);

const failedL1 = {
  ...validationReport,
  level_1: { passed: false, checks: [{ id: 'L1', severity: 'error', message: 'x' }] },
  summary: { errors: 1, warnings: 0 }
};
const pkgFail = generateExportPackage(minimalLayout, failedL1);
assert.strictEqual(pkgFail.manifest.validation_highest_passing_level, 0);

const br = buildRuntimeRoom(minimalLayout.rooms[0]);
assert.strictEqual(br.id, 'R1');
assert.ok(Array.isArray(br.movingPlatforms));
assert.strictEqual(br.environment.runtime.bespoke_asset_manifest.status, 'ready');

console.log('room-editor-export.test.js: all assertions passed');
