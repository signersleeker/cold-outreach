import {
  FileText,
  Gauge,
  LogOut,
  Settings as SettingsIcon,
  ShieldBan,
  Users,
} from 'lucide-react';
import type * as React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useDashboard, useLogout } from '@/hooks';
import { cn } from '@/lib/utils';
import { Badge } from './ui/badge';
import { Button } from './ui/button';

const NAV = [
  { to: '/', label: 'Dashboard', icon: Gauge, end: true },
  { to: '/contacts', label: 'Contacts', icon: Users, end: false },
  { to: '/templates', label: 'Templates', icon: FileText, end: false },
  { to: '/suppressions', label: 'Suppressions', icon: ShieldBan, end: false },
  { to: '/settings', label: 'Settings', icon: SettingsIcon, end: false },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { data: dashboard } = useDashboard();
  const logout = useLogout();
  const navigate = useNavigate();

  const atCap = dashboard ? dashboard.sendsToday >= dashboard.dailyCap : false;

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-52 shrink-0 flex-col border-r bg-muted/30">
        <div className="px-4 py-4">
          <p className="text-sm font-semibold tracking-tight">Kinnatic Outreach</p>
          <p className="mt-0.5 text-xs text-muted-foreground">Founder-led 1:1</p>
        </div>

        <nav className="flex flex-col gap-0.5 px-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-[var(--radius-sm)] px-2.5 py-1.5 text-sm transition-colors',
                  isActive
                    ? 'bg-card font-medium text-foreground shadow-xs'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                )
              }
            >
              <Icon className="size-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto space-y-2 border-t px-3 py-3">
          {dashboard ? (
            <div className="space-y-1.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Sent today</span>
                <span className={cn('font-mono font-semibold', atCap && 'text-danger')}>
                  {dashboard.sendsToday}/{dashboard.dailyCap}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Gmail</span>
                <Badge tone={dashboard.gmailConnected ? 'success' : 'danger'}>
                  {dashboard.gmailConnected ? 'connected' : 'not connected'}
                </Badge>
              </div>
            </div>
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
    <header className="flex flex-wrap items-start justify-between gap-3 border-b px-6 py-4">
      <div>
        <h1 className="text-base font-semibold">{title}</h1>
        {description ? (
          <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;
  const messages =
    error instanceof Error && 'messages' in error
      ? (error as { messages: string[] }).messages
      : [String(error instanceof Error ? error.message : error)];
  return (
    <div className="rounded-[var(--radius-sm)] border border-danger/30 bg-danger-subtle px-3 py-2 text-xs text-danger">
      {messages.map((m) => (
        <p key={m}>{m}</p>
      ))}
    </div>
  );
}
