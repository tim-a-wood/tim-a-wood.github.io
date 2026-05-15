import type { DataGroup, VariableDefinition } from "../types/appTypes";
import { allowedDataTypes, allowedVariableSources, maxXlsxFileSizeBytes } from "./workbookSchema";

export interface ParsedSheets {
  dataRows: Record<string, unknown>[];
  dataHeaders: string[];
  groups: DataGroup[] | null;
  variables: VariableDefinition[] | null;
}

export function validateFile(file: File): string | null {
  if (!file.name.endsWith(".xlsx")) return "Only XLSX files are supported in this MVP.";
  if (file.size > maxXlsxFileSizeBytes) return "XLSX file exceeds the 20 MB MVP limit.";
  return null;
}

export function validateSheets(sheets: ParsedSheets): string[] {
  const errors: string[] = [];

  if (!sheets.dataHeaders.includes("Case")) {
    errors.push("Data sheet is missing required 'Case' column.");
  }

  if (sheets.dataRows.length === 0) {
    errors.push("Data sheet contains no data rows.");
  }

  const caseSet = new Set<number>();
  sheets.dataRows.forEach((row, idx) => {
    const raw = row["Case"];
    if (raw === undefined || raw === null || raw === "") {
      errors.push(`Row ${idx + 2}: Case value is missing.`);
      return;
    }
    const n = Number(raw);
    if (!isFinite(n) || isNaN(n)) {
      errors.push(`Row ${idx + 2}: Case value '${raw}' is not a finite number.`);
      return;
    }
    if (caseSet.has(n)) {
      errors.push(`Duplicate Case value: ${n}.`);
    } else {
      caseSet.add(n);
    }
  });

  if (sheets.groups !== null) {
    sheets.groups.forEach((g, idx) => {
      if (!g.groupKey || typeof g.groupKey !== "string") {
        errors.push(`Groups row ${idx + 2}: GroupKey is missing or invalid.`);
      }
      if (!g.displayName || typeof g.displayName !== "string") {
        errors.push(`Groups row ${idx + 2}: DisplayName is missing or invalid.`);
      }
      if (typeof g.sortOrder !== "number" || !isFinite(g.sortOrder)) {
        errors.push(`Groups row ${idx + 2}: SortOrder is not a valid number.`);
      }
    });
  }

  if (sheets.variables !== null) {
    sheets.variables.forEach((v, idx) => {
      if (!v.variableKey || typeof v.variableKey !== "string") {
        errors.push(`Variables row ${idx + 2}: VariableKey is missing or invalid.`);
      }
      if (!(allowedDataTypes as readonly string[]).includes(v.dataType)) {
        errors.push(`Variables row ${idx + 2}: DataType '${v.dataType}' is not allowed.`);
      }
      if (!(allowedVariableSources as readonly string[]).includes(v.source)) {
        errors.push(`Variables row ${idx + 2}: Source '${v.source}' is not allowed.`);
      }
    });
  }

  return errors;
}
