export interface ParsedSheets {
  dataRows: Record<string, unknown>[];
  dataHeaders: string[];
  groups: Record<string, unknown>[] | null;
  variables: Record<string, unknown>[] | null;
}

export function validateFile(file: File): string | null {
  return validateFileType(file);
}

export function validateSheets(sheets: ParsedSheets): string[] {
  const errors: string[] = [];
  if (!sheets.dataHeaders.includes("Case")) {
    errors.push("Data sheet must contain a Case column.");
    return errors;
  }
  const caseVals = sheets.dataRows.map(r => r["Case"]);
  for (const v of caseVals) {
    if (typeof v !== "number" || !isFinite(v)) {
      errors.push("Case values must be finite numbers.");
      break;
    }
  }
  const seen = new Set<unknown>();
  for (const v of caseVals) {
    if (seen.has(v)) {
      errors.push("Duplicate Case values detected.");
      break;
    }
    seen.add(v);
  }
  return errors;
}

export function validateFileType(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".xlsx")) return "Only XLSX files are supported in this MVP.";
  if (file.size > 20 * 1024 * 1024) return "XLSX file exceeds the 20 MB MVP limit.";
  return null;
}

export function validateDataSheet(headers: string[], rows: Record<string, unknown>[]): string[] {
  const errors: string[] = [];
  if (!headers.includes("Case")) { errors.push("Data sheet must contain a Case column."); return errors; }
  if (rows.length === 0) { errors.push("Data sheet contains no data rows."); return errors; }
  const caseVals = rows.map(r => r["Case"]);
  for (const v of caseVals) {
    if (typeof v !== "number" || isNaN(v as number)) { errors.push("Case values must be numeric."); break; }
  }
  for (const v of caseVals) {
    if (typeof v === "number" && !isFinite(v)) { errors.push("Case values must be finite numbers."); break; }
  }
  const seen = new Set<unknown>();
  for (const v of caseVals) {
    if (seen.has(v)) { errors.push("Case values must be unique."); break; }
    seen.add(v);
  }
  return errors;
}

export function validateGroupsSheet(rows: Record<string, unknown>[]): string[] {
  const errors: string[] = [];
  for (const row of rows) {
    if (!row["GroupKey"] || String(row["GroupKey"]).trim() === "") errors.push("GroupKey must be non-empty.");
    if (!row["DisplayName"] || String(row["DisplayName"]).trim() === "") errors.push("Group DisplayName must be non-empty.");
    if (!/^#[0-9A-Fa-f]{6}$/.test(String(row["Color"] ?? ""))) errors.push("Group color must be a valid hex color.");
    if (isNaN(Number(row["SortOrder"]))) errors.push("Group SortOrder must be numeric.");
  }
  return errors;
}

export function validateVariablesSheet(rows: Record<string, unknown>[], knownGroupKeys: string[]): string[] {
  const errors: string[] = [];
  const allowedDT = ["number","string","boolean","date"];
  const allowedSrc = ["file","derived"];
  const keys = new Set<string>();
  for (const row of rows) {
    const k = String(row["VariableKey"] ?? "").trim();
    if (!k) { errors.push("VariableKey must be non-empty."); continue; }
    if (keys.has(k)) { errors.push("Duplicate variable keys detected."); } else { keys.add(k); }
    if (!row["DisplayName"] || String(row["DisplayName"]).trim() === "") errors.push("Variable DisplayName must be non-empty.");
    const gk = String(row["GroupKey"] ?? "").trim();
    if (!knownGroupKeys.includes(gk)) errors.push(`Variable references an unknown group key: ${gk}.`);
    if (!allowedDT.includes(String(row["DataType"] ?? ""))) errors.push("Variable data type must be number, string, boolean, or date.");
    if (!allowedSrc.includes(String(row["Source"] ?? ""))) errors.push("Variable source must be file or derived.");
  }
  return errors;
}
