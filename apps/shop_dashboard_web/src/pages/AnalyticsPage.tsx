import React, { useState } from 'react';
import { format, subDays } from 'date-fns';
import { useAnalytics } from '../hooks/useAnalytics';
import RevenueChart from '../components/RevenueChart';

export default function AnalyticsPage() {
  const [range, setRange] = useState(30);
  const dateTo = format(new Date(), 'yyyy-MM-dd');
  const dateFrom = format(subDays(new Date(), range), 'yyyy-MM-dd');
  const { analytics, isLoading } = useAnalytics(dateFrom, dateTo);

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

      {isLoading ? <p className="text-gray-500">Loading analytics…</p> : (
        <>
          <div className="bg-white rounded-2xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Revenue Trend</h2>
            <RevenueChart data={analytics?.revenueByDay ?? []} />
          </div>

          <div className="bg-white rounded-2xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Top Services</h2>
            <table className="w-full text-sm">
              <thead className="text-gray-500 text-xs uppercase">
                <tr>
                  <th className="pb-2 text-left">Service</th>
                  <th className="pb-2 text-right">Bookings</th>
                  <th className="pb-2 text-right">Revenue</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(analytics?.topServices ?? []).map(({ service, bookingCount, revenue }) => (
                  <tr key={service.id}>
                    <td className="py-2 font-medium text-gray-900">{service.name}</td>
                    <td className="py-2 text-right text-gray-600">{bookingCount}</td>
                    <td className="py-2 text-right font-semibold">${revenue.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white rounded-2xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Bookings by Status</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {Object.entries(analytics?.bookingsByStatus ?? {}).map(([status, count]) => (
                <div key={status} className="bg-gray-50 rounded-xl p-3 text-center">
                  <p className="text-2xl font-bold text-gray-900">{count}</p>
                  <p className="text-xs text-gray-500 capitalize mt-1">{status.replace('_', ' ')}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
