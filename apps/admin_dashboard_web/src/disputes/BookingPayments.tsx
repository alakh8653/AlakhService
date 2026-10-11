import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { getBookingPayments, refundPayment, type BookingPayment } from './PaymentService';

const rupees = (paise: number) => `₹${(paise / 100).toFixed(2)}`;

function detail(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) {
    const d = (e.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof d === 'string') return d;
  }
  return fallback;
}

/** The booking's payments, with a refund form for those that can still be refunded. */
export default function BookingPayments({ bookingId }: { bookingId: string }) {
  const [payments, setPayments] = useState<BookingPayment[] | null>(null);
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    getBookingPayments(bookingId)
      .then(setPayments)
      .catch(() => setMessage('Could not load payments.'));
  }, [bookingId]);

  useEffect(load, [load]);

  const refund = async (p: BookingPayment) => {
    const paise = Math.round(Number(amounts[p.id] ?? p.amountCents / 100) * 100);
    if (!Number.isFinite(paise) || paise <= 0) return setMessage('Enter an amount to refund.');
    if (!reason.trim()) return setMessage('Give a reason for the refund.');
    if (!window.confirm(`Refund ${rupees(paise)} to the customer?`)) return;
    setBusy(p.id);
    setMessage(null);
    try {
      const r = await refundPayment(p.id, paise, reason.trim());
      setMessage(
        r.status === 'MANUAL'
          ? `${rupees(paise)} recorded as a cash refund to hand back in person.`
          : `${rupees(paise)} refunded through Razorpay (${r.status.toLowerCase()}).`,
      );
      load();
    } catch (e) {
      setMessage(detail(e, 'The refund could not be made.'));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow p-6 space-y-3">
      <h2 className="text-lg font-semibold text-gray-900">Payments</h2>
      {payments === null && !message && <p className="text-gray-400 text-sm">Loading…</p>}
      {payments?.length === 0 && <p className="text-gray-400 text-sm">No payments for this booking.</p>}
      {payments?.map((p) => {
        const refundable = p.status === 'COMPLETED' || p.status === 'PARTIALLY_REFUNDED';
        return (
          <div key={p.id} className="border border-gray-100 rounded-xl p-3 text-sm space-y-2">
            <div className="flex justify-between">
              <span>
                {rupees(p.amountCents)} · {p.method.toUpperCase()}
                {p.gateway ? ` via ${p.gateway}` : ''}
              </span>
              <span className="font-medium">{p.status.replace(/_/g, ' ').toLowerCase()}</span>
            </div>
            {refundable && (
              <div className="flex gap-2 items-center">
                <label className="text-gray-600">
                  Refund ₹{' '}
                  <input
                    aria-label="Refund amount"
                    type="number"
                    min="0"
                    step="0.01"
                    value={amounts[p.id] ?? (p.amountCents / 100).toFixed(2)}
                    onChange={(e) => setAmounts((a) => ({ ...a, [p.id]: e.target.value }))}
                    className="w-28 border border-gray-300 rounded-lg px-2 py-1"
                  />
                </label>
                <button
                  type="button"
                  onClick={() => void refund(p)}
                  disabled={busy === p.id}
                  className="bg-red-600 text-white px-3 py-1.5 rounded-lg font-medium hover:bg-red-700 disabled:opacity-50"
                >
                  Refund
                </button>
              </div>
            )}
          </div>
        );
      })}
      {payments?.some((p) => p.status === 'COMPLETED' || p.status === 'PARTIALLY_REFUNDED') && (
        <input
          aria-label="Refund reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason for refund (shown in the customer's records)"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      )}
      {message && <p className="text-sm text-gray-700">{message}</p>}
    </div>
  );
}
