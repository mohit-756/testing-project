import React from "react";
import { cn } from "../utils/utils";

export default function ScoreProgressCell({ score, className }) {
  const numericScore = Number.isFinite(Number(score)) ? Number(score) : 0;

  // Determine color based on score
  const getScoreColor = (val) => {
    if (val >= 80) return "bg-emerald-500";
    if (val >= 60) return "bg-blue-500";
    if (val >= 40) return "bg-yellow-500";
    if (val > 0) return "bg-red-500";
    return "bg-amber-300 dark:bg-amber-600";
  };

  const getTextColor = (val) => {
    if (val >= 80) return "text-emerald-600 dark:text-emerald-400";
    if (val >= 60) return "text-blue-600 dark:text-blue-400";
    if (val >= 40) return "text-yellow-600 dark:text-yellow-400";
    if (val > 0) return "text-red-600 dark:text-red-400";
    return "text-amber-600 dark:text-amber-400";
  };

  return (
    <div className={cn("flex items-center space-x-3 min-w-[100px]", className)}>
      <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
        <div 
          className={cn("h-full rounded-full transition-all duration-500", getScoreColor(numericScore))}
          style={{ width: `${numericScore}%` }}
        />
      </div>
      <span className={cn("text-xs font-bold w-10 text-right", getTextColor(numericScore))}>
        {numericScore > 0 ? `${numericScore}%` : "Pending"}
      </span>
    </div>
  );
}
