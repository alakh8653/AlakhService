import { useState } from 'react';
import { format, subDays } from 'date-fns';
import { useAnalytics } from '../hooks/useAnalytics';
import { useShopServices } from '../hooks/useShopServices';
import RevenueChart from '../components/RevenueChart';
import { formatMoney, humanize, shortId } from '../services/format';

export default function AnalyticsPage() {
  const [range, setRange] = useState(30);
  const dateTo = format(new Date(), 'yyyy-MM-dd');
  const dateFrom = format(subDays(new Date(), range - 1), 'yyyy-MM-dd');
  const { analytics, isLoading, error } = useAnalytics(dateFrom, dateTo);
  const { serviceNames } = useShopServices();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
        <select value={range} onChange={(e) => setRange(Number(e.target.value))} className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>
      {error && <p className="text-red-500 text-sm">{error}</p>}

      {isLoading ? <p className="text-gray-500">Loading analytics…</p> : (
        <>
          <div className="bg-white rounded-2xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-1">Revenue Trend</h2>
            <p className="text-xs text-gray-400 mb-4">Completed bookings, by scheduled date</p>
            <RevenueChart data={analytics?.revenueByDay ?? []} />
          </div>

          <div className="bg-white rounded-2xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Top Services</h2>
            {(analytics?.topServices ?? []).length === 0 ? (
              <p className="text-gray-400 text-sm">No bookings in this period.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-gray-500 text-xs uppercase">
                  <tr>
                    <th className="pb-2 text-left">Service</th>
                    <th className="pb-2 text-right">Bookings</th>
                    <th className="pb-2 text-right">Revenue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {(analytics?.topServices ?? []).map(({ serviceId, bookingCount, revenue }) => (
                    <tr key={serviceId}>
                      <td className="py-2 font-medium text-gray-900">{serviceNames[serviceId] ?? `Service ${shortId(serviceId)}`}</td>
                      <td className="py-2 text-right text-gray-600">{bookingCount}</td>
                      <td className="py-2 text-right font-semibold">{formatMoney(revenue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="bg-white rounded-2xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Bookings by Status</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {Object.entries(analytics?.bookingsByStatus ?? {}).map(([status, count]) => (
                <div key={status} className="bg-gray-50 rounded-xl p-3 text-center">
                  <p className="text-2xl font-bold text-gray-900">{count}</p>
                  <p className="text-xs text-gray-500 mt-1">{humanize(status)}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
