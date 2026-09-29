/**
 * Every network call in the app lives here, with its wire types.
 *
 * Relative URLs only — the Vite proxy forwards /api to the backend in dev, and
 * in production the SPA is served from the same origin. There is no base URL to
 * configure and no CORS to negotiate.
 */

// ---------------------------------------------------------------- envelope ----
type DataEnvelope<T> = { data: T };
type ListEnvelope<T, M = unknown> = { data: T; meta: M };
type ErrorEnvelope = { errors: { message: string }[] };

export class ApiError extends Error {
  readonly status: number;
  readonly messages: string[];

  constructor(status: number, messages: string[]) {
    super(messages[0] ?? 'Request failed');
    this.status = status;
    this.messages = messages;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...init,
    headers:
      init?.body instanceof FormData
        ? init.headers
        : { 'Content-Type': 'application/json', ...init?.headers },
  });

  if (!response.ok) {
    let messages = [`HTTP ${response.status}`];
    try {
      const body = (await response.json()) as ErrorEnvelope;
      if (body.errors?.length) messages = body.errors.map((e) => e.message);
    } catch {
      // Non-JSON error body; keep the status line.
    }
    throw new ApiError(response.status, messages);
  }

  return (await response.json()) as T;
}

const unwrap = async <T>(path: string, init?: RequestInit): Promise<T> =>
  (await request<DataEnvelope<T>>(path, init)).data;

const unwrapList = async <T, M>(path: string, init?: RequestInit): Promise<ListEnvelope<T, M>> =>
  await request<ListEnvelope<T, M>>(path, init);

// ------------------------------------------------------------------- types ----
export type ValidationStatus = 'pending' | 'valid' | 'invalid' | 'risky' | 'unknown';

export type ContactFilter =
  | 'all'
  | 'ready'
  | 'risky'
  | 'invalid'
  | 'pending'
  | 'sent'
  | 'suppressed';

export interface Contact {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  company: string;
  companyId: string | null;
  companyIndustry: string;
  title: string;
  source: string;
  notes: string;
  hook: string;
  validationStatus: ValidationStatus;
  validationDetail: string;
  validatedAt: string | null;
  suppressed: boolean;
  suppressedReason: string;
  suppressedAt: string | null;
  lastSentAt: string | null;
  createdAt: string;
}

/** The editable fields when adding a contact by hand. */
export interface NewContact {
  email: string;
  firstName: string;
  lastName: string;
  company: string;
  title: string;
  hook: string;
  notes: string;
  source: string;
}

export interface DeleteContactResult {
  deleted: boolean;
  email: string;
  sendEventsDeleted: number;
  /** Deleting never lifts a suppression — the opt-out lives in its own table. */
  stillSuppressed: boolean;
}

export interface Template {
  id: string;
  name: string;
  subject: string;
  body: string;
  industry: string;
  referencedVars: string[];
  unknownVars: string[];
  createdAt: string;
  updatedAt: string;
}

export interface TemplateGroupItem {
  position: number;
  templateId: string;
  templateName: string;
  subject: string;
  industry: string;
}

export interface TemplateGroup {
  id: string;
  name: string;
  items: TemplateGroupItem[];
  createdAt: string;
  updatedAt: string;
}

export interface GateFinding {
  code: string;
  message: string;
  requiresAck: boolean;
}

export interface SendPreview {
  subject: string;
  body: string;
  bodyHtml: string;
  signatureHtml: string;
  unsubUrl: string;
  fromEmail: string;
  sendsToday: number;
  dailyCap: number;
  sendable: boolean;
  blockers: GateFinding[];
  warnings: GateFinding[];
  ackRequired: string[];
}

export interface SendEvent {
  id: string;
  contactId: string;
  templateId: string | null;
  subjectRendered: string;
  bodyRendered: string;
  gmailMessageId: string;
  status: 'queued' | 'sent' | 'failed' | 'bounced' | 'replied_stop';
  error: string;
  sentAt: string | null;
  createdAt: string;
}

export interface Suppression {
  id: string;
  email: string;
  reason: string;
  source: string;
  createdAt: string;
}

export interface AppSettings {
  senderName: string;
  senderTitle: string;
  companyLegal: string;
  fromEmail: string;
  replyHint: string;
  dailyCap: number;
  includeUnsubLink: boolean;
  effectiveDailyCap: number;
  hardMaxDailyCap: number;
  recommendedDailyCap: number;
  lastInboxSyncAt: string | null;
  updatedAt: string;
}

export interface GmailStatus {
  connected: boolean;
  configured: boolean;
  email: string;
  scopes: string[];
  status: string;
  lastError: string;
  lastValidatedAt: string | null;
  displayName: string;
  signatureHtml: string;
  canReadSignature: boolean;
}

export interface Dashboard {
  sendsToday: number;
  dailyCap: number;
  brisbaneDate: string;
  gmailConnected: boolean;
  gmailEmail: string;
  identityComplete: boolean;
  lastSend: { email: string; subject: string; sentAt: string | null } | null;
  contactsTotal: number;
  contactsReady: number;
  contactsRisky: number;
  contactsInvalid: number;
  contactsPending: number;
  suppressionsTotal: number;
  suppressionsByReason: Record<string, number>;
  bouncedCount: number;
  stuckQueuedCount: number;
  lastInboxSyncAt: string | null;
}

export interface ImportSummary {
  created: number;
  skippedDupes: number;
  skippedExistingCompany: number;
  invalid: number;
  risky: number;
  valid: number;
  pending: number;
  missingEmail: number;
  suppressedExisting: number;
  truncated: boolean;
  validator: string;
  headersRecognised: Record<string, string>;
}

export interface ImportPreview {
  headers: string[];
  suggestions: Record<string, string | null>;
}

export interface Company {
  id: string;
  name: string;
  website: string;
  industry: string;
  contactCount: number;
  createdAt: string;
}

export interface CompanyDetail {
  id: string;
  name: string;
  website: string;
  industry: string;
  createdAt: string;
  updatedAt: string;
}

export interface CompanyInput {
  name: string;
  website?: string;
  industry?: string;
}

export interface InboxSyncSummary {
  scanned: number;
  stopsFound: number;
  bouncesFound: number;
  softBounces: number;
  autoReplies: number;
  suppressed: number;
  errors: string[];
}

// --------------------------------------------------------------- endpoints ----
export const api = {
  // auth
  login: (password: string) =>
    unwrap<{ authenticated: boolean }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),
  logout: () => unwrap<{ authenticated: boolean }>('/api/v1/auth/logout', { method: 'POST' }),
  session: () => unwrap<{ authenticated: boolean }>('/api/v1/auth/session'),

  // dashboard
  dashboard: () => unwrap<Dashboard>('/api/v1/dashboard'),
  syncInbox: () => unwrap<InboxSyncSummary>('/api/v1/inbox/sync', { method: 'POST' }),

  // contacts
  contacts: (params: {
    q?: string;
    status?: ContactFilter;
    companyId?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params.q) query.set('q', params.q);
    if (params.status && params.status !== 'all') query.set('status', params.status);
    if (params.companyId) query.set('companyId', params.companyId);
    query.set('limit', String(params.limit ?? 50));
    query.set('offset', String(params.offset ?? 0));
    return unwrapList<Contact[], { total: number; limit: number; offset: number }>(
      `/api/v1/contacts?${query}`,
    );
  },
  contact: (id: string) => unwrap<Contact>(`/api/v1/contacts/${id}`),
  createContact: (input: NewContact) =>
    unwrap<Contact>('/api/v1/contacts', { method: 'POST', body: JSON.stringify(input) }),
  deleteContact: (id: string, force = false) =>
    unwrap<DeleteContactResult>(`/api/v1/contacts/${id}?force=${force}`, { method: 'DELETE' }),
  updateContact: (id: string, changes: Partial<Contact>) =>
    unwrap<Contact>(`/api/v1/contacts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),
  revalidateContact: (id: string) =>
    unwrap<Contact>(`/api/v1/contacts/${id}/revalidate`, { method: 'POST' }),
  suppressContact: (id: string, reason: string, note: string) =>
    unwrap<Contact>(`/api/v1/contacts/${id}/suppress`, {
      method: 'POST',
      body: JSON.stringify({ reason, note }),
    }),
  previewImport: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return unwrap<ImportPreview>('/api/v1/contacts/import/preview', {
      method: 'POST',
      body: form,
    });
  },
  importContacts: (
    file: File,
    mapping: Record<string, string>,
    skipValidation = false,
  ) => {
    const form = new FormData();
    form.append('file', file);
    form.append('mapping', JSON.stringify(mapping));
    if (skipValidation) form.append('skipValidation', 'true');
    return unwrap<ImportSummary>('/api/v1/contacts/import', { method: 'POST', body: form });
  },

  // companies
  companies: (params: { q?: string; limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.q) query.set('q', params.q);
    query.set('limit', String(params.limit ?? 50));
    query.set('offset', String(params.offset ?? 0));
    return unwrapList<Company[], { total: number; limit: number; offset: number }>(
      `/api/v1/companies?${query}`,
    );
  },
  company: (id: string) => unwrap<CompanyDetail>(`/api/v1/companies/${id}`),
  createCompany: (input: CompanyInput) =>
    unwrap<CompanyDetail>('/api/v1/companies', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  updateCompany: (id: string, changes: Partial<CompanyInput>) =>
    unwrap<CompanyDetail>(`/api/v1/companies/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),

  // templates
  templates: () => unwrapList<Template[], unknown>('/api/v1/templates'),
  createTemplate: (input: { name: string; subject: string; body: string; industry: string }) =>
    unwrap<Template>('/api/v1/templates', { method: 'POST', body: JSON.stringify(input) }),
  updateTemplate: (
    id: string,
    input: Partial<{ name: string; subject: string; body: string; industry: string }>,
  ) =>
    unwrap<Template>(`/api/v1/templates/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    }),
  deleteTemplate: (id: string) =>
    unwrap<{ deleted: boolean }>(`/api/v1/templates/${id}`, { method: 'DELETE' }),

  templateGroups: () => unwrapList<TemplateGroup[], unknown>('/api/v1/template-groups'),
  createTemplateGroup: (input: { name: string; templateIds: string[] }) =>
    unwrap<TemplateGroup>('/api/v1/template-groups', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  updateTemplateGroup: (
    id: string,
    input: Partial<{ name: string; templateIds: string[] }>,
  ) =>
    unwrap<TemplateGroup>(`/api/v1/template-groups/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    }),
  deleteTemplateGroup: (id: string) =>
    unwrap<{ deleted: boolean }>(`/api/v1/template-groups/${id}`, { method: 'DELETE' }),

  // sends
  previewSend: (input: { contactId: string; templateId: string; acknowledge: string[] }) =>
    unwrap<SendPreview>('/api/v1/sends/preview', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  send: (input: { contactId: string; templateId: string; acknowledge: string[] }) =>
    unwrap<SendEvent>('/api/v1/sends', { method: 'POST', body: JSON.stringify(input) }),
  sendHistory: (contactId?: string) => {
    const query = new URLSearchParams();
    if (contactId) query.set('contactId', contactId);
    return unwrapList<SendEvent[], unknown>(`/api/v1/sends?${query}`);
  },

  // suppressions
  suppressions: () =>
    unwrapList<Suppression[], { total: number; byReason: Record<string, number> }>(
      '/api/v1/suppressions',
    ),
  addSuppression: (input: { email: string; reason: string; source: string }) =>
    unwrap<Suppression>('/api/v1/suppressions', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  removeSuppression: (email: string) =>
    unwrap<{ deleted: boolean }>(`/api/v1/suppressions/${encodeURIComponent(email)}`, {
      method: 'DELETE',
    }),

  // settings + gmail
  settings: () => unwrap<AppSettings>('/api/v1/settings'),
  updateSettings: (changes: Partial<AppSettings>) =>
    unwrap<AppSettings>('/api/v1/settings', {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),
  gmailStatus: () => unwrap<GmailStatus>('/api/v1/gmail/status'),
  disconnectGmail: () =>
    unwrap<{ connected: boolean }>('/api/v1/gmail/disconnect', { method: 'POST' }),
};
