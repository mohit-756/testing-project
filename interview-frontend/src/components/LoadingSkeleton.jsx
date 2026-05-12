function Skeleton({ className = "" }) {
  return (
    <div className={`animate-pulse bg-slate-200 dark:bg-slate-700 rounded ${className}`} />
  );
}

export function TableSkeleton({ rows = 5, cols = 6 }) {
  return (
    <div className="w-full">
      <div className="flex gap-4 px-4 py-3 border-b border-slate-100 dark:border-slate-800">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={`header-${i}`} className="h-4 w-20" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={`row-${rowIndex}`} className="flex gap-4 px-4 py-4 border-b border-slate-50 dark:border-slate-800/50">
          {Array.from({ length: cols }).map((_, colIndex) => (
            <Skeleton 
              key={`cell-${rowIndex}-${colIndex}`} 
              className={`h-4 ${
                colIndex === 0 ? "w-16" : 
                colIndex === cols - 1 ? "w-16" : 
                "w-24"
              }`} 
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton({ hasImage = false }) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6">
      <div className="flex items-center gap-4 mb-4">
        {hasImage && <Skeleton className="w-12 h-12 rounded-full" />}
        <div className="flex-1">
          <Skeleton className="h-5 w-32 mb-2" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
      <Skeleton className="h-8 w-16 mb-2" />
      <Skeleton className="h-3 w-24" />
    </div>
  );
}

export function MetricSkeleton() {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="w-10 h-10 rounded-lg" />
        <div>
          <Skeleton className="h-3 w-16 mb-1" />
          <Skeleton className="h-6 w-12" />
        </div>
      </div>
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-6">
      <Skeleton className="h-6 w-32 mb-2" />
      <Skeleton className="h-4 w-48 mb-6" />
      <div className="flex items-end gap-2 h-48">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton 
            key={i} 
            className={`flex-1 rounded-t ${
              i === 0 ? "h-16" : 
              i === 1 ? "h-24" : 
              i === 2 ? "h-20" : 
              i === 3 ? "h-32" : 
              i === 4 ? "h-28" : 
              "h-12"
            }`} 
          />
        ))}
      </div>
    </div>
  );
}

export function FormSkeleton() {
  return (
    <div className="space-y-4">
      <div>
        <Skeleton className="h-4 w-16 mb-2" />
        <Skeleton className="h-10 w-full rounded-lg" />
      </div>
      <div>
        <Skeleton className="h-4 w-16 mb-2" />
        <Skeleton className="h-10 w-full rounded-lg" />
      </div>
      <div>
        <Skeleton className="h-4 w-16 mb-2" />
        <Skeleton className="h-24 w-full rounded-lg" />
      </div>
      <Skeleton className="h-10 w-24 rounded-lg" />
    </div>
  );
}

export default Skeleton;