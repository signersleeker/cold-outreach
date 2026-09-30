import { cn } from '@/lib/utils';

/**
 * The sparkbar inside a stat tile: recent daily volume, history recessive and
 * the current day in the accent.
 *
 * Bars rather than a sparkline on purpose. It keeps the same mark language as
 * the activity chart further down the page — one hue, 2px surface gaps, rounded
 * data-ends — and a flex row of rects survives being stretched to whatever width
 * the tile ends up at, which a stroked path does not without distorting either
 * the line weight or the end dot.
 *
 * There is no axis and no label: the tile's own value is the current figure, so
 * this row only has to carry shape. The accessible name states the range instead.
 */
export function TrendBars({
  values,
  label,
  className,
}: {
  values: number[];
  /** Accessible name — say what the shape is, since no axis explains it. */
  label: string;
  className?: string;
}) {
  if (values.length === 0) return null;
  const max = Math.max(...values, 1);
  const last = values.length - 1;

  return (
    <div className={cn('flex h-7 items-end gap-[2px]', className)} role="img" aria-label={label}>
      {values.map((value, index) => (
        <span
          key={index}
          className={cn(
            'flex-1 rounded-t-[2px]',
            // A zero day stays visible as a baseline tick, so gaps read as gaps
            // rather than as the chart ending early.
            value === 0
              ? 'bg-border'
              : index === last
                ? 'bg-chart-sends'
                : 'bg-chart-sends/35',
          )}
          style={{ height: value === 0 ? '1px' : `max(2px, ${(value / max) * 100}%)` }}
        />
      ))}
    </div>
  );
}
