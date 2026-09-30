import { Inbox, MailCheck, RefreshCw, ShieldBan, Users } from 'lucide-react';
import type * as React from 'react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorBanner, PageBody, PageHeader } from '@/components/AppLayout';
import { OutreachCalendar } from '@/components/OutreachCalendar';
import { StatTile } from '@/components/StatTile';
import { StreakBadge, TodayPanel } from '@/components/TodayPanel';
import { ListCompositionBar } from '@/components/charts/ListCompositionBar';
import { SendActivityChart } from '@/components/charts/SendActivityChart';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card';
import { Segmented } from '@/components/ui/segmented';
import { Skeleton, StatSkeleton } from '@/components/ui/skeleton';
import { useContactStats, useDashboard, useSendActivity, useSyncInbox } from '@/hooks';
import { formatDateTime, formatPct, formatRelative, plural } from '@/lib/format';
import { SUPPRESSION_REASON_LABELS } from '@/lib/gates';
import { deliverabilityTone, runwayDays, sendMetrics } from '@/lib/metrics';

/** The window the headline figures are read over. Fixed at 30 days on purpose:
 *  the chart's range toggle changes what you're looking at, not what the KPIs
 *  above it mean, so "vs prior 7 days" can't quietly become something else. */
const METRIC_WINDOW = 30;

const RANGES = [
  { value: '7', label: '7 days' },
  { value: '30', label: '30 days' },
  { value: '90', label: '90 days' },
] as const;

type Range = (typeof RANGES)[number]['value'];

/** A labelled band. The old page was six cards of identical weight, which is why
 *  it read as a wall; the rules give the eye somewhere to stop and say what the
 *  next group of cards is for. */
function Section({
  title,
  id,
  children,
}: {
  title: string;
  id?: string;
  children: React.ReactNode;
}) {
  return (
    // scroll-mt clears the sticky page header when the hero's links jump here.
    <section id={id} className="scroll-mt-20 space-y-3">
      <div className="flex items-center gap-3">
        <h2 className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
          {title}
        </h2>
        <span aria-hidden className="h-px flex-1 bg-border" />
      </div>
      {children}
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <PageBody className="space-y-5">
      <Skeleton className="h-44 w-full rounded-[var(--radius-lg)]" />
      <StatSkeleton />
      <Card className="p-4">
        <Skeleton className="h-3.5 w-28" />
        <Skeleton className="mt-4 h-36 w-full" />
      </Card>
    </PageBody>
  );
}

export function DashboardPage() {
  const { data, isLoading, error } = useDashboard();
  const [range, setRange] = useState<Range>('30');
  // The headline figures always read over METRIC_WINDOW; the chart follows the
  // toggle. Both go through the same cached query when they agree.
  const { data: metricActivity } = useSendActivity(METRIC_WINDOW);
  const { data: activity } = useSendActivity(Number(range));
  const { data: stats } = useContactStats();
  const sync = useSyncInbox();

  const metrics = metricActivity ? sendMetrics(metricActivity) : null;

  if (isLoading) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <DashboardSkeleton />
      </>
    );
  }
  if (!data) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <PageBody>
          <ErrorBanner error={error} />
        </PageBody>
      </>
    );
  }

  const runway = metrics ? runwayDays(data.contactsReady, metrics.pace) : null;
  const delivered = metrics?.deliveredRate ?? null;
  const suppressionReasons = Object.entries(data.suppressionsByReason);

  return (
    <>
      <PageHeader
        title="Dashboard"
        // The date, cap and timezone are the Today panel's job now — the header
        // just says whose mailbox this is.
        description={
          data.gmailConnected ? `Sending as ${data.gmailEmail}` : 'No mailbox connected yet'
        }
        actions={
          <>
            {metrics ? <StreakBadge streak={metrics.streak} /> : null}
            <Button
              variant="outline"
              disabled={!data.gmailConnected || sync.isPending}
              onClick={() => sync.mutate()}
              title={data.gmailConnected ? 'Check for replies and bounces' : 'Connect Gmail first'}
            >
              <RefreshCw className={sync.isPending ? 'animate-spin' : ''} />
              {sync.isPending ? 'Syncing…' : 'Sync inbox'}
            </Button>
          </>
        }
      />

      <PageBody className="space-y-5">
        <ErrorBanner error={sync.error} />

        {sync.data ? (
          <Callout tone="neutral" icon={Inbox} title="Inbox synced">
            <p>
              Scanned {plural(sync.data.scanned, 'message')} — {sync.data.stopsFound} stop
              {sync.data.stopsFound === 1 ? '' : 's'}, {sync.data.bouncesFound} hard bounce
              {sync.data.bouncesFound === 1 ? '' : 's'}, {sync.data.softBounces} soft bounce
              {sync.data.softBounces === 1 ? '' : 's'} (not suppressed), {sync.data.autoReplies}{' '}
              auto-reply{sync.data.autoReplies === 1 ? '' : 's'}. Suppressed {sync.data.suppressed}.
              {sync.data.errors.length > 0 ? (
                <span className="text-danger"> {sync.data.errors.length} error(s).</span>
              ) : null}
            </p>
          </Callout>
        ) : null}

        {!data.gmailConnected ? (
          <Callout tone="warning" title="No Gmail mailbox connected">
            Nothing can be sent. <Link to="/settings">Connect one in Settings</Link>.
          </Callout>
        ) : null}

        {!data.identityComplete ? (
          <Callout tone="warning" title="Sender identity incomplete">
            Legal company name or From address is missing. <Link to="/settings">Check Settings</Link>{' '}
            — every send is blocked until both are set (From comes from Gmail).
          </Callout>
        ) : null}

        {data.stuckQueuedCount > 0 ? (
          <Callout tone="danger" title={`${plural(data.stuckQueuedCount, 'send')} stuck in queued`}>
            The outcome was never confirmed. Check your Gmail Sent folder, or run{' '}
            <code className="rounded bg-danger/10 px-1 py-0.5 font-mono">nx reconcile api</code>.
          </Callout>
        ) : null}

        <TodayPanel dashboard={data} />

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Sent this week"
            value={metrics ? metrics.last7 : '—'}
            icon={MailCheck}
            delta={
              metrics
                ? { fraction: metrics.weekChange, label: 'vs the prior 7 days', goodWhen: 'up' }
                : undefined
            }
            trend={metrics?.trend}
            trendLabel="Daily sends, last 14 days"
            hint={
              metrics
                ? `${metrics.pace.toFixed(1)} a day on average · ${metrics.total} in ${METRIC_WINDOW} days`
                : undefined
            }
          />
          <StatTile
            label="Ready to send"
            value={data.contactsReady}
            icon={Users}
            to="/contacts?status=ready"
            hint={
              runway === null
                ? `${data.contactsTotal} contacts total`
                : runway < 1
                  ? // Rounding would say "about 0 days", which reads as a bug.
                    'under a day of pipeline at this pace'
                  : `about ${plural(Math.round(runway), 'day')} of pipeline at this pace`
            }
          />
          <StatTile
            label="Delivered clean"
            value={delivered === null ? '—' : formatPct(delivered)}
            tone={deliverabilityTone(delivered)}
            to="/suppressions"
            hint={
              delivered === null
                ? `nothing sent in the last ${METRIC_WINDOW} days`
                : `${plural(metrics?.bounced ?? 0, 'hard bounce')} in ${METRIC_WINDOW} days`
            }
          />
          <StatTile
            label="Suppressed"
            value={data.suppressionsTotal}
            icon={ShieldBan}
            to="/suppressions"
            hint="permanent — these addresses are never re-sent"
          />
        </div>

        <Section title="Momentum">
          <Card>
            <CardHeader className="flex-wrap">
              <CardTitle>Sending activity</CardTitle>
              <Segmented
                value={range}
                onChange={setRange}
                options={RANGES.map((option) => ({ ...option }))}
                aria-label="Activity range"
              />
            </CardHeader>
            <CardBody>
              {activity ? (
                <SendActivityChart activity={activity} />
              ) : (
                <Skeleton className="h-36 w-full" />
              )}
            </CardBody>
          </Card>
        </Section>

        <Section title="Pipeline">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>List health</CardTitle>
                <Link
                  to="/contacts"
                  className="text-xs font-semibold text-link hover:underline"
                >
                  All contacts
                </Link>
              </CardHeader>
              <CardBody className="space-y-3">
                {stats ? (
                  <ListCompositionBar stats={stats} />
                ) : (
                  <Skeleton className="h-2.5 w-full rounded-full" />
                )}

                {data.contactsInvalid > 0 || data.contactsPending > 0 ? (
                  <p className="text-xs text-muted-foreground">
                    {data.contactsInvalid > 0 ? (
                      <Link to="/contacts?status=invalid" className="font-semibold text-link hover:underline">
                        Fix or drop {plural(data.contactsInvalid, 'invalid address', 'invalid addresses')}
                      </Link>
                    ) : null}
                    {data.contactsInvalid > 0 && data.contactsPending > 0 ? ' · ' : null}
                    {data.contactsPending > 0 ? (
                      <Link to="/contacts?status=pending" className="font-semibold text-link hover:underline">
                        {plural(data.contactsPending, 'address', 'addresses')} still unvalidated
                      </Link>
                    ) : null}
                  </p>
                ) : null}

                {suppressionReasons.length > 0 ? (
                  <div className="space-y-2 border-t border-border pt-3">
                    <p className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
                      Why they were suppressed
                    </p>
                    {suppressionReasons.map(([reason, count]) => (
                      <div key={reason} className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">
                          {SUPPRESSION_REASON_LABELS[reason] ?? reason}
                        </span>
                        <span className="font-mono tabular-nums">{count}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Mailbox</CardTitle>
                <Badge tone={data.gmailConnected ? 'success' : 'danger'}>
                  {data.gmailConnected ? data.gmailEmail : 'not connected'}
                </Badge>
              </CardHeader>
              <CardBody className="space-y-3 text-xs">
                <div className="space-y-1.5">
                  <p className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
                    Last send
                  </p>
                  {data.lastSend ? (
                    <>
                      <p className="font-mono text-foreground">{data.lastSend.email}</p>
                      <p className="text-muted-foreground">{data.lastSend.subject}</p>
                      <p className="text-muted-foreground">
                        {formatDateTime(data.lastSend.sentAt, data.timezone)} (
                        {formatRelative(data.lastSend.sentAt)})
                      </p>
                    </>
                  ) : (
                    <p className="text-muted-foreground">Nothing sent yet.</p>
                  )}
                </div>
                <p className="border-t border-border pt-3 text-muted-foreground">
                  Inbox last synced {formatRelative(data.lastInboxSyncAt)} — replies and bounces are
                  only picked up when it runs.
                </p>
                {metrics && metrics.stopped > 0 ? (
                  <p className="text-muted-foreground">
                    {plural(metrics.stopped, 'person', 'people')} asked to stop in the last{' '}
                    {METRIC_WINDOW} days.
                  </p>
                ) : null}
              </CardBody>
            </Card>
          </div>
        </Section>

        {/* One grid for both halves of the timeline — sends behind, follow-ups
            ahead. The anchor is what the Today panel's links jump to. */}
        <Section title="Calendar" id="calendar">
          <OutreachCalendar />
        </Section>
      </PageBody>
    </>
  );
}
