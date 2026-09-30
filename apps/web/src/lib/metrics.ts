/**
 * Numbers the dashboard reads from the activity series, derived on the client.
 *
 * The API already returns the daily series the chart needs, so week-over-week,
 * pace and streak are folded out of that same payload rather than added to the
 * dashboard endpoint — one fetch, no second source of truth for "how many went
 * out on the 12th". Pure functions, so the thresholds stay testable.
 */
import type { ActivityDay, SendActivity } from './api';

export interface SendMetrics {
  /** Everything that left the mailbox across the whole window. */
  total: number;
  last7: number;
  prev7: number;
  /** last7 against prev7 as a signed fraction; null when there is no prior week. */
  weekChange: number | null;
  /** Mean sends per day over the last 7 days — the pace runway is read against. */
  pace: number;
  /** Consecutive days with a send, counting back from today. */
  streak: number;
  bounced: number;
  stopped: number;
  /** Share of the window's sends that did not hard-bounce; null with no sends. */
  deliveredRate: number | null;
  /** Last 14 days of volume, oldest first, for the tile sparkbars. */
  trend: number[];
}

const totalOf = (days: ActivityDay[], pick: (day: ActivityDay) => number): number =>
  days.reduce((sum, day) => sum + pick(day), 0);

/** A day with nothing sent *yet* is not a broken run, so today can't end one —
 *  otherwise every streak would read zero until the first send of the morning. */
function streakOf(days: ActivityDay[]): number {
  let index = days.length - 1;
  if (index >= 0 && days[index].sent === 0) index -= 1;
  let streak = 0;
  for (; index >= 0 && days[index].sent > 0; index -= 1) streak += 1;
  return streak;
}

export function sendMetrics(activity: SendActivity): SendMetrics {
  const { days } = activity;
  const last7 = totalOf(days.slice(-7), (day) => day.sent);
  const prev7 = totalOf(days.slice(-14, -7), (day) => day.sent);
  const bounced = totalOf(days, (day) => day.bounced);
  const hasPriorWeek = days.length >= 14 && prev7 > 0;

  return {
    total: activity.totalSent,
    last7,
    prev7,
    weekChange: hasPriorWeek ? (last7 - prev7) / prev7 : null,
    pace: last7 / Math.min(7, Math.max(days.length, 1)),
    streak: streakOf(days),
    bounced,
    stopped: totalOf(days, (day) => day.stopped),
    deliveredRate: activity.totalSent > 0 ? 1 - bounced / activity.totalSent : null,
    trend: days.slice(-14).map((day) => day.sent),
  };
}

/** How long the ready pile lasts at the current pace. Null when idle or empty —
 *  "∞ days of runway" for an operator who hasn't sent anything is noise. */
export function runwayDays(contactsReady: number, pace: number): number | null {
  if (pace <= 0 || contactsReady <= 0) return null;
  return contactsReady / pace;
}

/** Hard-bounce thresholds. Deliberately stricter than the 2% figure the big ESPs
 *  quote: at this volume a single bad address is a large share of the window, and
 *  the operator would rather look early than be told once it matters. */
export function deliverabilityTone(rate: number | null): 'default' | 'success' | 'warning' | 'danger' {
  if (rate === null) return 'default';
  if (rate < 0.95) return 'danger';
  if (rate < 0.98) return 'warning';
  return 'success';
}
