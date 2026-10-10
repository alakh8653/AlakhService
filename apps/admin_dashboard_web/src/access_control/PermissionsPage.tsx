import { useEffect, useMemo, useState } from 'react';
import DataTable, { type Column } from '../components/DataTable';
import { getPermissions, type Permission } from './AccessControlService';

const columns: Column<Permission>[] = [
  { key: 'key', header: 'Permission', render: (r) => <code className="text-xs">{r.key}</code> },
  { key: 'resource', header: 'Resource' },
  { key: 'description', header: 'Description' },
];

export default function PermissionsPage() {
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPermissions()
      .then(setPermissions)
      .catch(() => setError('Failed to load permissions.'))
      .finally(() => setIsLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return permissions;
    return permissions.filter((p) => p.key.toLowerCase().includes(q) || p.resource.toLowerCase().includes(q));
  }, [permissions, query]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Permissions</h1>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Filter by key or resource"
        className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-72"
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <DataTable columns={columns} rows={filtered} isLoading={isLoading} />
    </div>
  );
}
