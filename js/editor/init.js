'use strict';
(function () {
  async function boot() {
    try {
      const res = await fetch('./room-layout-seed.json', { cache: 'no-store' });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      RoomEditor.State.SEED_DATA = await res.json();
    } catch (error) {
      RoomEditor.Ui.setStatus(`Failed to load room-layout-seed.json: ${error.message}`, 'error');
      return;
    }

    window.validateLayout = RoomEditor.Validation.validateLayout;
    window.VALIDATION_L2 = RoomEditor.Constants.VALIDATION_L2;

    RoomEditor.Viewport.init();
    RoomEditor.Ui.populateAbilityOptions();
    RoomEditor.Ui.init();
    RoomEditor.Wizard.installRoomWizardQaHooks();
    document.getElementById('btnNewLocalProject')?.addEventListener('click', RoomEditor.Storage.createNewLocalProject);
    RoomEditor.Wizard.wireRoomWizardEvents();
    RoomEditor.WizardOptionB?.wireChromeEvents?.();
    RoomEditor.GamePreview.wireGamePreview();
    RoomEditor.Input.wireEvents();
    RoomEditor.Storage.refreshProjectList().catch(() => {});
    RoomEditor.Storage.loadData().catch((err) => {
      RoomEditor.Ui.setStatus(`Load failed: ${err.message}`, 'error');
    });
    RoomEditor.Storage.refreshCopilotStatus().catch(() => {});
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      () => {
        boot();
      },
      { once: true }
    );
  } else {
    boot();
  }
})();
