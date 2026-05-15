import { describe, it, expect } from "vitest";
import { normalizeRows } from "../model/normalizeData";
import type { VariableDefinition } from "../types/appTypes";

const vars: VariableDefinition[] = [
  { variableKey: "Case", displayName: "Case #", groupKey: "test_inputs", unit: "-", dataType: "number", sortOrder: 0, defaultVisible: true, source: "file" },
  { variableKey: "GrossWeight", displayName: "Gross Weight", groupKey: "test_inputs", unit: "lb", dataType: "number", sortOrder: 10, defaultVisible: true, source: "file" },
  { variableKey: "FlapsSetting", displayName: "Flaps Setting", groupKey: "inputs", unit: "-", dataType: "string", sortOrder: 10, defaultVisible: true, source: "file" },
];

describe("normalizeRows", () => {
  it("casts number strings to numbers", () => {
    const raw = [{ Case: "24", GrossWeight: "71500" }];
    const result = normalizeRows(raw, vars);
    expect(result[0]["Case"]).toBe(24);
    expect(result[0]["GrossWeight"]).toBe(71500);
  });

  it("leaves string values as strings", () => {
    const raw = [{ Case: "1", FlapsSetting: "15" }];
    const result = normalizeRows(raw, vars);
    expect(result[0]["FlapsSetting"]).toBe("15");
  });

  it("returns null for empty values", () => {
    const raw = [{ Case: "", GrossWeight: null }];
    const result = normalizeRows(raw, vars);
    expect(result[0]["Case"]).toBeNull();
    expect(result[0]["GrossWeight"]).toBeNull();
  });

  it("returns null for non-finite numbers", () => {
    const raw = [{ Case: "abc", GrossWeight: "Infinity" }];
    const result = normalizeRows(raw, vars);
    expect(result[0]["Case"]).toBeNull();
  });
});
