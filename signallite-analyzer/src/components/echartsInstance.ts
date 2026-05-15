import type { ECharts } from 'echarts';

let inst: ECharts | null = null;

export function setEChartsInstance(i: ECharts | null): void { inst = i; }
export function getEChartsInstance(): ECharts | null { return inst; }
