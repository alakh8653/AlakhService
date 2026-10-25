import { useState, type FormEvent } from 'react';
import { useSelector } from 'react-redux';
import { Plus, Pencil, Phone, CalendarDays } from 'lucide-react';
import type { RootState } from '../state/store';
import type { StaffMember } from '../types';
import { createStaffMember, updateStaffMember } from '../services/shopService';
import { apiErrorMessage } from '../services/format';
import { useShopServices } from '../hooks/useShopServices';
import { useStaff } from '../hooks/useStaff';
import StaffSchedule from '../components/StaffSchedule';
import Dialog from '../components/Dialog';
import Switch from '../components/Switch';
import { useToast } from '../components/Toast';

export interface StaffValues {
  name: string;
  role: string;
  email: string;
  phone: string;
  userId: string;
}

const ROLE_SUGGESTIONS = ['Stylist', 'Beautician', 'Technician', 'Doctor', 'Receptionist', 'Manager', 'Delivery'];
const input =
  'mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 aria-[invalid=true]:border-red-400';

export function StaffForm({ initial, onSubmit, onClose }: {
  initial?: StaffMember;
  onSubmit: (values: StaffValues) => Promise<void>;
  onClose: () => void;
}) {
  const [values, setValues] = useState<StaffValues>({
    name: initial?.name ?? '',
    role: initial?.role ?? '',
    email: initial?.email ?? '',
    phone: initial?.phone ?? '',
    userId: initial?.userId ?? '',
  });
  const [errors, setErrors] = useState<Partial<Record<keyof StaffValues, string>>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (key: keyof StaffValues) => (e: { target: { value: string } }) => setValues((v) => ({ ...v, [key]: e.target.value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const found: typeof errors = {};
    if (values.name.trim().length < 2) found.name = 'Enter their name';
    if (values.email.trim() && !/^\S+@\S+\.\S+$/.test(values.email.trim())) found.email = 'Enter a valid email, or leave it empty';
    if (values.phone.trim() && !/^\+?[\d\s-]{10,15}$/.test(values.phone.trim())) found.phone = '10-digit mobile, e.g. 98765 43210';
    setErrors(found);
    if (Object.keys(found).length) return;
    setSaving(true);
    setServerError(null);
    try {
      await onSubmit({
        name: values.name.trim(),
        role: values.role.trim() || 'staff',
        email: values.email.trim(),
        phone: values.phone.trim(),
        userId: values.userId.trim(),
      });
      onClose();
    } catch (err) {
      setServerError(apiErrorMessage(err, 'Could not save the staff member'));
    } finally {
      setSaving(false);
    }
  };

  const field = (key: keyof StaffValues, label: string, extra: Record<string, unknown> = {}) => (
    <div>
      <label className="block text-sm font-medium text-gray-700">
        {label}
      <input
        value={values[key]}
        onChange={set(key)}
        className={input}
        aria-invalid={!!errors[key]}
        aria-describedby={errors[key] ? `staff-${key}-error` : undefined}
        {...extra}
        />
      </label>
      {errors[key] && (
        <span id={`staff-${key}-error`} className="block mt-1 text-xs text-red-600">
          {errors[key]}
        </span>
      )}
    </div>
  );

  return (
    <Dialog title={initial ? `Edit ${initial.name}` : 'Add a staff member'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="grid sm:grid-cols-2 gap-3" noValidate>
        {field('name', 'Name', { autoComplete: 'off' })}
        {field('role', 'Role', { list: 'staff-roles', placeholder: 'e.g. Stylist' })}
        <datalist id="staff-roles">
          {ROLE_SUGGESTIONS.map((r) => (
            <option key={r} value={r} />
          ))}
        </datalist>
        {field('phone', 'Mobile', { type: 'tel', inputMode: 'tel', placeholder: '98765 43210' })}
        {field('email', 'Email (optional)', { type: 'email', inputMode: 'email' })}
        <div className="sm:col-span-2">
          {field('userId', 'Staff app account ID (optional)', { 'aria-describedby': 'staff-userId-help', autoCapitalize: 'off', spellCheck: false })}
          <p id="staff-userId-help" className="mt-1 text-xs text-gray-600">
            Needed to assign bookings to them. Ask them to sign up in the AlakhService app as a provider, then copy
            the account ID from their profile.
          </p>
        </div>
        {serverError && (
          <p role="alert" className="sm:col-span-2 text-sm text-red-700 bg-red-50 rounded px-3 py-2">
            {serverError}
          </p>
        )}
        <div className="sm:col-span-2 flex flex-col-reverse sm:flex-row gap-2 sm:justify-end pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2.5 rounded-lg text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="bg-indigo-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {saving ? 'Saving…' : initial ? 'Save changes' : 'Add staff member'}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export default function StaffPage() {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const { serviceNames } = useShopServices();
  const { staff, setStaff, isLoading } = useStaff();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState<StaffMember | 'new' | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const toast = useToast();

  const selected = staff.find((m) => m.id === selectedId) ?? null;
  const replace = (member: StaffMember) => setStaff((prev) => prev.map((m) => (m.id === member.id ? member : m)));

  const toggleActive = async (member: StaffMember) => {
    setToggling(member.id);
    try {
      const updated = await updateStaffMember(member.id, { isActive: !member.isActive });
      replace(updated);
      toast(updated.isActive ? `${updated.name} is active again.` : `${updated.name} is inactive and won't get new bookings.`);
    } catch (err) {
      toast(apiErrorMessage(err, 'Could not update the staff member'), 'error');
    } finally {
      setToggling(null);
    }
  };

  const save = async (values: StaffValues) => {
    if (editing === 'new') {
      if (!shopId) return;
      const created = await createStaffMember(shopId, values);
      setStaff((prev) => [...prev, created]);
      toast(`${created.name} added.`);
    } else if (editing) {
      const updated = await updateStaffMember(editing.id, values);
      replace(updated);
      toast(`${updated.name} saved.`);
    }
  };

  const showSchedule = (id: string) => {
    setSelectedId(id);
    // On a phone the schedule is below the list: bring it into view.
    requestAnimationFrame(() => document.getElementById('staff-schedule')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Staff</h1>
          <p className="text-sm text-gray-500">Who works here, and their bookings this week.</p>
        </div>
        <button type="button" onClick={() => setEditing('new')} className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 whitespace-nowrap">
          <Plus size={16} aria-hidden /> Add staff
        </button>
      </div>
      {editing && (
        <StaffForm
          key={editing === 'new' ? 'new' : editing.id}
          initial={editing === 'new' ? undefined : editing}
          onSubmit={save}
          onClose={() => setEditing(null)}
        />
      )}
      {isLoading ? (
        <div className="bg-white rounded-2xl shadow h-32 animate-pulse" aria-label="Loading staff" />
      ) : (
        <div className="grid md:grid-cols-2 gap-6 items-start">
          {staff.length === 0 ? (
            <div className="bg-white rounded-2xl shadow p-8 text-center space-y-2">
              <p className="text-gray-700 font-medium">No staff yet</p>
              <p className="text-sm text-gray-500">Add the people who serve customers so you can assign bookings to them.</p>
            </div>
          ) : (
            <ul className="bg-white rounded-2xl shadow divide-y divide-gray-100">
              {staff.map((member) => (
                <li key={member.id} className={`flex items-center gap-3 px-4 py-3 ${selectedId === member.id ? 'bg-indigo-50' : ''}`}>
                  <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center font-semibold text-indigo-600 flex-shrink-0" aria-hidden>
                    {member.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`font-medium truncate ${member.isActive ? 'text-gray-900' : 'text-gray-500'}`}>
                      {member.name}
                      {!member.isActive && <span className="ml-2 text-xs font-normal bg-gray-200 text-gray-700 rounded-full px-2 py-0.5">Inactive</span>}
                    </p>
                    <p className="text-xs text-gray-600 capitalize">{member.role}</p>
                    <p className="text-xs mt-0.5 flex flex-wrap gap-x-3 gap-y-1">
                      {member.phone && (
                        <a href={`tel:${member.phone}`} className="flex items-center gap-1 text-indigo-600 hover:underline">
                          <Phone size={12} aria-hidden /> {member.phone}
                        </a>
                      )}
                      {member.userId ? (
                        <span className="text-green-700">Can take bookings</span>
                      ) : (
                        <span className="text-amber-700">No staff app account linked</span>
                      )}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => showSchedule(member.id)}
                      aria-label={`${member.name}'s schedule`}
                      aria-pressed={selectedId === member.id}
                      className="p-2 rounded-lg text-gray-600 hover:bg-gray-100"
                    >
                      <CalendarDays size={18} aria-hidden />
                    </button>
                    <button type="button" onClick={() => setEditing(member)} aria-label={`Edit ${member.name}`} className="p-2 rounded-lg text-indigo-600 hover:bg-indigo-50">
                      <Pencil size={16} aria-hidden />
                    </button>
                    <Switch checked={member.isActive} disabled={toggling === member.id} onChange={() => void toggleActive(member)} label={`${member.name} active`} />
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div id="staff-schedule" className="scroll-mt-4">
            {selected ? (
              <StaffSchedule staffMember={selected} serviceNames={serviceNames} />
            ) : (
              staff.length > 0 && (
                <div className="bg-white rounded-2xl shadow p-6 text-center text-gray-500 text-sm">
                  Tap the calendar next to someone to see their bookings this week.
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}
