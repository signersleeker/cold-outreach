import { AlertTriangle, Ban, Send } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useSend, useSendPreview, useTemplates } from '@/hooks';
import type { Contact, GateFinding } from '@/lib/api';
import { fullName } from '@/lib/format';
import { gateLabel } from '@/lib/gates';
import { ErrorBanner } from './AppLayout';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';
import { Dialog, DialogBody, DialogContent, DialogFooter } from './ui/dialog';
import { Label } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

function GateList({ findings, tone }: { findings: GateFinding[]; tone: 'danger' | 'warning' }) {
  if (findings.length === 0) return null;
  const Icon = tone === 'danger' ? Ban : AlertTriangle;
  return (
    <ul className="space-y-1">
      {findings.map((finding) => (
        <li
          key={finding.code}
          className={
            tone === 'danger'
              ? 'flex items-start gap-2 rounded-[var(--radius-sm)] bg-danger-subtle px-2.5 py-1.5 text-xs text-danger'
              : 'flex items-start gap-2 rounded-[var(--radius-sm)] bg-warning-subtle px-2.5 py-1.5 text-xs text-warning'
          }
        >
          <Icon className="mt-px size-3.5 shrink-0" />
          <span>
            <strong className="font-semibold">{gateLabel(finding.code)}</strong> — {finding.message}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function SendModal({
  contact,
  open,
  onOpenChange,
}: {
  contact: Contact;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: templates } = useTemplates();
  const [templateId, setTemplateId] = useState('');
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const send = useSend();

  const list = templates?.data ?? [];

  useEffect(() => {
    if (!templateId && list.length > 0) setTemplateId(list[0].id);
  }, [list, templateId]);

  // Reset per-open so an acknowledgement never leaks between contacts.
  useEffect(() => {
    if (open) {
      setAcknowledged([]);
      send.reset();
    }
  }, [open]);

  const preview = useSendPreview(contact.id, templateId, acknowledged);
  const data = preview.data;

  const pendingAcks = useMemo(
    () => (data?.warnings ?? []).filter((w) => w.requiresAck),
    [data],
  );
  const allAcknowledged = pendingAcks.every((w) => acknowledged.includes(w.code));

  const toggleAck = (code: string, checked: boolean) =>
    setAcknowledged((current) =>
      checked ? [...new Set([...current, code])] : current.filter((c) => c !== code),
    );

  const canSend = Boolean(data?.sendable) && allAcknowledged && !send.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={`Send to ${fullName(contact) || contact.email}`}
        description={contact.email}
      >
        <DialogBody className="space-y-4">
          <div className="flex flex-col gap-1">
            <Label>Template</Label>
            <Select value={templateId} onValueChange={setTemplateId}>
              <SelectTrigger>
                <SelectValue placeholder="Choose a template" />
              </SelectTrigger>
              <SelectContent>
                {list.map((template) => (
                  <SelectItem key={template.id} value={template.id}>
                    {template.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {preview.isLoading ? (
            <p className="text-xs text-muted-foreground">Building preview…</p>
          ) : null}
          <ErrorBanner error={preview.error} />

          {data ? (
            <>
              <div className="space-y-2">
                <GateList findings={data.blockers} tone="danger" />
                <GateList findings={data.warnings} tone="warning" />
                {data.blockers.length === 0 && data.warnings.length === 0 ? (
                  <p className="rounded-[var(--radius-sm)] bg-success-subtle px-2.5 py-1.5 text-xs text-success">
                    All gates pass.
                  </p>
                ) : null}
              </div>

              {pendingAcks.map((warning) => (
                <label
                  key={warning.code}
                  className="flex cursor-pointer items-start gap-2 rounded-[var(--radius-sm)] border border-warning/30 px-2.5 py-2 text-xs"
                >
                  <Checkbox
                    checked={acknowledged.includes(warning.code)}
                    onCheckedChange={(checked) => toggleAck(warning.code, checked === true)}
                  />
                  <span>
                    Send anyway — I accept the <strong>{gateLabel(warning.code)}</strong> warning.
                  </span>
                </label>
              ))}

              <div className="space-y-1.5">
                <div className="flex items-baseline justify-between">
                  <Label>Exactly what will be sent</Label>
                  <span className="font-mono text-xs text-muted-foreground">
                    from {data.fromEmail || '—'}
                  </span>
                </div>
                <div className="rounded-[var(--radius-sm)] border bg-muted/40">
                  <p className="border-b px-3 py-2 font-mono text-xs">
                    <span className="text-muted-foreground">Subject: </span>
                    {data.subject || <em className="text-danger">empty</em>}
                  </p>
                  <pre className="max-h-40 overflow-y-auto border-b px-3 py-2 font-mono text-xs whitespace-pre-wrap">
                    {data.body}
                  </pre>
                  {data.signatureHtml ? (
                    <div className="space-y-1 px-3 py-2">
                      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                        Gmail signature (HTML)
                      </p>
                      <iframe
                        title="Signature preview"
                        sandbox=""
                        srcDoc={`<!DOCTYPE html><html><body style="margin:0;font:13px/1.4 system-ui,sans-serif">${data.signatureHtml}</body></html>`}
                        className="h-28 w-full rounded-[var(--radius-sm)] border bg-white"
                      />
                    </div>
                  ) : null}
                </div>
                <p className="text-xs text-muted-foreground">
                  The body is plain text. The Gmail HTML signature, opt-out sentence, and
                  unsubscribe line are included above.
                </p>
              </div>
            </>
          ) : null}

          <ErrorBanner error={send.error} />
        </DialogBody>

        <DialogFooter>
          <span className="font-mono text-xs text-muted-foreground">
            {data ? `${data.sendsToday}/${data.dailyCap} sent today (Brisbane)` : ''}
          </span>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              disabled={!canSend}
              onClick={() =>
                send.mutate(
                  { contactId: contact.id, templateId, acknowledge: acknowledged },
                  { onSuccess: () => onOpenChange(false) },
                )
              }
            >
              <Send className="size-4" />
              {send.isPending ? 'Sending…' : 'Send'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ValidationBadge({ contact }: { contact: Contact }) {
  if (contact.suppressed) {
    return <Badge tone="danger">suppressed</Badge>;
  }
  const tone = (
    { valid: 'success', risky: 'warning', unknown: 'warning', pending: 'muted', invalid: 'danger' } as const
  )[contact.validationStatus];
  return (
    <Badge tone={tone} title={contact.validationDetail}>
      {contact.validationStatus}
    </Badge>
  );
}
