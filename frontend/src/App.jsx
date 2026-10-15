import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { ProtectedRoute } from './auth/AuthContext.jsx';
import { AppShell } from './components/layout/AppShell.jsx';
import { LoadingState } from './components/ui/LoadingState.jsx';

const DashboardPage = lazy(() => import('./pages/colmena/DashboardPage.jsx'));
const LoginPage = lazy(() => import('./pages/LoginPage.jsx'));
const SignupPage = lazy(() => import('./pages/SignupPage.jsx'));
const PublicSurveyPage = lazy(() => import('./pages/PublicSurveyPage.jsx'));
const TelemetryModulePage = lazy(() => import('./pages/colmena/TelemetryModulePage.jsx'));
const ReportsModulePage = lazy(() => import('./pages/colmena/ReportsModulePage.jsx'));
const ArchiveProjectsPage = lazy(() => import('./pages/colmena/ArchiveProjectsPage.jsx'));
const SettingsPage = lazy(() => import('./pages/colmena/SettingsPage.jsx'));
const NotFoundPage = lazy(() => import('./pages/colmena/NotFoundPage.jsx'));
const ProjectConstructorPage = lazy(() => import('./pages/colmena/project/ProjectConstructorPage.jsx'));
const ProjectInstrumentsPage = lazy(() => import('./pages/colmena/project/ProjectInstrumentsPage.jsx'));
const ProjectFormPage = lazy(() => import('./pages/colmena/project/ProjectFormPage.jsx'));
const ProjectLinkPage = lazy(() => import('./pages/colmena/project/ProjectLinkPage.jsx'));
const ProjectMembersPage = lazy(() => import('./pages/colmena/project/ProjectMembersPage.jsx'));
const ProjectTelemetryPage = lazy(() => import('./pages/colmena/project/AdaptiveProjectTelemetryPage.jsx'));
const ProjectResultsPage = lazy(() => import('./pages/colmena/project/ProjectResultsPage.jsx'));
const ProjectReportsPage = lazy(() => import('./pages/colmena/project/ProjectReportsPage.jsx'));
const ProjectPremiumDashboardPage = lazy(() => import('./pages/colmena/project/ProjectPremiumDashboardPage.jsx'));
const ProjectAnalyticsLabPage = lazy(() => import('./pages/colmena/project/ProjectAnalyticsLabPage.jsx'));
const ProjectPlanPage = lazy(() => import('./pages/colmena/project/ProjectPlanPage.jsx'));
const ProjectExportsPage = lazy(() => import('./pages/colmena/project/ProjectExportsPage.jsx'));

export default function App() {
  return (
    <Suspense fallback={<LoadingState label="Cargando página…" />}>
      <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/encuesta/:publicId" element={<PublicSurveyPage />} />

      <Route
        path="/colmena"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="telemetry" element={<TelemetryModulePage />} />
        <Route path="reports" element={<ReportsModulePage />} />

        <Route path="project/new" element={<ProjectConstructorPage />} />
        <Route path="project/:projectId" element={<ProjectConstructorPage />} />
        <Route path="project/:projectId/instruments" element={<ProjectInstrumentsPage />} />
        <Route path="project/:projectId/form" element={<ProjectFormPage />} />
        <Route path="project/:projectId/link" element={<ProjectLinkPage />} />
        <Route path="project/:projectId/team" element={<ProjectMembersPage />} />
        <Route path="project/:projectId/telemetry" element={<ProjectTelemetryPage />} />
        <Route path="project/:projectId/results" element={<ProjectResultsPage />} />
        <Route path="project/:projectId/premium" element={<ProjectPremiumDashboardPage />} />
        <Route path="project/:projectId/analytics-lab" element={<ProjectAnalyticsLabPage />} />
        <Route path="project/:projectId/plan" element={<ProjectPlanPage />} />
        <Route path="project/:projectId/reports" element={<ProjectReportsPage />} />
        <Route path="project/:projectId/exports" element={<ProjectExportsPage />} />

        <Route path="archive/projects" element={<ArchiveProjectsPage />} />
        <Route path="settings" element={<SettingsPage />} />

        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route path="/" element={<Navigate to="/colmena" replace />} />
      <Route path="*" element={<Navigate to="/colmena" replace />} />
      </Routes>
    </Suspense>
  );
}
