import { ArrowUpRight, TrendingDown, TrendingUp } from 'lucide-react';
import type * as React from 'react';
import { Link } from 'react-router-dom';
import { TrendBars } from '@/components/charts/TrendBars';
import { cardClass } from '@/components/ui/card';
import { formatDeltaPct } from '@/lib/format';
import { cn } from '@/lib/utils';

/**
 * A headline number, with the three things that make one worth reading: what it
 * was last period, what shape it has been, and where to go to act on it.
 *
 * Lives here rather than in ui/ because of those last two — the tile knows about
 * the router and about the chart primitives, and the ui/ primitives are kept
 * clear of both.
 *
 * Data gets JetBrains Mono and a mono caption label, matching the stat block in
 * the brand guidelines (section 07/08).
 */

export interface StatDelta {
  /** Signed change as a fraction. Null when there is no baseline to compare. */
  fraction: number | null;
  /** The period compared against, e.g. "vs prior 7 days". */
  label: string;
  /** Which direction is the good news. Omit when the metric is neutral. */
  goodWhen?: 'up' | 'down';
}

const TONE_TEXT = {
  default: 'text-foreground',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
} as const;

/** The left rail is the tile's status channel — a tint, never the only signal;
 *  the hint line always spells the same state out in words. */
const TONE_RAIL = {
  default: 'bg-primary/15',
  success: 'bg-success/40',
  warning: 'bg-warning/40',
  danger: 'bg-danger/40',
} as const;

export type StatTone = keyof typeof TONE_TEXT;

function DeltaChip({ fraction, label, goodWhen }: StatDelta) {
  if (fraction === null) return null;
  const rounded = Math.round(fraction * 100);
  const up = rounded > 0;
  // Direction is a status, so it ships with an arrow and a written period, never
  // colour alone — and a flat week is grey rather than quietly good news.
  const tone =
    rounded === 0 || !goodWhen
      ? 'text-muted-foreground'
      : (up ? 'up' : 'down') === goodWhen
        ? 'text-success'
        : 'text-danger';
  const Icon = up ? TrendingUp : TrendingDown;

  return (
    <span className={cn('flex items-center gap-1 text-xs font-medium whitespace-nowrap', tone)}>
      {rounded === 0 ? null : <Icon className="size-3.5" aria-hidden />}
      <span className="font-mono">{formatDeltaPct(fraction)}</span>
      <span className="sr-only">{label}</span>
    </span>
  );
}

export interface StatTileProps {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: StatTone;
  /** Makes the whole tile a link. A number you can act on beats one you can't. */
  to?: string;
  icon?: React.ComponentType<{ className?: string }>;
  delta?: StatDelta;
  /** Daily series, oldest first, for the sparkbar under the value. */
  trend?: number[];
  trendLabel?: string;
}

export function StatTile({
  label,
  value,
  hint,
  tone = 'default',
  to,
  icon: Icon,
  delta,
  trend,
  trendLabel,
}: StatTileProps) {
  const content = (
    <>
      <span aria-hidden className={cn('absolute inset-y-0 left-0 w-0.5', TONE_RAIL[tone])} />

      <div className="flex items-start justify-between gap-2">
        <p className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
          {label}
        </p>
        {to ? (
          <ArrowUpRight
            aria-hidden
            className="size-3.5 shrink-0 text-muted-foreground opacity-45 transition-opacity group-hover:opacity-100"
          />
        ) : Icon ? (
          <Icon className="size-3.5 shrink-0 text-muted-foreground opacity-60" />
        ) : null}
      </div>

      <div className="mt-1.5 flex items-end justify-between gap-3">
        <p className={cn('font-mono text-[1.75rem] leading-none font-semibold', TONE_TEXT[tone])}>
          {value}
        </p>
        {delta ? <DeltaChip {...delta} /> : null}
      </div>

      {trend ? (
        <TrendBars values={trend} label={trendLabel ?? `${label}, recent daily volume`} className="mt-3" />
      ) : null}

      {hint ? <p className="mt-2 text-xs text-muted-foreground">{hint}</p> : null}
    </>
  );

  const shape = 'relative overflow-hidden px-4 py-3.5';

  if (!to) {
    return <div className={cn(cardClass, shape)}>{content}</div>;
  }

  return (
    <Link
      to={to}
      className={cn(
        cardClass,
        shape,
        'group block transition-[box-shadow,transform] hover:-translate-y-0.5 hover:shadow-card',
        'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
      )}
    >
      {content}
    </Link>
  );
}
