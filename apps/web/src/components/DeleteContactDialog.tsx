import { Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDeleteContact } from '@/hooks';
import { ApiError, type Contact } from '@/lib/api';
import { ErrorBanner } from './AppLayout';
import { Button } from './ui/button';
import { Dialog, DialogBody, DialogContent, DialogFooter } from './ui/dialog';

export function DeleteContactDialog({
  contact,
  trigger = 'button',
  redirectToList = true,
}: {
  contact: Contact;
  /** `icon` is the compact control used in the contacts table. */
  trigger?: 'button' | 'icon';
  /** Detail view leaves the page; the list stays put so filters are kept. */
  redirectToList?: boolean;
}) {
  const [open, setOpen] = useState(false);
  // Set once the server refuses because this contact has send history. The
  // escalation is deliberate: the first click cannot destroy an audit trail.
  const [needsForce, setNeedsForce] = useState(false);
  const remove = useDeleteContact();
  const navigate = useNavigate();

  function reset(next: boolean) {
    setOpen(next);
    if (next) {
      setNeedsForce(false);
      remove.reset();
    }
  }

  function submit(force: boolean) {
    remove.mutate(
      { id: contact.id, force },
      {
        onSuccess: () => {
          setOpen(false);
          if (redirectToList) navigate('/contacts');
        },
        onError: (error) => {
          if (error instanceof ApiError && error.status === 409) setNeedsForce(true);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={reset}>
      <Button
        size={trigger === 'icon' ? 'sm' : 'default'}
        variant="ghost"
        className="text-danger hover:bg-danger-subtle"
        onClick={() => reset(true)}
        title="Delete this contact"
        aria-label={`Delete ${contact.email}`}
      >
        <Trash2 />
        {trigger === 'button' ? 'Delete' : null}
      </Button>

      <DialogContent
        title={`Delete ${contact.email}?`}
        description="This removes the contact from your list. It cannot be undone."
      >
        <DialogBody className="space-y-3 text-xs">
          <p className="text-muted-foreground">
            Everything recorded about this person goes with it — including the{' '}
            <strong>source</strong> and <strong>notes</strong> that justify having contacted them.
          </p>

          {contact.suppressed ? (
            <p className="rounded-[var(--radius-sm)] bg-muted/60 px-2.5 py-2">
              This contact is suppressed. <strong>The suppression stays</strong> — it lives on the
              suppression list, keyed by email address, so deleting the contact cannot undo the
              opt-out. Re-importing this address would bring it back already suppressed.
            </p>
          ) : null}

          {needsForce ? (
            <div className="space-y-2 rounded-[var(--radius-sm)] border border-danger/30 bg-danger-subtle px-2.5 py-2 text-danger">
              <p className="font-semibold">You have already emailed this person.</p>
              <p>
                Deleting also deletes the record of what was sent and when. If you only want to
                stop emailing them, close this and use <strong>Suppress</strong> instead — that
                keeps the history and blocks every future send.
              </p>
            </div>
          ) : null}

          {!needsForce ? <ErrorBanner error={remove.error} /> : null}
        </DialogBody>

        <DialogFooter>
          <span />
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              disabled={remove.isPending}
              onClick={() => submit(needsForce)}
            >
              {remove.isPending
                ? 'Deleting…'
                : needsForce
                  ? 'Delete contact and its history'
                  : 'Delete contact'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
