import type { PlotSet } from "../types/appTypes";
export const defaultPlotSet: PlotSet = {
  id: "performance_summary",
  name: "Performance Summary (3 Plots)",
  xAxisVariableKey: "Case",
  plots: [
    {
      id: "plot_vr_v2",
      title: "VR and V2 Speeds",
      leftAxisLabel: "Speed [kt]",
      series: [
        { id: "s_vr_act", variableKey: "VR_Act", label: "VR Act [kt]", color: "#39b54a", lineStyle: "solid", width: 2, yAxis: "left", visible: true },
        { id: "s_vr_exp", variableKey: "VR_Exp", label: "VR Exp [kt]", color: "#39b54a", lineStyle: "dashed", width: 2, yAxis: "left", visible: true },
        { id: "s_v2_act", variableKey: "V2_Act", label: "V2 Act [kt]", color: "#9b5de5", lineStyle: "solid", width: 2, yAxis: "left", visible: true },
        { id: "s_v2_exp", variableKey: "V2_Exp", label: "V2 Exp [kt]", color: "#9b5de5", lineStyle: "dashed", width: 2, yAxis: "left", visible: true },
      ],
    },
    {
      id: "plot_todist",
      title: "Takeoff Distance [m]",
      leftAxisLabel: "Distance [m]",
      series: [
        { id: "s_todist_act", variableKey: "TODist_Act", label: "TO Dist Act [m]", color: "#ff7a00", lineStyle: "solid", width: 2, yAxis: "left", visible: true },
        { id: "s_todist_exp", variableKey: "TODist_Exp", label: "TO Dist Exp [m]", color: "#ff7a00", lineStyle: "dashed", width: 2, yAxis: "left", visible: true },
      ],
    },
    {
      id: "plot_errors",
      title: "Errors (Absolute & Relative)",
      leftAxisLabel: "Absolute Error",
      rightAxisLabel: "Relative Error [%]",
      series: [
        { id: "s_vr_abserr", variableKey: "VR_AbsErr", label: "VR Abs Err [kt]", color: "#ff7a00", lineStyle: "solid", width: 2, yAxis: "left", visible: true },
        { id: "s_v2_abserr", variableKey: "V2_AbsErr", label: "V2 Abs Err [kt]", color: "#9b5de5", lineStyle: "solid", width: 2, yAxis: "left", visible: true },
        { id: "s_todist_abserr", variableKey: "TODist_AbsErr", label: "TO Dist Abs Err [m]", color: "#d6a600", lineStyle: "solid", width: 2, yAxis: "left", visible: true },
        { id: "s_vr_relerr", variableKey: "VR_RelErr", label: "VR Rel [%]", color: "#00b8c8", lineStyle: "dashed", width: 2, yAxis: "right", visible: true },
        { id: "s_v2_relerr", variableKey: "V2_RelErr", label: "V2 Rel [%]", color: "#9b5de5", lineStyle: "dashed", width: 2, yAxis: "right", visible: true },
        { id: "s_todist_relerr", variableKey: "TODist_RelErr", label: "TO Dist Rel [%]", color: "#00b8c8", lineStyle: "dotted", width: 2, yAxis: "right", visible: true },
      ],
    },
  ],
};
