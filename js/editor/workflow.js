'use strict';
(function (root) {
  const Module = root.RoomEditor && root.RoomEditor.Workflow ? root.RoomEditor.Workflow : {};

function updateWorkflowScopeToggle() {
        const w = document.getElementById('workflowScopeWorld');
        const r = document.getElementById('workflowScopeRoom');
        const a = document.getElementById('workflowScopeArtDirection');
        const stack = document.getElementById('workflowRailsStack');
        if (!w || !r || !a) return;
        const world = RoomEditor.State.workflowScope === 'world';
        const room = RoomEditor.State.workflowScope === 'room';
        const artDirection = RoomEditor.State.workflowScope === 'art-direction';
        w.classList.toggle('active', world);
        r.classList.toggle('active', room);
        a.classList.toggle('active', artDirection);
        w.setAttribute('aria-selected', world ? 'true' : 'false');
        r.setAttribute('aria-selected', room ? 'true' : 'false');
        a.setAttribute('aria-selected', artDirection ? 'true' : 'false');
        stack?.classList.toggle('workflow-rails-stack--room', room || artDirection);
        stack?.classList.toggle('workflow-rails-stack--world', world);
      }

function syncWorldWorkflowRailVisibility() {
        const rail = document.getElementById('worldWorkflowRail');
        if (!rail) return;
        const show = RoomEditor.State.workflowScope === 'world';
        rail.hidden = !show;
        rail.setAttribute('aria-hidden', show ? 'false' : 'true');
      }

function syncWorldPlaceholderPanel() {
        const el = document.getElementById('worldWorkflowPlaceholderPanel');
        if (!el) return;
        const show =
          RoomEditor.State.workflowScope === 'world' && (RoomEditor.State.worldWorkflowStep === 2 || RoomEditor.State.worldWorkflowStep === 3);
        el.hidden = !show;
        el.setAttribute('aria-hidden', show ? 'false' : 'true');
      }

function updateWorldWorkflowPills() {
        const rail = document.getElementById('worldWorkflowRail');
        if (!rail) return;
        const step = RoomEditor.State.worldWorkflowStep;
        rail.querySelectorAll('[data-world-workflow-step]').forEach((pill) => {
          const n = Number(pill.dataset.worldWorkflowStep);
          pill.classList.remove('active', 'available');
          if (n === step) pill.classList.add('active');
          else pill.classList.add('available');
        });
      }

function updateEditorWorkflowPrimaryPills() {
        updateWorldWorkflowPills();
      }

function syncEditorWorkflowSecondaryRail() {
        const wrap = document.getElementById('roomWizardPhaseRailWrap');
        if (!wrap) return;
        const show = RoomEditor.State.workflowScope === 'room' && !!RoomEditor.State.data;
        wrap.hidden = !show;
        wrap.setAttribute('aria-hidden', show ? 'false' : 'true');
      }

function syncRoomWizardScopePanels() {
        const panL = document.getElementById('roomWizardPanelLayout');
        const panE = document.getElementById('roomWizardPanelEnvironment');
        const panA = document.getElementById('roomWizardPanelArtDirection');
        const panR = document.getElementById('roomWizardPanelReview');
        const artScope = RoomEditor.State.workflowScope === 'art-direction';
        if (panA) {
          panA.hidden = !artScope;
          panA.setAttribute('aria-hidden', artScope ? 'false' : 'true');
        }
        if (artScope) {
          if (panL) panL.hidden = true;
          if (panE) panE.hidden = true;
          if (panR) panR.hidden = true;
        }
      }

function setWorldWorkflowStep(step) {
        if (step < 1 || step > 4) return;
        if (RoomEditor.State.workflowScope !== 'world') return;
        RoomEditor.State.worldWorkflowStep = step;
        RoomEditor.Wizard.closeRoomWizard(true);
        RoomEditor.State.setViewMode('global');
        if (step === 4 && RoomEditor.State.data) {
          const report = RoomEditor.Validation.validateLayout(RoomEditor.State.data);
          RoomEditor.State.lastValidationReport = report;
          RoomEditor.Validation.renderValidationResults(report);
          document.getElementById('validationPanel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        RoomEditor.State.syncLegacyEditorWorkflowStep();
        updateWorldWorkflowPills();
        syncWorldPlaceholderPanel();
        syncWorldWorkflowRailVisibility();
        syncEditorWorkflowSecondaryRail();
        updateWorkflowRailPills();
        syncRoomWizardDock();
        RoomEditor.Render.redraw();
      }

function setWorkflowScope(scope) {
        if (scope !== 'world' && scope !== 'room' && scope !== 'art-direction') return;
        if (scope === 'room' && (!RoomEditor.State.data?.rooms?.length)) {
          RoomEditor.Ui.setStatus('Add a room first (world layout, or + Add Room in settings).', 'warning');
          return;
        }
        if (scope === 'art-direction' && !RoomEditor.State.PROJECT_ID) {
          RoomEditor.Ui.setStatus('Open a workbench project to edit project-wide art direction.', 'warning');
          return;
        }
        RoomEditor.State.workflowScope = scope;
        updateWorkflowScopeToggle();
        syncWorldWorkflowRailVisibility();
        if (scope === 'world') {
          RoomEditor.Wizard.closeRoomWizard(true);
          setWorldWorkflowStep(RoomEditor.State.worldWorkflowStep);
        } else if (scope === 'art-direction') {
          if (RoomEditor.State.currentRoomId && !RoomEditor.State.roomWizard.active) {
            RoomEditor.Wizard.openRoomWizard(RoomEditor.State.currentRoomId);
          }
          RoomEditor.State.setViewMode('room');
          RoomEditor.Wizard.loadRoomEnvironmentProjectData();
          RoomEditor.State.syncLegacyEditorWorkflowStep();
          updateWorldWorkflowPills();
          syncWorldPlaceholderPanel();
          syncEditorWorkflowSecondaryRail();
          updateWorkflowRailPills();
          syncRoomWizardDock();
          syncRoomWizardScopePanels();
          RoomEditor.Render.redraw();
        } else {
          RoomEditor.State.setViewMode('room');
          if (RoomEditor.State.currentRoomId && !RoomEditor.State.roomWizard.active) {
            RoomEditor.Wizard.openRoomWizard(RoomEditor.State.currentRoomId);
          } else {
            RoomEditor.State.syncLegacyEditorWorkflowStep();
            updateWorldWorkflowPills();
            syncWorldPlaceholderPanel();
            syncEditorWorkflowSecondaryRail();
            updateWorkflowRailPills();
            syncRoomWizardDock();
            RoomEditor.Render.redraw();
          }
        }
      }

function setEditorWorkflowStep(step) {
        if (step !== 1 && step !== 2 && step !== 3) return;
        if (step === 2 && (!RoomEditor.State.data?.rooms?.length)) {
          RoomEditor.Ui.setStatus('Add a room first (world layout, or + Add Room in settings).', 'warning');
          return;
        }
        if (step === 1) {
          RoomEditor.State.worldWorkflowStep = 1;
          setWorkflowScope('world');
        } else if (step === 2) {
          setWorkflowScope('room');
        } else {
          RoomEditor.State.worldWorkflowStep = 4;
          setWorkflowScope('world');
        }
      }

function updateWorkflowRailPills() {
        const ph = RoomEditor.State.roomWizard.phase;
        const wizardOn = RoomEditor.State.roomWizard.active;
        const vm = RoomEditor.State.viewMode;
        const rail = document.getElementById('roomWizardPhaseRail');
        if (!rail) return;
        const room = RoomEditor.Wizard.getRoomWizardRoom();
        const mod = globalThis.RoomWizardTerrain;
        const layoutOk = !!(room && mod && mod.isLayoutCompleteForTerrain(room));

        rail.querySelectorAll('.phase-pill[data-rw-phase]').forEach((pill) => {
          const key = pill.dataset.rwPhase;
          pill.classList.remove('active', 'available', 'locked', 'complete');
          if (key === 'layout') {
            if (wizardOn && ph === 'layout') {
              pill.classList.add('active');
            } else if (!wizardOn && vm === 'room' && RoomEditor.State.workflowScope === 'room') {
              pill.classList.add('active');
            } else {
              pill.classList.add('available');
            }
            return;
          }
          if (key === 'environment') {
            if (!layoutOk) {
              pill.classList.add('locked');
              pill.disabled = true;
              pill.title = 'Complete layout (name, id, footprint) first.';
              return;
            }
            pill.disabled = false;
            pill.title = '';
            if (wizardOn && ph === 'environment') {
              pill.classList.add('active');
            } else {
              pill.classList.add('available');
            }
            return;
          }
          if (key === 'objects') {
            pill.classList.add('locked');
            pill.disabled = true;
            pill.title = 'Coming in a later update';
            return;
          }
          if (key === 'review') {
            pill.disabled = false;
            pill.title = '';
            if (wizardOn && ph === 'review') {
              pill.classList.add('active');
            } else {
              pill.classList.add('available');
            }
          }
        });
      }

function syncWorkflowRailVisibility() {
        const stack = document.getElementById('workflowRailsStack');
        if (!stack) return;
        const show = !!RoomEditor.State.data;
        stack.hidden = !show;
        stack.setAttribute('aria-hidden', show ? 'false' : 'true');
        syncEditorWorkflowSecondaryRail();
        syncWorldWorkflowRailVisibility();
        updateWorkflowScopeToggle();
        updateWorldWorkflowPills();
        syncWorldPlaceholderPanel();
        updateWorkflowRailPills();
        syncRoomWizardScopePanels();
      }

function syncRoomWizardDock() {
        const dock = document.getElementById('roomWizardDock');
        if (!dock) return;
        if (RoomEditor.State.roomWizard.active && RoomEditor.State.data && RoomEditor.State.roomWizard.roomId) {
          const exists = RoomEditor.State.data.rooms.some((r) => r.id === RoomEditor.State.roomWizard.roomId);
          if (!exists) {
            RoomEditor.Wizard.closeRoomWizard(true);
            return;
          }
        }
        const room =
          RoomEditor.State.currentRoomId && RoomEditor.State.data
            ? RoomEditor.State.data.rooms.find((r) => r.id === RoomEditor.State.currentRoomId)
            : null;
        const show =
          (RoomEditor.State.workflowScope === 'room' || RoomEditor.State.workflowScope === 'art-direction') &&
          RoomEditor.State.viewMode === 'room' &&
          !!RoomEditor.State.data &&
          (RoomEditor.State.workflowScope === 'art-direction' ? !!RoomEditor.State.PROJECT_ID : !!room);
        dock.hidden = !show;
        dock.setAttribute('aria-hidden', show ? 'false' : 'true');
        dock.classList.toggle('room-wizard-dock--compact', show);
        if (RoomEditor.Ui.refs.roomSetupBtn) {
          RoomEditor.Ui.refs.roomSetupBtn.disabled = !RoomEditor.State.currentRoomId || !RoomEditor.State.data?.rooms?.length;
        }
      }

  Module.updateWorkflowScopeToggle = updateWorkflowScopeToggle;
  Module.syncWorldWorkflowRailVisibility = syncWorldWorkflowRailVisibility;
  Module.syncWorldPlaceholderPanel = syncWorldPlaceholderPanel;
  Module.updateWorldWorkflowPills = updateWorldWorkflowPills;
  Module.updateEditorWorkflowPrimaryPills = updateEditorWorkflowPrimaryPills;
  Module.syncEditorWorkflowSecondaryRail = syncEditorWorkflowSecondaryRail;
  Module.syncRoomWizardScopePanels = syncRoomWizardScopePanels;
  Module.setWorldWorkflowStep = setWorldWorkflowStep;
  Module.setWorkflowScope = setWorkflowScope;
  Module.setEditorWorkflowStep = setEditorWorkflowStep;
  Module.updateWorkflowRailPills = updateWorkflowRailPills;
  Module.syncWorkflowRailVisibility = syncWorkflowRailVisibility;
  Module.syncRoomWizardDock = syncRoomWizardDock;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Module;
  }
  root.RoomEditor = root.RoomEditor || {};
  root.RoomEditor.Workflow = Module;
})(typeof globalThis !== 'undefined' ? globalThis : this);
