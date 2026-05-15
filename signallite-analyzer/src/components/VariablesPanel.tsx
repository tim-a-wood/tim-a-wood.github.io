import React, { useState, useMemo } from "react";
import { useAppStore } from "../store/useAppStore";
import { getSortedGroups } from "../model/selectors";
import { AppTooltip } from "./AppTooltip";
import { tooltipContent } from "../config/tooltipContent";
import { Button } from "./Button";

export function VariablesPanel() {
  const workbookModel = useAppStore(s => s.workbookModel);
  const layoutState = useAppStore(s => s.layoutState);
  const toggleVariable = useAppStore(s => s.toggleVariable);
  const setCollapsedGroup = useAppStore(s => s.setCollapsedGroup);

  const [search, setSearch] = useState("");

  const { groups, variables } = workbookModel;
  const { visibleGroupKeys, visibleVariableKeys, collapsedGroupKeys } = layoutState;
  const sortedGroups = getSortedGroups(groups).filter(g => visibleGroupKeys.includes(g.groupKey));

  const searchLower = search.toLowerCase().trim();

  const groupedVariables = useMemo(() => {
    return sortedGroups.map(group => {
      const vars = variables
        .filter(v => v.groupKey === group.groupKey)
        .sort((a, b) => a.sortOrder - b.sortOrder);
      const filtered = searchLower
        ? vars.filter(v =>
            v.displayName.toLowerCase().includes(searchLower) ||
            v.variableKey.toLowerCase().includes(searchLower) ||
            v.unit.toLowerCase().includes(searchLower) ||
            group.displayName.toLowerCase().includes(searchLower)
          )
        : vars;
      return { group, vars: filtered, hasMatch: filtered.length > 0 };
    }).filter(g => g.hasMatch || !searchLower);
  }, [sortedGroups, variables, searchLower]);

  const handleSelectAll = () => {
    const allVarKeys = variables
      .filter(v => visibleGroupKeys.includes(v.groupKey) && v.variableKey !== "Case")
      .map(v => v.variableKey);
    const current = new Set(visibleVariableKeys);
    for (const k of allVarKeys) current.add(k);
    // Directly update store
    allVarKeys.forEach(k => {
      if (!visibleVariableKeys.includes(k)) toggleVariable(k);
    });
  };

  const handleClearAll = () => {
    // Remove all from visibleVariableKeys (not Case)
    [...visibleVariableKeys].forEach(k => {
      if (k !== "Case") toggleVariable(k);
    });
  };

  const totalVisible = visibleVariableKeys.filter(k => k !== "Case").length;
  const totalAvailable = variables.filter(v => visibleGroupKeys.includes(v.groupKey) && v.variableKey !== "Case").length;

  return (
    <div className="sidebar-section" style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <div className="sidebar-section-header">
        <span className="sidebar-section-title">Variables</span>
      </div>
      <div className="search-input-wrapper">
        <AppTooltip content={tooltipContent.variablesSearch}>
          <input
            type="text"
            className="search-input"
            placeholder="Search variables..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search variables"
          />
        </AppTooltip>
      </div>
      <div className="sidebar-scroll">
        {groupedVariables.map(({ group, vars }) => {
          const isCollapsed = collapsedGroupKeys.includes(group.groupKey) && !searchLower;
          return (
            <div key={group.groupKey}>
              <div
                className="variable-group-header"
                onClick={() => setCollapsedGroup(group.groupKey, !isCollapsed)}
                role="button"
                tabIndex={0}
                onKeyDown={e => { if (e.key === "Enter" || e.key === " ") setCollapsedGroup(group.groupKey, !isCollapsed); }}
                aria-expanded={!isCollapsed}
              >
                <span className={`variable-group-chevron${isCollapsed ? " collapsed" : ""}`}>▾</span>
                <span className="group-color-dot" style={{ background: group.color }} />
                <span className="variable-group-title" style={{ color: group.color }}>{group.displayName}</span>
              </div>
              {!isCollapsed && vars.map(v => {
                const isCase = v.variableKey === "Case";
                const isChecked = isCase || visibleVariableKeys.includes(v.variableKey);
                return (
                  <AppTooltip key={v.variableKey} content={isCase ? tooltipContent.caseAlwaysVisible : ""}>
                    <div
                      className={`variable-row${isCase ? " disabled" : ""}`}
                      onClick={() => { if (!isCase) toggleVariable(v.variableKey); }}
                      role="checkbox"
                      aria-checked={isChecked}
                      tabIndex={isCase ? -1 : 0}
                      onKeyDown={e => { if ((e.key === "Enter" || e.key === " ") && !isCase) toggleVariable(v.variableKey); }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        disabled={isCase}
                        onChange={() => { if (!isCase) toggleVariable(v.variableKey); }}
                        onClick={e => e.stopPropagation()}
                        aria-label={v.displayName}
                      />
                      <span className="variable-row-name">{v.displayName}</span>
                      <span className="variable-row-unit">{v.unit}</span>
                    </div>
                  </AppTooltip>
                );
              })}
            </div>
          );
        })}
      </div>
      <div className="variables-footer">
        <span className="variables-footer-count">{totalVisible} of {totalAvailable} selected</span>
        <div style={{ display: "flex", gap: 4 }}>
          <AppTooltip content={tooltipContent.selectAllVariables}>
            <Button variant="ghost" size="sm" onClick={handleSelectAll}>All</Button>
          </AppTooltip>
          <AppTooltip content={tooltipContent.clearAllVariables}>
            <Button variant="ghost" size="sm" onClick={handleClearAll}>Clear</Button>
          </AppTooltip>
        </div>
      </div>
    </div>
  );
}
