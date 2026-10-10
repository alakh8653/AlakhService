import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { format, startOfWeek, addDays } from 'date-fns';
import type { RootState } from '../state/store';
import type { Booking, StaffMember } from '../types';
import { getShopBookings } from '../services/bookingService';

interface StaffScheduleProps {
  staffMember: StaffMember;
  serviceNames: Record<string, string>;
}

/** This week's bookings assigned to the staff member's provider account. */
export default function StaffSchedule({ staffMember, serviceNames }: StaffScheduleProps) {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const [schedule, setSchedule] = useState<Booking[]>([]);
  const weekStart = startOfWeek(new Date(), { weekStartsOn: 1 });
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const from = format(weekStart, 'yyyy-MM-dd');
  const to = format(addDays(weekStart, 6), 'yyyy-MM-dd');
  const providerId = staffMember.userId;

  useEffect(() => {
    if (!shopId || !providerId) return;
    let cancelled = false;
    getShopBookings(shopId, { providerId, dateFrom: from, dateTo: to, perPage: 100 })
      .then((page) => {
        if (!cancelled) setSchedule(page.data);
      })
      .catch(() => {
        if (!cancelled) setSchedule([]);
      });
    return () => {
      cancelled = true;
    };
  }, [shopId, providerId, from, to]);

  const entriesFor = (day: Date) =>
    schedule.filter((b) => format(new Date(b.scheduledAt), 'yyyy-MM-dd') === format(day, 'yyyy-MM-dd'));

  return (
    <div className="bg-white rounded-2xl shadow p-4">
      <h3 className="font-semibold text-gray-900 mb-3">
        {staffMember.name}'s Schedule — Week of {format(weekStart, 'MMM d')}
      </h3>
      {!providerId ? (
        <p className="text-sm text-gray-400">
          Link this staff member to their provider account to see the bookings assigned to them.
        </p>
      ) : (
        <div className="grid grid-cols-7 gap-1">
          {days.map((day) => (
            <div key={day.toISOString()} className="min-h-[80px]">
              <p className="text-xs font-medium text-gray-500 text-center mb-1">{format(day, 'EEE')}</p>
              <p className="text-xs text-gray-400 text-center mb-2">{format(day, 'd')}</p>
              {entriesFor(day).map((b) => {
                const title = serviceNames[b.serviceId] ?? b.bookingNumber;
                return (
                  <div key={b.id} className="bg-indigo-100 text-indigo-800 text-[10px] rounded px-1 py-0.5 mb-0.5 truncate" title={title}>
                    {format(new Date(b.scheduledAt), 'h:mma')} {title}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
