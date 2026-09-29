/**
 * Presentation only: gate code -> short label.
 *
 * There is deliberately NO gate logic here. Whether a send may proceed is
 * decided solely by app/sends/gates.py on the server, which re-evaluates inside
 * the sending transaction. Reimplementing any of it in TypeScript would create a
 * second source of truth that drifts, and the disabled Send button is a courtesy
 * to the operator rather than the control.
 */

export const GATE_LABELS: Record<string, string> = {
  // blockers
  gmail_not_connected: 'Gmail not connected',
  settings_incomplete: 'Sender identity incomplete',
  template_missing: 'Template missing',
  email_invalid: 'Invalid address',
  contact_suppressed: 'Suppressed',
  cooldown_active: 'Cooldown active',
  daily_cap_reached: 'Daily cap reached',
  unrendered_merge_tags: 'Unfilled merge fields',
  subject_empty: 'Empty subject',
  body_empty: 'Empty body',
  warning_not_acknowledged: 'Needs confirmation',
  // warnings
  validation_risky: 'Risky address',
  validation_pending: 'Not yet validated',
  validation_unknown: 'Validation inconclusive',
  consumer_domain: 'Personal mailbox',
  missing_company: 'No company',
  missing_title: 'No title',
  multiple_links: 'Multiple links',
  no_source_recorded: 'No source recorded',
};

export const gateLabel = (code: string): string =>
  GATE_LABELS[code] ?? code.replace(/_/g, ' ');

export const VALIDATION_TONE: Record<string, 'success' | 'warning' | 'danger' | 'muted'> = {
  valid: 'success',
  risky: 'warning',
  unknown: 'warning',
  pending: 'muted',
  invalid: 'danger',
};

export const SEND_STATUS_TONE: Record<string, 'success' | 'warning' | 'danger' | 'muted'> = {
  sent: 'success',
  queued: 'warning',
  failed: 'danger',
  bounced: 'danger',
  replied_stop: 'muted',
};

export const SUPPRESSION_REASON_LABELS: Record<string, string> = {
  unsub: 'Used unsubscribe link',
  bounce: 'Permanent bounce',
  complaint: 'Spam complaint',
  manual: 'Added manually',
  reply_no: 'Replied to stop',
};
