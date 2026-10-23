import { useEffect, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Check, Copy, FileText } from 'lucide-react';
import { currentAdminId } from '../apiClient';
import ConfirmDialog from '../components/ConfirmDialog';
import { useToast } from '../components/Toast';
import { apiErrorMessage } from '../shared/apiError';
import { formatDateTime, formatMoney } from '../shared/format';
import { useAccounts } from '../users/accountNames';
import BookingPayments from './BookingPayments';
import {
  addDisputeMessage,
  escalateDispute,
  formatStatus,
  getDisputeById,
  OUTCOME_LABELS,
  getDisputeMessages,
  resolveDispute,
  startReview,
  STATUS_COLORS,
  type Dispute,
  type DisputeMessage,
  type DisputeOutcome,
  type DisputeStatus,
} from './DisputeService';

const OUTCOMES: DisputeOutcome[] = ['REFUND_FULL', 'REFUND_PARTIAL', 'RELEASE_TO_SHOP', 'NO_ACTION'];

const OUTCOME_HELP: Record<DisputeOutcome, string> = {
  REFUND_FULL: 'Everything still paid is refunded through Razorpay; the booking becomes refunded.',
  REFUND_PARTIAL: 'Refunds the amount below; the shop keeps the rest, less commission.',
  RELEASE_TO_SHOP: 'The shop is paid as for any completed booking.',
  NO_ACTION: 'Only closes the case (e.g. a complaint that is not about money).',
};

/** Rupees typed by the admin as paise, or null when it is not a positive amount. */
export function paiseFrom(rupees: string): number | null {
  const value = Number(rupees.trim());
  if (!rupees.trim() || !Number.isFinite(value) || value <= 0) return null;
  return Math.round(value * 100);
}

// Starting a review is a routine forward step, so it needs no confirmation; escalating and resolving do.
type Pending = 'escalate' | 'resolve' | null;

/** What the case needs next, in the words staff use. */
const NEXT_STEP: Record<DisputeStatus, string> = {
  OPEN: 'New case. Start a review to show the parties someone is looking at it.',
  UNDER_REVIEW: 'Check the payments, evidence and messages, then resolve it - or escalate it if it needs a senior decision.',
  ESCALATED: 'Escalated for a senior decision. Resolve it once a decision is made.',
  RESOLVED: 'This case is closed.',
};

function Stepper({ status }: { status: DisputeStatus }) {
  const steps: DisputeStatus[] = status === 'ESCALATED' ? ['OPEN', 'UNDER_REVIEW', 'ESCALATED', 'RESOLVED'] : ['OPEN', 'UNDER_REVIEW', 'RESOLVED'];
  const at = steps.indexOf(status);
  return (
    <ol aria-label="Case progress" className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
      {steps.map((s, i) => (
        <li key={s} className="flex items-center gap-2" aria-current={i === at ? 'step' : undefined}>
          <span
            className={`grid place-items-center size-5 rounded-full font-semibold ${
              i < at || status === 'RESOLVED' ? 'bg-green-600 text-white' : i === at ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-600'
            }`}
            aria-hidden="true"
          >
            {i < at || status === 'RESOLVED' ? <Check size={12} /> : i + 1}
          </span>
          <span className={`capitalize ${i === at ? 'font-semibold text-gray-900' : 'text-gray-600'}`}>{formatStatus(s)}</span>
          {i < steps.length - 1 && <span className="w-6 h-px bg-gray-300" aria-hidden="true" />}
        </li>
      ))}
    </ol>
  );
}

function CopyId({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label={copied ? 'Copied' : 'Copy booking ID'}
      title="Copy"
      onClick={() => {
        void navigator.clipboard?.writeText(value).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        });
      }}
      className="p-1 rounded text-gray-500 hover:text-gray-900"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

export default function DisputeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const notify = useToast();
  const [dispute, setDispute] = useState<Dispute | null>(null);
  const [messages, setMessages] = useState<DisputeMessage[]>([]);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [messageError, setMessageError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [starting, setStarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [outcome, setOutcome] = useState<DisputeOutcome>('REFUND_FULL');
  const [partialRupees, setPartialRupees] = useState('');
  const me = currentAdminId();
  const people = useAccounts([dispute?.raisedBy, ...messages.map((m) => m.authorId)]);

  useEffect(() => {
    if (!id) return;
    let current = true;
    setLoadError(null);
    Promise.all([getDisputeById(id), getDisputeMessages(id)])
      .then(([d, m]) => {
        if (!current) return;
        setDispute(d);
        setMessages(m);
      })
      .catch((e: unknown) => {
        if (!current) return;
        const status = (e as { response?: { status?: number } }).response?.status;
        setLoadError(status === 404 ? 'This dispute does not exist.' : 'Could not load this dispute.');
      });
    return () => {
      current = false;
    };
  }, [id, reloadKey]);

  // Back to the list as it was (filter, page) when we came from it.
  const back = () => (location.key !== 'default' ? navigate(-1) : navigate('/disputes'));

  const run = async (action: () => Promise<Dispute>, done: string) => {
    const updated = await action();
    setDispute(updated);
    setPending(null);
    notify(done);
  };

  const beginReview = async () => {
    if (!dispute) return;
    setStarting(true);
    setActionError(null);
    try {
      setDispute(await startReview(dispute.id));
      notify(`Case #${dispute.caseNumber} is under review.`);
    } catch (e) {
      setActionError(apiErrorMessage(e, 'Could not start the review. Please try again.'));
    } finally {
      setStarting(false);
    }
  };

  const sendReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!dispute || !reply.trim() || !me) return;
    setSending(true);
    setMessageError(null);
    try {
      const message = await addDisputeMessage(dispute.id, me, reply.trim());
      setMessages((m) => [...m, message]);
      setReply('');
    } catch {
      setMessageError('Your message was not sent. Please try again.');
    } finally {
      setSending(false);
    }
  };

  if (!dispute) {
    return loadError ? (
      <div className="bg-white rounded-xl shadow p-6 max-w-lg space-y-3">
        <p role="alert" className="text-red-700">
          {loadError}
        </p>
        <div className="flex gap-4 text-sm font-medium">
          <button type="button" onClick={() => setReloadKey((k) => k + 1)} className="text-indigo-700 hover:underline">
            Try again
          </button>
          <Link to="/disputes" className="text-indigo-700 hover:underline">
            Back to disputes
          </Link>
        </div>
      </div>
    ) : (
      <p role="status" className="text-gray-500">
        Loading dispute…
      </p>
    );
  }

  const isOpen = dispute.status !== 'RESOLVED';
  const raiser = people[dispute.raisedBy];
  const authorName = (authorId: string) =>
    authorId === me ? 'You' : authorId === dispute.raisedBy ? `${raiser?.name ?? 'Customer'} (raised the case)` : (people[authorId]?.name ?? 'Staff / provider');

  return (
    <div className="space-y-6 max-w-4xl">
      <button type="button" onClick={back} className="flex items-center gap-1 text-sm font-medium text-indigo-700 hover:underline">
        <ArrowLeft size={16} aria-hidden="true" /> Back to disputes
      </button>

      <section aria-labelledby="case-title" className="bg-white rounded-2xl shadow p-6 space-y-4">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h1 id="case-title" className="text-xl font-bold text-gray-900">
              Case #{dispute.caseNumber}
            </h1>
            <p className="text-sm text-gray-600 mt-0.5">Opened {formatDateTime(dispute.createdAt)}</p>
          </div>
          <span className={`text-sm font-semibold px-3 py-1 rounded-full capitalize ${STATUS_COLORS[dispute.status]}`}>{formatStatus(dispute.status)}</span>
        </div>
        <Stepper status={dispute.status} />

        <div className={`rounded-xl p-4 space-y-3 ${isOpen ? 'bg-indigo-50' : 'bg-green-50'}`}>
          <h2 className="text-sm font-semibold text-gray-900">{isOpen ? 'Next step' : 'Resolved'}</h2>
          <p className="text-sm text-gray-700">{NEXT_STEP[dispute.status]}</p>
          {dispute.outcome && dispute.outcome !== 'NO_ACTION' && (
            <p className="text-sm font-medium text-gray-900">
              {OUTCOME_LABELS[dispute.outcome]}
              {dispute.refundAmountCents != null && ` (${formatMoney(dispute.refundAmountCents / 100)})`}
            </p>
          )}
          {dispute.resolution && <p className="text-sm text-gray-900 whitespace-pre-line">{dispute.resolution}</p>}
          {dispute.resolvedAt && <p className="text-xs text-gray-600">Resolved {formatDateTime(dispute.resolvedAt)}</p>}
          {actionError && (
            <p role="alert" className="text-sm text-red-700">
              {actionError}
            </p>
          )}
          {isOpen && (
            <div className="flex flex-wrap gap-2">
              {dispute.status === 'OPEN' && (
                <button
                  type="button"
                  onClick={() => void beginReview()}
                  disabled={starting}
                  className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
                >
                  {starting ? 'Starting…' : 'Start review'}
                </button>
              )}
              {dispute.status !== 'OPEN' && (
                <button type="button" onClick={() => setPending('resolve')} className="bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-800">
                  Resolve…
                </button>
              )}
              {dispute.status === 'UNDER_REVIEW' && (
                <button
                  type="button"
                  onClick={() => setPending('escalate')}
                  className="border border-orange-300 bg-white text-orange-800 px-4 py-2 rounded-lg text-sm font-medium hover:bg-orange-50"
                >
                  Escalate…
                </button>
              )}
            </div>
          )}
        </div>

        <dl className="grid sm:grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-600">Type</dt>
            <dd className="font-medium capitalize">{dispute.type.replace(/_/g, ' ')}</dd>
          </div>
          <div>
            <dt className="text-gray-600">Raised by</dt>
            <dd className="font-medium">
              {raiser ? (
                <>
                  {raiser.name} <span className="font-normal text-gray-600">· {raiser.email ?? raiser.phone}</span>
                </>
              ) : (
                <span className="font-mono text-xs break-all">{dispute.raisedBy}</span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-gray-600">Booking ID</dt>
            <dd className="flex items-center gap-1 font-mono text-xs break-all">
              {dispute.bookingId} <CopyId value={dispute.bookingId} />
            </dd>
          </div>
        </dl>
        <div>
          <h2 className="text-gray-600 text-sm">Description</h2>
          <p className="mt-1 text-gray-900 whitespace-pre-line">{dispute.description}</p>
        </div>
      </section>

      <section aria-labelledby="messages-title" className="bg-white rounded-2xl shadow p-6 space-y-3">
        <h2 id="messages-title" className="text-lg font-semibold text-gray-900">
          Messages ({messages.length})
        </h2>
        {messages.length === 0 && <p className="text-gray-500 text-sm">No messages yet. Ask the parties for details below.</p>}
        <ol className="space-y-2">
          {messages.map((m) => (
            <li key={m.id} className={`rounded-xl p-3 text-sm ${m.authorId === me ? 'bg-indigo-50 ml-6' : 'bg-gray-50 mr-6'}`}>
              <p className="text-xs text-gray-600 mb-1">
                <span className="font-semibold text-gray-800">{authorName(m.authorId)}</span> · {formatDateTime(m.createdAt)}
              </p>
              <p className="text-gray-900 whitespace-pre-line">{m.content}</p>
            </li>
          ))}
        </ol>
        <form onSubmit={sendReply} className="flex flex-col sm:flex-row gap-2">
          <label htmlFor="dispute-reply" className="sr-only">
            Message to the parties
          </label>
          <textarea
            id="dispute-reply"
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) e.currentTarget.form?.requestSubmit();
            }}
            rows={2}
            placeholder="Write a message… (Ctrl+Enter to send)"
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={sending || !reply.trim()}
            className="self-end bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {sending ? 'Sending…' : 'Send'}
          </button>
        </form>
        {messageError && (
          <p role="alert" className="text-sm text-red-700">
            {messageError}
          </p>
        )}
      </section>

      <BookingPayments bookingId={dispute.bookingId} />

      <section aria-labelledby="evidence-title" className="bg-white rounded-2xl shadow p-6">
        <h2 id="evidence-title" className="text-lg font-semibold text-gray-900 mb-3">
          Evidence ({dispute.evidenceUrls.length})
        </h2>
        {dispute.evidenceUrls.length === 0 ? (
          <p className="text-gray-500 text-sm">No evidence submitted.</p>
        ) : (
          <ul className="space-y-2">
            {dispute.evidenceUrls.map((url, i) => (
              <li key={url} className="flex items-center gap-2 text-sm">
                <FileText size={16} className="text-gray-500 shrink-0" aria-hidden="true" />
                <a href={url} target="_blank" rel="noopener noreferrer" className="text-indigo-700 hover:underline break-all">
                  Evidence {i + 1}
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
                <span className="text-xs text-gray-500 truncate" title={url}>
                  {url.split('/').pop()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {pending === 'escalate' && (
        <ConfirmDialog
          title="Escalate this case?"
          confirmLabel="Escalate"
          onConfirm={() => run(() => escalateDispute(dispute.id), `Case #${dispute.caseNumber} escalated.`)}
          onCancel={() => setPending(null)}
        >
          <p>Escalated cases need a senior decision before they can be resolved. Add a message explaining why, so the next person has context.</p>
        </ConfirmDialog>
      )}
      {pending === 'resolve' && (
        <ConfirmDialog
          title={`Resolve case #${dispute.caseNumber}?`}
          tone="danger"
          confirmLabel="Resolve case"
          reason={{
            label: 'Resolution',
            required: true,
            placeholder: 'What was decided, e.g. "Full refund issued - provider did not attend."',
          }}
          onConfirm={(resolution) => {
            const paise = outcome === 'REFUND_PARTIAL' ? paiseFrom(partialRupees) : undefined;
            if (paise === null) {
              throw Object.assign(new Error('amount'), { response: { data: { detail: 'Enter the amount to refund, in rupees.' } } });
            }
            return run(() => resolveDispute(dispute.id, resolution, outcome, paise), `Case #${dispute.caseNumber} resolved.`);
          }}
          onCancel={() => setPending(null)}
        >
          <fieldset className="space-y-2">
            <legend className="text-sm font-semibold text-gray-900 mb-1">What happens to the money</legend>
            {OUTCOMES.map((o) => (
              <label key={o} className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="dispute-outcome"
                  value={o}
                  checked={outcome === o}
                  onChange={() => setOutcome(o)}
                  className="mt-1"
                />
                <span>
                  <span className="font-medium text-gray-900">{OUTCOME_LABELS[o]}</span>
                  <span className="block text-xs text-gray-600">{OUTCOME_HELP[o]}</span>
                </span>
              </label>
            ))}
            {outcome === 'REFUND_PARTIAL' && (
              <label className="block text-sm">
                <span className="text-gray-700">Amount to refund (₹)</span>
                <input
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  value={partialRupees}
                  onChange={(e) => setPartialRupees(e.target.value)}
                  className="mt-1 w-40 border border-gray-300 rounded-lg px-3 py-1.5"
                />
              </label>
            )}
          </fieldset>
          <p className="mt-3">
            This closes the case for good - it cannot be reopened. The refund or release is made first; if it fails, the case stays
            open. The resolution is kept on the case record.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}
