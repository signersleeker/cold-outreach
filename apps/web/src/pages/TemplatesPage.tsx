import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { ErrorBanner, PageBody, PageHeader } from '@/components/AppLayout';
import { IndustrySelect } from '@/components/IndustrySelect';
import { TemplateGroupsPanel } from '@/components/TemplateGroupsPanel';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, Input, Textarea } from '@/components/ui/input';
import { Segmented } from '@/components/ui/segmented';
import { Skeleton } from '@/components/ui/skeleton';
import { useTemplateMutations, useTemplates } from '@/hooks';
import type { Template } from '@/lib/api';
import { htmlClipboardToPlain, plainLinks } from '@/lib/html-paste';
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

const BLANK = { name: '', subject: '', body: '', industry: '' };

function LinkedWords({ text }: { text: string }) {
  const links = plainLinks(text);
  if (links.length === 0) return null;
  return (
    <p className="text-xs text-muted-foreground">
      Clickable in the email:{' '}
      {links.map((link, index) => (
        <span key={`${link.href}-${index}`}>
          {index > 0 ? ', ' : null}
          <a
            href={link.href}
            target="_blank"
            rel="noreferrer"
            className="text-link underline underline-offset-4"
          >
            {link.label}
          </a>
        </span>
      ))}
    </p>
  );
}

export function TemplatesPage() {
  const { data, isLoading } = useTemplates();
  const { create, update, remove } = useTemplateMutations();
  const templates = data?.data ?? [];

  const [section, setSection] = useState<'templates' | 'groups'>('templates');
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
      setDraft({
        name: selected.name,
        subject: selected.subject,
        body: selected.body,
        industry: selected.industry,
      });
    }
  }, [selectedId, selected?.updatedAt]);

  const dirty =
    creating ||
    (selected !== null &&
      (draft.name !== selected.name ||
        draft.subject !== selected.subject ||
        draft.body !== selected.body ||
        draft.industry !== selected.industry));

  const referenced = [...draft.subject.matchAll(/\{\{\s*(\w+)\s*\}\}/g), ...draft.body.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map(
    (m) => m[1],
  );
  const unknown = [...new Set(referenced.filter((name) => !MERGE_VARS.includes(name)))];

  return (
    <>
      <PageHeader
        title="Templates"
        description={
          section === 'templates'
            ? 'Paste from Gmail and a linked word keeps its address. Tag a template with an industry when it is written for that kind of company.'
            : 'A group is an ordered list of templates. Sending still happens one template at a time.'
        }
        actions={
          <>
            <Segmented
              aria-label="Templates or groups"
              value={section}
              onChange={setSection}
              options={[
                { value: 'templates', label: 'Templates' },
                { value: 'groups', label: 'Groups' },
              ]}
            />
            {section === 'templates' ? (
              <Button variant="outline" onClick={() => setSelectedId('new')}>
                <Plus />
                New template
              </Button>
            ) : null}
          </>
        }
      />

      {section === 'groups' ? <TemplateGroupsPanel /> : null}

      {section === 'templates' ? (

      <PageBody className="grid gap-4 lg:grid-cols-[14rem_1fr]">
        <Card className="h-fit overflow-hidden">
          {isLoading ? (
            <div className="space-y-3 p-3">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-3.5" style={{ opacity: 1 - i * 0.15 }} />
              ))}
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {templates.map((template: Template) => (
                <li key={template.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(template.id)}
                    className={cn(
                      'relative w-full px-3 py-2.5 text-left text-sm transition-colors',
                      selectedId === template.id
                        ? 'bg-accent font-semibold text-accent-foreground before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-primary'
                        : 'hover:bg-surface',
                    )}
                  >
                    <span>
                      {template.name}
                      {template.unknownVars.length > 0 ? (
                        <Badge tone="warning" className="ml-1.5">
                          !
                        </Badge>
                      ) : null}
                    </span>
                    {template.industry ? (
                      <span className="block truncate text-xs font-normal text-muted-foreground">
                        {template.industry}
                      </span>
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
              <Field label="Industry" hint="Leave unset when the template is not written for one industry.">
                <IndustrySelect
                  value={draft.industry}
                  onValueChange={(industry) => setDraft((d) => ({ ...d, industry }))}
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
              <Field
                label="Body"
                hint="A linked word pastes as [text](https://…). That word is the link in Gmail; the address is written out in the plain-text copy."
              >
                <Textarea
                  rows={16}
                  className="font-mono text-sm leading-5"
                  value={draft.body}
                  onChange={(event) => setDraft((d) => ({ ...d, body: event.target.value }))}
                  onPaste={(event) => {
                    const converted = htmlClipboardToPlain(event.clipboardData.getData('text/html'));
                    if (!converted) return;
                    event.preventDefault();
                    const el = event.currentTarget;
                    const start = el.selectionStart;
                    const end = el.selectionEnd;
                    const next = draft.body.slice(0, start) + converted + draft.body.slice(end);
                    setDraft((d) => ({ ...d, body: next }));
                    const cursor = start + converted.length;
                    requestAnimationFrame(() => {
                      el.focus();
                      el.setSelectionRange(cursor, cursor);
                    });
                  }}
                />
              </Field>
              <LinkedWords text={draft.body} />

              <Callout tone="neutral" title="Merge fields">
                <p className="font-mono text-muted-foreground">
                  {MERGE_VARS.map((v) => `{{${v}}}`).join('  ')}
                </p>
                <p className="text-muted-foreground">
                  A field that is empty on the contact leaves its tag in the output, which blocks
                  the send. That is deliberate — a raw <code>{'{{company}}'}</code> must never go
                  out.
                </p>
              </Callout>

              {unknown.length > 0 ? (
                <Callout
                  tone="warning"
                  title={`Unknown tag${unknown.length === 1 ? '' : 's'} in this template`}
                >
                  <span className="font-mono">{unknown.map((v) => `{{${v}}}`).join(' ')}</span> —
                  these will never be filled and will block every send.
                </Callout>
              ) : null}

              <ErrorBanner error={create.error ?? update.error ?? remove.error} />
            </CardBody>
          </Card>
        ) : null}
      </PageBody>
      ) : null}
    </>
  );
}
