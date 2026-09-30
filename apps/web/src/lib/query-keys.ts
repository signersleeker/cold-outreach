import type { ContactFilter, GroupAssignmentTarget, NoteTarget } from './api';

export interface ContactsQuery {
  q?: string;
  status?: ContactFilter;
  companyId?: string;
  industry?: string;
  group?: string;
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
  // Under the 'dashboard' prefix so the existing send/sync invalidations reach them.
  sentCalendar: (year: number, month: number) =>
    ['dashboard', 'sent', 'calendar', year, month] as const,
  sentEmails: (date: string) => ['dashboard', 'sent', 'day', date] as const,
  contacts: (params: ContactsQuery) => ['contacts', params] as const,
  // Under the 'contacts' prefix so the existing invalidations already cover it.
  contactStats: (params: Pick<ContactsQuery, 'q' | 'companyId' | 'industry' | 'group'>) =>
    ['contacts', 'stats', params] as const,
  groupAssignmentPreview: (
    input: GroupAssignmentTarget & { groupId: string; acknowledge: string[] },
  ) => ['group-assignment-preview', input] as const,
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
