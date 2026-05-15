import type { DataGroup, DataRow, VariableDefinition } from "../types/appTypes";

export function getSortedGroups(groups: DataGroup[]): DataGroup[] {
  return [...groups].sort((a, b) => a.sortOrder - b.sortOrder);
}

export function getVisibleGroups(groups: DataGroup[], visibleGroupKeys: string[]): DataGroup[] {
  return getSortedGroups(groups).filter(g => visibleGroupKeys.includes(g.groupKey));
}

export function getVariablesForGroup(variables: VariableDefinition[], groupKey: string): VariableDefinition[] {
  return [...variables].filter(v => v.groupKey === groupKey).sort((a, b) => a.sortOrder - b.sortOrder);
}

export function getVisibleVariablesForGroup(variables: VariableDefinition[], groupKey: string, visibleVariableKeys: string[]): VariableDefinition[] {
  return getVariablesForGroup(variables, groupKey).filter(v => v.variableKey === "Case" || visibleVariableKeys.includes(v.variableKey));
}

export function getAllCases(rows: DataRow[]): number[] {
  return [...rows].map(r => r["Case"] as number).filter(c => typeof c === "number" && isFinite(c)).sort((a, b) => a - b);
}

export function getRowByCase(rows: DataRow[], caseNum: number): DataRow | undefined {
  return rows.find(r => r["Case"] === caseNum);
}
