import { ArrowRight, CalendarClock, CheckCircle2, Flame, Users } from 'lucide-react';
import type * as React from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { useFollowUpCalendar } from '@/hooks';
import type { Dashboard } from '@/lib/api';
import { currentMonth, parseYmd } from '@/lib/calendar';
import { cn } from '@/lib/utils';

/**
 * The one panel the dashboard leads with, and the only hero figure on the page.
 *
 * It answers the question an operator actually opens this tool with — how much
 * can I still send, and who is waiting — so the left half is capacity and the
 * right half is the queue, each row of it a way into the work. Everything else
 * on the page is history; this is the part you act on.
 *
 * The hero figure is remaining capacity rather than the familiar `sent/cap`:
 * "17 left" is the number that decides what happens next, and the sidebar meter
 * already carries the sent-so-far reading on every other page.
 */

const HERO_DAY = new Intl.DateTimeFormat('en-AU', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
});

function heroDayLabel(today: string): string {
  const { year, month, day } = parseYmd(today);
  return HERO_DAY.format(new Date(Date.UTC(year, month - 1, day)));
}

/** One row of the queue: a count, what it is, and the way to go do it. */
function QueueRow({
  icon: Icon,
  count,
  label,
  tone = 'default',
  action,
}: {
  icon: React.ComponentType<{ className?: string }>;
  count: number;
  label: string;
  tone?: 'default' | 'warning';
  action?: React.ReactNode;
}) {
  return (
    <li className="flex items-center gap-3 py-2.5">
      <span
        className={cn(
          'grid size-7 shrink-0 place-items-center rounded-full',
          tone === 'warning' ? 'bg-warning-subtle text-warning' : 'bg-accent text-accent-foreground',
        )}
      >
        <Icon className="size-3.5" />
      </span>
      <span
        className={cn(
          'font-mono text-base font-semibold tabular-nums',
          tone === 'warning' ? 'text-warning' : 'text-foreground',
        )}
      >
        {count}
      </span>
      <span className="min-w-0 flex-1 text-xs text-muted-foreground">{label}</span>
      {action}
    </li>
  );
}

export function TodayPanel({ dashboard }: { dashboard: Dashboard }) {
  const { year, month } = currentMonth();
  const { data: calendar } = useFollowUpCalendar(year, month);

  const sent = dashboard.sendsToday;
  const cap = dashboard.dailyCap;
  const remaining = Math.max(0, cap - sent);
  const pct = cap > 0 ? Math.min(100, (sent / cap) * 100) : 0;
  const atCap = sent >= cap;
  const close = !atCap && remaining <= 3;

  const dueToday = calendar?.days.find((day) => day.date === calendar.today)?.items.length ?? 0;
  // Disjoint by construction: the API puts overdue steps on their own past date
  // and only totals them onto today, so these never double-count each other.
  const overdue = calendar?.overdueTotal ?? 0;

  return (
    <Card
      className={cn(
        'animate-rise relative overflow-hidden bg-gradient-to-br',
        atCap ? 'from-coral-50 to-card' : 'from-accent to-card',
      )}
    >
      <div className="grid lg:grid-cols-[1.1fr_1fr]">
        {/* ------------------------------------------------------ capacity ---- */}
        <div className="px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
              Today · {heroDayLabel(dashboard.today)}
            </p>
          </div>

          <div className="mt-3 flex items-end gap-3">
            {/* Hero figure. Mono because in this app every number is mono — the
                brand's stat block, not a display face borrowed for effect. */}
            <p
              className={cn(
                'font-mono text-[3rem] leading-none font-semibold',
                atCap ? 'text-signal-text' : close ? 'text-warning' : 'text-foreground',
              )}
            >
              {remaining}
            </p>
            <p className="pb-1 text-sm text-muted-foreground">
              {remaining === 1 ? 'send left' : 'sends left'}
              <span className="block font-mono text-caption">of a {cap}/day cap</span>
            </p>
          </div>

          <div
            className="mt-4 h-2 overflow-hidden rounded-full"
            role="progressbar"
            aria-valuenow={sent}
            aria-valuemin={0}
            aria-valuemax={cap}
            aria-label="Sends used today"
          >
            {/* Track is a lighter step of the fill's own ramp, so the state reads
                across the whole bar rather than only where it happens to end. */}
            <div
              className={cn(
                'h-full rounded-full',
                atCap ? 'bg-signal/20' : close ? 'bg-highlight/30' : 'bg-primary/15',
              )}
            >
              <div
                className={cn(
                  'h-full rounded-full transition-[width] duration-700 ease-out',
                  atCap ? 'bg-signal' : close ? 'bg-highlight' : 'bg-primary',
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
            <span>
              <span className="font-mono font-semibold text-foreground">{sent}</span> sent · resets
              at midnight {dashboard.timezone}
            </span>
            {atCap ? (
              <Badge tone="highlight">
                <CheckCircle2 className="size-3" aria-hidden />
                Cap reached
              </Badge>
            ) : null}
          </div>
        </div>

        {/* --------------------------------------------------------- queue ---- */}
        <div className="border-t border-border bg-card/65 px-5 py-4 lg:border-t-0 lg:border-l">
          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
              Up next
            </p>
            {dashboard.gmailConnected ? null : (
              <Link
                to="/settings"
                className="text-xs font-semibold text-link underline underline-offset-4"
              >
                Connect Gmail
              </Link>
            )}
          </div>

          <ul className="divide-y divide-border">
            <QueueRow
              icon={CalendarClock}
              count={dueToday}
              label={
                dueToday === 0
                  ? 'no follow-ups due today'
                  : `follow-up${dueToday === 1 ? '' : 's'} due today`
              }
              action={
                dueToday > 0 ? (
                  <a
                    href="#calendar"
                    className="flex items-center gap-1 text-xs font-semibold text-link whitespace-nowrap hover:underline"
                  >
                    See who
                    <ArrowRight className="size-3.5" aria-hidden />
                  </a>
                ) : null
              }
            />
            {overdue > 0 ? (
              <QueueRow
                icon={CalendarClock}
                count={overdue}
                label="overdue from earlier days"
                tone="warning"
                action={
                  <a
                    href="#calendar"
                    className="flex items-center gap-1 text-xs font-semibold text-link whitespace-nowrap hover:underline"
                  >
                    Catch up
                    <ArrowRight className="size-3.5" aria-hidden />
                  </a>
                }
              />
            ) : null}
            <QueueRow
              icon={Users}
              count={dashboard.contactsReady}
              label={
                dashboard.contactsReady === 0
                  ? 'nobody validated and unsent'
                  : 'ready to send — valid, never emailed'
              }
              action={
                <Link
                  to={dashboard.contactsReady > 0 ? '/contacts?status=ready' : '/contacts'}
                  className="flex items-center gap-1 text-xs font-semibold text-link whitespace-nowrap hover:underline"
                >
                  {dashboard.contactsReady > 0 ? 'Pick one' : 'Import a list'}
                  <ArrowRight className="size-3.5" aria-hidden />
                </Link>
              }
            />
          </ul>
        </div>
      </div>
    </Card>
  );
}

/** The streak chip, shown beside the page title rather than in the panel — it is
 *  encouragement, not a number you act on, so it stays out of the queue. */
export function StreakBadge({ streak }: { streak: number }) {
  if (streak < 2) return null;
  return (
    <Badge tone="highlight" title="Consecutive days with at least one send">
      <Flame className="size-3" aria-hidden />
      {streak}-day streak
    </Badge>
  );
}
