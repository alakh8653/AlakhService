import { useEffect, useState, type FormEvent } from 'react';
import DataTable, { type Column } from '../components/DataTable';
import ConfirmDialog from '../components/ConfirmDialog';
import Modal from '../components/Modal';
import { useToast } from '../components/Toast';
import { apiErrorMessage } from '../shared/apiError';
import { formatDateTime, shortId } from '../shared/format';
import { useAccounts } from '../users/accountNames';
import { decideRequest, getPrivacyRequests, type PrivacyRequest, type RequestStatus } from './PrivacyRequestService';

const STATUSES: { value: RequestStatus; label: string }[] = [
  { value: 'PENDING', label: 'Pending' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'REJECTED', label: 'Rejected' },
];

type Pending = { request: PrivacyRequest; action: 'complete' | 'reject' };

function CompleteExportDialog({ request, onDone, onCancel }: { request: PrivacyRequest; onDone: (r: PrivacyRequest) => void; onCancel: () => void }) {
  const [url, setUrl] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const invalid = !/^https:\/\/\S+$/.test(url.trim());

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (invalid || busy) return;
    setBusy(true);
    setError(null);
    try {
      onDone(await decideRequest(request, { status: 'COMPLETED', exportUrl: url.trim(), note: note.trim() }));
    } catch (err) {
      setError(apiErrorMessage(err, 'That did not work. Please try again.'));
      setBusy(false);
    }
  };

  return (
    <Modal title="Complete data export" onClose={() => !busy && onCancel()} initialFocus="input">
      <form onSubmit={(e) => void submit(e)} className="space-y-3">
        <label className="block text-sm font-medium text-gray-700">
          Download link for the user <span className="text-red-700">*</span>
          <input
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
            aria-invalid={url !== '' && invalid ? true : undefined}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-normal focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </label>
        {url !== '' && invalid && <p className="text-xs text-red-700">Use an https:// link.</p>}
        <label className="block text-sm font-medium text-gray-700">
          Note (optional)
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-normal focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
            {error}
          </p>
        )}
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button type="button" onClick={onCancel} disabled={busy} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
            Cancel
          </button>
          <button type="submit" disabled={busy || invalid} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
            {busy ? 'Working…' : 'Mark completed'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** Data export and erasure requests from users (DPDP / GDPR), worked through by hand. */
export default function PrivacyRequestsPage() {
  const notify = useToast();
  const [status, setStatus] = useState<RequestStatus>('PENDING');
  const [exportsList, setExports] = useState<PrivacyRequest[]>([]);
  const [erasures, setErasures] = useState<PrivacyRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const accounts = useAccounts([...exportsList, ...erasures].map((r) => r.userId));

  useEffect(() => {
    let current = true;
    setIsLoading(true);
    setError(null);
    getPrivacyRequests(status)
      .then((res) => {
        if (!current) return;
        setExports(res.exports);
        setErasures(res.erasures);
      })
      .catch((e) => current && setError(apiErrorMessage(e, 'Could not load privacy requests.')))
      .finally(() => current && setIsLoading(false));
    return () => {
      current = false;
    };
  }, [status]);

  const decided = (r: PrivacyRequest) => {
    const drop = (list: PrivacyRequest[]) => list.filter((x) => x.id !== r.id);
    if (r.kind === 'export') setExports(drop);
    else setErasures(drop);
    setPending(null);
    notify(`Request ${r.status === 'COMPLETED' ? 'completed' : 'rejected'}.`);
  };

  const person = (id: string) => <span title={id}>{accounts[id]?.name ?? <span className="font-mono text-xs">{shortId(id)}</span>}</span>;

  const columns = (kind: 'export' | 'erasure'): Column<PrivacyRequest>[] => [
    { key: 'requestedAt', header: 'Requested (IST)', render: (r) => formatDateTime(r.requestedAt).replace(' IST', '') },
    { key: 'userId', header: 'User', render: (r) => person(r.userId) },
    ...(kind === 'erasure'
      ? [{ key: 'reason' as const, header: 'Reason', className: 'hidden md:table-cell whitespace-normal', render: (r: PrivacyRequest) => r.reason ?? '—' }]
      : []),
    ...(status === 'PENDING'
      ? [
          {
            key: 'id' as const,
            header: 'Actions',
            render: (r: PrivacyRequest) => (
              <span className="flex gap-3">
                <button type="button" onClick={() => setPending({ request: r, action: 'complete' })} className="text-sm font-medium text-indigo-700 hover:underline" aria-label={`Complete ${kind} request from ${accounts[r.userId]?.name ?? shortId(r.userId)}`}>
                  Complete
                </button>
                <button type="button" onClick={() => setPending({ request: r, action: 'reject' })} className="text-sm font-medium text-red-700 hover:underline" aria-label={`Reject ${kind} request from ${accounts[r.userId]?.name ?? shortId(r.userId)}`}>
                  Reject
                </button>
              </span>
            ),
          },
        ]
      : [
          { key: 'completedAt' as const, header: 'Decided (IST)', render: (r: PrivacyRequest) => (r.completedAt ? formatDateTime(r.completedAt).replace(' IST', '') : '—') },
          { key: 'resolutionNote' as const, header: 'Note', className: 'hidden md:table-cell whitespace-normal', render: (r: PrivacyRequest) => r.resolutionNote ?? '—' },
        ]),
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Privacy requests</h1>
        <p className="text-sm text-gray-600">
          Users asking for a copy of their data or for their account to be erased. Do the work first, then record the outcome here.
        </p>
      </div>
      <div role="group" aria-label="Status" className="flex gap-2 flex-wrap">
        {STATUSES.map((s) => (
          <button
            key={s.value}
            type="button"
            aria-pressed={status === s.value}
            onClick={() => setStatus(s.value)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium border ${status === s.value ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'}`}
          >
            {s.label}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      <section aria-labelledby="exports" className="space-y-2">
        <h2 id="exports" className="text-lg font-semibold text-gray-900">Data exports</h2>
        <DataTable failed={!!error} label="Data exports" columns={columns('export')} rows={exportsList} isLoading={isLoading} emptyMessage="No export requests." />
      </section>
      <section aria-labelledby="erasures" className="space-y-2">
        <h2 id="erasures" className="text-lg font-semibold text-gray-900">Account erasures</h2>
        <DataTable failed={!!error} label="Account erasures" columns={columns('erasure')} rows={erasures} isLoading={isLoading} emptyMessage="No erasure requests." />
      </section>

      {pending?.action === 'complete' && pending.request.kind === 'export' && (
        <CompleteExportDialog request={pending.request} onDone={decided} onCancel={() => setPending(null)} />
      )}
      {pending?.action === 'complete' && pending.request.kind === 'erasure' && (
        <ConfirmDialog
          title="Mark erasure completed?"
          confirmLabel="Mark completed"
          tone="danger"
          reason={{ label: 'Note (optional)', placeholder: 'What was erased or anonymised' }}
          onCancel={() => setPending(null)}
          onConfirm={async (note) => decided(await decideRequest(pending.request, { status: 'COMPLETED', note }))}
        >
          <p>Only confirm once the user's personal data has been erased or anonymised in every service. This cannot be undone.</p>
        </ConfirmDialog>
      )}
      {pending?.action === 'reject' && (
        <ConfirmDialog
          title="Reject this request?"
          confirmLabel="Reject request"
          tone="danger"
          reason={{ label: 'Reason (shown to the user)', required: true, placeholder: 'e.g. Records kept for tax law until 2032' }}
          onCancel={() => setPending(null)}
          onConfirm={async (note) => decided(await decideRequest(pending.request, { status: 'REJECTED', note }))}
        />
      )}
    </div>
  );
}
