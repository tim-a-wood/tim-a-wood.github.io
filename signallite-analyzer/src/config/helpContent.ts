export const helpSections = [
  { title: "Workbook Format", body: "Load an XLSX workbook using the Import XLSX button. The workbook must contain a Data sheet with a Case column. Optional Groups and Variables sheets can configure the tool. If those sheets are missing, SignalLite uses the built-in aircraft performance template." },
  { title: "Data Groups", body: "Groups organize variables into configurable sections such as Test Inputs, Expected Outputs, Actual Outputs, Tolerances, Absolute Error, Relative Error, Inputs, and Logged Data. Use the Data Groups panel to show or hide entire groups." },
  { title: "Variable Selection", body: "Variables are sorted under their configured groups. Use checkboxes to show or hide variables in the table. The Case # variable remains available as the primary x-axis reference and cannot be hidden." },
  { title: "Plot Navigation", body: "Use horizontal zoom controls, the overview brush, or mouse wheel to zoom on the Case # axis. Use Focus Case # to center the plots around a specific case. Prev and Next move the cursor case one step at a time." },
  { title: "Cursors and Tooltips", body: "The plot cursor shows a vertical case marker and horizontal value marker. Tooltips show the selected case and precise signal values. Cursor values are also shown in the bottom status bar." },
  { title: "Exporting", body: "Export Visible Table as XLSX saves the current table columns. Export Plot Image as PNG saves the stacked plots. Export Layout as JSON saves the current layout and plot configuration without exporting workbook data." },
];
