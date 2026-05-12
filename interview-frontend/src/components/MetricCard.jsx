import React from "react";
import { TrendingDown, TrendingUp } from "lucide-react";

export default function MetricCard({
  title,
  label,
  value,
  hint,
  icon: Icon,
  trend,
  trendValue,
  color = "blue",
}) {
  const heading = title ?? label ?? "";
  const colorClasses = {
    blue: "bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400",
    green: "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400",
    red: "bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400",
    purple: "bg-purple-100 text-purple-600 dark:bg-purple-900/40 dark:text-purple-400",
    yellow: "bg-amber-100 text-amber-600 dark:bg-amber-900/40 dark:text-amber-400",
  };

  return (
    <div className="metric-card group">
      <div className="flex justify-between items-start">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{heading}</p>
          <h3 className="text-2xl font-black mt-1 text-slate-900 dark:text-white">{value}</h3>

          {trend && (
            <div className="flex items-center mt-2">
              {trend === "up" ? (
                <TrendingUp className="w-4 h-4 text-emerald-500 mr-1" />
              ) : (
                <TrendingDown className="w-4 h-4 text-red-500 mr-1" />
              )}
              <span className={`text-xs font-semibold ${trend === "up" ? "text-emerald-500" : "text-red-500"}`}>
                {trendValue}
              </span>
              <span className="text-xs text-slate-400 ml-1">vs last month</span>
            </div>
          )}

          {!trend && hint ? (
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-500">{hint}</p>
          ) : null}

          {String(value).includes("%") && (
            <div className="score-bar mt-3">
              <div
                className={`score-bar-fill ${color}`}
                style={{ width: `${Math.min(parseInt(value, 10) || 0, 100)}%` }}
              />
            </div>
          )}
        </div>
        {Icon && (
          <div className={`p-2.5 rounded-xl ${colorClasses[color]} ml-4 shrink-0 group-hover:scale-110 transition-transform duration-300`}>
            <Icon size={20} />
          </div>
        )}
      </div>
    </div>
  );
}