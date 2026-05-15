import { create } from "zustand";
import type { WorkbookModel, AppLayoutState, PlotSet, AppSettings, ToastMessage, SeriesConfig } from "../types/appTypes";
import { defaultLayout } from "../config/defaultLayout";
import { defaultPlotSet } from "../config/defaultPlotConfig";
import { sampleWorkbookModel } from "../data/sampleWorkbookModel";
import { saveLayout, loadLayout as loadLayoutData, clearLayout } from "../utils/localStorage";
import { nearestCase, clampXRange, computeZoomSliderValue, computeWindowSpanFromSlider } from "../model/xRange";
import { getAllCases } from "../model/selectors";

let autosaveTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleAutosave(get: () => AppState) {
  if (!get().layoutState.autosaveLayout) return;
  if (autosaveTimer) clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(() => {
    const s = get();
    saveLayout({ layoutState: s.layoutState, plotSet: s.plotSet, settings: s.settings });
    autosaveTimer = null;
  }, 300);
}

interface AppState {
  workbookModel: WorkbookModel;
  layoutState: AppLayoutState;
  plotSet: PlotSet;
  settings: AppSettings;
  toasts: ToastMessage[];
  activeError: string | null;
  isLoading: boolean;
  groupVisibilitySnapshots: Record<string, string[]>;

  loadWorkbook: (model: WorkbookModel) => void;
  loadSampleWorkbook: () => void;
  toggleGroup: (groupKey: string) => void;
  toggleVariable: (variableKey: string) => void;
  toggleGroupCollapse: (groupKey: string) => void;
  setSelectedCase: (c: number) => void;
  shiftSelectCase: (c: number) => void;
  setHoveredCase: (c: number | null) => void;
  setHoveredCaseRawX: (rawX: number | null) => void;
  setReferenceCase: (c: number | null) => void;
  setXRange: (range: [number, number]) => void;
  setZoomBySlider: (v: number) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  focusCase: (c: number) => void;
  previousCase: () => void;
  nextCase: () => void;
  setActivePlotSet: (id: string) => void;
  updateSeriesConfig: (seriesId: string, patch: Partial<SeriesConfig>) => void;
  setGridConfig: (patch: object) => void;
  setCursorConfig: (patch: object) => void;
  setAutosaveLayout: (enabled: boolean) => void;
  resetView: () => void;
  resetLayout: () => void;
  saveLayout: () => void;
  loadLayout: () => void;
  showToast: (message: string, kind?: ToastMessage["kind"]) => void;
  dismissToast: (id: string) => void;
  showError: (message: string) => void;
  clearError: () => void;
  setIsLoading: (v: boolean) => void;
}

function getFullWindow(model: WorkbookModel): number {
  const cases = getAllCases(model.rows);
  if (cases.length < 2) return 1;
  return cases[cases.length - 1] - cases[0];
}

function getDefaultXRange(model: WorkbookModel): { xRange: [number, number]; span: number; zoom: number } {
  const cases = getAllCases(model.rows);
  if (cases.length === 0) return { xRange: [0,1], span: 1, zoom: 0 };
  const fw = getFullWindow(model);
  if (cases.length < 16) {
    const xRange: [number, number] = [cases[0], cases[cases.length-1]];
    return { xRange, span: xRange[1]-xRange[0], zoom: computeZoomSliderValue(xRange[1]-xRange[0], fw) };
  }
  const xRange: [number, number] = [cases[0], cases[15]];
  const span = xRange[1] - xRange[0];
  return { xRange, span, zoom: computeZoomSliderValue(span, fw) };
}

export const useAppStore = create<AppState>((set, get) => ({
  workbookModel: sampleWorkbookModel,
  layoutState: { ...defaultLayout },
  plotSet: { ...defaultPlotSet, plots: defaultPlotSet.plots.map(p => ({ ...p, series: p.series.map(s => ({ ...s })) })) },
  settings: { autosaveLayout: true },
  toasts: [],
  activeError: null,
  isLoading: false,
  groupVisibilitySnapshots: {},

  loadWorkbook: (model) => {
    const cases = getAllCases(model.rows);
    const firstCase = cases[0] ?? 1;
    const { xRange, span, zoom } = getDefaultXRange(model);
    const visibleVariableKeys = model.variables.filter(v => v.variableKey !== "Case" && v.defaultVisible).map(v => v.variableKey);
    set(s => ({
      workbookModel: model,
      isLoading: false,
      activeError: null,
      layoutState: {
        ...s.layoutState,
        selectedCase: firstCase,
        referenceCase: firstCase,
        xRange,
        currentWindowSpan: span,
        zoomSliderValue: zoom,
        visibleGroupKeys: model.groups.map(g => g.groupKey),
        visibleVariableKeys,
      },
    }));
    scheduleAutosave(get);
  },

  loadSampleWorkbook: () => {
    set({ workbookModel: sampleWorkbookModel, layoutState: { ...defaultLayout }, activeError: null, isLoading: false });
  },

  toggleGroup: (groupKey) => {
    const s = get();
    const isVisible = s.layoutState.visibleGroupKeys.includes(groupKey);
    if (isVisible) {
      const groupVars = s.workbookModel.variables.filter(v => v.groupKey === groupKey && v.variableKey !== "Case");
      const snapshotKeys = groupVars.filter(v => s.layoutState.visibleVariableKeys.includes(v.variableKey)).map(v => v.variableKey);
      const newVisGroupKeys = s.layoutState.visibleGroupKeys.filter(k => k !== groupKey);
      const newVisVarKeys = s.layoutState.visibleVariableKeys.filter(k => !groupVars.map(v=>v.variableKey).includes(k));
      set(prev => ({
        groupVisibilitySnapshots: { ...prev.groupVisibilitySnapshots, [groupKey]: snapshotKeys },
        layoutState: { ...prev.layoutState, visibleGroupKeys: newVisGroupKeys, visibleVariableKeys: newVisVarKeys },
      }));
    } else {
      const snap = s.groupVisibilitySnapshots[groupKey];
      const groupVars = s.workbookModel.variables.filter(v => v.groupKey === groupKey && v.variableKey !== "Case");
      const toRestore = snap ?? groupVars.filter(v => v.defaultVisible).map(v => v.variableKey);
      const newVisVarKeys = [...new Set([...s.layoutState.visibleVariableKeys, ...toRestore])];
      set(prev => ({
        layoutState: { ...prev.layoutState, visibleGroupKeys: [...prev.layoutState.visibleGroupKeys, groupKey], visibleVariableKeys: newVisVarKeys },
      }));
    }
    scheduleAutosave(get);
  },

  toggleVariable: (variableKey) => {
    if (variableKey === "Case") return;
    set(s => {
      const vvk = s.layoutState.visibleVariableKeys;
      const next = vvk.includes(variableKey) ? vvk.filter(k => k !== variableKey) : [...vvk, variableKey];
      return { layoutState: { ...s.layoutState, visibleVariableKeys: next } };
    });
    scheduleAutosave(get);
  },

  toggleGroupCollapse: (groupKey) => {
    set(s => {
      const ck = s.layoutState.collapsedGroupKeys;
      return { layoutState: { ...s.layoutState, collapsedGroupKeys: ck.includes(groupKey) ? ck.filter(k=>k!==groupKey) : [...ck, groupKey] } };
    });
  },

  setSelectedCase: (c) => {
    set(s => ({ layoutState: { ...s.layoutState, selectedCase: c } }));
    scheduleAutosave(get);
  },

  shiftSelectCase: (c) => {
    set(s => {
      const prev = s.layoutState.selectedCase;
      return { layoutState: { ...s.layoutState, referenceCase: prev ?? c, selectedCase: c } };
    });
    scheduleAutosave(get);
  },

  setHoveredCase: (c) => set(s => ({ layoutState: { ...s.layoutState, hoveredCase: c } })),
  setHoveredCaseRawX: (rawX) => set(s => ({ layoutState: { ...s.layoutState, hoveredCaseRawX: rawX } })),
  setReferenceCase: (c) => set(s => ({ layoutState: { ...s.layoutState, referenceCase: c } })),

  setXRange: (range) => {
    const fw = getFullWindow(get().workbookModel);
    const span = range[1] - range[0];
    set(s => ({ layoutState: { ...s.layoutState, xRange: range, currentWindowSpan: span, zoomSliderValue: computeZoomSliderValue(span, fw) } }));
    scheduleAutosave(get);
  },

  setZoomBySlider: (v) => {
    const s = get();
    const cases = getAllCases(s.workbookModel.rows);
    if (cases.length === 0) return;
    const fw = getFullWindow(s.workbookModel);
    const span = computeWindowSpanFromSlider(v, fw);
    const center = s.layoutState.selectedCase ?? cases[Math.floor(cases.length/2)];
    const xRange = clampXRange(center, span, cases[0], cases[cases.length-1]);
    set(prev => ({ layoutState: { ...prev.layoutState, xRange, currentWindowSpan: span, zoomSliderValue: v } }));
    scheduleAutosave(get);
  },

  zoomIn: () => {
    const s = get();
    const cases = getAllCases(s.workbookModel.rows);
    if (cases.length === 0) return;
    const fw = getFullWindow(s.workbookModel);
    const newSpan = Math.max(10, s.layoutState.currentWindowSpan * 0.75);
    const center = s.layoutState.selectedCase ?? cases[0];
    const xRange = clampXRange(center, newSpan, cases[0], cases[cases.length-1]);
    const zoom = computeZoomSliderValue(newSpan, fw);
    set(prev => ({ layoutState: { ...prev.layoutState, xRange, currentWindowSpan: newSpan, zoomSliderValue: zoom } }));
    scheduleAutosave(get);
  },

  zoomOut: () => {
    const s = get();
    const cases = getAllCases(s.workbookModel.rows);
    if (cases.length === 0) return;
    const fw = getFullWindow(s.workbookModel);
    const newSpan = Math.min(fw, s.layoutState.currentWindowSpan / 0.75);
    const center = s.layoutState.selectedCase ?? cases[0];
    const xRange = clampXRange(center, newSpan, cases[0], cases[cases.length-1]);
    const zoom = computeZoomSliderValue(newSpan, fw);
    set(prev => ({ layoutState: { ...prev.layoutState, xRange, currentWindowSpan: newSpan, zoomSliderValue: zoom } }));
    scheduleAutosave(get);
  },

  focusCase: (c) => {
    const s = get();
    const cases = getAllCases(s.workbookModel.rows);
    if (cases.length === 0) return;
    const nc = nearestCase(c, cases);
    const xRange = clampXRange(nc, s.layoutState.currentWindowSpan, cases[0], cases[cases.length-1]);
    set(prev => ({ layoutState: { ...prev.layoutState, selectedCase: nc, xRange } }));
    scheduleAutosave(get);
  },

  previousCase: () => {
    const s = get();
    const cases = getAllCases(s.workbookModel.rows);
    const idx = cases.indexOf(s.layoutState.selectedCase!);
    if (idx <= 0) return;
    const nc = cases[idx - 1];
    const xRange = clampXRange(nc, s.layoutState.currentWindowSpan, cases[0], cases[cases.length-1]);
    set(prev => ({ layoutState: { ...prev.layoutState, selectedCase: nc, xRange } }));
    scheduleAutosave(get);
  },

  nextCase: () => {
    const s = get();
    const cases = getAllCases(s.workbookModel.rows);
    const idx = cases.indexOf(s.layoutState.selectedCase!);
    if (idx < 0 || idx >= cases.length - 1) return;
    const nc = cases[idx + 1];
    const xRange = clampXRange(nc, s.layoutState.currentWindowSpan, cases[0], cases[cases.length-1]);
    set(prev => ({ layoutState: { ...prev.layoutState, selectedCase: nc, xRange } }));
    scheduleAutosave(get);
  },

  setActivePlotSet: (id) => set(s => ({ layoutState: { ...s.layoutState, activePlotSetId: id } })),

  updateSeriesConfig: (seriesId, patch) => {
    set(s => ({
      plotSet: {
        ...s.plotSet,
        plots: s.plotSet.plots.map(p => ({
          ...p,
          series: p.series.map(ser => ser.id === seriesId ? { ...ser, ...patch } : ser),
        })),
      },
    }));
    scheduleAutosave(get);
  },

  setGridConfig: (patch) => {
    set(s => ({ layoutState: { ...s.layoutState, ...patch } }));
    scheduleAutosave(get);
  },

  setCursorConfig: (patch) => {
    set(s => ({ layoutState: { ...s.layoutState, ...patch } }));
    scheduleAutosave(get);
  },

  setAutosaveLayout: (enabled) => {
    set(s => ({ layoutState: { ...s.layoutState, autosaveLayout: enabled }, settings: { ...s.settings, autosaveLayout: enabled } }));
    get().showToast("Settings updated.");
  },

  resetView: () => {
    const s = get();
    if (s.workbookModel.isSample) {
      set(prev => ({
        layoutState: { ...prev.layoutState, selectedCase: 24, referenceCase: 24, xRange: [20,36], currentWindowSpan: 16, zoomSliderValue: 86 },
      }));
    } else {
      const { xRange, span, zoom } = getDefaultXRange(s.workbookModel);
      const cases = getAllCases(s.workbookModel.rows);
      set(prev => ({
        layoutState: { ...prev.layoutState, selectedCase: cases[0]??null, referenceCase: cases[0]??null, xRange, currentWindowSpan: span, zoomSliderValue: zoom },
      }));
    }
    scheduleAutosave(get);
  },

  resetLayout: () => {
    clearLayout();
    set({
      layoutState: { ...defaultLayout },
      plotSet: { ...defaultPlotSet, plots: defaultPlotSet.plots.map(p => ({ ...p, series: p.series.map(s => ({...s})) })) },
      settings: { autosaveLayout: true },
    });
    get().showToast("Settings updated.");
  },

  saveLayout: () => {
    if (autosaveTimer) { clearTimeout(autosaveTimer); autosaveTimer = null; }
    const s = get();
    saveLayout({ layoutState: s.layoutState, plotSet: s.plotSet, settings: s.settings });
    get().showToast("Layout saved.");
  },

  loadLayout: () => {
    const data = loadLayoutData() as { layoutState?: AppLayoutState; plotSet?: PlotSet; settings?: AppSettings } | null;
    if (!data) return;
    set(s => ({
      layoutState: data.layoutState ? { ...s.layoutState, ...data.layoutState } : s.layoutState,
      plotSet: data.plotSet ?? s.plotSet,
      settings: data.settings ?? s.settings,
    }));
  },

  showToast: (message, kind = "success") => {
    const id = Math.random().toString(36).slice(2);
    const now = Date.now();
    set(s => ({ toasts: [...s.toasts, { id, message, kind, createdAt: now, expiresAt: now + 2500 }] }));
    setTimeout(() => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })), 2600);
  },

  dismissToast: (id) => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),
  showError: (message) => set({ activeError: message, isLoading: false }),
  clearError: () => set({ activeError: null }),
  setIsLoading: (v) => set({ isLoading: v }),
}));
