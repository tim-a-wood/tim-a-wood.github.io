import React, { useRef } from 'react';
import { Zap, Upload, Save, Settings, HelpCircle } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { parseWorkbookFile } from '../xlsx/parseWorkbook';
import { formatDisplayTime } from '../utils/format';
import { AppTooltip } from './AppTooltip';
import { ExportMenu } from './ExportMenu';
import { tooltipContent } from '../config/tooltipContent';

interface Props {
  onOpenSettings: () => void;
  onOpenHelp: () => void;
}

export function Header({ onOpenSettings, onOpenHelp }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const { workbookModel, setIsLoading, loadWorkbook, showError, saveLayout } = useAppStore();

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    setIsLoading(true);
    const result = await parseWorkbookFile(file);
    if (result.errors.length > 0) showError(result.errors.join(' '));
    else if (result.model) loadWorkbook(result.model);
    else setIsLoading(false);
  };

  const loadedAt = workbookModel.isSample ? null : new Date(workbookModel.loadedAtIso);

  return (
    <div className="header-inner">
      <div className="logo-group">
        <div className="logo-title">
          <Zap size={15} color="var(--blue)" />
          <span>SignalLite Analyzer</span>
        </div>
        <div className="logo-sub">Aircraft Performance · FAR25.121 / FAR25.367</div>
      </div>

      <div className="logo-divider" />

      <AppTooltip content={tooltipContent.importXlsx}>
        <button className="btn btn-primary" onClick={() => fileRef.current?.click()}>
          <Upload size={12} /> Import XLSX
        </button>
      </AppTooltip>
      <input ref={fileRef} type="file" accept=".xlsx" style={{ display: 'none' }} onChange={handleFile} />

      {!workbookModel.isSample && loadedAt && (
        <div className="file-indicator">
          <span className="file-indicator-name">{workbookModel.fileName}</span>
          <span className="file-indicator-status">Loaded · {formatDisplayTime(loadedAt)}</span>
        </div>
      )}

      <div className="header-spacer" />

      <AppTooltip content={tooltipContent.saveLayout}>
        <button className="btn btn-ghost" onClick={saveLayout}>
          <Save size={12} /> Save Layout
        </button>
      </AppTooltip>
      <ExportMenu />
      <AppTooltip content={tooltipContent.settings}>
        <button className="btn btn-icon" onClick={onOpenSettings}><Settings size={14} /></button>
      </AppTooltip>
      <AppTooltip content={tooltipContent.help}>
        <button className="btn btn-icon" onClick={onOpenHelp}><HelpCircle size={14} /></button>
      </AppTooltip>

      <div className="logo-divider" />

      <div className="stat-chips">
        <div className="stat-chip">
          <span className="stat-chip-label">Rows</span>
          <span className="stat-chip-value">{workbookModel.rows.length}</span>
        </div>
        <div className="stat-chip">
          <span className="stat-chip-label">Vars</span>
          <span className="stat-chip-value">{workbookModel.variables.length}</span>
        </div>
        <div className="stat-chip">
          <span className="stat-chip-label">Groups</span>
          <span className="stat-chip-value">{workbookModel.groups.length}</span>
        </div>
      </div>
    </div>
  );
}
