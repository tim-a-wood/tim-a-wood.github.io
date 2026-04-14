'use strict';

/**
 * Splits scripts/_merged_editor_body.js into js/editor/*.js UMD modules (spec v1.3).
 * Run: node scripts/build-room-editor-modules.cjs
 */

const fs = require('fs');
const path = require('path');
const espree = require('espree');
const eslintScope = require('eslint-scope');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(__dirname, '_merged_editor_body.js');
const OUT_DIR = path.join(ROOT, 'js', 'editor');
const MAP = JSON.parse(fs.readFileSync(path.join(__dirname, 'function-module-map.json'), 'utf8'));

const NS_KEY = {
  constants: 'Constants',
  state: 'State',
  model: 'Model',
  topology: 'Topology',
  validation: 'Validation',
  workflow: 'Workflow',
  wizard: 'Wizard',
  wizardAsync: 'Wizard',
  wizardEvents: 'Wizard',
  viewport: 'Viewport',
  render: 'Render',
  storage: 'Storage',
  ui: 'Ui',
  input: 'Input',
  gamePreview: 'GamePreview',
};

const CONST_VARS = new Set([
  'DATA_URL',
  'API_PING_URL',
  'API_LAYOUT_URL',
  'API_COPILOT_URL',
  'ROOM_ENV_ARCHETYPES_URL',
  'LOCAL_STORAGE_PREFIX',
  'SIDEBAR_KEY',
  'ROOM_W',
  'ROOM_H',
  'TILE',
  'VALIDATION_L2',
  'PLATFORM_H',
  'ROOM_MARGIN_LEFT',
  'ROOM_MARGIN_RIGHT',
  'ROOM_MARGIN_TOP',
  'ROOM_MARGIN_BOTTOM',
  'GLOBAL_ROOM_PREVIEW_SCALE',
  'HIT_VERTEX',
  'HIT_DOOR_X',
  'HIT_DOOR_Y',
  'HIT_PLATFORM_PAD',
  'HIT_GLOBAL_PAD',
  'HIT_LINK_GUIDE_PAD',
  'HIT_ROOM_EDGE_PAD',
  'GLOBAL_DRAG_START_DISTANCE',
  'VIEW_PAN_STEP',
  'ROOM_ZOOM_MIN',
  'ROOM_ZOOM_MAX',
  'GLOBAL_ZOOM_MIN',
  'GLOBAL_ZOOM_MAX',
  'ABILITY_DEFS',
  'WORKBENCH_URL',
  'ROOM_EDITOR_URL',
  'TERRAIN_PRESET_FAIL',
  'RW_FOOTPRINT_PRESETS',
]);

/** Names that live on `RoomEditor.State` for cross-module access. Lexical helpers like PAGE_PARAMS stay local. */
const STATE_VARS = new Set([
  'PROJECT_ID',
  'LOCAL_SLOT',
  'PROJECT_ART_DIRECTION_URL',
  'PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL',
  'PROJECT_BIOME_GENERATE_VISUALS_URL',
  'PROJECT_ART_DIRECTION_TEMPLATES_URL',
  'PROJECT_LAYOUT_API_URL',
  'PROJECT_LAYOUT_DOWNLOAD_NAME',
  'LAYOUT_STORAGE_KEY',
  'SEED_DATA',
  'ROOM_AI_SESSION_ID',
]);

const VIEWPORT_VARS = new Set(['roomCanvas', 'roomCtx', 'globalCanvas', 'globalCtx']);

const fnToModule = {};
for (const [mod, names] of Object.entries(MAP)) {
  if (mod === 'constants' || !Array.isArray(names)) continue;
  for (const n of names) fnToModule[n] = mod;
}

function buildAstWithParents(ast) {
  function walk(node, parent) {
    node.parent = parent;
    for (const key of Object.keys(node)) {
      if (key === 'parent') continue;
      const v = node[key];
      if (Array.isArray(v)) {
        for (const child of v) {
          if (child && typeof child === 'object' && child.type) walk(child, node);
        }
      } else if (v && typeof v === 'object' && v.type) {
        walk(v, node);
      }
    }
  }
  walk(ast, null);
}

function homeModuleFromNode(node) {
  let p = node.parent;
  while (p) {
    if (p.type === 'FunctionDeclaration' && p.id && fnToModule[p.id.name]) {
      return fnToModule[p.id.name];
    }
    p = p.parent;
  }
  return 'top';
}

function stripUseStrictProgram(src, ast) {
  if (!ast.body.length) return { src, ast };
  const first = ast.body[0];
  if (
    first.type === 'ExpressionStatement' &&
    first.expression.type === 'Literal' &&
    first.expression.value === 'use strict'
  ) {
    const next = src.slice(first.range[1]).replace(/^\s*\n?/, '');
    const ast2 = espree.parse(next, { ecmaVersion: 2022, range: true, loc: true });
    return { src: next, ast: ast2 };
  }
  return { src, ast };
}

function preprocessLets(src) {
  return src
    .replace(
      /^\s*const SEED_DATA = JSON\.parse\(document\.getElementById\('seedData'\)\.textContent\);\s*$/m,
      '  /* SEED_DATA: assigned in init.js after fetch("./room-layout-seed.json") */'
    )
    .replace(/structuredClone\(SEED_DATA\)/g, 'structuredClone(RoomEditor.State.SEED_DATA)');
}

function qualifySource(src) {
  const ast0 = espree.parse(src, { ecmaVersion: 2022, range: true, loc: true });
  const { src: src1, ast } = stripUseStrictProgram(src, ast0);
  buildAstWithParents(ast);
  const scopeManager = eslintScope.analyze(ast, { ecmaVersion: 2022, sourceType: 'script' });
  const edits = [];

  function walkN(node) {
    if (node.type === 'AssignmentExpression' && node.left.type === 'Identifier') {
      const n = node.left.name;
      if (STATE_VARS.has(n) || CONST_VARS.has(n) || VIEWPORT_VARS.has(n)) {
        let repl = null;
        if (STATE_VARS.has(n)) repl = `RoomEditor.State.${n}`;
        else if (CONST_VARS.has(n)) repl = `RoomEditor.Constants.${n}`;
        else if (VIEWPORT_VARS.has(n)) repl = `RoomEditor.Viewport.${n}`;
        if (repl) {
          edits.push({ start: node.left.range[0], end: node.left.range[1], text: repl });
        }
      }
    }
    if (node.type === 'UpdateExpression' && node.argument.type === 'Identifier') {
      const n = node.argument.name;
      if (STATE_VARS.has(n)) {
        edits.push({
          start: node.argument.range[0],
          end: node.argument.range[1],
          text: `RoomEditor.State.${n}`,
        });
      }
    }
    if (node.type === 'CallExpression' || node.type === 'OptionalCallExpression') {
      const c = node.callee;
      if (c && c.type === 'Identifier' && fnToModule[c.name]) {
        const target = fnToModule[c.name];
        const home = homeModuleFromNode(node);
        // Top-level statements in the merged file are sliced into per-module files; calls to
        // `state` functions at program scope stay unqualified so they resolve to local decls in state.js.
        if (home !== target && !(home === 'top' && target === 'state')) {
          edits.push({
            start: c.range[0],
            end: c.range[1],
            text: `RoomEditor.${NS_KEY[target]}.${c.name}`,
          });
        }
      }
    }
    for (const key of Object.keys(node)) {
      if (key === 'parent') continue;
      const v = node[key];
      if (Array.isArray(v)) {
        for (const ch of v) {
          if (ch && ch.type) walkN(ch);
        }
      } else if (v && v.type) {
        walkN(v);
      }
    }
  }
  walkN(ast);

  const globalScope = scopeManager.scopes[0];
  if (globalScope && globalScope.through) {
    for (const ref of globalScope.through) {
      const name = ref.identifier.name;
      if (!CONST_VARS.has(name) && !STATE_VARS.has(name) && !VIEWPORT_VARS.has(name)) continue;
      let repl = null;
      if (CONST_VARS.has(name)) repl = `RoomEditor.Constants.${name}`;
      else if (STATE_VARS.has(name)) repl = `RoomEditor.State.${name}`;
      else if (VIEWPORT_VARS.has(name)) repl = `RoomEditor.Viewport.${name}`;
      const id = ref.identifier;
      const parent = id.parent;
      if (parent.type === 'MemberExpression' && parent.property === id && !parent.computed) continue;
      if (parent.type === 'Property' && parent.key === id && !parent.computed) continue;
      edits.push({ start: id.range[0], end: id.range[1], text: repl });
    }
  }

  for (const scope of scopeManager.scopes) {
    if (scope.type !== 'global') continue;
    for (const variable of scope.variables) {
      const name = variable.name;
      if (!CONST_VARS.has(name) && !STATE_VARS.has(name) && !VIEWPORT_VARS.has(name)) continue;
      let repl = null;
      if (CONST_VARS.has(name)) repl = `RoomEditor.Constants.${name}`;
      else if (STATE_VARS.has(name)) repl = `RoomEditor.State.${name}`;
      else if (VIEWPORT_VARS.has(name)) repl = `RoomEditor.Viewport.${name}`;

      for (const ref of variable.references) {
        if (ref.isWrite()) continue;
        const id = ref.identifier;
        const parent = id.parent;
        if (parent.type === 'MemberExpression' && parent.property === id && !parent.computed) continue;
        if (parent.type === 'Property' && parent.key === id && !parent.computed) continue;
        if (parent.type === 'VariableDeclarator' && parent.id === id) continue;
        if (parent.type === 'FunctionDeclaration' && parent.id === id) continue;
        edits.push({ start: id.range[0], end: id.range[1], text: repl });
      }
    }
  }

  edits.sort((a, b) => b.start - a.start);
  let out = src1;
  for (const e of edits) {
    out = out.slice(0, e.start) + e.text + out.slice(e.end);
  }
  return `'use strict';\n` + out;
}

const BOOT_CALLEE = new Set([
  'populateAbilityOptions',
  'initSidebarToggle',
  'installRoomWizardQaHooks',
  'wireRoomWizardEvents',
  'wireGamePreview',
  'wireEvents',
  'refreshProjectList',
  'loadData',
  'refreshCopilotStatus',
]);

function isUseStrictProgramStmt(node) {
  return (
    node.type === 'ExpressionStatement' &&
    node.expression.type === 'Literal' &&
    node.expression.value === 'use strict'
  );
}

function isBootCallExpression(e) {
  if (e.type !== 'CallExpression') return false;
  const cal = e.callee;
  if (cal.type === 'Identifier' && BOOT_CALLEE.has(cal.name)) return true;
  if (
    cal.type === 'MemberExpression' &&
    !cal.computed &&
    cal.property.type === 'Identifier' &&
    BOOT_CALLEE.has(cal.property.name)
  ) {
    return true;
  }
  return false;
}

function isBootSideEffectStatement(node) {
  if (isUseStrictProgramStmt(node)) return true;
  if (node.type !== 'ExpressionStatement') return false;
  const e = node.expression;
  if (
    e.type === 'AssignmentExpression' &&
    e.left.type === 'MemberExpression' &&
    !e.left.computed &&
    e.left.object.type === 'Identifier' &&
    e.left.object.name === 'window' &&
    e.left.property.type === 'Identifier' &&
    (e.left.property.name === 'validateLayout' || e.left.property.name === 'VALIDATION_L2')
  ) {
    return true;
  }
  if (e.type === 'CallExpression') {
    if (isBootCallExpression(e)) return true;
    if (
      e.callee.type === 'MemberExpression' &&
      !e.callee.computed &&
      e.callee.property.type === 'Identifier' &&
      e.callee.property.name === 'catch' &&
      e.callee.object.type === 'CallExpression' &&
      isBootCallExpression(e.callee.object)
    ) {
      return true;
    }
  }
  if (e.type === 'ChainExpression') {
    const inner = e.expression;
    if (
      inner.type === 'CallExpression' &&
      inner.callee.type === 'MemberExpression' &&
      inner.arguments.some((a) => a.type === 'Identifier' && a.name === 'createNewLocalProject')
    ) {
      return true;
    }
  }
  return false;
}

function reorderStateChunks(items) {
  const objIdx = items.findIndex((i) => /\bRoomEditor\.State\s*=\s*\{/.test(i.text));
  if (objIdx === -1) return items;
  const objItem = items[objIdx];
  const rest = items.filter((_, j) => j !== objIdx);
  const sanitizeIdx = rest.findIndex((i) => /\bfunction\s+sanitizeLocalSlot\b/.test(i.text));
  if (sanitizeIdx === -1) return [objItem, ...rest];
  return [...rest.slice(0, sanitizeIdx + 1), objItem, ...rest.slice(sanitizeIdx + 1)];
}

function isConfigureNavCall(node) {
  if (node.type !== 'ExpressionStatement' || node.expression.type !== 'CallExpression') return false;
  const c = node.expression.callee;
  if (c.type === 'Identifier' && c.name === 'configureNav') return true;
  if (
    c.type === 'MemberExpression' &&
    !c.computed &&
    c.object.type === 'MemberExpression' &&
    !c.object.computed &&
    c.object.object.type === 'Identifier' &&
    c.object.object.name === 'RoomEditor' &&
    c.object.property.type === 'Identifier' &&
    c.object.property.name === 'Ui' &&
    c.property.type === 'Identifier' &&
    c.property.name === 'configureNav'
  ) {
    return true;
  }
  return false;
}

function isUiRefsAssignment(node) {
  if (node.type !== 'ExpressionStatement' || node.expression.type !== 'AssignmentExpression') return false;
  const left = node.expression.left;
  return (
    left.type === 'MemberExpression' &&
    !left.computed &&
    left.object.type === 'MemberExpression' &&
    !left.object.computed &&
    left.object.object.type === 'Identifier' &&
    left.object.object.name === 'RoomEditor' &&
    left.object.property.type === 'Identifier' &&
    left.object.property.name === 'Ui' &&
    left.property.type === 'Identifier' &&
    left.property.name === 'refs'
  );
}

function isStateSingletonAssignment(node) {
  if (node.type !== 'ExpressionStatement' || node.expression.type !== 'AssignmentExpression') return false;
  const left = node.expression.left;
  return (
    left.type === 'MemberExpression' &&
    !left.computed &&
    left.object.type === 'Identifier' &&
    left.object.name === 'RoomEditor' &&
    left.property.type === 'Identifier' &&
    left.property.name === 'State' &&
    node.expression.right.type === 'ObjectExpression'
  );
}

function classifyStatement(node) {
  if (isConfigureNavCall(node)) return '__drop__';
  if (isBootSideEffectStatement(node)) return '__drop__';
  if (isUiRefsAssignment(node)) return 'ui';
  if (isStateSingletonAssignment(node)) return 'state';

  if (node.type === 'VariableDeclaration') {
    const ids = [];
    for (const d of node.declarations) {
      if (d.id.type === 'Identifier') ids.push(d.id.name);
      else return 'state';
    }
    if (ids.length && ids.every((n) => VIEWPORT_VARS.has(n))) return '__viewport_canvas__';
    if (ids.every((n) => CONST_VARS.has(n))) return 'constants';
    if (ids.some((n) => STATE_VARS.has(n))) return 'state';
    if (ids.some((n) => CONST_VARS.has(n))) return 'constants';
    return 'state';
  }
  if (node.type === 'FunctionDeclaration' && node.id) {
    const m = fnToModule[node.id.name];
    if (!m) throw new Error('Unmapped function ' + node.id.name);
    return m;
  }
  if (node.type === 'ExpressionStatement') return 'state';
  if (node.type === 'IfStatement' || node.type === 'TryStatement' || node.type === 'ForStatement') {
    return 'state';
  }
  if (node.type === 'EmptyStatement') return '__drop__';
  return 'state';
}

function constChunkToModule(chunk) {
  return chunk.replace(/\bconst\s+/g, 'Module.');
}

function standardUmdFooter(ns, moduleKey) {
  return `
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.${ns} = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
`;
}

function emitStandardModule(moduleKey, chunks) {
  const ns = NS_KEY[moduleKey];
  const inner = chunks.join('\n\n');
  const ast = espree.parse(inner, { ecmaVersion: 2022, range: true });
  const assigns = [];
  for (const n of ast.body) {
    if (n.type === 'FunctionDeclaration' && n.id) {
      assigns.push(`  Module.${n.id.name} = ${n.id.name};`);
    }
  }
  const head = `'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.${ns} ? root.RoomEditor.${ns} : {};
`;
  return head + '\n' + inner + '\n\n' + assigns.join('\n') + '\n' + standardUmdFooter(ns, moduleKey);
}

function emitConstantsModule(chunks) {
  const inner = chunks.map(constChunkToModule).join('\n\n');
  const head = `'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Constants ? root.RoomEditor.Constants : {};
`;
  return head + '\n' + inner + '\n' + standardUmdFooter('Constants', 'constants');
}

function emitStateModule(chunks) {
  let inner = chunks.join('\n\n');
  inner = inner.replace(
    /let PROJECT_ID = \(PAGE_PARAMS\.get\('project_id'\) \|\| ''\)\.trim\(\);/,
    `let PROJECT_ID = (PAGE_PARAMS.get('project_id') || '').trim();
RoomEditor.State.PROJECT_ID = PROJECT_ID;`
  );
  inner = inner.replace(
    /const LOCAL_SLOT = !RoomEditor\.State\.PROJECT_ID \? localSlotFromUrl : '';/,
    `const LOCAL_SLOT = !RoomEditor.State.PROJECT_ID ? localSlotFromUrl : '';
RoomEditor.State.LOCAL_SLOT = LOCAL_SLOT;`
  );
  inner = inner.replace(
    /(\n)(function syncLegacyEditorWorkflowStep\(\) \{)/,
    `
RoomEditor.State.PROJECT_ART_DIRECTION_URL = PROJECT_ART_DIRECTION_URL;
RoomEditor.State.PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL = PROJECT_ART_DIRECTION_GENERATE_CONCEPTS_URL;
RoomEditor.State.PROJECT_BIOME_GENERATE_VISUALS_URL = PROJECT_BIOME_GENERATE_VISUALS_URL;
RoomEditor.State.PROJECT_ART_DIRECTION_TEMPLATES_URL = PROJECT_ART_DIRECTION_TEMPLATES_URL;
RoomEditor.State.PROJECT_LAYOUT_API_URL = PROJECT_LAYOUT_API_URL;
RoomEditor.State.PROJECT_LAYOUT_DOWNLOAD_NAME = PROJECT_LAYOUT_DOWNLOAD_NAME;
RoomEditor.State.LAYOUT_STORAGE_KEY = LAYOUT_STORAGE_KEY;
RoomEditor.State.ROOM_AI_SESSION_ID = ROOM_AI_SESSION_ID;
$1$2`
  );
  const ast = espree.parse(inner, { ecmaVersion: 2022, range: true });
  const assigns = [];
  for (const n of ast.body) {
    if (n.type === 'FunctionDeclaration' && n.id) {
      assigns.push(`  RoomEditor.State.${n.id.name} = ${n.id.name};`);
    }
  }
  return `'use strict';
(function (root) {
  root.RoomEditor = root.RoomEditor || {};
${inner}

${assigns.join('\n')}

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = RoomEditor.State;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
`;
}

function emitUiModule(chunks) {
  const inner = chunks.join('\n\n');
  const ast = espree.parse(inner, { ecmaVersion: 2022, range: true });
  const assigns = [];
  for (const n of ast.body) {
    if (n.type === 'FunctionDeclaration' && n.id) {
      assigns.push(`  RoomEditor.Ui.${n.id.name} = ${n.id.name};`);
    }
  }
  return `'use strict';
(function (root) {
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Ui = root.RoomEditor.Ui || { refs: null };
${inner}

${assigns.join('\n')}

  function init() {
    configureNav();
    initSidebarToggle();
  }
  RoomEditor.Ui.init = init;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = RoomEditor.Ui;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
`;
}

function emitViewportModule(chunks) {
  const inner = chunks.join('\n\n');
  const ast = espree.parse(inner, { ecmaVersion: 2022, range: true });
  const assigns = [];
  for (const n of ast.body) {
    if (n.type === 'FunctionDeclaration' && n.id) {
      assigns.push(`  Module.${n.id.name} = ${n.id.name};`);
    }
  }
  const initFn = `
  function init() {
    RoomEditor.Viewport.roomCanvas = document.getElementById('roomCanvas');
    RoomEditor.Viewport.roomCtx = RoomEditor.Viewport.roomCanvas.getContext('2d');
    RoomEditor.Viewport.globalCanvas = document.getElementById('globalCanvas');
    RoomEditor.Viewport.globalCtx = RoomEditor.Viewport.globalCanvas.getContext('2d');
  }
  Module.init = init;
`;
  const head = `'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Viewport ? root.RoomEditor.Viewport : {};
`;
  return (
    head +
    '\n' +
    inner +
    '\n' +
    assigns.join('\n') +
    '\n' +
    initFn +
    '\n' +
    standardUmdFooter('Viewport', 'viewport')
  );
}

function emitWizardAugment(chunks) {
  const inner = chunks.join('\n\n');
  const ast = espree.parse(inner, { ecmaVersion: 2022, range: true });
  const assigns = [];
  for (const n of ast.body) {
    if (n.type === 'FunctionDeclaration' && n.id) {
      assigns.push(`  root.RoomEditor.Wizard.${n.id.name} = ${n.id.name};`);
    }
  }
  return `'use strict';
(function (root) {
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Wizard = root.RoomEditor.Wizard || {};
${inner}

${assigns.join('\n')}
})(typeof globalThis !== 'undefined' ? globalThis : this);
`;
}

function main() {
  let raw = fs.readFileSync(SRC, 'utf8');
  if (!raw.includes("'use strict'")) {
    raw = `'use strict';\n` + raw;
  }
  raw = preprocessLets(raw);
  const qualified = qualifySource(raw.replace(/^'use strict';\n/m, ''));
  const ast = espree.parse(qualified, { ecmaVersion: 2022, range: true });

  const buckets = {
    constants: [],
    state: [],
    model: [],
    topology: [],
    validation: [],
    workflow: [],
    wizard: [],
    wizardAsync: [],
    wizardEvents: [],
    viewport: [],
    render: [],
    storage: [],
    ui: [],
    input: [],
    gamePreview: [],
    __viewport_canvas__: [],
  };

  ast.body.forEach((node, order) => {
    const mod = classifyStatement(node);
    if (mod === '__drop__') return;
    const text = qualified.slice(node.range[0], node.range[1]);
    if (!buckets[mod]) throw new Error('Bad module ' + mod + ' at order ' + order);
    buckets[mod].push({ order, text });
  });

  fs.mkdirSync(OUT_DIR, { recursive: true });

  const orderKeys = [
    'constants',
    'state',
    'model',
    'topology',
    'validation',
    'workflow',
    'wizard',
    'wizardAsync',
    'wizardEvents',
    'viewport',
    'render',
    'storage',
    'ui',
    'input',
    'gamePreview',
  ];

  const writers = {
    constants: emitConstantsModule,
    state: emitStateModule,
    ui: emitUiModule,
    viewport: emitViewportModule,
    wizardAsync: emitWizardAugment,
    wizardEvents: emitWizardAugment,
  };

  const fileMap = {
    constants: 'constants.js',
    state: 'state.js',
    model: 'model.js',
    topology: 'topology.js',
    validation: 'validation.js',
    workflow: 'workflow.js',
    wizard: 'wizard.js',
    wizardAsync: 'wizard-async.js',
    wizardEvents: 'wizard-events.js',
    viewport: 'viewport.js',
    render: 'render.js',
    storage: 'storage.js',
    ui: 'ui.js',
    input: 'input.js',
    gamePreview: 'game-preview.js',
  };

  for (const key of orderKeys) {
    let items = buckets[key].sort((a, b) => a.order - b.order);
    if (key === 'state') {
      items = reorderStateChunks(items);
    }
    const chunks = items.map((i) => i.text);
    let out;
    if (writers[key]) {
      out = writers[key](chunks);
    } else {
      out = emitStandardModule(key, chunks);
    }
    fs.writeFileSync(path.join(OUT_DIR, fileMap[key]), out, 'utf8');
    console.log('Wrote', fileMap[key], 'parts', chunks.length);
  }
}

main();
