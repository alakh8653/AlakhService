import React, { useEffect, useState } from 'react';
import { format, startOfWeek, addDays } from 'date-fns';
import type { StaffMember, TimeSlot } from '../types';
import apiClient from '../services/apiClient';

interface StaffScheduleProps {
  staffMember: StaffMember;
}

interface ScheduleEntry {
  id: string;
  title: string;
  timeSlot: TimeSlot;
}

export default function StaffSchedule({ staffMember }: StaffScheduleProps) {
  const [schedule, setSchedule] = useState<ScheduleEntry[]>([]);
  const weekStart = startOfWeek(new Date(), { weekStartsOn: 1 });
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  useEffect(() => {
    const from = format(weekStart, 'yyyy-MM-dd');
    const to = format(addDays(weekStart, 6), 'yyyy-MM-dd');
    apiClient
      .get<{ data: ScheduleEntry[] }>(`/staff/${staffMember.id}/schedule`, { params: { from, to } })
      .then(({ data }) => setSchedule(data.data))
      .catch(() => setSchedule([]));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [staffMember.id]);

  const getEntriesForDay = (day: Date) =>
    schedule.filter((e) => format(new Date(e.timeSlot.start), 'yyyy-MM-dd') === format(day, 'yyyy-MM-dd'));

  return (
    <div className="bg-white rounded-2xl shadow p-4">
      <h3 className="font-semibold text-gray-900 mb-3">
        {staffMember.name}'s Schedule — Week of {format(weekStart, 'MMM d')}
      </h3>
      <div className="grid grid-cols-7 gap-1">
        {days.map((day) => (
          <div key={day.toISOString()} className="min-h-[80px]">
            <p className="text-xs font-medium text-gray-500 text-center mb-1">{format(day, 'EEE')}</p>
            <p className="text-xs text-gray-400 text-center mb-2">{format(day, 'd')}</p>
            {getEntriesForDay(day).map((entry) => (
              <div key={entry.id} className="bg-indigo-100 text-indigo-800 text-[10px] rounded px-1 py-0.5 mb-0.5 truncate" title={entry.title}>
                {format(new Date(entry.timeSlot.start), 'h:mma')} {entry.title}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
