import { Inbox } from 'lucide-react';
import type * as React from 'react';
import { cn } from '@/lib/utils';

/** The card surface on its own, for the few places that need it on an element
 *  other than a div — a whole card that is also a link, mainly. */
export const cardClass = 'rounded-[var(--radius-lg)] border border-border bg-card shadow-soft';

export function Card({ className, ...props }: React.ComponentProps<'div'>) {
  return <div className={cn(cardClass, className)} {...props} />;
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
