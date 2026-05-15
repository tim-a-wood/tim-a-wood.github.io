import React, { useRef, useCallback, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { ECharts } from "echarts";
import { useAppStore } from "../store/useAppStore";
import { setEChartsInstance } from "./echartsInstance";
import { getAllCases, getRowByCase } from "../model/selectors";
import { nearestCase } from "../model/xRange";
import { formatTooltipValue } from "../utils/format";
import { hexToRgba } from "../utils/color";

const LINE_STYLE_MAP: Record<string, string> = { solid: "solid", dashed: "dashed", dotted: "dotted" };

const GRIDS = [
  { top: "6%", height: "24%", left: "8%", right: "15%" },
  { top: "37%", height: "24%", left: "8%", right: "15%" },
  { top: "68%", height: "24%", left: "8%", right: "15%" },
];

export function StackedPlots() {
  const echartsRef = useRef<ReactECharts>(null);
  const workbookModel = useAppStore(s => s.workbookModel);
  const layoutState = useAppStore(s => s.layoutState);
  const plotSet = useAppStore(s => s.plotSet);
  const setSelectedCase = useAppStore(s => s.setSelectedCase);
  const shiftSelectCase = useAppStore(s => s.shiftSelectCase);
  const setHoveredCase = useAppStore(s => s.setHoveredCase);
  const setHoveredCaseRawX = useAppStore(s => s.setHoveredCaseRawX);
  const setXRange = useAppStore(s => s.setXRange);

  const { rows, variables } = workbookModel;
  const {
    xRange,
    selectedCase,
    hoveredCase,
    hoveredCaseRawX,
    showXGrid,
    showYGrid,
    showMinorGrid,
    gridStyle,
    gridOpacity,
    showCrosshair,
    snapToData,
    showTooltips,
  } = layoutState;

  const allCases = useMemo(() => getAllCases(rows), [rows]);

  const effectiveCursorX = useMemo(() => {
    if (hoveredCase !== null) {
      return snapToData ? hoveredCase : (hoveredCaseRawX ?? hoveredCase);
    }
    return selectedCase;
  }, [hoveredCase, hoveredCaseRawX, selectedCase, snapToData]);

  const gridLineStyle = useMemo(() => ({ type: LINE_STYLE_MAP[gridStyle] as "solid" | "dashed" | "dotted", opacity: gridOpacity / 100 }), [gridStyle, gridOpacity]);

  const option = useMemo(() => {
    const minCase = xRange?.[0] ?? (allCases[0] ?? 1);
    const maxCase = xRange?.[1] ?? (allCases[allCases.length - 1] ?? 120);

    const grids = GRIDS;
    const xAxes: object[] = [];
    const yAxes: object[] = [];
    const seriesList: object[] = [];
    const legends: object[] = [];

    const axisBase = {
      type: "value",
      axisLine: { lineStyle: { color: "rgba(32,50,66,0.8)" } },
      splitLine: { lineStyle: { color: "rgba(32,50,66,0.5)" } },
      axisLabel: { color: "#8797a7", fontSize: 10, fontFamily: "JetBrains Mono, monospace" },
      axisTick: { lineStyle: { color: "rgba(32,50,66,0.8)" } },
    };

    plotSet.plots.forEach((plot, pi) => {
      xAxes.push({
        ...axisBase,
        gridIndex: pi,
        min: minCase,
        max: maxCase,
        splitLine: { show: showXGrid, lineStyle: { ...gridLineStyle, color: "rgba(32,50,66,0.5)" } },
        minorSplitLine: { show: showMinorGrid, lineStyle: { ...gridLineStyle, color: "rgba(32,50,66,0.25)" } },
        axisPointer: { snap: true },
      });

      // Collect left and right series
      const leftSeries = plot.series.filter(s => s.visible && s.yAxis === "left");
      const rightSeries = plot.series.filter(s => s.visible && s.yAxis === "right");
      const hasRight = rightSeries.length > 0;

      // Left Y axis
      yAxes.push({
        ...axisBase,
        gridIndex: pi,
        name: plot.leftAxisLabel,
        nameTextStyle: { color: "#8797a7", fontSize: 9 },
        splitLine: { show: showYGrid, lineStyle: { ...gridLineStyle, color: "rgba(32,50,66,0.5)" } },
        minorSplitLine: { show: showMinorGrid, lineStyle: { ...gridLineStyle, color: "rgba(32,50,66,0.25)" } },
      });

      // Right Y axis
      yAxes.push({
        ...axisBase,
        gridIndex: pi,
        name: plot.rightAxisLabel ?? "",
        nameTextStyle: { color: "#8797a7", fontSize: 9 },
        splitLine: { show: false },
        position: "right",
      });

      const legendData: string[] = [];

      plot.series.forEach((s, si) => {
        if (!s.visible) return;
        const seriesData = rows.map(row => {
          const x = row["Case"];
          const y = row[s.variableKey];
          return [typeof x === "number" ? x : null, typeof y === "number" ? y : null];
        }).filter(d => d[0] !== null);

        const isLeft = s.yAxis === "left";
        const yAxisIndex = pi * 2 + (isLeft ? 0 : 1);

        const markLine = (si === 0 && effectiveCursorX !== null) ? {
          silent: true,
          symbol: "none",
          animation: false,
          lineStyle: { color: "#e8eef5", type: "dashed", width: 1 },
          data: [{ xAxis: effectiveCursorX }],
          label: { show: false },
        } : undefined;

        seriesList.push({
          type: "line",
          name: s.label,
          data: seriesData,
          xAxisIndex: pi,
          yAxisIndex,
          smooth: false,
          symbol: "none",
          lineStyle: {
            color: s.color,
            type: LINE_STYLE_MAP[s.lineStyle] as string,
            width: s.width,
          },
          itemStyle: { color: s.color },
          emphasis: { disabled: true },
          ...(markLine ? { markLine } : {}),
        });

        legendData.push(s.label);
      });

      // Empty state: if no visible series
      const visibleCount = plot.series.filter(s => s.visible).length;
      if (visibleCount === 0) {
        // Add an empty series so the grid still renders
        seriesList.push({
          type: "line",
          name: `${plot.title} (empty)`,
          data: [],
          xAxisIndex: pi,
          yAxisIndex: pi * 2,
          silent: true,
        });
      }

      if (legendData.length > 0) {
        legends.push({
          data: legendData,
          orient: "vertical",
          right: "2%",
          top: GRIDS[pi]?.top ?? "6%",
          backgroundColor: hexToRgba("#0a121a", 0.7),
          padding: [4, 8],
          textStyle: { color: "#8797a7", fontSize: 9, fontFamily: "JetBrains Mono, monospace" },
          icon: "roundRect",
          itemWidth: 16,
          itemHeight: 3,
          itemGap: 4,
        });
      }
    });

    return {
      backgroundColor: "#070d13",
      animation: false,
      grid: grids.map(g => ({ ...g, containLabel: false })),
      xAxis: xAxes,
      yAxis: yAxes,
      series: seriesList,
      legend: legends,
      axisPointer: {
        link: [{ xAxisIndex: "all" }],
        type: showCrosshair ? "cross" : "line",
        label: { backgroundColor: "#0d1822", borderColor: "#2a4358", color: "#c5d0dc", fontSize: 10 },
        crossStyle: { color: "#637385", type: "dashed" },
      },
      tooltip: {
        show: showTooltips,
        trigger: "axis",
        axisPointer: { type: showCrosshair ? "cross" : "line" },
        backgroundColor: "#0d1822",
        borderColor: "#2a4358",
        textStyle: { color: "#c5d0dc", fontSize: 11, fontFamily: "JetBrains Mono, monospace" },
        formatter: (params: unknown) => {
          if (!Array.isArray(params) || params.length === 0) return "";
          const caseVal = (params[0] as { data: [number, number] }).data[0];
          const displayCase = snapToData ? nearestCase(caseVal, allCases) : caseVal;
          let html = `<div style="font-weight:600;margin-bottom:4px;">Case # ${displayCase}</div>`;
          for (const p of params as { seriesName: string; color: string; data: [number, number] }[]) {
            const y = p.data[1];
            // Find the variable key from series name
            const s = plotSet.plots.flatMap(pl => pl.series).find(s => s.label === p.seriesName);
            const formatted = s ? formatTooltipValue(y, s.variableKey) : (y !== null && y !== undefined ? String(y) : "-");
            html += `<div style="display:flex;align-items:center;gap:6px;"><span style="width:10px;height:3px;display:inline-block;background:${p.color};border-radius:2px;"></span><span style="color:#8797a7;">${p.seriesName}</span><span style="margin-left:auto;padding-left:12px;">${formatted}</span></div>`;
          }
          return html;
        },
        padding: [8, 12],
      },
      dataZoom: plotSet.plots.flatMap((_, pi) => [
        { type: "inside", xAxisIndex: pi, start: 0, end: 100, zoomOnMouseWheel: true, moveOnMouseMove: true },
      ]),
    };
  }, [plotSet, rows, xRange, allCases, showXGrid, showYGrid, showMinorGrid, gridLineStyle, showCrosshair, showTooltips, snapToData, effectiveCursorX]);

  const onChartReady = useCallback((inst: ECharts) => {
    setEChartsInstance(inst);
  }, []);

  const handleClick = useCallback((params: { data?: [number, number]; event?: { event?: MouseEvent } }) => {
    if (!params.data) return;
    const x = params.data[0];
    const closest = nearestCase(x, allCases);
    const shiftKey = params.event?.event?.shiftKey ?? false;
    if (shiftKey) shiftSelectCase(closest);
    else setSelectedCase(closest);
  }, [allCases, setSelectedCase, shiftSelectCase]);

  const handleMouseMove = useCallback((params: { data?: [number, number] }) => {
    if (!params.data) return;
    const x = params.data[0];
    setHoveredCaseRawX(x);
    setHoveredCase(nearestCase(x, allCases));
  }, [allCases, setHoveredCase, setHoveredCaseRawX]);

  const handleMouseOut = useCallback(() => {
    setHoveredCase(null);
    setHoveredCaseRawX(null);
  }, [setHoveredCase, setHoveredCaseRawX]);

  const handleDataZoom = useCallback((params: unknown) => {
    const inst = echartsRef.current?.getEchartsInstance();
    if (!inst) return;
    const opt = inst.getOption() as { xAxis?: { min?: number; max?: number }[] };
    const xAxis0 = opt.xAxis?.[0];
    if (xAxis0 && typeof xAxis0.min === "number" && typeof xAxis0.max === "number") {
      setXRange([xAxis0.min, xAxis0.max]);
    }
  }, [setXRange]);

  const onEvents = useMemo(() => ({
    click: handleClick,
    mousemove: handleMouseMove,
    mouseout: handleMouseOut,
    datazoom: handleDataZoom,
  }), [handleClick, handleMouseMove, handleMouseOut, handleDataZoom]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <ReactECharts
        ref={echartsRef}
        option={option}
        style={{ width: "100%", height: "100%" }}
        notMerge={false}
        lazyUpdate={true}
        onChartReady={onChartReady}
        onEvents={onEvents}
      />
    </div>
  );
}
