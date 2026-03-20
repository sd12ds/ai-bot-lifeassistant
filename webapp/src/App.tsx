import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from './shared/layouts/AppLayout'
import { AuthLayout } from './shared/layouts/AuthLayout'
import { LoginPage } from './features/auth/LoginPage'
import { ResearchDashboard } from './features/research/ResearchDashboard'
import { JobsList } from './features/research/JobsList'
import { JobDetail } from './features/research/JobDetail'
import { NewJobForm } from './features/research/NewJobForm'
import { TemplatesList } from './features/research/TemplatesList'
import { ResultsExplorer } from './features/research/ResultsExplorer'
import { BillingDashboard } from './features/billing/BillingDashboard'
import { AuditPage } from './features/settings/AuditPage'
import { PlanSelector } from './features/billing/PlanSelector'
import { WorkspaceSettings } from './features/settings/WorkspaceSettings'
import { getToken } from './api/client'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  return getToken() ? <>{children}</> : <Navigate to="/auth" replace />
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/auth" element={<LoginPage />} />
          </Route>
          <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route path="/" element={<Navigate to="/research" replace />} />
            <Route path="/research" element={<ResearchDashboard />} />
            <Route path="/research/jobs" element={<JobsList />} />
            <Route path="/research/jobs/new" element={<NewJobForm />} />
            <Route path="/research/jobs/:id" element={<JobDetail />} />
            <Route path="/research/jobs/:id/results" element={<ResultsExplorer />} />
            <Route path="/research/templates" element={<TemplatesList />} />
            <Route path="/billing" element={<BillingDashboard />} />
            <Route path="/billing/plans" element={<PlanSelector />} />
            <Route path="/settings" element={<AuditPage />} />
            <Route path="/settings/workspace" element={<WorkspaceSettings />} />
          </Route>
          <Route path="*" element={<Navigate to="/research" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
