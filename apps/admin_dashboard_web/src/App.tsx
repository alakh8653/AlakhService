import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AdminSidebar from './components/AdminSidebar';
import AdminHeader from './components/AdminHeader';
import AuditLogPage from './audit/AuditLogPage';
import DisputeListPage from './disputes/DisputeListPage';
import DisputeDetailPage from './disputes/DisputeDetailPage';
import SettlementsPage from './finance/SettlementsPage';
import RevenueReportPage from './finance/RevenueReportPage';
import SystemHealthPage from './monitoring/SystemHealthPage';
import ServiceMetricsPage from './monitoring/ServiceMetricsPage';
import RolesPage from './access_control/RolesPage';
import PermissionsPage from './access_control/PermissionsPage';

export default function App() {
  return (
    <div className="flex h-screen bg-gray-100">
      <AdminSidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <AdminHeader />
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/" element={<Navigate to="/audit" replace />} />
            <Route path="/audit" element={<AuditLogPage />} />
            <Route path="/disputes" element={<DisputeListPage />} />
            <Route path="/disputes/:id" element={<DisputeDetailPage />} />
            <Route path="/finance/settlements" element={<SettlementsPage />} />
            <Route path="/finance/revenue" element={<RevenueReportPage />} />
            <Route path="/monitoring/health" element={<SystemHealthPage />} />
            <Route path="/monitoring/metrics" element={<ServiceMetricsPage />} />
            <Route path="/access/roles" element={<RolesPage />} />
            <Route path="/access/permissions" element={<PermissionsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
