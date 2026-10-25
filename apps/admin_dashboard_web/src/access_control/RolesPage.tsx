import { useEffect, useState, type FormEvent } from 'react';
import { ChevronDown, ChevronRight, Lock } from 'lucide-react';
import ConfirmDialog from '../components/ConfirmDialog';
import { useToast } from '../components/Toast';
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
  const notify = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set(role.permissions));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
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
      const updated = await updateRolePermissions(role.id, [...selected]);
      onSaved(updated);
      notify(`Permissions saved for ${role.name}.`);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save permissions.'));
    } finally {
      setIsSaving(false);
    }
  };

  const remove = async () => {
    await deleteRole(role.id);
    onDeleted(role.id);
    notify(`Role ${role.name} deleted.`);
  };

  return (
    <div id={`role-${role.id}`} className="border-t border-gray-100 bg-gray-50 px-4 sm:px-6 py-4 space-y-3">
      {readOnly && (
        <p className="flex items-center gap-2 text-sm text-gray-600">
          <Lock size={14} aria-hidden="true" /> The admin role always has every permission.
        </p>
      )}
      <fieldset>
        <legend className="sr-only">Permissions for {role.name}</legend>
        <div className="grid sm:grid-cols-2 gap-2">
          {permissions.map((p) => (
            <label key={p.key} className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5" checked={selected.has(p.key)} disabled={readOnly || isSaving} onChange={() => toggle(p.key)} />
              <span>
                <code className="text-xs">{p.key}</code>
                <span className="block text-gray-600">{p.description}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {!readOnly && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={save}
            disabled={!dirty || isSaving}
            className="bg-indigo-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {isSaving ? 'Saving…' : 'Save permissions'}
          </button>
          {dirty && !isSaving && (
            <>
              <span className="text-sm text-amber-800">Unsaved changes</span>
              <button type="button" onClick={() => setSelected(new Set(role.permissions))} className="text-sm text-gray-700 underline">
                Discard
              </button>
            </>
          )}
          {!role.isSystem && (
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              disabled={isSaving}
              className="ml-auto text-sm font-medium text-red-700 hover:underline disabled:opacity-50"
            >
              Delete role…
            </button>
          )}
        </div>
      )}
      {confirmDelete && (
        <ConfirmDialog title={`Delete the ${role.name} role?`} tone="danger" confirmLabel="Delete role" onConfirm={remove} onCancel={() => setConfirmDelete(false)}>
          <p>
            {role.userCount > 0
              ? `${role.userCount} ${role.userCount === 1 ? 'person has' : 'people have'} this role and will lose its permissions.`
              : 'Nobody has this role at the moment.'}{' '}
            This cannot be undone.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}

export default function RolesPage() {
  const notify = useToast();
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setIsLoading(true);
    setLoadError(null);
    Promise.all([getRoles(), getPermissions()])
      .then(([r, p]) => {
        setRoles(r);
        setPermissions(p);
      })
      .catch(() => setLoadError('Could not load roles.'))
      .finally(() => setIsLoading(false));
  }, [reloadKey]);

  const nameInvalid = newName !== '' && !/^[a-z][a-z0-9_-]+$/.test(newName);

  const addRole = async (event: FormEvent) => {
    event.preventDefault();
    if (nameInvalid || newName.length < 2) return;
    setCreateError(null);
    setCreating(true);
    try {
      const role = await createRole(newName.trim(), newDescription.trim());
      setRoles((rs) => [...rs, role]);
      setExpanded(role.id);
      setNewName('');
      setNewDescription('');
      notify(`Role ${role.name} created. Choose its permissions below.`);
    } catch (err) {
      setCreateError(apiErrorMessage(err, 'Could not create the role.'));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Roles</h1>
        <p className="text-sm text-gray-600">Choose what each staff role can see and do. Select a role to edit its permissions.</p>
      </div>
      {loadError && (
        <p role="alert" className="text-sm text-red-700">
          {loadError}{' '}
          <button type="button" onClick={() => setReloadKey((k) => k + 1)} className="font-medium underline">
            Try again
          </button>
        </p>
      )}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        {isLoading && <p className="px-6 py-8 text-center text-gray-500">Loading…</p>}
        {roles.map((role) => {
          const isOpen = expanded === role.id;
          return (
            <div key={role.id} className="border-b border-gray-100 last:border-0">
              <h2>
                <button
                  type="button"
                  aria-expanded={isOpen}
                  aria-controls={`role-${role.id}`}
                  onClick={() => setExpanded(isOpen ? null : role.id)}
                  className="w-full flex flex-wrap sm:flex-nowrap items-center gap-x-3 gap-y-1 px-4 sm:px-6 py-3 text-left hover:bg-gray-50"
                >
                  {isOpen ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
                  <span className="font-medium capitalize text-gray-900 sm:w-32">{role.name}</span>
                  {role.isSystem && <span className="sm:order-last text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full">built-in</span>}
                  <span className="basis-full sm:basis-auto sm:flex-1 pl-7 sm:pl-0 text-sm text-gray-600">{role.description}</span>
                  <span className="pl-7 sm:pl-0 text-sm text-gray-600 sm:w-32">{role.permissions.length} permissions</span>
                  <span className="text-sm text-gray-600 sm:w-20">
                    {role.userCount} {role.userCount === 1 ? 'user' : 'users'}
                  </span>
                </button>
              </h2>
              {isOpen && (
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
          );
        })}
      </div>
      <form onSubmit={addRole} aria-labelledby="new-role-title" className="bg-white rounded-xl shadow p-4 space-y-3">
        <h2 id="new-role-title" className="text-base font-semibold text-gray-900">
          New role
        </h2>
        <div className="flex gap-3 flex-wrap items-start">
          <label className="flex flex-col text-sm text-gray-700">
            Name
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value.toLowerCase())}
              placeholder="e.g. auditor"
              aria-invalid={nameInvalid || undefined}
              aria-describedby="role-name-hint"
              className={`mt-1 border rounded-lg px-3 py-1.5 text-gray-900 ${nameInvalid ? 'border-red-500' : 'border-gray-300'}`}
              autoComplete="off"
            />
            <span id="role-name-hint" className={`mt-1 text-xs ${nameInvalid ? 'text-red-700' : 'text-gray-500'}`}>
              Lowercase letters, digits, - or _
            </span>
          </label>
          <label className="flex flex-col text-sm text-gray-700 flex-1 min-w-48">
            Description
            <input
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              placeholder="What this role is for"
              className="mt-1 border border-gray-300 rounded-lg px-3 py-1.5 text-gray-900"
            />
          </label>
          <button
            type="submit"
            disabled={newName.trim().length < 2 || nameInvalid || creating}
            className="mt-6 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {creating ? 'Creating…' : 'Create role'}
          </button>
        </div>
        {createError && (
          <p role="alert" className="text-sm text-red-700">
            {createError}
          </p>
        )}
      </form>
    </div>
  );
}
