export function LoadingOverlay() {
  return (
    <div className="loading-overlay">
      <div className="spinner" />
      <div className="loading-text">Loading workbook...</div>
      <div className="loading-sub">Parsing XLSX data locally.</div>
    </div>
  );
}
