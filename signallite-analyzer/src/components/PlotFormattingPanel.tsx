import React from "react";
import { useAppStore } from "../store/useAppStore";
import { Toggle } from "./Toggle";
import { Select } from "./Select";
import { ColorSwatch } from "./ColorSwatch";
import { Button } from "./Button";
import { AppTooltip } from "./AppTooltip";
import { tooltipContent } from "../config/tooltipContent";

const LINE_STYLE_OPTIONS = [
  { value: "solid", label: "Solid" },
  { value: "dashed", label: "Dashed" },
  { value: "dotted", label: "Dotted" },
];

const WIDTH_OPTIONS = [
  { value: "1", label: "1px" },
  { value: "2", label: "2px" },
  { value: "3", label: "3px" },
];

const AXIS_OPTIONS = [
  { value: "left", label: "Left" },
  { value: "right", label: "Right" },
];

const GRID_STYLE_OPTIONS = [
  { value: "solid", label: "Solid" },
  { value: "dashed", label: "Dashed" },
  { value: "dotted", label: "Dotted" },
];

export function PlotFormattingPanel() {
  const plotSet = useAppStore(s => s.plotSet);
  const layoutState = useAppStore(s => s.layoutState);
  const updateSeriesConfig = useAppStore(s => s.updateSeriesConfig);
  const setGridConfig = useAppStore(s => s.setGridConfig);
  const setCursorConfig = useAppStore(s => s.setCursorConfig);
  const resetView = useAppStore(s => s.resetView);

  const {
    showXGrid, showYGrid, showMinorGrid, gridStyle, gridOpacity,
    showCrosshair, snapToData, showTooltips,
  } = layoutState;

  return (
    <div className="plot-panel">
      <div className="plot-panel-section">
        <div className="sidebar-section-header" style={{ padding: "8px 0 4px" }}>
          <AppTooltip content={tooltipContent.plotFormatting}>
            <span className="sidebar-section-title">Plot Formatting</span>
          </AppTooltip>
          <span className="sidebar-section-label">Configurable</span>
        </div>
      </div>

      {/* Plot Set Selection */}
      <div className="plot-panel-section">
        <div className="plot-panel-section-title">Plot Set</div>
        <Select
          value={plotSet.id}
          onChange={() => {}}
          options={[{ value: plotSet.id, label: plotSet.name }]}
          disabled
        />
      </div>

      {/* Series per plot */}
      {plotSet.plots.map(plot => (
        <div key={plot.id} className="plot-panel-section">
          <div className="plot-panel-section-title">{plot.title}</div>
          {plot.series.map(s => (
            <div key={s.id} className="series-row">
              <div className="series-row-top">
                <AppTooltip content={tooltipContent.seriesVisibility}>
                  <input
                    type="checkbox"
                    checked={s.visible}
                    onChange={e => updateSeriesConfig(s.id, { visible: e.target.checked })}
                    aria-label={`Toggle ${s.label}`}
                  />
                </AppTooltip>
                <span className="series-label" title={s.label}>{s.label}</span>
              </div>
              <div className="series-row-bottom">
                <AppTooltip content={tooltipContent.colorSwatch}>
                  <ColorSwatch color={s.color} onChange={color => updateSeriesConfig(s.id, { color })} />
                </AppTooltip>
                <AppTooltip content={tooltipContent.lineStyle}>
                  <Select
                    value={s.lineStyle}
                    onChange={v => updateSeriesConfig(s.id, { lineStyle: v as "solid" | "dashed" | "dotted" })}
                    options={LINE_STYLE_OPTIONS}
                  />
                </AppTooltip>
                <Select
                  value={String(s.width)}
                  onChange={v => updateSeriesConfig(s.id, { width: Number(v) })}
                  options={WIDTH_OPTIONS}
                />
                <Select
                  value={s.yAxis}
                  onChange={v => updateSeriesConfig(s.id, { yAxis: v as "left" | "right" })}
                  options={AXIS_OPTIONS}
                />
              </div>
            </div>
          ))}
        </div>
      ))}

      {/* Grid */}
      <div className="plot-panel-section">
        <div className="plot-panel-section-title">Grid</div>
        <div className="grid-row">
          <span className="grid-row-label">X Grid</span>
          <AppTooltip content={tooltipContent.gridToggle}>
            <Toggle checked={showXGrid} onChange={v => setGridConfig({ showXGrid: v })} />
          </AppTooltip>
        </div>
        <div className="grid-row">
          <span className="grid-row-label">Y Grid</span>
          <AppTooltip content={tooltipContent.gridToggle}>
            <Toggle checked={showYGrid} onChange={v => setGridConfig({ showYGrid: v })} />
          </AppTooltip>
        </div>
        <div className="grid-row">
          <span className="grid-row-label">Minor Grid</span>
          <Toggle checked={showMinorGrid} onChange={v => setGridConfig({ showMinorGrid: v })} />
        </div>
        <div className="grid-row">
          <span className="grid-row-label">Style</span>
          <Select value={gridStyle} onChange={v => setGridConfig({ gridStyle: v as "solid" | "dashed" | "dotted" })} options={GRID_STYLE_OPTIONS} />
        </div>
        <div className="grid-row">
          <span className="grid-row-label">Opacity</span>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <input
              type="range"
              min={0}
              max={100}
              value={gridOpacity}
              onChange={e => setGridConfig({ gridOpacity: Number(e.target.value) })}
              style={{ width: 60, accentColor: "var(--blue)" }}
              aria-label="Grid opacity"
            />
            <span style={{ fontSize: 11, color: "var(--text-muted)", minWidth: 28, fontFamily: "var(--font-mono)" }}>{gridOpacity}%</span>
          </div>
        </div>
      </div>

      {/* Cursor */}
      <div className="plot-panel-section">
        <div className="plot-panel-section-title">Cursor</div>
        <div className="grid-row">
          <span className="grid-row-label">Crosshair</span>
          <AppTooltip content={tooltipContent.cursorToggle}>
            <Toggle checked={showCrosshair} onChange={v => setCursorConfig({ showCrosshair: v })} />
          </AppTooltip>
        </div>
        <div className="grid-row">
          <span className="grid-row-label">Snap to Data</span>
          <AppTooltip content={tooltipContent.snapToData}>
            <Toggle checked={snapToData} onChange={v => setCursorConfig({ snapToData: v })} />
          </AppTooltip>
        </div>
        <div className="grid-row">
          <span className="grid-row-label">Tooltips</span>
          <AppTooltip content={tooltipContent.showTooltips}>
            <Toggle checked={showTooltips} onChange={v => setCursorConfig({ showTooltips: v })} />
          </AppTooltip>
        </div>
      </div>

      {/* X Axis Navigation */}
      <div className="plot-panel-section">
        <div className="plot-panel-section-title">X Axis Navigation</div>
        <div className="grid-row">
          <span className="grid-row-label">Zoom Behavior</span>
          <Button variant="ghost" size="sm" disabled>Horizontal</Button>
        </div>
        <div className="grid-row">
          <span className="grid-row-label">Zoom Mode</span>
          <Button variant="ghost" size="sm" disabled>Brush + Controls</Button>
        </div>
      </div>

      {/* Reset View */}
      <div className="plot-panel-section">
        <Button variant="ghost" size="sm" onClick={resetView} style={{ width: "100%" }}>Reset View</Button>
      </div>
    </div>
  );
}
