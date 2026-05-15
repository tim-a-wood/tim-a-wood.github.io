// MVP NOTE:
// This implementation uses npm xlsx@0.18.5 for local XLSX parsing.
// Before any formal, controlled, or safety-critical release, revisit the
// SheetJS packaging source, security posture, and licensing implications.

import * as XLSX from "xlsx";
import type { WorkbookModel, DataGroup, VariableDefinition, DataRow, DataValue } from "../types/appTypes";
import { defaultGroups } from "../config/defaultGroups";
import { defaultVariables } from "../config/defaultVariables";
import { workbookSheetNames } from "./workbookSchema";
import { validateFileType, validateDataSheet, validateGroupsSheet, validateVariablesSheet } from "./validateWorkbook";

export interface ParseResult {
  model: WorkbookModel | null;
  errors: string[];
}

export async function parseWorkbookFile(file: File): Promise<ParseResult> {
  const fileErr = validateFileType(file);
  if (fileErr) return { model: null, errors: [fileErr] };

  const buf = await file.arrayBuffer();
  let wb: XLSX.WorkBook;
  try {
    wb = XLSX.read(buf, { type: "array", cellDates: true });
  } catch {
    return { model: null, errors: ["Failed to parse XLSX file."] };
  }

  if (!wb.SheetNames.includes(workbookSheetNames.data)) {
    return { model: null, errors: ["Workbook must contain a Data sheet."] };
  }

  const dataSheet = wb.Sheets[workbookSheetNames.data];
  const rawRows = XLSX.utils.sheet_to_json<Record<string, unknown>>(dataSheet, { defval: null });
  const allHeaders: string[] = rawRows.length > 0 ? Object.keys(rawRows[0]) : (
    (XLSX.utils.sheet_to_json<string[]>(dataSheet, { header: 1 })[0] ?? []) as string[]
  );

  const dataErrors = validateDataSheet(allHeaders, rawRows);
  if (dataErrors.length > 0) return { model: null, errors: dataErrors };

  // Parse groups
  let groups: DataGroup[] = defaultGroups;
  if (wb.SheetNames.includes(workbookSheetNames.groups)) {
    const gs = XLSX.utils.sheet_to_json<Record<string, unknown>>(wb.Sheets[workbookSheetNames.groups], { defval: null });
    const gErrors = validateGroupsSheet(gs);
    if (gErrors.length > 0) return { model: null, errors: gErrors };
    groups = gs.map(r => ({
      groupKey: String(r["GroupKey"]),
      displayName: String(r["DisplayName"]),
      color: String(r["Color"]),
      sortOrder: Number(r["SortOrder"]),
      defaultVisible: String(r["DefaultVisible"]).toUpperCase() === "TRUE",
    }));
  }

  // Parse variables
  let variables: VariableDefinition[] = defaultVariables;
  if (wb.SheetNames.includes(workbookSheetNames.variables)) {
    const vs = XLSX.utils.sheet_to_json<Record<string, unknown>>(wb.Sheets[workbookSheetNames.variables], { defval: null });
    const vErrors = validateVariablesSheet(vs, groups.map(g => g.groupKey));
    if (vErrors.length > 0) return { model: null, errors: vErrors };
    variables = vs.map(r => ({
      variableKey: String(r["VariableKey"]),
      displayName: String(r["DisplayName"]),
      groupKey: String(r["GroupKey"]),
      unit: String(r["Unit"] ?? "-"),
      dataType: String(r["DataType"]) as "number"|"string"|"boolean"|"date",
      sortOrder: Number(r["SortOrder"]),
      defaultVisible: String(r["DefaultVisible"]).toUpperCase() === "TRUE",
      source: String(r["Source"]) as "file"|"derived",
    }));
  }

  const rows: DataRow[] = rawRows.map(raw => {
    const row: DataRow = {};
    for (const key of Object.keys(raw)) {
      const val = raw[key];
      const varDef = variables.find(v => v.variableKey === key);
      if (!varDef) { row[key] = val as DataValue; continue; }
      if (val === null || val === undefined) { row[key] = null; continue; }
      switch (varDef.dataType) {
        case "number": row[key] = typeof val === "number" ? val : parseFloat(String(val)); break;
        case "boolean": row[key] = val === true || String(val).toUpperCase() === "TRUE"; break;
        case "date": row[key] = val instanceof Date ? val : (typeof val === "string" ? new Date(val) : null); break;
        default: row[key] = String(val);
      }
    }
    return row;
  });

  return {
    model: {
      fileName: file.name,
      loadedAtIso: new Date().toISOString(),
      isSample: false,
      groups,
      variables,
      rows,
    },
    errors: [],
  };
}
