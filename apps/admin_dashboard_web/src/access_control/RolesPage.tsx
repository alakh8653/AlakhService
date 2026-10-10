import { useEffect, useState, type FormEvent } from 'react';
import { ChevronDown, ChevronRight, Lock } from 'lucide-react';
import {
  apiErrorMessage,
  createRole,
  deleteRole,
  getPermissions,
  getRoles,
  updateRolePermissions,
  type Permission,
  type Role,
} from './AccessControlService';

function RoleEditor({
  role,
  permissions,
  onSaved,
  onDeleted,
}: {
  role: Role;
  permissions: Permission[];
  onSaved: (role: Role) => void;
  onDeleted: (id: string) => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set(role.permissions));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const readOnly = role.name === 'admin';
  const dirty = selected.size !== role.permissions.length || role.permissions.some((p) => !selected.has(p));

  const toggle = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const save = async () => {
    setIsSaving(true);
    setError(null);
    try {
      onSaved(await updateRolePermissions(role.id, [...selected]));
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to save permissions.'));
    } finally {
      setIsSaving(false);
    }
  };

  const remove = async () => {
    setIsSaving(true);
    setError(null);
    try {
      await deleteRole(role.id);
      onDeleted(role.id);
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to delete role.'));
      setIsSaving(false);
    }
  };

  return (
    <div className="border-t border-gray-100 bg-gray-50 px-6 py-4 space-y-3">
      {readOnly && (
        <p className="flex items-center gap-2 text-sm text-gray-500">
          <Lock size={14} /> The admin role always has every permission.
        </p>
      )}
      <div className="grid sm:grid-cols-2 gap-2">
        {permissions.map((p) => (
          <label key={p.key} className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={selected.has(p.key)}
              disabled={readOnly || isSaving}
              onChange={() => toggle(p.key)}
            />
            <span>
              <code className="text-xs">{p.key}</code>
              <span className="block text-gray-500">{p.description}</span>
            </span>
          </label>
        ))}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!readOnly && (
        <div className="flex gap-3">
          <button type="button" onClick={save} disabled={!dirty || isSaving} className="bg-indigo-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50">
            Save permissions
          </button>
          {!role.isSystem && (
            <button type="button" onClick={remove} disabled={isSaving} className="text-sm text-red-600 hover:underline disabled:opacity-50">
              Delete role
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');

  useEffect(() => {
    Promise.all([getRoles(), getPermissions()])
      .then(([r, p]) => {
        setRoles(r);
        setPermissions(p);
      })
      .catch(() => setError('Failed to load roles.'))
      .finally(() => setIsLoading(false));
  }, []);

  const addRole = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const role = await createRole(newName.trim(), newDescription.trim());
      setRoles((rs) => [...rs, role]);
      setExpanded(role.id);
      setNewName('');
      setNewDescription('');
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to create role.'));
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Roles</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        {isLoading && <p className="px-6 py-8 text-center text-gray-400">Loading…</p>}
        {roles.map((role) => (
          <div key={role.id} className="border-b border-gray-100 last:border-0">
            <button
              type="button"
              onClick={() => setExpanded(expanded === role.id ? null : role.id)}
              className="w-full flex items-center gap-3 px-6 py-3 text-left hover:bg-gray-50"
            >
              {expanded === role.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              <span className="font-medium capitalize w-32">{role.name}</span>
              <span className="flex-1 text-sm text-gray-500">{role.description}</span>
              <span className="text-sm text-gray-500 w-32">{role.permissions.length} permissions</span>
              <span className="text-sm text-gray-500 w-20">{role.userCount} users</span>
              {role.isSystem && <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">built-in</span>}
            </button>
            {expanded === role.id && (
              <RoleEditor
                role={role}
                permissions={permissions}
                onSaved={(updated) => setRoles((rs) => rs.map((r) => (r.id === updated.id ? updated : r)))}
                onDeleted={(id) => {
                  setRoles((rs) => rs.filter((r) => r.id !== id));
                  setExpanded(null);
                }}
              />
            )}
          </div>
        ))}
      </div>
      <form onSubmit={addRole} className="bg-white rounded-xl shadow p-4 flex gap-3 flex-wrap items-end">
        <label className="flex flex-col text-sm text-gray-500">
          New role
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. auditor" pattern="[a-z][a-z0-9_-]*" className="border border-gray-300 rounded-lg px-3 py-1.5 text-gray-900" />
        </label>
        <label className="flex flex-col text-sm text-gray-500 flex-1 min-w-48">
          Description
          <input value={newDescription} onChange={(e) => setNewDescription(e.target.value)} className="border border-gray-300 rounded-lg px-3 py-1.5 text-gray-900" />
        </label>
        <button type="submit" disabled={newName.trim().length < 2} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
          Create role
        </button>
      </form>
    </div>
  );
}
