import { useEffect, useState, type FormEvent } from 'react';
import { useSelector } from 'react-redux';
import { Plus, UserCheck, UserX } from 'lucide-react';
import type { RootState } from '../state/store';
import type { StaffMember } from '../types';
import { createStaffMember, getStaff, updateStaffMember } from '../services/shopService';
import { apiErrorMessage } from '../services/format';
import { useShopServices } from '../hooks/useShopServices';
import StaffSchedule from '../components/StaffSchedule';

function AddStaffForm({ onSubmit, onClose }: {
  onSubmit: (values: { name: string; email: string; phone: string; role: string; userId: string }) => Promise<void>;
  onClose: () => void;
}) {
  const [values, setValues] = useState({ name: '', email: '', phone: '', role: 'staff', userId: '' });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!values.name.trim()) return setError('Name is required');
    setSaving(true);
    setError(null);
    try {
      await onSubmit({ ...values, name: values.name.trim() });
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not add the staff member'));
    } finally {
      setSaving(false);
    }
  };

  const input = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500';
  const field = (key: keyof typeof values, label: string, type = 'text') => (
    <label className="text-sm text-gray-700">
      {label}
      <input aria-label={label} type={type} value={values[key]} onChange={(e) => setValues({ ...values, [key]: e.target.value })} className={input} />
    </label>
  );

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow p-4 grid sm:grid-cols-2 gap-3">
      <h2 className="sm:col-span-2 font-semibold text-gray-900">New staff member</h2>
      {field('name', 'Name')}
      {field('role', 'Role')}
      {field('email', 'Email', 'email')}
      {field('phone', 'Phone', 'tel')}
      {field('userId', 'Provider account ID (to assign bookings)')}
      {error && <p className="sm:col-span-2 text-xs text-red-500">{error}</p>}
      <div className="sm:col-span-2 flex gap-2 justify-end">
        <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100">Cancel</button>
        <button type="submit" disabled={saving} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
          {saving ? 'Saving…' : 'Add'}
        </button>
      </div>
    </form>
  );
}

export default function StaffPage() {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const { serviceNames } = useShopServices();
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!shopId) return;
    getStaff(shopId)
      .then(setStaff)
      .catch((err: unknown) => setError(apiErrorMessage(err, 'Could not load staff')))
      .finally(() => setIsLoading(false));
  }, [shopId]);

  const selected = staff.find((m) => m.id === selectedId) ?? null;

  const toggleActive = async (member: StaffMember) => {
    try {
      setError(null);
      const updated = await updateStaffMember(member.id, { isActive: !member.isActive });
      setStaff((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not update the staff member'));
    }
  };

  const add = async (values: { name: string; email: string; phone: string; role: string; userId: string }) => {
    if (!shopId) return;
    const created = await createStaffMember(shopId, values);
    setStaff((prev) => [...prev, created]);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Staff</h1>
        <button onClick={() => setAdding(true)} className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700">
          <Plus size={16} /> Add Staff
        </button>
      </div>
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {adding && <AddStaffForm onSubmit={add} onClose={() => setAdding(false)} />}
      {isLoading ? <p className="text-gray-500">Loading staff…</p> : (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl shadow divide-y divide-gray-100">
            {staff.map((member) => (
              <div key={member.id} className={`flex items-center gap-3 px-4 py-3 hover:bg-gray-50 ${selectedId === member.id ? 'bg-indigo-50' : ''}`}>
                <button onClick={() => setSelectedId(member.id)} className="flex flex-1 items-center gap-3 text-left">
                  <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center font-semibold text-indigo-600">
                    {member.name.charAt(0)}
                  </div>
                  <div className="flex-1">
                    <p className={`font-medium ${member.isActive ? 'text-gray-900' : 'text-gray-400 line-through'}`}>{member.name}</p>
                    <p className="text-xs text-gray-500 capitalize">{member.role}</p>
                  </div>
                </button>
                <button onClick={() => toggleActive(member)} title={member.isActive ? 'Deactivate' : 'Reactivate'}>
                  {member.isActive ? <UserCheck size={16} className="text-green-500" /> : <UserX size={16} className="text-gray-400" />}
                </button>
              </div>
            ))}
            {staff.length === 0 && <p className="px-4 py-10 text-center text-gray-400">No staff yet.</p>}
          </div>
          <div>
            {selected ? (
              <StaffSchedule staffMember={selected} serviceNames={serviceNames} />
            ) : (
              <div className="bg-white rounded-2xl shadow p-8 text-center text-gray-400">
                Select a staff member to view their schedule
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
