import { lazy, Suspense, useEffect, useState } from 'react';
import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from './state/store';
import { setCredentials } from './state/authSlice';
import { restoreSession, rememberRefreshToken, storedRefreshToken } from './services/session';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import { ToastProvider } from './components/Toast';
import LoginPage from './pages/LoginPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import RegisterPage from './pages/RegisterPage';

// Signed-in pages load on demand so the auth screens don't pull in every page (and recharts).
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const BookingsPage = lazy(() => import('./pages/BookingsPage'));
const ServicesPage = lazy(() => import('./pages/ServicesPage'));
const QueuesPage = lazy(() => import('./pages/QueuesPage'));
const StaffPage = lazy(() => import('./pages/StaffPage'));
const ReviewsPage = lazy(() => import('./pages/ReviewsPage'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const ShopSetupPage = lazy(() => import('./pages/ShopSetupPage'));

function PageFallback() {
  return (
    <p role="status" className="text-sm text-gray-500">
      Loading…
    </p>
  );
}

export function NotFoundPage() {
  return (
    <div className="max-w-md mx-auto text-center py-16 space-y-3">
      <p className="text-5xl font-bold text-indigo-600">404</p>
      <h1 className="text-xl font-semibold text-gray-900">This page does not exist</h1>
      <p className="text-sm text-gray-500">The link may be old or mistyped.</p>
      <Link to="/dashboard" className="inline-block bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700">
        Go to dashboard
      </Link>
    </div>
  );
}

function ProtectedLayout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();

  // Every page starts at the top, with the phone menu closed.
  useEffect(() => {
    setMenuOpen(false);
    document.getElementById('main')?.scrollTo?.({ top: 0 });
  }, [pathname]);

  return (
    <div className="flex h-dvh bg-gray-50">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 bg-white px-3 py-2 rounded-lg shadow">
        Skip to content
      </a>
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Header onOpenMenu={() => setMenuOpen(true)} menuOpen={menuOpen} />
        <main id="main" tabIndex={-1} className="flex-1 overflow-y-auto p-4 md:p-6 focus:outline-none">
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/login" element={<Navigate to="/dashboard" replace />} />
              <Route path="/register" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/bookings" element={<BookingsPage />} />
              <Route path="/services" element={<ServicesPage />} />
              <Route path="/queues" element={<QueuesPage />} />
              <Route path="/staff" element={<StaffPage />} />
              <Route path="/reviews" element={<ReviewsPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  );
}

/** Signs the owner back in after a reload, if they were signed in before. */
function useRestoredSession(isAuthenticated: boolean): boolean {
  const dispatch = useDispatch<AppDispatch>();
  const [restoring, setRestoring] = useState(() => !isAuthenticated && !!storedRefreshToken());

  useEffect(() => {
    if (!restoring) return;
    const token = storedRefreshToken();
    if (!token) {
      setRestoring(false);
      return;
    }
    let cancelled = false;
    restoreSession(token)
      .then((session) => {
        if (!cancelled) dispatch(setCredentials(session));
      })
      .catch(() => rememberRefreshToken(null))
      .finally(() => {
        if (!cancelled) setRestoring(false);
      });
    return () => {
      cancelled = true;
    };
  }, [restoring, dispatch]);

  return restoring;
}

function SignedOutRedirect() {
  const location = useLocation();
  return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
}

export default function App() {
  const isAuthenticated = useSelector((state: RootState) => state.auth.isAuthenticated);
  const hasShop = useSelector((state: RootState) => state.auth.shop !== null);
  const restoring = useRestoredSession(isAuthenticated);

  if (restoring) {
    return (
      <div className="min-h-dvh flex items-center justify-center bg-gray-50">
        <p role="status" className="text-sm text-gray-500">
          Signing you in…
        </p>
      </div>
    );
  }

  return (
    <ToastProvider>
      <Routes>
        {!isAuthenticated && <Route path="/login" element={<LoginPage />} />}
        {!isAuthenticated && <Route path="/register" element={<RegisterPage />} />}
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route
          path="/*"
          element={
            !isAuthenticated ? (
              <SignedOutRedirect />
            ) : hasShop ? (
              <ProtectedLayout />
            ) : (
              // Signed in without a shop yet: set one up before anything else.
              <Suspense fallback={<PageFallback />}>
                <ShopSetupPage />
              </Suspense>
            )
          }
        />
      </Routes>
    </ToastProvider>
  );
}
