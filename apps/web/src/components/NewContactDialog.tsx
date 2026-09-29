import { UserPlus } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateContact } from '@/hooks';
import type { NewContact } from '@/lib/api';
import { ErrorBanner } from './AppLayout';
import { Button } from './ui/button';
import { Dialog, DialogBody, DialogContent, DialogFooter } from './ui/dialog';
import { Field, Input, Textarea } from './ui/input';

const BLANK: NewContact = {
  email: '',
  firstName: '',
  lastName: '',
  company: '',
  title: '',
  hook: '',
  notes: '',
  source: '',
};

export function NewContactDialog() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<NewContact>(BLANK);
  const create = useCreateContact();
  const navigate = useNavigate();

  const set = (key: keyof NewContact) => (value: string) =>
    setDraft((current) => ({ ...current, [key]: value }));

  function reset(next: boolean) {
    setOpen(next);
    if (next) {
      setDraft(BLANK);
      create.reset();
    }
  }

  function submit() {
    create.mutate(draft, {
      // Straight to the contact so the validation verdict is visible immediately.
      onSuccess: (contact) => {
        setOpen(false);
        navigate(`/contacts/${contact.id}`);
      },
    });
  }

  // The seeded first-touch template merges these three, and an empty value
  // leaves its {{tag}} in the body, which blocks the send. Flagged here rather
  // than discovered later in the send modal.
  const missingForFirstTouch = (
    [
      ['first name', draft.firstName],
      ['company', draft.company],
      ['title', draft.title],
    ] as const
  )
    .filter(([, value]) => !value.trim())
    .map(([label]) => label);

  return (
    <Dialog open={open} onOpenChange={reset}>
      <Button variant="outline" onClick={() => reset(true)}>
        <UserPlus />
        New contact
      </Button>

      <DialogContent
        title="New contact"
        description="Only the email address is required. It is validated as soon as you save."
      >
        <DialogBody className="space-y-3">
          <form
            id="new-contact"
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <Field label="Email *">
              <Input
                type="email"
                autoFocus
                required
                placeholder="avery.stone@northwind.com.au"
                value={draft.email}
                onChange={(event) => set('email')(event.target.value)}
              />
            </Field>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="First name">
                <Input
                  value={draft.firstName}
                  onChange={(event) => set('firstName')(event.target.value)}
                />
              </Field>
              <Field label="Last name">
                <Input
                  value={draft.lastName}
                  onChange={(event) => set('lastName')(event.target.value)}
                />
              </Field>
              <Field label="Company">
                <Input
                  value={draft.company}
                  onChange={(event) => set('company')(event.target.value)}
                />
              </Field>
              <Field label="Title">
                <Input
                  value={draft.title}
                  onChange={(event) => set('title')(event.target.value)}
                />
              </Field>
            </div>

            <Field
              label="Source"
              hint="Where this address came from, ideally a URL. Your evidence for why contacting this person is defensible."
            >
              <Input
                placeholder="https://…"
                value={draft.source}
                onChange={(event) => set('source')(event.target.value)}
              />
            </Field>

            <Field label="Hook" hint="The one specific thing that makes this email worth sending.">
              <Textarea
                rows={2}
                value={draft.hook}
                onChange={(event) => set('hook')(event.target.value)}
              />
            </Field>

            <Field label="Notes">
              <Textarea
                rows={2}
                value={draft.notes}
                onChange={(event) => set('notes')(event.target.value)}
              />
            </Field>
          </form>

          {missingForFirstTouch.length > 0 ? (
            <p className="rounded-[var(--radius-sm)] bg-warning-subtle px-2.5 py-2 text-xs text-warning">
              Without {missingForFirstTouch.join(', ')} the “CISO shadow AI” template cannot be
              sent to this contact — its merge tags would be left unfilled. You can add them later.
            </p>
          ) : null}

          <ErrorBanner error={create.error} />
        </DialogBody>

        <DialogFooter>
          <span className="text-xs text-muted-foreground">
            Duplicates are rejected, ignoring case.
          </span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="new-contact"
              disabled={!draft.email.trim() || create.isPending}
            >
              {create.isPending ? 'Saving…' : 'Add contact'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
