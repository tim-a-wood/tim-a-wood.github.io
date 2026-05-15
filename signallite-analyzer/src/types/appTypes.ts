export type DataType = "number" | "string" | "boolean" | "date";

export interface DataGroup {
  groupKey: string;
  displayName: string;
  color: string;
  sortOrder: number;
  defaultVisible: boolean;
}

export interface VariableDefinition {
  variableKey: string;
  displayName: string;
  groupKey: string;
  unit: string;
  dataType: DataType;
  sortOrder: number;
  defaultVisible: boolean;
  source: "file" | "derived";
}

export type DataValue = number | string | boolean | Date | null;
export type DataRow = Record<string, DataValue>;

export interface WorkbookModel {
  fileName: string;
  loadedAtIso: string;
  isSample: boolean;
  groups: DataGroup[];
  variables: VariableDefinition[];
  rows: DataRow[];
}

export interface SeriesConfig {
  id: string;
  variableKey: string;
  label: string;
  color: string;
  lineStyle: "solid" | "dashed" | "dotted";
  width: number;
  yAxis: "left" | "right";
  visible: boolean;
}

export interface PlotConfig {
  id: string;
  title: string;
  leftAxisLabel: string;
  rightAxisLabel?: string;
  series: SeriesConfig[];
}

export interface PlotSet {
  id: string;
  name: string;
  xAxisVariableKey: string;
  plots: PlotConfig[];
}

export interface AppLayoutState {
  visibleGroupKeys: string[];
  visibleVariableKeys: string[];
  collapsedGroupKeys: string[];
  selectedCase: number | null;
  hoveredCase: number | null;
  hoveredCaseRawX: number | null;
  referenceCase: number | null;
  xRange: [number, number] | null;
  currentWindowSpan: number;
  zoomSliderValue: number;
  activePlotSetId: string;
  showXGrid: boolean;
  showYGrid: boolean;
  showMinorGrid: boolean;
  gridStyle: "solid" | "dashed" | "dotted";
  gridOpacity: number;
  showCrosshair: boolean;
  snapToData: boolean;
  showTooltips: boolean;
  autosaveLayout: boolean;
}

export interface AppSettings {
  autosaveLayout: boolean;
}

export interface ToastMessage {
  id: string;
  message: string;
  kind: "success" | "info" | "warning";
  createdAt: number;
  expiresAt: number;
}
