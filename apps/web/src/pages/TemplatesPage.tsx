import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { ErrorBanner, PageHeader } from '@/components/AppLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, Input, Textarea } from '@/components/ui/input';
import { useTemplateMutations, useTemplates } from '@/hooks';
import type { Template } from '@/lib/api';
import { cn } from '@/lib/utils';

const MERGE_VARS = [
  'first_name',
  'last_name',
  'company',
  'title',
  'hook',
  'sender_name',
  'sender_title',
  'company_legal',
];

const BLANK = { name: '', subject: '', body: '' };

export function TemplatesPage() {
  const { data, isLoading } = useTemplates();
  const { create, update, remove } = useTemplateMutations();
  const templates = data?.data ?? [];

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState(BLANK);

  const selected = templates.find((t) => t.id === selectedId) ?? null;
  const creating = selectedId === 'new';

  useEffect(() => {
    if (!selectedId && templates.length > 0) setSelectedId(templates[0].id);
  }, [templates, selectedId]);

  useEffect(() => {
    if (creating) setDraft(BLANK);
    else if (selected) {
      setDraft({ name: selected.name, subject: selected.subject, body: selected.body });
    }
  }, [selectedId, selected?.updatedAt]);

  const dirty =
    creating ||
    (selected !== null &&
      (draft.name !== selected.name ||
        draft.subject !== selected.subject ||
        draft.body !== selected.body));

  const referenced = [...draft.subject.matchAll(/\{\{\s*(\w+)\s*\}\}/g), ...draft.body.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map(
    (m) => m[1],
  );
  const unknown = [...new Set(referenced.filter((name) => !MERGE_VARS.includes(name)))];

  return (
    <>
      <PageHeader
        title="Templates"
        description="Plain text only. Every template must end with a human opt-out sentence, not a marketing footer."
        actions={
          <Button variant="outline" onClick={() => setSelectedId('new')}>
            <Plus />
            New template
          </Button>
        }
      />

      <div className="grid gap-4 px-6 py-4 lg:grid-cols-[14rem_1fr]">
        <Card className="h-fit overflow-hidden">
          {isLoading ? (
            <p className="px-3 py-3 text-xs text-muted-foreground">Loading…</p>
          ) : (
            <ul className="divide-y">
              {templates.map((template: Template) => (
                <li key={template.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(template.id)}
                    className={cn(
                      'w-full px-3 py-2 text-left text-sm transition-colors',
                      selectedId === template.id ? 'bg-accent font-medium' : 'hover:bg-accent/60',
                    )}
                  >
                    {template.name}
                    {template.unknownVars.length > 0 ? (
                      <Badge tone="warning" className="ml-1.5">
                        !
                      </Badge>
                    ) : null}
                  </button>
                </li>
              ))}
              {creating ? (
                <li className="bg-accent px-3 py-2 text-sm font-medium italic">New template</li>
              ) : null}
            </ul>
          )}
        </Card>

        {creating || selected ? (
          <Card>
            <CardHeader>
              <CardTitle>{creating ? 'New template' : selected?.name}</CardTitle>
              <div className="flex gap-2">
                {!creating && selected ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-danger"
                    disabled={remove.isPending}
                    onClick={() => {
                      remove.mutate(selected.id, { onSuccess: () => setSelectedId(null) });
                    }}
                    title="Delete — send history is preserved"
                  >
                    <Trash2 />
                  </Button>
                ) : null}
                <Button
                  size="sm"
                  disabled={!dirty || create.isPending || update.isPending}
                  onClick={() => {
                    if (creating) {
                      create.mutate(draft, { onSuccess: (t) => setSelectedId(t.id) });
                    } else if (selected) {
                      update.mutate({ id: selected.id, ...draft });
                    }
                  }}
                >
                  {create.isPending || update.isPending ? 'Saving…' : 'Save'}
                </Button>
              </div>
            </CardHeader>
            <CardBody className="space-y-3">
              <Field label="Name">
                <Input
                  value={draft.name}
                  onChange={(event) => setDraft((d) => ({ ...d, name: event.target.value }))}
                />
              </Field>
              <Field
                label="Subject"
                hint="Avoid merge tags here — a blank field would block every send using this template."
              >
                <Input
                  value={draft.subject}
                  onChange={(event) => setDraft((d) => ({ ...d, subject: event.target.value }))}
                />
              </Field>
              <Field label="Body">
                <Textarea
                  rows={16}
                  className="font-mono text-xs"
                  value={draft.body}
                  onChange={(event) => setDraft((d) => ({ ...d, body: event.target.value }))}
                />
              </Field>

              <div className="space-y-1.5 rounded-[var(--radius-sm)] border bg-muted/40 px-3 py-2 text-xs">
                <p className="font-medium">Merge fields</p>
                <p className="font-mono text-muted-foreground">
                  {MERGE_VARS.map((v) => `{{${v}}}`).join('  ')}
                </p>
                <p className="text-muted-foreground">
                  A field that is empty on the contact leaves its tag in the output, which blocks
                  the send. That is deliberate — a raw <code>{'{{company}}'}</code> must never go
                  out.
                </p>
                {unknown.length > 0 ? (
                  <p className="text-warning">
                    Unknown tag{unknown.length === 1 ? '' : 's'}:{' '}
                    <span className="font-mono">{unknown.map((v) => `{{${v}}}`).join(' ')}</span> —
                    these will never be filled and will block every send.
                  </p>
                ) : null}
              </div>

              <ErrorBanner error={create.error ?? update.error ?? remove.error} />
            </CardBody>
          </Card>
        ) : null}
      </div>
    </>
  );
}
