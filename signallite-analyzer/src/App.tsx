import React, { useState, useEffect } from "react";
import { useAppStore } from "./store/useAppStore";
import { Header } from "./components/Header";
import { DataGroupsPanel } from "./components/DataGroupsPanel";
import { VariablesPanel } from "./components/VariablesPanel";
import { GroupedDataTable } from "./components/GroupedDataTable";
import { PlotWorkspace } from "./components/PlotWorkspace";
import { PlotFormattingPanel } from "./components/PlotFormattingPanel";
import { BottomStatusBar } from "./components/BottomStatusBar";
import { HelpDrawer } from "./components/HelpDrawer";
import { SettingsModal } from "./components/SettingsModal";
import { LoadingOverlay } from "./components/LoadingOverlay";
import { ErrorPanel } from "./components/ErrorPanel";
import { ToastHost } from "./components/ToastHost";

export default function App() {
  const [helpOpen, setHelpOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const isLoading = useAppStore(s => s.isLoading);
  const loadError = useAppStore(s => s.loadError);
  const setLoadError = useAppStore(s => s.setLoadError);
  const loadSavedLayout = useAppStore(s => s.loadSavedLayout);
  const previousCase = useAppStore(s => s.previousCase);
  const nextCase = useAppStore(s => s.nextCase);
  const saveLayout = useAppStore(s => s.saveLayout);

  // Load saved layout on mount
  useEffect(() => {
    loadSavedLayout();
  }, [loadSavedLayout]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName.toLowerCase();
      const inInput = tag === "input" || tag === "textarea" || tag === "select";

      if (e.key === "ArrowLeft" && !inInput) {
        e.preventDefault();
        previousCase();
      } else if (e.key === "ArrowRight" && !inInput) {
        e.preventDefault();
        nextCase();
      } else if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        saveLayout();
      } else if (e.key === "Escape") {
        setHelpOpen(false);
        setSettingsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [previousCase, nextCase, saveLayout]);

  return (
    <div className="app">
      {/* Header */}
      <div className="app-header">
        <Header
          onOpenSettings={() => setSettingsOpen(true)}
          onOpenHelp={() => setHelpOpen(true)}
        />
      </div>

      {/* Left Sidebar */}
      <div className="app-left-sidebar">
        {loadError && (
          <ErrorPanel message={loadError} onDismiss={() => setLoadError(null)} />
        )}
        <DataGroupsPanel />
        <div className="divider" />
        <VariablesPanel />
      </div>

      {/* Table */}
      <div className="app-table">
        <GroupedDataTable />
      </div>

      {/* Plots */}
      <div className="app-plots">
        <PlotWorkspace />
      </div>

      {/* Right Inspector */}
      <div className="app-right-inspector">
        <PlotFormattingPanel />
      </div>

      {/* Bottom Status */}
      <div className="app-bottom-status">
        <BottomStatusBar />
      </div>

      {/* Overlays */}
      {isLoading && <LoadingOverlay />}
      {helpOpen && <HelpDrawer onClose={() => setHelpOpen(false)} />}
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
      <ToastHost />
    </div>
  );
}
