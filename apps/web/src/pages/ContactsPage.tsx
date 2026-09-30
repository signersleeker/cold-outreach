import { Ban, Send, Upload } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorBanner, PageBody, PageHeader } from '@/components/AppLayout';
import { ListCompositionBar } from '@/components/charts/ListCompositionBar';
import { DeleteContactDialog } from '@/components/DeleteContactDialog';
import { IndustryFilter } from '@/components/IndustrySelect';
import { NewContactDialog } from '@/components/NewContactDialog';
import { SendModal, ValidationBadge } from '@/components/SendModal';
import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { Card, CardBody, EmptyState } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogBody, DialogContent, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Pagination } from '@/components/ui/pagination';
import { Segmented } from '@/components/ui/segmented';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton, TableSkeleton } from '@/components/ui/skeleton';
import { Table, TableWrap, Td, Th, Tr } from '@/components/ui/table';
import {
  useContacts,
  useContactStats,
  useImportContacts,
  usePreviewImport,
  useSuppressContact,
} from '@/hooks';
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

const IMPORT_FIELDS: { value: string; label: string }[] = [
  { value: 'ignore', label: 'Ignore' },
  { value: 'email', label: 'Email' },
  { value: 'company', label: 'Company name' },
  { value: 'website', label: 'Company website' },
  { value: 'industry', label: 'Industry' },
  { value: 'location', label: 'Company location' },
  { value: 'first_name', label: 'First name' },
  { value: 'last_name', label: 'Last name' },
  { value: 'full_name', label: 'Full name' },
  { value: 'title', label: 'Title' },
  { value: 'hook', label: 'Hook' },
  { value: 'notes', label: 'Notes' },
  { value: 'contact_notes', label: 'Contact notes' },
  { value: 'company_notes', label: 'Company notes' },
  { value: 'source', label: 'Source' },
];

const CSV_HEADERS = [
  'email',
  'first name',
  'last name',
  'full name',
  'company name',
  'company website',
  'industry',
  'company location',
  'title',
  'hook',
  'notes',
  'contact notes',
  'company notes',
  'source',
];

function ImportDialog() {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [skipValidation, setSkipValidation] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const preview = usePreviewImport();
  const importer = useImportContacts();

  const emailMappedOnce = useMemo(
    () => Object.values(mapping).filter((field) => field === 'email').length === 1,
    [mapping],
  );

  function reset() {
    setFile(null);
    setHeaders([]);
    setMapping({});
    setSkipValidation(false);
    preview.reset();
    importer.reset();
    if (fileInput.current) fileInput.current.value = '';
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) reset();
      }}
    >
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Upload />
        Import CSV
      </Button>
      <DialogContent
        title="Import prospects"
        description="Only an email column is required. Confirm how each header maps before importing."
      >
        <DialogBody className="space-y-3">
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            className="block w-full cursor-pointer rounded-[var(--radius-md)] border border-dashed border-input bg-surface px-3 py-3 text-xs transition-colors hover:border-primary/40 file:mr-3 file:cursor-pointer file:rounded-full file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary-foreground"
            onChange={(event) => {
              const next = event.target.files?.[0] ?? null;
              setFile(next);
              setHeaders([]);
              setMapping({});
              importer.reset();
              if (next) {
                preview.mutate(next, {
                  onSuccess: (data) => {
                    setHeaders(data.headers);
                    const initial: Record<string, string> = {};
                    for (const header of data.headers) {
                      initial[header] = data.suggestions[header] ?? 'ignore';
                    }
                    setMapping(initial);
                  },
                });
              }
            }}
          />
          <p className="text-xs text-muted-foreground">
            {skipValidation
              ? 'Addresses we have not checked before are imported unvalidated. A previous result is reused.'
              : 'Addresses we have not checked before are validated on import. A previous result is reused, and invalid ones are suppressed automatically.'}
          </p>
          <p className="font-mono text-xs text-muted-foreground">{CSV_HEADERS.join(', ')}</p>
          <label className="flex cursor-pointer items-start gap-2.5 text-xs">
            <Checkbox
              checked={skipValidation}
              disabled={importer.isPending}
              onCheckedChange={(checked) => setSkipValidation(checked === true)}
              className="mt-0.5"
            />
            <span>
              <span className="font-medium">Skip email validation</span>
              <span className="mt-0.5 block text-muted-foreground">
                Don't check addresses we haven't seen before. An address already checked keeps that result.
              </span>
            </span>
          </label>

          <ErrorBanner error={preview.error ?? importer.error} />

          {headers.length > 0 && !importer.data ? (
            <div className="space-y-2">
              <p className="text-xs font-medium">Map columns</p>
              <div className="max-h-64 space-y-2 overflow-y-auto rounded-[var(--radius-md)] border border-border bg-surface p-2.5">
                {headers.map((header) => (
                  <div key={header} className="grid grid-cols-[1fr_12.5rem] items-center gap-2">
                    <span className="truncate font-mono text-xs" title={header}>
                      {header || '(empty)'}
                    </span>
                    <Select
                      value={mapping[header] ?? 'ignore'}
                      onValueChange={(value) =>
                        setMapping((current) => ({ ...current, [header]: value }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {IMPORT_FIELDS.map((field) => (
                          <SelectItem key={field.value} value={field.value}>
                            {field.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
              {!emailMappedOnce ? (
                <Callout tone="warning">Map exactly one column to Email.</Callout>
              ) : null}
            </div>
          ) : null}

          {importer.data ? (
            <Callout tone="success" title="Import complete">
              <ul className="space-y-0.5 font-mono">
                <li>created: {importer.data.created}</li>
                <li>skipped duplicates: {importer.data.skippedDupes}</li>
                {importer.data.skippedExistingCompany > 0 ? (
                  <li>skipped existing company: {importer.data.skippedExistingCompany}</li>
                ) : null}
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
              <p className="opacity-80">
                {skipValidation
                  ? 'Email validation was skipped for addresses not checked before.'
                  : `Validator: ${importer.data.validator}.`}{' '}
                Columns recognised:{' '}
                {Object.entries(importer.data.headersRecognised)
                  .map(([header, field]) => `${header} → ${field}`)
                  .join(', ')}
              </p>
              {importer.data.truncated ? (
                <p className="font-semibold">
                  File was truncated at the row limit — split it and import the rest.
                </p>
              ) : null}
            </Callout>
          ) : null}
        </DialogBody>
        <DialogFooter>
          <span />
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              {importer.data ? 'Done' : 'Cancel'}
            </Button>
            {!importer.data ? (
              <Button
                disabled={
                  !file ||
                  !emailMappedOnce ||
                  preview.isPending ||
                  importer.isPending ||
                  headers.length === 0
                }
                onClick={() => {
                  if (file) importer.mutate({ file, mapping, skipValidation });
                }}
              >
                {importer.isPending ? 'Importing…' : preview.isPending ? 'Reading…' : 'Import'}
              </Button>
            ) : null}
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

function Metric({
  label,
  value,
  hint,
  emphasis,
}: {
  label: string;
  value: number | undefined;
  hint?: string;
  emphasis?: boolean;
}) {
  return (
    <div>
      <p className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
        {label}
      </p>
      {value === undefined ? (
        <Skeleton className="mt-1.5 h-6 w-12" />
      ) : (
        <p
          className={cn(
            'mt-1 font-mono text-2xl leading-none font-semibold tabular-nums',
            emphasis ? 'text-primary' : 'text-foreground',
          )}
        >
          {value}
        </p>
      )}
      {hint ? <p className="mt-1.5 text-caption text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function ContactsPage() {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<ContactFilter>('all');
  const [industry, setIndustry] = useState('');
  const [offset, setOffset] = useState(0);
  const [sendTo, setSendTo] = useState<Contact | null>(null);
  const [suppressTarget, setSuppressTarget] = useState<Contact | null>(null);

  const { data, isLoading, error } = useContacts({
    q: query,
    status,
    industry,
    limit: PAGE_SIZE,
    offset,
  });
  // Scoped by the search and industry, but not by the status filter — the chips
  // need to show what you'd get by switching to them, not what the current chip shows.
  const { data: stats } = useContactStats({ q: query, industry });
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

      <PageBody className="space-y-3">
        <Card>
          <CardBody className="space-y-4">
            <div className="flex flex-wrap gap-x-8 gap-y-3">
              <Metric label="Contacts" value={stats?.all} />
              <Metric
                label="Ready to send"
                value={stats?.ready}
                hint="valid, never emailed"
                emphasis
              />
              <Metric label="Contacted" value={stats?.sent} hint="at least one send" />
              <Metric label="Suppressed" value={stats?.suppressed} hint="never emailed again" />
            </div>
            <div className="border-t border-border pt-4">
              {stats ? (
                <ListCompositionBar stats={stats} />
              ) : (
                <Skeleton className="h-2.5 w-full rounded-full" />
              )}
            </div>
          </CardBody>
        </Card>

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
          <IndustryFilter
            value={industry}
            onValueChange={(next) => {
              setIndustry(next);
              setOffset(0);
            }}
          />
          <Segmented
            aria-label="Filter contacts by status"
            value={status}
            onChange={(next) => {
              setStatus(next);
              setOffset(0);
            }}
            options={FILTERS.map((filter) => ({
              ...filter,
              count: stats?.[filter.value],
            }))}
          />
        </div>

        <ErrorBanner error={error} />

        <Card className="overflow-hidden">
          {isLoading ? (
            <TableSkeleton cols={8} />
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
                    <Th>Industry</Th>
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
                      <Td>
                        {contact.companyId ? (
                          <Link
                            to={`/companies/${contact.companyId}`}
                            className="hover:underline"
                          >
                            {contact.company}
                          </Link>
                        ) : (
                          '—'
                        )}
                      </Td>
                      <Td className="whitespace-nowrap">{contact.companyIndustry || '—'}</Td>
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

        <Pagination
          offset={offset}
          pageSize={PAGE_SIZE}
          total={total}
          onOffsetChange={setOffset}
        />
      </PageBody>

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
