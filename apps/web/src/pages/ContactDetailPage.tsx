import { ArrowLeft, RefreshCw, Send } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ErrorBanner, PageHeader } from '@/components/AppLayout';
import { DeleteContactDialog } from '@/components/DeleteContactDialog';
import { SendModal, ValidationBadge } from '@/components/SendModal';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardBody, CardHeader, CardTitle, EmptyState } from '@/components/ui/card';
import { Field, Input, Textarea } from '@/components/ui/input';
import { Table, TableWrap, Td, Th, Tr } from '@/components/ui/table';
import { useContact, useRevalidateContact, useSendHistory, useUpdateContact } from '@/hooks';
import type { Contact } from '@/lib/api';
import { formatDateTime, fullName } from '@/lib/format';
import { SEND_STATUS_TONE, SUPPRESSION_REASON_LABELS } from '@/lib/gates';

type EditableField = 'firstName' | 'lastName' | 'company' | 'title' | 'hook' | 'source' | 'notes';

const TEXT_FIELDS: { key: EditableField; label: string; hint?: string }[] = [
  { key: 'firstName', label: 'First name' },
  { key: 'lastName', label: 'Last name' },
  { key: 'company', label: 'Company' },
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

  useEffect(() => {
    setDraft({});
  }, [id]);

  if (isLoading) {
    return (
      <>
        <PageHeader title="Contact" />
        <p className="px-6 py-4 text-xs text-muted-foreground">Loading…</p>
      </>
    );
  }
  if (!contact) {
    return (
      <>
        <PageHeader title="Contact" />
        <div className="px-6 py-4">
          <ErrorBanner error={error} />
        </div>
      </>
    );
  }

  const value = (key: EditableField) => draft[key] ?? contact[key];
  const dirty = Object.keys(draft).length > 0;
  const events = history?.data ?? [];

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

      <div className="grid gap-4 px-6 py-4 lg:grid-cols-[2fr_1fr]">
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
              <Field label="Notes">
                <Textarea
                  rows={3}
                  value={value('notes') as string}
                  onChange={(event) => setDraft((c) => ({ ...c, notes: event.target.value }))}
                />
              </Field>
              <ErrorBanner error={update.error} />
            </CardBody>
          </Card>

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
              <div className="mt-2 rounded-[var(--radius-sm)] bg-danger-subtle px-2.5 py-2 text-danger">
                <p className="font-semibold">Suppressed</p>
                <p>
                  {SUPPRESSION_REASON_LABELS[contact.suppressedReason] ??
                    contact.suppressedReason}{' '}
                  · {formatDateTime(contact.suppressedAt)}
                </p>
                <p className="mt-1">
                  Remove it from the{' '}
                  <Link to="/suppressions" className="underline">
                    suppressions list
                  </Link>{' '}
                  if this was a mistake.
                </p>
              </div>
            ) : null}
            <ErrorBanner error={revalidate.error} />
          </CardBody>
        </Card>
      </div>

      <SendModal contact={contact} open={sendOpen} onOpenChange={setSendOpen} />
    </>
  );
}
