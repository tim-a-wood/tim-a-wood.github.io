import React, { useMemo, useRef, useEffect } from "react";
import {
  useReactTable,
  getCoreRowModel,
  createColumnHelper,
  flexRender,
} from "@tanstack/react-table";
import { useAppStore } from "../store/useAppStore";
import { getVisibleGroups, getVisibleVariablesForGroup } from "../model/selectors";
import { formatTableValue } from "../utils/format";
import { hexToRgba } from "../utils/color";
import type { DataRow } from "../types/appTypes";

const columnHelper = createColumnHelper<DataRow>();

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

  const columnDefs = useMemo(() => {
    const cols = [];

    // Case column (always first, sticky)
    cols.push(
      columnHelper.accessor(row => row["Case"], {
        id: "Case",
        header: "Case",
        cell: info => {
          const v = info.getValue();
          return <span>{formatTableValue(v as number, "Case")}</span>;
        },
        meta: { groupKey: "_case", groupLabel: "Case", groupColor: "#2f8cff" },
      })
    );

    // One column per visible variable per visible group
    for (const group of visibleGroups) {
      const vars = getVisibleVariablesForGroup(variables, group.groupKey, visibleVariableKeys).filter(v => v.variableKey !== "Case");
      for (const v of vars) {
        cols.push(
          columnHelper.accessor(row => row[v.variableKey], {
            id: v.variableKey,
            header: `${v.displayName} [${v.unit}]`,
            cell: info => {
              const val = info.getValue();
              const formatted = formatTableValue(val as number | string | boolean | null, v.variableKey);
              if (v.variableKey === "PassFail") {
                const cls =
                  formatted === "PASS" ? "status-pass" :
                  formatted === "FAIL" ? "status-fail" :
                  formatted === "WARN" ? "status-warn" : "";
                return <span className={cls}>{formatted}</span>;
              }
              return <span>{formatted}</span>;
            },
            meta: { groupKey: group.groupKey, groupLabel: group.displayName, groupColor: group.color },
          })
        );
      }
    }

    return cols;
  }, [visibleGroups, variables, visibleVariableKeys]);

  const table = useReactTable({
    data: rows,
    columns: columnDefs,
    getCoreRowModel: getCoreRowModel(),
  });

  // Group columns by their group for the header
  const headerGroups = useMemo(() => {
    const result: { groupKey: string; groupLabel: string; groupColor: string; colIds: string[] }[] = [];
    for (const col of columnDefs) {
      const meta = (col as { meta?: { groupKey: string; groupLabel: string; groupColor: string } }).meta;
      if (!meta) continue;
      const last = result[result.length - 1];
      if (last && last.groupKey === meta.groupKey) {
        last.colIds.push(col.id as string);
      } else {
        result.push({ groupKey: meta.groupKey, groupLabel: meta.groupLabel, groupColor: meta.groupColor, colIds: [col.id as string] });
      }
    }
    return result;
  }, [columnDefs]);

  // Scroll selected row into view
  const tableRef = useRef<HTMLTableElement>(null);
  useEffect(() => {
    if (selectedCase === null) return;
    const el = tableRef.current?.querySelector(`[data-case="${selectedCase}"]`);
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedCase]);

  const headerRow = table.getHeaderGroups()[0];

  return (
    <div className="table-wrapper">
      <table className="data-table" ref={tableRef}>
        <thead>
          {/* Group header row */}
          <tr>
            {headerGroups.map(g => (
              <th
                key={g.groupKey}
                className="th-group"
                colSpan={g.colIds.length}
                style={{
                  background: hexToRgba(g.groupColor, 0.18),
                  borderBottom: `2px solid ${hexToRgba(g.groupColor, 0.55)}`,
                }}
              >
                {g.groupKey === "_case" ? "" : g.groupLabel}
              </th>
            ))}
          </tr>
          {/* Variable header row */}
          <tr>
            {headerRow.headers.map((header, idx) => {
              const isCase = header.id === "Case";
              return (
                <th
                  key={header.id}
                  className={`th-var${isCase ? " th-case" : ""}`}
                  style={{ minWidth: isCase ? 60 : 90, left: isCase ? 0 : undefined }}
                  title={header.id}
                >
                  {idx === 0 ? "Case #" : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => {
            const caseVal = row.original["Case"];
            const isSelected = caseVal === selectedCase;
            return (
              <tr
                key={row.id}
                className={`tr-row${isSelected ? " tr-selected" : ""}`}
                data-case={caseVal}
                style={{ cursor: "pointer" }}
                onClick={e => {
                  if (typeof caseVal !== "number") return;
                  if (e.shiftKey) shiftSelectCase(caseVal);
                  else setSelectedCase(caseVal);
                }}
              >
                {row.getVisibleCells().map((cell, idx) => {
                  const isCase = cell.column.id === "Case";
                  const varDef = variables.find(v => v.variableKey === cell.column.id);
                  const isNumeric = !varDef || varDef.dataType === "number";
                  return (
                    <td
                      key={cell.id}
                      className={`${isCase ? "td-case" : ""}${isNumeric && !isCase ? " td-number" : ""}`}
                      style={{ left: isCase ? 0 : undefined }}
                    >
                      {idx === 0 ? formatTableValue(caseVal as number, "Case") : flexRender(cell.column.columnDef.cell, cell.getContext())}
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
