import { AlertTriangle, Ban, Send } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  useContactFollowUp,
  useEnrollFollowUp,
  useSend,
  useSendHistory,
  useSendPreview,
  useTemplateGroups,
  useTemplates,
} from '@/hooks';
import type { Contact, GateFinding } from '@/lib/api';
import { fullName } from '@/lib/format';
import { gateLabel } from '@/lib/gates';
import { cn } from '@/lib/utils';
import { ErrorBanner } from './AppLayout';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Callout } from './ui/callout';
import { Checkbox } from './ui/checkbox';
import { Dialog, DialogBody, DialogContent, DialogFooter } from './ui/dialog';
import { Label } from './ui/input';
import { Segmented } from './ui/segmented';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

function GateList({ findings, tone }: { findings: GateFinding[]; tone: 'danger' | 'warning' }) {
  if (findings.length === 0) return null;
  const Icon = tone === 'danger' ? Ban : AlertTriangle;
  return (
    <ul className="space-y-1.5">
      {findings.map((finding) => (
        <li key={finding.code}>
          <Callout tone={tone} icon={Icon} className="py-2">
            <strong className="font-semibold">{gateLabel(finding.code)}</strong> — {finding.message}
          </Callout>
        </li>
      ))}
    </ul>
  );
}

export function SendModal({
  contact,
  open,
  onOpenChange,
  initialTemplateId,
}: {
  contact: Contact;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialTemplateId?: string;
}) {
  const { data: templates } = useTemplates();
  const { data: groupsData } = useTemplateGroups();
  const { data: history } = useSendHistory(contact.id, open);
  const { data: activePlan } = useContactFollowUp(contact.id);
  const [mode, setMode] = useState<'template' | 'group'>('template');
  const [groupId, setGroupId] = useState('');
  const [templateId, setTemplateId] = useState(initialTemplateId ?? '');
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const send = useSend();
  const enroll = useEnrollFollowUp();

  const list = templates?.data ?? [];
  const groups = groupsData?.data ?? [];
  const selectedGroup = groups.find((group) => group.id === groupId) ?? null;
  const selectedTemplate = list.find((template) => template.id === templateId) ?? null;

  const sentTemplateIds = useMemo(() => {
    const ids = new Set<string>();
    for (const event of history?.data ?? []) {
      if (event.status === 'sent' && event.templateId) ids.add(event.templateId);
    }
    return ids;
  }, [history]);

  useEffect(() => {
    if (open && initialTemplateId) {
      setMode('template');
      setTemplateId(initialTemplateId);
    }
  }, [open, initialTemplateId]);

  useEffect(() => {
    if (!templateId && list.length > 0 && mode === 'template') setTemplateId(list[0].id);
  }, [list, templateId, mode]);

  useEffect(() => {
    if (mode === 'group' && !groupId && groups[0]) setGroupId(groups[0].id);
  }, [mode, groupId, groups]);

  useEffect(() => {
    if (mode !== 'group' || !selectedGroup) return;
    const first = selectedGroup.items[0]?.templateId ?? '';
    if (templateId !== first) setTemplateId(first);
  }, [mode, selectedGroup, templateId]);

  // Reset per-open so an acknowledgement never leaks between contacts.
  useEffect(() => {
    if (open) {
      setAcknowledged([]);
      if (!initialTemplateId) setMode('template');
      send.reset();
      enroll.reset();
    }
  }, [open]);

  useEffect(() => {
    setAcknowledged([]);
  }, [templateId]);

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

  const canSend = Boolean(data?.sendable) && allAcknowledged && !send.isPending && !enroll.isPending;

  async function startSequence() {
    if (!selectedGroup || !templateId) return;
    const enrollment = await enroll.mutateAsync({
      contactId: contact.id,
      groupId: selectedGroup.id,
    });
    const first = enrollment.steps[0];
    if (!first) return;
    await send.mutateAsync({
      contactId: contact.id,
      templateId: first.templateId,
      acknowledge: acknowledged,
    });
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={`Send to ${fullName(contact) || contact.email}`}
        description={contact.email}
      >
        <DialogBody className="space-y-4">
          {contact.companyIndustry ? (
            <p className="text-xs text-muted-foreground">
              Company industry:{' '}
              <span className="font-medium text-foreground">{contact.companyIndustry}</span>
            </p>
          ) : null}

          {activePlan && mode === 'template' ? (
            <Callout tone="neutral">
              Active plan: {activePlan.groupName}
              {activePlan.nextStep
                ? ` — next is step ${activePlan.nextStep.position + 1} (${activePlan.nextStep.templateName})`
                : ''}
            </Callout>
          ) : null}

          <Segmented
            aria-label="Pick from a single template or a group"
            value={mode}
            onChange={(next) => {
              setMode(next);
              if (next === 'group' && !groupId && groups[0]) setGroupId(groups[0].id);
            }}
            options={[
              { value: 'template', label: 'Template' },
              { value: 'group', label: 'Group' },
            ]}
          />

          {mode === 'template' ? (
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
                      {template.industry ? ` · ${template.industry}` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex flex-col gap-1">
                <Label>Group</Label>
                {groups.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No groups yet. Create one on the Templates page.
                  </p>
                ) : groupId ? (
                  <Select value={groupId} onValueChange={setGroupId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a group" />
                    </SelectTrigger>
                    <SelectContent>
                      {groups.map((group) => (
                        <SelectItem key={group.id} value={group.id}>
                          {group.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : null}
              </div>
              {selectedGroup ? (
                <>
                  <Callout tone="neutral">
                    Starting this group assigns the plan and sends email 1 now. Later steps appear
                    on the dashboard calendar when they are due.
                  </Callout>
                  <ol className="space-y-1">
                    {selectedGroup.items.map((item, index) => (
                      <li
                        key={item.templateId}
                        className={cn(
                          'flex w-full items-center gap-2 rounded-[var(--radius-md)] border px-2.5 py-2 text-sm',
                          index === 0
                            ? 'border-primary bg-accent font-medium text-accent-foreground'
                            : 'border-border',
                        )}
                      >
                        <span className="w-5 font-mono text-xs text-muted-foreground">
                          {index + 1}
                        </span>
                        <span className="min-w-0 flex-1 truncate">
                          {item.templateName}
                          {item.industry ? (
                            <span className="ml-2 text-xs text-muted-foreground">{item.industry}</span>
                          ) : null}
                        </span>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {index === 0 ? 'Now' : `+${item.delayDays}d`}
                        </span>
                        {sentTemplateIds.has(item.templateId) ? (
                          <Badge tone="muted">sent</Badge>
                        ) : null}
                      </li>
                    ))}
                  </ol>
                </>
              ) : null}
            </div>
          )}

          {selectedTemplate?.industry &&
          contact.companyIndustry &&
          selectedTemplate.industry !== contact.companyIndustry ? (
            <Callout tone="warning">
              This template is written for {selectedTemplate.industry}. This company is{' '}
              {contact.companyIndustry}.
            </Callout>
          ) : null}

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
                  <Callout tone="success" className="py-2">
                    All gates pass.
                  </Callout>
                ) : null}
              </div>

              {pendingAcks.map((warning) => (
                <label
                  key={warning.code}
                  className="flex cursor-pointer items-start gap-2.5 rounded-[var(--radius-md)] border border-warning/30 bg-warning-subtle/40 px-3 py-2.5 text-xs"
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
                <div className="overflow-hidden rounded-[var(--radius-md)] border border-border bg-surface">
                  <p className="border-b border-border px-3 py-2 font-mono text-xs">
                    <span className="text-muted-foreground">Subject: </span>
                    {data.subject || <em className="text-danger">empty</em>}
                  </p>
                  <pre className="max-h-40 overflow-y-auto border-b border-border bg-card px-3 py-2.5 font-mono text-xs whitespace-pre-wrap">
                    {data.body}
                  </pre>
                  {data.signatureHtml ? (
                    <div className="space-y-1 px-3 py-2">
                      <p className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
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
                  The copy above is plain text. A linked word is written out with its address
                  here, and is clickable in Gmail. The HTML signature, opt-out sentence, and
                  unsubscribe line are included.
                </p>
              </div>
            </>
          ) : null}

          <ErrorBanner error={send.error ?? enroll.error} />
        </DialogBody>

        <DialogFooter>
          <span className="font-mono text-xs text-muted-foreground">
            {data ? `${data.sendsToday}/${data.dailyCap} sent today` : ''}
          </span>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            {mode === 'group' ? (
              <Button
                disabled={!canSend || !selectedGroup}
                onClick={() => {
                  void startSequence().catch(() => undefined);
                }}
              >
                <Send className="size-4" />
                {send.isPending || enroll.isPending ? 'Starting…' : 'Start sequence'}
              </Button>
            ) : (
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
            )}
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
