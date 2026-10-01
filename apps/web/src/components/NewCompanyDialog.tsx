import { Building2 } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateCompany } from '@/hooks';
import { ErrorBanner } from './AppLayout';
import { CompanySizeSelect } from './CompanySizeSelect';
import { IndustrySelect } from './IndustrySelect';
import { Button } from './ui/button';
import { Dialog, DialogBody, DialogContent, DialogFooter } from './ui/dialog';
import { Field, Input } from './ui/input';

export function NewCompanyDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [website, setWebsite] = useState('');
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [industry, setIndustry] = useState('');
  const [size, setSize] = useState('');
  const [location, setLocation] = useState('');
  const create = useCreateCompany();
  const navigate = useNavigate();

  function reset(next: boolean) {
    setOpen(next);
    if (next) {
      setName('');
      setWebsite('');
      setLinkedinUrl('');
      setIndustry('');
      setSize('');
      setLocation('');
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
              create.mutate(
                {
                  name: name.trim(),
                  website: website.trim(),
                  linkedinUrl: linkedinUrl.trim(),
                  industry,
                  size,
                  location: location.trim(),
                },
                {
                  onSuccess: (company) => {
                    setOpen(false);
                    navigate(`/companies/${company.id}`);
                  },
                },
              );
            }}
          >
            <div className="space-y-3">
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
              <Field label="Website">
                <Input
                  maxLength={500}
                  placeholder="https://northwind.example"
                  value={website}
                  onChange={(event) => setWebsite(event.target.value)}
                />
              </Field>
              <Field label="LinkedIn">
                <Input
                  maxLength={500}
                  placeholder="https://www.linkedin.com/company/northwind"
                  value={linkedinUrl}
                  onChange={(event) => setLinkedinUrl(event.target.value)}
                />
              </Field>
              <Field label="Location">
                <Input
                  maxLength={200}
                  placeholder="Sydney, Australia"
                  value={location}
                  onChange={(event) => setLocation(event.target.value)}
                />
              </Field>
              <Field label="Industry">
                <IndustrySelect value={industry} onValueChange={setIndustry} />
              </Field>
              <Field label="Size">
                <CompanySizeSelect value={size} onValueChange={setSize} />
              </Field>
            </div>
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
