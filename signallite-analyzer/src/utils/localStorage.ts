const STORAGE_KEY = "signallite.layout.v1";
export function saveLayout(data: unknown): void { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch {} }
export function loadLayout(): unknown { try { const s = localStorage.getItem(STORAGE_KEY); return s ? JSON.parse(s) : null; } catch { return null; } }
export function clearLayout(): void { try { localStorage.removeItem(STORAGE_KEY); } catch {} }
