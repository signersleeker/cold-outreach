import type * as React from 'react';
import { cn } from '@/lib/utils';

export function TableWrap({ className, ...props }: React.ComponentProps<'div'>) {
  // Wide tables scroll inside their own container so the page never scrolls sideways.
  return <div className={cn('w-full overflow-x-auto', className)} {...props} />;
}

export function Table({ className, ...props }: React.ComponentProps<'table'>) {
  return <table className={cn('w-full text-sm', className)} {...props} />;
}

export function Th({ className, ...props }: React.ComponentProps<'th'>) {
  return (
    <th
      className={cn(
        'border-b border-border bg-surface px-3 py-2.5 text-left font-mono text-caption font-medium tracking-wider text-muted-foreground uppercase whitespace-nowrap',
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: React.ComponentProps<'td'>) {
  return (
    <td
      className={cn('border-b border-border px-3 py-2.5 align-middle', className)}
      {...props}
    />
  );
}

export function Tr({ className, ...props }: React.ComponentProps<'tr'>) {
  return (
    <tr
      className={cn('transition-colors last:[&>td]:border-b-0 hover:bg-accent/70', className)}
      {...props}
    />
  );
}
