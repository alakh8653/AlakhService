import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '../state/store';
import { useToast } from '../components/Toast';
import { formatRupees } from '../services/earningsService';
import { apiErrorMessage } from '../services/format';
import {
  EXPENSE_CATEGORIES,
  INCOME_CATEGORIES,
  addEntry,
  categoryLabel,
  downloadReport,
  getEntries,
  getReport,
  getReportSettings,
  removeEntry,
  saveReportSettings,
  sendReportNow,
  type CashEntry,
  type EntryKind,
  type Period,
  type ReportSettings,
  type ShopReport,
} from '../services/reportService';

const PERIODS: { value: Period; label: string }[] = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'yearly', label: 'Yearly' },
];
const card = 'bg-white rounded-xl border border-gray-200 p-4 md:p-6';
const inputClass = 'border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

function Line({ label, amount }: { label: string; amount: number }) {
  return (
    <div className="flex justify-between py-1 text-sm">
      <span className="text-gray-600">{label}</span>
      <span className="font-medium text-gray-900">{formatRupees(amount)}</span>
    </div>
  );
}

function AddEntryForm({ shopId, onAdded }: { shopId: string; onAdded: () => void }) {
  const [kind, setKind] = useState<EntryKind>('EXPENSE');
  const [category, setCategory] = useState('MATERIALS');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const categories = kind === 'EXPENSE' ? EXPENSE_CATEGORIES : INCOME_CATEGORIES;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    const value = Number(amount);
    if (!value || value <= 0) {
      setError('Enter an amount.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await addEntry(shopId, { kind, category, amount: value, note: note.trim() || undefined });
      setAmount('');
      setNote('');
      onAdded();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save it'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={(e) => void save(e)} aria-label="Add an expense or income" className="grid grid-cols-1 sm:grid-cols-5 gap-3 items-end">
      <label className="text-sm font-medium text-gray-700">
        Type
        <select
          value={kind}
          onChange={(e) => {
            const next = e.target.value as EntryKind;
            setKind(next);
            setCategory(next === 'EXPENSE' ? 'MATERIALS' : 'OUTSIDE_WORK');
          }}
          className={`${inputClass} block w-full mt-1`}
        >
          <option value="EXPENSE">Expense</option>
          <option value="INCOME">Income</option>
        </select>
      </label>
      <label className="text-sm font-medium text-gray-700">
        For
        <select value={category} onChange={(e) => setCategory(e.target.value)} className={`${inputClass} block w-full mt-1`}>
          {categories.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm font-medium text-gray-700">
        Amount (₹)
        <input type="number" min="1" step="any" value={amount} onChange={(e) => setAmount(e.target.value)} className={`${inputClass} block w-full mt-1`} />
      </label>
      <label className="text-sm font-medium text-gray-700">
        Note (optional)
        <input maxLength={200} value={note} onChange={(e) => setNote(e.target.value)} className={`${inputClass} block w-full mt-1`} />
      </label>
      <button type="submit" disabled={saving} className="rounded-lg bg-indigo-600 text-white text-sm font-medium px-4 py-2 disabled:opacity-50">
        Add
      </button>
      {error && (
        <p role="alert" className="sm:col-span-5 text-sm text-red-700">
          {error}
        </p>
      )}
    </form>
  );
}

function SettingsCard({ shopId }: { shopId: string }) {
  const toast = useToast();
  const [settings, setSettings] = useState<ReportSettings | null>(null);

  useEffect(() => {
    let live = true;
    getReportSettings(shopId)
      .then((s) => live && setSettings(s))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [shopId]);

  if (!settings) return null;

  const change = async (next: ReportSettings) => {
    const before = settings;
    setSettings(next);
    try {
      await saveReportSettings(shopId, next);
    } catch (e) {
      setSettings(before);
      toast(apiErrorMessage(e, 'Could not save that'), 'error');
    }
  };

  const toggle = (key: keyof ReportSettings, label: string, help?: string) => (
    <label key={key} className="flex items-start gap-2 py-1 text-sm text-gray-800">
      <input type="checkbox" checked={settings[key]} onChange={(e) => void change({ ...settings, [key]: e.target.checked })} className="mt-1" />
      <span>
        {label}
        {help && <span className="block text-xs text-gray-500">{help}</span>}
      </span>
    </label>
  );

  return (
    <section className={card} aria-label="Report settings">
      <h2 className="font-semibold text-gray-900 mb-2">Send my reports</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          {toggle('daily', 'Daily')}
          {toggle('weekly', 'Weekly')}
          {toggle('monthly', 'Monthly')}
          {toggle('yearly', 'Yearly', "April to March, India's financial year")}
        </div>
        <div>
          {toggle('email', 'By email')}
          {toggle('whatsapp', 'On WhatsApp', 'By turning this on, you agree to get reports on WhatsApp on your number. Turn it off any time.')}
        </div>
      </div>
    </section>
  );
}

/** What the business made for a day, week, month or year, and where its reports go. */
export default function ReportsPage() {
  const toast = useToast();
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const [period, setPeriod] = useState<Period>('monthly');
  const [report, setReport] = useState<ShopReport | null>(null);
  const [entries, setEntries] = useState<CashEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!shopId) return;
    setError(null);
    try {
      const next = await getReport(shopId, period);
      setEntries(await getEntries(shopId, next.from, next.to));
      setReport(next);
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not load your report.'));
    }
  }, [shopId, period]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!shopId) return null;

  const remove = async (entry: CashEntry) => {
    try {
      await removeEntry(shopId, entry.id);
      await load();
    } catch (e) {
      toast(apiErrorMessage(e, 'Could not remove it'), 'error');
    }
  };

  const sendNow = async () => {
    try {
      const outside = (await sendReportNow(shopId, period)).filter((c) => c !== 'app');
      toast(outside.length ? `Sent to: ${outside.join(', ')}` : "It's in your notifications. Email and WhatsApp aren't set up or are turned off.");
    } catch (e) {
      toast(apiErrorMessage(e, 'Could not send it'), 'error');
    }
  };

  const download = async () => {
    try {
      const url = URL.createObjectURL(await downloadReport(shopId, period));
      const link = document.createElement('a');
      link.href = url;
      link.download = `report-${period}-${report?.from ?? ''}.csv`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      toast(apiErrorMessage(e, 'Could not download it'), 'error');
    }
  };

  const loss = (report?.profit ?? 0) < 0;
  const change = report?.profit_change_percent;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Reports and profit</h1>
      <div role="group" aria-label="Report period" className="flex flex-wrap gap-2">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            type="button"
            aria-pressed={period === p.value}
            onClick={() => setPeriod(p.value)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium ${period === p.value ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}
          >
            {p.label}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {report && (
        <>
          <section className={card} aria-label="Profit and loss">
            <p className="text-sm text-gray-500">{report.label}</p>
            <p className={`text-3xl font-bold ${loss ? 'text-red-700' : 'text-green-700'}`}>
              {loss ? 'Loss' : 'Profit'} {formatRupees(report.profit)}
            </p>
            {change != null && (
              <p className="text-sm text-gray-500">
                {change >= 0 ? 'Up' : 'Down'} {Math.abs(change)}% on the period before
              </p>
            )}
            <p className="text-sm text-gray-700 mt-3 mb-1">{report.bookings} {report.bookings === 1 ? 'booking' : 'bookings'} completed</p>
            <Line label="Customers paid" amount={report.gross} />
            <Line label="Paid in cash" amount={report.cash} />
            <Line label="Paid online" amount={report.online} />
            <Line label="Commission and GST" amount={0 - (report.commission + report.gst)} />
            <Line label="You earned from bookings" amount={report.earned} />
            <Line label="Other income" amount={report.other_income} />
            <Line label="Expenses" amount={0 - report.expenses} />
            {report.tips !== 0 && <Line label="Tips (not in profit)" amount={report.tips} />}
            <p className="text-xs text-gray-500 mt-3">{report.note}</p>
            <div className="flex flex-wrap gap-2 mt-4">
              <button type="button" onClick={() => void sendNow()} className="rounded-lg bg-indigo-600 text-white text-sm font-medium px-4 py-2">
                Send me this report now
              </button>
              <button type="button" onClick={() => void download()} className="rounded-lg border border-gray-300 text-sm font-medium px-4 py-2">
                Download (CSV)
              </button>
            </div>
          </section>
          <section className={card} aria-label="Expenses and income">
            <h2 className="font-semibold text-gray-900 mb-3">Add an expense or income</h2>
            <AddEntryForm shopId={shopId} onAdded={() => void load()} />
            {entries.length > 0 && (
              <ul className="mt-4 divide-y divide-gray-100">
                {entries.map((entry) => (
                  <li key={entry.id} className="flex items-center justify-between py-2 text-sm">
                    <span>
                      {categoryLabel(entry.category)}
                      <span className="text-gray-500"> · {entry.on_date}{entry.note ? ` · ${entry.note}` : ''}</span>
                    </span>
                    <span className="flex items-center gap-3">
                      {formatRupees(entry.kind === 'EXPENSE' ? -entry.amount : entry.amount)}
                      <button type="button" onClick={() => void remove(entry)} className="text-red-700 text-xs" aria-label={`Remove ${categoryLabel(entry.category)}`}>
                        Remove
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          {report.breakdown.length > 0 && (
            <section className={card} aria-label="Profit by date">
              <h2 className="font-semibold text-gray-900 mb-2">Profit by {period === 'yearly' ? 'month' : 'date'}</h2>
              {report.breakdown.map((b) => (
                <Line key={b.label} label={b.label} amount={b.profit} />
              ))}
            </section>
          )}
        </>
      )}
      <SettingsCard shopId={shopId} />
    </div>
  );
}
