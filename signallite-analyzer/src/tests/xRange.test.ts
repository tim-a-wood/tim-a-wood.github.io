import { describe, it, expect } from "vitest";
import { nearestCase, computeZoomSliderValue, computeWindowSpanFromSlider } from "../model/xRange";

describe("nearestCase", () => {
  it("returns 24 when equidistant between 24 and 25", () => {
    expect(nearestCase(24.5, [24, 25])).toBe(24);
  });
  it("returns exact match", () => {
    expect(nearestCase(24, [20, 24, 30])).toBe(24);
  });
  it("returns lower bound when below all cases", () => {
    expect(nearestCase(-5, [1, 2, 3])).toBe(1);
  });
  it("returns upper bound when above all cases", () => {
    expect(nearestCase(200, [1, 50, 100])).toBe(100);
  });
});

describe("zoomSlider", () => {
  it("slider 0 returns full window", () => {
    const fullWindow = 100;
    const span = computeWindowSpanFromSlider(0, fullWindow);
    expect(span).toBe(fullWindow);
  });
  it("slider 100 returns min window", () => {
    const span = computeWindowSpanFromSlider(100, 100);
    expect(span).toBe(10);
  });
  it("roundtrip slider value", () => {
    const sliderVal = 86;
    const span = computeWindowSpanFromSlider(sliderVal, 119);
    const back = computeZoomSliderValue(span, 119);
    expect(back).toBe(sliderVal);
  });
});
