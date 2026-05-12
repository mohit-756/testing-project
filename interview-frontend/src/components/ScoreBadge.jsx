import React from "react";
import { cn } from "../utils/utils";

export default function ScoreBadge({ score, className }) {
  const numericScore = Number.isFinite(Number(score)) ? Number(score) : 0;

  const getStyles = (val) => {
    if (val >= 80) return "bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-800/50";
    if (val >= 60) return "bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800/50";
    if (val >= 40) return "bg-yellow-50 text-yellow-700 border-yellow-100 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-800/50";
    if (val > 0) return "bg-red-50 text-red-700 border-red-100 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800/50";
    return "bg-amber-50 text-amber-600 border-amber-100 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800";
  };

  return (
    <span className={cn(
      "px-2 py-0.5 rounded-lg text-[10px] font-black border uppercase tracking-wider",
      getStyles(numericScore),
      className
    )}>
      {numericScore > 0 ? `${numericScore}%` : "Pending"}
    </span>
  );
}
