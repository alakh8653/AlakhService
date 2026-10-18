import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { format } from 'date-fns';
import { TrendingUp, Calendar, Users, Star, CheckCircle2, Circle, ArrowRight, Bell } from 'lucide-react';
import type { RootState } from '../state/store';
import { useAnalytics } from '../hooks/useAnalytics';
import { useShopServices } from '../hooks/useShopServices';
import { useStaff } from '../hooks/useStaff';
import { useBookingActions } from '../hooks/useBookingActions';
import RevenueChart from '../components/RevenueChart';
import BookingCard from '../components/BookingCard';
import { byScheduledAt, getShopBookings, inWindow, windowFilters } from '../services/bookingService';
import { apiErrorMessage, formatMoney } from '../services/format';
import type { Booking } from '../types';

interface StatCardProps {
  title: string;
  value: string | number;
  hint?: string;
  icon: ReactNode;
  color: string;
}

function StatCard({ title, value, hint, icon, color }: StatCardProps) {
  return (
    <div className={`bg-white rounded-2xl shadow p-4 md:p-5 flex items-center gap-3 md:gap-4 border-l-4 ${color}`}>
      <div className="text-gray-700" aria-hidden>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-sm text-gray-500">{title}</p>
        <p className="text-xl md:text-2xl font-bold text-gray-900 truncate">{value}</p>
        {hint && <p className="text-xs text-gray-500">{hint}</p>}
      </div>
    </div>
  );
}

const greeting = (hour: number) => (hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening');

const OPEN_STATUSES = new Set<Booking['status']>(['CANCELLED', 'COMPLETED', 'REFUNDED']);

/** Today's bookings (earliest first) and how many bookings are waiting to be confirmed. */
function useToday(shopId: string | undefined) {
  const [today, setToday] = useState<Booking[] | null>(null);
  const [toConfirm, setToConfirm] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!shopId) return;
    let cancelled = false;
    Promise.all([
      getShopBookings(shopId, { ...windowFilters('today'), perPage: 100 }),
      getShopBookings(shopId, { status: 'PENDING', perPage: 1 }),
    ])
      .then(([day, pending]) => {
        if (cancelled) return;
        setToday(day.data.filter((b) => inWindow(b, 'today')).sort(byScheduledAt));
        setToConfirm(pending.total);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(apiErrorMessage(err, "Could not load today's bookings"));
      });
    return () => {
      cancelled = true;
    };
  }, [shopId]);

  const replace = useCallback((b: Booking) => {
    setToday((list) => list?.map((x) => (x.id === b.id ? b : x)) ?? null);
    if (b.status !== 'PENDING') setToConfirm((n) => (n === null ? n : Math.max(0, n - 1)));
  }, []);

  return { today, toConfirm, error, replace };
}

export default function DashboardPage() {
  const shop = useSelector((state: RootState) => state.auth.shop);
  const userName = useSelector((state: RootState) => state.auth.user?.name);
  const { analytics, isLoading, error } = useAnalytics();
  const { services, serviceNames, isLoading: servicesLoading } = useShopServices();
  const { staff, providers, providerName, isLoading: staffLoading } = useStaff();
  const { today, toConfirm, error: todayError, replace } = useToday(shop?.id);
  const actions = useBookingActions(replace, providerName);
  const now = new Date();

  const remaining = today?.filter((b) => !OPEN_STATUSES.has(b.status)) ?? [];
  const setupSteps = [
    { done: services.length > 0, label: 'Add the services you offer, with prices', to: '/services' },
    { done: staff.length > 0, label: 'Add your staff so you can assign bookings', to: '/staff' },
    { done: shop?.latitude != null, label: 'Pin your shop on the map so customers find you', to: '/settings' },
  ];
  const setupDone = setupSteps.every((s) => s.done);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          {greeting(now.getHours())}
          {userName ? `, ${userName.split(' ')[0]}` : ''}
        </h1>
        <p className="text-sm text-gray-500">{format(now, 'EEEE, d MMMM')}</p>
      </div>

      {!setupDone && !servicesLoading && !staffLoading && (
        <section aria-labelledby="setup-heading" className="bg-indigo-50 border border-indigo-100 rounded-2xl p-4 md:p-5">
          <h2 id="setup-heading" className="font-semibold text-gray-900">
            Finish setting up your shop
          </h2>
          <ul className="mt-3 space-y-2">
            {setupSteps.map((s) => (
              <li key={s.to} className="flex items-center gap-2 text-sm">
                {s.done ? (
                  <CheckCircle2 size={18} className="text-green-600 flex-shrink-0" aria-label="Done" />
                ) : (
                  <Circle size={18} className="text-gray-400 flex-shrink-0" aria-label="To do" />
                )}
                {s.done ? (
                  <span className="text-gray-500 line-through">{s.label}</span>
                ) : (
                  <Link to={s.to} className="text-indigo-700 font-medium hover:underline">
                    {s.label}
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {!!toConfirm && (
        <Link
          to="/bookings?status=PENDING"
          className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-2xl p-4 text-amber-900 hover:bg-amber-100"
        >
          <Bell size={20} aria-hidden />
          <span className="flex-1 font-medium">
            {toConfirm === 1 ? '1 booking is' : `${toConfirm} bookings are`} waiting for you to confirm
          </span>
          <ArrowRight size={18} aria-hidden />
        </Link>
      )}

      <section aria-labelledby="today-heading" className="space-y-3">
        <div className="flex items-baseline justify-between gap-2">
          <h2 id="today-heading" className="text-lg font-semibold text-gray-900">
            Today{today ? ` · ${remaining.length} to go` : ''}
          </h2>
          <Link to="/bookings?when=week" className="text-sm font-medium text-indigo-600 hover:underline">
            Next 7 days
          </Link>
        </div>
        {todayError && (
          <p role="alert" className="text-sm text-red-700 bg-red-50 rounded-lg px-3 py-2">
            {todayError}
          </p>
        )}
        {today === null && !todayError ? (
          <div className="bg-white rounded-2xl shadow p-4 h-24 animate-pulse" aria-label="Loading today's bookings" />
        ) : today && today.length === 0 ? (
          <p className="bg-white rounded-2xl shadow p-6 text-center text-gray-500">No bookings today.</p>
        ) : (
          <div className="grid gap-3">
            {today?.map((b) => (
              <BookingCard
                key={b.id}
                booking={b}
                serviceName={serviceNames[b.serviceId]}
                providers={providers}
                onChangeStatus={actions.changeStatus}
                onAssign={actions.assign}
                onCancel={actions.cancel}
                onSetReadyBy={actions.setReadyBy}
              />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="month-heading" className="space-y-3">
        <h2 id="month-heading" className="text-lg font-semibold text-gray-900">
          Last 30 days
        </h2>
        {error && (
          <p role="alert" className="text-red-700 text-sm">
            {error}
          </p>
        )}
        <div className={`grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 ${isLoading && !analytics ? 'animate-pulse' : ''}`}>
          <StatCard title="Bookings" value={analytics?.totalBookings ?? '–'} icon={<Calendar size={24} />} color="border-indigo-500" />
          <StatCard title="Revenue" value={analytics ? formatMoney(analytics.totalRevenue) : '–'} hint="Completed" icon={<TrendingUp size={24} />} color="border-green-500" />
          <StatCard title="Customers" value={analytics?.uniqueCustomers ?? '–'} icon={<Users size={24} />} color="border-blue-500" />
          <StatCard
            title="Rating"
            value={shop?.ratingCount ? `${shop.ratingAvg.toFixed(1)} ★` : 'No ratings'}
            hint={shop?.ratingCount ? `${shop.ratingCount} rating${shop.ratingCount === 1 ? '' : 's'}` : undefined}
            icon={<Star size={24} />}
            color="border-yellow-500"
          />
        </div>
        <div className="bg-white rounded-2xl shadow p-4 md:p-6">
          <div className="flex items-baseline justify-between mb-4">
            <h3 className="font-semibold text-gray-800">Revenue</h3>
            <Link to="/analytics" className="text-sm font-medium text-indigo-600 hover:underline">
              More in Analytics
            </Link>
          </div>
          <RevenueChart data={analytics?.revenueByDay ?? []} />
        </div>
      </section>
    </div>
  );
}
