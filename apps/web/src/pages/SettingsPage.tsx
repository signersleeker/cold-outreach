import { Link2, Unlink } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ErrorBanner, PageHeader } from '@/components/AppLayout';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Field, Input } from '@/components/ui/input';
import {
  useAppSettings,
  useDisconnectGmail,
  useGmailStatus,
  useUpdateAppSettings,
} from '@/hooks';
import { formatDateTime } from '@/lib/format';
import { cn } from '@/lib/utils';

export function SettingsPage() {
  const { data: settings } = useAppSettings();
  const { data: gmail } = useGmailStatus();
  const update = useUpdateAppSettings();
  const disconnect = useDisconnectGmail();
  const [params, setParams] = useSearchParams();

  const [dailyCap, setDailyCap] = useState(20);
  const [includeUnsubLink, setIncludeUnsubLink] = useState(true);

  useEffect(() => {
    if (settings) {
      setDailyCap(settings.dailyCap);
      setIncludeUnsubLink(settings.includeUnsubLink);
    }
  }, [settings?.updatedAt]);

  const gmailResult = params.get('gmail');
  const gmailMessage = params.get('message');

  if (!settings) {
    return (
      <>
        <PageHeader title="Settings" />
        <p className="px-6 py-4 text-xs text-muted-foreground">Loading…</p>
      </>
    );
  }

  const overCap = dailyCap > settings.recommendedDailyCap;

  const toggleUnsub = (checked: boolean) => {
    setIncludeUnsubLink(checked);
    update.mutate({ includeUnsubLink: checked });
  };

  return (
    <>
      <PageHeader title="Settings" />

      <div className="max-w-3xl space-y-4 px-6 py-4">
        {gmailResult === 'connected' ? (
          <div className="flex items-center justify-between rounded-[var(--radius-sm)] border border-success/30 bg-success-subtle px-3 py-2 text-xs text-success">
            <span>Gmail connected.</span>
            <button type="button" className="underline" onClick={() => setParams({})}>
              dismiss
            </button>
          </div>
        ) : null}
        {gmailResult === 'error' ? (
          <div className="flex items-start justify-between gap-3 rounded-[var(--radius-sm)] border border-danger/30 bg-danger-subtle px-3 py-2 text-xs text-danger">
            <span>{gmailMessage || 'Connecting Gmail failed.'}</span>
            <button type="button" className="underline" onClick={() => setParams({})}>
              dismiss
            </button>
          </div>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>Gmail mailbox</CardTitle>
            <Badge tone={gmail?.connected ? 'success' : 'danger'}>
              {gmail?.connected ? 'connected' : 'not connected'}
            </Badge>
          </CardHeader>
          <CardBody className="space-y-3 text-xs">
            {gmail?.connected ? (
              <>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Sending as</span>
                  <span className="font-mono">{gmail.email}</span>
                </div>
                {gmail.displayName ? (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Display name</span>
                    <span>{gmail.displayName}</span>
                  </div>
                ) : null}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Connected</span>
                  <span>{formatDateTime(gmail.lastValidatedAt)}</span>
                </div>
                <p className="text-muted-foreground">
                  Scopes: <span className="font-mono">{gmail.scopes.join(' ')}</span>
                </p>
                {gmail.lastError ? <p className="text-danger">{gmail.lastError}</p> : null}

                {!gmail.canReadSignature ? (
                  <div className="space-y-2 rounded-[var(--radius-sm)] border border-warning/30 bg-warning-subtle px-3 py-2 text-warning">
                    <p>
                      This connection cannot read your Gmail signature. Disconnect and connect
                      again to grant the settings permission — then every send can carry the same
                      HTML signature you use in Gmail.
                    </p>
                    <Button
                      variant="outline"
                      disabled={disconnect.isPending}
                      onClick={() => disconnect.mutate()}
                    >
                      <Unlink />
                      Disconnect to reconnect
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <p className="text-muted-foreground">
                      Signature below is read from Gmail. Edit it in Gmail → Settings → See all
                      settings → Signature. It is appended to every send.
                    </p>
                    {gmail.signatureHtml ? (
                      <iframe
                        title="Gmail signature preview"
                        sandbox=""
                        srcDoc={`<!DOCTYPE html><html><body style="margin:0;font:13px/1.4 system-ui,sans-serif">${gmail.signatureHtml}</body></html>`}
                        className="h-40 w-full rounded-[var(--radius-sm)] border bg-white"
                      />
                    ) : (
                      <p className="rounded-[var(--radius-sm)] border border-dashed px-3 py-2 text-muted-foreground">
                        No signature is set on this mailbox in Gmail yet.
                      </p>
                    )}
                  </div>
                )}

                <Button
                  variant="outline"
                  disabled={disconnect.isPending}
                  onClick={() => disconnect.mutate()}
                >
                  <Unlink />
                  Disconnect
                </Button>
              </>
            ) : (
              <>
                <p className="text-muted-foreground">
                  Nothing can be sent until a mailbox is connected. The address you authorise
                  becomes the From and Reply-To for every email — Gmail forces this, so it cannot
                  be set by hand. Your Gmail HTML signature is read from the account and appended
                  to each send.
                </p>
                {gmail && !gmail.configured ? (
                  <p className="text-danger">
                    GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not set in apps/api/.env. See the
                    README for the Google Cloud walkthrough.
                  </p>
                ) : null}
                {/* A real anchor, not a fetch: /auth/google issues a 302 to
                    Google's consent screen, so the browser must navigate. */}
                <a
                  href="/auth/google"
                  aria-disabled={!gmail?.configured}
                  className={cn(
                    buttonVariants(),
                    'w-fit',
                    !gmail?.configured && 'pointer-events-none opacity-45',
                  )}
                >
                  <Link2 className="size-4" />
                  Connect Gmail
                </a>
              </>
            )}
            <ErrorBanner error={disconnect.error} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Unsubscribe link</CardTitle>
          </CardHeader>
          <CardBody className="space-y-2">
            <label className="flex cursor-pointer items-start gap-2.5 text-xs">
              <Checkbox
                checked={includeUnsubLink}
                disabled={update.isPending}
                onCheckedChange={(checked) => toggleUnsub(checked === true)}
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">Append an Unsubscribe link to every send</span>
                <span className="mt-0.5 block text-muted-foreground">
                  When off, mail still includes the opt-out sentence and your Gmail signature, but
                  not the per-contact unsubscribe URL.
                </span>
              </span>
            </label>
            <ErrorBanner error={update.error} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Daily cap</CardTitle>
            <Button
              size="sm"
              disabled={update.isPending}
              onClick={() => update.mutate({ dailyCap })}
            >
              {update.isPending ? 'Saving…' : 'Save'}
            </Button>
          </CardHeader>
          <CardBody className="space-y-2">
            <Field
              label={`Sends per Brisbane calendar day (max ${settings.hardMaxDailyCap})`}
              hint={`Currently enforcing ${settings.effectiveDailyCap}. The server clamps this to ${settings.hardMaxDailyCap} regardless of what is stored.`}
            >
              <Input
                type="number"
                min={1}
                max={settings.hardMaxDailyCap}
                className="max-w-28"
                value={dailyCap}
                onChange={(e) => setDailyCap(Number(e.target.value) || 1)}
              />
            </Field>
            {overCap ? (
              <p className="rounded-[var(--radius-sm)] bg-warning-subtle px-2.5 py-2 text-xs text-warning">
                Above {settings.recommendedDailyCap}/day from a single mailbox is the fastest way
                to damage your domain reputation. The low cap is the product, not a limitation.
              </p>
            ) : null}
            <ErrorBanner error={update.error} />
          </CardBody>
        </Card>
      </div>
    </>
  );
}
