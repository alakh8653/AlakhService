import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { format } from 'date-fns';
import DataTable, { type Column } from '../components/DataTable';
import { currentAdminId } from '../apiClient';
import RiskPanel, { RiskBadge } from './RiskPanel';
import { getRiskLevels, type RiskProfile } from './RiskService';
import { banAccount, searchAccounts, unbanAccount, type Account } from './UserService';

type AccountRow = Account & { risk?: RiskProfile };

function errorText(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) {
    const detail = (e.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === 'string') return detail;
  }
  return fallback;
}

export default function UsersPage() {
  const [query, setQuery] = useState('');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  // Keyed by user id; a user without a profile has had no signals yet.
  const [risks, setRisks] = useState<Record<string, RiskProfile>>({});
  const [riskError, setRiskError] = useState(false);
  const [riskOf, setRiskOf] = useState<AccountRow | null>(null);
  const me = currentAdminId();

  const load = useCallback((q: string) => {
    setIsLoading(true);
    setError(null);
    setRiskOf(null);
    searchAccounts(q)
      .then(setAccounts)
      .catch(() => {
        setAccounts([]);
        setError('Failed to load accounts.');
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => load(''), [load]);

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

  const toggle = async (account: Account) => {
    let reason = '';
    if (account.isActive) {
      const answer = window.prompt(`Ban ${account.name}? They will be signed out and unable to sign in.\nReason:`);
      if (answer === null) return;
      reason = answer.trim() || 'No reason given';
    } else if (!window.confirm(`Restore access for ${account.name}?`)) {
      return;
    }
    setBusyId(account.id);
    setError(null);
    try {
      if (account.isActive) await banAccount(account.id, reason);
      else await unbanAccount(account.id);
      setAccounts((list) => list.map((a) => (a.id === account.id ? { ...a, isActive: !a.isActive } : a)));
    } catch (e) {
      setError(errorText(e, 'The change could not be made.'));
    } finally {
      setBusyId(null);
    }
  };

  const columns: Column<AccountRow>[] = [
    { key: 'name', header: 'Name' },
    { key: 'email', header: 'Email', render: (r) => r.email ?? '—' },
    { key: 'phone', header: 'Phone', render: (r) => r.phone ?? '—' },
    { key: 'role', header: 'Role', render: (r) => <span className="capitalize">{r.role}</span> },
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
          <button type="button" aria-label={`Risk signals for ${r.name}`} onClick={() => setRiskOf(r)}>
            <RiskBadge level={r.risk.level} />
          </button>
        ) : (
          '—'
        ),
    },
    { key: 'createdAt', header: 'Joined', render: (r) => format(new Date(r.createdAt), 'MMM d, yyyy') },
    {
      key: 'id',
      header: '',
      render: (r) =>
        r.id === me ? null : (
          <button
            type="button"
            disabled={busyId === r.id}
            onClick={() => void toggle(r)}
            className={`text-sm font-medium ${r.isActive ? 'text-red-600' : 'text-green-700'} disabled:opacity-50`}
          >
            {r.isActive ? 'Ban' : 'Unban'}
          </button>
        ),
    },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Users</h1>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          load(query);
        }}
      >
        <input
          className="flex-1 max-w-md rounded-md border border-gray-300 px-3 py-2"
          placeholder="Search by name, email or phone"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" className="rounded-md bg-gray-900 text-white px-4 py-2 text-sm">
          Search
        </button>
      </form>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {riskError && <p className="text-sm text-gray-500">Risk levels could not be loaded.</p>}
      {riskOf?.risk && <RiskPanel name={riskOf.name} profile={riskOf.risk} onClose={() => setRiskOf(null)} />}
      <DataTable columns={columns} rows={rows} isLoading={isLoading} emptyMessage="No accounts found." />
    </div>
  );
}
