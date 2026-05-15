import { describe, it, expect } from "vitest";
import { getSortedGroups, getVisibleGroups, getVisibleVariablesForGroup, getAllCases, getRowByCase } from "../model/selectors";
import type { DataGroup, VariableDefinition, DataRow } from "../types/appTypes";

const groups: DataGroup[] = [
  { groupKey: "test_inputs", displayName: "Test Inputs", color: "#2f8cff", sortOrder: 10, defaultVisible: true },
  { groupKey: "expected_outputs", displayName: "Expected Outputs", color: "#39b54a", sortOrder: 20, defaultVisible: true },
  { groupKey: "inputs", displayName: "Inputs", color: "#4169e1", sortOrder: 70, defaultVisible: true },
];

const variables: VariableDefinition[] = [
  { variableKey: "Case", displayName: "Case #", groupKey: "test_inputs", unit: "-", dataType: "number", sortOrder: 0, defaultVisible: true, source: "file" },
  { variableKey: "GrossWeight", displayName: "Gross Weight", groupKey: "test_inputs", unit: "lb", dataType: "number", sortOrder: 10, defaultVisible: true, source: "file" },
  { variableKey: "VR_Exp", displayName: "VR Exp", groupKey: "expected_outputs", unit: "kt", dataType: "number", sortOrder: 10, defaultVisible: true, source: "file" },
  { variableKey: "FlapsSetting", displayName: "Flaps Setting", groupKey: "inputs", unit: "-", dataType: "string", sortOrder: 10, defaultVisible: true, source: "file" },
];

describe("getSortedGroups", () => {
  it("sorts by sortOrder ascending", () => {
    const sorted = getSortedGroups(groups);
    expect(sorted[0].groupKey).toBe("test_inputs");
    expect(sorted[2].groupKey).toBe("inputs");
  });
});

describe("getVisibleGroups", () => {
  it("returns only visible groups", () => {
    const visible = getVisibleGroups(groups, ["test_inputs", "inputs"]);
    expect(visible.map(g => g.groupKey)).toContain("test_inputs");
    expect(visible.map(g => g.groupKey)).toContain("inputs");
    expect(visible.map(g => g.groupKey)).not.toContain("expected_outputs");
  });
});

describe("getVisibleVariablesForGroup", () => {
  it("always includes Case when groupKey is test_inputs", () => {
    const vars = getVisibleVariablesForGroup(variables, "test_inputs", ["GrossWeight"]);
    const keys = vars.map(v => v.variableKey);
    expect(keys).toContain("Case");
    expect(keys).toContain("GrossWeight");
  });

  it("does not include Case for other groups", () => {
    const vars = getVisibleVariablesForGroup(variables, "expected_outputs", ["VR_Exp"]);
    const keys = vars.map(v => v.variableKey);
    expect(keys).not.toContain("Case");
    expect(keys).toContain("VR_Exp");
  });

  it("returns empty when no variables are visible", () => {
    const vars = getVisibleVariablesForGroup(variables, "expected_outputs", []);
    expect(vars).toHaveLength(0);
  });
});

describe("getAllCases", () => {
  it("returns sorted numeric case values", () => {
    const rows: DataRow[] = [{ Case: 3 }, { Case: 1 }, { Case: 2 }];
    expect(getAllCases(rows)).toEqual([1, 2, 3]);
  });
});

describe("getRowByCase", () => {
  it("returns the correct row", () => {
    const rows: DataRow[] = [{ Case: 24, GrossWeight: 71500 }, { Case: 25, GrossWeight: 68000 }];
    const row = getRowByCase(rows, 24);
    expect(row?.["GrossWeight"]).toBe(71500);
  });

  it("returns undefined for missing case", () => {
    const rows: DataRow[] = [{ Case: 1 }];
    expect(getRowByCase(rows, 999)).toBeUndefined();
  });
});
