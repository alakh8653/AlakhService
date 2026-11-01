import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '../state/store';
import { formatRupees, getEarnings, getPayouts, type Earnings, type PayoutItemStatus, type Payout } from '../services/earningsService';
import { apiErrorMessage } from '../services/format';
import { getStaff } from '../services/shopService';
import PayoutDetailsForm from '../components/PayoutDetailsForm';

const IST_DAY = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }); // yyyy-MM-dd
const dateFmt = new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', year: 'numeric' });

/** The first and last day of this month, in IST. */
export function thisMonth(now: Date = new Date()): { from: string; to: string } {
  const today = IST_DAY.format(now);
  return { from: `${today.slice(0, 8)}01`, to: today };
}

const showDate = (iso: string | null) => (iso ? dateFmt.format(new Date(iso)) : '—');

const ITEM_STATUS: Record<PayoutItemStatus, { label: string; className: string }> = {
  HELD: { label: 'On hold', className: 'bg-gray-100 text-gray-700' },
  READY: { label: 'Ready for payout', className: 'bg-yellow-100 text-yellow-800' },
  PAID: { label: 'Paid', className: 'bg-green-100 text-green-800' },
  REFUNDED: { label: 'Refunded', className: 'bg-red-100 text-red-800' },
};

function unavailable(err: unknown): boolean {
  const status = (err as { response?: { status?: number } })?.response?.status;
  return status === 404 || status === 501;
}

const card = 'bg-white rounded-xl border border-gray-200 p-4 md:p-6';
const inputClass = 'border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';

/** What the shop earned after commission, what has been paid out, and where payouts go. */
export default function EarningsPage() {
  const shop = useSelector((state: RootState) => state.auth.shop);
  const [range, setRange] = useState(thisMonth);
  const [earnings, setEarnings] = useState<Earnings | null>(null);
  const [earningsError, setEarningsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [payouts, setPayouts] = useState<Payout[] | null>(null);
  const [payoutsError, setPayoutsError] = useState<string | null>(null);
  // Names of the shop's staff by their app account, to say whom each tip is for.
  const [staffNames, setStaffNames] = useState<Record<string, string>>({});
  const shopId = shop?.id;
  const hasTips = (earnings?.tipsByProvider?.length ?? 0) > 0;
  const rangeInvalid = !range.from || !range.to || range.from > range.to;

  useEffect(() => {
    if (!shopId || rangeInvalid) return;
    let live = true;
    setLoading(true);
    setEarningsError(null);
    getEarnings(shopId, range.from, range.to)
      .then((e) => live && setEarnings(e))
      .catch((e) => {
        if (!live) return;
        setEarnings(null);
        setEarningsError(unavailable(e) ? 'Earnings are not available yet. Please check back soon.' : apiErrorMessage(e, 'Could not load your earnings.'));
      })
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [shopId, range.from, range.to, rangeInvalid]);

  useEffect(() => {
    if (!shopId) return;
    let live = true;
    getPayouts(shopId)
      .then((p) => live && setPayouts(p))
      .catch((e) => live && setPayoutsError(unavailable(e) ? 'Payout history is not available yet.' : apiErrorMessage(e, 'Could not load your payouts.')));
    return () => {
      live = false;
    };
  }, [shopId]);

  useEffect(() => {
    if (!shopId || !hasTips) return;
    let live = true;
    getStaff(shopId)
      .then((staff) => live && setStaffNames(Object.fromEntries(staff.filter((s) => s.userId).map((s) => [s.userId as string, s.name]))))
      .catch(() => undefined); // the tips still show, as "a staff member"
    return () => {
      live = false;
    };
  }, [shopId, hasTips]);

  if (!shop) return null;

  const stats = earnings
    ? [
        { label: 'Customers paid', value: earnings.gross },
        { label: 'Platform commission', value: earnings.commission, note: `+ ${formatRupees(earnings.gstOnCommission)} GST` },
        { label: 'Your earnings', value: earnings.net, strong: true },
        { label: 'Waiting for payout', value: earnings.pendingPayout },
        { label: 'Paid out', value: earnings.paidOut },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Earnings &amp; Payouts</h1>
        <p className="text-sm text-gray-500">Completed bookings, the platform commission on them, and what we have paid you.</p>
      </div>

      <section aria-labelledby="earnings-heading" className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-end gap-3 justify-between">
          <h2 id="earnings-heading" className="text-lg font-semibold text-gray-900">
            Earnings
          </h2>
          <div className="flex flex-wrap gap-3">
            <label className="text-sm text-gray-700">
              From
              <input type="date" value={range.from} max={range.to} onChange={(e) => setRange((r) => ({ ...r, from: e.target.value }))} className={`${inputClass} ml-2`} />
            </label>
            <label className="text-sm text-gray-700">
              To
              <input type="date" value={range.to} min={range.from} onChange={(e) => setRange((r) => ({ ...r, to: e.target.value }))} className={`${inputClass} ml-2`} />
            </label>
          </div>
        </div>
        {rangeInvalid && <p className="text-sm text-red-700">Choose a start date on or before the end date.</p>}
        {earningsError && (
          <p role="alert" className="text-sm text-gray-700 bg-gray-100 rounded-lg px-3 py-2">
            {earningsError}
          </p>
        )}
        {loading && !earnings && !earningsError && (
          <p role="status" className="text-sm text-gray-500">
            Loading…
          </p>
        )}
        {earnings && (
          <>
            <dl className="grid grid-cols-2 lg:grid-cols-5 gap-3">
              {stats.map((s) => (
                <div key={s.label} className={`${card} !p-4`}>
                  <dt className="text-xs font-medium text-gray-500">{s.label}</dt>
                  <dd className={`mt-1 text-lg ${s.strong ? 'font-bold text-indigo-700' : 'font-semibold text-gray-900'}`}>{formatRupees(s.value)}</dd>
                  {s.note && <dd className="text-xs text-gray-500">{s.note}</dd>}
                </div>
              ))}
            </dl>
            {hasTips && (
              <div className={`${card} space-y-2`} aria-labelledby="tips-heading" role="region">
                <h3 id="tips-heading" className="font-semibold text-gray-900">
                  Tips to pass on
                </h3>
                <p className="text-sm text-gray-500">
                  Customers tipped {formatRupees(earnings.tips ?? 0)}. No commission is taken: it comes with your payout, for the staff who did the job.
                </p>
                <ul className="divide-y divide-gray-100 text-sm">
                  {earnings.tipsByProvider?.map((t) => (
                    <li key={t.providerId ?? 'none'} className="flex justify-between py-2">
                      <span>{(t.providerId && staffNames[t.providerId]) || (t.providerId ? 'A staff member' : 'No staff assigned')}</span>
                      <span className="font-medium">{formatRupees(t.amount)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className={`${card} !p-0 overflow-x-auto`}>
              <table className="min-w-full text-sm" aria-label="Earnings by booking">
                <thead className="bg-gray-50 text-left text-gray-600">
                  <tr>
                    <th scope="col" className="px-4 py-3 font-semibold">Completed</th>
                    <th scope="col" className="px-4 py-3 font-semibold">Booking</th>
                    <th scope="col" className="px-4 py-3 font-semibold text-right">Paid</th>
                    <th scope="col" className="px-4 py-3 font-semibold text-right hidden sm:table-cell">Commission + GST</th>
                    <th scope="col" className="px-4 py-3 font-semibold text-right">You get</th>
                    <th scope="col" className="px-4 py-3 font-semibold">Payout</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {earnings.items.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                        No completed bookings in these dates.
                      </td>
                    </tr>
                  ) : (
                    earnings.items.map((i) => (
                      <tr key={`${i.bookingId}-${i.paymentId}-${i.kind ?? 'SALE'}`}>
                        <td className="px-4 py-3 whitespace-nowrap">{showDate(i.completedAt)}</td>
                        <td className="px-4 py-3 font-mono text-xs" title={i.bookingId}>
                          {i.bookingId.slice(0, 8)}
                          {i.kind?.startsWith('TIP') && <span className="ml-2 font-sans text-xs font-semibold text-emerald-700">Tip</span>}
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">{formatRupees(i.gross)}</td>
                        <td className="px-4 py-3 text-right whitespace-nowrap hidden sm:table-cell">{formatRupees(i.commission + i.gstOnCommission)}</td>
                        <td className="px-4 py-3 text-right whitespace-nowrap font-medium">{formatRupees(i.net)}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${ITEM_STATUS[i.payoutStatus]?.className ?? 'bg-gray-100 text-gray-700'}`}>
                            {ITEM_STATUS[i.payoutStatus]?.label ?? i.payoutStatus}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <section aria-labelledby="payouts-heading" className="space-y-3">
        <h2 id="payouts-heading" className="text-lg font-semibold text-gray-900">
          Payouts
        </h2>
        {payoutsError && <p className="text-sm text-gray-700 bg-gray-100 rounded-lg px-3 py-2">{payoutsError}</p>}
        {payouts && payouts.length === 0 && <p className="text-sm text-gray-500">No payouts yet.</p>}
        {payouts && payouts.length > 0 && (
          <div className={`${card} !p-0 overflow-x-auto`}>
            <table className="min-w-full text-sm" aria-label="Payouts">
              <thead className="bg-gray-50 text-left text-gray-600">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">Period</th>
                  <th scope="col" className="px-4 py-3 font-semibold text-right">Amount</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Status</th>
                  <th scope="col" className="px-4 py-3 font-semibold hidden sm:table-cell">Reference</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {payouts.map((p) => (
                  <tr key={p.id}>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {showDate(p.periodFrom)} – {showDate(p.periodTo)}
                    </td>
                    <td className="px-4 py-3 text-right font-medium whitespace-nowrap">{formatRupees(p.amount)}</td>
                    <td className="px-4 py-3 whitespace-nowrap">{p.status === 'PAID' ? `Paid ${showDate(p.paidAt)}` : 'Processing'}</td>
                    <td className="px-4 py-3 font-mono text-xs hidden sm:table-cell">{p.reference ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="payout-details-heading" className={`${card} space-y-4 max-w-3xl`}>
        <h2 id="payout-details-heading" className="text-lg font-semibold text-gray-900">
          Where we pay you
        </h2>
        <PayoutDetailsForm shopId={shop.id} />
      </section>
    </div>
  );
}
