'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const htmlPath = path.join(__dirname, '..', 'room-layout-editor.html');
const html = fs.readFileSync(htmlPath, 'utf8');

test('Option B shell markers exist in room-layout-editor.html', () => {
  assert.match(html, /id="rwOptbMain"/);
  assert.match(html, /id="rwWizardInsHeadSlot"/);
  assert.match(html, /id="rwFocusMainSlot"/);
  assert.match(html, /data-rw-phase="identity"/);
  assert.match(html, /data-rw-phase="entities"/);
  assert.match(html, /id="roomWizardPanelEntities"/);
  assert.match(html, /id="rwOptbPreviewModal"/);
  assert.match(html, /room-wizard-option-b\.js/);
});

test('Wizard phase order in option-b module matches design spec', async () => {
  const p = path.join(__dirname, '..', 'js', 'editor', 'room-wizard-option-b.js');
  const src = fs.readFileSync(p, 'utf8');
  assert.match(src, /\['identity', 'layout', 'environment', 'entities', 'review'\]/);
});
