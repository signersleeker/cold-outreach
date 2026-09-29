import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorBanner } from '@/components/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardBody } from '@/components/ui/card';
import { Field, Input } from '@/components/ui/input';
import { useLogin } from '@/hooks';

export function LoginPage() {
  const [password, setPassword] = useState('');
  const login = useLogin();
  const navigate = useNavigate();

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <Card className="w-full max-w-sm">
        <CardBody className="space-y-4">
          <div>
            <h1 className="text-base font-semibold">Kinnatic Outreach</h1>
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
  );
}
