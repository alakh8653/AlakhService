import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { format } from 'date-fns';
import DataTable, { type Column } from '../components/DataTable';
import { currentAdminId } from '../apiClient';
import { banAccount, searchAccounts, unbanAccount, type Account } from './UserService';

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
  const me = currentAdminId();

  const load = useCallback((q: string) => {
    setIsLoading(true);
    setError(null);
    searchAccounts(q)
      .then(setAccounts)
      .catch(() => {
        setAccounts([]);
        setError('Failed to load accounts.');
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => load(''), [load]);

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

  const columns: Column<Account>[] = [
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
      <DataTable columns={columns} rows={accounts} isLoading={isLoading} emptyMessage="No accounts found." />
    </div>
  );
}
