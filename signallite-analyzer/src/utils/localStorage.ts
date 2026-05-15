const KEY = "signallite.layout.v1";
export function saveLayout(data: unknown): void { try { localStorage.setItem(KEY, JSON.stringify(data)); } catch {} }
export function loadLayoutData(): unknown { try { const s = localStorage.getItem(KEY); return s ? JSON.parse(s) : null; } catch { return null; } }
export function clearLayout(): void { try { localStorage.removeItem(KEY); } catch {} }
