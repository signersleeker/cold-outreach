import { cn } from '@/lib/utils';

/**
 * Taddar mark, drawn from the anatomy in the brand guidelines (section 02):
 * ultraviolet bubble rounded at 24% of the icon width with the tail pointing
 * bottom-left, a white envelope whose flap and seam form the T, and the coral
 * reply dot overlapping the top-right corner.
 *
 * NOTE: the guidelines ship taddar-icon.svg / taddar-lockup.svg with the
 * wordmark supplied as outlines ("never retype it"). Those files weren't in the
 * handoff, so this is a faithful reconstruction and the wordmark below is set
 * live in Inter SemiBold at the specified -4.7% tracking. Swap both for the
 * official assets when they land.
 */

type MarkVariant = 'full' | 'reversed' | 'mono';

const BUBBLE = {
  full: '#3423A6',
  reversed: '#FFFFFF',
  mono: 'currentColor',
} as const;

const ENVELOPE = {
  full: '#FFFFFF',
  reversed: '#3423A6',
  mono: 'currentColor',
} as const;

export function TaddarIcon({
  variant = 'full',
  className,
  title,
}: {
  variant?: MarkVariant;
  className?: string;
  title?: string;
}) {
  const bubble = BUBBLE[variant];
  const envelope = ENVELOPE[variant];
  // Mono is one colour by definition, so the dot joins the bubble rather than
  // staying coral — matching taddar-lockup-mono-*.svg in the guidelines.
  const dot = variant === 'mono' ? 'currentColor' : '#FF6B5B';

  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('shrink-0', className)}
      role={title ? 'img' : 'presentation'}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      {title ? <title>{title}</title> : null}
      {/* Bubble tail — always bottom-left. Drawn first so the body covers the join. */}
      <path d="M5 24 L0.5 38.5 L15.5 32 Z" fill={bubble} />
      <rect x="0" y="0" width="34" height="34" rx="8.16" fill={bubble} />
      {/* Envelope body */}
      <rect
        x="8.6"
        y="10.9"
        width="16.8"
        height="12.4"
        rx="2.2"
        stroke={envelope}
        strokeWidth="2.1"
      />
      {/* Flap + seam: the T. */}
      <path
        d="M10.6 13.9 L17 18.1 L23.4 13.9"
        stroke={envelope}
        strokeWidth="2.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M17 18.1 V22.4" stroke={envelope} strokeWidth="2.1" strokeLinecap="round" />
      {/* Reply dot. Never recoloured, never moved. */}
      <circle cx="33" cy="7" r="6.6" fill={dot} />
    </svg>
  );
}

/**
 * Icon + wordmark. `size` controls the icon; the wordmark scales with it.
 * The guidelines set a 96px minimum for the lockup in print — on screen the
 * sidebar renders it at 28px icon height, which is the app-icon size, so the
 * wordmark is set rather than scaled down from the print lockup.
 */
export function TaddarLockup({
  variant = 'full',
  className,
  iconClassName,
}: {
  variant?: MarkVariant;
  className?: string;
  iconClassName?: string;
}) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <TaddarIcon variant={variant} className={cn('size-7', iconClassName)} title="Taddar" />
      <span
        className="text-[1.0625rem] leading-none font-semibold lowercase"
        // -4.7% tracking, per the wordmark spec.
        style={{ letterSpacing: '-0.047em' }}
      >
        taddar
      </span>
    </span>
  );
}
