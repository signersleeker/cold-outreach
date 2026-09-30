import { cn } from '@/lib/utils';

export function Skeleton({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn('animate-pulse rounded-[var(--radius-sm)] bg-muted', className)}
      {...props}
    />
  );
}

/** Placeholder rows that keep a table's shape while it loads, so the page
 *  doesn't collapse to a single line of text and jump when data lands. */
export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="divide-y" aria-hidden>
      <div className="flex gap-4 bg-muted/60 px-3 py-2.5">
        {Array.from({ length: cols }, (_, i) => (
          <Skeleton key={i} className="h-3 flex-1 bg-muted-foreground/15" />
        ))}
      </div>
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="flex gap-4 px-3 py-3">
          {Array.from({ length: cols }, (_, c) => (
            <Skeleton
              key={c}
              className="h-3.5 flex-1"
              style={{ opacity: 1 - r * 0.12, animationDelay: `${r * 60}ms` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function StatSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          className="space-y-2.5 rounded-[var(--radius-lg)] border border-border bg-card px-4 py-3.5 shadow-soft"
        >
          <Skeleton className="h-2.5 w-20" />
          <Skeleton className="h-6 w-16" />
          <Skeleton className="h-2.5 w-24" />
        </div>
      ))}
    </div>
  );
}
