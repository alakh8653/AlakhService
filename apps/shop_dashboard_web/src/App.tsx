import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import type { RootState } from './state/store';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
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
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const ShopSetupPage = lazy(() => import('./pages/ShopSetupPage'));

function PageFallback() {
  return <p className="text-sm text-gray-500">Loading…</p>;
}

function ProtectedLayout() {
  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/bookings" element={<BookingsPage />} />
              <Route path="/services" element={<ServicesPage />} />
              <Route path="/queues" element={<QueuesPage />} />
              <Route path="/staff" element={<StaffPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const isAuthenticated = useSelector(
    (state: RootState) => state.auth.isAuthenticated,
  );
  const hasShop = useSelector((state: RootState) => state.auth.shop !== null);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/*"
        element={
          !isAuthenticated ? (
            <Navigate to="/login" replace />
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
  );
}
