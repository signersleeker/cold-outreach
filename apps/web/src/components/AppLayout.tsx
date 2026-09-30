import {
  Building2,
  FileText,
  Gauge,
  LogOut,
  Settings as SettingsIcon,
  ShieldBan,
  Users,
} from 'lucide-react';
import type * as React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { TaddarLockup } from '@/components/brand/Logo';
import { useDashboard, useLogout } from '@/hooks';
import { cn } from '@/lib/utils';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Callout } from './ui/callout';

const NAV = [
  { to: '/', label: 'Dashboard', icon: Gauge, end: true },
  { to: '/contacts', label: 'Contacts', icon: Users, end: false },
  { to: '/companies', label: 'Companies', icon: Building2, end: false },
  { to: '/templates', label: 'Templates', icon: FileText, end: false },
  { to: '/suppressions', label: 'Suppressions', icon: ShieldBan, end: false },
  { to: '/settings', label: 'Settings', icon: SettingsIcon, end: false },
];

/** The daily cap is the product, so it gets a real meter rather than a number.
 *  Coral only at the cap — one accent, and only when it means "stop". */
function CapMeter({ sent, cap }: { sent: number; cap: number }) {
  const pct = cap > 0 ? Math.min(100, (sent / cap) * 100) : 0;
  const remaining = Math.max(0, cap - sent);
  const atCap = sent >= cap;
  const close = !atCap && remaining <= 3;

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between">
        <span className="text-caption text-muted-foreground">Sent today</span>
        <span
          className={cn(
            'font-mono text-xs font-semibold tabular-nums',
            atCap ? 'text-signal-text' : close ? 'text-warning' : 'text-foreground',
          )}
        >
          {sent}/{cap}
        </span>
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-border"
        role="progressbar"
        aria-valuenow={sent}
        aria-valuemin={0}
        aria-valuemax={cap}
        aria-label="Sends used today"
      >
        <div
          className={cn(
            'h-full rounded-full transition-[width] duration-500',
            atCap ? 'bg-signal' : close ? 'bg-highlight' : 'bg-primary',
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { data: dashboard } = useDashboard();
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen bg-surface">
      <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-border bg-card">
        <div className="px-4 py-4">
          <TaddarLockup className="text-foreground" />
          <p className="mt-1.5 text-caption text-muted-foreground">Founder-led 1:1 outreach</p>
        </div>

        <nav className="flex flex-col gap-0.5 px-2.5">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-accent font-semibold text-accent-foreground'
                    : 'text-muted-foreground hover:bg-surface hover:text-foreground',
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    aria-hidden
                    className={cn(
                      'absolute left-0 h-4 w-0.5 rounded-r-full bg-primary transition-opacity',
                      isActive ? 'opacity-100' : 'opacity-0',
                    )}
                  />
                  <Icon className="size-4 shrink-0" />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto space-y-3 border-t border-border px-3 py-3.5">
          {dashboard ? (
            <>
              <CapMeter sent={dashboard.sendsToday} cap={dashboard.dailyCap} />
              <div className="flex items-center justify-between">
                <span className="text-caption text-muted-foreground">Gmail</span>
                <Badge tone={dashboard.gmailConnected ? 'success' : 'danger'}>
                  {dashboard.gmailConnected ? 'connected' : 'not connected'}
                </Badge>
              </div>
            </>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start text-muted-foreground"
            onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
          >
            <LogOut className="size-4" />
            Sign out
          </Button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="sticky top-0 z-30 flex flex-wrap items-start justify-between gap-3 border-b border-border bg-background/85 px-6 py-3.5 backdrop-blur-sm">
      <div className="min-w-0">
        <h1 className="truncate text-[0.9375rem] font-semibold tracking-heading">{title}</h1>
        {description ? (
          <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}

/** Every page body shares one gutter and rhythm, so pages stop drifting apart. */
export function PageBody({ className, ...props }: React.ComponentProps<'div'>) {
  return <div className={cn('space-y-4 px-6 py-5', className)} {...props} />;
}

export function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;
  const messages =
    error instanceof Error && 'messages' in error
      ? (error as { messages: string[] }).messages
      : [String(error instanceof Error ? error.message : error)];
  return (
    <Callout tone="danger">
      {messages.map((m) => (
        <p key={m}>{m}</p>
      ))}
    </Callout>
  );
}
