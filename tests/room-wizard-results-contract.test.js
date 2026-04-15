'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'room-layout-editor.html'), 'utf8');
const shellCss = fs.readFileSync(path.join(__dirname, '..', 'css', 'editor-shell.css'), 'utf8');

function readRoomEditorChunkBundle() {
  const ed = path.join(__dirname, '..', 'js/editor');
  let s = '';
  for (let i = 0; i < 20; i += 1) {
    const f = path.join(ed, `chunk-${i}.js`);
    if (!fs.existsSync(f)) break;
    const t = fs.readFileSync(f, 'utf8');
    const m = t.match(/push\((.*)\);\s*$/s);
    if (!m) continue;
    s += JSON.parse(m[1]);
  }
  return s;
}

const editorJs = readRoomEditorChunkBundle();

function assertIncludes(snippet, message) {
  assert.ok(
    html.includes(snippet) || editorJs.includes(snippet) || shellCss.includes(snippet),
    message || `Expected HTML or editor bundle to include: ${snippet}`
  );
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
  const orderedLabels = ['Structure</label>', 'Background</label>', 'Decor</label>', 'Room overlay</label>'];
  let lastIndex = -1;
  orderedLabels.forEach((label) => {
    const idx = editorJs.indexOf(label);
    assert.ok(idx > lastIndex, `Expected Results overlay toggle labels in order: ${label}`);
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

(function testResultsReviewLayoutStacksBuildSummaryUnderPreview() {
  assert.ok(
    !html.includes('rw-env-review-layout--split'),
    'Environment review should stack build summary under preview pictures (no side-by-side split)'
  );
  assertIncludes(
    'build summary and checklist below',
    'Step 2 intro should describe the stacked preview-then-summary layout'
  );
})();

(function testPreviewGalleryOpensFullSizeInPopup() {
  assertIncludes('class="rw-preview-card-open"', 'Preview thumbnails should use a control for full-size view');
  assertIncludes('data-rw-asset-src', 'Preview should carry the asset URL for the viewer');
  assertIncludes('openRoomEnvironmentAssetPreviewWindow', 'Preview click should open the dark HTML viewer in a popup window');
  assertIncludes(
    '/room-environment-preview-full.html',
    'Full-size preview should open the dark HTML viewer, not the browser default image page'
  );
  assertIncludes('encodeURIComponent(raw)', 'Viewer should pass the image URL as a same-origin query param');
})();

(function testBuildSummaryAssetThumbsOpenInPopup() {
  assertIncludes('rw-environment-asset-open', 'Build summary asset thumbnails should open full size from a button');
  assertIncludes('data-rw-asset-src', 'Asset thumb buttons should carry the versioned image URL');
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

(function testBuildSummarySurfacesGeneratedImagesEarly() {
  assertIncludes(
    'rw-env-generated-images-surface',
    'Build summary should surface generated images in a dedicated block for quick visibility'
  );
  const layout = `${html}\n${editorJs}`;
  const genIdx = layout.indexOf('rw-env-generated-images-surface');
  const detailsIdx = layout.indexOf('Theme, pipeline, assets, and references');
  assert.ok(
    genIdx > 0 && detailsIdx > genIdx,
    'Template source should define generated-images surface before the collapsed build-details summary copy'
  );
})();

(function testBespokeSlotRegenerateControlsExist() {
  assertIncludes(
    'data-rw-bespoke-slot-action="regen"',
    'Build summary asset cards should expose per-slot Regenerate'
  );
  assertIncludes(
    'data-rw-bespoke-slot-action="iterate"',
    'AI-built asset cards should expose Iterate (current image as reference)'
  );
})();

(function testBespokeGeminiWaitEstimationWired() {
  assertIncludes('function roomWizardBespokeComponentUsesGemini', 'Gemini vs template slot classifier should exist');
  assertIncludes('function roomWizardEstimateBespokeGeminiSlotCount', 'Slot-count estimator should exist');
  assertIncludes('function roomWizardEstimateBespokeAssetWaitMs', 'Wall-clock estimator should exist');
  assertIncludes('startRoomWizardWaitbar(', 'Wait bar entry point should remain');
  assertIncludes('roomWizardEstimateBespokeAssetWaitMs(room, { slotId })', 'Per-slot build should pass timed wait estimate');
  assertIncludes('roomWizardEstimateBespokeAssetWaitMs(room, { forFullBuild: true })', 'Full kit build should pass timed wait estimate');
})();

(function testOptionBStageFirstShellContract() {
  [
    'id="optbStageBar"',
    'id="optbToolPalette"',
    'id="optbTaskDrawer"',
    'id="optb-modal"',
    'id="optb-wide-head-slot"',
    'id="optb-wide-main-slot"',
  ].forEach((snippet) => assertIncludes(snippet, `Missing Option B shell node ${snippet}`));

  assertIncludes("if (e.key === 'ArrowRight' || e.key === ']')", 'Option B phase keyboard nav should handle ArrowRight and ]');
  assertIncludes("if (e.key === 'ArrowLeft' || e.key === '[')", 'Option B phase keyboard nav should handle ArrowLeft and [');
  assertIncludes("if (e.key === 'Escape')", 'Option B modal should close on Escape');
})();

(function testOptionBInspectorTeleportDoesNotAbsorbLegacyRailPanels() {
  assert.ok(
    !html.includes('sideRail.remove()'),
    'Option B inspector hoist should not remove the legacy side rail container'
  );
  assert.ok(
    !html.includes('ins.appendChild(child)'),
    'Option B inspector hoist should not append legacy side-rail panels into the inspector column'
  );
})();

(function testOptionBMainGridUsesStagePlusInspectorColumns() {
  assertIncludes(
    'grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);',
    'Option B stage layout should use a two-column stage + inspector grid'
  );
  assertIncludes(
    'body#optb-app #optb-stage-layout > #optbSideRail {\n  display: none !important;',
    'Legacy side rail should stay hidden in Option B shell'
  );
})();

(function testOptionBPhaseRailDrivesWizardPanels() {
  assertIncludes('function syncWizardPanelsForPhase(phase)', 'Option B phase machine should include wizard panel synchronization');
  assertIncludes("layout: phase === 'layout' || phase === 'identity'", 'Identity should map to the layout/identity wizard pane');
  assertIncludes("environment: phase === 'environment'", 'Environment phase should map to the environment wizard pane');
  assertIncludes("art: phase === 'entities'", 'Entities phase should map to the art-direction pane');
  assertIncludes("review: phase === 'review'", 'Review phase should map to the review pane');
  assertIncludes("var isMainLayoutWorkspace = true;", 'Stabilization keeps wizard workspace visible for all phases');
  assertIncludes('dock.hidden = false;', 'Option B phase machine should force wizard dock visible independent of legacy roomWizard.active');
  assertIncludes("dock.setAttribute('aria-hidden', 'false');", 'Option B phase machine should keep wizard dock aria state visible');
  assertIncludes("environment: 'roomWizardTabEnvironment'", 'Option B phase machine should bridge Environment phase to legacy wizard handlers');
  assertIncludes('legacyBtn.click();', 'Option B phase machine should trigger legacy wizard handlers when available');
  assertIncludes('syncWizardPanelsForPhase(phase);', 'Phase changes should actively update visible wizard panes');
})();

(function testOptionBCssEnforcesPanelVisibilityPerPhase() {
  assertIncludes(
    'body#optb-app[data-phase="environment"] #roomWizardPanelEnvironment',
    'CSS should force Environment panel visible when Option B phase is environment'
  );
  assertIncludes(
    'body#optb-app[data-phase="entities"] #roomWizardPanelArtDirection',
    'CSS should force Entities panel visible via art-direction panel'
  );
  assertIncludes(
    'body#optb-app[data-phase="review"] #roomWizardPanelReview',
    'CSS should force Review panel visible when Option B phase is review'
  );
})();

(function testOptionBDockFallbackVisibilityContract() {
  assertIncludes(
    'body#optb-app #roomWizardDock:not(:has(#optb-inspector))',
    'Option B should hide wizard dock only after inspector hoist removes #optb-inspector'
  );
  assert.ok(
    !shellCss.includes('body#optb-app #roomWizardDock {\n  display: none !important;'),
    'Option B should not hard-hide roomWizardDock unconditionally'
  );
})();

(function testRuntimeReviewOpensGameWithoutDuplicateButton() {
  assert.ok(
    !html.includes('id="roomWizardPreviewOpenGame"'),
    'Open room in game should not duplicate a toolbar button when runtime review launches the preview'
  );
  assertIncludes(
    'rw-runtime-review-open-game',
    'Runtime review should expose Open in game beside the screenshot'
  );
  assertIncludes(
    'rw-runtime-review-thumb',
    'Runtime review screenshot should open full size from a dedicated control'
  );
  assertIncludes(
    'rw-runtime-review-row',
    'Runtime review should sit in its own row above the asset thumbnail grid'
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
