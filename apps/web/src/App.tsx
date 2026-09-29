import type * as React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from '@/components/AppLayout';
import { useSession } from '@/hooks';
import { ContactDetailPage } from '@/pages/ContactDetailPage';
import { ContactsPage } from '@/pages/ContactsPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { LoginPage } from '@/pages/LoginPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { SuppressionsPage } from '@/pages/SuppressionsPage';
import { TemplatesPage } from '@/pages/TemplatesPage';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { data, isLoading } = useSession();

  if (isLoading) {
    return <p className="p-6 text-xs text-muted-foreground">Loading…</p>;
  }
  if (!data?.authenticated) {
    return <Navigate to="/login" replace />;
  }
  return <AppLayout>{children}</AppLayout>;
}

/** Bounce an already-signed-in visitor off the login page. */
function LoginRoute() {
  const { data } = useSession();
  return data?.authenticated ? <Navigate to="/" replace /> : <LoginPage />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />
      <Route
        path="/contacts"
        element={
          <RequireAuth>
            <ContactsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/contacts/:id"
        element={
          <RequireAuth>
            <ContactDetailPage />
          </RequireAuth>
        }
      />
      <Route
        path="/templates"
        element={
          <RequireAuth>
            <TemplatesPage />
          </RequireAuth>
        }
      />
      <Route
        path="/suppressions"
        element={
          <RequireAuth>
            <SuppressionsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/settings"
        element={
          <RequireAuth>
            <SettingsPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
