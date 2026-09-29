import { RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ErrorBanner, PageHeader } from '@/components/AppLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardBody, CardHeader, CardTitle, StatTile } from '@/components/ui/card';
import { useDashboard, useSyncInbox } from '@/hooks';
import { formatDateTime, formatRelative, plural } from '@/lib/format';
import { SUPPRESSION_REASON_LABELS } from '@/lib/gates';

export function DashboardPage() {
  const { data, isLoading, error } = useDashboard();
  const sync = useSyncInbox();

  if (isLoading) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <p className="px-6 py-4 text-xs text-muted-foreground">Loading…</p>
      </>
    );
  }
  if (!data) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <div className="px-6 py-4">
          <ErrorBanner error={error} />
        </div>
      </>
    );
  }

  const remaining = Math.max(0, data.dailyCap - data.sendsToday);
  const capTone = data.sendsToday >= data.dailyCap ? 'danger' : remaining <= 3 ? 'warning' : 'default';

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={`Brisbane date ${data.brisbaneDate}. The cap resets at midnight Brisbane time.`}
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

      <div className="space-y-4 px-6 py-4">
        <ErrorBanner error={sync.error} />

        {sync.data ? (
          <div className="rounded-[var(--radius-sm)] border bg-muted/40 px-3 py-2 text-xs">
            Scanned {plural(sync.data.scanned, 'message')} — {sync.data.stopsFound} stop
            {sync.data.stopsFound === 1 ? '' : 's'}, {sync.data.bouncesFound} hard bounce
            {sync.data.bouncesFound === 1 ? '' : 's'}, {sync.data.softBounces} soft bounce
            {sync.data.softBounces === 1 ? '' : 's'} (not suppressed), {sync.data.autoReplies}{' '}
            auto-reply{sync.data.autoReplies === 1 ? '' : 's'}. Suppressed{' '}
            {sync.data.suppressed}.
            {sync.data.errors.length > 0 ? (
              <span className="text-danger"> {sync.data.errors.length} error(s).</span>
            ) : null}
          </div>
        ) : null}

        {!data.gmailConnected ? (
          <div className="rounded-[var(--radius-sm)] border border-warning/30 bg-warning-subtle px-3 py-2 text-xs text-warning">
            No Gmail mailbox connected — nothing can be sent.{' '}
            <Link to="/settings" className="font-semibold underline">
              Connect one in Settings
            </Link>
            .
          </div>
        ) : null}

        {!data.identityComplete ? (
          <div className="rounded-[var(--radius-sm)] border border-warning/30 bg-warning-subtle px-3 py-2 text-xs text-warning">
            Legal company name or From address is missing.{' '}
            <Link to="/settings" className="font-semibold underline">
              Check Settings
            </Link>{' '}
            — every send is blocked until both are set (From comes from Gmail).
          </div>
        ) : null}

        {data.stuckQueuedCount > 0 ? (
          <div className="rounded-[var(--radius-sm)] border border-danger/30 bg-danger-subtle px-3 py-2 text-xs text-danger">
            {plural(data.stuckQueuedCount, 'send')} stuck in <code>queued</code> — the outcome was
            never confirmed. Check your Gmail Sent folder, or run{' '}
            <code className="font-mono">nx reconcile api</code>.
          </div>
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

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Last send</CardTitle>
              <Badge tone={data.gmailConnected ? 'success' : 'danger'}>
                {data.gmailConnected ? data.gmailEmail : 'not connected'}
              </Badge>
            </CardHeader>
            <CardBody className="space-y-1 text-xs">
              {data.lastSend ? (
                <>
                  <p className="font-mono">{data.lastSend.email}</p>
                  <p className="text-muted-foreground">{data.lastSend.subject}</p>
                  <p className="text-muted-foreground">
                    {formatDateTime(data.lastSend.sentAt)} ({formatRelative(data.lastSend.sentAt)})
                  </p>
                </>
              ) : (
                <p className="text-muted-foreground">Nothing sent yet.</p>
              )}
              <p className="pt-2 text-muted-foreground">
                Inbox last synced {formatRelative(data.lastInboxSyncAt)}.
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>List health</CardTitle>
            </CardHeader>
            <CardBody className="space-y-1.5 text-xs">
              {[
                ['Valid, unsent', data.contactsReady],
                ['Risky', data.contactsRisky],
                ['Invalid', data.contactsInvalid],
                ['Not yet validated', data.contactsPending],
              ].map(([label, count]) => (
                <div key={String(label)} className="flex items-center justify-between">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-mono">{count}</span>
                </div>
              ))}
              {Object.keys(data.suppressionsByReason).length > 0 ? (
                <div className="mt-2 border-t pt-2">
                  {Object.entries(data.suppressionsByReason).map(([reason, count]) => (
                    <div key={reason} className="flex items-center justify-between">
                      <span className="text-muted-foreground">
                        {SUPPRESSION_REASON_LABELS[reason] ?? reason}
                      </span>
                      <span className="font-mono">{count}</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}
