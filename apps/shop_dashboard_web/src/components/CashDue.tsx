import { useEffect, useState } from 'react';
import { confirmCashReceived, getBookingPayments, type BookingPayment } from '../services/paymentService';
import { apiErrorMessage, formatMoney } from '../services/format';

/** Cash the customer chose to pay in person, with a button to record it once handed over. */
export default function CashDue({ bookingId }: { bookingId: string }) {
  const [due, setDue] = useState<BookingPayment[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getBookingPayments(bookingId)
      .then((payments) => {
        if (!cancelled) setDue(payments.filter((p) => p.method === 'cash' && p.status === 'PENDING'));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [bookingId]);

  if (due.length === 0) return null;
  const payment = due[0];

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await confirmCashReceived(payment.id);
      setDue([]);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not record the payment'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-amber-700">Cash due {formatMoney(payment.amountCents)}</span>
      <button
        type="button"
        onClick={() => void confirm()}
        disabled={busy}
        className="bg-green-50 text-green-700 border border-green-200 rounded-lg px-3 py-1.5 hover:bg-green-100 disabled:opacity-50"
      >
        Mark received
      </button>
      {error && <span className="text-red-600">{error}</span>}
    </div>
  );
}
