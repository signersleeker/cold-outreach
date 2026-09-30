import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorBanner } from '@/components/AppLayout';
import { TaddarLockup } from '@/components/brand/Logo';
import { Button } from '@/components/ui/button';
import { Card, CardBody } from '@/components/ui/card';
import { Field, Input } from '@/components/ui/input';
import { useLogin } from '@/hooks';

export function LoginPage() {
  const [password, setPassword] = useState('');
  const login = useLogin();
  const navigate = useNavigate();

  return (
    // The one full-ultraviolet surface in the app — an approved background from
    // the guidelines, with the reversed lockup and the brand's circle motif.
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-primary px-4">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 -right-32 size-[26rem] rounded-full bg-uv-600/50"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-28 -left-24 size-72 rounded-full bg-signal/85"
      />

      <div className="relative w-full max-w-sm space-y-5">
        <TaddarLockup variant="reversed" className="text-white" iconClassName="size-8" />

        <Card className="shadow-lift">
          <CardBody className="space-y-5 p-5">
            <div>
              <h1 className="text-sm font-semibold tracking-heading">Sign in</h1>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Internal tool. One mailbox, one send at a time.
              </p>
            </div>

            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                login.mutate(password, { onSuccess: () => navigate('/') });
              }}
            >
              <Field label="Password">
                <Input
                  type="password"
                  autoFocus
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </Field>
              <ErrorBanner error={login.error} />
              <Button type="submit" className="w-full" disabled={!password || login.isPending}>
                {login.isPending ? 'Signing in…' : 'Sign in'}
              </Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
