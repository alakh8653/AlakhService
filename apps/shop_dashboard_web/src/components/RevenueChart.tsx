import { format, parseISO } from 'date-fns';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import type { DailyRevenue } from '../types';
import { formatMoney, formatMoneyShort } from '../services/format';

interface RevenueChartProps {
  data: DailyRevenue[];
}

const dayLabel = (day: string) => format(parseISO(day), 'd MMM');

export default function RevenueChart({ data }: RevenueChartProps) {
  const total = data.reduce((sum, d) => sum + d.revenue, 0);
  if (!data.length || total === 0) {
    return (
      <p className="text-gray-500 text-sm text-center py-8">
        No completed bookings in this period yet. Revenue shows here once bookings are marked complete.
      </p>
    );
  }

  const best = data.reduce((a, b) => (b.revenue > a.revenue ? b : a));
  return (
    <figure
      role="img"
      aria-label={`Revenue by day from ${dayLabel(data[0].date)} to ${dayLabel(data[data.length - 1].date)}: ${formatMoney(total)} in total, best day ${dayLabel(best.date)} with ${formatMoney(best.revenue)}.`}
    >
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tickFormatter={dayLabel} minTickGap={24} tick={{ fontSize: 11, fill: '#6b7280' }} tickLine={false} axisLine={false} />
          <YAxis tickFormatter={(v: number) => formatMoneyShort(v)} width={52} tick={{ fontSize: 11, fill: '#6b7280' }} tickLine={false} axisLine={false} />
          <Tooltip
            labelFormatter={(label) => format(parseISO(String(label)), 'EEE d MMM yyyy')}
            formatter={(value) => [formatMoney(Number(value)), 'Revenue']}
            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.1)' }}
          />
          <Area type="monotone" dataKey="revenue" stroke="#6366f1" strokeWidth={2} fill="url(#revenueGradient)" dot={false} activeDot={{ r: 4 }} />
        </AreaChart>
      </ResponsiveContainer>
    </figure>
  );
}
