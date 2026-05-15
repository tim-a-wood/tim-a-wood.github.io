import React from "react";
import { StackedPlots } from "./StackedPlots";
import { XAxisNavigation } from "./XAxisNavigation";

export function PlotWorkspace() {
  return (
    <div className="plot-workspace">
      <div className="stacked-plots">
        <StackedPlots />
      </div>
      <XAxisNavigation />
    </div>
  );
}
