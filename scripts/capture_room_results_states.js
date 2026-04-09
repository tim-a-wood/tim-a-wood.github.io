#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const REMOTE_DEBUGGING_PORT = 9222;
const DEFAULT_EDITOR_URL = 'http://127.0.0.1:8766/room-layout-editor.html';
const OUTPUT_DIR = path.join(process.cwd(), 'artifacts', 'qa', 'room-results-states');

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function formatExceptionDetails(details) {
  if (!details) return 'unknown browser exception';
  const description = details.exception?.description || details.text || 'unknown browser exception';
  const location = details.lineNumber != null
    ? ` (line ${Number(details.lineNumber) + 1}, column ${Number(details.columnNumber || 0) + 1})`
    : '';
  return `${description}${location}`;
}

async function fetchJson(url, retries = 30) {
  let lastError;
  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      lastError = error;
      await delay(250);
    }
  }
  throw lastError;
}

async function fetchText(url, retries = 30) {
  let lastError;
  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return await response.text();
    } catch (error) {
      lastError = error;
      await delay(250);
    }
  }
  throw lastError;
}

class CdpClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 0;
    this.pending = new Map();
    this.events = new Map();
    this.openPromise = new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
    this.ws.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const slot = this.pending.get(message.id);
        if (!slot) return;
        this.pending.delete(message.id);
        if (message.error) {
          slot.reject(new Error(message.error.message || 'CDP error'));
        } else {
          slot.resolve(message.result || {});
        }
        return;
      }
      if (message.method) {
        const listeners = this.events.get(message.method) || [];
        for (const listener of listeners) {
          listener(message.params || {});
        }
      }
    });
  }

  async open() {
    await this.openPromise;
  }

  send(method, params = {}) {
    const id = ++this.id;
    const payload = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(payload);
    });
  }

  on(method, listener) {
    const listeners = this.events.get(method) || [];
    listeners.push(listener);
    this.events.set(method, listeners);
  }

  async close() {
    if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
      this.ws.close();
      await delay(100);
    }
  }
}

function launchChrome(editorUrl) {
  const chromeBinary = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mv-results-cdp-'));
  const args = [
    `--remote-debugging-port=${REMOTE_DEBUGGING_PORT}`,
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--hide-scrollbars',
    '--mute-audio',
    '--window-size=1680,2400',
    `--user-data-dir=${userDataDir}`,
    editorUrl,
  ];
  const proc = spawn(chromeBinary, args, {
    stdio: 'ignore',
  });
  return { proc, userDataDir };
}

function makeInjectionSource(variantName) {
  return `
(() => {
  const variant = ${JSON.stringify(variantName)};
  const baseRoom = {
    id: 'QA-R1',
    name: 'Calibration Gatehouse',
    size: { width: 1600, height: 1200 },
    global: { x: 640, y: 360 },
    polygon: [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
    platforms: [
      { id: 'QA-R1-P1', x: 224, y: 960, len: 22 },
      { id: 'QA-R1-P2', x: 640, y: 736, len: 10 },
    ],
    movingPlatforms: [],
    doors: [
      { id: 'QA-R1-D1', x: 160, y: 960, kind: 'transition' },
      { id: 'QA-R1-D2', x: 1440, y: 960, kind: 'transition' },
    ],
    keys: [],
    abilities: [],
    playerStart: { x: 320, y: 928 },
    edgeLinks: [],
    removedEdges: [],
  };

  const baseEnvironment = {
    environment_pipeline_version: 'v3',
    themeId: 'ruined-gothic',
    tags: ['ruined', 'gothic', 'threshold'],
    spec: {
      theme_name: 'Ruined Gothic Gatehouse',
      notes: 'Calibration room for embedded Results-tab browser QA.',
      seed: 'rg-gatehouse-seed',
      lock_stylepack: false,
      reference_uploads: [
        {
          id: 'ref-1',
          label: 'Masonry arches',
          file_name: 'masonry-arches.png',
          file_type: 'image/png',
          file_size: 245760,
          status: 'uploaded',
          pinned_to: 'stylepack',
          source_value: 'masonry-arches.png',
          uploaded_at: '2026-04-05T10:00:00Z',
        }
      ],
      description: 'A readable threshold room with clear side shell framing and a calm center route.',
      component_schemas: {
        floor: {},
        platforms: {},
        walls: {},
        doors: {},
        background: {},
        midground: {},
        ceiling: {},
        backwall_panel: {},
      },
      scene_schema: {
        set_dressing: [
          { anchor: 'left_wall', decor_type: 'banner_cluster', x: 236, y: 328 }
        ],
      },
    },
    preview: {
      status: 'ready',
      approved_image_id: null,
      last_generated_at: '2026-04-05T10:05:00Z',
      images: [
        {
          preview_id: 'preview-1',
          url: '/map-birdseye-current.png',
          rationale: 'Readable threshold shell with subdued background depth.',
        }
      ],
    },
    room_intent: {
      room_role: 'threshold',
    },
    assembly_plan: {
      slots: [
        {
          slot_id: 'wall-left',
          component_type: 'wall_module_left',
          schema_key: 'walls',
          placement: { display_width: 320, display_height: 880 },
          target_dimensions: { width: 320, height: 880 },
        },
        {
          slot_id: 'floor-top',
          component_type: 'main_floor_top',
          schema_key: 'floor',
          placement: { display_width: 512, display_height: 96 },
          target_dimensions: { width: 512, height: 96 },
        },
        {
          slot_id: 'mid-frame',
          component_type: 'midground_side_frame',
          schema_key: 'midground',
          placement: { display_width: 1600, display_height: 1200 },
          target_dimensions: { width: 1600, height: 1200 },
        },
      ],
      overlay_geometry: {
        room_polygon: [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
        doors: [
          { id: 'QA-R1-D1', x: 160, y: 960 },
          { id: 'QA-R1-D2', x: 1440, y: 960 },
        ],
        platforms: [
          { id: 'QA-R1-P1', x: 224, y: 960, len: 22 },
          { id: 'QA-R1-P2', x: 640, y: 736, len: 10 },
        ],
        slot_overlays: [
          { slot_id: 'wall-left' },
          { slot_id: 'floor-top' },
          { slot_id: 'mid-frame' },
        ],
      },
      planner_coverage_summary: {
        status: 'pass',
        major_structures: {
          door_count: 2,
          platform_count: 2,
          planned_door_slots: 2,
          planned_platform_slots: 2,
        },
        missing_slots: [],
        blockers: [],
      },
    },
    review_state: {
      approval_status: 'draft',
      validation_status: {
        status: 'pending',
        issues: ['runtime_review_pending'],
      },
      runtime_review: {
        status: 'idle',
        fail_reasons: [],
        warning_reasons: [],
        metrics: {},
        screenshot_url: null,
        review_mode: null,
      },
    },
    reference_pack: {
      reference_pack_id: 'reference-pack-q1',
      status: 'ready',
      summary: { upload_count: 1, canonical_count: 1 },
    },
    stylepack: {
      stylepack_id: 'stylepack-q1',
      status: 'draft',
      locked: false,
      summary: 'Ruined-gothic threshold with subdued cyan accent and restrained scenic drift.',
      material_vocabulary: ['worn stone', 'oxidized iron'],
      shape_language: ['broad arch', 'broken lintel'],
      motif_vocabulary: ['gatehouse ribs'],
      forbidden_drift_traits: ['altar clutter'],
    },
    room_semantics: {
      room_id: 'QA-R1',
      room_role: 'threshold',
      summary: { top_count: 2, opening_count: 2, cavity_count: 0 },
      overlay_keys: ['room_polygon', 'platform_tops', 'openings', 'gameplay_exclusion_zones'],
      overlay_geometry: {
        room_polygon: [[160, 160], [1440, 160], [1440, 1040], [160, 1040]],
        platform_tops: [
          { x: 224, y: 960, width: 352, height: 32 },
          { x: 640, y: 736, width: 160, height: 32 },
        ],
        openings: [
          { x: 160, y: 960, width: 96, height: 224 },
          { x: 1440, y: 960, width: 96, height: 224 },
        ],
      },
      truth_checks: [
        { code: 'doors_accounted_for', status: 'pass' }
      ],
    },
    environment_kit: {
      status: 'ready',
      summary: {
        component_count: 4,
        structural_count: 2,
        background_count: 1,
        decor_count: 1,
      },
      component_count_by_type: {
        wall_module_left: 1,
        main_floor_top: 1,
        midground_side_frame: 1,
        banner_cluster: 1,
      },
      taxonomy: {
        classes: {
          structural: { default_readability_impact: 'high' },
          background: { default_readability_impact: 'medium' },
          decor: { default_readability_impact: 'low' },
        },
      },
      validation_errors: [],
    },
    environment_manifest: {
      status: 'ready',
      stylepack_id: 'stylepack-q1',
      layer_order: ['structural', 'background', 'decor'],
      layers: {
        structural: [{ slot_id: 'wall-left' }, { slot_id: 'floor-top' }],
        background: [{ slot_id: 'mid-frame' }],
        decor: [],
      },
      passes: {
        sequence: [
          { pass_name: 'structural' },
          { pass_name: 'background' },
          { pass_name: 'decor' },
        ],
      },
      placement_summary: {
        total_count: 3,
        layers: {
          structural: { count: 2, slot_ids: ['wall-left', 'floor-top'] },
          background: { count: 1, slot_ids: ['mid-frame'] },
          decor: { count: 0, slot_ids: [] },
        },
      },
      generation_metadata: {
        structural_count: 2,
        background_count: 1,
        decor_count: 0,
        placement_count: 3,
        pass_order: ['structural', 'background', 'decor'],
      },
      deterministic_replay: {
        seed: 'rg-gatehouse-seed',
        replay_key: 'QA-R1:stylepack-q1:rg-gatehouse-seed:fingerprint',
      },
    },
    validation_report: {
      status: 'ready',
      blocker_count: 0,
      warning_count: 1,
      info_count: 1,
      findings: {
        blockers: [],
        warnings: [
          { severity: 'warning', code: 'floor_background_separation_low', message: 'Background separation should be checked in browser.' }
        ],
        info: [
          { severity: 'info', code: 'visual_validation_backed_by_screenshot', message: 'Browser-backed evidence still required.' }
        ],
      },
      validation_highlights: {
        unresolved_surfaces: [],
        wrong_surface_placements: [],
        gameplay_intrusions: [],
      },
      unresolved_surfaces: [],
    },
    staged_artifacts: {
      reference_pack: { status: 'ready', relative_path: 'derived/v3/reference_pack.json' },
      stylepack: { status: 'ready', relative_path: 'derived/v3/stylepack.json' },
      room_semantics: { status: 'ready', relative_path: 'derived/v3/room_semantics.json' },
      environment_kit: { status: 'ready', relative_path: 'derived/v3/environment_kit.json' },
      environment_manifest: { status: 'ready', relative_path: 'derived/v3/environment_manifest.json' },
      validation_report: { status: 'ready', relative_path: 'derived/v3/validation_report.json' },
    },
    editor_results_payload: {
      pipeline_version: 'v3',
      stylepack: { status: 'draft', summary: 'Ruined-gothic threshold with subdued cyan accent and restrained scenic drift.' },
      semantics: {
        status: 'ready',
        counts: { top_count: 2, opening_count: 2 },
        overlay_keys: ['room_polygon', 'platform_tops', 'openings'],
      },
      kit: {
        status: 'ready',
        summary: { component_count: 4, structural_count: 2, background_count: 1, decor_count: 1 },
        component_count_by_type: {
          wall_module_left: 1,
          main_floor_top: 1,
          midground_side_frame: 1,
          banner_cluster: 1,
        },
        taxonomy: { classes: { structural: { default_readability_impact: 'high' } } },
        validation_errors: [],
      },
      manifest: {
        status: 'ready',
        layer_order: ['structural', 'background', 'decor'],
        generation_metadata: {
          structural_count: 2,
          background_count: 1,
          decor_count: 0,
          placement_count: 3,
        },
        placement_summary: {
          layers: {
            structural: { count: 2 },
            background: { count: 1 },
            decor: { count: 0 },
          },
        },
        deterministic_replay: {
          seed: 'rg-gatehouse-seed',
          replay_key: 'QA-R1:stylepack-q1:rg-gatehouse-seed:fingerprint',
        },
      },
      validation: {
        status: 'ready',
        blocker_count: 0,
        findings: {
          blockers: [],
          warnings: [{ severity: 'warning', code: 'floor_background_separation_low', message: 'Background separation should be checked in browser.' }],
          info: [{ severity: 'info', code: 'visual_validation_backed_by_screenshot', message: 'Browser-backed evidence still required.' }],
        },
        blockers: [],
        warnings: [{ severity: 'warning', code: 'floor_background_separation_low', message: 'Background separation should be checked in browser.' }],
        validation_highlights: {
          unresolved_surfaces: [],
        },
      },
    },
    runtime: {
      status: 'idle',
      bespoke_asset_manifest: {
        status: 'idle',
        required_slots: ['wall-left', 'floor-top', 'mid-frame'],
        built_slots: [],
        slot_groups: {
          structural: { built: 0, required: 2 },
          background: { built: 0, required: 1 },
          decor: { built: 0, required: 0 },
        },
        schema_validation: { status: 'idle', valid: false, errors: [] },
        runtime_review: {
          status: 'idle',
          fail_reasons: [],
          warning_reasons: [],
          metrics: {},
          screenshot_url: null,
          review_mode: null,
          capture_issue: null,
        },
        review: {
          status: 'idle',
          fail_reasons: [],
          warning_reasons: [],
          metrics: {},
          screenshot_url: null,
          review_mode: null,
          capture_issue: null,
        },
        assets: {},
        failed_assets: [],
        validation_errors: [],
        used_ai: true,
        generated_at: '2026-04-05T10:08:00Z',
      },
    },
  };

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function makeEnvironment(name) {
    const env = clone(baseEnvironment);
    if (name === 'empty') {
      env.preview = { status: 'idle', approved_image_id: null, images: [] };
      env.runtime.bespoke_asset_manifest.status = 'idle';
      env.editor_results_payload.stylepack.status = 'draft';
      env.review_state.validation_status.status = 'pending';
      env.validation_report.blocker_count = 0;
      env.validation_report.warning_count = 0;
      env.validation_report.findings.warnings = [];
      env.editor_results_payload.validation.warnings = [];
      env.editor_results_payload.validation.findings.warnings = [];
      env.environment_manifest.status = 'idle';
      env.editor_results_payload.manifest.status = 'idle';
    } else if (name === 'draft') {
      env.spec.lock_stylepack = false;
      env.stylepack.status = 'draft';
      env.stylepack.locked = false;
      env.editor_results_payload.stylepack.status = 'draft';
      env.preview.approved_image_id = null;
    } else if (name === 'locked') {
      env.spec.lock_stylepack = true;
      env.stylepack.status = 'locked';
      env.stylepack.locked = true;
      env.editor_results_payload.stylepack.status = 'locked';
      env.preview.approved_image_id = null;
    } else if (name === 'generating') {
      env.preview.approved_image_id = 'preview-1';
      env.review_state.validation_status.status = 'running';
      env.runtime.bespoke_asset_manifest.status = 'running';
      env.runtime.bespoke_asset_manifest.built_slots = ['wall-left'];
      env.runtime.bespoke_asset_manifest.slot_groups.structural.built = 1;
      env.runtime.bespoke_asset_manifest.runtime_review.status = 'running';
      env.runtime.bespoke_asset_manifest.review.status = 'running';
    } else if (name === 'partial') {
      env.preview.approved_image_id = 'preview-1';
      env.review_state.validation_status.status = 'warning';
      env.runtime.bespoke_asset_manifest.status = 'failed';
      env.runtime.bespoke_asset_manifest.built_slots = ['wall-left', 'floor-top'];
      env.runtime.bespoke_asset_manifest.slot_groups.structural.built = 2;
      env.runtime.bespoke_asset_manifest.failed_assets = ['mid-frame'];
      env.runtime.bespoke_asset_manifest.validation_errors = ['midground_generation_failed'];
      env.runtime.bespoke_asset_manifest.runtime_review.status = 'blocked';
      env.runtime.bespoke_asset_manifest.runtime_review.fail_reasons = ['slot_generation_failed'];
      env.runtime.bespoke_asset_manifest.review = clone(env.runtime.bespoke_asset_manifest.runtime_review);
      env.validation_report.blocker_count = 1;
      env.validation_report.findings.blockers = [
        { severity: 'blocker', code: 'slot_generation_failed', message: 'Midground slot did not produce a valid artifact.' }
      ];
      env.editor_results_payload.validation.blocker_count = 1;
      env.editor_results_payload.validation.blockers = clone(env.validation_report.findings.blockers);
      env.editor_results_payload.validation.findings.blockers = clone(env.validation_report.findings.blockers);
    } else if (name === 'ready') {
      env.spec.lock_stylepack = true;
      env.stylepack.status = 'locked';
      env.stylepack.locked = true;
      env.editor_results_payload.stylepack.status = 'locked';
      env.preview.approved_image_id = 'preview-1';
      env.review_state.approval_status = 'approved';
      env.review_state.validation_status.status = 'complete';
      env.review_state.runtime_review.status = 'pass';
      env.runtime.status = 'ready';
      env.runtime.bespoke_asset_manifest.status = 'ready';
      env.runtime.bespoke_asset_manifest.built_slots = ['wall-left', 'floor-top', 'mid-frame'];
      env.runtime.bespoke_asset_manifest.slot_groups.structural.built = 2;
      env.runtime.bespoke_asset_manifest.slot_groups.background.built = 1;
      env.runtime.bespoke_asset_manifest.runtime_review = {
        status: 'pass',
        fail_reasons: [],
        warning_reasons: [],
        metrics: { threshold_visibility: 0.11, platform_top_readability: 0.08 },
        screenshot_url: '/map-birdseye-topology-scale.png',
        review_mode: 'headless_browser',
        capture_issue: null,
        generated_at: '2026-04-05T10:12:00Z',
      };
      env.runtime.bespoke_asset_manifest.review = clone(env.runtime.bespoke_asset_manifest.runtime_review);
      env.runtime.bespoke_asset_manifest.assets = {
        'wall-left': { slot_id: 'wall-left', component_type: 'wall_module_left', url: '/map-birdseye-current.png', generation_source: 'ai_generated' },
        'floor-top': { slot_id: 'floor-top', component_type: 'main_floor_top', url: '/map-birdseye-topology-scale.png', generation_source: 'ai_generated' },
      };
      env.editor_results_payload.validation.status = 'ready';
    } else if (name === 'blocked') {
      env.spec.lock_stylepack = true;
      env.stylepack.status = 'locked';
      env.stylepack.locked = true;
      env.editor_results_payload.stylepack.status = 'locked';
      env.preview.approved_image_id = 'preview-1';
      env.review_state.approval_status = 'blocked';
      env.review_state.validation_status.status = 'blocked';
      env.review_state.validation_status.issues = ['browser_capture_required', 'threshold_visibility_low'];
      env.review_state.runtime_review.status = 'fail';
      env.review_state.runtime_review.fail_reasons = ['browser_capture_required', 'threshold_visibility_low'];
      env.runtime.status = 'blocked';
      env.runtime.bespoke_asset_manifest.status = 'ready';
      env.runtime.bespoke_asset_manifest.built_slots = ['wall-left', 'floor-top', 'mid-frame'];
      env.runtime.bespoke_asset_manifest.slot_groups.structural.built = 2;
      env.runtime.bespoke_asset_manifest.slot_groups.background.built = 1;
      env.runtime.bespoke_asset_manifest.runtime_review = {
        status: 'fail',
        fail_reasons: ['browser_capture_required', 'threshold_visibility_low'],
        warning_reasons: ['floor_background_separation_low'],
        metrics: { threshold_visibility: 0.01, platform_top_readability: 0.08 },
        screenshot_url: '/map-birdseye-current.png',
        review_mode: 'composite_fallback',
        capture_issue: 'headless_browser_failed',
        generated_at: '2026-04-05T10:14:00Z',
      };
      env.runtime.bespoke_asset_manifest.review = clone(env.runtime.bespoke_asset_manifest.runtime_review);
      env.validation_report.blocker_count = 2;
      env.validation_report.findings.blockers = [
        { severity: 'blocker', code: 'browser_capture_required', message: 'Composite fallback cannot be approval evidence.' },
        { severity: 'blocker', code: 'threshold_visibility_low', message: 'Door threshold read is too weak in runtime review.' },
      ];
      env.editor_results_payload.validation.blocker_count = 2;
      env.editor_results_payload.validation.blockers = clone(env.validation_report.findings.blockers);
      env.editor_results_payload.validation.findings.blockers = clone(env.validation_report.findings.blockers);
    }
    return env;
  }

  if (!window.__ROOM_WIZARD_QA__ || typeof window.__ROOM_WIZARD_QA__.applyResultsEnvironment !== 'function') {
    throw new Error('window.__ROOM_WIZARD_QA__.applyResultsEnvironment is not available');
  }
  return window.__ROOM_WIZARD_QA__.applyResultsEnvironment(makeEnvironment(variant));
})();
`;
}

async function waitForPageReady(cdp) {
  let loaded = false;
  cdp.on('Page.loadEventFired', () => {
    loaded = true;
  });
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Page.navigate', { url: DEFAULT_EDITOR_URL });
  for (let i = 0; i < 120 && !loaded; i += 1) {
    await delay(250);
  }
  if (!loaded) {
    throw new Error('Timed out waiting for room-layout-editor.html to load.');
  }
  await delay(1500);
}

async function captureState(cdp, variant) {
  const evalResult = await cdp.send('Runtime.evaluate', {
    expression: makeInjectionSource(variant),
    awaitPromise: true,
    returnByValue: true,
  });
  if (evalResult.exceptionDetails) {
    throw new Error(`Injection failed for ${variant}: ${formatExceptionDetails(evalResult.exceptionDetails)}`);
  }
  await delay(400);
  const layoutResult = await cdp.send('Runtime.evaluate', {
    expression: `(() => {
      const panel = document.getElementById('rwEnvPanelResults');
      const activeTab = document.getElementById('rwEnvTabResults');
      const stageLabels = Array.from(document.querySelectorAll('#rwEnvPanelResults .rw-environment-preview-label')).map((node) => node.textContent.trim());
      const buildButton = document.getElementById('roomWizardBuildEnvironmentAssets');
      const doc = document.documentElement;
      const el = document.getElementById('rwEnvPanelResults');
      return {
        panel_hidden: !!panel?.hidden,
        tab_selected: activeTab?.getAttribute('aria-selected'),
        build_button_text: buildButton?.textContent?.trim() || '',
        build_button_disabled: !!buildButton?.disabled,
        stage_labels: stageLabels,
        scroll_width: Math.max(doc.scrollWidth, document.body?.scrollWidth || 0, window.innerWidth || 0),
        scroll_height: Math.max(doc.scrollHeight, document.body?.scrollHeight || 0, window.innerHeight || 0),
      };
    })()`,
    returnByValue: true,
  });
  if (layoutResult.exceptionDetails) {
    throw new Error(`Layout probe failed for ${variant}: ${formatExceptionDetails(layoutResult.exceptionDetails)}`);
  }
  const layout = layoutResult.result.value || {};
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: Math.max(1680, Number(layout.scroll_width || 1680)),
    height: Math.max(2400, Number(layout.scroll_height || 2400)),
    deviceScaleFactor: 1,
    mobile: false,
  });
  await delay(200);
  const screenshot = await cdp.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: true,
  });
  const filePath = path.join(OUTPUT_DIR, `${variant}.png`);
  fs.writeFileSync(filePath, Buffer.from(screenshot.data, 'base64'));
  return {
    variant,
    screenshot: filePath,
    details: {
      ...(evalResult.result.value || {}),
      ...layout,
    },
  };
}

async function main() {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  await fetchText(DEFAULT_EDITOR_URL);

  const { proc, userDataDir } = launchChrome(DEFAULT_EDITOR_URL);
  try {
    const targets = await fetchJson(`http://127.0.0.1:${REMOTE_DEBUGGING_PORT}/json/list`, 80);
    const pageTarget = Array.isArray(targets)
      ? targets.find((item) => String(item.url || '').includes('room-layout-editor.html'))
      : null;
    if (!pageTarget || !pageTarget.webSocketDebuggerUrl) {
      throw new Error('Could not find a debuggable room-layout-editor page target.');
    }
    const cdp = new CdpClient(pageTarget.webSocketDebuggerUrl);
    await cdp.open();
    try {
      await waitForPageReady(cdp);
      await cdp.send('Emulation.setDeviceMetricsOverride', {
        width: 1680,
        height: 2400,
        deviceScaleFactor: 1,
        mobile: false,
      });
      const variants = ['empty', 'draft', 'locked', 'generating', 'partial', 'ready', 'blocked'];
      const results = [];
      for (const variant of variants) {
        results.push(await captureState(cdp, variant));
      }
      const summaryPath = path.join(OUTPUT_DIR, 'summary.json');
      fs.writeFileSync(summaryPath, JSON.stringify({
        editor_url: DEFAULT_EDITOR_URL,
        generated_at: new Date().toISOString(),
        variants: results,
      }, null, 2));
      console.log(JSON.stringify({ ok: true, output_dir: OUTPUT_DIR, summary: summaryPath, variants: results }, null, 2));
    } finally {
      await cdp.close();
    }
  } finally {
    proc.kill('SIGTERM');
    await delay(500);
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
