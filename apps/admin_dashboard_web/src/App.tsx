import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import LoginPage from './auth/LoginPage';
import { isSignedIn } from './auth/session';
import AdminSidebar from './components/AdminSidebar';
import AdminHeader from './components/AdminHeader';

// Pages load on demand so the sign-in screen doesn't pull in every page (and recharts).
const UsersPage = lazy(() => import('./users/UsersPage'));
const CouponsPage = lazy(() => import('./coupons/CouponsPage'));
const AuditLogPage = lazy(() => import('./audit/AuditLogPage'));
const DisputeListPage = lazy(() => import('./disputes/DisputeListPage'));
const DisputeDetailPage = lazy(() => import('./disputes/DisputeDetailPage'));
const SettlementsPage = lazy(() => import('./finance/SettlementsPage'));
const RevenueReportPage = lazy(() => import('./finance/RevenueReportPage'));
const SystemHealthPage = lazy(() => import('./monitoring/SystemHealthPage'));
const ServiceMetricsPage = lazy(() => import('./monitoring/ServiceMetricsPage'));
const RolesPage = lazy(() => import('./access_control/RolesPage'));
const PermissionsPage = lazy(() => import('./access_control/PermissionsPage'));

function PageFallback() {
  return <p className="text-sm text-gray-500">Loading…</p>;
}

export default function App() {
  const location = useLocation();
  if (location.pathname === '/login') {
    return isSignedIn() ? <Navigate to="/" replace /> : <LoginPage />;
  }
  if (!isSignedIn()) return <Navigate to="/login" replace />;
  return (
    <div className="flex h-screen bg-gray-100">
      <AdminSidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <AdminHeader />
        <main className="flex-1 overflow-y-auto p-6">
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<Navigate to="/audit" replace />} />
              <Route path="/audit" element={<AuditLogPage />} />
              <Route path="/users" element={<UsersPage />} />
              <Route path="/disputes" element={<DisputeListPage />} />
              <Route path="/disputes/:id" element={<DisputeDetailPage />} />
              <Route path="/finance/settlements" element={<SettlementsPage />} />
              <Route path="/finance/revenue" element={<RevenueReportPage />} />
              <Route path="/finance/coupons" element={<CouponsPage />} />
              <Route path="/monitoring/health" element={<SystemHealthPage />} />
              <Route path="/monitoring/metrics" element={<ServiceMetricsPage />} />
              <Route path="/access/roles" element={<RolesPage />} />
              <Route path="/access/permissions" element={<PermissionsPage />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  );
}
