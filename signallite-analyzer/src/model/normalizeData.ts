import type { DataRow, VariableDefinition } from "../types/appTypes";
export function normalizeRows(rawRows: DataRow[], variables: VariableDefinition[]): DataRow[] {
  return rawRows.map(raw => {
    const row: DataRow = {};
    for (const [k, v] of Object.entries(raw)) {
      const def = variables.find(vd => vd.variableKey === k);
      if (!def || v === null || v === undefined) { row[k] = v ?? null; continue; }
      switch (def.dataType) {
        case "number": row[k] = typeof v === "number" ? v : parseFloat(String(v)); break;
        case "boolean": row[k] = v === true || String(v).toUpperCase() === "TRUE"; break;
        case "date": row[k] = v instanceof Date ? v : (typeof v === "string" ? new Date(v) : null); break;
        default: row[k] = String(v);
      }
    }
    return row;
  });
}
