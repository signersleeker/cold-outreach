const BRISBANE = 'Australia/Brisbane';

/** Absolute Brisbane time — the timezone the daily cap is measured in. */
export function formatDateTime(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-AU', {
    timeZone: BRISBANE,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

export function formatDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-AU', {
    timeZone: BRISBANE,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function formatRelative(iso: string | null): string {
  if (!iso) return 'never';
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['minute', 60],
    ['hour', 3600],
    ['day', 86400],
    ['week', 604800],
    ['month', 2629800],
    ['year', 31557600],
  ];
  let chosen: Intl.RelativeTimeFormatUnit = 'minute';
  let divisor = 60;
  for (const [unit, size] of units) {
    if (seconds >= size) {
      chosen = unit;
      divisor = size;
    }
  }
  const formatter = new Intl.RelativeTimeFormat('en-AU', { numeric: 'auto' });
  return formatter.format(-Math.round(seconds / divisor), chosen);
}

export function plural(count: number, singular: string, plural?: string): string {
  return `${count} ${count === 1 ? singular : (plural ?? `${singular}s`)}`;
}

export function fullName(contact: { firstName: string; lastName: string }): string {
  return [contact.firstName, contact.lastName].filter(Boolean).join(' ');
}

export function websiteHref(value: string): string {
  const trimmed = value.trim();
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}
