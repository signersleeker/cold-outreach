import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useContact, useFollowUpCalendar } from '@/hooks';
import type { CalendarDay } from '@/lib/api';
import { cn } from '@/lib/utils';
import { SendModal } from './SendModal';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardBody, CardHeader, CardTitle } from './ui/card';
import { Dialog, DialogBody, DialogContent } from './ui/dialog';
import { Skeleton } from './ui/skeleton';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function parseYmd(value: string): { year: number; month: number; day: number } {
  const [year, month, day] = value.split('-').map(Number);
  return { year, month, day };
}

function monthLabel(year: number, month: number): string {
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString('en-AU', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

function mondayOffset(year: number, month: number): number {
  const weekday = new Date(Date.UTC(year, month - 1, 1)).getUTCDay();
  return (weekday + 6) % 7;
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

export function FollowUpCalendar() {
  const todayParts = useMemo(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  }, []);
  const [cursor, setCursor] = useState(todayParts);
  const { data, isLoading } = useFollowUpCalendar(cursor.year, cursor.month);
  const [dayOpen, setDayOpen] = useState<CalendarDay | null>(null);
  const [sendTarget, setSendTarget] = useState<{
    contactId: string;
    templateId: string;
  } | null>(null);
  const { data: sendContact } = useContact(sendTarget?.contactId ?? '');

  const today = data?.today ?? null;
  const dayMap = useMemo(() => {
    const map = new Map<string, CalendarDay>();
    for (const day of data?.days ?? []) map.set(day.date, day);
    return map;
  }, [data]);

  const leading = mondayOffset(cursor.year, cursor.month);
  const totalDays = daysInMonth(cursor.year, cursor.month);
  const cells: Array<{ date: string | null; dayNum: number | null }> = [];
  for (let i = 0; i < leading; i++) cells.push({ date: null, dayNum: null });
  for (let day = 1; day <= totalDays; day++) {
    const date = `${cursor.year}-${String(cursor.month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    cells.push({ date, dayNum: day });
  }
  while (cells.length % 7 !== 0) cells.push({ date: null, dayNum: null });

  function shiftMonth(delta: number) {
    setCursor((current) => {
      const date = new Date(Date.UTC(current.year, current.month - 1 + delta, 1));
      return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1 };
    });
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Follow-up calendar</CardTitle>
          <div className="flex items-center gap-2">
            <Button size="icon" variant="ghost" onClick={() => shiftMonth(-1)} title="Previous month">
              <ChevronLeft />
            </Button>
            <span className="min-w-[9rem] text-center font-mono text-xs tracking-wide text-muted-foreground uppercase">
              {monthLabel(cursor.year, cursor.month)}
            </span>
            <Button size="icon" variant="ghost" onClick={() => shiftMonth(1)} title="Next month">
              <ChevronRight />
            </Button>
          </div>
        </CardHeader>
        <CardBody className="space-y-3">
          {data ? (
            <p className="text-xs text-muted-foreground">
              {data.today}. {data.sendsToday}/{data.dailyCap} sent today, {data.remaining} left
              {data.overdueTotal > 0 ? (
                <span className="text-warning">
                  {' '}
                  · {data.overdueTotal} overdue from earlier days
                </span>
              ) : null}
              . Cap timezone {data.timezone}. Click a day to see who is due.
            </p>
          ) : null}

          {isLoading && !data ? (
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
                  const day = dayMap.get(cell.date);
                  const count = day?.items.length ?? 0;
                  const isToday = today === cell.date;
                  const hasDue = count > 0;
                  return (
                    <button
                      key={cell.date}
                      type="button"
                      disabled={!hasDue}
                      onClick={() => day && setDayOpen(day)}
                      className={cn(
                        'flex min-h-20 flex-col gap-1 bg-card p-2 text-left transition-colors',
                        isToday && 'ring-1 ring-inset ring-primary',
                        hasDue ? 'hover:bg-accent' : 'cursor-default',
                      )}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span
                          className={cn(
                            'font-mono text-xs',
                            isToday ? 'font-semibold text-primary' : 'text-muted-foreground',
                          )}
                        >
                          {cell.dayNum}
                        </span>
                        {isToday && day && day.overdueCount > 0 ? (
                          <Badge tone="warning" title="Overdue from earlier days">
                            {day.overdueCount} overdue
                          </Badge>
                        ) : null}
                      </div>
                      {hasDue ? (
                        <span className="mt-auto text-sm font-medium tabular-nums">
                          {count} due
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      <Dialog open={dayOpen !== null} onOpenChange={(open) => !open && setDayOpen(null)}>
        <DialogContent
          title={
            dayOpen
              ? `Due ${parseYmd(dayOpen.date).day} ${monthLabel(parseYmd(dayOpen.date).year, parseYmd(dayOpen.date).month)}`
              : 'Due'
          }
          description={`${dayOpen?.items.length ?? 0} to send`}
        >
          <DialogBody>
            <ul className="divide-y divide-border">
              {(dayOpen?.items ?? []).map((item) => (
                <li key={item.stepId} className="flex items-center gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {item.contactName || item.contactEmail}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      Step {item.position + 1}/{item.stepCount} · {item.templateName}
                      {item.company ? ` · ${item.company}` : ''}
                      {item.pastCap ? " · past today's cap" : ''}
                      {item.overdue ? ' · overdue' : ''}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    onClick={() =>
                      setSendTarget({
                        contactId: item.contactId,
                        templateId: item.templateId,
                      })
                    }
                  >
                    Send
                  </Button>
                </li>
              ))}
            </ul>
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
