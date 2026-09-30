import { type ClassValue, clsx } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

/**
 * The brand kit ships its own font-size scale (text-display … text-caption).
 * tailwind-merge only knows Tailwind's stock sizes, so it filed those names
 * under text-*colour* — which meant a later colour class silently deleted the
 * size: `cn('text-caption', 'text-primary')` rendered at the inherited size
 * instead of 12px. Teaching it the scale puts size and colour back in separate
 * conflict groups.
 *
 * Only bites through `cn()`; a plain className string is never merged.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [
        {
          text: ['display', 'h1', 'h2', 'h3', 'h4', 'body-lg', 'body', 'small', 'caption'],
        },
      ],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
