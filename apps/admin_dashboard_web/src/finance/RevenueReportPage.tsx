import { useEffect, useState } from 'react';
import { format, subDays } from 'date-fns';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatMoney, getRevenueReport, type RevenueReport } from './FinanceService';

const toInputDate = (d: Date) => format(d, 'yyyy-MM-dd');

export default function RevenueReportPage() {
  const [dateFrom, setDateFrom] = useState(toInputDate(subDays(new Date(), 30)));
  const [dateTo, setDateTo] = useState(toInputDate(new Date()));
  const [report, setReport] = useState<RevenueReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    getRevenueReport({ dateFrom, dateTo })
      .then(setReport)
      .catch(() => setError('Failed to load revenue report.'));
  }, [dateFrom, dateTo]);

  const currency = report?.currency ?? 'INR';
  const kpis = report
    ? [
        { label: 'Gross collected', value: formatMoney(report.gross, currency) },
        { label: 'Refunds', value: formatMoney(report.refunds, currency) },
        { label: 'Net revenue', value: formatMoney(report.net, currency) },
        { label: 'Payments', value: report.payments.toLocaleString() },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <h1 className="text-2xl font-bold text-gray-900">Revenue Report</h1>
        <div className="flex gap-3 text-sm">
          <label className="flex flex-col text-gray-500">
            From
            <input type="date" value={dateFrom} max={dateTo} onChange={(e) => setDateFrom(e.target.value)} className="border border-gray-300 rounded-lg px-3 py-1.5 text-gray-900" />
          </label>
          <label className="flex flex-col text-gray-500">
            To
            <input type="date" value={dateTo} min={dateFrom} onChange={(e) => setDateTo(e.target.value)} className="border border-gray-300 rounded-lg px-3 py-1.5 text-gray-900" />
          </label>
        </div>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!report && !error && <p className="text-gray-500">Loading report…</p>}
      {report && (
        <>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {kpis.map((kpi) => (
              <div key={kpi.label} className="bg-white rounded-xl shadow p-5">
                <p className="text-sm text-gray-500">{kpi.label}</p>
                <p className="mt-1 text-2xl font-bold text-gray-900">{kpi.value}</p>
              </div>
            ))}
          </div>
          <div className="bg-white rounded-xl shadow p-5 h-96">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={report.series}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={(d: string) => format(new Date(d), 'MMM d')} />
                <YAxis />
                <Tooltip formatter={(value) => formatMoney(Number(value), currency)} />
                <Legend />
                <Line type="monotone" dataKey="gross" name="Gross" stroke="#4f46e5" dot={false} />
                <Line type="monotone" dataKey="net" name="Net" stroke="#16a34a" dot={false} />
                <Line type="monotone" dataKey="refunds" name="Refunds" stroke="#dc2626" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
