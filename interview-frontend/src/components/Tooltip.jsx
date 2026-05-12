import React, { useState } from "react";
import { Info } from "lucide-react";

export default function Tooltip({ text, children }) {
  const [show, setShow] = useState(false);

  return (
    <div 
      className="relative inline-flex items-center"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children || <Info size={14} className="text-slate-400" />}
      {show && text && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-slate-900 dark:bg-slate-800 text-white text-xs rounded-lg shadow-xl whitespace-nowrap animate-fadeIn">
          {text}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-900 dark:border-t-slate-800" />
        </div>
      )}
    </div>
  );
}