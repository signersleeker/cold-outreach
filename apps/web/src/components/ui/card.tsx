import { Inbox } from 'lucide-react';
import type * as React from 'react';
import { cn } from '@/lib/utils';

export function Card({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn('rounded-[var(--radius-lg)] border border-border bg-card shadow-soft', className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 border-b border-border px-4 py-3',
        className,
      )}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: React.ComponentProps<'h2'>) {
  return (
    <h2 className={cn('text-sm font-semibold tracking-heading', className)} {...props} />
  );
}

export function CardBody({ className, ...props }: React.ComponentProps<'div'>) {
  return <div className={cn('p-4', className)} {...props} />;
}

/** Data gets JetBrains Mono and a mono caption label, matching the stat block
 *  in the brand guidelines (section 07/08). */
export function StatTile({
  label,
  value,
  hint,
  tone = 'default',
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: 'default' | 'success' | 'warning' | 'danger';
}) {
  const toneClass = {
    default: 'text-foreground',
    success: 'text-success',
    warning: 'text-warning',
    danger: 'text-danger',
  }[tone];
  const railClass = {
    default: 'bg-primary/15',
    success: 'bg-success/40',
    warning: 'bg-warning/40',
    danger: 'bg-danger/40',
  }[tone];

  return (
    <Card className="relative overflow-hidden px-4 py-3.5">
      <span aria-hidden className={cn('absolute inset-y-0 left-0 w-0.5', railClass)} />
      <p className="font-mono text-caption tracking-wider text-muted-foreground uppercase">
        {label}
      </p>
      <p className={cn('mt-1.5 font-mono text-[1.75rem] leading-none font-semibold tabular-nums', toneClass)}>
        {value}
      </p>
      {hint ? <p className="mt-2 text-xs text-muted-foreground">{hint}</p> : null}
    </Card>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = Inbox,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex flex-col items-center gap-2.5 px-4 py-14 text-center">
      <span className="grid size-10 place-items-center rounded-full bg-accent text-accent-foreground">
        <Icon className="size-4.5" />
      </span>
      <p className="text-sm font-semibold">{title}</p>
      {description ? (
        <p className="max-w-md text-xs leading-relaxed text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-1.5">{action}</div> : null}
    </div>
  );
}
