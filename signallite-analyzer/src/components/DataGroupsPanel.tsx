import { useAppStore } from '../store/useAppStore';
import { getSortedGroups } from '../model/selectors';
import { AppTooltip } from './AppTooltip';
import { tooltipContent } from '../config/tooltipContent';

export function DataGroupsPanel() {
  const workbookModel = useAppStore(s => s.workbookModel);
  const layoutState = useAppStore(s => s.layoutState);
  const toggleGroup = useAppStore(s => s.toggleGroup);

  const sorted = getSortedGroups(workbookModel.groups);

  const getCount = (groupKey: string) => {
    const isVis = layoutState.visibleGroupKeys.includes(groupKey);
    if (!isVis) return 0;
    return workbookModel.variables
      .filter(v => v.groupKey === groupKey && (v.variableKey === 'Case' || layoutState.visibleVariableKeys.includes(v.variableKey)))
      .length;
  };

  return (
    <div style={{ flexShrink: 0 }}>
      <div className="sidebar-section-header">
        DATA GROUPS
        <span className="sidebar-section-label">configurable</span>
      </div>
      <AppTooltip content={tooltipContent.dataGroups}>
        <div>
          {sorted.map((g, i) => {
            const isVisible = layoutState.visibleGroupKeys.includes(g.groupKey);
            return (
              <div key={g.groupKey} className="group-row" onClick={() => toggleGroup(g.groupKey)}>
                <input
                  type="checkbox"
                  checked={isVisible}
                  onChange={() => toggleGroup(g.groupKey)}
                  onClick={e => e.stopPropagation()}
                />
                <span className="group-index">{i + 1}</span>
                <span className="group-color-dot" style={{ background: g.color }} />
                <span className="group-name">{g.displayName}</span>
                <span className="group-count">{getCount(g.groupKey)}</span>
              </div>
            );
          })}
        </div>
      </AppTooltip>
    </div>
  );
}
