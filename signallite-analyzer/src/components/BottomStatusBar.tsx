import React, { useMemo } from "react";
import { useAppStore } from "../store/useAppStore";
import { getRowByCase } from "../model/selectors";
import { formatTooltipValue } from "../utils/format";

export function BottomStatusBar() {
  const workbookModel = useAppStore(s => s.workbookModel);
  const layoutState = useAppStore(s => s.layoutState);
  const plotSet = useAppStore(s => s.plotSet);

  const { rows } = workbookModel;
  const { selectedCase, hoveredCase, hoveredCaseRawX } = layoutState;
  const displayCase = hoveredCase ?? selectedCase;

  const row = useMemo(() => {
    if (displayCase === null) return undefined;
    return getRowByCase(rows, displayCase);
  }, [rows, displayCase]);

  const firstPlot = plotSet.plots[0];
  const visibleSeries = firstPlot?.series.filter(s => s.visible).slice(0, 4) ?? [];

  const seriesValues = visibleSeries.map(s => {
    const val = row?.[s.variableKey];
    const formatted = formatTooltipValue(val ?? null, s.variableKey);
    return `${s.label}: ${formatted}`;
  });

  // ΔX: difference between hoveredCaseRawX and selectedCase
  let dxStr = "";
  if (hoveredCaseRawX !== null && selectedCase !== null) {
    const dx = hoveredCaseRawX - selectedCase;
    dxStr = ` | ΔX: ${dx > 0 ? "+" : ""}${dx.toFixed(1)}`;
  }

  return (
    <div
      className="app-bottom-status"
      style={{
        display: "flex",
        alignItems: "center",
        padding: "0 12px",
        fontFamily: "var(--font-mono)",
        fontSize: 11,
        color: "var(--text-2)",
        background: "var(--panel)",
        gap: 0,
        overflow: "hidden",
        whiteSpace: "nowrap",
      }}
    >
      {displayCase !== null ? (
        <span>
          <span style={{ color: "var(--text-1)", fontWeight: 600 }}>Cursor: Case # {displayCase}</span>
          {seriesValues.length > 0 && " | "}
          {seriesValues.join(" | ")}
          {dxStr}
        </span>
      ) : (
        <span style={{ color: "var(--text-muted)" }}>No case selected</span>
      )}
    </div>
  );
}
