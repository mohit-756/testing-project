import React from 'react';
import { Loader } from 'lucide-react';

export default function LoadingState({
  message = 'Loading...',
  variant = 'page', // 'page', 'card', 'inline'
  size = 'md', // 'sm', 'md', 'lg'
  fullHeight = false,
}) {
  const spinnerSizes = {
    sm: 'w-6 h-6',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  const messageSizes = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  };

  if (variant === 'page') {
    return (
      <div className={`flex items-center justify-center ${fullHeight ? 'min-h-screen' : 'min-h-[400px]'} bg-slate-50 dark:bg-slate-950`}>
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <Loader className={`${spinnerSizes[size]} text-blue-600 animate-spin`} aria-hidden="true" />
          </div>
          <p className={`${messageSizes[size]} text-slate-600 dark:text-slate-400 font-medium`}>
            {message}
          </p>
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Please wait while we load your data...
          </p>
        </div>
      </div>
    );
  }

  if (variant === 'card') {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-8 text-center space-y-4">
        <div className="flex justify-center">
          <Loader className={`${spinnerSizes[size]} text-blue-600 animate-spin`} aria-hidden="true" />
        </div>
        <p className={`${messageSizes[size]} text-slate-600 dark:text-slate-400 font-medium`}>
          {message}
        </p>
      </div>
    );
  }

  // inline variant
  return (
    <div className="flex items-center gap-2">
      <Loader className={`${spinnerSizes[size]} text-blue-600 animate-spin`} aria-hidden="true" />
      <p className={`${messageSizes[size]} text-slate-600 dark:text-slate-400 font-medium`}>
        {message}
      </p>
    </div>
  );
}
