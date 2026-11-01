import { useEffect, useState } from 'react';
import DataTable, { type Column } from '../components/DataTable';
import { formatDateTime, shortId } from '../shared/format';
import { useAccounts } from '../users/accountNames';
import {
  getFlaggedMessages,
  getRepeatOffenders,
  reasonLabel,
  type FlaggedMessage,
  type RepeatOffender,
} from './ChatModerationService';

const PER_PAGE = 25;
const ROLE_LABELS: Record<string, string> = { customer: 'Customer', shop: 'Shop owner', provider: 'Provider' };
const roleLabel = (role: string) => ROLE_LABELS[role] ?? role;

/**
 * Booking chat messages in which someone tried to share a phone number, email or UPI handle (hidden
 * before delivery), and the people who keep trying: taking customers off the platform costs commission.
 */
export default function ContactSharingPage() {
  const [offenders, setOffenders] = useState<RepeatOffender[]>([]);
  const [messages, setMessages] = useState<FlaggedMessage[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [senderId, setSenderId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const accounts = useAccounts([...offenders.map((o) => o.userId), ...messages.map((m) => m.senderId)]);

  useEffect(() => {
    getRepeatOffenders()
      .then(setOffenders)
      .catch(() => setError('Could not load contact-sharing attempts.'));
  }, []);

  useEffect(() => {
    let current = true;
    setIsLoading(true);
    getFlaggedMessages({ senderId: senderId ?? undefined, page, perPage: PER_PAGE })
      .then((res) => {
        if (!current) return;
        setMessages(res.data);
        setTotal(res.total);
      })
      .catch(() => {
        if (current) setError('Could not load contact-sharing attempts.');
      })
      .finally(() => {
        if (current) setIsLoading(false);
      });
    return () => {
      current = false;
    };
  }, [senderId, page]);

  const person = (id: string) => {
    const account = accounts[id];
    return account ? (
      <span title={id}>{account.name}</span>
    ) : (
      <span className="font-mono text-xs" title={id}>
        {shortId(id)}
      </span>
    );
  };

  const offenderColumns: Column<RepeatOffender>[] = [
    { key: 'userId', header: 'Person', render: (r) => person(r.userId) },
    { key: 'senderRole', header: 'Writes as', render: (r) => roleLabel(r.senderRole) },
    { key: 'attempts', header: 'Attempts' },
    { key: 'bookings', header: 'Bookings', className: 'hidden sm:table-cell' },
    { key: 'lastAttemptAt', header: 'Last attempt (IST)', render: (r) => formatDateTime(r.lastAttemptAt).replace(' IST', '') },
  ];

  const messageColumns: Column<FlaggedMessage>[] = [
    { key: 'createdAt', header: 'When (IST)', render: (r) => formatDateTime(r.createdAt).replace(' IST', '') },
    { key: 'senderId', header: 'From', render: (r) => <span>{person(r.senderId)} · {roleLabel(r.senderRole)}</span> },
    {
      key: 'originalBody',
      header: 'Written',
      render: (r) => <span className="whitespace-pre-wrap break-words">{r.originalBody ?? r.body}</span>,
    },
    { key: 'reasons', header: 'Hidden', render: (r) => r.reasons.map(reasonLabel).join(', ') },
    {
      key: 'bookingId',
      header: 'Booking',
      className: 'hidden lg:table-cell',
      render: (r) => (
        <span className="font-mono text-xs" title={r.bookingId}>
          {shortId(r.bookingId)}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Contact Sharing</h1>
        <p className="text-sm text-gray-600">
          Phone numbers, emails and UPI handles written in booking chats are hidden before delivery. Repeated attempts to take a
          customer off the platform show up here.
        </p>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      <section aria-labelledby="offenders" className="space-y-2">
        <h2 id="offenders" className="text-lg font-semibold text-gray-900">
          Repeated attempts (last 30 days)
        </h2>
        <DataTable failed={!!error}
          label="Repeated attempts"
          columns={offenderColumns}
          rows={offenders}
          onRowClick={(r) => {
            setSenderId(r.userId);
            setPage(1);
          }}
          rowLabel={(r) => `Show messages from ${accounts[r.userId]?.name ?? shortId(r.userId)}`}
          emptyMessage="Nobody has tried more than once."
        />
      </section>

      <section aria-labelledby="flagged" className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 id="flagged" className="text-lg font-semibold text-gray-900">
            {senderId ? `Messages from ${accounts[senderId]?.name ?? shortId(senderId)}` : 'Flagged messages'}
          </h2>
          {senderId && (
            <button
              type="button"
              onClick={() => {
                setSenderId(null);
                setPage(1);
              }}
              className="text-sm font-medium text-indigo-700 hover:underline"
            >
              Show everyone
            </button>
          )}
        </div>
        <DataTable failed={!!error}
          label="Flagged messages"
          columns={messageColumns}
          rows={messages}
          isLoading={isLoading}
          total={total}
          page={page}
          perPage={PER_PAGE}
          onPageChange={setPage}
          emptyMessage="No flagged messages."
        />
      </section>
    </div>
  );
}
