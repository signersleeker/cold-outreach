import { Send } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { ErrorBanner } from '@/components/AppLayout';
import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogBody, DialogContent, DialogFooter } from '@/components/ui/dialog';
import { useApplyGroupAssignment, useGroupAssignmentPreview } from '@/hooks';
import type { AssignmentContact, GateFinding, GroupAssignmentTarget } from '@/lib/api';
import { plural } from '@/lib/format';
import { gateLabel } from '@/lib/gates';

function findingText(findings: GateFinding[]): string {
  return [...new Set(findings.map((finding) => finding.message))].join(' ');
}

function rowReasons(row: AssignmentContact): string {
  return findingText([...row.blockers, ...row.warnings]);
}

export function BulkSequenceDialog({
  open,
  onOpenChange,
  groupId,
  target,
  onStarted,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groupId: string;
  target: GroupAssignmentTarget;
  onStarted: () => void;
}) {
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const start = useApplyGroupAssignment();
  const previewQuery = useGroupAssignmentPreview(
    { ...target, groupId, acknowledge: acknowledged },
    open && !!groupId && !start.data,
  );
  const preview = previewQuery.data;

  useEffect(() => {
    setAcknowledged([]);
    start.reset();
    // Clear on open and on close so an acknowledgement never leaks into the next batch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const ackCodes = useMemo(() => {
    if (!preview) return [];
    const seen = new Map<string, string>();
    for (const row of [...preview.blocked, ...preview.sendable, ...preview.warnings]) {
      for (const warning of row.warnings) {
        if (warning.requiresAck && !seen.has(warning.code)) {
          seen.set(warning.code, warning.message);
        }
      }
    }
    return [...seen].map(([code, message]) => ({ code, message }));
  }, [preview]);

  const canConfirm =
    !!preview &&
    preview.willSend > 0 &&
    !previewQuery.isFetching &&
    !start.isPending &&
    !start.data;

  function confirm() {
    if (!preview) return;
    start.mutate(
      {
        groupId,
        contactIds: preview.sendable.map((row) => row.contactId),
        acknowledge: acknowledged,
      },
      { onSuccess: () => onStarted() },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Start sequence"
        description={
          preview
            ? `Email 1 of ${preview.groupName}: ${preview.templateName}. Later steps are not sent.`
            : 'Checking who can receive email 1.'
        }
      >
        <DialogBody className="space-y-3">
          {previewQuery.isLoading ? (
            <p className="text-xs text-muted-foreground">Checking contacts…</p>
          ) : null}
          <ErrorBanner error={previewQuery.error ?? start.error} />

          {start.data ? (
            <div className="space-y-3">
              <Callout tone={start.data.failed.length > 0 ? 'warning' : 'success'}>
                {plural(start.data.sent, 'email')} sent.
                {start.data.skipped.length > 0
                  ? ` ${plural(start.data.skipped.length, 'contact')} not sent.`
                  : ''}
                {start.data.failed.length > 0
                  ? ` ${plural(start.data.failed.length, 'send')} failed.`
                  : ''}
              </Callout>
              <ContactIssues title="Not sent" rows={start.data.skipped} />
              <ContactIssues title="Failed" rows={start.data.failed} />
            </div>
          ) : preview ? (
            <>
              <p className="text-sm font-medium">
                {plural(preview.willSend, 'email')} will be sent now.
              </p>
              <p className="font-mono text-xs text-muted-foreground">
                {preview.sendsToday}/{preview.dailyCap} sent today
              </p>

              {ackCodes.map((warning) => (
                <label
                  key={warning.code}
                  className="flex cursor-pointer items-start gap-2.5 rounded-[var(--radius-md)] border border-warning/30 bg-warning-subtle/40 px-3 py-2.5 text-xs"
                >
                  <Checkbox
                    checked={acknowledged.includes(warning.code)}
                    onCheckedChange={(checked) =>
                      setAcknowledged((current) =>
                        checked === true
                          ? [...new Set([...current, warning.code])]
                          : current.filter((code) => code !== warning.code),
                      )
                    }
                  />
                  <span>
                    Send anyway — I accept the <strong>{gateLabel(warning.code)}</strong> warning.
                  </span>
                </label>
              ))}

              <ContactIssues title="Won't be sent" rows={preview.blocked} />

              {preview.warnings.length > 0 ? (
                <div className="space-y-1.5">
                  <p className="text-xs font-medium">These will still be sent</p>
                  <ul className="max-h-40 space-y-1.5 overflow-y-auto text-xs">
                    {preview.warnings.map((row) => (
                      <li key={row.contactId}>
                        <span className="font-mono">{row.email}</span>
                        <span className="text-muted-foreground"> — {findingText(row.warnings)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : null}
        </DialogBody>
        <DialogFooter>
          <span />
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {start.data ? 'Close' : 'Cancel'}
            </Button>
            {start.data ? null : (
              <Button disabled={!canConfirm} onClick={confirm}>
                <Send />
                {start.isPending ? 'Sending…' : 'Send now'}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ContactIssues({ title, rows }: { title: string; rows: AssignmentContact[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium">
        {title} ({rows.length})
      </p>
      <ul className="max-h-48 space-y-1.5 overflow-y-auto text-xs">
        {rows.map((row) => (
          <li key={row.contactId}>
            <span className="font-mono">{row.email || 'Unknown contact'}</span>
            {row.name ? <span className="text-muted-foreground"> {row.name}</span> : null}
            <span className="text-muted-foreground"> — {rowReasons(row)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
