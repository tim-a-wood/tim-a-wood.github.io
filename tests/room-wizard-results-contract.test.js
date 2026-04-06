'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'room-layout-editor.html'), 'utf8');

function assertIncludes(snippet, message) {
  assert.ok(html.includes(snippet), message || `Expected HTML to include: ${snippet}`);
}

(function testDescribeTabAuthoringFieldsExist() {
  [
    'id="roomWizardThemeName"',
    'id="roomWizardEnvironmentSeed"',
    'id="roomWizardEnvironmentNotes"',
    'id="roomWizardReferenceUpload"',
    'id="roomWizardLockStylepack"',
  ].forEach((snippet) => assertIncludes(snippet, `Missing Describe authoring control ${snippet}`));
})();

(function testEnvironmentWorkflowIsDescribeVersusReview() {
  ['id="rwEnvStepDescribe"', 'id="rwEnvStepReview"', 'id="rwEnvStepPanelDescribe"'].forEach((snippet) =>
    assertIncludes(snippet, `Missing Environment workflow control ${snippet}`)
  );
  assertIncludes('data-rw-env-step="describe"', 'Describe step should be wired for the environment workflow');
  assertIncludes('data-rw-env-step="review"', 'Review step should be wired for the environment workflow');
  assertIncludes('<strong>1 · Describe</strong>', 'Environment workflow should expose step 1 Describe tab');
  assertIncludes('<strong>2 · Preview &amp; build</strong>', 'Environment workflow should expose step 2 Preview & build');
  assert.ok(!html.includes('id="rwEnvTabComponents"'), 'Legacy Components tab should stay removed');
})();

(function testResultsStageOrderMatchesContract() {
  const orderedLabels = [
    '1. Visual style',
    '2. Walkable layout',
    '3. Room pieces',
    '4. Scene layout',
    '5. Quality check',
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
  assertIncludes('id="roomWizardBuildEnvironmentAssets">Build final room assets</button>', 'Initial build button copy should match the approved plain-English contract');
  assertIncludes("buildButton.disabled = !preview.approved_image_id;", 'Build button should stay disabled until a preview is approved');
  assertIncludes("? 'Rebuild final room assets'", 'Build button should reflect rebuild state');
  assertIncludes("? 'Retry final room assets'", 'Build button should reflect retry state');
})();

(function testResultsPreviewAvoidsDoublePanelChrome() {
  assertIncludes(
    'rw-copilot-preview-box--flush',
    'Results preview area should opt out of inner card chrome inside the stage-card shell'
  );
  assertIncludes(
    "resultsTarget.innerHTML = hasGalleryImages ? '' : generatedMarkup",
    'Results column should not duplicate the large generated preview when gallery cards already show images'
  );
  assertIncludes(
    'rw-environment-stage-hero',
    'Build summary header should not nest a bordered summary card inside the output section'
  );
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
