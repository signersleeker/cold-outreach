import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  useContact,
  useFollowUpCalendar,
  useSentCalendar,
  useSentEmails,
} from '@/hooks';
import type { CalendarDueItem, SentEmail } from '@/lib/api';
import {
  WEEKDAYS,
  currentMonth,
  monthCells,
  monthLabel,
  parseYmd,
  shiftMonth,
} from '@/lib/calendar';
import { formatDateTime, formatTime, plural } from '@/lib/format';
import { SEND_STATUS_TONE } from '@/lib/gates';
import { cn } from '@/lib/utils';
import { SendModal } from './SendModal';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardBody, CardHeader, CardTitle, EmptyState } from './ui/card';
import { Dialog, DialogBody, DialogContent } from './ui/dialog';
import { Segmented } from './ui/segmented';
import { Skeleton, TableSkeleton } from './ui/skeleton';
import { Table, TableWrap, Td, Th, Tr } from './ui/table';

/**
 * One month grid for the whole outreach timeline — what already went out and
 * what is still scheduled.
 *
 * This replaces the two separate month grids the dashboard used to stack. They
 * had the same geometry and the same month nav, and they never competed for the
 * same cell: sends are always in the past, scheduled follow-ups are always today
 * or later. Splitting them made the operator read the same calendar twice to
 * answer one question ("what does this week look like?").
 *
 * Two measures on one grid, so two deliberately different encodings:
 *
 *   sent      — it happened, and it has a magnitude: a *filled* cell on the
 *               four-step sequential ramp (the same `chart-sends` hue the
 *               activity chart uses for this series).
 *   scheduled — it is a plan, not a fact: an *outlined* chip, no fill. Planned
 *               versus actual is the one place outline-vs-fill is doing real
 *               work, and it keeps the heat ramp meaning exactly one thing.
 *
 * Bounces and stops stay what they were — a status, not more volume — so they
 * ride as labelled dots rather than distorting the ramp. Everything on the grid
 * is in the legend, and every cell carries its counts as text, so nothing here
 * is conveyed by colour alone.
 */

/**
 * Four ordinal steps against the month's own peak.
 *
 * Capped at /46, not /70. A month whose peak is one send puts every sending day
 * straight onto the top step, and at /70 the tint is dark enough that the day
 * number and the chips lose their contrast against it. The steps still read as
 * four because they are compared with each other across the grid, not judged in
 * isolation — and buying that back costs nothing, while an unreadable cell costs
 * the whole point of the grid.
 */
function heatClass(sent: number, busiest: number): string {
  if (sent === 0) return '';
  const ratio = sent / Math.max(busiest, 1);
  if (ratio <= 0.25) return 'bg-chart-sends/10';
  if (ratio <= 0.5) return 'bg-chart-sends/22';
  if (ratio <= 0.75) return 'bg-chart-sends/34';
  return 'bg-chart-sends/46';
}

const CELL_DATE = new Intl.DateTimeFormat('en-AU', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
});

function dayLabel(date: string): string {
  const { year, month, day } = parseYmd(date);
  return CELL_DATE.format(new Date(Date.UTC(year, month - 1, day)));
}

function dayHeading(date: string): string {
  const { year, month, day } = parseYmd(date);
  return `${day} ${monthLabel(year, month)}`;
}

/** What one cell is made of, once both payloads are folded together. */
interface DayFacts {
  sent: number;
  bounced: number;
  stopped: number;
  due: CalendarDueItem[];
  /** Still pending on a date that has already passed. */
  overdue: boolean;
}

function cellTitle(date: string, facts: DayFacts): string {
  const when = dayLabel(date);
  const parts: string[] = [];
  if (facts.sent > 0) parts.push(`${plural(facts.sent, 'email')} sent`);
  if (facts.bounced > 0) parts.push(`${facts.bounced} bounced`);
  if (facts.stopped > 0) parts.push(`${facts.stopped} asked to stop`);
  if (facts.due.length > 0) {
    parts.push(
      `${plural(facts.due.length, 'follow-up')} ${facts.overdue ? 'overdue' : 'scheduled'}`,
    );
  }
  return parts.length === 0 ? `${when}: nothing` : `${when}: ${parts.join(' · ')}`;
}

type DayTab = 'due' | 'sent';

/**
 * The selected day, split into the two things it can hold.
 *
 * Tabs rather than two stacked sections: a busy day put a long send table
 * between you and nothing useful, and the counts belong on the controls anyway.
 * Due leads — it is the half of the day you can still act on — but a day with
 * nothing scheduled opens on Sent instead of on an empty tab. Both tabs stay
 * visible and keep their counts either way, so a zero is still an answer.
 */
function DayPanel({
  date,
  due,
  overdue,
  emails,
  loading,
  timezone,
  onRead,
  onSend,
}: {
  date: string;
  due: CalendarDueItem[];
  overdue: boolean;
  emails: SentEmail[];
  loading: boolean;
  timezone?: string;
  onRead: (email: SentEmail) => void;
  onSend: (contactId: string, templateId: string) => void;
}) {
  // Null until the operator picks a side. The default is derived on every
  // render rather than frozen at mount: the sends and the follow-ups are two
  // independent queries, and if the sends land first the panel would otherwise
  // open on Sent and stay there even once the day's Due items arrived.
  const [picked, setPicked] = useState<DayTab | null>(null);
  const tab = picked ?? (due.length > 0 ? 'due' : 'sent');

  return (
    <div className="space-y-3 border-t border-border pt-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
          {dayHeading(date)}
        </h3>
        <Segmented
          value={tab}
          onChange={setPicked}
          aria-label="What to show for this day"
          options={[
            { value: 'due', label: overdue ? 'Overdue' : 'Due', count: due.length },
            { value: 'sent', label: 'Sent', count: emails.length },
          ]}
        />
      </div>

      {tab === 'due' ? (
        due.length === 0 ? (
          <p className="text-xs text-muted-foreground">Nothing scheduled on this day.</p>
        ) : (
          <ul className="divide-y divide-border rounded-[var(--radius-md)] border border-border">
            {due.map((item) => (
              <li key={item.stepId} className="flex items-center gap-3 px-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <Link
                    to={`/contacts/${item.contactId}`}
                    className="truncate text-sm font-medium hover:underline"
                  >
                    {item.contactName || item.contactEmail}
                  </Link>
                  <p className="truncate text-xs text-muted-foreground">
                    Step {item.position + 1}/{item.stepCount} · {item.templateName}
                    {item.company ? ` · ${item.company}` : ''}
                    {item.pastCap ? " · past today's cap" : ''}
                    {item.overdue ? ' · overdue' : ''}
                  </p>
                </div>
                <Button size="sm" onClick={() => onSend(item.contactId, item.templateId)}>
                  Send
                </Button>
              </li>
            ))}
          </ul>
        )
      ) : loading && emails.length === 0 ? (
        <TableSkeleton rows={3} cols={6} />
      ) : emails.length === 0 ? (
        <p className="text-xs text-muted-foreground">Nothing sent on this day.</p>
      ) : (
        <TableWrap>
          <Table>
            <thead>
              <tr>
                <Th>Time</Th>
                <Th>To</Th>
                <Th>Company</Th>
                <Th>Template</Th>
                <Th>Subject</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {emails.map((email) => (
                <Tr key={email.id} className="cursor-pointer" onClick={() => onRead(email)}>
                  <Td className="font-mono whitespace-nowrap tabular-nums">
                    {formatTime(email.sentAt, timezone)}
                  </Td>
                  <Td>
                    <Link
                      to={`/contacts/${email.contactId}`}
                      onClick={(event) => event.stopPropagation()}
                      className="font-medium hover:underline"
                    >
                      {email.contactName || email.contactEmail}
                    </Link>
                    {email.contactName ? (
                      <span className="block font-mono text-caption text-muted-foreground">
                        {email.contactEmail}
                      </span>
                    ) : null}
                  </Td>
                  <Td className="text-muted-foreground">{email.company || '—'}</Td>
                  <Td className="text-muted-foreground">{email.templateName || '—'}</Td>
                  <Td className="max-w-[18rem] truncate">{email.subject}</Td>
                  <Td>
                    <Badge tone={SEND_STATUS_TONE[email.status] ?? 'muted'}>
                      {email.status.replace('_', ' ')}
                    </Badge>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </TableWrap>
      )}
    </div>
  );
}

export function OutreachCalendar() {
  const [cursor, setCursor] = useState(currentMonth);
  const { data: sentCalendar, isLoading } = useSentCalendar(cursor.year, cursor.month);
  const { data: followUps } = useFollowUpCalendar(cursor.year, cursor.month);

  const today = sentCalendar?.today ?? followUps?.today ?? null;

  // ISO dates compare correctly as strings, so "has this date passed" needs no
  // parsing — and no timezone guesswork, which is the whole point of the API
  // handing us plain YYYY-MM-DD in the operator's zone.
  const byDate = useMemo(() => {
    const map = new Map<string, DayFacts>();
    const facts = (date: string): DayFacts => {
      const existing = map.get(date);
      if (existing) return existing;
      const fresh: DayFacts = { sent: 0, bounced: 0, stopped: 0, due: [], overdue: false };
      map.set(date, fresh);
      return fresh;
    };
    for (const day of sentCalendar?.days ?? []) {
      const entry = facts(day.date);
      entry.sent = day.sent;
      entry.bounced = day.bounced;
      entry.stopped = day.stopped;
    }
    for (const day of followUps?.days ?? []) {
      if (day.items.length === 0) continue;
      const entry = facts(day.date);
      entry.due = day.items;
      entry.overdue = today !== null && day.date < today;
    }
    return map;
  }, [sentCalendar, followUps, today]);

  const cells = useMemo(() => monthCells(cursor.year, cursor.month), [cursor]);
  const monthKey = `${cursor.year}-${cursor.month}`;

  /** Today if there is anything on it, else the last day that has something. */
  const defaultDay = useMemo(() => {
    if (today && byDate.has(today)) {
      const facts = byDate.get(today);
      if (facts && (facts.sent > 0 || facts.due.length > 0)) return today;
    }
    const populated = [...byDate.entries()]
      .filter(([, facts]) => facts.sent > 0 || facts.due.length > 0)
      .map(([date]) => date)
      .sort();
    return populated.at(-1) ?? null;
  }, [byDate, today]);

  // Keyed by month so a 60s refetch never clobbers the operator's choice, but
  // moving to another month re-picks a sensible default.
  const [selection, setSelection] = useState<{ month: string; date: string | null } | null>(null);
  const isCurrentMonth = selection?.month === monthKey;
  const selected = isCurrentMonth ? selection.date : null;

  useEffect(() => {
    if (isCurrentMonth || (!sentCalendar && !followUps)) return;
    setSelection({ month: monthKey, date: defaultDay });
  }, [defaultDay, isCurrentMonth, monthKey, sentCalendar, followUps]);

  const { data: dayData, isFetching: dayFetching } = useSentEmails(selected);
  const emails = dayData?.data ?? [];
  const selectedFacts = selected ? byDate.get(selected) : undefined;
  const dueOnSelected = selectedFacts?.due ?? [];

  const [reading, setReading] = useState<SentEmail | null>(null);
  const [sendTarget, setSendTarget] = useState<{ contactId: string; templateId: string } | null>(
    null,
  );
  const { data: sendContact } = useContact(sendTarget?.contactId ?? '');

  const timezone = sentCalendar?.timezone ?? followUps?.timezone;
  const hasOutcomes = (sentCalendar?.days ?? []).some((d) => d.bounced > 0 || d.stopped > 0);
  const scheduledThisMonth = (followUps?.days ?? []).reduce(
    (sum, day) => sum + day.items.length,
    0,
  );
  const nothingThisMonth = (sentCalendar?.monthTotal ?? 0) === 0 && scheduledThisMonth === 0;

  function moveMonth(delta: number) {
    setCursor((current) => shiftMonth(current, delta));
  }

  return (
    <>
      <Card>
        {/* Wraps rather than overflowing: the title plus the month nav is wider
            than a phone, and the page body must never scroll sideways. */}
        <CardHeader className="flex-wrap">
          {/* Names both encodings, so the card title isn't just the band label
              above it repeated back. */}
          <CardTitle>Sent &amp; scheduled</CardTitle>
          <div className="flex items-center gap-2">
            <Button size="icon" variant="ghost" onClick={() => moveMonth(-1)} title="Previous month">
              <ChevronLeft />
            </Button>
            <span className="min-w-[9rem] text-center font-mono text-xs tracking-wide text-muted-foreground uppercase">
              {monthLabel(cursor.year, cursor.month)}
            </span>
            <Button size="icon" variant="ghost" onClick={() => moveMonth(1)} title="Next month">
              <ChevronRight />
            </Button>
          </div>
        </CardHeader>

        <CardBody className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <p className="text-xs text-muted-foreground">
              <span className="font-mono font-semibold tabular-nums text-foreground">
                {sentCalendar?.monthTotal ?? 0}
              </span>{' '}
              sent ·{' '}
              <span className="font-mono font-semibold tabular-nums text-foreground">
                {scheduledThisMonth}
              </span>{' '}
              scheduled in {monthLabel(cursor.year, cursor.month)}
              {followUps && followUps.overdueTotal > 0 ? (
                <span className="text-warning"> · {followUps.overdueTotal} overdue</span>
              ) : null}
              {timezone ? `. Times in ${timezone}` : ''}. Click a day to see it.
            </p>

            {/* Legend. Two encodings on one grid, so it is never optional — and
                it is what lets the light end of the heat ramp be readable. */}
            <ul className="flex flex-wrap items-center gap-x-3.5 gap-y-1.5 font-mono text-caption text-muted-foreground">
              {/* The swatches are the cell chips in miniature — solid dot for
                  what happened, dashed outline for what is planned. */}
              <li className="flex items-center gap-1.5">
                <span aria-hidden className="size-2 rounded-full bg-chart-sends" />
                sent
              </li>
              <li className="flex items-center gap-1.5">
                <span
                  aria-hidden
                  className="size-2.5 rounded-full border border-dashed border-primary/60"
                />
                scheduled
              </li>
              {hasOutcomes ? (
                <>
                  <li className="flex items-center gap-1.5">
                    <span aria-hidden className="size-1.5 rounded-full bg-danger" />
                    bounced
                  </li>
                  <li className="flex items-center gap-1.5">
                    <span aria-hidden className="size-1.5 rounded-full bg-warning" />
                    stopped
                  </li>
                </>
              ) : null}
            </ul>
          </div>

          {isLoading && !sentCalendar ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <div className="overflow-x-auto">
              <div className="grid min-w-[40rem] grid-cols-7 gap-px rounded-[var(--radius-md)] border border-border bg-border">
                {WEEKDAYS.map((label) => (
                  <div
                    key={label}
                    className="bg-surface px-2 py-1.5 text-center font-mono text-caption tracking-wider text-muted-foreground uppercase"
                  >
                    {label}
                  </div>
                ))}
                {cells.map((cell, index) => {
                  if (!cell.date) {
                    return <div key={`empty-${index}`} className="min-h-20 bg-card/40" />;
                  }
                  const facts =
                    byDate.get(cell.date) ??
                    ({ sent: 0, bounced: 0, stopped: 0, due: [], overdue: false } as DayFacts);
                  const dueCount = facts.due.length;
                  const isToday = today === cell.date;
                  const isSelected = selected === cell.date;
                  // Today is always openable, so a quiet day can still be
                  // inspected rather than looking broken.
                  const openable = facts.sent > 0 || dueCount > 0 || isToday;

                  return (
                    <button
                      key={cell.date}
                      type="button"
                      disabled={!openable}
                      aria-pressed={isSelected}
                      title={cellTitle(cell.date, facts)}
                      onClick={() => setSelection({ month: monthKey, date: cell.date })}
                      className={cn(
                        'relative flex min-h-20 flex-col gap-1 bg-card p-2 text-left transition-colors',
                        heatClass(facts.sent, sentCalendar?.busiestDay ?? 0),
                        openable ? 'hover:brightness-95' : 'cursor-default',
                        isToday && 'ring-1 ring-inset ring-primary',
                        // Selection is a heavier ring in a different hue, so it
                        // never reads as "today" and survives the heat tint.
                        isSelected && 'ring-2 ring-inset ring-signal',
                      )}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span
                          className={cn(
                            'font-mono text-xs',
                            isToday && 'font-semibold',
                            // Ultraviolet on the heat tint only reaches 4.1:1, so
                            // a tinted cell takes full ink whatever day it is.
                            // Today loses nothing: the inset primary ring, not the
                            // numeral's colour, is what marks it.
                            facts.sent > 0
                              ? 'text-foreground'
                              : isToday
                                ? 'text-primary'
                                : 'text-muted-foreground',
                          )}
                        >
                          {cell.dayNum}
                        </span>
                        <span aria-hidden className="flex items-center gap-1">
                          {facts.bounced > 0 ? (
                            <span className="size-1.5 rounded-full bg-danger" />
                          ) : null}
                          {facts.stopped > 0 ? (
                            <span className="size-1.5 rounded-full bg-warning" />
                          ) : null}
                        </span>
                      </div>

                      {/* Both counts are labelled and both sit on a card plate, so
                          they stay readable at any heat step. What separates them
                          is form, not wording: a solid dot for what happened, a
                          dashed outline for what is only planned. */}
                      <div className="mt-auto flex flex-col items-start gap-1">
                        {facts.sent > 0 ? (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-card/85 px-1.5 py-px font-mono text-caption font-medium text-foreground">
                            <span aria-hidden className="size-1.5 rounded-full bg-chart-sends" />
                            {facts.sent} sent
                          </span>
                        ) : null}
                        {dueCount > 0 ? (
                          <span
                            className={cn(
                              'inline-flex items-center rounded-full border border-dashed bg-card/85 px-1.5 py-px font-mono text-caption',
                              facts.overdue
                                ? 'border-warning/70 text-warning'
                                : 'border-primary/55 text-primary',
                            )}
                          >
                            {dueCount} {facts.overdue ? 'overdue' : 'due'}
                          </span>
                        ) : null}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {nothingThisMonth && sentCalendar ? (
            <EmptyState
              icon={CalendarDays}
              title={`Nothing in ${monthLabel(cursor.year, cursor.month)}`}
              description="Days with sends are shaded; days with follow-ups scheduled are outlined."
            />
          ) : null}

          {selected ? (
            // Keyed by the date so the tab resets to Due each time another day
            // is opened — a remount does it, with no effect to keep in sync.
            <DayPanel
              key={selected}
              date={selected}
              due={dueOnSelected}
              overdue={selectedFacts?.overdue ?? false}
              emails={emails}
              loading={dayFetching}
              timezone={timezone}
              onRead={setReading}
              onSend={(contactId, templateId) => setSendTarget({ contactId, templateId })}
            />
          ) : null}
        </CardBody>
      </Card>

      <Dialog open={reading !== null} onOpenChange={(open) => !open && setReading(null)}>
        <DialogContent
          title={reading?.subject ?? 'Sent email'}
          description={
            reading
              ? `To ${reading.contactEmail} · ${formatDateTime(reading.sentAt, timezone)}`
              : undefined
          }
        >
          <DialogBody className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={SEND_STATUS_TONE[reading?.status ?? ''] ?? 'muted'}>
                {(reading?.status ?? '').replace('_', ' ')}
              </Badge>
              {reading?.templateName ? (
                <span className="text-xs text-muted-foreground">{reading.templateName}</span>
              ) : null}
              {reading?.error ? <span className="text-xs text-danger">{reading.error}</span> : null}
            </div>
            {/* The body is plain text by design — show it as it was sent. */}
            <pre className="max-h-[50vh] overflow-y-auto rounded-[var(--radius-md)] border border-border bg-surface p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
              {reading?.body}
            </pre>
            {reading?.gmailMessageId ? (
              <p className="font-mono text-caption text-muted-foreground">
                Gmail id {reading.gmailMessageId}
              </p>
            ) : null}
          </DialogBody>
        </DialogContent>
      </Dialog>

      {sendContact ? (
        <SendModal
          contact={sendContact}
          open={Boolean(sendTarget && sendContact)}
          onOpenChange={(open) => {
            if (!open) setSendTarget(null);
          }}
          initialTemplateId={sendTarget?.templateId}
        />
      ) : null}
    </>
  );
}
