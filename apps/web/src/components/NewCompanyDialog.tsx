import { Building2 } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateCompany } from '@/hooks';
import { ErrorBanner } from './AppLayout';
import { Button } from './ui/button';
import { Dialog, DialogBody, DialogContent, DialogFooter } from './ui/dialog';
import { Field, Input } from './ui/input';

export function NewCompanyDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const create = useCreateCompany();
  const navigate = useNavigate();

  function reset(next: boolean) {
    setOpen(next);
    if (next) {
      setName('');
      create.reset();
    }
  }

  return (
    <Dialog open={open} onOpenChange={reset}>
      <Button variant="outline" onClick={() => reset(true)}>
        <Building2 />
        New company
      </Button>

      <DialogContent
        title="New company"
        description="Create a company, then add contacts to it from the company page."
      >
        <DialogBody className="space-y-3">
          <form
            id="new-company"
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate(name.trim(), {
                onSuccess: (company) => {
                  setOpen(false);
                  navigate(`/companies/${company.id}`);
                },
              });
            }}
          >
            <Field label="Company name *">
              <Input
                autoFocus
                required
                maxLength={200}
                placeholder="Northwind Mutual"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </Field>
          </form>
          <ErrorBanner error={create.error} />
        </DialogBody>
        <DialogFooter>
          <span className="text-xs text-muted-foreground">
            Names are unique, ignoring case.
          </span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="new-company"
              disabled={!name.trim() || create.isPending}
            >
              {create.isPending ? 'Saving…' : 'Create company'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
