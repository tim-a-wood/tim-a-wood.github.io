import type { DataRow } from "../types/appTypes";

interface ErrorPair {
  actual: string;
  expected: string;
  absKey: string;
  relKey: string;
}

const ERROR_PAIRS: ErrorPair[] = [
  { actual: "VR_Act", expected: "VR_Exp", absKey: "VR_AbsErr", relKey: "VR_RelErr" },
  { actual: "V2_Act", expected: "V2_Exp", absKey: "V2_AbsErr", relKey: "V2_RelErr" },
  { actual: "TODist_Act", expected: "TODist_Exp", absKey: "TODist_AbsErr", relKey: "TODist_RelErr" },
];

function round2(x: number): number { return Math.round(x * 100) / 100; }
function round1(x: number): number { return Math.round(x * 10) / 10; }

export function computeErrors(rows: DataRow[]): DataRow[] {
  return rows.map(row => {
    const updated: DataRow = { ...row };
    for (const pair of ERROR_PAIRS) {
      const act = row[pair.actual];
      const exp = row[pair.expected];
      if (typeof act === "number" && typeof exp === "number") {
        const absErr = act - exp;
        updated[pair.absKey] = round1(absErr);
        if (exp === 0) {
          updated[pair.relKey] = null;
        } else {
          updated[pair.relKey] = round2(((act - exp) / exp) * 100);
        }
      } else {
        updated[pair.absKey] = null;
        updated[pair.relKey] = null;
      }
    }
    return updated;
  });
}
