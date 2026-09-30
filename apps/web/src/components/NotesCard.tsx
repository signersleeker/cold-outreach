import { Trash2 } from 'lucide-react';
import { useState } from 'react';
import { ErrorBanner } from '@/components/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useCreateNote, useDeleteNote, useNotes } from '@/hooks';
import type { NoteTarget } from '@/lib/api';
import { formatDateTime } from '@/lib/format';

export function NotesCard({
  notableType,
  notableId,
}: {
  notableType: NoteTarget;
  notableId: string;
}) {
  const notesQuery = useNotes(notableType, notableId);
  const create = useCreateNote();
  const remove = useDeleteNote();
  const [body, setBody] = useState('');
  const notes = notesQuery.data?.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Notes</CardTitle>
      </CardHeader>
      <CardBody className="space-y-3">
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            const text = body.trim();
            if (!text) return;
            create.mutate(
              { notableType, notableId, body: text },
              { onSuccess: () => setBody('') },
            );
          }}
        >
          <Textarea
            rows={3}
            value={body}
            placeholder="Add a note"
            onChange={(event) => setBody(event.target.value)}
          />
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={create.isPending || !body.trim()}>
              {create.isPending ? 'Adding…' : 'Add note'}
            </Button>
          </div>
          <ErrorBanner error={create.error ?? remove.error} />
        </form>

        {notesQuery.isLoading ? (
          <Skeleton className="h-12" />
        ) : notes.length === 0 ? (
          <p className="text-xs text-muted-foreground">No notes yet.</p>
        ) : (
          <ul className="space-y-2">
            {notes.map((note) => (
              <li
                key={note.id}
                className="rounded-[var(--radius-md)] border border-border px-3 py-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="whitespace-pre-wrap text-sm">{note.body}</p>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    title="Delete note"
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(note.id)}
                  >
                    <Trash2 />
                  </Button>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatDateTime(note.createdAt)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
