import { useEffect, useState } from 'react';
import DataTable, { type Column } from '../components/DataTable';
import { getRoles, type Role } from './AccessControlService';

const columns: Column<Role>[] = [
  { key: 'name', header: 'Role', render: (r) => <span className="font-medium capitalize">{r.name}</span> },
  { key: 'description', header: 'Description' },
  { key: 'permissions', header: 'Permissions', render: (r) => r.permissions.length },
  { key: 'userCount', header: 'Users' },
];

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRoles()
      .then(setRoles)
      .catch(() => setError('Failed to load roles.'))
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Roles</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <DataTable columns={columns} rows={roles} isLoading={isLoading} />
    </div>
  );
}
