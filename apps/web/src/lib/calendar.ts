/**
 * Month-grid geometry, shared by the follow-up and sent-email calendars.
 *
 * Everything here works in UTC deliberately. These are calendar dates, not
 * instants: `new Date('2026-03-01')` parses as UTC midnight, so doing the
 * arithmetic in local time would shift the grid a day west of Greenwich.
 */

export interface MonthCursor {
  year: number;
  /** 1-indexed, as it appears in a `YYYY-MM-DD` string. */
  month: number;
}

export interface MonthCell {
  /** `YYYY-MM-DD`, or null for the blank pad cells either side of the month. */
  date: string | null;
  dayNum: number | null;
}

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export function parseYmd(value: string): { year: number; month: number; day: number } {
  const [year, month, day] = value.split('-').map(Number);
  return { year, month, day };
}

export function ymd(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

export function monthLabel(year: number, month: number): string {
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString('en-AU', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/** Blank cells before the 1st, with the week starting on Monday. */
export function mondayOffset(year: number, month: number): number {
  const weekday = new Date(Date.UTC(year, month - 1, 1)).getUTCDay();
  return (weekday + 6) % 7;
}

export function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** The month padded to whole weeks, ready to drop into a 7-column grid. */
export function monthCells(year: number, month: number): MonthCell[] {
  const cells: MonthCell[] = [];
  for (let i = 0; i < mondayOffset(year, month); i++) cells.push({ date: null, dayNum: null });
  for (let day = 1; day <= daysInMonth(year, month); day++) {
    cells.push({ date: ymd(year, month, day), dayNum: day });
  }
  while (cells.length % 7 !== 0) cells.push({ date: null, dayNum: null });
  return cells;
}

export function shiftMonth(cursor: MonthCursor, delta: number): MonthCursor {
  const date = new Date(Date.UTC(cursor.year, cursor.month - 1 + delta, 1));
  return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1 };
}

/** The current month in the viewer's local time — only ever a starting cursor. */
export function currentMonth(): MonthCursor {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}
