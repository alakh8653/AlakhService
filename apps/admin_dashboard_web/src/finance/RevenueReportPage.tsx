import { useEffect, useState } from 'react';
import { differenceInCalendarDays, format, parseISO, startOfMonth, subDays } from 'date-fns';
import { Download } from 'lucide-react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { apiErrorMessage } from '../shared/apiError';
import { downloadCsv } from '../shared/csv';
import { formatMoneyCompact, formatNumber } from '../shared/format';
import { formatMoney, getRevenueReport, type RevenueReport } from './FinanceService';

const toInputDate = (d: Date) => format(d, 'yyyy-MM-dd');
const MAX_DAYS = 366;

const PRESETS: { label: string; range: () => [Date, Date] }[] = [
  { label: 'Last 7 days', range: () => [subDays(new Date(), 6), new Date()] },
  { label: 'Last 30 days', range: () => [subDays(new Date(), 29), new Date()] },
  { label: 'Last 90 days', range: () => [subDays(new Date(), 89), new Date()] },
  { label: 'This month', range: () => [startOfMonth(new Date()), new Date()] },
];

export default function RevenueReportPage() {
  const [dateFrom, setDateFrom] = useState(toInputDate(subDays(new Date(), 29)));
  const [dateTo, setDateTo] = useState(toInputDate(new Date()));
  const [report, setReport] = useState<RevenueReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const days = dateFrom && dateTo ? differenceInCalendarDays(parseISO(dateTo), parseISO(dateFrom)) + 1 : 0;
  const rangeError = !dateFrom || !dateTo ? 'Choose both dates.' : days < 1 ? '“From” must be on or before “To”.' : days > MAX_DAYS ? `Choose at most ${MAX_DAYS} days.` : null;

  useEffect(() => {
    if (rangeError) return;
    let current = true;
    setIsLoading(true);
    setError(null);
    getRevenueReport({ dateFrom, dateTo })
      .then((r) => {
        if (current) setReport(r);
      })
      .catch((e: unknown) => {
        if (current) setError(apiErrorMessage(e, 'Could not load the revenue report.'));
      })
      .finally(() => {
        if (current) setIsLoading(false);
      });
    return () => {
      current = false;
    };
  }, [dateFrom, dateTo, rangeError, reloadKey]);

  const currency = report?.currency ?? 'INR';

  const exportCsv = () => {
    if (!report) return;
    downloadCsv(
      `revenue-${dateFrom}-to-${dateTo}.csv`,
      ['Date (UTC)', `Gross (${currency})`, `Refunds (${currency})`, `Net (${currency})`, 'Payments'],
      [
        ...report.series.map((p) => [p.date, p.gross.toFixed(2), p.refunds.toFixed(2), p.net.toFixed(2), p.payments]),
        ['Total', report.gross.toFixed(2), report.refunds.toFixed(2), report.net.toFixed(2), report.payments],
      ],
    );
  };

  const kpis = report
    ? [
        { label: 'Gross collected', value: formatMoney(report.gross, currency) },
        { label: 'Refunds', value: formatMoney(report.refunds, currency) },
        { label: 'Net revenue', value: formatMoney(report.net, currency) },
        { label: 'Payments', value: formatNumber(report.payments) },
      ]
    : [];

  const activePreset = PRESETS.find((p) => {
    const [from, to] = p.range();
    return toInputDate(from) === dateFrom && toInputDate(to) === dateTo;
  })?.label;

  const field = 'mt-1 border border-gray-300 rounded-lg px-3 py-1.5 text-gray-900 bg-white';
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Revenue Report</h1>
          <p className="text-sm text-gray-600">Money collected from customers, less refunds. Days run midnight to midnight UTC (5:30 am IST).</p>
        </div>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <div role="group" aria-label="Quick ranges" className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                aria-pressed={activePreset === p.label}
                onClick={() => {
                  const [from, to] = p.range();
                  setDateFrom(toInputDate(from));
                  setDateTo(toInputDate(to));
                }}
                className={`px-3 py-1.5 rounded-full border font-medium ${
                  activePreset === p.label ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <label className="flex flex-col text-gray-700">
            From
            <input type="date" value={dateFrom} max={dateTo} onChange={(e) => setDateFrom(e.target.value)} className={field} />
          </label>
          <label className="flex flex-col text-gray-700">
            To
            <input type="date" value={dateTo} min={dateFrom} onChange={(e) => setDateTo(e.target.value)} className={field} />
          </label>
          <button
            type="button"
            onClick={exportCsv}
            disabled={!report || isLoading || !!rangeError}
            className="flex items-center gap-2 border border-gray-300 bg-white rounded-lg px-3 py-1.5 font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <Download size={16} aria-hidden="true" /> Export CSV
          </button>
        </div>
        {rangeError && (
          <p role="alert" className="text-sm text-red-700">
            {rangeError}
          </p>
        )}
      </div>
      {error && !rangeError && (
        <p role="alert" className="text-sm text-red-700">
          {error}{' '}
          <button type="button" onClick={() => setReloadKey((k) => k + 1)} className="font-medium underline">
            Try again
          </button>
        </p>
      )}
      {!report && !error && !rangeError && (
        <p role="status" className="text-gray-500">
          Loading report…
        </p>
      )}
      {report && (
        <div aria-busy={isLoading || undefined} className={`space-y-6 transition-opacity ${isLoading ? 'opacity-60' : ''}`}>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {kpis.map((kpi) => (
              <div key={kpi.label} className="bg-white rounded-xl shadow p-4 sm:p-5 min-w-0">
                <p className="text-sm text-gray-600">{kpi.label}</p>
                <p className="mt-1 text-xl sm:text-2xl font-bold text-gray-900 tabular-nums truncate">{kpi.value}</p>
              </div>
            ))}
          </div>
          <div className="bg-white rounded-xl shadow p-4 sm:p-5">
            <h2 className="text-base font-semibold text-gray-900 mb-3">Daily revenue</h2>
            {report.payments === 0 && report.refunds === 0 ? (
              <p className="py-16 text-center text-gray-600">No payments or refunds in this period.</p>
            ) : (
              <div className="h-80" role="img" aria-label={`Daily gross, net and refunds from ${dateFrom} to ${dateTo}. Totals: gross ${formatMoney(report.gross, currency)}, net ${formatMoney(report.net, currency)}.`}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={report.series} margin={{ left: 8, right: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" tickFormatter={(d: string) => format(parseISO(d), 'd MMM')} minTickGap={16} fontSize={12} />
                    <YAxis tickFormatter={(v: number) => formatMoneyCompact(v, currency)} width={64} fontSize={12} />
                    <Tooltip
                      formatter={(value) => formatMoney(Number(value), currency)}
                      labelFormatter={(d) => format(parseISO(String(d)), 'EEE, d MMM yyyy')}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="gross" name="Gross" stroke="#4f46e5" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="net" name="Net" stroke="#15803d" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="refunds" name="Refunds" stroke="#dc2626" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
