import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { format, startOfWeek, addDays, isToday } from 'date-fns';
import type { RootState } from '../state/store';
import type { Booking, StaffMember } from '../types';
import { byScheduledAt, getShopBookings } from '../services/bookingService';

interface StaffScheduleProps {
  staffMember: StaffMember;
  serviceNames: Record<string, string>;
}

/** This week's bookings assigned to the staff member's provider account. */
export default function StaffSchedule({ staffMember, serviceNames }: StaffScheduleProps) {
  const shopId = useSelector((state: RootState) => state.auth.shop?.id);
  const [schedule, setSchedule] = useState<Booking[] | null>(null);
  const [failed, setFailed] = useState(false);
  const weekStart = startOfWeek(new Date(), { weekStartsOn: 1 });
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const from = format(weekStart, 'yyyy-MM-dd');
  const to = format(addDays(weekStart, 6), 'yyyy-MM-dd');
  const providerId = staffMember.userId;

  useEffect(() => {
    if (!shopId || !providerId) return;
    let cancelled = false;
    setSchedule(null);
    setFailed(false);
    getShopBookings(shopId, { providerId, dateFrom: from, dateTo: to, perPage: 100 })
      .then((page) => {
        if (!cancelled) setSchedule(page.data.filter((b) => b.status !== 'CANCELLED').sort(byScheduledAt));
      })
      .catch(() => {
        if (!cancelled) {
          setSchedule([]);
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [shopId, providerId, from, to]);

  const entriesFor = (day: Date) =>
    (schedule ?? []).filter((b) => format(new Date(b.scheduledAt), 'yyyy-MM-dd') === format(day, 'yyyy-MM-dd'));
  const label = (b: Booking) => serviceNames[b.serviceId] ?? b.bookingNumber;

  return (
    <section aria-labelledby="schedule-heading" className="bg-white rounded-2xl shadow p-4">
      <h2 id="schedule-heading" className="font-semibold text-gray-900 mb-3">
        {staffMember.name} · week of {format(weekStart, 'd MMM')}
      </h2>
      {!providerId ? (
        <p className="text-sm text-gray-600">
          Link {staffMember.name}'s staff app account (Edit → Staff app account ID) to assign bookings and see them here.
        </p>
      ) : schedule === null ? (
        <p role="status" className="text-sm text-gray-500">
          Loading…
        </p>
      ) : failed ? (
        <p role="alert" className="text-sm text-red-700">
          Could not load this week's bookings.
        </p>
      ) : (
        <>
          {/* Phone: a list of the days that have bookings. */}
          <ul className="sm:hidden space-y-3">
            {days.filter((d) => entriesFor(d).length > 0).map((day) => (
              <li key={day.toISOString()}>
                <p className={`text-xs font-semibold uppercase ${isToday(day) ? 'text-indigo-700' : 'text-gray-500'}`}>
                  {isToday(day) ? 'Today' : format(day, 'EEE d MMM')}
                </p>
                <ul className="mt-1 space-y-1">
                  {entriesFor(day).map((b) => (
                    <li key={b.id} className="text-sm bg-indigo-50 text-indigo-900 rounded-lg px-3 py-2">
                      <span className="font-medium">{format(new Date(b.scheduledAt), 'h:mm a')}</span> · {label(b)}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
            {schedule.length === 0 && <li className="text-sm text-gray-500">No bookings this week.</li>}
          </ul>
          {/* Larger screens: the whole week. */}
          <div className="hidden sm:grid grid-cols-7 gap-1">
            {days.map((day) => (
              <div key={day.toISOString()} className={`min-h-[80px] rounded-lg ${isToday(day) ? 'bg-indigo-50/50' : ''}`}>
                <p className={`text-xs font-medium text-center ${isToday(day) ? 'text-indigo-700' : 'text-gray-600'}`}>{format(day, 'EEE')}</p>
                <p className="text-xs text-gray-500 text-center mb-2">{format(day, 'd')}</p>
                {entriesFor(day).map((b) => (
                  <div key={b.id} className="bg-indigo-100 text-indigo-900 text-[11px] rounded px-1 py-0.5 mb-0.5 truncate" title={`${format(new Date(b.scheduledAt), 'h:mm a')} ${label(b)}`}>
                    {format(new Date(b.scheduledAt), 'h:mma')} {label(b)}
                  </div>
                ))}
              </div>
            ))}
          </div>
          {schedule.length === 0 && <p className="hidden sm:block text-sm text-gray-500 mt-2">No bookings this week.</p>}
        </>
      )}
    </section>
  );
}
