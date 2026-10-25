import { useCallback, useEffect, useState } from 'react';
import ConfirmDialog from '../components/ConfirmDialog';
import { useToast } from '../components/Toast';
import { formatDateTime, formatMoney } from '../shared/format';
import { getBookingPayments, refundPayment, type BookingPayment } from './PaymentService';

const rupees = (paise: number) => formatMoney(paise / 100);

const STATUS_STYLES: Record<string, string> = {
  COMPLETED: 'bg-green-100 text-green-800',
  PARTIALLY_REFUNDED: 'bg-yellow-100 text-yellow-800',
  REFUNDED: 'bg-gray-100 text-gray-700',
  FAILED: 'bg-red-100 text-red-800',
};

const refundable = (p: BookingPayment) => p.status === 'COMPLETED' || p.status === 'PARTIALLY_REFUNDED';

/** The booking's payments, with a refund action for those that can still be refunded. */
export default function BookingPayments({ bookingId }: { bookingId: string }) {
  const notify = useToast();
  const [payments, setPayments] = useState<BookingPayment[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [invalid, setInvalid] = useState<string | null>(null);
  const [refunding, setRefunding] = useState<{ payment: BookingPayment; paise: number } | null>(null);

  const load = useCallback(() => {
    setLoadError(false);
    getBookingPayments(bookingId)
      .then(setPayments)
      .catch(() => setLoadError(true));
  }, [bookingId]);

  useEffect(load, [load]);

  const askRefund = (p: BookingPayment) => {
    const paise = Math.round(Number(amounts[p.id] ?? p.amountCents / 100) * 100);
    if (!Number.isFinite(paise) || paise <= 0) return setInvalid(p.id);
    setInvalid(null);
    setRefunding({ payment: p, paise });
  };

  const doRefund = async (reason: string) => {
    if (!refunding) return;
    const r = await refundPayment(refunding.payment.id, refunding.paise, reason);
    setRefunding(null);
    notify(
      r.status === 'MANUAL'
        ? `${rupees(refunding.paise)} recorded as a cash refund to hand back in person.`
        : `${rupees(refunding.paise)} refunded through Razorpay (${r.status.toLowerCase()}).`,
    );
    load();
  };

  return (
    <section aria-labelledby="payments-title" className="bg-white rounded-2xl shadow p-6 space-y-3">
      <h2 id="payments-title" className="text-lg font-semibold text-gray-900">
        Payments
      </h2>
      {loadError && (
        <p role="alert" className="text-sm text-red-700">
          Could not load payments.{' '}
          <button type="button" onClick={load} className="font-medium underline">
            Try again
          </button>
        </p>
      )}
      {payments === null && !loadError && <p className="text-gray-500 text-sm">Loading…</p>}
      {payments?.length === 0 && <p className="text-gray-500 text-sm">No payments for this booking.</p>}
      {payments?.map((p) => (
        <div key={p.id} className="border border-gray-200 rounded-xl p-3 text-sm space-y-2">
          <div className="flex justify-between gap-2 flex-wrap">
            <span>
              <span className="font-semibold text-gray-900">{rupees(p.amountCents)}</span> · {p.method.toUpperCase()}
              {p.gateway ? ` via ${p.gateway}` : ''}
              <span className="block text-xs text-gray-600">{formatDateTime(p.createdAt)}</span>
            </span>
            <span className={`self-start text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[p.status] ?? 'bg-gray-100 text-gray-700'}`}>
              {p.status.replace(/_/g, ' ').toLowerCase()}
            </span>
          </div>
          {refundable(p) && (
            <div className="flex gap-2 items-center flex-wrap">
              <label htmlFor={`refund-${p.id}`} className="text-gray-700">
                Refund amount (₹)
              </label>
              <input
                id={`refund-${p.id}`}
                type="number"
                inputMode="decimal"
                min="0.01"
                max={(p.amountCents / 100).toFixed(2)}
                step="0.01"
                value={amounts[p.id] ?? (p.amountCents / 100).toFixed(2)}
                onChange={(e) => setAmounts((a) => ({ ...a, [p.id]: e.target.value }))}
                aria-invalid={invalid === p.id || undefined}
                aria-describedby={invalid === p.id ? `refund-${p.id}-error` : undefined}
                className="w-32 border border-gray-300 rounded-lg px-2 py-1"
              />
              <button
                type="button"
                onClick={() => askRefund(p)}
                className="border border-red-300 text-red-700 px-3 py-1.5 rounded-lg font-medium hover:bg-red-50"
              >
                Refund…
              </button>
              {invalid === p.id && (
                <p id={`refund-${p.id}-error`} className="basis-full text-red-700">
                  Enter an amount to refund.
                </p>
              )}
            </div>
          )}
        </div>
      ))}
      {refunding && (
        <ConfirmDialog
          title={`Refund ${rupees(refunding.paise)}?`}
          tone="danger"
          confirmLabel={`Refund ${rupees(refunding.paise)}`}
          reason={{ label: 'Reason (shown in the customer’s records)', required: true, placeholder: 'e.g. Provider did not attend' }}
          onConfirm={doRefund}
          onCancel={() => setRefunding(null)}
        >
          <p>
            {refunding.payment.method.toLowerCase() === 'cash'
              ? 'Cash payments are recorded as a manual refund for you to hand back in person.'
              : 'The money goes back to the customer’s original payment method through Razorpay. This cannot be undone.'}
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}
