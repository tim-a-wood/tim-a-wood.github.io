import { describe, it, expect } from "vitest";
import { computeErrors } from "../model/computeErrors";
import type { DataRow } from "../types/appTypes";

describe("computeErrors", () => {
  it("computes AbsErr as Act minus Exp", () => {
    const rows: DataRow[] = [
      { Case: 1, VR_Act: 133.0, VR_Exp: 132.0, V2_Act: 144.0, V2_Exp: 143.0, TODist_Act: 2100, TODist_Exp: 2000 },
    ];
    const result = computeErrors(rows);
    expect(result[0]["VR_AbsErr"]).toBeCloseTo(1.0, 1);
    expect(result[0]["V2_AbsErr"]).toBeCloseTo(1.0, 1);
    expect(result[0]["TODist_AbsErr"]).toBe(100);
  });

  it("computes RelErr as 100*(Act-Exp)/Exp", () => {
    const rows: DataRow[] = [
      { Case: 1, VR_Act: 132.4, VR_Exp: 132.8, V2_Act: 143.5, V2_Exp: 143.2, TODist_Act: 2061, TODist_Exp: 2038 },
    ];
    const result = computeErrors(rows);
    expect(result[0]["VR_RelErr"]).toBeCloseTo(-0.30, 1);
    expect(result[0]["V2_RelErr"]).toBeCloseTo(0.21, 1);
  });

  it("sets RelErr to null when Exp is zero", () => {
    const rows: DataRow[] = [
      { Case: 1, VR_Act: 5.0, VR_Exp: 0, V2_Act: 0, V2_Exp: 0, TODist_Act: 0, TODist_Exp: 0 },
    ];
    const result = computeErrors(rows);
    expect(result[0]["VR_RelErr"]).toBeNull();
    expect(result[0]["V2_RelErr"]).toBeNull();
    expect(result[0]["TODist_RelErr"]).toBeNull();
  });

  it("sets AbsErr and RelErr to null when actual or expected is missing", () => {
    const rows: DataRow[] = [
      { Case: 1, VR_Act: null, VR_Exp: 132.0, V2_Act: null, V2_Exp: null, TODist_Act: null, TODist_Exp: null },
    ];
    const result = computeErrors(rows);
    expect(result[0]["VR_AbsErr"]).toBeNull();
    expect(result[0]["VR_RelErr"]).toBeNull();
  });
});
