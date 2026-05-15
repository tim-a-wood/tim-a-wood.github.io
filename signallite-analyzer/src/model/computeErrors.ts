import type { DataRow } from "../types/appTypes";

const ERROR_PAIRS = [
  { actual: "VR_Act", expected: "VR_Exp", absKey: "VR_AbsErr", relKey: "VR_RelErr" },
  { actual: "V2_Act", expected: "V2_Exp", absKey: "V2_AbsErr", relKey: "V2_RelErr" },
  { actual: "TODist_Act", expected: "TODist_Exp", absKey: "TODist_AbsErr", relKey: "TODist_RelErr" },
] as const;

function round2(x: number): number { return Math.round(x * 100) / 100; }
function round1(x: number): number { return Math.round(x * 10) / 10; }

export function computeErrors(rows: DataRow[]): DataRow[] {
  return rows.map(row => {
    const updated: DataRow = { ...row };
    for (const pair of ERROR_PAIRS) {
      const act = row[pair.actual];
      const exp = row[pair.expected];
      if (typeof act === "number" && typeof exp === "number") {
        updated[pair.absKey] = round1(act - exp);
        updated[pair.relKey] = exp === 0 ? null : round2(((act - exp) / exp) * 100);
      } else {
        updated[pair.absKey] = null;
        updated[pair.relKey] = null;
      }
    }
    // Default tolerances
    if (!("VR_Tol" in updated)) updated["VR_Tol"] = 10;
    if (!("V2_Tol" in updated)) updated["V2_Tol"] = 10;
    if (!("TODist_Tol" in updated)) updated["TODist_Tol"] = 650;
    return updated;
  });
}

// Alias used in tests
export const computeDerivedErrors = computeErrors;
