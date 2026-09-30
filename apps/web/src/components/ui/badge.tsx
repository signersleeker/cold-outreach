import { type VariantProps, cva } from 'class-variance-authority';
import type * as React from 'react';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
  {
    variants: {
      tone: {
        success: 'border-transparent bg-success-subtle text-success',
        warning: 'border-transparent bg-warning-subtle text-warning',
        danger: 'border-transparent bg-danger-subtle text-danger',
        muted: 'border-transparent bg-muted text-muted-foreground',
        // Butter badge from the kit. Brand rule: butter is never a text colour,
        // so the label is ink via highlight-foreground.
        highlight: 'border-transparent bg-highlight text-highlight-foreground',
        accent: 'border-transparent bg-accent text-accent-foreground',
        outline: 'border-border text-foreground',
      },
    },
    defaultVariants: { tone: 'muted' },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
