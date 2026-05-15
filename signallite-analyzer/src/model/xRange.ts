export function nearestCase(requestedCase: number, availableCases: number[]): number {
  const sorted = [...availableCases].sort((a, b) => a - b);
  if (sorted.length === 0) return requestedCase;
  let best = sorted[0];
  let bestDistance = Math.abs(requestedCase - best);
  for (const candidate of sorted) {
    const d = Math.abs(requestedCase - candidate);
    if (d < bestDistance || (d === bestDistance && candidate < best)) {
      best = candidate;
      bestDistance = d;
    }
  }
  return best;
}

export function computeWindowSpanFromSlider(sliderValue: number, fullWindow: number): number {
  const minWindow = Math.min(10, fullWindow);
  return fullWindow - (sliderValue / 100) * (fullWindow - minWindow);
}

export function computeZoomSliderValue(span: number, fullWindow: number): number {
  const minWindow = Math.min(10, fullWindow);
  if (fullWindow <= minWindow) return 100;
  return Math.round(Math.max(0, Math.min(100, ((fullWindow - span) / (fullWindow - minWindow)) * 100)));
}

export function clampXRange(center: number, span: number, minC: number, maxC: number): [number, number] {
  let lo = center - span / 2, hi = center + span / 2;
  if (lo < minC) { hi += minC - lo; lo = minC; }
  if (hi > maxC) { lo -= hi - maxC; hi = maxC; }
  return [Math.max(minC, lo), Math.min(maxC, hi)];
}
