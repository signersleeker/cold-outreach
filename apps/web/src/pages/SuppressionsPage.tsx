import { ShieldBan, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { ErrorBanner, PageBody, PageHeader } from '@/components/AppLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { Card, CardBody, EmptyState } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { TableSkeleton } from '@/components/ui/skeleton';
import { Table, TableWrap, Td, Th, Tr } from '@/components/ui/table';
import { useSuppressionMutations, useSuppressions } from '@/hooks';
import { formatDateTime, plural } from '@/lib/format';
import { SUPPRESSION_REASON_LABELS } from '@/lib/gates';

export function SuppressionsPage() {
  const { data, isLoading } = useSuppressions();
  const { add, remove } = useSuppressionMutations();
  const [email, setEmail] = useState('');

  const rows = data?.data ?? [];
  const total = data?.meta.total ?? 0;

  return (
    <>
      <PageHeader
        title="Suppressions"
        description={`${plural(total, 'address', 'addresses')} that will never be emailed again. This list is the authority — the send gate reads it directly.`}
      />

      <PageBody className="space-y-3">
        <Card>
          <CardBody className="space-y-2 p-3.5">
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              add.mutate(
                { email, reason: 'manual', source: 'added manually' },
                { onSuccess: () => setEmail('') },
              );
            }}
          >
            <Input
              type="email"
              placeholder="someone@example.com"
              className="max-w-xs"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <Button type="submit" disabled={!email || add.isPending}>
              {add.isPending ? 'Adding…' : 'Add suppression'}
            </Button>
            <p className="text-xs text-muted-foreground">
              Works for addresses that are not imported yet.
            </p>
          </form>
          <ErrorBanner error={add.error ?? remove.error} />
          </CardBody>
        </Card>

        <Card className="overflow-hidden">
          {isLoading ? (
            <TableSkeleton cols={5} />
          ) : rows.length === 0 ? (
            <EmptyState
              icon={ShieldBan}
              title="No suppressions"
              description="Unsubscribes, stop replies and hard bounces land here automatically."
            />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <Th>Email</Th>
                    <Th>Reason</Th>
                    <Th>Source</Th>
                    <Th>Added</Th>
                    <Th className="text-right">Remove</Th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <Tr key={row.id}>
                      <Td className="font-mono text-xs">{row.email}</Td>
                      <Td>
                        <Badge tone={row.reason === 'manual' ? 'muted' : 'warning'}>
                          {SUPPRESSION_REASON_LABELS[row.reason] ?? row.reason}
                        </Badge>
                      </Td>
                      <Td className="max-w-md truncate text-xs text-muted-foreground">
                        {row.source || '—'}
                      </Td>
                      <Td className="text-xs whitespace-nowrap">{formatDateTime(row.createdAt)}</Td>
                      <Td className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-danger"
                          disabled={remove.isPending}
                          title="Remove — only do this if it was a mistake"
                          onClick={() => remove.mutate(row.email)}
                        >
                          <Trash2 />
                        </Button>
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </Card>

        <Callout tone="neutral">
          Removing a suppression is never automatic — re-importing a CSV or syncing the inbox will
          not undo an opt-out.
        </Callout>
      </PageBody>
    </>
  );
}
