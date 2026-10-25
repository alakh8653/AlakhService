import { useState } from 'react';
import { format, subDays } from 'date-fns';
import { useAnalytics } from '../hooks/useAnalytics';
import { useShopServices } from '../hooks/useShopServices';
import RevenueChart from '../components/RevenueChart';
import StatusBadge from '../components/StatusBadge';
import { BOOKING_STATUSES } from '../services/bookingService';
import { formatMoney, shortId } from '../services/format';

const RANGES = [
  { days: 7, label: '7 days' },
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
];

export default function AnalyticsPage() {
  const [range, setRange] = useState(30);
  const dateTo = format(new Date(), 'yyyy-MM-dd');
  const dateFrom = format(subDays(new Date(), range - 1), 'yyyy-MM-dd');
  const { analytics, isLoading, error, refetch } = useAnalytics(dateFrom, dateTo);
  const { serviceNames } = useShopServices();
  const completed = analytics?.bookingsByStatus.COMPLETED ?? 0;
  const statuses = BOOKING_STATUSES.filter((s) => (analytics?.bookingsByStatus[s] ?? 0) > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
          <p className="text-sm text-gray-500">
            {format(subDays(new Date(), range - 1), 'd MMM')} – {format(new Date(), 'd MMM yyyy')}, by booking date
          </p>
        </div>
        <div role="group" aria-label="Period" className="inline-flex rounded-xl bg-gray-100 p-1">
          {RANGES.map((r) => (
            <button
              type="button"
              key={r.days}
              aria-pressed={range === r.days}
              onClick={() => setRange(r.days)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${range === r.days ? 'bg-white shadow text-indigo-700' : 'text-gray-600 hover:text-gray-900'}`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <div role="alert" className="text-red-700 bg-red-50 rounded-lg px-3 py-2 text-sm flex justify-between gap-2">
          {error}
          <button type="button" onClick={refetch} className="font-medium underline">
            Try again
          </button>
        </div>
      )}

      <div className={`space-y-6 ${isLoading ? 'opacity-60' : ''}`} aria-busy={isLoading}>
        <dl className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            ['Bookings', analytics ? String(analytics.totalBookings) : '–'],
            ['Revenue', analytics ? formatMoney(analytics.totalRevenue) : '–'],
            ['Average bill', analytics && completed ? formatMoney(Math.round(analytics.totalRevenue / completed)) : '–'],
            ['Customers', analytics ? String(analytics.uniqueCustomers) : '–'],
          ].map(([label, value]) => (
            <div key={label} className="bg-white rounded-2xl shadow p-4">
              <dt className="text-sm text-gray-500">{label}</dt>
              <dd className="text-xl font-bold text-gray-900">{value}</dd>
            </div>
          ))}
        </dl>

        <section className="bg-white rounded-2xl shadow p-4 md:p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Revenue trend</h2>
          <p className="text-xs text-gray-500 mb-4">Completed bookings, by scheduled date</p>
          <RevenueChart data={analytics?.revenueByDay ?? []} />
        </section>

        <section className="bg-white rounded-2xl shadow p-4 md:p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Top services</h2>
          {(analytics?.topServices ?? []).length === 0 ? (
            <p className="text-gray-500 text-sm">No bookings in this period.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-gray-500 text-xs uppercase">
                <tr>
                  <th scope="col" className="pb-2 text-left">Service</th>
                  <th scope="col" className="pb-2 text-right">Bookings</th>
                  <th scope="col" className="pb-2 text-right">Revenue</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(analytics?.topServices ?? []).map(({ serviceId, bookingCount, revenue }) => (
                  <tr key={serviceId}>
                    <td className="py-2 pr-2 font-medium text-gray-900">{serviceNames[serviceId] ?? `Service ${shortId(serviceId)}`}</td>
                    <td className="py-2 text-right text-gray-600">{bookingCount}</td>
                    <td className="py-2 pl-2 text-right font-semibold whitespace-nowrap">{formatMoney(revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="bg-white rounded-2xl shadow p-4 md:p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Bookings by status</h2>
          {statuses.length === 0 ? (
            <p className="text-gray-500 text-sm">No bookings in this period.</p>
          ) : (
            <ul className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {statuses.map((status) => (
                <li key={status} className="bg-gray-50 rounded-xl p-3 flex items-center justify-between gap-2">
                  <StatusBadge status={status} />
                  <span className="text-xl font-bold text-gray-900">{analytics?.bookingsByStatus[status]}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
