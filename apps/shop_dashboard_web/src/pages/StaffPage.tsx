import React, { useEffect, useState } from 'react';
import apiClient from '../services/apiClient';
import type { StaffMember } from '../types';
import StaffSchedule from '../components/StaffSchedule';
import { Plus, UserCheck, UserX } from 'lucide-react';

export default function StaffPage() {
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [selected, setSelected] = useState<StaffMember | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    apiClient.get<{ data: StaffMember[] }>('/staff').then(({ data }) => {
      setStaff(data.data);
    }).finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Staff</h1>
        <button className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700">
          <Plus size={16} /> Add Staff
        </button>
      </div>
      {isLoading ? <p className="text-gray-500">Loading staff…</p> : (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl shadow divide-y divide-gray-100">
            {staff.map((member) => (
              <button key={member.id} onClick={() => setSelected(member)} className={`w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left ${selected?.id === member.id ? 'bg-indigo-50' : ''}`}>
                <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center font-semibold text-indigo-600">
                  {member.name.charAt(0)}
                </div>
                <div className="flex-1">
                  <p className="font-medium text-gray-900">{member.name}</p>
                  <p className="text-xs text-gray-500">{member.role}</p>
                </div>
                {member.isActive ? <UserCheck size={16} className="text-green-500" /> : <UserX size={16} className="text-gray-400" />}
              </button>
            ))}
          </div>
          <div>
            {selected ? (
              <StaffSchedule staffMember={selected} />
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
