import { Link2, Unlink } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ErrorBanner, PageHeader } from '@/components/AppLayout';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, Input, Textarea } from '@/components/ui/input';
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

  const [draft, setDraft] = useState({
    senderName: '',
    senderTitle: '',
    companyLegal: '',
    replyHint: '',
    dailyCap: 20,
  });

  useEffect(() => {
    if (settings) {
      setDraft({
        senderName: settings.senderName,
        senderTitle: settings.senderTitle,
        companyLegal: settings.companyLegal,
        replyHint: settings.replyHint,
        dailyCap: settings.dailyCap,
      });
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

  const overCap = draft.dailyCap > settings.recommendedDailyCap;

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
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Connected</span>
                  <span>{formatDateTime(gmail.lastValidatedAt)}</span>
                </div>
                <p className="text-muted-foreground">
                  Scopes: <span className="font-mono">{gmail.scopes.join(' ')}</span>
                </p>
                {gmail.lastError ? <p className="text-danger">{gmail.lastError}</p> : null}
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
                  be set by hand.
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
            <CardTitle>Sender identity</CardTitle>
            <Button
              size="sm"
              disabled={update.isPending}
              onClick={() => update.mutate(draft)}
            >
              {update.isPending ? 'Saving…' : 'Save'}
            </Button>
          </CardHeader>
          <CardBody className="space-y-3">
            <p className="text-xs text-muted-foreground">
              These appear in the identity block appended to every email. Accurate sender
              identification is a legal requirement for a commercial electronic message, so a send
              is blocked while any of them is blank.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Sender name">
                <Input
                  value={draft.senderName}
                  onChange={(e) => setDraft((d) => ({ ...d, senderName: e.target.value }))}
                />
              </Field>
              <Field label="Sender title">
                <Input
                  value={draft.senderTitle}
                  onChange={(e) => setDraft((d) => ({ ...d, senderTitle: e.target.value }))}
                />
              </Field>
              <Field label="Legal company name">
                <Input
                  value={draft.companyLegal}
                  onChange={(e) => setDraft((d) => ({ ...d, companyLegal: e.target.value }))}
                />
              </Field>
              <Field label="From address" hint="Read from the Gmail profile. Not editable.">
                <Input value={settings.fromEmail} readOnly className="bg-muted text-muted-foreground" />
              </Field>
            </div>
            <Field label="Reply hint" hint="A note to yourself, shown in the app. Never an email header.">
              <Textarea
                rows={2}
                value={draft.replyHint}
                onChange={(e) => setDraft((d) => ({ ...d, replyHint: e.target.value }))}
              />
            </Field>
            <ErrorBanner error={update.error} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Daily cap</CardTitle>
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
                value={draft.dailyCap}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, dailyCap: Number(e.target.value) || 1 }))
                }
              />
            </Field>
            {overCap ? (
              <p className="rounded-[var(--radius-sm)] bg-warning-subtle px-2.5 py-2 text-xs text-warning">
                Above {settings.recommendedDailyCap}/day from a single mailbox is the fastest way
                to damage your domain reputation. The low cap is the product, not a limitation.
              </p>
            ) : null}
          </CardBody>
        </Card>
      </div>
    </>
  );
}
