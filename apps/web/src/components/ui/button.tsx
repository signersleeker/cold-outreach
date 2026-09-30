import { type VariantProps, cva } from 'class-variance-authority';
import type * as React from 'react';
import { cn } from '@/lib/utils';

// Pill shape, semibold label and the 2px/2px focus ring come from the brand
// kit's btn-* components; the h-8 sizes stay dense for an internal tool.
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-full text-sm font-semibold tracking-[-0.005em] transition-[background-color,box-shadow,transform] outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring active:translate-y-px disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground shadow-card hover:bg-primary-hover',
        // Coral CTA. Brand rule: ink text on coral, never white.
        signal: 'bg-signal text-signal-foreground hover:bg-signal-hover',
        danger: 'bg-danger text-danger-foreground hover:bg-danger/90',
        outline: 'border border-border bg-card hover:bg-accent hover:text-accent-foreground',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-link underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-8 px-3',
        sm: 'h-7 px-2 text-xs',
        lg: 'h-9 px-4',
        icon: 'size-8',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { buttonVariants };
