import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import LoginPage from './auth/LoginPage';
import { isSignedIn } from './auth/session';
import AdminSidebar, { navLabelFor } from './components/AdminSidebar';
import AdminHeader from './components/AdminHeader';
import { ToastProvider } from './components/Toast';

// Pages load on demand so the sign-in screen doesn't pull in every page (and recharts).
const UsersPage = lazy(() => import('./users/UsersPage'));
const CouponsPage = lazy(() => import('./coupons/CouponsPage'));
const AuditLogPage = lazy(() => import('./audit/AuditLogPage'));
const ContactSharingPage = lazy(() => import('./moderation/ContactSharingPage'));
const ShopsPage = lazy(() => import('./shops/ShopsPage'));
const PrivacyRequestsPage = lazy(() => import('./privacy/PrivacyRequestsPage'));
const DisputeListPage = lazy(() => import('./disputes/DisputeListPage'));
const DisputeDetailPage = lazy(() => import('./disputes/DisputeDetailPage'));
const SettlementsPage = lazy(() => import('./finance/SettlementsPage'));
const RevenueReportPage = lazy(() => import('./finance/RevenueReportPage'));
const SystemHealthPage = lazy(() => import('./monitoring/SystemHealthPage'));
const ServiceMetricsPage = lazy(() => import('./monitoring/ServiceMetricsPage'));
const RolesPage = lazy(() => import('./access_control/RolesPage'));
const PermissionsPage = lazy(() => import('./access_control/PermissionsPage'));

const APP_NAME = 'AlakhService Admin';

function PageFallback() {
  return (
    <p role="status" className="text-sm text-gray-500">
      Loading…
    </p>
  );
}

function NotFound() {
  return (
    <div className="bg-white rounded-xl shadow p-8 max-w-lg space-y-2">
      <h1 className="text-xl font-bold text-gray-900">Page not found</h1>
      <p className="text-sm text-gray-600">This address doesn’t match any page in the dashboard.</p>
      <Link to="/disputes" className="inline-block text-sm font-medium text-indigo-700 hover:underline">
        Go to Disputes
      </Link>
    </div>
  );
}

export default function App() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  useEffect(() => {
    const label = location.pathname === '/login' ? 'Sign in' : navLabelFor(location.pathname);
    document.title = label ? `${label} · ${APP_NAME}` : APP_NAME;
  }, [location.pathname]);

  if (location.pathname === '/login') {
    return isSignedIn() ? <Navigate to="/" replace /> : <LoginPage />;
  }
  if (!isSignedIn()) return <Navigate to="/login" replace />;
  return (
    <ToastProvider>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[70] focus:bg-white focus:px-4 focus:py-2 focus:rounded-lg focus:shadow"
      >
        Skip to content
      </a>
      <div className="flex h-dvh bg-gray-100">
        <AdminSidebar open={menuOpen} onClose={closeMenu} />
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <AdminHeader menuOpen={menuOpen} onOpenMenu={() => setMenuOpen(true)} />
          <main id="main" tabIndex={-1} className="flex-1 overflow-y-auto p-4 sm:p-6 focus:outline-none">
            <Suspense fallback={<PageFallback />}>
              <Routes>
                {/* Disputes are the queue staff act on, so that is where the dashboard opens. */}
                <Route path="/" element={<Navigate to="/disputes" replace />} />
                <Route path="/audit" element={<AuditLogPage />} />
                <Route path="/users" element={<UsersPage />} />
                <Route path="/shops" element={<ShopsPage />} />
                <Route path="/privacy-requests" element={<PrivacyRequestsPage />} />
                <Route path="/disputes" element={<DisputeListPage />} />
                <Route path="/moderation/contact-sharing" element={<ContactSharingPage />} />
                <Route path="/disputes/:id" element={<DisputeDetailPage />} />
                <Route path="/finance/settlements" element={<SettlementsPage />} />
                <Route path="/finance/revenue" element={<RevenueReportPage />} />
                <Route path="/finance/coupons" element={<CouponsPage />} />
                <Route path="/monitoring/health" element={<SystemHealthPage />} />
                <Route path="/monitoring/metrics" element={<ServiceMetricsPage />} />
                <Route path="/access/roles" element={<RolesPage />} />
                <Route path="/access/permissions" element={<PermissionsPage />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
