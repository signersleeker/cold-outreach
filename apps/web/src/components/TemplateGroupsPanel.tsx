import { ArrowDown, ArrowUp, Plus, Trash2, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { ErrorBanner } from '@/components/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useTemplateGroupMutations, useTemplateGroups, useTemplates } from '@/hooks';
import { cn } from '@/lib/utils';

type DraftItem = { templateId: string; delayDays: number };

const BLANK = { name: '', items: [] as DraftItem[] };

export function TemplateGroupsPanel() {
  const { data, isLoading } = useTemplateGroups();
  const { data: templatesData } = useTemplates();
  const { create, update, remove } = useTemplateGroupMutations();
  const groups = data?.data ?? [];
  const templates = templatesData?.data ?? [];

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState(BLANK);
  const [addKey, setAddKey] = useState(0);

  const selected = groups.find((group) => group.id === selectedId) ?? null;
  const creating = selectedId === 'new';

  useEffect(() => {
    if (!selectedId && groups.length > 0) setSelectedId(groups[0].id);
  }, [groups, selectedId]);

  const itemKey =
    selected?.items.map((item) => `${item.templateId}:${item.delayDays}`).join(',') ?? '';

  useEffect(() => {
    if (creating) setDraft(BLANK);
    else if (selected) {
      setDraft({
        name: selected.name,
        items: selected.items.map((item) => ({
          templateId: item.templateId,
          delayDays: item.delayDays,
        })),
      });
    }
  }, [selectedId, selected?.updatedAt, itemKey]);

  const dirty =
    creating ||
    (selected !== null &&
      (draft.name !== selected.name ||
        draft.items.length !== selected.items.length ||
        draft.items.some(
          (item, index) =>
            item.templateId !== selected.items[index]?.templateId ||
            item.delayDays !== selected.items[index]?.delayDays,
        )));

  const available = templates.filter(
    (template) => !draft.items.some((item) => item.templateId === template.id),
  );
  const byId = new Map(templates.map((template) => [template.id, template]));

  function move(index: number, delta: number) {
    setDraft((current) => {
      const next = [...current.items];
      const target = index + delta;
      if (target < 0 || target >= next.length) return current;
      const [item] = next.splice(index, 1);
      next.splice(target, 0, item);
      return {
        ...current,
        items: next.map((entry, position) =>
          position === 0 ? { ...entry, delayDays: 0 } : entry.delayDays < 1
            ? { ...entry, delayDays: 1 }
            : entry,
        ),
      };
    });
  }

  function setDelay(index: number, delayDays: number) {
    if (index === 0) return;
    setDraft((current) => ({
      ...current,
      items: current.items.map((item, i) =>
        i === index ? { ...item, delayDays: Math.max(1, delayDays) } : item,
      ),
    }));
  }

  return (
    <div className="grid gap-4 px-6 py-5 lg:grid-cols-[14rem_1fr]">
      <Card className="h-fit overflow-hidden">
        <div className="border-b border-border px-3 py-2.5">
          <Button size="sm" variant="outline" className="w-full" onClick={() => setSelectedId('new')}>
            <Plus />
            New group
          </Button>
        </div>
        {isLoading ? (
          <div className="space-y-3 p-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-3.5" style={{ opacity: 1 - i * 0.2 }} />
            ))}
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {groups.map((group) => (
              <li key={group.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(group.id)}
                  className={cn(
                    'relative w-full px-3 py-2.5 text-left text-sm transition-colors',
                    selectedId === group.id
                      ? 'bg-accent font-semibold text-accent-foreground before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-primary'
                      : 'hover:bg-surface',
                  )}
                >
                  {group.name}
                  <span className="block text-xs font-normal text-muted-foreground">
                    {group.items.length} template{group.items.length === 1 ? '' : 's'}
                  </span>
                </button>
              </li>
            ))}
            {creating ? (
              <li className="bg-accent px-3 py-2 text-sm font-medium italic">New group</li>
            ) : null}
          </ul>
        )}
      </Card>

      {creating || selected ? (
        <Card>
          <CardHeader>
            <CardTitle>{creating ? 'New group' : selected?.name}</CardTitle>
            <div className="flex gap-2">
              {!creating && selected ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-danger"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(selected.id, { onSuccess: () => setSelectedId(null) })}
                  title="Delete group"
                >
                  <Trash2 />
                </Button>
              ) : null}
              <Button
                size="sm"
                disabled={
                  !dirty ||
                  !draft.name.trim() ||
                  draft.items.length === 0 ||
                  draft.items.some((item, index) => index > 0 && item.delayDays < 1) ||
                  create.isPending ||
                  update.isPending
                }
                onClick={() => {
                  const input = {
                    name: draft.name.trim(),
                    items: draft.items.map((item, index) => ({
                      templateId: item.templateId,
                      delayDays: index === 0 ? 0 : item.delayDays,
                    })),
                  };
                  if (creating) {
                    create.mutate(input, { onSuccess: (group) => setSelectedId(group.id) });
                  } else if (selected) {
                    update.mutate({ id: selected.id, ...input });
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
                maxLength={120}
                placeholder="Insurance first touch"
                onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
              />
            </Field>

            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                Templates, in send order. Delay is days after the previous email was sent.
              </p>
              {draft.items.length === 0 ? (
                <p className="text-xs text-muted-foreground">Add at least one template.</p>
              ) : (
                <ol className="space-y-1">
                  {draft.items.map((item, index) => {
                    const template = byId.get(item.templateId);
                    return (
                      <li
                        key={item.templateId}
                        className="flex items-center gap-2 rounded-[var(--radius-sm)] border px-2 py-1.5"
                      >
                        <span className="w-5 font-mono text-xs text-muted-foreground">{index + 1}</span>
                        <span className="min-w-0 flex-1 truncate text-sm">
                          {template?.name ?? 'Removed template'}
                          {template?.industry ? (
                            <span className="ml-2 text-xs text-muted-foreground">{template.industry}</span>
                          ) : null}
                        </span>
                        {index === 0 ? (
                          <span className="shrink-0 rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                            Now
                          </span>
                        ) : (
                          <label className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                            <Input
                              type="number"
                              min={1}
                              max={365}
                              className="h-7 w-14 px-1.5 text-center font-mono"
                              value={item.delayDays}
                              onChange={(event) =>
                                setDelay(index, Number.parseInt(event.target.value, 10) || 1)
                              }
                            />
                            days later
                          </label>
                        )}
                        <Button
                          size="icon"
                          variant="ghost"
                          disabled={index === 0}
                          onClick={() => move(index, -1)}
                          title="Move earlier"
                        >
                          <ArrowUp />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          disabled={index === draft.items.length - 1}
                          onClick={() => move(index, 1)}
                          title="Move later"
                        >
                          <ArrowDown />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          title="Remove"
                          onClick={() =>
                            setDraft((current) => ({
                              ...current,
                              items: current.items
                                .filter((entry) => entry.templateId !== item.templateId)
                                .map((entry, position) =>
                                  position === 0 ? { ...entry, delayDays: 0 } : entry,
                                ),
                            }))
                          }
                        >
                          <X />
                        </Button>
                      </li>
                    );
                  })}
                </ol>
              )}
            </div>

            {templates.length === 0 ? (
              <p className="text-xs text-muted-foreground">Create a template before adding it to a group.</p>
            ) : available.length > 0 ? (
              <Field label="Add template">
                <Select
                  key={addKey}
                  onValueChange={(templateId) => {
                    setDraft((current) => ({
                      ...current,
                      items: [
                        ...current.items,
                        {
                          templateId,
                          delayDays: current.items.length === 0 ? 0 : 5,
                        },
                      ],
                    }));
                    setAddKey((key) => key + 1);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a template" />
                  </SelectTrigger>
                  <SelectContent>
                    {available.map((template) => (
                      <SelectItem key={template.id} value={template.id}>
                        {template.name}
                        {template.industry ? ` · ${template.industry}` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            ) : (
              <p className="text-xs text-muted-foreground">Every template is already in this group.</p>
            )}

            <ErrorBanner error={create.error ?? update.error ?? remove.error} />
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}
