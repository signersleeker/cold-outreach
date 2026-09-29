import type { ContactFilter } from './api';

export interface ContactsQuery {
  q?: string;
  status?: ContactFilter;
  limit?: number;
  offset?: number;
}

export const queryKeys = {
  session: ['session'] as const,
  dashboard: ['dashboard'] as const,
  contacts: (params: ContactsQuery) => ['contacts', params] as const,
  contact: (id: string) => ['contacts', id] as const,
  templates: ['templates'] as const,
  sendPreview: (contactId: string, templateId: string, acknowledge: string[]) =>
    ['send-preview', contactId, templateId, [...acknowledge].sort()] as const,
  sendHistory: (contactId?: string) => ['sends', contactId ?? 'all'] as const,
  suppressions: ['suppressions'] as const,
  settings: ['settings'] as const,
  gmailStatus: ['gmail-status'] as const,
};
