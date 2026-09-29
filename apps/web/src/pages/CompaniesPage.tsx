import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorBanner, PageHeader } from '@/components/AppLayout';
import { NewCompanyDialog } from '@/components/NewCompanyDialog';
import { Button } from '@/components/ui/button';
import { Card, EmptyState } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableWrap, Td, Th, Tr } from '@/components/ui/table';
import { useCompanies } from '@/hooks';
import { formatRelative, plural } from '@/lib/format';

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

      <div className="space-y-3 px-6 py-4">
      <Input
        value={q}
        onChange={(event) => setQ(event.target.value)}
        placeholder="Search company name…"
        className="max-w-sm"
      />

      <ErrorBanner error={error} />

      <Card className="overflow-hidden">
        {isLoading ? (
          <p className="px-4 py-6 text-xs text-muted-foreground">Loading…</p>
        ) : companies.length === 0 ? (
          <EmptyState
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
    </>
  );
}
