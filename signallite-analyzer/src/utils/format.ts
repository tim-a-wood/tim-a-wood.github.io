const intFmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const oneDec = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const twoDec = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const threeDec = new Intl.NumberFormat("en-US", { minimumFractionDigits: 3, maximumFractionDigits: 3 });

const speedKeys = ["VR_Act","VR_Exp","V2_Act","V2_Exp","OAT"];
const intKeys = ["GrossWeight","PressureAltitude","TODist_Act","TODist_Exp","TODist_AbsErr"];
const absSpeedErrKeys = ["VR_AbsErr","V2_AbsErr"];
const relErrKeys = ["VR_RelErr","V2_RelErr","TODist_RelErr"];
const tolKeys = ["VR_Tol","V2_Tol","TODist_Tol"];

export function formatTableValue(value: unknown, variableKey: string): string {
  if (value === null || value === undefined) return "";
  if (variableKey === "Case") return String(Math.round(Number(value)));
  if (tolKeys.includes(variableKey)) return `±${intFmt.format(Number(value))}`;
  if (variableKey === "PassFail" || typeof value === "string") return String(value);
  if (value instanceof Date) return formatDate(value);
  if (typeof value === "boolean") return value ? "TRUE" : "FALSE";
  const n = Number(value);
  if (speedKeys.includes(variableKey)) return oneDec.format(n);
  if (intKeys.includes(variableKey)) return intFmt.format(n);
  if (absSpeedErrKeys.includes(variableKey)) return oneDec.format(n);
  if (relErrKeys.includes(variableKey)) return twoDec.format(n);
  return String(value);
}

export function formatTooltipValue(value: unknown, variableKey: string): string {
  if (value === null || value === undefined) return "-";
  if (variableKey === "Case") return String(Math.round(Number(value)));
  if (tolKeys.includes(variableKey)) return `±${intFmt.format(Number(value))}`;
  if (typeof value === "string") return value;
  if (value instanceof Date) return formatDate(value);
  if (typeof value === "boolean") return value ? "TRUE" : "FALSE";
  const n = Number(value);
  if (speedKeys.includes(variableKey)) return threeDec.format(n);
  if (intKeys.includes(variableKey)) return intFmt.format(n);
  if (absSpeedErrKeys.includes(variableKey)) return threeDec.format(n);
  if (relErrKeys.includes(variableKey)) return threeDec.format(n);
  return String(value);
}

function pad(n: number, digits = 2): string { return String(n).padStart(digits, "0"); }

function formatDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function formatTimestamp(d: Date): string {
  return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

export function formatDisplayTime(d: Date): string {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
