import type { WorkbookModel, DataRow } from "../types/appTypes";
import { defaultGroups } from "../config/defaultGroups";
import { defaultVariables } from "../config/defaultVariables";

function round1(x: number): number { return Math.round(x * 10) / 10; }
function round2(x: number): number { return Math.round(x * 100) / 100; }
function roundInt(x: number): number { return Math.round(x); }
function roundToNearest(x: number, nearest: number): number { return Math.round(x / nearest) * nearest; }
function relativeError(actual: number, expected: number): number {
  if (expected === 0) return 0;
  return ((actual - expected) / expected) * 100;
}

function generateRow(c: number): DataRow {
  const GrossWeight = roundToNearest(68450 + 185 * (c - 20) + 420 * Math.sin(c / 5), 50);
  const PressureAltitude = Math.floor((c - 1) / 4) * 500;
  const OAT = round1(16.0 + 0.85 * Math.sin(c / 3) + 0.35 * Math.cos(c / 7));
  const VR_Exp = round1(126.3 + 0.205 * (c - 20) + 0.0007 * (GrossWeight - 68450) + 0.00018 * PressureAltitude - 0.025 * (OAT - 16));
  const V2_Exp = round1(VR_Exp + 10.4 + 0.35 * Math.sin(c / 6));
  const TODist_Exp = roundInt(1620 + 18.6 * (c - 20) + 0.084 * (GrossWeight - 68450) + 0.115 * PressureAltitude + 5.2 * (OAT - 16));
  const VR_Act = round1(VR_Exp + 0.55 * Math.sin(c / 2.8) - 0.15);
  const V2_Act = round1(V2_Exp + 0.5 * Math.cos(c / 3.2) + 0.1);
  const TODist_Act = roundInt(TODist_Exp + 24 * Math.sin(c / 4) + 9 * Math.cos(c / 2.7));
  const VR_Tol = 10, V2_Tol = 10, TODist_Tol = 650;
  const VR_AbsErr = round1(VR_Act - VR_Exp);
  const V2_AbsErr = round1(V2_Act - V2_Exp);
  const TODist_AbsErr = roundInt(TODist_Act - TODist_Exp);
  const VR_RelErr = round2(relativeError(VR_Act, VR_Exp));
  const V2_RelErr = round2(relativeError(V2_Act, V2_Exp));
  const TODist_RelErr = round2(relativeError(TODist_Act, TODist_Exp));
  const FlapsSetting = c < 24 ? "5" : c < 40 ? "15" : "30";
  const RunwayCondition = c < 25 ? "Dry" : c < 70 ? "Wet" : "Dry";
  const AntiIce = c % 9 === 0 ? "On" : "Off";
  const Notes = "-";
  const PassFail = Math.abs(VR_AbsErr) > VR_Tol || Math.abs(V2_AbsErr) > V2_Tol || Math.abs(TODist_AbsErr) > TODist_Tol
    ? "FAIL" : c % 37 === 0 ? "WARN" : "PASS";
  return { Case: c, GrossWeight, PressureAltitude, OAT, VR_Exp, V2_Exp, TODist_Exp, VR_Act, V2_Act, TODist_Act, VR_Tol, V2_Tol, TODist_Tol, VR_AbsErr, V2_AbsErr, TODist_AbsErr, VR_RelErr, V2_RelErr, TODist_RelErr, FlapsSetting, RunwayCondition, AntiIce, Notes, PassFail };
}

const rows: DataRow[] = [];
for (let c = 1; c <= 120; c++) rows.push(generateRow(c));
const idx24 = rows.findIndex(r => r["Case"] === 24);
rows[idx24] = { Case: 24, GrossWeight: 71500, PressureAltitude: 3000, OAT: 16.9, VR_Exp: 132.8, V2_Exp: 143.2, TODist_Exp: 2038, VR_Act: 132.4, V2_Act: 143.5, TODist_Act: 2061, VR_Tol: 10, V2_Tol: 10, TODist_Tol: 650, VR_AbsErr: -0.4, V2_AbsErr: 0.3, TODist_AbsErr: 23, VR_RelErr: -0.30, V2_RelErr: 0.21, TODist_RelErr: 1.13, FlapsSetting: "15", RunwayCondition: "Dry", AntiIce: "Off", Notes: "-", PassFail: "PASS" };

export const sampleWorkbookModel: WorkbookModel = {
  fileName: "sample",
  loadedAtIso: new Date().toISOString(),
  isSample: true,
  groups: defaultGroups,
  variables: defaultVariables,
  rows,
};
