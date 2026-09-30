import { Inbox, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ErrorBanner, PageBody, PageHeader } from '@/components/AppLayout';
import { FollowUpCalendar } from '@/components/FollowUpCalendar';
import { SendActivityChart } from '@/components/charts/SendActivityChart';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { Card, CardBody, CardHeader, CardTitle, StatTile } from '@/components/ui/card';
import { Skeleton, StatSkeleton } from '@/components/ui/skeleton';
import { useDashboard, useSendActivity, useSyncInbox } from '@/hooks';
import { formatDateTime, formatRelative, plural } from '@/lib/format';
import { SUPPRESSION_REASON_LABELS } from '@/lib/gates';

function DashboardSkeleton() {
  return (
    <PageBody>
      <StatSkeleton />
      <div className="grid gap-4 lg:grid-cols-2">
        {[0, 1].map((i) => (
          <Card key={i} className="p-4">
            <Skeleton className="h-3.5 w-28" />
            <div className="mt-4 space-y-2.5">
              <Skeleton className="h-3 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          </Card>
        ))}
      </div>
    </PageBody>
  );
}

export function DashboardPage() {
  const { data, isLoading, error } = useDashboard();
  const { data: activity } = useSendActivity(30);
  const sync = useSyncInbox();

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

  const remaining = Math.max(0, data.dailyCap - data.sendsToday);
  const capTone =
    data.sendsToday >= data.dailyCap ? 'danger' : remaining <= 3 ? 'warning' : 'default';

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={`Today ${data.today} (${data.timezone}). The cap resets at midnight in that timezone.`}
        actions={
          <Button
            variant="outline"
            disabled={!data.gmailConnected || sync.isPending}
            onClick={() => sync.mutate()}
            title={data.gmailConnected ? 'Check for replies and bounces' : 'Connect Gmail first'}
          >
            <RefreshCw className={sync.isPending ? 'animate-spin' : ''} />
            {sync.isPending ? 'Syncing…' : 'Sync inbox'}
          </Button>
        }
      />

      <PageBody>
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

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Sent today"
            value={`${data.sendsToday}/${data.dailyCap}`}
            hint={`${plural(remaining, 'send')} left`}
            tone={capTone}
          />
          <StatTile
            label="Ready to send"
            value={data.contactsReady}
            hint={`${data.contactsTotal} contacts total`}
          />
          <StatTile
            label="Suppressed"
            value={data.suppressionsTotal}
            hint="permanent, never re-sent"
            tone={data.suppressionsTotal > 0 ? 'warning' : 'default'}
          />
          <StatTile
            label="Bounced"
            value={data.bouncedCount}
            hint="hard bounces recorded"
            tone={data.bouncedCount > 0 ? 'danger' : 'default'}
          />
        </div>

        <FollowUpCalendar />

        <Card>
          <CardHeader>
            <CardTitle>Sending activity</CardTitle>
            <span className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
              last 30 days
            </span>
          </CardHeader>
          <CardBody>
            {activity ? (
              <SendActivityChart activity={activity} />
            ) : (
              <Skeleton className="h-36 w-full" />
            )}
          </CardBody>
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Last send</CardTitle>
              <Badge tone={data.gmailConnected ? 'success' : 'danger'}>
                {data.gmailConnected ? data.gmailEmail : 'not connected'}
              </Badge>
            </CardHeader>
            <CardBody className="space-y-1.5 text-xs">
              {data.lastSend ? (
                <>
                  <p className="font-mono text-foreground">{data.lastSend.email}</p>
                  <p className="text-muted-foreground">{data.lastSend.subject}</p>
                  <p className="text-muted-foreground">
                    {formatDateTime(data.lastSend.sentAt)} ({formatRelative(data.lastSend.sentAt)})
                  </p>
                </>
              ) : (
                <p className="text-muted-foreground">Nothing sent yet.</p>
              )}
              <p className="border-t border-border pt-2.5 text-muted-foreground">
                Inbox last synced {formatRelative(data.lastInboxSyncAt)}.
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>List health</CardTitle>
            </CardHeader>
            <CardBody className="space-y-2 text-xs">
              {[
                ['Valid, unsent', data.contactsReady],
                ['Risky', data.contactsRisky],
                ['Invalid', data.contactsInvalid],
                ['Not yet validated', data.contactsPending],
              ].map(([label, count]) => (
                <div key={String(label)} className="flex items-center justify-between">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-mono tabular-nums">{count}</span>
                </div>
              ))}
              {Object.keys(data.suppressionsByReason).length > 0 ? (
                <div className="mt-1 space-y-2 border-t border-border pt-2.5">
                  {Object.entries(data.suppressionsByReason).map(([reason, count]) => (
                    <div key={reason} className="flex items-center justify-between">
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
        </div>
      </PageBody>
    </>
  );
}
