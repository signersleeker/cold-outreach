import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Building2 } from 'lucide-react';
import { ErrorBanner, PageBody, PageHeader } from '@/components/AppLayout';
import { NewCompanyDialog } from '@/components/NewCompanyDialog';
import { Card, EmptyState } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Pagination } from '@/components/ui/pagination';
import { TableSkeleton } from '@/components/ui/skeleton';
import { Table, TableWrap, Td, Th, Tr } from '@/components/ui/table';
import { useCompanies } from '@/hooks';
import { formatRelative, plural, websiteHref } from '@/lib/format';

const PAGE_SIZE = 50;

export function CompaniesPage() {
  const [q, setQ] = useState('');
  const [debounced, setDebounced] = useState('');
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebounced(q);
      setOffset(0);
    }, 250);
    return () => window.clearTimeout(handle);
  }, [q]);

  const { data, error, isLoading } = useCompanies({
    q: debounced,
    limit: PAGE_SIZE,
    offset,
  });
  const companies = data?.data ?? [];
  const total = data?.meta.total ?? 0;

  return (
    <>
      <PageHeader
        title="Companies"
        description="Create a company, or ones pulled from contact and CSV company names."
        actions={<NewCompanyDialog />}
      />

      <PageBody className="space-y-3">
      <Input
        value={q}
        onChange={(event) => setQ(event.target.value)}
        placeholder="Search company name…"
        className="max-w-sm"
      />

      <ErrorBanner error={error} />

      <Card className="overflow-hidden">
        {isLoading ? (
          <TableSkeleton cols={8} />
        ) : companies.length === 0 ? (
          <EmptyState
            icon={Building2}
            title="No companies yet"
            description="Create a company, import contacts with a company column, or set a company on a contact."
            action={<NewCompanyDialog />}
          />
        ) : (
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>Name</Th>
                  <Th>Industry</Th>
                  <Th>Size</Th>
                  <Th>Location</Th>
                  <Th>Website</Th>
                  <Th>LinkedIn</Th>
                  <Th>Contacts</Th>
                  <Th>Created</Th>
                </tr>
              </thead>
              <tbody>
                {companies.map((company) => (
                  <Tr key={company.id}>
                    <Td>
                      <Link
                        to={`/companies/${company.id}`}
                        className="font-medium hover:underline"
                      >
                        {company.name}
                      </Link>
                    </Td>
                    <Td>{company.industry || '—'}</Td>
                    <Td>{company.size || '—'}</Td>
                    <Td>{company.location || '—'}</Td>
                    <Td className="max-w-48 truncate text-xs">
                      {company.website ? (
                        <a
                          href={websiteHref(company.website)}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:underline"
                        >
                          {company.website}
                        </a>
                      ) : (
                        '—'
                      )}
                    </Td>
                    <Td className="max-w-48 truncate text-xs">
                      {company.linkedinUrl ? (
                        <a
                          href={websiteHref(company.linkedinUrl)}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:underline"
                        >
                          {company.linkedinUrl}
                        </a>
                      ) : (
                        '—'
                      )}
                    </Td>
                    <Td className="font-mono text-xs">
                      {plural(company.contactCount, 'contact')}
                    </Td>
                    <Td className="text-xs text-muted-foreground">
                      {formatRelative(company.createdAt)}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Card>

      <Pagination offset={offset} pageSize={PAGE_SIZE} total={total} onOffsetChange={setOffset} />
      </PageBody>
    </>
  );
}
