import React from "react";
import { cn } from "../utils/utils";

export default function StepChecklist({ steps }) {
  return (
    <div className="relative">
      {steps.map((step, index) => (
        <div key={index} className="relative flex items-start pb-6 last:pb-0">
          {/* Vertical connector line */}
          {index < steps.length - 1 && (
            <div className={cn(
              "absolute left-3 top-7 bottom-0 w-0.5 -ml-px",
              step.completed ? "bg-emerald-500" : "bg-slate-200 dark:bg-slate-700"
            )} />
          )}
          
          {/* Step circle */}
          <div className={cn(
            "relative flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mr-4 mt-0.5 z-10",
            step.completed 
              ? "bg-emerald-500 text-white" 
              : "bg-slate-200 dark:bg-slate-700 text-slate-500"
          )}>
            {step.completed ? (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            ) : (
              <span className="text-xs font-bold">{index + 1}</span>
            )}
          </div>
          
          {/* Step content */}
          <div className="flex-1 pt-0.5">
            <h4 className={cn(
              "text-sm font-semibold",
              step.completed ? 'text-emerald-700 dark:text-emerald-400' : 'text-slate-700 dark:text-slate-300'
            )}>
              {step.title}
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {step.description}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
