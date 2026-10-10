import type { ReactNode } from 'react';
import { useSelector } from 'react-redux';
import { TrendingUp, Calendar, Users, Star } from 'lucide-react';
import type { RootState } from '../state/store';
import { useAnalytics } from '../hooks/useAnalytics';
import RevenueChart from '../components/RevenueChart';
import { formatMoney } from '../services/format';

interface StatCardProps {
  title: string;
  value: string | number;
  hint?: string;
  icon: ReactNode;
  color: string;
}

function StatCard({ title, value, hint, icon, color }: StatCardProps) {
  return (
    <div className={`bg-white rounded-2xl shadow p-5 flex items-center gap-4 border-l-4 ${color}`}>
      <div className="text-3xl">{icon}</div>
      <div>
        <p className="text-sm text-gray-500">{title}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        {hint && <p className="text-xs text-gray-400">{hint}</p>}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const shop = useSelector((state: RootState) => state.auth.shop);
  const { analytics, isLoading, error } = useAnalytics();

  if (isLoading && !analytics) return <p className="text-gray-500">Loading dashboard…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      {error && <p className="text-red-500 text-sm">{error}</p>}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Bookings" value={analytics?.totalBookings ?? 0} hint="Last 30 days" icon={<Calendar size={28} />} color="border-indigo-500" />
        <StatCard title="Revenue" value={formatMoney(analytics?.totalRevenue ?? 0)} hint="Completed bookings" icon={<TrendingUp size={28} />} color="border-green-500" />
        <StatCard title="Customers" value={analytics?.uniqueCustomers ?? 0} hint="Last 30 days" icon={<Users size={28} />} color="border-blue-500" />
        <StatCard title="Avg Rating" value={(shop?.ratingAvg ?? 0).toFixed(1)} hint={`${shop?.ratingCount ?? 0} ratings`} icon={<Star size={28} />} color="border-yellow-500" />
      </div>
      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Revenue (Last 30 Days)</h2>
        <RevenueChart data={analytics?.revenueByDay ?? []} />
      </div>
    </div>
  );
}
