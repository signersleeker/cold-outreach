import { useState } from 'react';
import type { SendActivity } from '@/lib/api';
import { cn } from '@/lib/utils';

/**
 * Daily send volume against the cap.
 *
 * One series, so one hue and no legend — the card title says what is plotted.
 * Today is distinguished by an outline rather than a second colour: a hue swap
 * would encode recency as identity, and the two ultraviolet steps that read as
 * "same series, different day" are only 11.9 ΔE apart anyway.
 *
 * The cap line is dashed on purpose. Gridlines here are solid hairlines, so
 * dashing is what separates "this is a threshold" from "this is a gridline".
 */

const DAY = new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'short' });
const WEEKDAY = new Intl.DateTimeFormat('en-AU', { weekday: 'short', day: 'numeric', month: 'short' });

/** Parse the API's plain `YYYY-MM-DD` as a local date — `new Date(s)` would
 *  read it as UTC midnight and shift the label a day back west of Greenwich. */
function parseDay(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function SendActivityChart({ activity }: { activity: SendActivity }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const { days, dailyCap } = activity;

  // Anchor the scale to the cap so bar heights always read against it; only
  // grow past it if a day somehow exceeded the cap.
  const yMax = Math.max(dailyCap, activity.busiestDay, 1);
  const capPct = (dailyCap / yMax) * 100;
  const todayIndex = days.length - 1;
  const active = hovered === null ? null : days[hovered];

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          <span className="font-mono font-semibold tabular-nums text-foreground">
            {activity.totalSent}
          </span>{' '}
          sent over {days.length} days
        </p>
        <p className="font-mono text-caption text-muted-foreground">
          peak {activity.busiestDay}/{dailyCap}
        </p>
      </div>

      <div className="relative mt-3 h-36">
        {/* Gridlines: hairline, solid, recessive. */}
        {[0, 0.5, 1].map((t) => (
          <div
            key={t}
            aria-hidden
            className="absolute inset-x-0 border-t border-border"
            style={{ bottom: `${t * 100}%` }}
          />
        ))}

        {/* Cap threshold. */}
        <div
          aria-hidden
          className="absolute inset-x-0 border-t border-dashed border-signal/70"
          style={{ bottom: `${capPct}%` }}
        />
        <span
          aria-hidden
          className="absolute right-0 z-10 -translate-y-1/2 bg-card pl-1.5 font-mono text-caption text-signal-text"
          style={{ bottom: `${capPct}%` }}
        >
          cap {dailyCap}
        </span>

        <div className="flex h-full items-end gap-[2px]">
          {days.map((day, index) => {
            const pct = (day.sent / yMax) * 100;
            const isToday = index === todayIndex;
            const date = parseDay(day.date);
            return (
              <button
                key={day.date}
                type="button"
                // The whole slot is the hit target, not the painted pixels.
                className="group relative flex h-full max-w-6 flex-1 cursor-default items-end outline-none"
                onMouseEnter={() => setHovered(index)}
                onMouseLeave={() => setHovered((c) => (c === index ? null : c))}
                onFocus={() => setHovered(index)}
                onBlur={() => setHovered((c) => (c === index ? null : c))}
                aria-label={`${WEEKDAY.format(date)}: ${day.sent} sent${
                  day.bounced ? `, ${day.bounced} bounced` : ''
                }${day.stopped ? `, ${day.stopped} asked to stop` : ''}`}
              >
                <span
                  className={cn(
                    // 4px rounded data-end, square at the baseline.
                    'w-full rounded-t-[4px] bg-chart-sends transition-opacity',
                    day.sent === 0 && 'bg-border',
                    hovered !== null && hovered !== index && 'opacity-55',
                    isToday && 'ring-2 ring-primary ring-offset-1 ring-offset-card',
                  )}
                  style={{ height: day.sent === 0 ? '2px' : `max(3px, ${pct}%)` }}
                />
                <span
                  aria-hidden
                  className="absolute inset-0 rounded-sm group-focus-visible:ring-2 group-focus-visible:ring-ring"
                />
              </button>
            );
          })}
        </div>

        {active ? (
          <div
            role="status"
            className="pointer-events-none absolute -top-1 z-20 -translate-y-full rounded-[var(--radius-md)] border border-border bg-popover px-2.5 py-1.5 shadow-lift"
            style={{
              // Clamp near the edges so the card never overflows its container.
              left: `${(hovered! / Math.max(days.length - 1, 1)) * 100}%`,
              transform: `translate(${
                hovered! < days.length / 6 ? '0' : hovered! > (days.length * 5) / 6 ? '-100%' : '-50%'
              }, -100%)`,
            }}
          >
            <p className="font-mono text-sm font-semibold tabular-nums">
              {active.sent} <span className="text-caption font-normal text-muted-foreground">sent</span>
            </p>
            <p className="text-caption whitespace-nowrap text-muted-foreground">
              {WEEKDAY.format(parseDay(active.date))}
            </p>
            {active.bounced > 0 || active.stopped > 0 ? (
              <p className="text-caption whitespace-nowrap text-muted-foreground">
                {active.bounced > 0 ? `${active.bounced} bounced` : null}
                {active.bounced > 0 && active.stopped > 0 ? ' · ' : null}
                {active.stopped > 0 ? `${active.stopped} stopped` : null}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-1.5 flex justify-between font-mono text-caption text-muted-foreground">
        <span>{DAY.format(parseDay(days[0].date))}</span>
        <span>today</span>
      </div>
    </div>
  );
}
