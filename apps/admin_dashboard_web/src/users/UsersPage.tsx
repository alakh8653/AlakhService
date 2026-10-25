import { useEffect, useState } from 'react';
import { Search, X } from 'lucide-react';
import DataTable, { type Column } from '../components/DataTable';
import ConfirmDialog from '../components/ConfirmDialog';
import { useToast } from '../components/Toast';
import { currentAdminId } from '../apiClient';
import { formatDate } from '../shared/format';
import { useDebouncedValue } from '../shared/useDebouncedValue';
import RiskPanel, { RiskBadge } from './RiskPanel';
import { getRiskLevels, type RiskProfile } from './RiskService';
import { banAccount, searchAccounts, unbanAccount, type Account } from './UserService';

type AccountRow = Account & { risk?: RiskProfile };

const LIMIT = 50;

export default function UsersPage() {
  const notify = useToast();
  const [query, setQuery] = useState('');
  // Search as you type, once typing pauses; Enter searches straight away.
  const debounced = useDebouncedValue(query.trim(), 350);
  const [submitted, setSubmitted] = useState<string | null>(null);
  const searchFor = submitted ?? debounced;
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  // Keyed by user id; a user without a profile has had no signals yet.
  const [risks, setRisks] = useState<Record<string, RiskProfile>>({});
  const [riskError, setRiskError] = useState(false);
  const [riskOf, setRiskOf] = useState<AccountRow | null>(null);
  const [pending, setPending] = useState<Account | null>(null);
  const me = currentAdminId();

  useEffect(() => {
    let current = true; // ignore answers to searches the admin has already moved on from
    setIsLoading(true);
    setError(null);
    setRiskOf(null);
    searchAccounts(searchFor, LIMIT)
      .then((found) => {
        if (current) setAccounts(found);
      })
      .catch(() => {
        if (!current) return;
        setAccounts([]);
        setError('Could not load accounts.');
      })
      .finally(() => {
        if (current) setIsLoading(false);
      });
    return () => {
      current = false;
    };
  }, [searchFor, reloadKey]);

  // One lookup for every account on the page, again only when the set of accounts changes (not on a ban).
  const accountIds = accounts.map((a) => a.id).join('\n');
  useEffect(() => {
    if (!accountIds) return;
    let current = true;
    setRiskError(false);
    getRiskLevels(accountIds.split('\n'))
      .then((found) => {
        if (current) setRisks(found);
      })
      .catch(() => {
        if (!current) return;
        setRisks({});
        setRiskError(true);
      });
    return () => {
      current = false;
    };
  }, [accountIds]);

  const rows: AccountRow[] = accounts.map((a) => ({ ...a, risk: risks[a.id] }));

  const applyChange = async (account: Account, reason: string) => {
    if (account.isActive) await banAccount(account.id, reason);
    else await unbanAccount(account.id);
    setAccounts((list) => list.map((a) => (a.id === account.id ? { ...a, isActive: !a.isActive } : a)));
    setPending(null);
    notify(account.isActive ? `${account.name} is banned and has been signed out.` : `${account.name} can sign in again.`);
  };

  const columns: Column<AccountRow>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (r) => (
        <span className="font-medium text-gray-900">
          {r.name}
          {r.id === me && <span className="ml-2 text-xs font-normal text-gray-500">(you)</span>}
          <span className="sm:hidden block text-xs font-normal text-gray-500 max-w-40 truncate">{r.email ?? r.phone}</span>
        </span>
      ),
    },
    {
      key: 'email',
      header: 'Contact',
      render: (r) => (
        <span className="block leading-tight">
          {r.email ?? '—'}
          {r.phone && <span className="block text-xs text-gray-500">{r.phone}</span>}
        </span>
      ),
      className: 'hidden sm:table-cell',
    },
    { key: 'role', header: 'Role', render: (r) => <span className="capitalize">{r.role}</span>, className: 'hidden md:table-cell' },
    {
      key: 'isActive',
      header: 'Status',
      render: (r) => (
        <span
          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${r.isActive ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}
        >
          {r.isActive ? 'Active' : 'Banned'}
        </span>
      ),
    },
    {
      key: 'risk',
      header: 'Risk',
      render: (r) =>
        r.risk ? (
          <button
            type="button"
            aria-label={`Risk signals for ${r.name}`}
            title="Show risk signals"
            onClick={() => setRiskOf(r)}
            className="rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
          >
            <RiskBadge level={r.risk.level} />
          </button>
        ) : (
          <span className="text-gray-500" title="No risk signals recorded yet">
            —
          </span>
        ),
    },
    { key: 'createdAt', header: 'Joined', render: (r) => formatDate(r.createdAt), className: 'hidden lg:table-cell' },
    {
      key: 'id',
      header: 'Actions',
      render: (r) =>
        r.id === me ? null : (
          <button
            type="button"
            aria-label={`${r.isActive ? 'Ban' : 'Unban'} ${r.name}`}
            onClick={() => setPending(r)}
            className={`text-sm font-medium rounded-lg border px-3 py-1 ${
              r.isActive ? 'border-red-200 text-red-700 hover:bg-red-50' : 'border-green-200 text-green-800 hover:bg-green-50'
            }`}
          >
            {r.isActive ? 'Ban' : 'Unban'}
          </button>
        ),
    },
  ];

  const searching = searchFor !== '';
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Users</h1>
        <p className="text-sm text-gray-600">Find an account to check its risk, or ban or restore it.</p>
      </div>
      <form
        role="search"
        className="flex gap-2 max-w-xl"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(query.trim());
        }}
      >
        <label htmlFor="user-search" className="sr-only">
          Search users
        </label>
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" aria-hidden="true" />
          <input
            id="user-search"
            type="search"
            className="w-full rounded-lg border border-gray-300 pl-9 pr-9 py-2"
            placeholder="Name, email, phone or user ID"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSubmitted(null);
            }}
            autoComplete="off"
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => {
                setQuery('');
                setSubmitted('');
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-500 hover:text-gray-900"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </form>
      <p className="text-sm text-gray-600" aria-live="polite">
        {isLoading
          ? 'Searching…'
          : error
            ? null
            : searching
              ? `${accounts.length === LIMIT ? `First ${LIMIT}` : accounts.length} ${accounts.length === 1 ? 'account matches' : 'accounts match'} “${searchFor}”`
              : `Newest ${accounts.length} accounts`}
      </p>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}{' '}
          <button type="button" onClick={() => setReloadKey((k) => k + 1)} className="font-medium underline">
            Try again
          </button>
        </p>
      )}
      {riskError && <p className="text-sm text-gray-600">Risk levels could not be loaded.</p>}
      {riskOf?.risk && <RiskPanel name={riskOf.name} profile={riskOf.risk} onClose={() => setRiskOf(null)} />}
      <DataTable
        label="Accounts"
        columns={columns}
        rows={rows}
        isLoading={isLoading}
        emptyMessage={searching ? `No accounts match “${searchFor}”.` : 'No accounts yet.'}
      />
      {pending &&
        (pending.isActive ? (
          <ConfirmDialog
            title={`Ban ${pending.name}?`}
            tone="danger"
            confirmLabel="Ban account"
            reason={{ label: 'Reason', required: true, placeholder: 'e.g. Repeated no-shows reported by providers' }}
            onConfirm={(reason) => applyChange(pending, reason)}
            onCancel={() => setPending(null)}
          >
            <p>
              {pending.email ?? pending.phone ?? pending.name} will be signed out everywhere and won’t be able to sign in until
              unbanned. The reason is kept in the audit log.
            </p>
          </ConfirmDialog>
        ) : (
          <ConfirmDialog
            title={`Unban ${pending.name}?`}
            confirmLabel="Restore access"
            onConfirm={(reason) => applyChange(pending, reason)}
            onCancel={() => setPending(null)}
          >
            <p>They will be able to sign in again straight away.</p>
          </ConfirmDialog>
        ))}
    </div>
  );
}
