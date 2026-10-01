import { ArrowLeft, RefreshCw, Send } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ErrorBanner, PageBody, PageHeader } from '@/components/AppLayout';
import { ContactFollowUpCard } from '@/components/ContactFollowUpCard';
import { DeleteContactDialog } from '@/components/DeleteContactDialog';
import { NotesCard } from '@/components/NotesCard';
import { SendModal, ValidationBadge } from '@/components/SendModal';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { Card, CardBody, CardHeader, CardTitle, EmptyState } from '@/components/ui/card';
import { Field, Input, Textarea } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableWrap, Td, Th, Tr } from '@/components/ui/table';
import { useContact, useRevalidateContact, useSendHistory, useUpdateContact } from '@/hooks';
import type { Contact } from '@/lib/api';
import { formatDateTime, fullName } from '@/lib/format';
import { SEND_STATUS_TONE, SUPPRESSION_REASON_LABELS } from '@/lib/gates';

type EditableField = 'firstName' | 'lastName' | 'title' | 'hook' | 'source' | 'notes';

const TEXT_FIELDS: { key: EditableField; label: string; hint?: string }[] = [
  { key: 'firstName', label: 'First name' },
  { key: 'lastName', label: 'Last name' },
  { key: 'title', label: 'Title' },
];

export function ContactDetailPage() {
  const { id = '' } = useParams();
  const { data: contact, isLoading, error } = useContact(id);
  const update = useUpdateContact();
  const revalidate = useRevalidateContact();
  const { data: history } = useSendHistory(id);
  const [draft, setDraft] = useState<Partial<Contact>>({});
  const [sendOpen, setSendOpen] = useState(false);
  const [sendTemplateId, setSendTemplateId] = useState<string | undefined>();

  useEffect(() => {
    setDraft({});
  }, [id]);

  if (isLoading) {
    return (
      <>
        <PageHeader title="Contact" />
        <PageBody className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <Card className="p-4">
            <Skeleton className="h-3.5 w-24" />
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-8" />
              ))}
            </div>
            <Skeleton className="mt-3 h-16" />
          </Card>
          <Card className="h-fit p-4">
            <Skeleton className="h-3.5 w-20" />
            <div className="mt-4 space-y-2.5">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-3" />
              ))}
            </div>
          </Card>
        </PageBody>
      </>
    );
  }
  if (!contact) {
    return (
      <>
        <PageHeader title="Contact" />
        <PageBody>
          <ErrorBanner error={error} />
        </PageBody>
      </>
    );
  }

  const value = (key: EditableField) => draft[key] ?? contact[key];
  const dirty = Object.keys(draft).length > 0;
  const events = history?.data ?? [];
  const historyLoaded = history !== undefined;
  const mailRecorded =
    contact.lastSentAt != null || events.some((event) => event.status !== 'failed');
  // Wait for send history before unlocking. An empty list while the query is
  // in flight would otherwise flash an editable field on a contact who has
  // already been emailed.
  const emailEditable = historyLoaded && !mailRecorded;

  return (
    <>
      <PageHeader
        title={fullName(contact) || contact.email}
        description={contact.email}
        actions={
          <>
            <Link to="/contacts" className={buttonVariants({ variant: 'ghost' })}>
              <ArrowLeft className="size-4" />
              Back
            </Link>
            <Button
              variant="outline"
              disabled={revalidate.isPending}
              onClick={() => revalidate.mutate(contact.id)}
            >
              <RefreshCw className={revalidate.isPending ? 'animate-spin' : ''} />
              Revalidate
            </Button>
            <Button disabled={contact.suppressed} onClick={() => setSendOpen(true)}>
              <Send />
              Send
            </Button>
            <DeleteContactDialog contact={contact} />
          </>
        }
      />

      <PageBody className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
              {dirty ? (
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setDraft({})}>
                    Discard
                  </Button>
                  <Button
                    size="sm"
                    disabled={update.isPending}
                    onClick={() =>
                      update.mutate(
                        { id: contact.id, changes: draft },
                        { onSuccess: () => setDraft({}) },
                      )
                    }
                  >
                    {update.isPending ? 'Saving…' : 'Save'}
                  </Button>
                </div>
              ) : null}
            </CardHeader>
            <CardBody className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  className="sm:col-span-2"
                  label="Email"
                  hint={
                    emailEditable
                      ? 'You can correct this until the first email is sent.'
                      : mailRecorded
                        ? 'An email has already been sent to this address.'
                        : undefined
                  }
                >
                  <Input
                    type="email"
                    autoComplete="off"
                    spellCheck={false}
                    disabled={!emailEditable}
                    value={emailEditable ? (draft.email ?? contact.email) : contact.email}
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, email: event.target.value }))
                    }
                  />
                </Field>
                {TEXT_FIELDS.map((field) => (
                  <Field key={field.key} label={field.label}>
                    <Input
                      value={value(field.key) as string}
                      onChange={(event) =>
                        setDraft((current) => ({ ...current, [field.key]: event.target.value }))
                      }
                    />
                  </Field>
                ))}
                <Field label="Company">
                  <div className="flex h-8 items-center rounded-[var(--radius-md)] border border-input bg-surface px-2.5 text-sm">
                    {contact.companyId && contact.company ? (
                      <Link
                        to={`/companies/${contact.companyId}`}
                        className="truncate font-medium text-foreground underline-offset-2 hover:underline"
                      >
                        {contact.company}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">No company</span>
                    )}
                  </div>
                </Field>
              </div>
              <Field
                label="Hook"
                hint="The one specific thing that makes this email worth sending."
              >
                <Textarea
                  rows={2}
                  value={value('hook') as string}
                  onChange={(event) => setDraft((c) => ({ ...c, hook: event.target.value }))}
                />
              </Field>
              <Field
                label="Source"
                hint="Where this address came from, ideally a URL. This is your Spam Act evidence trail."
              >
                <Input
                  value={value('source') as string}
                  onChange={(event) => setDraft((c) => ({ ...c, source: event.target.value }))}
                />
              </Field>
              <Field label="Notes" hint="Free text stored on this contact.">
                <Textarea
                  rows={3}
                  value={value('notes') as string}
                  onChange={(event) => setDraft((c) => ({ ...c, notes: event.target.value }))}
                />
              </Field>
              <ErrorBanner error={update.error} />
            </CardBody>
          </Card>

          <NotesCard notableType="contact" notableId={contact.id} />

          <ContactFollowUpCard
            contactId={contact.id}
            onSendStep={(templateId) => {
              setSendTemplateId(templateId);
              setSendOpen(true);
            }}
          />

          <Card>
            <CardHeader>
              <CardTitle>Send history</CardTitle>
            </CardHeader>
            {events.length === 0 ? (
              <EmptyState title="Nothing sent yet" />
            ) : (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <Th>When</Th>
                      <Th>Subject</Th>
                      <Th>Status</Th>
                      <Th>Detail</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event) => (
                      <Tr key={event.id}>
                        <Td className="text-xs whitespace-nowrap">
                          {formatDateTime(event.sentAt ?? event.createdAt)}
                        </Td>
                        <Td className="text-xs">{event.subjectRendered}</Td>
                        <Td>
                          <Badge tone={SEND_STATUS_TONE[event.status] ?? 'muted'}>
                            {event.status}
                          </Badge>
                        </Td>
                        <Td className="max-w-xs truncate text-xs text-muted-foreground">
                          {event.error || event.gmailMessageId || '—'}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            )}
          </Card>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Validation</CardTitle>
            <ValidationBadge contact={contact} />
          </CardHeader>
          <CardBody className="space-y-2 text-xs">
            <p className="text-muted-foreground">{contact.validationDetail || 'Not checked yet.'}</p>
            <div className="flex justify-between border-t pt-2">
              <span className="text-muted-foreground">Checked</span>
              <span>{formatDateTime(contact.validatedAt)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Last sent</span>
              <span>{formatDateTime(contact.lastSentAt)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Added</span>
              <span>{formatDateTime(contact.createdAt)}</span>
            </div>
            {contact.suppressed ? (
              <Callout tone="danger" title="Suppressed" className="mt-1">
                <p>
                  {SUPPRESSION_REASON_LABELS[contact.suppressedReason] ??
                    contact.suppressedReason}{' '}
                  · {formatDateTime(contact.suppressedAt)}
                </p>
                <p>
                  Remove it from the <Link to="/suppressions">suppressions list</Link> if this was
                  a mistake.
                </p>
              </Callout>
            ) : null}
            <ErrorBanner error={revalidate.error} />
          </CardBody>
        </Card>
      </PageBody>

      <SendModal
        contact={contact}
        open={sendOpen}
        onOpenChange={(open) => {
          setSendOpen(open);
          if (!open) setSendTemplateId(undefined);
        }}
        initialTemplateId={sendTemplateId}
      />
    </>
  );
}
