'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'room-layout-editor.html'), 'utf8');

function assertIncludes(snippet, message) {
  assert.ok(html.includes(snippet), message || `Expected HTML to include: ${snippet}`);
}

(function testResultsTabAuthoringFieldsExist() {
  [
    'id="roomWizardThemeName"',
    'id="roomWizardEnvironmentSeed"',
    'id="roomWizardEnvironmentNotes"',
    'id="roomWizardReferenceUpload"',
    'id="roomWizardLockStylepack"',
  ].forEach((snippet) => assertIncludes(snippet, `Missing Results authoring control ${snippet}`));
})();

(function testResultsStageOrderMatchesContract() {
  const orderedLabels = [
    '1. Stylepack',
    '2. Semantics',
    '3. Kit',
    '4. Manifest',
    '5. Validation',
  ];
  let lastIndex = -1;
  orderedLabels.forEach((label) => {
    const idx = html.indexOf(label);
    assert.ok(idx > lastIndex, `Expected Results stage label in order: ${label}`);
    lastIndex = idx;
  });
})();

(function testOverlayControlsRemainEmbeddedInResultsSurface() {
  [
    'id="roomWizardToggleStructural"',
    'id="roomWizardToggleBackground"',
    'id="roomWizardToggleDecor"',
    'id="roomWizardToggleSemantics"',
    'id="roomWizardToggleExclusion"',
    'id="roomWizardToggleUnresolved"',
    'id="roomWizardToggleValidation"',
  ].forEach((snippet) => assertIncludes(snippet, `Missing overlay toggle ${snippet}`));
})();

(function testBuildButtonCopyAndDisabledStateContract() {
  assertIncludes('id="roomWizardBuildEnvironmentAssets">Build Production Assets</button>', 'Initial build button copy should match the production-assets contract');
  assertIncludes("buildButton.disabled = !preview.approved_image_id;", 'Build button should stay disabled until a preview is approved');
  assertIncludes("buildButton.textContent = bespokeManifest.status === 'ready'", 'Build button should reflect ready/retry/rebuild states');
})();

(function testResultsStatusVocabularyIsPresent() {
  [
    "if (normalized === 'generating') return 'Generating';",
    "if (normalized === 'partial') return 'Partial';",
    "if (normalized === 'locked') return 'Locked';",
    "if (normalized === 'ready') return 'Ready';",
    "if (normalized === 'empty') return 'Empty';",
    "if (normalized === 'draft') return 'Draft';",
    "if (normalized === 'blocked') return 'Blocked';",
    "if (normalized === 'complete') return 'Ready';",
    "if (normalized === 'warning') return 'Warning';",
    "if (normalized === 'pass') return 'Pass';",
    "if (normalized === 'pass') return 'Reviewed';",
    "if (normalized === 'fail') return 'Review failed';",
  ].forEach((snippet) => assertIncludes(snippet));
})();

console.log('room-wizard-results-contract.test.js: all assertions passed');
