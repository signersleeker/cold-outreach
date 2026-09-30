/**
 * One hook per resource. Components never call fetch and never build query keys.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  type AppSettings,
  type CompanyInput,
  type Contact,
  type NewContact,
  type NoteTarget,
  api,
} from '@/lib/api';
import { type ContactsQuery, queryKeys } from '@/lib/query-keys';

// ------------------------------------------------------------------- auth ----
export const useSession = () =>
  useQuery({ queryKey: queryKeys.session, queryFn: api.session, retry: false });

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => api.login(password),
    onSuccess: (result) => {
      // Seed the session cache synchronously. Invalidating alone would leave the
      // stale `authenticated: false` in place until the refetch resolves, and
      // RequireAuth would bounce straight back to /login in the meantime.
      client.setQueryData(queryKeys.session, result);
      client.invalidateQueries();
    },
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.logout,
    onSuccess: () => client.clear(),
  });
}

// -------------------------------------------------------------- dashboard ----
export const useDashboard = () =>
  useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: api.dashboard,
    refetchInterval: 30_000,
  });

export const useSendActivity = (days = 30) =>
  useQuery({
    queryKey: queryKeys.sendActivity(days),
    queryFn: () => api.sendActivity(days),
    refetchInterval: 60_000,
  });

export function useSyncInbox() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.syncInbox,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: queryKeys.suppressions });
      client.invalidateQueries({ queryKey: ['contacts'] });
    },
  });
}

// --------------------------------------------------------------- contacts ----
export const useContacts = (params: ContactsQuery) =>
  useQuery({
    queryKey: queryKeys.contacts(params),
    queryFn: () => api.contacts(params),
  });

export const useContactStats = (
  params: Pick<ContactsQuery, 'q' | 'companyId' | 'industry'> = {},
) =>
  useQuery({
    queryKey: queryKeys.contactStats(params),
    queryFn: () => api.contactStats(params),
    // Keep the previous counts on screen while a new search settles, so the
    // chips don't flash empty on every keystroke.
    placeholderData: (previous) => previous,
  });

export const useContact = (id: string) =>
  useQuery({ queryKey: queryKeys.contact(id), queryFn: () => api.contact(id), enabled: !!id });

function useContactMutation<TArgs>(mutationFn: (args: TArgs) => Promise<Contact>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (contact) => {
      client.setQueryData(queryKeys.contact(contact.id), contact);
      client.invalidateQueries({ queryKey: ['contacts'] });
      client.invalidateQueries({ queryKey: ['companies'] });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: queryKeys.suppressions });
      client.invalidateQueries({ queryKey: ['send-preview'] });
    },
  });
}

export const useUpdateContact = () =>
  useContactMutation(({ id, changes }: { id: string; changes: Partial<Contact> }) =>
    api.updateContact(id, changes),
  );

export const useRevalidateContact = () =>
  useContactMutation((id: string) => api.revalidateContact(id));

export const useSuppressContact = () =>
  useContactMutation(({ id, reason, note }: { id: string; reason: string; note: string }) =>
    api.suppressContact(id, reason, note),
  );

export function useCreateContact() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: NewContact) => api.createContact(input),
    onSuccess: (contact) => {
      client.setQueryData(queryKeys.contact(contact.id), contact);
      client.invalidateQueries({ queryKey: ['contacts'] });
      client.invalidateQueries({ queryKey: ['companies'] });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

export function useDeleteContact() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, force }: { id: string; force?: boolean }) =>
      api.deleteContact(id, force ?? false),
    onSuccess: (_result, { id }) => {
      client.removeQueries({ queryKey: queryKeys.contact(id) });
      client.invalidateQueries({ queryKey: ['contacts'] });
      client.invalidateQueries({ queryKey: ['sends'] });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

export function useImportContacts() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      mapping,
      skipValidation,
    }: {
      file: File;
      mapping: Record<string, string>;
      skipValidation?: boolean;
    }) => api.importContacts(file, mapping, skipValidation ?? false),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['contacts'] });
      client.invalidateQueries({ queryKey: ['companies'] });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: queryKeys.suppressions });
    },
  });
}

export function usePreviewImport() {
  return useMutation({
    mutationFn: (file: File) => api.previewImport(file),
  });
}

export const useCompanies = (params: { q?: string; limit?: number; offset?: number }) =>
  useQuery({
    queryKey: queryKeys.companies(params),
    queryFn: () => api.companies(params),
  });

export const useCompany = (id: string) =>
  useQuery({
    queryKey: queryKeys.company(id),
    queryFn: () => api.company(id),
    enabled: !!id,
  });

export function useCreateCompany() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: CompanyInput) => api.createCompany(input),
    onSuccess: (company) => {
      client.setQueryData(queryKeys.company(company.id), company);
      client.invalidateQueries({ queryKey: ['companies'] });
    },
  });
}

export function useUpdateCompany() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...changes }: { id: string } & Partial<CompanyInput>) =>
      api.updateCompany(id, changes),
    onSuccess: (company) => {
      client.setQueryData(queryKeys.company(company.id), company);
      client.invalidateQueries({ queryKey: ['companies'] });
      client.invalidateQueries({ queryKey: ['contacts'] });
    },
  });
}

// ------------------------------------------------------------------ notes ----
export const useNotes = (notableType: NoteTarget, notableId: string) =>
  useQuery({
    queryKey: queryKeys.notes(notableType, notableId),
    queryFn: () => api.notes(notableType, notableId),
    enabled: !!notableId,
  });

export function useCreateNote() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.createNote,
    onSuccess: (note) => {
      client.invalidateQueries({
        queryKey: queryKeys.notes(note.notableType, note.notableId),
      });
    },
  });
}

export function useDeleteNote() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.deleteNote,
    onSuccess: () => client.invalidateQueries({ queryKey: ['notes'] }),
  });
}

// --------------------------------------------------------------- templates ----
export const useTemplates = () =>
  useQuery({ queryKey: queryKeys.templates, queryFn: api.templates });

export function useTemplateMutations() {
  const client = useQueryClient();
  const invalidate = () => {
    client.invalidateQueries({ queryKey: queryKeys.templates });
    client.invalidateQueries({ queryKey: queryKeys.templateGroups });
    client.invalidateQueries({ queryKey: ['send-preview'] });
  };

  return {
    create: useMutation({ mutationFn: api.createTemplate, onSuccess: invalidate }),
    update: useMutation({
      mutationFn: ({
        id,
        ...input
      }: {
        id: string;
        name?: string;
        subject?: string;
        body?: string;
        industry?: string;
      }) => api.updateTemplate(id, input),
      onSuccess: invalidate,
    }),
    remove: useMutation({ mutationFn: api.deleteTemplate, onSuccess: invalidate }),
  };
}

export const useTemplateGroups = () =>
  useQuery({ queryKey: queryKeys.templateGroups, queryFn: api.templateGroups });

export function useTemplateGroupMutations() {
  const client = useQueryClient();
  const invalidate = () => {
    client.invalidateQueries({ queryKey: queryKeys.templateGroups });
  };
  return {
    create: useMutation({ mutationFn: api.createTemplateGroup, onSuccess: invalidate }),
    update: useMutation({
      mutationFn: ({
        id,
        ...input
      }: {
        id: string;
        name?: string;
        templateIds?: string[];
      }) => api.updateTemplateGroup(id, input),
      onSuccess: invalidate,
    }),
    remove: useMutation({ mutationFn: api.deleteTemplateGroup, onSuccess: invalidate }),
  };
}

// ------------------------------------------------------------------- sends ----
export const useSendPreview = (
  contactId: string,
  templateId: string,
  acknowledge: string[],
) =>
  useQuery({
    queryKey: queryKeys.sendPreview(contactId, templateId, acknowledge),
    queryFn: () => api.previewSend({ contactId, templateId, acknowledge }),
    enabled: !!contactId && !!templateId,
    // The preview is advisory; the server re-evaluates every gate at send time.
    staleTime: 0,
  });

export function useSend() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.send,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: ['contacts'] });
      client.invalidateQueries({ queryKey: ['sends'] });
      client.invalidateQueries({ queryKey: ['send-preview'] });
    },
  });
}

export const useSendHistory = (contactId?: string, enabled = true) =>
  useQuery({
    queryKey: queryKeys.sendHistory(contactId),
    queryFn: () => api.sendHistory(contactId),
    enabled,
  });

// ------------------------------------------------------------ suppressions ----
export const useSuppressions = () =>
  useQuery({ queryKey: queryKeys.suppressions, queryFn: api.suppressions });

export function useSuppressionMutations() {
  const client = useQueryClient();
  const invalidate = () => {
    client.invalidateQueries({ queryKey: queryKeys.suppressions });
    client.invalidateQueries({ queryKey: ['contacts'] });
    client.invalidateQueries({ queryKey: queryKeys.dashboard });
  };
  return {
    add: useMutation({ mutationFn: api.addSuppression, onSuccess: invalidate }),
    remove: useMutation({ mutationFn: api.removeSuppression, onSuccess: invalidate }),
  };
}

// ---------------------------------------------------------- settings + gmail ----
export const useAppSettings = () =>
  useQuery({ queryKey: queryKeys.settings, queryFn: api.settings });

export function useUpdateAppSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (changes: Partial<AppSettings>) => api.updateSettings(changes),
    onSuccess: (settings) => {
      client.setQueryData(queryKeys.settings, settings);
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: ['send-preview'] });
    },
  });
}

export const useGmailStatus = () =>
  useQuery({ queryKey: queryKeys.gmailStatus, queryFn: api.gmailStatus });

export function useDisconnectGmail() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.disconnectGmail,
    onSuccess: () => client.invalidateQueries(),
  });
}
