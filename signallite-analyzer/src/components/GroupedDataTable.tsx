import React, { useMemo, useRef, useEffect } from "react";
import { useAppStore } from "../store/useAppStore";
import { getVisibleGroups, getVisibleVariablesForGroup } from "../model/selectors";
import { formatTableValue } from "../utils/format";
import { hexToRgba } from "../utils/color";
import type { DataRow } from "../types/appTypes";

interface ColDef {
  id: string;
  header: string;
  accessor: (row: DataRow) => unknown;
  meta: { groupKey: string; groupLabel: string; groupColor: string };
  isCase: boolean;
  isNumeric: boolean;
}

export function GroupedDataTable() {
  const workbookModel = useAppStore(s => s.workbookModel);
  const layoutState = useAppStore(s => s.layoutState);
  const setSelectedCase = useAppStore(s => s.setSelectedCase);
  const shiftSelectCase = useAppStore(s => s.shiftSelectCase);

  const { groups, variables, rows } = workbookModel;
  const { visibleGroupKeys, visibleVariableKeys, selectedCase } = layoutState;

  const visibleGroups = useMemo(
    () => getVisibleGroups(groups, visibleGroupKeys),
    [groups, visibleGroupKeys]
  );

  const cols = useMemo<ColDef[]>(() => {
    const result: ColDef[] = [];
    result.push({
      id: "Case",
      header: "Case #",
      accessor: row => row["Case"],
      meta: { groupKey: "_case", groupLabel: "Case", groupColor: "#2f8cff" },
      isCase: true,
      isNumeric: false,
    });
    for (const group of visibleGroups) {
      const vars = getVisibleVariablesForGroup(variables, group.groupKey, visibleVariableKeys)
        .filter(v => v.variableKey !== "Case");
      for (const v of vars) {
        result.push({
          id: v.variableKey,
          header: `${v.displayName} [${v.unit}]`,
          accessor: row => row[v.variableKey],
          meta: { groupKey: group.groupKey, groupLabel: group.displayName, groupColor: group.color },
          isCase: false,
          isNumeric: v.dataType === "number",
        });
      }
    }
    return result;
  }, [visibleGroups, variables, visibleVariableKeys]);

  const headerGroups = useMemo(() => {
    const result: { groupKey: string; groupLabel: string; groupColor: string; colCount: number }[] = [];
    for (const col of cols) {
      const last = result[result.length - 1];
      if (last && last.groupKey === col.meta.groupKey) {
        last.colCount++;
      } else {
        result.push({ ...col.meta, colCount: 1 });
      }
    }
    return result;
  }, [cols]);

  const tableRef = useRef<HTMLTableElement>(null);
  useEffect(() => {
    if (selectedCase === null) return;
    const el = tableRef.current?.querySelector(`[data-case="${selectedCase}"]`);
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedCase]);

  return (
    <div className="table-wrapper">
      <table className="grouped-data-table" ref={tableRef}>
        <thead>
          <tr>
            {headerGroups.map(g => (
              <th
                key={g.groupKey}
                className="group-header"
                colSpan={g.colCount}
                style={{
                  background: hexToRgba(g.groupColor, 0.18),
                  borderBottom: `2px solid ${hexToRgba(g.groupColor, 0.55)}`,
                }}
              >
                {g.groupKey === "_case" ? "" : g.groupLabel}
              </th>
            ))}
          </tr>
          <tr>
            {cols.map(col => (
              <th
                key={col.id}
                className={`var-header${col.isCase ? " th-case" : ""}`}
                style={{ minWidth: col.isCase ? 60 : 90, left: col.isCase ? 0 : undefined }}
                title={col.id}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => {
            const caseVal = row["Case"];
            const isSelected = caseVal === selectedCase;
            return (
              <tr
                key={ri}
                className={`tr-body${isSelected ? " tr-selected" : ""}`}
                data-case={String(caseVal)}
                onClick={e => {
                  if (typeof caseVal !== "number") return;
                  if (e.shiftKey) shiftSelectCase(caseVal);
                  else setSelectedCase(caseVal);
                }}
              >
                {cols.map(col => {
                  const val = col.accessor(row);
                  const formatted = formatTableValue(val, col.id);
                  let content: React.ReactNode = formatted;
                  if (col.id === "PassFail") {
                    const cls =
                      formatted === "PASS" ? "status-pass" :
                      formatted === "FAIL" ? "status-fail" :
                      formatted === "WARN" ? "status-warn" : "";
                    content = <span className={cls}>{formatted}</span>;
                  }
                  return (
                    <td
                      key={col.id}
                      className={`${col.isCase ? "td-case" : ""}${col.isNumeric ? " td-num" : ""}`}
                      style={{ left: col.isCase ? 0 : undefined }}
                    >
                      {content}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
