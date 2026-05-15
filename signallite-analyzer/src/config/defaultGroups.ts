import type { DataGroup } from "../types/appTypes";
export const defaultGroups: DataGroup[] = [
  { groupKey: "test_inputs", displayName: "Test Inputs", color: "#2f8cff", sortOrder: 10, defaultVisible: true },
  { groupKey: "expected_outputs", displayName: "Expected Outputs", color: "#39b54a", sortOrder: 20, defaultVisible: true },
  { groupKey: "actual_outputs", displayName: "Actual Outputs", color: "#9b5de5", sortOrder: 30, defaultVisible: true },
  { groupKey: "tolerances", displayName: "Tolerances", color: "#d6a600", sortOrder: 40, defaultVisible: true },
  { groupKey: "absolute_error", displayName: "Absolute Error", color: "#ff7a00", sortOrder: 50, defaultVisible: true },
  { groupKey: "relative_error", displayName: "Relative Error", color: "#00b8c8", sortOrder: 60, defaultVisible: true },
  { groupKey: "inputs", displayName: "Inputs", color: "#4169e1", sortOrder: 70, defaultVisible: true },
  { groupKey: "logged_data", displayName: "Logged Data", color: "#c43ac4", sortOrder: 80, defaultVisible: true },
];
