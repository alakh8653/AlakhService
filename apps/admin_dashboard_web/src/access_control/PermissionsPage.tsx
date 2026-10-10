import { useEffect, useMemo, useState } from 'react';
import DataTable, { type Column } from '../components/DataTable';
import { getPermissions, getRoles, type Permission, type Role } from './AccessControlService';

interface PermissionRow extends Permission {
  id: string;
  grantedTo: string[];
}

const columns: Column<PermissionRow>[] = [
  { key: 'key', header: 'Permission', render: (r) => <code className="text-xs">{r.key}</code> },
  { key: 'resource', header: 'Resource', render: (r) => <span className="capitalize">{r.resource}</span> },
  { key: 'description', header: 'Description' },
  {
    key: 'grantedTo',
    header: 'Granted to',
    render: (r) => (
      <span className="flex gap-1 flex-wrap">
        {r.grantedTo.map((name) => (
          <span key={name} className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full capitalize">{name}</span>
        ))}
      </span>
    ),
  },
];

export default function PermissionsPage() {
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getPermissions(), getRoles()])
      .then(([p, r]) => {
        setPermissions(p);
        setRoles(r);
      })
      .catch(() => setError('Failed to load permissions.'))
      .finally(() => setIsLoading(false));
  }, []);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return permissions
      .filter((p) => !q || p.key.toLowerCase().includes(q) || p.resource.toLowerCase().includes(q))
      .map((p) => ({
        ...p,
        id: p.key,
        grantedTo: roles.filter((r) => r.permissions.includes(p.key)).map((r) => r.name),
      }));
  }, [permissions, roles, query]);

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
      <DataTable columns={columns} rows={rows} isLoading={isLoading} />
    </div>
  );
}
