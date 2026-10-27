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
  { key: 'description', header: 'Description', className: 'hidden md:table-cell' },
  {
    key: 'grantedTo',
    header: 'Granted to',
    render: (r) => (
      <span className="flex gap-1 flex-wrap">
        {r.grantedTo.length === 0 && <span className="text-gray-500">No role</span>}
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
      .catch(() => setError('Could not load permissions.'))
      .finally(() => setIsLoading(false));
  }, []);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return permissions
      .filter((p) => !q || [p.key, p.resource, p.description].some((t) => t.toLowerCase().includes(q)))
      .map((p) => ({
        ...p,
        id: p.key,
        grantedTo: roles.filter((r) => r.permissions.includes(p.key)).map((r) => r.name),
      }));
  }, [permissions, roles, query]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Permissions</h1>
        <p className="text-sm text-gray-600">Everything a role can be allowed to do, and which roles have it. Change them on the Roles page.</p>
      </div>
      <label className="flex flex-col gap-1 text-sm text-gray-700 max-w-xs">
        Filter permissions
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Key, resource or description"
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      <DataTable failed={!!error}
        label="Permissions"
        columns={columns}
        rows={rows}
        isLoading={isLoading}
        emptyMessage={query ? `No permissions match “${query}”.` : 'No permissions defined.'}
      />
    </div>
  );
}
