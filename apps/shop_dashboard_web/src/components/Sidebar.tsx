import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Calendar, Scissors, Users, BarChart2, Settings } from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
  { to: '/bookings', label: 'Bookings', icon: <Calendar size={18} /> },
  { to: '/services', label: 'Services', icon: <Scissors size={18} /> },
  { to: '/staff', label: 'Staff', icon: <Users size={18} /> },
  { to: '/analytics', label: 'Analytics', icon: <BarChart2 size={18} /> },
  { to: '/settings', label: 'Settings', icon: <Settings size={18} /> },
];

export default function Sidebar() {
  return (
    <aside className="w-60 bg-white border-r border-gray-200 flex flex-col h-full">
      <div className="px-6 py-5 border-b border-gray-100">
        <span className="text-lg font-bold text-indigo-600">AlakhService</span>
        <p className="text-xs text-gray-400 mt-0.5">Shop Dashboard</p>
      </div>
      <nav className="flex-1 py-4 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${
                isActive
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-gray-600 hover:bg-gray-50'
              }`
            }
          >
            {icon}
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
