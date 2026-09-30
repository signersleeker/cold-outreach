import { type VariantProps, cva } from 'class-variance-authority';
import { AlertTriangle, Ban, CheckCircle2, Info, X } from 'lucide-react';
import type * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * One banner for every "something needs your attention" surface: gate blockers,
 * missing Gmail, cap warnings, import summaries. Replaces the hand-rolled
 * `rounded border bg-*-subtle px-3 py-2 text-xs text-*` divs that had drifted
 * apart across the pages.
 */
const calloutVariants = cva(
  'flex items-start gap-2.5 rounded-[var(--radius-md)] border px-3 py-2.5 text-xs',
  {
    variants: {
      tone: {
        neutral: 'border-border bg-surface text-foreground',
        info: 'border-primary/20 bg-accent text-accent-foreground',
        success: 'border-success/25 bg-success-subtle text-success',
        warning: 'border-warning/25 bg-warning-subtle text-warning',
        danger: 'border-danger/25 bg-danger-subtle text-danger',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
);

const TONE_ICON = {
  neutral: Info,
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: Ban,
} as const;

export interface CalloutProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'>,
    VariantProps<typeof calloutVariants> {
  title?: React.ReactNode;
  /** Pass `null` to drop the icon entirely (dense inline lists). */
  icon?: React.ComponentType<{ className?: string }> | null;
  action?: React.ReactNode;
  onDismiss?: () => void;
}

export function Callout({
  className,
  tone,
  title,
  icon,
  action,
  onDismiss,
  children,
  ...props
}: CalloutProps) {
  const Icon = icon === null ? null : (icon ?? TONE_ICON[tone ?? 'neutral']);

  return (
    <div className={cn(calloutVariants({ tone }), className)} {...props}>
      {Icon ? <Icon className="mt-px size-3.5 shrink-0 opacity-80" /> : null}
      <div className="min-w-0 flex-1 space-y-1.5">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className="[&_a]:font-semibold [&_a]:underline">{children}</div> : null}
        {action ? <div className="pt-0.5">{action}</div> : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="-my-0.5 -mr-1 shrink-0 rounded-full p-1 opacity-60 transition-opacity hover:opacity-100"
        >
          <X className="size-3.5" />
        </button>
      ) : null}
    </div>
  );
}
