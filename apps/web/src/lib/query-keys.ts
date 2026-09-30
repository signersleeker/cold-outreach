import type { ContactFilter, NoteTarget } from './api';

export interface ContactsQuery {
  q?: string;
  status?: ContactFilter;
  companyId?: string;
  industry?: string;
  limit?: number;
  offset?: number;
}

export interface CompaniesQuery {
  q?: string;
  limit?: number;
  offset?: number;
}

export const queryKeys = {
  session: ['session'] as const,
  dashboard: ['dashboard'] as const,
  sendActivity: (days: number) => ['dashboard', 'activity', days] as const,
  contacts: (params: ContactsQuery) => ['contacts', params] as const,
  // Under the 'contacts' prefix so the existing invalidations already cover it.
  contactStats: (params: Pick<ContactsQuery, 'q' | 'companyId' | 'industry'>) =>
    ['contacts', 'stats', params] as const,
  contact: (id: string) => ['contacts', id] as const,
  companies: (params: CompaniesQuery) => ['companies', params] as const,
  company: (id: string) => ['companies', id] as const,
  notes: (notableType: NoteTarget, notableId: string) =>
    ['notes', notableType, notableId] as const,
  templates: ['templates'] as const,
  templateGroups: ['template-groups'] as const,
  followUpCalendar: (year: number, month: number) =>
    ['follow-ups', 'calendar', year, month] as const,
  contactFollowUp: (contactId: string) => ['follow-ups', 'contact', contactId] as const,
  sendPreview: (contactId: string, templateId: string, acknowledge: string[]) =>
    ['send-preview', contactId, templateId, [...acknowledge].sort()] as const,
  sendHistory: (contactId?: string) => ['sends', contactId ?? 'all'] as const,
  suppressions: ['suppressions'] as const,
  settings: ['settings'] as const,
  gmailStatus: ['gmail-status'] as const,
};
