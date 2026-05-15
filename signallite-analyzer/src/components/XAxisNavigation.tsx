import React, { useState, useCallback, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { useAppStore } from "../store/useAppStore";
import { getAllCases } from "../model/selectors";
import { nearestCase } from "../model/xRange";
import { AppTooltip } from "./AppTooltip";
import { Button } from "./Button";
import { NumberInput } from "./NumberInput";
import { tooltipContent } from "../config/tooltipContent";

export function XAxisNavigation() {
  const workbookModel = useAppStore(s => s.workbookModel);
  const layoutState = useAppStore(s => s.layoutState);
  const zoomIn = useAppStore(s => s.zoomIn);
  const zoomOut = useAppStore(s => s.zoomOut);
  const setZoomBySlider = useAppStore(s => s.setZoomBySlider);
  const focusCase = useAppStore(s => s.focusCase);
  const previousCase = useAppStore(s => s.previousCase);
  const nextCase = useAppStore(s => s.nextCase);
  const setXRange = useAppStore(s => s.setXRange);

  const [focusInput, setFocusInput] = useState("");
  const [focusError, setFocusError] = useState("");

  const { rows } = workbookModel;
  const { xRange, zoomSliderValue } = layoutState;

  const allCases = useMemo(() => getAllCases(rows), [rows]);
  const minCase = allCases[0] ?? 1;
  const maxCase = allCases[allCases.length - 1] ?? 120;

  const lo = xRange ? Math.round(xRange[0]) : minCase;
  const hi = xRange ? Math.round(xRange[1]) : maxCase;

  const handleGoFocus = () => {
    const parsed = parseFloat(focusInput);
    if (isNaN(parsed)) { setFocusError("Enter a numeric case."); return; }
    setFocusError("");
    focusCase(nearestCase(parsed, allCases));
    setFocusInput("");
  };

  const overviewOption = useMemo(() => {
    const data = allCases.map(c => [c, 0]);
    const startValue = xRange?.[0] ?? minCase;
    const endValue = xRange?.[1] ?? maxCase;
    return {
      backgroundColor: "#0b141d",
      animation: false,
      grid: { top: 4, bottom: 18, left: 8, right: 8, containLabel: false },
      xAxis: {
        type: "value",
        min: minCase,
        max: maxCase,
        show: false,
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { show: false },
        splitLine: { show: false },
      },
      yAxis: { type: "value", show: false, min: 0, max: 1 },
      series: [{
        type: "line",
        data,
        symbol: "none",
        lineStyle: { color: "#2f8cff", width: 1, opacity: 0.5 },
      }],
      dataZoom: [{
        type: "slider",
        xAxisIndex: 0,
        startValue,
        endValue,
        height: 14,
        bottom: 2,
        brushSelect: false,
        handleSize: "80%",
        handleStyle: { color: "#2f8cff", borderColor: "#2f8cff" },
        fillerColor: "rgba(47,140,255,0.15)",
        borderColor: "rgba(47,140,255,0.3)",
        backgroundColor: "rgba(11,20,29,0.8)",
        dataBackground: { lineStyle: { color: "#2f8cff", opacity: 0.3 }, areaStyle: { color: "rgba(47,140,255,0.08)" } },
        selectedDataBackground: { lineStyle: { color: "#2f8cff" }, areaStyle: { color: "rgba(47,140,255,0.15)" } },
        showDetail: false,
        showDataShadow: true,
        textStyle: { color: "#637385", fontSize: 9 },
        labelFormatter: (v: number) => String(Math.round(v)),
      }],
    };
  }, [allCases, minCase, maxCase, xRange]);

  const handleOverviewDataZoom = useCallback((params: unknown, chart: unknown) => {
    const inst = chart as { getOption: () => { xAxis?: { min?: number; max?: number }[] } };
    if (!inst) return;
    const opt = inst.getOption();
    const xAxis0 = opt.xAxis?.[0];
    if (xAxis0 && typeof xAxis0.min === "number" && typeof xAxis0.max === "number") {
      // The dataZoom gives us start/end values
      const p = params as { start?: number; end?: number; startValue?: number; endValue?: number };
      if (typeof p.startValue === "number" && typeof p.endValue === "number") {
        setXRange([p.startValue, p.endValue]);
      }
    }
  }, [setXRange]);

  return (
    <div className="x-axis-nav">
      <span style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", whiteSpace: "nowrap" }}>X-Axis</span>

      {/* Zoom controls */}
      <AppTooltip content={tooltipContent.zoomMinus}>
        <Button variant="icon" size="sm" onClick={zoomOut} aria-label="Zoom out">−</Button>
      </AppTooltip>
      <AppTooltip content={tooltipContent.zoomSlider}>
        <input
          type="range"
          min={0}
          max={100}
          value={zoomSliderValue}
          onChange={e => setZoomBySlider(Number(e.target.value))}
          style={{ width: 80, accentColor: "var(--blue)" }}
          aria-label="Zoom level"
        />
      </AppTooltip>
      <AppTooltip content={tooltipContent.zoomPlus}>
        <Button variant="icon" size="sm" onClick={zoomIn} aria-label="Zoom in">+</Button>
      </AppTooltip>

      {/* Overview brush */}
      <AppTooltip content={tooltipContent.overviewBrush}>
        <div className="overview-brush-container">
          <ReactECharts
            option={overviewOption}
            style={{ width: "100%", height: "100%" }}
            notMerge={false}
            lazyUpdate={true}
            onEvents={{ datazoom: handleOverviewDataZoom }}
          />
        </div>
      </AppTooltip>

      {/* X Range chip */}
      <div className="x-range-chip">Cases: {lo}–{hi}</div>

      {/* Focus Case */}
      <span style={{ fontSize: 11, color: "var(--text-2)", whiteSpace: "nowrap" }}>Focus Case #</span>
      <AppTooltip content={tooltipContent.focusCase}>
        <NumberInput
          value={focusInput}
          onChange={v => { setFocusInput(v); setFocusError(""); }}
          onEnter={handleGoFocus}
          error={focusError}
          placeholder="e.g. 24"
        />
      </AppTooltip>
      <Button variant="ghost" size="sm" onClick={handleGoFocus}>Go</Button>

      {/* Prev / Next */}
      <AppTooltip content={tooltipContent.previousCase}>
        <Button variant="ghost" size="sm" onClick={previousCase} aria-label="Previous case">|◀ Prev</Button>
      </AppTooltip>
      <AppTooltip content={tooltipContent.nextCase}>
        <Button variant="ghost" size="sm" onClick={nextCase} aria-label="Next case">Next ▶|</Button>
      </AppTooltip>
    </div>
  );
}
