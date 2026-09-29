import { Ban, Send } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ErrorBanner, PageHeader } from '@/components/AppLayout';
import { DeleteContactDialog } from '@/components/DeleteContactDialog';
import { IndustrySelect } from '@/components/IndustrySelect';
import { NewContactDialog } from '@/components/NewContactDialog';
import { SendModal, ValidationBadge } from '@/components/SendModal';
import { Button } from '@/components/ui/button';
import { Card, CardBody, CardHeader, CardTitle, EmptyState } from '@/components/ui/card';
import { Dialog, DialogBody, DialogContent, DialogFooter } from '@/components/ui/dialog';
import { Field, Input } from '@/components/ui/input';
import { Table, TableWrap, Td, Th, Tr } from '@/components/ui/table';
import { useCompany, useContacts, useSuppressContact, useUpdateCompany } from '@/hooks';
import type { Contact } from '@/lib/api';
import { formatRelative, fullName, websiteHref } from '@/lib/format';

const PAGE_SIZE = 50;

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
        title="Suppress contact"
        description={`Stop emailing ${contact.email}. This is recorded on the suppression list.`}
      >
        <DialogBody className="space-y-3">
          <Input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note"
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
              disabled={suppress.isPending}
              onClick={() =>
                suppress.mutate(
                  { id: contact.id, reason: 'manual', note },
                  { onSuccess: () => onOpenChange(false) },
                )
              }
            >
              {suppress.isPending ? 'Suppressing…' : 'Suppress'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function CompanyDetailPage() {
  const { id = '' } = useParams();
  const [offset, setOffset] = useState(0);
  const [sendTo, setSendTo] = useState<Contact | null>(null);
  const [suppressTarget, setSuppressTarget] = useState<Contact | null>(null);
  const [profile, setProfile] = useState({ name: '', website: '', industry: '' });
  const updateCompany = useUpdateCompany();

  const companyQuery = useCompany(id);
  const contactsQuery = useContacts({
    companyId: id,
    limit: PAGE_SIZE,
    offset,
  });

  const company = companyQuery.data;
  const contacts = contactsQuery.data?.data ?? [];

  useEffect(() => {
    if (!company) return;
    setProfile({
      name: company.name,
      website: company.website,
      industry: company.industry,
    });
  }, [company]);
  const total = contactsQuery.data?.meta.total ?? 0;
  const error = companyQuery.error ?? contactsQuery.error;

  const addContact =
    company != null ? (
      <NewContactDialog
        companyName={company.name}
        companyLocked
        onCreated={() => {
          void contactsQuery.refetch();
          void companyQuery.refetch();
        }}
      />
    ) : null;

  return (
    <>
      <PageHeader
        title={company?.name ?? 'Company'}
        description={
          company
            ? [company.industry, `${total} contact${total === 1 ? '' : 's'}`]
                .filter(Boolean)
                .join(' · ')
            : 'Loading company…'
        }
        actions={
          <div className="flex items-center gap-2">
            {addContact}
            <Link to="/companies" className="text-xs text-muted-foreground hover:underline">
              All companies
            </Link>
          </div>
        }
      />

      <div className="space-y-3 px-6 py-4">
      <ErrorBanner error={error} />

      {company ? (
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
            <Button
              size="sm"
              disabled={
                updateCompany.isPending ||
                !profile.name.trim() ||
                (profile.name === company.name &&
                  profile.website === company.website &&
                  profile.industry === company.industry)
              }
              onClick={() =>
                updateCompany.mutate({
                  id: company.id,
                  name: profile.name.trim(),
                  website: profile.website.trim(),
                  industry: profile.industry,
                })
              }
            >
              {updateCompany.isPending ? 'Saving…' : 'Save'}
            </Button>
          </CardHeader>
          <CardBody className="grid gap-3 sm:grid-cols-2">
            <Field label="Name">
              <Input
                maxLength={200}
                value={profile.name}
                onChange={(event) => setProfile((current) => ({ ...current, name: event.target.value }))}
              />
            </Field>
            <Field label="Industry">
              <IndustrySelect
                value={profile.industry}
                onValueChange={(industry) => setProfile((current) => ({ ...current, industry }))}
              />
            </Field>
            <Field label="Website" className="sm:col-span-2">
              <Input
                maxLength={500}
                placeholder="https://example.com"
                value={profile.website}
                onChange={(event) =>
                  setProfile((current) => ({ ...current, website: event.target.value }))
                }
              />
              {profile.website.trim() ? (
                <a
                  href={websiteHref(profile.website)}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-muted-foreground hover:underline"
                >
                  Open website
                </a>
              ) : null}
            </Field>
            <div className="sm:col-span-2">
              <ErrorBanner error={updateCompany.error} />
            </div>
          </CardBody>
        </Card>
      ) : null}

      <Card className="overflow-hidden">
        {companyQuery.isLoading || contactsQuery.isLoading ? (
          <p className="px-4 py-6 text-xs text-muted-foreground">Loading…</p>
        ) : contacts.length === 0 ? (
          <EmptyState
            title="No contacts at this company"
            description="Add a contact here, or import one with this company name."
            action={addContact}
          />
        ) : (
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>Email</Th>
                  <Th>Name</Th>
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
