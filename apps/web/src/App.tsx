import type * as React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from '@/components/AppLayout';
import { TaddarIcon } from '@/components/brand/Logo';
import { useSession } from '@/hooks';
import { CompaniesPage } from '@/pages/CompaniesPage';
import { CompanyDetailPage } from '@/pages/CompanyDetailPage';
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
    // Session check is a sub-second round trip, so this is a held brand beat
    // rather than a skeleton of a layout we may never render.
    return (
      <div className="grid min-h-screen place-items-center bg-surface">
        <TaddarIcon className="size-9 animate-pulse" title="Loading Taddar" />
      </div>
    );
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
        path="/companies"
        element={
          <RequireAuth>
            <CompaniesPage />
          </RequireAuth>
        }
      />
      <Route
        path="/companies/:id"
        element={
          <RequireAuth>
            <CompanyDetailPage />
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
