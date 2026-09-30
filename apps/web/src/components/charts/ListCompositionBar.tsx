import type { ContactStats } from '@/lib/api';
import { cn } from '@/lib/utils';

/**
 * What the list is made of — a part-to-whole stacked bar over validation state.
 *
 * Four segments sit in a fixed quality order, so the palette is fixed too and
 * never reassigned by size; a segment keeps its colour when a filter empties it.
 * The legend carries a label and a count for every segment, which is what lets
 * the grey "unverified" step (no chroma, correctly — it means "no verdict") and
 * the butter step (2.88:1) be legible: nothing here is colour-alone.
 */

type Segment = {
  key: string;
  label: string;
  count: number;
  className: string;
  swatch: string;
};

function segmentsOf(stats: ContactStats): Segment[] {
  return [
    {
      key: 'valid',
      label: 'Valid',
      count: stats.validationValid,
      className: 'bg-chart-valid',
      swatch: 'bg-chart-valid',
    },
    {
      key: 'risky',
      label: 'Risky',
      count: stats.risky,
      className: 'bg-chart-risky',
      swatch: 'bg-chart-risky',
    },
    {
      key: 'invalid',
      label: 'Invalid',
      count: stats.invalid,
      className: 'bg-chart-invalid',
      swatch: 'bg-chart-invalid',
    },
    {
      key: 'unverified',
      label: 'Unverified',
      count: stats.validationUnverified,
      className: 'bg-chart-unverified',
      swatch: 'bg-chart-unverified',
    },
  ];
}

export function ListCompositionBar({ stats }: { stats: ContactStats }) {
  const segments = segmentsOf(stats);
  const total = segments.reduce((sum, s) => sum + s.count, 0);

  if (total === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        Nothing to summarise yet — import a CSV to see the list break down.
      </p>
    );
  }

  const shown = segments.filter((s) => s.count > 0);

  return (
    <div className="space-y-2.5">
      {/* gap-[2px] is the surface gap that separates touching segments — no
          strokes, which would add ink that isn't data. */}
      <div className="flex h-2.5 gap-[2px] overflow-hidden rounded-full">
        {shown.map((segment) => (
          <div
            key={segment.key}
            className={cn('h-full first:rounded-l-full last:rounded-r-full', segment.className)}
            style={{ width: `${(segment.count / total) * 100}%` }}
            title={`${segment.label}: ${segment.count}`}
          />
        ))}
      </div>

      <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {segments.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1.5 text-xs">
            <span aria-hidden className={cn('size-2 rounded-full', segment.swatch)} />
            <span className="text-muted-foreground">{segment.label}</span>
            <span className="font-mono font-semibold tabular-nums">{segment.count}</span>
            <span className="font-mono text-caption text-muted-foreground">
              {Math.round((segment.count / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
