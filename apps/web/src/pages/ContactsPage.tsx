import { Ban, Send, Upload } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorBanner, PageHeader } from '@/components/AppLayout';
import { DeleteContactDialog } from '@/components/DeleteContactDialog';
import { NewContactDialog } from '@/components/NewContactDialog';
import { SendModal, ValidationBadge } from '@/components/SendModal';
import { Button } from '@/components/ui/button';
import { Card, EmptyState } from '@/components/ui/card';
import { Dialog, DialogBody, DialogContent, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Table, TableWrap, Td, Th, Tr } from '@/components/ui/table';
import { useContacts, useImportContacts, useSuppressContact } from '@/hooks';
import type { Contact, ContactFilter } from '@/lib/api';
import { formatRelative, fullName, plural } from '@/lib/format';
import { cn } from '@/lib/utils';

const FILTERS: { value: ContactFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'ready', label: 'Ready' },
  { value: 'risky', label: 'Risky' },
  { value: 'invalid', label: 'Invalid' },
  { value: 'pending', label: 'Unvalidated' },
  { value: 'sent', label: 'Sent' },
  { value: 'suppressed', label: 'Suppressed' },
];

const PAGE_SIZE = 50;

function ImportDialog() {
  const [open, setOpen] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const importer = useImportContacts();

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) importer.reset();
      }}
    >
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Upload />
        Import CSV
      </Button>
      <DialogContent
        title="Import prospects"
        description="Only an email column is required. Common header spellings are mapped automatically."
      >
        <DialogBody className="space-y-3">
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            className="block w-full text-xs file:mr-3 file:rounded-[var(--radius-sm)] file:border file:border-input file:bg-card file:px-2.5 file:py-1.5 file:text-xs"
          />
          <p className="text-xs text-muted-foreground">
            Every new address is validated on import. Invalid ones are suppressed automatically.
            Record where each address came from in the <strong>source</strong> column — that is
            your evidence for why contacting this person is defensible.
          </p>

          <ErrorBanner error={importer.error} />

          {importer.data ? (
            <div className="space-y-2 rounded-[var(--radius-sm)] border bg-muted/40 px-3 py-2 text-xs">
              <p className="font-medium">Import summary</p>
              <ul className="space-y-0.5 font-mono">
                <li>created: {importer.data.created}</li>
                <li>skipped duplicates: {importer.data.skippedDupes}</li>
                <li>valid: {importer.data.valid}</li>
                <li>risky: {importer.data.risky}</li>
                <li>invalid (auto-suppressed): {importer.data.invalid}</li>
                <li>not yet validated: {importer.data.pending}</li>
                {importer.data.missingEmail > 0 ? (
                  <li>rows with no email: {importer.data.missingEmail}</li>
                ) : null}
                {importer.data.suppressedExisting > 0 ? (
                  <li>already opted out: {importer.data.suppressedExisting}</li>
                ) : null}
              </ul>
              <p className="text-muted-foreground">
                Validator: {importer.data.validator}. Columns recognised:{' '}
                {Object.entries(importer.data.headersRecognised)
                  .map(([header, field]) => `${header} → ${field}`)
                  .join(', ')}
              </p>
              {importer.data.truncated ? (
                <p className="text-warning">
                  File was truncated at the row limit — split it and import the rest.
                </p>
              ) : null}
            </div>
          ) : null}
        </DialogBody>
        <DialogFooter>
          <span />
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              {importer.data ? 'Done' : 'Cancel'}
            </Button>
            <Button
              disabled={importer.isPending}
              onClick={() => {
                const file = fileInput.current?.files?.[0];
                if (file) importer.mutate(file);
              }}
            >
              {importer.isPending ? 'Importing…' : 'Import'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SuppressDialog({
  contact,
  open,
  onOpenChange,
}: {
  contact: Contact;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [note, setNote] = useState('');
  const suppress = useSuppressContact();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={`Suppress ${contact.email}`}
        description="Permanent. This address will never be sent to again."
      >
        <DialogBody className="space-y-3">
          <Input
            placeholder="Reason note (optional)"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
          <ErrorBanner error={suppress.error} />
        </DialogBody>
        <DialogFooter>
          <span />
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              disabled={suppress.isPending}
              onClick={() =>
                suppress.mutate(
                  { id: contact.id, reason: 'manual', note },
                  { onSuccess: () => onOpenChange(false) },
                )
              }
            >
              Suppress
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ContactsPage() {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<ContactFilter>('all');
  const [offset, setOffset] = useState(0);
  const [sendTo, setSendTo] = useState<Contact | null>(null);
  const [suppressTarget, setSuppressTarget] = useState<Contact | null>(null);

  const { data, isLoading, error } = useContacts({
    q: query,
    status,
    limit: PAGE_SIZE,
    offset,
  });
  const contacts = data?.data ?? [];
  const total = data?.meta.total ?? 0;

  useEffect(() => {
    if (offset > 0 && offset >= total && data) {
      setOffset(Math.max(0, total - (total % PAGE_SIZE || PAGE_SIZE)));
    }
  }, [data, offset, total]);

  return (
    <>
      <PageHeader
        title="Contacts"
        description={`${plural(total, 'contact')} matching the current filter`}
        actions={
          <>
            <NewContactDialog />
            <ImportDialog />
          </>
        }
      />

      <div className="space-y-3 px-6 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            placeholder="Search email, name, company, title…"
            className="max-w-xs"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOffset(0);
            }}
          />
          <div className="flex flex-wrap gap-1">
            {FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                onClick={() => {
                  setStatus(filter.value);
                  setOffset(0);
                }}
                className={cn(
                  'rounded-full border px-2.5 py-1 text-xs transition-colors',
                  status === filter.value
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border text-muted-foreground hover:bg-accent',
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        <ErrorBanner error={error} />

        <Card className="overflow-hidden">
          {isLoading ? (
            <p className="px-4 py-6 text-xs text-muted-foreground">Loading…</p>
          ) : contacts.length === 0 ? (
            <EmptyState
              title="No contacts match"
              description="Import a CSV to get started, or clear the filter."
            />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <Th>Email</Th>
                    <Th>Name</Th>
                    <Th>Company</Th>
                    <Th>Title</Th>
                    <Th>Status</Th>
                    <Th>Last sent</Th>
                    <Th className="text-right">Actions</Th>
                  </tr>
                </thead>
                <tbody>
                  {contacts.map((contact) => (
                    <Tr key={contact.id}>
                      <Td className="font-mono text-xs">
                        <Link to={`/contacts/${contact.id}`} className="hover:underline">
                          {contact.email}
                        </Link>
                      </Td>
                      <Td className="whitespace-nowrap">{fullName(contact) || '—'}</Td>
                      <Td>{contact.company || '—'}</Td>
                      <Td>{contact.title || '—'}</Td>
                      <Td>
                        <ValidationBadge contact={contact} />
                      </Td>
                      <Td className="text-xs whitespace-nowrap text-muted-foreground">
                        {contact.lastSentAt ? formatRelative(contact.lastSentAt) : '—'}
                      </Td>
                      <Td>
                        <div className="flex justify-end gap-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setSendTo(contact)}
                            disabled={contact.suppressed}
                            title={contact.suppressed ? 'Suppressed' : 'Preview and send'}
                          >
                            <Send />
                            Send
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setSuppressTarget(contact)}
                            disabled={contact.suppressed}
                            title="Suppress"
                          >
                            <Ban />
                          </Button>
                          <DeleteContactDialog
                            contact={contact}
                            trigger="icon"
                            redirectToList={false}
                          />
                        </div>
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </Card>

        {total > PAGE_SIZE ? (
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      {sendTo ? (
        <SendModal
          contact={sendTo}
          open={!!sendTo}
          onOpenChange={(open) => !open && setSendTo(null)}
        />
      ) : null}
      {suppressTarget ? (
        <SuppressDialog
          contact={suppressTarget}
          open={!!suppressTarget}
          onOpenChange={(open) => !open && setSuppressTarget(null)}
        />
      ) : null}
    </>
  );
}
