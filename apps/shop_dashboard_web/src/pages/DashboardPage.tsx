import React from 'react';
import { useAnalytics } from '../hooks/useAnalytics';
import RevenueChart from '../components/RevenueChart';
import { TrendingUp, Calendar, Users, Star } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}

function StatCard({ title, value, icon, color }: StatCardProps) {
  return (
    <div className={`bg-white rounded-2xl shadow p-5 flex items-center gap-4 border-l-4 ${color}`}>
      <div className="text-3xl">{icon}</div>
      <div>
        <p className="text-sm text-gray-500">{title}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { analytics, isLoading } = useAnalytics();

  if (isLoading) return <p className="text-gray-500">Loading dashboard…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Bookings" value={analytics?.totalBookings ?? 0} icon={<Calendar size={28} />} color="border-indigo-500" />
        <StatCard title="Revenue" value={`$${(analytics?.totalRevenue ?? 0).toLocaleString()}`} icon={<TrendingUp size={28} />} color="border-green-500" />
        <StatCard title="Customers" value={analytics?.activeCustomers ?? 0} icon={<Users size={28} />} color="border-blue-500" />
        <StatCard title="Avg Rating" value={(analytics?.averageRating ?? 0).toFixed(1)} icon={<Star size={28} />} color="border-yellow-500" />
      </div>
      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Revenue (Last 30 Days)</h2>
        <RevenueChart data={analytics?.revenueByDay ?? []} />
      </div>
    </div>
  );
}
